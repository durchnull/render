#!/usr/bin/env python3
"""The index page — one magazine card per rendered output, rewritten on
every run.

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

A card is a cover motif, a title, a description and one quiet meta line —
nothing else (design-manual.md 5.5). The cover is drawn from what the page
actually contains (its section count, its items and their progress, its
questions), so the graphic is derived, never decorative stock. Last-change
comes from the output file itself rather than from the record, so it stays
honest across a cache wipe and reports what is actually on disk.
"""

import re
from datetime import datetime
from pathlib import Path

from content_core import strip_inline
from design_system import badge, esc, icon, section_head, subhead

#: Written to ``<out dir>/`` unless ``config.INDEX_FILENAME`` says otherwise.
FILENAME = "index.html"

#: Longest description a card shows; longer text is cut at a word boundary.
DESC_MAX = 190

#: The growth path (design-manual.md 5.5): up to GROUPED-1 outputs the index
#: is the uniform card grid; from GROUPED on it gains the recently-updated
#: strip; from ROWS on the cards become definition-list rows — known-item
#: finding needs a scannable list, not a browsing gallery.
GROUPED = 8
ROWS = 15

#: One small violet glyph per page kind — the heterogeneity signal in the
#: rows and strip variants, where there is no room for a cover. Section
#: pages read as charts; unknown kinds as documents.
GLYPHS = {None: "chart", "checklist": "list", "questionnaire": "question"}

# User-visible text. English defaults, overridable through config.STRINGS
# like every other engine string — unknown keys there are ignored.
STRINGS = {
    "idx_title": "Pages",
    "idx_kicker": "render",
    "idx_n_sections": "{n} sections",
    "idx_one_section": "1 section",
    "idx_instances": "{n} pages",
    "idx_one_instance": "1 page",
    "idx_empty": ("Nothing rendered yet — a page appears here as soon as its "
                  "folder exists under <code>pages/</code>."),
    "idx_updated": "Recently updated",
    "idx_generated": "Generated on {generated}",
    "idx_self_contained": "self-contained · no external resources",
}

