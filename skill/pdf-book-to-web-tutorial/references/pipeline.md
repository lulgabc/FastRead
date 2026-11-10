# Pipeline details

## Phase 0 — Scope and deliverable

Default deliverable:

- one `dist/<Book>-Tutorial.html`
- Chinese exposition
- covers every chapter, section, numbered result, example, algorithm/command and code block
- statements are complete; proofs are proof ideas/skeletons unless the user asks for full proofs
- ~30–80k Chinese characters for a 500–700 page book; **length follows content, never a cap**
- 20–40 sections, several hours of reading

Decision rules:

- If the book has multiple parts, mirror them in the navigation.
- If it is a research monograph, do **not** try to prove every theorem. Prioritize: definitions, main theorems, counterexamples, regularity thresholds, applications.
- If it is an undergraduate text, expand computations and exercises instead of literature notes.

## Phase 1 — Extraction

```bash
python3 -m pip install --user pymupdf
python3 scripts/extract_book.py "book.pdf" work/
python3 scripts/extract_book.py "book.epub" work/
```

Check `work/meta.json`:

- `low_text_pages`: if > 5% of pages, OCR first (PDF only).
- `documents`: EPUB XHTML document count; `pages` is an estimate from characters.
- `images`: EPUB/PDF images seen; formulas that are images need manual inspection.
- `numbered_results_total`: use this number in the page stats (and say “编号结果”, not “定理”).
- `chapters`: if chapter detection failed (no TOC), fall back to 50-page chunks and split manually by headings.

Read in this order:

1. TOC
2. Preface / plan of the book
3. Notation
4. First page of every chapter
5. Notes / Problems of each chapter (for pitfalls and open problems)

Keep `work/full.txt` with page markers. It is the source of truth for page ranges and quotes.

## Phase 2 — Blueprint

Write a short `plan.md` before writing HTML:

```markdown
# Plan
- Stats: 15 chapters, 766 numbered results, 40+ examples
- T0 chains:
  1. measure → max principle → comparison → Perron
  2. sections → localization → C^{1,a} → W^{2,1+e} → C^{2,a}
  3. boundary localization → boundary sections → boundary C^{2,a}
  4. linearized: Harnack → boundary → Green → divergence form
- Sections: 00 intro, 01 notation, 02 applications, ch2..ch15, A toolbox, B counterexamples, C map, D exercises, E glossary, F summary
- Nav groups: 开始 / Part I / Part II / Part III / 复盘
- Depth: every section covered; each chapter has multiple T0 boxes + per-section detail + cheat table + pitfalls
- Coverage target: no section omitted; length follows content, not the other way around
```

Depth budget per chapter (complete mode):

| Chapter type | Coverage | T0 boxes | Examples |
|---|---|---|---|
| Preliminaries | every section | 6–12 | all worked examples |
| Core theory | every section + numbered result | 8–15 | all examples/counterexamples |
| Applications | every section | 4–10 | all cases/commands |
| Advanced/tools | every section | 5–12 | all code/config examples |

Cheat tables are review indexes, not a substitute for prose.

## Phase 3 — Parallel notes

'Split chapters into jobs. Complete mode: **one job = one chapter** (split a very long chapter into 2–3 jobs). A chapter note usually runs 3k–10k Chinese characters; long chapters can exceed that. Do not cap length.

Prompt template:

```text
You are preparing source material for a Chinese-language tutorial web page about
the book "<TITLE>" by <AUTHOR>.

Read "/.../work/chapters/<N>.txt" (Chapter <N>). PDF extraction mangles math;
reconstruct correct formulas using your knowledge, but do NOT invent theorem
content. Cover EVERY numbered Definition/Lemma/Theorem/Proposition/Example/
Remark in the chapter.

Write detailed Markdown notes to "/.../notes/ch<N>.md":
- Organize by the book's section numbers and titles.
- For each item: exact number/name, precise LaTeX statement, 1-3 sentences of
  plain-Chinese explanation, and the proof idea when instructive.
- Include all examples and counterexamples with concrete computations.
- Add a short "本章脉络" summary and a "常见误区" list.
- Use LaTeX with $...$ and $$...$$.
- Do not omit sections, examples, parameters, code blocks, or figures.
- Do not cap length. Typical chapter: 3k–10k Chinese characters; long chapters 10k+.
Return only a one-line confirmation.
Return only a one-line confirmation.
```

Run them with `background: true` if the tool supports it, then build the UI shell while they work.

Quality gates for notes:

- every numbered item appears exactly once
- no “Theorem X (statement omitted)”
- examples have numbers, not just names
- “common mistakes” are specific (direction of inequality, missing hypothesis, dimension exception)

## Phase 4 — Section writing

File naming:

```
src/sections/00-hero.html
src/sections/01-intro.html
src/sections/02-notation.html
src/sections/03-applications.html
src/sections/04-ch2.html
...
src/sections/18-appendix-a.html
src/sections/19-appendix-b.html
...
```

