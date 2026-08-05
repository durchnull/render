#!/usr/bin/env python3
"""Incremental page renderer — engine of the render plugin.

A project declares any number of pages in its config directory: every
subpackage of ``pages/`` is one page. Its ``__init__.py`` is the page, and
it comes in one of two flavours:

* **section page** — declares ``SECTIONS``; its sibling modules are the
  sections. They are built and cached individually under
  ``<out dir>/.cache/fragments/<page>/``, so a run only rebuilds the
  sections whose inputs or code changed.
* **kind page** — declares ``KIND`` plus ``SOURCES``; the kind
  (``engine/kinds/<name>.py``, or the project's own ``kinds/``) turns each
  spec file matching the glob into one output. The glob is the lifecycle:
  a spec that leaves it takes its page with it (``--prune``).

Either way a run only rewrites the pages whose HTML actually moved; the
rest comes from the cache.

Output is one self-contained HTML file per page or instance — no external
resources. ``<out dir>/<page>.html`` for a section page, the page's
``FILENAME`` template (``{stem}``, ``{pid}``) for a family.

On top of those the engine keeps ``<out dir>/index.html`` — a card per
output, linking to it, rewritten whenever anything the project renders
changes (``index.py``; ``config.INDEX = False`` switches it off).

Usage:
    render.py                     render all pages incrementally
    render.py --page ID[:INST]    only this page, or one instance of it
    render.py --status            report what is stale, build nothing
    render.py --all               discard the cache, rebuild everything
    render.py --only REF          force one section (PAGE/SID) or one
                                  instance (PAGE:INSTANCE), repeatable
    render.py --preview PAGE/SID  render one section as its own small page
    render.py --prune             delete outputs whose spec file is gone
    render.py --check             verify structure and design, sets exit code
    render.py --config-dir DIR    use DIR as the project config directory
    render.py --if-configured     exit 0 silently when no config is found
                                  (for the PostToolUse hook)
"""

import argparse
import html as _html
import importlib
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# No ``__pycache__`` — neither in the plugin installation nor in the consuming
# project. Two reasons, and the second one is a correctness argument: the
# hook renders right after a Write, and CPython invalidates a ``.pyc`` by
# (mtime in whole seconds, size), so an edit that lands in the same second
# without changing the file's size would be executed from the stale bytecode
# while the cache key — read from the source bytes — already moved on.
sys.dont_write_bytecode = True

import index                                                  # noqa: E402
import kinds                                                  # noqa: E402
import project                                                # noqa: E402
import scaffold                                               # noqa: E402
from design_system import (                                   # noqa: E402
    MODAL_JS, TOKENS, BASE_CSS, modal_host, set_strings,
)
from page_api import check_page                               # noqa: E402

CSS = TOKENS + BASE_CSS


class PageError(Exception):
    """A page declares something the engine cannot act on. Aborts that page
    (and only that page), reports, and sets a non-zero exit code."""


TOC_JS = """/* Highlights the section currently being read in the jump bar. */
(function () {
  var links = [].slice.call(document.querySelectorAll('nav.toc a'));
  var map = {};
  links.forEach(function (a) { map[a.getAttribute('href').slice(1)] = a; });
  var secs = [].slice.call(document.querySelectorAll('section[id]'));
  function mark(id) {
    links.forEach(function (a) { a.classList.toggle('is-active', a === map[id]); });
  }
  if (!('IntersectionObserver' in window)) return;
  var seen = {};
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) { seen[e.target.id] = e.isIntersecting ? e.intersectionRatio : 0; });
    var best = null, top = -1;
    secs.forEach(function (s) { if ((seen[s.id] || 0) > top) { top = seen[s.id] || 0; best = s.id; } });
    if (best && top > 0) mark(best);
  }, { rootMargin: '-76px 0px -60% 0px', threshold: [0, 0.25, 0.5, 1] });
  secs.forEach(function (s) { io.observe(s); });
})();"""

DEFAULT_FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
                   "viewBox='0 0 16 16'%3E%3Ctext y='14' font-size='15'%3E"
                   "%F0%9F%93%8A%3C/text%3E%3C/svg%3E")

# User-visible text the engine itself produces. A project may override any
# key via ``config.STRINGS``, a page via its own ``STRINGS`` on top.
DEFAULT_STRINGS = {
    "section_error": (
        "<div class='card'><div class='banner banner--crit'>"
        "<strong>⚠ This section could not be built.</strong> "
        "<code>{error}</code><br>"
        "The remaining sections are up to date. Fix the cause and run "
        "<code>python3 render.py --only {sid}</code>."
        "</div></div>"),
    "preview_eyebrow": "Preview · this section only",
    "preview_title": "Preview · {title}",
    "preview_note": ("Generated from <code>{module}</code>. "
                     "Not the full page — just this excerpt."),
}


# ---------------------------------------------------------------- config ----

def _config():
    import config
    return config


def _cfg(name, default=None):
    return getattr(_config(), name, default)


def _pcfg(page, name, default=None):
    """A page's value for ``name``, falling back to config, then default."""
    return getattr(page, name, _cfg(name, default))


