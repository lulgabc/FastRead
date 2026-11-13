# 新增一本书的流程

FastRead 只保存生成的 HTML 教程，不保存 PDF。新书转换分两条路：让 agent 跑，或手动跑。

转换默认是**完整模式**：章节、小节、编号结果、例子、代码、参数都要保留；**不设字数上限**，长度服从内容。

---

## 0. 准备

把新 PDF 或 EPUB 放在仓库外的暂存目录，例如：

```bash
mkdir -p ~/Downloads/FastRead-inbox
# 把新书 PDF/EPUB 放进去
```

不要放进 `FastRead/`，避免 PDF 进入 Git。仓库的 `.gitignore` 已忽略 `*.pdf`、`inbox/` 和 `work/`。

---

## 1. 最省事：直接对 agent 说

在 OpenCode 里发：

> 用 `pdf-book-to-web-tutorial` 把 `~/Downloads/FastRead-inbox/` 下的所有 PDF 做成单页教程。
> 每本输出到 `~/Documents/Default Project/FastRead/books/<英文短名>-Tutorial.html`；
> 完整覆盖原书章节/小节/例子/代码，不设字数上限；
> 更新 `catalog.json`、`README.md`、`index.html`；
> 跑 `check_coverage.py` 和 `qa_tutorial.py`；
> 最后提交 Git 并 push。

如果要控制得更细，加一句：

> 先给我书目、页数、分类和输出文件名，确认后再写。

Agent 会按 skill 的流水线执行：提取 → 蓝图 → 章节笔记 → 写 sections → 构建 → 覆盖率检测 → QA → 更新索引 → 提交。

---

## 2. 手动流程（完全可控）

### 2.0 查重（先做）

```bash
python3 tools/check_duplicate.py ~/Downloads/FastRead-inbox/某本书.pdf
# 也可以只给标题/作者
python3 tools/check_duplicate.py --title "Mathematical Logic" --author "Ebbinghaus"
```

- 退出码 **0**：没找到，可以继续转换
- 退出码 **1**：已存在或可能重复，先人工确认，不要直接开工

匹配使用 PDF/EPUB 元数据与文件名，比较标题词元、序列相似度和作者姓氏；输出会列出最接近的 3 本馆藏及分数。阈值默认 `0.72`，可用 `--threshold` 调整。

### 2.1 提取（PDF/EPUB）

```bash
cd "$HOME/Documents/Default Project/FastRead"
python3 skill/pdf-book-to-web-tutorial/scripts/extract_book.py \
  ~/Downloads/FastRead-inbox/某本书.pdf \
  work/某本书

# EPUB 用同样的命令，只把 .pdf 换成 .epub
```

查看：

```bash
cat work/某本书/meta.json
```

确认页数/文档数、章节数、`numbered_results_total`；PDF 若 `low_text_pages` 很多，先 OCR。EPUB 若 `images` 很多，公式/图可能是图片，需要回看原书。

### 2.2 写 sections

在 `work/某本书/src/sections/` 下写：

```
00-hero.html
01-ch1.html
02-ch2.html
...
99-summary.html
```

每节使用 skill 的类：`chapter`、`lede`、`chap-intro`、`thm def/theorem/lem/ex/rem/warn`、`intuition`、`table-wrap cheat`、`cards`。

详见：

- `skill/pdf-book-to-web-tutorial/SKILL.md`
- `skill/pdf-book-to-web-tutorial/references/pipeline.md`
- `skill/pdf-book-to-web-tutorial/references/design-system.md`

### 2.3 构建

```bash
python3 skill/pdf-book-to-web-tutorial/scripts/build_tutorial.py \
  --sections work/某本书/src/sections \
  --out books/Some-Book-Tutorial.html \
  --title "书名 · 交互教程" \
  --book-title "书名" \
  --book-subtitle "副标题" \
  --short-title "短书名" \
  --stats "<b>12</b> 章 · <b>500</b> 页" \
  --footer-coverage "12 章 · 500 页 · 核心概念 + 例子 + 速查表"
```

