# `page_api` — the interface for standalone renderers

Most pages are declared in a project's `.render/pages/` and rendered by
the engine. A page the engine cannot own — output that belongs outside
the configuration directory, or a page another tool generates — is
written as a standalone script instead. `engine/page_api.py` is what such
a script imports.

**It is the only stable interface.** Everything else under `engine/` is
internals and may change in any release without notice. A script that
imports `design_system` or `render` directly will break; one that imports
`page_api` will not.

## What it re-exports

| Tier | Names |
|---|---|
| design system | `TOKENS`, `BASE_CSS`, `card`, `tile`, `tile_group`, `list_row`, `badge`, `timeline`, `filter_row`, `show_all`, `bar_list`, `tracker`, `metric_hero`, `FILTER_JS`, `SHOWALL_JS`, … |
| interactive | `FORM_CSS`, `APP_CSS`, `option_row`, `field`, `progress_bar`, `action_bar`, `toast`, `summary_row`, `STATE_JS`, `HANDBACK_JS`, … |
| long-form | `ARTICLE_CSS`, `article_head`, `pull_quote`, `source_list`, `aside_note`, `mini_toc` |
| content core | `md_to_html`, `parse_frontmatter`, … |

## What it adds

- `page_shell(title, body, …)` — a complete self-contained page with the
  design system's standard shell.
- `check_page(html) -> list[str]` — the same deterministic checks as
  `render.py --check`: self-containment (including "no `https://` in the
  markup"), hex colors only from the token blocks, no unresolved
  placeholders, and the mechanical half of design-manual.md 5.1 (no card
  with an empty body, no prose in a table cell). A standalone renderer
  calls it to verify itself before it writes.

A standalone page that uses `filter_row()` or `show_all()` appends the
matching script itself — the engine's shell does it only for declared
pages: `tail=f"<script>{FILTER_JS}{SHOWALL_JS}</script>"`.

## Finding the engine

A standalone script must not hard-code an installation path. The
`engine_locator.py` that `/render:init` scaffolds into `.render/`
resolves the installed engine in order:

1. the environment variable `RENDER_ENGINE`,
2. `CLAUDE_PLUGIN_ROOT`,
3. `~/.claude/plugins`.

The engine is imported, never copied. `/render:new` carries a runnable
skeleton that already does this.
