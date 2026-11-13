# 新增论文解读

论文和书共用同一套视觉与交互（目录、搜索、暗色、书签、高亮、阅读进度），但输入与结构不同：

- 输入：本地 PDF，或论文 URL（目前支持 arXiv 与直链 `.pdf`）
- 元数据：自动读取 arXiv API / PDF 元数据 / 首页大字号标题
- 分节：优先用 PDF outline；没有 outline 时按标题启发式切分
- 存储：`papers/<英文短名>.html`，索引 `papers.json` → `papers/index.html`

## 1. 查重（先做）

```bash
# 本地 PDF
python3 tools/check_duplicate.py ~/Downloads/paper.pdf

# 只有 arXiv 号
python3 tools/check_duplicate.py --arxiv 1706.03762
```

`papers.json` 里的 `arxiv` 字段用于精确命中；标题/作者相似度作为兜底。
退出码 **0** = 新论文，可以继续；**1** = 已存在或可能重复。

## 2. 提取

```bash
# arXiv 摘要页、PDF 链接，或本地文件
python3 skill/pdf-book-to-web-tutorial/scripts/extract_paper.py \
  https://arxiv.org/abs/1706.03762 \
  work/papers/attention
```

输出：

```
work/papers/attention/
  source.pdf        # URL 输入时下载的副本
  meta.json         # kind=paper, title, authors, year, venue, arxiv_id, doi, abstract
  full.txt          # 带页码的全文
  toc.json          # outline 或启发式标题
  abstract.txt
  refs.txt
  sections/NN.txt   # 按节切分
```

检查 `meta.json` 的 `title/authors/year` 是否被正确识别；PDF 首页排版特殊时，标题可能带进页眉，需要手工修正后再写教程。

## 3. 写 sections

论文通常 10–13 个 section 就够，但**技术内容不能省**：

1. `00-hero`：标题、作者、会议、一句话结论、关键数字
2. `01-tldr`：问题、贡献、结果表
3. `02-problem`：背景与已有方法的缺陷
4. `03-method`：核心公式、符号解释、算法步骤
5. `04-architecture`：整体结构、数据流、超参数
6. `05-training`：数据、优化器、schedule、正则
7. `06-results`：主结果、消融、对照
8. `07-analysis`：复杂度、可视化、为什么有效
9. `08-limitations`：假设、失败模式、后续工作
10. `09-reproduction`：数据/代码/算力/复现清单
11. `10-glossary` + `99-summary`：术语、自测题

要求：

- 公式保留，首次出现解释每个符号
- 所有关键数字（BLEU、维度、层数、GPU、时长、学习率）都写进正文或速查表
- 区分“论文声称”与“后来验证”
- 中文讲解，术语首次出现加英文括注
- 不要逐字翻译摘要

## 4. 构建

```bash
python3 skill/pdf-book-to-web-tutorial/scripts/build_tutorial.py \
  --sections work/papers/attention/src/sections \
  --out papers/Attention-Is-All-You-Need.html \
  --title "Attention Is All You Need · 论文解读" \
  --book-title "Attention Is All You Need" \
  --book-subtitle "Transformer · NeurIPS 2017 · arXiv 1706.03762" \
  --short-title "Attention" \
  --description "《Attention Is All You Need》中文论文解读" \
  --stats "15 页 · 12 个 section"
```

## 5. 覆盖率与 QA

```bash
python3 skill/pdf-book-to-web-tutorial/scripts/check_coverage.py \
  --work work/papers/attention \
  --html papers/Attention-Is-All-You-Need.html

python3 tools/qa_tutorial.py papers/Attention-Is-All-You-Need.html
```

论文的 outline 往往很细（22 节），章节召回可能被短小节拉低。先补内容；确实因切分过细导致误判时，再加 `--min-chapter 0.5`，并在提交说明里写清原因。

## 6. 入库

`papers.json` 一条记录：

```json
{
  "file": "Attention-Is-All-You-Need.html",
  "title": "Attention Is All You Need",
  "authors": "Ashish Vaswani et al.",
  "venue": "NeurIPS 2017",
  "year": 2017,
  "arxiv": "1706.03762",
  "doi": "",
  "tags": ["transformer", "NLP"],
  "summary": "用纯注意力替代循环与卷积，提出 Transformer。",
  "source_url": "https://arxiv.org/abs/1706.03762",
  "pages": 15,
  "sections": 22
}
```

然后：

```bash
python3 tools/build_papers_index.py     # 重建 papers/index.html
python3 tools/build_index.py            # 刷新全站导航（含论文）
python3 tools/qa_all.py                 # 书 + 论文一起检查
```

`build_index.py` 会自动调用 `enhance_books.py`，给论文注入「上一篇 / 书库 / 下一篇」、阅读进度、书签和高亮；论文的“书库”指回 `papers/index.html`。站点结构是：`/index.html` 首页 → `/books/index.html` 与 `/papers/index.html` 两个独立索引。

## 7. 提交

```bash
git add papers/Attention-Is-All-You-Need.html papers.json papers/index.html \
        README.md index.html
git commit -m "Add paper note: Attention Is All You Need"
git push
```

CI 会检查 `papers.json` 与 `papers/` 一致、每篇都有导航、静态 QA 通过、生成物没有过期。

## 与书籍流程的区别

| 项 | 书 | 论文 |
|---|---|---|
| 输入 | PDF / EPUB | PDF / arXiv URL |
| 元数据 | 用户填写 | arXiv API / PDF 自动 |
| 分节 | 章节文件 `chapters/` | `sections/`（outline 或启发式） |
| 篇幅 | 15–30 个 section | 10–13 个 section |
| 重点 | 全书覆盖 | 方法、实验、局限、复现 |
| 索引 | `catalog.json` | `papers.json` |