Each chapter follows the rhythm in `SKILL.md`. Use the CSS classes from `theme.css`:

- `<div class="thm def">` definition (teal)
- `<div class="thm theorem">` theorem (red)
- `<div class="thm lem">` lemma (gold)
- `<div class="thm ex">` example (violet)
- `<div class="thm rem">` remark (blue)
- `<div class="thm warn">` pitfalls (red warning)
- `<div class="intuition">` intuition box
- `<details class="proof"><summary>证明思路</summary>...</details>`
- `<div class="table-wrap cheat">` full result table
- `<figure><svg>...` diagram + `<figcaption>`

Theorem box skeleton:

```html
<div class="thm theorem">
  <div class="thm-head">
    <span class="thm-kind">Theorem</span>
    <span class="thm-title">5.11 Caffarelli 局部化定理</span>
    <span class="thm-id">§5.2</span>
  </div>
  <div class="thm-body">
    <p>...</p>
    $$...$$
  </div>
</div>
```

Proof skeleton:

```html
<details class="proof">
  <summary>证明思路：三步紧性 + 平衡性矛盾</summary>
  <div class="proof-body">
    <p>...</p>
  </div>
</details>
```

Cheat table skeleton:

```html
<div class="table-wrap cheat">
  <table>
    <thead><tr><th>编号</th><th>一句话内容</th></tr></thead>
    <tbody>
      <tr><td class="id">5.1–5.4</td><td>截面定义；可微记法；缩放包含；测度加倍</td></tr>
    </tbody>
  </table>
</div>
```

Content rules:

- use `\operatorname{...}` for multi-letter operators, `\,` before differentials
- avoid `\text{中文}`; move Chinese outside math
- display math should be a standalone line (`$$...$$`), not inside a `<p>` with other text if it can be avoided
- if a formula is longer than the content width, split it with `\begin{aligned}` or allow horizontal scroll
- every table gets a `<thead>`
- every image/SVG gets a caption explaining **what to look at**, not just a label

## Phase 5 — Build

```bash
python3 scripts/build_tutorial.py \
  --sections src/sections --out dist/Tutorial.html \
  --title "..." --book-title "..." --book-subtitle "..." \
  --short-title "..." --stats "..." --footer-coverage "..."
```

The script:

1. reads sections in filename order
2. escapes math (`<`, `>`, `&`) outside `<script>/<style>`
3. generates nav from sections if `src/nav.html` is missing
4. inlines `theme.css`, `app.js`, MathJax `tex-svg.js`
5. appends the MathJax config and a post-typeset hash-fix script
6. warns on unresolved `{{PLACEHOLDERS}}`

Dev loop:

```bash
# fast build without 2 MB MathJax
python3 scripts/build_tutorial.py ... --dev
python3 -m http.server 8765
# open http://127.0.0.1:8765/dist/Tutorial.html
```

Use a cache-busting query (`?v=13`) during iteration.

## Phase 6 — Coverage gate

Build first, then run the detector from the extracted source:

```bash
python3 scripts/check_coverage.py \
  --work work/<book> --html dist/<book>-Tutorial.html \
  --report coverage-<book>.md
```

It reports:

- TOC entries that never appear in the tutorial
- per-chapter salient-term recall
- global technical-term recall
- source/tutorial length ratio (reported, never gated)

Default gates: TOC ≥75%, chapter recall ≥70%, term recall ≥30%. `--strict` uses 85/90/60. If it fails, do **not** edit the report; add the missing sections/details and rerun.

Then run a semantic audit: even if the numbers pass, read the missing/weak list and ask an agent to compare each chapter's TOC/section list against the tutorial. The detector catches omissions, not wrong paraphrases.

## Phase 7 — QA

Run `references/qa-checklist.md`. Fix in this order:

1. raw math / MathJax errors (page is visibly broken)
2. broken anchors / no scroll
3. overflow / mobile
4. dark mode contrast
5. content errors

## Phase 8 — Fact-check

Two audit prompts:

```text
You are a meticulous mathematical fact-checker. The file ".../dist/Tutorial.html"
is a Chinese tutorial based on "<BOOK>". Source chapter texts: work/chapters/*.txt;
notes: notes/*.md.

Audit ONLY Chapters <a>–<b>. Check:
1. Every explicitly cited theorem/lemma/example number exists and is described
   with the correct content.
2. Formulas, exponents, constants, hypotheses (e.g. C^3 vs C^2, dimension
   restrictions, n=2 exceptions) are correct.
3. No fabricated theorem, misattributed result, or reversed inequality.
4. Important knowledge points entirely missing (ignore Problems/bibliography).
Do NOT comment on style or HTML. Do NOT edit files. Output a concise list:
location, what is wrong, correct statement with source theorem number.
```

Apply every concrete correction, then rebuild and rerun QA.

## Phase 9 — Delivery

- state the single-file path and size
- state what is covered and what is not (“all numbered results indexed; core theorems get proof ideas”)
- mention offline/self-contained
- keep `src/` and `scripts/` for future edits
