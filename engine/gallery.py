#!/usr/bin/env python3
"""Component gallery — every design-system helper rendered beside its call.

The snippets are the source: each sample is a Python expression string that
is evaluated against ``design_system``, so the shown code and the shown
result can never drift apart. Deterministic by construction — fixed sample
dates, no clock, no randomness — so rerunning writes byte-identical output.

Usage:
    gallery.py [-o design-gallery.html]

Regenerate after any change to ``design_system.py`` (design-manual.md, 9)
and check the result in light and dark mode.
"""

import argparse
import html
import sys
from datetime import date  # noqa: F401 — available inside the sample snippets
from pathlib import Path

# Same deliberate choice as render.py: no stale bytecode beside the source.
sys.dont_write_bytecode = True

sys.path.insert(0, str(Path(__file__).resolve().parent))

import design_system as ds  # noqa: E402

# (expr, bare) — bare samples already draw their own surface (card, tile …);
# the rest render on a neutral stage so they sit on "card ground" as designed.
GROUPS = [
    ("Badges, deltas, status marks — 6.2 / 6.15", [
        ("badge('documented', 'good', icon='✓')", False),
        ("badge('due soon', 'warn', icon='⚠')", False),
        ("badge('deadline missed', 'crit', icon='✕')", False),
        ("badge('to review', 'accent')", False),
        ("badge('12 entries')", False),
        ("delta('12 % vs. June', 'up')", False),
        ("delta('4 % vs. June', 'down')", False),
        ("status_marks('done ✅ · level 🟢 · assumption 🟡 · unknown ❓ · attention ⚠')",
         False),
    ]),
    ("Chips, tags, crumbs — 6.3 / 6.3b", [
        ("\"<span class='chip'>reporting period 2025</span> \""
         "\"<span class='chip'><span class='dot'></span> next deadline 31.07.2026</span>\"",
         False),
        ("\"<span class='tag'>8 entries</span>\"", False),
        ("crumbs('Settings › Accounts › Approvals', note='unconfirmed')", False),
    ]),
    ("Buttons — 6.4", [
        ("\"<button class='btn'>Secondary</button> \""
         "\"<button class='btn btn--primary'>Primary</button> \""
         "\"<button class='btn btn--ghost'>Ghost</button>\"", False),
        ("\"A control in body text is a <button class='btn-link'>btn-link</button>, "
         "not an anchor without a destination.\"", False),
    ]),
    ("Section furniture — 6.0 / 6.0b", [
        ("eyebrow('Figures', num='02')", False),
        ("section_head('Project file 2025', 'Checklist, open items and master data',"
         " num='02', kicker='Figures', right=badge('29 open', 'warn', icon='⚠'))", False),
        ("subhead('Open items', sub='8 folders without a receipt')", False),
    ]),
    ("Card shell — 6.18", [
        ("card(list_row('Working tree', badge('clean', 'good', icon='✓'))\n"
         "     + list_row('Unpublished commits', '5', sub='no upstream yet'),\n"
         "     title='Repo state', sub='measured at render time',\n"
         "     right=\"<span class='tag'>2 facts</span>\",\n"
         "     foot_left='Full audit: /audit', foot_right='As of 26.07.2026')", True),
    ]),
    ("Focus card and KPI tiles — 6.0c / 6.1", [
        ("focus_card('5', 'Days until the filing deadline',\n"
         "           sub='Deadline 31.07.2026 — the date is binding', kind='crit',\n"
         "           chip=badge('urgent', 'crit', icon='⚠'),\n"
         "           aside=[('Next step · Priority 0', 'Sort the receipts folder'),\n"
         "                  ('Checklist progress', meter_row('2 of 31 done', 6, kind='crit'))])",
         True),
        ("tile('Days until the filing deadline', '5',\n"
         "     sub='Deadline 31.07.2026 — binding', chip=badge('due soon', 'warn', icon='⚠'))",
         True),
        ("tile('Revenue', '4.520', sub='last 12 weeks',\n"
         "     spark=sparkline([3, 4, 3, 5, 6, 5, 7, 8, 7, 9, 10, 11], label='Revenue trend'))",
         True),
    ]),
    ("List rows and meters — 6.6 / 6.7", [
        ("list_row('pages', '8 declared', sub='one directory each under pages/')", False),
        ("list_row('Remote', badge('does not resolve', 'crit', icon='✕'),"
         " sub='github.com/example/project')", False),
        ("meter_row('Checklist', 62)", False),
        ("meter_row('Receipts folder', 34, kind='warn')", False),
        ("meter_row('Master data', 6, kind='crit')", False),
    ]),
    ("Tile variants — 6.1", [
        ("tile('Responses', '9', chip=delta('2', 'up'),"
         " trend='Trending up this month', sub='of 34 applications')", False),
        ("tile('Storage used', '1,85 GB', capacity=(18.5, '1.85 of 10 GB'))", False),
        ("tile_group([('Applications', '34', 'sent'), ('Responses', '9', '26 %'),"
         " ('Interviews', '3', 'scheduled')])", False),
    ]),
    ("Ranked bar list and tracker — 6.27 / 6.28", [
        ("bar_list([('Berlin', 4210), ('Hamburg', 2380, '2 portals'),"
         " ('Köln', 990)], unit='€')", False),
        ("(tracker([('good', 'passed')] * 14 + [('crit', '07-15 · failed')]"
         " + [('good', 'passed')] * 9, left='July 1', right='July 24'))", False),
    ]),
    ("Metric-tab hero — 6.29", [
        ("metric_hero([('Applications', '34'), ('Responses', '9', '26 %'),"
         " ('Interviews', '3')],"
         " chart=sparkline([3, 5, 4, 8, 7, 9, 12, 10, 14, 13, 16, 18],"
         " width=520, height=80),"
         " active=1, foot_right='As of 2026-08-18')", True),
    ]),
    ("Filter row and show-all — 6.5 / 6.6", [
        ("(filter_row([('preferred', 'preferred'), ('secondary', 'secondary')],"
         " '#g-filter-demo')\n"
         " + \"<div id='g-filter-demo'>\"\n"
         " + list_row('First entry', badge('preferred'), tags='preferred')\n"
         " + list_row('Second entry', badge('secondary'), tags='secondary')\n"
         " + list_row('Third entry', badge('preferred'), tags='preferred')\n"
         " + '</div>')", False),
        ("show_all([list_row(f'Portal {i}', 'tier 1' if i <= 5 else 'tier 2')\n"
         "          for i in range(1, 11)], limit=4)", False),
    ]),
    ("Share bar, legend, sparkline — 6.8 / 7.2", [
        ("(share_bar([('Rent', 9120), ('Travel', 4210), ('Material', 2380), ('Other', 990)])"
         "\n + legend(['Rent', 'Travel', 'Material', 'Other']))", False),
        ("sparkline([5, 6, 5, 7, 8, 7, 9, 8, 10, 11, 10, 12], label='This period',\n"
         "          compare=[4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10])", False),
    ]),
    ("Rows, tables, banners — 6.9 / 6.11 / 6.12 / 6.14", [
        ("accordion('Checklist — 2025 tax return', '<p>Prioritized to-do list through "
         "filing.</p>',\n          sub='29 items, 2 done', mark='01',\n"
         "          meta='checklist.md · as of 26.07.2026', right=badge('29 open', 'warn'))",
         False),
        ("(\"<div class='table-wrap'><table><thead><tr><th>Date</th>"
         "<th class='num'>Amount</th></tr></thead>\"\n"
         " \"<tbody><tr><td>26.07.2026</td><td class='num'>1.234,56 €</td></tr>\"\n"
         " \"<tr class='total'><td>Total</td><td class='num'>1.234,56 €</td></tr>"
         "</tbody></table></div>\")", False),
        ("\"<div class='banner banner--warn'>⚠ One statement, one sentence, icon first."
         "</div>\"", False),
        ("\"<p class='empty'>no entries — new files go into the intake folder first.</p>\"",
         False),
    ]),
    ("Icons — 6.13", [
        ("' · '.join(f\"{icon(n)} {n}\" for n in\n"
         "           ('check', 'doc', 'folder', 'chat', 'user', 'lock', 'clock', 'flag'))",
         False),
    ]),
    ("Timeline — 7.6", [
        ("(timeline([{'name': 'Income', 'slot': 1, 'meta': '3 events',\n"
         "           'events': [\n"
         "    {'id': 'ev01', 'titel': 'Incoming payment', 'kurz': 'Payment',\n"
         "     'start': date(2025, 3, 4), 'end': None, 'status': 'confirmed'},\n"
         "    {'id': 'ev02', 'titel': 'Project phase', 'kurz': 'Project',\n"
         "     'start': date(2025, 5, 1), 'end': date(2025, 8, 15), 'status': 'assumed'},\n"
         "  ]},\n"
         "  {'name': 'Obligations', 'slot': 2, 'meta': '2 events',\n"
         "   'events': [\n"
         "    {'id': 'ev03', 'titel': 'Open question', 'kurz': 'Open',\n"
         "     'start': date(2025, 6, 10), 'end': date(2025, 7, 20), 'status': 'open'},\n"
         "    {'id': 'ev04', 'titel': 'Filing deadline', 'kurz': 'Deadline',\n"
         "     'start': date(2025, 10, 31), 'end': None, 'status': 'deadline'},\n"
         "  ]}],\n"
         "  date(2025, 1, 1), date(2025, 12, 31), today=date(2025, 7, 1))\n"
         " + timeline_key())", False),
    ]),
    ("Check rows — 6.26", [
        ("(check_row('a3f91c', 'Collect the receipts', state='done',\n"
         "           context=crumbs('Settings › Accounts › Approvals'))\n"
         " + check_row('b1c204', 'Ask about the invoice',\n"
         "             context=badge('due 31.07.2026', 'warn'),\n"
         "             detail='<p>Indented lines under the item render here.</p>')\n"
         " + check_row('d09f31', 'Superseded by the new process', state='obsolete'))",
         False),
    ]),
    ("Input and app chrome — 6.19 / 6.20 / 6.25", [
        ("(option_row('a', 'Yes, in full', hint='everything was recorded', index=0)\n"
         " + option_row('b', 'Partly', index=1, selected=True)\n"
         " + option_row('c', 'Not at all', index=2))", False),
        ("text_field('q07-note', 'What is missing?',\n"
         "           placeholder='one sentence is enough',\n"
         "           hint='free text — for whatever no option covers')", False),
        ("amount_field('q08', 'Roughly how much?', unit='€', placeholder='1200')", False),
        ("(summary_row('01', 'Were the receipts recorded?', answer='Yes, in full',\n"
         "             state='answered')\n"
         " + summary_row('02', 'Which account was it?', note='two are still missing',\n"
         "               state='unclear')\n"
         " + summary_row('03', 'Anything else worth knowing?', state='open'))", False),
    ]),
    ("Progress and actions — 6.22 / 6.23 / 6.24", [
        ("progress_bar(3, 12, left='Section 2 · Records', approx=True)", False),
        ("action_bar(\"<button class='btn btn--ghost'>← Back</button>\",\n"
         "           \"<button class='btn btn--primary'>Next →</button>\")", False),
        ("toast('copied to the clipboard')", False),
    ]),
    ("Long-form furniture — 11b", [
        ("article_head('What the sweep measured',\n"
         "             kicker='Session log', lede='One turn, kept as a page: the "
         "headline comes from the document, the meta line from the file.',\n"
         "             meta=['03.08.2026', '4 min read', 'render'])", True),
        ("pull_quote('Duplication between plugins is correct, not debt.',\n"
         "           cite='CLAUDE.md — plugin isolation')", True),
        ("source_list(['code.claude.com/docs/en/plugins',\n"
         "             'code.claude.com/docs/en/skills'])", True),
    ]),
    ("Detail dialog — 6.17", [
        ("\"<button class='btn' data-ev='ev01'>Open the detail for ev01</button>\"", False),
        # Renders nothing visible by design — the block is display:none until
        # the dialog adopts it; the button above proves it works.
        ("modal_detail('ev01', 'Incoming payment 4.500,00 €', kicker='Income',\n"
         "             when='04.03.2025', badges=badge('documented', 'good', icon='✓'),\n"
         "             body='<p>Hidden block — the dialog adopts it when a "
         "<code>data-ev</code> trigger fires.</p>',\n"
         "             source='Source: <code>bank statement</code>')", True),
    ]),
]

