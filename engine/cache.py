#!/usr/bin/env python3
"""Fragment cache for the rendered pages.

Each section is written to ``<out dir>/.cache/fragments/<page>/<id>.html``
on its own. Whether it must be rebuilt is decided by a key with four parts:

1. **Shared code** — the engine modules plus the project's ``config.py``,
   ``content.py`` and ``pages/__init__.py``. If any of these change, all
   fragments are void.
2. **Page code** — the page's ``__init__.py`` (shell + section list). If it
   changes, only that page's fragments are void.
3. **Own code** — the section's module inside the page package. If only
   that changes, only that one section is rebuilt.
4. **Input data** — the files declared in ``INPUTS``/``LISTING``, hashed by
   content (not by timestamp: a ``touch`` must not trigger anything).

``VOLATILE = True`` additionally folds today's date into the key — for
sections that show "days until deadline" or a today marker.

Content is hashed, not mtimes; the only exception is the newest modification
day, because it is shown as the data revision in card footers.
"""

import hashlib
import json
import shutil
from datetime import date, datetime
from pathlib import Path

import project

#: 3: index records carry ``meta`` phrases and ``cover`` data instead of
#: ``facts`` pairs — resetting the manifest re-derives every card once.
VERSION = 3

# Code that feeds into every fragment — a change forces a full rebuild.
ENGINE_CODE = ["render.py", "cache.py", "content_core.py", "design_system.py",
               "project.py", "page_api.py"]
PROJECT_CODE = ["config.py", "content.py", "pages/__init__.py"]


def _root() -> Path:
    from config import ROOT
    return ROOT


def _cache_dir() -> Path:
    return project.out_dir() / ".cache"


def _frag_dir() -> Path:
    return _cache_dir() / "fragments"


def _manifest_path() -> Path:
    return _cache_dir() / "manifest.json"


def _sha(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:16]


def content_hash(*parts: str) -> str:
    """Hash over finished fragment HTML — detects whether a rebuild actually
    changed the page or merely produced the same bytes again."""
    return _sha(*parts)


def _expand(patterns) -> list:
    """Resolve glob patterns relative to the project root, sorted."""
    root = _root()
    found = []
    for pat in patterns:
        found.extend(p for p in root.glob(pat) if p.is_file())
    return sorted(set(found), key=lambda p: str(p))


def hash_inputs(patterns) -> str:
    """Content hash over all matches, plus the newest modification day."""
    root = _root()
    paths = _expand(patterns)
    parts, newest = [], 0.0
    for p in paths:
        parts.append(str(p.relative_to(root)))
        parts.append(hashlib.sha256(p.read_bytes()).hexdigest())
        newest = max(newest, p.stat().st_mtime)
    if newest:
        parts.append(datetime.fromtimestamp(newest).strftime("%Y-%m-%d"))
    return _sha(*parts)


def hash_listing(patterns) -> str:
    """Hash over the file listing instead of contents — for folders where
    only name, size and modification date appear on the page."""
    root = _root()
    parts = []
    for p in _expand(patterns):
        st = p.stat()
        parts.append(f"{p.relative_to(root)}|{st.st_size}|"
                     f"{datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d')}")
    return _sha(*parts)


def shared_hash() -> str:
    parts = []
    for base, rels in ((project.ENGINE_DIR, ENGINE_CODE),
                       (project.CONFIG_DIR, PROJECT_CODE)):
        for rel in rels:
            p = Path(base) / rel
            parts.append(rel)
            parts.append(hashlib.sha256(p.read_bytes()).hexdigest()
                         if p.exists() else "-")
    return _sha(*parts)


def page_hash(pid: str) -> str:
    """Hash over the page's own code (``pages/<pid>/__init__.py``)."""
    p = Path(project.CONFIG_DIR) / "pages" / pid / "__init__.py"
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "-"


def file_hash(path) -> str:
    p = Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "-"


def instance_key(shared: str, phash: str, kind_hash: str, src,
                 volatile: bool = False) -> str:
    """A kind-page instance's key: shared code, the page's own code, the kind
    module that renders it, and the spec file's content.

    Deliberately not the section key: a kind page has no sections and no
    ``INPUTS`` — its one input is the spec. A change to the kind rebuilds
    every instance of that kind and nothing else.

    ``volatile`` folds today's date in, exactly as ``VOLATILE`` does for a
    section. Without it a page showing "5 days until the deadline" would be
    served from yesterday's cache forever: nothing about the spec changed,
    and the answer moved anyway.
    """
    parts = [shared, phash, kind_hash, file_hash(src)]
    if volatile:
        parts.append(date.today().isoformat())
    return _sha(*parts)


def section_key(mod, shared: str, phash: str) -> str:
    """A section's key from shared code, page code, own code and input data."""
    own = Path(mod.__file__)
    parts = [shared, phash, hashlib.sha256(own.read_bytes()).hexdigest()]
    parts.append(hash_inputs(getattr(mod, "INPUTS", [])))
    parts.append(hash_listing(getattr(mod, "LISTING", [])))
    if getattr(mod, "VOLATILE", False):
        parts.append(date.today().isoformat())
    return _sha(*parts)


# --------------------------------------------------------------- storage ----

def load_manifest() -> dict:
    """The manifest carries three independent registries:

    * ``pages`` — one entry per section, per section page;
    * ``kinds`` — one entry per kind-page instance, keyed by its stem;
    * ``index`` — one card record per output, keyed by its ref, for the
      index page (``index.py``). Not a cache key: it is what a ``--page``
      run carries over about the outputs it did not look at.

    A registry that is missing is simply empty — the two build registries
    then rebuild what they describe, and the index records come back with
    the next run that enumerates their pages.
    """
    empty = {"version": VERSION, "pages": {}, "kinds": {}, "index": {}}
    path = _manifest_path()
    if not path.exists():
        return dict(empty)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(empty)
    if data.get("version") != VERSION:
        return dict(empty)
    for registry in ("pages", "kinds", "index"):
        data.setdefault(registry, {})
    return data


def save_manifest(data: dict) -> None:
    _cache_dir().mkdir(parents=True, exist_ok=True)
    _manifest_path().write_text(json.dumps(data, indent=1, ensure_ascii=False),
                                encoding="utf-8")


def frag_path(pid: str, sid: str, part: str = "html") -> Path:
    name = f"{sid}.html" if part == "html" else f"{sid}.{part}.html"
    return _frag_dir() / pid / name


def read_fragment(pid: str, sid: str, part: str = "html"):
    p = frag_path(pid, sid, part)
    return p.read_text(encoding="utf-8") if p.exists() else None


def write_fragment(pid: str, sid: str, text: str, part: str = "html") -> None:
    p = frag_path(pid, sid, part)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def clear() -> None:
    if _frag_dir().exists():
        shutil.rmtree(_frag_dir())
    if _manifest_path().exists():
        _manifest_path().unlink()
