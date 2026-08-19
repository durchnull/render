#!/usr/bin/env python3
"""02 What is left — INPUTS again, but the source is data, not prose.

Same contract as ``overview``: the file's content is hashed, so adding an
item to ``docs/work.json`` rebuilds this section alone. What the section
adds is the two view-only interactions from the manual — a filter row over
tagged rows (6.5) and truncation behind a show-all trigger (6.6). Both are
enhancements: with scripting off every pill is inert, the trigger hides
itself, and all eleven rows stay on the page and in print.
"""

import json

import content
from config import ROOT
from page_api import badge, card, filter_row, list_row, show_all

INPUTS = ["docs/work.json"]
LISTING = []
VOLATILE = False

SOURCE = "docs/work.json"

#: Item state → badge kind. A state the file invents renders neutral
#: rather than breaking the page.
_KIND = {"in progress": "warn", "blocked": "crit", "ready": "neutral"}


def build():
    path = ROOT / SOURCE
    if not path.exists():
        return content.wrap(
            "work",
            f"<p class='empty'>No <code>{SOURCE}</code> yet — this section "
            "renders the items in it.</p>")

    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    if not items:
        return content.wrap(
            "work", "<p class='empty'>Nothing open — the milestone is clear.</p>")

    # Areas come from the data, so a new area needs no code change.
    areas = sorted({item["area"] for item in items})
    rows = [
        list_row(item["title"],
                 badge(item["state"], _KIND.get(item["state"], "neutral")),
                 sub=item.get("note", ""),
                 tags=item["area"])
        for item in items
    ]

    blocked = sum(1 for item in items if item["state"] == "blocked")
    body = card(
        filter_row([(area, area.capitalize()) for area in areas], "#work-items")
        + f"<div id='work-items'>{show_all(rows)}</div>",
        title=f"Open before {data.get('milestone', 'the next release')}",
        sub=f"{len(items)} items across {len(areas)} areas · "
            "the filter is a view, it changes nothing",
        right=badge(f"{blocked} blocked", "crit") if blocked else "",
        foot_left="Ordered as the file orders them — the file is the backlog",
        foot_right=f"As of {data.get('updated', 'unset')}",
    )
    return content.wrap("work", body)
