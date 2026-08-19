#!/usr/bin/env python3
"""The ``checklist`` page kind — one maintained markdown file becomes one
interactive view of itself.

The opposite data flow to the questionnaire. A questionnaire's spec is
authored *for* the renderer and the page collects new data; a checklist's
source is a document the project maintains, the page is an editable **view**
of it, and what comes back is the **diff** — which the project's own skill
applies to the file. The file stays the truth. Everything here follows from
that one sentence:

* ids are content fingerprints, never positions, because the file is edited
  while people have the page open (design-manual.md, 11.7);
* the hand-back is the changes shape, with ``based-on:`` so a stale page can
  be recognised rather than applied (docs/handback.md);
* **this module never writes to the source file.** The engine is a renderer;
  it supplies the fingerprints, the parsed diff and the drift check, and the
  skill applies them, where the change gets a review step.

Validation is the deliberate opposite of the questionnaire's: **permissive
about prose, strict about structure.** A spec written for the renderer may be
rejected for an unknown key, because that is a typo. A document a person owns
may not be rejected for containing a paragraph the parser did not anticipate.

The pipeline order is an invariant, and ``check()`` asserts it held:

    parse → exclude → fingerprint → render, count

Excluded blocks never reach the fingerprinter, so they consume no id, appear
in no total, and can never surface in a hand-back.

The kind is domain-free. It knows how to show a checklist; it knows nothing
about what is on it or what happens to the diff.
"""

import html as _html
import json as _json
import re
from datetime import date
from pathlib import Path

from content_core import (closes_fence, fence_info, fingerprint, inline, md_to_html,
                          parse_frontmatter, strip_inline)
from design_system import (
    APP_CSS, FORM_CSS, STATE_JS, STRINGS as DS_STRINGS, TOAST_JS, action_bar,
    badge, card, check_row, crumbs, esc, focus_card, handback_js, meter_row,
    progress_bar, section_head, subhead, tile, toast,
)

NAME = "checklist"
WRAP_CLASS = "wrap has-actionbar"
# The deadline countdown moves without the file moving, so an instance may not
# be served from yesterday's cache (kinds/__init__.py, VOLATILE).
VOLATILE = True

DEFAULT_MARKER = "CHECKLIST CHANGES"

#: Indented lines under an item whose key is one of these are annotations.
#: Anything else is detail — this is a document a human owns, and an unknown
#: key is far more likely to be their note than a mistake worth an error.
ANNOTATIONS = ("path", "due")

STATES = ("open", "done", "obsolete")

#: Days before the deadline at which the focus card stops being neutral.
DUE_SOON_DAYS = 7

# User-visible text. English defaults; a project overrides any key through
# config.STRINGS or the page's STRINGS. The hand-back grammar is deliberately
# NOT in here — it is a protocol the agent parses, not interface text.
STRINGS = {
    "ck_show": "Show",
    "ck_all": "All",
    "ck_open": "Open",
    "ck_done": "Done",
    "ck_obsolete": "Obsolete",
    "ck_groups": "Groups",
    "ck_filter_aria": "Show part of the list",
    "ck_shown": "{shown} of {total} shown",
    "ck_group_kicker": "Checklist",
    "ck_group_open": "{n} open",
    "ck_next": "Next open item",
    "ck_nothing_open": "Nothing open — everything is done or struck out.",
    "ck_progress": "Progress",
    "ck_progress_done": "{done} of {total} done",
    "ck_days_left": "Days left",
    "ck_days_over": "Days overdue",
    "ck_deadline_sub": "Deadline {date}",
    "ck_deadline_named": "{label} {date}",
    "ck_focus_label": "Items done",
    "ck_focus_ratio": "{done} / {total}",
    "ck_focus_sub": "of {total} that count towards the total",
    "ck_due": "due {date}",
    "ck_overdue": "overdue since {date}",
    "ck_source": "Source",
    "ck_of_counted": "of {total} that count",
    "ck_share": "{pct} % of the list",
    "ck_outside": "outside the ratio, still on the page",
    "ck_items_total": "{n} items in total",
    "ck_set_na": "n/a — does not apply",
    "ck_set_deferred": "later",
    "ck_changes_title": "What you changed",
    "ck_changes_lead": ("The document stays the truth. This is the difference, "
                        "ready to hand back."),
    "ck_nothing_changed": ("Nothing changed yet. Tick something, or leave a note "
                           "on an item that did not go the way it is written."),
    "ck_copy": "Copy the changes",
    "ck_changed_count": "{n} changed",
    "ck_keys": ("Tab moves through the items · Space or Enter ticks the one you "
                "are on"),
    "ck_privacy": ("What you tick and write stays in this browser, on this device, "
                   "until you copy it out. This page loads nothing, sends nothing, "
                   "and never writes to the source file."),
    "ck_generated": "Generated on {generated}",
    "ck_no_storage": ("This browser will not remember what you tick — best to "
                      "finish in one sitting and copy the result out."),
}

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_LIST = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_CHECKBOX = re.compile(r"^\[([ xX])\]\s*(.*)$")
_ANNOTATION = re.compile(r"^(" + "|".join(ANNOTATIONS) + r")\s*:\s*(.*)$", re.I)
_ISO_DATE = re.compile(r"\A(\d{4})-(\d{2})-(\d{2})\Z")
#: An emoji marker may or may not carry its variation selector, and the
#: difference is invisible in an editor. Comparing without it costs one call
#: and removes a whole class of "the exclusion silently stopped working".
_VARIATION = "️"


# ------------------------------------------------------------- frontmatter ----

def _as_date(value):
    """An ISO date, or None. Never guesses at another format: a document that
    writes dates some other way should be told, not silently reinterpreted."""
    if isinstance(value, date):
        return value
    m = _ISO_DATE.match(str(value).strip())
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _as_list(value):
    """A frontmatter list. ``parse_frontmatter`` is a flat key/value reader, so
    a list arrives here as the raw text between the brackets — this is where it
    becomes a list, and where an unusable one becomes a finding.

    Returns (markers, error).
    """
    raw = str(value).strip()
    if not raw:
        return (), None
    if not (raw.startswith("[") and raw.endswith("]")):
        return (), (f"'exclude' must be a list in brackets, e.g. "
                    f'exclude: ["\U0001f5c4", "**Archive"] — found {raw!r}')
    inner = raw[1:-1].strip()
    if not inner:
        return (), None
    out = []
    for part in _split_items(inner):
        part = part.strip()
        if len(part) >= 2 and part[0] == part[-1] and part[0] in "\"'":
            part = part[1:-1]
        if part:
            out.append(part)
    if not out:
        return (), f"'exclude' is a list with nothing usable in it: {raw!r}"
    return tuple(out), None


