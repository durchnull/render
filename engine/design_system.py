#!/usr/bin/env python3
"""Design system for every HTML output rendered with this engine.

Single source of truth for colors, typography, spacing and components.
The rules and their rationale live in the plugin's `design-manual.md` —
this module is the executable version of that manual.

Usage in a renderer:

    from design_system import TOKENS, BASE_CSS, tile, badge, sparkline

    html = f"<style>{TOKENS}{BASE_CSS}</style>…"

Nothing here loads external resources: no web fonts, no CDN scripts, no
remote images. Every generated page stays a single, offline-capable file.

User-visible text is English by default and configurable: every string the
design system emits lives in STRINGS below, and a project overrides any key
via its config.py STRINGS dict (render.py forwards them through
set_strings()). templates/config.py carries a ready-made German block.
"""

from __future__ import annotations

import html as _html
import json as _json
import re as _re
from datetime import date as _date

# ---------------------------------------------------------------- strings ----
# Every user-visible text this module emits. English defaults; projects
# override via config.STRINGS (unknown keys are ignored here — render.py's
# own keys share the same dict).

STRINGS = {
    "months_short": ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    "today": "today",
    "today_fmt": "%Y-%m-%d",
    "key_span": "Period",
    "key_dot": "Point in time",
    "key_soft": "Assumption or forecast",
    "key_open": "unresolved",
    "key_deadline": "Deadline",
    "key_hint": "Click a mark to open its details",
    "modal_aria": "Event detail",
    "modal_prev": "← Earlier",
    "modal_next": "Later →",
    "modal_close": "Close",
    "mark_confirmed": "confirmed",
    "mark_low": "low",
    "mark_assumption": "assumption",
    "mark_attention": "attention",
    "mark_high": "high",
    "mark_no": "no",
    "mark_unknown": "unknown",
    "mark_important": "important",
    "mark_done": "done",
    "mark_open": "open",
    "focus_kicker": "Focus",
    "crumbs_label": "Path",
    # Input and app chrome (6b) — only interactive pages emit these.
    "progress_of": "{done} of {total}",
    "progress_upto": "up to",
    "actions_aria": "Actions",
    "state_answered": "answered",
    "state_unclear": "don't know",
    "state_skipped": "skipped",
    "state_open": "not provided",
    "check_obsolete": "obsolete",
    "check_todo": "to do",
    "check_na": "n/a",
    "check_deferred": "later",
    "check_note_open": "+ add a note",
    "check_note_label": "Anything to add?",
    "check_note_placeholder": "in your own words",
    "toc_contents": "Contents",
    "copy_ok": "copied to the clipboard",
    "copy_manual": "could not copy — select the block below and copy it by hand",
    # List behavior (6.5 / 6.6) — filter pills and the show-all trigger.
    "filter_aria": "Filter",
    "filter_all": "all",
    "filter_empty": "nothing matches this filter",
    "show_all": "show all {n}",
}


_DEFAULT_STRINGS = dict(STRINGS)


def set_strings(overrides) -> None:
    """Reset to the defaults, then merge the supplied overrides.

    The engine calls this once per page (project-wide STRINGS merged with
    the page's own), so one page's overrides never leak into the next.
    """
    STRINGS.clear()
    STRINGS.update(_DEFAULT_STRINGS)
    if overrides:
        STRINGS.update({k: v for k, v in overrides.items() if k in _DEFAULT_STRINGS})

# ----------------------------------------------------------------- tokens ----
# Colors: neutral gray + one violet accent (screenshot template).
# Contrasts (WCAG, against the respective surface) are noted in the trailing comments;
# series colors are checked for contrast + color-vision deficiency — see design-manual.md 2.4.
#
# The architecture underneath (design-manual.md 2.1): two Geist-style
# 10-step scales, identical structure for gray and violet — steps 100–300
# are backgrounds, 400–600 lines and borders, 700 reserved, 800 meta text,
# 900 secondary text, 1000 primary text. The semantic tokens below are
# assigned FROM these tables, so dark mode is a re-derivation of the same
# structure instead of a set of per-component overrides. The "surface" and
# "raised" keys carry the card tier, which sits between the numeric steps
# in dark mode and is plain white in light mode.
#
# Dark surfaces are tinted 2–3 % toward the violet hue (design-manual.md
# 2.1/8) — never pure neutral black. Text steps stay neutral.

GRAY = {
    "light": {100: "#f9f9fb", 200: "#f5f5f7", 300: "#eaecf0",
              400: "#d0d5dd", 500: "#b9bec8", 600: "#98a2b3",
              700: "#7d8698", 800: "#667085", 900: "#475467",
              1000: "#101828",
              "surface": "#ffffff", "raised": "#ffffff"},
    "dark": {100: "#121118", 200: "#0d0c12", 300: "#2b2a33",
             400: "#3b3a45", 500: "#5e5d6b", 600: "#85888e",
             700: "#8b8d94", 800: "#94969c", 900: "#cecfd2",
             1000: "#f7f7f8",
             "surface": "#17161c", "raised": "#1f1e25"},
}

VIOLET = {
    "light": {100: "#f4f3ff", 200: "#ebe9fe", 300: "#d9d6fe",
              400: "#bdb4fe", 500: "#9e77ed", 600: "#7f56d9",
              700: "#6941c6", 800: "#53389e", 900: "#42307d",
              1000: "#2c1c5f"},
    # Dark mode re-derives by role: text lightens past the 400 step, the
    # solid surface stays put, and the soft tiers become translucent 600.
    "dark": {"text": "#b9a7fc", "solid": "#7f56d9",
             "soft": "rgba(127,86,217,0.18)", "line": "rgba(127,86,217,0.45)",
             "series": "#9e77ed"},
}

_SCALE = {}
for _mode in ("light", "dark"):
    for _step, _value in GRAY[_mode].items():
        _SCALE[f"g{_step}" if _mode == "light" else f"gd{_step}"] = _value
for _step, _value in VIOLET["light"].items():
    _SCALE[f"v{_step}"] = _value
for _role, _value in VIOLET["dark"].items():
    _SCALE[f"vd_{_role}"] = _value

TOKENS = """
:root {
  color-scheme: light;

  /* Surfaces */
  --plane: %(g200)s;        /* page background */
  --surface: %(gsurface)s;      /* cards, tiles, table surfaces */
  --raised: %(graised)s;       /* controls on cards */
  --inset: %(g100)s;        /* inset blocks: code, quote, context */
  --plane-read: #fbfaf6;   /* the article tier's warm plane (11b) */

  /* Text */
  --ink: %(g1000)s;          /* 17.8:1 — headings, values */
  --ink-2: %(g900)s;        /* 7.7:1  — body text, labels */
  --muted: %(g800)s;        /* 5.0:1  — meta, axes, timestamps */
  --faint: %(g600)s;        /* 2.6:1  — decoration/icons/disabled ONLY, never text */

  /* Lines */
  --hairline: %(g300)s;     /* dividers, gridlines, table rules */
  --border: rgba(16,24,40,0.10);
  --shadow: 0 1px 2px rgba(16,24,40,0.05);
  --shadow-lift: 0 2px 8px rgba(16,24,40,0.07);

  /* Accent */
  --accent: %(v700)s;       /* 6.6:1 — links, active states, text */
  --accent-solid: %(v600)s; /* surfaces; white on top 5.0:1 */
  --accent-soft: %(v100)s;  /* badge/icon background */
  --accent-line: %(v300)s;  /* border of soft accent surfaces */
  --on-accent: #ffffff;    /* text on --accent-solid; 5.0:1 */

  /* Status — text/border (dark step) */
  --good: #067647;         /* 5.7:1 */
  --warning: #b54708;      /* 5.4:1 */
  --critical: #b42318;     /* 6.6:1 */
  --info: #175cd3;         /* 5.6:1 */
  /* Status — surfaces & marks in charts (>= 3:1 against --surface) */
  --good-mark: #079455;
  --warning-mark: #dc6803;
  --critical-mark: #d92d20;
  --good-soft: #ecfdf3;
  --warning-soft: #fffaeb;
  --critical-soft: #fef3f2;

  /* Categorical series colors — fixed order, never rotate, max. 6 */
  --series-1: %(v700)s;  /* violet   */
  --series-2: #0e9384;  /* teal     */
  --series-3: #1570ef;  /* blue     */
  --series-4: #e04f16;  /* orange   */
  --series-5: #dd2590;  /* magenta  */
  --series-6: #ca8504;  /* yellow   */

  /* Chart chrome */
  --chart-grid: %(g300)s;
  --chart-axis: %(g400)s;
  --chart-compare: %(g500)s;   /* previous-period line */

  /* Spacing (4-px grid) */
  --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px; --s5: 20px;
  --s6: 24px; --s7: 32px; --s8: 40px; --s9: 56px; --s10: 72px;

  /* Radii */
  --r-card: 14px; --r-tile: 12px; --r-input: 10px; --r-btn: 9px;
  --r-chip: 999px; --r-small: 6px;

  /* Type. The serif stack is the article tier's reading face (11b) — real
     book faces every OS ships; the apparatus around the text stays sans. */
  --font: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-serif: Charter, "Bitstream Charter", "Sitka Text", Cambria, serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;

  /* Font sizes — exactly one step per hierarchy level (design-manual.md, 3.1).
     Renderers never write a pixel size; they pull these tokens. */
  --fs-hero: 40px;         /* E1  page title                        */
  --fs-h2: 27px;           /* E2  section title                     */
  --fs-h3: 19px;           /* E3  card/group title                  */
  --fs-h4: 16px;           /* E4  subheading in body text, rows     */
  --fs-body: 15px;         /* E5  body text                         */
  --fs-read: 18px;         /*     long-form body text, serif (ARTICLE_CSS) */
  --fs-lede: 21px;         /*     lede / pull quote (ARTICLE_CSS)    */
  /* The reading measure (11b.6) as a length, not ch: a ch-based cap would
     resize with every child's own font and misalign headings with prose. */
  --measure-read: 600px;   /*     ~66 ch of Charter at --fs-read      */
  --measure-wide: 860px;   /*     the wide tier: tables, code         */
  --fs-sub: 14.5px;        /*     secondary text, section subline   */
  --fs-label: 13.5px;      /*     metric label, table cell          */
  --fs-meta: 12.5px;       /*     meta, timestamps, footer          */
  --fs-eyebrow: 11.5px;    /*     overline, table header            */
  /* Metrics — three weight classes, see 3.2 */
  --fs-focus: 64px;        /*     focus metric (exactly one per page) */
  --fs-value: 34px;        /*     tile metric                       */
  --fs-value-sm: 26px;     /*     secondary metric                  */
}

@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --plane: %(gd200)s;
    --surface: %(gdsurface)s;
    --raised: %(gdraised)s;
    --inset: %(gd100)s;
    --plane-read: #141318;

    --ink: %(gd1000)s;        /* 16.7:1 */
    --ink-2: %(gd900)s;      /* 11.5:1 */
    --muted: %(gd800)s;      /* 6.1:1  */
    --faint: %(gd600)s;      /* 5.0:1  */

    --hairline: %(gd300)s;
    --border: rgba(255,255,255,0.10);
    --shadow: none;
    --shadow-lift: none;

    --accent: %(vd_text)s;     /* 8.5:1 */
    --accent-solid: %(vd_solid)s;
    --accent-soft: %(vd_soft)s;
    --accent-line: %(vd_line)s;
    --on-accent: #ffffff;

    --good: #47cd89;       /* 8.8:1 */
    --warning: #fdb022;    /* 9.7:1 */
    --critical: #fda29b;   /* 9.2:1 */
    --info: #84caff;
    --good-mark: #17b26a;
    --warning-mark: #f79009;
    --critical-mark: #f04438;
    --good-soft: rgba(23,178,106,0.16);
    --warning-soft: rgba(247,144,9,0.16);
    --critical-soft: rgba(240,68,56,0.16);

    --series-1: %(vd_series)s;
    --series-2: #0e9384;
    --series-3: #2e90fa;
    --series-4: #e04f16;
    --series-5: #dd2590;
    --series-6: #b08903;

    --chart-grid: %(gd300)s;
    --chart-axis: %(gd400)s;
    --chart-compare: %(gd500)s;
  }
}
""" % _SCALE

# --------------------------------------------------------------- base css ----

