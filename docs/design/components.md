<!-- Components (§6) — part of the render design manual. -->

Part of the **design manual** and exactly as binding: the core rules,
tokens and catalog live in `design-manual.md`; this file is the
reference for the helpers it lists. Section numbers are stable and
cited from code.

## 6. Components

All classes are defined in `BASE_CSS`; the helpers in `design_system.py` produce the
markup. **No renderer writes its own styling in `style="…"`, except for widths,
flex shares, and series-color assignment.**

### 6.0 Section head `.section-head` — `section_head()`

The only way to start a section.

```python
section_head("Project file 2025",
             "Checklist, open items, master data, and calculations",
             num="02", kicker="Figures",
             right=badge("29 open items", "warn"))
```

Structure: overline `NN · KICKER` (number in a 23 px accent mark) · H2 (E2) ·
subline (max. 64 characters wide) · counter or status on the right · hairline below.
The number is **mandatory** — it is level 2's recurring cue.

`count=8` puts a muted count chip directly after the title ("Backlog 8") —
magnitude before content (Linear). It never replaces the `right` slot, which
stays for status; a count is not a status.

### 6.0b Group title `.subhead` — `subhead()`

Level 3 inside a card: 3 px accent bar, title (E3), optional gray addition
("8 folders without a receipt"). Separates groups within a card **without** opening a
second box level. Markdown passages produce the same look automatically via `.prose > h3`.

`num="02.1"` prefixes a decimal sub-number in the meta voice — citable card
headings inside a numbered section (design-manual.md 5.4). Two levels, never
three.

### 6.0c Focus card `.focus` — `focus_card()`

The one card that gets the eye first. **At most one per page.**

```python
focus_card("5", "Days until the filing deadline",
           sub="Deadline 31.07.2026 — the date is binding",
           kind="crit", chip=badge("urgent", "crit", icon="⚠"),
           aside=[("Next step · Priority 0", "…"),
                  ("Checklist progress", meter_row("2 of 31 done", 6, kind="crit"))])
```

- On the left the focus number (E-focus, 64 px) with label (E4) and reference line; on the
  right one or two "What now?" blocks with overline labels.
- `kind` colors **only the 4 px bar at the top edge** (`--accent-solid` neutral,
  otherwise `--good-mark` / `--warning-mark` / `--critical-mark`). The text stays `--ink`;
  the statement additionally carries a badge with a word — never color alone (2.3).
- The bar is the only permitted exception to "hierarchy not through borders"
  (1.4): it is a status indicator, not decoration.

### 6.1 KPI tile `.tile` — `tile()`, `tile_group()`

Contract: `label` (a declarative phrase, no colon) · `value` (large, semibold) · optional
`icon` (tile on the left), `chip` (badge/delta on the right), `spark` (sparkline), `sub` (footnote).

```python
tile("Days until the filing deadline", "5", sub="Deadline 31.07.2026 — binding",
     chip=badge("due soon", "warn", icon="⚠"))
```

Rules: one number per tile; the footnote explains the reference or source; a delta
always names the comparison period. Compound labels get a non-breaking
hyphen (U+2011, e.g. "To‑dos") so the tile does not wrap mid-word.

**Four variants** (Tremor/shadcn direction — interpretation, not just
measurement):

- **Trend line** — `trend="Trending up this month"`: one plain-language
  sentence of interpretation in the tile footer, written by the generator at
  render time. It says what the number *means*; the `sub` still says where it
  came from. Never invented — only written where the data supports it.
- **Capacity** — `capacity=(18.5, "1.85 of 10 GB")`: a used-of-available
  reading with the caption over a thin 6.7 meter.
- **Dual delta** — two `delta()` calls joined in `chip` ("↑ 1.1 T€ ↑ 9,1 %"):
  the absolute and the relative change together, when one alone misleads.
- **Grouped triplet** — `tile_group([(label, value, sub), …])`: up to three
  stats that only mean something together, in ONE tile with hairlines between
  them — no second box level, and no pretending three dependent numbers are
  three independent tiles. Laid out on a **two-column** grid: the third stat
  wraps to a second row (2×2), because a tile's own width never fits three
  columns of label-plus-value.

### 6.2 Delta and badge — `delta()`, `badge()`

Pills with a soft status surface. `↑`/`↓` carries the direction so the statement stays
readable without color. A delta is **green when the direction is good** — for costs
"↓ 12 %" is green, for income "↑ 12 %".

### 6.3 Chip and tag

