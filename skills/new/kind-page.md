# The kind page — one folder, one output per data file

Scaffolded by `scaffold.py --new-page <id> --kind <kind> --sources '<glob>'`.
The declaration is three lines and never changes again; **no design-manual
read is needed — the kind renders itself.**

- The **glob is the lifecycle**: a source file that leaves it takes its page
  with it on the next `--prune`. Nothing to scaffold or delete per instance.
- Address one instance as `<page>:<stem>` —
  `render.py --page survey:2026-08-02-intake`.
- The output name comes from the kind, or from `FILENAME` as a template
  (`"survey-{stem}.html"`).
- A page declares `SECTIONS` **or** `KIND`, never both, and `KIND` always
  needs `SOURCES`.

Shipped kinds live in the engine and are imported, never copied — that is
how a page gets behaviour fixes. Two ship, and they are opposites:

| Kind | Source | Hands back | Walkthrough |
|---|---|---|---|
| `questionnaire` | a JSON spec written **for** the renderer | the answers | `/render:questionnaire` |
| `checklist` | a markdown document the project **maintains** | the **diff** against it | `/render:checklist` |

Reach for `checklist` whenever the content already exists as a file somebody
keeps up to date — the page becomes a view of it rather than a second copy
of it, and the plugin never writes back.

## A kind of the project's own

If the project needs a data-driven page the plugin does not ship, it writes
its **own** kind in `.render/kinds/<name>.py` (same contract, no `SECTIONS`;
the engine's kinds win on a name collision). Read
`${CLAUDE_PLUGIN_ROOT}/engine/kinds/__init__.py` for the contract — that
module's docstring is the specification. Implement its optional
`summary(spec, ctx)` hook too: without it every instance's index card falls
back to the spec's bare title, and the kind is the only thing that knows
what is worth saying about one of its pages.
