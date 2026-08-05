#!/usr/bin/env python3
"""Page kinds — pages the engine builds from a data file, not from sections.

A section page declares ``SECTIONS`` and owns its markup. A **kind page**
declares ``KIND = "<name>"`` instead and owns only its shell: the kind
module turns one *spec file* into the page body. Together with ``SOURCES``
(one output per matching spec) that makes a page folder a template for a
whole family — per-instance questionnaires, reports, checklists — where the
glob is the lifecycle: a spec that leaves the glob takes its page with it.

Two places supply kinds, in this order:

1. ``engine/kinds/<name>.py`` — shipped with the plugin, imported and
   never copied into a project, so behaviour fixes arrive with an update.
2. ``<config dir>/kinds/<name>.py`` — the consuming project's own kind, for
   data-driven pages the plugin does not ship. A built-in name always wins,
   so a project can never shadow a shipped kind by accident.

A kind module fulfils this contract:

    NAME        str — must equal the module's file name
    STRINGS     optional dict: the kind's own user-visible text, English
                defaults. Merged under config.STRINGS, then the page's
                STRINGS (unknown keys ignored, as in the design system).
    VOLATILE    optional bool: True when the output depends on today's date
                (a countdown, a today marker). Folds the day into the cache
                key of every instance, as ``VOLATILE`` does for a section.
                A page may set it too; either one is enough.
    load(src, ctx)
                optional: (Path, BuildContext) -> spec. Default: strict JSON.
                ``ctx`` is already complete here — a kind whose source can
                leave something to the project (a default the document may
                override) has to resolve it *before* parsing, not after.
    validate(spec, src) -> list[str]
                every problem with this spec, [] when it is usable. A
                non-empty list aborts *this instance*: nothing is written
                and the run exits non-zero (see render.py). Be exhaustive —
                the caller reports all findings at once.
    css()       page CSS appended after BASE_CSS. Tokens only.
    build(spec, ctx) -> str | (body, tail)
                the finished page body. ``ctx`` carries page, pid, stem,
                src and the merged strings (see BuildContext).
    filename(spec, src, pid) -> str
                optional: the output file name. Default comes from the
                page's FILENAME template.
    summary(spec, ctx) -> dict
                optional: how this instance introduces itself on the index
                page — ``title``, ``desc`` (prose, markdown welcome),
                ``facts`` (label/value pairs) and ``badge`` (text, tone).
                Every key is optional; without the hook the index falls
                back to the spec's own title. Called for cached instances
                too, so it must read the spec and nothing else — never the
                rendered HTML, which may not have been built this run.
    scripts()   optional: inline JS for the page, appended inside the
                shell's own <script> block.
    check(spec, html) -> list[str]
                optional: the kind's own assertions for ``--check``, on top
                of the generic ``check_page()`` half.

Kinds are engine code: they may import ``design_system`` and
``content_core`` directly. Project-local kinds get the same imports — the
engine directory is ahead of the config directory on ``sys.path``.
"""

import hashlib
import importlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import project

BUILTIN_DIR = Path(__file__).resolve().parent
NAME_RE = re.compile(r"[a-z][a-z0-9_]*\Z")
REQUIRED = ("NAME", "validate", "css", "build")


class KindError(Exception):
    """A kind cannot be used: unknown name, or the module breaks the contract."""


class SpecError(Exception):
    """A spec file is unusable. Carries every finding, not just the first."""

    def __init__(self, findings):
        self.findings = list(findings)
        super().__init__("; ".join(self.findings))


class BuildContext:
    """What a kind needs besides the spec itself.

    ``strings`` is already merged (kind defaults → config.STRINGS → the
    page's STRINGS), so a kind reads ``ctx.strings["key"]`` and never has
    to know about the layers. ``stem`` is the sanitized source file stem —
    the instance's handle on the command line (``<pid>:<stem>``).
    """

    def __init__(self, page, pid: str, stem: str, src: Path, strings: dict,
                 setting=None):
        self.page = page
        self.pid = pid
        self.stem = stem
        self.src = src
        self.strings = strings
        self._setting = setting

    def setting(self, name: str, default=None):
        """A configurable value for this instance: the page's own attribute,
        else the project's ``config.py``, else ``default``.

        The same chain ``LANG``, ``FAVICON_HREF`` and ``EXTRA_CSS`` already
        follow, handed to kinds so a kind never imports the project's config
        itself. A kind that also reads the value out of its source document
        puts the document in front — for a page that mirrors a file, the file
        is the truth.
        """
        if self._setting is not None:
            return self._setting(name, default)
        return getattr(self.page, name, default)


