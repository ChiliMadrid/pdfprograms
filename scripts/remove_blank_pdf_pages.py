import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PY = ROOT / ".codex_local_py"
if LOCAL_PY.exists():
    sys.path.insert(0, str(LOCAL_PY))

import fitz  # noqa: E402


def page_average(page) -> float:
    pix = page.get_pixmap(matrix=fitz.Matrix(0.20, 0.20), alpha=False)
    return sum(pix.samples) / len(pix.samples) if pix.samples else 255.0


def should_remove(page, white_threshold: float, max_tiny_text_length: int) -> bool:
    avg = page_average(page)
    if avg < white_threshold:
        return False

    text = " ".join(page.get_text().split())
    if not text:
        return True

    if len(text) <= max_tiny_text_length:
        return True

    return False


def clean_pdf(path: Path, white_threshold: float, max_tiny_text_length: int) -> None:
    doc = fitz.open(path)
    remove_indexes = [
        index for index, page in enumerate(doc)
        if should_remove(page, white_threshold, max_tiny_text_length)
    ]

    if not remove_indexes:
        print(f"{path.name}: no blank pages removed")
        return

    cleaned = fitz.open()
    for index in range(len(doc)):
        if index not in remove_indexes:
            cleaned.insert_pdf(doc, from_page=index, to_page=index)

    temp = path.with_suffix(".cleaned.pdf")
    cleaned.save(temp, garbage=4, deflate=True)
    cleaned.close()
    doc.close()
    temp.replace(path)

    pages = ", ".join(str(index + 1) for index in remove_indexes[:40])
    suffix = "" if len(remove_indexes) <= 40 else f" ... +{len(remove_indexes) - 40} more"
    print(f"{path.name}: removed {len(remove_indexes)} blank/tiny-footer page(s): {pages}{suffix}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--white-threshold", type=float, default=253.0)
    parser.add_argument("--max-tiny-text-length", type=int, default=24)
    args = parser.parse_args()

    clean_pdf(args.pdf, args.white_threshold, args.max_tiny_text_length)


if __name__ == "__main__":
    main()
