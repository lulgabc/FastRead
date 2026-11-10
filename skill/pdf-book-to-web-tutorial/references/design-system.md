# Design system

A warm-paper academic look: cream background, ink text, vermilion accent, teal for definitions, gold for lemmas. It is designed for long reading, not for a marketing landing page.

## Layout

- Sidebar 284px, dark ink, fixed; main content max ~940px.
- Topbar 62px, sticky, translucent; search + proof toggle + font + theme.
- Reading column ~820px, serif Chinese body 17px, line-height 1.88.
- Sections use `scroll-margin-top: 84px`.
- On ≤900px: sidebar becomes a drawer; menu button appears; hero becomes one column.
- On ≤620px: 17px outer padding, smaller hero, search hidden.

CSS variables (`theme.css`):

```css
--paper, --paper2, --paper3   /* backgrounds */
--ink, --ink2, --muted        /* text */
--line, --line2               /* borders */
--accent (red), --teal, --gold, --violet, --blue
--*-soft                      /* tinted backgrounds */
--plate                       /* light plate behind diagrams, fixed in both themes */
--sidebar: 284px; --read: 820px; --fs: 17px;
```

Night mode is `html[data-theme="night"]`; all colors must use variables, not hard-coded pastels.

## Components

### Hero

- huge serif title `clamp(38px, 5.4vw, 72px)`
- English italic subtitle
- one-sentence “what this is” with a highlighted phrase
- two actions: start reading / one-page summary
- 3–4 stats: chapters, results, examples, equations
- one inline SVG diagram on a light plate; caption below, not absolute

### Chapter opening

```html
<section id="ch5" class="chapter">
  <div class="wrap">
    <div class="sec-label">Part II · Chapter 5</div>
    <h2><span class="num">5</span>截面与内部一阶导数估计</h2>
    <p class="lede">...</p>
    <div class="chap-intro"><p>...</p><span class="tag">§5.1 – §5.9</span></div>
    <div class="mapchips"><span class="chip">截面</span>...</div>
```

### Theorem boxes

| class | use | color |
|---|---|---|
| `thm def` | definition | teal |
| `thm theorem` | theorem | red |
| `thm lem` | lemma/proposition | gold |
| `thm ex` | example | violet |
| `thm rem` | remark | blue |
| `thm warn` | pitfalls | red warning |

Never use `class="thm thm"`: `.thm.thm` also matches `class="thm def"` and overrides the type color. Use `thm theorem`.

Head:

```html
<div class="thm-head">
  <span class="thm-kind">Theorem</span>
  <span class="thm-title">5.11 Caffarelli 局部化定理</span>
  <span class="thm-id">§5.2</span>
</div>
```

### Proof

```html
<details class="proof">
  <summary>证明思路：...</summary>
  <div class="proof-body">...</div>
</details>
```

Collapsed by default. The topbar “证明” button toggles all.

### Intuition

```html
<div class="intuition">
  <div class="ih">◆ 直觉：为什么是行列式？</div>
  <p>...</p>
</div>
```

Use for “why this is true”, “what to picture”, “what would fail without the hypothesis”.

### Cheat table

`<div class="table-wrap cheat">` + `<table>` with `<thead>`. One row per numbered item, or a range with a one-line summary. This is how you claim full coverage without writing 700 proof boxes.

### Figure

Inline SVG, no external files. Give it `role="img"` and `aria-label`. Caption says what to look at. Put a light plate behind fixed-color diagrams:

```css
figure svg { background: var(--plate); border-radius: 10px; padding: 6px; }
```

SVG `<text>` must use plain Unicode, never `$...$`.

### Quiz

```html
<div class="quiz" data-quiz>
  <div class="quiz-q"><span class="qmark">Q1</span>...</div>
  <div class="quiz-opts">
    <button data-correct="false">...</button>
    <button data-correct="true">...</button>
  </div>
  <div class="quiz-exp">...</div>
</div>
```

One correct option; click disables all and reveals explanation.

## Interaction behavior

- Scroll: debounce 55ms, update progress bar/ring, active nav, crumb.
- Search: index all `section[id]` + `.thm-title`; rank title matches first; limit 18; snippet ±80 chars; `mark` the query.
- Hash: after `MathJax.startup.promise`, re-scroll to `location.hash`; also on `hashchange`, because MathJax changes layout.
- Theme/font: `localStorage` behind try/catch (file:// can throw).
- Mobile drawer: toggle `body.nav-open`; clicking outside sidebar/menu closes.
- Reveal animation: only `.chapter`, `IntersectionObserver`, respect `prefers-reduced-motion`.
- Print: hide sidebar/topbar/fabs/ring; show content; page-break before chapters.

## Typography rules

- Chinese body: Songti/Noto Serif; UI: PingFang/Noto Sans.
- Mixed Chinese/English: keep a space between them; use `–` for Monge–Ampère, not a hyphen.
- Theorem titles bold; IDs small, muted, right-aligned.
- Do not justify Chinese text; left-aligned with 1.8+ line-height.
- Display math centered with 1.1em vertical margin; allow horizontal scroll for long formulas.

## Color usage

- Red = theorem / important result / pitfall.
- Teal = definition / construction / positive.
- Gold = lemma / technical tool.
- Violet = example / counterexample.
- Blue = remark / context.
- Never use color as the only distinction; the `thm-kind` label carries the meaning.