def _split_items(inner: str) -> list:
    """Split on commas that are not inside quotes — a marker may contain one."""
    out, buf, quote = [], [], ""
    for ch in inner:
        if quote:
            if ch == quote:
                quote = ""
            buf.append(ch)
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch == ",":
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return out


# ------------------------------------------------------------------ blocks ----

def _unstrike(text: str):
    """(text, struck). A strikethrough counts only when it wraps the *whole*
    line — ``~~a~~ and ~~b~~`` strikes two phrases, not the instruction."""
    s = text.strip()
    if s.startswith("~~") and s.endswith("~~") and len(s) > 4 and "~~" not in s[2:-2]:
        return s[2:-2].strip(), True
    return s, False


def _checkbox(content: str):
    """(state, text) for a checklist line, or None for anything else.

    Both spellings are accepted, because real files carry both:
    ``~~[ ] …~~`` strikes the item including its box, ``[x] ~~…~~`` strikes
    only the instruction. Either way the result is ``obsolete`` — the plan's
    rule is that strikethrough wins *whatever the checkbox says*, and an item
    somebody struck out is not progress just because it was once ticked.
    """
    body, struck = _unstrike(content)
    m = _CHECKBOX.match(body)
    if not m:
        return None
    text, struck_inner = _unstrike(m.group(2))
    struck = struck or struck_inner
    if struck:
        return "obsolete", text
    return ("done" if m.group(1).lower() == "x" else "open"), text


def _strip_marker(line: str, markers):
    """What is left of this block's raw source line once its exclusion marker
    is removed, or None when no marker matched.

    The remainder, not the whole line, is what ``check()`` looks for in the
    finished page: a block that leaked without its marker is exactly the
    failure worth catching, and matching on the marker would miss it.
    """
    probe = line.strip()
    bare = probe.replace(_VARIATION, "")
    for marker in markers:
        marker = str(marker)
        if probe.startswith(marker):
            return probe[len(marker):].strip()
        plain = marker.replace(_VARIATION, "")
        if plain and bare.startswith(plain):
            return bare[len(plain):].strip()
    return None


def _matches(line: str, markers) -> bool:
    return _strip_marker(line, markers) is not None


def _parse_blocks(body: str, markers):
    """The document as groups of ordered blocks — ``item | prose | subhead``.

    Real files carry paragraphs between the item blocks, subheads inside a
    group, and bold-only lines titling what follows. All of it is kept, in
    order, so the renderer can walk it and put everything back where it was.
    Being permissive about prose in *validation* is not the same as rendering
    it in the right place.

    Exclusion happens here, before anything is fingerprinted or counted.
    """
    groups = [{"title": None, "blocks": []}]
    # Inside a fenced block nothing is structure: a ``## heading`` or a
    # ``- [ ] step`` in a code sample is text the document is *showing*, and
    # counting it as an item would put a sample into the tally and onto the
    # page as something to tick. (marker, indent, sink) while one is open.
    fence = None
    # What was dropped, kept only so ``check()`` can assert none of it reached
    # the page. It is never rendered and never fingerprinted — remembering the
    # text is how the invariant is proved, not a way around it.
    excluded = []
    prose, item, subhead = [], None, None
    title = ""

    def flush():
        nonlocal prose
        if not prose:
            return
        text = "\n".join(prose)
        prose = []
        head = prose_head(text)
        rest = _strip_marker(head, markers)
        if rest is not None:
            excluded.append(rest or head)
            return
        groups[-1]["blocks"].append({"kind": "prose", "md": text})

    def prose_head(text: str) -> str:
        for line in text.splitlines():
            if line.strip():
                return line
        return ""

    for lineno, raw in enumerate(body.splitlines(), start=1):
        stripped = raw.strip()

        if fence is not None:
            marker, off, sink = fence
            sink.append(raw[off:] if raw[:off].strip() == "" else raw.lstrip())
            if closes_fence(raw, marker):
                fence = None
            continue

        opening = fence_info(raw)
        if opening:
            off = len(raw) - len(raw.lstrip())
            # An indented fence under an item is that item's detail; anything
            # else is prose, and ends the item the way a plain line would.
            sink = item["detail"] if (item is not None and off) else prose
            if sink is prose:
                item = None
            sink.append(raw[off:])
            fence = (opening[0], off, sink)
            continue

        if not stripped:
            flush()
            item = None
            continue

        head = _HEADING.match(raw)
        if head:
            flush()
            item = None
            level, text = len(head.group(1)), head.group(2)
            if level == 1:
                title = title or text
                continue
            if level == 2:
                subhead = None
                groups.append({"title": text, "blocks": []})
                continue
            subhead = text
            rest = _strip_marker(text, markers)
            if rest is not None:
                excluded.append(rest or text)
                subhead = None
                continue
            groups[-1]["blocks"].append({"kind": "subhead", "text": text})
            continue

        listed = _LIST.match(raw)
        checked = _checkbox(listed.group(2)) if listed else None
        if checked:
            # A checkbox is an item wherever it sits. Nesting is flattened
            # rather than swallowed: an indented item that became detail text
            # could be neither counted nor ticked, which is the worse loss.
            flush()
            state, text = checked
            rest = _strip_marker(text, markers)
            if rest is not None:
                excluded.append(rest or text)
                item = None
                continue
            item = {"kind": "item", "state": state, "text": text,
                    "annotations": {}, "detail": [], "line": lineno,
                    "group": groups[-1]["title"], "subhead": subhead}
            groups[-1]["blocks"].append(item)
            continue

        if raw[:1].isspace() and item is not None:
            annotation = _ANNOTATION.match(stripped)
            if annotation:
                item["annotations"][annotation.group(1).lower()] = annotation.group(2).strip()
            else:
                item["detail"].append(stripped)
            continue

        item = None
        prose.append(stripped)

    flush()
    groups = [g for g in groups if g["title"] is not None or g["blocks"]]
    return groups, excluded, title


# ------------------------------------------------------------ fingerprints ----

def _heading_path(item) -> str:
    parts = [p for p in (item["group"], item["subhead"]) if p]
    return " › ".join(parts)


