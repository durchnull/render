---
description: Turn a checklist the project maintains into an interactive page, then apply what comes back — render a markdown checklist as a page someone can tick and annotate, parse the changes block they paste into the chat, and edit the source file from it. Use when a project has a checklist document that people work through.
allowed-tools: Read, Write, Edit, Bash(python3:*)
---

# Checklist pages on the render engine

## When

The project maintains a checklist as a markdown file — a release checklist, an
onboarding list, a set of steps somebody works through — and somebody has to
actually work through it.

The loop is: **document in → page out → person ticks and annotates → changes
block in → the document gets edited.** You own the last step; the plugin owns
everything before it.

This is the opposite data flow to `/render:questionnaire`. A
questionnaire's spec is written *for* the renderer and the page collects new
data. Here the file already exists, belongs to the project, and stays the truth;
the page is a view of it and hands back a **diff**.

## What this plugin does not decide

**The plugin never writes to the source file.** It is a renderer: it supplies
the fingerprints, the parsed diff and the drift check. Applying them is yours,
because that is where the change gets a review step, and because a renderer with
write access to a project's documents is a different tool with different failure
modes.

It also does not decide what belongs on a checklist, when one is due, or where a
note ends up. That is the consuming project's business.

## 1. Scaffold the kind page — once per project

If `.render/` does not exist yet, run `/render:init` first.

A checklist family is one page folder plus wherever the documents already live.
The page is three lines and never changes again:

```python
# .render/pages/checklist/__init__.py
"""Checklists — one page per markdown file in docs/checklists/."""

TITLE = "Checklist"
KIND = "checklist"
SOURCES = "docs/checklists/*.md"   # glob relative to ROOT — one output per match
```

`SOURCES` **is the lifecycle.** Every document that matches gets a page; move one
out of the glob and `--prune` deletes the page that belonged to it.

Point the glob at where the documents already are. Do not move them into
`.render/` — they are the project's content, they existed before the
page, and somebody who never renders anything still has to be able to read them.

## 2. Leave the document alone

The whole point is that it stays a document, and ordinary markdown already
works:

- `##` is a group, `- [ ]` and `- [x]` are items, `~~…~~` is obsolete
- indented lines under an item are its detail; `path:` and `due:` are annotations
- everything else is prose and renders where it stands

Optional frontmatter adds `title`, `deadline`, `deadline-label`,
`handback-marker` and `exclude`. Add them if they help. **Do not restructure a
file to suit the renderer** — if it renders badly, that is worth knowing about
the file, or about the renderer.

A document that breaks a structural rule is refused with every finding printed
at once — fix what the findings name. Open
`${CLAUDE_PLUGIN_ROOT}/docs/spec-checklist.md` only when a finding or an
advanced feature needs the full grammar.

Two things are worth telling the person whose file it is:

- **`exclude`** keeps a block off the page while it stays in the file — for
  content that is a record rather than a task. It is opt-in and per block.
- **Two items that read exactly the same in one group are refused**, because
  their state could then only be told apart by position. That is a defect a
  reader hits too.

## 3. Render

```bash
python3 .render/render.py --check
python3 .render/render.py --page checklist:<file-stem>   # just this one
python3 .render/render.py --prune                        # drop orphaned pages
```

A document that fails validation is **not rendered** — every finding is printed
and the run exits non-zero, while every other document still renders. Fix the
document; never work around the validator.

Then tell the person where the file is. It is one self-contained file: it works
offline, and what they tick stays in their browser until they copy it out.

## 4. Apply what comes back

The person pastes the **changes** block. Save the paste to a file (or pipe it
in) and let the shipped parser do the mechanics — never parse it by eye:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/handback.py" paste.txt --source docs/checklists/<file>.md
```

The script checks `based-on:` against the file's current fingerprint, joins
every item id, and prints the split that matters:

- **`edits (n)` — apply verbatim with Edit.** Exact line edits,
  `L<line>: old → new`; they are the whole mechanical half.
- **`judgment (n)` — yours.** Notes, cleared notes, anything editorial the
  script refuses to turn into an edit — see below.
- **`control-mismatch:` / `unmatched:` / `warning:`** — the block and the
  file disagree somewhere short of drift. Read them before applying anything.

**Exit 3 is drift** — the file changed while the page was open. **Stop and
ask.** Say what changed in the file since, and offer to re-render so the
person can redo the affected part. Never reconcile it silently: a diff forced
onto a document that moved underneath it is how somebody's edit disappears.

Exit 2 means no usable block — usually a truncated copy. Ask for the paste
again. (The grammar itself lives in `${CLAUDE_PLUGIN_ROOT}/docs/handback.md`;
you should not need it unless the report surprises you.)

### Notes are the interesting part

A tick says a task was done. A note says it was done *differently*, or could not
be done, or should not have been on the list. Where it goes is the project's
decision, and it is usually not the checklist:

- it may belong in the ticket, the log, or the conversation
- **a note on an item still open is the signal to consider striking that item**
  — the person is saying the instruction did not survive contact with reality.
  Propose it; do not do it silently. Marking an item obsolete changes what the
  document says, which is why the browser cannot do it either.
- if the note describes a step that is now wrong, the fix is to reword the
  instruction — and say so, because rewording it costs that item its tick

Never drop a note because you could not place it. Quote it back.

## 5. Iterating

Editing the document re-renders only its page, and what people have ticked
survives — state is keyed by a fingerprint over the instruction text alone.
Adding an annotation, adding detail, reordering items, renaming a heading and
striking something out all cost nothing. **Rewording an instruction costs that
one item its tick**, on purpose: the page can no longer honestly claim the tick
was about this text.

Say so when you reword something for somebody.

## Never

- **Never let the plugin write to the source document**, and never add a step
  that does it automatically. The review is the point.
- **Never apply a diff whose `based-on:` does not match.** Re-render and ask.
- **Never rewrite a maintained document to render more tidily.** Prose in an
  awkward place is rendered where it stands; that is a feature of the kind.
- **Never copy the checklist kind into a project.** It lives in the engine and
  is imported; a copy forks on day one and never receives a behaviour fix. A
  project that needs a page type the plugin does not ship writes its own kind in
  `.render/kinds/<name>.py` — a different thing from forking this one.
- **Never write project-side CSS or JS for these pages.** The components, the
  state kit and the copy mechanics are in the design system; anything missing
  gets added there and documented in `design-manual.md` first (6b and 11).
