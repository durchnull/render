---
title: Release checklist — 0.4.0
description: Everything that has to be true before 0.4.0 goes out.
deadline: 2026-08-31
deadline-label: Release window closes
handback-marker: RELEASE CHECKLIST CHANGES
exclude: ["🗄️", "**Superseded"]
---

# Release checklist — 0.4.0

Everything that has to be true before this release goes out. Tick what you did,
and leave a note wherever the instruction did not survive contact with reality —
a note on an item nobody ticked is worth more than a tick.

## Before the branch

Nothing here needs the release branch to exist yet, so it can all happen while
the last changes are still landing.

- [x] Agree what goes in and what waits
      Anything that arrives after this point goes into the release after this
      one, however small it looks.
- [ ] Check the dependency licences
      path: Settings › Compliance › Licences
      due: 2026-08-20
      owner: whoever cut the previous release
      The report is generated per branch, so read it on the branch you are
      about to cut from, not on the default one.
- [ ] 🗄️ Post the printed sign-off sheet to the records team

🗄️ Kept for the record: the sheet above was retired two years ago and is listed
only so the step numbers still line up with the old printed process.

**Both runs matter**

The checks below run twice — once here, once after the branch exists. That is
deliberate: the first run is cheap, catches most of it, and leaves the second
run something small enough to read.

- [ ] Run the full test suite
- [ ] Read the changelog end to end

Two things that are not checklist items, and must not be counted as any:

- the release notes live with the tag, not in this file
- anything marked obsolete stays here as part of the record

### Only when the release is a major one

- [ ] Write the migration note
- ~~[ ] Announce the deprecation window~~
- [x] ~~Ship the compatibility shim~~

## After the branch

- [ ] Run the **full** test suite
- [ ] Tag the release
      due: 2026-08-28
      path: Repository › Releases › Draft a new release

**Superseded** — the release calendar used to live here. It moved to the
handbook, and is kept off the page so nobody plans from a stale copy.

## Rollback

Read this before you need it, not after.

- [ ] Know how to roll back
      path: Deployments › Releases › History
