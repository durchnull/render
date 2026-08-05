# The hand-back block

**Grammar version 2.** How a generated page talks back to the agent that made it.

A rendered page is offline and self-contained: it cannot post anywhere, and that
is the point. So when a page has collected something — answers, a checklist run,
a review — it produces one block of plain text that a person copies and pastes
back into the chat. This file is the contract both sides parse against.

The block is **not questionnaire-specific**. Any page kind, and any standalone
`page_api` script, may produce one; the design system ships the copy mechanics
(`HANDBACK_JS`, `toast()`, the `.handback` block style) so nobody has to reinvent
them.

There are two **shapes**, because there are two things a page can be. A page that
**collected** something hands back what it collected. A page that **mirrors a
document the project maintains** hands back the *difference* — the document is
the truth, and the block is a proposal to change it. Same skeleton, same
line-oriented conventions, same parser.

| | Shape 1 · answers | Shape 2 · changes |
|---|---|---|
| The page | asked questions | showed an existing document |
| Handed back | every visible item and its answer | only the items that moved, plus a control listing |
| Afterwards | the answers get routed somewhere | the source file gets edited |
| Default marker | `QUESTIONNAIRE ANSWERS` | `CHECKLIST CHANGES` |
| Carries `based-on:` | no | yes |

## The skeleton both shapes share

| Rule | Why |
|---|---|
| Line-oriented, never JSON | A person copies this by hand out of a browser. A JSON blob survives that badly and mangles unrecoverably; lines degrade gracefully. |
| `### <MARKER>` opens, `### END <MARKER>` closes | Lets a project key its own agent-side rule on a marker it chose, and lets a parser find the block inside a longer message. |
| A fixed, ordered header block of `key: value` lines | `source:` identifies which document this is, so the agent can look up the original — including anything the page never rendered. |
| `## <Group title>` splits the body into groups | The document's own structure, carried through so a reader recognizes it. |
| `[<item id>] <item text>` names an item, then its own lines follow | Order carries no meaning: `[<id>]` is the join key. Reordering the source document does not break an already-pasted block. |
| Every per-item line starts with a one-character prefix | `→` `~` `+` `-` — cheap to parse, unambiguous, and readable to the person who pasted it. |
| Newlines inside any value collapse to `" / "` | Keeps the grammar line-oriented. It is the only alteration made to typed text. |
| Everything may be incomplete | The block is produced from whatever exists. A document that demands completeness before it hands anything back is a document people abandon. |

## Shape 1 — answers

```text
### <MARKER>
source: <document id>
title: <document title>
status: <n> of <m> answered · <u> unclear · <s> skipped

## <Group title>
[<item id>] <item text>
→ (<key>) <label>
   note: <free text, newlines collapsed to " / ">

[<item id>] <item text>
→ ? don't know — please follow up

[<item id>] <item text>
→ (skipped)

[<item id>] <item text>
→ (not answered)

### END <MARKER>
```

| Rule | Why |
|---|---|
| One `[<id>]` line per item, then one or more `→` lines | The answer belongs to the item above it. |
| `→ (<key>) <label>` for a chosen option | The key is parsed, the label is read. Rewording a label never breaks parsing; that is why keys exist at all. |
| Multiple `→` lines mean multiple choices | Multi-select needs no separate syntax. |
| `→ <text>` with no parentheses for typed answers | Free text and amounts. **Handed back exactly as typed**, with the unit appended — no rounding, no locale interpretation. That is the reader's job. |
| `note:` lines are indented three spaces | Belongs to the item above; survives on skipped and don't-know items. |
| `→ ? don't know — please follow up` is a **distinct state** | Not a blank. It marks something to come back to, which is different from an unanswered question and different from a deliberate skip. |
| Items never shown are simply absent | A conditional question that never became relevant is not reported as unanswered. |

## Shape 2 — changes

```text
### CHECKLIST CHANGES
source: docs/checklist.md
title: Filing checklist
based-on: 8f2a1c
status: 12 of 31 done · 3 changed here

## Records
[a3f91c] Collect the receipts
~ open → done
+ note: found them in the drawer

[b1c204] Ask about the invoice
+ note: did it by phone instead

[c77e01] File the return
- note:

## Full state (control)
[a3f91c] ☑ Collect the receipts
[b1c204] ☐ Ask about the invoice
[d09f31] ~~Superseded by the new process~~

### END CHECKLIST CHANGES
```

| Line | Means |
|---|---|
| `~ <old> → <new>` | state change |
| `+ note: <text>` | note set or edited |
| `- note:` | note cleared |
| `based-on: <hash>` | the source fingerprint the page was rendered from |

| Rule | Why |
|---|---|
| An item appears in the changes section if it has **at least one** change line | A note with no state change is itself reportable, and is how a person says "did it, but not the way this says". An item nobody touched is absent, because absence is the accurate report. |
| `[<id>]` is a **content fingerprint**, not a position | The source document is edited while people have the page open. A positional id would be wrong the moment a line moved; a content-derived one still points at the same sentence. |
| `## Full state (control)` is a **reserved heading**, and what follows it is not a change | It is control material: it lets the agent verify it understood the diff before writing anything. Every item the page knows appears there, in document order, whether it moved or not. |
| Full-state lines carry a state glyph — `☑` done · `☐` open · `~~…~~` obsolete | Self-describing line by line, so the listing is still readable if it is quoted out of context. |
| `based-on:` is the **drift check** | If it does not match the current file, the file moved while the page was open. Re-render and ask — never force the diff onto a document that changed underneath it. |
| `obsolete` never appears as a `~` target | Striking an item is an editorial judgement about the task list, not a record of progress. It changes what the document *says*, so it belongs to the agent applying the diff, where it gets a review step. |

## The keywords are English, deliberately

The item text, option labels and notes are in the document's language. The
**keywords are not translatable**: `source`, `title`, `status`, `based-on`,
`note`, `answered`, `unclear`, `skipped`, `don't know — please follow up`,
`(skipped)`, `(not answered)`, `Full state (control)`, and the
`###`/`##`/`[…]`/`→`/`~`/`+`/`-` markers are protocol. A German checklist hands
back German instructions inside an English frame.

Translating them would break every parser on the other side for no reader's
benefit — the block is addressed to an agent, and the human reading over its
shoulder still sees their own language in every field that carries meaning.

Only `<MARKER>` is configurable, per document.

## Parsing it

Nobody parses this by eye. The reference parser ships as a script — one
parser, both shapes, the shape told apart by `based-on:`, which only the
changes shape carries:

```bash
python3 scripts/handback.py paste.txt              # report; stdin works too
python3 scripts/handback.py paste.txt --json       # the parsed block as data
python3 scripts/handback.py paste.txt --source docs/checklist.md
```

`--source` turns a changes block into an **edit plan** against the maintained
document: the `based-on:` drift check first (a mismatch is exit 3 and no
plan), then one exact line edit per state change. Notes and anything
editorial come back under `judgment:` — the script never writes to the
document, deliberately.

In the changes shape a `state` of `None` means **unchanged** — the item is
reported for its note alone. Do not read it as "open"; the control listing is
where the current state of everything lives.

Join the result against the source by item id to reach anything the page
deliberately never rendered — a questionnaire's `meta` object, for instance,
which exists precisely so a project can route answers without showing the
routing to the person answering.

## Versioning

This grammar is versioned with the plugin and changes only in a minor release
while the major version is `0`. A change that would break an existing parser
gets a new marker default, not a silent redefinition.

Version 2 **added** the changes shape and left the answers shape untouched: a
version 1 parser reads a version 1 block exactly as before.
