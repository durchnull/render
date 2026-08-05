#!/usr/bin/env python3
"""Checklists — one page per markdown file in docs/checklists/.

The whole family is these three lines: the engine's ``checklist`` kind
builds each page from a document the project already maintains, and the
glob decides which of them have pages. Archiving a checklist means moving
its file out of ``docs/checklists/`` — the next ``--prune`` removes the
page that belonged to it.

Nothing here configures the checklist itself. The document is in front of
this file for everything it can carry: its own title, deadline and
exclusion markers live in its frontmatter, because for this page type the
document is the truth. ``DEADLINE`` and ``EXCLUDE_MARKERS`` may be set here
or in ``config.py`` as project-wide defaults for documents that say nothing.
"""

TITLE = "Checklist"
KIND = "checklist"
SOURCES = "docs/checklists/*.md"
