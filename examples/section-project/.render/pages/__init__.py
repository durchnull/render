#!/usr/bin/env python3
"""Registry of the project's pages.

This file states the contract; it belongs to the plugin and ``/render:init``
replaces it with the installed version whenever the two differ. The pages
themselves are subpackages beside it and are never touched.

Every subpackage of this package is one page, designed by the project:
``pages/<id>/`` renders to ``<out dir>/<id>.html``. Page ids are lowercase
letters only. Add a page by adding a folder — the engine discovers it,
renders it, caches it and checks it like every other page, and lists it on
``<out dir>/index.html`` with whatever ``TITLE`` and ``DESCRIPTION`` say.

``pages/<id>/__init__.py`` is the page — shell plus what it is built from:

    TITLE      required: the page title
    SECTIONS   list of (id, number, kicker, title, subline, nav label) in
               display order; each id needs a sibling module
               ``pages/<id>/<sid>.py``
    DESCRIPTION
               required: one sentence saying what the page is for. Shown on
               the index page's card for it — the only place a page
               introduces itself to someone who has not opened it yet, which
               is why ``--check`` reports a page that leaves it out.
    optional   FILENAME, LANG, FAVICON_HREF, EXTRA_CSS, HERO_HTML / hero(),
               FOOTER_HTML / footer(generated), GENERATED_FMT, STRINGS
               — unset values fall back to config.py, then to defaults

The jump bar appears automatically on pages with two or more sections.

A page may instead be built from data, one output per file:

    KIND       the kind that renders it — "questionnaire" (a JSON spec
               becomes a page that asks) or "checklist" (a markdown
               document the project maintains becomes an editable view of
               itself). Resolved from the engine's kinds/ first, then the
               project's own.
    SOURCES    required with KIND: a glob relative to ROOT. Every match
               becomes one output; a file that leaves the glob takes its
               output with it on the next ``--prune``.

A page declares SECTIONS **or** KIND, never both and never neither.
Instances are addressed as ``<page>:<stem>`` on the command line, and
FILENAME becomes a template there (``"<id>-{stem}.html"`` by default).

Each section module fulfils a small contract:

    INPUTS   list of glob patterns (relative to ROOT) whose **content**
             the section renders. If any of them changes, it is rebuilt.
    LISTING  glob patterns where only **name, size and mtime** matter.
    VOLATILE True if the output depends on today's date. Such sections
             are rebuilt once per day, not on every run.
    build()  returns the finished `<section>…</section>` (use
             `content.wrap`), or `(section, tail)`.
"""
