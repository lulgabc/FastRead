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
@media print{.fr-nav{display:none}}
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
      localStorage.setItem(LAST, JSON.stringify({ file: file, title: document.title, pct: pct, ts: Date.now() }));
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
</script>
""" + PROG_END


def strip_block(text: str, start: str, end: str) -> str:
    return re.sub(re.escape(start) + r".*?" + re.escape(end), "", text, flags=re.S)


def nav_block(prev_row, next_row) -> str:
    def link(cls, row, label, arrow):
        if not row:
            return f'<span class="tool-btn {cls} is-off" aria-disabled="true">{arrow}</span>'
        name = row["title"]
        return (f'<a class="tool-btn {cls}" href="{html.escape(row["file"], quote=True)}" '
                f'title="{label}：{html.escape(name, quote=True)}" '
                f'aria-label="{label}：{html.escape(name, quote=True)}">{arrow}</a>')

    return (NAV_START + '\n<nav class="fr-nav" aria-label="书库导航">'
            + link("fr-prev", prev_row, "上一本", "‹")
            + '<a class="tool-btn fr-home" href="../index.html" title="返回书库索引">书库</a>'
            + link("fr-next", next_row, "下一本", "›")
            + '</nav>\n' + NAV_END)


def enhance(path: Path, prev_row, next_row) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    for start, end in ((STYLE_START, STYLE_END), (NAV_START, NAV_END), (PROG_START, PROG_END)):
        text = strip_block(text, start, end)

    if "</head>" not in text or '<div class="tools">' not in text or "</body>" not in text:
        print(f"  ! structure inattendue, ignoré : {path.name}")
        return False

    text = text.replace("</head>", STYLE + "\n</head>", 1)
    text = text.replace('<div class="tools">', '<div class="tools">' + nav_block(prev_row, next_row), 1)
    text = text.replace("</body>", PROGRESS + "\n</body>", 1)

    if text == original:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="ne rien écrire, signaler les fichiers sans nav")
    args = ap.parse_args()

    rows = [r for r in C.ordered_rows(C.load_rows()) if (C.ROOT / "books" / r["file"]).exists()]
    changed = 0
    missing = []
    for i, row in enumerate(rows):
        path = C.ROOT / "books" / row["file"]
        if args.check:
            if NAV_START not in path.read_text(encoding="utf-8"):
                missing.append(row["file"])
            continue
        prev_row = rows[i - 1] if i > 0 else None
        next_row = rows[i + 1] if i + 1 < len(rows) else None
        if enhance(path, prev_row, next_row):
            changed += 1

    if args.check:
        if missing:
            print(f"{len(missing)} livre(s) sans navigation :")
            for name in missing[:10]:
                print("  -", name)
            sys.exit(1)
        print(f"navigation OK sur {len(rows)} livres")
        return

    print(f"navigation + reprise de lecture : {changed} fichier(s) mis à jour sur {len(rows)}")


if __name__ == "__main__":
    main()
