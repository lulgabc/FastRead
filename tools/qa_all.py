#!/usr/bin/env python3
"""Static QA across every tutorial in books/ (no browser needed).

Usage:
    python3 tools/qa_all.py            # summary + failures
    python3 tools/qa_all.py --verbose  # one line per book
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qa_tutorial import inspect  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    files = sorted((ROOT / "books").glob("*-Tutorial.html"))
    if not files:
        sys.exit("no tutorials in books/")

    failed = []
    for p in files:
        r = inspect(p)
        if r["problems"]:
            failed.append((p.name, r["problems"]))
            print(f"FAIL {p.name}: {r['problems']}")
        elif args.verbose:
            print(f"ok   {p.name}  {r['size_mb']:.2f} MB  {r['sections']} sections")

    total_mb = sum(p.stat().st_size for p in files) / 1e6
    print(f"\n{len(files) - len(failed)}/{len(files)} tutorials pass static checks "
          f"({total_mb:.1f} MB)")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