BASE_CSS = """
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--plane); color: var(--ink);
  font: 400 var(--fs-body)/1.6 var(--font);
  -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
}

/* ---- Layout ------------------------------------------------------------ */
.wrap { max-width: 1040px; margin: 0 auto; padding: 0 var(--s6) var(--s10); }
.wrap--narrow { max-width: 720px; }
section { margin-top: var(--s9); scroll-margin-top: 76px; }
.grid { display: grid; gap: var(--s4); grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
.grid--2 { grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
.tiles { display: grid; gap: var(--s3); grid-template-columns: repeat(auto-fit, minmax(232px, 1fr)); }

/* Bento grid (design-manual.md 5.2c): importance decides span — only for
   pages whose author genuinely ranked the tiles. DOM order = visual order. */
.bento { display: grid; gap: var(--s4); grid-template-columns: repeat(6, 1fr); }
.bento > .card, .bento > .tile { margin-bottom: 0; height: 100%; }
.bento .b-2 { grid-column: span 2; }
.bento .b-3 { grid-column: span 3; }
.bento .b-4 { grid-column: span 4; }
.bento .b-6 { grid-column: span 6; }
.bento .b-hero { grid-column: span 4; grid-row: span 2; }
@media (max-width: 820px) {
  .bento { grid-template-columns: 1fr; }
  .bento > * { grid-column: auto !important; grid-row: auto !important; }
}
.row { display: flex; align-items: center; gap: var(--s2); flex-wrap: wrap; }
.spacer { flex: 1 1 auto; }

/* ---- Header & navigation ------------------------------------------------ */
/* Cross-page chrome (5.5): the same tiny header on every generated page —
   project mark, the way back to the index, the rendered date. Navigation
   learned once; provenance stated once. */
.pagebar { display: flex; align-items: baseline; gap: var(--s3);
  padding: var(--s3) 0 var(--s2); border-bottom: 1px solid var(--hairline);
  color: var(--muted); font: 400 12px var(--font-mono);
  font-variant-numeric: tabular-nums; }
.pagebar .k { letter-spacing: 0.05em; text-transform: uppercase; font-size: 11px; }
.pagebar a { color: var(--muted); text-decoration: none; }
.pagebar a:hover { color: var(--accent); }

header.hero { padding: var(--s9) 0 var(--s4); }
.eyebrow {
  display: inline-flex; align-items: center; gap: var(--s2);
  font-size: var(--fs-eyebrow); font-weight: 600; letter-spacing: 0.07em;
  text-transform: uppercase; color: var(--muted); margin-bottom: var(--s3);
}
.eyebrow .num {
  display: inline-grid; place-items: center; width: 23px; height: 23px; flex: none;
  border-radius: var(--r-small); background: var(--accent-soft); color: var(--accent);
  border: 1px solid var(--accent-line);
  font-size: 11.5px; font-weight: 600; letter-spacing: 0; font-variant-numeric: tabular-nums;
}
header.hero h1 {
  font-size: var(--fs-hero); font-weight: 650; letter-spacing: -0.025em;
  line-height: 1.08; margin: 0 0 var(--s3);
}
header.hero p { margin: 0; color: var(--ink-2); font-size: var(--fs-sub); }
header.hero .row { margin-top: var(--s3); gap: var(--s2); }

nav.toc {
  position: sticky; top: 0; z-index: 5; display: flex; gap: var(--s1); flex-wrap: wrap;
  background: color-mix(in srgb, var(--plane) 90%, transparent);
  backdrop-filter: blur(10px); padding: var(--s3) 0; margin-bottom: var(--s2);
  border-bottom: 1px solid var(--hairline);
}
nav.toc a {
  color: var(--muted); text-decoration: none; font-size: 13.5px; font-weight: 550;
  padding: 6px 13px; border-radius: var(--r-chip);
}
nav.toc a:hover { background: var(--surface); color: var(--ink); box-shadow: var(--shadow); }
nav.toc a.is-active { background: var(--accent-soft); color: var(--accent); box-shadow: none; }

/* ---- Section head ------------------------------------------------------ */
.section-head {
  display: flex; align-items: flex-end; gap: var(--s4); flex-wrap: wrap;
  padding-bottom: var(--s4); margin-bottom: var(--s5); border-bottom: 1px solid var(--hairline);
}
.section-head h2 {
  font-size: var(--fs-h2); font-weight: 600; letter-spacing: -0.022em; line-height: 1.15; margin: 0;
}
/* Count chip on a section head (6.0): magnitude before content. */
.section-head h2 .tag {
  vertical-align: 5px; margin-left: var(--s2); color: var(--muted);
  font-variant-numeric: tabular-nums; letter-spacing: 0;
}
.section-head .sub { color: var(--muted); font-size: var(--fs-sub); margin: 6px 0 0; max-width: 64ch; }
.section-head .eyebrow { margin-bottom: var(--s2); }
section > h2 { font-size: var(--fs-h2); font-weight: 600; letter-spacing: -0.022em; margin: 0 0 var(--s5); }

/* ---- Cards ------------------------------------------------------------- */
.card {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-card);
  box-shadow: var(--shadow); padding: var(--s5) var(--s6); margin-bottom: var(--s4);
}
.card--flat { box-shadow: none; }
.card--pad { padding: var(--s6); }
.card-head { display: flex; align-items: baseline; gap: var(--s2); margin-bottom: var(--s1); }
.card-head .icon-badge { align-self: center; width: 28px; height: 28px;
  margin-right: var(--s1); }
.card-title { font-size: var(--fs-h3); font-weight: 600; letter-spacing: -0.012em; margin: 0; }
.card-sub { font-size: var(--fs-meta); color: var(--muted); margin: 0 0 var(--s4); }
.card-foot {
  display: flex; align-items: center; gap: var(--s3); flex-wrap: wrap;
  margin-top: var(--s5); padding-top: var(--s3); border-top: 1px solid var(--hairline);
  color: var(--muted); font: 400 12px var(--font-mono);
  font-variant-numeric: tabular-nums;
}

/* ---- Group title inside a card (level 3) ------------------------------- */
.subhead {
  display: flex; align-items: center; gap: var(--s3); flex-wrap: wrap;
  font-size: var(--fs-h3); font-weight: 600; letter-spacing: -0.012em;
  margin: var(--s7) 0 var(--s3);
}
.subhead::before {
  content: ""; flex: none; width: 3px; height: 18px; border-radius: 2px; background: var(--accent-line);
}
.subhead .sub { font-size: var(--fs-meta); font-weight: 400; color: var(--muted); }
.card > .subhead:first-child, .prose > .subhead:first-child { margin-top: 0; }

/* ---- Metric tile ------------------------------------------------------- */
.tile {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-tile);
  box-shadow: var(--shadow); padding: var(--s4) var(--s5);
}
/* Chips wrap under the label when the tile is narrow — never past the edge. */
.tile-head { display: flex; flex-wrap: wrap; align-items: flex-start; gap: var(--s2); min-height: 34px; }
.tile .label { flex: 1 1 auto; font-size: var(--fs-label); font-weight: 500; line-height: 1.35; color: var(--ink-2); }
.tile .value { font-size: var(--fs-value); font-weight: 600; line-height: 1.1; letter-spacing: -0.02em; margin-top: var(--s2); }
.tile .value.sm { font-size: var(--fs-value-sm); }
.tile .sub { font-size: var(--fs-meta); color: var(--muted); margin-top: var(--s2); }
.tile .spark { margin-top: var(--s3); }
.tile--quiet { background: transparent; box-shadow: none; border-style: dashed; }
.tile--quiet .value { font-size: var(--fs-value-sm); }
/* Tile variants (6.1): a one-sentence verdict, a capacity bar, a triplet. */
.tile .trend { display: flex; align-items: baseline; gap: 6px; font-size: var(--fs-meta);
  color: var(--ink-2); margin-top: var(--s2); }
.tile .trend .dir { color: var(--muted); font-size: 11px; }
.tile .capacity { margin-top: var(--s3); }
.tile .capacity .meter { display: block; }
.tile .capacity .cap-note { font-size: var(--fs-meta); color: var(--muted);
  font-variant-numeric: tabular-nums; margin-bottom: var(--s1); }
/* Two columns, never three: a third stat wraps to a second row (2x2), so a
   tile-sized card never crams three columns into its own width. */
.tile-trio { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0; }
.tile-trio > div { min-width: 0; }
.tile-trio > div:nth-child(odd) { padding-right: var(--s4); }
.tile-trio > div:nth-child(even) { padding-left: var(--s4); border-left: 1px solid var(--hairline); }
.tile-trio > div:nth-child(n+3) { border-top: 1px solid var(--hairline); padding-top: var(--s3); margin-top: var(--s3); }
.tile-trio .label { font-size: var(--fs-label); font-weight: 500; color: var(--ink-2); }
.tile-trio .value { font-size: var(--fs-value-sm); font-weight: 600; letter-spacing: -0.02em;
  margin-top: var(--s1); font-variant-numeric: tabular-nums; }
.tile-trio .sub { font-size: var(--fs-meta); color: var(--muted); margin-top: 2px; }
.icon-badge {
  flex: none; width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center;
  background: var(--accent-soft); color: var(--accent); font-size: 16px; line-height: 1;
}
.icon-badge svg, .acc-mark svg, .chip svg, .stamp svg { display: block; }

/* ---- Focus card (exactly one per page) ---------------------------------- */
.focus {
  position: relative; overflow: hidden;
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-card);
  box-shadow: var(--shadow-lift); padding: var(--s7) var(--s6) var(--s6);
  display: grid; grid-template-columns: minmax(200px, 300px) 1fr; gap: var(--s5) var(--s7);
  margin-bottom: var(--s3);
}
.focus::before {
  content: ""; position: absolute; inset: 0 0 auto 0; height: 4px; background: var(--accent-solid);
}
.focus--warn::before { background: var(--warning-mark); }
.focus--crit::before { background: var(--critical-mark); }
.focus--good::before { background: var(--good-mark); }
.focus .lead { display: flex; flex-direction: column; gap: var(--s2); }
.focus .value {
  font-size: var(--fs-focus); font-weight: 650; line-height: 0.98; letter-spacing: -0.035em;
}
.focus .label { font-size: var(--fs-h4); font-weight: 600; color: var(--ink); line-height: 1.3; }
.focus .sub { font-size: var(--fs-meta); color: var(--muted); }
.focus .aside { display: flex; flex-direction: column; gap: var(--s4); min-width: 0; }
.focus .aside .k { font-size: var(--fs-eyebrow); font-weight: 600; letter-spacing: 0.07em;
  text-transform: uppercase; color: var(--muted); margin-bottom: var(--s2); }
.focus .aside .v { font-size: var(--fs-sub); color: var(--ink); line-height: 1.5; }
.focus .aside .v strong { font-weight: 600; }
.focus .meter-row { grid-template-columns: max-content 1fr 46px; padding: 0; }

/* ---- Metric-tab hero (design-manual.md 5.2b) ------------------------------ */
/* One hero chart card whose header row IS the KPI strip: one metric marked
   active (violet underline) and plotted below. Static — no series switching. */
.metric-tabs { display: flex; flex-wrap: wrap; border-bottom: 1px solid var(--hairline);
  margin: 0 0 var(--s5); }
.metric-tabs .mt { min-width: 0; padding: var(--s2) var(--s5) var(--s3) var(--s4);
  border-left: 1px solid var(--hairline); border-bottom: 2px solid transparent;
  margin-bottom: -1px; }
.metric-tabs .mt:first-child { border-left: 0; padding-left: 0; }
.metric-tabs .mt .label { font-size: var(--fs-label); font-weight: 500; color: var(--ink-2); }
.metric-tabs .mt .value { font-size: var(--fs-value-sm); font-weight: 600;
  letter-spacing: -0.02em; margin-top: var(--s1); font-variant-numeric: tabular-nums; }
.metric-tabs .mt .sub { font-size: var(--fs-meta); color: var(--muted); margin-top: 2px; }
.metric-tabs .mt.is-active { border-bottom-color: var(--accent-solid); }
.metric-tabs .mt.is-active .label { color: var(--ink); font-weight: 600; }

/* ---- Status mark in body text (replaces colorful emoji) ----------------- */
.mark {
  display: inline-grid; place-items: center; width: 19px; height: 19px; flex: none;
  border-radius: var(--r-chip); font-size: 11px; font-weight: 600; line-height: 1;
  vertical-align: -4px; margin-right: 3px;
  background: var(--inset); color: var(--muted); border: 1px solid var(--border);
}
.mark--good { background: var(--good-soft); color: var(--good); border-color: transparent; }
.mark--warn { background: var(--warning-soft); color: var(--warning); border-color: transparent; }
.mark--crit { background: var(--critical-soft); color: var(--critical); border-color: transparent; }

/* ---- Badges, Chips, Tags ----------------------------------------------- */
.delta, .badge {
  display: inline-flex; align-items: center; gap: 4px; white-space: nowrap;
  font-size: 12px; font-weight: 600; border-radius: var(--r-chip); padding: 2px 9px;
  background: var(--inset); color: var(--ink-2); border: 1px solid var(--border);
  font-variant-numeric: tabular-nums;
}
.badge--good, .delta.up   { background: var(--good-soft); color: var(--good); border-color: transparent; }
.badge--warn              { background: var(--warning-soft); color: var(--warning); border-color: transparent; }
.badge--crit, .delta.down { background: var(--critical-soft); color: var(--critical); border-color: transparent; }
.badge--accent            { background: var(--accent-soft); color: var(--accent); border-color: transparent; }
.chip {
  display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; font-weight: 500;
  color: var(--ink-2); border: 1px solid var(--border); border-radius: var(--r-chip); padding: 3px 11px;
}
.chip .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); flex: none; }
.tag {
  font-size: 11px; font-weight: 600; color: var(--ink-2);
  border: 1px solid var(--border); border-radius: var(--r-chip); padding: 1px 8px;
}
/* Metadata reads as instrument, not brochure (3.3): timestamps, sources and
   counts take the system mono stack — numbers align for free. */
.stamp { display: inline-flex; align-items: center; gap: 5px; color: var(--muted);
  font: 400 12px var(--font-mono); font-variant-numeric: tabular-nums; }

/* ---- Navigation path inside a foreign interface (6.3b) ------------------ */
.crumbs {
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 6px;
  font-size: var(--fs-meta); line-height: 1.5; color: var(--muted);
}
.crumbs .k {
  font-size: var(--fs-eyebrow); font-weight: 600; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--muted);   /* --faint would be text below 3:1 */
}
.crumbs .c--target { color: var(--ink-2); font-weight: 550; }
.crumbs .sep { color: var(--faint); }

/* ---- Controls ------------------------------------------------------------ */
.btn {
  display: inline-flex; align-items: center; gap: 7px; font: inherit; font-size: 13.5px; font-weight: 550;
  cursor: pointer; border-radius: var(--r-btn); padding: 8px 14px;
  border: 1px solid var(--border); background: var(--raised); color: var(--ink);
  box-shadow: var(--shadow); text-decoration: none;
}
.btn:hover { background: var(--inset); }
.btn--primary { background: var(--accent-solid); border-color: var(--accent-solid); color: var(--on-accent); }
.btn--primary:hover { background: color-mix(in srgb, var(--accent-solid) 88%, #000); }
.btn--ghost { background: transparent; border-color: transparent; box-shadow: none; color: var(--ink-2); }
.btn--ghost:hover { background: var(--inset); color: var(--ink); }
.btn:disabled { opacity: .45; cursor: not-allowed; }

.tabs { display: flex; gap: var(--s5); border-bottom: 1px solid var(--hairline); }
.tabs a, .tabs button {
  font: inherit; font-size: 13.5px; font-weight: 500; color: var(--muted);
  background: none; border: 0; padding: 8px 0; cursor: pointer; text-decoration: none;
  border-bottom: 2px solid transparent; margin-bottom: -1px;
}
.tabs .is-active { color: var(--ink); border-bottom-color: var(--accent-solid); font-weight: 600; }
.filters { display: flex; align-items: center; gap: var(--s2); flex-wrap: wrap; margin-bottom: var(--s4); }
.filters .note { font-size: 13px; color: var(--muted); }
.filters button.chip { font: inherit; font-size: 12.5px; font-weight: 500; background: var(--surface); cursor: pointer; }
.filters button.chip:hover { background: var(--inset); color: var(--ink); }
.filters button.chip.is-active { background: var(--accent-soft); color: var(--accent); border-color: transparent; }
.is-filtered-out { display: none !important; }

/* ---- Lists ------------------------------------------------------------- */
.list { display: flex; flex-direction: column; }
.list-row {
  display: flex; align-items: baseline; gap: var(--s3);
  padding: 11px 0; border-bottom: 1px solid var(--hairline);
}
.list-row:last-child { border-bottom: 0; }
.list-row .main { display: block; font-size: 14px; font-weight: 500; }
.list-row .sub { display: block; font-size: 12.5px; color: var(--muted); margin-top: 2px; }
.list-row .value { margin-left: auto; font-size: 14px; font-weight: 600; font-variant-numeric: tabular-nums; }
.is-truncated { display: none; }
.show-all { margin-top: var(--s3); }

/* ---- Meters / share bars ------------------------------------------------ */
.meter-row { display: grid; grid-template-columns: 1fr 120px 46px; align-items: center; gap: var(--s3); padding: 7px 0; }
.meter-row .name { font-size: 13.5px; }
.meter-row .pct { font-size: 13px; color: var(--muted); text-align: right; font-variant-numeric: tabular-nums; }
.meter { height: 8px; border-radius: var(--r-chip); background: var(--hairline); overflow: hidden; }
.meter > i { display: block; height: 100%; border-radius: var(--r-chip); background: var(--series-1); }
.meter.warn > i { background: var(--warning-mark); }
.meter.crit > i { background: var(--critical-mark); }

.share-bar { display: flex; gap: 2px; height: 10px; margin: var(--s2) 0 var(--s4); }
.share-bar > span { display: block; height: 100%; }
.share-bar > span:first-child { border-radius: 4px 0 0 4px; }
.share-bar > span:last-child { border-radius: 0 4px 4px 0; }

/* ---- Ranked bar list (design-manual.md 6.27) ------------------------------ */
/* The analytics workhorse: a proportional accent-tinted bar BEHIND each
   label/value row. Magnitude is visible before a single number is read. */
.bar-list { display: flex; flex-direction: column; }
.bar-row { position: relative; display: flex; align-items: center; gap: var(--s3);
  min-height: 32px; padding: 0 var(--s2); }
.bar-row .fill { position: absolute; top: 3px; bottom: 3px; left: 0;
  border-radius: var(--r-small); background: var(--accent-soft); }
.bar-row .name, .bar-row .value { position: relative; min-width: 0; }
.bar-row .name { flex: 1 1 auto; font-size: 13.5px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-row .name .sub { font-size: var(--fs-meta); color: var(--muted); margin-left: var(--s2); }
.bar-row .value { font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; }

/* ---- Tracker strip (design-manual.md 6.28) -------------------------------- */
/* Status over time as contiguous blocks: anomalies pop as color breaks.
   Status tokens only; a slice with nothing to say stays hairline gray. */
.tracker { display: flex; gap: 1px; height: 10px; margin: var(--s2) 0; }
.tracker > span { flex: 1 1 0; background: var(--hairline); min-width: 2px; }
.tracker > span:first-child { border-radius: 4px 0 0 4px; }
.tracker > span:last-child { border-radius: 0 4px 4px 0; }
.tracker > .t-good { background: var(--good-mark); }
.tracker > .t-warn { background: var(--warning-mark); }
.tracker > .t-crit { background: var(--critical-mark); }
.tracker-meta { display: flex; justify-content: space-between; gap: var(--s3);
  font-size: var(--fs-meta); color: var(--muted); font-variant-numeric: tabular-nums; }

/* ---- Charts -------------------------------------------------------------- */
figure { margin: 0 0 var(--s4); }
figcaption { font-size: 12.5px; color: var(--muted); margin-top: var(--s2); }
.chart { display: block; width: 100%; overflow: visible; }
.chart .grid-line { stroke: var(--chart-grid); stroke-width: 1; }
.chart .axis { stroke: var(--chart-axis); stroke-width: 1; }
.chart .series { fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.chart .compare { fill: none; stroke: var(--chart-compare); stroke-width: 2; stroke-linecap: round; }
.chart .marker { stroke: var(--surface); stroke-width: 2; }
.chart .tick { font: 11.5px var(--font); fill: var(--muted); }
.legend { display: flex; gap: var(--s4); flex-wrap: wrap; font-size: 12.5px; color: var(--ink-2); margin-top: var(--s2); }
.legend .item { display: inline-flex; align-items: center; gap: 6px; }
.legend .swatch { width: 10px; height: 10px; border-radius: 3px; flex: none; }
.axis-label { font-size: 11.5px; color: var(--muted); }

/* ---- Body text ----------------------------------------------------------- */
h3 { font-size: var(--fs-h3); font-weight: 600; margin: var(--s7) 0 var(--s3); letter-spacing: -0.012em; }
h4 { font-size: var(--fs-h4); font-weight: 600; margin: var(--s6) 0 var(--s2); letter-spacing: -0.008em; }
h5 { font-size: var(--fs-sub); font-weight: 600; margin: var(--s5) 0 var(--s2); color: var(--ink-2); }
h6 {
  font-size: var(--fs-eyebrow); font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--muted); margin: var(--s5) 0 var(--s2);
}
.card > h3:first-child, .card > h4:first-child { margin-top: 0; }

/* Markdown stretches get visible group boundaries (design-manual.md, 3.3) */
.prose > h3 {
  display: flex; align-items: center; gap: var(--s3);
  padding-top: var(--s5); border-top: 1px solid var(--hairline);
}
.prose > h3::before {
  content: ""; flex: none; width: 3px; height: 18px; border-radius: 2px; background: var(--accent-line);
}
.prose > h4::before {
  content: ""; display: inline-block; width: 5px; height: 5px; border-radius: 50%;
  background: var(--faint); vertical-align: 3px; margin-right: var(--s2);
}
.prose > :first-child { margin-top: 0; }
.prose > h3:first-child { padding-top: 0; border-top: 0; }
.prose > table, .prose > .table-wrap { margin-bottom: var(--s5); }
p { margin: var(--s2) 0; }
ul, ol { margin: var(--s2) 0; padding-left: 22px; }
li { margin: 3px 0; }
a { color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 2px; }
strong { font-weight: 600; color: var(--ink); }
code {
  font: 12.5px var(--font-mono); background: var(--inset);
  border: 1px solid var(--hairline); border-radius: var(--r-small); padding: 1px 5px;
}
pre { background: var(--inset); border: 1px solid var(--hairline); border-radius: var(--r-input);
      padding: var(--s4); overflow: auto; font: 12.5px/1.55 var(--font-mono); color: var(--ink-2); }
/* A fenced block is <pre><code>: the inline chip styling must not repeat inside it. */
pre code { background: none; border: 0; padding: 0; font: inherit; color: inherit; }
blockquote { margin: var(--s3) 0; padding: 2px var(--s4); border-left: 3px solid var(--accent-line); color: var(--ink-2); }
hr { border: 0; border-top: 1px solid var(--hairline); margin: var(--s5) 0; }

/* ---- Tables -------------------------------------------------------------- */
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: var(--fs-label); }
th {
  text-align: left; font-size: var(--fs-eyebrow); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--muted); padding: 8px 14px 8px 0; border-bottom: 1px solid var(--hairline); white-space: nowrap;
}
td { padding: 9px 14px 9px 0; border-bottom: 1px solid var(--hairline); vertical-align: top;
     font-variant-numeric: tabular-nums; }
tbody tr:last-child td { border-bottom: 0; }
td.num, th.num { text-align: right; padding-right: 0; }
td.ctr, th.ctr { text-align: center; }
td.total, tr.total td { font-weight: 600; color: var(--ink); border-top: 2px solid var(--hairline); }
/* Table-first sections (6.9): a compact variant chosen at generation time
   (never a toggle), and a sticky tinted header band for a full-width table
   that fits without .table-wrap — sticky cannot work inside a scroll box. */
.table--dense th { padding-top: 5px; padding-bottom: 5px; }
.table--dense td { padding-top: 6px; padding-bottom: 6px; }
.table--sticky thead th { position: sticky; top: 52px; z-index: 2;
  background: var(--inset); box-shadow: 0 1px 0 var(--hairline); border-bottom: 0;
  padding-left: var(--s2); }
.table--sticky td { padding-left: var(--s2); }

/* ---- Collapsibles -------------------------------------------------------- */
details { border-top: 1px solid var(--hairline); }
details:first-of-type { border-top: 0; }
summary {
  cursor: pointer; padding: 13px 2px; font-weight: 550; list-style: none;
  display: flex; align-items: baseline; gap: var(--s2); flex-wrap: wrap;
}
summary::-webkit-details-marker { display: none; }
summary::before { content: "▸"; color: var(--faint); font-size: 12px; }
details[open] > summary::before { content: "▾"; }
summary .meta { color: var(--muted); margin-left: auto;
  font: 400 11.5px var(--font-mono); font-variant-numeric: tabular-nums; }
details .body { padding: 0 2px var(--s4) var(--s5); }

/* Dossier/entry row: collapsible, yet readable as a row (6.14) */
details.acc > summary {
  align-items: center; gap: var(--s3); padding: var(--s4) 2px; font-weight: 400; flex-wrap: nowrap;
}
details.acc > summary::before { display: none; }
.acc .acc-mark {
  flex: none; width: 30px; height: 30px; border-radius: var(--r-small); display: grid; place-items: center;
  background: var(--inset); color: var(--muted); border: 1px solid var(--border);
  font-size: 12px; font-weight: 600; font-variant-numeric: tabular-nums; line-height: 1;
}
.acc .acc-text { min-width: 0; flex: 1 1 auto; }
.acc .acc-title { display: block; font-size: var(--fs-h4); font-weight: 600; letter-spacing: -0.008em; line-height: 1.35; }
.acc .acc-title .badge, .acc .acc-title .tag { margin-left: var(--s2); vertical-align: middle; }
.acc .acc-sub { display: block; font-size: var(--fs-meta); color: var(--muted); margin-top: 2px; }
.acc > summary .tag, .acc > summary .badge { flex: none; }
.acc > summary .meta {
  flex: 0 1 auto; margin-left: var(--s3); text-align: right; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;
}
.acc > summary::after { content: "▾"; color: var(--muted); font-size: 14px; flex: none; margin-left: var(--s1); }
.acc[open] > summary::after { content: "▴"; color: var(--accent); }
@media (max-width: 620px) { .acc > summary .meta { display: none; } }
.acc[open] > summary .acc-title { color: var(--accent); }
.acc[open] > summary .acc-mark { background: var(--accent-soft); color: var(--accent); border-color: transparent; }
.acc .body { padding: var(--s1) 2px var(--s6) calc(30px + var(--s3)); }
@media (max-width: 620px) { .acc .body { padding-left: 2px; } }

/* ---- Notices & empty state ----------------------------------------------- */
.banner {
  border-radius: var(--r-input); padding: 12px 15px; font-size: 13.5px; margin-bottom: var(--s4);
  border: 1px solid var(--border); background: var(--inset); color: var(--ink-2);
}
.banner--ok   { background: var(--good-soft); border-color: transparent; }
.banner--warn { background: var(--warning-soft); border-color: transparent; }
.banner--crit { background: var(--critical-soft); border-color: transparent; }
.banner strong { color: var(--ink); }
.empty { color: var(--muted); font-size: 13.5px; font-style: italic; }

footer {
  margin-top: var(--s9); color: var(--muted); font-size: 12.5px;
  border-top: 1px solid var(--hairline); padding-top: var(--s4);
}

/* ---- Timeline (design-manual.md, 7.6) ------------------------------------ */
.tl-scroll { overflow-x: auto; overflow-y: hidden; padding-bottom: var(--s1); }
.tl-head { position: relative; }
.tl-head > span {
  position: absolute; top: 0; white-space: nowrap; padding-left: 5px;
  font-size: var(--fs-eyebrow); color: var(--muted); border-left: 1px solid var(--chart-grid);
}
.tl-years { height: 21px; }
.tl-years > span {
  font-weight: 600; letter-spacing: 0.07em; color: var(--ink-2);
  border-left-color: var(--chart-axis);
}
.tl-months { height: 18px; margin-bottom: var(--s2); }

.tl-body { position: relative; }
.tl-gl { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--chart-grid); }
.tl-gl--year { background: var(--chart-axis); }
.tl-now { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--faint); z-index: 1; }
.tl-foot { position: relative; height: 18px; margin-top: 6px; }
.tl-foot > span {
  position: absolute; top: 0; white-space: nowrap; padding-left: 5px;
  font-size: var(--fs-eyebrow); font-weight: 600; letter-spacing: 0.07em;
  text-transform: uppercase; color: var(--ink-2);
}
.tl-foot > span.is-right { transform: translateX(-100%); padding: 0 5px 0 0; }

.tl-lane + .tl-lane { margin-top: var(--s4); }
.tl-lane-head {
  position: relative; z-index: 2; display: flex; align-items: center; gap: 7px;
  background: var(--surface); padding-bottom: 6px;
  font-size: var(--fs-meta); font-weight: 600; color: var(--ink-2);
}
.tl-lane-head .sw { flex: none; width: 10px; height: 10px; border-radius: 3px; background: var(--c); }
.tl-lane-head .meta {
  margin-left: auto; padding-left: var(--s3); font-weight: 400; color: var(--muted);
  font-variant-numeric: tabular-nums;
}
.tl-rows { position: relative; }
.tl-row { position: relative; height: 28px; }
.tl-none {
  position: absolute; left: 0; top: 5px; white-space: nowrap; background: var(--surface);
  padding-right: var(--s2); font-size: var(--fs-meta); font-style: italic; color: var(--muted);
}

.tl-mark {
  position: absolute; padding: 0; border: 0; background: none; color: inherit; font: inherit;
  cursor: pointer;
}
.tl-mark:focus-visible { outline: 2px solid var(--accent-solid); outline-offset: 3px; }
.tl-mark .lb {
  position: absolute; white-space: nowrap; font-size: var(--fs-meta); line-height: 15px;
  color: var(--ink-2);
}
.tl-span { top: 16px; height: 10px; border-radius: 4px; background: var(--c); }
.tl-span .lb { left: 1px; top: -16px; }
.tl-span:hover { box-shadow: 0 0 0 3px color-mix(in srgb, var(--c) 26%, transparent); }
.tl-span--clip-l { border-top-left-radius: 0; border-bottom-left-radius: 0; }
.tl-span--clip-r { border-top-right-radius: 0; border-bottom-right-radius: 0; }
.tl-dot {
  top: 14px; width: 14px; height: 14px; margin-left: -7px; border-radius: 50%;
  background: var(--c); box-shadow: 0 0 0 2px var(--surface);
}
.tl-dot .lb { left: 19px; top: 0; }
.tl-dot:hover { box-shadow: 0 0 0 2px var(--surface), 0 0 0 5px color-mix(in srgb, var(--c) 26%, transparent); }
.tl-mark--soft.tl-span {
  background: color-mix(in srgb, var(--c) 30%, var(--surface));
  box-shadow: inset 0 0 0 1.5px var(--c);
}
.tl-mark--soft.tl-span:hover {
  box-shadow: inset 0 0 0 1.5px var(--c), 0 0 0 3px color-mix(in srgb, var(--c) 26%, transparent);
}
.tl-mark--soft.tl-dot { background: var(--surface); box-shadow: 0 0 0 2px var(--surface), inset 0 0 0 3.5px var(--c); }
.tl-mark--soft.tl-dot:hover {
  box-shadow: 0 0 0 2px var(--surface), inset 0 0 0 3.5px var(--c),
              0 0 0 5px color-mix(in srgb, var(--c) 26%, transparent);
}
.tl-mark--open.tl-span { background: var(--hairline); box-shadow: inset 0 0 0 1px var(--border); }
.tl-mark--open .lb { color: var(--muted); }
.tl-mark--deadline { --c: var(--critical-mark); }
.tl-mark--deadline .lb { color: var(--critical); font-weight: 600; }

.tl-key {
  display: flex; gap: var(--s4); flex-wrap: wrap; margin-top: var(--s4);
  font-size: var(--fs-meta); color: var(--muted);
}
.tl-key .item { display: inline-flex; align-items: center; gap: 6px; }
.tl-key .k-span { flex: none; width: 18px; height: 8px; border-radius: 3px; background: var(--muted); }
.tl-key .k-dot { flex: none; width: 11px; height: 11px; border-radius: 50%; background: var(--muted); }
.tl-key .k-soft { background: var(--surface); box-shadow: inset 0 0 0 2.5px var(--muted); }
.tl-key .k-open { background: var(--hairline); box-shadow: inset 0 0 0 1px var(--border); }
.tl-key .k-deadline { background: var(--critical-mark); }

/* ---- Detail modal (design-manual.md, 6.17) ------------------------------- */
/* The content blocks live hidden in the document; the dialog adopts a copy. */
[data-ev-detail] { display: none; }
dialog.modal {
  border: 0; padding: 0; background: transparent; color: var(--ink);
  width: 100%; max-width: min(560px, calc(100vw - 32px));
}
dialog.modal::backdrop { background: rgba(12, 12, 15, 0.55); }
.modal-card {
  display: flex; flex-direction: column; max-height: 84vh; overflow: hidden;
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-card);
  box-shadow: var(--shadow-lift);
}
.modal-slot { display: flex; flex-direction: column; min-height: 0; }
.modal-head { padding: var(--s5) var(--s6) var(--s4); border-bottom: 1px solid var(--hairline); }
.modal-head .eyebrow { margin-bottom: var(--s2); }
.modal-head h3 { font-size: var(--fs-h3); font-weight: 600; letter-spacing: -0.012em; margin: 0; }
.modal-when { font-size: var(--fs-meta); color: var(--muted); margin-top: var(--s1); font-variant-numeric: tabular-nums; }
.modal-head .row { margin-top: var(--s3); }
.modal-body { padding: var(--s5) var(--s6); overflow-y: auto; font-size: var(--fs-sub); }
.modal-src { margin-top: var(--s4); padding-top: var(--s3); border-top: 1px solid var(--hairline);
             font-size: var(--fs-meta); color: var(--muted); }
.modal-foot {
  display: flex; align-items: center; gap: var(--s2); flex-wrap: wrap;
  padding: var(--s3) var(--s6) var(--s4); border-top: 1px solid var(--hairline);
}
.btn-link {
  background: none; border: 0; padding: 0; font: inherit; color: var(--accent); cursor: pointer;
  text-align: left; text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 2px;
}
.btn-link:hover { color: var(--ink); }

/* ---- Reduced motion, print, small screens -------------------------------- */
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
@media (max-width: 820px) {
  :root { --fs-hero: 32px; --fs-h2: 23px; --fs-focus: 48px; }
  .focus { grid-template-columns: 1fr; gap: var(--s5); }
}
@media (max-width: 620px) {
  :root { --fs-hero: 28px; --fs-h2: 21px; --fs-h3: 17px; --fs-focus: 44px; --fs-value: 28px; }
  .wrap { padding: 0 var(--s4) var(--s9); }
  header.hero { padding-top: var(--s7); }
  .card { padding: var(--s4) var(--s4); }
  .focus { padding: var(--s6) var(--s4) var(--s5); }
  .meter-row { grid-template-columns: 1fr 80px 40px; }
}
@media print {
  body { background: #fff; }
  nav.toc, .btn, .filters, .show-all, .pagebar a { display: none; }
  .card, .tile { box-shadow: none; break-inside: avoid; }
  details { open: true; }
  /* Printed, a list shows everything — view state is not document state. */
  .is-filtered-out, .is-truncated { display: revert !important; }
}
"""

