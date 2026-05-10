from __future__ import annotations

import html as html_lib
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import fitz


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PAGES = 93
PREVIEW_PAGES = [6, 8, 14, 15, 22, 29, 37, 44, 58, 61, 72, 86, 91]
WEEKLY_SPLIT_PAGES = {5, 14, 21, 28, 36, 43, 50, 57, 64, 71, 78, 85}
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
PATCH_PAGES = {2, 3, 4, 5} | WEEKLY_SPLIT_PAGES | WORKOUT_PAGES
PLACEHOLDERS = ["TODO_TRANSLATE", "한국어 번역문", "한국어 섹션 제목"]
SUSPICIOUS_TERMS = [
    "T바",
    "EZ바",
    "JM프레스",
    "SUPERSET WITH",
    "TOTAL WORK SETS",
    "MACHINE PRESS",
    "DUMBELL",
    "DUMBBELL",
    "PUSHDOWNS",
    "PULLUPS",
    "ROM",
    "REST/PAUSE",
]
ALLOWED_ENGLISH = [
    "CM Strength",
    "Dynasty",
    "RPE",
    "reps",
    "sets",
    "kg",
    "lb",
    "lbs",
]
ACRONYM_ALLOWLIST = {"RPE", "PPL", "URL"}


@dataclass
class Overlay:
    page: int
    text: str
    left: float
    top: float
    width: float
    height: float
    font_size: float
    line_height: float


@dataclass
class GoldLine:
    y: float
    x0: float
    x1: float


def add_issue(issues: list[dict], severity: str, code: str, message: str, page: int | None = None, sample: str | None = None) -> None:
    item = {"severity": severity, "code": code, "message": message}
    if page is not None:
        item["page"] = page
    if sample:
        item["sample"] = sample[:240]
    issues.append(item)


def sections_by_page(html: str) -> dict[int, str]:
    pattern = re.compile(
        r'<section class="pdf-page" data-page="(?P<page>\d+)"[^>]*>(?P<body>.*?)</section>',
        re.S,
    )
    return {int(match.group("page")): match.group("body") for match in pattern.finditer(html)}


def style_value(style: str, key: str, default: float = 0.0) -> float:
    match = re.search(rf"{re.escape(key)}\s*:\s*([0-9.]+)pt", style)
    return float(match.group(1)) if match else default


def extract_overlays(sections: dict[int, str]) -> list[Overlay]:
    overlays: list[Overlay] = []
    span_pattern = re.compile(r'<span class="ko-text"[^>]*style="(?P<style>[^"]*)"[^>]*>(?P<text>.*?)</span>', re.S)
    for page, body in sections.items():
        for match in span_pattern.finditer(body):
            style = match.group("style")
            text = html_lib.unescape(re.sub(r"<[^>]+>", "", match.group("text"))).strip()
            overlays.append(
                Overlay(
                    page=page,
                    text=text,
                    left=style_value(style, "left"),
                    top=style_value(style, "top"),
                    width=style_value(style, "width"),
                    height=style_value(style, "height"),
                    font_size=style_value(style, "font-size", 10.0),
                    line_height=style_value(style, "line-height", style_value(style, "font-size", 10.0) * 1.15),
                )
            )
    return overlays


