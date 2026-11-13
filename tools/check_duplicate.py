#!/usr/bin/env python3
"""Check whether a book is already in the FastRead library, before converting it.

Usage
-----
    python3 tools/check_duplicate.py ~/Downloads/Books/new-book.pdf
    python3 tools/check_duplicate.py --title "Mathematical Logic" --author "Ebbinghaus"
    python3 tools/check_duplicate.py book1.pdf book2.epub --threshold 0.80

Exit codes
----------
    0  no convincing match  -> safe to convert
    1  duplicate or possible duplicate -> stop and review
    2  bad arguments / unreadable file

Matching uses the PDF/EPUB metadata when available, otherwise the filename.
It compares normalised title tokens, sequence similarity and author surnames
against catalog.json. Output always shows the closest matches with scores.
"""
import argparse
import difflib
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog.json"
PAPERS = ROOT / "papers.json"

STOP = {
    "a", "an", "the", "of", "and", "or", "for", "to", "in", "on", "with",
    "at", "by", "from", "as", "is", "are", "be", "new", "book",
    "edition", "ed", "vol", "volume", "pdf", "epub", "ebook",
}
NOISE_PARENS = re.compile(
    r"\((?:z-?library[^)]*|1lib[^)]*|z-lib[^)]*|libgen[^)]*|.*?\bedition\b.*?)\)",
    re.I,
)


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def normalise(s: str) -> str:
    s = strip_accents(str(s or "")).lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(s: str) -> set:
    return {w for w in normalise(s).split() if w not in STOP and len(w) > 1}


SUBTITLE = re.compile(
    r"\s+(?:How to|A Guide|The Complete|The Definitive|A Foundation|A Course|"
    r"An Introduction|A Comprehensive|A Treatise|A No-Nonsense|The Big Ideas|"
    r"With Applications|Models, Algorithms)\b", re.I)
EDITION = re.compile(r"\b(?:\d+(?:st|nd|rd|th)\s+Edition|Second Edition|Third Edition|"
                     r"Revised Edition|International Edition)\b", re.I)


def parse_filename(path: Path) -> dict:
    """Split a typical Z-Library filename into (title, author)."""
    stem = NOISE_PARENS.sub(" ", path.stem)
    author = ""
    # Un groupe entre parenthèses qui ressemble à un nom = auteur/éditeur.
    for group in re.findall(r"\(([^()]*)\)", stem):
        if re.search(r"[,&]|\betc\b|\b[A-Z][a-z]+\s+[A-Z]", group) and not re.search(
                r"edition|library|press|series|volume|vol\.", group, re.I):
            author = author or re.sub(r"\s+", " ", group).strip()
    title = re.sub(r"\([^()]*\)", " ", stem)
    title = EDITION.sub(" ", title)
    title = re.sub(r"\b(19|20)\d{2}\b", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" -_,")

    # Coupe un sous-titre commercial, mais seulement s'il reste un vrai titre.
    m = SUBTITLE.search(title)
    if m and m.start() >= 8:
        title = title[:m.start()].strip(" -_,")
    for sep in (" — ", " – ", " - ", ": "):
        if sep in title:
            head = title.split(sep)[0].strip(" -_,")
            if len(head.split()) >= 2:
                title = head
                break
    return {"title": title, "author": author, "arxiv": parsed.get("arxiv", "")}


def file_meta(path: Path) -> dict:
    """Filename is the most reliable signal; PDF metadata fills the author."""
    parsed = parse_filename(path)
    title, author = parsed["title"], parsed["author"]
    if path.suffix.lower() == ".pdf":
        try:
            import fitz  # PyMuPDF, optional

            with fitz.open(path) as doc:
                meta = doc.metadata or {}
                meta_title = re.sub(r"\s+", " ", (meta.get("title") or "")).strip()
                # Les métadonnées sont souvent vides ou polluées (nom de fichier).
                if meta_title and 3 <= len(meta_title) <= 120 and "z-lib" not in meta_title.lower():
                    title = meta_title
                author = (meta.get("author") or "").strip() or author
                first = doc[0].get_text("text") if len(doc) else ""
                m = re.search(r"arXiv:\s*(\d{4}\.\d{4,5})", first or "")
                if m:
                    parsed["arxiv"] = m.group(1)
        except Exception:
            pass
    return {"title": title, "author": author}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def surnames(author: str) -> set:
    """Loose author identity: last word of each comma/& separated name."""
    out = set()
    for part in re.split(r"[,;&]|\band\b", author or ""):
        words = [w for w in normalise(part).split() if w not in STOP and len(w) > 2]
        if words:
            out.add(words[-1])
    return out


