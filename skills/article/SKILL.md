---
description: Render one markdown document — or the last thing that was said in this conversation — as a self-contained, magazine-styled HTML page, and open it. Use when somebody asks for a readable page out of a document or a turn.
argument-hint: [file.md | headline | nothing]
disable-model-invocation: true
allowed-tools: Read, Write, Bash(python3:*), Bash(open:*), Bash(xdg-open:*)
---

# One page, made to be read

## When

Somebody wants **one** thing to read: a document turned into a page worth
looking at, or the answer that just went past kept as something more durable
than scrollback. Nothing here is automatic — this runs when a person asks for
it, once, and produces exactly one file.

This is the long-form flavour of the engine, not a declared page: no
`.render/` needed, no cache, no hook, nothing in the index. It works in any
project, configured or not.

## What the argument means

| `/render:article …` | Renders |
|---|---|
| a path to a markdown file | that file |
| any other text | the last substantive message in this conversation, with that text as the headline |
| nothing | the last substantive message, headline taken from the document |

"Last substantive message" is the assistant turn before this command — unless
that one was trivial (a one-liner, this command's own echo), in which case it
is the last one that carried real content. Tool calls and their results are
not part of a message.

## The four steps

1. **Get the markdown.**
   - A file was named → use it as it is. Never edit somebody's document to
     make it render better.
   - Otherwise → write the message **verbatim** into
     `articles/<YYYY-MM-DD>-<slug>.md`, relative to the working directory:
     its full markdown text, unchanged. No summarizing, no reformatting, no
     added commentary, no "as requested" preamble. `<slug>` comes from the
     headline, lowercased, words joined by hyphens. Create `articles/` if it
     is not there.

     The markdown file stays — it is the source, and the page can be rendered
     again from it after the plugin updates. A page nobody can regenerate is
     a dead end.

2. **Render:**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/article.py" <source.md>
   ```

   The page lands next to the source unless `-o` says otherwise. Useful
   flags: `--title` (headline), `--kicker` (overline), `--lede`
   (standfirst), `--date`. Without them the script reads the document's
   frontmatter, then its first `#` heading, then the file name.

   The script writes nothing if `check_page()` finds anything — a failed run
   leaves no half-good page behind. Report what it said instead of working
   around it.

3. **Open it** — `open <path>` on macOS, `xdg-open` elsewhere. A rendered
   page is meant to be looked at, and an editor shows markup, not a page.

4. **Reply with the path** as a clickable link, and nothing else. One line.
   The page speaks for itself; a summary of what is in it is noise.

## What happens to links

A self-contained page fetches nothing, so **no link survives as a link** —
`check_page()` refuses external URLs outright and the script would rather
strip them than write a page that fails its own contract:

- an external link becomes its label plus `[n]`, and `[n]` is resolved in the
  source list at the foot;
- a link into the project (a relative path, an anchor) becomes its label —
  in a technical document the label is usually the path already;
- a URL inside a code sample keeps everything but its scheme
  (`https://example.com/x` → `example.com/x`), so the command still reads
  correctly and still cannot be clicked.

Say this once if somebody expects clickable links; do not try to reintroduce
them.

## Never

- **Never edit the message to make a better article.** The page is a view of
  what was said. Fixing a typo means changing the record.
- **Never render into `.render/output/`** — that directory belongs to the
  declared pages and their index, and an article is neither.
- **Never wire this into a hook.** One page, when a person asks. If it ever
  runs by itself, it is the wrong tool.
- **Never modify the plugin's own files** to change how a page looks. Style
  belongs in `ARTICLE_CSS`, which ships with the engine; a page-specific
  tweak goes through `--title`/`--kicker`/`--lede` or into the document.

## Behind it

`${CLAUDE_PLUGIN_ROOT}/scripts/article.py` is a standalone renderer on
`page_api` — the same public interface a project's own page scripts use
(`/render:new` has the pattern).
The look is the design system's long-form tier (`ARTICLE_CSS`,
design-manual.md 11b): one reading column, a masthead, a drop cap where the
text really opens with prose, and code samples that stay legible. Colors,
spacing and type come from the tokens like everywhere else, so an article and
a dashboard from this engine are recognisably the same family.
