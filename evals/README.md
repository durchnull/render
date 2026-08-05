# Eval suite — the loops that come back

Four cases about the half of this plugin no test can reach: what the agent does
with what a person hands back.

The engine is covered by `tests/run.py` — parsing, fingerprints, edit plans,
`check_page()`, all of it deterministic and free to run. What that suite cannot
see is the judgment the skills ask for afterwards: apply the mechanical edit but
place the notes; treat a fingerprint mismatch as a stop sign rather than an
obstacle; report "don't know" as its own state instead of flattening it into a
blank. Those are the instructions most likely to be quietly lost in an edit, and
the only evidence they still work is a run.

## The cases

| Case | Shape | What a pass means |
|---|---|---|
| `01-checklist-changes-applied` | the loop working | One tick applied as an exact line edit, both notes quoted back and placed, striking an item offered rather than done |
| `02-checklist-drift-refused` | the loop refusing | The document moved since the page was rendered, so nothing is written; the answer names the line that changed and offers a re-render |
| `03-questionnaire-answers-routed` | the other direction | Six items reported with the states the block gives them — don't-know, skipped and unanswered kept apart, the amount repeated as typed |
| `04-neg-docs-typo-fix` | should **not** fire | Two typos fixed, no page, no `.render/`, no pitch |

Every fixture is real input, not a plausible-looking imitation. The block in
`01` parses against its scaffolded document and yields exactly one edit; the
block in `02` is the same block against a document reworded by one line, which
is why `handback.py` exits 3 on it; `03`'s spec validates; `04`'s checklist is a
document the plugin would happily render, which is what makes the case a
temptation rather than a formality.

`02` is the case worth keeping if any were ever dropped. Drift is the failure a
person cannot see: the diff lands on a document that moved, their own edit
disappears, and the answer reads exactly like a successful run.

## Running it

```bash
claude plugin eval . --ablation with-without --scaffold \
  --allow-tools Bash Write Edit \
  --judge-model sonnet \
  --output-dir .dev/eval-results/
```

Four flags that are not optional here:

- **`--scaffold`** builds each case's project. Without it every case runs in an
  empty directory: no document to edit, no spec to look up, and the graders
  measure nothing. The scripts are `scaffold.sh` in each case folder — read them
  before you pass the flag, they run as you.
- **`--allow-tools Bash Write Edit`** grants the tools the cases declare. Leave
  it off and every "never edits the drifted document" grader passes because the
  run could not have edited anything — a vacuous pass, worse than a failure.
- **`--judge-model sonnet`** keeps the rubric graders on a model large enough to
  read them. The default judge is smaller.
- **`--output-dir`** keeps results out of the published tree. `.dev/` is this
  repo's one ignored folder.

The headline number is Δ — the with-plugin score minus the no-plugin baseline.
Case `04` cannot move it (with no plugin loaded the skill cannot fire, so the
baseline passes too); it is there to catch over-triggering, which a pass rate
across the other three hides completely.

Runs cost money: 4 cases × 3 runs × 2 arms, plus a judge call per rubric grader.
Add `--max-cost-usd` if that matters, and `--case '02-*'` while iterating on one.

## What this suite does not cover

- **`/render:init` and `/render:new`.** Both are worth cases and neither has
  one. They end in a render, and a render inside the sandbox depends on
  `engine_locator.py` resolving the engine there — which would make the case
  score the locator, not the skill. Worth building once a real run has shown
  what the sandbox actually resolves.
- **Anything the page does.** The generated HTML, its offline guarantee and its
  copy mechanics are `tests/run.py`'s job and stay there. An eval that opened a
  page would be paying an LLM to re-check an assertion.
- **The render half of the checklist loop.** These four cases all start from a
  block that already exists. Rendering the page that produced it is the gap
  above.

## These graders have never been calibrated

The normal way to build a suite is `claude plugin eval init`, which pilots it
once and shows each output next to its grade, so you can see whether the rubric
agrees with your own judgement before trusting it. That step has not happened
here: on this machine `claude plugin eval` exits with `` `plugin eval` is
currently in early access `` and does nothing, so the suite was written against
the schema and against real parser output, never against a real run.

Treat the first real run as the calibration, not as a measurement. Read the
per-case output and the judge's reasoning before believing any score.

Two shapes most likely to be wrong, because they assume something about the
runner that nothing here could check:

- The `input_match` patterns assume a tool call's serialized input contains the
  file path and the command line. If `parses-with-the-shipped-script` reports
  zero Bash calls in a run that plainly used `handback.py`, the matcher is
  reading something narrower than expected.
- `strikes-nothing-on-its-own` in `01` matches `~~` anywhere in an Edit. A run
  that legitimately edits a line already containing struck text would trip it.
  No fixture line does today; a fixture change could make it a false failure.

## Cases are `case.yaml`, not `prompt.md`

The prose form (`prompt.md` plus `graders/*.md`) cannot express
`context.scaffold_script`, and every case here needs a project to act on. One
`case.yaml` per case keeps the fixture, the prompt and the graders in a single
reviewable file.
