#!/usr/bin/env python3
"""Assemble a single self-contained tutorial HTML from shell + sections.

Typical layout
--------------
    project/
      src/
        sections/00-intro.html
        sections/01-ch1.html
        ...
        nav.html            (optional; auto-generated from sections if absent)
      dist/Tutorial.html

Usage
-----
    python build_tutorial.py --sections src/sections --out dist/Tutorial.html \
        --title "Monge–Ampère 方程 · 交互教程" \
        --book-title "Monge–Ampère 方程" --book-subtitle "从凸几何到正则性"

Everything is inlined: CSS, JS, MathJax (tex-svg). The result opens from
file:// with no network. Use --dev to load MathJax from a CDN instead.
"""
import argparse
import html
import re
import sys
import urllib.request
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from escape_math import escape_math_html  # noqa: E402

MATHJAX_URL = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"

CONFIG = r"""
<script>
window.MathJax = {
  tex: {
    inlineMath: [['$','$'],['\\(','\\)']],
    displayMath: [['$$','$$'],['\\[','\\]']],
    processEscapes: true,
    macros: {
      R: '{\\mathbb{R}}', N: '{\\mathbb{N}}', C: '{\\mathbb{C}}',
      dd: '{\\,\\mathrm{d}}', tr: '{\\operatorname{tr}}', Cof: '{\\operatorname{Cof}}',
      eps: '{\\varepsilon}', Om: '{\\Omega}',
      norm: ['{\\left\\|#1\\right\\|}', 1], abs: ['{\\left|#1\\right|}', 1],
      loc: '{\\mathrm{loc}}', dist: '{\\operatorname{dist}}', spt: '{\\operatorname{spt}}',
      osc: '{\\operatorname{osc}}', dH: '{d_H}', pa: '{\\partial}',
      la: '{\\lambda}', Lamb: '{\\Lambda}', weak: '{\\rightharpoonup}',
      boldsymbol: ['{\\mathbf{#1}}', 1], bm: ['{\\mathbf{#1}}', 1]
    }
  },
  svg: { fontCache: 'local', scale: 1.02 },
  options: { skipHtmlTags: ['script','noscript','style','textarea','pre','code'] }
};
</script>
"""

POST = r"""
<script>
(function(){
  function fixHash(){
    if(!location.hash || location.hash.length<2) return;
    var el=null; try{ el=document.querySelector(location.hash); }catch(e){ return; }
    if(el) el.scrollIntoView({behavior:"auto",block:"start"});
    setTimeout(function(){window.dispatchEvent(new Event("scroll"));},420);
  }
  MathJax.startup.promise.then(function(){ fixHash(); window.dispatchEvent(new Event("scroll")); });
  window.addEventListener("hashchange",function(){ fixHash(); setTimeout(function(){window.dispatchEvent(new Event("scroll"));},60); });
  window.addEventListener("load",function(){ setTimeout(function(){ fixHash(); window.dispatchEvent(new Event("scroll")); }, 150); });
})();
</script>
"""


def strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def auto_nav(sections_html: str) -> str:
    out = []
    for m in re.finditer(r'<section\s+([^>]*)>(.*?)</section>', sections_html, re.S):
        attrs, body = m.group(1), m.group(2)
        id_m = re.search(r'id="([^"]+)"', attrs)
        if not id_m:
            continue
        sec_id = id_m.group(1)
        h2 = re.search(r"<h2[^>]*>(.*?)</h2>", body, re.S)
        title = strip_tags(h2.group(1)) if h2 else sec_id
        title = re.sub(r"^\d+[\.\s]*", "", title).strip() or sec_id
        is_hero = "hero" in attrs.split('class="')[-1].split('"')[0] if 'class="' in attrs else False
        if sec_id == "top" or is_hero:
            num, title = "00", "导读"
        elif sec_id.lower() in ("summary", "conclusion", "wrapup"):
            num, title = "F", "总结"
        elif sec_id.lower().startswith("app"):
            num = "A"
        else:
            num = re.sub(r"^ch", "", sec_id) if sec_id.startswith("ch") else sec_id
            if not re.fullmatch(r"[0-9.\-]+", num):
                num = "•"
        out.append(
            f'    <a class="nav-link" href="#{sec_id}" data-sec="{sec_id}">'
            f'<span class="nav-num">{html.escape(num)}</span> <span>{html.escape(title)}</span></a>'
        )
    return "\n".join(out)




