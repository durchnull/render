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

from page_api import (ARTICLE_CSS, article_head, check_page,  # noqa: E402
                      md_to_html, page_shell, parse_frontmatter, source_list,
                      strip_inline)
from content_core import closes_fence, fence_info  # noqa: E402

WORDS_PER_MINUTE = 220

_IMAGE = re.compile(r"!\[([^\]]*)\]\(\s*<?([^)>\s]*)>?(?:\s+\"[^\"]*\")?\s*\)")
_LINK = re.compile(r"\[([^\]]+)\]\(\s*<?([^)>\s]*)>?(?:\s+\"[^\"]*\")?\s*\)")
_AUTOLINK = re.compile(r"<((?:https?://|www\.)[^>\s]+)>")
_BARE = re.compile(r"(?<![\w@/])https?://([^\s<>()\[\]\"'`]+)")
_EXTERNAL = re.compile(r"^(?:https?://|www\.)", re.I)


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
    body = md_to_html(unlink(text, sources), heading_base=heading_base(text))

    page = (article_head(title, kicker=kicker, lede=lede,
                         meta=[when, reading_time(text)])
            + f"<div class='article'>{body}</div>"
            + source_list(sources.entries()))
    return page_shell(title, f"<div class='wrap wrap--narrow'>{page}</div>",
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