def _assign(items) -> list:
    """Three tiers, applied only as far as needed (see the plan, correction 2).

    1. the instruction text — position- and group-independent, and enough for
       virtually every item;
    2. on collision: text plus the enclosing heading path;
    3. still colliding: plus an ordinal, **and it is reported**.

    Group-qualifying every id would mean a heading rename invalidates every
    item under it. A bare ordinal tiebreak would mean reordering two identical
    items swaps their state. Tiering keeps the positional fallback rare, loud,
    and pointed at what is nearly always a genuine document problem: two
    instructions a *reader* cannot tell apart either.
    """
    parts = {i: (it["text"],) for i, it in enumerate(items)}
    tiers = {i: 1 for i in range(len(items))}

    for tier in (2, 3):
        buckets = {}
        for i, base in parts.items():
            buckets.setdefault(fingerprint(*base), []).append(i)
        clashing = [group for group in buckets.values() if len(group) > 1]
        if not clashing:
            break
        for group in clashing:
            for ordinal, i in enumerate(group, start=1):
                base = (items[i]["text"], _heading_path(items[i]))
                parts[i] = base if tier == 2 else base + (str(ordinal),)
                tiers[i] = tier

    findings = []
    for i, item in enumerate(items):
        item["fp"] = fingerprint(*parts[i])
        item["tier"] = tiers[i]

    seen = {}
    for item in items:
        seen.setdefault(item["fp"], []).append(item)
    for fp, sharing in sorted(seen.items()):
        if len(sharing) > 1:
            texts = ", ".join(repr(s["text"]) for s in sharing)
            findings.append(f"two items share the fingerprint {fp}: {texts}")
    return findings


# -------------------------------------------------------------------- load ----

def _body_offset(raw: str) -> int:
    """Lines ``parse_frontmatter`` removes ahead of the body — the frontmatter
    block and any blank lines after it. Added back onto each item's ``line``
    so the number points into the file as it sits on disk, which is the only
    form an edit plan can honestly reference."""
    text = raw
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]
    lead = len(text) - len(text.lstrip())
    return raw[:len(raw) - len(text) + lead].count("\n")


def load(src: Path, ctx=None):
    """Parse one maintained markdown document into the kind's model.

    Never raises for a document that is merely *wrong* — that is
    ``validate()``'s job, and it reports every finding at once. This raises
    only when the bytes cannot be read at all.

    The exclusion markers have to be resolved *here* rather than at build
    time, because exclusion happens before anything is fingerprinted: a block
    dropped later would already have consumed an id. Hence ``ctx`` — the
    project's default is needed while reading, not after.
    """
    raw = src.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(raw)
    findings = []

    markers, bad = _as_list(meta.get("exclude", ""))
    if bad:
        findings.append(bad)
    if not markers and ctx is not None:
        # frontmatter → page → config → nothing. The document comes first
        # because for this page type the document is the truth.
        markers = tuple(ctx.setting("EXCLUDE_MARKERS", ()) or ())

    groups, excluded, h1 = _parse_blocks(body, markers)
    items = [b for g in groups for b in g["blocks"] if b["kind"] == "item"]
    offset = _body_offset(raw)
    for item in items:
        item["line"] += offset
    findings += _assign(items)

    deadline = None
    if meta.get("deadline"):
        deadline = _as_date(meta["deadline"])
        if deadline is None:
            findings.append(f"frontmatter 'deadline': {meta['deadline']!r} is not an "
                            "ISO date (YYYY-MM-DD)")
    for item in items:
        if "due" in item["annotations"]:
            item["due"] = _as_date(item["annotations"]["due"])
            if item["due"] is None:
                findings.append(f"item {item['fp']} ({item['text']!r}): "
                                f"due {item['annotations']['due']!r} is not an ISO "
                                "date (YYYY-MM-DD)")
        else:
            item["due"] = None

    counts = {state: sum(1 for i in items if i["state"] == state) for state in STATES}
    return {
        "title": meta.get("title") or h1 or src.stem,
        "meta": meta,
        "marker": meta.get("handback-marker") or DEFAULT_MARKER,
        "exclude": markers,
        "deadline": deadline,
        "deadline_label": meta.get("deadline-label") or "",
        "groups": groups,
        "items": items,
        "counts": counts,
        "counted": counts["open"] + counts["done"],
        "excluded": len(excluded),
        "excluded_text": tuple(excluded),
        # The drift check: what the page was rendered from, handed back as
        # ``based-on:`` so a stale page can be recognised (docs/handback.md).
        "source_fp": fingerprint(raw),
        "findings": findings,
    }


# -------------------------------------------------------------- validation ----

def validate(spec, src: Path) -> list:
    """Every structural problem with this document, [] when it is usable.

    Reserved for genuine breakage — nothing here fires because a person wrote
    a paragraph in an unexpected place. A document that cannot be rendered
    honestly is refused; one that is merely unusual is rendered.
    """
    bad = list(spec.get("findings", []))

    if not spec["items"]:
        bad.append("no checklist items — a checklist page needs at least one "
                   "'- [ ]' or '- [x]' line. Lines without a checkbox are prose, "
                   "and prose alone makes a document, not a checklist")

    # One finding per collision, not one per item in it: the reader has one
    # problem to fix, and hearing about it twice does not help them find it.
    positional = {}
    for item in spec["items"]:
        if item["tier"] == 3:
            positional.setdefault((_heading_path(item), strip_inline(item["text"])),
                                  []).append(item)
    for (where, _), sharing in sorted(positional.items()):
        bad.append(
            f"{len(sharing)} items in {where or 'the same group'!r} read exactly "
            f"the same: {sharing[0]['text']!r}. Their state could then only be "
            "told apart by position, so reordering them would swap what is "
            "ticked — give each one wording that says how it differs")
    return bad


# ------------------------------------------------------------------ output ----

