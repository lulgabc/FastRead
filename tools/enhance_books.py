#!/usr/bin/env python3
"""Inject library navigation and reading-position memory into built tutorials.

Every tutorial is a standalone HTML file, so the navigation and the progress
script have to live inside it. This script edits them in place:

  * prev / next / index links, computed from catalog.json display order
  * a small script that remembers the reading position per book
    (localStorage key ``fastread:pos:<file>``) and the last opened book
    (``fastread:last``), which index.html uses for its "continue reading" strip

It is idempotent: each block is delimited by markers and replaced, so running
it after adding a book only rewrites what changed. `build_index.py` calls it
automatically; use ``--skip-books`` there if you really want to avoid it.

Usage:
    python3 tools/enhance_books.py [--check]
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_lib as C  # noqa: E402

STYLE_START = "<!-- fastread:style:start -->"
STYLE_END = "<!-- fastread:style:end -->"
NAV_START = "<!-- fastread:nav:start -->"
NAV_END = "<!-- fastread:nav:end -->"
PROG_START = "<!-- fastread:progress:start -->"
PROG_END = "<!-- fastread:progress:end -->"

STYLE = STYLE_START + """
<style>
.fr-nav{display:flex;align-items:center;gap:2px;margin-right:3px;padding-right:7px;
  border-right:1px solid color-mix(in srgb,var(--line) 80%,transparent)}
.fr-nav .tool-btn{text-decoration:none;padding:0 7px;font-size:15px;line-height:1}
.fr-nav .fr-home{font-size:12.5px;letter-spacing:.02em}
.fr-nav .is-off{opacity:.32;cursor:default}
@media(max-width:820px){.fr-nav .fr-prev,.fr-nav .fr-next{display:none}}
@media(max-width:620px){.fr-nav{margin-right:0;padding-right:0;border-right:0}.brand-mini{display:none}}
.fr-bm{float:right;border:0;background:transparent;color:var(--muted);font:16px/1 var(--sans);
  cursor:pointer;padding:2px 5px;margin-left:8px;border-radius:6px}
.fr-bm:hover{background:var(--paper3);color:var(--ink)}
.fr-bm.on{color:var(--gold)}
.nav-link .fr-star{margin-left:auto;color:var(--gold);font-size:10px}
.fr-hl{background:color-mix(in srgb,var(--gold) 32%,transparent);color:inherit;border-radius:2px;padding:0 1px;cursor:pointer}
html[data-theme="night"] .fr-hl{background:rgba(214,171,84,.26)}
.fr-hlbar[hidden]{display:none}
.fr-hlbar{position:absolute;z-index:140;display:flex;background:var(--ink);border-radius:8px;padding:3px;
  box-shadow:0 8px 22px rgba(0,0,0,.28)}
.fr-hlbar button{border:0;background:transparent;color:var(--paper);font:12px/1.3 var(--sans);
  padding:5px 10px;border-radius:6px;cursor:pointer}