def _strings(page) -> dict:
    merged = dict(DEFAULT_STRINGS)
    merged.update(_cfg("STRINGS", {}) or {})
    merged.update(getattr(page, "STRINGS", {}) or {})
    return merged


def _extra_css(page) -> str:
    """Page-level CSS appended after ``BASE_CSS`` — page, else config, else
    nothing. Tokens only; ``check_page()`` flags raw hex values in it just
    as it does in the token blocks."""
    return _pcfg(page, "EXTRA_CSS", "") or ""


def _rel(p: Path):
    from config import ROOT
    try:
        return p.relative_to(ROOT)
    except ValueError:
        return p


# ----------------------------------------------------------------- pages ----

def page_ids() -> list:
    """Every subpackage of ``pages/`` is one page; ids are lowercase letters."""
    base = Path(project.CONFIG_DIR) / "pages"
    ids = []
    for init in sorted(base.glob("*/__init__.py")):
        pid = init.parent.name
        if re.fullmatch(r"[a-z]+", pid):
            ids.append(pid)
        else:
            print(f"WARN  pages/{pid}/ ignored — page ids are lowercase "
                  "letters only", file=sys.stderr)
    return ids


def load_page(pid: str):
    return importlib.import_module(f"pages.{pid}")


def load_section(pid: str, sid: str):
    """Load a section module lazily — at build time, not at import time."""
    return importlib.import_module(f"pages.{pid}.{sid}")


def activate_page(page) -> None:
    """Per-page global state: design-system strings and the section-meta
    registry that ``content_core.wrap`` reads."""
    from content_core import set_section_meta
    overrides = dict(_cfg("STRINGS", {}) or {})
    overrides.update(getattr(page, "STRINGS", {}) or {})
    set_strings(overrides)
    set_section_meta({s[0]: s for s in getattr(page, "SECTIONS", [])})


# ------------------------------------------------------- flavour & family ----

def flavour(pid: str, page) -> str:
    """``sections`` or ``kind`` — a page declares exactly one of the two.

    Also the single place that checks the declaration hangs together, so a
    half-declared page is reported once, wherever it is first touched.
    """
    has_sections = getattr(page, "SECTIONS", None) is not None
    has_kind = getattr(page, "KIND", None) is not None
    has_sources = bool(getattr(page, "SOURCES", None))
    if has_sections and has_kind:
        raise PageError(f"page {pid} declares both SECTIONS and KIND — "
                        "a page is built either from its own section modules "
                        "or by a kind, never both")
    if not (has_sections or has_kind):
        raise PageError(f"page {pid} declares neither SECTIONS nor KIND — "
                        f"known kinds: {', '.join(kinds.available()) or 'none'}")
    if has_kind and not has_sources:
        raise PageError(f"page {pid} declares KIND without SOURCES — a kind "
                        "page renders one output per spec file, so it needs "
                        "the glob that finds them")
    if has_sections and has_sources:
        raise PageError(f"page {pid} declares SOURCES without KIND — one output "
                        "per source file is a kind-page feature; a section page "
                        "renders exactly one output")
    return "kind" if has_kind else "sections"


def page_kind(pid: str, page):
    """The page's kind, or None for a section page."""
    return kinds.load(page.KIND) if flavour(pid, page) == "kind" else None


def instance_volatile(page, kind) -> bool:
    """Does this family's output depend on today's date?

    Either side may say so: the kind, because every instance it renders
    carries a countdown, or the page, because this one family does. Read in
    one place so ``--status`` and the build can never key an instance
    differently.
    """
    return bool(getattr(page, "VOLATILE", False) or (kind is not None and kind.volatile))


def kind_strings(kind, page) -> dict:
    """The kind's own strings: its English defaults under the project's
    ``config.STRINGS``, under the page's ``STRINGS``. Keys the kind does not
    define are ignored — as in the design system, one dict serves every
    layer and each layer takes only what belongs to it."""
    merged = kind.strings
    for layer in (_cfg("STRINGS", {}) or {}, getattr(page, "STRINGS", {}) or {}):
        merged.update({k: v for k, v in layer.items() if k in merged})
    return merged


_UNSAFE_STEM = re.compile(r"[^a-z0-9]+")
_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def safe_stem(name) -> str:
    """A source file's stem, reduced to what may appear in a file name and in
    a command-line reference."""
    return _UNSAFE_STEM.sub("-", str(name).lower()).strip("-") or "spec"


def safe_filename(name) -> str:
    """Never let a spec decide where to write: directories are stripped, the
    rest is reduced to a plain ``.html`` file name."""
    base = _UNSAFE_NAME.sub("-", Path(str(name)).name).strip("-") or "page"
    return base if base.endswith(".html") else f"{base}.html"


def sources(pid: str, page) -> list:
    """The spec files of a page family, in stable order. No ``SOURCES`` means
    a single-output page; an empty glob is not an error — it renders nothing.
    """
    if flavour(pid, page) != "kind":
        return []
    pattern = getattr(page, "SOURCES")
    from config import ROOT
    found = sorted((p for p in Path(ROOT).glob(str(pattern)) if p.is_file()),
                   key=lambda p: str(p))
    seen = {}
    for p in found:
        seen.setdefault(safe_stem(p.stem), []).append(p)
    clashing = {s: v for s, v in seen.items() if len(v) > 1}
    if clashing:
        detail = "; ".join(f"{s}: {', '.join(str(_rel(p)) for p in v)}"
                           for s, v in sorted(clashing.items()))
        raise PageError(f"page {pid}: two source files share one instance name "
                        f"and would overwrite each other — {detail}")
    return found


