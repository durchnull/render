# examples/section-project

A complete, runnable consuming project — a working example and the fixture CI
renders. Nothing here is copied into a real project by any command; it exists to
be read and to be run.

```bash
python3 ../../engine/render.py --config-dir .render --check
```

The two sibling examples are **kind** pages: one declaration, one output per
data file. This is the other half of the contract — a **section page**, where
the project designs the page itself and every section declares what it is built
from. Three files in `docs/`, one page folder, one rendered page.

## What to look at

| Path | Why |
|---|---|
| `.render/pages/status/__init__.py` | the page: `TITLE`, `DESCRIPTION`, `SECTIONS`, a custom hero — no build logic |
| `.render/pages/status/overview.py` | `INPUTS` over a document — frontmatter feeds the tiles, the body is the prose |
| `.render/pages/status/work.py` | `INPUTS` over a data file — a filter row and a show-all list, both view-only |
| `.render/pages/status/notes.py` | `LISTING` + `VOLATILE` — a directory's shape, never its contents |
| `docs/` | the three files a maintainer actually edits; the page is a view of them |

## The point: each section teaches one cache answer

The render is incremental because every section says what it is built from, and
the engine keys the fragment on exactly that. The three sections here exist to
show the three answers, so the table below is the example:

| Section | Declares | Keyed on |
|---|---|---|
| `overview` | `INPUTS = ["docs/status.md"]` | a SHA over the file's **bytes** |
| `work` | `INPUTS = ["docs/work.json"]` | a SHA over the file's **bytes** |
| `notes` | `LISTING = ["docs/notes/*.md"]`, `VOLATILE = True` | path, size and modification **date** — the files are never opened — plus today |

`INPUTS` and `LISTING` are a real trade, not two names for one thing:

```bash
touch docs/status.md                       # same bytes
python3 ../../engine/render.py --config-dir .render   # unchanged — 3 sections from cache

sed -i '' 's/^tests: 412/tests: 418/' docs/status.md
python3 ../../engine/render.py --config-dir .render   # new: overview · from cache: 2
```

`INPUTS` hashes content, so a touch is free and any edit rebuilds. `LISTING`
never opens the files, which stays cheap over a directory of hundreds — the
trade is a coarser key: a note that appears, disappears, is renamed, changes
size, or is saved on a later day invalidates `notes`, while re-saving one with
identical bytes on the same day does not.

```bash
printf -- "\n- **Fixed** — one more entry\n" >> docs/notes/0.8.1-2026-06-02.md
python3 ../../engine/render.py --config-dir .render   # new: notes · from cache: 2
```

`VOLATILE = True` on `notes` says the output has a shelf life — its "last
edited" column is measured against today, so it is rebuilt once per day instead
of on every run.

## Things worth trying

```bash
# Add a fourth section: a line in SECTIONS plus a sibling module of that name
python3 ../../engine/render.py --config-dir .render --page status

# Delete DESCRIPTION from the page and --check refuses it: the index card
# is the only place a page introduces itself
python3 ../../engine/render.py --config-dir .render --check
```

Empty the frontmatter of `docs/status.md` and the tiles fall back to `—`
rather than breaking the page; delete the file entirely and the section renders
one `.empty` line, because a card around nothing is a rendered nothing
(design-manual §5).

The rendered page lands in `.render/output/` and is gitignored: it is
regenerable, and a file that size is not worth versioning.
