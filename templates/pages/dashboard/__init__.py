#!/usr/bin/env python3
"""Dashboard — example page. Rename, redesign or replace it: every page
is the project's own design, and every sibling folder is another page."""

TITLE = "Project Dashboard"

# One sentence for the card this page gets on the index page.
DESCRIPTION = "Where the project stands right now — everything on one screen."

HERO_HTML = """  <header class="hero">
    <div class="eyebrow">Project</div>
    <h1>Dashboard</h1>
    <p>Current state of the project — everything in one self-contained page.</p>
  </header>
"""

# {generated} is replaced with the render date (format: GENERATED_FMT).
FOOTER_HTML = ("  <footer>Generated on {generated} · self-contained HTML, "
               "no external resources</footer>")
GENERATED_FMT = "%Y-%m-%d"

# Sections in display order: (id, number, kicker, title, subline, nav label).
# Each id needs a sibling module pages/dashboard/<id>.py — see overview.py.
SECTIONS = [
    ("overview", "01", "Focus", "Overview",
     "The project at a glance", "Overview"),
]
