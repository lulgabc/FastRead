#!/usr/bin/env python3
"""Entity-aware escaping for math inside HTML.

Why this exists
---------------
TeX such as ``$u(x)<u(y)$`` is valid math but invalid HTML: the browser
parses ``<u`` as an HTML tag and silently eats the rest of the formula.
This tool escapes ``<``, ``>`` and bare ``&`` *only inside* ``$...$`` and
``$$...$$``, leaving HTML tags, attributes and <script>/<style> blocks alone.
Existing entities (``&lt;``, ``&gt;``, ``&amp;``, ...) are preserved, so the
tool is idempotent.

Usage
-----
    python escape_math.py file1.html file2.html ...
    cat page.html | python escape_math.py
"""
import re
import sys

ENTITY = re.compile(r"&(lt|gt|amp|quot|apos|#\d+|#x[0-9a-fA-F]+);")


def escape_math_segment(s: str) -> str:
    out = []
    i, n, mode = 0, len(s), None
    while i < n:
        if mode is None:
            if s.startswith("$$", i):
                out.append("$$")
                mode = "display"
                i += 2
                continue
            if s[i] == "$" and (i == 0 or s[i - 1] != "\\"):
                out.append("$")
                mode = "inline"
                i += 1
                continue
            out.append(s[i])
            i += 1
            continue

        if mode == "display" and s.startswith("$$", i):
            out.append("$$")
            mode = None
            i += 2
            continue
        if mode == "inline" and s[i] == "$" and (i == 0 or s[i - 1] != "\\"):
            out.append("$")
            mode = None
            i += 1
            continue

        ch = s[i]
        if ch == "&":
            out.append("&" if ENTITY.match(s, i) else "&amp;")
        elif ch == "<":
            out.append("&lt;")
        elif ch == ">":
            out.append("&gt;")
        else:
            out.append(ch)
        i += 1
    return "".join(out)




def _escape_text(s: str) -> str:
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "&":
            out.append("&" if ENTITY.match(s, i) else "&amp;")
        elif ch == "<":
            out.append("&lt;")
        elif ch == ">":
            out.append("&gt;")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


CODE = re.compile(r"(<code\b[^>]*>)(.*?)(</code\s*>)", re.S | re.I)
PRE = re.compile(r"(<pre\b[^>]*>)(.*?)(</pre\s*>)", re.S | re.I)


def escape_code_block(block: str) -> str:
    """Escape text inside <pre> (including nested <code>) or <code>."""
    m = PRE.fullmatch(block)
    if m:
        inner = m.group(2)
        if CODE.search(inner):
            inner = CODE.sub(lambda x: x.group(1) + _escape_text(x.group(2)) + x.group(3), inner)
        else:
            inner = _escape_text(inner)
        return m.group(1) + inner + m.group(3)
    m = CODE.fullmatch(block)
    if m:
        return m.group(1) + _escape_text(m.group(2)) + m.group(3)
    return block


def escape_math_html(html: str) -> str:
    """Escape math outside <script> and <style> blocks."""
    parts = re.split(
        r"(<script\b.*?</script\s*>|<style\b.*?</style\s*>|"
        r"<pre\b[^>]*>.*?</pre\s*>|<code\b[^>]*>.*?</code\s*>)",
        html, flags=re.S | re.I)
    out = []
    for idx, part in enumerate(parts):
        if idx % 2 == 1:  # protected block
            low = part[:10].lower()
            if low.startswith("<pre") or low.startswith("<code"):
                out.append(escape_code_block(part))
            else:
                out.append(part)
        else:
            out.append(escape_math_segment(part))
    return "".join(out)


if __name__ == "__main__":
    files = sys.argv[1:]
    if not files:
        sys.stdout.write(escape_math_html(sys.stdin.read()))
    else:
        for name in files:
            with open(name, "r", encoding="utf-8") as f:
                text = f.read()
            with open(name, "w", encoding="utf-8") as f:
                f.write(escape_math_html(text))
            print(f"escaped {name}")
