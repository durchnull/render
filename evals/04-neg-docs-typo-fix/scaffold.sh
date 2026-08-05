#!/usr/bin/env bash
# Everything the checklist skill looks for is here — a maintained markdown
# checklist, with groups, ticks and a struck item — and none of it is what the
# person asked about. The two typos are in the prose around it, one in the
# README and one in a heading nobody would render.
set -euo pipefail

mkdir -p docs/checklists

cat > README.md <<'MD'
# Meridian

An internal tool. Documentation lives in `docs/`, and each release is worked
through as a checklist in `docs/checklists/`.

## Contributing

Open a pull request against `main`. Every change needs a reviewr, and the
changelog entry goes in the same commit.
MD

cat > docs/checklists/release-2026-08.md <<'MD'
---
title: Release 2026-08
---

# Release 2026-08

## Before the freze

- [x] Close the milestone in the tracker
- [x] Update the changelog
- [ ] Ask the design team to sign off
- [ ] ~~Regenerate the screenshots~~

## Release day

- [ ] Tag the release
- [ ] Announce it in the community channel
MD
