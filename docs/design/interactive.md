<!-- Interactive pages (§11) — part of the render design manual. -->

Part of the **design manual** and exactly as binding: the core rules,
tokens and catalog live in `design-manual.md`; this file is the
reference for the helpers it lists. Section numbers are stable and
cited from code.

## 11. Interactive pages

A **display page** reports; it is finished when it is written. An **interactive page** asks
— a questionnaire, a checklist — and is only finished when a person has worked through it.
That is a different contract, so it gets its own rules instead of bending 6.16's.

An interactive page is still a single self-contained file with no external resources, still
built from the same tokens and components, and still checked by `check_page()`.

### 11.1 The three permitted script purposes

Beyond 6.16's two, an interactive page's JavaScript may do exactly these three things:

1. **Remember** what was entered — `localStorage`, namespaced per document
   (`STATE_JS`), keyed by content where the document can change under it (11.7).
   Never a cookie, never a network call.
2. **Move between screens** — show and hide content that is *already in the document*.
   Filtering a list is this purpose, not a fourth one: the rows stay in the markup and a
   CSS rule decides which are shown.
3. **Hand the result back** — assemble the answers as text and copy it (`HANDBACK_JS`).

Anything else is a fourth purpose and is recorded here first, exactly as in 6.16.

### 11.2 Content is in the document, not assembled in the browser

Every question, option, hint and explanatory passage is **rendered server-side into the
HTML** and merely hidden (`hidden`, one screen visible at a time). Markdown is converted at
render time by `content_core`; the client never parses markdown and never writes markup
into the page.

Three things follow, and all three are the point:

- the page prints, and reads top to bottom without any script;
- there is no injection surface, because nothing is ever built from a string at view time;
- `--check` can count the questions in the finished file instead of trusting a payload.

A `<script type="application/json">` block may carry the **machine half** — ids, option
keys, types, conditions — which is what the hand-back and the progress count are computed
from. It never carries display text that is not also in the DOM.

### 11.3 State is private, and the page says so

Answers live in `localStorage` on that one device until the person copies them out. No
network, no beacon, no autosave anywhere else. The footer states this in plain language by
default, translatable via `STRINGS` — self-containment (1.5) is a privacy property here,
not just a build rule, and the person answering deserves to be told.

Storage may be unavailable (private mode, disabled cookies). The page then keeps working
for the session with in-memory state and says nothing alarming — a questionnaire that
refuses to start because it cannot save is worse than one that forgets.

### 11.4 Nothing is mandatory

"I don't know" and "skip" are **first-class answers**, tracked separately from untouched,
and they never block the hand-back. A question that cannot be skipped is a question that
ends the session. The free-text note (6.21) is always reachable, on every question.

### 11.5 Keyboard and focus

Fully operable without a mouse, and the keys are stated on the page:

| Key | Does |
|---|---|
| `1`–`9` | select the first nine options |
| `←` / `→` | previous / next screen |
| `Enter` | next screen (`⌘`/`Ctrl+Enter` from inside a text field) |
| `Tab` | through options, note, action bar — in that order |

On a screen change, focus moves to the new screen's heading (`tabindex="-1"`), so a screen
reader announces where it landed. The active step carries `aria-current="step"`. Focus
rings come from the token set and are never suppressed.

An auto-advance after a single-select is allowed at **≤ 200 ms**, and is suppressed when
`prefers-reduced-motion: reduce` is set, when the note field is open, and when the note
already holds text. It never applies to multi-select, amount or free-text questions —
those have no moment at which the answer is obviously complete.

### 11.6 What a person may never lose

Typed text is committed on every navigation, on every option selection, and on
`beforeunload`. Progress counts answered against **currently visible** questions and is
recomputed whenever a condition changes what is visible (6.22 covers the honest total).

**Every derived number on the page is recomputed together**, not just the progress bar.
A focus card, a KPI tile and a section counter that still show the values the page was
rendered with put two different answers to the same question on one screen — and the
reader has no way to know which of them is about what they just did. Filtering is the
exception that proves it: hiding rows changes what is *shown*, never what is counted, so
the totals must not move when a filter does.

**A closed branch never discards answers.** A question hidden by a condition
is removed from the flow — never grayed, never disabled (USWDS) — and its
recorded answers are *retained*: they leave the hand-back (the question is
"not asked") and return intact if the branch reopens. Nothing is silently
deleted, so no destructive-change confirmation is ever needed — the design
removes the destruction instead of confirming it.

### 11.7 When the document can change under the state

A questionnaire's spec is authored *for* the page, so its ids are stable by construction.
A page that mirrors a document a person maintains has no such luxury: the source is edited
while someone still has the page open, and every id the page invented is invalid the moment
a line moves.

**The key is the content, not the position.** Each entry is keyed by a fingerprint over the
instruction text alone — inline markup stripped, whitespace collapsed. On load, entries
whose fingerprint is no longer in the document are dropped
(`Store.make(ns, { keys, bucket })`). Three consequences, and all three are the point:

- reordering, regrouping and rewriting *other* items changes nothing;
- an edited item loses its state precisely because its content changed, which is the
  honest outcome — the page can no longer claim the tick was about this text;
- nothing accumulates: state for text that no longer exists is collected, not kept.

What goes **into** the fingerprint is only the instruction. Not the state marker, not
annotation lines, not indented detail. Adding a navigation path to an item is not a changed
task, and an edit that silently discards a tick teaches people not to edit.

The guard against a stale page overwriting a newer file is **not** the state key — it is a
source fingerprint the page hands back (`based-on:`), where the agent applying the result
can see it and ask.
