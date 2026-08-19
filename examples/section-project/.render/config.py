#!/usr/bin/env python3
"""Project-wide configuration for the render plugin — adapt freely.

One file per project; everything page-specific lives with the page itself
in ``pages/<id>/__init__.py``. This file holds only what all pages share.
The engine reads it via `import config`, so keep the names below.

Required:  ROOT
Optional:  OUT_DIR, LANG, GENERATED_FMT, FAVICON_HREF, STRINGS,
           INDEX, INDEX_FILENAME
           (any page may override the optional values individually)
"""

from pathlib import Path

# This file sits in <project>/.render/ — HERE is that directory,
# ROOT the project the pages render. Everything generated stays under
# HERE/output (one HTML file per page, and the fragment cache next to
# them); uncomment OUT_DIR to put the pages somewhere else.
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
# OUT_DIR = HERE / "output"

# The engine writes <out dir>/index.html on every run: one card per page,
# each linking to it. Rename it with INDEX_FILENAME (a file name, always
# next to the pages), or switch it off entirely.
# INDEX = False
# INDEX_FILENAME = "start.html"

# Defaults every page inherits unless it sets its own.
LANG = "en"

# Override engine strings here — one dict serves both layers: the texts
# from render.py (section_error, preview_*) and the design system's UI
# strings (modal buttons, timeline legend, month names). English is the
# default; pages may override on top. Ready-made German block:
# STRINGS = {
#     "months_short": ("Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
#                      "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"),
#     "today": "heute", "today_fmt": "%d.%m.%Y",
#     "key_span": "Zeitraum", "key_dot": "Zeitpunkt",
#     "key_soft": "Annahme oder Prognose", "key_open": "ungeklärt",
#     "key_deadline": "Frist",
#     "key_hint": "Klick auf eine Marke öffnet die Details",
#     "modal_aria": "Detail zum Ereignis", "modal_prev": "← Früher",
#     "modal_next": "Später →", "modal_close": "Schließen",
#     "mark_confirmed": "bestätigt", "mark_low": "gering",
#     "mark_assumption": "Annahme", "mark_attention": "Achtung",
#     "mark_high": "hoch", "mark_no": "nein", "mark_unknown": "unbekannt",
#     "mark_important": "wichtig", "mark_done": "erledigt", "mark_open": "offen",
#     "filter_aria": "Filter", "filter_all": "alle",
#     "filter_empty": "nichts entspricht diesem Filter",
#     "show_all": "alle {n} anzeigen",
#     "state_answered": "beantwortet", "state_unclear": "weiß nicht",
#     "state_skipped": "übersprungen", "state_open": "nicht angegeben",
#     "check_obsolete": "hinfällig", "check_na": "entfällt",
#     "check_deferred": "später", "toc_contents": "Inhalt",
#     "chrome_index": "Übersicht",
#     "idx_title": "Seiten", "idx_kicker": "render",
#     "idx_n_sections": "{n} Abschnitte", "idx_one_section": "1 Abschnitt",
#     "idx_instances": "{n} Seiten", "idx_one_instance": "1 Seite",
#     "idx_updated": "Zuletzt aktualisiert",
#     "idx_generated": "Erzeugt am {generated}",
#     "idx_self_contained": "in sich geschlossen · keine externen Ressourcen",
# }
