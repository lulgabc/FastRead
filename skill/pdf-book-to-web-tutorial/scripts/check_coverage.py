#!/usr/bin/env python3
"""Final coverage detector: did the tutorial lose whole chapters/topics/details?

It is deliberately conservative and explainable, not a semantic judge. It
compares the extracted book (`work/full.txt`, `work/toc.json`,
`work/chapters/`) with the generated HTML and reports:

  1. TOC coverage       — which book sections never appear in the tutorial
  2. Chapter coverage   — per-chapter salient-term recall
  3. Term coverage      — global technical-term recall
  4. Length ratio       — source chars vs tutorial chars (reported, not gated)

Usage:
    python check_coverage.py --work work/BOOK --html books/BOOK-Tutorial.html
    python check_coverage.py --work work/BOOK --html books/BOOK-Tutorial.html \
        --strict --report coverage-report.md

Exit code is 1 when a threshold fails, unless --warn-only is given. The
report is a worklist for a human/agent: fill every missing TOC entry and every
missing top term, then rerun until it passes.
"""
import argparse
import html
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

STOP = set("""
a about above after again against all also am an and any are aren't as at be
because been before being below between both but by can can't cannot could
couldn't did didn't do does doesn't doing don't down during each few for from
further had hadn't has hasn't have haven't having he he'd he'll he's her here
here's hers herself him himself his how how's i i'd i'll i'm i've if in into is
isn't it it's its itself let's me more most mustn't my myself no nor not of off
on once only or other ought our ours ourselves out over own same shan't she
she'd she'll she's should shouldn't so some such than that that's the their
theirs them themselves then there there's these they they'd they'll they're
they've this those through to too under until up very was wasn't we we'd we'll
we're we've were weren't what what's when when's where where's which while who
who's whom why why's with won't would wouldn't you you'd you'll you're you've
your yours yourself yourselves chapter section figure table example theorem
definition lemma proof page pages book part contents preface appendix index
notes bibliography introduction conclusion summary overview
""".split())

