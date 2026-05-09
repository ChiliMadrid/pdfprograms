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
KOREAN_PDF_PATH = WORKSPACE / "korean_exports" / "final" / "CM Strength Dynasty conv Korean.pdf"
ASSETS = ROOT / "assets" / "pages"

RENDER_ZOOM = 2

LABEL_TRANSLATIONS = {
    "TABLE OF CONTENTS": "목차",
    "PROGRAM ROADMAP": "프로그램 로드맵",
    "PROGRAM DURATION AND SPLIT": "프로그램 기간 및 분할",
    "PULL / PUSH / LEGS STRUCTURE": "당기기 / 밀기 / 하체 구조",
    "DELOADS AND OVERLOAD METHOD": "디로드와 과부하 방법",
    "RECOVERY MANAGEMENT AND PROGRESSION": "회복 관리와 진행",
    "RECOVERY NUTRITION": "회복 영양",
    "WEEKLY SPLIT": "주간 분할",
    "DAY": "요일",
    "FOCUS": "초점",
    "SECTION": "섹션",
    "PAGE": "페이지",
    "PULL": "당기기",
    "PUSH": "밀기",
    "LEGS": "하체",
    "OFF": "휴식",
    "PULL (PUMP)": "당기기 (펌프)",
    "PUSH (PUMP)": "밀기 (펌프)",
    "LEGS (PUMP)": "하체 (펌프)",
    "TOTAL WORK SETS": "총 작업 세트",
    "GOAL": "목표",
    "PRO TIP": "프로 팁",
    "SUPERSET WITH": "슈퍼세트",
    "CHEST": "가슴",
    "BACK": "등",
    "SHOULDERS": "어깨",
    "TRICEPS": "삼두근",
    "BICEPS": "이두근",
    "ABS": "복근",
    "UPPER LEGS": "상부 하체",
    "HAMS": "햄스트링",
    "CALVES": "종아리",
    "WEEK": "주차",
    "MONDAY": "월요일",
    "TUESDAY": "화요일",
    "WEDNESDAY": "수요일",
    "THURSDAY": "목요일",
    "FRIDAY": "금요일",
    "SATURDAY": "토요일",
    "SUNDAY": "일요일",
}


def validate_sources() -> None:
    required = [PDF_PATH, DOCX_PATH]
    missing = [path for path in required if not path.exists()]
    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(f"Required source file(s) missing:\n{formatted}")


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


def read_pdf_page_lines(path: Path) -> list[list[str]]:
    doc = fitz.open(path)
    pages: list[list[str]] = []
    for page in doc:
        lines: list[str] = []
        for line in page.get_text().splitlines():
            line = clean_visible_text(line)
            if line:
                lines.append(line)
        pages.append(lines)
    doc.close()
    return pages


def color_to_hex(value: int | None) -> str:
    if value is None:
        return "#000000"
    return f"#{(value >> 16) & 255:02x}{(value >> 8) & 255:02x}{value & 255:02x}"


def clean_visible_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("•", "")).strip()


def has_korean(text: str) -> bool:
    return bool(re.search(r"[가-힣]", text))


def is_numeric_fragment(text: str) -> bool:
    return bool(re.fullmatch(r"[\d\s./:%+–—-]+", text.strip()))


