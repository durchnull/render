#!/usr/bin/env python3
"""01 Where 1.0 stands — INPUTS: this section renders a document's content.

``INPUTS`` are globs whose **bytes** this section renders. The engine
hashes them, so changing one number in ``docs/status.md`` rebuilds this
fragment and nothing else. The frontmatter carries the numbers the tiles
show and the body carries the narrative: the document stays the single
place a maintainer edits, and the page is a view of it.
"""

import content
from config import ROOT
from page_api import badge, card, delta, tile, tile_group

INPUTS = ["docs/status.md"]
LISTING = []
VOLATILE = False

SOURCE = "docs/status.md"


def build():
    path = ROOT / SOURCE
    if not path.exists():
        # Empty means invisible (design-manual 5): one line, never a card
        # wrapped around nothing.
        return content.wrap(
            "overview",
            f"<p class='empty'>No <code>{SOURCE}</code> yet — this section "
            "renders that document.</p>")

    meta, md = content.read_md(path)
    title, rest = content.split_title(md)

    tiles = "<div class='tiles'>" + tile(
        "Version in flight", meta.get("version", "—"),
        sub=f"Reporting period {meta.get('period', 'unset')}",
        chip=badge(f"next: {meta['next']}", "neutral") if meta.get("next") else "",
    ) + tile(
        "Test suite", f"{meta.get('tests', '—')} tests",
        sub="Runs in under nine seconds, no network, no fixtures on disk",
        chip=delta(f"{meta['tests_added']} this period", "up")
        if meta.get("tests_added") else "",
    ) + tile(
        "Line coverage", f"{meta.get('coverage', '—')} %",
        capacity=(int(meta["coverage"]), "the parser itself is at 99 %")
        if str(meta.get("coverage", "")).isdigit() else None,
        sub="Whole package, branch coverage not enforced",
    ) + tile_group(
        [("Open items", str(meta.get("open", "—"))),
         ("Python versions", str(meta.get("pythons", "—"))),
         ("Dependencies", str(meta.get("deps", "—")))],
        label="Shape",
    ) + "</div>"

    narrative = card(
        content.prose(rest, bool(title)),
        title=title or "Status",
        sub=f"Verbatim from {SOURCE} — edit the document, not the page",
        pad=True,
        foot_left="The frontmatter above feeds the tiles",
        foot_right=f"Period {meta.get('period', 'unset')}",
    )

    return content.wrap("overview", tiles + narrative)
