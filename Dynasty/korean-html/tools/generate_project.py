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


def localize_mixed_text(text: str) -> str:
    replacements = {
        "SUPERSET WITH": "슈퍼세트",
        "TOTAL WORK SETS": "총 작업 세트",
        "MACHINE PRESS": "기계 프레스",
        "SLIGHT DECLINE DUMBELL": "약간의 디클라인 덤벨",
        "DUMBELL DECLINE": "덤벨 디클라인",
        "DUMBELL BENT OVER SIDE LATERALS": "벤트오버 덤벨 사이드 레터럴",
        "SPIDERCRAWLS": "스파이더 크롤",
        "ROPE PUSHDOWNS": "로프 푸시다운",
        "PRONATED": "회내",
        "TRAIN EXPLOSIVELY": "폭발적으로 훈련",
        "ACTIVATION AND START": "활성화 및 시작",
        "SAFETY SQUAT": "세이프티 스쿼트",
        "MEADOWS ROW": "메도우즈 로우",
        "REST/PAUSE": "휴식-정지",
        "ROM": "가동범위",
        "LIGHT": "가볍게",
        "HEAVY": "무겁게",
        "WITH": "슈퍼세트",
        "EZBAR": "이지바",
        "SMITH": "스미스",
        "JM PRESS": "제이엠 프레스",
        "FATGRIPZ": "팻그립즈",
        "GRIP4ORCE": "그립포스",
        "GRIPZ": "그립즈",
        "ELITEFTS.NET": "엘리트에프티에스 사이트",
        "ELITEFTS": "엘리트에프티에스",
        "EAAS": "필수 아미노산",
        "EAA": "필수 아미노산",
        "T-BAR": "티바",
        "T BAR": "티바",
        "PULLUP": "풀업",
        "PULLUPS": "풀업",
        "BACK": "등",
        "SAFETY": "세이프티",
        "SQUAT": "스쿼트",
        "MEADOWS": "메도우즈",
        "ROW": "로우",
        "PAUSE": "정지",
        "KELSO": "켈소",
    }
    for english, korean in replacements.items():
        text = re.sub(rf"(?<![A-Za-z]){re.escape(english)}(?![A-Za-z])", korean, text, flags=re.IGNORECASE)
    text = re.sub(r"(?<![A-Za-z])T[- ]?바", "티바", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<![A-Za-z])EZ바", "이지바", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<![A-Za-z])JM프레스", "제이엠 프레스", text, flags=re.IGNORECASE)
    text = re.sub(r"10ish", "약 10회", text, flags=re.IGNORECASE)
    text = re.sub(r"25's", "25파운드 원판", text, flags=re.IGNORECASE)
    text = re.sub(r"bis", "이두근", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+)m\b", r"\1미터", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<![A-Za-z])m(?=[가-힣\s.,;:!?)]|$)", "미터", text, flags=re.IGNORECASE)
    return text


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


def style_number(style: str, key: str, default: float = 0.0) -> float:
    match = re.search(rf"{re.escape(key)}\s*:\s*([0-9.]+)pt", style)
    return float(match.group(1)) if match else default


def style_replace_number(style: str, key: str, value: float) -> str:
    return re.sub(rf"{re.escape(key)}\s*:\s*[0-9.]+pt", f"{key}:{value:.3f}pt", style)


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


def extract_existing_text_spans(page: fitz.Page) -> list[dict]:
    raw = page.get_text("rawdict")
    spans: list[dict] = []
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = "".join(ch.get("c", "") for ch in span.get("chars", []))
                if not text.strip():
                    continue
                visible_text = localize_mixed_text(clean_visible_text(text))
                if re.search(r"[A-Za-z]", visible_text) and not has_korean(visible_text):
                    if visible_text.upper().rstrip(":") == "RPE":
                        visible_text = "RPE" + (":" if visible_text.endswith(":") else "")
                    else:
                        translated = translate_label(visible_text)
                        visible_text = "" if translated == visible_text.upper() else translated
                if not visible_text:
                    continue
                style = span_style(span, tuple(float(v) for v in span["bbox"]))
                x0 = float(span["bbox"][0])
                if visible_text == ":" and 68 <= x0 <= 78:
                    visible_text = "RPE:"
                    style = style_replace_number(style, "left", 55.900)
                    style = style_replace_number(style, "width", 24.000)
                spans.append(
                    {
                        "text": visible_text,
                        "source": clean_visible_text(text),
                        "style": style,
                    }
                )
    return spans


