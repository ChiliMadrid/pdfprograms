import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".codex_local_py"))

import fitz


FONT_REG = r"C:\Windows\Fonts\malgun.ttf"
FONT_BOLD = r"C:\Windows\Fonts\malgunbd.ttf"
FONT_REG_NAME = "cm_layout_kr"
FONT_BOLD_NAME = "cm_layout_kr_bold"

BLACK = (0.0, 0.0, 0.0)
WHITE = (1.0, 1.0, 1.0)
GOLD = (0.7137, 0.6353, 0.3490)
TEXT = (0.04, 0.04, 0.04)

EXERCISE_RE = re.compile(r"^\s*\d+\s*/")
FOOTER_RE = re.compile(r"^CM\s*(Strength|강도)", re.I)


def clean(text: str) -> str:
    text = text.replace("\u200b", "")
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("A BS", "복근").replace("Abs", "복근")
    text = text.replace("연습문제", "운동")
    return text


def ensure_fonts(page: fitz.Page) -> None:
    page.insert_font(fontname=FONT_REG_NAME, fontfile=FONT_REG)
    page.insert_font(fontname=FONT_BOLD_NAME, fontfile=FONT_BOLD)


def text_len(text: str, size: float, bold: bool = False) -> float:
    font = fitz.Font(fontfile=FONT_BOLD if bold else FONT_REG)
    return font.text_length(text, fontsize=size)


def fit_size(text: str, width: float, start: float, min_size: float, bold: bool = False) -> float:
    size = start
    while size > min_size and text_len(text, size, bold) > width:
        size -= 0.2
    return size


def insert_center(page: fitz.Page, rect: fitz.Rect, text: str, bold: bool = False, color=TEXT):
    ensure_fonts(page)
    text = clean(text)
    size = fit_size(text, rect.width - 6, 6.2, 4.5, bold)
    width = text_len(text, size, bold)
    x = rect.x0 + max(3, (rect.width - width) / 2)
    y = rect.y0 + (rect.height + size) / 2 - 1.2
    page.insert_text(
        fitz.Point(x, y),
        text,
        fontname=FONT_BOLD_NAME if bold else FONT_REG_NAME,
        fontsize=size,
        color=color,
    )


def insert_left(page: fitz.Page, point: fitz.Point, text: str, size: float, bold: bool = False, color=TEXT):
    ensure_fonts(page)
    page.insert_text(
        point,
        clean(text),
        fontname=FONT_BOLD_NAME if bold else FONT_REG_NAME,
        fontsize=size,
        color=color,
    )


def page_text_lines(page: fitz.Page):
    lines = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            text = clean(" ".join(span["text"] for span in line["spans"]))
            if not text or FOOTER_RE.match(text):
                continue
            lines.append({"text": text, "rect": fitz.Rect(line["bbox"])})
    return sorted(lines, key=lambda item: (item["rect"].y0, item["rect"].x0))


def table_rects(page: fitz.Page):
    rects = []
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        fill = drawing.get("fill")
        if not rect or not fill:
            continue
        if rect.y0 > 245 or rect.width < 260 or rect.height < 35 or rect.height > 130:
            continue
        if fill[0] > 0.95 and fill[1] > 0.95 and fill[2] > 0.95:
            rects.append(rect)
    # De-duplicate close rectangles.
    unique = []
    for rect in rects:
        if not any(abs(rect.y0 - other.y0) < 2 and abs(rect.x0 - other.x0) < 2 for other in unique):
            unique.append(rect)
    return unique


def header_rect(page: fitz.Page):
    best = None
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        fill = drawing.get("fill")
        if not rect or not fill:
            continue
        if rect.y0 > 90 or rect.width < 300 or rect.height < 18:
            continue
        if fill[0] < 0.08 and fill[1] < 0.08 and fill[2] < 0.08:
            if best is None or rect.width > best.width:
                best = rect
    return best


def redraw_header(page: fitz.Page, lines):
    rect = header_rect(page)
    if rect is None:
        return
    header_lines = [
        line for line in lines
        if rect.x0 - 2 <= line["rect"].x0 <= rect.x1 and rect.y0 - 8 <= line["rect"].y0 <= rect.y1 + 2
    ]
    if not header_lines:
        return
    header_lines.sort(key=lambda item: (item["rect"].y0, item["rect"].x0))
    page.draw_rect(rect, color=(0.04, 0.04, 0.04), fill=(0.04, 0.04, 0.04), width=0, overlay=True)
    title = header_lines[0]["text"]
    title_size = fit_size(title, rect.width - 18, 8.7, 5.7, True)
    insert_left(page, fitz.Point(rect.x0 + 10, rect.y0 + 17), title, title_size, bold=True, color=GOLD)
    if len(header_lines) > 1:
        subtitle = header_lines[1]["text"]
        subtitle_size = fit_size(subtitle, rect.width - 18, 5.7, 4.4, False)
        insert_left(page, fitz.Point(rect.x0 + 10, rect.y0 + 31), subtitle, subtitle_size, bold=False, color=WHITE)


def group_rows(items, tolerance=10.0):
    rows = []
    for item in items:
        y = item["rect"].y0
        for row in rows:
            if abs(row[0]["rect"].y0 - y) <= tolerance:
                row.append(item)
                break
        else:
            rows.append([item])
    for row in rows:
        row.sort(key=lambda item: item["rect"].x0)
    return rows


