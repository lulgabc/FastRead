#!/usr/bin/env python3
"""Extract an academic paper from a PDF file or a URL into a work directory.

Usage
-----
    python3 extract_paper.py paper.pdf work/papers/my-paper
    python3 extract_paper.py https://arxiv.org/abs/1706.03762 work/papers/attention

The URL form supports arXiv abstract/PDF links and direct .pdf URLs. For arXiv
the title, authors, abstract, year and DOI are read from the official API; the
PDF is downloaded next to the extracted text.

Outputs
-------
    work/papers/<slug>/source.pdf     downloaded copy (URL input only)
    work/papers/<slug>/meta.json      kind=paper + bibliographic metadata
    work/papers/<slug>/full.txt       page-marked text
    work/papers/<slug>/toc.json       detected headings [level,title,page]
    work/papers/<slug>/abstract.txt   abstract only
    work/papers/<slug>/refs.txt       bibliography text (best effort)
    work/papers/<slug>/sections/NN.txt one file per detected section

Section detection is heuristic: PDF outline first, then numbered/named headings
(Abstract, Introduction, Method, Experiments, Results, Conclusion, References…).
Always skim full.txt before writing the tutorial.
"""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"

HEAD_NAMES = (
    "abstract", "introduction", "related work", "background", "preliminaries",
    "method", "methods", "methodology", "approach", "model", "architecture",
    "experiments", "experiment", "evaluation", "results", "result", "analysis",
    "ablation", "discussion", "limitations", "conclusion", "conclusions",
    "future work", "references", "bibliography", "acknowledgments",
    "acknowledgements", "appendix",
)
HEAD_RE = re.compile(
    r"^\s*(?:(\d{1,2})[.\s]+)?(" + "|".join(HEAD_NAMES) +
    r")(?:\s+[A-Z][\w &/()'\-]{0,60})?\s*$", re.I)
NUM_RE = re.compile(r"^\s*\d{1,2}\.?\s+[A-Z][\w &/()'\-]{2,70}\s*$")
BAD_CHARS = set("·=→←_|{}<>$")


def normalise_space(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def arxiv_id(url: str):
    m = re.search(
        r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5}|[a-z\-]+/\d{7})(?:v\d+)?",
        url, re.I)
    return m.group(1) if m else None


def fetch(url: str, dest: Path) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": "FastRead/1.0 (paper extraction)"})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = r.read()
    dest.write_bytes(data)
    return data


def arxiv_meta(arxiv: str) -> dict:
    api = f"http://export.arxiv.org/api/query?id_list={arxiv}"
    try:
        with urllib.request.urlopen(api, timeout=60) as r:
            root = ET.fromstring(r.read())
    except Exception as e:
        print(f"WARNING: arXiv API failed ({e}); metadata will be guessed.")
        return {}
    entry = root.find(f"{ATOM}entry")
    if entry is None:
        return {}
    title = normalise_space(entry.findtext(f"{ATOM}title", ""))
    abstract = normalise_space(entry.findtext(f"{ATOM}summary", ""))
    authors = [normalise_space(a.findtext(f"{ATOM}name", ""))
               for a in entry.findall(f"{ATOM}author")]
    published = entry.findtext(f"{ATOM}published", "") or ""
    doi = entry.findtext(f"{ARXIV}doi", "") or ""
    journal = entry.findtext(f"{ARXIV}journal_ref", "") or ""
    return {
        "title": title,
        "authors": [a for a in authors if a],
        "abstract": abstract,
        "year": int(published[:4]) if published[:4].isdigit() else None,
        "doi": doi,
        "venue": journal,
    }


def infer_title_from_pdf(doc) -> tuple:
    """Largest-font line group on page 1, plus nearby author line."""
    try:
        page = doc[0]
        data = page.get_text("dict")
    except Exception:
        return "", []
    lines = []
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = normalise_space("".join(s.get("text", "") for s in spans))
            size = max(float(s.get("size", 0)) for s in spans)
            if text:
                lines.append((size, text, line.get("bbox", (0, 0, 0, 0))))
    if not lines:
        return "", []
    lines.sort(key=lambda x: -x[0])
    top_size = lines[0][0]
    title_parts = [t for s, t, _ in lines if abs(s - top_size) < 0.6][:4]
    title = normalise_space(" ".join(title_parts))
    # L'auteur est souvent la première ligne nettement plus petite sous le titre.
    authors = []
    for s, t, bbox in lines:
        if top_size * 0.55 < s < top_size * 0.95 and bbox[1] > lines[0][2][1]:
            if "," in t or re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", t):
                authors.append(t)
            if len(authors) >= 2:
                break
    return title, authors


def detect_headings(lines):
    """Return [(line_index, title)] for likely top-level section headings."""
    out = []
    seen = set()
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line or len(line) > 80:
            continue
        if line[0].islower() or BAD_CHARS & set(line):
            continue
        if line.endswith((".", ":", ";", ",")):
            continue
        is_head = bool(HEAD_RE.match(line)) or bool(NUM_RE.match(line))
        if not is_head:
            continue
        key = normalise_space(line).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((i, normalise_space(line)))
    # Déduplique les détections collées (en-têtes courants, pieds de page).
    clean, last = [], -10
    for i, title in out:
        if i - last <= 2:
            continue
        clean.append((i, title))
        last = i
    return clean