def closing_page_spans(page: fitz.Page) -> list[dict]:
    text = (
        "CM Strength를 선택해 주셔서 감사합니다. 이 프로그램은 체육관에 들어설 때마다 구조, 목적, "
        "강도를 제공하도록 만들어졌습니다. 계획을 따르고, 진행 상황을 기록하고, 의도적으로 훈련하며, "
        "훈련 밖의 회복도 존중하세요. 목표는 단순히 프로그램을 끝내는 것이 아니라 더 강하고, 더 절제되고, "
        "체육관 안팎에서 더 자신감 있는 사람이 되는 것입니다. — 칠리 코치"
    )
    return [
        {
            "text": text,
            "source": text,
            "style": (
                "left:46.800pt;top:548.000pt;width:518.400pt;height:92.000pt;"
                "font-size:13.000pt;line-height:16.000pt;font-weight:400;"
                "font-style:normal;color:#111111;text-align:center;"
            ),
        }
    ]


def art_header(title: str, subtitle: str = "", top: float = 43.5, height: float = 38.5) -> str:
    subtitle_html = f'<div class="art-subtitle">{html.escape(subtitle)}</div>' if subtitle else ""
    return (
        f'<div class="art-patch art-header" style="left:43.400pt;top:{top:.3f}pt;'
        f'width:525.200pt;height:{height:.3f}pt">'
        f'<div class="art-title">{html.escape(title)}</div>{subtitle_html}</div>'
    )


def art_cover(left: float, top: float, width: float, height: float) -> str:
    return (
        f'<div class="art-patch art-whiteout" style="left:{left:.3f}pt;top:{top:.3f}pt;'
        f'width:{width:.3f}pt;height:{height:.3f}pt"></div>'
    )


def art_table(rows: list[list[str]], left: float, top: float, width: float, row_height: float, class_name: str) -> str:
    rendered_rows = []
    for index, row in enumerate(rows):
        cells = "".join(f"<td>{html.escape(cell)}</td>" for cell in row)
        rendered_rows.append(f'<tr class="{"head" if index == 0 else "body"}">{cells}</tr>')
    height = row_height * len(rows)
    return (
        f'<div class="art-patch art-table-patch {class_name}" style="left:{left:.3f}pt;top:{top:.3f}pt;'
        f'width:{width:.3f}pt;height:{height:.3f}pt">'
        '<table>'
        + "".join(rendered_rows)
        + "</table></div>"
    )


def toc_table_patch() -> str:
    rows = [
        ["섹션", "페이지"],
        ["프로그램 기간 및 분할", "-"],
        ["1주차", "-"],
        ["2주차", "-"],
        ["3주차", "-"],
        ["4주차", "-"],
        ["5주차", "-"],
        ["6주차", "-"],
        ["7주차", "-"],
        ["8주차", "-"],
        ["9주차", "-"],
        ["10주차", "-"],
        ["11주차", "-"],
        ["12주차", "-"],
    ]
    return art_cover(43.5, 126.6, 525.1, 276.0) + art_table(rows, 43.5, 126.6, 525.1, 19.1, "toc-table")


def split_method_table_patch() -> str:
    rows = [
        ["버전", "월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"],
        ["엘리트 회복형", "당기기", "밀기", "하체", "당기기(펌프)", "밀기(펌프)", "하체(펌프)", "휴식"],
        ["밀기 집중형", "당기기", "밀기", "하체", "휴식", "밀기(펌프)", "하체(펌프)", "휴식"],
        ["당기기 집중형", "당기기", "밀기", "하체", "휴식", "당기기(펌프)", "하체(펌프)", "휴식"],
        ["하체 집중형", "당기기", "밀기", "하체", "휴식", "밀기(펌프)", "하체(펌프)", "휴식"],
    ]
    return art_cover(43.7, 304.2, 525.0, 70.0) + art_table(rows, 43.7, 304.2, 525.0, 10.45, "split-method-table")


