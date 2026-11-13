#!/usr/bin/env python3
"""Regenerate README.md and index.html from catalog.json.

Also refreshes the in-book library navigation (prev/next/index) via
tools/enhance_books.py, so adding a book only needs one command.

Options:
    --check       validate catalog.json + books/ consistency, then exit
    --skip-books  do not touch the tutorial HTML files
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_lib  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROWS = catalog_lib.load_rows()
PAPERS = []
if (ROOT / "papers.json").exists():
    PAPERS = json.load(open(ROOT / "papers.json", encoding="utf-8"))

ap = argparse.ArgumentParser()
ap.add_argument("--check", action="store_true", help="valider le catalogue et sortir")
ap.add_argument("--skip-books", action="store_true", help="ne pas injecter la navigation")
ARGS = ap.parse_args()

if ARGS.check:
    issues = catalog_lib.problems(ROWS)
    if issues:
        print(f"{len(issues)} problème(s) :")
        for issue in issues:
            print("  -", issue)
        sys.exit(1)
    print(f"catalogue OK : {len(ROWS)} livres")
    sys.exit(0)

groups = catalog_lib.groups(ROWS)
total_pages = sum(r["pages"] for r in ROWS)
book_files = [ROOT / "books" / r["file"] for r in ROWS]
total_bytes = sum(f.stat().st_size for f in book_files if f.exists())
total_mb = round(total_bytes / 1024 / 1024)
avg_mb = round(total_bytes / max(1, len(ROWS)) / 1024 / 1024, 1)
category_count = len(groups)

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
    "- 新转换默认**完整模式**：章节/小节/例子/代码全保留，不设字数上限，并用 `check_coverage.py` 验收",
    "",
    "打开 [`index.html`](index.html) 浏览卡片式索引，或直接打开 `books/` 下的文件。",
    *([f"- 论文解读单独成区：[papers/index.html](papers/index.html)（{len(PAPERS)} 篇）"] if PAPERS else []),
    "",
    "## 分类索引",
    "",
]
for cat in groups:
    lines += [f"### {cat}", "", "| 教程 | 作者 | 页数 | 打开 |", "|---|---|---:|---|"]
    for r in groups[cat]:
        title = r["title"]
        if r.get("subtitle"):
            title += f"：{r['subtitle']}"
        lines.append(f"| {title} | {r['author']} | {r['pages']} | [HTML](books/{r['file']}) |")
    lines.append("")
lines += [
    "## 使用说明",
    "",
    "- 直接双击 HTML 即可；侧栏目录、搜索、暗色模式、字号、证明折叠都在页面内。",
    "- 顶部有「‹ 书库 ›」：上一本 / 返回索引 / 下一本；关闭页面再打开会回到上次阅读位置。",
    "- 每节标题右侧的 ☆ 收藏该节（侧栏显示 ★）；选中正文可高亮，点击高亮即可移除。两者都只存在本机浏览器里。",
    f"- 每本都是单文件，约 {avg_mb} MB；{len(ROWS)} 本合计约 {total_mb} MB。",
    "- 原书 PDF 不在此仓库中；这里只保存学习版教程。",
    "- `books/Index-Books1.html`、`books/Index-Books2.html` 是两批生成时的原始索引。",
    "",
    "## 生成技能：pdf-book-to-web-tutorial",
    "",
    "把“技术 PDF / EPUB → 中文单页教程”的完整流水线保存在：",
    "",
    "`skill/pdf-book-to-web-tutorial/`",
    "",
    "它包含：从 PDF 提取与分章、并行章节笔记提示词、单文件 HTML 构建、数学公式转义、页面骨架、主题 CSS、交互 JS，以及**内联 MathJax**（因此生成物可离线打开）。",
    "",
    "### 安装到 OpenCode",
    "",
    "```bash",
    "# 方案 A：复制（简单）",
    "mkdir -p ~/.config/opencode/skills",
    "cp -R skill/pdf-book-to-web-tutorial ~/.config/opencode/skills/",
    "",
    "# 方案 B：软链接（推荐；仓库更新后自动生效）",
    "ln -sfn \"$PWD/skill/pdf-book-to-web-tutorial\" ~/.config/opencode/skills/pdf-book-to-web-tutorial",
    "```",
    "",
    "### 怎么触发",
    "",
    "在对话里直接说：",
    "",
    "> 用 `pdf-book-to-web-tutorial` 把这本书做成单页教程",
    "",
    "或在 OpenCode 中加载该 skill。它会按“提取 → 蓝图 → 并行笔记 → 写作 → 构建 → QA → 事实核查”的顺序执行。",
    "",
    "### 手动使用",
    "",
    "```bash",
    "# 1) 提取 PDF：带页码全文 + 按章拆分 + 编号结果统计",
    "python3 skill/pdf-book-to-web-tutorial/scripts/extract_book.py book.pdf work/",
    "",
    "# 2) 在 src/sections/ 写 HTML 片段后，组装单文件",
    "python3 skill/pdf-book-to-web-tutorial/scripts/build_tutorial.py \\",
    "  --sections src/sections --out dist/Book-Tutorial.html \\",
    "  --title \"书名 · 交互教程\" --book-title \"书名\" \\",
    "  --book-subtitle \"副标题\" --short-title \"书名\"",
    "```",
    "",
    "`--dev` 会改用 CDN 加载 MathJax，构建更快，但产物不自包含；正式交付不要加。",
    "",
    "### 技能目录",
    "",
    "| 路径 | 作用 |",
    "|---|---|",
    "| `SKILL.md` | 完整工作流与十个常见坑 |",
    "| `scripts/extract_book.py` | PDF/EPUB → `full.txt`、`chapters/`、`meta.json` |",
    "| `scripts/build_tutorial.py` | sections + shell → 单文件 HTML（内联 CSS/JS/MathJax） |",
    "| `scripts/escape_math.py` | 修复公式里的 `<`、`>`、`&`，并保护代码块 |",
    "| `scripts/check_coverage.py` | 最终覆盖率检测（TOC/章节/术语/长度比） |",
    "| `assets/shell.html` | 侧栏、顶栏、搜索、进度、暗色模式骨架 |",
    "| `assets/theme.css` | 定理盒、速查表、代码块、响应式、打印样式 |",
    "| `assets/app.js` | 目录高亮、搜索、主题、字号、证明折叠 |",
    "| `assets/mathjax-tex-svg.js` | 内联 MathJax，保证离线可用 |",
    "| `references/pipeline.md` | 分阶段细节与子代理提示词 |",
    "| `references/qa-checklist.md` | 浏览器、手机、file:// 离线检查 |",
    "| `references/design-system.md` | 版式、定理盒与交互约定 |",
    "",
    "## 维护",
    "",
    "**第 0 步：查重**（避免把同一本书做两遍）：",
    "",
    "```bash",
    "python3 tools/check_duplicate.py ~/Downloads/Books/新书.pdf",
    "# 退出码 0 = 没找到，可以转换；1 = 已存在/可能重复，先人工确认",
    "```",
    "",
    "新增教程：把 HTML 放进 `books/`，在 `catalog.json` 增加一条记录，然后运行：",
    "",
    "```bash",
    "python3 tools/build_index.py",
    "```",
    "",
    "会重新生成 `README.md` 与 `index.html`。",
]

ADD_BOOK = r"""
## 新增一本书

