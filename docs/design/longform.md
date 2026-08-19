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
| Shell | `.wrap` (1040px) — room for a grid | `.wrap--read` (1160px) — room for the width tiers (11b.6); prose stays at 66 ch |
| Body face | `--font` (sans) | `--font-serif` — Charter / Sitka Text / Cambria, the book faces every OS ships |
| Body type | `--fs-body` / 1.6 | `--fs-read` (18px) / 1.55 — serif wants the size |
| Plane | `--plane` | `--plane-read` — barely warm in light, lifted and tinted in dark |
| Rhythm | dense, cards carry the grouping | open, whitespace carries the grouping |
| Entry point | the focus metric (6.0c) | the masthead: kicker, headline, lede, meta line |

**Two voices.** The text reads serif; the *apparatus* — masthead, meta line,
mini-TOC, captions, asides, sources, colophon — stays the sans, and code the
mono. "System fonts only" never meant `system-ui` for everything: the default
feeling of system-font pages comes from using the sans for the text too.
Colors, spacing steps, radii and dark mode are the same tokens as everywhere
else — an article and a dashboard from this engine must be recognisable as
the same family, or the design system has failed at its one job.

**Book paragraphing.** One mode per document, chosen by the renderer from the
text itself (`paragraph_mode()`): prose-led pieces take `.article--indent` —
`p + p` indents 1.5 em with no vertical gap, the strongest single "essay, not
README" signal; list- and code-heavy documents keep spaced paragraphs.
Indents *or* spacing, never both (Butterick).

**Display scale is fluid, reading scale is fixed.** H1 and H2 use `clamp()`
against the viewport; body text never scales with it — reading size is about
distance, not screen width (iA). This is the design system's own sizing, not
a renderer writing pixel values.

### 11b.2 The masthead

`article_head(title, kicker, lede, meta)`: an optional overline, the headline at
the fluid display size, an optional lede at `--fs-lede` held to 48 characters a line,
and the **meta line** over a hairline — tracked caps (3.3), derivable facts
only: date, word count, reading time (words / 230), source count, plus a
frontmatter `status` passed through verbatim, never invented. The lede is a
*standfirst* — it says what the piece is about, it does not repeat the headline.

### 11b.3 One drop cap, or none

The drop cap fires only on `.article > p:first-child` — a page that opens with a heading, a
list or a quote gets none, because a decoration that lands mid-page is noise. Likewise
`pull_quote()` is for **one** sentence per page: three pull quotes are none.

### 11b.4 Links become text — with internal anchors

1.4's self-containment rule has a consequence long-form pages meet more often than any
other flavour: prose is full of links, and `check_page()` refuses external URLs outright.
So a link is rendered as its **label plus a reference number** — a `sup.src-ref`
carrying an *internal* anchor into the `source_list()` at the foot, whose
entries link back (`↩`, `source_list(linked=True)`); a link inside the
project keeps its label alone; a URL inside a code sample loses its scheme
and nothing else, so the sample stays readable and stays honestly
unclickable. Internal anchors are the ones a self-contained page can honour;
a page never carries an anchor it cannot.

### 11b.5 Margin asides — `aside_note()`

Markdown footnotes (`[^key]` / `[^key]: …`) become **asides**: block-level
`<details open>` notes placed right after the paragraph that references them,
numbered in the accent, in the sans apparatus voice at 0.82 em. At reading
width (≥ 1210px) they float into the right rail Tufte-style; below it they
are an indented disclosure the reader may collapse. No JS packs or positions
anything, so **a paragraph anchoring two or more notes sends those notes to
the end-notes list instead** (`.endnotes`, same `fn-n` anchors) — an honest
fallback over overlapping floats.

Asides are for *extended discussions* (gwern's distinction); citations stay
in the numbered source list — links killed citation-footnotes.

### 11b.6 Three width tiers

The article column is a per-child cap, not a fixed box: prose at
`min(66ch, 100%)` centered, tables and code one tier wider (`92ch`, inside
their own `overflow-x: auto`), and full-bleed by explicit opt-in
(`.full-bleed`). The measure stays sacred; a width change is itself a rhythm
device, which is why it is never automatic for prose. Figcaptions move into
the right rail at reading width, sharing the aside geometry.

### 11b.7 Apparatus: dinkus, epigraph, mini-TOC, end matter

- **Dinkus** — the markdown `---` renders as a centered `· · ·` with ~3 em of
  air: the missing rhythm register between paragraph and H2. A thought break,
  not a rule.
- **Epigraph** — a blockquote that *opens* the document (before any prose)
  renders italic, borderless, with generous margins; a second paragraph
  inside it is read as the attribution — roman, right-aligned, muted. It
  gives a long document a front door.
- **Mini-TOC** — `mini_toc()` renders a `<details open>` contents list after
  the masthead **for documents with four or more sections**; every H2
  carries a slug id either way. The no-JS subset of a reading apparatus.
- **End matter** — `source_list(linked=True, colophon_line=…)`: the tracked-caps
  "Sources" label, `↩` backlinks from each entry to its first in-text
  reference, and the **colophon** — one line in the mono instrument voice
  stating what this file is: "rendered 2026-08-18 · 4,120 words · single
  file, works offline". The constraint stated as a point of pride.

### 11b.8 Print

A single file's natural second life is Cmd+P → PDF, and links-as-text plus
the source list already *is* the print answer to hyperlinks. `ARTICLE_CSS`
adds: 2 cm page margins, `widows`/`orphans` 3, `break-inside: avoid` on
figures, tables, code and quotes, asides un-floated back into the flow, the
mini-TOC dropped (page numbers do not exist to point at), and full-bleed
constrained to the page.
