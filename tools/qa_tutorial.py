#!/usr/bin/env python3
"""Static + optional headless-render QA for one FastRead tutorial.

Usage:
    python3 tools/qa_tutorial.py books/Some-Tutorial.html
    python3 tools/qa_tutorial.py books/Some-Tutorial.html --render
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def inspect(path: Path) -> dict:
    """Static checks shared with tools/qa_all.py."""
    s = path.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', s)
    seen, dup = set(), set()
    for i in ids:
        if i in seen:
            dup.add(i)
        seen.add(i)
    hrefs = re.findall(r'href="#([^"]+)"', s)
    bad = sorted({h for h in hrefs if h not in seen})
    placeholders = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", s)))
    double_escaped = s.count("&amp;lt;") + s.count("&amp;gt;")
    problems = []
    if dup:
        problems.append(f"duplicate ids: {sorted(dup)[:5]}")
    if bad:
        problems.append(f"broken anchors: {bad[:5]}")
    if placeholders:
        problems.append(f"unresolved placeholders: {placeholders[:5]}")
    if double_escaped:
        problems.append(f"double-escaped entities: {double_escaped}")
    return {
        "path": path,
        "size_mb": path.stat().st_size / 1e6,
        "sections": s.count("<section"),
        "dup": sorted(dup),
        "bad": bad,
        "placeholders": placeholders,
        "problems": problems,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--render", action="store_true", help="also run headless Chrome")
    args = ap.parse_args()
    p = Path(args.file)
    if not p.exists():
        sys.exit(f"not found: {p}")

    r = inspect(p)
    print(f"file       : {p}")
    print(f"size       : {r['size_mb']:.2f} MB")
    print(f"sections   : {r['sections']}")
    print(f"duplicate  : {r['dup'] or 'none'}")
    print(f"bad anchors: {r['bad'] or 'none'}")
    print(f"placeholders: {r['placeholders'] or 'none'}")

    problems = list(r["problems"])

    if args.render:
        if not Path(CHROME).exists():
            print("render     : SKIP (Chrome not found)")
        else:
            url = "file://" + str(p.resolve())
            r2 = subprocess.run(
                [CHROME, "--headless=new", "--disable-gpu",
                 "--virtual-time-budget=9000", "--dump-dom", url],
                capture_output=True, text=True, timeout=120)
            dom = r2.stdout.split("<body", 1)[-1]
            merr = dom.count("<merror")
            mjx = dom.count("<mjx-container")
            body = re.sub(r"<script.*?</script>", "", dom, flags=re.S)
            raw = len(re.findall(r"\$\$", body))
            print(f"mathjax    : {mjx} containers, {merr} errors, {raw} raw display $$")
            if merr:
                problems.append(f"MathJax errors: {merr}")
            if raw:
                problems.append(f"raw display math: {raw}")

    if problems:
        print("\nFAIL")
        for x in problems:
            print(" -", x)
        sys.exit(1)
    print("\nPASS")


if __name__ == "__main__":
    main()