# -------------------------------------------------- form & app chrome css ----
# design-manual.md 6b: deliberately NOT part of BASE_CSS. An interactive page
# opts in through EXTRA_CSS; a dashboard that never asks a question never
# carries a byte of it. Tokens only, like everything else.

FORM_CSS = """
/* ---- Option row (6.19) --------------------------------------------------- */
.opt {
  display: flex; align-items: flex-start; gap: var(--s3); width: 100%; text-align: left;
  font: inherit; color: var(--ink); cursor: pointer; margin-bottom: var(--s2);
  background: var(--raised); border: 1px solid var(--border); border-radius: var(--r-input);
  padding: var(--s3) var(--s4); box-shadow: var(--shadow);
}
.opt:hover { border-color: var(--accent-line); background: var(--inset); }
.opt:focus-visible { outline: 2px solid var(--accent-solid); outline-offset: 2px; }
.opt[aria-pressed="true"] { border-color: var(--accent-solid); background: var(--accent-soft); }
.opt[aria-pressed="true"] .opt-label { color: var(--accent); font-weight: 600; }
.opt-key {
  flex: none; display: inline-grid; place-items: center; width: 22px; height: 22px;
  border-radius: var(--r-small); background: var(--inset); color: var(--muted);
  border: 1px solid var(--border); font-size: var(--fs-eyebrow); font-weight: 600;
  font-variant-numeric: tabular-nums; line-height: 1; margin-top: 1px;
}
.opt[aria-pressed="true"] .opt-key {
  background: var(--accent-solid); color: var(--on-accent); border-color: transparent;
}
.opt-text { min-width: 0; flex: 1 1 auto; }
.opt-label { display: block; font-size: var(--fs-h4); font-weight: 500; line-height: 1.35; }
.opt-hint { display: block; font-size: var(--fs-meta); color: var(--muted); margin-top: 2px; }
/* The check is the second, non-color carrier of the pressed state (2.3). */
.opt-tick { flex: none; margin-left: auto; color: var(--accent); visibility: hidden; }
.opt[aria-pressed="true"] .opt-tick { visibility: visible; }

/* ---- Field (6.20) -------------------------------------------------------- */
.field { margin-bottom: var(--s4); }
.field > label { display: block; font-size: var(--fs-h4); font-weight: 600; margin-bottom: var(--s1); }
.field .hint { display: block; font-size: var(--fs-meta); color: var(--muted); margin-bottom: var(--s2); }
.field input[type="text"], .field textarea {
  display: block; width: 100%; font: inherit; font-size: var(--fs-body); color: var(--ink);
  background: var(--raised); border: 1px solid var(--border); border-radius: var(--r-input);
  padding: 10px var(--s3); box-shadow: var(--shadow);
}
.field textarea { min-height: 76px; resize: vertical; line-height: 1.5; }
.field input[type="text"]:focus-visible, .field textarea:focus-visible {
  outline: 2px solid var(--accent-solid); outline-offset: 1px; border-color: var(--accent-solid);
}
.field input::placeholder, .field textarea::placeholder { color: var(--faint); }
/* Amount: the unit is a static suffix, never part of the value (6.20). */
.field .amount { display: flex; align-items: center; gap: var(--s2); }
.field .amount input[type="text"] { flex: 1 1 auto; font-variant-numeric: tabular-nums; }
.field .unit { flex: none; font-size: var(--fs-h4); font-weight: 500; color: var(--muted); }

/* ---- Note disclosure (6.21) ---------------------------------------------- */
.note-open { margin-top: var(--s2); }
.note-wrap[hidden] { display: none; }
.note-wrap { margin-top: var(--s3); }

/* ---- Summary row (6.25) -------------------------------------------------- */
.sumrow {
  display: flex; align-items: baseline; gap: var(--s3); width: 100%; text-align: left;
  font: inherit; color: var(--ink); cursor: pointer; background: none; border: 0;
  padding: 11px 2px; border-bottom: 1px solid var(--hairline);
}
.sumrow:last-of-type { border-bottom: 0; }
.sumrow:hover .sumrow-q { color: var(--accent); }
.sumrow:focus-visible { outline: 2px solid var(--accent-solid); outline-offset: -2px; }
.sumrow .num {
  flex: none; font-size: var(--fs-meta); color: var(--muted); font-variant-numeric: tabular-nums;
}
.sumrow-text { min-width: 0; flex: 1 1 auto; }
.sumrow-q { display: block; font-size: var(--fs-label); font-weight: 500; }
.sumrow-a { display: block; font-size: var(--fs-meta); color: var(--ink-2); margin-top: 2px; }
.sumrow-note { display: block; font-size: var(--fs-meta); color: var(--muted); margin-top: 2px; font-style: italic; }
.sumrow-a:empty, .sumrow-note:empty { display: none; }
.sumrow .badge { flex: none; margin-left: auto; }

/* ---- Check row (6.26) ---------------------------------------------------- */
.ck-row {
  display: flex; align-items: flex-start; gap: var(--s3);
  padding: 11px 0; border-bottom: 1px solid var(--hairline);
}
.ck-row:last-child { border-bottom: 0; }
/* The tick is the only control that changes state; the rest of the row stays
   selectable text, so an instruction can be copied without toggling it. */
.ck-tick {
  flex: none; display: inline-grid; place-items: center; width: 24px; height: 24px;
  margin-top: 1px; cursor: pointer; font: inherit;
  border: 1px solid var(--border); border-radius: var(--r-small);
  background: var(--raised); color: transparent; box-shadow: var(--shadow);
}
.ck-tick:hover { border-color: var(--accent-line); background: var(--inset); }
.ck-tick:focus-visible { outline: 2px solid var(--accent-solid); outline-offset: 2px; }
/* Second, non-color carrier of the pressed state: the glyph appears (2.3). */
.ck-tick[aria-pressed="true"] {
  background: var(--accent-solid); border-color: var(--accent-solid); color: var(--on-accent);
}
.ck-tick:disabled { cursor: not-allowed; opacity: .45; box-shadow: none; }
.ck-body { min-width: 0; flex: 1 1 auto; max-width: 68ch; }
.ck-text { display: block; font-size: var(--fs-h4); font-weight: 500; line-height: 1.4; }
/* Attention inversion (6.26): the states still asking for work carry the
   tag; done and n/a sit quiet — color and marks point at what is pending. */
.ck-row[data-state="done"] .ck-text { color: var(--ink-2); }
.ck-row[data-state="na"] .ck-text { color: var(--muted); }
.ck-row[data-state="na"] .ck-tick { opacity: .45; }
.ck-row[data-state="deferred"] .ck-state { background: var(--warning-soft);
  color: var(--warning); border-color: transparent; }
.ck-row[data-state="obsolete"] .ck-text { color: var(--muted); text-decoration: line-through; }
.ck-row .ck-state { flex: none; margin-left: auto; align-self: flex-start; margin-top: 4px; }
.ck-context {
  display: flex; align-items: center; gap: var(--s3); flex-wrap: wrap; margin-top: var(--s2);
}
.ck-detail { font-size: var(--fs-sub); color: var(--ink-2); margin-top: var(--s2); }
.ck-detail > :first-child { margin-top: 0; }
.ck-detail > :last-child { margin-bottom: 0; }
.ck-row .note-open { font-size: var(--fs-meta); padding: 5px 9px; }
.ck-row .note-wrap { margin-top: var(--s2); }
.ck-row .note-wrap .field { margin-bottom: 0; }
"""