.fr-hlbar button:hover{background:rgba(255,255,255,.16)}
@media print{.fr-nav,.fr-bm,.fr-hlbar{display:none}}
</style>
""" + STYLE_END

PROGRESS = PROG_START + """
<script>
(function(){
  var POS = 'fastread:pos:';
  var LAST = 'fastread:last';
  var file = (location.pathname.split('/').pop() || '').replace(/\\.html$/, '');
  if (!file) return;
  try { localStorage.setItem('__fr', '1'); localStorage.removeItem('__fr'); }
  catch (e) { return; }

  var sections = Array.prototype.slice.call(document.querySelectorAll('section[id]'));
  var saved = null;
  try { saved = JSON.parse(localStorage.getItem(POS + file) || 'null'); } catch (e) {}
  var armed = false;          // pas d'écriture avant la tentative de restauration
  var userMoved = false;

  ['wheel', 'touchstart', 'keydown'].forEach(function(ev){
    window.addEventListener(ev, function(){ userMoved = true; }, { passive: true, once: true });
  });

  function activeSection(){
    var y = window.scrollY || document.documentElement.scrollTop || 0;
    var id = sections.length ? sections[0].id : '';
    for (var i = 0; i < sections.length; i++) {
      if (sections[i].getBoundingClientRect().top <= 200) id = sections[i].id;
    }
    return { id: id, y: y };
  }

  function save(){
    if (!armed) return;
    var a = activeSection();
    var el = a.id ? document.getElementById(a.id) : null;
    var frac = 0;
    if (el) {
      var top = el.getBoundingClientRect().top + (window.scrollY || 0);
      var h = el.offsetHeight || 1;
      frac = Math.min(1, Math.max(0, (a.y - top) / h));
    }
    var max = document.documentElement.scrollHeight - window.innerHeight;
    var pct = max > 0 ? Math.min(1, Math.max(0, a.y / max)) : 0;
    try {
      localStorage.setItem(POS + file, JSON.stringify({ id: a.id, frac: frac, pct: pct, ts: Date.now() }));
      var dir = location.pathname.indexOf('/papers/') >= 0 ? 'papers/' : 'books/';
      localStorage.setItem(LAST, JSON.stringify({ file: file, path: dir + file + '.html', title: document.title, pct: pct, ts: Date.now() }));
    } catch (e) { /* quota / mode privé */ }
  }

  var timer = null;
  window.addEventListener('scroll', function(){
    if (timer) clearTimeout(timer);
    timer = setTimeout(save, 700);
  }, { passive: true });
  window.addEventListener('pagehide', save);
  document.addEventListener('visibilitychange', function(){ if (document.hidden) save(); });

  function restore(){
    if (armed) return;
    armed = true;
    if (location.hash || userMoved) return;        // un lien ou une action utilisateur gagne
    var s = saved;
    if (!s || !s.id || !(s.pct > 0.02) || s.pct > 0.97) return;
    var el = document.getElementById(s.id);
    if (!el) return;
    var target = el.getBoundingClientRect().top + (window.scrollY || 0) + Math.max(0, s.frac || 0) * el.offsetHeight;
    function jump(){
      // html{scroll-behavior:smooth} rendrait la restauration animée et instable
      // pendant le re-coulement de MathJax : on force un saut instantané.
      var prev = document.documentElement.style.scrollBehavior;
      document.documentElement.style.scrollBehavior = 'auto';
      window.scrollTo(0, target);
      document.documentElement.style.scrollBehavior = prev;
    }
    jump();
    // MathJax peut re-couler après le premier rendu : on réapplique une fois.
    setTimeout(function(){
      if (Math.abs((window.scrollY || 0) - target) > 80) jump();
    }, 900);
  }

  function later(){
    if (window.MathJax && MathJax.startup && MathJax.startup.promise) {
      MathJax.startup.promise.then(function(){ setTimeout(restore, 80); });
    } else {
      setTimeout(restore, 400);
    }
  }
  if (document.readyState === 'complete') later();
  else window.addEventListener('load', function(){ setTimeout(later, 50); });
})();