# Page CSS, tokens only (design-manual.md, 10). The card is the link: one
# anchor around the whole card keeps the entire surface clickable without a
# second component. The card is built here rather than with card(): the
# full-bleed cover band has no place in the component's padded anatomy.
CSS = """
.idx-link { display: block; text-decoration: none; color: inherit;
  border-radius: var(--r-card); }
.idx-link:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
.idx-card { height: 100%; display: flex; flex-direction: column; overflow: hidden;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r-card); box-shadow: var(--shadow);
  transition: border-color .12s ease, box-shadow .12s ease, transform .12s ease; }
.idx-link:hover .idx-card { border-color: var(--accent-line);
  box-shadow: var(--shadow-lift); transform: translateY(-1px); }
/* The cover band — a quiet inset stage for the content motif; the badge is
   the one piece of status that may sit on it. */
.idx-cover { position: relative; display: grid; place-items: center;
  height: 104px; flex: none; background: var(--inset);
  border-bottom: 1px solid var(--hairline); }
.idx-cover .badge { position: absolute; top: 10px; right: 10px; }
.idx-cover svg { display: block; }
.idx-cover .cv-fill { fill: var(--accent-solid); }
.idx-cover .cv-line { fill: none; stroke: var(--accent-line); stroke-width: 1.5; }
.idx-cover .cv-tick { fill: none; stroke: var(--on-accent); stroke-width: 1.75;
  stroke-linecap: round; stroke-linejoin: round; }
.idx-body { display: flex; flex-direction: column; flex: 1 1 auto;
  padding: var(--s4) var(--s5) var(--s4); }
.idx-title { font-size: var(--fs-h3); font-weight: 600; letter-spacing: -0.012em;
  line-height: 1.3; margin: 0; }
.idx-link:hover .idx-title { color: var(--accent); }
.idx-desc { margin: var(--s1) 0 0; color: var(--ink-2); font-size: var(--fs-sub); }
.idx-meta { margin-top: auto; padding-top: var(--s3); color: var(--muted);
  font: 400 12px var(--font-mono); font-variant-numeric: tabular-nums; }
.idx-meta span { white-space: nowrap; }
/* The one hero slot (5.5) — the most recently updated output spans two
   tracks, lead-story sized. The only piece of bento the index takes;
   single-column unaffected. */
.grid .idx-hero { grid-column: span 2; }
.idx-hero .idx-cover { height: 148px; }
.idx-hero .idx-cover svg { transform: scale(1.25); }
.idx-hero .idx-title { font-size: var(--fs-h2); letter-spacing: -0.022em; }
@media (max-width: 620px) {
  .grid .idx-hero { grid-column: auto; }
  .idx-hero .idx-cover { height: 104px; }
  .idx-hero .idx-cover svg { transform: none; }
  .idx-hero .idx-title { font-size: var(--fs-h3); }
}
/* Definition-list rows — "lists wearing card clothes" — for 15+ outputs, and
   the slim recently-updated strip above the sections from 8 on. */
.idx-rows { display: flex; flex-direction: column; }
.idx-row { display: flex; align-items: baseline; gap: var(--s3);
  padding: 12px 2px; border-bottom: 1px solid var(--hairline);
  text-decoration: none; color: inherit; }
.idx-row:last-child { border-bottom: 0; }
.idx-row:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.idx-row .idx-glyph { flex: none; color: var(--accent); align-self: center; }
.idx-row .t { font-size: var(--fs-h4); font-weight: 600; }
.idx-row:hover .t { color: var(--accent); }
.idx-row .d { display: block; font-size: var(--fs-sub); color: var(--muted);
  margin-top: 2px; }
.idx-row .idx-text { min-width: 0; flex: 1 1 auto; }
.idx-row .idx-date { flex: none; color: var(--muted);
  font: 400 12px var(--font-mono); font-variant-numeric: tabular-nums; }
.idx-strip { margin-bottom: var(--s7); }
.idx-strip .idx-row { padding: 8px 2px; }
.idx-strip .t { font-size: var(--fs-body); font-weight: 500; }
@media (prefers-reduced-motion: reduce) {
  .idx-card { transition: none; }
  .idx-link:hover .idx-card { transform: none; }
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


def section_record(pid: str, page, out_name: str, strings: dict) -> dict:
    """The card for a section page: it is one page, so it is one card.

    No ``page_title``: a section page is not a family, so it never gets a
    group heading, and the field would only repeat ``title``. The meta
    phrase is resolved to the project's language here, while the layer that
    knows which language that is is still in scope; the record then carries
    finished text and the index never has to translate anything again.
    """
    n = len(list(getattr(page, "SECTIONS", []) or []))
    phrase = (strings["idx_one_section"] if n == 1
              else strings["idx_n_sections"].format(n=n))
    return {
        "pid": pid,
        "stem": None,
        "kind": None,
        "out": out_name,
        "title": str(getattr(page, "TITLE", pid)),
        "desc": _lede(getattr(page, "DESCRIPTION", "")),
        "meta": [phrase],
        "cover": {"form": "sections", "n": n},
        "badge": None,
    }


def instance_record(pid: str, stem: str, page, kind, spec, ctx,
                    out_name: str) -> dict:
    """The card for one instance of a kind page.

    The kind decides what its instance is called and what is worth knowing
    about it (``summary()``): ``meta`` is a list of finished phrases for the
    card's one meta line, ``cover`` the JSON-safe data its cover motif is
    drawn from. A kind still handing over the retired ``facts`` pairs gets
    them folded into meta phrases rather than dropped. Everything the kind
    leaves out falls back to what the engine can see by itself — the spec's
    own title, else the stem.
    """
    summary = kind.summary(spec, ctx) if kind is not None else {}
    fallback = spec.get("title") if isinstance(spec, dict) else None
    meta = [str(p) for p in summary.get("meta") or ()]
    meta += [f"{label} {value}" for label, value in summary.get("facts") or ()
             if str(value)]
    cover = summary.get("cover")
    mark = summary.get("badge") or None
    return {
        "pid": pid,
        "stem": stem,
        "kind": kind.name if kind is not None else None,
        "out": out_name,
        "page_title": str(getattr(page, "TITLE", pid)),
        "title": str(summary.get("title") or fallback or stem),
        "desc": _lede(summary.get("desc") or ""),
        "meta": meta,
        "cover": dict(cover) if isinstance(cover, dict) else None,
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


def _ref(rec: dict) -> str:
    return f"{rec.get('pid')}:{rec.get('stem')}" if rec.get("stem") else str(rec.get("pid"))


def _glyph(rec: dict) -> str:
    return GLYPHS.get(rec.get("kind"), "doc")


# ----------------------------------------------------------------- covers ----
# The cover motif (5.5): a small abstract drawing of what the page holds,
# derived from real counts — a progress mosaic from a checklist's items, a
# form silhouette with one row per question, a wireframe with one block per
# section. A motif, deliberately not a chart: it caps at what stays legible
# at cover size, and the meta line below carries the exact numbers. Colors
# are the two accent classes in the CSS above; the SVG stays token-free.

def _svg(w: int, h: int, body: str) -> str:
    return (f"<svg viewBox='0 0 {w} {h}' width='{w}' height='{h}' "
            f"aria-hidden='true'>{body}</svg>")


def _cv_checks(data: dict) -> str:
    """One cell per counted item (capped at 24), done ones filled and
    ticked. With more items than cells, the filled share keeps the ratio."""
    total = max(_num(data.get("total")), 0)
    done = min(max(_num(data.get("done")), 0), total)
    cells = min(total, 24) or 8
    filled = round(done * cells / total) if total else 0
    cols, step = min(cells, 8), 21
    rows = -(-cells // cols)
    parts = []
    for i in range(cells):
        x, y = (i % cols) * step, (i // cols) * step
        if i < filled:
            parts.append(f"<rect class='cv-fill' x='{x}' y='{y}' "
                         f"width='14' height='14' rx='4'/>")
            parts.append(f"<path class='cv-tick' d='M{x + 3.5} {y + 7.2}"
                         f"l2.4 2.4 4.6-5'/>")
        else:
            parts.append(f"<rect class='cv-line' x='{x}' y='{y}' "
                         f"width='14' height='14' rx='4'/>")
    return _svg(cols * step - 7, rows * step - 7, "".join(parts))


def _cv_list(data: dict) -> str:
    """A form silhouette: one dot-and-line row per question, capped at 5."""
    rows = min(max(_num(data.get("n")), 1), 5)
    widths = (128, 100, 138, 88, 116)
    parts, y = [], 5
    for i in range(rows):
        parts.append(f"<circle class='cv-fill' cx='5' cy='{y}' r='4.5'/>")
        parts.append(f"<path class='cv-line' d='M19 {y}h{widths[i % 5]}' "
                     f"stroke-linecap='round' stroke-width='3'/>")
        y += 17
    return _svg(19 + max(widths[:rows]), y - 17 + 6, "".join(parts))


def _cv_sections(data: dict) -> str:
    """A page wireframe: a title mark, then one block per section (capped
    at 6) in the two-column rhythm the section pages themselves use."""
    n = min(max(_num(data.get("n")), 1), 6)
    parts = ["<rect class='cv-fill' x='0' y='0' width='56' height='6' rx='3'/>"]
    for i in range(n):
        x, y = (i % 2) * 84, 16 + (i // 2) * 26
        parts.append(f"<rect class='cv-line' x='{x}' y='{y}' "
                     f"width='76' height='18' rx='5'/>")
    rows = -(-n // 2)
    return _svg(160, 16 + rows * 26 - 8, "".join(parts))


def _cv_doc() -> str:
    """The fallback for a record without cover data: a document."""
    parts = ["<rect class='cv-fill' x='0' y='0' width='56' height='6' rx='3'/>"]
    for i, w in enumerate((140, 118, 132)):
        parts.append(f"<path class='cv-line' d='M0 {20 + i * 13}h{w}' "
                     f"stroke-linecap='round' stroke-width='3'/>")
    return _svg(140, 49, "".join(parts))


_COVERS = {"checks": _cv_checks, "list": _cv_list, "sections": _cv_sections}


def _num(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _cover(rec: dict) -> str:
    data = rec.get("cover") or {}
    draw = _COVERS.get(data.get("form"))
    svg = draw(data) if draw else _cv_doc()
    mark = rec.get("badge")
    b = badge(mark[0], mark[1]) if mark else ""
    return f"<div class='idx-cover'>{svg}{b}</div>"


# ------------------------------------------------------------------ cards ----

def _card(rec: dict, out_dir: Path, date_fmt: str, hero: str = "") -> str:
    """One magazine card: cover · title · description · one meta line."""
    _, changed = _stat(out_dir / rec["out"])
    phrases = [str(p) for p in rec.get("meta") or ()]
    if changed:
        phrases.append(changed.strftime(date_fmt))
    # Each phrase in its own span: the line may break between phrases,
    # never inside one — a date split across lines reads as two numbers.
    meta = ("<div class='idx-meta'>"
            + " · ".join(f"<span>{esc(p)}</span>" for p in phrases)
            + "</div>") if phrases else ""
    desc = (f"<p class='idx-desc'>{esc(rec.get('desc') or '')}</p>"
            if rec.get("desc") else "")
    cls = " idx-hero" if hero and hero == _ref(rec) else ""
    return (f"<a class='idx-link{cls}' href='{esc(rec['out'])}'>"
            f"<article class='idx-card'>{_cover(rec)}"
            f"<div class='idx-body'>"
            f"<h3 class='idx-title'>{esc(rec.get('title') or rec['out'])}</h3>"
            f"{desc}{meta}</div></article></a>")


def _grid(records, out_dir, date_fmt, hero: str = "") -> str:
    return ("<div class='grid'>"
            + "".join(_card(r, out_dir, date_fmt, hero) for r in records)
            + "</div>")


def _row(rec: dict, out_dir: Path, date_fmt: str, desc: bool = True) -> str:
    """One definition-list row: glyph · bold title · one description line ·
    mono date. The whole row is the link — 'lists wearing card clothes'."""
    _, changed = _stat(out_dir / rec["out"])
    d = (f"<span class='d'>{esc(rec.get('desc') or '')}</span>"
         if desc and rec.get("desc") else "")
    when = changed.strftime(date_fmt) if changed else ""
    return (f"<a class='idx-row' href='{esc(rec['out'])}'>"
            f"<span class='idx-glyph'>{icon(_glyph(rec), 15)}</span>"
            f"<span class='idx-text'><span class='t'>"
            f"{esc(rec.get('title') or rec['out'])}</span>{d}</span>"
            f"<span class='idx-date'>{esc(when)}</span></a>")


def _rows(records, out_dir, date_fmt) -> str:
    return ("<div class='idx-rows'>"
            + "".join(_row(r, out_dir, date_fmt) for r in records)
            + "</div>")


def _by_recency(records, out_dir):
    """(changed, record) pairs, newest first — mtime is measured, never
    recorded, so the ordering stays honest across a cache wipe (and relative
    wording stays off the page: the strip shows absolute dates only)."""
    dated = []
    for rec in records:
        _, changed = _stat(out_dir / rec["out"])
        if changed is not None:
            dated.append((changed, rec))
    dated.sort(key=lambda pair: pair[0], reverse=True)
    return dated


def _strip(dated, out_dir, strings, date_fmt) -> str:
    """The continue-where-I-left-off strip (5.5): a slim title+date list of
    the most recently updated outputs, above the sections."""
    rows = "".join(_row(rec, out_dir, date_fmt, desc=False)
                   for _, rec in dated[:4])
    if not rows:
        return ""
    return (f"<section class='idx-strip'>"
            + subhead(strings["idx_updated"])
            + f"<div class='idx-rows'>{rows}</div></section>")


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

    # The masthead carries no lead sentence: the cards below say everything
    # a lead could, and the page exists to be left within seconds.
    hero = (f"  <header class=\"hero\"><div class=\"eyebrow\">"
            f"{esc(strings['idx_kicker'])}</div>"
            f"<h1>{esc(strings['idx_title'])}</h1></header>\n")

    parts = []
    if not listed:
        parts.append(f"<p class='empty'>{strings['idx_empty']}</p>")

    # The growth path (design-manual.md 5.5), decided by a count check and
    # nothing else: a small index browses as cards, a grown one gains the
    # continue-where-I-left-off strip, a large one reads as rows. The hero
    # slot marks the most recently updated output — a judgment the generator
    # can legitimately make — and only exists while cards are cards.
    dated = _by_recency(listed, out_dir)
    as_rows = len(listed) >= ROWS
    hero_ref = (_ref(dated[0][1])
                if not as_rows and len(listed) >= 4 and dated else "")
    if len(listed) >= GROUPED and dated:
        parts.append(_strip(dated, out_dir, strings, date_fmt))
    render = _rows if as_rows else (
        lambda group, o, f: _grid(group, o, f, hero_ref))

    # Pages the project designed one by one carry no group heading: they are
    # not a family, and a heading over them would only repeat the page title.
    # The families below name themselves, which is what tells the two apart.
    if singles:
        parts.append(f"<section>{render(singles, out_dir, date_fmt)}</section>")

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
                     f"{render(group, out_dir, date_fmt)}</section>")

    foot = (f"  <footer>{esc(strings['idx_generated'].format(generated=generated))}"
            f" · {esc(strings['idx_self_contained'])}</footer>")

    return shell(PAGE, "".join(parts), "", title=strings["idx_title"],
                 hero=hero, foot=foot, extra_css=CSS, chrome=False,
                 topbar=False)
