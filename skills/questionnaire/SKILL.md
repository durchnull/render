---
description: Build, render and read back a data-driven questionnaire page — scaffold the kind page once, author a JSON spec per questionnaire, render it, and parse the hand-back block the person pastes into the chat. Use when you need to ask someone a set of questions and get structured answers back.
allowed-tools: Read, Write, Edit, Bash(python3:*)
---

# Questionnaire pages on the render engine

## When

You need answers from a person that you cannot derive yourself, and there are
enough of them that asking in chat would be a slog — an intake, a review, a set
of decisions someone has to make before work can continue.

The loop is: **spec in → page out → person answers → hand-back block in →
structured answers out.** You own the first and the last step; the plugin owns
everything between them.

## What this plugin does not decide

The plugin knows how to ask. It does not know **what** to ask or **where the
answers go** — that is the consuming project's business.

- The project's own skill owns the trigger ("when the user starts a new
  engagement, ask the intake questions"), the domain wording, and the routing of
  answers into files, tickets or a plan.
- This skill owns the spec schema, the rendering, and the parsing.

Keep them separate. A project skill that inlines this one's mechanics stops
getting fixes; this skill that learns a project's vocabulary stops being usable
anywhere else.

## 1. Scaffold the kind page — once per project

If `.render/` does not exist yet, run `/render:init` first.

A questionnaire family is one page folder plus a folder for the specs. The page
is about ten lines and never changes again:

```python
# .render/pages/survey/__init__.py
"""Questionnaires — one page per spec in docs/questions/."""

TITLE = "Questionnaire"           # per-page title; each page shows its spec's own
KIND = "questionnaire"            # rendered by the engine's questionnaire kind
SOURCES = "docs/questions/*.json" # glob, relative to ROOT — one output per match
```

`SOURCES` **is the lifecycle.** Every spec that matches becomes a page; move a
spec out of the glob and `--prune` deletes the page that belonged to it. There is
no folder to create or delete per questionnaire, and no registry to update.

Put the specs somewhere that belongs to the project, not inside
`.render/` — they are content, and someone other than you may want to read
them.

## 2. Author a spec

One JSON file per questionnaire. The shape:

```json
{ "id": "2026-08-intake", "title": "Project intake",
  "intro": "markdown", "handback-marker": "ACME INTAKE ANSWERS",
  "sections": [ { "title": "Scope", "questions": [
    { "id": "q01", "question": "…", "why": "one line: what this decides",
      "type": "single", "options": [ { "key": "a", "label": "…" } ],
      "show-if": { "question": "q00", "answer": ["a"] },
      "meta": { "routes-to": "…" } } ] } ] }
```

The rules that matter:

- `id` stable and unique — it keys both the saved answers and the output file
  name; question `id`s are the join key in the hand-back
- `type` is `single` (default) · `multi` · `amount` · `text`; prefer `single`
  over free text; give every question a `why`; use `show-if` rather than
  "if applicable" prose
- option `key`s are short and stable, labels are free to reword
- anything the schema does not know belongs in `meta`, which is never rendered

Strict JSON, no comments. Unknown keys are errors on purpose — a typo that
renders is a question nobody will ever see. The validator prints **every**
finding at once and a failing spec renders nothing, so render and read the
findings; open `${CLAUDE_PLUGIN_ROOT}/docs/spec-questionnaire.md` only when a
finding or an advanced field needs the full schema.

## 3. Render and check

```bash
python3 .render/render.py --check
python3 .render/render.py --page survey:<spec-stem>   # just this one
python3 .render/render.py --prune                     # drop orphaned pages
```

A spec that fails validation is **not rendered** — the run prints every finding
and exits non-zero. Fix the spec; never work around the validator.

Then tell the person where the file is and let them open it. It is one
self-contained file: it works offline, from a USB stick, in a browser with no
network. Their answers stay in that browser until they copy them out.

## 4. Read the hand-back

The summary screen produces a text block behind a copy button. The person pastes
it into the chat. Save the paste to a file (or pipe it in) and let the shipped
parser do the mechanics — never parse it by eye:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/handback.py" paste.txt          # report
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/handback.py" paste.txt --json   # as data
```

The marker is auto-detected, the block is found inside a longer message, and
every item comes back with its state, answers and note. Exit 2 means no usable
block — usually a truncated copy; ask for the paste again. (The grammar lives
in `${CLAUDE_PLUGIN_ROOT}/docs/handback.md`; you should not need it unless the
report surprises you.)

What to do with the result:

- **`[q..]` ids are the join key.** Match them against your spec to reach `meta`
  and anything else the page deliberately never showed.
- **`(key) Label`** — parse the key, quote the label back to the person.
- **`? don't know — please follow up`** is a real answer. It marks what to ask
  about next, in conversation, where a form was the wrong tool.
- **`(skipped)` and `(not answered)`** are different: one is a decision, the
  other is an absence. Neither is an error.
- **Notes matter most where the answer is weakest.** A note on a skipped question
  is usually the reason it was skipped.

### The paste may arrive with no skill running

A person pastes the block whenever they finish, which may be hours later, in a
fresh session, with nothing loaded. Plan for it in the **project's** skill:

- give the marker a distinctive, project-specific name
  (`"handback-marker": "ACME INTAKE ANSWERS"`) so it cannot collide
- have the project skill's `description` name that exact marker, so a paste
  containing it is enough to select the skill
- keep the routing rule in the project skill, not here

## 5. Iterating

Editing a spec re-renders only that page, and the answers already given survive:
they are keyed by the spec `id`, not by the file's contents. Changing the `id`
starts an empty page — so do not change it to fix a typo in the title.

Adding a question mid-flow is safe. Removing one drops it from the hand-back but
leaves the rest untouched.

## Never

- **Never copy the questionnaire kind into a project.** It lives in the engine and
  is imported; a copy forks on day one and never receives a behaviour fix. If a
  project needs a page type the plugin does not ship, it writes its own kind in
  `.render/kinds/<name>.py` — a different thing from forking this one.
- **Never write project-side CSS or JS for these pages.** The interactive
  components, the state kit and the copy mechanics are in the design system; if
  something is missing, it gets added there, documented in `design-manual.md`
  first (section 6b and 11).
- **Never make a question mandatory** and never gate the hand-back on
  completeness. A questionnaire that demands everything gets abandoned; one that
  accepts a third of the answers gets finished later.
- **Never put anything sensitive in a spec** expecting it to stay hidden. The
  page is a plain file; `meta` is invisible to the reader, not secret.
