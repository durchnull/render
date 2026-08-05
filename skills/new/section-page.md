# The section page — one output, the project's own design

Scaffolded by `scaffold.py --new-page <id> --section <sid> …` (id: lowercase
letters only). What the scaffold leaves deliberately unfinished is yours:

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
