#!/usr/bin/env python3
"""One markdown document → one self-contained article page.

The long-form counterpart to the declared pages: no config directory, no
cache, no hook — a person asks for a page, the page is written, that is the
whole lifecycle. Everything visual comes from the design system's article
tier (``ARTICLE_CSS``), so a page written here belongs to the same family as
every dashboard and questionnaire the engine renders.

    python3 scripts/article.py INPUT.md [-o OUT.html] [--title …] [--kicker …]

The headline comes from ``--title``, else the document's frontmatter, else
its first ``#`` heading, else the file name. Front matter may also carry
``kicker``, ``lede`` and ``date``.

**Links become text.** A self-contained page fetches nothing, and
``check_page()`` refuses external URLs outright, so a link is rendered as its
label with a number, and the numbers are resolved in a source list at the
foot. Targets inside the project (relative paths, anchors) keep their label
and are not listed — in a technical document the label is usually the path
itself. URLs inside code samples lose their scheme (``https://x`` → ``x``)
and nothing else, so a command stays readable and stays honest about not
being clickable.
"""

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "engine"))

from page_api import (ARTICLE_CSS, article_head, aside_note,  # noqa: E402
                      check_page, md_to_html, mini_toc, page_shell,
                      parse_frontmatter, source_list, strip_inline)
from content_core import closes_fence, fence_info  # noqa: E402

WORDS_PER_MINUTE = 230

_IMAGE = re.compile(r"!\[([^\]]*)\]\(\s*<?([^)>\s]*)>?(?:\s+\"[^\"]*\")?\s*\)")
_LINK = re.compile(r"\[([^\]]+)\]\(\s*<?([^)>\s]*)>?(?:\s+\"[^\"]*\")?\s*\)")
_AUTOLINK = re.compile(r"<((?:https?://|www\.)[^>\s]+)>")
_BARE = re.compile(r"(?<![\w@/])https?://([^\s<>()\[\]\"'`]+)")
_EXTERNAL = re.compile(r"^(?:https?://|www\.)", re.I)
_FOOTNOTE_DEF = re.compile(r"^\[\^([A-Za-z0-9_-]+)\]:\s?(.*)$")
_FOOTNOTE_REF = re.compile(r"\[\^([A-Za-z0-9_-]+)\]")
_PROTECTED = re.compile(r"<pre\b.*?</pre>|<code\b.*?</code>", re.S)


def outside_code(html: str, fn) -> str:
    """Apply ``fn`` to every stretch of HTML that is not a code sample — the
    post-processing passes below must never rewrite what a document shows."""
    out, last = [], 0
    for m in _PROTECTED.finditer(html):
        out.append(fn(html[last:m.start()]))
        out.append(m.group(0))
        last = m.end()
    out.append(fn(html[last:]))
    return "".join(out)


def deschemed(url: str) -> str:
    """A URL with its scheme removed — text that points somewhere without
    being a fetchable address on the page."""
    return re.sub(r"^https?://", "", url.strip()).rstrip(">")


class Sources:
    """The destinations an article's links pointed at, in first-seen order."""

    def __init__(self):
        self.order = []
        self._seen = {}

    def ref(self, url: str) -> int:
        key = deschemed(url)
        if key not in self._seen:
            self.order.append(key)
            self._seen[key] = len(self.order)
        return self._seen[key]

    def __len__(self):
        return len(self.order)

    def entries(self):
        """In reference order — ``source_list`` numbers them, so the ``[n]``
        in the text and the list item line up without either counting twice."""
        return list(self.order)


def unlink(md: str, sources: Sources) -> str:
    """Every link replaced by text, code samples left alone but de-schemed.

    Runs line by line because fences decide the rules: inside one, the text
    is a sample and only the scheme has to go; outside, link syntax is markup
    and is resolved into label plus reference number.
    """
    out, fence = [], None
    for line in md.splitlines():
        if fence is not None:
            if closes_fence(line, fence):
                fence = None
            out.append(_BARE.sub(lambda m: m.group(1), line))
            continue
        opening = fence_info(line)
        if opening:
            fence = opening[0]
            out.append(line)
            continue

        line = _IMAGE.sub(lambda m: m.group(1), line)

        def link(m):
            label, target = m.group(1), m.group(2)
            if not _EXTERNAL.match(target):
                return label          # in-project path or anchor: the label says it
            return f"{label} [{sources.ref(target)}]"

        line = _LINK.sub(link, line)
        line = _AUTOLINK.sub(lambda m: f"{deschemed(m.group(1))} "
                                       f"[{sources.ref(m.group(1))}]", line)
        line = _BARE.sub(lambda m: f"{m.group(1)} [{sources.ref(m.group(0))}]", line)
        out.append(line)
    return "\n".join(out)


