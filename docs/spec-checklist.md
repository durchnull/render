# The checklist source

**Schema version 1.** One markdown file becomes one interactive view of itself.

There is no spec format here. The source is **a document the project already
maintains** — the page is a view of it, and the file stays the truth. So the
grammar is ordinary markdown, and almost everything in a real file is already
valid.

```markdown
---
title: Release checklist — 0.4.0
description: Everything that has to be true before 0.4.0 goes out.
deadline: 2026-08-31
deadline-label: Release window closes
handback-marker: RELEASE CHECKLIST CHANGES
exclude: ["🗄️", "**Superseded"]
---

# Release checklist — 0.4.0

A paragraph that belongs here and stays here.

## Before the branch

- [x] Agree what goes in and what waits
      Indented lines under an item are its detail.
- [ ] Check the dependency licences
      path: Settings › Compliance › Licences
      due: 2026-08-20

### A subhead inside the group

- [ ] Write the migration note
- ~~[ ] Announce the deprecation window~~
```

## Frontmatter

Every key is optional. Unknown keys are ignored, not refused.

| Key | Does |
|---|---|
| `title` | the page title. Falls back to the file's `# ` line, then its name |
| `description` | one sentence, shown on this checklist's card on the index page |
| `deadline` | ISO date. Drives the countdown on the focus card |
| `deadline-label` | what that date *is*, in your words ("Release window closes") |
| `handback-marker` | the marker of the block the page produces. Default `CHECKLIST CHANGES` |
| `exclude` | a list of prefixes that keep a block off the page — see below |

`deadline` and the exclusion markers each resolve **document → page →
`config.py` → nothing**. The document is in front because for this page type the
document is the truth; the other two layers are for a project-wide default a
file can override.

## The body

| Line | Becomes |
|---|---|
| `## Title` | a group — one numbered section on the page |
| `### Title` | a subhead **inside** the group |
| `- [ ]` / `- [x]` | an item, open or done |
| `~~[ ] …~~` or `[x] ~~…~~` | an **obsolete** item |
| an indented line under an item, key in the vocabulary | an annotation |
| any other indented line under an item | that item's detail |
| anything else | prose, rendered where it stands |

Everything renders **in the order it was written**. Paragraphs between item
blocks, a subhead in the middle of a group, a bold-only line titling what
follows — all of it stays where you put it.

**Groups are optional.** A short list can be a `#` heading and some items,
and it renders as one unnamed section — the page does not invent a group
title the file never wrote. Items before the first `##` behave the same way
in a document that does use groups: they render first, in their own section,
above the named ones. The one thing the position changes is an opening
paragraph: prose written before any item is the page's lead and sits above
the derived overview, because it introduces the whole list rather than the
first item. From the first item onwards, document order is kept exactly.

A `-` line with **no checkbox** is an ordinary markdown list: it renders as one,
and it is counted as nothing. That is how you write a note that happens to be a
list without it becoming work.

### Item state

The **document** knows a closed set of three. `obsolete` cannot be set from
the browser: striking an item out is an editorial judgement about the task
list — it changes what the document *says* — so it belongs to whoever edits
the file, where it gets a review step.

| State | Written as | Counts as done | Counts in the total | On the page |
|---|---|---|---|---|
| open | `- [ ]` | no | yes | normally |
| done | `- [x]` | yes | yes | ticked |
| obsolete | `~~…~~`, whatever the checkbox says | no | **no** | struck, still there |

A strikethrough counts only when it wraps the whole line. `- [ ] Tag ~~the~~
release` is an open item with a struck word in it, not an obsolete item.

The **person** working the page can additionally declare two states the
checkbox syntax cannot hold (design manual 6.26): `na` ("does not apply" —
an affirmative answer, counted as done in every ratio) and `deferred`
("later" — still open work). Both travel in the hand-back as `~` state
changes and full-state spellings (`n/a <text>`, `☐ <text> (later)`,
`docs/handback.md` v3); neither has a mechanical edit — the parser routes
them under `judgment:`, and where they land in the file (struck, annotated,
left as is) is the applying agent's call.

