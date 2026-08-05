<!-- Long-form pages (§11b) — part of the render design manual. -->

Part of the **design manual** and exactly as binding: the core rules,
tokens and catalog live in `design-manual.md`; this file is the
reference for the helpers it lists. Section numbers are stable and
cited from code.

## 11b. Long-form pages

A dashboard is **scanned**: numbers first, everything in reach, the eye jumping between
tiles. A long-form page is **read**: one column, top to bottom, for minutes rather than
seconds. Same tokens, same components, different job — so the reading page opts into
`ARTICLE_CSS` the way an interactive page opts into `FORM_CSS`/`APP_CSS` (6b), and a page
that reports numbers carries none of it.

### 11b.1 What changes, and why

| | Display page | Long-form page |
|---|---|---|
| Column | `.wrap` (1040px) — room for a grid | `.wrap--narrow` (720px) — ~65 characters a line |
| Body type | `--fs-body` / 1.6 | `--fs-read` / 1.72 — larger and airier for sustained reading |
| Rhythm | dense, cards carry the grouping | open, whitespace carries the grouping |
| Entry point | the focus metric (6.0c) | the masthead: kicker, headline, lede, meta line |

Nothing else moves. Colors, spacing steps, radii, code blocks, tables and dark mode are the
same tokens as everywhere else — an article and a dashboard from this engine must be
recognisable as the same family, or the design system has failed at its one job.

### 11b.2 The masthead

`article_head(title, kicker, lede, meta)`: an optional overline, the headline at
`--fs-hero`, an optional lede at `--fs-lede` held to 48 characters a line, and a meta line
of short facts (date, reading time, source) over a hairline. The lede is a *standfirst* —
it says what the piece is about, it does not repeat the headline.

### 11b.3 One drop cap, or none

The drop cap fires only on `.article > p:first-child` — a page that opens with a heading, a
list or a quote gets none, because a decoration that lands mid-page is noise. Likewise
`pull_quote()` is for **one** sentence per page: three pull quotes are none.

### 11b.4 Links become text

1.4's self-containment rule has a consequence long-form pages meet more often than any
other flavour: prose is full of links, and `check_page()` refuses external URLs outright.
So a link is rendered as its **label plus a reference number**, resolved in a
`source_list()` at the foot; a link inside the project keeps its label alone; a URL inside a
code sample loses its scheme and nothing else, so the sample stays readable and stays
honestly unclickable. A page never carries an anchor it cannot honour.
