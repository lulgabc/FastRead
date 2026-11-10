---
name: pdf-book-to-web-tutorial
description: Build a single self-contained interactive HTML tutorial from a long technical PDF/book (mathematics, physics, CS, engineering), in Chinese by default. Use when the user asks to "把这本书/PDF做成网页教程", "做成一个单页教程", "summarize this book as an interactive site", or wants a 500+ page book turned into a searchable, illustrated guide covering all numbered results, examples and proofs, with MathJax, dark mode and offline support.
---

# PDF/书籍 → 单页交互教程

目标产物：**一个 HTML 文件**。双击可读、断网可读；有目录、搜索、定理盒、证明折叠、速查表、暗色模式、阅读进度。内容不是“读后感”，而是**按原书编号覆盖全部结果**的学习版：核心定理给陈述 + 直觉 + 证明思路，全部编号结果用每章速查表兜底。

本 skill 附带一套已验证的流水线与可直接复用的 UI：

- `scripts/extract_book.py`：PDF → 带页码的全文 + 按章拆分 + 结果清单
- `scripts/build_tutorial.py`：`shell + sections` → 单文件（内联 CSS/JS/MathJax）
- `scripts/escape_math.py`：修复 `$...$` 里的 `<`/`>`/`&`（最容易毁掉整页的坑）
- `assets/shell.html`、`theme.css`、`app.js`：生产级页面骨架
- `references/pipeline.md`：分阶段细节、子代理提示词、内容配比
- `references/qa-checklist.md`：浏览器自动检查 + 人工核对清单
- `references/design-system.md`：版式、定理盒类型、交互约定

---

## 0. 先定“覆盖契约”

不要承诺“所有证明都展开”——599 页的书不可能。用三层覆盖：

| 层级 | 内容 | 呈现 |
|---|---|---|
| T0 核心 | 每条主线 5–10 个定理 | 完整陈述 + 直觉 + 证明思路（可折叠） |
| T1 全量 | 所有 Definition/Theorem/Lemma/Example | 每章末尾“全章结果速查表”逐条一行 |
| T2 例子 | 书中 Example、反例、应用 | 独立盒子 + 计算；反例进“反例博物馆” |

再补：证明技术工具箱、定理依赖图、术语表、20 道自测、一页纸总结。这样既不会写成 800 页，也不会漏知识点。

**不要中途问用户**。缺信息就按“教材化、可读优先”自行决定，最后说明取舍。

---

## 1. 提取与侦察

```bash
python3 -m pip install --user pymupdf
python3 <skill>/scripts/extract_book.py "/path/book.pdf" work/
```

看 `work/meta.json`：

- `pages`、`toc_entries`、`chapters`
- `numbered_results_total`（决定“766 条”这类统计口径）
- `low_text_pages`：若很多页几乎无字，先 OCR：
  ```bash
  brew install ocrmypdf tesseract
  ocrmypdf --deskew --clean book.pdf book-ocr.pdf
  ```

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

把章节文本分给 6–8 个子代理，每个 1–2 章。提示词必须包含：

- 读 `work/chapters/N.txt`
- **覆盖每一个编号结果**，保留原编号
- PDF 公式乱码，按数学知识重建，但**不得编造定理内容**
- 每条：精确 LaTeX 陈述 + 1–3 句中文直觉 + 证明思路（有教学价值时）
- 例子要给计算；反例要写“打破了什么”
- 结尾写“本章脉络”“常见误区”
- 目标 5000–10000 汉字，输出 `notes/chNN.md`

完整模板见 `references/pipeline.md`。子代理跑的时候，你可以同时写 UI/骨架，不要等。

---

## 4. 写章节

每章固定节奏（读者会形成预期）：

1. `lede`：这一章解决什么问题，一句话。
2. 章节卡：本章覆盖范围 + 标签。
3. `mapchips`：5–8 个关键词。
4. 3–6 个 T0 深潜：定义 → 定理 → 直觉盒 → 证明思路折叠。
5. 1–2 个可手算例子 / 反例。
6. “全章结果速查表”：**每个编号一行**。
7. “常见误区”盒：3–5 条。

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

启动 2 个审计子代理：一个查第 1–8 章，一个查 9–15 章。让它们**只列具体错误**：

- 编号是否存在、内容是否对得上
- 公式/指数/常数/假设（\(C^3\) vs \(C^2\)、\(p>n\) vs \(p<n\)、\(n=2\) 例外）
- 是否把“未解决”说成“失败”，把“凸包”说成“原函数”
- 是否漏掉重要编号结果

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

不要把“学习版”说成“原书全文翻译”；准确说明：**核心定理详细讲，全部编号结果可查，证明给思路而非逐字重写**。