`.chip` for header metadata (count, duration, date), `.tag` for counters and categories
next to headings. Both neutrally framed, no status color.

### 6.3b Navigation path `.crumbs` — `crumbs()`

The path to a place in a **foreign** application (e.g. specialist software), not
this page's navigation. Level › level › target, horizontal, wrappable, with the
label `PATH` (STRINGS: `crumbs_label`) as an overline in front.

```python
crumbs("Settings › Accounts › Approvals", note="unconfirmed")
```

- The **last** level is the target and is set in `--ink-2`, semibold; the levels before it
  in `--muted`. The `›` separator in `--faint` and `aria-hidden` — it is decoration, not information.
- Levels are taken **verbatim** from the foreign interface; nothing is shortened
  or translated. Three to four levels are enough.
- `note` is a `.tag` at the end for the verification state ("unconfirmed", "unknown").
  That keeps the uncertainty visible without letting colored emoji into the interface.
- Belongs below the row it leads to (checklist item), never in its own card.

### 6.4 Buttons

`.btn` (secondary, white with border) · `.btn--primary` (accent surface, white text) ·
`.btn--ghost` (borderless). At most **one** primary button per viewport.
In generated reports buttons are rare — only where something actually happens
(copy, reset). No button that merely looks nice.

`.btn-link` is the exception for controls **in body text or a table cell**
(e.g. the event title that opens its detail dialog): looks like a link, but is a
`<button>` — correct for the keyboard and for screen readers, because there is no destination.

### 6.5 Tabs / filter row — `filter_row()`, `FILTER_JS`

`.tabs` with a 2 px underline beneath the active entry (Untitled reference), filters in
**one** row above the content (`.filters`), never beside or below the chart.

`filter_row()` renders the filter pills; `FILTER_JS` (standard chrome on every
section page, next to the jump-bar and modal scripts) makes them work:

```python
filter_row([("track-2", "Track 2"), ("track-5", "Track 5")], "#postings")
```

The contract: `scope` is a CSS selector; inside that container, every element
carrying `data-tags` (rows opt in via the `tags` parameter of `list_row()` /
`accordion()` — space-separated lowercase tokens) is shown or hidden per pill.
An "all" pill is prepended automatically and starts active; selection is
single-select and view-only — **no state is stored, and a filter is never the
only way to reach content**: without scripting every pill is inert and the
full list stays visible. Elements without `data-tags` (subheads, banners) are
never hidden. The "nothing matches" note is in the document (a hidden
`.empty`, string `filter_empty`), not assembled at view time. Printing shows
the full list regardless of the active pill. Do not combine with
`show_all()` on the same list — filtering a half-truncated list reads as
missing data; pick one per list.

### 6.6 List row `.list-row` — `list_row()`, `show_all()`, `SHOWALL_JS`

Main text plus gray secondary text on the left, the value with `tabular-nums` on the right
(Stripe reference "Top customers by spend"). Separated by hairlines, none after the last row.
From eight rows on: truncate and link "show all" — `show_all()` is that mechanism:

```python
list_row("Working tree", badge("clean", "good", icon="✓"), sub="measured via git status")
show_all([list_row(p["name"], p["tier"]) for p in portals], limit=8)
```

`value` passes finished markup (a badge or delta) through unchanged; everything else —
including `main` and `sub` — is escaped. No renderer writes `.list-row` markup by hand.

`show_all()` takes finished rows (`list_row()`, `accordion()` — not `<tr>`:
a long table is authored top-N with a total row instead). At the limit or
below it is a plain join with no wrapper; beyond it the rows land in a
`data-show-all` container whose trailing trigger ("show all {n}", string
`show_all`) `SHOWALL_JS` reveals. Without scripting the trigger stays hidden
and every row is visible; printing always shows the full list. The reveal is
one-way — a reader who asked for everything keeps everything.

### 6.7 Meter `.meter` — `meter_row()`

Thin bar (8 px, fully rounded), track `--hairline`, fill `--series-1` or
`--warning-mark` / `--critical-mark` at thresholds. Row: name · bar · percentage
right-aligned (Untitled reference "Active users").

### 6.8 Share bar `.share-bar` — `share_bar()`

Horizontal bar across the full width, segments in slot order, **2 px gap in the
surface color** between the segments, ends rounded 4 px (Stripe reference "Payments").
Below it the legend with a value per segment. No border around segments.

### 6.9 Table

