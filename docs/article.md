# One document, one page to read

**`/render:article` and `scripts/article.py`.** The long-form flavour of the
engine, and the one page that is not declared: no `.render/` directory, no
cache, no hook, nothing in the index. A person asks for a page, the page is
written, that is the whole lifecycle. It works in any project, configured or
not.

Everything visual comes from the design system's long-form tier
(`ARTICLE_CSS`), so an article and a dashboard out of this engine are
recognisably the same family — the rules are
[design/longform.md](design/longform.md) §11b. The renderer itself is a
standalone script on `page_api`, the same public interface a project's own
page scripts use ([page-api.md](page-api.md)).

## What the argument means

| `/render:article …` | Renders |
|---|---|
| a path to a markdown file | that file |
| any other text | the last substantive message in the conversation, with that text as the headline |
| nothing | the last substantive message, headline taken from the document |

When the source is a message rather than a file, it is written verbatim to
`articles/<YYYY-MM-DD>-<slug>.md` first, relative to the working directory.
That markdown file stays: it is the source, and the page can be rendered
again from it after the plugin updates. A page nobody can regenerate is a
dead end.

## The script

```bash
python3 scripts/article.py INPUT.md [-o OUT.html] [--title …] [--kicker …] [--lede …] [--date …]
```

| Flag | Sets | Default |
|---|---|---|
| `-o`, `--out` | the output path | the input's name with `.html` |
| `--title` | the headline | see below |
| `--kicker` | the overline above the headline | frontmatter `kicker`, else none |
| `--lede` | the standfirst under the headline | frontmatter `lede`, else none |
| `--date` | the date in the meta line | frontmatter `date`, else the file's own mtime |

The date defaults to the **document's** date, never today's — re-rendering an
old file must not restamp it as new. The meta line also carries a reading
time, estimated at 220 words per minute.

## Where the headline comes from

In order, first hit wins: `--title` → the document's frontmatter `title` →
its first `#` heading → the file name (hyphens become spaces). A leading `#`
heading is lifted out of the body when it is used, so the masthead does not
repeat what the first line already says.

Section headings are then normalized: the shallowest heading level present in
the document becomes `h2`, whatever the source wrote. Documents disagree about
where they start — some head their sections with `#`, some with `##` — and
anchoring on the shallowest one means the first section always lands exactly
one step under the masthead.

## What happens to links

A self-contained page fetches nothing, and `check_page()` refuses external
URLs outright, so **no link survives as a link**:

- an **external** link becomes its label plus `[n]`, and `[n]` is resolved in
  a source list at the foot;
- a link **into the project** (a relative path, an anchor) becomes its label —
  in a technical document the label is usually the path already;
- a URL **inside a code sample** keeps everything but its scheme
  (`https://example.com/x` → `example.com/x`), so the command still reads
  correctly and still cannot be clicked.

Images are replaced by their alt text. Sources are numbered in first-seen
order and deduplicated, so the same destination cited twice is one entry.

## Failure

The script runs `check_page()` before writing and writes **nothing** if it
finds anything, reporting each finding instead. A failed run leaves no
half-good page behind — the fix is the document or the flags, never working
around the check.

## Out of scope, deliberately

- **Never rendered into `.render/output/`** — that directory belongs to the
  declared pages and their index, and an article is neither.
- **Never wired into a hook.** One page, when a person asks for it. If it runs
  by itself, it is the wrong tool.
- **Never restyled through the plugin's own files.** Style belongs in
  `ARTICLE_CSS`; a page-specific tweak goes through `--title`/`--kicker`/
  `--lede` or into the document.
