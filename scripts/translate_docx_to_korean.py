import argparse
import hashlib
import json
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

from lxml import etree


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PY = ROOT / ".codex_local_py"
if LOCAL_PY.exists():
    sys.path.insert(0, str(LOCAL_PY))

from deep_translator import GoogleTranslator  # noqa: E402


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}

TRANSLATABLE_PART = re.compile(
    r"^word/(document|footnotes|endnotes|comments|header\d+|footer\d+)\.xml$"
)
LATIN_RE = re.compile(r"[A-Za-z]")
KOREAN_RE = re.compile(r"[\uac00-\ud7af]")
ONLY_SYMBOLS_RE = re.compile(r"^[\s\d.,:;!?%()+\-–—/*#&@'\"[\]{}<>|\\]+$")
EXERCISE_HEADING_RE = re.compile(r"^\s*\d+\s*/")


GLOSSARY = [
    ("Cable lateral raise", "케이블 레터럴 레이즈"),
    ("cable lateral raise", "케이블 레터럴 레이즈"),
    ("Lateral raise", "레터럴 레이즈"),
    ("lateral raise", "레터럴 레이즈"),
    ("Side lateral raise", "사이드 레터럴 레이즈"),
    ("side lateral raise", "사이드 레터럴 레이즈"),
    ("Dumbbell press", "덤벨 프레스"),
    ("dumbbell press", "덤벨 프레스"),
    ("Incline dumbbell press", "인클라인 덤벨 프레스"),
    ("incline dumbbell press", "인클라인 덤벨 프레스"),
    ("Bench press", "벤치 프레스"),
    ("bench press", "벤치 프레스"),
    ("Chest press", "체스트 프레스"),
    ("chest press", "체스트 프레스"),
    ("Leg press", "레그 프레스"),
    ("leg press", "레그 프레스"),
    ("Hack squat", "핵 스쿼트"),
    ("hack squat", "핵 스쿼트"),
    ("Leg curl", "레그 컬"),
    ("leg curl", "레그 컬"),
    ("Leg extension", "레그 익스텐션"),
    ("leg extension", "레그 익스텐션"),
    ("Romanian deadlift", "루마니안 데드리프트"),
    ("romanian deadlift", "루마니안 데드리프트"),
    ("Deadlift", "데드리프트"),
    ("deadlift", "데드리프트"),
    ("Barbell row", "바벨 로우"),
    ("barbell row", "바벨 로우"),
    ("Cable row", "케이블 로우"),
    ("cable row", "케이블 로우"),
    ("Pulldown", "풀다운"),
    ("pulldown", "풀다운"),
    ("Lat pulldown", "랫 풀다운"),
    ("lat pulldown", "랫 풀다운"),
    ("Face pull", "페이스 풀"),
    ("face pull", "페이스 풀"),
    ("Rear delt", "후면 삼각근"),
    ("rear delt", "후면 삼각근"),
    ("Biceps", "이두근"),
    ("biceps", "이두근"),
    ("Triceps", "삼두근"),
    ("triceps", "삼두근"),
    ("Hamstrings", "햄스트링"),
    ("hamstrings", "햄스트링"),
    ("Glutes", "둔근"),
    ("glutes", "둔근"),
    ("Calves", "종아리"),
    ("calves", "종아리"),
    ("RPE", "RPE"),
    ("Reps", "반복"),
    ("reps", "반복"),
    ("Sets", "세트"),
    ("sets", "세트"),
    ("Rest", "휴식"),
    ("rest", "휴식"),
]


FIXUPS = [
    ("케이블 측면 상승", "케이블 레터럴 레이즈"),
    ("측면 상승", "레터럴 레이즈"),
    ("덤벨 측면 상승", "덤벨 레터럴 레이즈"),
    ("다리 누르기", "레그 프레스"),
    ("다리 컬", "레그 컬"),
    ("다리 확장", "레그 익스텐션"),
    ("얼굴 당기기", "페이스 풀"),
    ("풀다운", "풀다운"),
    ("반복수", "반복"),
    ("대표자", "반복"),
]


