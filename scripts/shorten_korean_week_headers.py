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


def set_spacing(paragraph) -> None:
    ppr = paragraph.find("w:pPr", namespaces=NS)
    if ppr is None:
        ppr = etree.Element(f"{{{W}}}pPr")
        paragraph.insert(0, ppr)
    spacing = ppr.find("w:spacing", namespaces=NS)
    if spacing is None:
        spacing = etree.SubElement(ppr, f"{{{W}}}spacing")
    spacing.set(f"{{{W}}}before", "0")
    spacing.set(f"{{{W}}}after", "0")
    spacing.set(f"{{{W}}}line", "220")
    spacing.set(f"{{{W}}}lineRule", "auto")


def set_spacing_values(paragraph, before=None, after=None, line=None) -> None:
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


def shorten(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if "훈련 개요" in cleaned or "훈련 분할" in cleaned:
        match = re.match(r"^(\d+\s*주차)", cleaned)
        return f"{match.group(1)} - 훈련 개요" if match else cleaned
    match = re.match(r"^(\d+\s*주차\s*-\s*[^-]+-\s*.+?운동)\b", cleaned)
    return match.group(1) if match else cleaned


def process_xml(xml_bytes: bytes) -> bytes:
    root = etree.fromstring(xml_bytes, parser=etree.XMLParser(remove_blank_text=False, recover=True))
    paragraphs = root.xpath(".//w:p", namespaces=NS)
    texts = [paragraph_text(paragraph).strip() for paragraph in paragraphs]

    description_indexes = set()
    for index, text in enumerate(texts):
        if not EXERCISE_RE.match(text):
            continue
        # Add breathing room before the first real description/prescription
        # so the inherited gold rule sits between the heading and text.
        for next_index in range(index + 1, min(index + 6, len(texts))):
            next_text = texts[next_index]
            if not next_text:
                continue
            if EXERCISE_RE.match(next_text):
                break
            description_indexes.add(next_index)
            break

    for index, paragraph in enumerate(paragraphs):
        text = texts[index]
        text = paragraph_text(paragraph).strip()
        if WEEK_HEADING_RE.match(text):
            set_paragraph_text(paragraph, shorten(text))
            set_run_size(paragraph, 22)
            set_spacing(paragraph)
        elif index in description_indexes:
            set_spacing_values(paragraph, before=170, line=175)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def process_docx(source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output)
    with zipfile.ZipFile(source, "r") as zin:
        entries = {name: zin.read(name) for name in zin.namelist()}
    entries["word/document.xml"] = process_xml(entries["word/document.xml"])
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for name, data in entries.items():
            zout.writestr(name, data)
    print(f"Wrote {output}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    process_docx(args.source, args.output)


if __name__ == "__main__":
    main()