def out_name(pid: str, page, kind, spec, src, stem: str) -> str:
    """The output file name for one instance.

    A kind may decide it (``filename()``); otherwise the page's ``FILENAME``
    serves as a template with ``{stem}`` and ``{pid}``. Single-output pages
    keep taking ``FILENAME`` literally — it was never a template there.
    """
    if src is None:
        return getattr(page, "FILENAME", f"{pid}.html")
    chosen = kind.filename(spec, src, pid) if kind else None
    if chosen is None:
        template = getattr(page, "FILENAME", None) or f"{pid}-{{stem}}.html"
        try:
            chosen = template.format(stem=stem, pid=pid)
        except (KeyError, IndexError) as exc:
            raise PageError(f"page {pid}: FILENAME template {template!r} uses "
                            f"an unknown placeholder ({exc}) — available: "
                            "{stem}, {pid}") from None
    return safe_filename(chosen)


def out_path(pid: str, page, name: str = None) -> Path:
    return project.out_dir() / (name or getattr(page, "FILENAME", f"{pid}.html"))


def _hero(page) -> str:
    hero = getattr(page, "hero", None)
    return hero() if callable(hero) else (getattr(page, "HERO_HTML", "") or "")


def _footer(page, generated: str) -> str:
    footer = getattr(page, "footer", None)
    if callable(footer):
        return footer(generated)
    tpl = getattr(page, "FOOTER_HTML", "") or ""
    return tpl.format(generated=generated) if tpl else ""


# ------------------------------------------------------------- fragments ----

def _fallback(pid: str, sid: str, exc: Exception, strings: dict) -> str:
    """Substitute body when a section fails to build and no fragment is
    cached — the remaining sections must still appear."""
    from content_core import wrap
    error = _html.escape(f"{type(exc).__name__}: {exc}")
    return wrap(sid, strings["section_error"].format(error=error, sid=f"{pid}/{sid}"))


def collect(pid: str, page, old: dict, shared: str, force=False, only=frozenset()):
    """Fetch one page's sections — from the cache or freshly built.

    Returns: (fragments, tails, entries, built, changed, failed)

    ``built`` are the sections that were computed; ``changed`` those whose
    HTML actually moved in the process. Not the same thing: a code refactor
    can force a rebuild that yields byte-identical HTML.

    If a section fails, its last valid fragment stays in place (and its
    manifest entry invalid, so the next run tries again). A broken ``.md``
    no longer takes the whole page down.
    """
    import cache
    phash = cache.page_hash(pid)
    strings = _strings(page)
    frags, tails, new = {}, {}, {}
    built, changed, failed = [], [], []

    for sid in (s[0] for s in page.SECTIONS):
        mod = load_section(pid, sid)
        key = cache.section_key(mod, shared, phash)
        prev = old.get(sid, {})

        stale = force or f"{pid}/{sid}" in only or prev.get("key") != key
        frag = None if stale else cache.read_fragment(pid, sid)

        if frag is None:
            try:
                result = mod.build()
                frag, tail = result if isinstance(result, tuple) else (result, "")
                tail = tail or ""
                cache.write_fragment(pid, sid, frag)
                cache.write_fragment(pid, sid, tail, "tail")
                built.append(sid)
            except Exception as exc:                       # noqa: BLE001
                failed.append((sid, exc))
                stale_frag = cache.read_fragment(pid, sid)
                frag = stale_frag if stale_frag is not None else _fallback(pid, sid, exc, strings)
                tail = cache.read_fragment(pid, sid, "tail") or ""
                # Key deliberately not stored: the next run tries again.
                frags[sid], tails[sid] = frag, tail
                new[sid] = {"key": "", "html": prev.get("html", "")}
                continue
        else:
            tail = cache.read_fragment(pid, sid, "tail") or ""

        digest = cache.content_hash(frag, tail)
        if prev.get("html") != digest:
            changed.append(sid)

        frags[sid], tails[sid] = frag, tail
        new[sid] = {"key": key, "html": digest}

    return frags, tails, new, built, changed, failed


def stale_units() -> dict:
    """Which units would need a rebuild, per page? Builds nothing — for
    ``--status``. A section page reports section ids, a kind page the stems
    of the instances whose spec or kind moved."""
    import cache
    shared = cache.shared_hash()
    manifest = cache.load_manifest()
    out = {}
    for pid in page_ids():
        page = load_page(pid)
        phash = cache.page_hash(pid)
        try:
            kind = page_kind(pid, page)
            if kind is None:
                old = manifest["pages"].get(pid, {})
                stale = [sid for sid in (s[0] for s in page.SECTIONS)
                         if old.get(sid, {}).get("key")
                         != cache.section_key(load_section(pid, sid), shared, phash)]
            else:
                old = manifest["kinds"].get(pid, {})
                khash = kind.code_hash()
                vol = instance_volatile(page, kind)
                stale = [safe_stem(src.stem) for src in sources(pid, page)
                         if old.get(safe_stem(src.stem), {}).get("key")
                         != cache.instance_key(shared, phash, khash, src, vol)]
        except (PageError, kinds.KindError) as exc:
            out[pid] = [f"unusable — {exc}"]
            continue
        if stale:
            out[pid] = stale
    return out


