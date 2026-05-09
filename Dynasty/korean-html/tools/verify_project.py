from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PAGES = 93
EXPECTED_WIDTH = 612
EXPECTED_HEIGHT = 792


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def main() -> None:
    index_path = ROOT / "index.html"
    manifest_path = ROOT / "assets" / "manifest.json"
    pages_dir = ROOT / "assets" / "pages"
    output_path = ROOT / "output.pdf"

    if not index_path.exists() or index_path.stat().st_size == 0:
        fail("index.html is missing or empty")
    if not manifest_path.exists():
        fail("assets/manifest.json is missing")
    if not output_path.exists() or output_path.stat().st_size < 1_000_000:
        fail("output.pdf is missing or unexpectedly small")

    html = index_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    page_sections = len(re.findall(r'<section class="pdf-page"', html))
    backgrounds = len(list(pages_dir.glob("page-*-background.png")))

    checks = {
        "index_size_bytes": index_path.stat().st_size,
        "pdf_page_sections": page_sections,
        "background_pngs": backgrounds,
        "manifest_page_count": manifest.get("page_count"),
        "mapped_docx_paragraphs": manifest.get("mapped_docx_paragraphs"),
        "korean_docx_found": manifest.get("korean_docx_found"),
    }

    if page_sections != EXPECTED_PAGES:
        fail(f"expected {EXPECTED_PAGES} .pdf-page sections, found {page_sections}")
    if backgrounds != EXPECTED_PAGES:
        fail(f"expected {EXPECTED_PAGES} page backgrounds, found {backgrounds}")
    if manifest.get("page_count") != EXPECTED_PAGES:
        fail(f"manifest page_count is {manifest.get('page_count')}, expected {EXPECTED_PAGES}")
    if manifest.get("korean_docx_found") is not True:
        fail("Korean DOCX was not found")

    forbidden = ["TODO_TRANSLATE", "한국어 번역문", "한국어 섹션 제목"]
    found_forbidden = [token for token in forbidden if token in html]
    if found_forbidden:
        fail(f"placeholder text remains in index.html: {', '.join(found_forbidden)}")

    doc = fitz.open(output_path)
    if doc.page_count != EXPECTED_PAGES:
        fail(f"output.pdf has {doc.page_count} pages, expected {EXPECTED_PAGES}")
    for i, page in enumerate(doc):
        rect = page.rect
        if round(rect.width) != EXPECTED_WIDTH or round(rect.height) != EXPECTED_HEIGHT:
            fail(f"page {i + 1} size is {rect.width}x{rect.height}, expected {EXPECTED_WIDTH}x{EXPECTED_HEIGHT}")
        pix = page.get_pixmap(matrix=fitz.Matrix(0.08, 0.08), alpha=False)
        samples = pix.samples
        if samples and min(samples) > 248:
            fail(f"page {i + 1} appears blank")
    doc.close()

    checks["output_size_bytes"] = output_path.stat().st_size
    checks["output_pages"] = EXPECTED_PAGES
    print(json.dumps(checks, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