def css() -> str:
    """The two opt-in stylesheets plus what only a checklist needs.

    The filter is two rules against ``body[data-filter]`` and nothing else:
    every row stays in the markup, so the count, the hand-back and the print
    output are all unaffected by what is currently on screen.
    """
    return FORM_CSS + APP_CSS + """
/* ---- Checklist (design-manual.md, 6.26 / 11) ----------------------------- */
.ck-lead { font-size: var(--fs-sub); color: var(--ink-2); max-width: 68ch; }
.ck-lead > :first-child { margin-top: 0; }
.ck-filters { margin: var(--s7) 0 var(--s4); }
.ck-filters .btn[aria-pressed="true"] {
  background: var(--accent-soft); border-color: var(--accent-line); color: var(--accent);
}
.ck-filters .btn:focus-visible { outline: 2px solid var(--accent-solid); outline-offset: 2px; }
.ck-prose { font-size: var(--fs-sub); color: var(--ink-2); margin: var(--s4) 0; max-width: 68ch; }
.ck-prose > :first-child { margin-top: 0; }
.ck-prose > :last-child { margin-bottom: 0; }
.ck-copy { display: flex; gap: var(--s3); align-items: baseline; flex-wrap: wrap; }
.ck-copy .hint { font-size: var(--fs-meta); color: var(--muted); }
.ck-keys { font-size: var(--fs-meta); color: var(--muted); margin-top: var(--s5); }

/* The filter: two rules, nothing removed from the markup. */
body[data-filter="open"] .ck-row:not([data-state="open"]) { display: none; }
body[data-filter="done"] .ck-row:not([data-state="done"]) { display: none; }
"""


def footer(spec, ctx, generated: str) -> str:
    """Says where what you tick lives, and that the page never touches the
    source file (11.3). A page's own FOOTER_HTML always wins."""
    s = ctx.strings
    return (f"  <footer>{esc(s['ck_generated'].format(generated=generated))} · "
            f"{esc(s['ck_source'])}: <code>{esc(_source_path(ctx))}</code> · "
            f"{esc(s['ck_privacy'])}</footer>")


def summary(spec, ctx) -> dict:
    """How this checklist introduces itself on the index page.

    Progress is the number worth carrying to a card, and the deadline decides
    its colour — an open item is urgent because of a date, never because it
    is open. Without a deadline a finished list still earns its green: that
    is a state, not a warning.

    The description comes from the document's frontmatter if it left one.
    Nothing is invented from the items: a list of tasks summarised into a
    sentence would be the page guessing what the document means.
    """
    s = ctx.strings
    counts, counted = spec["counts"], spec["counted"]
    meta = [s["ck_group_open"].format(n=counts["open"])]
    deadline = _deadline(spec, ctx)
    tone = ""
    if deadline:
        left = (deadline - date.today()).days
        tone = "crit" if left <= 0 else ("warn" if left <= DUE_SOON_DAYS else "")
        # The absolute date, not a day count: a countdown freezes at render
        # time and starts lying the next morning (design-manual.md 5.5).
        meta.append(s["ck_overdue" if left < 0 else "ck_due"]
                    .format(date=deadline.isoformat()))
    if not tone and counted and not counts["open"]:
        tone = "good"
    return {
        "title": spec["title"],
        "desc": spec["meta"].get("description") or "",
        "meta": meta,
        "cover": {"form": "checks", "done": counts["done"], "total": counted},
        "badge": (s["ck_progress_done"].format(done=counts["done"], total=counted),
                  tone or "neutral"),
    }


def scripts() -> str:
    return TOAST_JS + STATE_JS + handback_js() + CHECKLIST_JS


def _source_path(ctx) -> str:
    """The source file as the project would name it — what ``source:`` in the
    hand-back has to say for the agent to find the file again."""
    try:
        from config import ROOT
        return str(Path(ctx.src).resolve().relative_to(Path(ROOT).resolve()))
    except (ImportError, ValueError):
        return Path(ctx.src).name


def _deadline(spec, ctx):
    """Frontmatter → page → config. The document is in front because for this
    page type the document is the truth (kinds/__init__.py, BuildContext)."""
    if spec["deadline"]:
        return spec["deadline"]
    return _as_date(ctx.setting("DEADLINE", "") or "")


def _next_open(spec):
    """The item to do next: the earliest due date wins, then document order.
    Items with no due date keep their place behind the dated ones rather than
    being sorted to the end of nothing."""
    dated, plain = [], []
    for order, item in enumerate(spec["items"]):
        if item["state"] != "open":
            continue
        (dated if item["due"] else plain).append((item["due"], order, item))
    dated.sort(key=lambda row: (row[0], row[1]))
    return (dated or plain)[0][2] if (dated or plain) else None


def _due_badge(item, today, s) -> str:
    if not item["due"]:
        return ""
    shown = item["due"].isoformat()
    if item["due"] < today:
        return badge(s["ck_overdue"].format(date=shown), "crit")
    tone = "warn" if (item["due"] - today).days <= DUE_SOON_DAYS else "neutral"
    return badge(s["ck_due"].format(date=shown), tone)


def _item_html(item, today, s) -> str:
    context = ""
    if item["annotations"].get("path"):
        context += crumbs(item["annotations"]["path"])
    context += _due_badge(item, today, s)
    detail = md_to_html("\n".join(item["detail"]), heading_base=4) if item["detail"] else ""
    # The person's two statements beyond the tick (6.26): "does not apply" is
    # an affirmative answer, "later" is GOV.UK's own deferral. The document
    # cannot say either, so these exist only as user state — and an obsolete
    # item, which is the document's statement, offers neither.
    actions = ""
    if item["state"] != "obsolete":
        actions = "".join(
            f"<button type='button' class='btn btn--ghost note-open'"
            f" data-set='{key}' data-for='{esc(item['fp'])}'"
            f" aria-pressed='false'>{esc(s[label])}</button>"
            for key, label in (("na", "ck_set_na"), ("deferred", "ck_set_deferred")))
    return check_row(item["fp"], inline(item["text"]), state=item["state"],
                     context=context, detail=detail, actions=actions)


def _split_prelude(blocks) -> tuple:
    """The blocks before the first ``##`` heading, split into lead and list.

    A document that opens with a paragraph and then names its groups wants
    that paragraph above the derived overview — it introduces the whole page,
    not the first item. A document that never names a group has its items
    here instead, and those must not be torn apart: from the first non-prose
    block on, everything stays in the order the file wrote it, because a
    paragraph sitting between two items is explaining one of them.
    """
    for i, block in enumerate(blocks):
        if block["kind"] != "prose":
            return blocks[:i], blocks[i:]
    return list(blocks), []


def _blocks_html(blocks, today, s) -> str:
    out = []
    for block in blocks:
        if block["kind"] == "item":
            out.append(_item_html(block, today, s))
        elif block["kind"] == "subhead":
            out.append(subhead(block["text"]))
        else:
            out.append(f"<div class='prose ck-prose'>"
                       f"{md_to_html(block['md'], heading_base=4)}</div>")
    return "".join(out)


