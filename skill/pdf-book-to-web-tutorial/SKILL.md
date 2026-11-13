---
name: pdf-book-to-web-tutorial
description: Build a single self-contained interactive HTML tutorial from a long technical PDF or EPUB book (mathematics, physics, CS, engineering), in Chinese by default. Use when the user asks to "把这本书/PDF做成网页教程", "做成一个单页教程", "turn this book into an interactive site", or wants a 500+ page book turned into a searchable, illustrated guide that preserves all chapters, sections and details, with MathJax, dark mode, offline support and a final coverage audit.
---

# PDF/书籍 → 单页交互教程

目标产物：**一个 HTML 文件**。双击可读、断网可读；有目录、搜索、定理盒、证明折叠、速查表、暗色模式、阅读进度。内容不是“读后感”，而是**按原书编号覆盖全部结果**的学习版：核心定理给陈述 + 直觉 + 证明思路，全部编号结果用每章速查表兜底。

本 skill 附带一套已验证的流水线与可直接复用的 UI：

- `scripts/extract_book.py`：PDF 或 EPUB → 带页码/文档标记的全文 + 按章拆分 + 结果清单
- `scripts/extract_paper.py`：论文 PDF 或 arXiv/PDF URL → 元数据 + 摘要 + 分节文本（outline 优先，缺失时按标题启发式）
- `scripts/build_tutorial.py`：`shell + sections` → 单文件（内联 CSS/JS/MathJax）
- `scripts/check_coverage.py`：最终覆盖率检测（TOC、章节、术语、长度比），可生成缺口报告
- `scripts/escape_math.py`：修复 `$...$` 里的 `<`/`>`/`&`（最容易毁掉整页的坑）
- `assets/shell.html`、`theme.css`、`app.js`：生产级页面骨架
- `references/pipeline.md`：分阶段细节、子代理提示词、内容配比
- `references/qa-checklist.md`：浏览器自动检查 + 人工核对清单
- `references/design-system.md`：版式、定理盒类型、交互约定

---

## 论文模式（paper）

论文与书的流水线共用 UI 和构建器，但提取与结构不同：

```bash
python3 <skill>/scripts/extract_paper.py https://arxiv.org/abs/1706.03762 work/papers/attention
# 或
python3 <skill>/scripts/extract_paper.py paper.pdf work/papers/attention
```

- 自动读取 arXiv API（标题、作者、摘要、年份、DOI）或 PDF 元数据/首页大字号标题
- 输出 `meta.json`、`full.txt`、`toc.json`、`abstract.txt`、`refs.txt`、`sections/`
- 覆盖检测同样用 `check_coverage.py`；它会自动回退到 `sections/` 目录

论文教程建议 10–13 个 section：问题 → 方法（公式与符号）→ 架构 → 训练 → 结果与消融 → 分析 → 局限 → 复现 → 术语/自测。**不要逐字翻译摘要**，要解释设计动机与数字。

论文入库见 `docs/ADDING-PAPERS.md`（`papers.json` + `papers/index.html`）。

---

## 0. 先定“覆盖契约”：默认是完整模式，不是摘要

**长度不是约束，覆盖才是约束。** 一本 500 页的书做成 30k–80k 汉字是正常的；不要为了“好读”删掉章节、小节、公式、代码、参数或反例。

必须保留：

- 目录里的每一个 chapter 与 section（包括 “Bonus Material”“Appendix”“Problems” 中的关键结论）
- 所有 Definition / Theorem / Lemma / Proposition / Example / Remark 的**陈述**；证明可压缩为思路，但不能删掉假设、结论、常数的含义
- 所有算法步骤、命令、配置、代码示例的关键行，以及输入/输出/复杂度
- 关键数字、参数、阈值、公式、图注、表格、反例、失败模式
- 原书的术语与符号；首次出现给中文解释

允许：合并重复叙述、改写语言、去掉页眉页脚/纯排版、把长证明压成“证明骨架”。

禁止：“本章只讲重点”“其余从略”“类似地”“不再赘述”。

建议分层，但 T1 不是“速查表替代正文”：

| 层级 | 内容 | 呈现 |
|---|---|---|
| T0 | 每条主线的核心定理/算法 | 完整陈述 + 直觉 + 证明/推导思路 |
| T1 | 每个 section 的定义、结论、参数、例子 | 正文逐节覆盖；章末速查表只做复习 |
| T2 | 所有 Example、反例、应用、代码 | 独立盒子 + 计算/运行结果 |

最后必须跑 `check_coverage.py`：TOC 覆盖、章节术语召回、全局术语召回三项都过线才算完成。检测报告是工作清单，不是装饰。

**不要中途问用户**。缺信息就按“完整、可读、可核查”自行决定，最后说明取舍。

---

## 1. 提取与侦察

```bash
python3 -m pip install --user pymupdf
python3 <skill>/scripts/extract_book.py "/path/book.pdf" work/
python3 <skill>/scripts/extract_book.py "/path/book.epub" work/
```

