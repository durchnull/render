# examples/questionnaire-project

A complete, runnable consuming project — a working example and the fixture CI
renders. Nothing here is copied into a real project by any command; it exists to
be read and to be run.

```bash
python3 ../../engine/render.py --config-dir .render --check
```

Two spec files in `docs/questions/`, one page folder, two rendered pages.

## What to look at

| Path | Why |
|---|---|
| `.render/pages/survey/__init__.py` | the entire family: `KIND` + `SOURCES`, ten lines including the docstring |
| `docs/questions/*.json` | one spec per questionnaire — the only thing that changes per instance |
| `.render/config.py` | untouched from the scaffold; a questionnaire needs no project-side configuration |

## Things worth trying

```bash
# One instance by name
python3 ../../engine/render.py --config-dir .render --page survey:2026-08-02-project-intake

# Archive one: the page follows the spec out of the glob
mv docs/questions/2026-08-02-release-readiness.json /tmp/
python3 ../../engine/render.py --config-dir .render          # reports one orphan
python3 ../../engine/render.py --config-dir .render --prune  # deletes it
```

Break a spec on purpose — misspell a key, point a `show-if` at a question that
does not exist — and the run refuses to write that page, reports every finding,
and renders the other one anyway.

The rendered pages land in `.render/output/` and are gitignored: they are
regenerable, and a 70 KB file per spec is not worth versioning.