def _hook(markup: str, name: str) -> str:
    """Name one tile so the script can keep its number honest.

    The tiles are rendered by the design system, which has no opinion about
    who reads them back. ``check()`` asserts every hook survived, so a change
    to ``tile()`` fails loudly here instead of quietly leaving a stale number
    on an interactive page.
    """
    return markup.replace("<div class='tile'>",
                          f"<div class='tile' data-tile='{name}'>", 1)


def _overview(spec, ctx, today) -> str:
    """Computed, never authored, and counted **after** exclusion.

    Every number in here also moves while the page is used, so all of them are
    recomputed by the script from the same state the progress bar reads. Two
    ratios for the same thing on one screen is a defect, not a distinction
    between "what the file says" and "what you did".
    """
    s = ctx.strings
    counts, counted = spec["counts"], spec["counted"]
    done = counts["done"]
    pct = (done / counted * 100) if counted else 0
    nxt = _next_open(spec)
    none = esc(s["ck_nothing_open"])
    nxt_html = (f"<span id='ck-next' data-none='{none}'>"
                + (esc(strip_inline(nxt["text"])) if nxt else f"<em>{none}</em>")
                + "</span>")
    aside = [(s["ck_next"], nxt_html),
             (s["ck_progress"], meter_row(s["ck_progress_done"].format(done=done,
                                                                      total=counted),
                                          pct, kind=_meter_tone(pct)))]

    deadline = _deadline(spec, ctx)
    if deadline:
        left = (deadline - today).days
        word = s["ck_days_over" if left < 0 else "ck_days_left"]
        tone = "crit" if left <= 0 else ("warn" if left <= DUE_SOON_DAYS else "")
        # The label always names the unit, so "29" can only be read one way;
        # the document's own wording goes on the reference line, where it says
        # what the date *is*. The badge appears only where there is colour to
        # accompany with a word (2.3) — a neutral badge repeating the label
        # would be decoration.
        focus = focus_card(
            str(abs(left)), word,
            sub=_deadline_sub(spec, deadline, s), kind=tone, aside=aside,
            chip=badge(word, tone) if tone else "")
    else:
        focus = focus_card(s["ck_focus_ratio"].format(done=done, total=counted),
                           s["ck_focus_label"],
                           sub=s["ck_focus_sub"].format(total=counted),
                           kind=_meter_tone(pct), aside=aside)

    groups = [g for g in spec["groups"] if g["title"]]
    tiles = (_hook(tile(s["ck_open"], str(counts["open"]),
                        sub=s["ck_of_counted"].format(total=counted)), "open")
             + _hook(tile(s["ck_done"], str(counts["done"]),
                          sub=s["ck_share"].format(pct=f"{pct:.0f}")), "done")
             + tile(s["ck_obsolete"], str(counts["obsolete"]), sub=s["ck_outside"])
             + tile(s["ck_groups"], str(len(groups)),
                    sub=s["ck_items_total"].format(n=len(spec["items"]))))
    # Every template the script needs, in the document rather than in the
    # script (11.2). ``ck-focus`` says whether the focus number is the
    # countdown (fixed for the day) or the ratio (moves with every tick).
    return (f"<div id='ck-overview'"
            f" data-focus='{'deadline' if deadline else 'ratio'}'"
            f" data-focus-ratio='{esc(s['ck_focus_ratio'])}'"
            f" data-progress='{esc(s['ck_progress_done'])}'"
            f" data-share='{esc(s['ck_share'])}'"
            f" data-group-open='{esc(s['ck_group_open'])}'>"
            f"{focus}<div class='tiles'>{tiles}</div></div>")


def _deadline_sub(spec, deadline, s) -> str:
    """What the date is, in the document's own words where it gave any."""
    if spec["deadline_label"]:
        return s["ck_deadline_named"].format(label=spec["deadline_label"],
                                             date=deadline.isoformat())
    return s["ck_deadline_sub"].format(date=deadline.isoformat())


def _meter_tone(pct: float) -> str:
    return "crit" if pct < 34 else ("warn" if pct < 67 else "")


def _filters(spec, ctx) -> str:
    """Three buttons and a live count. The labels live in the DOM as attributes
    so the script never invents display text (11.2)."""
    s = ctx.strings
    counts = spec["counts"]
    buttons = "".join(
        f"<button type='button' class='btn' data-filter='{key}'"
        f" data-label='{esc(s[label])}' aria-pressed='{'true' if key == 'all' else 'false'}'>"
        f"{esc(s[label])}{'' if key == 'all' else f' ({counts[key]})'}</button>"
        for key, label in (("all", "ck_all"), ("open", "ck_open"), ("done", "ck_done")))
    return (f"<div class='filters ck-filters' role='group'"
            f" aria-label='{esc(s['ck_filter_aria'])}'>"
            f"<span class='note'>{esc(s['ck_show'])}</span>{buttons}"
            f"<span class='note' id='ck-shown' role='status' aria-live='polite'"
            f" data-template='{esc(s['ck_shown'])}'></span></div>")


def _data_block(spec, ctx) -> str:
    """The machine half (11.2): fingerprints, states and group titles — all of
    it also in the DOM. No display text that is not, and nothing about the
    blocks that were excluded, which the page has never heard of."""
    payload = {
        "id": f"{ctx.pid}/{ctx.stem}",
        "marker": spec["marker"],
        "source": _source_path(ctx),
        "title": spec["title"],
        "basedOn": spec["source_fp"],
        "counted": spec["counted"],
        "items": [dict({"fp": i["fp"], "s": i["state"],
                        "g": i["group"] or "", "t": strip_inline(i["text"])},
                       **({"due": i["due"].isoformat()} if i["due"] else {}))
                  for i in spec["items"]],
    }
    text = _json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    text = text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return f"<script type='application/json' id='ck-data'>{text}</script>"


