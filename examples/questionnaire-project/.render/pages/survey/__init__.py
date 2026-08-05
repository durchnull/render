#!/usr/bin/env python3
"""Questionnaires — one page per spec in docs/questions/.

The whole family is these three lines: the engine's ``questionnaire`` kind
builds each page, and the glob decides which specs exist. Archiving a
questionnaire means moving its spec out of ``docs/questions/`` — the next
``--prune`` removes the page that belonged to it.
"""

TITLE = "Questionnaire"
KIND = "questionnaire"
SOURCES = "docs/questions/*.json"