### 最省事：让 agent 跑

1. 把新 PDF 放到仓库外：

```bash
mkdir -p ~/Downloads/FastRead-inbox
# 把 PDF 放进 FastRead-inbox
```

2. 在 OpenCode 里说：

> 先用 `python3 tools/check_duplicate.py` 对 `~/Downloads/FastRead-inbox/` 里的每本书查重，已存在的跳过；  
> 再用 `pdf-book-to-web-tutorial` 把剩下的 PDF 做成单页教程。  
> 每本输出到 `~/Documents/Default Project/FastRead/books/<英文短名>-Tutorial.html`，  
> 完整覆盖原书章节/小节/例子/代码，不设字数上限；  
> 更新 `catalog.json`、`README.md`、`index.html`，  
> 跑覆盖率检测和 QA，最后提交并 push。

Agent 会依次完成：提取 → 章节蓝图 → 写 sections → 构建单文件 → **覆盖率检测** → QA → 更新索引 → Git 提交。

默认是**完整模式**：章节、小节、编号结果、例子、代码、参数都要保留；不设字数上限，长度服从内容。

### 手动流程

#### 1. 提取

```bash
cd "$HOME/Documents/Default Project/FastRead"
python3 skill/pdf-book-to-web-tutorial/scripts/extract_book.py \
  ~/Downloads/FastRead-inbox/新书.pdf \
  work/新书
```

