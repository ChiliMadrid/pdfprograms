from __future__ import annotations

import html
import json
import re
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import fitz


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT.parent
WORKSPACE = ROOT.parents[1]
PDF_PATH = SOURCE_DIR / "CM Strength Dynasty.pdf"
DOCX_PATH = SOURCE_DIR / "CM Strength Dynasty conv.docx"
KOREAN_DOCX_PATH = WORKSPACE / "korean_exports" / "final" / "CM Strength Dynasty conv Korean.docx"
ASSETS = ROOT / "assets" / "pages"

PT_TO_IN = 1 / 72
RENDER_ZOOM = 2


def read_docx_paragraphs(path: Path) -> list[str]:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    paragraphs: list[str] = []
    for para in root.findall(".//w:p", ns):
        text = "".join(t.text or "" for t in para.findall(".//w:t", ns)).strip()
        if text:
            paragraphs.append(re.sub(r"\s+", " ", text))
    return paragraphs


def color_to_hex(value: int | None) -> str:
    if value is None:
        return "#000000"
    return f"#{(value >> 16) & 255:02x}{(value >> 8) & 255:02x}{value & 255:02x}"


def classify_placeholder(text: str, size: float, source: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return ""
    upper = clean.upper()
    if "CM STRENGTH DYNASTY" in upper:
        return "CM STRENGTH DYNASTY"
    if size >= 34:
        return "CM 스트렝스 다이너스티"
    if size >= 18 or (upper == clean and len(clean) > 3):
        return "한국어 섹션 제목"
    if re.fullmatch(r"[\d\s./:%+-]+", clean):
        return clean
    if re.search(r"[가-힣]", source):
        target = max(4, min(70, int(len(clean) * 0.62)))
        return source[:target].rstrip()
    if len(clean) <= 3:
        return clean
    base = "한국어 번역문"
    target = max(4, min(42, int(len(clean) * 0.45)))
    repeated = (base + " ") * ((target // len(base)) + 3)
    return repeated[:target].rstrip()


def span_style(span: dict, bbox: tuple[float, float, float, float]) -> str:
    x0, y0, x1, y1 = bbox
    size = float(span.get("size", 10))
    flags = int(span.get("flags", 0))
    font = span.get("font", "")
    weight = "700" if "Bold" in font or flags & 16 else "400"
    italic = "italic" if "Italic" in font or flags & 2 else "normal"
    color = color_to_hex(span.get("color"))
    width = max(1, x1 - x0)
    height = max(size * 1.1, y1 - y0)
    return (
        f"left:{x0:.3f}pt;top:{y0:.3f}pt;width:{width:.3f}pt;"
        f"height:{height:.3f}pt;font-size:{size:.3f}pt;"
        f"line-height:{height:.3f}pt;font-weight:{weight};font-style:{italic};"
        f"color:{color};"
    )


def extract_spans(page: fitz.Page, docx_paras: list[str], para_index: int) -> tuple[list[dict], int]:
    raw = page.get_text("rawdict")
    spans: list[dict] = []
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                chars = span.get("chars", [])
                text = "".join(ch.get("c", "") for ch in chars)
                if not text.strip():
                    continue
                bbox = tuple(float(v) for v in span["bbox"])
                source = docx_paras[para_index] if para_index < len(docx_paras) else ""
                if len(text.strip()) > 8 and para_index < len(docx_paras):
                    para_index += 1
                spans.append(
                    {
                        "text": classify_placeholder(text, float(span.get("size", 10)), source),
                        "source": source,
                        "style": span_style(span, bbox),
                        "bbox": bbox,
                    }
                )
    return spans, para_index


def render_textless_page(src: fitz.Document, page_number: int, out_path: Path) -> None:
    single = fitz.open()
    single.insert_pdf(src, from_page=page_number, to_page=page_number)
    page = single[0]
    raw = page.get_text("rawdict")
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if not "".join(ch.get("c", "") for ch in span.get("chars", [])).strip():
                    continue
                rect = fitz.Rect(span["bbox"])
                rect.x0 -= 0.35
                rect.y0 -= 0.25
                rect.x1 += 0.35
                rect.y1 += 0.25
                page.add_redact_annot(rect, fill=None, cross_out=False)
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE, text=fitz.PDF_REDACT_TEXT_REMOVE)
    pix = page.get_pixmap(matrix=fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM), alpha=False)
    pix.save(out_path)
    single.close()


def build_html(pages: list[dict], metadata: dict) -> str:
    parts = [
        "<!doctype html>",
        '<html lang="ko">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>CM Strength Dynasty Korean PDF Source</title>",
        '<link rel="stylesheet" href="styles.css">',
        "</head>",
        "<body>",
        f"<!-- Generated from {html.escape(str(PDF_PATH.name))} and {html.escape(str(DOCX_PATH.name))}. -->",
    ]
    for page in pages:
        w = page["width"]
        h = page["height"]
        parts.append(
            f'<section class="pdf-page" data-page="{page["number"]}" '
            f'style="width:{w:.3f}pt;height:{h:.3f}pt">'
        )
        parts.append(
            f'<img class="page-art" src="assets/pages/page-{page["number"]:03d}-background.png" alt="">'
        )
        for span in page["spans"]:
            text = html.escape(span["text"])
            source = html.escape(span["source"])
            parts.append(f'<span class="ko-text" data-source="{source}" style="{span["style"]}">{text}</span>')
        parts.append("</section>")
    parts.extend(["</body>", "</html>"])
    return "\n".join(parts)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    raw_docx_paras = read_docx_paragraphs(DOCX_PATH)
    visible_docx_path = KOREAN_DOCX_PATH if KOREAN_DOCX_PATH.exists() else DOCX_PATH
    visible_docx_paras = read_docx_paragraphs(visible_docx_path)
    pdf = fitz.open(PDF_PATH)
    pages: list[dict] = []
    para_index = 0

    for i, page in enumerate(pdf):
        number = i + 1
        bg = ASSETS / f"page-{number:03d}-background.png"
        render_textless_page(pdf, i, bg)
        spans, para_index = extract_spans(page, visible_docx_paras, para_index)
        pages.append(
            {
                "number": number,
                "width": page.rect.width,
                "height": page.rect.height,
                "background": bg.name,
                "spans": spans,
            }
        )

    metadata = {
        "source_pdf": str(PDF_PATH),
        "source_docx": str(DOCX_PATH),
        "visible_text_docx": str(visible_docx_path),
        "page_count": pdf.page_count,
        "docx_paragraph_count": len(raw_docx_paras),
        "visible_docx_paragraph_count": len(visible_docx_paras),
        "mapped_docx_paragraphs": para_index,
        "render_zoom": RENDER_ZOOM,
    }
    (ROOT / "index.html").write_text(build_html(pages, metadata), encoding="utf-8")
    (ROOT / "assets" / "manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    pdf.close()
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