APP_CSS = """
/* An interactive page hides and shows what is already in the document, so
   `hidden` has to beat every layout rule here — a component that sets its own
   `display` would otherwise silently ignore it. */
[hidden] { display: none !important; }

/* ---- Screens (11.2): every screen is in the document, one is visible ------ */
.screen[hidden] { display: none; }
.screen { margin-top: var(--s6); }
/* Focus moves to the new screen's heading on every change (11.5). Plain
   :focus, not :focus-visible — the move is programmatic, and the manual asks
   for a visible landing point rather than a suppressed one. */
.screen h1[tabindex]:focus, .screen h2[tabindex]:focus {
  outline: 2px solid var(--accent-solid); outline-offset: 6px;
  border-radius: var(--r-small);
}

/* ---- Progress bar (6.22) — the sticky slot nav.toc holds elsewhere -------- */
.progress {
  position: sticky; top: 0; z-index: 5; padding: var(--s3) 0 var(--s2);
  background: color-mix(in srgb, var(--plane) 90%, transparent);
  backdrop-filter: blur(10px); border-bottom: 1px solid var(--hairline);
}
.progress-meta {
  display: flex; align-items: baseline; gap: var(--s3);
  font-size: var(--fs-meta); color: var(--muted); margin-bottom: 6px;
}
.progress-meta .right { margin-left: auto; font-variant-numeric: tabular-nums; }
.progress .meter { height: 8px; border-radius: var(--r-chip); background: var(--hairline); overflow: hidden; }
.progress .meter > i {
  display: block; height: 100%; border-radius: var(--r-chip); background: var(--accent-solid);
  transition: width .18s ease;
}

/* ---- Action bar (6.23) --------------------------------------------------- */
.actionbar {
  position: fixed; left: 0; right: 0; bottom: 0; z-index: 6;
  display: flex; align-items: center; gap: var(--s2); flex-wrap: wrap;
  padding: var(--s3) var(--s6); border-top: 1px solid var(--hairline);
  background: color-mix(in srgb, var(--plane) 92%, transparent); backdrop-filter: blur(10px);
}
.actionbar .spacer { flex: 1 1 auto; }
/* The bar is fixed, so the column reserves its height — it covers nothing,
   ever (6.23). Sized for the bar wrapped onto two rows, which is what a
   narrow screen with long labels produces; the spare whitespace below a
   one-row bar is the cheaper of the two mistakes. */
.has-actionbar { padding-bottom: calc(var(--s10) + var(--s8)); }

/* ---- Toast (6.24) -------------------------------------------------------- */
.toast {
  position: fixed; left: 50%; bottom: var(--s9); transform: translateX(-50%);
  z-index: 7; max-width: calc(100vw - 32px);
  padding: 10px var(--s4); border-radius: var(--r-input);
  background: var(--ink); color: var(--plane); font-size: var(--fs-label); font-weight: 500;
  box-shadow: var(--shadow-lift); opacity: 0; visibility: hidden; transition: opacity .16s ease;
}
.toast.is-on { opacity: 1; visibility: visible; }

/* ---- Hand-back block (part 4 of the plugin contract) --------------------- */
.handback {
  white-space: pre-wrap; word-break: break-word; max-height: 340px; overflow: auto;
  user-select: all;
}

/* ---- Print: the content, never the chrome (6b) --------------------------- */
/* BASE_CSS already drops nav.toc and .btn. These three are the positioned
   components, and on paper they are worse than useless: the action bar would
   cover the last lines, the progress bar would print a frozen ratio, and the
   toast is a message about something that already happened. */
@media print {
  .progress, .actionbar, .toast { display: none; }
  .has-actionbar { padding-bottom: 0; }
  .handback { max-height: none; overflow: visible; }
}
"""

# ------------------------------------------------------------- article css ----
# design-manual.md 11b: the long-form flavour. A dashboard packs facts into a
# scannable grid; an article asks to be read from top to bottom, so the column
# narrows, the type turns serif and the vertical rhythm opens up. Two voices
# (11b.1): the text reads in the OS's book face (--font-serif), everything
# around it — masthead, meta, captions, asides, sources — stays the sans
# apparatus. Opt-in like FORM_CSS/APP_CSS — a page that shows numbers carries
# none of it.

