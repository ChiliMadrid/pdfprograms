from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path
from xml.sax.saxutils import escape

import fitz


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
SOURCE_PDF = ROOT.parent / "CM Strength Dynasty.pdf"
KOREAN_PDF = WORKSPACE / "korean_exports" / "final" / "CM Strength Dynasty conv Korean.pdf"
OUTPUT_PDF = ROOT / "output.pdf"
INDEX_HTML = ROOT / "index.html"
REPORT_DIR = ROOT / "qa-reports"
PREVIEW_DIR = ROOT / "qa-previews" / "all-pages"
EXPECTED_PAGES = 93
WORKOUT_PAGES = (
    set(range(6, 14))
    | set(range(15, 21))
    | set(range(22, 28))
    | set(range(29, 36))
    | set(range(37, 43))
    | set(range(44, 50))
    | set(range(51, 57))
    | set(range(58, 64))
    | set(range(65, 71))
    | set(range(72, 78))
    | set(range(79, 85))
    | set(range(86, 93))
)
WEEKLY_TABLE_PAGES = {5, 14, 21, 28, 36, 43, 50, 57, 64, 71, 78, 85}
ALLOWLIST = ["CM Strength", "Dynasty", "RPE", "PPL", "URL", "reps", "sets", "kg", "lb", "lbs"]


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def page_lines(doc: fitz.Document, page_index: int) -> list[str]:
    return [clean_text(line) for line in doc[page_index].get_text().splitlines() if clean_text(line)]


def page_words(doc: fitz.Document, page_index: int) -> int:
    return len(doc[page_index].get_text("words"))


def sections_by_page(index_text: str) -> dict[int, str]:
    pattern = re.compile(r'<section class="pdf-page" data-page="(?P<page>\d+)"[^>]*>(?P<body>.*?)</section>', re.S)
    return {int(match.group("page")): match.group("body") for match in pattern.finditer(index_text)}


def strip_tags(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def html_overlays(section: str) -> list[str]:
    spans = re.findall(r'<span class="ko-text"[^>]*>(.*?)</span>', section, re.S)
    return [strip_tags(span) for span in spans if strip_tags(span)]


def strip_allowlisted_english(text: str) -> str:
    stripped = re.sub(r"https?://\S+|\b[\w.-]+\.(?:com|net|org|io|co)\b", "", text, flags=re.I)
    for term in ALLOWLIST:
        stripped = re.sub(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", "", stripped, flags=re.I)
    stripped = re.sub(r"\d+(?:\.\d+)?\s*(?:%|kg|lbs?|g)\b", "", stripped, flags=re.I)
    return stripped


def english_findings(text: str) -> list[str]:
    stripped = strip_allowlisted_english(text)
    phrases = re.findall(r"\b[A-Za-z][A-Za-z'/-]*(?:\s+[A-Za-z][A-Za-z'/-]*){1,}\b", stripped)
    suspicious = re.findall(r"\b(?:SUPERSET WITH|TOTAL WORK SETS|MACHINE PRESS|DUMBELL|DUMBBELL|PUSHDOWNS|PULLUPS|REST/PAUSE|ROM)\b", text, re.I)
    return sorted(set([clean_text(item) for item in phrases + suspicious if clean_text(item)]))


def exercise_header_count(lines: list[str]) -> int:
    return sum(1 for line in lines if re.search(r"^\d+/", line))


def table_signal(lines: list[str]) -> int:
    terms = ["Day", "Focus", "Exercises", "Sets", "요일", "초점", "운동", "세트", "월요일", "화요일", "수요일"]
    return sum(1 for line in lines if any(term in line for term in terms))


def set_rep_signal(lines: list[str]) -> int:
    terms = ["TOTAL WORK SETS", "GOAL", "RPE", "총 작업", "목표", "작업량", "세트"]
    return sum(1 for line in lines if any(term in line for term in terms))


def meaningful_korean_count(text: str) -> int:
    return len(re.findall(r"[가-힣]", text))


def render_all_previews() -> list[str]:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(OUTPUT_PDF)
    written: list[str] = []
    for index, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=fitz.Matrix(0.38, 0.38), alpha=False)
        out = PREVIEW_DIR / f"page-{index:03d}.jpg"
        pix.save(out, jpg_quality=72)
        written.append(str(out.relative_to(ROOT)))
    doc.close()
    return written


def write_contact_sheet(previews: list[str], worst_pages: list[int]) -> None:
    html_parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8"><title>Dynasty QA Contact Sheet</title>',
        "<style>body{font-family:Arial,sans-serif;margin:18px;background:#eee} .grid{display:grid;grid-template-columns:repeat(6,1fr);gap:12px} .p{background:white;padding:8px;border:1px solid #ccc} .bad{border:3px solid #b00020} img{width:100%;display:block} h1{font-size:20px}</style>",
        "</head><body><h1>Dynasty Korean QA Contact Sheet</h1><div class=\"grid\">",
    ]
    for path in previews:
        page = int(re.search(r"page-(\d+)", path).group(1))
        cls = "p bad" if page in worst_pages else "p"
        html_parts.append(f'<div class="{cls}"><strong>Page {page}</strong><img src="{escape(path.replace(chr(92), "/"))}" alt="Page {page}"></div>')
    html_parts.extend(["</div></body></html>"])
    (ROOT / "qa-previews" / "contact-sheet.html").write_text("\n".join(html_parts), encoding="utf-8")


