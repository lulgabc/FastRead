#!/usr/bin/env python3
"""Regenerate papers/index.html from papers.json.

Usage:
    python3 tools/build_papers_index.py
    python3 tools/build_papers_index.py --check
"""
import argparse
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "papers.json"
OUT = ROOT / "papers" / "index.html"

REQUIRED = ("file", "title", "authors", "year")

CSS = """
:root{--paper:#f4efe4;--paper2:#fffdf7;--paper3:#ece4d4;--ink:#1c1b18;--ink2:#3b372f;
--muted:#726a5c;--line:#d8cdb9;--accent:#b23a26;--teal:#11645c;--gold:#9a6f13;--violet:#5a4a78}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Songti SC","Noto Serif SC",Georgia,serif;
line-height:1.7;background-image:radial-gradient(circle at 12% 0%,rgba(178,58,38,.04),transparent 40%)}
.wrap{max-width:1180px;margin:0 auto;padding:54px 26px 80px}
.kicker{font-family:ui-sans-serif,system-ui;font-size:11px;letter-spacing:.22em;color:var(--accent);text-transform:uppercase}
h1{font-size:clamp(34px,5.5vw,56px);line-height:1.08;margin:14px 0 8px;letter-spacing:-.02em}
.sub{color:var(--muted);max-width:52em;margin:0 0 20px}
.crumb{font-family:ui-sans-serif,system-ui;font-size:12px;margin:0 0 18px}
.crumb a{color:var(--teal);text-decoration:none}
.stats{display:flex;gap:26px;flex-wrap:wrap;margin:18px 0 24px;padding:14px 0;
border-top:1px solid var(--line);border-bottom:1px solid var(--line);font-family:ui-sans-serif,system-ui}
.stats b{display:block;font-size:20px}.stats span{font-size:10.5px;color:var(--muted);letter-spacing:.08em;text-transform:uppercase}
.tools{display:flex;gap:10px;align-items:center;margin:0 0 26px;flex-wrap:wrap}
input{width:min(440px,100%);height:42px;border:1px solid var(--line);border-radius:10px;background:var(--paper2);
padding:0 14px;font-family:ui-sans-serif,system-ui;font-size:14px;color:var(--ink);outline:none}
input:focus{border-color:var(--teal);box-shadow:0 0 0 3px rgba(17,100,92,.12)}
.hint{font-family:ui-sans-serif,system-ui;font-size:12px;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:13px}
.card{display:block;background:var(--paper2);border:1px solid var(--line);border-radius:12px;padding:16px 18px;
text-decoration:none;color:inherit;transition:.15s}
.card:hover{transform:translateY(-2px);box-shadow:0 10px 26px rgba(60,45,20,.1);border-color:#c4b7a0}
.year{font-family:ui-sans-serif,system-ui;font-size:10.5px;letter-spacing:.12em;color:var(--accent)}
.t{font-weight:700;font-size:16px;line-height:1.4;margin-top:4px}
.a{font-size:12.5px;color:var(--muted);margin-top:4px;line-height:1.5}
.abs{font-size:12.8px;color:var(--ink2);margin-top:8px;line-height:1.65;
display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.meta{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;font-family:ui-sans-serif,system-ui;font-size:10.5px;color:var(--muted)}
.tag{color:var(--teal)}.venue{color:var(--violet)}
.empty{display:none;color:var(--muted);font-family:ui-sans-serif,system-ui;font-size:14px;margin:30px 0}
footer{margin-top:46px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);
font-family:ui-sans-serif,system-ui;font-size:12px;display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap}
footer a{color:var(--teal);text-decoration:none}
@media(prefers-color-scheme:dark){
body{--paper:#121417;--paper2:#191c21;--paper3:#20242b;--ink:#e9e3d6;--ink2:#c7c0b2;--muted:#9b9487;--line:#33383f}
}
"""


