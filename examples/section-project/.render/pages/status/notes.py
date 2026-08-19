#!/usr/bin/env python3
"""03 Release notes on disk — LISTING and VOLATILE, the other two answers.

``LISTING`` globs are keyed on **path, size and modification date** —
never on the bytes. The engine does not open the files at all, which is
what makes it the cheap answer for a directory that may hold hundreds of
them; the trade is a coarser key. A note appearing, disappearing, being
renamed, changing size, or being saved on a later day invalidates this
section; re-saving one with identical bytes on the same day does not.
Everything shown is therefore metadata: the version and release date come
out of the file *name*, the size and the last-edited age out of ``stat()``.

``VOLATILE = True`` because that age is measured against today. A volatile
section is rebuilt once per day rather than on every run, which is the
honest way to say "this output has a shelf life".
"""

import datetime as _dt

import content
from config import ROOT
from page_api import badge, card, fmt_size

INPUTS = []
LISTING = ["docs/notes/*.md"]
VOLATILE = True

SOURCE = "docs/notes"


def _split_stem(stem):
    """``0.9.0-2026-08-04`` → ``("0.9.0", "2026-08-04")``.

    The name is the metadata, which is the whole point of LISTING: a note
    that has not been released yet simply carries no date.
    """
    version, _, released = stem.partition("-")
    return version, released or "unreleased"


def build():
    notes = sorted((ROOT / SOURCE).glob("*.md"), reverse=True)
    if not notes:
        return content.wrap(
            "notes",
            f"<p class='empty'>No notes in <code>{SOURCE}/</code> yet — the "
            "first release will put one there.</p>")

    today = _dt.date.today()
    rows = []
    for path in notes:
        version, released = _split_stem(path.stem)
        stat = path.stat()
        age = (today - _dt.date.fromtimestamp(stat.st_mtime)).days
        edited = "today" if age == 0 else f"{age} d ago"
        rows.append(
            f"<tr><td>{version}</td><td>{released}</td>"
            f"<td class='num'>{fmt_size(stat.st_size)}</td>"
            f"<td class='num'>{edited}</td></tr>")

    table = ("<div class='table-wrap'><table><thead>"
             "<tr><th>Version</th><th>Released</th>"
             "<th class='num'>Size</th><th class='num'>Last edited</th></tr>"
             "</thead><tbody>" + "".join(rows) + "</tbody></table></div>")

    return content.wrap("notes", card(
        table,
        title=f"{len(notes)} releases on record",
        sub="Read from the directory listing — no note is opened to build this",
        right=badge("metadata only", "neutral"),
        foot_left="Keyed on names, sizes and dates — no note is opened, "
                  "so this stays cheap over a full archive",
        foot_right=f"Ages against {today.isoformat()}",
    ))