ARTICLE_CSS = """
/* The reading page: warm plane, wide shell for the three width tiers (11b.6).
   Prose is capped per child, so wide tables, code and full-bleed figures can
   escape the measure without a second column system. */
body:has(.article) { background: var(--plane-read); }
.wrap--read { max-width: 1160px; }

/* ---- Masthead ------------------------------------------------------------ */
.article-head { padding: var(--s9) 0 var(--s6); max-width: var(--measure-read); margin: 0 auto; }
.article-head h1 {
  font-size: clamp(1.9rem, 1.2rem + 3vw, 3.2rem); font-weight: 650;
  letter-spacing: -0.03em;
  line-height: 1.06; margin: 0 0 var(--s4); color: var(--ink); text-wrap: balance;
}
.article-head .lede {
  font-size: var(--fs-lede); line-height: 1.5; color: var(--ink-2);
  margin: 0 0 var(--s5); max-width: 48ch;
}
/* Tracked caps, never font-variant small caps — system fonts fake those (3.3). */
.article-head .meta {
  display: flex; align-items: center; gap: var(--s3); flex-wrap: wrap;
  padding-top: var(--s4); border-top: 1px solid var(--hairline);
  font-size: var(--fs-eyebrow); font-weight: 500; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--muted);
  font-variant-numeric: tabular-nums;
}
.article-head .meta .sep { color: var(--faint); }

/* ---- Mini-TOC (11b.7) — for documents with four or more sections --------- */
.mini-toc { border-top: 1px solid var(--hairline); border-bottom: 1px solid var(--hairline);
  font-family: var(--font); font-size: var(--fs-sub); padding: var(--s2) 0;
  max-width: var(--measure-read); margin: 0 auto var(--s6); }
.mini-toc > summary { padding: var(--s2) 2px; font-weight: 500;
  font-size: var(--fs-eyebrow); letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--muted); }
.mini-toc ol { margin: var(--s2) 0 var(--s3); padding-left: 24px; color: var(--ink-2); }
.mini-toc li { margin: 4px 0; }
.mini-toc a { color: var(--accent); text-decoration: none; }
.mini-toc a:hover { text-decoration: underline; }

/* ---- The reading column (11b.1) ------------------------------------------ */
.article { font-family: var(--font-serif); font-size: var(--fs-read);
  line-height: 1.55; color: var(--ink-2); }
/* Width tiers (11b.6): prose at the measure, tables and code one tier wider,
   full-bleed by opt-in. Margins stay block-only so the caps keep centering. */
.article > * { max-width: var(--measure-read); margin-left: auto; margin-right: auto; }
.article > .table-wrap, .article > pre { max-width: min(var(--measure-wide), 100%); }
.article > .full-bleed, .article > figure.full-bleed { max-width: none; }
.article p { margin-block: var(--s5); }
.article h2 {
  font-family: var(--font); font-size: clamp(1.45rem, 1.15rem + 1.1vw, 1.7rem);
  font-weight: 600; letter-spacing: -0.022em; line-height: 1.2;
  color: var(--ink); margin-block: var(--s9) var(--s4);
}
.article h3 {
  font-family: var(--font); font-size: var(--fs-h3); font-weight: 600;
  color: var(--ink); margin-block: var(--s7) var(--s3);
}
.article h4 { font-family: var(--font); font-size: var(--fs-h4); font-weight: 600;
  color: var(--ink); margin-block: var(--s6) var(--s2); }
.article > :first-child { margin-top: 0; }
.article ul, .article ol { margin-block: var(--s5); padding-left: 26px; }
.article li { margin-block: var(--s2); }
.article li > ul, .article li > ol { margin-block: var(--s2); }
.article strong { color: var(--ink); }
/* In a reading column the inline chip has to sit inside the line, not push it
   apart — the border and the larger type around it already separate it. */
.article code { font-size: var(--fs-label); padding: 0 4px; }
.article pre { margin-block: var(--s6); padding: var(--s5); font-size: var(--fs-label); }
.article pre code { font-size: inherit; }
.article blockquote {
  margin-block: var(--s6); margin-inline: auto; padding: var(--s1) 0 var(--s1) var(--s5);
  border-left: 3px solid var(--accent-line); color: var(--ink-2);
  hanging-punctuation: first;
}
.article blockquote p { margin-block: var(--s2); }
.article table { font-size: var(--fs-body); font-family: var(--font); }
.article .table-wrap { margin-block: var(--s6); }
.article figure { margin-block: var(--s6); }
.article figcaption { font-family: var(--font); }
.article img { max-width: 100%; height: auto; }

/* Book paragraphing (11b.1): the renderer picks ONE mode per document —
   indents for prose-led pieces, spacing for list- and code-heavy ones.
   Indents or spacing, never both. */
.article--indent p { margin-block: 0; }
.article--indent p + p { text-indent: 1.5em; }
.article--indent p:last-child { margin-bottom: var(--s5); }

/* Dinkus (11b.7): the markdown `---` as the rhythm register between
   paragraph and section — a thought break, not a rule. */
.article hr { border: 0; margin-block: var(--s8); text-align: center; }
.article hr::before { content: "\\00B7 \\00B7 \\00B7"; letter-spacing: 0.8em;
  margin-left: 0.8em; color: var(--muted); font-size: var(--fs-read); }

/* Epigraph (11b.7): a blockquote that opens the document — italic, quiet,
   borderless, with air. A second paragraph is read as the attribution. */
.article > blockquote:first-child {
  border-left: 0; padding: 0; margin-block: var(--s7) var(--s10);
  font-style: italic; hanging-punctuation: first;
}
.article > blockquote:first-child > p:last-child:not(:only-child) {
  font-style: normal; text-align: right; font-size: 0.85em;
  font-family: var(--font); color: var(--muted);
}

/* A drop cap only where an article really opens with prose — never mid-page,
   and never on a page that starts with a heading or a list. */
.article > p:first-child::first-letter {
  float: left; font-size: 3.3em; line-height: 0.86; font-weight: 650;
  color: var(--accent); padding: 4px var(--s2) 0 0;
}

/* ---- Asides (11b.5): footnotes as margin notes --------------------------- */
/* Block-level, placed right after the paragraph that references them; open by
   default so the note reads without interaction. At reading width they float
   into the right rail; below it they are an indented disclosure. */
sup.fn-ref { font-family: var(--font); font-size: 0.72em; line-height: 0; }
sup.fn-ref a, .src-ref a { color: var(--accent); text-decoration: none; font-weight: 600; }
sup.src-ref { font-family: var(--font); font-size: 0.72em; line-height: 0; }
.endnotes { font-family: var(--font); font-size: 0.85em; color: var(--ink-2); }
details.aside { border: 0; font-family: var(--font); font-size: 0.82em;
  line-height: 1.5; color: var(--ink-2); margin-block: var(--s3) var(--s5); }
details.aside > summary { padding: 0 2px; font-weight: 600; color: var(--accent);
  font-size: var(--fs-eyebrow); font-variant-numeric: tabular-nums; }
details.aside > summary::before { content: none; }
details.aside .body { padding: var(--s1) 2px var(--s2) var(--s4); }
@media (min-width: 1210px) {
  details.aside { float: right; clear: right; width: 230px;
    margin: 0 0 var(--s4) var(--s5); }
  details.aside .body { padding: var(--s1) 0 0; }
  .article figure { position: relative; }
  .article figcaption { position: absolute; left: 100%; top: 0; width: 230px;
    margin-left: var(--s6); }
}

/* ---- Pull quote ---------------------------------------------------------- */
.pull {
  margin-block: var(--s8); padding: 0; border: 0;
  font-size: var(--fs-lede); line-height: 1.42; font-weight: 500;
  color: var(--ink); letter-spacing: -0.012em;
}
.pull::before {
  content: ""; display: block; width: 48px; height: 3px; border-radius: 2px;
  background: var(--accent-line); margin-bottom: var(--s4);
}
.pull cite { display: block; margin-top: var(--s3); font: inherit;
  font-size: var(--fs-meta); font-style: normal; color: var(--muted); }

/* ---- Foot: end matter (11b.4 / 11b.7) ------------------------------------ */
.article-foot {
  margin-top: var(--s9); padding-top: var(--s5); border-top: 1px solid var(--hairline);
  font-family: var(--font); font-size: var(--fs-meta); color: var(--muted);
  max-width: var(--measure-read); margin-left: auto; margin-right: auto;
}
.article-foot h2 {
  font-size: var(--fs-eyebrow); font-weight: 600; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--muted); margin: 0 0 var(--s3);
}
.article-foot ol { margin: 0; padding-left: 22px; }
.article-foot li { margin: 4px 0; word-break: break-word; }
.article-foot .backref { color: var(--accent); text-decoration: none; margin-left: 5px; }
/* The colophon: one line saying what this file is — the offline, single-file
   promise stated as a fact, in the instrument voice. */
.colophon { margin-top: var(--s6); color: var(--muted);
  font: 400 11.5px var(--font-mono); letter-spacing: 0.02em;
  font-variant-numeric: tabular-nums; }

/* ---- Print (11b.8): a single file's natural second life is Cmd+P --------- */
@page { margin: 2cm; }
@media print {
  .article-head { padding-top: 0; }
  .article { font-size: var(--fs-body); widows: 3; orphans: 3; }
  .article figure, .article .table-wrap, .article pre, .article blockquote {
    break-inside: avoid;
  }
  .article > .full-bleed, .article > figure.full-bleed { max-width: 100%; }
  details.aside { float: none; width: auto; margin: var(--s3) 0 var(--s5); }
  .mini-toc { display: none; }
}
"""

# ------------------------------------------------------------ helpers -------

SERIES_COUNT = 6


def esc(s) -> str:
    return _html.escape(str(s), quote=True)


def fmt_eur(value: float, decimals: int = 2) -> str:
    """1234.5 -> '1.234,50 €' (German notation in body text)."""
    return f"{fmt_num(value, decimals)} \u20ac"


def fmt_num(value: float, decimals: int = 0) -> str:
    """1234.5 -> '1.234,5' — dot as thousands separator, comma as decimal mark."""
    s = f"{value:,.{decimals}f}"
    return s.replace(",", "\u0001").replace(".", ",").replace("\u0001", ".")


def de_date(value: str) -> str:
    """Germanize an ISO date from frontmatter for display: 2026-07-26 -> 26.07.2026."""
    v = str(value).strip()
    if len(v) == 10 and v[4] == "-" and v[7] == "-":
        y, m, d = v.split("-")
        if y.isdigit() and m.isdigit() and d.isdigit():
            return f"{d}.{m}.{y}"
    return v


def badge(text: str, kind: str = "neutral", icon: str = "") -> str:
    """kind: neutral | good | warn | crit | accent — never color alone, icon+text."""
    cls = "" if kind == "neutral" else f" badge--{kind}"
    ic = f"{esc(icon)} " if icon else ""
    return f"<span class='badge{cls}'>{ic}{esc(text)}</span>"


def crumbs(path, note: str = "", label: str | None = None) -> str:
    """Navigation path inside a foreign interface (design-manual.md, 6.3b).

    `path` is a list of levels or a `›`-separated string; the last level is
    the target and gets highlighted. `note` names the verification status.
    """
    if label is None:
        label = STRINGS["crumbs_label"]
    parts = _re.split(r"[›>]", path) if isinstance(path, str) else list(path)
    parts = [p for p in (str(p).strip() for p in parts) if p]
    if not parts:
        return ""
    sep = "<span class='sep' aria-hidden='true'>›</span>"
    steps = []
    for i, p in enumerate(parts):
        cls = "c c--target" if i == len(parts) - 1 else "c"
        steps.append(f"<span class='{cls}'>{esc(p)}</span>")
    tail = f"<span class='tag'>{esc(note)}</span>" if note else ""
    return (f"<div class='crumbs'><span class='k'>{esc(label)}</span>"
            + sep.join(steps) + tail + "</div>")


def delta(text: str, direction: str = "up") -> str:
    """direction: up | down — the arrow carries the direction, not just the color."""
    arrow = "↑" if direction == "up" else "↓"
    return f"<span class='delta {esc(direction)}'>{arrow} {esc(text)}</span>"


def tile(label: str, value: str, sub: str = "", chip: str = "", icon: str = "",
         spark: str = "", trend: str = "", capacity=None) -> str:
    """Metric tile: label · value · optionally icon, badge/delta, sparkline,
    footnote — plus two variants (design-manual.md, 6.1):

    ``trend`` is one plain-language sentence of interpretation, written by the
    generator ("Trending up this month") — the tile explains itself instead of
    only measuring. ``capacity`` is ``(pct, caption)`` for a used-of-available
    reading ("1.85 of 10 GB"): the caption above a thin meter. A delta pair in
    ``chip`` (two ``delta()`` calls joined) makes the dual-delta variant.
    """
    head = (
        "<div class='tile-head'>"
        + (f"<span class='icon-badge'>{_maybe_html(icon)}</span>" if icon else "")
        + f"<div class='label'>{esc(label)}</div>"
        + (chip or "")
        + "</div>"
    )
    cap = ""
    if capacity:
        pct, caption = capacity
        cap = (f"<div class='capacity'><div class='cap-note'>{esc(caption)}</div>"
               f"<span class='meter'><i style='width:{max(0, min(100, pct)):.1f}%'></i>"
               "</span></div>")
    return (
        "<div class='tile'>"
        + head
        + f"<div class='value'>{esc(value)}</div>"
        + (f"<div class='spark'>{spark}</div>" if spark else "")
        + cap
        + (f"<div class='sub'>{esc(sub)}</div>" if sub else "")
        + (f"<div class='trend'>{esc(trend)}</div>" if trend else "")
        + "</div>"
    )


def tile_group(stats, label: str = "") -> str:
    """Grouped-triplet tile (6.1): up to three stats that only mean something
    together, in ONE tile — hairlines between them, no second box level.

    ``stats`` is a sequence of ``(label, value)`` or ``(label, value, sub)``.
    """
    cells = []
    for stat in stats:
        name, value, sub = (stat + ("",))[:3] if len(stat) < 3 else stat[:3]
        cells.append(f"<div><div class='label'>{esc(name)}</div>"
                     f"<div class='value'>{esc(value)}</div>"
                     + (f"<div class='sub'>{esc(sub)}</div>" if sub else "")
                     + "</div>")
    head = f"<div class='tile-head'><div class='label'>{esc(label)}</div></div>" if label else ""
    return f"<div class='tile'>{head}<div class='tile-trio'>{''.join(cells)}</div></div>"


def metric_hero(metrics, chart: str, active: int = 0, sub: str = "",
                foot_left: str = "", foot_right: str = "") -> str:
    """Metric-tab hero (design-manual.md, 5.2b): one hero chart card whose
    header row IS the KPI strip — one metric marked active and plotted below.

    ``metrics``: sequence of ``(label, value)`` or ``(label, value, sub)``;
    ``chart`` is the finished chart markup for the active metric. Static by
    design — the underline says what is plotted, nothing switches.
    """
    tabs = []
    for i, m in enumerate(metrics):
        name, value, note = (tuple(m) + ("",))[:3]
        cls = " is-active" if i == active else ""
        tabs.append(f"<div class='mt{cls}'><div class='label'>{esc(name)}</div>"
                    f"<div class='value'>{esc(value)}</div>"
                    + (f"<div class='sub'>{esc(note)}</div>" if note else "")
                    + "</div>")
    body = f"<div class='metric-tabs'>{''.join(tabs)}</div>{chart}"
    return card(body, sub=sub, foot_left=foot_left, foot_right=foot_right)


def bar_list(rows, unit: str = "", fmt=None) -> str:
    """Ranked bar-list breakdown (design-manual.md, 6.27): each row carries a
    proportional accent-tinted bar behind label and right-aligned value, so
    magnitude is visible before a single number is read.

    ``rows``: sequence of ``(label, value)`` or ``(label, value, sub)`` with
    numeric values, largest-first by convention (the helper does not sort —
    order is the author's statement). ``fmt`` formats the shown value
    (default ``fmt_num``); ``unit`` is appended to it. Bars never drop below
    2 % so every row stays visibly a bar.
    """
    rows = list(rows)
    if not rows:
        return ""
    top = max(float(r[1]) for r in rows) or 1.0
    fmt = fmt or (lambda v: fmt_num(v, 0))
    out = []
    for r in rows:
        label, value, sub = (tuple(r) + ("",))[:3]
        width = max(2.0, float(value) / top * 100)
        shown = f"{fmt(value)}{(' ' + unit) if unit else ''}"
        s = f"<span class='sub'>{esc(sub)}</span>" if sub else ""
        out.append(f"<div class='bar-row'>"
                   f"<span class='fill' style='width:{width:.1f}%'></span>"
                   f"<span class='name'>{esc(label)}{s}</span>"
                   f"<span class='value'>{esc(shown)}</span></div>")
    return f"<div class='bar-list'>{''.join(out)}</div>"


def tracker(slices, left: str = "", right: str = "") -> str:
    """Tracker strip (design-manual.md, 6.28): status over time as one row of
    contiguous blocks — anomalies pop as color breaks.

    ``slices``: sequence of states (``good`` · ``warn`` · ``crit`` · ``''``
    for nothing-to-say) or ``(state, title)`` pairs — the title names the
    slice for hover and assistive tech. 60–90 slices read best; status colors
    only, neutral slices stay hairline gray. ``left``/``right`` label the
    strip's time span underneath.
    """
    blocks = []
    for s in slices:
        state, title = (s, "") if isinstance(s, str) else (tuple(s) + ("",))[:2]
        cls = f" class='t-{esc(state)}'" if state else ""
        t = f" title='{esc(title)}'" if title else ""
        blocks.append(f"<span{cls}{t}></span>")
    meta = ""
    if left or right:
        meta = (f"<div class='tracker-meta'><span>{esc(left)}</span>"
                f"<span>{esc(right)}</span></div>")
    return f"<div class='tracker'>{''.join(blocks)}</div>{meta}"