Header: 11.5 px caps, `--muted`, hairline below. Cells: 13.5 px, top-aligned,
tabular numerals throughout. **The alignment triad**: text left, numbers
right (`.num`), badges center (`.ctr`) — a column picks one and keeps it.
Total row `tr.total` with a 2 px line above and semibold text. Wide tables
sit in `.table-wrap` (`overflow-x: auto`) — **the page itself never scrolls
horizontally**.

Two variants for table-first sections (design-manual.md 5.3):
`.table--dense` tightens rows to ~36 px — a **generation-time** page decision
(`density`), never a toggle; `.table--sticky` pins a tinted header band under
the jump bar — only for a full-width table that fits *without* `.table-wrap`,
because position: sticky cannot escape a scroll box.

**A cell holds an atom** (design-manual.md 5.1): a name, a number, a short
phrase. Rationale and multi-clause prose go into an `.acc` body (6.14) or the
detail dialog (6.17) — `--check` flags cells over 80 visible characters. A
column whose values are all identical is deleted; the shared fact moves into
the section head's counter. A long table is authored top-N with a total row —
`show_all()` (6.6) is for row lists, not `<tr>`.

### 6.10 Collapsible `details`

Summary with ▸/▾, meta on the right (file, as-of date). The plain variant for short
asides. For files and lists, 6.14 applies instead.

### 6.11 Banner `.banner`

Four tiers: neutral, `--ok`, `--warn`, `--crit`. One statement, one sentence, icon first.
Not for body text, not stacked — at most two banners per page.

### 6.12 Empty state `.empty`

Italic, `--muted`, says what is missing **and** what to do: "no entries — new
files go into the project's intake folder first."

Empty means invisible (design-manual.md 5.1): zero items are this one line or
nothing — never a card around nothing (`--check` flags empty card bodies).
When the absence itself is the alert, it is a `.banner` (6.11) instead.

### 6.13 Icons — `icon()`

**Monochrome inline SVG** from the set in `design_system.py` (`check`, `doc`, `folder`,
`chat`, `user`, `lock`, `clock`, `flag`): `fill="none"`, `stroke="currentColor"`,
`stroke-width="1.75"`, sizes 13/16/20, `aria-hidden="true"`. They take on the color of
their surroundings and therefore work in both modes.

**No colored emoji in the interface.** 🗂 💬 👤 🔒 are colored differently on every
operating system, clash with the single accent, and cannot be tinted. Monochrome
Unicode characters remain allowed as status characters (✓ ⚠ ✕ ≈ ?) — in `.badge`,
`.mark`, or as the expand arrow. An icon never replaces a word; it accompanies it.
If a symbol is missing, it is added to the set in `_ICONS`, not invented in the renderer.

### 6.14 Entry row `.acc` — `accordion()`

A file, an FAQ entry, a receipt category — anything that is one row in a list
and shows content when expanded.

```python
accordion("Checklist — 2025 tax return",
          prose_html, sub="Prioritized to-do list through filing.",
          mark="01", meta="checklist.md · as of 26.07.2026",
          right=badge("29 open", "warn"))
```

Structure: 30 px mark (running number or `icon()`) · title (E4) with subtitle in
`--muted` · optional status/tag · meta on the right (truncates with an ellipsis, drops out below 620 px)
· arrow ▾/▴. In the open state, mark and title take the accent color — so it is
visible without scrolling which row is currently expanded.

Rules: the title is the file's `# ` line (short), the subtitle its
`description` frontmatter (explanatory) — never the other way around. Closed by default.

`tags="track-2 new"` (space-separated lowercase tokens) makes a row
addressable by a `filter_row()` above the list (6.5); rows without it are
never hidden by a filter. `.acc` rows are also the row type of choice for
entities whose table would need prose cells — title line for the atoms,
body for the rationale.

### 6.15 Status mark `.mark` — `status_marks()`

Source files mark status with emoji (✅ 🟡 ❓ 🔴 🟢 ⚠️ ☐ ☑). At render time these become
19 px pills on a soft status surface with a monochrome character: ✓ confirmed · ≈ assumption ·
? unknown · ● level · ! attention. The meaning is stated in the adjacent text or in the
`title` attribute; the mark carries only color and character (2.3).

The translation happens centrally in `inline()` — **no renderer replaces emoji itself**,
and no source file has to be changed for it.

### 6.16 Active navigation

`nav.toc a.is-active` (accent surface, accent text) marks the section currently in
view. Set by an `IntersectionObserver` in the page script — inline, without an
external resource, with a fallback to "no marking" when the browser does not support it.

