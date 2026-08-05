---
description: Add a page to the project's .render/ — a section page under pages/ (dashboard, report, checklist), a data-driven kind page that renders one output per data file, or a standalone page_api script when the page must live outside the config. Use when the project needs another HTML page.
allowed-tools: Read, Write, Edit, Glob, Bash(python3:*)
---

# Add a page on the render engine

The project needs another self-contained HTML page. Pages are the unit the
engine thinks in: a project declares any number, each designed by the
project itself. The plugin brings the shell, the fragment cache, the design
system and the checks; the page brings its content.

If `.render/` does not exist yet, run `/render:init` first.

## Which of the three

| The page is… | Use |
|---|---|
| one output, content the project assembles from files and its own code | a **section page** — the default |
| one output **per data file**, all built the same way from a spec (a questionnaire per topic, a report per client, a checklist per year) | a **kind page** |
| output that must land outside the config directory, or that other tooling generates on its own schedule | a **standalone script** |

Reach for a section page unless one of the other two clearly fits. The
standalone script is genuinely last: it is the only one the hook does not
keep fresh, and the only one the index page cannot list.

Pick the branch, scaffold it, then read **only that branch's file** — it
carries the contract and the steps:

- **Section page** — read `${CLAUDE_PLUGIN_ROOT}/skills/new/section-page.md`, then:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/engine/scaffold.py" --new-page <id> --section <sid> --section <sid> --title "…"
  ```
- **Kind page** — read `${CLAUDE_PLUGIN_ROOT}/skills/new/kind-page.md`, then:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/engine/scaffold.py" --new-page <id> --kind <kind> --sources '<glob>' --title "…"
  ```
- **Standalone script** — read `${CLAUDE_PLUGIN_ROOT}/skills/new/standalone.md`, then:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/engine/scaffold.py" --standalone <name> --title "…"
  ```

The scaffold writes starter content only — everything it emits is the
project's from the first byte and is never refreshed or overwritten.

## Never

- **Never copy or modify engine code** — the engine is imported from the
  installation; a copy forks silently and never receives another update.
- **Never touch the plugin's installation directory** — it is read-only for
  consumers and the next sync would discard any change.
- **No custom hex values and no CSS that bypasses the design system** —
  colors, typography, spacing and components come exclusively from the
  tokens. Page-specific CSS goes into the page's `EXTRA_CSS` (declared
  pages) or `page_shell(extra_css=…)` (standalone scripts) and uses tokens
  only (`var(--s4)`, `var(--ink-2)`, …). Interactive pages pull in
  `FORM_CSS` / `APP_CSS` there — they are opt-in so a dashboard never
  carries form styling it has no use for.