# Inline SVG icons: monochrome, `currentColor`, no icon font, no external set (6.13).
_ICONS = {
    "check": '<path d="M3 8.4l3.2 3.2L13 4.9"/>',
    "doc": '<path d="M9.1 2.4H5c-.7 0-1.3.6-1.3 1.3v8.6c0 .7.6 1.3 1.3 1.3h6.1c.7 0 1.3-.6 1.3-1.3V5.6z"/>'
           '<path d="M9.1 2.4v3.2h3.3"/>',
    "folder": '<path d="M2.2 4.7c0-.6.5-1.1 1.1-1.1h2.6l1.5 1.8h5.3c.6 0 1.1.5 1.1 1.1v5.2c0 .6-.5 1.1-1.1 1.1'
              'H3.3c-.6 0-1.1-.5-1.1-1.1z"/>',
    "chat": '<path d="M13.4 9.1c0 .7-.6 1.3-1.3 1.3H6.2l-3 2.4V4.2c0-.7.6-1.3 1.3-1.3h7.6c.7 0 1.3.6 1.3 1.3z"/>',
    "user": '<circle cx="8" cy="5.5" r="2.4"/><path d="M3.3 13.2c.5-2.2 2.3-3.5 4.7-3.5s4.2 1.3 4.7 3.5"/>',
    "lock": '<rect x="3.4" y="7" width="9.2" height="6.2" rx="1.4"/><path d="M5.8 7V5.5a2.2 2.2 0 0 1 4.4 0V7"/>',
    "clock": '<circle cx="8" cy="8" r="5.5"/><path d="M8 4.9V8l2.2 1.5"/>',
    "flag": '<path d="M4 13.4V3.1"/><path d="M4 3.6h6.8l-1.3 2.3 1.3 2.3H4"/>',
    # Kind glyphs — the index page's entire heterogeneity signal (per kind).
    "chart": '<path d="M3 13.2h10.4"/><path d="M4.6 10.6l2.6-2.9 2.2 1.7 3-3.8"/>',
    "list": '<rect x="2.8" y="2.8" width="4" height="4" rx="1"/><path d="M4 4.8l.9.9 1.5-1.8"/>'
            '<path d="M9 4.8h4.2"/><rect x="2.8" y="9.2" width="4" height="4" rx="1"/>'
            '<path d="M9 11.2h4.2"/>',
    "question": '<path d="M13.4 9.1c0 .7-.6 1.3-1.3 1.3H6.2l-3 2.4V4.2c0-.7.6-1.3 1.3-1.3'
                'h7.6c.7 0 1.3.6 1.3 1.3z"/><path d="M6.6 5.9c.2-.7.8-1.1 1.5-1.1.9 0 '
                '1.5.5 1.5 1.2 0 1-1.4 1.1-1.4 2"/><path d="M8.2 9.6v.1"/>',
}


def icon(name: str, size: int = 16) -> str:
    """Monochrome inline SVG. Meaning always rides on the text next to it, never on the icon alone."""
    body = _ICONS.get(name, "")
    return (
        f"<svg viewBox='0 0 16 16' width='{size}' height='{size}' fill='none' stroke='currentColor'"
        f" stroke-width='1.75' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>{body}</svg>"
    )


def _maybe_html(value: str) -> str:
    """Pass finished markup (e.g. `icon()`) through unchanged, escape everything else."""
    return value if value.lstrip().startswith("<") else esc(value)


def eyebrow(text: str, num: str = "") -> str:
    """Overline above a title — optionally with a numbered accent mark."""
    n = f"<span class='num'>{esc(num)}</span>" if num else ""
    return f"<div class='eyebrow'>{n}{esc(text)}</div>"


def section_head(title: str, sub: str = "", num: str = "", kicker: str = "",
                 right: str = "", count=None) -> str:
    """Section head (level 2): overline with number · large title · subline ·
    meta on the right. ``count`` puts a muted count chip right after the title
    ("Backlog 8") — magnitude before content (6.0); it never replaces the
    ``right`` slot, which stays for status."""
    top = eyebrow(kicker, num) if (kicker or num) else ""
    c = f"<span class='tag'>{esc(count)}</span>" if count is not None else ""
    s = f"<p class='sub'>{esc(sub)}</p>" if sub else ""
    r = f"<span class='spacer'></span>{right}" if right else ""
    return (
        f"<div class='section-head'><div>{top}<h2>{esc(title)}{c}</h2>{s}</div>{r}</div>"
    )


def subhead(title: str, sub: str = "", right: str = "", num: str = "") -> str:
    """Group title inside a card (level 3). ``num`` prefixes a decimal
    sub-number ("02.1") in the meta voice — citable card headings inside a
    numbered section (5.4)."""
    n = f"<span class='sub num'>{esc(num)}</span>" if num else ""
    s = f"<span class='sub'>{esc(sub)}</span>" if sub else ""
    r = f"<span class='spacer'></span>{right}" if right else ""
    return f"<div class='subhead'>{n}{esc(title)}{s}{r}</div>"


def card(body: str, title: str = "", sub: str = "", right: str = "",
         foot_left: str = "", foot_right: str = "", pad: bool = False,
         icon: str = "") -> str:
    """Card shell (design-manual.md, 5 / 6.18): head · context line · body · footer.

    The footer is mandatory as soon as the card shows computed values (5).
    `right`, `icon` and `body` take finished markup; everything else is
    escaped. ``icon`` puts a small soft-accent tile before the title (the
    index cards' kind glyph).
    """
    head = ""
    if title or right or icon:
        i = f"<span class='icon-badge'>{_maybe_html(icon)}</span>" if icon else ""
        r = f"<span class='spacer'></span>{right}" if right else ""
        head = f"<div class='card-head'>{i}<h3 class='card-title'>{esc(title)}</h3>{r}</div>"
    s = f"<p class='card-sub'>{esc(sub)}</p>" if sub else ""
    foot = ""
    if foot_left or foot_right:
        foot = (f"<div class='card-foot'><span>{_maybe_html(foot_left)}</span>"
                f"<span class='spacer'></span><span>{_maybe_html(foot_right)}</span></div>")
    cls = " card--pad" if pad else ""
    return f"<div class='card{cls}'>{head}{s}{body}{foot}</div>"


def focus_card(value: str, label: str, sub: str = "", kind: str = "", chip: str = "",
               kicker: str | None = None, aside=()) -> str:
    """The one card that gets the eye first (design-manual.md, 5.3 / 6.14).

    kind: '' | good | warn | crit — colors only the 4-px bar, never the text.
    aside: sequence of (heading, HTML) — right column, e.g. the next step.
    """
    if kicker is None:
        kicker = STRINGS["focus_kicker"]
    cls = f" focus--{kind}" if kind else ""
    blocks = "".join(f"<div><div class='k'>{esc(k)}</div><div class='v'>{v}</div></div>" for k, v in aside)
    return (
        f"<div class='focus{cls}'>"
        f"<div class='lead'>{eyebrow(kicker)}"
        f"<div class='value'>{esc(value)}</div>"
        f"<div class='label'>{esc(label)}</div>"
        + (f"<div class='sub'>{esc(sub)}</div>" if sub else "")
        + (f"<div class='row'>{chip}</div>" if chip else "")
        + "</div>"
        + (f"<div class='aside'>{blocks}</div>" if blocks else "")
        + "</div>"
    )


def accordion(title: str, body: str, sub: str = "", mark: str = "", meta: str = "",
              right: str = "", tag: str = "", open_: bool = False,
              tags: str = "") -> str:
    """Collapsible entry row: mark · title (+ tag) · subline · meta on the right.

    `tag` renders inline after the title — finished chip markup (e.g. `badge()`)
    passes through, plain text becomes a `.tag` chip. `tags` (space-separated
    lowercase tokens) makes the row addressable by a `filter_row()` above the
    list (6.5); rows without it are never hidden by a filter.
    """
    m = f"<span class='acc-mark'>{_maybe_html(mark)}</span>" if mark else ""
    s = f"<span class='acc-sub'>{esc(sub)}</span>" if sub else ""
    t = ((tag if tag.lstrip().startswith("<") else f"<span class='tag'>{esc(tag)}</span>")
         if tag else "")
    meta_html = f"<span class='meta'>{esc(meta)}</span>" if meta else ""
    dt = f" data-tags='{esc(tags)}'" if tags else ""
    return (
        f"<details class='acc'{' open' if open_ else ''}{dt}><summary>{m}"
        f"<span class='acc-text'><span class='acc-title'>{esc(title)}{t}</span>{s}</span>"
        f"{right}{meta_html}</summary>"
        f"<div class='body'><div class='prose'>{body}</div></div></details>"
    )


# Translate colorful emoji markers from the source files into design-system marks.
# Meaning stays with the text next to them; the mark carries only color + glyph (2.3).
# The title text comes from STRINGS (mark_* keys) so it stays translatable.
_MARKS = {
    "✅": ("good", "✓", "mark_confirmed"),          # ✅
    "\U0001f7e2": ("good", "●", "mark_low"),        # 🟢
    "\U0001f7e1": ("warn", "≈", "mark_assumption"), # 🟡
    "⚠️": ("warn", "!", "mark_attention"),     # ⚠️
    "⚠": ("warn", "!", "mark_attention"),           # ⚠
    "\U0001f534": ("crit", "●", "mark_high"),       # 🔴
    "❌": ("crit", "✕", "mark_no"),             # ❌
    "❓": ("", "?", "mark_unknown"),                 # ❓
    "❗": ("crit", "!", "mark_important"),           # ❗
    "☑": ("good", "✓", "mark_done"),                # checked off
    "☐": ("", "", "mark_open"),                     # open
}


def status_marks(s: str) -> str:
    """Replace emoji status glyphs with `.mark` pills in status color."""
    for ch, (kind, glyph, key) in _MARKS.items():
        if ch in s:
            cls = f" mark--{kind}" if kind else ""
            s = s.replace(ch, f"<span class='mark{cls}' title='{esc(STRINGS[key])}'>{glyph}</span>")
    return s


def sparkline(values, series: int = 1, width: int = 132, height: int = 34,
              compare=None, label: str = "") -> str:
    """12-point sparkline as inline SVG. Previous period optionally as a gray line.

    Mark: 2 px line, endpoint as a dot with a 2-px ring in surface color.
    """
    if not values or len(values) < 2:
        return ""
    pad = 4
    lo, hi = min(values + (compare or [])), max(values + (compare or []))
    span = (hi - lo) or 1

    def path(vals):
        n = len(vals) - 1
        pts = [
            (pad + i * (width - 2 * pad) / n, height - pad - (v - lo) / span * (height - 2 * pad))
            for i, v in enumerate(vals)
        ]
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts), pts

    d, pts = path(values)
    cmp_line = ""
    if compare and len(compare) == len(values):
        dc, _ = path(compare)
        cmp_line = f"<polyline class='compare' points='{dc}'/>"
    ex, ey = pts[-1]
    aria = f" role='img' aria-label='{esc(label)}'" if label else " aria-hidden='true'"
    return (
        f"<svg class='chart spark'{aria} viewBox='0 0 {width} {height}' width='{width}' height='{height}'>"
        f"{cmp_line}"
        f"<polyline class='series' points='{d}' stroke='var(--series-{series})'/>"
        f"<circle class='marker' cx='{ex:.1f}' cy='{ey:.1f}' r='3.5' fill='var(--series-{series})'/>"
        f"</svg>"
    )


def share_bar(segments) -> str:
    """Share bar à la Stripe: [(label, value), …] — a 2-px gap separates, no border."""
    total = sum(v for _, v in segments) or 1
    parts = "".join(
        f"<span style='flex:{v / total:.6f};background:var(--series-{(i % SERIES_COUNT) + 1})'"
        f" title='{esc(l)}'></span>"
        for i, (l, v) in enumerate(segments)
    )
    return f"<div class='share-bar'>{parts}</div>"


def legend(labels, start: int = 1) -> str:
    """Legend mandatory from 2 series on — identity never through color alone."""
    items = "".join(
        f"<span class='item'><span class='swatch' style='background:var(--series-"
        f"{((start - 1 + i) % SERIES_COUNT) + 1})'></span>{esc(l)}</span>"
        for i, l in enumerate(labels)
    )
    return f"<div class='legend'>{items}</div>"


def list_row(main: str, value: str = "", sub: str = "", tags: str = "") -> str:
    """One 'text left, value right' row (design-manual.md, 6.6).

    `value` passes finished markup (badge, delta) through unchanged; plain
    strings — and always `main` and `sub` — are escaped. `tags`
    (space-separated lowercase tokens) makes the row addressable by a
    `filter_row()` above the list (6.5).
    """
    s = f"<span class='sub'>{esc(sub)}</span>" if sub else ""
    v = f"<span class='value'>{_maybe_html(value)}</span>" if value else ""
    dt = f" data-tags='{esc(tags)}'" if tags else ""
    return (f"<div class='list-row'{dt}><span><span class='main'>{esc(main)}</span>{s}</span>"
            f"{v}</div>")


def filter_row(options, scope: str, label: str = "") -> str:
    """Filter pills above a list (design-manual.md, 6.5) — one row, single-select.

    `options` is a sequence of ``(token, label)`` pairs; an "all" pill is
    prepended automatically and starts active. `scope` is a CSS selector for
    the container whose ``data-tags`` children the pills filter (rows opt in
    via the `tags` parameter of `accordion()` / `list_row()`). The behavior
    is FILTER_JS's job — without scripting every pill is inert and the full
    list stays visible, so a filter is always an enhancement, never the only
    way to reach content. The empty note is in the document (a hidden
    `.empty`), not assembled at view time.
    """
    pills = (f"<button type='button' class='chip is-active' data-filter='' "
             f"aria-pressed='true'>{esc(STRINGS['filter_all'])}</button>")
    for token, text in options:
        pills += (f"<button type='button' class='chip' data-filter='{esc(token)}' "
                  f"aria-pressed='false'>{esc(text)}</button>")
    return (f"<div class='filters' role='group' aria-label='{esc(label or STRINGS['filter_aria'])}' "
            f"data-filter-scope='{esc(scope)}'>{pills}"
            f"<span class='empty' hidden>{esc(STRINGS['filter_empty'])}</span></div>")


def show_all(rows, limit: int = 8) -> str:
    """Truncate a long list behind a show-all trigger (design-manual.md, 6.6).

    `rows` is a sequence of finished row markup (`list_row()`, `accordion()`
    — not table rows: a long table is authored top-N instead). At `limit`
    rows or fewer this is a plain join with no wrapper. Beyond it, the rows
    land in a ``data-show-all`` container whose trailing trigger SHOWALL_JS
    reveals; without scripting the trigger stays hidden and every row is
    visible, and printing always shows the full list.
    """
    rows = list(rows)
    if len(rows) <= limit:
        return "".join(rows)
    trigger = (f"<button type='button' class='btn-link show-all' hidden>"
               f"{esc(STRINGS['show_all'].format(n=len(rows)))}</button>")
    return f"<div data-show-all='{limit}'>{''.join(rows)}{trigger}</div>"


def meter_row(name: str, pct: float, kind: str = "") -> str:
    cls = f" {kind}" if kind else ""
    return (
        f"<div class='meter-row'><span class='name'>{esc(name)}</span>"
        f"<span class='meter{cls}'><i style='width:{max(0, min(100, pct)):.1f}%'></i></span>"
        f"<span class='pct'>{fmt_num(pct, 0)} %</span></div>"
    )


# -------------------------------------------------------------- timeline ----
# Horizontal timeline with lanes (design-manual.md, 7.6). The marks are real
# buttons — each opens its detail modal (6.17).

_TL_DOT_PX = 14.0        # diameter of a point-in-time mark
_TL_GAP_PX = 8.0         # minimum air between two marks in the same row
_TL_SEG_GAP_PX = 2.0     # joint between two adjacent bars
_TL_MIN_BAR_PX = 8.0     # shortest visible bar
_TL_CHAR_PX = 6.4        # estimated character width at --fs-meta
_TL_LABEL_PAD = 6.0
_TL_MONTH_LABEL_PX = 26.0