def extract_footnotes(md: str):
    """(body, notes) — ``[^key]:`` definitions lifted out of the document,
    in-text references renumbered ``[^1]``… in order of first appearance.

    Notes become margin asides (design-manual.md 11b.5). A definition's
    indented continuation lines belong to it; a reference without a
    definition stays literal text, because silently eating it would change
    what the document says.
    """
    defs, out, fence, open_key = {}, [], None, None
    for line in md.splitlines():
        if fence is not None:
            if closes_fence(line, fence):
                fence = None
            out.append(line)
            continue
        opening = fence_info(line)
        if opening:
            fence, open_key = opening[0], None
            out.append(line)
            continue
        m = _FOOTNOTE_DEF.match(line) if not line[:1].isspace() else None
        if m:
            open_key = m.group(1)
            defs[open_key] = [m.group(2)]
            continue
        if open_key is not None and line[:1].isspace() and line.strip():
            defs[open_key].append(line.strip())
            continue
        open_key = None
        out.append(line)

    order = []

    def number(m):
        key = m.group(1)
        if key not in defs:
            return m.group(0)
        if key not in order:
            order.append(key)
        return f"[^{order.index(key) + 1}]"

    lines, fence = [], None
    for line in out:
        if fence is not None:
            if closes_fence(line, fence):
                fence = None
            lines.append(line)
            continue
        opening = fence_info(line)
        if opening:
            fence = opening[0]
            lines.append(line)
            continue
        lines.append(_FOOTNOTE_REF.sub(number, line))
    notes = [" ".join(defs[k]) for k in order]
    return "\n".join(lines), notes


_FOOTNOTE_NUM = re.compile(r"\[\^(\d+)\]")


def weave_asides(html: str, notes) -> tuple:
    """Turn numbered ``[^n]`` markers into sup anchors and place each note as
    an aside right after the paragraph that references it.

    No JS packing exists (11b.5), so a paragraph anchoring more than one
    note sends those notes to the end-notes list instead — honest fallback
    over overlapping floats. Returns ``(html, endnotes)``.
    """
    seen = set()

    def sup(chunk):
        def rep(m):
            n = int(m.group(1))
            id_attr = f" id='fn-ref-{n}'" if n not in seen else ""
            seen.add(n)
            return f"<sup class='fn-ref'{id_attr}><a href='#fn-{n}'>{n}</a></sup>"
        return _FOOTNOTE_NUM.sub(rep, chunk)

    html = outside_code(html, sup)
    inserts, endnotes, used = [], [], set()
    for n in range(1, len(notes) + 1):
        body = md_to_html(notes[n - 1], heading_base=5)
        anchor = html.find(f"id='fn-ref-{n}'")
        p_start = html.rfind("<p>", 0, anchor) if anchor >= 0 else -1
        p_end = html.find("</p>", anchor) if anchor >= 0 else -1
        para = html[p_start:p_end] if 0 <= p_start < p_end else ""
        if not para or p_start in used or para.count("class='fn-ref'") > 1:
            endnotes.append((n, body))
            continue
        used.add(p_start)
        inserts.append((p_end + len("</p>"), aside_note(n, body)))
    for pos, block in sorted(inserts, reverse=True):
        html = html[:pos] + block + html[pos:]
    return html, endnotes


def endnote_block(endnotes, title: str = "Notes") -> str:
    """The notes that could not float: a numbered list at the article's foot,
    each item carrying the ``fn-n`` anchor its in-text reference points at —
    and its real number (``value``), so the list agrees with the sup marks."""
    if not endnotes:
        return ""
    rows = "".join(f"<li id='fn-{n}' value='{n}'>{body}</li>"
                   for n, body in endnotes)
    return f"<h2>{title}</h2><ol class='endnotes'>{rows}</ol>"


def link_sources(html: str, count: int) -> str:
    """The ``[n]`` markers ``unlink()`` wrote become internal sup anchors to
    the source list (11b.4); the first occurrence of each carries the
    ``ref-n`` id the list's ↩ backlink returns to."""
    seen = set()

    def refs(chunk):
        def rep(m):
            n = int(m.group(1))
            if not 1 <= n <= count:
                return m.group(0)
            id_attr = f" id='ref-{n}'" if n not in seen else ""
            seen.add(n)
            return (f"<sup class='src-ref'{id_attr}>"
                    f"<a href='#src-{n}'>[{n}]</a></sup>")
        return re.sub(r"(?<=\s)\[(\d{1,3})\](?!\()", rep, chunk)

    return outside_code(html, refs)


def heading_anchors(html: str):
    """(html, entries) — every ``<h2>`` gets a slug id so the mini-TOC (11b.7)
    has something to point at. Internal anchors only."""
    entries, seen = [], set()

    def rep(m):
        text = re.sub(r"<[^>]+>", "", m.group(1))
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "section"
        while slug in seen:
            slug += "-x"
        seen.add(slug)
        entries.append((slug, text))
        return f"<h2 id='{slug}'>{m.group(1)}</h2>"

    return re.sub(r"<h2>(.*?)</h2>", rep, html, flags=re.S), entries


