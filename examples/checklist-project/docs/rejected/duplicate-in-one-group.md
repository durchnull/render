---
title: Two identical instructions in one group
---

# Two identical instructions in one group

This file is **deliberately broken** and lives outside the page's `SOURCES`
glob, so nothing renders it. It exists to be refused, and the test suite checks
that it is.

Two items with the same text in the same group cannot be told apart by their
content — which is exactly how the page keys its state. Qualifying them by
position instead would mean that reordering the two swaps which one is ticked,
so the kind reports the collision and refuses to render the page rather than
inventing an id that quietly lies.

A reader cannot tell them apart either. That is the actual defect, and it is in
the document, not in the renderer.

## Checks

- [ ] Run the full test suite
- [ ] Read the changelog end to end
- [ ] Run the full test suite