def strip_allowed_english(text: str) -> str:
    stripped = text
    stripped = re.sub(r"https?://\S+|\b[\w.-]+\.(?:com|net|org|io|co)\b", "", stripped, flags=re.I)
    for term in ALLOWED_ENGLISH:
        stripped = re.sub(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", "", stripped, flags=re.I)
    stripped = re.sub(r"\b[A-Z]{2,5}\b", lambda m: "" if m.group(0) in ACRONYM_ALLOWLIST else m.group(0), stripped)
    stripped = re.sub(r"\d+(?:\.\d+)?\s*(?:%|kg|lbs?|g)\b", "", stripped, flags=re.I)
    return stripped


def english_phrases(text: str) -> list[str]:
    stripped = strip_allowed_english(text)
    phrases = re.findall(r"\b[A-Za-z][A-Za-z'/-]*(?:\s+[A-Za-z][A-Za-z'/-]*){2,}\b", stripped)
    return [phrase for phrase in phrases if phrase.strip()]


def has_suspicious_term(text: str) -> str | None:
    upper_text = text.upper()
    for term in SUSPICIOUS_TERMS:
        if term.upper() in upper_text:
            return term
    return None


def overflow_score(overlay: Overlay) -> float:
    if not overlay.text or overlay.width <= 0 or overlay.height <= 0 or overlay.font_size <= 0:
        return 0.0
    effective_chars = 0.0
    for char in overlay.text:
        if char.isspace():
            effective_chars += 0.35
        elif re.match(r"[A-Za-z0-9]", char):
            effective_chars += 0.55
        else:
            effective_chars += 1.0
    lines = max(1.0, overlay.height / max(overlay.line_height, overlay.font_size * 1.1))
    chars_per_line = max(1.0, overlay.width / max(overlay.font_size * 0.62, 1.0))
    capacity = chars_per_line * lines
    return effective_chars / capacity


def similar_coord(a: Overlay, b: Overlay) -> bool:
    return (
        abs(a.left - b.left) < 0.8
        and abs(a.top - b.top) < 0.8
        and abs(a.width - b.width) < 1.2
        and abs(a.height - b.height) < 1.2
    )


def normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def render_previews(output_path: Path) -> list[str]:
    preview_dir = ROOT / "qa-previews"
    preview_dir.mkdir(exist_ok=True)
    doc = fitz.open(output_path)
    written: list[str] = []
    for page_number in PREVIEW_PAGES:
        if page_number > doc.page_count:
            continue
        page = doc[page_number - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(0.55, 0.55), alpha=False)
        out = preview_dir / f"page-{page_number:03d}.png"
        pix.save(out)
        written.append(str(out.relative_to(ROOT)))
    doc.close()
    return written


def detect_gold_lines(page: fitz.Page, zoom: float = 2.0) -> list[GoldLine]:
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    width, height, channels = pix.width, pix.height, pix.n
    samples = pix.samples
    rows: list[tuple[int, int, int]] = []
    threshold = max(90, int(width * 0.32))
    for y in range(height):
        xs: list[int] = []
        row_start = y * width * channels
        for x in range(width):
            i = row_start + x * channels
            r, g, b = samples[i], samples[i + 1], samples[i + 2]
            if 120 <= r <= 210 and 95 <= g <= 180 and b < 125 and r >= g >= b:
                xs.append(x)
        if len(xs) >= threshold:
            rows.append((y, min(xs), max(xs)))

    grouped: list[list[int]] = []
    for y, x0, x1 in rows:
        if not grouped or y > grouped[-1][1] + 1:
            grouped.append([y, y, x0, x1])
        else:
            grouped[-1][1] = y
            grouped[-1][2] = min(grouped[-1][2], x0)
            grouped[-1][3] = max(grouped[-1][3], x1)
    return [
        GoldLine(y=((start + end) / 2) / zoom, x0=x0 / zoom, x1=x1 / zoom)
        for start, end, x0, x1 in grouped
    ]


def exercise_title_overlays(overlays: list[Overlay]) -> dict[int, list[Overlay]]:
    titles: dict[int, list[Overlay]] = {}
    for overlay in overlays:
        if re.fullmatch(r"\d+/", overlay.text.strip()) and overlay.top >= 88 and overlay.left < 60 and overlay.font_size >= 7:
            titles.setdefault(overlay.page, []).append(overlay)
    for page in titles:
        titles[page].sort(key=lambda item: item.top)
    return titles


def check_exercise_underlines(output_path: Path, overlays: list[Overlay], issues: list[dict]) -> None:
    titles_by_page = exercise_title_overlays(overlays)
    doc = fitz.open(output_path)
    for page_number in sorted(WORKOUT_PAGES):
        if page_number > doc.page_count:
            continue
        lines = detect_gold_lines(doc[page_number - 1])
        titles = titles_by_page.get(page_number, [])
        for title in titles:
            candidates = [line for line in lines if title.top + 6 <= line.y <= title.top + 28]
            if not candidates:
                add_issue(
                    issues,
                    "error",
                    "missing-title-underline",
                    "No nearby gold underline was detected below an exercise title",
                    page=page_number,
                    sample=title.text,
                )
                continue
            line = min(candidates, key=lambda item: abs(item.y - (title.top + 15)))
            distance = line.y - title.top
            if distance < 9 or distance > 20:
                add_issue(
                    issues,
                    "error",
                    "title-underline-distance",
                    f"Exercise underline is {distance:.1f}pt below title; expected 9-20pt",
                    page=page_number,
                    sample=title.text,
                )
            if line.x0 > title.left + 8 or line.x1 < title.left + 180:
                add_issue(
                    issues,
                    "error",
                    "title-underline-horizontal",
                    "Exercise underline appears horizontally detached from its title",
                    page=page_number,
                    sample=title.text,
                )
        for line in lines:
            nearby_title = any(9 <= line.y - title.top <= 22 for title in titles)
            if not nearby_title and 88 <= line.y < 585:
                add_issue(
                    issues,
                    "warning",
                    "orphan-gold-rule",
                    "Gold underline/divider has no nearby exercise title",
                    page=page_number,
                    sample=f"y={line.y:.1f}pt",
                )
    doc.close()


def issue_counts(issues: Iterable[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue["severity"]] = counts.get(issue["severity"], 0) + 1
    return counts


def main() -> int:
    index_path = ROOT / "index.html"
    output_path = ROOT / "output.pdf"
    manifest_path = ROOT / "assets" / "manifest.json"
    pages_dir = ROOT / "assets" / "pages"
    report_path = ROOT / "qa-production-report.json"
    issues: list[dict] = []

    if not index_path.exists():
        add_issue(issues, "error", "missing-index", "index.html is missing")
        html = ""
    else:
        html = index_path.read_text(encoding="utf-8")

    sections = sections_by_page(html)
    overlays = extract_overlays(sections)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    if len(sections) != EXPECTED_PAGES:
        add_issue(issues, "error", "page-count-html", f"Expected {EXPECTED_PAGES} HTML pages, found {len(sections)}")
    missing_sections = [page for page in range(1, EXPECTED_PAGES + 1) if page not in sections]
    for page in missing_sections:
        add_issue(issues, "error", "missing-html-page", "Missing .pdf-page section", page=page)

    missing_backgrounds = []
    missing_background_refs = []
    for page in range(1, EXPECTED_PAGES + 1):
        image_name = f"page-{page:03d}-background.png"
        if not (pages_dir / image_name).exists():
            missing_backgrounds.append(page)
        if page in sections and image_name not in sections[page]:
            missing_background_refs.append(page)
    for page in missing_backgrounds:
        add_issue(issues, "error", "missing-background-file", "Expected page background PNG is missing", page=page)
    for page in missing_background_refs:
        add_issue(issues, "error", "missing-background-ref", "HTML page does not reference its expected background image", page=page)

    for page in sorted(PATCH_PAGES):
        body = sections.get(page, "")
        if 'class="art-patch' not in body:
            add_issue(issues, "error", "missing-art-patch", "Expected localized art patch is missing", page=page)
    for page in sorted(WEEKLY_SPLIT_PAGES):
        if "weekly-split-table" not in sections.get(page, ""):
            add_issue(issues, "error", "missing-weekly-table-patch", "Expected weekly split table patch is missing", page=page)

    for token in PLACEHOLDERS:
        if token in html:
            add_issue(issues, "error", "placeholder", "Generic placeholder remains in HTML", sample=token)

    for overlay in overlays:
        if overlay.font_size < 4.0:
            add_issue(
                issues,
                "warning",
                "tiny-font",
                f"Overlay font-size is under 4pt: {overlay.font_size:.2f}pt",
                page=overlay.page,
                sample=overlay.text,
            )
        score = overflow_score(overlay)
        if score > 1.45 and len(overlay.text) > 12:
            add_issue(
                issues,
                "warning",
                "overflow-risk",
                f"Overlay may overflow its box; score {score:.2f}",
                page=overlay.page,
                sample=overlay.text,
            )

    by_page_text: dict[int, list[Overlay]] = {}
    for overlay in overlays:
        key = normalized_text(overlay.text)
        if len(key) < 3:
            continue
        by_page_text.setdefault(overlay.page, []).append(overlay)
    duplicate_count = 0
    for page, page_overlays in by_page_text.items():
        for index, left in enumerate(page_overlays):
            for right in page_overlays[index + 1 :]:
                if normalized_text(left.text) == normalized_text(right.text) and similar_coord(left, right):
                    duplicate_count += 1
                    add_issue(issues, "warning", "duplicate-overlap", "Duplicate overlay text at near-identical coordinates", page=page, sample=left.text)
                    break
            if duplicate_count > 50:
                break

    if not output_path.exists():
        add_issue(issues, "error", "missing-output", "output.pdf is missing")
        output_pages = 0
        preview_files: list[str] = []
    else:
        doc = fitz.open(output_path)
        output_pages = doc.page_count
        if output_pages != EXPECTED_PAGES:
            add_issue(issues, "error", "page-count-pdf", f"Expected {EXPECTED_PAGES} PDF pages, found {output_pages}")
        for page_number, page in enumerate(doc, start=1):
            text = "\n".join(line.strip() for line in page.get_text().splitlines() if line.strip())
            suspicious = has_suspicious_term(text)
            if suspicious:
                add_issue(issues, "error", "suspicious-term", f"Suspicious mixed-language term remains: {suspicious}", page=page_number)
            phrases = english_phrases(text)
            for phrase in phrases[:4]:
                add_issue(issues, "error", "english-phrase", "English phrase longer than two words remains", page=page_number, sample=phrase)
        doc.close()
        check_exercise_underlines(output_path, overlays, issues)
        preview_files = render_previews(output_path)

    report = {
        "summary": {
            "expected_pages": EXPECTED_PAGES,
            "html_pages": len(sections),
            "output_pages": output_pages,
            "background_files": len(list(pages_dir.glob("page-*-background.png"))),
            "manifest_page_count": manifest.get("page_count"),
            "overlay_count": len(overlays),
            "patched_pages_expected": len(PATCH_PAGES),
            "qa_preview_pages": PREVIEW_PAGES,
            "qa_preview_files": preview_files,
            "allowlisted_english": ALLOWED_ENGLISH + sorted(ACRONYM_ALLOWLIST),
            "issue_counts": issue_counts(issues),
        },
        "issues": issues,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Production QA report")
    print("====================")
    print(f"HTML pages: {len(sections)} / {EXPECTED_PAGES}")
    print(f"PDF pages: {output_pages} / {EXPECTED_PAGES}")
    print(f"Background PNGs: {len(list(pages_dir.glob('page-*-background.png')))} / {EXPECTED_PAGES}")
    print(f"Overlays: {len(overlays)}")
    print(f"Preview PNGs: {len(preview_files)} ({', '.join(str(page) for page in PREVIEW_PAGES)})")
    counts = issue_counts(issues)
    print(f"Issues: {counts or {'none': 0}}")
    if issues:
        print("\nTop issues:")
        for issue in issues[:20]:
            location = f" page {issue['page']}" if "page" in issue else ""
            sample = f" | {issue['sample']}" if "sample" in issue else ""
            print(f"- [{issue['severity']}] {issue['code']}{location}: {issue['message']}{sample}")
    print(f"\nJSON report: {report_path}")

    return 1 if counts.get("error", 0) else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}")
        raise SystemExit(1)