def build(spec, ctx):
    s = ctx.strings
    today = date.today()
    chips = [f"<span class='chip'>{esc(_source_path(ctx))}</span>"]
    deadline = _deadline(spec, ctx)
    if deadline:
        chips.append(f"<span class='chip'><span class='dot'></span>"
                     f"{esc(_deadline_sub(spec, deadline, s))}</span>")

    # Only the first group can be untitled — ``##`` always appends a titled
    # one — so this is the prelude, everything the file wrote before it named
    # a group. Its items are items like any other and belong on the page.
    prelude = [b for g in spec["groups"] if g["title"] is None for b in g["blocks"]]
    lead_blocks, loose = _split_prelude(prelude)
    lead = "".join(f"<div class='prose ck-lead'>{md_to_html(b['md'], heading_base=4)}</div>"
                   for b in lead_blocks)

    sections = []
    if loose:
        # No heading and no ``data-group``: the document named no group here,
        # and inventing one would put a word on the page the file never said —
        # and a group badge the hand-back would then have to explain away.
        sections.append("<section class='ck-group'>"
                        + card(_blocks_html(loose, today, s))
                        + "</section>")
    for n, group in enumerate([g for g in spec["groups"] if g["title"]], start=1):
        items = [b for b in group["blocks"] if b["kind"] == "item"]
        still_open = sum(1 for b in items if b["state"] == "open")
        sections.append(
            f"<section class='ck-group' data-group='{esc(group['title'])}'>"
            + section_head(group["title"], num=f"{n:02d}", kicker=s["ck_group_kicker"],
                           right=badge(s["ck_group_open"].format(n=still_open),
                                       "warn" if still_open else "good"))
            + card(_blocks_html(group["blocks"], today, s))
            + "</section>")

    changes = card(
        f"<p class='empty' id='ck-unchanged'>{esc(s['ck_nothing_changed'])}</p>"
        f"<pre class='handback' id='ck-handback'></pre>"
        f"<p class='ck-keys'>{esc(s['ck_keys'])}</p>",
        title=s["ck_changes_title"], sub=s["ck_changes_lead"])

    storage = (f"<div class='banner banner--warn' id='ck-nostore' hidden>"
               f"{esc(s['ck_no_storage'])}</div>")

    # The progress wording is a DOM attribute rather than a string in the
    # script: 11.2 keeps display text in the document, and the script has to
    # rewrite the ratio on every tick.
    body = (progress_bar(spec["counts"]["done"], spec["counted"], left=spec["title"])
            + f"<main data-progress='{esc(DS_STRINGS['progress_of'])}'>"
            + "<header class='hero'>"
            + f"<h1 tabindex='-1'>{esc(spec['title'])}</h1>"
            + f"<div class='row'>{''.join(chips)}</div></header>"
            + storage + lead
            + _overview(spec, ctx, today)
            + _filters(spec, ctx)
            + "".join(sections)
            + f"<section id='ck-changes'>{changes}</section>"
            + "</main>"
            + _data_block(spec, ctx))

    tail = (toast()
            + action_bar(f"<span class='note' id='ck-changed'"
                         f" data-template='{esc(s['ck_changed_count'])}'></span>",
                         f"<button type='button' class='btn btn--primary' id='ck-copy'>"
                         f"{esc(s['ck_copy'])}</button>")
            + _noscript())
    return body, tail


def _noscript() -> str:
    """Without scripting the page is the document: every item, its state as the
    file records it, and every annotation. What disappears is only the chrome
    that would do nothing — the same set that disappears in print."""
    return ("<noscript><style>"
            ".progress, .actionbar, .ck-filters, .note-open, #ck-changes "
            "{ display: none !important; }"
            ".ck-tick { cursor: default; }"
            ".has-actionbar { padding-bottom: var(--s7); }"
            "</style></noscript>")


# ------------------------------------------------------------------- check ----

_TAGS = re.compile(r"<[^>]+>")


def check(spec, html: str) -> list:
    """What must be true of every checklist page this kind produces.

    The count assertions are the pipeline invariant made mechanical: rendered
    rows == fingerprints issued == open + done + obsolete, and the progress
    denominator counts only the two states that are progress.
    """
    bad = []
    rows = re.findall(r"data-check-row='([^']*)'", html)
    issued = [i["fp"] for i in spec["items"]]
    counts = spec["counts"]

    if "class='focus" not in html:
        bad.append("the derived overview is missing — a checklist page leads "
                   "with what it adds to the document, not with the list")
    # Every number the script keeps in step needs its hook, or the page would
    # quietly show the document's figures next to the reader's.
    for hook in ("id='ck-overview'", "data-tile='open'", "data-tile='done'",
                 "id='ck-next'", "class='meter-row'"):
        if hook not in html:
            bad.append(f"the overview cannot be kept in step: {hook} is missing")
    if "id='ck-handback'" not in html:
        bad.append("the hand-back block is missing")
    if "id='ck-data'" not in html:
        bad.append("the data block is missing")
    if html.count("<noscript>") != 1:
        bad.append("the no-script fallback is missing")

    if sorted(rows) != sorted(issued):
        bad.append(f"{len(rows)} rows rendered for {len(issued)} fingerprints issued")
    if len(set(rows)) != len(rows):
        dupes = sorted({r for r in rows if rows.count(r) > 1})
        bad.append(f"fingerprint rendered more than once: {', '.join(dupes)}")
    total = counts["open"] + counts["done"] + counts["obsolete"]
    if len(issued) != total:
        bad.append(f"{len(issued)} fingerprints for {total} counted states "
                   f"({counts})")

    denominator = re.search(r"class='meter' role='progressbar'[^>]*aria-valuemax='(\d+)'",
                            html)
    if not denominator:
        bad.append("the progress bar is missing")
    elif int(denominator.group(1)) != spec["counted"]:
        bad.append(f"progress counts against {denominator.group(1)} items, but "
                   f"{spec['counted']} of them are open or done — an obsolete item "
                   "belongs in neither half of the ratio")

    # The pipeline invariant: excluded blocks never reached the page at all.
    text = _html.unescape(_TAGS.sub(" ", html))
    for gone in spec["excluded_text"]:
        needle = strip_inline(gone.lstrip("*_`~ "))
        # A remainder too short to be distinctive would assert nothing useful
        # and could collide with ordinary wording elsewhere on the page.
        if len(needle) >= 12 and needle in text:
            bad.append(f"an excluded block reached the page: {needle[:60]!r}")
    return bad


# --------------------------------------------------------------------- js ----
# Purpose 2 of the three permitted ones (design-manual.md, 11.1): show and hide
# what is already in the document — which is what the filter does, since every
# row stays in the markup. Purposes 1 and 3 come from STATE_JS and HANDBACK_JS.