def paragraph_mode(body: str) -> str:
    """``indent`` or ``spaced`` (11b.1) — one mode per document, decided from
    the text itself: book indents for prose-led pieces, spacing for documents
    that lean on lists and code. Indents or spacing, never both."""
    paras = lists = fences = 0
    fence = None
    for line in body.splitlines():
        if fence is not None:
            if closes_fence(line, fence):
                fence = None
            continue
        opening = fence_info(line)
        if opening:
            fence = opening[0]
            fences += 1
            continue
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if re.match(r"^(\s*)([-*+]|\d+[.)])\s", line):
            lists += 1
        else:
            paras += 1
    return "indent" if lists * 3 <= paras and fences <= 2 else "spaced"


def headline(text: str):
    """(title, body) — the leading ``#`` heading lifted out of the document,
    so the masthead does not repeat what the first line already says."""
    for i, line in enumerate(text.splitlines()):
        if not line.strip():
            continue
        m = re.match(r"^#\s+(.*)$", line.strip())
        if not m:
            return "", text
        rest = "\n".join(text.splitlines()[i + 1:]).lstrip("\n")
        return m.group(1).strip(), rest
    return "", text


def heading_base(body: str) -> int:
    """The shift that makes the document's own top heading level an ``h2``.

    Documents disagree about where they start — some head their sections with
    ``#``, some with ``##``, and a captured message often does both across
    days. Anchoring on the shallowest heading present means the first section
    always sits one step under the masthead, whatever the source wrote.
    """
    top, fence = 6, None
    for line in body.splitlines():
        if fence is not None:
            if closes_fence(line, fence):
                fence = None
            continue
        opening = fence_info(line)
        if opening:
            fence = opening[0]
            continue
        m = re.match(r"^(#{1,6})\s+\S", line.strip())
        if m:
            top = min(top, len(m.group(1)))
    return 3 - min(top, 2)


def reading_time(body: str) -> str:
    words = len(strip_inline(body).split())
    return f"{max(1, round(words / WORDS_PER_MINUTE))} min read"


def build(src: Path, title: str = "", kicker: str = "", lede: str = "",
          when: str = "") -> str:
    """The finished page for one markdown file."""
    meta, text = parse_frontmatter(src.read_text(encoding="utf-8"))
    first, text = headline(text)
    title = title or meta.get("title") or first or src.stem.replace("-", " ")
    kicker = kicker or meta.get("kicker", "")
    lede = lede or meta.get("lede", "")
    when = when or meta.get("date") or _mtime(src)

    sources = Sources()
    md, notes = extract_footnotes(unlink(text, sources))
    body = md_to_html(md, heading_base=heading_base(text))
    body, endnotes = weave_asides(body, notes)
    body = link_sources(body, len(sources))
    body, headings = heading_anchors(body)

    # The meta line (11b.2): derivable facts only — plus a frontmatter
    # `status`, passed through verbatim, never invented.
    words = len(strip_inline(md).split())
    facts = [when, f"{words:,} words", reading_time(md)]
    if len(sources):
        facts.append(f"{len(sources)} source{'s' if len(sources) != 1 else ''}")
    if meta.get("status"):
        facts.append(str(meta["status"]))

    toc = mini_toc(headings) if len(headings) >= 4 else ""
    mode = paragraph_mode(md)
    cls = "article article--indent" if mode == "indent" else "article"
    colophon = (f"rendered {date.today().isoformat()} · {words:,} words · "
                "single file, works offline")

    page = (article_head(title, kicker=kicker, lede=lede, meta=facts)
            + toc
            + f"<div class='{cls}'>{body}{endnote_block(endnotes)}</div>"
            + source_list(sources.entries(), linked=True,
                          colophon_line=colophon))
    return page_shell(title, f"<div class='wrap wrap--read'>{page}</div>",
                      favicon="📰", extra_css=ARTICLE_CSS, wrap=False)


def _mtime(src: Path) -> str:
    """The document's own date — not today's. Re-rendering an old file must
    not restamp it as new."""
    try:
        return datetime.fromtimestamp(src.stat().st_mtime).date().isoformat()
    except OSError:
        return date.today().isoformat()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Render one markdown document as a self-contained article page.")
    ap.add_argument("input", metavar="INPUT.md")
    ap.add_argument("-o", "--out", metavar="FILE",
                    help="output path (default: the input's name with .html)")
    ap.add_argument("--title", default="", help="headline; overrides the document")
    ap.add_argument("--kicker", default="", help="overline above the headline")
    ap.add_argument("--lede", default="", help="standfirst under the headline")
    ap.add_argument("--date", default="", dest="when",
                    help="date in the meta line (default: the file's own)")
    args = ap.parse_args()

    src = Path(args.input).expanduser()
    if not src.is_file():
        return f"no such file: {src}"
    html = build(src, title=args.title, kicker=args.kicker, lede=args.lede,
                 when=args.when)

    findings = check_page(html)
    if findings:
        return "\n".join(f"CHECK  {f}" for f in findings)

    out = Path(args.out).expanduser() if args.out else src.with_suffix(".html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"OK  {out.resolve()} · {out.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
