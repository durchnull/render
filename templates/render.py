#!/usr/bin/env python3
"""Render this project's pages — thin entry point over the plugin engine.

Sits in the project's ``.render/`` config directory and lets you run

    python3 .render/render.py [--all | --check | --status | …]

without knowing where the plugin is installed: it pins
``RENDERER_CONFIG_DIR`` to this directory, resolves the engine via
``engine_locator``, and hands over to the engine's ``render.py``. All
command-line flags are the engine's own.

The engine is imported from the installation, never copied — see this
directory's README.md.

**This file belongs to the plugin, not to the project.** It holds no
project-specific settings — those live in ``config.py`` — and
``/render:init`` replaces it with the installed version whenever the two
differ.
"""

import os
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

if __name__ == "__main__":
    os.environ["RENDERER_CONFIG_DIR"] = str(HERE)
    sys.path.insert(0, str(HERE))                  # engine_locator lives here
    from engine_locator import engine_dir

    engine = engine_dir()
    # Engine first on sys.path — its modules must win over same-named files
    # in this directory (the engine's project.py re-asserts this order).
    sys.path.insert(0, str(engine))
    runpy.run_path(str(engine / "render.py"), run_name="__main__")
