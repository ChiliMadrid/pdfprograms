from __future__ import annotations

import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

import fitz
from PIL import Image, ImageChops, ImageDraw, ImageStat


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PDF = ROOT.parent / "CM Strength Dynasty.pdf"
OUTPUT_PDF = ROOT / "output.pdf"
REPORT_DIR = ROOT / "qa-reports"
DIFF_DIR = ROOT / "qa-previews" / "visual-diff"
PUBLISHER_DIR = ROOT / "qa-previews" / "publisher-review"
EXPECTED_PAGES = 93
ZOOM = 0.75
PUBLISHER_PAGES = [2, 3, 4, 5, 6, 8, 10, 14, 15, 21, 22, 28, 29, 36, 37, 44, 50, 57, 61, 64, 71, 78, 85, 86, 91, 93]
REGIONS = {
    "top_header": (0.00, 0.00, 1.00, 0.13),
    "main_header_bar": (0.05, 0.05, 0.95, 0.16),
    "exercise_title_area": (0.05, 0.13, 0.95, 0.34),
    "body_area": (0.05, 0.18, 0.95, 0.78),
    "table_area": (0.05, 0.13, 0.95, 0.48),
    "footer": (0.00, 0.82, 1.00, 1.00),
}


def render_page(doc: fitz.Document, page_number: int) -> Image.Image:
    pix = doc[page_number - 1].get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def rms_diff(a: Image.Image, b: Image.Image) -> float:
    diff = ImageChops.difference(a, b)
    stat = ImageStat.Stat(diff)
    return math.sqrt(sum(value * value for value in stat.rms) / len(stat.rms))


def crop_region(image: Image.Image, region: tuple[float, float, float, float]) -> Image.Image:
    w, h = image.size
    x0, y0, x1, y1 = region
    return image.crop((round(w * x0), round(h * y0), round(w * x1), round(h * y1)))


def heatmap(a: Image.Image, b: Image.Image) -> Image.Image:
    diff = ImageChops.difference(a, b).convert("L")
    diff = diff.point(lambda p: min(255, p * 3))
    red = Image.new("RGB", diff.size, (190, 0, 0))
    white = Image.new("RGB", diff.size, (255, 255, 255))
    return Image.composite(red, white, diff)


def side_by_side(original: Image.Image, output: Image.Image, page: int, score: float) -> Image.Image:
    gap = 18
    label_h = 28
    w, h = original.size
    canvas = Image.new("RGB", (w * 2 + gap, h + label_h), (238, 238, 238))
    canvas.paste(original, (0, label_h))
    canvas.paste(output, (w + gap, label_h))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 7), f"Page {page:03d} original", fill=(0, 0, 0))
    draw.text((w + gap + 8, 7), f"generated | diff score {score:.2f}", fill=(0, 0, 0))
    return canvas


def save_jpg(image: Image.Image, path: Path, quality: int = 78) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, quality=quality, optimize=True)


def classify_page(page: int, region_scores: dict[str, float]) -> list[str]:
    notes: list[str] = []
    if region_scores["main_header_bar"] > 28:
        notes.append("Header/bar region differs strongly; inspect black/gold patch sizing and title placement.")
    if region_scores["table_area"] > 24 and page in {2, 3, 5, 14, 21, 28, 36, 43, 50, 57, 64, 71, 78, 85}:
        notes.append("Table/overview area differs; check table proportions, row heights, borders, and font weight.")
    if region_scores["exercise_title_area"] > 24:
        notes.append("Exercise title/underline area differs; check title coordinates and gold rules.")
    if region_scores["body_area"] > 20:
        notes.append("Body region differs; check text density, font size, and vertical rhythm.")
    if region_scores["footer"] > 22:
        notes.append("Footer/lower-page relationship differs.")
    return notes


def write_contact_sheet(records: list[dict]) -> None:
    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8"><title>Visual Fidelity Contact Sheet</title>',
        "<style>body{font-family:Arial,sans-serif;margin:20px;background:#eee} .grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.card{background:white;border:1px solid #bbb;padding:10px}.score{font-weight:bold}.notes{font-size:12px;color:#333}img{width:100%;display:block;border:1px solid #ddd}</style>",
        "</head><body><h1>Dynasty Visual Fidelity Audit</h1><div class=\"grid\">",
    ]
    for rec in records:
        side = f"page-{rec['page']:03d}-side-by-side.jpg"
        notes = "<br>".join(escape(note) for note in rec["notes"]) or "No automatic note."
        parts.append(
            f"<div class=\"card\"><div class=\"score\">Page {rec['page']:03d}: {rec['score']:.2f}</div>"
            f"<div class=\"notes\">{notes}</div><img src=\"{side}\" alt=\"Page {rec['page']:03d}\"></div>"
        )
    parts.append("</div></body></html>")
    (DIFF_DIR / "contact-sheet.html").write_text("\n".join(parts), encoding="utf-8")