查看 `work/新书/meta.json`：页数、章节数、`numbered_results_total`。若 `low_text_pages` 很多，先 OCR。

#### 2. 写 sections

在 `work/新书/src/sections/` 下写：

```text
00-hero.html
01-ch1.html
02-ch2.html
...
99-summary.html
```

使用 skill 的类：`chapter`、`lede`、`chap-intro`、`thm def/theorem/lem/ex/rem/warn`、`intuition`、`table-wrap cheat`、`cards`。

参考：

- `skill/pdf-book-to-web-tutorial/SKILL.md`
- `skill/pdf-book-to-web-tutorial/references/pipeline.md`
- `skill/pdf-book-to-web-tutorial/references/design-system.md`

#### 3. 构建

```bash
python3 skill/pdf-book-to-web-tutorial/scripts/build_tutorial.py \
  --sections work/新书/src/sections \
  --out books/New-Book-Tutorial.html \
  --title "新书 · 交互教程" \
  --book-title "新书" \
  --book-subtitle "副标题" \
  --short-title "新书" \
  --stats "<b>12</b> 章 · <b>500</b> 页"
```

默认内联 MathJax，产物约 2.2 MB，可离线打开。正式交付不要加 `--dev`。

#### 4. 覆盖率检测（必须）

```bash
python3 skill/pdf-book-to-web-tutorial/scripts/check_coverage.py \
  --work work/新书 --html books/New-Book-Tutorial.html \
  --report work/新书/coverage-report.md
```

门槛：TOC ≥75%、章节召回 ≥70%、术语召回 ≥30%。报告里的 missing 条目要补内容后重跑，不要改报告。

#### 5. QA

```bash
python3 tools/qa_tutorial.py books/New-Book-Tutorial.html --render
```

应满足：`merror = 0`、无 raw `$$`、无重复 ID、无断链、无未替换占位符、控制台 0 错误。手机 390px 检查见 skill 的 `references/qa-checklist.md`。

#### 6. 更新索引

在 `catalog.json` 增加一条：

```json
{
  "file": "New-Book-Tutorial.html",
  "title": "New Book",
  "subtitle": "A Subtitle",
  "author": "Author Name",
  "pages": 500,
  "category": "数学 · 分析与代数",
  "batch": "Books3"
}
```

可以直接使用现有九类之一；新分类会自动追加到末尾（要控制位置就加进 `tools/catalog_lib.py` 的 `ORDER`）：

- 数学 · 分析与代数
- 优化 · 金融 · 概率
- 逻辑 · 形式方法 · 理论计算机
- 机器学习 · 语言模型
- 系统 · 数据 · 网络
- 安全 · 二进制 · 逆向
- 数值计算 · 工程
- 认知科学 · 哲学
- 经济学

然后重建索引：

```bash
python3 tools/build_index.py
```

会重新生成 `README.md` 与 `index.html`，并给**所有**书刷新「上一本 / 书库 / 下一本」导航、阅读进度、书签与高亮脚本。新书顺序由分类 + 标题自动计算，不需要改其它书。

提交前校验：

```bash
python3 tools/build_index.py --check
```

#### 7. 提交

```bash
git add books/New-Book-Tutorial.html catalog.json README.md index.html
git commit -m "Add New Book tutorial"
git push
```

### 命名约定

- 文件名：`Title-Words-Tutorial.html`，ASCII、连字符、无空格。
- 一本书一个 HTML；配套 `work/` 不提交。
- 不要提交 PDF；`.gitignore` 已忽略 `*.pdf`、`inbox/`、`work/`。

### 详细版