def weekly_split_table_patch() -> str:
    rows = [
        ["요일", "초점", "운동", "세트"],
        ["월요일", "당기기", "8", "28"],
        ["화요일", "밀기", "8", "27"],
        ["수요일", "하체", "5", "21"],
        ["목요일", "당기기(펌프)", "7", "27"],
        ["금요일", "밀기(펌프)", "7", "28"],
        ["토요일", "하체(펌프)", "5", "18"],
        ["일요일", "휴식", "0", "0"],
    ]
    return art_cover(43.7, 173.1, 525.0, 170.0) + art_table(rows, 43.7, 173.1, 525.0, 20.4, "weekly-split-table")


WEEK_SPLIT_PAGES = {5, 14, 21, 28, 36, 43, 50, 57, 64, 71, 78, 85}
DAY_TITLES = {
    "monday": ("월요일 - 당기기 운동", "기본 당기기 운동일"),
    "tuesday": ("화요일 - 밀기 운동", "기본 밀기 운동일"),
    "wednesday": ("수요일 - 하체 운동", "기본 하체 운동일"),
    "thursday": ("목요일 - 당기기 운동", "펌프 전용"),
    "friday": ("금요일 - 밀기 운동", "펌프 전용"),
    "saturday": ("토요일 - 하체 운동", "펌프 전용"),
}
WEEK_PAGE_RANGES = [
    (1, {6: "monday", 7: "monday", 8: "tuesday", 9: "tuesday", 10: "wednesday", 11: "thursday", 12: "friday", 13: "saturday"}),
    (2, {15: "monday", 16: "tuesday", 17: "wednesday", 18: "thursday", 19: "friday", 20: "saturday"}),
    (3, {22: "monday", 23: "tuesday", 24: "wednesday", 25: "thursday", 26: "friday", 27: "saturday"}),
    (4, {29: "monday", 30: "tuesday", 31: "tuesday", 32: "wednesday", 33: "thursday", 34: "friday", 35: "saturday"}),
    (5, {37: "monday", 38: "tuesday", 39: "wednesday", 40: "thursday", 41: "friday", 42: "saturday"}),
    (6, {44: "monday", 45: "tuesday", 46: "wednesday", 47: "thursday", 48: "friday", 49: "saturday"}),
    (7, {51: "monday", 52: "tuesday", 53: "wednesday", 54: "thursday", 55: "friday", 56: "saturday"}),
    (8, {58: "monday", 59: "tuesday", 60: "wednesday", 61: "thursday", 62: "friday", 63: "saturday"}),
    (9, {65: "monday", 66: "tuesday", 67: "wednesday", 68: "thursday", 69: "friday", 70: "saturday"}),
    (10, {72: "monday", 73: "tuesday", 74: "wednesday", 75: "thursday", 76: "friday", 77: "saturday"}),
    (11, {79: "monday", 80: "tuesday", 81: "wednesday", 82: "thursday", 83: "friday", 84: "saturday"}),
    (12, {86: "monday", 87: "monday", 88: "tuesday", 89: "wednesday", 90: "thursday", 91: "friday", 92: "saturday"}),
]


def workout_header_for_page(page_number: int) -> tuple[int, str] | None:
    for week, mapping in WEEK_PAGE_RANGES:
        if page_number in mapping:
            return week, mapping[page_number]
    return None


def page_art_patches(page_number: int) -> list[str]:
    patches: list[str] = []
    if page_number == 2:
        patches.append(art_header("목차", "프로그램 로드맵"))
        patches.append(toc_table_patch())
    elif page_number == 3:
        patches.append(art_header("프로그램 기간 및 분할", "당기기 / 밀기 / 하체 구조"))
        patches.append(split_method_table_patch())
        patches.append(art_header("디로드와 과부하 방법", "회복 관리와 진행", top=416.5))
    elif page_number == 4:
        patches.append(art_header("회복 영양, 밴드 워크 및 휴식 시간", "훈련 스트레스 관리"))
        patches.append(art_header("적절한 강도", "RPE 기준표 사용", top=468.6))
    elif page_number in WEEK_SPLIT_PAGES:
        week = sorted(WEEK_SPLIT_PAGES).index(page_number) + 1
        patches.append(art_header(f"{week}주차", "주간 트레이닝 개요"))
        patches.append(weekly_split_table_patch())
    else:
        header = workout_header_for_page(page_number)
        if header:
            week, day_key = header
            title, subtitle = DAY_TITLES[day_key]
            pump_suffix = " - 펌프 전용" if day_key in {"thursday", "friday", "saturday"} else ""
            patches.append(art_header(f"{week}주차 - {title}{pump_suffix}", subtitle, height=58.0))
    return patches