### Annotations

A small declared vocabulary on indented lines under an item.

| Key | Renders as |
|---|---|
| `path:` | a navigation path inside another application (`Settings › Accounts › Approvals`) |
| `due:` | a date badge, and the order in which "next open item" is chosen |

**An unknown key is not an error.** `owner: someone` renders as detail, because
this is a document a person owns and an indented line they wrote is far more
likely to be their note than a mistake. Detail lines are markdown, so
consecutive lines join into one paragraph exactly as they would anywhere else; a
blank line ends the item.

Nesting is flattened: an indented `- [ ]` is still an item. Losing the
indentation costs a visual level, and swallowing it into the parent's detail
would cost a tick nobody could record.

### Keeping something off the page

`exclude` is a list of **prefixes**, matched against a block's raw source line
after list and checkbox syntax and leading whitespace are stripped. One rule
covers an emoji marker and a bold lead alike:

```yaml
exclude: ["🗄️", "**Superseded"]
```

It works **per block** — one item, or one paragraph among its siblings, anywhere
in the document. It is not a way to drop a section, and a `##` heading is a
container rather than a block, so a marker on one does not remove its group.

The order is **parse → exclude → fingerprint → render, count**. An excluded
block consumes no id, appears in no total, and can never surface in a hand-back;
`--check` asserts it. The default is empty — content only ever disappears
because someone asked for it.

## What is refused

The opposite of the questionnaire's strict-unknown-keys, and for the opposite
reason: that spec is written *for* the renderer, so a typo is an error. This is
a document somebody maintains, and it cannot be rejected for containing a
paragraph the parser did not anticipate. Only genuine structural breakage stops
a page from rendering:

| Refused | Why |
|---|---|
| no items at all | prose alone makes a document, not a checklist |
| two identical instructions in one group | see below |
| a `deadline:` or `due:` that is not an ISO date | guessing at another format silently changes what the page says |
| an `exclude:` that is not a usable list | silently dropping nothing is worse than saying so |

Every finding is reported at once, and a document that fails writes **nothing** —
while every other document in the glob still renders.

### Two items that read the same

Item ids are fingerprints over the instruction text, because the file is edited
while people have the page open. Two items with the same text in the same group
cannot be told apart by their content — and keying them by position instead
would mean that reordering them swaps which one is ticked.

So the kind refuses. A reader cannot tell them apart either: that is the actual
defect, and it is in the document. Give each one wording that says how it
differs.

Identical text in **different** groups is fine — those are separated by their
heading automatically, and only the pair that collided is qualified that way, so
renaming a heading never invalidates anything that was not colliding.

## What survives an edit

State lives in the browser, keyed by a fingerprint over the **instruction
alone** — not the checkbox, not annotations, not indented detail, not the
strikethrough. So:

| Edit | Effect on what people have ticked |
|---|---|
| adding or changing `path:`, `due:` or detail | nothing |
| striking an item out | nothing |
| reordering items, renaming a heading, editing other items | nothing |
| rewording the instruction | **that item alone** loses its tick |

The last row is the point rather than a cost: the page can no longer honestly
claim the tick was about this text. Everything else keeps working, and stale
entries are dropped from storage on the next load.

## The hand-back

The page produces the **changes** shape of the hand-back block —
[docs/handback.md](handback.md), grammar version 2. It carries only what moved,
a full-state listing as control material, and `based-on:`, the fingerprint of
the source it was rendered from. If that no longer matches the file, the file
moved while somebody had the page open: re-render and ask rather than applying a
diff to a document that changed underneath it.

**The plugin never writes to the source file.** It supplies the fingerprints,
the parsed diff and the drift check; applying them is the project's job, where
the change gets a review step. See `/render:checklist`.
