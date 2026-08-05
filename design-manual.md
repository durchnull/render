---
title: Design manual — HTML output of the render plugin
description: Binding design rules for all pages generated with the plugin engine (colors, typography, spacing, sections, components, charts).
updated: 2026-08-03
applies-to: engine/render.py and every additional renderer that includes design_system.py
source: Design references — Stripe dashboard screenshot, Untitled UI dashboard screenshot
---

# Design Manual

**Scope: binding.** Every HTML file produced with this engine follows this manual. The
executable version is [engine/design_system.py](engine/design_system.py) — the same values live
there as CSS custom properties (`TOKENS`), base styles (`BASE_CSS`), and component
helpers. **Renderers define no colors, sizes, or spacing of their own**; they import from
`design_system.py`. If a special case has to deviate, the deviation is added here —
not hidden in the renderer.

The foundation is the two reference screenshots: a payments dashboard (Stripe) and an
analytics dashboard (Untitled UI). Adopted from them: a calm neutral plane, white data
cards, **one** violet accent, large semibold key figures above small gray labels,
thin hairlines instead of boxed frames, plenty of whitespace.

This file is the core: principles, tokens, hierarchy, page structure, and the
component **catalog**. The component and behaviour reference lives in
`docs/design/` beside it, one file per topic, and is exactly as binding.
Section numbers are stable across the split — code cites them by number, and
the catalog in §6 maps every number to its file.

---

## 1. Core principles

1. **The surface is quiet, the data is loud.** Only numbers and chart marks carry
   color or weight. Backgrounds, lines, and labels recede.
2. **One accent.** Violet marks what is active, what is linked, and the primary data series. A
   second "brand tone" does not exist.
3. **Card = one statement.** Every card answers exactly one question and carries a title,
   a time reference, and — where useful — a footer with as-of date/source.
4. **Hierarchy through text size and color, not through borders.** Whitespace and
   hairlines may separate; boxes inside boxes inside boxes are forbidden.
5. **Self-contained.** No web fonts, no CDNs, no remote images, no tracking.
   Icons are inline SVG or Unicode. This doubles as a privacy requirement.
6. **Light and dark are both designed** — dark is not an inverted light, but
   its own, validated set of steps.
7. **One language, consistently.** All visible text — including axes,
   legends, and empty states — is in the project's language
   (`LANG` + `STRINGS` in `config.py`; engine default English,
   German block in `templates/config.py`). Number and date formats follow
   the same language; for German notation (`1.234,56 €`,
   `31.07.2026`) the engine ships `fmt_eur`, `fmt_num`, and `de_date`.

---

## 2. Colors

All values as CSS variables in `TOKENS`. The contrast ratios are measured (WCAG,
against the respective surface) — not estimated.

### 2.1 Surfaces and text

| Role | Token | Light | Dark | Usage |
|---|---|---|---|---|
| Page plane | `--plane` | `#f5f5f7` | `#0c0c0f` | Body background |
| Card | `--surface` | `#ffffff` | `#17171b` | Cards, tiles, chart surface |
| Control | `--raised` | `#ffffff` | `#1f1f23` | Buttons, inputs on cards |
| Inset | `--inset` | `#f9f9fb` | `#121216` | Code, quotes, context blocks |
| Primary text | `--ink` | `#101828` (17.8:1) | `#f7f7f8` (16.7:1) | Headings, values |
| Body text | `--ink-2` | `#475467` (7.7:1) | `#cecfd2` (11.5:1) | Paragraphs, labels |
| Meta | `--muted` | `#667085` (5.0:1) | `#94969c` (6.1:1) | Timestamps, axes, notes |
| Decorative | `--faint` | `#98a2b3` (2.6:1) | `#85888e` (5.0:1) | **never text** — icons and disabled elements only |
| Hairline | `--hairline` | `#eaecf0` | `#2a2a31` | Dividers, gridlines |
| Border | `--border` | `rgba(16,24,40,.10)` | `rgba(255,255,255,.10)` | Card and button borders |

Shadows only in light mode and only as a hint: `--shadow: 0 1px 2px rgba(16,24,40,.05)`.
In dark mode the border does the separating, not the shadow (`--shadow: none`).

### 2.2 Accent

