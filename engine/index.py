#!/usr/bin/env python3
"""The index page — one card per rendered output, rewritten on every run.

Any project that renders anything gets ``<out dir>/index.html`` for free:
the entry point that shows what the engine produced and links to each page.
It is furniture, not a page the project declares — no folder under
``pages/``, no entry in the cache manifest's page registries, and it never
lists itself.

Two properties make it survive a partial run:

* the card records live in the manifest under ``index``, keyed by the ref
  that already identifies one output (``<pid>`` for a section page,
  ``<pid>:<stem>`` for one instance of a kind page). A ``--page`` run
  refreshes the cards it touched and carries the rest over unchanged, so a
  single-page render never empties the index;
* a record survives only as long as its output file does. A pruned
  instance, a deleted page folder and a file somebody removed by hand all
  drop off the index on the next run, without any of the three having to be
  noticed separately.

Titles and descriptions come from the thing being listed, never from here:
a section page's ``TITLE`` and ``DESCRIPTION``, a kind's ``summary()`` hook
for one of its instances. A kind that implements nothing still yields a
usable card — its spec's title if it has one, else the instance stem.

Size and last-change come from the output file itself rather than from the
record, so they stay honest across a cache wipe and report what is actually
on disk.
"""

import re
from datetime import datetime
from pathlib import Path

from content_core import fmt_size, strip_inline
from design_system import badge, card, esc, list_row, section_head, tile

#: Written to ``<out dir>/`` unless ``config.INDEX_FILENAME`` says otherwise.
FILENAME = "index.html"

#: Longest description a card shows; longer text is cut at a word boundary.
DESC_MAX = 190

# User-visible text. English defaults, overridable through config.STRINGS
# like every other engine string — unknown keys there are ignored.
STRINGS = {
    "idx_title": "Pages",
    "idx_kicker": "render",
    "idx_lead": ("Everything this project renders, in one place. "
                 "Each card opens its page."),
    "idx_pages": "Pages",
    "idx_size": "Total size",
    "idx_changed": "Last change",
    "idx_sections": "Sections",
    "idx_source": "Source",
    "idx_instances": "{n} pages",
    "idx_one_instance": "1 page",
    "idx_empty": ("Nothing rendered yet — a page appears here as soon as its "
                  "folder exists under <code>pages/</code>."),
    "idx_generated": "Generated on {generated}",
    "idx_self_contained": "self-contained · no external resources",
}

# Page CSS, tokens only (design-manual.md, 10). The card is the link: an
# anchor around the finished card keeps the whole surface clickable without
# a second component, and the grid needs the card's own bottom margin gone.
CSS = """
.idx-link { display: block; text-decoration: none; color: inherit;
  border-radius: var(--r-card); }
.idx-link .card { margin-bottom: 0; height: 100%;
  transition: border-color .12s ease, box-shadow .12s ease, transform .12s ease; }
.idx-link:hover .card { border-color: var(--accent-line);
  box-shadow: var(--shadow-lift); transform: translateY(-1px); }
.idx-link:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
.idx-link .card-title { color: var(--accent); }
.idx-link .card-foot code { font-size: var(--fs-eyebrow); }
@media (prefers-reduced-motion: reduce) {
  .idx-link .card { transition: none; }
  .idx-link:hover .card { transform: none; }
}
"""

_BLOCK_MARKUP = re.compile(r"\A\s*(#{1,6}\s|[-*+]\s|\d+[.)]\s|>\s|\||```)")


# --------------------------------------------------------------- records ----

def _lede(text: str) -> str:
    """One sentence of plain text out of whatever prose was handed over.

    Descriptions arrive as markdown as often as not — a questionnaire's
    intro, a document's frontmatter. The first paragraph line that is not a
    heading, a list item or a table row is the one that reads like a
    description; inline markup comes off it, and an over-long one is cut at
    a word boundary rather than mid-word.
    """
    for line in str(text or "").splitlines():
        if not line.strip() or _BLOCK_MARKUP.match(line):
            continue
        s = strip_inline(line)
        if len(s) <= DESC_MAX:
            return s
        return s[:DESC_MAX].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"
    return ""


def _facts(pairs) -> list:
    """Label/value pairs as JSON-safe strings — the manifest stores them.

    Labels are resolved to the project's language here, while the layer that
    knows which language that is is still in scope; the record then carries
    finished text and the index never has to translate anything again.
    """
    return [[str(label), str(value)] for label, value in pairs if str(value)]


def section_record(pid: str, page, out_name: str, strings: dict) -> dict:
    """The card for a section page: it is one page, so it is one card.

    No ``page_title``: a section page is not a family, so it never gets a
    group heading, and the field would only repeat ``title``.
    """
    sections = list(getattr(page, "SECTIONS", []) or [])
    return {
        "pid": pid,
        "stem": None,
        "kind": None,
        "out": out_name,
        "title": str(getattr(page, "TITLE", pid)),
        "desc": _lede(getattr(page, "DESCRIPTION", "")),
        "facts": _facts([(strings["idx_sections"], len(sections))]),
        "badge": None,
    }


