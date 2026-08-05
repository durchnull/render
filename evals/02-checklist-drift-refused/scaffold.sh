#!/usr/bin/env bash
# The same project and the same block, one instruction later. "Tag the release"
# has been reworded since the page was rendered, so the document now fingerprints
# as 604978 while the block still says `based-on: fc3a3a`. `handback.py --source`
# exits 3 on that, and exit 3 is a stop sign, not a warning to work around.
#
# The reworded item is deliberately NOT one of the two the block changes: the
# tick could be applied "safely" by anyone reasoning line by line, which is
# exactly the shortcut the case exists to catch.
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

- [ ] Tag the release and push the tag to the remote
- [ ] Announce it in the community channel
MD