def fix_broken_anchors(html: str) -> str:
    """Point missing #summary/#cheat/#chN links at a sensible existing section."""
    secs = re.findall(r'<section\s+[^>]*id="([^"]+)"[^>]*>(.*?)</section>', html, re.S)
    if not secs:
        return html
    ids = [x[0] for x in secs]
    titles = {sid: strip_tags(re.search(r"<h2[^>]*>(.*?)</h2>", body, re.S).group(1))
              if re.search(r"<h2[^>]*>(.*?)</h2>", body, re.S) else "" for sid, body in secs}
    last = ids[-1]
    def pick(key: str) -> str:
        k = key.lower()
        if k in ids:
            return key
        for sid, title in titles.items():
            if any(w in title for w in ("总结", "一页纸", "速查", "附录")) and any(
                    w in k for w in ("summary", "sheet", "cheat", "appendix")):
                return sid
        m = re.fullmatch(r"ch(\d+)", k)
        if m:
            n = int(m.group(1))
            cand = [(abs(int(re.sub(r"\D", "", sid) or 0) - n), sid)
                    for sid in ids if re.fullmatch(r"ch\d+", sid) and re.sub(r"\D", "", sid)]
            if cand:
                return min(cand)[1]
        return last
    def repl(m):
        return 'href="#' + pick(m.group(1)) + '"'
    return re.sub(r'href="#([^"]+)"', repl, html)


def get_mathjax(dev: bool) -> str:
    if dev:
        return CONFIG + f'<script src="{MATHJAX_URL}"></script>' + POST
    candidates = [
        SKILL / "assets/mathjax-tex-svg.js",
        Path.home() / ".cache" / "book-tutorial" / "mathjax-tex-svg.js",
    ]
    for p in candidates:
        if p.exists() and p.stat().st_size > 500_000:
            return CONFIG + "<script>\n" + p.read_text(encoding="utf-8") + "\n</script>" + POST
    cache = candidates[1]
    cache.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading MathJax -> {cache}")
    urllib.request.urlretrieve(MATHJAX_URL, cache)
    return CONFIG + "<script>\n" + cache.read_text(encoding="utf-8") + "\n</script>" + POST


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", default="src/sections")
    ap.add_argument("--nav", default="src/nav.html")
    ap.add_argument("--out", default="dist/Tutorial.html")
    ap.add_argument("--shell", default=str(SKILL / "assets/shell.html"))
    ap.add_argument("--css", default=str(SKILL / "assets/theme.css"))
    ap.add_argument("--js", default=str(SKILL / "assets/app.js"))
    ap.add_argument("--title", default="交互教程")
    ap.add_argument("--description", default="一本可读、可查、可自测的单页教程。")
    ap.add_argument("--kicker", default="A FIELD GUIDE")
    ap.add_argument("--book-title", default="书名")
    ap.add_argument("--book-subtitle", default="副标题")
    ap.add_argument("--short-title", default="教程")
    ap.add_argument("--stats", default="")
    ap.add_argument("--foot-note", default="编号与原文一致")
    ap.add_argument("--crumb", default="导读")
    ap.add_argument("--footer-about", default="本页是基于原书的学习笔记与讲解。")
    ap.add_argument("--footer-coverage", default="")
    ap.add_argument("--dev", action="store_true", help="load MathJax from CDN (fast builds)")
    ap.add_argument("--no-escape", action="store_true", help="skip math < > & escaping")
    args = ap.parse_args()

    sec_dir = Path(args.sections)
    files = sorted(sec_dir.glob("*.html"))
    if not files:
        sys.exit(f"no .html sections in {sec_dir}")

    pieces = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        pieces.append(text if args.no_escape else escape_math_html(text))
    content = "\n".join(pieces)
    content = fix_broken_anchors(content)

    nav_path = Path(args.nav)
    nav = nav_path.read_text(encoding="utf-8") if nav_path.exists() else auto_nav(content)
    if not nav_path.exists():
        print(f"note: {nav_path} not found, generated nav with {nav.count('nav-link')} links")

    shell = Path(args.shell).read_text(encoding="utf-8")
    values = {
        "TITLE": args.title,
        "DESCRIPTION": args.description,
        "CSS": Path(args.css).read_text(encoding="utf-8"),
        "KICKER": args.kicker,
        "BOOK_TITLE": args.book_title,
        "BOOK_SUBTITLE": args.book_subtitle,
        "STATS": args.stats,
        "NAV": nav,
        "FOOT_NOTE": args.foot_note,
        "SHORT_TITLE": args.short_title,
        "CRUMB": args.crumb,
        "CONTENT": content,
        "FOOTER_ABOUT": args.footer_about,
        "FOOTER_COVERAGE": args.footer_coverage,
        "APP_JS": Path(args.js).read_text(encoding="utf-8"),
    }
    for k, v in values.items():
        shell = shell.replace("{{" + k + "}}", v)
    shell = shell.replace("{{MATHJAX}}", get_mathjax(args.dev))

    leftovers = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", shell)))
    if leftovers:
        print("WARNING: unresolved placeholders:", leftovers)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(shell, encoding="utf-8")
    secs = content.count("<section")
    print(f"wrote {out} | {out.stat().st_size/1e6:.2f} MB | sections: {secs}")
    if args.dev:
        print("dev build: MathJax is loaded from CDN, not self-contained")


if __name__ == "__main__":
    main()