def translate_label(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if clean.startswith("Thank you for choosing CM Strength"):
        return (
            "CM Strength를 선택해 주셔서 감사합니다. 이 프로그램은 체육관에 들어설 때마다 구조, 목적, "
            "강도를 제공하도록 만들어졌습니다. 계획을 따르고, 진행 상황을 기록하고, 의도적으로 훈련하며, "
            "훈련 밖의 회복도 존중하세요. 목표는 단순히 프로그램을 끝내는 것이 아니라 더 강하고, 더 절제되고, "
            "체육관 안팎에서 더 자신감 있는 사람이 되는 것입니다. — 칠리 코치"
        )
    upper = clean.upper()
    if upper in LABEL_TRANSLATIONS:
        return LABEL_TRANSLATIONS[upper]

    translated = upper
    for english, korean in sorted(LABEL_TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True):
        translated = re.sub(rf"\b{re.escape(english)}\b", korean, translated)
    translated = re.sub(r"WEEK\s+(\d+)", r"\1주차", translated)
    translated = translated.replace(" – ", " - ").replace(" — ", " - ")
    return translated


def fitted_korean_source(source: str, original_text: str, size: float) -> str:
    source = clean_visible_text(source)
    if not source:
        return ""

    original = original_text.strip()
    if len(original) <= 3:
        return original

    factor = 0.78 if size < 12 else 0.68
    target = max(3, min(96, int(len(original) * factor)))
    if len(source) <= target:
        return source

    cut = source[:target].rstrip()
    last_space = cut.rfind(" ")
    if last_space > target * 0.55:
        cut = cut[:last_space]
    return cut.rstrip(" ,.;:")


def classify_text(text: str, size: float, source: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return ""

    upper = clean.upper()
    if re.fullmatch(r"CM\s+STRENGTH(?:\s+DYNASTY)?", upper):
        return clean
    if size >= 34:
        return "CM 스트렝스 다이너스티"
    if is_numeric_fragment(clean):
        return clean
    if has_korean(source):
        fitted = fitted_korean_source(source, clean, size)
        if fitted:
            return fitted
    if len(clean) <= 3:
        return clean
    return translate_label(clean)


def source_for_span(original_text: str, visible_paragraphs: list[str], para_index: int) -> tuple[str, int]:
    if para_index >= len(visible_paragraphs):
        return "", para_index

    source = visible_paragraphs[para_index]
    if has_korean(source) or is_numeric_fragment(original_text):
        return source, para_index

    # DOCX conversion sometimes emits standalone numeric fragments. Skip those
    # for prose/header spans so generic placeholders never appear in output.
    for idx in range(para_index + 1, min(len(visible_paragraphs), para_index + 12)):
        if has_korean(visible_paragraphs[idx]):
            return visible_paragraphs[idx], idx
    return source, para_index


def span_style(span: dict, bbox: tuple[float, float, float, float]) -> str:
    x0, y0, x1, y1 = bbox
    size = float(span.get("size", 10))
    flags = int(span.get("flags", 0))
    font = span.get("font", "")
    weight = "700" if "Bold" in font or flags & 16 else "400"
    italic = "italic" if "Italic" in font or flags & 2 else "normal"
    color = color_to_hex(span.get("color"))
    width = max(1, x1 - x0)
    height = max(size * 1.12, y1 - y0)
    ko_size = size * (0.92 if size < 13 else 0.96)
    line_height = max(ko_size * 1.13, height)
    return (
        f"left:{x0:.3f}pt;top:{y0:.3f}pt;width:{width:.3f}pt;"
        f"height:{height:.3f}pt;font-size:{ko_size:.3f}pt;"
        f"line-height:{line_height:.3f}pt;font-weight:{weight};font-style:{italic};"
        f"color:{color};"
    )


def extract_spans(page: fitz.Page, visible_paragraphs: list[str], para_index: int = 0) -> tuple[list[dict], int]:
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
                source, source_index = source_for_span(text, visible_paragraphs, para_index)
                if len(text.strip()) > 8 and source_index < len(visible_paragraphs):
                    para_index = source_index + 1
                spans.append(
                    {
                        "text": classify_text(text, float(span.get("size", 10)), source),
                        "source": source,
                        "style": span_style(span, bbox),
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
    page.apply_redactions(
        images=fitz.PDF_REDACT_IMAGE_NONE,
        graphics=fitz.PDF_REDACT_LINE_ART_NONE,
        text=fitz.PDF_REDACT_TEXT_REMOVE,
    )
    pix = page.get_pixmap(matrix=fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM), alpha=False)
    pix.save(out_path)
    single.close()


def build_html(pages: list[dict], visible_docx_path: Path) -> str:
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
        (
            f"<!-- Generated from {html.escape(PDF_PATH.name)} with visible text from "
            f"{html.escape(visible_docx_path.name)}. -->"
        ),
    ]
    for page in pages:
        parts.append(
            f'<section class="pdf-page" data-page="{page["number"]}" '
            f'style="width:{page["width"]:.3f}pt;height:{page["height"]:.3f}pt">'
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
    validate_sources()
    ASSETS.mkdir(parents=True, exist_ok=True)

    english_paragraphs = read_docx_paragraphs(DOCX_PATH)
    visible_docx_path = KOREAN_DOCX_PATH if KOREAN_DOCX_PATH.exists() else DOCX_PATH
    visible_paragraphs = read_docx_paragraphs(visible_docx_path)
    page_aligned_text = read_pdf_page_lines(KOREAN_PDF_PATH) if KOREAN_PDF_PATH.exists() else []

    pdf = fitz.open(PDF_PATH)
    pages: list[dict] = []
    mapped_paragraphs = 0
    for i, page in enumerate(pdf):
        number = i + 1
        render_textless_page(pdf, i, ASSETS / f"page-{number:03d}-background.png")
        page_sources = page_aligned_text[i] if i < len(page_aligned_text) and page_aligned_text[i] else visible_paragraphs
        spans, used_paragraphs = extract_spans(page, page_sources)
        mapped_paragraphs += used_paragraphs
        pages.append(
            {
                "number": number,
                "width": page.rect.width,
                "height": page.rect.height,
                "spans": spans,
            }
        )

    metadata = {
        "source_pdf": str(PDF_PATH),
        "source_docx": str(DOCX_PATH),
        "visible_text_docx": str(visible_docx_path),
        "visible_text_pdf": str(KOREAN_PDF_PATH) if KOREAN_PDF_PATH.exists() else None,
        "korean_docx_found": KOREAN_DOCX_PATH.exists(),
        "korean_pdf_found": KOREAN_PDF_PATH.exists(),
        "page_count": pdf.page_count,
        "docx_paragraph_count": len(english_paragraphs),
        "visible_docx_paragraph_count": len(visible_paragraphs),
        "mapped_docx_paragraphs": mapped_paragraphs,
        "render_zoom": RENDER_ZOOM,
    }
    (ROOT / "index.html").write_text(build_html(pages, visible_docx_path), encoding="utf-8")
    (ROOT / "assets" / "manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    pdf.close()
    print(json.dumps(metadata, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
