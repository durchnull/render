# Changelog

All notable changes to the `render` plugin are recorded here. The
project follows [Semantic Versioning](https://semver.org) and
[Keep a Changelog](https://keepachangelog.com).

`render` is pre-1.0: as long as the major version is `0`, the page
and section contracts (including the timeline status values), the
`STRINGS` schema and the command surface may change in a minor release.

## [0.1.0] — 2026-08-05

First release.

### Pages and the engine

- Incremental renderer for self-contained single-file pages: a project
  declares any number of pages, each its own design — every subpackage of
  `.render/pages/` is one page, its `__init__.py` the shell
  (`TITLE`, hero, footer, strings, `SECTIONS`), its sibling modules the
  sections. Each page renders to `<out dir>/<id>.html`; the jump bar
  appears automatically on pages with two or more sections.
- **The index page.** Every run also writes `<out dir>/index.html`: one
  card per rendered output, linking to it, with the page's title, its
  `DESCRIPTION` and a few facts about what is inside. Nothing declares it
  and nothing registers with it — the cards live in the cache manifest
  keyed by output ref, so a `--page` run refreshes what it touched and
  carries the rest over, and a card survives exactly as long as its file
  does (pruned, deleted, or removed by hand — one rule for all three). A
  kind describes its own instances through the optional `summary()` hook;
  both shipped kinds implement it. `INDEX = False` switches the page off,
  `INDEX_FILENAME` renames it, and a page of the project's own that
  already writes `index.html` keeps the name.
- Per-section fragment cache keyed per page (invalidation via content
  hashes, `VOLATILE` sections once per day);
  `--page`/`--status`/`--all`/`--only`/`--preview`, with `--only` and
  `--preview` taking qualified `PAGE/SID` references.
- Project config directory discovery (`--config-dir` →
  `RENDERER_CONFIG_DIR` → `<project>/.render/`); without a hit the
  PostToolUse hook is a silent no-op via `--if-configured`.
- **A project is told when its copies of the plugin's files fall behind.**
  Every run compares them against the installation and prints one line —
  `.render/ has 1 plugin-owned file that does not match render 0.1.0 —
  /render:init refreshes it` — naming the version it is running, which the
  engine reads from its own manifest, and a count it derives from the files
  themselves. Nothing here is taken on trust: no stamp records which release
  last wrote them, because a stamp can be wrong and a byte comparison cannot.
  A release that changes none of them says nothing; a file the project never
  had is filled in by a refresh rather than reported, because absence can be
  a choice and a stale copy cannot. The note survives the hook's quiet run —
  the only render most projects ever trigger — on any run that also rendered,
  aborted or failed something.
- `--check`: deterministic checks for section structure, self-containment
  (no external resources) and token fidelity of colors, across every page.
- **`--check` reports a section page that does not describe itself.**
  `DESCRIPTION` is read in exactly one place — the card the index page gives
  a page — and that card is all anyone sees before opening it. Leaving the
  field out therefore costs nothing at render time and produces a bare card
  that passes every structural assertion, which is how a project ends up with
  an index that lists its pages without saying what any of them are for. A
  missing or blank one is a finding, named per page.

  It stays a finding rather than a refusal: the page itself is fine, only
  its card is not. Kind pages are never asked for one — their cards are
  written per instance by the kind's `summary()` hook, so the page-level
  field is never read. Nor is a project that has switched the index off with
  `INDEX = False`: with no card to feed, the field feeds nothing.
- **Spec errors abort, build crashes degrade.** A section that raises falls
  back to its cached fragment. A data file that fails its kind's validation
  is a hard stop for **that instance**: every finding is reported, nothing
  is written, the run exits non-zero — while the other instances and every
  other page still render. Rendering a broken page is worse than rendering
  none.
- `check()` is flavour-aware: the section and jump-bar assertions run for
  section pages, a kind contributes its own for kind pages, and
  `check_page()`'s generic half runs for everything.
- **The markdown renderer covers what a written document actually
  contains** — headings, lists, tables, quotes and paragraphs, plus fenced
  code blocks and nested lists. Fences are literal (escaped, never inlined,
  language kept as a class); lists nest by indentation and carry wrapped
  text and indented fences inside an item; a numbered list after a bulleted
  one starts a new list; two trailing spaces break a line. Every page that
  renders markdown has this — checklist details and questionnaire context
  passages included.
- The engine never writes `__pycache__` — not into the plugin, not into the
  consuming project. Besides the litter, CPython invalidates bytecode by
  (whole-second mtime, size), so an edit landing in the same second without
  changing the file's size could be executed from stale bytecode while the
  cache key had already moved on.
- `engine/page_api.py` — the **only stable interface** for standalone
  page scripts built in `.render/` on top of the plugin.
  Re-exports the design system and the content core, and adds
  `page_shell()` (complete self-contained page with the standard shell)
  and `check_page()` (the same deterministic self-containment/design
  checks as `render.py --check`, as a library function).
- All visible engine texts default to English and are fully translatable
  via `STRINGS` — project-wide defaults in `config.py`, per-page
  overrides on the page, merged per page; timeline status API
  `confirmed | assumed | planned | open | deadline`.

### Page kinds and families

- **Page kinds.** A page may declare `KIND = "<name>"` instead of
  `SECTIONS` and let a kind module build it from a data file. Kinds are
  resolved from `engine/kinds/<name>.py` first, then the consuming
  project's own `kinds/<name>.py`; they are imported, never copied, so a
  page receives behaviour fixes with a plugin update. The contract is the
  docstring of `engine/kinds/__init__.py`.
- **Page families.** With `SOURCES = "<glob>"` a kind page renders **one
  output per matching file**. The glob is the lifecycle — a source that
  leaves it takes its output with it on the next `--prune`, so nothing is
  scaffolded or deleted per instance. Instances are addressed as
  `<page>:<stem>` by `--page` and `--only`, appear in `--status`, and are
  cached per instance (spec content + kind code + shared code). `FILENAME`
  becomes a template with `{stem}` and `{pid}`. An empty glob renders
  nothing and says so.
- **`--prune`** — deletes outputs whose source file is gone. Only files the
  manifest recorded are ever considered, and only for pages the run
  actually enumerated; without the flag they are reported, not touched.
- A kind's `load()` hook takes the build context as a second argument, so a
  kind whose source can leave a value to the project resolves that chain
  while reading rather than after.
- `BuildContext.setting()` gives a kind the page → `config.py` → default
  chain that `LANG` and `FAVICON_HREF` follow, without importing the
  consuming project's config itself.
- **`VOLATILE` for kind instances**, on the kind or on the page — today's
  date folds into the instance cache key, so a page showing "5 days until
  the deadline" is not served from yesterday's cache.

### The two shipped kinds

- **The `questionnaire` kind** — one JSON spec becomes one self-contained,
  offline, three-screen questionnaire. "I don't know" and "skip" are
  first-class answer states, a free-text note is reachable on every
  question, nothing is mandatory and nothing blocks the hand-back.
  Conditional questions via `show-if`, auto-advance on single-select only
  (suppressed under `prefers-reduced-motion` and while a note is open),
  full keyboard operation, resume by default, and a summary screen that is
  the editor rather than a report. Markdown is rendered at build time; the
  client never builds markup from a string.
- **The `checklist` kind** — one markdown document the project already
  maintains becomes one interactive view of itself. The opposite data flow
  to the questionnaire: the file stays the truth, the page is an editable
  view of it, and what comes back is the **diff**, which the project's own
  skill applies. The plugin never writes to the source document.
  The parser keeps a real file readable: paragraphs between item blocks,
  subheads inside a group and bold-only lines all render where they stand;
  groups are optional, so a document that never writes a `##` — and the run
  of items before the first `##` in one that does — renders as one unnamed
  section rather than a group the file never named;
  a `-` line without a checkbox is prose and is counted as nothing;
  `path:` and `due:` are annotations while any other indented key is that
  person's detail rather than an error. Item state is a closed set of
  three, where `obsolete` is written as a strikethrough whatever the
  checkbox says, stays on the page as part of the record, and counts in
  neither half of the ratio. Three filter buttons, a derived overview that
  moves with the list, and a page that reads top to bottom with scripting
  off.
- **A checklist document may show a checklist.** Fenced blocks are text to
  the parser: they contribute no items, no groups and no headings, so a
  `- [ ]` inside a fenced sample is never counted in the progress meter nor
  offered on the page as something to tick, and a `##` in a sample opens no
  group. Both reach the page as the code they are.
- **Checklist items carry their source line.** The kind's parser records
  where each checkbox sits in the file — invisible in the rendered output,
  and what makes an exact edit plan possible when the page comes back.
- **`exclude`** — a list of prefixes in a document's frontmatter that keeps
  a block off the page while it stays in the file, per item and per
  paragraph rather than per section. The order is parse → exclude →
  fingerprint → render, count, so an excluded block consumes no id, appears
  in no total and can never surface in a hand-back; `--check` asserts it.
  Resolves document → page → `config.py`, and the default is empty.

### Talking back to an agent

- **The hand-back block as a plugin-level contract** —
  [docs/handback.md](docs/handback.md) carries the grammar and a worked
  sample. Line-oriented, stable, marker configurable per document; how any
  generated page talks back to an agent, not questionnaire-specific.
- Two hand-back *shapes* at grammar version 2: the answers shape, and a
  shape for pages that mirror a document — `~ old → new`, `+ note:` /
  `- note:`, a reserved `## Full state (control)` listing, and
  `based-on:`, the source fingerprint that lets an agent notice the file
  moved while somebody had the page open.
- **`scripts/handback.py` — the grammar's reference parser, shipped rather
  than described.** Pipe the pasted block in (the marker is auto-detected
  inside a longer message, line endings and trailing whitespace are
  normalized) and read a compact report or `--json` back. A truncated or
  missing block is a named refusal, never a traceback. With
  `--source <file>` a checklist **changes** block becomes an edit plan: the
  `based-on:` drift check first (a mismatch is exit 3 and no plan), then one
  exact line edit per state change, ready to apply verbatim — while notes,
  cleared notes and anything editorial land under `judgment:`, deliberately
  unapplied. The script never writes to anybody's document; there is no
  `--apply` and never will be. The worked sample in `docs/handback.md` is
  the CLI's test fixture, so the documentation and the parser are executed
  against each other.
- **`content_core.fingerprint()`** — six hex characters naming a piece of
  text by its content, with inline markup stripped and whitespace
  collapsed, plus extra parts for resolving a collision. Re-exported
  through `page_api` with its companion `strip_inline()`.
- **Content-addressed browser state.** `Store.make(ns, { keys, bucket })`
  drops entries whose key is no longer in the document on every read, so a
  page whose source was edited keeps everything whose text is still there
  and forgets exactly what changed — rather than expiring the lot because
  somebody fixed a typo. Written up as `design-manual.md` 11.7.

### Design system

- Design system as an executable manual: `TOKENS` + `BASE_CSS` +
  component helpers (tiles, focus card, badges, meters, share bars,
  sparkline, timeline with lanes, detail modal), verified light/dark
  color steps, `design-manual.md` as the binding rule base.
- **A component catalog.** `design-manual.md` is the core — principles,
  tokens, hierarchy, page structure, and an index of every component with
  its helper and its reference file. The component and behaviour reference
  lives beside it in `docs/design/` (`components.md`, `chrome.md`,
  `charts.md`, `interactive.md`, `longform.md`), read per page flavour
  instead of wholesale; a test holds catalog, files and `page_api`
  together.
- **`EXTRA_CSS`** on the page shell (page → `config.py` → empty), appended
  after `BASE_CSS` — the same hook `page_shell(extra_css=…)` gives
  standalone renderers. `check_page()`'s "hex colors only in the token
  blocks" rule applies to it unchanged.
- **Interactive page tier**, all opt-in through `EXTRA_CSS` so no dashboard
  carries it: `FORM_CSS` and `APP_CSS`, the components `option_row`,
  `field`, `text_field`, `amount_field`, `progress_bar`, `action_bar`,
  `toast`, `summary_row`, and the JS kits `TOAST_JS`, `STATE_JS`
  (namespaced `localStorage` with an in-memory fallback) and `HANDBACK_JS`
  (clipboard with an `execCommand` fallback and an always-selectable
  block). All re-exported from `page_api`, all in the component gallery,
  all documented in `design-manual.md` 6b.
- **A long-form tier** (`ARTICLE_CSS`, `design-manual.md` 11b), opt-in
  exactly like `FORM_CSS`/`APP_CSS`: a 720-pixel reading column,
  `--fs-read`/`--fs-lede` type, a masthead (`article_head`), a pull quote
  (`pull_quote`) and a source list (`source_list`). A page that reports
  numbers carries none of it. Everything else — colors, spacing, code
  blocks, dark mode — stays the tokens every other page uses.

  Links are the one thing the flavour has to solve: a self-contained page
  fetches nothing, so an external link becomes its label plus a reference
  number resolved at the foot, a link into the project keeps its label, and
  a URL inside a code sample loses its scheme and nothing else.
- **`check_row()`** (`design-manual.md` 6.26) — one instruction from a
  maintained document: a tick that is the only control changing its state,
  a note reachable whatever that state is, and `obsolete` rendered as a
  statement the document makes rather than progress the reader records.
- `APP_CSS` hides the progress bar, action bar and toast under
  `@media print`: a printed interactive page is its content, never its
  controls.
- `design-manual.md` section **11, Interactive pages**: a second page
  flavour with three permitted script purposes, content in the document
  rather than assembled in the browser, private state the page states in
  its own footer, nothing mandatory, and keyboard/focus rules. Section 6.16
  binds display pages to their two purposes. Section 11.6 carries the rule
  the checklist forced: every derived number on an interactive page is
  recomputed together, and filtering changes what is shown but never what
  is counted.

### Skills, docs and tests

- `/render:init` creates the starter scaffold from `templates/` in
  the project: config, an example page, a thin `render.py` entry point,
  and `engine_locator.py` (resolves the installed engine via
  `RENDER_ENGINE` → `CLAUDE_PLUGIN_ROOT` → `~/.claude/plugins` —
  the engine is imported, never copied).
- **The same command keeps a configured project current.** Four files in
  `.render/` belong to the plugin rather than the project —
  `engine_locator.py`, `render.py`, `README.md` and `pages/__init__.py` —
  and each says so in its own header; because the engine is imported, they
  are the only things a plugin update cannot reach on its own. Run in a
  configured project, `/render:init` replaces those four whenever they
  differ from the installation, creates any that are missing, and leaves
  `config.py`, `content.py`, `kinds/` and everything under `pages/<id>/`
  untouched. `engine/scaffold.py` owns that split and runs on its own with
  `--check` to report without writing.
- **`scaffold.py` write modes — boilerplate is emitted, not typed.**
  `--fresh` writes the full first scaffold in one command; `--new-page ID
  --kind K --sources GLOB` the three-line kind page; `--new-page ID
  --section SID …` a section page whose stubs raise until they render
  something real; `--standalone NAME` the runnable `page_api` skeleton.
  Everything these modes write is the project's from the first byte —
  never refreshed, never overwritten, never in `PLUGIN_OWNED`.
- `/render:new` adds a page: a declared page under `pages/` by
  default (rendered, cached and checked by the engine like every other),
  or a standalone `page_api` script for output the engine cannot own —
  with prohibitions (never copy or edit the engine, no custom hex values,
  output stays self-contained).
- **`/render:article` — one markdown document, one page made to be read.**
  A person asks, once, and gets a single self-contained page: no `.render/`
  needed, no cache, no hook, no index card. It takes a file, or captures
  the last thing that was said in the conversation and keeps the markdown
  next to the page so it can be rendered again after an update.
  `scripts/article.py` does the rendering and is a standalone renderer on
  `page_api` — the same public interface a project's own page scripts use.
- `/render:questionnaire` and `/render:checklist` — the agent-side loops:
  scaffold, author or render, then apply what comes back through
  `handback.py` rather than by eye. Reading the fingerprint out of the
  output, mapping ids to lines and cross-checking the control listing are
  the script's work; what stays with the agent is the judgment — drift is a
  stop sign, and notes are routed rather than applied.
- **`allowed-tools` on every skill** — the tools each skill actually uses
  are pre-approved for the invoking turn, so a render loop is not a chain
  of permission prompts.
- `docs/spec-checklist.md` and `docs/spec-questionnaire.md` — the deep
  reference for authoring a kind's data file, opened when a validator
  finding or an advanced field needs it. Both kind skills carry a short
  inline cheat-sheet and otherwise lean on the validator's
  all-findings-at-once output.
- Two runnable example projects — one questionnaire, one checklist whose
  fixture is deliberately messy: every awkward shape a real maintained
  document grows, plus one file that exists to be refused.
- `tests/run.py` (standard library only), wired into CI along with both
  example projects.
- `evals/` — four agent-side cases for the hand-back loops, the half no
  test can reach: the checklist diff applied, the same diff refused as
  drift, a filled questionnaire read back with its four states intact,
  and one case that must not fire at all. Every fixture is real input —
  the blocks parse against their own scaffolded documents. Running them
  costs money, so CI never does; `evals/README.md` has the flags.
