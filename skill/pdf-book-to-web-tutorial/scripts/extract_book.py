#!/usr/bin/env python3
"""Extract a PDF or EPUB book into text and per-chapter files.

Usage
-----
    python extract_book.py "/path/book.pdf" work/
    python extract_book.py "/path/book.epub" work/

Outputs
-------
    work/full.txt          text with ===== PAGE/DOCUMENT n ===== markers
    work/chapters/NN.txt   one file per chapter (from the book's TOC/nav)
    work/toc.json          raw PDF outline, or EPUB [level,title,doc_index]
    work/meta.json         format, pages/documents, chapters, result counts

PDF requires PyMuPDF:
    python3 -m pip install --user pymupdf
Scanned PDFs should be OCR'd first:
    brew install ocrmypdf tesseract
    ocrmypdf --deskew --clean book.pdf book-ocr.pdf

EPUB support uses only the standard library. DRM-protected EPUBs are rejected.
Formulas that are images cannot be extracted as text; the script reports how
many images it saw so you can inspect the XHTML manually.
"""
import json
import posixpath
import re
import sys
import zipfile
from collections import Counter
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote
import xml.etree.ElementTree as ET

ITEM = re.compile(
    r"^(Theorem|Definition|Deﬁnition|Lemma|Proposition|Corollary|Example|Remark|Problem)"
    r"\s+(\d+)\.(\d+)", re.M)

BLOCK = {
    "p", "div", "br", "li", "tr", "section", "article", "blockquote",
    "h1", "h2", "h3", "h4", "h5", "h6", "pre", "table", "ul", "ol",
    "figure", "figcaption", "header", "footer", "aside", "nav",
}


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


class TextExtractor(HTMLParser):
    def __init__(self, collect_headings=False):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0
        self.has_text = False
        self.collect_headings = collect_headings
        self.headings = []
        self._heading = None
        self.images = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ("script", "style", "noscript"):
            self.skip += 1
            return
        if tag in BLOCK:
            self.parts.append("\n")
        if tag == "img":
            self.images += 1
            alt = dict(attrs).get("alt", "").strip()
            if alt:
                self.parts.append(f"[image: {alt}]")
        if self.collect_headings and tag in ("h1", "h2", "h3"):
            self._heading = {"tag": tag, "text": []}

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("script", "style", "noscript"):
            self.skip = max(0, self.skip - 1)
            return
        if tag in BLOCK:
            self.parts.append("\n")
        if self.collect_headings and self._heading and tag == self._heading["tag"]:
            text = re.sub(r"\s+", " ", "".join(self._heading["text"])).strip()
            if text:
                self.headings.append(text)
            self._heading = None

    def handle_data(self, data):
        if self.skip:
            return
        if data.strip():
            self.has_text = True
            self.parts.append(data)
            if self._heading is not None:
                self._heading["text"].append(data)

    def text(self):
        raw = "".join(self.parts)
        raw = raw.replace("\xa0", " ")
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in raw.splitlines()]
        out = []
        blank = False
        for ln in lines:
            if ln:
                out.append(ln)
                blank = False
            elif not blank:
                out.append("")
                blank = True
        return "\n".join(out).strip()


# ---------------------------------------------------------------- PDF
def extract_pdf(path: Path, out_dir: Path, chapters_dir: Path) -> dict:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        sys.exit("PDF input needs PyMuPDF. Run: python3 -m pip install --user pymupdf")

    doc = fitz.open(path)
    toc = doc.get_toc(simple=True)
    (out_dir / "toc.json").write_text(
        json.dumps(toc, ensure_ascii=True, indent=2), encoding="utf-8")

    chunks, low_text = [], []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if len(text.strip()) < 40:
            low_text.append(i + 1)
        chunks.append(f"\n\n===== PAGE {i + 1} =====\n{text}")
    full = "".join(chunks)
    (out_dir / "full.txt").write_text(full, encoding="utf-8")

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
        for k in range(0, len(doc), 50):
            name = f"part-{k // 50 + 1:02d}.txt"
            text = "".join(doc[j].get_text("text") for j in range(k, min(k + 50, len(doc))))
            (chapters_dir / name).write_text(text, encoding="utf-8")
            chapter_files.append(name)

    counts = Counter(k.replace("ﬁ", "fi") for k, _, _ in ITEM.findall(full))
    return {
        "format": "pdf",
        "source": str(path),
        "pages": len(doc),
        "toc_entries": len(toc),
        "chapters": chapter_files,
        "numbered_results": dict(counts),
        "numbered_results_total": sum(counts.values()),
        "low_text_pages": low_text,
        "images": sum(len(p.get_images(full=True)) for p in doc),
    }