| Token | Light | Dark | Usage |
|---|---|---|---|
| `--accent` | `#6941c6` (6.6:1) | `#b9a7fc` (8.5:1) | Link text, active labels, icons |
| `--accent-solid` | `#7f56d9` | `#7f56d9` | filled surfaces; white on top 5.0:1 |
| `--accent-soft` | `#f4f3ff` | `rgba(127,86,217,.18)` | Icon tiles, badge backgrounds |
| `--accent-line` | `#d9d6fe` | `rgba(127,86,217,.45)` | Borders of soft accent surfaces |

Rule: **Text takes `--accent`, surfaces take `--accent-solid`.** Never the other way around —
`#7f56d9` as body text on white falls below 5:1 and looks dull in dark mode.

### 2.3 Status

Status **always carries icon + word**, never color alone. The text tier and the chart tier
are separate, because the same color cannot do both jobs.

| Role | Text light / dark | Mark (≥ 3:1) light / dark | Soft surface | Example |
|---|---|---|---|---|
| good / done | `#067647` / `#47cd89` | `#079455` / `#17b26a` | `--good-soft` | "✓ on track" |
| warning / due soon | `#b54708` / `#fdb022` | `#dc6803` / `#f79009` | `--warning-soft` | "⚠ due soon" |
| critical / deadline | `#b42318` / `#fda29b` | `#d92d20` / `#f04438` | `--critical-soft` | "✕ deadline missed" |
| Info | `#175cd3` / `#84caff` | — | — | "to review" |

Status colors are **reserved** — never use them as "series 7" for data.

### 2.4 Series colors for charts

Fixed order, **never rotate, never generate**: slot 1 first, then 2, then 3 …

| Slot | Hue | Light | Dark |
|---|---|---|---|
| 1 | violet | `#6941c6` | `#9e77ed` |
| 2 | teal | `#0e9384` | `#0e9384` |
| 3 | blue | `#1570ef` | `#2e90fa` |
| 4 | orange | `#e04f16` | `#e04f16` |
| 5 | magenta | `#dd2590` | `#dd2590` |
| 6 | yellow | `#ca8504` | `#b08903` |

Validated against `#ffffff` and `#17171b` respectively: all six pass the lightness band,
chroma floor, color-vision-deficiency distance (worst neighbor pair
ΔE 14.6), normal-vision distance (17.2), and surface contrast — in **both** modes.

- **Six series at most.** Anything beyond that is merged into "Other" or split across
  several small charts. A seventh hue does not pass the validation.
- **For forms where any color can sit next to any other** (scatter, bubble charts):
  only **slots 1, 2, and 4** (violet, teal, orange) — this trio passes the validation
  across all pairs. Violet and blue side by side are too similar.
- **Color follows the thing, not the rank.** "Travel costs" keeps its hue even
  when the category slides to first place in another chart.
- If anyone changes a series value, the validation must be re-run — with a
  contrast/color-vision-deficiency checking tool of your choice, against both
  surfaces (`#ffffff` and `#17171b`) and across all neighbor pairs. The thresholds
  above (surface contrast ≥ 3:1, CVD ΔE, lightness band) are the yardstick; the
  result is recorded here in 2.4.

### 2.5 Scales for magnitude gradients

- **Sequential** (one quantity, e.g. amount magnitude in a heatmap): one hue, violet,
  light → dark. `#ebe9fe · #d9d6fe · #bdb4fe · #9e77ed · #7f56d9 · #6941c6 · #53389e`.
- **Ordinal** (graded classes, e.g. progress levels): light mode starts no earlier than
  `#9e77ed`, dark mode ends no later than `#53389e` — otherwise the first step vanishes
  into the surface. Both directions are validated.
- **Diverging** (signed deviation, e.g. target/actual): blue ↔ orange with
  neutral gray in the middle, the same number of steps per arm. Never a hue in the middle.
- **Never rainbows, never gradients as decoration.**

---

## 3. Typography and hierarchy

System font, everywhere: `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`.
No secondary typeface, no serifs, no display cuts — not even for large numbers.

### 3.1 Five levels, five sizes

The page has **exactly five text levels**. Each level has one size, and the jump
between two levels is large enough to recognize without comparing (factor ≈ 1.4).
All sizes live as tokens in `TOKENS`; **a renderer never writes a pixel size**.

