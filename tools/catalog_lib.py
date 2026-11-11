#!/usr/bin/env python3
"""Shared catalog helpers for the FastRead generators.

Keeping the display order in one place means a new book (or a new category)
gets the same position in README, index.html and the in-book prev/next links.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Ordre d'affichage des catégories connues. Toute catégorie absente de cette
# liste est ajoutée à la fin (ordre alphabétique) au lieu d'être ignorée.
ORDER = [
    "数学 · 分析与代数",
    "数学 · 物理 · 理论",
    "优化 · 金融 · 概率",
    "逻辑 · 形式方法 · 理论计算机",
    "机器学习 · 语言模型",
    "系统 · 数据 · 网络",
    "安全 · 二进制 · 逆向",
    "数值计算 · 工程",
    "认知科学 · 哲学",
    "经济学",
]

REQUIRED = ("file", "title", "author", "pages", "category")


def load_rows():
    return json.load(open(ROOT / "catalog.json", encoding="utf-8"))


def categories(rows):
    seen = {r.get("category", "").strip() for r in rows}
    seen.discard("")
    known = [c for c in ORDER if c in seen]
    extra = sorted(seen - set(ORDER))
    return known + extra


def groups(rows):
    cats = categories(rows)
    out = {c: [] for c in cats}
    for r in rows:
        cat = r.get("category", "").strip()
        if cat in out:
            out[cat].append(r)
    return {c: sorted(out[c], key=lambda x: x["title"].lower()) for c in cats}


def ordered_rows(rows):
    """Flattened display order: category order, then title."""
    out = []
    for cat, items in groups(rows).items():
        out.extend(items)
    return out


def problems(rows):
    """Return a list of human-readable inconsistencies (empty = OK)."""
    out = []
    seen = set()
    for i, r in enumerate(rows, 1):
        for key in REQUIRED:
            if key not in r or r[key] in ("", None):
                out.append(f"ligne {i} : champ « {key} » manquant")
        name = r.get("file", "")
        if name in seen:
            out.append(f"fichier dupliqué dans catalog.json : {name}")
        seen.add(name)
        if name and not (ROOT / "books" / name).exists():
            out.append(f"fichier absent : books/{name}")
        if "pages" in r and not isinstance(r["pages"], int):
            out.append(f"{name} : « pages » doit être un entier")
    books = {p.name for p in (ROOT / "books").glob("*-Tutorial.html")}
    for orphan in sorted(books - seen):
        out.append(f"présent dans books/ mais absent du catalogue : {orphan}")
    return out


if __name__ == "__main__":
    import sys

    rows = load_rows()
    issues = problems(rows)
    if issues:
        print(f"{len(issues)} problème(s) :")
        for p in issues:
            print("  -", p)
        sys.exit(1)
    print(f"catalogue OK : {len(rows)} livres, {len(categories(rows))} catégories")