# ---------------------------------------------------------------- EPUB
def read_xml(z: zipfile.ZipFile, name: str):
    return ET.fromstring(z.read(name))


def parse_ncx(z: zipfile.ZipFile, ncx_path: str, opf_dir: str):
    root = read_xml(z, ncx_path)
    entries = []

    def walk(node, level):
        for child in node:
            if local(child.tag) == "navPoint":
                label = ""
                for el in child.iter():
                    if local(el.tag) == "text" and el.text:
                        label = re.sub(r"\s+", " ", el.text).strip()
                        break
                src = ""
                for el in child.iter():
                    if local(el.tag) == "content":
                        src = el.attrib.get("src", "")
                        break
                if label:
                    doc = normalize_href(posixpath.join(posixpath.dirname(ncx_path), src))
                    entries.append([level, label, doc])
                walk(child, level + 1)

    nav_map = None
    for el in root.iter():
        if local(el.tag) == "navMap":
            nav_map = el
            break
    if nav_map is not None:
        walk(nav_map, 1)
    return entries


def parse_nav_html(z: zipfile.ZipFile, nav_path: str):
    class NavParser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.entries = []
            self._href = None
            self._text = []

        def handle_starttag(self, tag, attrs):
            if tag.lower() == "a":
                self._href = dict(attrs).get("href")
                self._text = []

        def handle_data(self, data):
            if self._href is not None and data.strip():
                self._text.append(data.strip())

        def handle_endtag(self, tag):
            if tag.lower() == "a" and self._href is not None:
                text = re.sub(r"\s+", " ", " ".join(self._text)).strip()
                if text and not self._href.startswith(("http:", "https:", "mailto:")):
                    self.entries.append((self._href, text))
                self._href = None
                self._text = []

    parser = NavParser()
    parser.feed(z.read(nav_path).decode("utf-8", "replace"))
    base = posixpath.dirname(nav_path)
    return [(normalize_href(posixpath.join(base, href)), text)
            for href, text in parser.entries]


def normalize_href(href: str) -> str:
    href = unquote(href.split("#", 1)[0])
    return posixpath.normpath(href).lstrip("./")


