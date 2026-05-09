import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".codex_local_py"))

import fitz


ROOT = Path(__file__).resolve().parents[1]
INPUT_PDF = ROOT / "korean_exports" / "final" / "CM Strength Dynasty conv Korean.pdf"
OUTPUT_PDF = ROOT / "korean_exports" / "dynasty_pub_pass" / "CM Strength Dynasty Korean Publishing Pass.pdf"

FONT_REG = r"C:\Windows\Fonts\malgun.ttf"
FONT_BOLD = r"C:\Windows\Fonts\malgunbd.ttf"
FONT_REG_NAME = "cm_kr"
FONT_BOLD_NAME = "cm_kr_bold"

BLACK = (0.04, 0.04, 0.04)
WHITE = (1, 1, 1)
GOLD = (0.71, 0.64, 0.35)
TEXT = (0.05, 0.05, 0.05)
RED = (0.84, 0.05, 0.08)


OVERVIEW_PAGES = {
    5: 1,
    14: 2,
    21: 3,
    28: 4,
    36: 5,
    43: 6,
    50: 7,
    57: 8,
    64: 9,
    71: 10,
    78: 11,
    85: 12,
}

WORKOUT_PAGES = {
    6: (1, "월요일", "풀 운동"),
    8: (1, "화요일", "푸시 운동"),
    10: (1, "수요일", "하체 운동"),
    11: (1, "목요일", "풀 운동 - 펌프 전용"),
    12: (1, "금요일", "푸시 운동 - 펌프 전용"),
    13: (1, "토요일", "하체 운동 - 펌프 전용"),
    15: (2, "월요일", "풀 운동"),
    16: (2, "화요일", "푸시 운동"),
    17: (2, "수요일", "하체 운동"),
    18: (2, "목요일", "풀 운동 - 펌프 전용"),
    19: (2, "금요일", "푸시 운동 - 펌프 전용"),
    20: (2, "토요일", "하체 운동 - 펌프 전용"),
    22: (3, "월요일", "풀 운동"),
    23: (3, "화요일", "푸시 운동"),
    24: (3, "수요일", "하체 운동"),
    25: (3, "목요일", "풀 운동 - 펌프 전용"),
    26: (3, "금요일", "푸시 운동 - 펌프 전용"),
    27: (3, "토요일", "하체 운동 - 펌프 전용"),
    29: (4, "월요일", "풀 운동"),
    30: (4, "화요일", "푸시 운동"),
    32: (4, "수요일", "하체 운동"),
    33: (4, "목요일", "풀 운동 - 펌프 전용"),
    34: (4, "금요일", "푸시 운동 - 펌프 전용"),
    35: (4, "토요일", "하체 운동 - 펌프 전용"),
    37: (5, "월요일", "풀 운동"),
    38: (5, "화요일", "푸시 운동"),
    39: (5, "수요일", "하체 운동"),
    40: (5, "목요일", "풀 운동 - 펌프 전용"),
    41: (5, "금요일", "푸시 운동 - 펌프 전용"),
    42: (5, "토요일", "하체 운동 - 펌프 전용"),
    44: (6, "월요일", "풀 운동"),
    45: (6, "화요일", "푸시 운동"),
    46: (6, "수요일", "하체 운동"),
    47: (6, "목요일", "풀 운동 - 펌프 전용"),
    48: (6, "금요일", "푸시 운동 - 펌프 전용"),
    49: (6, "토요일", "하체 운동 - 펌프 전용"),
    51: (7, "월요일", "풀 운동"),
    52: (7, "화요일", "푸시 운동"),
    53: (7, "수요일", "하체 운동"),
    54: (7, "목요일", "풀 운동 - 펌프 전용"),
    55: (7, "금요일", "푸시 운동 - 펌프 전용"),
    56: (7, "토요일", "하체 운동 - 펌프 전용"),
    58: (8, "월요일", "풀 운동"),
    59: (8, "화요일", "푸시 운동"),
    60: (8, "수요일", "하체 운동"),
    61: (8, "목요일", "풀 운동 - 펌프 전용"),
    62: (8, "금요일", "푸시 운동 - 펌프 전용"),
    63: (8, "토요일", "하체 운동 - 펌프 전용"),
    65: (9, "월요일", "풀 운동"),
    66: (9, "화요일", "푸시 운동"),
    67: (9, "수요일", "하체 운동"),
    68: (9, "목요일", "풀 운동 - 펌프 전용"),
    69: (9, "금요일", "푸시 운동 - 펌프 전용"),
    70: (9, "토요일", "하체 운동 - 펌프 전용"),
    72: (10, "월요일", "풀 운동"),
    73: (10, "화요일", "푸시 운동"),
    74: (10, "수요일", "하체 운동"),
    75: (10, "목요일", "풀 운동 - 펌프 전용"),
    76: (10, "금요일", "푸시 운동 - 펌프 전용"),
    77: (10, "토요일", "하체 운동 - 펌프 전용"),
    79: (11, "월요일", "풀 운동"),
    80: (11, "화요일", "푸시 운동"),
    81: (11, "수요일", "하체 운동"),
    82: (11, "목요일", "풀 운동 - 펌프 전용"),
    83: (11, "금요일", "푸시 운동 - 펌프 전용"),
    84: (11, "토요일", "하체 운동 - 펌프 전용"),
    86: (12, "월요일", "풀 운동"),
    88: (12, "화요일", "푸시 운동"),
    89: (12, "수요일", "하체 운동"),
    90: (12, "목요일", "풀 운동 - 펌프 전용"),
    91: (12, "금요일", "푸시 운동 - 펌프 전용"),
    92: (12, "토요일", "하체 운동 - 펌프 전용"),
}

