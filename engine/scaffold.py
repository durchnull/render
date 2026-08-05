#!/usr/bin/env python3
"""The plugin-owned half of a project's config directory, kept current.

``/render:init`` copies a handful of files into ``<project>/.render/``. Two
kinds of file end up there and they age in opposite directions:

* **the plugin's** — ``engine_locator.py`` and ``render.py`` are machinery
  with nothing project-specific in them, and ``README.md`` and
  ``pages/__init__.py`` describe a contract the plugin defines. A copy that
  stays behind is how a project ends up unable to find the engine at all;
* **the project's** — ``config.py``, ``content.py`` and everything under
  ``pages/`` are the project's own design. Nothing here touches them, not
  even when they differ from the template that seeded them.

That split is the whole idea: the plugin's files can be replaced without
asking because nobody but the plugin ever writes them, and the project's
files are never replaced because nobody but the project does. Every
plugin-owned file says so in its own header, because replacing a file in
someone's repository is only fair when the file announces it.

The engine is what keeps this a small job: it is imported from the
installation rather than copied into the project, so it is current the
moment the plugin is. Only these four ever drift.

Drift is detected by comparing bytes, not version numbers — a release that
changes none of them is not worth a word. Bytes are also the only evidence
there is: nothing records which version wrote a project's copy, so nothing
can name it wrongly either. What the engine says is what it can prove — the
version it is running, and the files that do not match it.

Refreshing fills gaps as well as replacing stale copies; the engine's own
note is narrower and speaks only of files that exist and differ — see
``behind()``.

Run it to refresh, ``--check`` to report without writing:

    python3 "${CLAUDE_PLUGIN_ROOT}/engine/scaffold.py" [DIR] [--check]

Beside the refresh it owns, this is also where boilerplate gets written
instead of typed — starter content that is byte-identical every time it is
needed has no business being re-authored by hand (or by a model):

    scaffold.py --fresh [DIR]                 the full first scaffold
    scaffold.py --new-page ID --kind K --sources GLOB [--title T] [DIR]
    scaffold.py --new-page ID --section SID [--section SID …] [--title T] [DIR]
    scaffold.py --standalone NAME [--title T] [DIR]

Everything these modes write is the **project's** from the moment it lands —
starter content, written once, never refreshed, never added to
``PLUGIN_OWNED``. The refresh contract above is untouched by all of them.

Exit status: 0 done or already current, 1 ``--check`` found drift, 2 no
usable config directory or a refused write (the target already exists, a bad
id, missing arguments).
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = PLUGIN_ROOT / "templates"
MANIFEST = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"

#: Paths the plugin owns, relative to the config directory.
PLUGIN_OWNED = ("engine_locator.py", "render.py", "README.md",
                "pages/__init__.py")

def plugin_version():
    """Version of the installation this module belongs to, or None when it
    has no manifest beside it — a checkout run through ``RENDER_ENGINE``."""
    try:
        with MANIFEST.open(encoding="utf-8") as handle:
            return json.load(handle).get("version") or None
    except (OSError, ValueError):
        return None


def plan(config_dir):
    """One ``(relative path, action)`` per plugin-owned file.

    ``create`` — missing, a gap to fill; ``refresh`` — present and different;
    ``current`` — byte-identical to what ships, so nothing to do.
    """
    config_dir = Path(config_dir)
    out = []
    for rel in PLUGIN_OWNED:
        shipped, mine = TEMPLATES / rel, config_dir / rel
        if not shipped.is_file():
            continue
        if not mine.is_file():
            out.append((rel, "create"))
        elif mine.read_bytes() != shipped.read_bytes():
            out.append((rel, "refresh"))
        else:
            out.append((rel, "current"))
    return out


def behind(config_dir):
    """The plugin-owned files a project *has* and that no longer match.

    Deliberately not the missing ones. A file that differs is unambiguous —
    the project is carrying an older copy of something only the plugin
    writes, which is the failure this whole module exists for. A file that
    is absent may be a project that never wanted it, and the engine is in no
    position to argue. Refreshing fills those gaps anyway; nagging about
    them would be the engine mistaking a choice for a fault.
    """
    return [rel for rel, action in plan(config_dir) if action == "refresh"]


def note(config_dir):
    """One line for the engine to print when a project's copies are behind,
    or None when they are current — which includes every project rendering
    against a checkout, where there is no installed version to be behind.

    It names the running version and counts the files, both of which it can
    show its work for. Which version wrote the copies is not knowable here,
    and a sentence is better one honest half than two halves where one is a
    guess.
    """
    if not TEMPLATES.is_dir() or plugin_version() is None:
        return None
    stale = behind(config_dir)
    if not stale:
        return None
    count = len(stale)
    return (f"note  .render/ has {count} plugin-owned "
            f"file{'s' if count != 1 else ''} that do"
            f"{'' if count != 1 else 'es'} not match render "
            f"{plugin_version()} — /render:init refreshes "
            f"{'them' if count != 1 else 'it'}")


def apply(config_dir, actions):
    """Copy every file that is not already current."""
    config_dir = Path(config_dir)
    for rel, action in actions:
        if action == "current":
            continue
        target = config_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TEMPLATES / rel, target)


# -------------------------------------------------------------- emitters ----
# Starter content the modes below write. Project-owned from the first byte:
# nothing here is tracked, refreshed or compared ever again, which is why it
# says "yours" in the report and appears nowhere in PLUGIN_OWNED.

KIND_PAGE = '''"""{title} — one page per match of {sources}."""

TITLE = "{title}"
KIND = "{kind}"
SOURCES = "{sources}"   # glob relative to ROOT — one output per match
'''

SECTION_PAGE = '''#!/usr/bin/env python3
"""{title}."""

TITLE = "{title}"

# One sentence for the card this page gets on the index page. --check
# reports a section page that leaves it empty.
DESCRIPTION = ""

# Sections in display order: (id, number, kicker, title, subline, nav label).
# Each id has a sibling module pages/{pid}/<id>.py fulfilling the contract
# stated in pages/__init__.py.
SECTIONS = [
{sections}]
'''

SECTION_STUB = '''#!/usr/bin/env python3
"""{number} {title} — scaffolded stub; make build() return the real thing."""

INPUTS = []      # globs (relative to ROOT) whose content this section renders
LISTING = []     # globs where only name, size and mtime matter
VOLATILE = False


def build():
    raise NotImplementedError(
        "section '{sid}' is a scaffolded stub — build() returns the finished "
        "<section> markup (use content.wrap; the contract is stated in "
        "pages/__init__.py)")
'''

STANDALONE = '''#!/usr/bin/env python3
"""{title} — standalone page on the render engine.

