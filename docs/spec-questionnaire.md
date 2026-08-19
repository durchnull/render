# The questionnaire spec

**Schema version 1.** One JSON file becomes one interactive questionnaire page.

Strict JSON — no comments, no trailing commas. Unknown keys are **errors**, not
noise: the only escape hatch is the reserved `meta` object, which the page never
renders and never hands back. A spec that does not validate is not rendered at
all; the run reports every finding and exits non-zero.

```json
{
  "id": "2026-08-02-topic-slug",
  "title": "Project intake",
  "intro": "markdown, shown on the first screen",
  "estimate": "about 5 minutes",
  "impact": "why it is worth doing",
  "created": "2026-08-02",
  "handback-marker": "INTAKE ANSWERS",
  "sections": [
    {
      "title": "Scope",
      "intro": "markdown, optional",
      "questions": [
        {
          "id": "q01",
          "question": "Is there an existing system this has to fit into?",
          "why": "one line: what this decides",
          "context": "markdown: what the term means, what the answer changes",
          "detail": "markdown, collapsed behind a disclosure",
          "type": "single",
          "options": [
            { "key": "a", "label": "Yes, and it must not change",
              "hint": "second line", "note": true }
          ],
          "allow-note": true,
          "note-label": "caption for the note field",
          "placeholder": "shown in the empty field",
          "show-if": { "question": "q01", "answer": ["a", "b"] },
          "meta": { "routes-to": "architecture" }
        }
      ]
    }
  ]
}
```

## Fields

| Level | Key | Required | Notes |
|---|---|---|---|
| spec | `id` | yes | Stable. Keys the saved answers **and** the output file name — changing it starts a new, empty page. Lowercase letters, digits, `. - _`. |
| spec | `title` | yes | |
| spec | `intro` | no | Markdown, rendered at build time. Its first paragraph line is also the description on this questionnaire's index card, so write that line to stand on its own. |
| spec | `estimate`, `impact`, `created` | no | Meta chips on the intro screen; `estimate` also reaches the index card's meta line (verbatim, next to the question count — write it as a phrase, "about two minutes"). |
| spec | `handback-marker` | no | Default `QUESTIONNAIRE ANSWERS`. See [handback.md](handback.md). |
| spec | `sections` | yes | At least one. |
| section | `title` | yes | Shown in the progress bar while its questions are on screen. |
| section | `intro` | no | Markdown. |
| section | `questions` | yes | At least one. |
| question | `id` | yes | Unique across the **whole** spec. It is the join key in the hand-back. |
| question | `question` | yes | The question itself. |
| question | `why` | no | One line: what this decides. |
| question | `context` | no | Markdown: what the term means, what the answer changes. |
| question | `detail` | no | Markdown, collapsed behind a disclosure. |
| question | `type` | no | `single` (default) · `multi` · `amount` · `text`. |
| question | `options` | for `single`/`multi` | At least two, with unique keys. |
| question | `allow-note` | no | Pre-opens the note field. Never gates it — the note is always reachable. |
| question | `note-label` | no | Caption for the note field. |
| question | `unit` | `amount` only | A suffix label. The value is handed back as typed. |
| question | `placeholder` | no | For the typed field of that question. |
| question | `show-if` | no | `{ "question": "<id>", "answer": ["<key>", …] }` — any-of match. |
| question | `meta` | no | Never rendered, never handed back. Yours to route with. |
| option | `key` | yes | Short, stable. This is what the agent parses. |
| option | `label` | yes | What the person reads. Reword freely; the key carries the meaning. |
| option | `hint` | no | Second line. |
| option | `note` | no | Pre-opens the note field when this option is chosen. |
| option | `exclusive` | no | Multi only, last option(s) only: "None of these". Renders behind an "or" divider; choosing it clears the others and vice versa. An answer about the world — never a substitute for Skip. |

## What the validator refuses

- a missing `id`, `title`, `sections`, or an empty section
- a duplicate question id anywhere in the spec
- `single`/`multi` with fewer than two options, or duplicate/blank option keys
- `exclusive` on a `single` question, or an exclusive option that is not last
- options on an `amount` or `text` question, `unit` on anything but `amount`
- `show-if` pointing at a question that does not exist, at itself, at a question
  with no options, or at option keys that question does not offer
- `show-if` pointing at a **later** question — a condition may only depend on one
  already answered, which is also what makes a circular condition impossible
- any key the schema does not know, at any level, outside `meta`

## Writing questions worth answering

- **Prefer `single` over `text`.** A closed question is answered in a second and
  parsed exactly; free text costs the reader effort and the agent certainty. Use
  `text` when you genuinely cannot enumerate the answers.
- **Give every question a `why`.** One line on what the answer decides. It is the
  difference between a form and a conversation, and it is what makes someone
  willing to answer the twelfth question.
- **Use `context` for the vocabulary**, not for instructions. If a term could be
  read two ways, say which one you mean.
- **Use `show-if` instead of "if applicable" prose.** A question that does not
  apply should not be on screen at all.
- **Keep option keys short and stable** (`a`, `b`, `yes`, `partial`). Rewrite
  labels whenever the wording can be better; never renumber the keys.
- **Offer an option that means "none of these"** where it is plausible. The note
  field is the pressure valve, but a real option is better than a note.
- **Put routing in `meta`.** The person answering should never see which internal
  path their answer takes.
