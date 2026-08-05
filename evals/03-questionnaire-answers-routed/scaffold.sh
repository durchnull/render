#!/usr/bin/env bash
# A consultancy that asks each new client the same six questions. The spec is
# the fixture's own file, so the run can look up every question, option key and
# unit the pasted block refers to — the block carries keys, the spec carries
# what they mean, and the answer has to join the two without inventing either.
set -euo pipefail

mkdir -p docs/questions

cat > README.md <<'MD'
# Onboarding

Client work. Every new engagement starts with the onboarding questionnaire in
`docs/questions/`; the answers get written up as a scope note before anything
is estimated.
MD

cat > docs/questions/2026-09-onboarding.json <<'JSON'
{
  "id": "2026-09-onboarding",
  "title": "New client onboarding",
  "intro": "Six questions so the migration can be scoped properly. Skip anything that does not apply, and say *I don't know* wherever that is the honest answer.",
  "created": "2026-09-01",
  "handback-marker": "ONBOARDING ANSWERS",
  "sections": [
    {
      "title": "Access",
      "questions": [
        {
          "id": "systems",
          "question": "Which systems does the team already use?",
          "why": "decides what the migration has to keep working",
          "type": "multi",
          "options": [
            { "key": "crm", "label": "A CRM we cannot replace" },
            { "key": "sheets", "label": "Shared spreadsheets", "note": true },
            { "key": "none", "label": "Nothing we depend on" }
          ],
          "meta": { "routes-to": "architecture" }
        },
        {
          "id": "owner",
          "question": "Who owns the migration on your side?",
          "why": "one name, so questions have somewhere to go",
          "type": "text",
          "placeholder": "a name"
        }
      ]
    },
    {
      "title": "Budget",
      "questions": [
        {
          "id": "ceiling",
          "question": "Is there a budget ceiling we should design against?",
          "why": "an honest ceiling is worth more than a generous estimate",
          "type": "amount",
          "unit": "€",
          "allow-note": true,
          "note-label": "What does that figure include?"
        },
        {
          "id": "invoicing",
          "question": "How should we invoice?",
          "type": "single",
          "options": [
            { "key": "monthly", "label": "Monthly" },
            { "key": "milestone", "label": "Per milestone" }
          ]
        }
      ]
    },
    {
      "title": "Timing",
      "questions": [
        {
          "id": "golive",
          "question": "When does this have to be live?",
          "type": "text",
          "placeholder": "a date, or what it depends on"
        },
        {
          "id": "training",
          "question": "How many people need training?",
          "type": "amount",
          "unit": "people"
        }
      ]
    }
  ]
}
JSON
