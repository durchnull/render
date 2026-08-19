#!/usr/bin/env python3
"""The hand-back block, parsed by machine instead of by eye.

A rendered page hands its result back as one block of plain text pasted into
the chat (``docs/handback.md`` is the grammar). This script is the reference
parser for that grammar — the agent pipes the paste in and reads a short
report back out, instead of parsing lines in its head:

    python3 scripts/handback.py [FILE] [--marker M] [--source PATH] [--json]

Reads FILE, or stdin when no file is given. The paste may sit inside a longer
message: the block is found by its ``### <MARKER>`` … ``### END <MARKER>``
frame, and the marker is auto-detected unless ``--marker`` pins it.

``--source PATH`` turns a **changes** block into an edit plan against the
maintained document it came from: the drift check first (``based-on:``
against the file's current fingerprint — a mismatch is exit 3 and no plan),
then one exact line edit per state change, ready to apply verbatim. Notes,
cleared notes and anything editorial land under ``judgment:`` — they are the
agent's to place, which is why there is no ``--apply`` and never will be:
this script does not write to anybody's documents.

Exit status: 0 parsed (warnings included), 2 no usable block or bad usage,
3 the source file moved since the page was rendered.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "engine"))

HEADER = re.compile(r"^(source|title|status|based-on): (.*)$")
ITEM = re.compile(r"^\[([^\]]+)\] ?(.*)$")
MOVED = re.compile(r"^~ (.+) → (.+)$")
CONTROL = "## Full state (control)"
BOX = {"open": "[ ]", "done": "[x]"}


def read_state(text):
    """A full-state line: the glyph carries the state, the rest is the text.

    ``n/a`` and ``(later)`` are the person's statements (grammar version 3) —
    states the document itself has no checkbox form for.
    """
    if text.startswith("~~") and text.endswith("~~"):
        return {"state": "obsolete", "text": text[2:-2]}
    if text.startswith("☑ "):
        return {"state": "done", "text": text[2:]}
    if text.startswith("n/a "):
        return {"state": "na", "text": text[4:]}
    if text.startswith("☐ ") and text.endswith(" (later)"):
        return {"state": "deferred", "text": text[2:-8]}
    if text.startswith("☐ "):
        return {"state": "open", "text": text[2:]}
    return {"state": None, "text": text}


def parse(text, marker):
    """One parser, both shapes — the shape is told apart by ``based-on:``,
    which only the changes shape carries. Returns None when the block is not
    there at all; lines the grammar does not know are collected under
    ``ignored``, never fatal — the paste came out of a browser by hand."""
    block = re.search(rf"^### {re.escape(marker)}$(.*?)^### END {re.escape(marker)}$",
                      text, re.M | re.S)
    if not block:
        return None
    out = {"meta": {}, "items": {}, "control": {}, "ignored": []}
    group, item, control = "", None, False
    for line in block.group(1).splitlines():
        head = HEADER.match(line)
        named = ITEM.match(line)
        if not line:
            continue
        elif head:
            out["meta"][head.group(1)] = head.group(2)
        elif line == CONTROL:
            control, item = True, None
        elif line.startswith("## "):
            group = line[3:]
        elif named:
            iid, rest = named.groups()
            if control:
                out["control"][iid] = read_state(rest)
                continue
            item = iid
            out["items"][iid] = {"text": rest, "group": group, "answers": [],
                                 "note": None, "state": None, "was": None}
        elif item is None:
            out["ignored"].append(line)
        elif line.startswith("→ "):                       # shape 1
            value = line[2:]
            entry = out["items"][item]
            if value.startswith("? "):
                entry["state"] = "unclear"
            elif value == "(skipped)":
                entry["state"] = "skipped"
            elif value == "(not answered)":
                pass
            else:
                key = re.match(r"^\((\S+)\) (.*)$", value)
                entry["answers"].append(
                    {"key": key.group(1), "label": key.group(2)} if key
                    else {"key": None, "label": value})
                entry["state"] = "answered"
        elif MOVED.match(line):                           # shape 2
            was, now = MOVED.match(line).groups()
            out["items"][item].update(was=was, state=now)
        elif line.startswith("+ note: "):
            out["items"][item]["note"] = line[8:]
        elif line == "- note:":
            out["items"][item]["note"] = ""
        elif line.startswith("   note: "):
            out["items"][item]["note"] = line[9:]
        else:
            out["ignored"].append(line)
    out["shape"] = "changes" if "based-on" in out["meta"] else "answers"
    if out["shape"] == "answers":
        for entry in out["items"].values():
            if entry["state"] is None:
                entry["state"] = "open"
    return out


# ------------------------------------------------------------- the block ----

def normalized(text: str) -> str:
    """What a copy out of a browser does to text, undone: CR line endings and
    trailing whitespace, the two alterations that carry no meaning."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n"))