# ------------------------------------------------------------- instances ----

class Instance:
    """One output file of a kind page, before it is built."""

    def __init__(self, pid: str, stem: str, src: Path):
        self.pid, self.stem, self.src = pid, stem, src

    @property
    def ref(self) -> str:
        return f"{self.pid}:{self.stem}"


class Rendered:
    """One finished output file — a whole section page, or one instance of a
    kind page. Everything the reporting, writing and checking steps need."""

    def __init__(self, pid, page, out, html, previous, *, stem=None, kind=None,
                 spec=None, ctx=None, entry=None, entries=None, built=(), changed=(),
                 failed=(), units=1):
        self.pid, self.page, self.out = pid, page, out
        self.html, self.previous = html, previous
        self.stem, self.kind, self.spec = stem, kind, spec
        # Carried even when the instance came straight from disk: the index
        # asks the kind to describe every instance, built or cached.
        self.ctx = ctx
        self.entry, self.entries = entry, entries
        self.built, self.changed, self.failed = list(built), list(changed), list(failed)
        self.units = units

    @property
    def ref(self) -> str:
        return f"{self.pid}:{self.stem}" if self.stem else self.pid

    @property
    def moved(self) -> bool:
        return bool(self.changed) or self.previous != self.html


def instances(pid: str, page) -> list:
    return [Instance(pid, safe_stem(src.stem), src) for src in sources(pid, page)]


def build_instance(inst: Instance, page, kind, entries: dict, shared: str,
                   force=False, only=frozenset()) -> Rendered:
    """Build — or take unchanged from disk — one kind-page instance.

    Raises ``SpecError`` when the spec is unusable: the caller reports every
    finding and writes nothing for this instance. Unlike a failing section,
    this never degrades into a fallback, because a questionnaire rendered
    from a broken spec is worse than no questionnaire at all.

    The **output file is its own cache**: a kind page is one indivisible
    unit, so a fragment store would only hold a second copy of it. The spec
    is parsed and validated on every run either way — it costs microseconds,
    and it means a spec that went bad is reported even when the page it
    produced is still sitting on disk.
    """
    import cache
    pid, stem, src = inst.pid, inst.stem, inst.src
    # Built before the spec is parsed, not after: a kind whose source may
    # leave a value to the project has to resolve that chain while reading.
    ctx = kinds.BuildContext(page, pid, stem, src, kind_strings(kind, page),
                             setting=lambda name, default=None: _pcfg(page, name, default))
    spec = kind.load(src, ctx)
    findings = kind.validate(spec, src)
    if findings:
        raise kinds.SpecError(findings)

    name = out_name(pid, page, kind, spec, src, stem)
    out = out_path(pid, page, name)
    key = cache.instance_key(shared, cache.page_hash(pid), kind.code_hash(), src,
                             instance_volatile(page, kind))
    prev = entries.get(stem, {})
    previous = out.read_text(encoding="utf-8") if out.exists() else None

    if (not force and inst.ref not in only and previous is not None
            and prev.get("key") == key and prev.get("out") == name):
        return Rendered(pid, page, out, previous, previous, stem=stem, kind=kind,
                        spec=spec, ctx=ctx, entry=dict(prev))

    body, tail = kind.build(spec, ctx)
    generated = datetime.now().strftime(_pcfg(page, "GENERATED_FMT", "%Y-%m-%d"))
    html = shell(page, body, tail,
                 hero=_hero(page),
                 foot=_footer(page, generated) or kind.footer(spec, ctx, generated),
                 extra_css=kind.css() + _extra_css(page),
                 scripts=kind.scripts(),
                 wrap_class=kind.wrap_class, chrome=False)
    entry = {"key": key, "html": cache.content_hash(html), "out": name}
    return Rendered(pid, page, out, html, previous, stem=stem, kind=kind, spec=spec,
                    ctx=ctx, entry=entry, built=[stem],
                    changed=[stem] if previous != html else [])


# ----------------------------------------------------------------- shell ----

