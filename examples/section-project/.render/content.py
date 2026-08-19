#!/usr/bin/env python3
"""Project-specific content helpers.

Re-exports the generic core (markdown renderer, frontmatter parsing,
section wrapper) so section modules only ever import from `content`.
Add your own gather/format helpers below — anything that knows your
project's folder layout belongs here, not in the engine.
"""

from content_core import *  # noqa: F401,F403 — generic core from the engine
