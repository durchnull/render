<!-- Charts and visualizations (§7) — part of the render design manual. -->

Part of the **design manual** and exactly as binding: the core rules,
tokens and catalog live in `design-manual.md`; this file is the
reference for the helpers it lists. Section numbers are stable and
cited from code.

## 7. Charts and visualizations

### 7.1 Choose the form (before the color)

| Task | Form |
|---|---|
| One key figure | Tile or hero number, **not** a chart |
| Comparing magnitudes (categories) | horizontal bars, sorted |
| Trend over time | line (≤ 4 series), sparkline in the tile |
| Shares of a whole | share bar `.share-bar` (no pie, no donut chart) |
| Distribution / comparing two periods | line + gray comparison line `--chart-compare` |
| **Events and phases in their temporal position** | **timeline with lanes (7.6)** |
| Exact amounts | table — numbers may be worth reading |

Rule of thumb: **if a table says it just as well, use the table.**
Charts serve the overview; the exact values live in tables.

### 7.2 Mark specifications

| Mark | Spec |
|---|---|
| Line | 2 px, round caps and joins |
| Endpoint / marker | ≥ 8 px diameter, series color, **2 px ring in the surface color** |
| Bar | ≤ 24 px thick, data end rounded 4 px, square at the baseline |
| Area under a line | series hue at ~10 % opacity — never fully filled |
| Grid / axis | 1 px, solid, `--chart-grid` / `--chart-axis`, receding |
| Comparison period | 2 px, `--chart-compare` (gray), always behind the current series |
| Gap between segments | 2 px in the surface color — never a border around the mark |

### 7.3 Labeling

- **A legend is mandatory from two series on**; with one series the title says what is shown.
- Direct labels **sparingly**: endpoint, extreme value, or the one narrated series.
  Never a number at every point.
- **Text never carries the data color.** Labels take `--ink`, `--ink-2`, `--muted`;
  identity comes from the colored swatch next to them.
- Axis values at round numbers, German thousands separators, the unit once at the axis title.
- If a label does not fit inside a mark, it moves outside or is dropped —
  **never clipped**.

### 7.4 Forbidden

Two y-axes · pie/donut charts · 3D · rainbow scales · dashed gridlines ·
truncated y-axis on bars (bars start at 0) · color as the only carrier of
meaning · charts without a time reference.

### 7.5 Accessibility

Every graphic has either `role="img"` with an `aria-label` (sparkline) or an
accessible table with the same values nearby — usually the table, because the
exact values are needed anyway. Purely decorative SVGs get
`aria-hidden="true"`.

### 7.6 Timeline — `timeline()`, `timeline_key()`

The form for **"when was what"**: a horizontal, true-to-scale time axis, below it one
**lane** per subject area. It answers what a table cannot show — order,
duration, simultaneity, and gaps.

```python
timeline(lanes, date(2025, 1, 1), date(2026, 12, 31), today=date.today())
```

**Axis.** A month grid across the whole window: a hairline at each month start
(`--chart-grid`), a stronger line and year number at each turn of the year (`--chart-axis`).
Month abbreviations drop out automatically when a month becomes narrower than 26 px — then
only the quarter months remain (abbreviations from STRINGS: `months_short`). A 1 px line in `--faint`
marks **today**, labeled below the axis (STRINGS: `today`, `today_fmt`). The
window is fixed (e.g. reporting period + following year), not data-driven:
events before it are **clipped square** at the edge — the square edge means
"starts earlier", the round one "starts here".

**Lanes.** At most **six** (one series color per lane, slot order). The lane is
labeled directly — color swatch, name, the balance on the right ("12 events · documented 49.205,83 €").
This makes a separate legend for the colors unnecessary. **An empty lane stays in place**
and says what is missing; the hole is the statement.

**Marks.**

| Mark | Status (API value) | Spec |
|---|---|---|
| Bar | period | 10 px tall, ends rounded 4 px, **2 px seam** to adjacent bars (7.2) |
| Dot | point in time | 14 px, series color, 2 px ring in the surface color |
| filled | documented (`confirmed`) | full series color |
| hollow / tinted | assumption or forecast (`assumed`, `planned`) | surface color with series-color ring, or 30 % tint |
| gray | unresolved (`open`) | `--hairline` — a visible gap in the evidence |
| critical | deadline (`deadline`) | `--critical-mark`, **always labeled**, regardless of the lane's color |

The three states hang on the **shape**, not the color; `timeline_key()` explains them
below the chart (2.3). Deadlines are the only status color permitted in the data area —
they are status, not a series.

**Stacking.** Overlapping marks in a lane slide into a second row (28 px), never on
top of each other. Adjacent bars stay in **one** row — otherwise a payment
stream visually falls apart into stairs.

**Labeling.** A bar labels itself only if the text fits its width, a
dot only if there is room before the next mark — otherwise **not at all** (7.3, "never
clip"). Dot-dense lanes therefore stay deliberately silent; the details come from the
detail dialog.

**Interaction and accessibility.** Every mark is a `<button>` with a descriptive
`aria-label` and `title` that opens its detail dialog (6.17). **Mandatory:** the same
events additionally as a chronological table (time reference · event · lane · amount ·
status) in the same section — it is the chart's accessible twin (7.5) and the
only way to reach the values when no script runs.

**Width.** The chart has a minimum width (820 px) and sits in its own
scroll container; the **page** never scrolls horizontally (6.9).