| Level | Role | Token | Size / line height | Weight | Tracking | Color |
|---|---|---|---|---|---|---|
| **E1** | Page title (H1) | `--fs-hero` | 40 / 1.08 | 650 | −0.025em | `--ink` |
| **E2** | Section title (H2) | `--fs-h2` | 27 / 1.15 | 600 | −0.022em | `--ink` |
| **E3** | Card/group title (H3, `.subhead`, `.card-title`) | `--fs-h3` | 19 / 1.4 | 600 | −0.012em | `--ink` |
| **E4** | Row title, subheading in text (H4, `.acc-title`) | `--fs-h4` | 16 / 1.35 | 600 | −0.008em | `--ink` |
| **E5** | Body text | `--fs-body` | 15 / 1.6 | 400 | 0 | `--ink` |

Below these sit only **supporting tiers** that never carry a heading:

| Role | Token | Size | Weight | Color | Class |
|---|---|---|---|---|---|
| Secondary text, section subline | `--fs-sub` | 14.5 | 400 | `--ink-2` / `--muted` | `.card-sub`, `.section-head .sub` |
| KPI label, table cell | `--fs-label` | 13.5 | 500 / 400 | `--ink-2` | `.tile .label`, `td` |
| Meta / timestamp | `--fs-meta` | 12.5 | 400 | `--muted` | `.stamp`, `.acc-sub`, `.tile .sub` |
| Overline, table header | `--fs-eyebrow` | 11.5 | 600 | `--muted` | `.eyebrow`, `th`, `.focus .k` |
| Badge / delta | — | 12 | 600 | status color | `.badge`, `.delta` |
| Code | `--fs-meta` | 12.5 | 400 | `--ink-2` | `code`, `pre` |

On narrow screens **only the tokens** shrink (820 px and 620 px, see 4);
the rules themselves stay the same.

### 3.2 Three weight classes for numbers

A number is as large as its role — not as large as its space.

| Class | Token | Size | Usage |
|---|---|---|---|
| **Focus** | `--fs-focus` | 64 | **Exactly one number per page** (`.focus .value`) — the one the page is opened for. |
| KPI | `--fs-value` | 34 | Tiles of the overview row (`.tile .value`). |
| Secondary KPI | `--fs-value-sm` | 26 | Values in lists, quiet tiles (`.tile--quiet`). |

If there are two focus numbers, there is no focus number. When in doubt, the second one
drops down a class.

### 3.3 Making hierarchy visible

Size alone does not carry the structure — each level gets a **recurring
cue** the eye can recognize without reading:

| Level | Cue |
|---|---|
| E2 section | Overline with a numbered accent mark (`01`, `02`, …) above the title, hairline below, 56 px of air before it |
| E3 group | 3 px accent bar left of the title (`.subhead`, `.prose > h3`), hairline above |
| E4 row | 30 px mark on the left (number or icon), subtitle in `--muted` below |

In Markdown passages (`.prose`) the same applies automatically: a file's `##` becomes E3
with bar and divider, `###` becomes E4 with a dot. For this the renderer strips the
file's `# ` title line — the row or section title already says it.

**Weights.** Only three steps: 400 regular, 550–600 semibold for titles, values, badges and
table totals, 650 for the page title and the focus number. No 700+, no italics except in the
empty state (`.empty`) and for highlighting technical terms.

**Numbers.**
- Large single values (KPI tile, hero number): **proportional figures** — the default.
- Number columns in tables, list values, axis labels:
  `font-variant-numeric: tabular-nums` (class `.num`), right-aligned.
- German notation in body text: `1.234,56 €`, `12,5 %` (a narrow space before
  `%` is not required, but a regular space belongs there).
- Never abbreviate amounts ("12,9 T€") — wherever receipt-level values are shown, the
  exact value counts. Abbreviating is allowed only in sparklines/axes.
- Dates are stored ISO in the files (`2026-07-26`); the display follows the
  target language (German via `de_date()`, `26.07.2026`) — never reformatted by hand.

**Line length.** Body text at most ~75 characters: text pages use `.wrap--narrow`
(720 px), dashboards `.wrap` (1040 px) with text at card or column width.

---

## 4. Spacing and grid

4 px grid; only these steps (`--s1` … `--s10`):
`4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 56 · 72`.

| Purpose | Value |
|---|---|
| Page margin (desktop / mobile) | 24 / 16 |
| Content width dashboard / text | 1040 / 720 |
| **Space between sections** | **56** — the largest gap on the page; it separates the levels |
| Section head → content | 20 (hairline in between) |
| Group title (E3) → content | 12, with 32 before it |
| Card padding | 20 vertical / 24 horizontal (mobile 16) |
| Tile padding | 16 / 20 |
| Focus card padding | 32 top / 24 elsewhere, column gap 32 |
| Space between cards | 16 |
| Space between tiles | 12 |
| Label → value | 8 |
| Value → footnote | 8 |
| Table row (padding) | 9 top/bottom, 14 right |
| List/accordion row | 11 and 16 top/bottom respectively |

