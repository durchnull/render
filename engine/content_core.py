#!/usr/bin/env python3
"""Generic building blocks shared by all sections: markdown renderer,
frontmatter parsing, file reading, section wrapper.

Everything here is project-agnostic. Project-specific gather/format helpers
belong in the project's ``content.py``, which re-exports this module via
``from content_core import *`` so section modules can keep a single
``from content import …`` import.

A change to this file voids the whole fragment cache (see ``cache.py``) —
unlike a change to a single section module inside a page package, which
only rebuilds that section's fragment.
"""

import hashlib
import html
import re
from pathlib import Path


# ------------------------------------------------------ markdown -> html ----

def parse_frontmatter(text: str):
    meta = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            for line in text[3:end].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"')
            text = text[end + 4:]
    return meta, text.strip()


def inline(s: str) -> str:
    from design_system import status_marks
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*([^*]+)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return status_marks(s)


_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*([^`\s]*)\s*$")
_LIST = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
_TAB = "    "
_BR = "\x00br\x00"          # survives inline()'s escaping, replaced afterwards


def _indent(line: str) -> int:
    """Leading whitespace in columns — tabs count as four."""
    grown = line.replace("\t", _TAB)
    return len(grown) - len(grown.lstrip(" "))


def fence_info(line: str):
    """``(marker, language)`` when this line opens or closes a code fence,
    else ``None``.

    Public because a document parser has to see fences before it sees
    anything else: inside one, a ``## heading`` or a ``- [ ] item`` is sample
    text, not structure (the checklist kind relies on this).
    """
    m = _FENCE.match(line)
    return (m.group(1), m.group(2)) if m else None


def closes_fence(line: str, marker: str) -> bool:
    """True when this line ends a block opened with ``marker`` — same fence
    character, at least as long, and carrying no language of its own."""
    info = fence_info(line)
    return bool(info and not info[1]
                and info[0][0] == marker[0] and len(info[0]) >= len(marker))


def _fence_block(lines, i: int, n: int):
    """``<pre>`` for the fence opening at ``i``, and the index after it.

    Fenced content is literal: it is escaped and never passed through
    ``inline()``, so backticks, asterisks and brackets inside a code sample
    reach the page as themselves. An unclosed fence runs to the end of the
    text rather than swallowing the rest of the document as prose.
    """
    marker, lang = fence_info(lines[i])
    off = _indent(lines[i])
    body, i = [], i + 1
    while i < n and not closes_fence(lines[i], marker):
        row = lines[i].replace("\t", _TAB)
        body.append(row[off:] if row[:off].strip() == "" else row.lstrip())
        i += 1
    cls = f' class="lang-{html.escape(lang, quote=True)}"' if lang else ""
    code = html.escape("\n".join(body), quote=False)
    return f"<pre><code{cls}>{code}</code></pre>", min(i + 1, n)


def _list_block(lines, i: int, n: int, indent: int):
    """One list starting at ``lines[i]``, nested lists included, and the index
    after it.

    Nesting is by indentation: a deeper item opens a sub-list inside the item
    above it. Anything else indented past the marker continues the item —
    wrapped text, a second paragraph, a fenced sample under a step.
    """
    ordered = _LIST.match(lines[i]).group(2) not in ("-", "*", "+")
    items = []

    while i < n:
        m = _LIST.match(lines[i])
        if not m or _indent(lines[i]) != indent:
            break
        # A numbered list after a bulleted one is a new list, not more items.
        if (m.group(2) not in ("-", "*", "+")) != ordered:
            break
        parts, inner, i = [m.group(3)], [], i + 1

        while i < n:
            line = lines[i]
            if not line.strip():
                j = i
                while j < n and not lines[j].strip():
                    j += 1
                # A blank line ends the item unless what follows still belongs
                # to it: a sibling item (loose list) or an indented block.
                if j < n and (_indent(lines[j]) > indent
                              or (_LIST.match(lines[j]) and _indent(lines[j]) == indent)):
                    i = j
                    continue
                i = j
                break
            deeper = _indent(line) > indent
            if _LIST.match(line):
                if not deeper:
                    break
                sub, i = _list_block(lines, i, n, _indent(line))
                inner.append(sub)
                continue
            if not deeper:
                break
            if _FENCE.match(line):
                block, i = _fence_block(lines, i, n)
                inner.append(block)
                continue
            parts.append(line.strip())
            i += 1

        text = " ".join(p for p in parts if p).strip()
        for box, mark in (("[ ]", "☐"), ("[x]", "☑"), ("[X]", "☑")):
            if text.startswith(box):
                text = mark + text[len(box):]
                break
        items.append(f"<li>{inline(text)}{''.join(inner)}</li>")

    tag = "ol" if ordered else "ul"
    return f"<{tag}>" + "".join(items) + f"</{tag}>", i


def md_to_html(text: str, heading_base: int = 3) -> str:
    """Minimal markdown renderer: headings, lists, code fences, tables, quotes,
    hr, paragraphs.

    Deliberately not a full CommonMark implementation — it covers the shapes
    documents in a project actually use. Lists nest, fenced blocks stay
    literal, and a line ending in two spaces breaks inside its paragraph.
    """
    lines = text.splitlines()
    out, i, n = [], 0, len(lines)

    def flush_para(buf):
        if buf:
            joined = " ".join(b for b in buf if b)
            out.append("<p>" + inline(joined).replace(_BR, "<br>") + "</p>")
            buf.clear()

    para = []
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_para(para); i += 1; continue

        if _FENCE.match(line):
            flush_para(para)
            block, i = _fence_block(lines, i, n)
            out.append(block)
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_para(para)
            lvl = min(len(m.group(1)) + heading_base - 1, 6)
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1; continue

        if re.match(r"^(-{3,}|\*{3,})$", stripped):
            flush_para(para); out.append("<hr>"); i += 1; continue

        if stripped.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|-]+\|?$", lines[i + 1].strip()):
            flush_para(para)
            header = [c.strip() for c in stripped.strip("|").split("|")]
            rows, i2 = [], i + 2
            while i2 < n and lines[i2].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i2].strip().strip("|").split("|")])
                i2 += 1
            t = ["<div class='table-wrap'><table>", "<thead><tr>"]
            t += [f"<th>{inline(c)}</th>" for c in header]
            t.append("</tr></thead><tbody>")
            for r in rows:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table></div>")
            out.append("".join(t))
            i = i2; continue

        if stripped.startswith(">"):
            flush_para(para)
            quote = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip("> ").strip())
                i += 1
            out.append("<blockquote><p>" + inline(" ".join(quote)) + "</p></blockquote>")
            continue

        if _LIST.match(line):
            flush_para(para)
            block, i = _list_block(lines, i, n, _indent(line))
            out.append(block)
            continue

        # Two trailing spaces are markdown's hard break; the marker survives
        # escaping and becomes a <br> once the paragraph is inlined.
        para.append(stripped + _BR if line.rstrip("\n").endswith("  ") else stripped)
        i += 1

    flush_para(para)
    return "\n".join(out)


# -------------------------------------------------------------- identity ----
# Naming a piece of text by its content, so a page can key state on it and
# survive the document being edited around it (design-manual.md, 11.7).

_INLINE_MARKUP = (
    (re.compile(r"!?\[([^\]]*)\]\([^)]*\)"), r"\1"),          # link/image -> label
    (re.compile(r"~~(.+?)~~"), r"\1"),                        # strikethrough
    (re.compile(r"\*\*(.+?)\*\*"), r"\1"),                    # bold
    (re.compile(r"(?<![\w*])\*([^*]+)\*(?![\w*])"), r"\1"),   # italic
    (re.compile(r"`([^`]+)`"), r"\1"),                        # code
)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def strip_inline(text: str) -> str:
    """Markdown inline markup removed, whitespace collapsed, controls dropped.

    What survives is what the sentence *says* — the form it was written in
    does not. Reformatting a word as bold, wrapping a term in backticks or
    re-wrapping a long line all leave the result untouched.
    """
    s = str(text)
    for pattern, repl in _INLINE_MARKUP:
        s = pattern.sub(repl, s)
    return " ".join(_CONTROL.sub(" ", s).split())


def fingerprint(*parts) -> str:
    """Six hex characters naming a piece of text by its content.

    Every part is normalised with ``strip_inline()`` and joined with a
    separator no normalised part can contain, so ``fingerprint("a b")`` and
    ``fingerprint("a", "b")`` can never coincide. Extra parts are how a
    caller resolves a collision — text alone first, text plus its enclosing
    heading next — without group-qualifying every id and making a heading
    rename invalidate everything under it.

    Six characters is a deliberate size: short enough to read out of a
    hand-back block and type into a search, long enough that a document
    would need tens of thousands of items before a chance collision, and
    the caller checks for one anyway.
    """
    base = "\x1f".join(strip_inline(p) for p in parts)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:6]


# --------------------------------------------------------------- reading ----

def read_md(path: Path):
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    return meta, body


# ------------------------------------------------------------ formatting ----

def drop_blocks(body: str, titles) -> str:
    """Remove named ``##`` blocks including content (up to the next ``##``).

    For content that stays in the source file but must not reach the page.
    Apply the *same* list wherever the page both renders and counts — else
    tiles count entries that never appear on the page.
    """
    for title in titles:
        body = re.sub(
            r"^##\s+" + re.escape(title) + r"\s*$.*?(?=^##\s|\Z)",
            "", body, flags=re.MULTILINE | re.DOTALL,
        )
    return body.strip()


def strip_leading_h1(body: str) -> str:
    """Drop the first ``# …`` line — the section/row title already says it."""
    lines = body.lstrip().splitlines()
    if lines and lines[0].startswith("# "):
        return "\n".join(lines[1:]).lstrip()
    return body


def split_title(body: str):
    """Split the first ``# …`` line off as the display title."""
    text = body.lstrip()
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        return lines[0][2:].strip(), "\n".join(lines[1:]).lstrip()
    return "", text


def prose(body: str, stripped: bool) -> str:
    """Render a file's markdown. Without its own H1, ``##`` maps to level 3."""
    return f"<div class='prose'>{md_to_html(body, heading_base=2 if stripped else 3)}</div>"


def fmt_size(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024


# ----------------------------------------------------------------- shell ----

# Filled by the engine from the page's SECTIONS before it builds that page's
# sections (and before a --preview): section id -> (id, number, kicker,
# title, subline, nav label). Section modules never touch this directly —
# they just call ``wrap()``.
SECTION_META = {}


def set_section_meta(meta: dict) -> None:
    """Point ``wrap()`` at the section metadata of the page being built."""
    global SECTION_META
    SECTION_META = meta


def wrap(sid: str, body: str, right: str = "") -> str:
    """Wrap a section body in ``<section>`` plus its header row.

    The header deliberately lives inside the fragment: each fragment then
    carries its own counter badge (``right``) and the page shell in
    ``render.py`` stays dumb.
    """
    from design_system import section_head
    _, num, kicker, title, sub, _ = SECTION_META[sid]
    return (f"<section id='{sid}'>"
            f"{section_head(title, sub, num=num, kicker=kicker, right=right)}"
            f"{body}</section>")
