<!-- Input and app chrome (§6b) — part of the render design manual. -->

Part of the **design manual** and exactly as binding: the core rules,
tokens and catalog live in `design-manual.md`; this file is the
reference for the helpers it lists. Section numbers are stable and
cited from code.

## 6b. Input and app chrome

These eight components exist for **interactive pages** (section 11) and for nothing else.
Their CSS is **not** part of `BASE_CSS` — it lives in two opt-in constants, `FORM_CSS`
(6.19–6.21, 6.25, 6.26) and `APP_CSS` (6.22–6.24), which a page pulls in through
`EXTRA_CSS`. A dashboard that never asks a question never pays for them.

Everything else in this manual still applies without exception: tokens only, five text
levels, status never through color alone, no external resources.

**In print, the app chrome is gone.** `APP_CSS`'s three positioned components
(6.22–6.24) hide under `@media print`, as `nav.toc` and `.btn` already do in `BASE_CSS`:
a printed interactive page is its content, never its controls. What was entered stays
visible — only the things that would do nothing on paper disappear.

### 6.19 Option row `.opt` — `option_row()`

One answer to choose. A **real `<button>`** — never a styled `<div>`, never a bare
`<input>` with a label sitting next to it.

```python
option_row("a", "Yes, in full", hint="everything was recorded", index=0)
```

Structure: keycap on the left (the digit that selects it, 1–9 — beyond nine there is no
cap and no shortcut) · label (E4) · optional hint on a second line in `--muted`.
Selected state carries `aria-pressed="true"` **and** a visible accent border plus a check
glyph — pressed state never rides on the background tint alone (2.3). Focus ring from the
token set, always visible, never removed.

### 6.20 Field `.field` — `field()`, `text_field()`, `amount_field()`

A labeled control. The label is a real `<label for=…>`; the control is a real `<input>` or
`<textarea>`. Optional hint below the label, in `--muted`, before the control — it must be
readable *before* answering, not after.

```python
text_field("q07-note", "What is missing?", placeholder="one sentence is enough")
amount_field("q08", "Roughly how much?", unit="€")
```

`amount_field` renders the unit as a static suffix inside the control's frame. It is a
label, not a parser: **the value is handed on as typed** — no rounding, no locale
guessing, no silent normalization (3.2 says the exact value counts; here it also says
nobody may reinterpret it).

### 6.21 Note disclosure `.note-open` — part of `field()`

The always-reachable free-text escape hatch: a `.btn--ghost` reading "+ add detail" that
reveals a `text_field`. Present on **every** question, whatever its type, because the
person who wrote the question cannot anticipate every case. Pre-opening it is allowed;
removing it is not.

### 6.22 Progress bar `.progress` — `progress_bar()`

Sticky at the top of an interactive page, in the slot `nav.toc` holds on a display page —
the two never appear together. Thin bar (8 px, fully rounded, `--accent-solid` fill on a
`--hairline` track, the 6.7 meter's geometry), a label on the left and a count on the
right.

```python
progress_bar(3, 12, left="Section 2 · Records", approx=True)
```

`approx=True` renders "up to 12" instead of "12". **Mandatory** as soon as a single
question can be skipped by a condition: an exact total that later turns out wrong is worse
than an honest upper bound.

### 6.23 Action bar `.actionbar` — `action_bar()`

Fixed to the bottom edge, translucent with a blurred backdrop and a hairline above —
`nav.toc`'s treatment, mirrored. Primary action on the right, back/secondary on the left,
**at most one primary button** (6.4).

The page reserves its height as bottom padding on the content column. A fixed bar that
covers the last line of content is a defect, not a style choice.

### 6.24 Toast `.toast` — `toast()`

A brief confirmation for an action that leaves no visible trace — "copied", "saved".
`role="status"` with `aria-live="polite"`, so it is announced without stealing focus. One
per page, bottom center, above the action bar, auto-hides. Never for errors (those are a
`.banner`, 6.11), never the only feedback for something important.

### 6.25 Summary row `.sumrow` — `summary_row()`

One answered question in a review list, and the way back to it: the whole row is a
`<button>` that jumps to its question.

```python
summary_row("03", "Were the receipts recorded?", answer="Yes, in full",
            note="two are still missing", state="answered")
```

`state`: `answered · unclear · skipped · open`. The state shows as a `.badge` with a word
(2.3) — an unanswered row is visibly marked and still clickable, because a review list you
cannot act on is a report, not an editor.

### 6.26 Check row `.ck-row` — `check_row()`

One instruction from a maintained document, with its state, its context and a place to
say something about it. The counterpart to 6.19: an option row records a **choice**, a
check row records **progress against something that already exists**.

```python
check_row("a3f91c", "Collect the receipts", state="done",
          context=crumbs("Settings › Accounts › Approvals"),
          detail="<p>Indented lines under the item.</p>",
          note_label="What happened?")
```

Structure: a 24 px tick **`<button>`** on the left carrying the state, the instruction
(E4) beside it, then — indented under the instruction — context (a `crumbs()` path, a due
badge), detail prose, and the note disclosure (6.21). The tick is the only control that
changes state; the rest of the row stays selectable text, so a person can copy an
instruction without toggling it.

- **Three states, closed set:** `open` · `done` · `obsolete`. `done` carries
  `aria-pressed="true"`, an accent tick glyph and an accent border — never the background
  tint alone (2.3). `obsolete` strikes the instruction, dims it to `--muted`, and
  **disables the tick**: it is a statement the document makes, not progress the reader
  records.
- The first argument is the row's **fingerprint** — the stable id that keys its browser
  state and travels in the hand-back. It is content-derived, never positional, so the row
  survives everything in the document moving around it (11.7).
- The note is reachable on every row, whatever its state (6.21). A note on a row left
  open is a person saying "did it, but not the way this says" — the most valuable thing
  the row can collect, and the reason it is never gated on the tick.
- Rows are **not** wrapped in a card each. A group of rows sits in one `.card`, separated
  by hairlines, exactly as `.list-row` does (6.6) — a card per row would be a box level
  per instruction.