**The rhythm carries the structure.** 56 between sections, 32 between groups,
16 between cards, 12 between tiles. Whoever invents a gap in between makes the
levels indistinguishable.

**Grid.**
- KPI row: `.tiles` → `repeat(auto-fit, minmax(232px, 1fr))`, gap 12.
  At 1040 px exactly four tiles fit in one row — **which is why the overview row
  has four tiles**, not five (a fifth would stand alone as an orphan).
- Card grid: `.grid` → `repeat(auto-fit, minmax(260px, 1fr))`, gap 16.
  For wide cards `.grid--2` (320 px minimum).
- Focus card: two columns `minmax(200px, 300px) 1fr`, single column from 820 px.
- Breakpoints at **820 px** (titles 32 / 23, focus number 48) and **620 px**
  (titles 28 / 21, focus number 44, KPI 28, margins 16, cards full width).
  Only the tokens on `:root` are reduced, never individual rules.

**Radii.** Card 14 · tile 12 · input/banner 10 · button 9 · icon tile 10 ·
tag/chip/badge 999 · code 6. Invent nothing in between.

---

## 5. Page structure and sections

Order from top to bottom — as in both references:

1. **Hero.** Overline, H1 (E1), one line of context, below it a row of `.chip` with the
   project's framing data (e.g. reporting period, next deadline, status).
   No box, no background.
2. **Sticky navigation** (`nav.toc`): flat pills, translucent blurred background,
   hairline below. Only same-page jump targets, **short forms** of the section titles
   (one word, so the bar stays on one line). The section currently being read carries
   `.is-active` — set by an `IntersectionObserver` (see 6.16).
3. **Focus zone.** Exactly **one** `.focus` card, directly below the first section head:
   the number the page is opened for, plus next step and progress.
   Below it **four** KPI tiles as an inventory row — they count, they don't alarm.
4. **Content sections.** Each starts with `.section-head`: numbered overline, H2 (E2),
   subline, optionally status/counter on the right, hairline below. Then cards or a
   card grid. The numbers run through the whole page (`01` … `06`) and live in
   **one** list in the renderer, so navigation, order, and numbers can never
   drift apart.
5. **Footer.** Generating script, timestamp, self-containment note —
   for sensitive data also a confidentiality note.

**What catches the eye first** (descending): focus number → the focus card's status
bar → section numbers → KPI values → row titles. Whoever adds a new section
checks that it does not break this order.

**Long content becomes rows, not walls.** Everything that comes from a file
(records folder, FAQ, knowledge collection, log) appears as an `.acc` row with title,
subtitle, and as-of date — you expand what you need. The default is **closed**;
that keeps the page surveyable and the section structure visible.

**Card anatomy** (from the Stripe reference):

```
┌─ .card ──────────────────────────────────────────────┐
│  Title ⓘ                          [Action]           │  .card-head
│  Period / context                                    │  .card-sub
│                                                      │
│  … content (chart, list, table) …                    │
│                                                      │
│  View all receipts                As of 26.07., 20:41│  .card-foot
└──────────────────────────────────────────────────────┘
```

The footer is mandatory as soon as the card shows computed values: the follow-up
link on the left, the as-of date on the right ("🕒 As of …"). For estimated values it
additionally says "estimated — to review".

---

## 6. Components — the catalog

The component and behaviour reference lives beside this manual in
`docs/design/`, split by what a page is made of. **The catalog below is an
index, not a spec — read the reference file for every helper you call,
before writing the markup.** Which files a page needs is mechanical:

| Page flavour | Read |
|---|---|
| dashboard / report / any section page | `components.md`, plus `charts.md` when it charts |
| interactive page (form, checklist, app-like) | `components.md`, `chrome.md`, `interactive.md` |
| article / long-form | none of them — `scripts/article.py` embodies 11b |

### `docs/design/components.md` — §6 — the dashboard and report vocabulary

