#!/usr/bin/env python3
"""Locate the render plugin's engine directory.

This file lives in the project's ``.render/`` config directory
(scaffolded by ``/render:init``) so project-local scripts
never hard-code the plugin's installation path.

**It belongs to the plugin, not to the project.** Nothing project-specific
goes here: ``/render:init`` replaces it with the installed version whenever
the two differ, so a project never carries a locator that has fallen behind
where the plugin actually installs.

Resolution order — first hit wins:

    1. environment variable ``RENDER_ENGINE`` (path to the engine dir)
    2. ``CLAUDE_PLUGIN_ROOT`` (set while the plugin's own hook or skills run)
    3. installed plugin copies under ``~/.claude/plugins``

A directory qualifies as the engine when it carries ``render.py``,
``design_system.py`` and ``page_api.py`` **and** the plugin manifest beside it
names this plugin. The file signature alone is not enough: one machine can
carry several plugins whose engines match it exactly — a predecessor, a fork,
the same plugin from a second marketplace — and rendering against the wrong
one fails far from here. A candidate with no manifest beside it is accepted:
that is the checkout case, where ``RENDER_ENGINE`` points at a working tree
deliberately.

The marketplace installs to ``cache/<owner>/<plugin>/<version>/engine`` — four
levels below the plugins directory. The sweep starts there, also covers the
two shallower shapes, and prefers the highest version it finds. On success the
resolved path is exported as ``RENDER_ENGINE`` so child processes skip the
search. Run directly, the script prints the resolved path.
"""

import json
import os
import sys
from pathlib import Path

ENGINE_SIGNATURE = ("render.py", "design_system.py", "page_api.py")
PLUGIN_NAME = "render"

_INSTALL_HELP = """\
render engine not found.

Install the plugin (inside Claude Code):

    /plugin marketplace add durchnull/render
    /plugin install render@durchnull

Or point RENDER_ENGINE at the engine directory of a checkout:

    export RENDER_ENGINE=/path/to/render/engine
"""


def _manifest_name(engine: Path):
    """Name from the plugin manifest beside ``engine``.

    ``None`` means no manifest at all — a bare checkout, which the caller
    trusts. An empty string means there is one but it does not identify a
    plugin we can accept.
    """
    manifest = engine.parent / ".claude-plugin" / "plugin.json"
    if not manifest.is_file():
        return None
    try:
        with manifest.open(encoding="utf-8") as handle:
            return json.load(handle).get("name") or ""
    except (OSError, ValueError):
        return ""


def _qualifies(d: Path) -> bool:
    if not all((d / name).is_file() for name in ENGINE_SIGNATURE):
        return False
    return _manifest_name(d) in (None, PLUGIN_NAME)


def _newest_first(engine: Path):
    """Sort key for install paths, whose parent is the version directory."""
    parts = engine.parent.name.split(".")
    numeric = tuple(int(p) for p in parts) if all(p.isdigit() for p in parts) else ()
    return numeric, str(engine)


def _candidates():
    env = os.environ.get("RENDER_ENGINE")
    if env:
        yield Path(env)
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        yield Path(plugin_root) / "engine"
    plugins = Path.home() / ".claude" / "plugins"
    if plugins.is_dir():
        # Installs sit four levels down (cache/<owner>/<plugin>/<version>);
        # shallower layouts have existed, so sweep from the deepest and let
        # the manifest check decide which copy is actually this plugin.
        for depth in (4, 3, 2):
            pattern = "/".join(["*"] * depth) + "/engine"
            yield from sorted(plugins.glob(pattern), key=_newest_first, reverse=True)


def engine_dir() -> Path:
    """Return the engine directory; export RENDER_ENGINE on success."""
    for c in _candidates():
        try:
            c = c.resolve()
        except OSError:
            continue
        if _qualifies(c):
            os.environ["RENDER_ENGINE"] = str(c)
            return c
    raise FileNotFoundError(_INSTALL_HELP)


if __name__ == "__main__":
    try:
        print(engine_dir())
    except FileNotFoundError as exc:
        sys.exit(str(exc))
