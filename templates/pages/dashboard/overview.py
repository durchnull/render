#!/usr/bin/env python3
"""01 Overview — example section: renders the project's README."""

from config import ROOT
from content import prose, read_md, split_title, wrap

INPUTS = ["README.md"]
LISTING = []
VOLATILE = False


def build():
    path = ROOT / "README.md"
    if not path.exists():
        body = ("<div class='card'><p class='empty'>No README.md yet — "
                "this example section renders it here.</p></div>")
        return wrap("overview", body)

    _, md = read_md(path)
    title, rest = split_title(md)
    body = f"<div class='card card--pad'>{prose(rest, bool(title))}</div>"
    return wrap("overview", body)