def detect_marker(text):
    """(marker, problem) — the marker of the first complete block, or what
    stood in the way of finding one."""
    opened = re.findall(r"^### (?!END )(.+)$", text, re.M)
    ends = set(re.findall(r"^### END (.+)$", text, re.M))
    for marker in opened:
        if marker in ends:
            return marker, None
    if opened:
        return None, (f"'### {opened[0]}' opens a block but '### END "
                      f"{opened[0]}' never closes it — the paste is "
                      "truncated; ask for it again.")
    return None, ("no hand-back block found — expected '### <MARKER>' … "
                  "'### END <MARKER>' lines.")


# ------------------------------------------------------------- edit plan ----

def edit_plan(out, src: Path):
    """A changes block joined against the document it proposes to change.

    Everything mechanical becomes an exact line edit; everything editorial
    (notes, cleared notes, anything trying to strike an item) is listed for
    the agent, because that is where the review step lives.
    """
    import kinds.checklist as checklist

    spec = checklist.load(src)
    based_on = out["meta"].get("based-on", "")
    plan = {"source": str(src), "based_on": based_on,
            "source_fp": spec["source_fp"],
            "drift": based_on != spec["source_fp"],
            "edits": [], "judgment": [], "unmatched": [],
            "control_mismatch": [], "warnings": []}
    if plan["drift"]:
        return plan

    by_fp = {i["fp"]: i for i in spec["items"]}
    raw_lines = src.read_text(encoding="utf-8").splitlines()

    for fp, entry in out["items"].items():
        known = by_fp.get(fp)
        if known is None:
            plan["unmatched"].append({"fp": fp, "text": entry["text"]})
            continue
        if entry["was"] is not None:
            if entry["state"] in ("na", "deferred"):
                # The person's statement (grammar v3): the document has no
                # checkbox form for it, so where it lands — struck, annotated,
                # left as is — is the agent's editorial call.
                said = ("does not apply" if entry["state"] == "na"
                        else "deferred — will come back to it")
                plan["judgment"].append(
                    {"fp": fp, "text": known["text"], "group": known["group"],
                     "state": known["state"],
                     "why": f"declared {said}; no mechanical edit exists for "
                            "this — place it in the document yourself"})
            elif entry["state"] not in BOX:
                # ``obsolete`` never appears as a ``~`` target; a block that
                # carries one is asking for an editorial change sideways.
                plan["judgment"].append(
                    {"fp": fp, "text": known["text"], "group": known["group"],
                     "state": known["state"],
                     "why": f"asks for a state this plan never applies: "
                            f"{entry['was']} → {entry['state']}"})
            elif known["state"] == entry["state"]:
                plan["warnings"].append(
                    f"[{fp}] already {entry['state']} in the file — "
                    "nothing to do")
            else:
                old = raw_lines[known["line"] - 1]
                plan["edits"].append(
                    {"fp": fp, "line": known["line"], "old": old,
                     "new": re.sub(r"\[[ xX]\]", BOX[entry["state"]], old,
                                   count=1),
                     "text": known["text"]})
        if entry["note"] is not None:
            plan["judgment"].append(
                {"fp": fp, "text": known["text"], "group": known["group"],
                 "state": entry["state"] or known["state"],
                 "why": "note cleared" if entry["note"] == ""
                        else f"note: {entry['note']}"})

    # What the file will say once the edits land, held against what the page
    # says it should — the control listing is the page's whole belief. The
    # person-states (na, deferred) are part of that belief even though no
    # edit carries them, or every such item would read as a mismatch.
    expected = {fp: i["state"] for fp, i in by_fp.items()}
    for fp, entry in out["items"].items():
        if (entry["was"] is not None and fp in expected
                and (entry["state"] in BOX or entry["state"] in ("na", "deferred"))):
            expected[fp] = entry["state"]
    for fp, control in out["control"].items():
        if fp not in expected:
            plan["unmatched"].append({"fp": fp, "text": control["text"]})
        elif control["state"] and expected[fp] != control["state"]:
            plan["control_mismatch"].append(
                {"fp": fp, "text": control["text"],
                 "file": expected[fp], "control": control["state"]})
    return plan