def shell(page, body: str, tail: str, title: str = None, nav: str = "",
          hero: str = "", foot: str = "", extra_css: str = "",
          scripts: str = "", wrap_class: str = "wrap", chrome: bool = True) -> str:
    """Self-contained HTML page around a finished body.

    ``extra_css`` lands inside the same ``<style>`` block after ``BASE_CSS``
    (page-level CSS, tokens only — ``check_page()`` flags raw hex there as
    everywhere else). ``chrome=True`` adds the engine's standard page
    furniture: the detail-modal host plus the jump-bar and modal scripts.
    Kind pages switch it off and bring their own ``scripts`` instead of
    shipping two dead ones. The defaults reproduce a section page's HTML
    byte for byte.
    """
    lang = _pcfg(page, "LANG", "en")
    favicon = _pcfg(page, "FAVICON_HREF", DEFAULT_FAVICON)
    if chrome:
        end = f"""{modal_host()}
<script>
{TOC_JS}
{MODAL_JS}{scripts}
</script>"""
    else:
        end = f"<script>{scripts}\n</script>" if scripts else ""
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title if title is not None else page.TITLE}</title>
<link rel="icon" href="{favicon}">
<style>{CSS}{extra_css}</style>
</head>
<body>
<div class="{wrap_class}">
{hero}{nav}
{body}
{foot}
</div>
{tail}
{end}
</body>
</html>
"""


def compose(pid: str, page, frags: dict, tails: dict) -> str:
    sections = page.SECTIONS
    ids = [s[0] for s in sections]
    # The jump bar appears automatically on pages with two or more sections.
    nav = ""
    if len(sections) >= 2:
        nav = "  <nav class=\"toc\">" + "".join(
            f"<a href='#{sid}'>{short}</a>" for sid, _, _, _, _, short in sections
        ) + "</nav>"
    body = "".join(frags[sid] for sid in ids)
    tail = "".join(tails[sid] for sid in ids if tails[sid])

    # Date only, no time of day: otherwise the file differs on every run and
    # the hook would rewrite it even when nothing else changed.
    generated = datetime.now().strftime(_pcfg(page, "GENERATED_FMT", "%Y-%m-%d"))
    return shell(page, body, tail, nav=nav, hero=_hero(page),
                 foot=_footer(page, generated), extra_css=_extra_css(page))


def preview(pid: str, sid: str) -> Path:
    """A single section as its own small page — to inspect a change without
    loading or screenshotting the full page."""
    page = load_page(pid)
    activate_page(page)
    mod = load_section(pid, sid)
    result = mod.build()
    frag, tail = result if isinstance(result, tuple) else (result, "")
    title = {s[0]: s for s in page.SECTIONS}[sid][3]
    s = _strings(page)
    note = s["preview_note"].format(module=_rel(Path(mod.__file__)))
    hero = (f'  <header class="hero"><div class="eyebrow">{s["preview_eyebrow"]}</div>'
            f'<h1>{title}</h1><p>{note}</p></header>\n')
    out = project.out_dir() / f".preview-{pid}-{sid}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(shell(page, frag, tail or "", title=s["preview_title"].format(title=title),
                         hero=hero, extra_css=_extra_css(page)),
                   encoding="utf-8")
    return out


# ----------------------------------------------------------------- check ----

def check(page, text: str, kind=None, spec=None) -> list:
    """Deterministic assertions about one generated page.

    Replaces eyeballing: a screenshot proves none of this reliably, these
    checks do — and cost nothing. The generic half (self-containment, token
    fidelity, unresolved placeholders) lives in ``page_api.check_page`` so
    standalone renderers run exactly the same checks. What comes on top
    depends on the page's flavour: a section page is checked for its
    sections and its jump bar, a kind page by its own kind — the structural
    assertions of one flavour say nothing about the other.
    """
    errors = check_page(text)
    if kind is not None:
        # No DESCRIPTION assertion here: a kind page's cards are written per
        # instance by the kind's summary() hook, so the page-level field is
        # never read for one and demanding it would be demanding nothing.
        return errors + kind.check(spec, text)

    # The index card is the only place a page introduces itself to someone
    # who has not opened it, and it is built from this one field. Without it
    # the card is a title and nothing else: a page that renders perfectly,
    # passes every other assertion, and says nothing about what it is for.
    # Only worth asserting while there is an index to carry the card.
    if _cfg("INDEX", True) and not str(getattr(page, "DESCRIPTION", "") or "").strip():
        errors.append("no DESCRIPTION — its index card cannot say what the "
                      "page is for")

    ids_expected = [s[0] for s in page.SECTIONS]

    ids = re.findall(r"<section id='([a-z]+)'>", text)
    missing = [s for s in ids_expected if s not in ids]
    if missing:
        errors.append(f"missing section: {', '.join(missing)}")
    if len(ids) != len(set(ids)):
        errors.append("duplicate section id")

    if len(ids_expected) >= 2:
        nav = re.findall(r"<nav class=\"toc\">(.*?)</nav>", text, re.S)
        targets = re.findall(r"href='#([a-z]+)'", nav[0]) if nav else []
        if targets != ids_expected:
            errors.append(f"jump bar does not match the sections: {targets}")

    # Suspiciously empty section bodies.
    for sid in ids:
        i = text.index(f"<section id='{sid}'>")
        j = text.find("<section id='", i + 10)
        chunk = text[i:(j if j > 0 else text.find("<footer>", i))]
        if len(chunk) < 300:
            errors.append(f"section {sid} has a suspiciously empty body")

    return errors


# ------------------------------------------------------------------- cli ----
#
# Two reference syntaxes, one per flavour, and they cannot be confused:
#   ``page/section``  addresses a section of a section page
#   ``page:instance`` addresses one output of a kind page (the spec's stem)

def _split_ref(ref: str):
    pid, _, sid = ref.partition("/")
    return pid, sid


def _units(results) -> str:
    """'5 sections' / '2 instances' / both — a run may hold either flavour."""
    sections = sum(r.units for r in results if r.kind is None)
    made = sum(1 for r in results if r.kind is not None)
    parts = [f"{sections} sections"]
    if made:
        parts.append(f"{made} instance{'s' if made != 1 else ''}")
    return ", ".join(parts)


def find_orphans(manifest_kinds: dict, live: dict, trusted: set, known: set) -> list:
    """Recorded instance outputs whose spec file is gone.

    The glob is the lifecycle: a project archives an instance by moving its
    spec out of ``SOURCES``, and the page that belonged to it becomes an
    orphan. Only entries the manifest wrote are ever considered — the output
    directory is never globbed for deletion candidates — and only for pages
    whose instance list this run actually enumerated (``trusted``), so a
    ``--page`` run can never prune what it did not look at.
    """
    found = []
    for pid, entries in sorted(manifest_kinds.items()):
        if pid not in known:                      # the page folder itself is gone
            found += [(pid, stem, e.get("out")) for stem, e in sorted(entries.items())]
        elif pid in trusted:
            alive = live.get(pid, {})
            found += [(pid, stem, e.get("out")) for stem, e in sorted(entries.items())
                      if stem not in alive]
    return [(pid, stem, name) for pid, stem, name in found if name]


# ----------------------------------------------------------------- index ----
#
# The index is the one page no project declares: the engine keeps it because
# a directory of HTML files is not an entry point. It is composed from
# records, not from the pages themselves, so a ``--page`` run refreshes the
# cards it touched and leaves the others exactly as they were.

def index_strings() -> dict:
    """The index's own text: English defaults under the project's
    ``STRINGS``, keys it does not define ignored — as everywhere else."""
    merged = dict(index.STRINGS)
    merged.update({k: v for k, v in (_cfg("STRINGS", {}) or {}).items()
                   if k in merged})
    return merged


def index_path() -> Path:
    """Sanitized like every other name the engine takes from a declaration —
    the index belongs next to the pages it links to, so ``INDEX_FILENAME``
    names a file there and never a path out of the output directory."""
    return project.out_dir() / safe_filename(_cfg("INDEX_FILENAME")
                                             or index.FILENAME)


def index_record(r: Rendered, strings: dict) -> dict:
    """One card record for a finished output, whichever flavour made it."""
    if r.kind is None:
        return index.section_record(r.pid, r.page, r.out.name, strings)
    from config import ROOT
    return index.instance_record(r.pid, r.stem, r.page, r.kind, r.spec, r.ctx,
                                 r.out.name, r.ctx.src, Path(ROOT), strings)


def index_records(results, records: dict, pids, strings: dict) -> dict:
    """The records this run leaves behind: what it rendered, plus what it did
    not look at — minus everything whose output is no longer on disk.

    That last rule is the whole lifecycle in one line. A pruned instance, a
    page folder that was deleted and a file someone removed by hand are three
    different events, and none of them has to be recognised as such: the
    index lists output files, so it lists the ones that exist.
    """
    out_dir = project.out_dir()
    for r in results:
        records[r.ref] = index_record(r, strings)
    return {ref: rec for ref, rec in records.items()
            if rec.get("pid") in pids and rec.get("out")
            and (out_dir / rec["out"]).exists()}


def write_index(records: dict, quiet: bool):
    """Compose and write the index, unless the project switched it off or a
    page of its own already owns the file name.

    Returns ``(html, moved)`` — ``html`` is None when no index was written,
    ``moved`` says whether the file on disk changed, so the caller can report
    it alongside the pages instead of ahead of them.

    A page that writes ``index.html`` wins without discussion: the project
    declared it, the engine merely offers one. Overwriting it would be the
    engine deleting a page it was asked to render.
    """
    if not _cfg("INDEX", True):
        return None, False
    out = index_path()
    if out.name in {rec.get("out") for rec in records.values()}:
        if not quiet:
            print(f"note  {_rel(out)} is a page of this project — "
                  "the engine's index is not written", file=sys.stderr)
        return None, False
    fmt = _cfg("GENERATED_FMT", "%Y-%m-%d")
    html = index.build(records, index_strings(), project.out_dir(),
                       datetime.now().strftime(fmt), fmt, shell)
    previous = out.read_text(encoding="utf-8") if out.exists() else None
    if previous == html:
        return html, False
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return html, True


def _say_drift(config_dir):
    """One line when the project's plugin-owned copies are behind — see
    ``scaffold.note`` for what it can honestly claim."""
    drift = scaffold.note(config_dir)
    if drift:
        print(drift, file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description="Render the project's pages (incrementally).")
    ap.add_argument("--config-dir", metavar="DIR",
                    help="project config directory (default: auto-discovery)")
    ap.add_argument("--if-configured", action="store_true",
                    help="exit 0 silently when no project config is found (for hooks)")
    ap.add_argument("--page", action="append", metavar="ID[:INSTANCE]", default=[],
                    help="render only this page, or one instance of a kind page "
                         "(repeatable)")
    ap.add_argument("--status", action="store_true",
                    help="only report what is stale — writes nothing")
    ap.add_argument("--all", action="store_true", help="discard the cache, rebuild everything")
    ap.add_argument("--only", action="append", metavar="REF", default=[],
                    help="force this section (PAGE/SID) or instance (PAGE:INSTANCE), "
                         "repeatable")
    ap.add_argument("--preview", metavar="PAGE/SID",
                    help="render only this section as its own page")
    ap.add_argument("--prune", action="store_true",
                    help="delete outputs of kind-page instances whose spec file is gone")
    ap.add_argument("--check", action="store_true",
                    help="verify structure, self-containment and design of the pages")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="print nothing when nothing changed (for the hook)")
    args = ap.parse_args()

    config_dir = project.locate(args.config_dir)
    if config_dir is None:
        if args.if_configured:
            return 0
        print("No renderer config found (config.py + pages/ — see plugin README).\n"
              "Pass --config-dir or set RENDERER_CONFIG_DIR.", file=sys.stderr)
        return 2
    project.activate(config_dir)

    # Said on every run a person watches: the project's copies of the
    # plugin's files have fallen behind the installation, and nobody would
    # think to look. The hook's quiet run says it only when it has something
    # else to say — a drifted project would otherwise hear the same line
    # (and pay the byte compares) after every single Write/Edit.
    if not args.quiet:
        _say_drift(config_dir)

    pids = page_ids()
    if not pids:
        if args.if_configured:
            return 0
        print("No pages found — every subpackage of pages/ is one page "
              "(pages/<id>/__init__.py).", file=sys.stderr)
        return 2

    # Every addressable unit: "page/section" for section pages, "page:instance"
    # for kind pages. Pages that cannot be read at all are reported when they
    # are rendered, not here — a broken page must not block the others.
    known_refs = set()
    for pid in pids:
        page = load_page(pid)
        try:
            if page_kind(pid, page) is None:
                known_refs |= {f"{pid}/{s[0]}" for s in page.SECTIONS}
            else:
                known_refs |= {f"{pid}:{safe_stem(s.stem)}" for s in sources(pid, page)}
        except (PageError, kinds.KindError):
            continue

    # --page takes a page or a single instance of one: "faq", "survey:2026-q3".
    wanted, unknown = {}, []
    for ref in args.page:
        pid, _, stem = ref.partition(":")
        if pid not in pids or (stem and f"{pid}:{safe_stem(stem)}" not in known_refs):
            unknown.append(ref)
            continue
        wanted.setdefault(pid, set())
        if stem:
            wanted[pid].add(safe_stem(stem))
    if unknown:
        instance_refs = sorted(r for r in known_refs if ":" in r)
        extra = f"\nKnown instances: {', '.join(instance_refs)}" if instance_refs else ""
        print(f"Unknown page: {', '.join(unknown)}\nKnown: {', '.join(pids)}{extra}",
              file=sys.stderr)
        return 2
    selected = list(wanted) or pids

    bad_refs = [r for r in args.only if r not in known_refs]
    if bad_refs:
        print(f"Unknown section or instance: {', '.join(bad_refs)}\n"
              f"Known: {', '.join(sorted(known_refs))}", file=sys.stderr)
        return 2

    if args.preview:
        pid, sid = _split_ref(args.preview)
        page = load_page(pid) if pid in pids else None
        if page is None or f"{pid}/{sid}" not in {
                f"{pid}/{s[0]}" for s in getattr(page, "SECTIONS", []) or []}:
            hint = ""
            if page is not None and getattr(page, "KIND", None) is not None:
                hint = (f"\n{pid} is a kind page ({page.KIND}) — it has no sections "
                        f"to preview. Render one instance with --page {pid}:<instance>.")
            print(f"Unknown section: {args.preview}{hint}", file=sys.stderr)
            return 2
        out = preview(pid, sid)
        print(f"OK  {_rel(out)} written (section {args.preview} only)")
        return 0

    if args.status:
        stale = stale_units()
        if not stale:
            print("up to date — nothing to do")
        for pid, units in stale.items():
            print(f"stale: {pid}: {', '.join(units)}")
        return 0

    import cache
    t0 = time.perf_counter()
    if args.all:
        cache.clear()

    shared = cache.shared_hash()
    manifest = cache.load_manifest()
    manifest_pages, manifest_kinds = manifest["pages"], manifest["kinds"]
    forced = set(args.only)
    results, aborted, empty_families = [], [], []
    live, trusted = {}, set()

    for pid in selected:
        page = load_page(pid)
        activate_page(page)
        try:
            kind = page_kind(pid, page)
            todo = instances(pid, page) if kind else None
        except (PageError, kinds.KindError) as exc:
            aborted.append((pid, [str(exc)]))
            continue

        if kind is None:
            frags, tails, entries, built, changed, failed = collect(
                pid, page, manifest_pages.get(pid, {}), shared,
                force=args.all, only=forced)
            html_out = compose(pid, page, frags, tails)
            out = out_path(pid, page)
            previous = out.read_text(encoding="utf-8") if out.exists() else None
            manifest_pages[pid] = entries
            results.append(Rendered(pid, page, out, html_out, previous, entries=entries,
                                    built=built, changed=changed, failed=failed,
                                    units=len(page.SECTIONS)))
            continue

        # A kind page: one output per spec file that matches SOURCES.
        entries = manifest_kinds.setdefault(pid, {})
        picked = wanted.get(pid) or set()
        live[pid] = {}
        trusted.add(pid)
        if not todo:
            empty_families.append((pid, getattr(page, "SOURCES", "")))
        for inst in todo:
            if picked and inst.stem not in picked:
                live[pid][inst.stem] = entries.get(inst.stem, {}).get("out")
                continue
            try:
                r = build_instance(inst, page, kind, entries, shared,
                                   force=args.all, only=forced)
            except kinds.SpecError as exc:
                aborted.append((inst.ref, exc.findings))
                # The instance keeps its previous output and its manifest entry:
                # deleting a page someone has open is worse than a loud error.
                live[pid][inst.stem] = entries.get(inst.stem, {}).get("out")
                continue
            entries[inst.stem] = r.entry
            live[pid][inst.stem] = r.entry["out"]
            results.append(r)

    for r in results:
        r.out.parent.mkdir(parents=True, exist_ok=True)
        if r.previous != r.html:
            r.out.write_text(r.html, encoding="utf-8")

    # Orphans: recorded outputs whose spec left the glob. Only --prune deletes.
    orphans = find_orphans(manifest_kinds, live, trusted, set(pids))
    if args.prune:
        for pid, stem, name in orphans:
            path = project.out_dir() / name
            if path.exists():
                path.unlink()
            print(f"pruned  {_rel(path)} ({pid}:{stem} — source gone)")
            manifest_kinds.get(pid, {}).pop(stem, None)
        manifest_kinds = {p: v for p, v in manifest_kinds.items() if v}

    # The index, after everything else has landed: it reads the finished
    # files, so it has to be composed once the writing and pruning are done.
    records = index_records(results, manifest["index"], set(pids), index_strings())
    index_html, index_moved = write_index(records, args.quiet)

    # Drop pages that no longer exist; keep the entries of unselected ones.
    cache.save_manifest({"version": cache.VERSION,
                         "pages": {p: v for p, v in manifest_pages.items() if p in pids},
                         "kinds": {p: v for p, v in manifest_kinds.items() if p in pids},
                         "index": records})
    ms = (time.perf_counter() - t0) * 1000

    for r in results:
        for sid, exc in r.failed:
            print(f"ERROR  section {r.pid}/{sid}: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
            if not args.quiet:
                traceback.print_exception(type(exc), exc, exc.__traceback__, limit=3,
                                          file=sys.stderr)
    for ref, findings in aborted:
        for finding in findings:
            print(f"SPEC   {ref}: {finding}", file=sys.stderr)
        print(f"ERROR  {ref}: nothing written — fix the findings above",
              file=sys.stderr)

    if args.check:
        findings = []
        for r in results:
            findings += [f"{r.ref}: {f}"
                         for f in check(r.page, r.html, kind=r.kind, spec=r.spec)]
        if index_html is not None:
            # The generic half only: the index has no sections and no kind,
            # so the structural assertions of neither flavour apply to it.
            findings += [f"{index_path().name}: {f}"
                         for f in check_page(index_html)]
        if findings:
            for f in findings:
                print(f"CHECK  {f}", file=sys.stderr)
            return 1
        kb = sum(len(r.html.encode("utf-8")) for r in results) / 1024
        extra = " + index" if index_html is not None else ""
        print(f"check OK — {len(results)} pages{extra}, {_units(results)}, "
              f"{kb:.0f} KB, 0 external references, colors only from tokens")

    for pid, pattern in empty_families:
        if not args.quiet:
            print(f"OK  {pid}: no spec matches {pattern!r} — nothing to render")
    if orphans and not args.prune and not args.quiet:
        print(f"note  {len(orphans)} output(s) without a source file — "
              "run with --prune to delete them")

    if aborted or any(r.failed for r in results):
        if args.quiet:
            _say_drift(config_dir)
        return 1

    moved = [r for r in results if r.moved]
    if not moved and not args.quiet:
        print(f"OK  unchanged — {len(results)} pages, {_units(results)} "
              f"from cache ({ms:.0f} ms)")

    for r in moved:
        if r.kind is None:
            ids = [s[0] for s in r.page.SECTIONS]
            from_cache = [s for s in ids if s not in r.built]
            parts = [f"new: {', '.join(r.changed) if r.changed else '—'}"]
            if from_cache:
                parts.append(f"from cache: {len(from_cache)}")
        else:
            parts = [f"{r.kind.name} {r.stem}"]
        parts.append(f"{len(r.html.encode('utf-8')) / 1024:.0f} KB")
        print(f"OK  {_rel(r.out)} · {' · '.join(parts)} ({ms:.0f} ms)")

    # Last, because it is derived from all of the above — and reported even
    # under ``-q``, which silences unchanged runs, not changes.
    if index_moved:
        print(f"OK  {_rel(index_path())} · index · {len(records)} pages · "
              f"{len(index_html.encode('utf-8')) / 1024:.0f} KB")
    if args.quiet and (moved or index_moved):
        _say_drift(config_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
