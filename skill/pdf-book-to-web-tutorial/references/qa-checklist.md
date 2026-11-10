# QA checklist

Run all checks on a **fresh cache-busted load** (`?v=N`). Fix order: math → anchors → overflow → dark mode → content.

## 1. Automated page health

Open DevTools (or the browser tool) and evaluate:

```js
(() => {
  const ids = [...document.querySelectorAll('[id]')].map(e => e.id);
  const dup = [...new Set(ids.filter((x,i,a) => a.indexOf(x) !== i))];
  const badLinks = [...document.querySelectorAll('a[href^="#"]')]
    .map(a => a.getAttribute('href'))
    .filter(h => h !== '#' && !document.querySelector(h));
  const raw = [...document.querySelectorAll('p,li,td,.thm-title')]
    .filter(e => /\$\$|\\[a-z]+\{/.test(e.textContent) && !e.querySelector('mjx-container'))
    .map(e => e.textContent.slice(0, 80));
  return {
    sections: document.querySelectorAll('section[id]').length,
    theorems: document.querySelectorAll('.thm').length,
    mjx: document.querySelectorAll('mjx-container').length,
    merror: document.querySelectorAll('merror').length,
    rawMath: raw,
    duplicateIds: dup,
    brokenAnchors: badLinks,
    bodyWidth: document.body.scrollWidth,
    viewport: innerWidth
  };
})()
```

Expected:

- `merror === 0`
- `rawMath.length === 0`
- `duplicateIds.length === 0`
- `brokenAnchors.length === 0`
- `bodyWidth === viewport` (or at most +1 for scrollbar rounding)
- `mjx > 500` for a 20+ section book

Console: **0 uncaught errors**.

## 2. Math escaping

The most common silent failure is a formula containing `<` followed by a letter. Verify:

```bash
grep -n "&amp;lt;\|&amp;gt;\|&amp;amp;" dist/Tutorial.html   # must be empty
```

Also spot-check formulas with `<`, `>`, `\begin{cases}`, `\Subset`, `\lesssim`, `\asymp`, `\gtrsim`:

```js
// count display math that failed to become mjx-container
[...document.querySelectorAll('p')].filter(p => p.textContent.includes('$$')).length
```

Expected 0.

If a formula is missing after an inequality, run:

```bash
python3 scripts/escape_math.py src/sections/*.html
python3 scripts/build_tutorial.py ...
```

## 3. Navigation and scroll

For every nav link:

```js
[...document.querySelectorAll('.nav-link')].map(a => {
  const el = document.querySelector(a.getAttribute('href'));
  return [a.textContent.trim(), !!el];
})
```

Expected all `true`.

Click a middle link (e.g. `#ch5`) and check:

```js
({
  hash: location.hash,
  top: document.querySelector('#ch5').getBoundingClientRect().top,
  active: [...document.querySelectorAll('.nav-link.active')].map(x => x.textContent.trim()),
  crumb: document.querySelector('#crumb').textContent,
  pct: document.querySelector('#pct').textContent
})
```

Expected: `top` between 60 and 220; active link/crumb correspond to that chapter; `pct` updates.

If it lands at the bottom or the wrong chapter, the MathJax hash fix is missing. The shell already contains it; keep it after the MathJax script.

## 4. Search

1. click the search box → panel opens
2. type `Harnack`, `截面`, `Green 函数`
3. expect 5–18 results; first result should be title-relevant
4. click a result → scrolls to that section and flashes it
5. `Esc` closes the panel

If results are 0 after typing, the input event was not fired (some automation tools set `.value` directly). In real typing it works; for automation dispatch `input`.

## 5. Proof toggle / theme / font

```js
document.querySelector('#proofBtn').click();
[...document.querySelectorAll('details.proof')].every(d => d.open) // true
document.querySelector('#proofBtn').click();
[...document.querySelectorAll('details.proof')].some(d => d.open)  // false

document.querySelector('#themeBtn').click(); // dark
document.documentElement.dataset.theme // "night"
document.querySelector('#fontPlus').click(); // --fs grows, max 21
```

Reload → theme and font size persist (localStorage guarded by try/catch).

## 6. Mobile 390px

Headless Chrome has a minimum layout width around 500px. Do **not** trust `--window-size=390`; use a 390px iframe:

```html
<!doctype html><html><body style="margin:0;background:#888">
<iframe src="/dist/Tutorial.html" style="width:390px;height:844px;border:0;display:block;margin:0 auto"></iframe>
</body></html>
```

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --hide-scrollbars --window-size=500,844 \
  --screenshot=/tmp/mobile.png --virtual-time-budget=10000 \
  "http://127.0.0.1:8765/mobile-test.html"
```

Check:

- no horizontal cut-off
- hero title/subtitle wraps
- menu button opens drawer; tapping the dim area closes it
- tables scroll inside their wrapper, not the page
- MathJax display formulas scroll horizontally inside `mjx-container`

## 7. Offline / file://

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --window-size=1200,900 \
  --screenshot=/tmp/offline.png --virtual-time-budget=10000 \
  "file:///absolute/path/dist/Tutorial.html"
```

The page must render with the network off. If formulas show raw `$`, MathJax was not inlined (`--dev` build).

## 8. Dark mode diagrams

- hero SVG and every `<figure>` must sit on a light plate (`background: var(--plate)`) or use colors that work on dark
- tables: `th` background and `td` text readable
- theorem boxes: definition teal, theorem red, lemma gold, example violet
- no hard-coded `#f6dede` warning background in dark mode (use a theme variable)

## 9. Content spot-check

Pick 10 random theorem boxes and compare against `work/chapters`:

- number exists
- hypotheses complete
- inequality direction correct
- exponent/constant correct
- no “proof” that actually proves a different statement
- examples have concrete numbers

Run the two audit subagents from `references/pipeline.md` before delivery.

## 10. Coverage gate (must)

```bash
python3 scripts/check_coverage.py \
  --work work/<book> --html dist/<book>-Tutorial.html \
  --report coverage-<book>.md
```

Read the report, not just the exit code:

- **Missing TOC entries**: every chapter/section must appear. Add them, don't rename the report.
- **Weak chapters**: open the source chapter and compare its section list with the tutorial. A low term recall usually means whole subsections are missing.
- **Top terms not found**: technical terms may be translated; check whether the concept is present under a Chinese name before adding the English term.
- **Length ratio**: reported only. A very low ratio is a warning, not an automatic failure; a long tutorial can still omit details.

Default gates: 75% TOC / 70% chapter / 30% terms. `--strict` = 85/90/60. `--warn-only` is for exploration, not delivery.

Then do a semantic audit: the script cannot detect a section that is present but wrong. Ask an audit agent to compare each chapter's TOC and key claims.

## 11. Final smoke test

- open at top: hero visible, sidebar active “导读”, 0%
- click last chapter: scrolls, active link correct, progress ~90%+
- print preview: sidebar/topbar hidden, content readable
- file size reasonable (1.5–3 MB with inline MathJax)
- no unresolved `{{PLACEHOLDER}}`
