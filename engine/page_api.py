#!/usr/bin/env python3
"""Stable facade for project-local pages built on the render engine.

This module is the **only** stable interface for renderers that live in a
consuming project's config directory (checklist pages, questionnaires,
reports, …). Everything else under ``engine/`` is internal: names, modules
and signatures there may change in any release without notice, while the
names exported here follow the plugin's SemVer contract.

Usage in a project-local renderer (see the ``custom-page`` skill):

    from engine_locator import engine_dir
    sys.path.insert(0, str(engine_dir()))          # engine first
    from page_api import page_shell, check_page, card, list_row, TOKENS

    html = page_shell("My page", card("…", title="…"))
    findings = check_page(html)                    # must be [] before shipping

The facade re-exports the design system (tokens, base CSS, component
helpers) and the generic content core (markdown renderer, frontmatter
parsing), and adds two page-level functions of its own: ``page_shell()``
builds a complete self-contained page around finished body markup, and
``check_page()`` runs the same deterministic self-containment and design
checks as ``render.py --check`` (single source of truth — render.py calls
this function).
"""

import html as _html
import re as _re

from design_system import (  # noqa: F401 — re-exported facade surface
    # tokens + base stylesheet (always used together, never modified)
    TOKENS, BASE_CSS,
    # opt-in stylesheets: interactive pages (6b / 11), long-form pages (11b)
    FORM_CSS, APP_CSS, ARTICLE_CSS,
    # strings / localization
    STRINGS, set_strings,
    # formatting helpers
    esc, fmt_eur, fmt_num, de_date,
    # components
    badge, delta, tile, card, focus_card, accordion, icon, eyebrow,
    section_head, subhead, crumbs, list_row, meter_row, share_bar, legend,
    sparkline, status_marks, timeline, timeline_key, modal_host, modal_detail,
    MODAL_JS, SERIES_COUNT,
    # input and app chrome
    option_row, field, text_field, amount_field, progress_bar, action_bar,
    toast, summary_row, check_row, TOAST_JS, STATE_JS, HANDBACK_JS, handback_js,
    # long-form pages
    article_head, pull_quote, source_list,
)

from content_core import (  # noqa: F401 — re-exported facade surface
    parse_frontmatter, read_md, md_to_html, inline, prose,
    drop_blocks, strip_leading_h1, split_title, fmt_size,
    fingerprint, strip_inline,
)

__all__ = [
    # design system
    "TOKENS", "BASE_CSS", "FORM_CSS", "APP_CSS", "ARTICLE_CSS", "STRINGS", "set_strings",
    "esc", "fmt_eur", "fmt_num", "de_date",
    "badge", "delta", "tile", "card", "focus_card", "accordion", "icon",
    "eyebrow", "section_head", "subhead", "crumbs", "list_row", "meter_row",
    "share_bar", "legend", "sparkline", "status_marks",
    "timeline", "timeline_key", "modal_host", "modal_detail",
    "MODAL_JS", "SERIES_COUNT",
    # input and app chrome (interactive pages — design-manual.md 6b / 11)
    "option_row", "field", "text_field", "amount_field", "progress_bar",
    "action_bar", "toast", "summary_row", "check_row",
    "TOAST_JS", "STATE_JS", "HANDBACK_JS", "handback_js",
    # long-form pages (design-manual.md 11b)
    "article_head", "pull_quote", "source_list",
    # content core
    "parse_frontmatter", "read_md", "md_to_html", "inline", "prose",
    "drop_blocks", "strip_leading_h1", "split_title", "fmt_size",
    "fingerprint", "strip_inline",
    # page level
    "page_shell", "check_page",
]


# ----------------------------------------------------------------- shell ----

def page_shell(title: str, body: str, lang: str = "en", favicon: str = "📊",
               extra_css: str = "", tail: str = "", wrap: bool = True,
               modal: bool = False) -> str:
    """A complete self-contained page with the design system's standard shell.

    ``body`` is finished markup (cards, tiles, prose, …) and lands inside
    the standard ``.wrap`` column unless ``wrap=False``. ``extra_css`` is
    page-specific CSS appended after ``BASE_CSS`` — it must use tokens only
    (``var(--s4)``, ``var(--ink-2)``, …); ``check_page()`` flags raw hex
    values. ``tail`` is extra HTML before ``</body>`` (e.g. hidden
    ``modal_detail()`` blocks). ``modal=True`` appends the detail-modal
    host and its script for pages whose marks carry ``data-ev``.
    """
    icon_href = (
        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'"
        f"%3E%3Ctext y='14' font-size='15'%3E{_html.escape(favicon)}%3C/text%3E%3C/svg%3E"
    )
    content = f'<div class="wrap">\n{body}\n</div>' if wrap else body
    end = tail or ""
    if modal:
        end += f"\n{modal_host()}\n<script>{MODAL_JS}</script>"
    return f"""<!DOCTYPE html>
<html lang="{esc(lang)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="icon" href="{icon_href}">
<style>{TOKENS}{BASE_CSS}{extra_css}</style>
</head>
<body>
{content}{end}
</body>
</html>
"""


# ----------------------------------------------------------------- check ----

# Pure black/white as mixing partners in ``color-mix()`` and in the print
# stylesheet are allowed; any other hex value outside the token blocks
# violates design-manual.md §10 (colors come exclusively from TOKENS).
HEX_ALLOWED = {"#000", "#fff", "#000000", "#ffffff"}


def check_page(text: str) -> list:
    """Deterministic page checks — the generic half of ``render.py --check``.

    Verifies what every page rendered with this engine must hold, dashboard
    or not: self-containment (no ``src=``, no stylesheet links, no
    ``@import``, no ``https://`` anywhere in the markup outside SVG
    ``xmlns`` declarations), hex colors only inside the token blocks, and
    no unresolved ``{PLACEHOLDER}`` leftovers. Returns a list of findings;
    an empty list means the page passes. Project-local renderers call this
    before writing their output — do not ship on findings.
    """
    errors = []

    # Self-containment — nothing may be fetched at view time.
    if _re.search(r"\bsrc\s*=", text):
        errors.append("external resource: src=")
    if _re.search(r"<link[^>]+stylesheet", text):
        errors.append("external resource: <link rel=stylesheet>")
    if "@import" in text:
        errors.append("external resource: @import")
    if _re.search(r"url\(\s*['\"]?https?:", text):
        errors.append("external resource: url(http…)")
    foreign = [m.start() for m in _re.finditer(r"https?://", text)
               if not _re.match(r"xmlns=", text[max(0, m.start() - 7):m.start()])]
    if foreign:
        errors.append(f"{len(foreign)} external URL(s) outside xmlns")

    # design-manual.md §10: colors only from the token blocks.
    for block in _re.findall(r"<style>(.*?)</style>", text, _re.S):
        inside = ([m.span() for m in _re.finditer(r":root\s*\{.*?\}", block, _re.S)]
                  + [m.span() for m in _re.finditer(
                      r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{.*?\n\}", block, _re.S)])
        stray = [m.group(0) for m in _re.finditer(r"#[0-9a-fA-F]{3,8}\b", block)
                 if not any(a <= m.start() < b for a, b in inside)
                 and m.group(0).lower() not in HEX_ALLOWED]
        if stray:
            errors.append(f"hex color outside the token blocks: {', '.join(sorted(set(stray)))}")

    # Unresolved f-string leftovers.
    for rest in _re.findall(r"\{[A-Z_]{3,}\}", text):
        errors.append(f"unresolved placeholder {rest}")

    return errors
