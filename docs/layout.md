# What is in this repository

```text
render/
├── .claude-plugin/
│   ├── plugin.json              plugin manifest
│   └── marketplace.json         marketplace definition `durchnull` (for /plugin)
├── hooks/hooks.json             PostToolUse hook: renders the pages after every Write/Edit
├── engine/                      generic code, no project knowledge
│   ├── render.py                CLI + page shell + checks (--check)
│   ├── project.py               discovery of the project config directory
│   ├── cache.py                 fragment cache (invalidation via content hashes, per page)
│   ├── content_core.py          markdown renderer, frontmatter, section wrapper
│   ├── design_system.py         TOKENS + BASE_CSS + components (executable manual)
│   ├── page_api.py              stable facade for standalone page scripts
│   ├── index.py                 the index page: a card per output, linking to it
│   ├── gallery.py               component gallery: every helper beside its call
│   ├── scaffold.py              creates and refreshes a project's .render/
│   └── kinds/                   page kinds: __init__.py is the contract,
│                                questionnaire.py and checklist.py ship
├── scripts/
│   ├── article.py               one markdown document → one long-form page
│   └── handback.py              the hand-back reference parser + edit plans
├── design-manual.md             binding design rules for every output (the core)
├── docs/
│   ├── contract.md              what a project provides: files, pages, kinds, shell
│   ├── page-api.md              the stable interface for standalone renderers
│   ├── article.md               /render:article — flags, headline, link rules
│   ├── spec-questionnaire.md    the questionnaire spec schema
│   ├── spec-checklist.md        the markdown a checklist page reads
│   ├── handback.md              the hand-back grammar + reference parser
│   ├── layout.md                this file
│   └── design/                  the component reference, one file per topic
├── examples/                    runnable fixture projects, doubling as CI fixtures
├── tests/                       stdlib self-tests (python3 tests/run.py)
├── evals/                       agent-side cases for the hand-back loops; costs
│                                money to run, so never wired into CI
├── templates/                   starter scaffold for a new project
│   ├── config.py, content.py    project-wide values + gather helpers
│   ├── pages/                   the page contract + an example `dashboard` page
│   ├── render.py                thin entry point (resolves the engine itself)
│   ├── engine_locator.py        finds the installed engine, no hard-coded paths
│   └── README.md                what lives in .render/, what is off-limits
└── skills/
    ├── init/                    /render:init — create the scaffold
    ├── article/                 /render:article — one document → one page to read
    ├── new/                     /render:new — add a page (or a standalone script)
    ├── questionnaire/           /render:questionnaire — spec → page → answers
    └── checklist/               /render:checklist — document → page → diff → document
```

Two boundaries are worth knowing:

- **`engine/` is the plugin's, `templates/` is what a project gets a copy
  of.** The engine is imported from the installation and never copied, so
  updating the plugin updates every project's renderer at once. Only four
  scaffolded files are copies, and `/render:init` refreshes them.
- **`engine/page_api.py` is the only stable interface** — see
  [page-api.md](page-api.md). Everything else under `engine/` is internals.
