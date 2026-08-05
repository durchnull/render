# render

[![ci](https://img.shields.io/github/actions/workflow/status/durchnull/render/ci.yml?branch=main&label=ci)](https://github.com/durchnull/render/actions/workflows/ci.yml)
[![version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fdurchnull%2Frender%2Fmain%2F.claude-plugin%2Fplugin.json&query=%24.version&label=version&prefix=v)](CHANGELOG.md)
[![license](https://img.shields.io/github/license/durchnull/render)](LICENSE)
[![Claude Code plugin](https://img.shields.io/badge/Claude_Code-plugin-D97757?logo=claude&logoColor=white)](https://code.claude.com/docs/en/plugins)

> **Beta — version 0.x.** Things will still change: a release may rename or
> remove commands, config keys or file formats without a migration path,
> and pages and cache files this plugin writes under `.render/` can be lost
> on update. It ships as-is, with no warranty (see [LICENSE](LICENSE)).

A Claude Code plugin that renders a project's HTML pages — dashboards,
checklists, reports, questionnaires, as many as the project declares. Each
page is a single file that loads nothing from the network. Some pages
report; others ask a question and hand back what a person answered or
changed.

The engine knows nothing about any particular project. Every page lives in
a small configuration directory inside the project itself, and the plugin
supplies the rest: the page shell, a cache that re-renders only what
changed, one design system all pages share, and the checks that keep the
output self-contained.

## Install

```text
/plugin marketplace add durchnull/claude-plugins
/plugin install render@durchnull
```

To take this plugin on its own, add its repo directly instead — it carries
its own `durchnull` marketplace definition:

```text
/plugin marketplace add durchnull/render
/plugin install render@durchnull
```

Both routes register a marketplace named `durchnull`, and adding one
replaces the other, so prefer the catalog whenever you want more than one
durchnull plugin at a time.

## Commands

| Command | Does |
|---|---|
| `/render:init` | create the `.render/` directory in a project, or refresh it after an update |
| `/render:new` | add a page — a section page, a data-driven kind page, or a standalone script |
| `/render:article` | turn one markdown document into a single page to read |
| `/render:questionnaire` | build a questionnaire page and read the answers back |
| `/render:checklist` | turn a checklist the project maintains into a page, and apply what comes back |

## Setting up in a project

1. Install the plugin.
2. Run `/render:init`. It copies `templates/` to `<project>/.render/` and
   adapts it to the pages the project wants. The `dashboard` page it
   scaffolds is a starter, not an assumption — rename it or replace it.
3. Run `python3 .render/render.py` to render what you have.

To test the plugin from a checkout instead of an installation, start
Claude Code with `claude --plugin-dir /path/to/render`, then run
`/reload-plugins`.

### Keeping a project current

The engine is imported from the installation rather than copied into the
project, so updating the plugin updates the renderer. Four files in
`.render/` are the exception — `engine_locator.py`, `render.py`,
`README.md` and `pages/__init__.py` are the plugin's, copied at scaffold
time. If an old copy is left behind after an update, the project can end up
unable to find the engine at all.

**Run `/render:init` again after updating.** In a configured project it
refreshes exactly those four and fills in any that are missing. It never
touches `config.py`, `content.py`, `kinds/` or anything under `pages/<id>/`.
Version control is what makes the replacement reversible; every file it may
replace says in its own header that it belongs to the plugin.

Nobody has to remember this: the engine compares those four against the
installation on every run and says one line when they differ. On an
already-configured project `/render:init` is the refresh — it reports what
`engine/scaffold.py` would replace before it replaces anything.

## What a project provides

A `.render/` directory, created by `/render:init`:

- `config.py` — project-wide values every page inherits.
- `pages/<id>/` — one folder per page. A page is either a **section page**,
  which assembles its own markup into one output, or a **kind page**, which
  names a glob of data files and lets the engine render one output per
  matching file.
- `content.py` and `kinds/` — optional: the project's own gather helpers
  (re-exporting the generic markdown/frontmatter core,
  `engine/content_core.py`), and its own page kinds when none of the
  shipped ones fit.

Every subpackage of `pages/` is one page; nothing is registered anywhere
else. Two kinds ship, and they are opposites: `questionnaire` asks a set of
questions the project does not have answers to, `checklist` mirrors a
markdown document the project already maintains. Both hand back what a
person entered.

The engine also writes an index page listing everything it rendered
(`engine/index.py`, one card per output) and keeps a fragment cache next
to the output (`engine/cache.py` decides per section what is stale), so
everything generated sits under `.render/` and can be ignored or deleted
as one unit.

**[docs/contract.md](docs/contract.md) is the full contract** — every file,
both page flavours, the index page, the page shell, and how the
configuration directory is found.

## Usage

The scaffolded `.render/render.py` is a thin entry point that finds the
installed engine on its own:

```bash
python3 .render/render.py                      # render all pages incrementally
python3 .render/render.py --page faq           # only this page
python3 .render/render.py --page survey:2026-08-02-intake   # one instance
python3 .render/render.py --status             # what is stale, per page?
python3 .render/render.py --all                # discard the cache, rebuild everything
python3 .render/render.py --only faq/answers   # force one section
python3 .render/render.py --preview faq/answers  # one section as its own page
python3 .render/render.py --prune              # delete outputs whose source is gone
python3 .render/render.py --check              # structure, descriptions, self-containment, color rules
```

References follow the flavour: `page/section` for a section of a section
page, `page:instance` for one output of a kind page.

The hook (`hooks/hooks.json`) automatically calls the engine after every
`Write` and `Edit`, so all declared pages stay fresh; the cache keeps that
instant. In a project with no `.render/` directory the hook does nothing.

## Configuration

`config.py` holds what every page shares. A page overrides any of these in
its own `pages/<id>/__init__.py`; unset values fall back to `config.py`,
then to the engine's defaults.

| Key | Sets | Default |
|---|---|---|
| `ROOT` | the project directory the pages describe | required |
| `OUT_DIR` | where the pages are written | `.render/output/` |
| `LANG` | the document language | `en` |
| `GENERATED_FMT` | the date format in the footer | `%Y-%m-%d` |
| `FAVICON_HREF` | the favicon | a built-in inline SVG |
| `EXTRA_CSS` | CSS appended after the design system's — tokens only | none |
| `STRINGS` | text overrides for the engine and the design system | English |
| `INDEX` | write the index page | on |
| `INDEX_FILENAME` | the index file name | `index.html` |
| `DEADLINE`, `EXCLUDE_MARKERS` | defaults the `checklist` kind reads | unset |

A page adds `TITLE` (required), `DESCRIPTION`, `FILENAME`, `hero()` or
`HERO_HTML`, `footer()` or `FOOTER_HTML`, `VOLATILE`, and either `SECTIONS`
or `KIND` plus `SOURCES`. Each one is described in
[docs/contract.md](docs/contract.md).

Finding both is `engine/project.py`'s job; two environment variables
override it: `RENDERER_CONFIG_DIR` names the configuration directory,
`RENDER_ENGINE` the installed engine.

## Extending: more pages

Another page is another folder — run `/render:new` for the
walkthrough: `pages/<id>/__init__.py` plus section modules, and the engine
picks it up on its own. When the pages differ only in their data, declare
`KIND` + `SOURCES` once instead and let the engine render one output per
data file. Pages the engine cannot own (output outside the config
directory, generated by other tooling) fall back to a standalone script on
`page_api`; the same skill carries all three patterns and a runnable
skeleton.

## One page to read: `/render:article`

Not every page is a dashboard. `/render:article` turns **one markdown
document** — or the last thing that was said in the conversation — into a
self-contained, magazine-styled page and opens it:

```text
/render:article notes.md                 → notes.html
/render:article notes.md --title "…"     → a title you choose
```

The command runs `scripts/article.py`, a standalone renderer that sits
deliberately outside everything else the plugin does: no `.render/` needed
(it works in an unconfigured project), no cache, no hook, no index card —
one file, when a person asks for it. Because the page fetches nothing, no
link survives as a link: they become text, resolved in a source list at the
foot. [docs/article.md](docs/article.md) has the flags, where the headline
comes from, and the link rules in full.

## Interactive pages: questionnaires and checklists

Both shipped kinds produce a single offline file that collects something
and hands it back as a block of text a person pastes into the chat. Both
keep what was entered in `localStorage` and send it nowhere.

`/render:questionnaire` — scaffold once, author a JSON spec per
questionnaire, render, parse the answers. Three screens, and "I don't
know" and "skip" are first-class answers that never block handing back
what exists.

`/render:checklist` — point the page at checklists the project
already maintains as markdown, render one page each, and apply the
**diff** that comes back to the source file. The file stays the truth:
the page is a view of it, items are keyed by a fingerprint over their
text so the two survive being edited apart, and **the plugin never writes
to the document** — the parsed diff goes to the project's own skill,
where it gets a review step.

- [docs/spec-questionnaire.md](docs/spec-questionnaire.md) — spec schema,
  what the validator refuses, how to write questions worth answering
- [docs/spec-checklist.md](docs/spec-checklist.md) — the markdown a
  checklist page reads, what survives an edit, what is refused
- [docs/handback.md](docs/handback.md) — the hand-back grammar, versioned,
  with a reference parser (`scripts/handback.py` — pipe the paste in, read
  a short report or an edit plan back out). Not kind-specific: it is how
  any generated page talks back to an agent, in two shapes — the answers a
  page collected, or the changes against a document it mirrored.

Interactive pages are a distinct page flavour in the design manual
(section 11) with their own rules — three permitted script purposes,
content in the document rather than assembled in the browser, and nothing
mandatory.

A page the engine cannot own is written as a standalone script instead.
`engine/page_api.py` is the **only stable interface** for those —
everything else under `engine/` is internals and may change in any release
without notice. It re-exports the design system, the interactive and
long-form tiers and the content core, and adds a page shell and the same
self-check `--check` runs: [docs/page-api.md](docs/page-api.md).

## Layout

`engine/` is the renderer and knows nothing about any project;
`design-manual.md` and `engine/design_system.py` are the design system;
`skills/` holds the five commands; `templates/` is the scaffold a project
gets a copy of; `docs/` carries the schemas and the contract; `examples/`
and `tests/` run in CI. `evals/` holds agent-side cases for the hand-back
loops — they cost money to run, so CI never does
([evals/README.md](evals/README.md)). A commented file tree is in
[docs/layout.md](docs/layout.md).

The engine is imported from the installation, never copied. The scaffolded
`engine_locator.py` resolves it (env `RENDER_ENGINE` → `CLAUDE_PLUGIN_ROOT`
→ `~/.claude/plugins`), so no script hard-codes an installation path.

## Design rule

`design-manual.md` applies to **every** generated page: colors, typography,
spacing and components come exclusively from `engine/design_system.py`
(`TOKENS` + `BASE_CSS`); no custom hex values in renderers. `--check`
enforces this mechanically (token blocks, self-containment, section structure).

The visual reference is generated, not maintained:

```bash
python3 engine/gallery.py   # from a checkout of this repo; writes design-gallery.html
```

It renders every component beside the snippet that produced it,
deterministic and self-contained. Regenerate after any change to
`design_system.py`.

## License

[MIT](LICENSE) © David Friedrich.

The license covers the code, not the name. It grants no right to use **durchnull** as the
name of a derived or redistributed work — fork it freely, under a name of your own.