GENERIC_TOC = {
    "cover", "title page", "copyright", "contents", "table of contents",
    "preface", "foreword", "acknowledgments", "acknowledgements", "dedication",
    "epigraph", "about the author", "about the cover", "index", "bibliography",
    "notes", "credits", "back cover", "half-title",
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", html.unescape(s))
    s = s.replace("\u00ad", "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip().lower()


def words(s: str):
    return re.findall(r"[a-z][a-z0-9'’\-]{2,}", norm(s))


def content_words(s: str):
    return [w for w in words(s) if w not in STOP and not w.isdigit()]


def han_ngrams(s: str, n=2):
    chars = re.findall(r"[\u4e00-\u9fff]", norm(s))
    return {''.join(chars[i:i + n]) for i in range(len(chars) - n + 1)}


def strip_html(s: str) -> str:
    s = re.sub(r"<script\b.*?</script\s*>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style\b.*?</style\s*>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return html.unescape(s)


def load_toc(work: Path):
    p = work / "toc.json"
    if not p.exists():
        return []
    toc = json.load(open(p, encoding="utf-8"))
    out = []
    for e in toc:
        if len(e) >= 3:
            out.append((int(e[0]), str(e[1]).strip(), e[2]))
    return out


def title_coverage(title: str, tut_norm: str, tut_words: set, tut_han: set) -> float:
    t = norm(title)
    if len(t) >= 4 and t in tut_norm:
        return 1.0
    tw = [w for w in content_words(title)]
    if tw:
        return sum(w in tut_words for w in tw) / len(tw)
    hg = han_ngrams(title)
    if hg:
        return len(hg & tut_han) / len(hg)
    return 1.0


def read_chapters(work: Path):
    d = work / "chapters"
    if not d.exists():
        return []
    files = sorted(d.glob("*.txt"))
    out = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        title = f.stem
        first = text.splitlines()[0].strip() if text.splitlines() else ""
        if first.startswith("#"):
            title = first.lstrip("#").strip()
        out.append({"file": f.name, "title": title, "text": text})
    return out


def salient_terms(chapters):
    token_sets = []
    counts = []
    for ch in chapters:
        ws = content_words(ch["text"])
        token_sets.append(set(ws))
        counts.append(Counter(ws))
    df = Counter()
    for st in token_sets:
        for w in st:
            df[w] += 1
    n = max(1, len(chapters))
    result = []
    for i, c in enumerate(counts):
        scored = []
        for w, k in c.items():
            if len(w) < 4 or df[w] < 2:
                continue
            score = k * math.log((n + 1) / (df[w] + 1))
            if score > 0:
                scored.append((score, w))
        scored.sort(reverse=True)
        result.append([w for _, w in scored[:40]])
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True, help="work dir from extract_book.py")
    ap.add_argument("--html", required=True, help="generated tutorial HTML")
    ap.add_argument("--min-toc", type=float, default=0.75)
    ap.add_argument("--min-term", type=float, default=0.30)
    ap.add_argument("--min-chapter", type=float, default=0.70)
    ap.add_argument("--strict", action="store_true",
                    help="raise thresholds to 0.85 / 0.60 / 0.90")
    ap.add_argument("--warn-only", action="store_true")
    ap.add_argument("--report", default=None)
    args = ap.parse_args()

    if args.strict:
        args.min_toc = max(args.min_toc, 0.85)
        args.min_term = max(args.min_term, 0.60)
        args.min_chapter = max(args.min_chapter, 0.90)

    work = Path(args.work)
    full_path = work / "full.txt"
    if not full_path.exists():
        sys.exit(f"missing {full_path}; run extract_book.py first")
    source = full_path.read_text(encoding="utf-8", errors="replace")
    source = re.sub(r"^===== (PAGE|DOCUMENT) .*=====$", "", source, flags=re.M)
    html_text = strip_html(Path(args.html).read_text(encoding="utf-8", errors="replace"))
    tut_norm = norm(html_text)
    tut_words = set(words(html_text))
    tut_han = han_ngrams(html_text)

    # 1) TOC coverage
    toc = load_toc(work)
    toc_rows = []
    for level, title, loc in toc:
        key = norm(title).rstrip(".")
        if not key or key in GENERIC_TOC or len(key) < 3:
            continue
        cov = title_coverage(title, tut_norm, tut_words, tut_han)
        toc_rows.append({"level": level, "title": title, "loc": loc, "coverage": cov})
    toc_recall = (sum(r["coverage"] >= 0.5 for r in toc_rows) / len(toc_rows)) if toc_rows else 1.0

    # 2) Chapter/term coverage
    chapters = read_chapters(work)
    terms_per_chapter = salient_terms(chapters) if chapters else []
    chapter_rows = []
    all_terms = set()
    hit_terms = set()
    for ch, terms in zip(chapters, terms_per_chapter):
        hits = [w for w in terms if w in tut_words]
        recall = len(hits) / len(terms) if terms else 1.0
        chapter_rows.append({
            "file": ch["file"], "title": ch["title"], "terms": len(terms),
            "hit": len(hits), "recall": recall,
            "missing": [w for w in terms if w not in tut_words][:15],
        })
        all_terms.update(terms)
        hit_terms.update(hits)
    term_recall = len(hit_terms) / len(all_terms) if all_terms else 1.0
    chapter_recall = (sum(r["recall"] >= 0.30 for r in chapter_rows) / len(chapter_rows)
                      if chapter_rows else 1.0)

    # 3) Length ratio (reported, never gated)
    ratio = len(html_text) / max(1, len(source))

    missing_toc = [r for r in toc_rows if r["coverage"] < 0.5]
    weak_chapters = [r for r in chapter_rows if r["recall"] < 0.30]
    missing_terms = sorted(all_terms - hit_terms)[:80]

    print(f"source       : {len(source):,} chars")
    print(f"tutorial     : {len(html_text):,} chars  ({ratio:.1%} of source; not gated)")
    print(f"TOC          : {len(toc_rows)-len(missing_toc)}/{len(toc_rows)} covered "
          f"({toc_recall:.1%}; need {args.min_toc:.0%})")
    print(f"chapters     : {len(chapter_rows)-len(weak_chapters)}/{len(chapter_rows)} above 30% "
          f"term recall ({chapter_recall:.1%}; need {args.min_chapter:.0%})")
    print(f"terms        : {len(hit_terms)}/{len(all_terms)} present "
          f"({term_recall:.1%}; need {args.min_term:.0%})")

    if missing_toc:
        print("\nMISSING / WEAK TOC ENTRIES")
        for r in missing_toc[:40]:
            print(f"  [{r['coverage']:.0%}] {r['title']}")
    if weak_chapters:
        print("\nWEAK CHAPTERS")
        for r in weak_chapters[:20]:
            print(f"  [{r['recall']:.0%}] {r['file']} {r['title']}  missing: {', '.join(r['missing'][:8])}")
    if missing_terms:
        print("\nTOP TERMS NOT FOUND (sample)")
        print("  " + ", ".join(missing_terms[:40]))

    failed = (toc_recall < args.min_toc or term_recall < args.min_term
              or chapter_recall < args.min_chapter)
    if failed:
        print("\nFAIL: coverage below threshold. Expand the missing sections, then rerun.")
    else:
        print("\nPASS: coverage thresholds met. Still do a semantic audit for paraphrased ideas.")

    if args.report:
        md = [
            "# Coverage report",
            "",
            f"- Source: `{full_path}`",
            f"- Tutorial: `{args.html}`",
            f"- Source chars: {len(source):,}",
            f"- Tutorial chars: {len(html_text):,} ({ratio:.1%}; not gated)",
            f"- TOC recall: {toc_recall:.1%} (threshold {args.min_toc:.0%})",
            f"- Chapter recall: {chapter_recall:.1%} (threshold {args.min_chapter:.0%})",
            f"- Term recall: {term_recall:.1%} (threshold {args.min_term:.0%})",
            "",
            "## Missing / weak TOC entries",
            "",
            *([f"- [{r['coverage']:.0%}] {r['title']}" for r in missing_toc] or ["- none"]),
            "",
            "## Weak chapters",
            "",
            *([f"- [{r['recall']:.0%}] `{r['file']}` {r['title']} — missing: {', '.join(r['missing'][:10])}"
               for r in weak_chapters] or ["- none"]),
            "",
            "## Top terms not found",
            "",
            *(["  " + ", ".join(missing_terms[:120])] if missing_terms else ["- none"]),
            "",
            "> This is a heuristic worklist. Missing TOC entries and weak chapters must be",
            "> expanded from the source; paraphrased ideas still need a semantic audit.",
        ]
        Path(args.report).write_text("\n".join(md), encoding="utf-8")
        print(f"\nreport: {args.report}")

    if failed and not args.warn_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