class Kind:
    """One loaded kind module plus the defaults for its optional hooks."""

    def __init__(self, name: str, module, path: Path, builtin: bool):
        self.name = name
        self.module = module
        self.path = path
        self.builtin = builtin

    # -- optional hooks, with their defaults ---------------------------------

    @property
    def strings(self) -> dict:
        return dict(getattr(self.module, "STRINGS", {}) or {})

    @property
    def wrap_class(self) -> str:
        """The content column's class. A form reads better in the narrow
        column than in the dashboard-wide one."""
        return getattr(self.module, "WRAP_CLASS", "wrap")

    @property
    def volatile(self) -> bool:
        """True when every instance of this kind depends on today's date."""
        return bool(getattr(self.module, "VOLATILE", False))

    def footer(self, spec, ctx, generated: str) -> str:
        """The kind's own footer, used only when the page defines none — a
        page's FOOTER_HTML always wins."""
        fn = getattr(self.module, "footer", None)
        return (fn(spec, ctx, generated) or "") if fn else ""

    def load(self, src: Path, ctx: "BuildContext" = None):
        """Parse a spec file. The default is strict JSON — no comments, no
        trailing commas — so a malformed spec fails with a line number
        instead of being half-understood."""
        loader = getattr(self.module, "load", None)
        if loader is not None:
            return loader(src, ctx)
        text = src.read_text(encoding="utf-8")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise SpecError([f"not valid JSON: {exc.msg} (line {exc.lineno},"
                             f" column {exc.colno})"]) from None

    def validate(self, spec, src: Path) -> list:
        return list(self.module.validate(spec, src) or [])

    def css(self) -> str:
        return self.module.css() or ""

    def scripts(self) -> str:
        fn = getattr(self.module, "scripts", None)
        return (fn() or "") if fn else ""

    def build(self, spec, ctx: BuildContext):
        result = self.module.build(spec, ctx)
        body, tail = result if isinstance(result, tuple) else (result, "")
        return body, (tail or "")

    def filename(self, spec, src: Path, pid: str):
        fn = getattr(self.module, "filename", None)
        return fn(spec, src, pid) if fn else None

    def summary(self, spec, ctx: BuildContext) -> dict:
        """What the index page says about one instance. A kind that does not
        implement it gets the engine's fallback, never an empty card."""
        fn = getattr(self.module, "summary", None)
        return dict(fn(spec, ctx) or {}) if fn else {}

    def check(self, spec, html: str) -> list:
        fn = getattr(self.module, "check", None)
        return list(fn(spec, html) or []) if fn else []

    # -- cache ---------------------------------------------------------------

    def code_hash(self) -> str:
        """Hash over the kind's own code plus this loader — an instance is
        rebuilt when the kind that renders it changes, without voiding the
        fragment cache of every unrelated section page."""
        h = hashlib.sha256()
        for p in (BUILTIN_DIR / "__init__.py", self.path):
            h.update(p.read_bytes() if p.exists() else b"-")
            h.update(b"\x00")
        return h.hexdigest()[:16]


def _import_project_kind(name: str, path: Path):
    """Import a project-local kind under its own module name, so it can never
    collide with an engine module of the same name."""
    mod_name = f"_project_kinds_{name}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        del sys.modules[mod_name]
        raise
    return module


def _project_dir():
    return Path(project.CONFIG_DIR) / "kinds" if project.CONFIG_DIR else None


def available() -> list:
    """Every usable kind name — built-ins first, then the project's own."""
    names = {p.stem for p in BUILTIN_DIR.glob("*.py") if p.stem != "__init__"}
    d = _project_dir()
    if d and d.is_dir():
        names |= {p.stem for p in d.glob("*.py") if p.stem != "__init__"}
    return sorted(names)


def load(name: str) -> Kind:
    """Resolve a kind by name: built-in first, then the project's ``kinds/``."""
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise KindError(f"kind name {name!r} is not usable — lowercase letters, "
                        "digits and underscores only, starting with a letter")

    path = BUILTIN_DIR / f"{name}.py"
    builtin = path.is_file()
    if builtin:
        module = importlib.import_module(f"kinds.{name}")
    else:
        d = _project_dir()
        path = (d / f"{name}.py") if d else None
        if path is None or not path.is_file():
            known = ", ".join(available()) or "none"
            where = f"{d}/" if d else "the project's kinds/ directory"
            raise KindError(f"unknown kind {name!r} — no kinds/{name}.py in the "
                            f"engine and none in {where}. Known kinds: {known}")
        module = _import_project_kind(name, path)

    missing = [n for n in REQUIRED if not hasattr(module, n)]
    if missing:
        raise KindError(f"kind {name!r} ({path}) is missing: {', '.join(missing)}")
    if getattr(module, "NAME", None) != name:
        raise KindError(f"kind {name!r} ({path}) declares NAME="
                        f"{getattr(module, 'NAME', None)!r} — the two must agree")
    return Kind(name, module, path, builtin)