def detect_gold_lines(pix: fitz.Pixmap) -> list[float]:
    width, height, channels = pix.width, pix.height, pix.n
    samples = pix.samples
    rows: list[int] = []
    threshold = max(90, int(width * 0.32))
    for y in range(height):
        count = 0
        row_start = y * width * channels
        for x in range(width):
            i = row_start + x * channels
            r, g, b = samples[i], samples[i + 1], samples[i + 2]
            if 120 <= r <= 210 and 95 <= g <= 180 and b < 120 and r >= g >= b:
                count += 1
        if count >= threshold:
            rows.append(y)

    groups: list[list[int]] = []
    for y in rows:
        if not groups or y > groups[-1][1] + 1:
            groups.append([y, y])
        else:
            groups[-1][1] = y
    return [((start + end) / 2) / RENDER_ZOOM for start, end in groups]


def exercise_title_tops(spans: list[dict]) -> list[float]:
    tops: list[float] = []
    for span in spans:
        text = span.get("text", "").strip()
        style = span.get("style", "")
        top = style_number(style, "top")
        if re.fullmatch(r"\d+/", text) and top >= 88 and style_number(style, "left") < 60 and style_number(style, "font-size") >= 7:
            if not tops or abs(top - tops[-1]) > 2:
                tops.append(top)
    return tops


def exercise_underline_patches(page_number: int, spans: list[dict], gold_lines: list[float]) -> list[str]:
    if workout_header_for_page(page_number) is None:
        return []

    patches: list[str] = []
    for line in gold_lines:
        if 88 <= line <= 705:
            patches.append(
                f'<div class="exercise-rule-cover" style="left:42.000pt;top:{line - 0.900:.3f}pt;'
                'width:528.000pt;height:2.400pt"></div>'
            )

    title_tops = exercise_title_tops(spans)
    for top in title_tops:
        target = top + 14.8
        patches.append(
            f'<div class="exercise-rule" style="left:46.800pt;top:{target:.3f}pt;'
            'width:518.400pt;height:0.720pt"></div>'
        )
    return patches


def render_textless_page(src: fitz.Document, page_number: int, out_path: Path) -> list[float]:
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
    gold_lines = detect_gold_lines(pix)
    pix.save(out_path)
    single.close()
    return gold_lines


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
        parts.extend(exercise_underline_patches(page["number"], page["spans"], page.get("gold_lines", [])))
        parts.extend(page_art_patches(page["number"]))
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
    korean_pdf = fitz.open(KOREAN_PDF_PATH) if KOREAN_PDF_PATH.exists() else None

    pdf = fitz.open(PDF_PATH)
    pages: list[dict] = []
    mapped_paragraphs = 0
    for i, page in enumerate(pdf):
        number = i + 1
        gold_lines = render_textless_page(pdf, i, ASSETS / f"page-{number:03d}-background.png")
        if korean_pdf is not None and i == pdf.page_count - 1:
            spans = closing_page_spans(korean_pdf[i])
            used_paragraphs = len(spans)
        elif korean_pdf is not None:
            spans = extract_existing_text_spans(korean_pdf[i])
            used_paragraphs = len(spans)
            if not spans:
                page_sources = page_aligned_text[i] if i < len(page_aligned_text) and page_aligned_text[i] else visible_paragraphs
                spans, used_paragraphs = extract_spans(page, page_sources)
        else:
            page_sources = page_aligned_text[i] if i < len(page_aligned_text) and page_aligned_text[i] else visible_paragraphs
            spans, used_paragraphs = extract_spans(page, page_sources)
        mapped_paragraphs += used_paragraphs
        pages.append(
            {
                "number": number,
                "width": page.rect.width,
                "height": page.rect.height,
                "spans": spans,
                "gold_lines": gold_lines,
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
    if korean_pdf is not None:
        korean_pdf.close()
    print(json.dumps(metadata, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