# Page-specific CSS (design-manual.md, 9): tokens only, after BASE_CSS.
# The three positioned app-chrome components are pinned back into their stage —
# a gallery shows them, it does not run them.
GALLERY_CSS = """
.g-stage { background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r-card); box-shadow: var(--shadow); padding: var(--s5) var(--s6); }
.g-sample { margin-bottom: var(--s4); }
.g-sample pre { margin: var(--s2) 0 0; overflow-x: auto; }
.g-stage .actionbar { position: static; padding: var(--s3) 0 0; }
.g-stage .progress { position: static; }
.g-stage .toast { position: static; transform: none; opacity: 1; visibility: visible; }
"""


def build() -> str:
    ns = {**vars(ds), "date": date}
    parts = []
    for i, (title, samples) in enumerate(GROUPS, start=1):
        parts.append("<section>")
        parts.append(ds.section_head(title, num=f"{i:02d}", kicker="Components"))
        for expr, bare in samples:
            rendered = eval(expr, ns)  # noqa: S307 — our own literals above
            stage = rendered if bare else f"<div class='g-stage'>{rendered}</div>"
            parts.append(f"<div class='g-sample'>{stage}"
                         f"<pre><code>{html.escape(expr)}</code></pre></div>")
        parts.append("</section>")

    hero = ("  <header class='hero'><div class='eyebrow'>render · design system</div>"
            "<h1>Component gallery</h1>"
            "<p>Every helper rendered beside the exact snippet that produced it — "
            "generated from <code>design_system.py</code>, so it cannot drift.</p></header>")
    body = ("<div class='wrap'>" + hero + "".join(parts)
            + "<footer>Generated by engine/gallery.py · self-contained HTML, "
              "no external resources</footer></div>"
            + ds.modal_host()
            + f"<script>{ds.MODAL_JS}{ds.FILTER_JS}{ds.SHOWALL_JS}</script>")
    page = ds.page("Design system gallery", body, favicon="🧩")
    # FORM_CSS/APP_CSS/ARTICLE_CSS are opt-in (6b / 11b) — a gallery shows
    # every tier, which is the one page that legitimately opts into all of them.
    return page.replace(
        "</style>", ds.FORM_CSS + ds.APP_CSS + ds.ARTICLE_CSS + GALLERY_CSS + "</style>", 1)


def main() -> int:
    ap = argparse.ArgumentParser(description="Render the component gallery.")
    ap.add_argument("-o", "--out", default="design-gallery.html", metavar="FILE")
    args = ap.parse_args()
    out = Path(args.out)
    out.write_text(build(), encoding="utf-8")
    kb = out.stat().st_size / 1024
    n = sum(len(s) for _, s in GROUPS)
    print(f"OK  {out} · {len(GROUPS)} groups, {n} samples, {kb:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