| § | Component | Helper |
|---|---|---|
| 6.0 | Section head `.section-head` | `section_head()` |
| 6.0b | Group title `.subhead` | `subhead()` |
| 6.0c | Focus card `.focus` | `focus_card()` |
| 6.1 | KPI tile `.tile` | `tile()` |
| 6.2 | Delta and badge | `delta()`, `badge()` |
| 6.3 | Chip and tag |  |
| 6.3b | Navigation path `.crumbs` | `crumbs()` |
| 6.4 | Buttons |  |
| 6.5 | Tabs / filter row |  |
| 6.6 | List row `.list-row` | `list_row()` |
| 6.7 | Meter `.meter` | `meter_row()` |
| 6.8 | Share bar `.share-bar` | `share_bar()` |
| 6.9 | Table |  |
| 6.10 | Collapsible `details` |  |
| 6.11 | Banner `.banner` |  |
| 6.12 | Empty state `.empty` |  |
| 6.13 | Icons | `icon()` |
| 6.14 | Entry row `.acc` | `accordion()` |
| 6.15 | Status mark `.mark` | `status_marks()` |
| 6.16 | Active navigation |  |
| 6.17 | Detail dialog `dialog.modal` | `modal_host()`, `modal_detail()`, `MODAL_JS` |
| 6.18 | Card shell `.card` | `card()` |

### `docs/design/chrome.md` — §6b — what interactive pages are operated with

| § | Component | Helper |
|---|---|---|
| 6.19 | Option row `.opt` | `option_row()` |
| 6.20 | Field `.field` | `field()`, `text_field()`, `amount_field()` |
| 6.21 | Note disclosure `.note-open` | part of `field()` |
| 6.22 | Progress bar `.progress` | `progress_bar()` |
| 6.23 | Action bar `.actionbar` | `action_bar()` |
| 6.24 | Toast `.toast` | `toast()` |
| 6.25 | Summary row `.sumrow` | `summary_row()` |
| 6.26 | Check row `.ck-row` | `check_row()` |

### `docs/design/charts.md` — §7 — forms, marks, labeling, the timeline

| § | Component | Helper |
|---|---|---|
| 7.1 | Choose the form (before the color) |  |
| 7.2 | Mark specifications |  |
| 7.3 | Labeling |  |
| 7.4 | Forbidden |  |
| 7.5 | Accessibility |  |
| 7.6 | Timeline | `timeline()`, `timeline_key()` |

### `docs/design/interactive.md` — §11 — the rules that make an interactive page honest

| § | Component | Helper |
|---|---|---|
| 11.1 | The three permitted script purposes |  |
| 11.2 | Content is in the document, not assembled in the browser |  |
| 11.3 | State is private, and the page says so |  |
| 11.4 | Nothing is mandatory |  |
| 11.5 | Keyboard and focus |  |
| 11.6 | What a person may never lose |  |
| 11.7 | When the document can change under the state |  |

### `docs/design/longform.md` — §11b — the reading tier for articles

| § | Component | Helper |
|---|---|---|
| 11b.1 | What changes, and why |  |
| 11b.2 | The masthead |  |
| 11b.3 | One drop cap, or none |  |
| 11b.4 | Links become text |  |

---

## 8. Dark mode

Via `prefers-color-scheme` in the same tokens, no toggle, no JavaScript.
Rules: surfaces go dark, **text is not pure white on black** (`#f7f7f8` on
`#17171b`), shadows are dropped, borders take over the separation, series and status colors
are their own, validated steps (see 2.4). Every color change is checked in **both**
modes.

---

## 9. Implementation in the renderer

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from design_system import (TOKENS, BASE_CSS, page, card, list_row, tile, badge, delta,
                           sparkline, share_bar, legend, meter_row, fmt_eur, fmt_num, de_date)

