const fs = require("fs");
const path = require("path");

const port = process.env.CDP_PORT;
const root = process.env.WORKDIR || process.cwd();

const files = [
  {
    html: path.join(root, "EBook/html-edition/index.html"),
    pdf: path.join(root, "EBook/html-edition/cm-strength-korea-performance-nutrition-manual-en-proof.pdf"),
  },
  {
    html: path.join(root, "EBook/html-edition/cm-strength-korea-performance-nutrition-manual-ko.html"),
    pdf: path.join(root, "EBook/html-edition/cm-strength-korea-performance-nutrition-manual-ko-proof.pdf"),
  },
];

async function openTarget(url) {
  let res = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, { method: "PUT" });
  if (!res.ok) res = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`);
  if (!res.ok) throw new Error(`open target failed ${res.status} ${await res.text()}`);
  return res.json();
}

function cdp(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    let id = 0;
    const pending = new Map();
    const timer = setTimeout(() => reject(new Error(`websocket open timeout: ${wsUrl}`)), 10000);

    ws.onopen = () =>
      {
        clearTimeout(timer);
        resolve({
        send(method, params = {}) {
          return new Promise((res, rej) => {
            const msg = { id: ++id, method, params };
            const timeout = setTimeout(() => {
              pending.delete(msg.id);
              rej(new Error(`CDP timeout: ${method}`));
            }, method === "Page.printToPDF" ? 60000 : 15000);
            pending.set(msg.id, {
              res: (value) => {
                clearTimeout(timeout);
                res(value);
              },
              rej: (error) => {
                clearTimeout(timeout);
                rej(error);
              },
            });
            ws.send(JSON.stringify(msg));
          });
        },
        close() {
          ws.close();
        },
      });
      };
    ws.onerror = () => {
      clearTimeout(timer);
      reject(new Error("websocket error"));
    };
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && pending.has(msg.id)) {
        const { res, rej } = pending.get(msg.id);
        pending.delete(msg.id);
        msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result);
      }
    };
  });
}

async function waitLoad(client) {
  for (let i = 0; i < 80; i++) {
    const r = await client.send("Runtime.evaluate", {
      expression: "document.readyState",
      returnByValue: true,
    });
    if (r.result.value === "complete") return;
    await new Promise((res) => setTimeout(res, 100));
  }
}

const checkExpr = `(() => {
  const pages = [...document.querySelectorAll('section.page')];
  const bad = [], tableIssues = [], footerIssues = [], pageContentIssues = [], orphanHeadings = [], splitRisks = [];
  for (const [i,page] of pages.entries()) {
    const pr = page.getBoundingClientRect();
    const content = page.querySelector(':scope > .page-content');
    const footer = page.querySelector(':scope > .footer');
    const structuralPage = page.classList.contains('author-spread') || page.classList.contains('part-divider');
    if (!page.classList.contains('cover-page') && !footer) footerIssues.push({page:i+1, issue:'missing footer'});
    if (footer && !structuralPage) {
      const fr = footer.getBoundingClientRect();
      if (fr.bottom > pr.bottom - 3) footerIssues.push({page:i+1, issue:'footer outside page', delta: Math.round(fr.bottom - pr.bottom)});
      if (content) {
        const children = [...content.querySelectorAll('*')].filter(el => getComputedStyle(el).display !== 'none');
        const maxBottom = Math.max(content.getBoundingClientRect().top, ...children.map(el => el.getBoundingClientRect().bottom));
        if (maxBottom > fr.top - 8) pageContentIssues.push({page:i+1, id:page.id, cls:page.className, overBy: Math.round(maxBottom - fr.top + 8), title:(page.querySelector('h1,h2')?.textContent||'').trim().slice(0,80)});
      }
    }
    if (content && !structuralPage && content.scrollHeight > content.clientHeight + 3) {
      bad.push({page:i+1, id:page.id, cls:page.className, scrollOverflow: Math.round(content.scrollHeight - content.clientHeight), title:(page.querySelector('h1,h2')?.textContent||'').trim().slice(0,80)});
    }
    for (const h of page.querySelectorAll('h1,h2,h3')) {
      const hr = h.getBoundingClientRect();
      if (content && !structuralPage && hr.bottom > content.getBoundingClientRect().bottom - 36) orphanHeadings.push({page:i+1, text:h.textContent.trim().slice(0,70)});
    }
    for (const keep of page.querySelectorAll('.figure-block,.phase-table,.coach-panel,.warning-box,.satiety-plot-block,.meal-grid,.coach-grid,.cta-grid,.action-list')) {
      const kr = keep.getBoundingClientRect();
      if (kr.bottom > pr.bottom - 58 || kr.top < pr.top) splitRisks.push({page:i+1, cls:keep.className, text:(keep.querySelector('h3')?.textContent||'').trim().slice(0,60)});
    }
  }
  for (const span of document.querySelectorAll('.phase-row span, .toc-chapter, .toc-part')) {
    if (span.scrollWidth > span.clientWidth + 2) tableIssues.push({text:span.textContent.trim().slice(0,90), overBy:Math.round(span.scrollWidth-span.clientWidth)});
  }
  const text = document.body.textContent;
  const firstP = document.querySelector('p, li, .phase-row span');
  const pageById = new Map();
  pages.forEach((page, index) => {
    if (page.id) pageById.set(page.id, index + 1);
    page.querySelectorAll('[id]').forEach(el => {
      if (!pageById.has(el.id)) pageById.set(el.id, index + 1);
    });
  });
  const tocMismatches = [...document.querySelectorAll('.toc-chapter[href^="#"]')].map(link => {
    const id = link.getAttribute('href').slice(1);
    const actual = pageById.get(id);
    const shownText = link.querySelector('.toc-page')?.textContent || '';
    const shown = Number((shownText.match(/\\d+/) || [])[0]);
    return actual && shown && actual !== shown ? {text: link.textContent.trim().slice(0,90), shown, actual} : null;
  }).filter(Boolean);
  const tocActualPages = [...document.querySelectorAll('.toc-chapter[href^="#"]')].map(link => {
    const id = link.getAttribute('href').slice(1);
    return {href: link.getAttribute('href'), actual: pageById.get(id) || null};
  });
  return {
    lang: document.documentElement.lang,
    pages: pages.length,
    tocLinks: document.querySelectorAll('.toc-chapter').length,
    tocMissingPages: [...document.querySelectorAll('.toc-chapter')].filter(a=>!a.querySelector('.toc-page')).length,
    qrElements: document.querySelectorAll('.qr-grid,.qr-placeholder').length,
    cmAllCapsOccurrences: (text.match(/CM STRENGTH/g)||[]).length,
    badBuildPhraseOccurrences: (text.match(/Build Beyond Basics/g)||[]).length,
    footerIssues,
    pageContentIssues: pageContentIssues.slice(0,20),
    scrollIssues: bad.slice(0,20),
    orphanHeadings: orphanHeadings.slice(0,20),
    splitRisks: splitRisks.slice(0,20),
    tableIssues: tableIssues.slice(0,20),
    tocMismatches,
    tocActualPages,
    computedHyphens: firstP ? getComputedStyle(firstP).hyphens : null,
    computedWordBreak: firstP ? getComputedStyle(firstP).wordBreak : null
  };
})()`;

(async () => {
  if (!port) throw new Error("CDP_PORT is required");
  if (process.env.QA_VERBOSE) console.error(`checking ${files.length} files on port ${port}`);
  const results = [];
  for (const file of files) {
    if (process.env.QA_VERBOSE) console.error(`opening ${path.basename(file.html)}`);
    const url = `file:///${file.html.replace(/\\/g, "/").replace(/ /g, "%20")}`;
    const target = await openTarget(url);
    if (process.env.QA_VERBOSE) console.error(`target ${target.id || "unknown"}`);
    const client = await cdp(target.webSocketDebuggerUrl);
    if (process.env.QA_VERBOSE) console.error("cdp connected");
    await client.send("Page.enable");
    await client.send("Runtime.enable");
    if (process.env.QA_VERBOSE) console.error("runtime enabled");
    await waitLoad(client);
    if (process.env.QA_VERBOSE) console.error("page loaded");
    await client.send("Emulation.setEmulatedMedia", { media: "print" });
    const layout = await client.send("Runtime.evaluate", { expression: checkExpr, returnByValue: true });
    if (process.env.QA_VERBOSE) console.error("layout checked");
    if (!process.env.SKIP_PDF) {
      const pdf = await client.send("Page.printToPDF", { printBackground: true, preferCSSPageSize: true });
      if (process.env.QA_VERBOSE) console.error("pdf printed");
      fs.writeFileSync(file.pdf, Buffer.from(pdf.data, "base64"));
    }
    results.push({
      file: path.basename(file.html),
      pdf: path.basename(file.pdf),
      ...layout.result.value,
      pdfBytes: fs.existsSync(file.pdf) ? fs.statSync(file.pdf).size : 0,
    });
    client.close();
  }
  process.stdout.write(`${JSON.stringify(results, null, 2)}\n`);
})().catch((err) => {
  console.error(err.stack || err);
  process.exit(1);
});
