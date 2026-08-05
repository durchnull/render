---
description: Scaffold the render config (.render/ with config.py + pages/) for this project, or refresh an existing one against the installed plugin
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Bash(python3:*)
---

Set up the render plugin for the current project:

1. If a qualifying config already exists (`.render/` with both `config.py` **and** `pages/__init__.py`), this is a **refresh**, not a scaffold — the command a project runs after updating the plugin:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/engine/scaffold.py"
   ```

   It replaces the four files the plugin owns (`engine_locator.py`, `render.py`, `README.md`, `pages/__init__.py`) whenever they differ from the installation, and creates any that are missing. It never touches `config.py`, `content.py`, `kinds/` or anything under `pages/<id>/` — the project's own design is not yours to overwrite, then or ever. Report its output: which files were refreshed, and that the project's files were left alone. Pass `--check` first when the user wants to see what would change without changing it. Then stop — a configured project needs nothing else from this skill.
2. Otherwise scaffold it in one command — never copy the files by hand:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/engine/scaffold.py" --fresh
   ```

   It writes the full template scaffold (`config.py`, `content.py`, `pages/__init__.py`, the example `dashboard` page, `render.py`, `engine_locator.py`, `README.md`) and never overwrites a file that already exists. A fresh copy is by definition current — the engine compares bytes, so a new directory needs nothing further to be recognised as up to date.
3. Ask the user which pages the project needs if the request doesn't say. The example `dashboard` page is a starter, not an assumption — rename it, redesign it or replace it entirely; every page is the project's own design.
4. For each page, scaffold the folder instead of typing it:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/engine/scaffold.py" --new-page <id> --section <sid> --section <sid> --title "…"
   ```

   Then make it real: each section stub's `build()` raises until it renders something, and `DESCRIPTION` is empty until you write the one sentence the index card shows — `--check` reports a section page without one. Each page renders to `output/<id>.html` (override with `FILENAME`; move all output with `OUT_DIR` in `config.py`). A page that should render **one output per data file** takes `--kind <k> --sources '<glob>'` instead of `--section` — see the `new` skill, or `/render:questionnaire` and `/render:checklist` for the two kinds that ship.
5. Read `${CLAUDE_PLUGIN_ROOT}/design-manual.md` (the core: principles, tokens, hierarchy, component catalog) before writing any section markup — colors, typography and components come exclusively from the engine's `design_system.py` (`TOKENS` + `BASE_CSS`); no custom hex values. Then pick the components from the catalog in its §6 and **read the listed `docs/design/` reference file for every helper you call** — the catalog is an index, not a spec.
6. Render and verify:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/engine/render.py" --all
   python3 "${CLAUDE_PLUGIN_ROOT}/engine/render.py" --check
   ```
   (Equivalent once scaffolded: `python3 .render/render.py --all` / `--check` — the thin entry point resolves the engine itself.)
7. Tell the user where the pages land (`output/` next to the config unless `OUT_DIR` says otherwise), that `output/index.html` is the entry point the engine keeps up to date on its own — a card per page, linking to it — and that the plugin's PostToolUse hook now re-renders all of it automatically after every Write/Edit. Mention once that running this command again after a plugin update refreshes the plugin's own files in `.render/` and leaves theirs untouched; the engine says so itself when they fall behind.

Arguments (optional): $ARGUMENTS — if a directory is given, use it instead of `<project>/.render/`.

## The extension contract

Everything project-specific lives in `.render/` — config, pages,
content helpers, and any standalone page scripts the project adds later.
The engine is **imported from the plugin installation, never copied**:
`engine_locator.py` resolves it, and `page_api` is the only stable
interface for project-local code.

Four files in that directory are the plugin's rather than the project's —
`engine_locator.py`, `render.py`, `README.md`, `pages/__init__.py` — and
each says so in its own header. They are the only things a plugin update
leaves behind, which is why re-running this command is all a project ever
has to do; `engine/scaffold.py` owns that split, and nothing else may
decide it case by case. When the project needs another page (a
checklist, a form/questionnaire, a report, a second dashboard), follow the
`new` skill — a page is a folder under `pages/`, and the engine picks
it up on its own.