SUNDAY_BARS = {13, 20, 27, 35, 42, 49, 56, 63, 70, 77, 84, 92}

TOC_ROWS = [
    ("프로그램 기간 및 분할", "—"),
    ("1주차", "—"),
    ("2주차", "—"),
    ("3주차", "—"),
    ("4주차", "—"),
    ("5주차", "—"),
    ("6주차", "—"),
    ("7주차", "—"),
    ("8주차", "—"),
    ("9주차", "—"),
    ("10주차", "—"),
    ("11주차", "—"),
    ("12주차", "—"),
]

WEEKLY_NUMBERS = {
    1: [(8, 28), (8, 27), (5, 21), (7, 27), (7, 28), (5, 18), (0, 0)],
    2: [(8, 29), (8, 27), (5, 21), (7, 27), (7, 27), (5, 19), (0, 0)],
    3: [(8, 31), (8, 27), (5, 21), (7, 29), (7, 28), (5, 19), (0, 0)],
    4: [(8, 32), (8, 27), (6, 20), (7, 30), (7, 28), (4, 17), (0, 0)],
    5: [(8, 33), (8, 30), (6, 22), (7, 30), (7, 28), (4, 18), (0, 0)],
    6: [(8, 34), (8, 30), (5, 21), (7, 30), (7, 28), (5, 21), (0, 0)],
    7: [(7, 31), (8, 28), (6, 24), (7, 30), (7, 28), (5, 22), (0, 0)],
    8: [(7, 31), (8, 28), (5, 20), (7, 30), (7, 28), (5, 22), (0, 0)],
    9: [(8, 32), (8, 28), (5, 19), (7, 30), (7, 28), (5, 22), (0, 0)],
    10: [(8, 32), (8, 28), (5, 17), (7, 30), (7, 27), (5, 18), (0, 0)],
    11: [(8, 33), (8, 28), (5, 16), (7, 30), (7, 27), (5, 19), (0, 0)],
    12: [(8, 32), (8, 29), (5, 19), (7, 30), (7, 27), (5, 19), (0, 0)],
}


def ensure_fonts(page: fitz.Page) -> None:
    page.insert_font(fontname=FONT_REG_NAME, fontfile=FONT_REG)
    page.insert_font(fontname=FONT_BOLD_NAME, fontfile=FONT_BOLD)


def font_length(text: str, size: float, bold: bool = False) -> float:
    return fitz.Font(fontfile=FONT_BOLD if bold else FONT_REG).text_length(text, fontsize=size)


def fit_size(text: str, max_width: float, start: float, minimum: float, bold: bool = False) -> float:
    size = start
    while size > minimum and font_length(text, size, bold) > max_width:
        size -= 0.15
    return max(size, minimum)


