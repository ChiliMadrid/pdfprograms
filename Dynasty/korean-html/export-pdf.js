const path = require("path");
const { pathToFileURL } = require("url");
const { chromium } = require("playwright");

async function main() {
  const root = __dirname;
  const input = pathToFileURL(path.join(root, "index.html")).href;
  const output = path.join(root, "output.pdf");

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1224, height: 1584 }, deviceScaleFactor: 1 });
  await page.goto(input, { waitUntil: "networkidle" });
  await page.pdf({
    path: output,
    format: "Letter",
    printBackground: true,
    preferCSSPageSize: true,
    margin: { top: "0", right: "0", bottom: "0", left: "0" }
  });
  await browser.close();
  console.log(`Wrote ${output}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