def instance_record(pid: str, stem: str, page, kind, spec, ctx, out_name: str,
                    src: Path, root: Path, strings: dict) -> dict:
    """The card for one instance of a kind page.

    The kind decides what its instance is called and what is worth knowing
    about it (``summary()``); everything it leaves out falls back to what
    the engine can see by itself — the spec's own title, else the stem, and
    the source file the instance was rendered from.
    """
    summary = kind.summary(spec, ctx) if kind is not None else {}
    fallback = spec.get("title") if isinstance(spec, dict) else None
    try:
        source = str(Path(src).relative_to(root))
    except (ValueError, TypeError):
        source = Path(src).name
    facts = _facts(summary.get("facts") or [])
    facts.append([strings["idx_source"], source])
    mark = summary.get("badge") or None
    return {
        "pid": pid,
        "stem": stem,
        "kind": kind.name if kind is not None else None,
        "out": out_name,
        "page_title": str(getattr(page, "TITLE", pid)),
        "title": str(summary.get("title") or fallback or stem),
        "desc": _lede(summary.get("desc") or ""),
        "facts": facts,
        "badge": [str(mark[0]), str(mark[1])] if mark else None,
    }


def order(records: dict) -> list:
    """Every record in display order: section pages first, then the families,
    each by page id and instance stem. Stable, so the file only moves when
    its content does."""
    return sorted(records.values(),
                  key=lambda r: (r.get("kind") is not None, r.get("pid") or "",
                                 r.get("stem") or ""))


# ------------------------------------------------------------------ page ----

class _IndexPage:
    """What ``shell()`` reads off a page. Deliberately almost empty:
    ``LANG``, ``FAVICON_HREF`` and ``GENERATED_FMT`` fall through to the
    project's ``config.py``, so the index wears the same clothes as the
    pages it lists."""


PAGE = _IndexPage()


def _stat(path: Path):
    try:
        st = path.stat()
    except OSError:
        return None, None
    return st.st_size, datetime.fromtimestamp(st.st_mtime)


def _value(text: str) -> str:
    """A fact value is data, never markup.

    ``list_row`` passes anything starting with ``<`` through unchanged so a
    badge can sit in the value slot. Here the values come out of spec files,
    so that door is closed by wrapping such a value in a span — the text
    still reads the same, and it reaches the page escaped.
    """
    s = str(text)
    return f"<span>{esc(s)}</span>" if s.lstrip().startswith("<") else s


def _card(rec: dict, out_dir: Path, date_fmt: str) -> str:
    size, changed = _stat(out_dir / rec["out"])
    rows = "".join(list_row(label, _value(value))
                   for label, value in rec.get("facts") or [])
    mark = rec.get("badge")
    foot_right = " · ".join(p for p in (
        fmt_size(size) if size is not None else "",
        changed.strftime(date_fmt) if changed else "") if p)
    body = card(rows,
                title=rec.get("title") or rec["out"],
                sub=rec.get("desc") or "",
                right=badge(mark[0], mark[1]) if mark else "",
                foot_left=f"<code>{esc(rec['out'])}</code>",
                foot_right=foot_right)
    return f"<a class='idx-link' href='{esc(rec['out'])}'>{body}</a>"


def _grid(records, out_dir, date_fmt) -> str:
    return ("<div class='grid'>"
            + "".join(_card(r, out_dir, date_fmt) for r in records)
            + "</div>")


def _tiles(records, out_dir, strings, date_fmt) -> str:
    sizes, times = [], []
    for rec in records:
        size, changed = _stat(out_dir / rec["out"])
        if size is not None:
            sizes.append(size)
        if changed is not None:
            times.append(changed)
    return ("<div class='tiles'>"
            + tile(strings["idx_pages"], str(len(records)))
            + tile(strings["idx_size"], fmt_size(sum(sizes)) if sizes else "—")
            + tile(strings["idx_changed"],
                   max(times).strftime(date_fmt) if times else "—")
            + "</div>")


def build(records: dict, strings: dict, out_dir, generated: str, date_fmt: str,
          shell) -> str:
    """The finished index page.

    ``shell`` is handed in rather than imported: the composer lives in
    ``render.py`` and importing it back here would make the two modules
    depend on each other for nothing.
    """
    out_dir = Path(out_dir)
    listed = order(records)
    singles = [r for r in listed if r.get("kind") is None]
    families = [r for r in listed if r.get("kind") is not None]

    hero = (f"  <header class=\"hero\"><div class=\"eyebrow\">"
            f"{esc(strings['idx_kicker'])}</div>"
            f"<h1>{esc(strings['idx_title'])}</h1>"
            f"<p>{esc(strings['idx_lead'])}</p></header>\n")

    parts = []
    if listed:
        parts.append(_tiles(listed, out_dir, strings, date_fmt))
    else:
        parts.append(f"<p class='empty'>{strings['idx_empty']}</p>")

    # Pages the project designed one by one carry no group heading: they are
    # not a family, and a heading over them would only repeat the page title.
    # The families below name themselves, which is what tells the two apart.
    if singles:
        parts.append(f"<section>{_grid(singles, out_dir, date_fmt)}</section>")

    num = 0
    for pid in dict.fromkeys(r["pid"] for r in families):
        group = [r for r in families if r["pid"] == pid]
        num += 1
        count = (strings["idx_one_instance"] if len(group) == 1
                 else strings["idx_instances"].format(n=len(group)))
        head = section_head(group[0].get("page_title") or pid,
                            num=f"{num:02d}", kicker=group[0].get("kind") or "",
                            right=badge(count))
        parts.append(f"<section>{head}"
                     f"{_grid(group, out_dir, date_fmt)}</section>")

    foot = (f"  <footer>{esc(strings['idx_generated'].format(generated=generated))}"
            f" · {esc(strings['idx_self_contained'])}</footer>")

    return shell(PAGE, "".join(parts), "", title=strings["idx_title"],
                 hero=hero, foot=foot, extra_css=CSS, chrome=False)