def split_compact_cell(text: str):
    text = clean(text)
    match = re.match(r"^([^\d]+?)(\d.*)$", text)
    if match:
        left = clean(match.group(1))
        right = clean(match.group(2))
        return [left, right]
    return [text]


def normalize_rows(rows):
    normalized = []
    for row in rows:
        cells = [clean(item["text"]) for item in row]
        if len(cells) == 1:
            cells = split_compact_cell(cells[0])
        if len(cells) > 4:
            cells = cells[:4]
        normalized.append(cells)
    return [row for row in normalized if any(cell for cell in row)]


def cover_old_grid(page: fitz.Page, rect: fitz.Rect):
    # Paint over the old table strokes without blanking nearby body text.
    for drawing in page.get_drawings():
        drect = drawing.get("rect")
        color = drawing.get("color")
        if not drect or not color:
            continue
        if rect.intersects(drect) or (
            rect.x0 - 4 <= drect.x0 <= rect.x1 + 4 and rect.y0 - 8 <= drect.y0 <= rect.y1 + 8
        ):
            page.draw_line(
                fitz.Point(drect.x0, drect.y0),
                fitz.Point(drect.x1, drect.y1),
                color=WHITE,
                width=2.2,
                overlay=True,
            )


def redraw_table(page: fitz.Page, rect: fitz.Rect, lines):
    candidates = []
    for line in lines:
        lr = line["rect"]
        text = line["text"]
        if EXERCISE_RE.match(text) or len(text) > 72:
            continue
        if rect.x0 - 3 <= lr.x0 <= rect.x1 + 3 and rect.y0 - 30 <= lr.y0 <= rect.y1 - 3:
            candidates.append(line)
    if len(candidates) < 2:
        return False

    rows = normalize_rows(group_rows(candidates))
    if len(rows) < 2:
        return False

    col_count = max(2, max(len(row) for row in rows))
    col_count = min(col_count, 4)
    for row in rows:
        while len(row) < col_count:
            row.append("")

    cover_old_grid(page, rect)
    for line in candidates:
        r = line["rect"] + (-2, -1, 2, 2)
        page.draw_rect(r, color=WHITE, fill=WHITE, width=0, overlay=True)

    top = max(84, rect.y0)
    row_h = 15.8 if len(rows) <= 5 else 14.2
    height = row_h * len(rows)
    left = 39.5 if rect.x0 < 42 else rect.x0
    right = 572.5 if rect.x1 > 560 else rect.x1
    table = fitz.Rect(left, top, right, top + height)

    first_row_text = " ".join(rows[0])
    header = rows[0][0] in {"낮", "Day"} or ("집중" in first_row_text and "연습세트" in first_row_text)
    page.draw_rect(table, color=BLACK, fill=WHITE, width=0.65, overlay=True)
    if header:
        page.draw_rect(fitz.Rect(table.x0, table.y0, table.x1, table.y0 + row_h), color=BLACK, fill=BLACK, width=0, overlay=True)
    for i in range(1, len(rows)):
        y = table.y0 + row_h * i
        page.draw_line(fitz.Point(table.x0, y), fitz.Point(table.x1, y), color=BLACK, width=0.45, overlay=True)
    for c in range(1, col_count):
        x = table.x0 + table.width * c / col_count
        page.draw_line(fitz.Point(x, table.y0), fitz.Point(x, table.y1), color=BLACK, width=0.45, overlay=True)

    for r_i, row in enumerate(rows):
        for c_i, cell in enumerate(row[:col_count]):
            cell_rect = fitz.Rect(
                table.x0 + table.width * c_i / col_count,
                table.y0 + row_h * r_i,
                table.x0 + table.width * (c_i + 1) / col_count,
                table.y0 + row_h * (r_i + 1),
            )
            is_head = header and r_i == 0
            insert_center(page, cell_rect, cell, bold=is_head or c_i == 0, color=GOLD if is_head else TEXT)
    return True


def polish_underlines(page: fitz.Page, lines):
    for line in lines:
        if not EXERCISE_RE.match(line["text"]):
            continue
        rect = line["rect"]
        if rect.y0 < 70 or rect.y0 > 710:
            continue
        y = rect.y1 + 4.0
        for drawing in page.get_drawings():
            drect = drawing.get("rect")
            color = drawing.get("color")
            if not drect or not color:
                continue
            is_gold = color[0] > 0.55 and color[1] > 0.45 and color[2] < 0.45
            if is_gold and abs(drect.y0 - y) <= 8 and drect.x0 < 70 and drect.x1 > 520:
                page.draw_line(
                    fitz.Point(drect.x0, drect.y0),
                    fitz.Point(drect.x1, drect.y1),
                    color=WHITE,
                    width=1.8,
                    overlay=True,
                )
        page.draw_line(fitz.Point(45.5, y), fitz.Point(570.5, y), color=GOLD, width=0.55, overlay=True)


def polish(input_pdf: Path, output_pdf: Path):
    doc = fitz.open(input_pdf)
    for page in doc:
        lines = page_text_lines(page)
        for rect in table_rects(page):
            redraw_table(page, rect, lines)
        polish_underlines(page, lines)
        redraw_header(page, lines)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    if output_pdf.exists():
        output_pdf.unlink()
    doc.save(output_pdf, garbage=4, deflate=True)
    doc.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("output_pdf", type=Path)
    args = parser.parse_args()
    polish(args.input_pdf, args.output_pdf)


if __name__ == "__main__":
    main()