更细的说明、常见坑和 QA 清单见 **[docs/ADDING-BOOKS.md](docs/ADDING-BOOKS.md)**。
"""
idx = lines.index("## 维护")
lines[idx:idx] = ADD_BOOK.strip("\n").split("\n") + [""]

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
.goto{font-family:ui-sans-serif,system-ui;font-size:12.5px;color:var(--teal);text-decoration:none;
border:1px solid var(--line);border-radius:9px;padding:9px 13px;background:var(--paper2)}
.goto:hover{border-color:var(--teal);background:var(--paper3)}
input{width:min(420px,100%);height:42px;border:1px solid var(--line);border-radius:10px;background:var(--paper2);padding:0 14px;font-family:ui-sans-serif,system-ui;font-size:14px;color:var(--ink);outline:none}
input:focus{border-color:var(--teal);box-shadow:0 0 0 3px rgba(17,100,92,.12)}
.hint{font-family:ui-sans-serif,system-ui;font-size:12px;color:var(--muted)}
.continue[hidden]{display:none}
.continue{display:flex;align-items:center;gap:10px;margin:0 0 22px;padding:12px 15px;border:1px solid var(--line);border-left:3px solid var(--teal);border-radius:10px;background:var(--paper2);font-family:ui-sans-serif,system-ui;font-size:13px}
.continue a{color:inherit;text-decoration:none;display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;flex:1}
.continue b{font-weight:700}
.continue span{color:var(--muted);font-size:12px}
.continue button{border:0;background:transparent;color:var(--muted);cursor:pointer;font-size:13px;padding:2px 6px;border-radius:6px}
.continue button:hover{background:var(--paper3);color:var(--ink)}
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
for cat in groups:
    cards = []
    for r in groups[cat]:
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

paper_link = (f'<a class="goto" href="papers/index.html">论文解读 · {len(PAPERS)} 篇 →</a>'
              if PAPERS else "")
html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FastRead · 私人阅读库</title><style>{CSS}</style></head><body><div class="wrap">
<div class="kicker">FASTREAD · PRIVATE READING LIBRARY</div>
<h1>私人阅读库</h1>
<p class="sub">{len(ROWS)} 本技术书的中文单页教程：一条主线、关键例子、速查表与常见坑。每个文件都是独立 HTML，离线可读。</p>
<div class="stats">
  <div><b>{len(ROWS)}</b><span>本书</span></div>
  <div><b>{total_pages:,}</b><span>原书页数</span></div>
  <div><b>{category_count}</b><span>主题分类</span></div>
  <div><b>0</b><span>需要联网</span></div>
</div>
<div class="tools"><input id="q" type="search" placeholder="搜索书名、作者、主题…" aria-label="搜索"><span class="hint" id="hint">输入关键词过滤</span>{paper_link}</div>
<div id="continue" class="continue" hidden></div>
<div id="empty" class="empty">没有匹配的教程。</div>
{"".join(parts)}
<footer><span>FastRead · 私人阅读库</span><span><a href="README.md">README</a> · <a href="docs/ADDING-BOOKS.md">新增书籍</a> · <a href="docs/ADDING-PAPERS.md">新增论文</a> · <a href="papers/index.html">论文解读</a> · <a href="skill/pdf-book-to-web-tutorial/SKILL.md">Skill</a></span></footer>
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
CONTINUE_JS = """
<script>
(function(){
  try{
    var last=JSON.parse(localStorage.getItem('fastread:last')||'null');
    if(!last||!last.file) return;
    var box=document.getElementById('continue');
    var link=document.createElement('a');
    link.href=last.path||('books/'+last.file+'.html');
    var b=document.createElement('b');
    b.textContent=String(last.title||last.file).replace(/ · 交互教程$/,'');
    var meta=document.createElement('span');
    meta.textContent='上次读到 '+Math.round((last.pct||0)*100)+'%';
    link.appendChild(document.createTextNode('继续阅读：')); link.appendChild(b); link.appendChild(meta);
    var clear=document.createElement('button');
    clear.type='button'; clear.textContent='×'; clear.title='清除阅读记录';
    clear.setAttribute('aria-label','清除阅读记录');
    clear.addEventListener('click',function(){ try{localStorage.removeItem('fastread:last');}catch(e){} box.hidden=true; });
    box.appendChild(link); box.appendChild(clear); box.hidden=false;
  }catch(e){}
})();
</script>
"""
html = html.replace("</body>", CONTINUE_JS + "</body>", 1)
(ROOT / "index.html").write_text(html, encoding="utf-8")
print(f"wrote README.md and index.html ({len(ROWS)} books, {total_pages} pages)")

if not ARGS.skip_books:
    subprocess.run([sys.executable, str(ROOT / "tools" / "enhance_books.py")], check=True)
