#!/usr/bin/env python3
"""The ``questionnaire`` page kind — one spec file becomes one interactive page.

Three screens: intro → one question at a time → summary. Everything is in the
document from the start and merely hidden (design-manual.md, 11.2); the script
switches screens, remembers answers in ``localStorage``, and assembles the
hand-back block. Nothing is fetched, nothing is sent, nothing is parsed from a
string at view time.

The spec is data, not code — see ``docs/spec-questionnaire.md`` for the schema
and ``docs/handback.md`` for the grammar of the block the page produces. This
module refuses to render a spec it does not fully understand: unknown keys and
dangling conditions are errors, because a typo that renders is a question the
person answering will never see.

The kind is deliberately domain-free. It knows how to ask; it knows nothing
about what is asked or where the answers go — that belongs to the consuming
project's own skill.
"""

import json as _json
import re
from pathlib import Path

from content_core import md_to_html
from design_system import (
    APP_CSS, FORM_CSS, HANDBACK_JS, STATE_JS, STRINGS as DS_STRINGS, TOAST_JS,
    action_bar, amount_field, badge, card, esc, handback_js, option_row,
    progress_bar, summary_row, text_field, toast,
)

NAME = "questionnaire"
WRAP_CLASS = "wrap wrap--narrow has-actionbar"

TYPES = ("single", "multi", "amount", "text")
ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")
QID_RE = re.compile(r"[A-Za-z0-9_-]+\Z")
KEY_RE = re.compile(r"[A-Za-z0-9_-]+\Z")

SPEC_KEYS = {"id", "title", "intro", "estimate", "impact", "created",
             "handback-marker", "sections", "meta"}
SECTION_KEYS = {"title", "intro", "questions", "meta"}
QUESTION_KEYS = {"id", "question", "why", "context", "detail", "type", "options",
                 "allow-note", "note-label", "unit", "placeholder", "show-if", "meta"}
OPTION_KEYS = {"key", "label", "hint", "note"}
SHOW_IF_KEYS = {"question", "answer"}

# User-visible text. English defaults; a project overrides any key through
# config.STRINGS or the page's STRINGS. The hand-back grammar is deliberately
# NOT in here — it is a protocol the agent parses, not interface text.
STRINGS = {
    "q_start": "Start",
    "q_continue": "Continue where you left off",
    "q_restart": "Start over",
    "q_to_summary": "Jump to the summary",
    "q_back": "← Back",
    "q_next": "Next →",
    "q_finish": "To the summary →",
    "q_dont_know": "I don't know",
    "q_skip": "Skip this one",
    "q_note_open": "+ add detail — if no answer fits exactly",
    "q_note_label": "Anything to add?",
    "q_note_placeholder": "in your own words",
    "q_detail": "More on this",
    "q_why": "Why this is asked",
    "q_summary_title": "Your answers",
    "q_summary_lead": ("Every row jumps back to its question. Nothing here is "
                       "mandatory — hand back what you have."),
    "q_copy": "Copy the answers",
    "q_copy_hint": "Paste this block back into the chat.",
    "q_keys": "Keys: 1–9 choose · ← → move · Enter continues",
    "q_estimate": "Takes about",
    "q_impact": "Why it matters",
    "q_created": "Created",
    "q_resume": "You have answered some of this already.",
    "q_no_storage": ("This browser will not remember answers — best to finish "
                     "in one sitting and copy the result out."),
    "q_question": "Question",
    "q_questions": "Questions",
    "q_privacy": ("Your answers stay in this browser, on this device, until you "
                  "copy them out. This page loads nothing and sends nothing."),
    "q_generated": "Generated on {generated}",
    "q_answered_none": "not answered",
}


# ------------------------------------------------------------ validation ----

def _unknown(mapping, allowed, path: str) -> list:
    return [f"{path}: unknown key {k!r} — the reserved 'meta' object is the "
            "place for anything the schema does not know"
            for k in mapping if k not in allowed]


