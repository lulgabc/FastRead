#!/usr/bin/env python3
"""Split a PDF book into page-marked text and per-chapter files.

Usage
-----
    python extract_book.py "/path/book.pdf" work/

Outputs
-------
    work/full.txt          text with ===== PAGE n ===== markers
    work/chapters/NN.txt   one file per chapter (numbered from the TOC)
    work/toc.json          raw PDF outline
    work/meta.json         pages, chapters, numbered-result counts

Requires PyMuPDF:  python3 -m pip install --user pymupdf
If a page has almost no text, the PDF is probably scanned. OCR it first:
    brew install ocrmypdf tesseract
    ocrmypdf --deskew --clean book.pdf book-ocr.pdf
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("Missing PyMuPDF. Run: python3 -m pip install --user pymupdf")

ITEM = re.compile(
    r"^(Theorem|Definition|Deﬁnition|Lemma|Proposition|Corollary|Example|Remark|Problem)"
    r"\s+(\d+)\.(\d+)", re.M)


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    pdf_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir = out_dir / "chapters"
    chapters_dir.mkdir(exist_ok=True)

    doc = fitz.open(pdf_path)
    toc = doc.get_toc(simple=True)
    (out_dir / "toc.json").write_text(
        json.dumps(toc, ensure_ascii=True, indent=2), encoding="utf-8")

    # Page-marked full text
    chunks = []
    low_text_pages = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if len(text.strip()) < 40:
            low_text_pages.append(i + 1)
        chunks.append(f"\n\n===== PAGE {i + 1} =====\n{text}")
    full = "".join(chunks)
    (out_dir / "full.txt").write_text(full, encoding="utf-8")

    # Locate chapter starts. Chapters can sit at TOC level 1 or 2 (after a Part).
    starts = []
    for _level, title, page in toc:
        m = re.match(r"\s*Chapter\s+(\d+)\b", title)
        if m:
            starts.append((int(m.group(1)), title.strip(), int(page)))
    starts.sort(key=lambda x: x[2])

    chapter_files = []
    if starts:
        for idx, (num, title, page) in enumerate(starts):
            end = starts[idx + 1][2] - 1 if idx + 1 < len(starts) else len(doc)
            end = max(page, end)
            text = "".join(doc[j].get_text("text") for j in range(page - 1, min(end, len(doc))))
            name = f"{num:02d}.txt"
            (chapters_dir / name).write_text(text, encoding="utf-8")
            chapter_files.append(name)
    else:
        # Fallback: one file per 50 pages.
        for k in range(0, len(doc), 50):
            name = f"part-{k // 50 + 1:02d}.txt"
            text = "".join(doc[j].get_text("text") for j in range(k, min(k + 50, len(doc))))
            (chapters_dir / name).write_text(text, encoding="utf-8")
            chapter_files.append(name)

    counts = Counter(k.replace("ﬁ", "fi") for k, _, _ in ITEM.findall(full))
    meta = {
        "source": str(pdf_path),
        "pages": len(doc),
        "toc_entries": len(toc),
        "chapters": chapter_files,
        "numbered_results": dict(counts),
        "numbered_results_total": sum(counts.values()),
        "low_text_pages": low_text_pages,
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"pages: {len(doc)} | toc: {len(toc)} | chapters: {len(chapter_files)}")
    print(f"numbered results: {sum(counts.values())} {dict(counts)}")
    if low_text_pages:
        print(f"WARNING: {len(low_text_pages)} pages have almost no text "
              f"(first: {low_text_pages[:10]}). If this is a scan, OCR it.")
    print(f"wrote {out_dir}/full.txt, toc.json, meta.json, chapters/")


if __name__ == "__main__":
    main()