def write_publisher_index(records: list[dict]) -> None:
    by_page = {rec["page"]: rec for rec in records}
    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8"><title>Publisher Review</title>',
        "<style>body{font-family:Arial,sans-serif;margin:20px;background:#f1f1f1}.pair{background:white;margin:0 0 18px;padding:12px;border:1px solid #bbb}.imgs{display:grid;grid-template-columns:1fr 1fr;gap:12px}img{width:100%;border:1px solid #ddd}.notes{font-size:13px;color:#333}</style>",
        "</head><body><h1>Publisher Review / Prepress QA</h1>",
    ]
    for page in PUBLISHER_PAGES:
        rec = by_page[page]
        notes = "<br>".join(escape(note) for note in rec["notes"]) or "Human visual approval required."
        parts.append(
            f"<section class=\"pair\"><h2>Page {page:03d} | visual score {rec['score']:.2f}</h2>"
            f"<div class=\"notes\">{notes}</div><div class=\"imgs\">"
            f"<div><strong>Original</strong><img src=\"page-{page:03d}-original.jpg\"></div>"
            f"<div><strong>Generated</strong><img src=\"page-{page:03d}-generated.jpg\"></div>"
            "</div></section>"
        )
    parts.append("</body></html>")
    (PUBLISHER_DIR / "index.html").write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    REPORT_DIR.mkdir(exist_ok=True)
    DIFF_DIR.mkdir(parents=True, exist_ok=True)
    PUBLISHER_DIR.mkdir(parents=True, exist_ok=True)
    original_doc = fitz.open(SOURCE_PDF)
    output_doc = fitz.open(OUTPUT_PDF)
    records: list[dict] = []

    for page in range(1, EXPECTED_PAGES + 1):
        original = render_page(original_doc, page)
        output = render_page(output_doc, page)
        if original.size != output.size:
            output = output.resize(original.size)
        score = rms_diff(original, output)
        region_scores = {
            name: rms_diff(crop_region(original, region), crop_region(output, region))
            for name, region in REGIONS.items()
        }
        rec = {
            "page": page,
            "score": round(score, 3),
            "region_scores": {name: round(value, 3) for name, value in region_scores.items()},
            "notes": classify_page(page, region_scores),
        }
        records.append(rec)
        save_jpg(side_by_side(original, output, page, score), DIFF_DIR / f"page-{page:03d}-side-by-side.jpg")
        save_jpg(heatmap(original, output), DIFF_DIR / f"page-{page:03d}-diff.jpg", quality=70)
        if page in PUBLISHER_PAGES:
            save_jpg(original, PUBLISHER_DIR / f"page-{page:03d}-original.jpg")
            save_jpg(output, PUBLISHER_DIR / f"page-{page:03d}-generated.jpg")
            save_jpg(side_by_side(original, output, page, score), PUBLISHER_DIR / f"page-{page:03d}-side-by-side.jpg")
            save_jpg(heatmap(original, output), PUBLISHER_DIR / f"page-{page:03d}-diff.jpg", quality=70)

    records.sort(key=lambda item: item["score"], reverse=True)
    write_contact_sheet(records)
    write_publisher_index(records)
    report = {
        "summary": {
            "expected_pages": EXPECTED_PAGES,
            "original_pages": original_doc.page_count,
            "output_pages": output_doc.page_count,
            "worst_pages": [rec["page"] for rec in records[:15]],
            "visual_diff_folder": "qa-previews/visual-diff",
            "publisher_review_folder": "qa-previews/publisher-review",
        },
        "worst_pages": records[:25],
        "pages": sorted(records, key=lambda item: item["page"]),
    }
    (REPORT_DIR / "visual-fidelity.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# Dynasty Visual Fidelity Audit", "", "## Summary", ""]
    for key, value in report["summary"].items():
        md.append(f"- `{key}`: {value}")
    md.extend(["", "## Worst Pages", ""])
    for rec in records[:25]:
        md.append(f"- Page {rec['page']}: score {rec['score']}; regions={rec['region_scores']}")
        for note in rec["notes"]:
            md.append(f"  - {note}")
    (REPORT_DIR / "visual-fidelity.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    original_doc.close()
    output_doc.close()

    print("Visual fidelity audit")
    print("=====================")
    print(f"Pages compared: {EXPECTED_PAGES}")
    print(f"Worst pages: {', '.join(str(rec['page']) for rec in records[:15])}")
    print(f"Visual diff contact sheet: {DIFF_DIR / 'contact-sheet.html'}")
    print(f"Publisher review index: {PUBLISHER_DIR / 'index.html'}")
    print(f"JSON report: {REPORT_DIR / 'visual-fidelity.json'}")
    print(f"Markdown report: {REPORT_DIR / 'visual-fidelity.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
