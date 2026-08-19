# The project contract

What a project provides so the renderer can render it. `/render:init`
creates all of it; this document is the reference for what it created,
what each file is for, and what you may declare in it.

Everything lives in one directory — `.render/` inside the project —
and nothing is registered anywhere else. The engine discovers what is
there.

## The directory

| File | Required | Content |
|---|---|---|
| `config.py` | yes | project-wide: `ROOT` — plus optional defaults every page inherits |
| `pages/__init__.py` | yes | package marker carrying the page/section contract |
| `pages/<id>/__init__.py` | one per page | the page: `TITLE` plus either `SECTIONS` or `KIND`, optional shell |
| `pages/<id>/<sid>.py` | one per section | section modules, siblings of the page's `__init__.py` |
| `kinds/<name>.py` | optional | the project's own page kind, when the plugin ships none that fits |
| `content.py` | recommended | `from content_core import *` + the project's own gather helpers |

Every subpackage of `pages/` is one page. Page ids are lowercase letters
only. The fragment cache (`.cache/`) and `--preview` pages are written
next to the output, so everything generated sits under the configuration
directory and can be ignored or deleted as one unit. `<out dir>` is
`config.OUT_DIR` or `.render/output/`.

## The two page flavours

A page declares **either** `SECTIONS` **or** `KIND`, never both.

### Section page

The page assembles its own markup and renders one output at
`<out dir>/<id>.html`.

`SECTIONS` is a list of `(id, number, kicker, title, subline, nav label)`
in display order; the jump bar appears automatically from two sections
on. Each section module (`pages/<id>/<sid>.py`) declares:

- `INPUTS` — globs whose *content* matters,
- `LISTING` — globs where only name, size and date matter,
- `VOLATILE` — the output depends on the day,
- `build()` — returns `<section>…</section>` or `(section, tail)`.

The full contract is in `templates/pages/__init__.py`. Timeline events
carry a `status` from `confirmed | assumed | planned | open | deadline`.

### Kind page

The page declares `KIND = "<name>"` plus `SOURCES = "<glob>"` (relative
to `ROOT`), and the engine renders **one output per matching data file**.

The glob is the lifecycle: move a source out of it and `--prune` deletes
the output that belonged to it. Instances are addressed as
`<page>:<stem>`. The file name comes from the kind, or from `FILENAME`
as a template with `{stem}` and `{pid}` (default `<id>-{stem}.html`).

A source that fails the kind's validation is **not rendered at all** —
every finding is reported and the run exits non-zero, while other
instances and pages still render.

Kinds are resolved from `engine/kinds/<name>.py` first, then the
project's own `kinds/<name>.py`. They are imported, never copied. A kind
declaring `VOLATILE = True` (or a page that does) has today's date folded
into its instances' cache key, for pages that show a countdown.

Two kinds ship, and they are opposites — one collects data the project
does not have, the other mirrors data the project maintains:

| Kind | Source | The page | Hands back | Skill · schema |
|---|---|---|---|---|
| `questionnaire` | a JSON spec written **for** the renderer | asks a set of questions | the answers | `/render:questionnaire` · [spec-questionnaire.md](spec-questionnaire.md) |
| `checklist` | a markdown document the project **maintains** | an editable view of that document | the **diff** against it | `/render:checklist` · [spec-checklist.md](spec-checklist.md) |

## The index page

The one page no project declares. Every run also writes
`<out dir>/index.html`: one magazine card per output, linking to it, with
the title, the description, a small cover graphic drawn from what is
inside (a checklist's progress, a questionnaire's questions, a section
page's sections) and one quiet meta line.

It is rewritten whenever anything the project renders changes, so it
never goes stale against the directory it describes, and a record leaves
it as soon as its file does — pruned, deleted or removed by hand, all
the same rule.

What a card says comes from the page itself: `TITLE` and `DESCRIPTION`
for a section page, the kind's `summary()` hook for one instance of a
family. `INDEX = False` in `config.py` switches it off,
`INDEX_FILENAME` renames it; a page of the project's own that already
writes `index.html` keeps the name and the engine writes none.

## The page shell

`pages/<id>/__init__.py` requires `TITLE`. Everything else is optional
and applies to both flavours:

| Value | Sets |
|---|---|
| `DESCRIPTION` | one sentence, shown on the index card |
| `FILENAME` | the output file name |
| `LANG` | the document language |
| `FAVICON_HREF` | the favicon |
| `EXTRA_CSS` | page CSS appended after `BASE_CSS` — tokens only |
| `hero()` or `HERO_HTML` | the page hero |
| `footer(generated)` or `FOOTER_HTML` | the footer (`{generated}` placeholder) |
| `GENERATED_FMT` | the date format in the footer |
| `STRINGS` | text overrides for this page |
| `VOLATILE` | the page's output depends on the day |

Unset values fall back to `config.py`, then to the engine's defaults. A
kind may read further values through the same chain: the `checklist`
kind takes `DEADLINE` and `EXCLUDE_MARKERS` as project-wide defaults its
documents override.

## Language

All visible engine texts **default to English** and are fully
translatable via `STRINGS`. One dict serves both layers: the texts from
`render.py` (`section_error`, `preview_*`) and those of the design system
(modal buttons, timeline legend, month abbreviations, status mark titles,
`today`/`today_fmt`).

Project-wide overrides live in `config.py`, per-page overrides on the
page; they merge per page and never leak into the next.
`templates/config.py` contains a ready-made German block to uncomment.

For number and date formats in your own sections, `design_system.py`
ships the helpers `fmt_eur`, `fmt_num` and `de_date` (German notation).

## How the configuration directory is found

First hit wins:

1. `--config-dir` on the command line,
2. the environment variable `RENDERER_CONFIG_DIR`,
3. `<project>/.render` — where `<project>` is `$CLAUDE_PROJECT_DIR` or
   the working directory.

Without a hit the hook is a silent no-op thanks to `--if-configured`, so
the plugin does not disturb unconfigured projects.
