import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PY = ROOT / ".codex_local_py"
if LOCAL_PY.exists():
    sys.path.insert(0, str(LOCAL_PY))

import fitz  # noqa: E402


EXERCISE_RE = re.compile(r"^\s*\d+\s*/")
GOLD = (0.8196078539, 0.6941176653, 0.2941176593)
WHITE = (1, 1, 1)


def is_gold(color) -> bool:
    if not color:
        return False
    return abs(color[0] - GOLD[0]) < 0.08 and abs(color[1] - GOLD[1]) < 0.08 and abs(color[2] - GOLD[2]) < 0.08


def cover_old_gold_lines(page) -> int:
    doc = page.parent
    page.clean_contents()
    removed = 0
    pattern = re.compile(
        rb"q \.81960788 \.69411769 \.29411767 RG 1 j 1 w "
        rb"[-0-9.]+ [-0-9.]+ m [-0-9.]+ [-0-9.]+ l S Q"
    )
    for xref in page.get_contents():
        stream = doc.xref_stream(xref)
        stream, count = pattern.subn(b"", stream)
        if count:
            doc.update_stream(xref, stream)
            removed += count
    return removed


def exercise_heading_boxes(page):
    boxes = []
    text = page.get_text("dict")
    for block in text.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            line_text = "".join(span.get("text", "") for span in spans).strip()
            if not EXERCISE_RE.match(line_text):
                continue
            # Avoid tiny table/list text accidentally matching.
            max_size = max((span.get("size", 0) for span in spans), default=0)
            if max_size < 8:
                continue
            boxes.append(fitz.Rect(line["bbox"]))
    return boxes


def draw_attached_underlines(page, boxes) -> int:
    count = 0
    for box in boxes:
        y = box.y1 + 6
        if y > page.rect.height - 35:
            continue
        page.draw_line(
            fitz.Point(45.5, y),
            fitz.Point(page.rect.width - 41.5, y),
            color=GOLD,
            width=0.8,
            overlay=True,
        )
        count += 1
    return count


def fix_pdf(source: Path, output: Path) -> None:
    doc = fitz.open(source)
    removed = 0
    added = 0
    for page in doc:
        boxes = exercise_heading_boxes(page)
        if not boxes:
            continue
        removed += cover_old_gold_lines(page)
        added += draw_attached_underlines(page, boxes)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output, garbage=4, deflate=True)
    doc.close()
    print(f"Wrote {output} (covered {removed} old line(s), drew {added} attached underline(s))")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    fix_pdf(args.source, args.output)


if __name__ == "__main__":
    main()