def _text(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def validate(spec, src: Path) -> list:
    """Every problem with this spec, not just the first.

    Strict by design: an unknown key is an error, because the alternative is a
    typo that disappears silently — ``questoin:`` next to a missing question is
    exactly the bug that never gets noticed until someone has already filled
    the page out.
    """
    bad = []
    if not isinstance(spec, dict):
        return ["the spec must be a JSON object"]
    bad += _unknown(spec, SPEC_KEYS, "spec")

    if not _text(spec.get("id")):
        bad.append("spec: 'id' is required — it keys the saved answers and the "
                   "output file name, so it must be stable")
    elif not ID_RE.match(spec["id"]):
        bad.append(f"spec: id {spec['id']!r} — lowercase letters, digits, dot, "
                   "dash and underscore only, starting with a letter or digit")
    if not _text(spec.get("title")):
        bad.append("spec: 'title' is required")
    for key in ("intro", "estimate", "impact", "created", "handback-marker"):
        if key in spec and not isinstance(spec[key], str):
            bad.append(f"spec: {key!r} must be a string")
    if _text(spec.get("handback-marker")) and not re.fullmatch(
            r"[A-Za-z0-9 _-]+", spec["handback-marker"]):
        bad.append("spec: 'handback-marker' may hold letters, digits, spaces, "
                   "dashes and underscores only — it is a line marker the agent "
                   "matches on")

    sections = spec.get("sections")
    if not isinstance(sections, list) or not sections:
        bad.append("spec: 'sections' is required and needs at least one section")
        return bad

    seen_ids, order, option_keys = {}, [], {}
    for si, section in enumerate(sections):
        where = f"sections[{si}]"
        if not isinstance(section, dict):
            bad.append(f"{where}: must be an object")
            continue
        bad += _unknown(section, SECTION_KEYS, where)
        if not _text(section.get("title")):
            bad.append(f"{where}: 'title' is required")
        if "intro" in section and not isinstance(section["intro"], str):
            bad.append(f"{where}: 'intro' must be a string")
        questions = section.get("questions")
        if not isinstance(questions, list) or not questions:
            bad.append(f"{where}: 'questions' is required and needs at least one entry")
            continue
        for qi, q in enumerate(questions):
            bad += _validate_question(q, f"{where}.questions[{qi}]", seen_ids,
                                      order, option_keys)

    bad += _validate_conditions(sections, seen_ids, order, option_keys)
    return bad


def _validate_question(q, where: str, seen_ids: dict, order: list,
                       option_keys: dict) -> list:
    bad = []
    if not isinstance(q, dict):
        return [f"{where}: must be an object"]
    bad += _unknown(q, QUESTION_KEYS, where)

    qid = q.get("id")
    if not _text(qid):
        bad.append(f"{where}: 'id' is required")
    elif not QID_RE.match(qid):
        bad.append(f"{where}: id {qid!r} — letters, digits, dash and underscore only")
    elif qid in seen_ids:
        bad.append(f"{where}: duplicate question id {qid!r} (already used in "
                   f"{seen_ids[qid]}) — ids must be unique across the whole spec")
    else:
        seen_ids[qid] = where
        order.append(qid)

    if not _text(q.get("question")):
        bad.append(f"{where}: 'question' is required")
    for key in ("why", "context", "detail", "note-label", "unit", "placeholder"):
        if key in q and not isinstance(q[key], str):
            bad.append(f"{where}: {key!r} must be a string")
    if "allow-note" in q and not isinstance(q["allow-note"], bool):
        bad.append(f"{where}: 'allow-note' must be true or false")
    if "meta" in q and not isinstance(q["meta"], dict):
        bad.append(f"{where}: 'meta' must be an object")

    qtype = q.get("type", "single")
    if qtype not in TYPES:
        bad.append(f"{where}: type {qtype!r} is unknown — one of {', '.join(TYPES)}")
        return bad

    options = q.get("options")
    if qtype in ("single", "multi"):
        if not isinstance(options, list) or len(options) < 2:
            bad.append(f"{where}: a {qtype} question needs at least two options")
            return bad
        keys = []
        for oi, opt in enumerate(options):
            spot = f"{where}.options[{oi}]"
            if not isinstance(opt, dict):
                bad.append(f"{spot}: must be an object")
                continue
            bad += _unknown(opt, OPTION_KEYS, spot)
            if not _text(opt.get("key")):
                bad.append(f"{spot}: 'key' is required — it is what the answer is "
                           "handed back as, so it must be short and stable")
            elif not KEY_RE.match(opt["key"]):
                bad.append(f"{spot}: key {opt['key']!r} — letters, digits, dash "
                           "and underscore only")
            else:
                keys.append(opt["key"])
            if not _text(opt.get("label")):
                bad.append(f"{spot}: 'label' is required")
            if "hint" in opt and not isinstance(opt["hint"], str):
                bad.append(f"{spot}: 'hint' must be a string")
            if "note" in opt and not isinstance(opt["note"], bool):
                bad.append(f"{spot}: 'note' must be true or false")
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        if dupes:
            bad.append(f"{where}: option keys must be unique — {', '.join(dupes)}")
        if _text(qid):
            option_keys[qid] = set(keys)
        if "unit" in q:
            bad.append(f"{where}: 'unit' belongs to an amount question")
    else:
        if options is not None:
            bad.append(f"{where}: a {qtype} question takes no options")
        if qtype == "text" and "unit" in q:
            bad.append(f"{where}: 'unit' belongs to an amount question")
    return bad


def _validate_conditions(sections, seen_ids: dict, order: list,
                         option_keys: dict) -> list:
    """``show-if`` may only point backwards, at an option question, at keys that
    exist. Backwards-only is what makes a circular condition impossible: a
    question can never wait on one that is asked after it."""
    bad = []
    rank = {qid: i for i, qid in enumerate(order)}
    for section in sections:
        if not isinstance(section, dict):
            continue
        for q in section.get("questions") or []:
            if not isinstance(q, dict) or "show-if" not in q:
                continue
            qid = q.get("id")
            where = f"question {qid!r}" if _text(qid) else "a question"
            cond = q["show-if"]
            if not isinstance(cond, dict):
                bad.append(f"{where}: 'show-if' must be an object with 'question' "
                           "and 'answer'")
                continue
            bad += _unknown(cond, SHOW_IF_KEYS, f"{where}.show-if")
            target = cond.get("question")
            if not _text(target):
                bad.append(f"{where}: show-if needs 'question'")
                continue
            if target not in seen_ids:
                bad.append(f"{where}: show-if points at {target!r}, which is not a "
                           "question in this spec")
                continue
            if target == qid:
                bad.append(f"{where}: show-if points at itself")
                continue
            if _text(qid) and rank.get(target, -1) > rank.get(qid, -1):
                bad.append(f"{where}: show-if points at {target!r}, which is asked "
                           "later — a condition may only depend on an earlier "
                           "question, which is also what rules out circular ones")
                continue
            if target not in option_keys:
                bad.append(f"{where}: show-if points at {target!r}, which has no "
                           "options to match against")
                continue
            answers = cond.get("answer")
            answers = [answers] if isinstance(answers, str) else answers
            if not isinstance(answers, list) or not answers:
                bad.append(f"{where}: show-if needs 'answer' — one option key or a "
                           "list of them")
                continue
            missing = [a for a in answers if a not in option_keys[target]]
            if missing:
                known = ", ".join(sorted(option_keys[target]))
                bad.append(f"{where}: show-if expects {', '.join(map(repr, missing))} "
                           f"on {target!r}, which offers: {known}")
    return bad


# ----------------------------------------------------------------- output ----

def css() -> str:
    """The two opt-in stylesheets plus what only a questionnaire needs."""
    return FORM_CSS + APP_CSS + """
/* ---- Questionnaire (design-manual.md, 11) -------------------------------- */
.q-meta { display: flex; gap: var(--s2); flex-wrap: wrap; margin-top: var(--s4); }
.q-why {
  font-size: var(--fs-sub); color: var(--ink-2); margin: 0 0 var(--s3);
  padding-left: var(--s3); border-left: 3px solid var(--accent-line);
}
.q-head { margin-bottom: var(--s4); }
.q-head h2 {
  font-size: var(--fs-h2); font-weight: 600; letter-spacing: -0.022em;
  line-height: 1.2; margin: 0 0 var(--s3);
}
.q-step {
  font-size: var(--fs-eyebrow); font-weight: 600; letter-spacing: 0.07em;
  text-transform: uppercase; color: var(--muted); margin-bottom: var(--s2);
}
.q-context { font-size: var(--fs-body); color: var(--ink-2); }
.q-context > :first-child { margin-top: 0; }
.q-aside { margin-top: var(--s3); }
.q-pass { display: flex; gap: var(--s2); flex-wrap: wrap; margin-top: var(--s4); }
.q-keys { font-size: var(--fs-meta); color: var(--muted); margin-top: var(--s5); }
.q-resume { display: flex; gap: var(--s2); flex-wrap: wrap; margin-top: var(--s4); }
.q-copy { display: flex; gap: var(--s3); align-items: center; flex-wrap: wrap;
          margin-bottom: var(--s3); }
.q-copy .hint { font-size: var(--fs-meta); color: var(--muted); }
"""


def filename(spec, src: Path, pid: str) -> str:
    """One page per spec id — the id is validated to a safe charset, so it can
    carry the file name without further translation."""
    return f"{pid}-{spec['id']}.html"


def summary(spec, ctx) -> dict:
    """How this questionnaire introduces itself on the index page.

    What someone deciding whether to open it wants to know is how long it
    will take and how much there is — so the estimate and the question count
    go on the card, and the intro supplies the sentence.
    """
    s = ctx.strings
    facts = [(s["q_questions"], len(_questions(spec)))]
    if spec.get("estimate"):
        facts.append((s["q_estimate"], spec["estimate"]))
    if spec.get("created"):
        facts.append((s["q_created"], spec["created"]))
    return {"title": spec.get("title"), "desc": spec.get("intro"), "facts": facts}


def footer(spec, ctx, generated: str) -> str:
    """Says where the answers live (11.3). A page's own FOOTER_HTML wins."""
    s = ctx.strings
    return (f"  <footer>{esc(s['q_generated'].format(generated=generated))} · "
            f"{esc(s['q_privacy'])}</footer>")


def scripts() -> str:
    return TOAST_JS + STATE_JS + handback_js() + QUESTION_JS


def _prose(md: str, base: int = 4) -> str:
    return f"<div class='prose q-context'>{md_to_html(md, heading_base=base)}</div>" if md else ""


def _json_block(payload: dict, block_id: str) -> str:
    """The machine half of the spec (11.2). Never display text, never ``meta``:
    the project already has the spec file, so the page carries only what the
    hand-back and the progress count are computed from."""
    text = _json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    text = text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return f"<script type='application/json' id='{block_id}'>{text}</script>"


def _questions(spec) -> list:
    out = []
    for si, section in enumerate(spec["sections"]):
        for q in section["questions"]:
            out.append((si, section, q))
    return out


def build(spec, ctx):
    s = ctx.strings
    flat = _questions(spec)
    total = len(flat)
    conditional = any("show-if" in q for _, _, q in flat)

    screens = [_intro_screen(spec, ctx, total, conditional)]
    payload = {"id": spec["id"], "title": spec["title"],
               "marker": spec.get("handback-marker") or "QUESTIONNAIRE ANSWERS",
               "approx": conditional,
               "sections": [sec["title"] for sec in spec["sections"]],
               "questions": []}

    for n, (si, section, q) in enumerate(flat, start=1):
        screens.append(_question_screen(q, section, si, n, total, ctx))
        entry = {"id": q["id"], "type": q.get("type", "single"), "section": si,
                 "text": q["question"]}
        if q.get("type", "single") in ("single", "multi"):
            entry["options"] = [{"key": o["key"], "label": o["label"]}
                                for o in q["options"]]
        if "show-if" in q:
            answer = q["show-if"]["answer"]
            entry["showIf"] = {"question": q["show-if"]["question"],
                               "answer": [answer] if isinstance(answer, str) else answer}
        if q.get("unit"):
            entry["unit"] = q["unit"]
        if q.get("allow-note") or any(o.get("note") for o in q.get("options") or []):
            entry["noteOn"] = [o["key"] for o in q.get("options") or [] if o.get("note")] or True
        payload["questions"].append(entry)

    screens.append(_summary_screen(spec, ctx, flat))

    body = (progress_bar(0, total, left=spec["title"], approx=conditional)
            + "<main>" + "".join(screens) + "</main>"
            + _json_block(payload, "q-data"))
    # Both button labels live in the DOM as attributes, not in the payload —
    # 11.2 keeps display text out of the data block.
    tail = (toast()
            + action_bar(f"<button type='button' class='btn btn--ghost' id='q-back'"
                         f" hidden>{esc(s['q_back'])}</button>",
                         f"<button type='button' class='btn btn--primary' id='q-next'"
                         f" data-label-next='{esc(s['q_next'])}'"
                         f" data-label-finish='{esc(s['q_finish'])}'"
                         f" hidden>{esc(s['q_next'])}</button>")
            + _noscript())
    return body, tail


def _noscript() -> str:
    """Without scripting every screen is shown at once and the chrome that would
    do nothing is hidden — the page stays a readable, printable questionnaire
    (design-manual.md, 11.2)."""
    return ("<noscript><style>"
            ".screen[hidden] { display: block !important; }"
            ".note-wrap[hidden] { display: block !important; }"
            ".progress, .actionbar, .q-pass, .note-open, .q-resume "
            "{ display: none !important; }"
            ".has-actionbar { padding-bottom: var(--s7); }"
            "</style></noscript>")


def _intro_screen(spec, ctx, total: int, conditional: bool) -> str:
    s = ctx.strings
    chips = []
    for key, label in (("estimate", "q_estimate"), ("impact", "q_impact"),
                       ("created", "q_created")):
        if spec.get(key):
            chips.append(f"<span class='chip'>{esc(s[label])}: {esc(spec[key])}</span>")
    count = f"{s['q_question']} 1–{total}" if not conditional else f"≤ {total}"
    chips.append(f"<span class='chip'>{esc(count)}</span>")

    resume = (f"<div class='q-resume' id='q-resume' hidden>"
              f"<p class='empty'>{esc(s['q_resume'])}</p>"
              f"<button type='button' class='btn btn--primary' data-go='resume'>"
              f"{esc(s['q_continue'])}</button>"
              f"<button type='button' class='btn' data-go='summary'>"
              f"{esc(s['q_to_summary'])}</button>"
              f"<button type='button' class='btn btn--ghost' data-go='restart'>"
              f"{esc(s['q_restart'])}</button></div>")
    storage = (f"<div class='banner banner--warn' id='q-nostore' hidden>"
               f"{esc(s['q_no_storage'])}</div>")
    return (
        "<section class='screen' id='q-intro' data-screen='intro'>"
        "<header class='hero'>"
        f"<h1 tabindex='-1'>{esc(spec['title'])}</h1>"
        f"<div class='q-meta'>{''.join(chips)}</div></header>"
        + storage
        + (f"<div class='card card--pad'>{_prose(spec.get('intro', ''), 3)}</div>"
           if spec.get("intro") else "")
        + resume
        + f"<p class='q-keys'>{esc(s['q_keys'])}</p>"
        + "</section>"
    )


def _question_screen(q, section, si: int, n: int, total: int, ctx) -> str:
    s = ctx.strings
    qid = q["id"]
    qtype = q.get("type", "single")
    step = f"{esc(section['title'])} · {esc(s['q_question'])} {n}"

    head = (f"<div class='q-head'><div class='q-step' aria-current='step'>{step}</div>"
            f"<h2 tabindex='-1'>{esc(q['question'])}</h2>"
            + (f"<p class='q-why'>{esc(q['why'])}</p>" if q.get("why") else "")
            + "</div>")
    context = _prose(q.get("context", ""))
    detail = (f"<details class='q-aside'><summary>{esc(s['q_detail'])}</summary>"
              f"<div class='body'>{_prose(q.get('detail', ''))}</div></details>"
              if q.get("detail") else "")

    if qtype in ("single", "multi"):
        control = "".join(
            option_row(o["key"], o["label"], hint=o.get("hint", ""), index=i, name=qid)
            for i, o in enumerate(q["options"]))
    elif qtype == "amount":
        control = amount_field(f"{qid}-value", q["question"], unit=q.get("unit", ""),
                               placeholder=q.get("placeholder", ""))
    else:
        control = text_field(f"{qid}-value", q["question"],
                             placeholder=q.get("placeholder", ""))

    note = (f"<button type='button' class='btn btn--ghost note-open'"
            f" data-note-open='{esc(qid)}' aria-expanded='false'"
            f" aria-controls='{esc(qid)}-note-wrap'>{esc(s['q_note_open'])}</button>"
            f"<div class='note-wrap' id='{esc(qid)}-note-wrap' hidden>"
            + text_field(f"{qid}-note", q.get("note-label") or s["q_note_label"],
                         placeholder=s["q_note_placeholder"], rows=2)
            + "</div>")

    pass_row = (f"<div class='q-pass'>"
                f"<button type='button' class='btn' data-mark='unclear'>"
                f"{esc(s['q_dont_know'])}</button>"
                f"<button type='button' class='btn btn--ghost' data-mark='skipped'>"
                f"{esc(s['q_skip'])}</button></div>")

    return (
        f"<section class='screen' id='q-{esc(qid)}' data-screen='question'"
        f" data-q='{esc(qid)}' data-type='{esc(qtype)}' hidden>"
        f"{head}{context}{detail}"
        f"<div class='card card--pad'>{control}{note}{pass_row}</div>"
        "</section>"
    )


def _summary_screen(spec, ctx, flat) -> str:
    s = ctx.strings
    rows = "".join(
        summary_row(f"{n:02d}", q["question"], state="open", target=q["id"])
        for n, (_, _, q) in enumerate(flat, start=1))
    copy_row = (f"<div class='q-copy'>"
                f"<button type='button' class='btn btn--primary' id='q-copy'>"
                f"{esc(s['q_copy'])}</button>"
                f"<span class='hint'>{esc(s['q_copy_hint'])}</span></div>")
    # The four state words as attributes: translatable through the design
    # system's STRINGS, and in the document rather than in the data block.
    words = " ".join(
        f"data-word-{name}='{esc(DS_STRINGS[key])}'"
        for name, key in (("answered", "state_answered"), ("unclear", "state_unclear"),
                          ("skipped", "state_skipped"), ("open", "state_open")))
    return (
        "<section class='screen' id='q-summary' data-screen='summary' hidden>"
        f"<div class='q-head'><h2 tabindex='-1'>{esc(s['q_summary_title'])}</h2>"
        f"<p class='q-why'>{esc(s['q_summary_lead'])}</p></div>"
        + card(f"<div id='q-rows' {words}>{rows}</div>")
        + card(copy_row + "<pre class='handback' id='q-handback'></pre>")
        + "</section>"
    )


# ------------------------------------------------------------------ check ----

def check(spec, html: str) -> list:
    """What must be true of every questionnaire this kind produces."""
    bad = []
    flat = _questions(spec)
    screens = re.findall(r"data-screen='question' data-q='([^']+)'", html)
    expected = [q["id"] for _, _, q in flat]
    if screens != expected:
        bad.append(f"question screens do not match the spec: {len(screens)} in the "
                   f"page, {len(expected)} in the spec")
    if "id='q-data'" not in html:
        bad.append("the data block is missing")
    if "id='q-handback'" not in html:
        bad.append("the hand-back block is missing")
    if html.count("<noscript>") != 1:
        bad.append("the no-script fallback is missing")
    rows = html.count("class='sumrow'")
    if rows != len(expected):
        bad.append(f"summary has {rows} rows for {len(expected)} questions")
    # Every question offers both ways past it, and a note (11.4). Checked by
    # attribute, not by wording, so a translated page passes the same test.
    for name, needle in (("don't-know", "data-mark='unclear'"),
                         ("skip", "data-mark='skipped'"),
                         ("note", "data-note-open=")):
        if html.count(needle) != len(expected):
            bad.append(f"{html.count(needle)} of {len(expected)} questions offer "
                       f"the {name} affordance — it is not optional")
    return bad


# --------------------------------------------------------------------- js ----
# Purpose 2 of the three permitted ones (design-manual.md, 11.1): show and hide
# what is already in the document. Purposes 1 and 3 come from STATE_JS and
# HANDBACK_JS above.

QUESTION_JS = r"""
(function () {
  var raw = document.getElementById('q-data');
  if (!raw) return;
  var data = JSON.parse(raw.textContent);
  var store = Store.make('questionnaire/' + data.id);
  var state = store.read();
  if (!state || typeof state !== 'object') state = {};
  if (!state.answers) state.answers = {};

  var byId = {};
  data.questions.forEach(function (q) { byId[q.id] = q; });
  var screens = {};
  [].slice.call(document.querySelectorAll('.screen')).forEach(function (el) {
    screens[el.id] = el;
  });
  var reduced = window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var current = 'q-intro', timer = null;
  var resumeAt = state.at;          /* captured before the first show() moves it */

  /* Question ids may start with a digit, which no CSS id selector accepts —
     address the fields by attribute instead. */
  function fieldOf(el, id, part) {
    return el.querySelector('[id="' + id + '-' + part + '"]');
  }

  function answer(id) {
    if (!state.answers[id]) state.answers[id] = { v: [], note: '', state: 'open' };
    return state.answers[id];
  }
  function save() { store.write(state); }

  /* Which questions are on the table right now: a condition hides its
     question, and a hidden question is not counted and not handed back. */
  function visible() {
    var out = [];
    data.questions.forEach(function (q) {
      if (!q.showIf) { out.push(q); return; }
      var on = state.answers[q.showIf.question];
      if (!on || on.state !== 'answered') return;
      var hit = on.v.some(function (v) { return q.showIf.answer.indexOf(v) >= 0; });
      if (hit) out.push(q);
    });
    return out;
  }
  function counted() {
    var n = 0;
    visible().forEach(function (q) {
      var a = state.answers[q.id];
      if (a && a.state !== 'open') n += 1;
    });
    return n;
  }

  /* Never lose typed text: the current screen's fields are committed before
     anything else happens (11.6). */
  function commit() {
    var el = screens[current];
    if (!el || el.getAttribute('data-screen') !== 'question') return;
    var id = el.getAttribute('data-q');
    var a = answer(id);
    var value = fieldOf(el, id, 'value');
    var note = fieldOf(el, id, 'note');
    if (note) a.note = note.value.trim();
    if (value) {
      var text = value.value.trim();
      a.v = text ? [text] : [];
      if (text) a.state = 'answered';
      else if (a.state === 'answered') a.state = 'open';
    }
    save();
  }

  function paint() {
    var live = visible();
    var ids = live.map(function (q) { return q.id; });
    data.questions.forEach(function (q) {
      var el = screens['q-' + q.id];
      if (el) el.setAttribute('data-live', ids.indexOf(q.id) >= 0 ? 'yes' : 'no');
    });
    var bar = document.querySelector('.progress .meter');
    var done = counted(), total = live.length;
    /* The bar tracks what is on the table; the printed total stays the upper
       bound, because a condition can only ever add questions (6.22). */
    var shown = data.approx ? data.questions.length : total;
    if (bar) {
      var fill = bar.querySelector('i');
      if (fill) fill.style.width = (total ? (done / total * 100) : 0).toFixed(1) + '%';
      bar.setAttribute('aria-valuenow', String(done));
      bar.setAttribute('aria-valuemax', String(total));
      bar.setAttribute('aria-label', progressText(done, shown));
    }
    var right = document.querySelector('.progress .right');
    if (right) right.textContent = progressText(done, shown);
    var left = document.querySelector('.progress-meta > span');
    var here = screens[current];
    if (left && here && here.getAttribute('data-screen') === 'question') {
      var q = byId[here.getAttribute('data-q')];
      if (q) left.textContent = data.sections[q.section];
    } else if (left) {
      left.textContent = data.title;
    }
    paintOptions();
    paintSummary(live);
    if (handbackBlock) handbackBlock.textContent = handback();
  }
  function progressText(done, total) {
    return done + ' / ' + (data.approx ? ('≤ ' + total) : String(total));
  }
  function paintOptions() {
    data.questions.forEach(function (q) {
      var el = screens['q-' + q.id];
      if (!el) return;
      var a = state.answers[q.id];
      [].slice.call(el.querySelectorAll('.opt')).forEach(function (b) {
        var on = !!(a && a.state === 'answered'
                    && a.v.indexOf(b.getAttribute('data-key')) >= 0);
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      [].slice.call(el.querySelectorAll('[data-mark]')).forEach(function (b) {
        var on = !!(a && a.state === b.getAttribute('data-mark'));
        b.classList.toggle('btn--primary', on);
      });
      var value = fieldOf(el, q.id, 'value');
      if (value && a && a.v.length && value.value !== a.v[0]) value.value = a.v[0];
      var note = fieldOf(el, q.id, 'note');
      if (note && a && a.note && note.value !== a.note) note.value = a.note;
      if (a && a.note) openNote(q.id, true);
    });
  }
  function paintSummary(live) {
    var ids = live.map(function (q) { return q.id; });
    [].slice.call(document.querySelectorAll('.sumrow')).forEach(function (row) {
      var id = row.getAttribute('data-goto');
      row.hidden = ids.indexOf(id) < 0;
      var a = state.answers[id] || { v: [], note: '', state: 'open' };
      row.setAttribute('data-state', a.state);
      var text = row.querySelector('.sumrow-a');
      var note = row.querySelector('.sumrow-note');
      if (text) text.textContent = readable(id, a);
      if (note) note.textContent = a.note || '';
      var mark = row.querySelector('.badge');
      if (mark) {
        mark.textContent = words[a.state] || words.open;
        mark.className = 'badge' + (a.state === 'answered' ? ' badge--good'
                                    : (a.state === 'unclear' ? ' badge--warn' : ''));
      }
    });
  }
  function readable(id, a) {
    if (a.state !== 'answered' || !a.v.length) return '';
    var q = byId[id];
    if (!q.options) return a.v[0] + (q.unit ? ' ' + q.unit : '');
    var out = [];
    a.v.forEach(function (key) {
      q.options.forEach(function (o) { if (o.key === key) out.push(o.label); });
    });
    return out.join(' · ');
  }

  function show(id, focus) {
    commit();
    if (!screens[id]) return;
    if (screens[current]) screens[current].hidden = true;
    current = id;
    screens[id].hidden = false;
    state.at = id;
    save();
    paint();
    var head = screens[id].querySelector('h1, h2');
    if (head && focus !== false) head.focus();
    window.scrollTo(0, 0);
    var back = document.getElementById('q-back');
    var next = document.getElementById('q-next');
    var kind = screens[id].getAttribute('data-screen');
    if (back) back.hidden = (kind === 'intro');
    if (next) {
      next.hidden = (kind === 'summary');
      next.textContent = lastQuestion(id) ? labels.finish : labels.next;
    }
  }
  function chain() {
    return ['q-intro'].concat(visible().map(function (q) { return 'q-' + q.id; }))
      .concat(['q-summary']);
  }
  function lastQuestion(id) {
    var list = chain();
    return list.indexOf(id) === list.length - 2;
  }
  function step(delta) {
    var list = chain(), i = list.indexOf(current);
    if (i < 0) { show('q-intro'); return; }
    var next = Math.min(Math.max(i + delta, 0), list.length - 1);
    if (next !== i) show(list[next]);
  }

  function openNote(id, on) {
    var el = screens['q-' + id];
    if (!el) return;
    var wrap = el.querySelector('.note-wrap');
    var btn = el.querySelector('[data-note-open]');
    if (!wrap || !btn) return;
    wrap.hidden = !on;
    btn.setAttribute('aria-expanded', on ? 'true' : 'false');
  }
  function noteBusy(id) {
    var el = screens['q-' + id];
    if (!el) return false;
    var wrap = el.querySelector('.note-wrap');
    var note = fieldOf(el, id, 'note');
    return !!(wrap && !wrap.hidden) || !!(note && note.value.trim());
  }

  function choose(id, key) {
    commit();                       /* a half-typed note is never lost (11.6) */
    var q = byId[id], a = answer(id);
    if (q.type === 'multi') {
      var at = a.v.indexOf(key);
      if (at >= 0) a.v.splice(at, 1); else a.v.push(key);
      a.state = a.v.length ? 'answered' : 'open';
    } else {
      a.v = [key];
      a.state = 'answered';
    }
    if (q.noteOn === true || (q.noteOn && q.noteOn.indexOf(key) >= 0)) openNote(id, true);
    save();
    paint();
    /* Auto-advance only where an answer is unambiguously complete, and never
       while a thought is being typed (11.5). */
    if (q.type === 'single' && !reduced && !noteBusy(id)) {
      if (timer) clearTimeout(timer);
      timer = setTimeout(function () { if (current === 'q-' + id) step(1); }, 180);
    }
  }
  function mark(id, how) {
    commit();
    var a = answer(id);
    a.state = (a.state === how) ? 'open' : how;
    a.v = [];
    /* "Don't know" and "skip" are answers in their own right, so the field is
       cleared with them — otherwise the next commit() would read the leftover
       text back and quietly overrule what the person just said. The note is
       kept: it is often the reason they could not answer (11.4). */
    var el = screens['q-' + id];
    var value = el ? fieldOf(el, id, 'value') : null;
    if (value) value.value = '';
    save();
    paint();
    if (a.state === how) step(1);
  }

  /* The hand-back grammar is a protocol, not interface text — see
     docs/handback.md. Only the marker is configurable. */
  function flat(text) { return String(text).replace(/\s*\n+\s*/g, ' / '); }

  function handback() {
    var live = visible(), lines = [];
    var done = 0, unclear = 0, skipped = 0;
    live.forEach(function (q) {
      var a = state.answers[q.id] || { v: [], note: '', state: 'open' };
      if (a.state === 'answered') done += 1;
      else if (a.state === 'unclear') unclear += 1;
      else if (a.state === 'skipped') skipped += 1;
    });
    lines.push('### ' + data.marker);
    lines.push('source: ' + data.id);
    lines.push('title: ' + data.title);
    lines.push('status: ' + done + ' of ' + live.length + ' answered · '
               + unclear + ' unclear · ' + skipped + ' skipped');
    var section = -1;
    live.forEach(function (q) {
      if (q.section !== section) {
        section = q.section;
        lines.push('');
        lines.push('## ' + data.sections[section]);
      }
      lines.push('[' + q.id + '] ' + q.text);
      var a = state.answers[q.id] || { v: [], note: '', state: 'open' };
      if (a.state === 'answered' && a.v.length) {
        if (q.options) {
          a.v.forEach(function (key) {
            var label = key;
            q.options.forEach(function (o) { if (o.key === key) label = o.label; });
            lines.push('→ (' + key + ') ' + label);
          });
        } else {
          /* The grammar is line-oriented, so a typed answer folds onto one
             line the same way a note does — the characters are untouched
             otherwise, amounts least of all (11.4, docs/handback.md). */
          lines.push('→ ' + flat(a.v[0]) + (q.unit ? ' ' + q.unit : ''));
        }
      } else if (a.state === 'unclear') {
        lines.push('→ ? don\'t know — please follow up');
      } else if (a.state === 'skipped') {
        lines.push('→ (skipped)');
      } else {
        lines.push('→ (not answered)');
      }
      if (a.note) lines.push('   note: ' + flat(a.note));
    });
    lines.push('');
    lines.push('### END ' + data.marker);
    return lines.join('\n');
  }

  /* Every user-visible word this script needs comes out of the document
     (11.2) — the data block carries no display text. */
  var rowHost = document.getElementById('q-rows');
  var nextBtn = document.getElementById('q-next');
  var handbackBlock = document.getElementById('q-handback');
  var words = {
    answered: word(rowHost, 'answered'), unclear: word(rowHost, 'unclear'),
    skipped: word(rowHost, 'skipped'), open: word(rowHost, 'open')
  };
  var labels = {
    next: nextBtn ? nextBtn.getAttribute('data-label-next') : '',
    finish: nextBtn ? nextBtn.getAttribute('data-label-finish') : ''
  };
  function word(host, name) {
    return (host && host.getAttribute('data-word-' + name)) || name;
  }

  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target : null;
    if (!t) return;
    var opt = t.closest('.opt');
    if (opt) {
      var host = opt.closest('[data-q]');
      choose(host.getAttribute('data-q'), opt.getAttribute('data-key'));
      return;
    }
    var pass = t.closest('[data-mark]');
    if (pass) {
      mark(pass.closest('[data-q]').getAttribute('data-q'),
           pass.getAttribute('data-mark'));
      return;
    }
    var opener = t.closest('[data-note-open]');
    if (opener) {
      var id = opener.getAttribute('data-note-open');
      var wrap = screens['q-' + id].querySelector('.note-wrap');
      openNote(id, wrap.hidden);
      if (!wrap.hidden) {
        var field = wrap.querySelector('textarea');
        if (field) field.focus();
      }
      return;
    }
    var row = t.closest('.sumrow');
    if (row) { show('q-' + row.getAttribute('data-goto')); return; }
    var go = t.closest('[data-go]');
    if (go) {
      var what = go.getAttribute('data-go');
      if (what === 'restart') {
        state = { answers: {} };
        store.clear();
        save();
        paint();
        step(1);
      } else if (what === 'summary') {
        show('q-summary');
      } else {
        show(resumeAt && screens[resumeAt] ? resumeAt : chain()[1]);
      }
      return;
    }
    if (t.closest('#q-next')) { step(1); return; }
    if (t.closest('#q-back')) { step(-1); return; }
    if (t.closest('#q-copy')) {
      commit();
      paint();
      Handback.copy(handbackBlock ? handbackBlock.textContent : handback(), null);
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { step(1); return; }
    var active = document.activeElement;
    if (/^(INPUT|TEXTAREA)$/.test((active && active.tagName) || '')) return;
    if (e.key === 'ArrowRight') { step(1); return; }
    if (e.key === 'ArrowLeft') { step(-1); return; }
    if (e.key === 'Enter') { step(1); return; }
    if (/^[1-9]$/.test(e.key)) {
      var el = screens[current];
      if (!el || el.getAttribute('data-screen') !== 'question') return;
      var opts = el.querySelectorAll('.opt');
      var pick = opts[parseInt(e.key, 10) - 1];
      if (pick) {
        e.preventDefault();
        choose(el.getAttribute('data-q'), pick.getAttribute('data-key'));
      }
    }
  });

  window.addEventListener('beforeunload', commit);

  var nostore = document.getElementById('q-nostore');
  if (nostore && !store.persistent) nostore.hidden = false;
  var resume = document.getElementById('q-resume');
  var progressed = Object.keys(state.answers).some(function (k) {
    var a = state.answers[k];
    return a && a.state && a.state !== 'open';
  });
  if (resume && progressed) resume.hidden = false;
  paint();
  show('q-intro', false);
})();
"""