默认内联 MathJax，产物约 2.2 MB，可离线打开。不要加 `--dev` 交付。

### 2.4 覆盖率检测（必须）

```bash
python3 skill/pdf-book-to-web-tutorial/scripts/check_coverage.py \
  --work work/某本书 --html books/Some-Book-Tutorial.html \
  --report work/某本书/coverage-report.md
```

默认门槛：TOC 覆盖 ≥ 75%、章节术语召回 ≥ 70%、全局术语召回 ≥ 30%。报告里的 missing TOC entries / weak chapters 是工作清单：补内容后重跑，不要改报告。

### 2.5 QA

```bash
python3 tools/qa_tutorial.py books/Some-Book-Tutorial.html --render
```

应满足：

- `merror = 0`
- 无 raw `$$`
- 无重复 ID
- 无断链
- 无 `{{PLACEHOLDER}}`
- 控制台 0 错误
- 手机 390px 无横向溢出（详细检查见 skill 的 `references/qa-checklist.md`）

### 2.6 更新索引

在 `catalog.json` 末尾加一条：

```json
{
  "file": "Some-Book-Tutorial.html",
  "title": "Some Book",
  "subtitle": "A Subtitle",
  "author": "Author Name",
  "pages": 500,
  "category": "数学 · 分析与代数",
  "batch": "Books3"
}
```

可以直接使用现有九类之一；也可以用新分类——它会自动追加到索引末尾。想控制新分类的位置，把它加进 `tools/catalog_lib.py` 的 `ORDER`。

- 数学 · 分析与代数
- 优化 · 金融 · 概率
- 逻辑 · 形式方法 · 理论计算机
- 机器学习 · 语言模型
- 系统 · 数据 · 网络
- 安全 · 二进制 · 逆向
- 数值计算 · 工程
- 认知科学 · 哲学
- 经济学

然后：

```bash
python3 tools/build_index.py
```

会重建 `README.md`、首页 `index.html`、书籍索引 `books/index.html`，并给**所有**书刷新「上一本 / 书库 / 下一本」导航、阅读进度、书签与高亮脚本。新增一本书不需要手动改其它书；顺序由 `catalog.json` 的分类 + 标题决定。

提交前先校验目录与文件是否一致：

```bash
python3 tools/build_index.py --check
```

### 2.7 提交

```bash
git add books/Some-Book-Tutorial.html catalog.json README.md index.html
git commit -m "Add Some Book tutorial"
git push
```

如果开了 GitHub Pages，push 后会自动更新；否则本地打开 `index.html` 即可。

---

## 3. 命名约定

- 文件名：`Title-Words-Tutorial.html`，ASCII、连字符、无空格。
- 例：`Fourier-Analysis-Tutorial.html`、`Book-of-PF-Tutorial.html`。
- 一本书一个文件；不要把多本书合并。
- 配套的 `work/` 目录不提交，留在本地用于以后修改。

---

## 4. 常见坑

1. **公式里的 `<`**：`$a<b$` 必须写成 `$a&lt;b$`。`build_tutorial.py` 会自动处理，但手改 HTML 时注意。
2. **代码块里的 `<`**：用 `&lt;`，构建脚本会保护 `<pre><code>`。
3. **类名**：定理盒用 `thm theorem`，不要 `thm thm`（会和 `thm def` 冲突）。
4. **MathJax 异步 + 锚点**：构建脚本已内置 hash 修复，不要删。
5. **`\boldsymbol`**：skill 已把它映射到 `\mathbf`，避免离线时 MathJax 去 CDN 拉扩展。
6. **不要提交 PDF**：仓库只存 HTML。
7. **页面体积**：每本约 2.2 MB，43 本已约 95 MB；新增前确认磁盘和 Git 体积可接受。
