import argparse
import re
import shutil
import sys
import zipfile
from pathlib import Path

from lxml import etree


NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = NS["w"]

WEEK_HEADING_RE = re.compile(r"^\s*\d+\s*주차\s*-")
EXERCISE_RE = re.compile(r"^\s*\d+\s*/")


def paragraph_text(paragraph) -> str:
    return "".join(node.text or "" for node in paragraph.xpath(".//w:t", namespaces=NS))


def set_paragraph_text(paragraph, text: str) -> None:
    nodes = paragraph.xpath(".//w:t", namespaces=NS)
    if not nodes:
        return
    nodes[0].text = text
    for node in nodes[1:]:
        node.text = ""


def set_run_size(paragraph, half_points: int) -> None:
    for rpr in paragraph.xpath(".//w:rPr", namespaces=NS):
        for tag in ("sz", "szCs"):
            node = rpr.find(f"w:{tag}", namespaces=NS)
            if node is None:
                node = etree.SubElement(rpr, f"{{{W}}}{tag}")
            node.set(f"{{{W}}}val", str(half_points))


def set_spacing(paragraph, before=None, after=None, line=None) -> None:
    ppr = paragraph.find("w:pPr", namespaces=NS)
    if ppr is None:
        ppr = etree.Element(f"{{{W}}}pPr")
        paragraph.insert(0, ppr)
    spacing = ppr.find("w:spacing", namespaces=NS)
    if spacing is None:
        spacing = etree.SubElement(ppr, f"{{{W}}}spacing")
    if before is not None:
        spacing.set(f"{{{W}}}before", str(before))
    if after is not None:
        spacing.set(f"{{{W}}}after", str(after))
    if line is not None:
        spacing.set(f"{{{W}}}line", str(line))
        spacing.set(f"{{{W}}}lineRule", "auto")


def set_keep_next(paragraph, enabled: bool) -> None:
    ppr = paragraph.find("w:pPr", namespaces=NS)
    if ppr is None:
        ppr = etree.Element(f"{{{W}}}pPr")
        paragraph.insert(0, ppr)
    node = ppr.find("w:keepNext", namespaces=NS)
    if enabled:
        if node is None:
            ppr.insert(0, etree.Element(f"{{{W}}}keepNext"))
    elif node is not None:
        ppr.remove(node)


def add_heading_border(paragraph) -> None:
    ppr = paragraph.find("w:pPr", namespaces=NS)
    if ppr is None:
        ppr = etree.Element(f"{{{W}}}pPr")
        paragraph.insert(0, ppr)
    bdr = ppr.find("w:pBdr", namespaces=NS)
    if bdr is None:
        bdr = etree.SubElement(ppr, f"{{{W}}}pBdr")
    bottom = bdr.find("w:bottom", namespaces=NS)
    if bottom is None:
        bottom = etree.SubElement(bdr, f"{{{W}}}bottom")
    bottom.set(f"{{{W}}}val", "single")
    bottom.set(f"{{{W}}}sz", "6")
    bottom.set(f"{{{W}}}space", "7")
    bottom.set(f"{{{W}}}color", "C9A33A")


def shorten_week_heading(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if "훈련 개요" in cleaned or "훈련 분할" in cleaned:
        match = re.match(r"^(\d+\s*주차)", cleaned)
        return f"{match.group(1)} - 훈련 개요" if match else cleaned

    # Keep only "N주차 - DAY - WORKOUT NAME 운동"; the detailed set summary
    # is represented in the grid immediately below.
    match = re.match(r"^(\d+\s*주차\s*-\s*[^-]+-\s*.+?운동)\b", cleaned)
    if match:
        return match.group(1)
    return cleaned


def clean_grid_text(text: str) -> str:
    cleaned = text
    cleaned = cleaned.replace("연습", "운동")
    cleaned = cleaned.replace("집중하다", "포커스")
    cleaned = cleaned.replace("꼬다", "휴식")
    cleaned = cleaned.replace("뒤쪽에", "등")
    cleaned = cleaned.replace("가슴/삼두근", "가슴/삼두근")
    cleaned = cleaned.replace("Abs", "복근")
    cleaned = re.sub(r"(\d+)가지 운동\s*(\d+)\s*세트", r"운동 \1개 / \2세트", cleaned)
    cleaned = re.sub(r"운동\s*(\d+)개\s*(\d+)\s*세트", r"운동 \1개 / \2세트", cleaned)
    cleaned = re.sub(r"(\d+)개의 운동\s*(\d+)\s*세트", r"운동 \1개 / \2세트", cleaned)
    cleaned = re.sub(r"(\d+)개의?\s*운동\s*(\d+)\s*세트", r"운동 \1개 / \2세트", cleaned)
    cleaned = re.sub(r"([가-힣A-Za-z])(\d+)", r"\1 \2", cleaned)
    cleaned = re.sub(r"(\d+)([가-힣A-Za-z])", r"\1 \2", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def polish_xml(xml_bytes: bytes) -> bytes:
    parser = etree.XMLParser(remove_blank_text=False, recover=True)
    root = etree.fromstring(xml_bytes, parser=parser)
    paragraphs = root.xpath(".//w:p", namespaces=NS)

    in_grid = False
    grid_count = 0

    for paragraph in paragraphs:
        text = paragraph_text(paragraph).strip()
        if not text:
            continue

        if WEEK_HEADING_RE.match(text):
            set_paragraph_text(paragraph, shorten_week_heading(text))
            set_run_size(paragraph, 22)
            set_spacing(paragraph, before=0, after=0, line=220)
            in_grid = True
            grid_count = 0
            continue

        if in_grid and not EXERCISE_RE.match(text):
            set_paragraph_text(paragraph, clean_grid_text(text))
            set_run_size(paragraph, 14)
            set_spacing(paragraph, before=0, after=0, line=170)
            grid_count += 1
            if grid_count > 36:
                in_grid = False
            continue

        if EXERCISE_RE.match(text):
            in_grid = False
            set_run_size(paragraph, 23)
            set_spacing(paragraph, before=90, after=90, line=240)
            set_keep_next(paragraph, True)
            add_heading_border(paragraph)
            continue

        # Exercise body and metric text: compact enough to clear inherited rules.
        if any(marker in text for marker in ("총 작업", "RPE", "목표:", "휴식")):
            set_run_size(paragraph, 15)
            set_spacing(paragraph, before=0, after=0, line=170)
        else:
            set_run_size(paragraph, 16)
            set_spacing(paragraph, line=190)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def polish_docx(source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output)
    with zipfile.ZipFile(source, "r") as zin:
        entries = {name: zin.read(name) for name in zin.namelist()}
    entries["word/document.xml"] = polish_xml(entries["word/document.xml"])
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for name, data in entries.items():
            zout.writestr(name, data)
    print(f"Wrote {output}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    polish_docx(args.source, args.output)


if __name__ == "__main__":
    main()