def _tl_next_month(d: _date) -> _date:
    return _date(d.year + d.month // 12, d.month % 12 + 1, 1)


def _tl_geo(ev: dict, start: _date, total: int, width: float) -> dict:
    """Position of a mark: share of the axis (%) and footprint in px."""
    s, e = ev["start"], ev.get("end")
    if e is not None:
        f0 = (s - start).days / total
        f1 = ((e - start).days + 1) / total
        clip_l, clip_r = f0 < 0, f1 > 1
        f0, f1 = min(max(f0, 0.0), 1.0), min(max(f1, 0.0), 1.0)
        f1 = max(f1, f0 + _TL_MIN_BAR_PX / width)
        return {"f0": f0, "f1": f1, "span": True, "clip_l": clip_l, "clip_r": clip_r,
                "x0": f0 * width, "x1": f1 * width}
    c = min(max(((s - start).days + 0.5) / total, 0.0), 1.0)
    return {"f0": c, "f1": c, "span": False, "clip_l": False, "clip_r": False,
            "x0": c * width - _TL_DOT_PX / 2, "x1": c * width + _TL_DOT_PX / 2}


def timeline(lanes, start: _date, end: _date, today=None, min_width: int = 820) -> str:
    """Timeline with one lane per subject area.

    lanes: [{name, slot (1–6), events, meta, info, empty}] — each event is
    {id, titel, kurz, start, end (None ⇒ point in time), status, tooltip}.
    status: confirmed | assumed | planned | open | deadline.

    Labels appear only when they fit without clipping (7.3): a bar labels
    itself within its own width, a dot in the gap up to the next mark.
    Deadlines always carry their label.
    """
    total = max((end - start).days + 1, 1)
    width = float(min_width)

    # --- Axis: years, months, grid ------------------------------------------
    years, months, grid = [], [], []
    cur = _date(start.year, start.month, 1)
    while cur <= end:
        nxt = _tl_next_month(cur)
        f = (cur - start).days / total
        days = min(nxt.toordinal(), end.toordinal() + 1) - max(cur.toordinal(), start.toordinal())
        if f >= 0:
            months.append((f, cur.month, days / total * width))
            if f > 0:
                grid.append((f, cur.month == 1))
            if cur.month == 1 or not years:
                years.append((max(f, 0.0), cur.year))
        cur = nxt

    head = (
        "<div class='tl-head tl-years'>"
        + "".join(f"<span style='left:{f * 100:.4f}%'>{y}</span>" for f, y in years)
        + "</div><div class='tl-head tl-months'>"
        + "".join(
            f"<span style='left:{f * 100:.4f}%'>{esc(STRINGS['months_short'][m - 1])}</span>"
            for f, m, w in months
            if w >= _TL_MONTH_LABEL_PX or (m % 3 == 1 and w * 3 >= _TL_MONTH_LABEL_PX)
        )
        + "</div>"
    )
    gridlines = "".join(
        f"<span class='tl-gl{' tl-gl--year' if yr else ''}' style='left:{f * 100:.4f}%'></span>"
        for f, yr in grid
    )

    # --- Lanes ----------------------------------------------------------------
    lanes_html = []
    for lane in lanes:
        slot = ((int(lane.get("slot", 1)) - 1) % SERIES_COUNT) + 1
        evs = [dict(ev, **_tl_geo(ev, start, total, width)) for ev in lane.get("events", [])]
        evs.sort(key=lambda v: (v["x0"], v["x1"]))

        rows = []                                   # per row: the right end in px
        for ev in evs:
            ev["lbw"] = len(ev["kurz"]) * _TL_CHAR_PX + _TL_LABEL_PAD if ev.get("kurz") else 0.0
            ev["forced"] = ev.get("status") == "deadline" and bool(ev["lbw"])
            reach = ev["x1"] + (ev["lbw"] + _TL_LABEL_PAD if ev["forced"] else 0.0)
            # Bars may butt against each other — the joint is created while drawing
            # (7.2); dots, in contrast, need air or the marks would overlap.
            need = -_TL_SEG_GAP_PX if ev["span"] else _TL_GAP_PX
            for i, occupied in enumerate(rows):
                if occupied + need <= ev["x0"]:
                    rows[i], ev["row"] = reach, i
                    break
            else:
                rows.append(reach)
                ev["row"] = len(rows) - 1

        by_row = {}
        for ev in evs:
            by_row.setdefault(ev["row"], []).append(ev)
        for row_evs in by_row.values():             # already sorted by x0
            for i, ev in enumerate(row_evs):
                nxt_x0 = row_evs[i + 1]["x0"] if i + 1 < len(row_evs) else width
                if not ev["lbw"]:
                    ev["label"] = False
                elif ev["forced"]:
                    ev["label"] = True
                elif ev["span"]:
                    ev["label"] = ev["lbw"] + _TL_LABEL_PAD <= ev["x1"] - ev["x0"]
                else:
                    ev["label"] = ev["x1"] + _TL_LABEL_PAD + ev["lbw"] + _TL_GAP_PX <= nxt_x0

        marks = {}
        for ev in evs:
            cls = ["tl-mark", "tl-span" if ev["span"] else "tl-dot"]
            status = ev.get("status", "confirmed")
            if status in ("assumed", "planned"):
                cls.append("tl-mark--soft")
            elif status == "open":
                cls.append("tl-mark--open")
            elif status == "deadline":
                cls.append("tl-mark--deadline")
            if ev["clip_l"]:
                cls.append("tl-span--clip-l")
            if ev["clip_r"]:
                cls.append("tl-span--clip-r")
            # Deadlines carry the critical status color, not their lane's color (2.3).
            tone = "var(--critical-mark)" if status == "deadline" else f"var(--series-{slot})"
            style = f"left:{ev['f0'] * 100:.4f}%;--c:{tone}"
            if ev["span"]:
                # 2 px in surface color separate adjacent bars (7.2) — never a border.
                style += f";width:calc({(ev['f1'] - ev['f0']) * 100:.4f}% - {int(_TL_SEG_GAP_PX)}px)"
            lb = f"<span class='lb'>{esc(ev['kurz'])}</span>" if ev["label"] else ""
            marks.setdefault(ev["row"], []).append(
                f"<button type='button' class='{' '.join(cls)}' style='{style}'"
                f" data-ev='{esc(ev['id'])}' title='{esc(ev.get('tooltip', ev['titel']))}'"
                f" aria-label='{esc(ev.get('tooltip', ev['titel']))}'>{lb}</button>"
            )

        if evs:
            rows_html = "".join(
                f"<div class='tl-row'>{''.join(marks.get(i, []))}</div>" for i in range(len(rows))
            )
        else:
            note = lane.get("empty", "")
            inner = f"<span class='tl-none'>{esc(note)}</span>" if note else ""
            rows_html = f"<div class='tl-row'>{inner}</div>"

        info = f" title='{esc(lane['info'])}'" if lane.get("info") else ""
        lanes_html.append(
            f"<div class='tl-lane'><div class='tl-lane-head' style='--c:var(--series-{slot})'{info}>"
            f"<span class='sw'></span>{esc(lane['name'])}"
            + (f"<span class='meta'>{esc(lane['meta'])}</span>" if lane.get("meta") else "")
            + f"</div><div class='tl-rows'>{rows_html}</div></div>"
        )

    now, foot = "", ""
    if today and start <= today <= end:
        f = ((today - start).days + 0.5) / total * 100
        now = f"<span class='tl-now' style='left:{f:.4f}%'></span>"
        right = " is-right" if f > 72 else ""
        foot = (f"<div class='tl-foot'><span class='{right.strip()}' style='left:{f:.4f}%'>"
                f"{esc(STRINGS['today'])} · {today.strftime(STRINGS['today_fmt'])}</span></div>")

    return (
        f"<div class='tl-scroll'><div class='tl' style='min-width:{int(min_width)}px'>{head}"
        f"<div class='tl-body'>{gridlines}{now}{''.join(lanes_html)}</div>{foot}</div></div>"
    )


def timeline_key() -> str:
    """Shape legend — meaning hangs on the shape, not on the color (2.3)."""
    items = (
        ("k-span", STRINGS["key_span"]),
        ("k-dot", STRINGS["key_dot"]),
        ("k-dot k-soft", STRINGS["key_soft"]),
        ("k-span k-open", STRINGS["key_open"]),
        ("k-dot k-deadline", STRINGS["key_deadline"]),
    )
    return "<div class='tl-key'>" + "".join(
        f"<span class='item'><span class='{c}'></span>{esc(t)}</span>" for c, t in items
    ) + f"<span class='item'>{esc(STRINGS['key_hint'])}</span></div>"


# ------------------------------------------------------------- detail modal --

def modal_host(dialog_id: str = "evmodal") -> str:
    """Empty detail modal; the content comes from the `modal_detail()` blocks."""
    return (
        f"<dialog class='modal' id='{esc(dialog_id)}' aria-label='{esc(STRINGS['modal_aria'])}'>"
        "<div class='modal-card'><div class='modal-slot'></div>"
        "<div class='modal-foot'>"
        f"<button type='button' class='btn btn--ghost' data-prev>{esc(STRINGS['modal_prev'])}</button>"
        f"<button type='button' class='btn btn--ghost' data-next>{esc(STRINGS['modal_next'])}</button>"
        "<span class='spacer'></span>"
        f"<button type='button' class='btn modal-close'>{esc(STRINGS['modal_close'])}</button>"
        "</div></div></dialog>"
    )


def modal_detail(ev_id: str, title: str, kicker: str = "", when: str = "",
                 badges: str = "", body: str = "", source: str = "") -> str:
    """Hidden content block the detail modal adopts when it opens."""
    return (
        f"<div data-ev-detail='{esc(ev_id)}'><div class='modal-head'>"
        + (f"<div class='eyebrow'>{esc(kicker)}</div>" if kicker else "")
        + f"<h3>{esc(title)}</h3>"
        + (f"<div class='modal-when'>{esc(when)}</div>" if when else "")
        + (f"<div class='row'>{badges}</div>" if badges else "")
        + f"</div><div class='modal-body'><div class='prose'>{body}</div>"
        + (f"<div class='modal-src'>{source}</div>" if source else "")
        + "</div></div>"
    )


# The pages' second (and last) JavaScript purpose: opening, paging through and
# closing the detail modal. Without script, all values stay readable via the table.
MODAL_JS = r"""
(function () {
  var dlg = document.getElementById('evmodal');
  if (!dlg) return;
  var slot = dlg.querySelector('.modal-slot');
  var prev = dlg.querySelector('[data-prev]');
  var next = dlg.querySelector('[data-next]');
  var nodes = [].slice.call(document.querySelectorAll('[data-ev-detail]'));
  var ids = nodes.map(function (n) { return n.getAttribute('data-ev-detail'); });
  var cur = -1, opener = null;

  function fill(id) {
    var i = ids.indexOf(id);
    if (i < 0) return false;
    slot.innerHTML = nodes[i].innerHTML;
    cur = i;
    prev.disabled = i <= 0;
    next.disabled = i >= ids.length - 1;
    var body = slot.querySelector('.modal-body');
    if (body) body.scrollTop = 0;
    return true;
  }
  function open(id, btn) {
    if (!fill(id)) return;
    opener = btn || null;
    if (!dlg.open) { if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', ''); }
    var c = dlg.querySelector('.modal-close');
    if (c) c.focus();
  }
  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-ev]') : null;
    if (t) { e.preventDefault(); open(t.getAttribute('data-ev'), t); return; }
    if (e.target === dlg) dlg.close();
  });
  prev.addEventListener('click', function () { if (cur > 0) fill(ids[cur - 1]); });
  next.addEventListener('click', function () { if (cur < ids.length - 1) fill(ids[cur + 1]); });
  dlg.querySelector('.modal-close').addEventListener('click', function () { dlg.close(); });
  dlg.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowLeft' && cur > 0) fill(ids[cur - 1]);
    if (e.key === 'ArrowRight' && cur < ids.length - 1) fill(ids[cur + 1]);
  });
  dlg.addEventListener('close', function () { if (opener) { opener.focus(); opener = null; } });
})();
"""

FILTER_JS = r"""
/* Filter pills (6.5): single-select visibility filter over data-tags rows.
   View-only — no state is stored, and without this script every pill is
   inert while the full list stays visible. */
(function () {
  [].slice.call(document.querySelectorAll('.filters[data-filter-scope]')).forEach(function (bar) {
    var scope = document.querySelector(bar.getAttribute('data-filter-scope'));
    if (!scope) return;
    var pills = [].slice.call(bar.querySelectorAll('button[data-filter]'));
    var note = bar.querySelector('.empty');
    function apply(token) {
      var visible = 0;
      [].slice.call(scope.querySelectorAll('[data-tags]')).forEach(function (el) {
        var show = !token ||
          (' ' + el.getAttribute('data-tags') + ' ').indexOf(' ' + token + ' ') >= 0;
        el.classList.toggle('is-filtered-out', !show);
        if (show) visible += 1;
      });
      if (note) note.hidden = visible > 0;
    }
    pills.forEach(function (p) {
      p.addEventListener('click', function () {
        pills.forEach(function (q) {
          q.classList.toggle('is-active', q === p);
          q.setAttribute('aria-pressed', q === p ? 'true' : 'false');
        });
        apply(p.getAttribute('data-filter'));
      });
    });
  });
})();
"""

SHOWALL_JS = r"""
/* Show-all (6.6): truncate a long list, one click reveals the rest.
   Without this script the trigger stays hidden and every row is visible. */
(function () {
  [].slice.call(document.querySelectorAll('[data-show-all]')).forEach(function (box) {
    var limit = parseInt(box.getAttribute('data-show-all'), 10) || 8;
    var btn = box.querySelector('.show-all');
    var rows = [].slice.call(box.children).filter(function (el) { return el !== btn; });
    if (rows.length <= limit || !btn) return;
    rows.slice(limit).forEach(function (el) { el.classList.add('is-truncated'); });
    btn.hidden = false;
    btn.addEventListener('click', function () {
      rows.forEach(function (el) { el.classList.remove('is-truncated'); });
      btn.hidden = true;
    });
  });
})();
"""


# ------------------------------------------- input and app chrome (6b) -------
# Components for interactive pages (design-manual.md, 11). They need FORM_CSS
# and/or APP_CSS — a page pulls those in through EXTRA_CSS.

def option_row(key: str, label: str, hint: str = "", selected: bool = False,
               index: int = None, name: str = "") -> str:
    """One choosable answer as a real ``<button>`` (design-manual.md, 6.19).

    ``key`` is the stable, short identifier that travels in the hand-back —
    it survives a reworded label, which is why the two are separate.
    ``index`` (0-based) puts the keyboard digit on the cap; from the tenth
    option on there is neither cap nor shortcut.
    """
    cap = ""
    if index is not None and index < 9:
        cap = f"<span class='opt-key' aria-hidden='true'>{index + 1}</span>"
    hint_html = f"<span class='opt-hint'>{esc(hint)}</span>" if hint else ""
    group = f" data-group='{esc(name)}'" if name else ""
    return (
        f"<button type='button' class='opt' data-key='{esc(key)}'{group}"
        f" aria-pressed='{'true' if selected else 'false'}'>{cap}"
        f"<span class='opt-text'><span class='opt-label'>{esc(label)}</span>{hint_html}</span>"
        f"<span class='opt-tick' aria-hidden='true'>{icon('check', 15)}</span>"
        "</button>"
    )


def field(label: str, control: str, hint: str = "", for_id: str = "") -> str:
    """A labeled control (6.20): real ``<label for=…>``, hint before the input."""
    attr = f" for='{esc(for_id)}'" if for_id else ""
    hint_html = f"<span class='hint'>{esc(hint)}</span>" if hint else ""
    return f"<div class='field'><label{attr}>{esc(label)}</label>{hint_html}{control}</div>"


def text_field(fid: str, label: str, placeholder: str = "", hint: str = "",
               value: str = "", rows: int = 3, multiline: bool = True) -> str:
    """Free text — a textarea by default, a single-line input with ``multiline=False``."""
    ph = f" placeholder='{esc(placeholder)}'" if placeholder else ""
    if multiline:
        control = (f"<textarea id='{esc(fid)}' rows='{int(rows)}'{ph}>{esc(value)}</textarea>")
    else:
        control = (f"<input type='text' id='{esc(fid)}' value='{esc(value)}'{ph}>")
    return field(label, control, hint=hint, for_id=fid)


def amount_field(fid: str, label: str, unit: str = "", placeholder: str = "",
                 hint: str = "", value: str = "") -> str:
    """An amount as typed (6.20). The unit is a suffix label, never parsed into
    the value: interpreting '1.200' is the reader's job, not this page's."""
    ph = f" placeholder='{esc(placeholder)}'" if placeholder else ""
    unit_html = f"<span class='unit' aria-hidden='true'>{esc(unit)}</span>" if unit else ""
    control = (f"<div class='amount'><input type='text' inputmode='decimal' "
               f"id='{esc(fid)}' value='{esc(value)}'{ph}>{unit_html}</div>")
    return field(label, control, hint=hint, for_id=fid)


def progress_bar(done: int, total: int, left: str = "", right: str = "",
                 approx: bool = False, label: str = "") -> str:
    """Sticky progress header (6.22).

    ``approx`` renders an upper bound ("up to 12") — mandatory as soon as a
    condition can hide a question, because a precise total that turns out
    wrong is worse than an honest one.
    """
    total = max(int(total), 0)
    done = max(min(int(done), total), 0)
    pct = (done / total * 100) if total else 0
    if not right:
        count = f"{STRINGS['progress_upto']} {total}" if approx else str(total)
        right = STRINGS["progress_of"].format(done=done, total=count)
    aria = esc(label or right)
    return (
        "<div class='progress'>"
        f"<div class='progress-meta'><span>{esc(left)}</span>"
        f"<span class='right'>{esc(right)}</span></div>"
        f"<div class='meter' role='progressbar' aria-valuemin='0' aria-valuemax='{total}'"
        f" aria-valuenow='{done}' aria-label='{aria}'>"
        f"<i style='width:{pct:.1f}%'></i></div></div>"
    )


def action_bar(left_html: str = "", right_html: str = "", label: str = "") -> str:
    """Fixed bottom bar (6.23). The content column must carry
    ``class='… has-actionbar'`` so the bar covers nothing."""
    aria = esc(label or STRINGS["actions_aria"])
    return (f"<div class='actionbar' role='group' aria-label='{aria}'>{left_html}"
            f"<span class='spacer'></span>{right_html}</div>")


def toast(text: str = "") -> str:
    """The announcement host (6.24) — ``TOAST_JS`` fills and shows it."""
    return (f"<div class='toast' id='toast' role='status' aria-live='polite'>{esc(text)}</div>")


def check_row(rid: str, text: str, state: str = "open", context: str = "",
              detail: str = "", note: str = "", note_label: str = "",
              note_open: str = "", actions: str = "") -> str:
    """One instruction from a maintained document (design-manual.md, 6.26).

    ``rid`` is the row's stable, id-safe identifier — a content fingerprint,
    never a position (11.7). It keys the browser state and travels in the
    hand-back, and it is what lets the row survive the document being edited
    around it.

    ``state``: ``open`` · ``done`` · ``obsolete`` · ``na`` · ``deferred``.
    ``obsolete`` is a statement the *document* makes, so its tick is disabled
    and the state is spelled out in a tag — strikethrough alone would be a
    purely visual signal (2.3). ``na`` ("does not apply") and ``deferred``
    ("I'll come back to it later") are statements the *person* makes — n/a is
    an affirmative answer, not a blank. Attention is inverted (GOV.UK): the
    states still asking for work carry the tag; done and n/a rows sit quiet.

    ``text``, ``context`` and ``detail`` take finished markup (the caller
    renders the source's markdown); labels and values are escaped. The note
    disclosure is present on every row whatever its state (6.21) — a note on a
    row left open is a person saying "did it, but not the way this says", and
    gating that on the tick would lose exactly the interesting case.
    ``actions`` is finished markup for the page's own per-row controls
    (e.g. the n/a and later toggles), placed beside the note opener.
    """
    done = state == "done"
    obsolete = state == "obsolete"
    tid = f"ck-{esc(rid)}-text"
    tick = (f"<button type='button' class='ck-tick' data-check='{esc(rid)}'"
            f" aria-pressed='{'true' if done else 'false'}'"
            f" aria-labelledby='{tid}'{' disabled' if obsolete else ''}>"
            f"{icon('check', 15)}</button>")
    tags = {"obsolete": "check_obsolete", "na": "check_na", "deferred": "check_deferred"}
    word = STRINGS[tags[state]] if state in tags else ""
    # Always in the document, hidden when the row sits quiet: the page script
    # only ever toggles it, never invents its text (11.2). The state words it
    # may need ride as attributes.
    mark = (f"<span class='tag ck-state'{'' if word else ' hidden'}>"
            f"{esc(word)}</span>")
    ctx = f"<div class='ck-context'>{context}</div>" if context else ""
    body = f"<div class='ck-detail prose'>{detail}</div>" if detail else ""
    opener = (f"<button type='button' class='btn btn--ghost note-open'"
              f" data-note-open='{esc(rid)}' aria-expanded='false'"
              f" aria-controls='ck-{esc(rid)}-note-wrap'>"
              f"{esc(note_open or STRINGS['check_note_open'])}</button>"
              f"<div class='note-wrap' id='ck-{esc(rid)}-note-wrap' hidden>"
              + text_field(f"ck-{rid}-note", note_label or STRINGS["check_note_label"],
                           placeholder=STRINGS["check_note_placeholder"],
                           value=note, rows=2)
              + "</div>")
    return (f"<div class='ck-row' data-check-row='{esc(rid)}'"
            f" data-state='{esc(state)}'"
            f" data-word-na='{esc(STRINGS['check_na'])}'"
            f" data-word-deferred='{esc(STRINGS['check_deferred'])}'>{tick}"
            f"<div class='ck-body'><span class='ck-text' id='{tid}'>{text}</span>"
            f"{ctx}{body}{actions}{opener}</div>{mark}</div>")


def summary_row(num: str, question: str, answer: str = "", note: str = "",
                state: str = "open", target: str = "") -> str:
    """One row of the review list, and the way back to its question (6.25).

    ``state``: answered · unclear · skipped · open. The badge carries the word;
    an unanswered row stays clickable — the summary is the editor, not a report.
    """
    kinds_ = {"answered": ("good", "state_answered"), "unclear": ("warn", "state_unclear"),
              "skipped": ("", "state_skipped"), "open": ("", "state_open")}
    tone, key = kinds_.get(state, ("", "state_open"))
    mark = badge(STRINGS[key], tone or "neutral")
    # Both slots are always emitted, empty when there is nothing to say: an
    # interactive page fills them in place, and CSS hides the empty ones.
    a = f"<span class='sumrow-a'>{esc(answer)}</span>"
    n = f"<span class='sumrow-note'>{esc(note)}</span>"
    to = f" data-goto='{esc(target)}'" if target else ""
    return (
        f"<button type='button' class='sumrow' data-state='{esc(state)}'{to}>"
        f"<span class='num'>{esc(num)}</span>"
        f"<span class='sumrow-text'><span class='sumrow-q'>{esc(question)}</span>{a}{n}</span>"
        f"{mark}</button>"
    )


# ------------------------------------------------------------- article -------
# The long-form page's own furniture (11b). Needs ARTICLE_CSS.

def article_head(title: str, kicker: str = "", lede: str = "", meta=()) -> str:
    """The masthead: an optional kicker, the headline, an optional lede, and a
    meta line of short facts (date, reading time, source) separated by dots."""
    parts = [eyebrow(kicker)] if kicker else []
    parts.append(f"<h1>{_maybe_html(title)}</h1>")
    if lede:
        parts.append(f"<p class='lede'>{_maybe_html(lede)}</p>")
    facts = [str(m) for m in (meta or ()) if m]
    if facts:
        joined = "<span class='sep'>·</span>".join(f"<span>{_maybe_html(f)}</span>" for f in facts)
        parts.append(f"<div class='meta'>{joined}</div>")
    return f"<header class='article-head'>{''.join(parts)}</header>"


def pull_quote(text: str, cite: str = "") -> str:
    """One sentence lifted out of the flow. Used sparingly — a page with three
    of them has none, because nothing stands out any more."""
    body = f"<p>{_maybe_html(text)}</p>"
    if cite:
        body += f"<cite>{_maybe_html(cite)}</cite>"
    return f"<blockquote class='pull'>{body}</blockquote>"


def source_list(items, title: str = "Sources", linked: bool = False,
                colophon_line: str = "") -> str:
    """The numbered destinations an article's links pointed at, and the
    document's designed end matter (11b.4 / 11b.7).

    A self-contained page carries no external anchors (design-manual.md, 1.4),
    so a link becomes its label plus a number, and the number is resolved
    here. Entries are plain text on purpose — nothing on the page is
    fetchable. ``linked=True`` gives each entry an ``id`` (``src-n``) and a
    ``↩`` backlink to its first in-text reference (``ref-n``) — internal
    anchors the page can honour. ``colophon_line`` closes the document with
    one line in the instrument voice ("rendered 2026-08-18 · 4,120 words ·
    single file, works offline").
    """
    rows = []
    for n, item in enumerate((str(i) for i in items if i), start=1):
        if linked:
            rows.append(f"<li id='src-{n}'>{_maybe_html(item)}"
                        f"<a class='backref' href='#ref-{n}' aria-label='back to "
                        f"reference {n}'>↩</a></li>")
        else:
            rows.append(f"<li>{_maybe_html(item)}</li>")
    tail = f"<p class='colophon'>{esc(colophon_line)}</p>" if colophon_line else ""
    if not rows and not tail:
        return ""
    body = f"<h2>{esc(title)}</h2><ol>{''.join(rows)}</ol>" if rows else ""
    return f"<footer class='article-foot'>{body}{tail}</footer>"


def aside_note(num: int, body: str) -> str:
    """One margin aside (11b.5): a markdown footnote as a block placed right
    after the paragraph that references it. Open by default so the note reads
    without interaction; at reading width the CSS floats it into the right
    rail. The in-text anchor is ``sup.fn-ref`` with ``id='fn-ref-{num}'``."""
    return (f"<details class='aside' id='fn-{num}' open>"
            f"<summary>{int(num)}</summary>"
            f"<div class='body'>{body}</div></details>")


def mini_toc(entries, label: str = "") -> str:
    """The no-JS table of contents (11b.7): a ``<details open>`` after the
    masthead for documents with four or more sections. ``entries`` is a
    sequence of ``(anchor, text)`` — anchors are internal, which a
    self-contained page can honour."""
    rows = "".join(f"<li><a href='#{esc(anchor)}'>{esc(text)}</a></li>"
                   for anchor, text in entries)
    if not rows:
        return ""
    return (f"<details class='mini-toc' open><summary>"
            f"{esc(label or STRINGS['toc_contents'])}</summary>"
            f"<ol>{rows}</ol></details>")


# ------------------------------------------------------------- js kits -------
# design-manual.md 11.1 permits exactly three script purposes on an
# interactive page. These are the first and the third; screen switching (the
# second) belongs to the page or kind that owns the screens.

TOAST_JS = r"""
/* Brief confirmation for an action that leaves no visible trace (6.24). */
var Toast = (function () {
  var node = null, timer = null;
  function show(text, ms) {
    node = node || document.getElementById('toast');
    if (!node) return;
    node.textContent = text;
    node.classList.add('is-on');
    if (timer) clearTimeout(timer);
    timer = setTimeout(function () { node.classList.remove('is-on'); }, ms || 2200);
  }
  return { show: show };
})();
"""

STATE_JS = r"""
/* Purpose 1 (11.1): remember what was entered, on this device only.
   Namespaced per document, and degrading to memory when storage is not
   available — private mode must not stop the page from working (11.3).

   Store.make(ns, { keys: [...], bucket: 'items' }) additionally collects, on
   every read, the entries of state[bucket] whose key is no longer in `keys`.
   That is what makes content-addressed state work (11.7): a page whose source
   document was edited keeps every entry whose text is still there and forgets
   exactly the ones whose text is not — rather than expiring the lot because
   somebody fixed a typo. Without the option nothing is ever dropped. */
var Store = (function () {
  function usable() {
    try {
      var k = 'render.probe';
      window.localStorage.setItem(k, '1');
      window.localStorage.removeItem(k);
      return true;
    } catch (e) { return false; }
  }
  function make(ns, opts) {
    var key = 'render/' + ns, live = usable(), mem = null;
    var keep = (opts && opts.keys) || null;
    var bucket = (opts && opts.bucket) || null;
    function collect(data) {
      if (!keep || !bucket) return 0;
      var held = data[bucket];
      if (!held || typeof held !== 'object') return 0;
      var gone = 0;
      Object.keys(held).forEach(function (k) {
        if (keep.indexOf(k) < 0) { delete held[k]; gone += 1; }
      });
      return gone;
    }
    var store = {
      persistent: live,
      read: function () {
        var data;
        if (!live) data = mem;
        else {
          try { data = JSON.parse(window.localStorage.getItem(key) || '{}'); }
          catch (e) { data = null; }
        }
        if (!data || typeof data !== 'object') data = {};
        /* Persist the collection, so storage cannot grow without bound across
           many edits — and so the drop is not silently recomputed every load. */
        if (collect(data)) store.write(data);
        return data;
      },
      write: function (obj) {
        mem = obj;
        if (!live) return false;
        try { window.localStorage.setItem(key, JSON.stringify(obj)); return true; }
        catch (e) { live = false; return false; }
      },
      clear: function () {
        mem = null;
        if (!live) return;
        try { window.localStorage.removeItem(key); } catch (e) { /* nothing to undo */ }
      }
    };
    return store;
  }
  return { make: make };
})();
"""

HANDBACK_JS = r"""
/* Purpose 3 (11.1): hand the result back as text. Three ways out, in order —
   the async clipboard, the execCommand fallback, and the block itself, which
   stays visible and selectable so a person can always copy it by hand. */
var Handback = (function () {
  var messages = {
    ok: 'copied to the clipboard',
    manual: 'could not copy — select the block below and copy it by hand'
  };
  function legacy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '-1000px';
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }
  function announce(ok, done) {
    if (typeof done === 'function') { done(ok); return; }
    if (typeof Toast !== 'undefined') Toast.show(ok ? messages.ok : messages.manual);
  }
  function copy(text, done) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function () { announce(true, done); },
        function () { announce(legacy(text), done); }
      );
      return;
    }
    announce(legacy(text), done);
  }
  function bind(button, block) {
    if (!button || !block) return;
    button.addEventListener('click', function () { copy(block.textContent, null); });
  }
  return { copy: copy, bind: bind, messages: messages };
})();
"""


def handback_js(copied: str = "", manual: str = "") -> str:
    """``HANDBACK_JS`` plus the two messages in the page's language.

    The constant is valid JavaScript on its own with English defaults; this
    appends the overrides rather than patching the source, so the kit can
    never be shipped half-substituted.
    """
    return (f"{HANDBACK_JS}\n"
            f"Handback.messages.ok = {_js_str(copied or STRINGS['copy_ok'])};\n"
            f"Handback.messages.manual = {_js_str(manual or STRINGS['copy_manual'])};\n")


def _js_str(value) -> str:
    """A Python string as a JavaScript literal that cannot end the script
    element or break out of its quotes."""
    return (_json.dumps(str(value), ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def page(title: str, body: str, lang: str = "en", favicon: str = "📊") -> str:
    """Skeleton for a self-contained page — no external resources."""
    icon = (
        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'"
        f"%3E%3Ctext y='14' font-size='15'%3E{_html.escape(favicon)}%3C/text%3E%3C/svg%3E"
    )
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="icon" href="{icon}">
<style>{TOKENS}{BASE_CSS}</style>
</head>
<body>
{body}
</body>
</html>
"""
