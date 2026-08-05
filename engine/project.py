#!/usr/bin/env python3
"""Locate and activate the per-project renderer configuration.

The engine is project-agnostic. Everything page-specific lives in a config
directory inside the consuming project, containing at least:

    config.py               project-wide constants: ROOT, ... (see README)
    pages/__init__.py       package with one subpackage per page —
                            ``pages/<id>/__init__.py`` is the page (shell +
                            section list), its sibling modules the sections
    content.py              optional: project-specific gather/format helpers
                            (re-export the generic core via
                            `from content_core import *`)

Discovery order — first hit wins:

    1. explicit ``--config-dir`` argument
    2. environment variable ``RENDERER_CONFIG_DIR``
    3. ``<project>/.render`` — where <project> is
       ``$CLAUDE_PROJECT_DIR`` or the current directory

A directory qualifies when it contains both ``config.py`` and
``pages/__init__.py`` — this keeps the PostToolUse hook a silent no-op in
projects that never configured any pages.

``activate()`` puts the engine directory *before* the config directory on
``sys.path`` so the engine's modules (``design_system``, ``cache``, …) are
always the ones that load, even when the project keeps compatibility shims
with the same names.
"""

import os
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
SEARCH_SUBDIRS = (".render",)

# Set by activate(); engine modules read it for cache invalidation.
CONFIG_DIR = None


def qualifies(d: Path) -> bool:
    return (d / "config.py").is_file() and (d / "pages" / "__init__.py").is_file()


def out_dir() -> Path:
    """Directory the rendered pages land in: ``config.OUT_DIR`` or
    ``<config dir>/output``. Requires an activated configuration."""
    import config
    d = getattr(config, "OUT_DIR", None)
    return Path(d) if d else CONFIG_DIR / "output"


def locate(explicit=None):
    """Return the first qualifying config directory, or None."""
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.environ.get("RENDERER_CONFIG_DIR")
    if env:
        candidates.append(Path(env))
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    candidates += [root / sub for sub in SEARCH_SUBDIRS]
    for c in candidates:
        try:
            c = c.resolve()
        except OSError:
            continue
        if qualifies(c):
            return c
    return None


def activate(config_dir) -> Path:
    """Make `import config` / `import sections` resolve to the project."""
    global CONFIG_DIR
    CONFIG_DIR = Path(config_dir).resolve()
    for p in (str(ENGINE_DIR), str(CONFIG_DIR)):
        while p in sys.path:
            sys.path.remove(p)
    sys.path.insert(0, str(CONFIG_DIR))
    sys.path.insert(0, str(ENGINE_DIR))
    return CONFIG_DIR