def extract_epub(path: Path, out_dir: Path, chapters_dir: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if "META-INF/encryption.xml" in names:
            sys.exit("EPUB appears to be DRM-protected (META-INF/encryption.xml). "
                     "Remove DRM legally before conversion.")
        if "META-INF/container.xml" not in names:
            sys.exit("Not a valid EPUB: missing META-INF/container.xml")

        container = read_xml(z, "META-INF/container.xml")
        opf_path = None
        for el in container.iter():
            if local(el.tag) == "rootfile":
                opf_path = el.attrib.get("full-path")
                break
        if not opf_path:
            sys.exit("EPUB has no rootfile in container.xml")

        opf = read_xml(z, opf_path)
        opf_dir = posixpath.dirname(opf_path)
        manifest = {}
        spine_ids = []
        ncx_path = None
        nav_path = None
        for el in opf.iter():
            t = local(el.tag)
            if t == "item":
                item_id = el.attrib.get("id")
                href = el.attrib.get("href", "")
                media = el.attrib.get("media-type", "")
                full = normalize_href(posixpath.join(opf_dir, href))
                manifest[item_id] = {"href": full, "media": media,
                                     "properties": el.attrib.get("properties", "")}
                if media == "application/x-dtbncx+xml":
                    ncx_path = full
                if "nav" in el.attrib.get("properties", "").split():
                    nav_path = full
            elif t == "spine":
                toc_id = el.attrib.get("toc")
                if toc_id and toc_id in manifest:
                    ncx_path = manifest[toc_id]["href"]
            elif t == "itemref":
                spine_ids.append(el.attrib.get("idref"))

        docs = []
        images = 0
        for item_id in spine_ids:
            item = manifest.get(item_id)
            if not item or not item["href"].endswith((".xhtml", ".html", ".htm")):
                continue
            if item["href"] not in names:
                continue
            parser = TextExtractor(collect_headings=True)
            parser.feed(z.read(item["href"]).decode("utf-8", "replace"))
            docs.append({"href": item["href"], "text": parser.text(),
                         "headings": parser.headings})
            images += parser.images

        if not docs:
            sys.exit("EPUB spine contains no readable XHTML documents.")

        # TOC: NCX first, then nav.xhtml; fall back to first heading per document.
        href_to_doc = {d["href"]: i for i, d in enumerate(docs)}
        entries = []
        if ncx_path and ncx_path in names:
            for level, title, href in parse_ncx(z, ncx_path, opf_dir):
                if href in href_to_doc:
                    entries.append([level, title, href_to_doc[href]])
        if not entries and nav_path and nav_path in names:
            for href, title in parse_nav_html(z, nav_path):
                if href in href_to_doc:
                    entries.append([1, title, href_to_doc[href]])
        if not entries:
            for i, d in enumerate(docs):
                title = d["headings"][0] if d["headings"] else f"Document {i + 1}"
                entries.append([1, title, i])

        # De-duplicate, keep document order, and ensure a start at 0.
        seen = set()
        clean = []
        for level, title, idx in entries:
            key = (idx, title)
            if key in seen:
                continue
            seen.add(key)
            clean.append([level, title, idx])
        clean.sort(key=lambda x: (x[2], x[0]))
        if not clean or clean[0][2] != 0:
            clean.insert(0, [1, "Front Matter", 0])

        # One chapter per top-level TOC entry (or every 10 docs if too many).
        tops = [e for e in clean if e[0] == 1]
        if not tops:
            tops = clean
        spans = []
        for i, (_level, title, idx) in enumerate(tops):
            end = tops[i + 1][2] - 1 if i + 1 < len(tops) else len(docs) - 1
            if end < idx:
                continue
            spans.append((title, idx, end))
        if not spans:
            spans = [("Book", 0, len(docs) - 1)]

        full_parts = []
        for i, d in enumerate(docs):
            full_parts.append(f"\n\n===== DOCUMENT {i + 1}: {d['href']} =====\n{d['text']}")
        full = "".join(full_parts)
        (out_dir / "full.txt").write_text(full, encoding="utf-8")
        (out_dir / "toc.json").write_text(
            json.dumps(clean, ensure_ascii=True, indent=2), encoding="utf-8")

        chapter_files = []
        for n, (title, start, end) in enumerate(spans, 1):
            text = "\n\n".join(docs[i]["text"] for i in range(start, end + 1))
            name = f"{n:02d}.txt"
            (chapters_dir / name).write_text(
                f"# {title}\n\n{text}", encoding="utf-8")
            chapter_files.append(name)

        counts = Counter(k.replace("ﬁ", "fi") for k, _, _ in ITEM.findall(full))
        chars = sum(len(d["text"]) for d in docs)
        return {
            "format": "epub",
            "source": str(path),
            "pages": max(1, round(chars / 1800)),
            "pages_estimated": True,
            "documents": len(docs),
            "toc_entries": len(clean),
            "chapters": chapter_files,
            "numbered_results": dict(counts),
            "numbered_results_total": sum(counts.values()),
            "low_text_pages": [i + 1 for i, d in enumerate(docs) if len(d["text"]) < 40],
            "images": images,
        }


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    book_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    if not book_path.exists():
        sys.exit(f"not found: {book_path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir = out_dir / "chapters"
    chapters_dir.mkdir(exist_ok=True)

    suffix = book_path.suffix.lower()
    if suffix == ".pdf":
        meta = extract_pdf(book_path, out_dir, chapters_dir)
    elif suffix == ".epub":
        meta = extract_epub(book_path, out_dir, chapters_dir)
    else:
        sys.exit(f"unsupported format: {suffix} (expected .pdf or .epub)")

    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=True, indent=2), encoding="utf-8")

    unit = "pages" if meta["format"] == "pdf" else "documents"
    print(f"{meta['format']}: {meta['pages']} {unit} | toc: {meta['toc_entries']} "
          f"| chapters: {len(meta['chapters'])}")
    print(f"numbered results: {meta['numbered_results_total']} {meta['numbered_results']}")
    if meta.get("low_text_pages"):
        print(f"WARNING: {len(meta['low_text_pages'])} {unit} have almost no text "
              f"(first: {meta['low_text_pages'][:10]}).")
    if meta.get("images"):
        print(f"NOTE: {meta['images']} image(s) seen. Formulas/figures that are images "
              f"cannot be extracted as text; inspect the source if needed.")
    print(f"wrote {out_dir}/full.txt, toc.json, meta.json, chapters/")


if __name__ == "__main__":
    main()