def problems(rows):
    out = []
    seen = set()
    for i, r in enumerate(rows, 1):
        for key in REQUIRED:
            if key not in r or r[key] in ("", None):
                out.append(f"ligne {i} : champ « {key} » manquant")
        name = r.get("file", "")
        if name in seen:
            out.append(f"fichier dupliqué : {name}")
        seen.add(name)
        if name and not (ROOT / "papers" / name).exists():
            out.append(f"fichier absent : papers/{name}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if not CATALOG.exists():
        if args.check:
            print("papers.json absent (aucune publication)")
            return
        rows = []
    else:
        rows = json.load(open(CATALOG, encoding="utf-8"))

    issues = problems(rows)
    if args.check:
        if issues:
            for x in issues:
                print(" -", x)
            sys.exit(1)
        print(f"papers OK : {len(rows)}")
        return

    rows.sort(key=lambda r: (-int(r.get("year") or 0), r["title"].lower()))
    cards = []
    for r in rows:
        tags = "".join(f'<span class="tag">#{html.escape(str(t))}</span>'
                       for t in (r.get("tags") or [])[:4])
        venue = f'<span class="venue">{html.escape(r["venue"])}</span>' if r.get("venue") else ""
        arx = f'<span>arXiv {html.escape(r["arxiv"])}</span>' if r.get("arxiv") else ""
        cards.append(
            f'<a class="card" href="{html.escape(r["file"], quote=True)}" '
            f'data-search="{html.escape(" ".join([r["title"], r.get("authors",""), r.get("venue",""), " ".join(r.get("tags") or [])]).lower(), quote=True)}">'
            f'<div class="year">{int(r.get("year") or 0)}</div>'
            f'<div class="t">{html.escape(r["title"])}</div>'
            f'<div class="a">{html.escape(r.get("authors",""))}</div>'
            f'<div class="abs">{html.escape(r.get("summary",""))}</div>'
            f'<div class="meta">{venue}{arx}{tags}</div></a>')

    years = [int(r.get("year") or 0) for r in rows if r.get("year")]
    span = (str(years[0]) if min(years) == max(years)
            else f"{min(years)}–{max(years)}") if years else "—"
    page = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FastRead · 论文索引</title><style>{CSS}</style></head><body><div class="wrap">
<div class="kicker">FASTREAD · PAPER NOTES</div>
<h1>论文解读</h1>
<p class="sub">把论文读成可复述的结构：问题、方法、实验、结论与局限。每篇一个独立 HTML，公式内联，断网可读。</p>
<div class="crumb"><a href="../index.html">← 首页</a> · <a href="../books/index.html">书籍索引</a> · <b>论文索引</b></div>
<div class="stats">
  <div><b>{len(rows)}</b><span>篇论文</span></div>
  <div><b>{span}</b><span>年份跨度</span></div>
  <div><b>{len({t for r in rows for t in (r.get("tags") or [])})}</b><span>主题标签</span></div>
  <div><b>0</b><span>需要联网</span></div>
</div>
<div class="tools"><input id="q" type="search" placeholder="搜索标题、作者、会议、标签…" aria-label="搜索">
<span class="hint" id="hint">输入关键词过滤</span></div>
<div id="empty" class="empty">没有匹配的论文。</div>
<div class="grid" id="grid">{"".join(cards)}</div>
<footer><span>FastRead · 论文索引</span><span><a href="../index.html">首页</a> ·
<a href="../books/index.html">书籍</a> · <a href="../docs/ADDING-PAPERS.md">新增论文</a></span></footer>
</div>
<script>
const q=document.getElementById('q'),hint=document.getElementById('hint'),empty=document.getElementById('empty');
q.addEventListener('input',()=>{{
  const v=q.value.trim().toLowerCase();let n=0;
  document.querySelectorAll('.card').forEach(c=>{{
    const hit=!v||c.dataset.search.includes(v);
    c.style.display=hit?'':'none';if(hit)n++;
  }});
  empty.style.display=n?'none':'block';
  hint.textContent=v?`找到 ${{n}} 篇`:'输入关键词过滤';
}});
</script>
</body></html>"""
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote papers/index.html ({len(rows)} papers)")


if __name__ == "__main__":
    main()