Runs outside the declared-pages pipeline: no cache, no hook, run it
yourself. Imports only from ``page_api`` — everything else under the
engine is internals and may change in any release.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # …/.render
sys.path.insert(0, str(HERE))                   # engine_locator lives here
from engine_locator import engine_dir
sys.path.insert(0, str(engine_dir()))           # engine first on sys.path
from page_api import card, check_page, page_shell

body = card("<p>Build the page body from page_api components.</p>",
            title="{title}")
html = page_shell("{title}", body)

findings = check_page(html)
if findings:
    sys.exit("\\n".join(f"CHECK  {{f}}" for f in findings))

out = HERE / "output" / "{name}.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html, encoding="utf-8")
print(f"OK  {{out}}")
'''


def _title(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").strip().capitalize()


def fresh(config_dir: Path) -> int:
    """The whole first scaffold in one copy — what ``/render:init`` used to
    assemble by hand, file by file. Refuses a directory that already
    qualifies: that project wants the plain refresh, which knows the
    ownership split this mode deliberately ignores."""
    if qualifies(config_dir):
        print(f"{config_dir} is already a render config — run the plain "
              "refresh instead (no flag), which replaces only the files the "
              "plugin owns.", file=sys.stderr)
        return 2
    written, kept = [], []
    for shipped in sorted(TEMPLATES.rglob("*")):
        if not shipped.is_file() or "__pycache__" in shipped.parts:
            continue
        rel = shipped.relative_to(TEMPLATES)
        target = config_dir / rel
        if target.is_file():
            kept.append(str(rel))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(shipped, target)
        written.append(str(rel))
    print(config_dir)
    print(f"scaffolded: {len(written)} file{'s' if len(written) != 1 else ''}")
    for rel in written:
        print(f"  {rel}")
    for rel in kept:
        print(f"  {rel} (already there — left alone)")
    print("\nA fresh copy is by definition current. config.py, content.py "
          "and everything under pages/ are yours from here.")
    return 0


def new_page(config_dir: Path, pid: str, args) -> int:
    """One page folder, written instead of typed. Two flavours: ``--kind``
    declares a data-driven family (one output per source match), ``--section``
    a section page with one contract-complete stub per section."""
    if not re.fullmatch(r"[a-z]+", pid):
        print(f"page id {pid!r} — lowercase letters only, that is the "
              "contract in pages/__init__.py.", file=sys.stderr)
        return 2
    if bool(args.kind) == bool(args.section):
        print("--new-page needs exactly one of --kind K --sources GLOB or "
              "--section SID [--section SID …].", file=sys.stderr)
        return 2
    target = config_dir / "pages" / pid
    if target.exists():
        print(f"{target} already exists — a scaffold never overwrites a "
              "page; edit it, or pick another id.", file=sys.stderr)
        return 2
    title = args.title or _title(pid)

    if args.kind:
        if not args.sources:
            print("--kind needs --sources GLOB (relative to the project "
                  "root); the glob is the page family's lifecycle.",
                  file=sys.stderr)
            return 2
        target.mkdir(parents=True)
        (target / "__init__.py").write_text(
            KIND_PAGE.format(title=title, kind=args.kind,
                             sources=args.sources), encoding="utf-8")
        print(f"created: pages/{pid}/__init__.py — kind {args.kind!r}, one "
              f"output per match of {args.sources!r}")
        shipped = (PLUGIN_ROOT / "engine" / "kinds" / f"{args.kind}.py").is_file()
        project = (config_dir / "kinds" / f"{args.kind}.py").is_file()
        if not shipped and not project:
            print(f"note  no kind named {args.kind!r} ships with the engine "
                  f"and .render/kinds/{args.kind}.py does not exist yet — "
                  "the page renders once it does")
        prefix = args.sources.split("*")[0].rstrip("/")
        root = config_dir.parent
        if prefix and not (root / prefix).is_dir():
            print(f"note  {prefix}/ does not exist yet — the sources live "
                  "there; an empty glob renders nothing and is not an error")
    else:
        target.mkdir(parents=True)
        rows = "".join(
            f'    ("{sid}", "{n:02d}", "", "{_title(sid)}", "", '
            f'"{_title(sid)}"),\n'
            for n, sid in enumerate(args.section, start=1))
        (target / "__init__.py").write_text(
            SECTION_PAGE.format(title=title, pid=pid, sections=rows),
            encoding="utf-8")
        for n, sid in enumerate(args.section, start=1):
            (target / f"{sid}.py").write_text(
                SECTION_STUB.format(number=f"{n:02d}", title=_title(sid),
                                    sid=sid), encoding="utf-8")
        print(f"created: pages/{pid}/ with "
              f"{len(args.section)} section stub"
              f"{'s' if len(args.section) != 1 else ''} — each build() "
              "raises until it renders something real, and DESCRIPTION "
              "is empty until somebody says what the page is for")
    print("\nYours from here: nothing under pages/ is ever refreshed.")
    return 0


def standalone(config_dir: Path, name: str, args) -> int:
    """The runnable skeleton for a page outside the declared pipeline."""
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", name):
        print(f"script name {name!r} — lowercase, digits, '-' and '_'.",
              file=sys.stderr)
        return 2
    target = config_dir / f"{name}.py"
    if target.exists():
        print(f"{target} already exists — a scaffold never overwrites; "
              "edit it, or pick another name.", file=sys.stderr)
        return 2
    title = args.title or _title(name)
    target.write_text(STANDALONE.format(title=title, name=name),
                      encoding="utf-8")
    print(f"created: {target.relative_to(config_dir.parent)} — runnable as "
          f"python3 .render/{name}.py, yours from here")
    return 0


# ------------------------------------------------------------------- cli ----

def locate(explicit=None):
    """The config directory, discovered the way the engine discovers it.

    Unlike the engine this accepts one that does not qualify yet: saying
    *why* it does not is more useful than saying nothing at all.
    """
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get("RENDERER_CONFIG_DIR")
    if env:
        return Path(env).resolve()
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    return (root / ".render").resolve()


def qualifies(d):
    """The engine's own test: a configured project, not an empty directory."""
    d = Path(d)
    return (d / "config.py").is_file() and (d / "pages" / "__init__.py").is_file()


def report(config_dir, actions, checking):
    """What changed, in the order it is read: where, against which version,
    which files, and the reassurance that the project's own work was left
    alone."""
    changed = [(rel, a) for rel, a in actions if a != "current"]
    print(config_dir)
    print(f"installed: render {plugin_version()}")
    if changed:
        print(f"\n{'would refresh' if checking else 'refreshed'}:")
        for rel, action in changed:
            print(f"  {rel}{' (was missing)' if action == 'create' else ''}")
    if not changed:
        print("\nUp to date: every plugin-owned file matches this installation.")
        return
    print("\nLeft alone (yours): config.py, content.py, pages/<id>/, kinds/, output/")
    if not checking:
        print("Replaced files are recoverable from version control.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dir", nargs="?", help="config directory; discovered "
                                           "when omitted")
    ap.add_argument("--check", action="store_true",
                    help="report the refresh without writing")
    ap.add_argument("--fresh", action="store_true",
                    help="write the full first scaffold")
    ap.add_argument("--new-page", metavar="ID", dest="new_page",
                    help="write a page folder under pages/")
    ap.add_argument("--kind", help="with --new-page: the kind that renders it")
    ap.add_argument("--sources", help="with --kind: glob relative to ROOT")
    ap.add_argument("--section", action="append", default=[], metavar="SID",
                    help="with --new-page: one section stub per flag")
    ap.add_argument("--title", help="page or script title; derived from the "
                                    "id when omitted")
    ap.add_argument("--standalone", metavar="NAME",
                    help="write a runnable standalone page script")
    args = ap.parse_args()

    modes = sum(bool(m) for m in (args.fresh, args.new_page, args.standalone))
    if modes > 1:
        print("--fresh, --new-page and --standalone are separate modes — "
              "one at a time.", file=sys.stderr)
        return 2

    config_dir = locate(args.dir)
    if args.fresh:
        return fresh(config_dir)

    if not config_dir.is_dir():
        print(f"No config directory at {config_dir} — /render:init scaffolds one.",
              file=sys.stderr)
        return 2
    if not qualifies(config_dir):
        print(f"{config_dir} is not a render config yet (needs config.py and "
              "pages/__init__.py) — /render:init scaffolds it.", file=sys.stderr)
        return 2

    if args.new_page:
        return new_page(config_dir, args.new_page, args)
    if args.standalone:
        return standalone(config_dir, args.standalone, args)

    actions = plan(config_dir)
    if not args.check:
        apply(config_dir, actions)
    report(config_dir, actions, args.check)
    drifted = any(a != "current" for _, a in actions)
    return 1 if args.check and drifted else 0


if __name__ == "__main__":
    sys.exit(main())