CHECKLIST_JS = r"""
(function () {
  var raw = document.getElementById('ck-data');
  if (!raw) return;
  var data = JSON.parse(raw.textContent);

  /* The document is the baseline; the browser records only the deviation. */
  var doc = {}, order = [];
  data.items.forEach(function (i) { doc[i.fp] = i; order.push(i.fp); });

  /* Content-addressed state (11.7): entries whose fingerprint left the
     document are collected on load, so an edit costs only what changed. */
  var store = Store.make('checklist/' + data.id, { keys: order, bucket: 'items' });
  var state = store.read();
  if (!state.items) state.items = {};
  function save() { store.write(state); }

  function entry(fp) {
    if (!state.items[fp]) state.items[fp] = {};
    return state.items[fp];
  }
  function stateOf(fp) {
    var e = state.items[fp];
    return (e && e.s) || doc[fp].s;
  }
  function noteOf(fp) {
    var e = state.items[fp];
    return (e && e.n) || '';
  }
  /* An entry that says nothing the document does not already say is removed
     rather than stored, so the diff stays the difference. */
  function tidy(fp) {
    var e = state.items[fp];
    if (!e) return;
    if (e.s === doc[fp].s) delete e.s;
    if (!e.n) delete e.n;
    if (!e.s && !e.n) delete state.items[fp];
  }
  function changes() {
    var out = [];
    order.forEach(function (fp) {
      var was = doc[fp].s, now = stateOf(fp), note = noteOf(fp);
      if (was !== now || note) out.push({ fp: fp, was: was, now: now, note: note });
    });
    return out;
  }

  function toggle(fp) {
    /* Obsolete is a statement the document makes, not progress to record. */
    if (doc[fp].s === 'obsolete') return;
    entry(fp).s = (stateOf(fp) === 'done') ? 'open' : 'done';
    tidy(fp);
    save();
    paint();
  }
  /* The person's own statements beyond the tick (6.26): n/a and deferred.
     Pressing the active one takes the statement back. */
  function setState(fp, which) {
    if (doc[fp].s === 'obsolete') return;
    entry(fp).s = (stateOf(fp) === which) ? 'open' : which;
    tidy(fp);
    save();
    paint();
  }

  function fill(tpl, values) {
    return String(tpl || '').replace(/\{(\w+)\}/g, function (whole, key) {
      return Object.prototype.hasOwnProperty.call(values, key) ? values[key] : whole;
    });
  }
  function text(el, value) { if (el) el.textContent = value; }

  var body = document.body;
  var main = document.querySelector('main');
  var overview = document.getElementById('ck-overview');
  var handbackBlock = document.getElementById('ck-handback');
  var shown = document.getElementById('ck-shown');
  var changedOut = document.getElementById('ck-changed');
  var emptyNote = document.getElementById('ck-unchanged');
  var filterButtons = [].slice.call(
    document.querySelectorAll('.ck-filters [data-filter]'));
  var filter = 'all';

  function rowOf(fp) { return document.querySelector('[data-check-row="' + fp + '"]'); }
  function fieldOf(fp) { return document.querySelector('[id="ck-' + fp + '-note"]'); }

  function paint() {
    var counts = { open: 0, done: 0, obsolete: 0, na: 0, deferred: 0 };
    order.forEach(function (fp) {
      var st = stateOf(fp);
      counts[st] += 1;
      var row = rowOf(fp);
      if (!row) return;
      row.setAttribute('data-state', st);
      var tick = row.querySelector('.ck-tick');
      if (tick) tick.setAttribute('aria-pressed', st === 'done' ? 'true' : 'false');
      /* The state tag (attention inversion, 6.26): visible on the person's
         statements, quiet otherwise. Words come from the row's attributes —
         the script never invents display text (11.2). */
      var mark = row.querySelector('.ck-state');
      if (mark && doc[fp].s !== 'obsolete') {
        var word = (st === 'na' || st === 'deferred')
          ? row.getAttribute('data-word-' + st) : '';
        mark.textContent = word || '';
        mark.hidden = !word;
      }
      [].slice.call(row.querySelectorAll('[data-set]')).forEach(function (b) {
        b.setAttribute('aria-pressed',
                       b.getAttribute('data-set') === st ? 'true' : 'false');
      });
      var field = fieldOf(fp);
      var note = noteOf(fp);
      if (field && field.value !== note && document.activeElement !== field) {
        field.value = note;
      }
      if (note) openNote(fp, true);
    });

    /* n/a is an affirmative answer: it counts as handled. Deferred is open
       work the person postponed: it stays in the denominator, unfilled. */
    var counted = counts.open + counts.done + counts.na + counts.deferred;
    var handled = counts.done + counts.na;
    var bar = document.querySelector('.progress .meter');
    var label = fill(main && main.getAttribute('data-progress'),
                     { done: handled, total: counted });
    if (bar) {
      var meter = bar.querySelector('i');
      if (meter) meter.style.width = (counted ? handled / counted * 100 : 0)
        .toFixed(1) + '%';
      bar.setAttribute('aria-valuenow', String(handled));
      bar.setAttribute('aria-valuemax', String(counted));
      bar.setAttribute('aria-label', label);
    }
    text(document.querySelector('.progress .right'), label);

    filterButtons.forEach(function (b) {
      var which = b.getAttribute('data-filter');
      b.setAttribute('aria-pressed', which === filter ? 'true' : 'false');
      var base = b.getAttribute('data-label');
      b.textContent = which === 'all' ? base : base + ' (' + counts[which] + ')';
    });
    var visible = filter === 'all' ? order.length : counts[filter];
    if (shown) {
      text(shown, fill(shown.getAttribute('data-template'),
                       { shown: visible, total: order.length }));
    }
    paintOverview(counts, counted);
    var moved = changes();
    if (changedOut) {
      text(changedOut, fill(changedOut.getAttribute('data-template'),
                            { n: moved.length }));
    }
    if (emptyNote) emptyNote.hidden = moved.length > 0;
    if (handbackBlock) handbackBlock.textContent = handback(moved, counts);
  }

  /* The derived overview moves with the list. Leaving it at the document's
     numbers would put two different answers to the same question on one
     screen — the focus card's ratio against the progress bar's. */
  function paintOverview(counts, counted) {
    if (!overview) return;
    var handled = counts.done + counts.na;
    var pct = counted ? handled / counted * 100 : 0;
    var tone = pct < 34 ? ' crit' : (pct < 67 ? ' warn' : '');

    var row = document.querySelector('.focus .meter-row');
    if (row) {
      text(row.querySelector('.name'),
           fill(overview.getAttribute('data-progress'),
                { done: handled, total: counted }));
      var meter = row.querySelector('.meter');
      if (meter) {
        meter.className = 'meter' + tone;
        var bar = meter.querySelector('i');
        if (bar) bar.style.width = pct.toFixed(1) + '%';
      }
      text(row.querySelector('.pct'), Math.round(pct) + ' %');
    }

    if (overview.getAttribute('data-focus') === 'ratio') {
      var focus = document.querySelector('.focus');
      text(focus && focus.querySelector('.value'),
           fill(overview.getAttribute('data-focus-ratio'),
                { done: handled, total: counted }));
      if (focus) {
        focus.className = 'focus' + (tone ? ' focus--' + tone.trim() : '');
      }
    }

    /* Deferred is still work: it stays in the open tile, so "later" can
       never quietly improve the numbers (11.6). */
    var openTile = overview.querySelector('[data-tile="open"] .value');
    if (openTile) openTile.textContent = String(counts.open + counts.deferred);
    var doneTile = overview.querySelector('[data-tile="done"]');
    if (doneTile) {
      text(doneTile.querySelector('.value'), String(handled));
      text(doneTile.querySelector('.sub'),
           fill(overview.getAttribute('data-share'), { pct: Math.round(pct) }));
    }

    var next = document.getElementById('ck-next');
    if (next) {
      var pick = nextOpen();
      if (pick) next.textContent = doc[pick].t;
      else next.innerHTML = '<em>' + next.getAttribute('data-none') + '</em>';
    }

    var template = overview.getAttribute('data-group-open');
    [].slice.call(document.querySelectorAll('.ck-group[data-group]')).forEach(
      function (section) {
        var name = section.getAttribute('data-group'), still = 0;
        order.forEach(function (fp) {
          var st = stateOf(fp);
          if (doc[fp].g === name && (st === 'open' || st === 'deferred')) still += 1;
        });
        var mark = section.querySelector('.section-head .badge');
        if (!mark) return;
        mark.textContent = fill(template, { n: still });
        mark.className = 'badge badge--' + (still ? 'warn' : 'good');
      });
  }

  /* The earliest due date wins, then document order — the same rule the
     renderer used, so the two can never name different items. */
  function nextOpen() {
    var dated = null, plain = null;
    order.forEach(function (fp) {
      if (stateOf(fp) !== 'open') return;
      if (doc[fp].due) {
        if (!dated || doc[fp].due < doc[dated].due) dated = fp;
      } else if (!plain) {
        plain = fp;
      }
    });
    return dated || plain;
  }

  function setFilter(which) {
    filter = which;
    if (which === 'all') body.removeAttribute('data-filter');
    else body.setAttribute('data-filter', which);
    paint();
  }

  function openNote(fp, on) {
    var wrap = document.getElementById('ck-' + fp + '-note-wrap');
    var row = rowOf(fp);
    var btn = row && row.querySelector('[data-note-open]');
    if (!wrap || !btn) return;
    wrap.hidden = !on;
    btn.setAttribute('aria-expanded', on ? 'true' : 'false');
  }

  /* The hand-back grammar is a protocol, not interface text — see
     docs/handback.md. Only the marker is configurable. */
  function flat(value) { return String(value).replace(/\s*\n+\s*/g, ' / '); }

  function handback(moved, counts) {
    var lines = [];
    lines.push('### ' + data.marker);
    lines.push('source: ' + data.source);
    lines.push('title: ' + data.title);
    lines.push('based-on: ' + data.basedOn);
    /* n/a counts as handled ("done" in the ratio); deferred does not — the
       per-item `~` lines below carry the exact states either way. */
    lines.push('status: ' + (counts.done + counts.na) + ' of '
               + (counts.open + counts.done + counts.na + counts.deferred)
               + ' done · ' + moved.length + ' changed here');
    var group = null;
    moved.forEach(function (c) {
      var g = doc[c.fp].g;
      if (g !== group) {
        group = g;
        if (g) { lines.push(''); lines.push('## ' + g); }
      }
      lines.push('[' + c.fp + '] ' + doc[c.fp].t);
      if (c.was !== c.now) lines.push('~ ' + c.was + ' → ' + c.now);
      if (c.note) lines.push('+ note: ' + flat(c.note));
    });
    lines.push('');
    lines.push('## Full state (control)');
    order.forEach(function (fp) {
      var st = stateOf(fp), label = doc[fp].t;
      lines.push('[' + fp + '] ' + (st === 'obsolete' ? '~~' + label + '~~'
                                    : st === 'na' ? 'n/a ' + label
                                    : st === 'deferred' ? '☐ ' + label + ' (later)'
                                    : (st === 'done' ? '☑ ' : '☐ ') + label));
    });
    lines.push('');
    lines.push('### END ' + data.marker);
    return lines.join('\n');
  }

  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target : null;
    if (!t) return;
    var tick = t.closest('.ck-tick');
    if (tick) { toggle(tick.getAttribute('data-check')); return; }
    var set = t.closest('[data-set]');
    if (set) { setState(set.getAttribute('data-for'),
                        set.getAttribute('data-set')); return; }
    var pick = t.closest('.ck-filters [data-filter]');
    if (pick) { setFilter(pick.getAttribute('data-filter')); return; }
    var opener = t.closest('[data-note-open]');
    if (opener) {
      var fp = opener.getAttribute('data-note-open');
      var wrap = document.getElementById('ck-' + fp + '-note-wrap');
      openNote(fp, wrap.hidden);
      if (!wrap.hidden) {
        var field = wrap.querySelector('textarea');
        if (field) field.focus();
      }
      return;
    }
    if (t.closest('#ck-copy')) {
      Handback.copy(handbackBlock ? handbackBlock.textContent : '', null);
    }
  });

  /* Typed text is committed as it is typed and again on the way out (11.6). */
  document.addEventListener('input', function (e) {
    var field = e.target.closest ? e.target.closest('.ck-row textarea') : null;
    if (!field) return;
    var fp = field.id.slice(3, field.id.length - 5);
    entry(fp).n = field.value.trim();
    tidy(fp);
    save();
    paint();
  });
  window.addEventListener('beforeunload', save);

  var nostore = document.getElementById('ck-nostore');
  if (nostore && !store.persistent) nostore.hidden = false;
  paint();
})();
"""