看 `work/meta.json`：

- `pages`、`toc_entries`、`chapters`
- `numbered_results_total`（决定“766 条”这类统计口径）
- `low_text_pages`：若很多页几乎无字，先 OCR：
  ```bash
  brew install ocrmypdf tesseract
  ocrmypdf --deskew --clean book.pdf book-ocr.pdf
  ```

EPUB 会按 OPF spine 与 NCX/nav 拆分；若公式是图片，`meta.json` 的 `images` 会提醒你回看 XHTML。

然后读：目录、Preface、Notation、每章第一页、Notes。**先读目录再读正文**，否则容易把全书读成流水账。

---

## 2. 画蓝图（写代码前）

1. 从 `toc.json` 列出章/节，标出 Part 分界。
2. 用 `meta.json` 的结果计数确认“全量”规模。
3. 选 8–12 条**定理链**作为 T0，例如：
   - 弱解：测度 → 极值原理 → 比较 → Perron
   - 内部正则：截面 → 局部化 → \(C^{1,\alpha}\) → \(W^{2,1+\varepsilon}\) → \(C^{2,\alpha}\)
   - 边界：边界局部化 → 边界截面 → 边界二阶估计
   - 线性化：Harnack → 边界估计 → Green 函数 → 散度型
4. 决定页面 section 数（通常 20–26 个）与侧栏导航。
5. 写一个 `src/nav.html`（可选；不写则 build 自动从 section 生成）。

---

## 3. 并行章节笔记（关键加速）

把章节文本分给多个子代理。完整模式下建议 **一个代理只负责一章**（长书可一章拆 2–3 个代理），不要一个代理吞 1–2 章后只写 8k 字。

提示词必须包含：

- 读 `work/chapters/N.txt`（EPUB 同样）
- **逐节覆盖**：每个 section、每个编号结果、每个 Example、每个算法/命令/代码块
- PDF/EPUB 公式乱码或图片，按数学知识重建，但**不得编造定理内容**
- 每条：精确 LaTeX 陈述 + 1–3 句中文直觉 + 证明思路（有教学价值时）
- 例子要给计算/运行结果；反例要写“打破了什么”
- 结尾写“本章脉络”“常见误区”
- **不设字数上限**；一章通常 3k–8k 汉字，长章可 10k+
- 输出 `notes/chNN.md`

完整模板见 `references/pipeline.md`。子代理跑的时候，你可以同时写 UI/骨架，不要等。

---

## 4. 写章节

每章固定节奏（读者会形成预期）：

1. `lede`：这一章解决什么问题，一句话。
2. 章节卡：本章覆盖范围 + 标签。
3. `mapchips`：5–8 个关键词。
4. 按原书 section 顺序逐节展开，不要跳过“小”节；每节给定义/定理/算法/例子。
5. 每个编号结果至少有一个独立盒子或明确段落；长证明给折叠的证明骨架。
6. 代码/命令/参数表按原书出现顺序保留；不要只给“代表性例子”。
7. “全章结果速查表”：**每个编号一行**，作为复习索引，不替代正文。
8. “常见误区”盒：3–5 条。

写作规则：

- 定理陈述用书里的编号：`5.11`、`Theorem 5.11` 不混用。
- 中文放在 math 外面。不要在 `\text{...}` 里写中文（SVG 字体常缺字）。
- 证明放 `<details class="proof">`，正文只留“证明思路”。
- 直觉用 `.intuition`，不要和定理混在一起。
- 每个反例都回答：打破哪个直觉？标度指数？依赖哪个维数/边界条件？

---

## 5. 组装单文件

项目结构：

```
project/
  src/
    sections/00-intro.html
    sections/01-ch1.html
    ...
    nav.html
  dist/Tutorial.html
```

构建：

```bash
python3 <skill>/scripts/build_tutorial.py \
  --sections src/sections \
  --out dist/Tutorial.html \
  --title "Monge–Ampère 方程 · 交互教程" \
  --book-title "Monge–Ampère 方程" \
  --book-subtitle "从凸几何到完全非线性正则性" \
  --short-title "Monge–Ampère" \
  --stats "<b>15</b> 章 · <b>766</b> 条结果" \
  --footer-coverage "15 章 · 766 条编号结果 · 40+ 例子与反例"
```

- 默认内联 `assets/mathjax-tex-svg.js`，产出约 2–2.5 MB，可离线。
- `--dev` 改用 CDN，构建快，但产物不自包含。
- `build_tutorial.py` 会自动调用 `escape_math.py`，仍建议单独跑一次检查。
- 若不用自带 shell，也可以直接维护 `head.html + sec-*.html + end.html` 再拼接；核心是**最后一定内联 MathJax**。

---

## 6. 自动 QA（必须做）

见 `references/qa-checklist.md`。最低门槛：