def score_page(item: dict) -> int:
    score = 0
    score += item["remaining_english_count"] * 5
    score += item["missing_exercise_names"] * 7
    score += item["missing_tables"] * 6
    score += item["missing_set_rep_rest"] * 4
    score += item["low_output_vs_korean"] * 5
    score += item["low_output_vs_original"] * 3
    score += item["blank_overlay_risk"] * 10
    score += item["missing_instruction_blocks"] * 4
    return score


def main() -> int:
    REPORT_DIR.mkdir(exist_ok=True)
    index_text = INDEX_HTML.read_text(encoding="utf-8") if INDEX_HTML.exists() else ""
    sections = sections_by_page(index_text)
    original = fitz.open(SOURCE_PDF)
    korean = fitz.open(KOREAN_PDF)
    output = fitz.open(OUTPUT_PDF)
    pages: list[dict] = []

    for page in range(1, EXPECTED_PAGES + 1):
        i = page - 1
        original_lines = page_lines(original, i)
        korean_lines = page_lines(korean, i) if i < korean.page_count else []
        output_lines = page_lines(output, i) if i < output.page_count else []
        overlays = html_overlays(sections.get(page, ""))
        output_text = "\n".join(output_lines)
        korean_text = "\n".join(korean_lines)
        original_words = page_words(original, i)
        korean_words = page_words(korean, i) if i < korean.page_count else 0
        output_words = page_words(output, i) if i < output.page_count else 0

        original_exercises = exercise_header_count(original_lines)
        korean_exercises = exercise_header_count(korean_lines)
        output_exercises = exercise_header_count(output_lines)
        expected_exercises = max(original_exercises, korean_exercises)
        original_tables = table_signal(original_lines)
        korean_tables = table_signal(korean_lines)
        output_tables = table_signal(output_lines)
        expected_tables = max(original_tables, korean_tables)
        expected_sets = max(set_rep_signal(original_lines), set_rep_signal(korean_lines))
        output_sets = set_rep_signal(output_lines)
        korean_chars = meaningful_korean_count(output_text)
        overlay_coverage = (len(overlays) / korean_words) if korean_words else 1.0
        low_vs_korean = int(korean_words > 40 and overlay_coverage < 0.72 and output_words < korean_words * 0.70)
        low_vs_original = int(original_words > 40 and len(overlays) < original_words * 0.55 and output_words < original_words * 0.55)
        missing_instruction = int(page in WORKOUT_PAGES and overlay_coverage < 0.72 and output_words < max(30, korean_words * 0.45))

        item = {
            "page": page,
            "original_text_count": original_words,
            "korean_source_text_count": korean_words,
            "html_overlay_count": len(overlays),
            "output_text_count": output_words,
            "suspected_missing_titles": int(page in {2, 3, 4} and len(overlays) < 20),
            "suspected_missing_tables": max(0, expected_tables - output_tables) if page in WEEKLY_TABLE_PAGES or page in {2, 3} else 0,
            "suspected_missing_workout_exercise_names": max(0, expected_exercises - output_exercises) if page in WORKOUT_PAGES else 0,
            "suspected_missing_instruction_blocks": missing_instruction,
            "suspected_missing_sets_reps_rest_columns": max(0, expected_sets - output_sets) if page in WORKOUT_PAGES else 0,
            "remaining_english": english_findings(output_text),
            "remaining_english_count": len(english_findings(output_text)),
            "suspected_blank_near_blank_overlay_areas": int(page not in {1} and len(overlays) < 5 and max(original_words, korean_words) > 20),
            "overlay_coverage_vs_korean": round(overlay_coverage, 3),
            "low_output_vs_korean": low_vs_korean,
            "low_output_vs_original": low_vs_original,
            "missing_exercise_names": max(0, expected_exercises - output_exercises) if page in WORKOUT_PAGES else 0,
            "missing_tables": max(0, expected_tables - output_tables) if page in WEEKLY_TABLE_PAGES or page in {2, 3} else 0,
            "missing_set_rep_rest": max(0, expected_sets - output_sets) if page in WORKOUT_PAGES else 0,
            "missing_instruction_blocks": missing_instruction,
            "blank_overlay_risk": int(page not in {1} and korean_chars < 20 and max(original_words, korean_words) > 30),
            "notes": [],
        }
        item["score"] = score_page(item)
        if item["low_output_vs_korean"]:
            item["notes"].append("Output text count is much lower than Korean source.")
        if item["low_output_vs_original"]:
            item["notes"].append("Output text count is much lower than original source.")
        if item["remaining_english"]:
            item["notes"].append("Remaining non-allowlisted English text detected.")
        pages.append(item)

    worst = [item for item in sorted(pages, key=lambda item: item["score"], reverse=True) if item["score"] > 0][:15]
    previews = render_all_previews()
    write_contact_sheet(previews, [item["page"] for item in worst])

    report = {
        "summary": {
            "expected_pages": EXPECTED_PAGES,
            "original_pages": original.page_count,
            "korean_source_pages": korean.page_count,
            "output_pages": output.page_count,
            "html_pages": len(sections),
            "worst_pages": [item["page"] for item in worst],
            "pages_with_score": sum(1 for item in pages if item["score"] > 0),
            "preview_count": len(previews),
            "preview_folder": str(PREVIEW_DIR.relative_to(ROOT)),
            "contact_sheet": "qa-previews/contact-sheet.html",
        },
        "worst_pages": worst,
        "pages": pages,
    }
    (REPORT_DIR / "missing-content.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# Dynasty Missing Content Audit", "", "## Summary", ""]
    for key, value in report["summary"].items():
        md.append(f"- `{key}`: {value}")
    md.extend(["", "## Worst 15 Pages", ""])
    for item in worst:
        md.append(
            f"- Page {item['page']}: score {item['score']}; "
            f"orig={item['original_text_count']} korean={item['korean_source_text_count']} "
            f"html_overlays={item['html_overlay_count']} output={item['output_text_count']} "
            f"missing_ex={item['missing_exercise_names']} missing_tables={item['missing_tables']} "
            f"english={item['remaining_english_count']}"
        )
        if item["notes"]:
            md.append(f"  - {'; '.join(item['notes'])}")
    (REPORT_DIR / "missing-content.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    original.close()
    korean.close()
    output.close()

    print("Missing-content audit")
    print("=====================")
    print(f"Pages audited: {len(pages)}")
    print(f"Pages with score > 0: {report['summary']['pages_with_score']}")
    print(f"Worst pages: {', '.join(str(item['page']) for item in worst)}")
    print(f"All-page previews: {PREVIEW_DIR}")
    print(f"Contact sheet: {ROOT / 'qa-previews' / 'contact-sheet.html'}")
    print(f"JSON report: {REPORT_DIR / 'missing-content.json'}")
    print(f"Markdown report: {REPORT_DIR / 'missing-content.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