def score(cand: dict, row: dict) -> tuple:
    ct, rt = normalise(cand["title"]), normalise(row.get("title", ""))
    if not ct or not rt:
        return 0.0, 0.0
    if ct == rt:
        return 1.0, 1.0

    seq = difflib.SequenceMatcher(None, ct, rt).ratio()
    a, b = tokens(cand["title"]), tokens(row.get("title", ""))
    if a and b:
        jac = len(a & b) / len(a | b)
        cont = len(a & b) / min(len(a), len(b))
        title = max(seq, 0.45 * jac + 0.55 * cont)
    else:
        title = seq

    ca, ra = surnames(cand.get("author", "")), surnames(row.get("author", ""))
    if ca and ra:
        overlap = len(ca & ra) / min(len(ca), len(ra))
        author = 1.0 if overlap else 0.0
        final = 0.85 * title + 0.15 * author
        # Pénalise une signature explicitement différente.
        if not overlap:
            final -= 0.05
    else:
        final = title
    return max(0.0, min(1.0, final)), title


def check_one(cand: dict, rows: list, threshold: float) -> dict:
    scored = []
    for row in rows:
        total, title = score(cand, row)
        if cand.get("arxiv") and cand["arxiv"] == row.get("arxiv"):
            total, title = 1.0, 1.0
        scored.append((total, title, row))
    scored.sort(key=lambda x: -x[0])
    best = scored[:3]
    top = best[0][0] if best else 0.0

    if top >= 0.90:
        verdict, code = "已存在（重复）", 1
    elif top >= threshold:
        verdict, code = "可能重复，需要人工确认", 1
    else:
        verdict, code = "未找到，可以转换", 0
    return {"candidate": cand, "best": best, "top": top, "verdict": verdict, "code": code}


def report(res: dict) -> None:
    c = res["candidate"]
    print(f"\n候选：{c['title']}" + (f" — {c['author']}" if c.get("author") else ""))
    if c.get("sha256"):
        print(f"sha256：{c['sha256'][:16]}…")
    if c.get("arxiv"):
        print(f"arXiv：{c['arxiv']}")
    print(f"判定：{res['verdict']}（最高分 {res['top']:.2f}）")
    if res["best"]:
        print("最接近的馆藏：")
        for total, title, row in res["best"]:
            kind = "论文" if row.get("_kind") == "paper" else "书"
            print(f"  {total:.2f}  [{kind}] {row['title']} — {row.get('author','')}  [{row['file']}]")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="PDF/EPUB à vérifier")
    ap.add_argument("--title", help="titre si aucun fichier")
    ap.add_argument("--author", default="", help="auteur avec --title")
    ap.add_argument("--arxiv", default="", help="identifiant arXiv (ex. 1706.03762)")
    ap.add_argument("--threshold", type=float, default=0.72,
                    help="seuil « possible doublon » (défaut 0.72)")
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    args = ap.parse_args()

    if not args.files and not args.title and not args.arxiv:
        ap.error("fournir un fichier, --title ou --arxiv")

    if not CATALOG.exists():
        sys.exit("catalog.json introuvable")
    rows = []
    for r in json.load(open(CATALOG, encoding="utf-8")):
        rows.append({**r, "_kind": "book"})
    if PAPERS.exists():
        for r in json.load(open(PAPERS, encoding="utf-8")):
            rows.append({**r, "author": r.get("authors", ""), "_kind": "paper"})

    candidates = []
    for raw in args.files:
        p = Path(raw).expanduser()
        if not p.exists():
            print(f"fichier introuvable : {p}")
            sys.exit(2)
        meta = file_meta(p)
        meta["sha256"] = sha256(p)
        meta["path"] = str(p)
        candidates.append(meta)
    if args.title:
        candidates.append({"title": args.title, "author": args.author})
    if args.arxiv:
        candidates.append({"title": "", "author": "", "arxiv": args.arxiv.strip()})

    results = [check_one(c, rows, args.threshold) for c in candidates]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for res in results:
            report(res)
        print(f"\n{len(rows)} entrées (livres + articles) ; "
              f"seuil « possible » = {args.threshold:.2f}")

    sys.exit(1 if any(r["code"] == 1 for r in results) else 0)


if __name__ == "__main__":
    main()