```bash
python3 <skill>/scripts/check_coverage.py \
  --work work/<book> --html dist/<book>-Tutorial.html \
  --report coverage-<book>.md
```

要求：TOC 覆盖 ≥ 75%、章节召回 ≥ 70%、术语召回 ≥ 30%（`--strict` 为 85/90/60）。不过线就补，不要只改报告。



```js
({
  merr: document.querySelectorAll('merror').length,        // 0
  mjx: document.querySelectorAll('mjx-container').length,  // > 1000
  raw: [...document.querySelectorAll('p,li,td,.thm-title')]
        .filter(e => /\$\$|\\[a-z]+\{/.test(e.textContent)
                  && !e.querySelector('mjx-container')).length, // 0
  dup: [...new Set([...document.querySelectorAll('[id]')]
        .map(e=>e.id).filter((x,i,a)=>a.indexOf(x)!==i))],   // []
  badLinks: [...document.querySelectorAll('a[href^="#"]')]
        .map(a=>a.getAttribute('href'))
        .filter(h=>h!=='#'&&!document.querySelector(h)),      // []
  overflow: [document.body.scrollWidth, innerWidth]          // 相等
})
```

再加：console error = 0；手机 390px 宽（用 iframe 测，见 QA）；`file://` 打开正常；暗色模式图表可读。

---

## 7. 事实核查（不要省）

先跑覆盖率检测并补齐缺口；再启动 2 个审计子代理（前半/后半），让它们**只列具体遗漏和错误**：

- 编号是否存在、内容是否对得上
- 公式/指数/常数/假设（\(C^3\) vs \(C^2\)、\(p>n\) vs \(p<n\)、\(n=2\) 例外）
- 是否把“未解决”说成“失败”，把“凸包”说成“原函数”
- 是否漏掉 TOC 中的 section、编号结果、参数、代码/命令、图注
- 覆盖率报告里列为 missing 的条目是否真的补上

收到清单后逐条修，再跑一次 QA。数学书里最常见的错不是大方向，而是**指数、积分条件、边界假设、归属**。

---

## 8. 十个必须记住的坑

1. **`$...$` 里的 `<` 会被 HTML 吃掉。** 例如 `$u(x)<u(y)$` 里的 `<u` 被当成 `<u>` 标签，后半句消失。用 `escape_math.py`，它是幂等的，能保留已有 `&lt;`。
2. **类名冲突。** `.thm.thm` 会匹配 `class="thm def"`（同一个 `thm` 类出现一次就够），从而覆盖定义盒颜色。定理类型用 `.thm.theorem`，不要 `.thm.thm`。
3. **MathJax 异步 + `#anchor`。** 页面先按未排版高度跳转，排完版就跑偏。在 `MathJax.startup.promise` 后重新 `scrollIntoView`，并监听 `hashchange`。
4. **`\text{中文}`。** MathJax SVG 字体通常没有中文字形。中文一律放 math 外。
5. **SVG `<text>` 里的 `$...$`** 会被 MathJax 当公式排版，可能变成巨大字符。SVG 标签用普通 Unicode（`C¹,ᵅ`、`W²,¹⁺ᵋ`）。
6. **暗色模式图表。** 图里写死深色描边，夜间会看不见。给 `figure svg`/hero SVG 加一块浅色“纸板”背景。
7. **手机测试。** macOS headless Chrome 最小布局宽度约 500px，`--window-size=390` 的截图会把 500px 布局裁掉。用 390px iframe 测真实媒体查询。
8. **缓存。** 开发时浏览器会缓存旧 HTML/JS；每次用 `?v=N` 或 hard reload，否则“改了没生效”会浪费半小时。
9. **PDF 公式是乱码，不是真理。** 所有公式按数学重建后，用原书定理编号回查；不要相信 `pdftotext` 的上下标。
10. **不要用 `Definition 11.5` 指代公式 (11.5)。** 书里 `(11.5)` 是显示公式，`Theorem 11.5` 才是定理；编号前先看它是 Definition/Theorem 还是公式号。
11. **EPUB 的公式可能是图片。** `meta.json` 的 `images` 只是提醒；关键公式要回看 XHTML/原书，不能只读提取文本。
12. **覆盖率检测不是语义理解。** 它抓“整节没写、术语没出现”，抓不到“写了一段但意思错了”；所以必须再做人工/子代理审计。

---

## 9. 交付

```bash
ls -lh dist/Tutorial.html
```

交付时说清楚：

- 文件路径；单文件、离线、MathJax 已内联
- 覆盖：章数 / 编号结果数 / 例子与反例数
- 交互：目录、搜索、暗色、字号、证明折叠、自测
- 核对：MathJax 错误 0、断链 0、控制台 0
- 保留 `src/` 与构建脚本，方便下次改

不要把“完整模式”说成“逐字翻译”；准确说明：**章节/小节/编号结果/例子/代码全部覆盖，证明给思路而非逐字重写，长度服从内容**。交付时附上 `coverage-report.md` 和检测结论。