def split_sections(full_text: str) -> list:
    lines = full_text.splitlines()
    heads = detect_headings(lines)
    sections = []
    for n, (idx, title) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        body = "\n".join(lines[idx + 1:end]).strip()
        if len(body) >= 120:
            sections.append({"title": title, "text": body})
    return sections


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src, out_dir = sys.argv[1], Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sections").mkdir(exist_ok=True)

    meta = {"kind": "paper", "format": "pdf", "extracted_at":
            datetime.now(timezone.utc).isoformat(timespec="seconds")}

    if re.match(r"https?://", src):
        meta["url"] = src
        aid = arxiv_id(src)
        if aid:
            meta["arxiv_id"] = aid
            meta.update({k: v for k, v in arxiv_meta(aid).items() if v})
            pdf_url = f"https://arxiv.org/pdf/{aid}"
        elif src.lower().split("?")[0].endswith(".pdf"):
            pdf_url = src
        else:
            sys.exit("URL non reconnue : fournir un lien arXiv ou un fichier .pdf")
        pdf_path = out_dir / "source.pdf"
        print(f"download: {pdf_url}")
        fetch(pdf_url, pdf_path)
    else:
        pdf_path = Path(src).expanduser()
        if not pdf_path.exists():
            sys.exit(f"not found: {pdf_path}")

    try:
        import fitz  # PyMuPDF
    except ImportError:
        sys.exit("Missing PyMuPDF. Run: python3 -m pip install --user pymupdf")

    doc = fitz.open(pdf_path)
    meta["pages"] = len(doc)
    md = doc.metadata or {}
    title = normalise_space(md.get("title", ""))
    authors = [a.strip() for a in re.split(r";|,| and ", md.get("author", "")) if a.strip()]
    if not title or len(title) < 4:
        guessed, guessed_authors = infer_title_from_pdf(doc)
        title = title or guessed
        authors = authors or guessed_authors
    meta.setdefault("title", title or pdf_path.stem)
    meta.setdefault("authors", authors)

    chunks = []
    for i, page in enumerate(doc):
        chunks.append(f"\n\n===== PAGE {i + 1} =====\n{page.get_text('text')}")
    full = "".join(chunks)
    (out_dir / "full.txt").write_text(full, encoding="utf-8")

    # 1) Outline PDF quand il est utilisable (fréquent sur arXiv).
    outline = [[l, normalise_space(t), int(p)]
               for l, t, p in (doc.get_toc(simple=True) or []) if t and int(p) >= 1]
    if len(outline) >= 3:
        toc = outline
        for n, (_level, title, page) in enumerate(toc):
            end_page = toc[n + 1][2] - 1 if n + 1 < len(toc) else len(doc)
            end_page = max(page, end_page)
            text = "\n".join(doc[j].get_text("text")
                             for j in range(page - 1, min(end_page, len(doc))))
            if text.strip():
                (out_dir / "sections" / f"{n + 1:02d}.txt").write_text(
                    f"# {title}\n\n{text.strip()}", encoding="utf-8")
        meta["sections"] = len(list((out_dir / "sections").glob("*.txt")))
    else:
        # 2) Sinon, découpage heuristique sur les titres détectés.
        sections = split_sections(full)
        page_texts = ["PAGE " + chunk for chunk in full.split("===== PAGE ")[1:]]

        def page_of(title: str) -> int:
            needle = normalise_space(title).lower()
            for k, text in enumerate(page_texts, 1):
                if needle and needle in normalise_space(text).lower():
                    return k
            return 1

        toc = []
        for n, sec in enumerate(sections, 1):
            toc.append([1, sec["title"], page_of(sec["title"])])
            (out_dir / "sections" / f"{n:02d}.txt").write_text(
                f"# {sec['title']}\n\n{sec['text']}", encoding="utf-8")
        meta["sections"] = len(sections)

    (out_dir / "toc.json").write_text(json.dumps(toc, ensure_ascii=False, indent=2),
                                      encoding="utf-8")

    # Résumé : la métadonnée arXiv est fiable ; sinon on découpe le texte.
    flat = full.replace("===== PAGE", "\n===== PAGE")
    abstract = normalise_space(meta.get("abstract", ""))
    if not abstract:
        m = re.search(r"\bAbstract\b(.*?)(?=\n\s*(?:\d+[.\s]+)?(?:Introduction|1\s+Introduction)\b)",
                      flat, re.S | re.I)
        abstract = normalise_space(m.group(1)) if m else ""
        # Coupe les notes de bas de page et les marqueurs de page.
        abstract = re.split(r"\s*[∗†‡]|===== PAGE", abstract)[0].strip()
        abstract = re.sub(r"\s*\d+\s*$", "", abstract)
    meta["abstract"] = abstract
    (out_dir / "abstract.txt").write_text(abstract, encoding="utf-8")

    m = re.search(r"\bReferences\b(.*)$", flat, re.S | re.I)
    refs = m.group(1).strip() if m else ""
    (out_dir / "refs.txt").write_text(refs, encoding="utf-8")
    meta["references"] = len(re.findall(r"^\s*(?:\[\d+\]|\d+\.)\s+\S", refs, re.M))

    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"paper: {meta['title']}")
    print(f"authors: {', '.join(meta.get('authors') or [])[:120]}")
    print(f"pages: {meta['pages']} | sections: {meta.get('sections', 0)} "
          f"| refs≈{meta.get('references', 0)}")
    if meta.get("arxiv_id"):
        print(f"arxiv: {meta['arxiv_id']} | year: {meta.get('year', '?')}")
    print(f"wrote {out_dir}/meta.json, full.txt, toc.json, sections/, abstract.txt")


if __name__ == "__main__":
    main()
