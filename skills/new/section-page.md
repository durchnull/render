# The section page — one output, the project's own design

Scaffolded by `scaffold.py --new-page <id> --section <sid> …` (id: lowercase
letters only). What the scaffold leaves deliberately unfinished is yours:

## Before any section is written: the content budget

A generated page fails by burying what it is for, not by being ugly — so
settle the editorial decisions before the first line of markup
(design-manual.md 5.1 is the binding form):

1. **Name the question the page is opened to answer**, in one sentence.
   The focus card states the thing to act on ("3 to verify"), not the
   inventory ("19 on the list"), and the first screen must answer that
   question on its own.
2. **Classify every candidate section: living or reference.** Living data
   (what changed since the last visit) comes first; reference material
   (criteria, definitions, standing lists) comes last as closed `.acc`
   rows — or stays in its source document and off the page entirely.
   Content that serves a *different* question belongs on a different page,
   not in another section.
3. **Apply the budget while writing:** every number appears once (tiles
   never restate the focus card); zero items render as one `.empty` line
   or a banner, never a card around nothing; table cells hold atoms with
   the rationale in `.acc` bodies or the detail dialog; lists beyond
   eight rows get `show_all()` or closed accordions, and filters
   (`filter_row()`) stay view-only.
4. **Order like an instrument panel** (Grafana/Carbon doctrine,
   design-manual.md 5.1/5.2): sections run general → specific, one section
   per subsystem in data-flow order; a panel answers **one** question
   ("which servers are in trouble" shows only the troubled ones); the
   overview links down to detail via the detail dialog — the one sanctioned
   exploration affordance. Unlike capacities are normalized to percentages
   before they are compared.
5. **Pick the one opening** (5.2): the focus card by default; the
   metric-tab hero (`metric_hero()`) when the page is about a trend; the
   needs-attention queue when it is an operator's page over live exceptions.
   Ranked breakdowns use `bar_list()`, status-over-time uses `tracker()` —
   a table that only exists to be scanned for the biggest value is the bar
   list's job.

`--check` enforces the mechanical half (empty cards, prose cells); the
ordering and the focus question are yours to get right here.

1. **`DESCRIPTION` is empty until you write it** — one sentence saying what
   the page is for. It is what the index page puts on this page's card, and
   without it the card is a title and a file name; `--check` reports a
   section page that leaves it out.
2. **Every section stub's `build()` raises until it renders something
   real.** The contract is stated in `pages/__init__.py`: declare `INPUTS`
   (globs whose **content** the section renders — any change rebuilds it),
   `LISTING` (globs where only name, size and mtime matter), `VOLATILE`
   (True only when the output depends on today's date), and make `build()`
   return `content.wrap(sid, body)` or `(section, tail)`.
3. The page declaration takes more when needed: `HERO_HTML`/`hero()`,
   `FOOTER_HTML`/`footer(generated)`, `FILENAME`, `LANG`, `STRINGS`,
   `EXTRA_CSS` — unset values fall back to `config.py`. The jump bar
   appears automatically on pages with two or more sections.

**Read `${CLAUDE_PLUGIN_ROOT}/design-manual.md` before writing any markup**
— colors, typography and components come exclusively from the engine's
design system (`TOKENS` + `BASE_CSS`); no custom hex values, ever. Then pick
the components from the catalog in its §6 and **read the listed
`${CLAUDE_PLUGIN_ROOT}/docs/design/` reference file for every helper you
call** — the catalog is an index, not a spec.

Render and verify — the engine discovers the new folder on its own:

```bash
python3 .render/render.py --page <id>
python3 .render/render.py --check
```

From then on the plugin's PostToolUse hook keeps the page fresh after every
Write/Edit, like every other page, and `output/index.html` gains a card for
it — nothing to register.