**On a display page, JavaScript is limited to two purposes:** this navigation marking and
the detail dialog (6.17). Everything else is produced at render time. A page that needs
more than those two is not a display page but an **interactive page** — a separate,
enumerated flavour with its own rules in section 11. Adding a purpose to *this* list still
requires recording it here and showing the page stays fully readable without the script.

### 6.17 Detail dialog `dialog.modal` — `modal_host()`, `modal_detail()`, `MODAL_JS`

For content that belongs to a mark or row but would overwhelm the surface —
typically the explanation of a timeline event.

```python
modal_host()                       # once per page: the empty dialog
modal_detail("ev08", "Incoming payment 4.500,00 €", kicker="Income",
             when="01.07.2025", badges=badge("documented", "good", icon="✓"),
             body=prose_html, source="Source: <code>bank statement</code>")
```

- A native `<dialog>`, **one per page**. The contents sit as hidden blocks
  (`[data-ev-detail]`) in the document; on open, the matching one is copied in. Triggered
  via `data-ev="…"` on **any** button — chart mark and table row alike.
- Structure: overline (origin/lane) · title (E3) · time reference · badge row (status, amount) ·
  body text · source line. Footer with previous/next (steps chronologically, also via ←/→)
  and close — labels from STRINGS (`modal_prev`, `modal_next`, `modal_close`).
- Closes on Escape, click on the backdrop, and the button; focus then jumps back
  to the triggering mark.
- **A detail dialog may never be the only source of a piece of information.** Everything
  in it also appears in the associated table — otherwise it is lost without JavaScript, in
  print, and for screen readers (7.5).
- No focus number, no second dialog on top of the dialog, no forms inside.

### 6.18 Card shell `.card` — `card()`

The card anatomy from section 5 as a helper: optional head (title E3, action or counter on
the right), context line, body, footer with the follow-up link on the left and the as-of
date on the right.

```python
card(rows, title="Measured to-dos", sub="computed per directory",
     foot_left="Full audit: /audit", foot_right="As of 26.07.2026")
```

The footer stays mandatory as soon as the card shows computed values (5); the helper only
makes the markup canonical. It adds no second box level — no card inside a card.
`icon=icon("chart")` puts a small soft-accent glyph before the title — for
the rare card whose identity needs a mark; most cards never carry one.

### 6.27 Ranked bar list `.bar-list` — `bar_list()`

The analytics workhorse: rows with a **proportional accent-tinted bar behind**
label and right-aligned value — magnitude is visible before a single number
is read (Plausible, Tremor).

```python
bar_list([("Berlin", 4210), ("Hamburg", 2380, "2 portals"), ("Köln", 990)],
         unit="€", fmt=lambda v: fmt_num(v, 0))
```

Rules: 32 px rows; bars never drop below 2 % so every row stays visibly a
bar; the helper does not sort — order is the author's statement, and ranked
largest-first is the convention. The fill is `--accent-soft` (a tint, behind
text — it never has to pass a text-contrast bar). Two bar-list cards pair
two-up in a `.grid--2`. Beyond ~8 rows: top-N plus an "Other" row, detail in
the dialog (6.17) — never a scrollbar.

### 6.28 Tracker strip `.tracker` — `tracker()`

Status over time as one row of contiguous ~10 px blocks, rounded only at the
ends — anomalies pop as color breaks (Tremor).

```python
tracker([("good", "07-01 · passed")] * 20 + [("crit", "07-21 · failed")]
        + [("good", "07-22 · passed")] * 9,
        left="July 1", right="July 31")
```

Rules: 60–90 slices read best; **status tokens only** (2.3 discipline holds —
red in a tracker means action was required at that point), neutral slices
stay hairline gray. Each slice takes a `title` naming its time point and
state — that, plus an adjacent count ("29 of 30 passed"), is the accessible
reading. `left`/`right` label the span underneath in the meta voice.

### 6.29 Metric-tab hero `.metric-tabs` — `metric_hero()`

The sanctioned opening 5.2b: one hero chart card whose **header row is the
KPI strip** — each metric a bordered cell, one marked active with the violet
underline, and the chart below plots exactly that one (Plausible).

```python
metric_hero([("Applications", "34"), ("Responses", "9", "26 %"),
             ("Interviews", "3")],
            chart=sparkline(series, width=760, height=120, label="…"),
            active=0, foot_right="As of 2026-08-18")
```

Static by design: the underline says what is plotted, nothing switches, and
the inactive metrics are honest KPIs in their own right. Never together with
a focus card — 5.2 sanctions exactly one opening.
