# The standalone script — the escape hatch, genuinely last

Only when the page cannot be declared: its output must land outside the
config directory, or other tooling generates it on its own schedule. The
hook does not keep it fresh and the index page cannot list it — the engine
indexes what it renders, and it does not render this.

`scaffold.py --standalone <name>` writes a runnable skeleton into
`.render/<name>.py`. The rules it is built around:

1. Resolve the engine through the locator that `init` scaffolded — never
   through a hard-coded path (the skeleton already does).
2. Import **only from `page_api`** — the one stable interface for
   project-local code: `page_shell`, `check_page`, the design-system
   components (`card`, `tile`, `list_row`, `badge`, `accordion`,
   `timeline`, …), tokens (`TOKENS`, `BASE_CSS`) and the content core
   (`md_to_html`, `parse_frontmatter`, …). Everything else under `engine/`
   is internals and may change in any release.
3. Build the page body from the components, wrap it with
   `page_shell(title, body, …)`, and keep the `check_page(html)` gate
   **before the write — do not ship on findings.** It runs the same
   deterministic checks as `render.py --check`: self-containment, hex
   colors only from the token blocks, no unresolved placeholders.
4. Run the script yourself to generate the page — the hook renders only
   declared pages.

**Read `${CLAUDE_PLUGIN_ROOT}/design-manual.md` before writing any markup**
— the design rules bind standalone pages exactly as hard as declared ones.
Pick the components from the catalog in its §6 and read the listed
`${CLAUDE_PLUGIN_ROOT}/docs/design/` reference file for every helper you
call.

For richer pages the same components grow sideways: `tile`/`focus_card` for
metrics, `accordion` for question groups, `timeline` plus
`page_shell(modal=True, tail=…)` for event details, `md_to_html` for
markdown sources.