/* ---- signets de section + surlignage ---- */
(function(){
  var file = (location.pathname.split('/').pop() || '').replace(/\.html$/, '');
  if (!file) return;
  try { localStorage.setItem('__fr2', '1'); localStorage.removeItem('__fr2'); }
  catch (e) { return; }

  var BM = 'fastread:bm:' + file;
  var bms = [];
  try { bms = JSON.parse(localStorage.getItem(BM) || '[]') || []; } catch (e) {}
  function saveBm(){ try { localStorage.setItem(BM, JSON.stringify(bms)); } catch (e) {} }
  function paintNav(id, on){
    var a = document.querySelector('.nav-link[data-sec="' + id + '"]');
    if (!a) return;
    var star = a.querySelector('.fr-star');
    if (!star) { star = document.createElement('span'); star.className = 'fr-star'; star.textContent = '★'; a.appendChild(star); }
    star.style.display = on ? '' : 'none';
  }
  Array.prototype.forEach.call(document.querySelectorAll('section[id]'), function(sec){
    var h = sec.querySelector('h2');
    if (!h) return;
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'fr-bm'; b.title = '收藏本节'; b.setAttribute('aria-label', '收藏本节');
    function paint(){
      var on = bms.indexOf(sec.id) >= 0;
      b.textContent = on ? '★' : '☆';
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      paintNav(sec.id, on);
    }
    b.addEventListener('click', function(e){
      e.preventDefault(); e.stopPropagation();
      var i = bms.indexOf(sec.id);
      if (i >= 0) bms.splice(i, 1); else bms.push(sec.id);
      saveBm(); paint();
    });
    h.appendChild(b);
    paint();
  });

  var HL = 'fastread:hl:' + file;
  var hls = [];
  try { hls = JSON.parse(localStorage.getItem(HL) || '[]') || []; } catch (e) {}
  function saveHl(){ try { localStorage.setItem(HL, JSON.stringify(hls)); } catch (e) {} }
  var SKIP = 'mjx-container,script,style,pre,code,.fr-bm,.fr-hlbar';

  function frWalk(sec){
    var w = document.createTreeWalker(sec, NodeFilter.SHOW_TEXT, null);
    var nodes = [], text = '', n;
    while ((n = w.nextNode())) {
      var par = n.parentElement;
      if (!par || !n.nodeValue || par.closest(SKIP)) continue;
      nodes.push({ node: n, start: text.length });
      text += n.nodeValue;
    }
    return { nodes: nodes, text: text };
  }
  function frAbs(w, node, off){
    for (var i = 0; i < w.nodes.length; i++) {
      if (w.nodes[i].node === node) return w.nodes[i].start + off;
    }
    return -1;
  }
  function frPos(w, off){
    for (var i = w.nodes.length - 1; i >= 0; i--) {
      if (w.nodes[i].start <= off) return { node: w.nodes[i].node, offset: off - w.nodes[i].start };
    }
    return null;
  }
  function frLocate(sec, quote, prefix, suffix){
    if (!quote) return null;
    var w = frWalk(sec), from = 0, idx = -1;
    while ((idx = w.text.indexOf(quote, from)) >= 0) {
      var before = w.text.slice(Math.max(0, idx - 24), idx);
      var after = w.text.slice(idx + quote.length, idx + quote.length + 24);
      var okP = !prefix || before.slice(-prefix.length) === prefix;
      var okS = !suffix || after.slice(0, suffix.length) === suffix;
      if (okP && okS) break;
      from = idx + 1;
    }
    if (idx < 0) return null;
    var a = frPos(w, idx), b = frPos(w, idx + quote.length);
    if (!a || !b) return null;
    var r = document.createRange();
    try { r.setStart(a.node, a.offset); r.setEnd(b.node, b.offset); } catch (e) { return null; }
    return r;
  }
  function frWrap(r, id){
    var m = document.createElement('mark');
    m.className = 'fr-hl'; m.dataset.hl = id; m.title = '点击移除高亮';
    try { r.surroundContents(m); }
    catch (e) { var frag = r.extractContents(); m.appendChild(frag); r.insertNode(m); }
    return m;
  }
  function restoreHighlights(){
    hls.forEach(function(h){
      var sec = document.getElementById(h.sec);
      if (!sec) return;
      var r = frLocate(sec, h.quote, h.prefix, h.suffix);
      if (r) frWrap(r, h.id);
    });
  }
  // Après MathJax : les formules sont remplacées par des <svg>, la carte des
  // nœuds de texte change. On restaure donc une fois le rendu stabilisé.
  if (window.MathJax && MathJax.startup && MathJax.startup.promise) {
    MathJax.startup.promise.then(function(){ setTimeout(restoreHighlights, 150); });
  } else if (document.readyState === 'complete') {
    restoreHighlights();
  } else {
    window.addEventListener('load', function(){ setTimeout(restoreHighlights, 300); });
  }

  var bar = document.createElement('div');
  bar.className = 'fr-hlbar'; bar.hidden = true;
  var btn = document.createElement('button');
  btn.type = 'button'; btn.id = 'fr-hl-btn'; btn.textContent = '高亮';
  bar.appendChild(btn); document.body.appendChild(bar);

  var pending = null, shownAt = 0;
  function hideBar(){ bar.hidden = true; pending = null; }

  function onSelect(){
    var sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) { hideBar(); return; }
    var range = sel.getRangeAt(0);
    var node = range.commonAncestorContainer;
    var el = node.nodeType === 1 ? node : node.parentElement;
    if (!el || el.closest('pre,code,mjx-container,mark.fr-hl')) { hideBar(); return; }
    var sec = el.closest('section[id]');
    if (!sec) { hideBar(); return; }
    var raw = sel.toString();
    if (raw.trim().length < 2 || raw.length > 800) { hideBar(); return; }
    var w = frWalk(sec);
    var a = frAbs(w, range.startContainer, range.startOffset);
    var b = frAbs(w, range.endContainer, range.endOffset);
    var quote = raw, prefix = '', suffix = '';
    if (a >= 0 && b > a) {
      quote = w.text.slice(a, b);
      prefix = w.text.slice(Math.max(0, a - 24), a);
      suffix = w.text.slice(b, b + 24);
    }
    if (!quote.trim()) { hideBar(); return; }
    pending = { sec: sec.id, quote: quote, prefix: prefix, suffix: suffix };
    var rect = range.getBoundingClientRect();
    bar.hidden = false; shownAt = Date.now();
    bar.style.left = Math.max(8, rect.left + window.scrollX + Math.min(rect.width / 2 - 24, 90)) + 'px';
    bar.style.top = Math.max(8, rect.top + window.scrollY - 42) + 'px';
  }

  document.addEventListener('mouseup', function(e){
    if (e.target.closest('.fr-hlbar')) return;
    setTimeout(onSelect, 0);
  });
  document.addEventListener('touchend', function(e){
    if (e.target.closest('.fr-hlbar')) return;
    setTimeout(onSelect, 0);
  }, { passive: true });
  document.addEventListener('mousedown', function(e){ if (!e.target.closest('.fr-hlbar')) hideBar(); });
  window.addEventListener('scroll', function(){ if (Date.now() - shownAt > 250) hideBar(); }, { passive: true });

  btn.addEventListener('click', function(){
    if (!pending) return;
    var h = { id: 'h' + Date.now(), sec: pending.sec, quote: pending.quote, prefix: pending.prefix, suffix: pending.suffix };
    var sec = document.getElementById(h.sec);
    var r = sec ? frLocate(sec, h.quote, h.prefix, h.suffix) : null;
    if (r) { frWrap(r, h.id); hls.push(h); saveHl(); }
    hideBar();
    try { window.getSelection().removeAllRanges(); } catch (e) {}
  });

  document.addEventListener('click', function(e){
    var m = e.target.closest('mark.fr-hl');
    if (!m) return;
    e.preventDefault();
    var id = m.dataset.hl;
    hls = hls.filter(function(h){ return h.id !== id; });
    saveHl();
    var parent = m.parentNode;
    while (m.firstChild) parent.insertBefore(m.firstChild, m);
    parent.removeChild(m);
    try { parent.normalize(); } catch (err) {}
  });
})();
</script>
""" + PROG_END


def strip_block(text: str, start: str, end: str) -> str:
    # Absorbe aussi les sauts de ligne autour du bloc, sinon chaque passage
    # ajoute une ligne vide (le fichier ne serait plus idempotent).
    return re.sub(r"\n*" + re.escape(start) + r".*?" + re.escape(end) + r"\n*", "",
                  text, flags=re.S)


def strip_nav(text: str) -> str:
    # La nav est insérée inline après <div class="tools"> : on ne mange que
    # l'indentation qui la suit, jamais le saut de ligne du contenu voisin.
    return re.sub(r"\n*" + re.escape(NAV_START) + r".*?" + re.escape(NAV_END)
                  + r"[ \t]*\n?", "", text, flags=re.S)


def nav_block(prev_row, next_row, home_href, prev_label, next_label) -> str:
    def link(cls, row, label, arrow):
        if not row:
            return f'<span class="tool-btn {cls} is-off" aria-disabled="true">{arrow}</span>'
        name = row["title"]
        return (f'<a class="tool-btn {cls}" href="{html.escape(row["file"], quote=True)}" '
                f'title="{label}：{html.escape(name, quote=True)}" '
                f'aria-label="{label}：{html.escape(name, quote=True)}">{arrow}</a>')

    return (NAV_START + '\n<nav class="fr-nav" aria-label="书库导航">'
            + link("fr-prev", prev_row, prev_label, "‹")
            + f'<a class="tool-btn fr-home" href="{html.escape(home_href, quote=True)}" '
              f'title="返回索引">书库</a>'
            + link("fr-next", next_row, next_label, "›")
            + '</nav>\n' + NAV_END)


def enhance(path: Path, nav_html: str) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    for start, end in ((STYLE_START, STYLE_END), (PROG_START, PROG_END)):
        text = strip_block(text, start, end)
    text = strip_nav(text)

    if "</head>" not in text or '<div class="tools">' not in text or "</body>" not in text:
        print(f"  ! structure inattendue, ignoré : {path.name}")
        return False

    text = text.replace("</head>", "\n" + STYLE + "\n</head>", 1)
    text = text.replace('<div class="tools">', '<div class="tools">' + nav_html + '\n', 1)
    text = text.replace("</body>", "\n" + PROGRESS + "\n</body>", 1)

    if text == original:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def enhance_set(directory: str, rows, home_href: str, labels, check: bool):
    changed, missing = 0, []
    for i, row in enumerate(rows):
        path = C.ROOT / directory / row["file"]
        if not path.exists():
            continue
        if check:
            if NAV_START not in path.read_text(encoding="utf-8"):
                missing.append(row["file"])
            continue
        prev_row = rows[i - 1] if i > 0 else None
        next_row = rows[i + 1] if i + 1 < len(rows) else None
        nav = nav_block(prev_row, next_row, home_href, labels[0], labels[1])
        if enhance(path, nav):
            changed += 1
    return changed, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="ne rien écrire, signaler les fichiers sans nav")
    args = ap.parse_args()

    books = [r for r in C.ordered_rows(C.load_rows())
             if (C.ROOT / "books" / r["file"]).exists()]
    papers = []
    papers_json = C.ROOT / "papers.json"
    if papers_json.exists():
        papers = [r for r in json.load(open(papers_json, encoding="utf-8"))
                  if (C.ROOT / "papers" / r["file"]).exists()]
        papers.sort(key=lambda r: (-int(r.get("year") or 0), r["title"].lower()))

    if args.check:
        _, miss_books = enhance_set("books", books, "../books/index.html", ("上一本", "下一本"), True)
        _, miss_papers = enhance_set("papers", papers, "index.html", ("上一篇", "下一篇"), True)
        missing = miss_books + miss_papers
        if missing:
            print(f"{len(missing)} fichier(s) sans navigation :")
            for name in missing[:10]:
                print("  -", name)
            sys.exit(1)
        print(f"navigation OK sur {len(books)} livres et {len(papers)} articles")
        return

    changed_books, _ = enhance_set("books", books, "../books/index.html", ("上一本", "下一本"), False)
    changed_papers, _ = enhance_set("papers", papers, "index.html", ("上一篇", "下一篇"), False)
    print(f"navigation + reprise de lecture : {changed_books} livre(s), "
          f"{changed_papers} article(s) mis à jour")


if __name__ == "__main__":
    main()