html = f"<style>{TOKENS}{BASE_CSS}</style>" + body
```

- `TOKENS` and `BASE_CSS` are **always included together and unmodified**.
- Page-specific CSS goes in its own block **after** `BASE_CSS` and uses
  tokens exclusively (`var(--s4)`, `var(--ink-2)`, …) — no raw hex values,
  no odd pixel values.
- **Project-local pages import only from `engine/page_api.py`** — the one
  stable facade for renderers that live in a consuming project's
  `.render/` directory. It re-exports the design system and content
  core and adds `page_shell()` (the standard shell around finished body
  markup) and `check_page()` (the same deterministic checks as
  `render.py --check`, run before writing — do not ship on findings).
  Everything else under `engine/` — module layout, private helpers,
  signatures outside the facade — is internal and may change in any
  release. The snippet above is the engine-internal form; outside the
  plugin it becomes `from page_api import …`.
- A new reusable component? Describe it here in the manual first, then implement it in
  `design_system.py`, then use it.
- **The visual reference is generated, not maintained:** `python3 engine/gallery.py`
  writes `design-gallery.html` (`-o` for another path) — every component rendered beside
  the snippet that produced it. The samples are evaluated from the shown snippets, so the
  gallery cannot drift from the engine. Regenerate after any change to `design_system.py`
  and check the result in both modes.

---

## 10. Checklist before shipping

- [ ] `TOKENS` + `BASE_CSS` included, **no hex value and no pixel size in the renderer**
      (`grep -nE "font-size: *[0-9]|#[0-9a-fA-F]{3,6}" <configdir>/sections/*.py` ⇒ empty).
- [ ] Five text levels recognizable, each with its cue (3.3); exactly **one** focus number.
- [ ] Sections numbered consecutively, numbers and navigation generated from **one** list.
- [ ] Checked light **and** dark (toggle the system setting).
- [ ] No horizontal page scroll at 375 px width; tables in `.table-wrap`.
- [ ] No colored emoji in the interface (6.13); status characters as `.mark`/`.badge`.
- [ ] At most six series colors, in slot order; legend from two series on.
- [ ] Timeline: no label clipped, states recognizable by shape,
      event table present as the twin; the detail dialog contains nothing that exists only there.
- [ ] Status always icon + word, never color alone.
- [ ] Every computed card has a time reference and an as-of date; estimates are marked as such.
- [ ] Amounts formatted in the target language, number columns right-aligned and tabular.
- [ ] No external resources (`render.py --check` ⇒ 0 external references).
- [ ] For sensitive data: confidentiality note in the footer.
- [ ] After a color change: validator run, result recorded in section 2.4.

For an **interactive page** (11), additionally:

- [ ] Every question, option and passage is in the document; nothing is assembled from a
      string at view time (11.2). The page reads top to bottom with scripting off.
- [ ] Script does only the three permitted things (11.1) — no fourth purpose crept in.
- [ ] Nothing is mandatory: "don't know" and "skip" exist, the note is reachable on every
      question, and the hand-back works from an empty page (11.4).
- [ ] Fully keyboard operable, the keys are stated on the page, focus lands on the new
      heading after every screen change (11.5).
- [ ] The fixed action bar covers nothing — the content column reserves its height (6.23).
- [ ] Progress counts against currently visible questions; conditional totals say
      "up to N" (6.22).
- [ ] `prefers-reduced-motion` suppresses auto-advance and transitions.
- [ ] The footer states where the answers live and that they go nowhere else (11.3), and
      the page still starts when storage is unavailable.
- [ ] If the source document can change under the page: state keys are content-derived,
      stale keys are dropped on load, and the hand-back carries `based-on:` (11.7).
- [ ] Printed, the page shows its content and none of its chrome (6b).

---


---

## 12. Provenance of the decisions

| Element | Source |
|---|---|
| Long-form tier: reading column, masthead, drop cap, links as text | own addition 2026-08-03 |
| Check row, content-addressed state, chrome hidden in print | own addition 2026-08-02 |
| Interactive pages: three script purposes, content in the document | own addition 2026-08-02 |
| Input and app chrome (option row, field, progress, action bar, toast, summary row) | own addition 2026-08-02 |
| Component gallery generated from the executable manual | own addition 2026-07-31 |
| Focus card with one very large number and a status bar | own addition 2026-07-26 |
| Timeline with lanes, state shapes, and detail dialog | own addition 2026-07-26 |
| Numbered section overlines as recurring landmarks | own addition 2026-07-26 |
| Large key figure above a small gray label, delta pill beside it | both |
| Stacked share bar with legend list and amounts on the right | Stripe |
| Line + gray comparison line of the previous period, labels only at the edges | Stripe |
| Card footer with link on the left and "As of …" on the right | Stripe |
| Status pills on a soft surface ("Blocked", "Failed") | Stripe |
| White cards with 1 px border, 12–14 px radius, hinted shadow on a gray plane | Untitled UI |
| Icon tile in a soft accent tone at the top of the KPI card | Untitled UI |
| Period tabs with underline, filters in one row | Untitled UI |
| Thin, fully rounded progress bars with percentage on the right | Untitled UI |
| Single violet accent, neutral grays | both |