def insert_text(page, x, y, text, size=8.0, bold=False, color=TEXT, max_width=None):
    ensure_fonts(page)
    text = clean_text(text)
    if max_width:
        size = fit_size(text, max_width, size, max(5.2, size - 1.8), bold)
    page.insert_text(
        fitz.Point(x, y),
        text,
        fontname=FONT_BOLD_NAME if bold else FONT_REG_NAME,
        fontsize=size,
        color=color,
        overlay=True,
    )


def insert_box(page, rect, text, size=8.0, bold=False, color=TEXT, align=0, lineheight=1.15):
    ensure_fonts(page)
    page.insert_textbox(
        rect,
        text,
        fontname=FONT_BOLD_NAME if bold else FONT_REG_NAME,
        fontsize=size,
        color=color,
        align=align,
        lineheight=lineheight,
        overlay=True,
    )


def clean_text(text: str) -> str:
    text = text.replace("\u200b", "")
    text = re.sub(r"\s+", " ", text).strip()
    replacements = [
        ("절단", "감량기"),
        ("통증을 다음 단계로", "훈련 자극을 다음 단계로"),
        ("기본일", "베이스 데이"),
        ("펌프일", "펌프 데이"),
        ("휴식 더 많으므로", "휴식이 더 많으므로"),
        ("기준일", "베이스 데이"),
        ("알아 두십시오", "알아두세요"),
        ("설치", "추가"),
        ("세트이(가)", "세트는"),
        ("세트이", "세트가"),
        ("세트을", "세트를"),
        ("세트은", "세트는"),
        ("총 작업량 세트", "총 작업 세트"),
        ("작업량 세트", "총 작업 세트"),
        ("TOTAL WORK 세트", "총 작업 세트"),
        ("연습세트", "작업 세트"),
        ("낮", "요일"),
        ("집중하다", "초점"),
        ("당기다", "풀"),
        ("끄다", "휴식"),
        ("돌아가기", "등"),
        ("위 다리", "하체"),
        ("윗다리", "하체"),
        ("어퍼 다리", "하체"),
        ("상부 다리", "하체"),
        ("햄을", "햄스트링을"),
        ("근육 운동", "근육 훈련"),
        ("목표: 펌프 활성화 및 시작", "목표: 활성화 및 시작 펌프"),
        ("목표: 폭발적인 훈련", "목표: 폭발적으로 훈련"),
        ("프로팁", "프로 팁"),
        ("RPE :", "RPE:"),
        ("목표 :", "목표:"),
        ("쪼개다", "분할"),
        ("반복을 탱크", "여유 반복"),
        ("탱크에 반복 몇 개", "여유 반복 몇 개"),
        ("탱크에 1회 더", "여유 1회"),
        ("탱크에 2회 더", "여유 2회"),
        ("슈퍼세트 WITH", "슈퍼세트로 이어서"),
        ("SUPERSET WITH", "슈퍼세트로 이어서"),
        ("Supramax", "수프라맥스"),
        ("supraMax", "수프라맥스"),
        ("LIGHT", "가볍게"),
        ("Heavy", "무겁게"),
        ("FIRE", "불타는 느낌"),
        ("EZ 바", "EZ바"),
        ("Vbar", "V바"),
        ("JM프레스", "JM 프레스"),
        ("1.5s", "1.5회 반복"),
        ("iso 홀드", "아이소 홀드"),
        ("ROM", "가동범위"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    if text == "총":
        return ""
    if text.endswith(" 총"):
        text = text[:-2].rstrip()
    text = re.sub(r"세트 of (\d+)", r"\1회 세트", text, flags=re.I)
    text = re.sub(r"(\d+)\s*개 중\s*(\d+)\s*개(?:의)?\s*세트", r"\2세트 x \1회", text)
    text = re.sub(r"(\d+)\s*개 중\s*(\d+)\s*회", r"\2세트 x \1회", text)
    text = re.sub(r"(\d+)\s*개의 반복", r"\1회 반복", text)
    text = re.sub(r"(\d+)\s*반복", r"\1회 반복", text)
    text = re.sub(r"(\d+)\s+세트", r"\1세트", text)
    text = re.sub(r"\s+([.,:;!?])", r"\1", text)
    return text


def cover(page, rect, fill=WHITE):
    page.draw_rect(rect, color=fill, fill=fill, width=0, overlay=True)


def draw_bar(page, y, title, subtitle=None):
    cover(page, fitz.Rect(42, y - 2, 575, y + 58), WHITE)
    cover(page, fitz.Rect(45, y, 572, y + 40), BLACK)
    insert_text(page, 53, y + 18, title, size=13.2, bold=True, color=GOLD, max_width=430)
    if subtitle:
        insert_text(page, 53, y + 31, subtitle, size=7.2, color=WHITE, max_width=430)


def draw_toc(page):
    cover(page, fitz.Rect(42, 44, 575, 475), WHITE)
    draw_bar(page, 48, "목차", "프로그램 로드맵")
    x0, y0, w, row_h = 46, 125, 528, 20.5
    col1 = 265
    page.draw_rect(fitz.Rect(x0, y0, x0 + w, y0 + row_h), color=BLACK, fill=BLACK, width=0.6, overlay=True)
    insert_text(page, x0 + 8, y0 + 14, "섹션", size=7.3, bold=True, color=WHITE)
    insert_text(page, x0 + col1 + 8, y0 + 14, "페이지", size=7.3, bold=True, color=WHITE)
    for i, (section, page_no) in enumerate(TOC_ROWS):
        y = y0 + row_h * (i + 1)
        page.draw_rect(fitz.Rect(x0, y, x0 + w, y + row_h), color=BLACK, fill=WHITE, width=0.45, overlay=True)
        page.draw_line(fitz.Point(x0 + col1, y), fitz.Point(x0 + col1, y + row_h), color=BLACK, width=0.45, overlay=True)
        insert_text(page, x0 + 8, y + 14, section, size=7.4, color=TEXT, max_width=230)
        insert_text(page, x0 + col1 + 8, y + 14, page_no, size=7.4, color=TEXT)


def draw_program_split(page):
    cover(page, fitz.Rect(44, 114, 572, 376), WHITE)
    intro = (
        "이 프로그램은 오프시즌이나 근육량 증가 단계에 특히 잘 맞습니다. 감량기에도 사용할 수 있지만, "
        "그때는 회복 관리가 더 중요합니다. 시작 전에는 식단, 수면, 스트레스, 회복 상태를 먼저 확인하세요.\n\n"
        "풀을 푸시보다 먼저 배치한 이유는 하체와 등 베이스 데이 사이에 허리 부담을 분산하기 위해서입니다. "
        "스쿼트와 데드리프트 계열을 연속으로 몰아넣기보다, 주간 구조 안에서 강도를 더 예측 가능하게 만듭니다.\n\n"
        "주간 구성은 6일 훈련으로 적혀 있지만 대부분의 사람은 펌프 데이 하나를 빼서 주 5일로 운영해도 좋습니다. "
        "회복이 부족하거나 일정이 바쁘다면 강점 부위를 줄이고 약점 보완에 집중하세요."
    )
    insert_box(page, fitz.Rect(46, 116, 566, 230), intro, size=7.15, color=TEXT, lineheight=1.12)
    insert_text(page, 46, 248, "훈련 분할 옵션", size=8.4, bold=True)
    rows = [
        ["유형", "월", "화", "수", "목", "금", "토", "일"],
        ["회복 우선", "풀", "푸시", "하체", "풀(펌프)", "푸시(펌프)", "하체(펌프)", "휴식"],
        ["푸시 집중", "풀", "푸시", "하체", "휴식", "푸시(펌프)", "하체(펌프)", "휴식"],
        ["풀 집중", "풀", "푸시", "하체", "휴식", "풀(펌프)", "하체(펌프)", "휴식"],
        ["하체 집중", "풀", "푸시", "하체", "휴식", "푸시(펌프)", "하체(펌프)", "휴식"],
    ]
    draw_table(page, 46, 266, 528, 15.0, rows, col_widths=[86, 60, 60, 60, 70, 72, 76, 44])
    draw_bar(page, 420, "디로드와 과부하 방식", "회복 관리와 진행 기준")
    deload = (
        "디로드는 필요할 때 언제든지 1주간 넣을 수 있습니다. 수행력이 떨어지고, 헬스장에 가고 싶은 의욕이 계속 낮고, "
        "회복이 밀린다면 강도를 낮추는 것이 더 좋은 선택일 수 있습니다.\n\n"
        "디로드 주간에는 어떤 주차를 따라도 되지만 두 가지를 지키세요. 하루 볼륨은 약 20% 줄이고, 실패 지점까지 가지 않습니다. "
        "모든 세트는 RPE 8 이하로 관리합니다.\n\n"
        "이 프로그램의 주요 과부하 방식은 볼륨을 계속 늘리는 것이 아니라, 베이스 운동에서 반복 수와 수행 품질을 올리는 것입니다. "
        "운동은 대략 4주마다 바뀌며, 펌프 작업은 혈류와 훈련 자극을 보완합니다."
    )
    cover(page, fitz.Rect(44, 485, 572, 670), WHITE)
    insert_box(page, fitz.Rect(46, 494, 566, 650), deload, size=7.1, color=TEXT, lineheight=1.14)


def draw_recovery_page(page):
    cover(page, fitz.Rect(44, 100, 572, 735), WHITE)
    draw_bar(page, 48, "회복 영양, 밴드, 휴식 시간", "훈련 스트레스를 버티는 기준")
    insert_text(page, 46, 128, "회복 영양", size=9.8, bold=True)
    page.draw_line(fitz.Point(46, 136), fitz.Point(572, 136), color=GOLD, width=0.5, overlay=True)
    recovery = (
        "이 정도의 볼륨과 강도에서는 회복이 성과를 결정합니다. 운동 중 EAA, 전해질, 탄수화물을 활용하면 세션 중 연료 공급과 "
        "회복 관리에 도움이 될 수 있습니다.\n\n"
        "남성은 보통 EAA 10g과 탄수화물 40-50g, 여성은 EAA 10g과 탄수화물 20-30g부터 시작해 체격과 훈련량에 맞게 조절합니다. "
        "목표는 통증을 줄이고 다음 세션의 수행력을 유지하는 것입니다.\n\n"
        "훈련 밖에서는 스트레스 관리와 충분한 수면을 우선하세요. 회복은 프로그램 밖에서 완성됩니다."
    )
    insert_box(page, fitz.Rect(46, 144, 566, 260), recovery, size=7.3, lineheight=1.15)
    insert_text(page, 46, 296, "밴드 사용", size=9.3, bold=True)
    page.draw_line(fitz.Point(46, 304), fitz.Point(572, 304), color=GOLD, width=0.5, overlay=True)
    bands = (
        "밴드 사용은 선택 사항입니다. 추가하려면 EliteFTS.net 기준으로 오렌지 마이크로 미니, 빨간 롱 프로 미니, "
        "빨간 쇼트 프로 미니, 프로 라이트 밴드를 준비하면 대부분의 밴드 동작에 대응할 수 있습니다."
    )
    insert_box(page, fitz.Rect(46, 312, 566, 360), bands, size=7.25, lineheight=1.15)
    insert_text(page, 46, 392, "휴식 시간", size=9.3, bold=True)
    page.draw_line(fitz.Point(46, 400), fitz.Point(572, 400), color=GOLD, width=0.5, overlay=True)
    rest = (
        "별도 지시가 없으면 1단계 활성화/펌프는 2분, 2단계 폭발적 훈련은 3분, 3단계 수프라맥스 펌프는 2분, "
        "4단계 스트레치 포지션 훈련은 90초를 기준으로 합니다. 후반부 펌프 작업은 보통 60초 휴식입니다."
    )
    insert_box(page, fitz.Rect(46, 408, 566, 455), rest, size=7.25, lineheight=1.13)
    draw_bar(page, 468, "적절한 강도", "RPE 기준 사용")
    intensity = (
        "실패 지점과의 거리를 정확히 관리해야 결과가 안정됩니다. 너무 쉽게 가면 자극이 부족하고, 너무 자주 실패하면 회복이 무너질 수 있습니다.\n\n"
        "RPE 6은 워밍업처럼 여유롭고, RPE 7은 2-3회 여유, RPE 8은 약 2회 여유, RPE 8.5는 1회 여유, "
        "RPE 9는 좋은 자세로 거의 실패, RPE 10은 완벽한 반복 이후 실패입니다. RPE 11 이상은 고강도 기법으로 실패 지점을 넘어가는 세트입니다.\n\n"
        "대부분의 작업 세트는 RPE 7 이상으로 계산합니다. 각 운동의 RPE 지시를 우선하세요."
    )
    insert_box(page, fitz.Rect(46, 535, 566, 705), intensity, size=7.35, lineheight=1.15)


def draw_table(page, x, y, width, row_h, rows, col_widths=None):
    cols = len(rows[0])
    if col_widths is None:
        col_widths = [width / cols] * cols
    scale = width / sum(col_widths)
    col_widths = [w * scale for w in col_widths]
    height = row_h * len(rows)
    page.draw_rect(fitz.Rect(x, y, x + width, y + height), color=BLACK, fill=WHITE, width=0.55, overlay=True)
    page.draw_rect(fitz.Rect(x, y, x + width, y + row_h), color=BLACK, fill=BLACK, width=0, overlay=True)
    xpos = x
    for w in col_widths[:-1]:
        xpos += w
        page.draw_line(fitz.Point(xpos, y), fitz.Point(xpos, y + height), color=BLACK, width=0.45, overlay=True)
    for i in range(1, len(rows)):
        yy = y + i * row_h
        page.draw_line(fitz.Point(x, yy), fitz.Point(x + width, yy), color=BLACK, width=0.45, overlay=True)
    for r, row in enumerate(rows):
        cx = x
        for c, cell in enumerate(row):
            rect = fitz.Rect(cx + 3, y + r * row_h + 3, cx + col_widths[c] - 3, y + (r + 1) * row_h - 2)
            color = GOLD if r == 0 else TEXT
            insert_box(page, rect, str(cell), size=5.8 if len(str(cell)) > 8 else 6.4, bold=(r == 0 or c == 0), color=color, align=1, lineheight=1.0)
            cx += col_widths[c]


def draw_weekly_overview(page, week):
    y0 = 128 if week in {2, 3, 5, 6} else 150
    if week == 1:
        y0 = 172
    if week == 6:
        y0 = 194
    cover(page, fitz.Rect(44, 90, 602, min(430, y0 + 230)), WHITE)
    insert_text(page, 46, max(122, y0 - 38), "주간 분할", size=9.0, bold=True)
    page.draw_line(fitz.Point(46, max(130, y0 - 30)), fitz.Point(572, max(130, y0 - 30)), color=GOLD, width=0.5, overlay=True)
    days = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    focus = ["풀", "푸시", "하체", "풀(펌프)", "푸시(펌프)", "하체(펌프)", "휴식"]
    rows = [["요일", "초점", "운동", "세트"]]
    for day, f, (ex, sets) in zip(days, focus, WEEKLY_NUMBERS[week]):
        rows.append([day, f, ex, sets])
    draw_table(page, 50, y0, 535, 18.0, rows, col_widths=[130, 130, 130, 145])


def redraw_line(page, line):
    rect = fitz.Rect(line["bbox"])
    raw = " ".join(span["text"] for span in line["spans"])
    text = clean_text(raw)
    if not text or text == "CM Strength Dynasty":
        return
    if rect.y0 < 94 or rect.y0 > 725:
        return
    if text in {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}:
        return

    is_exercise = bool(re.match(r"^\d+\s*/", text))
    is_metric = text.startswith(("총 작업", "RPE", "목표:", "참고:", "노트:"))
    is_red = text.startswith(("프로 팁", "경고", "SUPERSET", "슈퍼세트"))
    cover(page, rect + (-1.2, -0.8, 1.2, 1.0), WHITE)
    size = 8.1 if is_exercise else 6.95
    bold = is_exercise or is_metric
    color = RED if is_red else (GOLD if is_metric else TEXT)
    baseline = rect.y0 + (9.4 if is_exercise else 8.2)
    insert_text(page, rect.x0, baseline, text, size=size, bold=bold, color=color, max_width=570 - rect.x0)
    if is_exercise:
        page.draw_line(fitz.Point(46, rect.y1 + 0.5), fitz.Point(572, rect.y1 + 0.5), color=GOLD, width=0.5, overlay=True)


def redraw_body_lines(page, page_no):
    skip_areas = []
    if page_no in OVERVIEW_PAGES:
        skip_areas.append(fitz.Rect(40, 95, 590, 370))
    if page_no in {2, 3, 4, 93}:
        return
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            rect = fitz.Rect(line["bbox"])
            if any(area.intersects(rect) for area in skip_areas):
                continue
            redraw_line(page, line)


def apply_headers(page, page_no):
    if page_no == 2:
        draw_toc(page)
    elif page_no == 3:
        draw_bar(page, 48, "프로그램 기간과 분할", "풀·푸시·하체 구조")
        draw_program_split(page)
    elif page_no == 4:
        draw_recovery_page(page)
    elif page_no in OVERVIEW_PAGES:
        week = OVERVIEW_PAGES[page_no]
        draw_bar(page, 48, f"{week}주차", "주간 훈련 개요")
        draw_weekly_overview(page, week)
    elif page_no in WORKOUT_PAGES:
        week, day, focus = WORKOUT_PAGES[page_no]
        draw_bar(page, 48, f"{week}주차 - {day} - {focus}")
    if page_no in SUNDAY_BARS:
        week = WORKOUT_PAGES.get(page_no, (None,))[0]
        if week:
            draw_sunday_bar(page, week)


def draw_sunday_bar(page, week):
    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
    rows = []
    for y in range(500, pix.height):
        dark = 0
        for x in range(30, pix.width - 30, 3):
            r, g, b = pix.samples[(y * pix.width + x) * 3:(y * pix.width + x) * 3 + 3]
            if r < 35 and g < 35 and b < 35:
                dark += 1
        if dark > 125:
            rows.append(y)
    y = 650
    if rows:
        y = max(500, rows[0] - 8)
    cover(page, fitz.Rect(42, y - 3, 575, y + 45), WHITE)
    draw_bar(page, y, f"{week}주차 - 일요일 - 휴식 - 가족과 보내는 날")


def draw_cover_overlay(page):
    ensure_fonts(page)
    # Preserve the cover image and add a Korean production subtitle over the lower title area.
    page.draw_rect(fitz.Rect(34, 616, 430, 708), color=BLACK, fill=BLACK, width=0, overlay=True)
    insert_text(page, 45, 646, "DYNASTY", size=23, bold=True, color=GOLD, max_width=245)
    insert_text(page, 47, 666, "12주 하이퍼트로피 프로그램", size=10.4, bold=True, color=WHITE, max_width=245)
    insert_text(page, 47, 681, "풀 / 푸시 / 하체 구조", size=8.0, color=WHITE, max_width=245)
    insert_text(page, 47, 702, "CM Strength", size=8.8, bold=True, color=GOLD, max_width=245)


def draw_final_page(page):
    cover(page, fitz.Rect(42, 548, 575, 704), WHITE)
    text = (
        "CM Strength를 선택해주셔서 감사합니다. 이 프로그램은 체육관에 들어갈 때마다 구조, 목적, 강도를 제공하기 위해 만들어졌습니다. "
        "계획을 따르고, 진행 상황을 기록하고, 의도를 가지고 훈련하며, 훈련 밖의 회복까지 존중하세요.\n\n"
        "목표는 단순히 프로그램을 끝내는 것이 아닙니다. 더 강하고, 더 절제되어 있으며, 체육관 안팎에서 스스로의 가능성을 더 확신하는 모습으로 마무리하는 것입니다.\n\n"
        "— Coach Chili"
    )
    insert_box(page, fitz.Rect(56, 558, 556, 685), text, size=12.2, bold=False, color=TEXT, align=1, lineheight=1.18)


def main():
    if not INPUT_PDF.exists():
        raise FileNotFoundError(INPUT_PDF)
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(INPUT_PDF)
    for idx, page in enumerate(doc, start=1):
        ensure_fonts(page)
        if idx == 1:
            draw_cover_overlay(page)
            continue
        redraw_body_lines(page, idx)
        apply_headers(page, idx)
        if idx == 93:
            draw_final_page(page)
    if OUTPUT_PDF.exists():
        OUTPUT_PDF.unlink()
    doc.save(OUTPUT_PDF, garbage=4, deflate=True)
    doc.close()
    print(OUTPUT_PDF)


if __name__ == "__main__":
    main()
