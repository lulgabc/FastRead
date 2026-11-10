#!/usr/bin/env python3
"""Regenerate README.md and index.html from catalog.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROWS = json.load(open(ROOT / "catalog.json", encoding="utf-8"))
ORDER = [
    "数学 · 分析与代数",
    "优化 · 金融 · 概率",
    "逻辑 · 形式方法 · 理论计算机",
    "机器学习 · 语言模型",
    "系统 · 数据 · 网络",
    "安全 · 二进制 · 逆向",
    "数值计算 · 工程",
    "认知科学 · 哲学",
    "经济学",
]
groups = {c: [r for r in ROWS if r["category"] == c] for c in ORDER}
total_pages = sum(r["pages"] for r in ROWS)

# ---------- README ----------
lines = [
    "# FastRead",
    "",
    "私人阅读库：把技术书拆成**可读、可查、可自测**的中文单页教程。",
    "",
    f"- **{len(ROWS)} 本**书 · **约 {total_pages:,} 页**原书",
    "- 每个教程是一个独立 HTML 文件，MathJax 已内联，**断网可读**",
    "- 每本含：主线讲解、关键定义/定理/算法、例子、速查表、常见坑",
    "- 数学/理论书含定理盒与公式；系统/编程书含命令、代码与故障案例",
    "",
    "打开 [`index.html`](index.html) 浏览卡片式索引，或直接打开 `books/` 下的文件。",
    "",
    "## 分类索引",
    "",
]
for cat in ORDER:
    if not groups[cat]:
        continue
    lines += [f"### {cat}", "", "| 教程 | 作者 | 页数 | 打开 |", "|---|---|---:|---|"]
    for r in sorted(groups[cat], key=lambda x: x["title"]):
        title = r["title"]
        if r.get("subtitle"):
            title += f"：{r['subtitle']}"
        lines.append(f"| {title} | {r['author']} | {r['pages']} | [HTML](books/{r['file']}) |")
    lines.append("")
lines += [
    "## 使用说明",
    "",
    "- 直接双击 HTML 即可；侧栏目录、搜索、暗色模式、字号、证明折叠都在页面内。",
    "- 每本都是单文件，约 2.2–2.3 MB；43 本合计约 95 MB。",
    "- 原书 PDF 不在此仓库中；这里只保存学习版教程。",
    "- `books/Index-Books1.html`、`books/Index-Books2.html` 是两批生成时的原始索引。",
    "",
    "## 维护",
    "",
    "新增教程：把 HTML 放进 `books/`，在 `catalog.json` 增加一条记录，然后运行：",
    "",
    "```bash",
    "python3 tools/build_index.py",
    "```",
    "",
    "会重新生成 `README.md` 与 `index.html`。",
]
(ROOT / "README.md").write_text("\n".join(lines), encoding="utf-8")

# ---------- index.html ----------
CSS = """
:root{--paper:#f4efe4;--paper2:#fffdf7;--paper3:#ece4d4;--ink:#1c1b18;--ink2:#3b372f;--muted:#726a5c;--line:#d8cdb9;--accent:#b23a26;--teal:#11645c;--gold:#9a6f13}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:"Songti SC","Noto Serif SC",Georgia,serif;line-height:1.7;background-image:radial-gradient(circle at 12% 0%,rgba(178,58,38,.04),transparent 40%)}
.wrap{max-width:1180px;margin:0 auto;padding:54px 26px 80px}
.kicker{font-family:ui-sans-serif,system-ui;font-size:11px;letter-spacing:.22em;color:var(--accent);text-transform:uppercase}
h1{font-size:clamp(36px,6vw,64px);line-height:1.05;margin:14px 0 8px;letter-spacing:-.02em}
.sub{color:var(--muted);max-width:46em;margin:0 0 22px}
.stats{display:flex;gap:26px;flex-wrap:wrap;margin:20px 0 26px;padding:14px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);font-family:ui-sans-serif,system-ui}
.stats b{display:block;font-size:20px}.stats span{font-size:10.5px;color:var(--muted);letter-spacing:.08em;text-transform:uppercase}
.tools{display:flex;gap:10px;align-items:center;margin:0 0 30px;flex-wrap:wrap}
input{width:min(420px,100%);height:42px;border:1px solid var(--line);border-radius:10px;background:var(--paper2);padding:0 14px;font-family:ui-sans-serif,system-ui;font-size:14px;color:var(--ink);outline:none}
input:focus{border-color:var(--teal);box-shadow:0 0 0 3px rgba(17,100,92,.12)}
.hint{font-family:ui-sans-serif,system-ui;font-size:12px;color:var(--muted)}
h2{font-size:21px;margin:38px 0 14px;border-bottom:1px solid var(--line);padding-bottom:8px;display:flex;justify-content:space-between;align-items:baseline}
h2 small{font-family:ui-sans-serif,system-ui;font-size:11px;color:var(--muted);font-weight:400}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:13px}
.card{display:block;background:var(--paper2);border:1px solid var(--line);border-radius:12px;padding:15px 17px;text-decoration:none;color:inherit;transition:.15s}
.card:hover{transform:translateY(-2px);box-shadow:0 10px 26px rgba(60,45,20,.1);border-color:#c4b7a0}
.t{font-weight:700;font-size:15.5px;line-height:1.4}
.s{font-size:12.5px;color:var(--muted);margin-top:3px;line-height:1.5}
.a{font-family:ui-sans-serif,system-ui;font-size:11.5px;color:var(--ink2);margin-top:9px}
.meta{display:flex;gap:10px;margin-top:10px;font-family:ui-sans-serif,system-ui;font-size:10.5px;color:var(--muted);letter-spacing:.03em}
.tag{color:var(--teal)}
footer{margin-top:46px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-family:ui-sans-serif,system-ui;font-size:12px;display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap}
.empty{display:none;color:var(--muted);font-family:ui-sans-serif,system-ui;font-size:14px;margin:30px 0}
"""
parts = []
for cat in ORDER:
    if not groups[cat]:
        continue
    cards = []
    for r in sorted(groups[cat], key=lambda x: x["title"]):
        sub = f'<div class="s">{r["subtitle"]}</div>' if r.get("subtitle") else ""
        cards.append(
            f'<a class="card" href="books/{r["file"]}" data-search="{r["title"]} {r.get("subtitle","")} {r["author"]} {cat}">'
            f'<div class="t">{r["title"]}</div>{sub}'
            f'<div class="a">{r["author"]}</div>'
            f'<div class="meta"><span>{r["pages"]} 页</span><span class="tag">离线 HTML</span></div></a>'
        )
    parts.append(
        f'<section class="cat" data-cat="{cat}"><h2>{cat}<small>{len(groups[cat])} 本</small></h2>'
        f'<div class="grid">{"".join(cards)}</div></section>'
    )

html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FastRead · 私人阅读库</title><style>{CSS}</style></head><body><div class="wrap">
<div class="kicker">FASTREAD · PRIVATE READING LIBRARY</div>
<h1>私人阅读库</h1>
<p class="sub">43 本技术书的中文单页教程：一条主线、关键例子、速查表与常见坑。每个文件都是独立 HTML，离线可读。</p>
<div class="stats">
  <div><b>{len(ROWS)}</b><span>本书</span></div>
  <div><b>{total_pages:,}</b><span>原书页数</span></div>
  <div><b>9</b><span>主题分类</span></div>
  <div><b>0</b><span>需要联网</span></div>
</div>
<div class="tools"><input id="q" type="search" placeholder="搜索书名、作者、主题…" aria-label="搜索"><span class="hint" id="hint">输入关键词过滤</span></div>
<div id="empty" class="empty">没有匹配的教程。</div>
{"".join(parts)}
<footer><span>FastRead · 私人阅读库</span><span><a href="README.md">README</a> · 每个 HTML 自包含</span></footer>
</div>
<script>
const q=document.getElementById('q'), hint=document.getElementById('hint'), empty=document.getElementById('empty');
q.addEventListener('input',()=>{{
  const v=q.value.trim().toLowerCase(); let n=0;
  document.querySelectorAll('section.cat').forEach(sec=>{{
    let m=0;
    sec.querySelectorAll('.card').forEach(c=>{{
      const hit=!v||c.dataset.search.toLowerCase().includes(v);
      c.style.display=hit?'':'none'; if(hit)m++;
    }});
    sec.style.display=m?'':'none'; n+=m;
  }});
  empty.style.display=n?'none':'block';
  hint.textContent=v?`找到 ${{n}} 本`:'输入关键词过滤';
}});
</script>
</body></html>"""
(ROOT / "index.html").write_text(html, encoding="utf-8")
print(f"wrote README.md and index.html ({len(ROWS)} books, {total_pages} pages)")
