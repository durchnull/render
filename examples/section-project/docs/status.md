---
version: 0.9.0
period: 2026-08-01 → 2026-08-19
tests: 412
tests_added: 34
coverage: 94
open: 11
pythons: 3.10 – 3.14
deps: 0
next: 1.0.0 · 2026-09-30
---

# Where 1.0 stands

Meridian parses the dates people actually write — `next friday`, `12.03.`,
`2026-W07-3` — and returns something you can compute with. The API has not
changed since 0.7; what is left before 1.0 is not features but the promises
a 1.0 makes: a frozen public surface, a deprecation policy, and a parser
that fails predictably on input it cannot read.

Two things are still open in the parser itself. Ambiguous two-part dates
(`03.04.`) resolve by locale today and by an explicit `dayfirst` argument
after 1.0, which is the last breaking change planned. Week dates parse but
do not round-trip through `isoformat()` on Python 3.10, where the standard
library disagrees with us about the ISO year boundary.

Everything else on the list is documentation and packaging. The suite runs
in under nine seconds, the library has no dependencies, and it is meant to
keep both of those properties — they are the reason people vendor it.