# ---------------------------------------------------------------- report ----

def report_items(out):
    lines = []
    group = object()
    for iid, entry in out["items"].items():
        if entry["group"] != group:
            group = entry["group"]
            if group:
                lines.append(f"## {group}")
        state = entry["state"] or "unchanged"
        if entry["was"] is not None:
            state = f"{entry['was']} → {entry['state']}"
        lines.append(f"[{iid}] {state} · {entry['text']}")
        for answer in entry["answers"]:
            key = f"({answer['key']}) " if answer["key"] else ""
            lines.append(f"  = {key}{answer['label']}")
        if entry["note"] == "":
            lines.append("  note cleared")
        elif entry["note"] is not None:
            lines.append(f"  note: {entry['note']}")
    return lines


def report(out, plan):
    lines = [f"shape: {out['shape']}"]
    lines += [f"{k}: {v}" for k, v in out["meta"].items() if k != "based-on"]
    if out["ignored"]:
        count = len(out["ignored"])
        lines.append(f"ignored ({count} line{'s' if count != 1 else ''} "
                     "the grammar does not know)")

    if plan is None:
        lines.append("")
        lines += report_items(out)
        return lines

    lines.append(f"based-on: {plan['based_on']} — matches {plan['source']}")
    lines.append("")
    lines.append(f"edits ({len(plan['edits'])}) — apply verbatim:")
    for e in plan["edits"]:
        lines.append(f"L{e['line']}: {e['old']}")
        lines.append(f"   → {e['new']}")
    lines.append("")
    lines.append(f"judgment ({len(plan['judgment'])}) — yours to place, "
                 "never applied mechanically:")
    for j in plan["judgment"]:
        where = f" · {j['group']}" if j["group"] else ""
        lines.append(f"[{j['fp']}] ({j['state']}{where}) {j['text']}")
        lines.append(f"   {j['why']}")
    for u in plan["unmatched"]:
        lines.append(f"unmatched: [{u['fp']}] {u['text']} — not in the file")
    for m in plan["control_mismatch"]:
        lines.append(f"control-mismatch: [{m['fp']}] file says {m['file']}, "
                     f"page says {m['control']} · {m['text']}")
    lines += [f"warning: {w}" for w in plan["warnings"]]
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("file", nargs="?", help="the paste; stdin when omitted")
    ap.add_argument("--marker", help="pin the block marker instead of "
                                     "auto-detecting it")
    ap.add_argument("--source", type=Path,
                    help="the maintained document a changes block belongs "
                         "to; emits an edit plan against it")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="the parsed block (and plan) as JSON")
    args = ap.parse_args()

    try:
        text = (Path(args.file).read_text(encoding="utf-8") if args.file
                else sys.stdin.read())
    except OSError as err:
        print(err, file=sys.stderr)
        return 2
    text = normalized(text)

    marker = args.marker
    if marker is None:
        marker, problem = detect_marker(text)
        if marker is None:
            print(problem, file=sys.stderr)
            return 2
    out = parse(text, marker)
    if out is None:
        _, problem = detect_marker(text)
        print(problem or f"no block framed by '### {marker}' … "
                         f"'### END {marker}' in the input.", file=sys.stderr)
        return 2

    plan = None
    if args.source:
        if out["shape"] != "changes":
            print("--source needs a changes block (one carrying 'based-on:'); "
                  "this is the answers shape.", file=sys.stderr)
            return 2
        if not args.source.is_file():
            print(f"{args.source} is not a file.", file=sys.stderr)
            return 2
        plan = edit_plan(out, args.source)
        if plan["drift"]:
            print(f"drift: the page was rendered from {plan['based_on']}, "
                  f"but {plan['source']} is now {plan['source_fp']} — the "
                  "file changed while the page was open. Never force the "
                  "diff: re-render and ask what changed.", file=sys.stderr)
            return 3

    if args.as_json:
        payload = dict(out, **({"plan": plan} if plan else {}))
        print(json.dumps(payload, ensure_ascii=False, indent=1))
    else:
        print("\n".join(report(out, plan)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
