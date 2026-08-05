# examples/checklist-project

A complete, runnable consuming project — a working example and the fixture CI
renders. Nothing here is copied into a real project by any command; it exists to
be read and to be run.

```bash
python3 ../../engine/render.py --config-dir .render --check
```

One markdown checklist in `docs/checklists/`, one page folder, one rendered page.

## The fixture is deliberately messy

`docs/checklists/2026-08-release.md` is not a tidy example. Every awkward shape a
real maintained document grows is in it on purpose, because each one is a bug a
clean fixture would pass and a real file would fail:

| In the file | What it proves |
|---|---|
| paragraphs between the item blocks, and a list that is not a checklist | prose renders where it stands, and a plain `-` list is not counted as items |
| a `###` subhead inside a group, and a bold-only line titling the block below it | the parser emits an ordered block list, not just items |
| `🗄️` on one item and one paragraph, `**Superseded` on another paragraph | exclusion is per block — one item or one paragraph among its siblings, not a whole section |
| `path:`, `due:`, and an `owner:` the vocabulary does not know | declared annotations render as themselves; anything else passes through as detail rather than erroring |
| `~~[ ] …~~` and `[x] ~~…~~` | obsolete is obsolete whatever the checkbox says, and it counts in neither half of the ratio |
| "Run the full test suite" in two groups, one of them with `**bold**` in it | the fingerprint ignores markup, so the two collide on text and are separated by their heading |
| `deadline:` and `exclude:` in the frontmatter | the document is in front of the page and the project config for both |

## The file that is meant to be refused

`docs/rejected/duplicate-in-one-group.md` sits **outside** the page's `SOURCES`
glob, so no page is ever rendered from it. It carries the one case the kind
refuses outright — two identical instructions in one group — and the test suite
asserts the refusal. Keeping it out of the glob is what lets the example stay
green while still carrying the case.

## Things worth trying

```bash
# What the page is keyed on: change an annotation and the fingerprints hold
python3 ../../engine/render.py --config-dir .render --page checklist:2026-08-release

# Archive it: the page follows the file out of the glob
mv docs/checklists/2026-08-release.md /tmp/
python3 ../../engine/render.py --config-dir .render          # reports one orphan
python3 ../../engine/render.py --config-dir .render --prune  # deletes it
```

Add `🗄️` to the front of any item and it leaves the page entirely: no
fingerprint, no place in the totals, no way for it to appear in a hand-back.
Remove the `exclude:` line from the frontmatter and every one of them comes back.

The rendered page lands in `.render/output/` and is gitignored: it is
regenerable, and a file that size per checklist is not worth versioning.
