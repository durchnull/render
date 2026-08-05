#!/usr/bin/env bash
# A project that keeps its release checklist as an ordinary markdown document.
# The document is the fixture the pasted block in the prompt was rendered from:
# its fingerprint is fc3a3a and its item ids are the ones the block names, so
# `handback.py --source` reports "matches" and emits exactly one edit. Change a
# single instruction here and the case becomes the drift case instead.
set -euo pipefail

mkdir -p docs/checklists

cat > README.md <<'MD'
# Orbit

A small product. Release checklists live in `docs/checklists/`, one file per
release, and are worked through by whoever is running the release that month.
MD

cat > docs/checklists/release-2026-09.md <<'MD'
---
title: Release 2026-09
deadline: 2026-09-30
---

# Release 2026-09

Everything that has to happen before the September release goes out.

## Before the freeze

- [x] Close the milestone in the tracker
- [ ] Update the changelog
      due: 2026-09-24
- [ ] Ask the design team to sign off on the new empty states

## Release day

- [ ] Tag the release
- [ ] Announce it in the community channel
MD