def load_cache(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def should_translate(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if KOREAN_RE.search(stripped):
        return False
    if not LATIN_RE.search(stripped):
        return False
    if ONLY_SYMBOLS_RE.match(stripped):
        return False
    return True


def protect_glossary(text: str):
    protected = text
    tokens = {}
    for index, (src, ko) in enumerate(sorted(GLOSSARY, key=lambda item: len(item[0]), reverse=True)):
        pattern = re.compile(rf"\b{re.escape(src)}\b", flags=re.IGNORECASE)
        token = f"__CMTERM{index:04d}__"
        if pattern.search(protected):
            protected = pattern.sub(token, protected)
            tokens[token] = ko
    return protected, tokens


def apply_fixups(text: str) -> str:
    output = text
    for bad, good in FIXUPS:
        output = output.replace(bad, good)
    output = re.sub(r"\s+([.,:;!?])", r"\1", output)
    return output


def restore_tokens(text: str, tokens: dict) -> str:
    output = text
    for token, value in tokens.items():
        output = output.replace(token, value)
        output = output.replace(token.lower(), value)
    return apply_fixups(output)


def translate_texts(texts: list[str], translator, cache: dict, sleep_seconds: float, batch_size: int) -> dict[str, str]:
    result = {}
    pending = []

    for text in texts:
        if text in result:
            continue
        if not should_translate(text):
            result[text] = text
            continue

        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if key in cache:
            result[text] = cache[key]
            continue

        protected, tokens = protect_glossary(text)
        pending.append((text, key, protected, tokens))

    for start in range(0, len(pending), batch_size):
        chunk = pending[start:start + batch_size]
        protected_batch = [item[2] for item in chunk]
        try:
            translated_batch = translator.translate_batch(protected_batch)
        except Exception:
            translated_batch = [translator.translate(item) for item in protected_batch]

        for (original, key, _protected, tokens), translated in zip(chunk, translated_batch):
            restored = restore_tokens(translated, tokens)
            cache[key] = restored
            result[original] = restored

        if sleep_seconds:
            time.sleep(sleep_seconds)

    return result


def set_on_off(paragraph, tag: str) -> None:
    ppr = paragraph.find("w:pPr", namespaces=NS)
    if ppr is None:
        ppr = etree.Element(f"{{{NS['w']}}}pPr")
        paragraph.insert(0, ppr)

    element = ppr.find(f"w:{tag}", namespaces=NS)
    if element is None:
        element = etree.Element(f"{{{NS['w']}}}{tag}")
        ppr.insert(0, element)


def add_page_break(paragraph, before: bool) -> None:
    run = etree.Element(f"{{{NS['w']}}}r")
    br = etree.SubElement(run, f"{{{NS['w']}}}br")
    br.set(f"{{{NS['w']}}}type", "page")
    if before:
        paragraph.insert(0, run)
    else:
        paragraph.append(run)


def is_exercise_heading(text: str) -> bool:
    return bool(EXERCISE_HEADING_RE.match(text.strip()))


def is_footer_or_repeating_brand(text: str) -> bool:
    stripped = text.strip().upper()
    return stripped.startswith("CM STRENGTH") or stripped in {"LOTUS", "THE FIRST FLAME"}


def is_removable_repeating_brand(text: str) -> bool:
    stripped = text.strip().upper()
    return stripped.startswith("CM STRENGTH")


def clear_paragraph_text(paragraph) -> None:
    for node in paragraph_text_nodes(paragraph):
        node.text = ""


def remove_repeating_brand_paragraphs(paragraphs, original_texts) -> None:
    counts = {}
    for text in original_texts:
        stripped = text.strip()
        if is_removable_repeating_brand(stripped):
            key = stripped.upper()
            counts[key] = counts.get(key, 0) + 1

    for index, text in enumerate(original_texts):
        stripped = text.strip()
        if not is_removable_repeating_brand(stripped):
            continue
        if counts.get(stripped.upper(), 0) > 2:
            clear_paragraph_text(paragraphs[index])
            original_texts[index] = ""


def apply_layout_rules(paragraphs, original_texts) -> None:
    keep_next_indexes = set()
    bio_nonempty_remaining = 0
    inserted_bio_after = False

    for index, text in enumerate(original_texts):
        if not is_exercise_heading(text):
            continue
        # Keep the exercise label attached to the blank spacer and first
        # description/prescription paragraph without forcing the whole block
        # onto one page.
        for offset in range(0, 3):
            if index + offset < len(original_texts):
                keep_next_indexes.add(index + offset)

    for index, paragraph in enumerate(paragraphs):
        original = original_texts[index].strip()
        if not original:
            if index in keep_next_indexes:
                set_on_off(paragraph, "keepNext")
            continue

        set_on_off(paragraph, "keepLines")

        if original.upper() == "ABOUT CHILI":
            add_page_break(paragraph, before=True)
            set_on_off(paragraph, "keepNext")
            bio_nonempty_remaining = 2
            continue

        if bio_nonempty_remaining > 0:
            set_on_off(paragraph, "keepNext")
            bio_nonempty_remaining -= 1
            if bio_nonempty_remaining == 0 and not inserted_bio_after:
                add_page_break(paragraph, before=False)
                inserted_bio_after = True
            continue

        if index in keep_next_indexes:
            set_on_off(paragraph, "keepNext")


def normalize_section_breaks(tree) -> None:
    for type_element in tree.xpath(".//w:sectPr/w:type", namespaces=NS):
        value = type_element.get(f"{{{NS['w']}}}val")
        if value in {"oddPage", "evenPage"}:
            type_element.set(f"{{{NS['w']}}}val", "nextPage")


def ensure_korean_font(run, font_name: str, font_scale: float) -> None:
    rpr = run.find("w:rPr", namespaces=NS)
    if rpr is None:
        rpr = etree.Element(f"{{{NS['w']}}}rPr")
        run.insert(0, rpr)

    rfonts = rpr.find("w:rFonts", namespaces=NS)
    if rfonts is None:
        rfonts = etree.Element(f"{{{NS['w']}}}rFonts")
        rpr.insert(0, rfonts)

    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        rfonts.set(f"{{{NS['w']}}}{attr}", font_name)

    size = rpr.find("w:sz", namespaces=NS)
    if size is not None and font_scale != 1:
        val = size.get(f"{{{NS['w']}}}val")
        if val and val.isdigit():
            scaled = max(12, int(round(int(val) * font_scale)))
            size.set(f"{{{NS['w']}}}val", str(scaled))

    size_cs = rpr.find("w:szCs", namespaces=NS)
    if size_cs is not None and font_scale != 1:
        val = size_cs.get(f"{{{NS['w']}}}val")
        if val and val.isdigit():
            scaled = max(12, int(round(int(val) * font_scale)))
            size_cs.set(f"{{{NS['w']}}}val", str(scaled))


def compact_paragraph_spacing(paragraph, line_scale: float) -> None:
    if line_scale == 1:
        return

    ppr = paragraph.find("w:pPr", namespaces=NS)
    if ppr is None:
        ppr = etree.Element(f"{{{NS['w']}}}pPr")
        paragraph.insert(0, ppr)

    spacing = ppr.find("w:spacing", namespaces=NS)
    if spacing is None:
        spacing = etree.Element(f"{{{NS['w']}}}spacing")
        ppr.append(spacing)

    line_attr = f"{{{NS['w']}}}line"
    rule_attr = f"{{{NS['w']}}}lineRule"
    current = spacing.get(line_attr)
    if current and current.isdigit():
        spacing.set(line_attr, str(max(180, int(round(int(current) * line_scale)))))
    else:
        spacing.set(line_attr, "252")
    spacing.set(rule_attr, "auto")


def paragraph_text_nodes(paragraph):
    return paragraph.xpath(".//w:t", namespaces=NS)


def translate_paragraph(paragraph, translated_text, font_name, font_scale, line_scale) -> bool:
    text_nodes = paragraph_text_nodes(paragraph)
    if not text_nodes:
        return False

    original = "".join(node.text or "" for node in text_nodes)
    translated = translated_text
    if translated == original:
        return False

    text_nodes[0].text = translated
    for node in text_nodes[1:]:
        node.text = ""

    first_run = text_nodes[0].getparent()
    while first_run is not None and etree.QName(first_run).localname != "r":
        first_run = first_run.getparent()
    if first_run is not None:
        ensure_korean_font(first_run, font_name, font_scale)
        compact_paragraph_spacing(paragraph, line_scale)

    return True


def translate_xml(xml_bytes, translator, cache, font_name, font_scale, intro_font_scale, line_scale, sleep_seconds, limit, batch_size):
    parser = etree.XMLParser(remove_blank_text=False, recover=True)
    tree = etree.fromstring(xml_bytes, parser=parser)
    changed = 0
    paragraphs = tree.xpath(".//w:p", namespaces=NS)
    original_texts = ["".join(node.text or "" for node in paragraph_text_nodes(paragraph)) for paragraph in paragraphs]
    remove_repeating_brand_paragraphs(paragraphs, original_texts)
    first_exercise_index = next((i for i, text in enumerate(original_texts) if is_exercise_heading(text)), len(original_texts))

    apply_layout_rules(paragraphs, original_texts)
    normalize_section_breaks(tree)

    candidate_texts = []
    for text in original_texts:
        if limit is not None and len(candidate_texts) >= limit:
            break
        if should_translate(text):
            candidate_texts.append(text)

    translated_lookup = translate_texts(candidate_texts, translator, cache, sleep_seconds, batch_size)

    for index, paragraph in enumerate(paragraphs):
        if limit is not None and changed >= limit:
            break
        original = original_texts[index]
        if not should_translate(original):
            continue
        scale = font_scale
        if index < first_exercise_index and original.strip() and not is_footer_or_repeating_brand(original):
            scale = intro_font_scale
        if translate_paragraph(paragraph, translated_lookup.get(original, original), font_name, scale, line_scale):
            changed += 1
    return etree.tostring(tree, xml_declaration=True, encoding="UTF-8", standalone=None), changed


def translate_docx(
    source: Path,
    output: Path,
    cache_path: Path,
    font_name: str,
    font_scale: float,
    intro_font_scale: float,
    line_scale: float,
    sleep_seconds: float,
    batch_size: int,
    limit: int | None,
):
    cache = load_cache(cache_path)
    translator = GoogleTranslator(source="en", target="ko")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output)

    translated_parts = 0
    translated_paragraphs = 0
    with zipfile.ZipFile(source, "r") as zin:
        entries = {name: zin.read(name) for name in zin.namelist()}

    for name in list(entries):
        if not TRANSLATABLE_PART.match(name):
            continue
        if limit is not None and translated_paragraphs >= limit:
            break
        remaining = None if limit is None else max(0, limit - translated_paragraphs)
        if remaining == 0:
            break
        xml, changed = translate_xml(
            entries[name],
            translator,
            cache,
            font_name,
            font_scale,
            intro_font_scale,
            line_scale,
            sleep_seconds,
            remaining,
            batch_size,
        )
        if changed:
            entries[name] = xml
            translated_parts += 1
            translated_paragraphs += changed
            save_cache(cache_path, cache)
            print(f"{source.name}: translated {changed} paragraph(s) in {name}", flush=True)

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for name, data in entries.items():
            zout.writestr(name, data)

    save_cache(cache_path, cache)
    print(f"Wrote {output} ({translated_paragraphs} translated paragraph(s), {translated_parts} part(s))")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cache", type=Path, default=ROOT / "korean_exports" / "translation_cache.json")
    parser.add_argument("--font", default="Noto Sans KR")
    parser.add_argument("--font-scale", type=float, default=1.0)
    parser.add_argument("--intro-font-scale", type=float, default=0.86)
    parser.add_argument("--line-scale", type=float, default=0.94)
    parser.add_argument("--sleep", type=float, default=0.05)
    parser.add_argument("--batch-size", type=int, default=30)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    translate_docx(
        args.source,
        args.output,
        args.cache,
        args.font,
        args.font_scale,
        args.intro_font_scale,
        args.line_scale,
        args.sleep,
        args.batch_size,
        args.limit,
    )


if __name__ == "__main__":
    main()
