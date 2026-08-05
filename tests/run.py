#!/usr/bin/env python3
"""Self-tests for the render engine — ``python3 tests/run.py``.

Standard library only, no external dependencies: the same command runs in CI
and on a laptop. Every test that needs a project builds a throwaway one in a
temporary directory, so nothing here touches the repository or a real project.

What is worth testing here is what a reader cannot check by looking:

* section pages still render **byte-identically** — the whole point of calling
  0.2.0 additive;
* the questionnaire validator refuses each malformed spec class it claims to,
  with all findings at once rather than the first;
* a spec error writes nothing while its neighbours still render;
* ``--prune`` deletes exactly the outputs whose source is gone, and nothing it
  did not record itself;
* every page the new code can produce passes ``check_page()`` with zero
  findings;
* the scaffolded ``engine_locator`` finds a real marketplace install, and
  refuses a foreign plugin whose engine carries the same three files.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

# Same deliberate choice as render.py: no stale bytecode beside the source.
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine"
sys.path.insert(0, str(ENGINE))

import cache                                                     # noqa: E402
import content_core                                              # noqa: E402
import design_system                                             # noqa: E402
import index as index_module                                     # noqa: E402
import scaffold                                                  # noqa: E402
from page_api import check_page                                  # noqa: E402
import kinds                                                     # noqa: E402
from kinds import checklist, questionnaire                       # noqa: E402

CHECKLIST_FIXTURE = (ROOT / "examples" / "checklist-project" / "docs"
                     / "checklists" / "2026-08-release.md")
CHECKLIST_REJECTED = (ROOT / "examples" / "checklist-project" / "docs"
                      / "rejected" / "duplicate-in-one-group.md")


def render(config_dir, *args):
    """Run the engine as the CLI does, and hand back its result verbatim."""
    return subprocess.run(
        [sys.executable, str(ENGINE / "render.py"), "--config-dir", str(config_dir), *args],
        capture_output=True, text=True, cwd=str(ROOT),
    )


def valid_spec(**over):
    spec = {
        "id": "sample",
        "title": "Sample",
        "sections": [{
            "title": "Only section",
            "questions": [
                {"id": "q01", "question": "Pick one",
                 "options": [{"key": "a", "label": "A"}, {"key": "b", "label": "B"}]},
                {"id": "q02", "question": "Say something", "type": "text"},
            ],
        }],
    }
    spec.update(over)
    return spec


class TempProject:
    """A minimal consuming project, thrown away when the test ends."""

    def __init__(self, kind=False):
        self.dir = Path(tempfile.mkdtemp(prefix="render-test-"))
        self.config = self.dir / ".render"
        (self.config / "pages").mkdir(parents=True)
        for name in ("config.py", "content.py"):
            shutil.copy(ROOT / "templates" / name, self.config / name)
        shutil.copy(ROOT / "templates" / "pages" / "__init__.py",
                    self.config / "pages" / "__init__.py")
        # What /render:init leaves behind, so a fixture is a real scaffold and
        # not a project the engine would rightly report as behind.
        scaffold.apply(self.config, scaffold.plan(self.config))

    def section_page(self, pid="dashboard"):
        target = self.config / "pages" / pid
        target.mkdir(parents=True, exist_ok=True)
        src = ROOT / "templates" / "pages" / "dashboard"
        shutil.copy(src / "__init__.py", target / "__init__.py")
        shutil.copy(src / "overview.py", target / "overview.py")
        # Long enough to clear check()'s "suspiciously empty section" rule —
        # the example section renders this file, so a stub would trip it.
        (self.dir / "README.md").write_text(
            "# Fixture Project\n\n"
            "A body with enough prose for the section to look like a real one.\n"
            "It carries a ✅ and a ⚠ so the status marks are exercised too.\n\n"
            "## A heading\n\n"
            "- a list item\n- another one\n- a third, for good measure\n\n"
            "One closing paragraph so the rendered section is comfortably past\n"
            "the minimum body length the structural check insists on.\n",
            encoding="utf-8")

    def kind_page(self, pid="survey", glob="questions/*.json"):
        target = self.config / "pages" / pid
        target.mkdir(parents=True, exist_ok=True)
        (target / "__init__.py").write_text(
            f'TITLE = "Survey"\nKIND = "questionnaire"\nSOURCES = "{glob}"\n',
            encoding="utf-8")
        (self.dir / "questions").mkdir(exist_ok=True)

    def spec(self, name, spec):
        path = self.dir / "questions" / f"{name}.json"
        path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def output(self, name):
        return self.config / "output" / name

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.project = TempProject()
        self.addCleanup(self.project.cleanup)


# --------------------------------------------------------- no regression ----

class SectionPagesUnchanged(ProjectCase):
    """0.2.0 is additive: a section page's bytes may not move."""

    def test_renders_and_checks_clean(self):
        self.project.section_page()
        result = render(self.project.config, "--all")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(render(self.project.config, "--check").returncode, 0)
        self.assertEqual(check_page(self.project.output("dashboard.html")
                                    .read_text(encoding="utf-8")), [])

    def test_second_run_rewrites_nothing(self):
        self.project.section_page()
        render(self.project.config, "--all")
        before = self.project.output("dashboard.html").read_text(encoding="utf-8")
        render(self.project.config, "--all")
        self.assertEqual(before,
                         self.project.output("dashboard.html").read_text(encoding="utf-8"))

    def test_extra_css_reaches_the_page_and_nothing_else(self):
        self.project.section_page()
        page = self.project.config / "pages" / "dashboard" / "__init__.py"
        page.write_text(page.read_text(encoding="utf-8")
                        + '\nEXTRA_CSS = "\\n.probe { color: var(--ink-2); }\\n"\n',
                        encoding="utf-8")
        render(self.project.config, "--all")
        html = self.project.output("dashboard.html").read_text(encoding="utf-8")
        self.assertIn(".probe { color: var(--ink-2); }", html)
        self.assertEqual(check_page(html), [])

    def test_extra_css_is_still_held_to_the_color_rule(self):
        html = ("<html><head><style>:root{--x:#fff}</style>"
                "<style>.probe{color:#ff0000}</style></head><body></body></html>")
        self.assertTrue(any("hex color" in f for f in check_page(html)))


# ------------------------------------------------------ page declaration ----

class PageDeclaration(ProjectCase):
    def declare(self, body):
        target = self.project.config / "pages" / "broken"
        target.mkdir(parents=True, exist_ok=True)
        (target / "__init__.py").write_text(body, encoding="utf-8")
        return render(self.project.config)

    def test_both_sections_and_kind_is_refused(self):
        r = self.declare('TITLE = "x"\nSECTIONS = []\nKIND = "questionnaire"\n'
                         'SOURCES = "q/*.json"\n')
        self.assertEqual(r.returncode, 1)
        self.assertIn("both SECTIONS and KIND", r.stderr)

    def test_neither_is_refused(self):
        r = self.declare('TITLE = "x"\n')
        self.assertEqual(r.returncode, 1)
        self.assertIn("neither SECTIONS nor KIND", r.stderr)

    def test_kind_without_sources_is_refused(self):
        r = self.declare('TITLE = "x"\nKIND = "questionnaire"\n')
        self.assertEqual(r.returncode, 1)
        self.assertIn("KIND without SOURCES", r.stderr)

    def test_sources_without_kind_is_refused(self):
        r = self.declare('TITLE = "x"\nSECTIONS = []\nSOURCES = "q/*.json"\n')
        self.assertEqual(r.returncode, 1)
        self.assertIn("SOURCES without KIND", r.stderr)

    def test_unknown_kind_names_the_known_ones(self):
        r = self.declare('TITLE = "x"\nKIND = "nosuch"\nSOURCES = "q/*.json"\n')
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown kind", r.stderr)
        self.assertIn("questionnaire", r.stderr)


# ---------------------------------------------------------------- family ----

class Families(ProjectCase):
    def test_one_output_per_spec(self):
        self.project.kind_page()
        self.project.spec("first", valid_spec(id="first"))
        self.project.spec("second", valid_spec(id="second", title="Second"))
        r = render(self.project.config, "--check")
        self.assertEqual(r.returncode, 0, r.stderr)
        for name in ("survey-first.html", "survey-second.html"):
            html = self.project.output(name).read_text(encoding="utf-8")
            self.assertEqual(check_page(html), [], name)

    def test_empty_glob_is_not_an_error(self):
        self.project.kind_page()
        r = render(self.project.config)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no spec matches", r.stdout)

    def test_single_instance_can_be_addressed(self):
        self.project.kind_page()
        self.project.spec("first", valid_spec(id="first"))
        self.project.spec("second", valid_spec(id="second"))
        render(self.project.config)
        r = render(self.project.config, "--page", "survey:second", "--only", "survey:second")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_unknown_instance_is_refused(self):
        self.project.kind_page()
        self.project.spec("first", valid_spec(id="first"))
        r = render(self.project.config, "--page", "survey:nope")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Unknown page", r.stderr)

    def test_colliding_stems_are_refused(self):
        self.project.kind_page(glob="questions/**/*.json")
        self.project.spec("clash", valid_spec(id="one"))
        nested = self.project.dir / "questions" / "sub"
        nested.mkdir(parents=True, exist_ok=True)
        (nested / "clash.json").write_text(json.dumps(valid_spec(id="two")),
                                           encoding="utf-8")
        r = render(self.project.config)
        self.assertEqual(r.returncode, 1)
        self.assertIn("share one instance name", r.stderr)

    def test_unchanged_specs_come_from_cache(self):
        self.project.kind_page()
        self.project.spec("first", valid_spec(id="first"))
        render(self.project.config)
        r = render(self.project.config)
        self.assertIn("unchanged", r.stdout)


class Pruning(ProjectCase):
    def setUp(self):
        super().setUp()
        self.project.kind_page()
        self.keep = self.project.spec("keep", valid_spec(id="keep"))
        self.drop = self.project.spec("drop", valid_spec(id="drop"))
        render(self.project.config)

    def test_orphan_is_reported_but_not_deleted_without_the_flag(self):
        self.drop.unlink()
        r = render(self.project.config)
        self.assertIn("without a source file", r.stdout)
        self.assertTrue(self.project.output("survey-drop.html").exists())

    def test_prune_deletes_exactly_the_orphan(self):
        self.drop.unlink()
        r = render(self.project.config, "--prune")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pruned", r.stdout)
        self.assertFalse(self.project.output("survey-drop.html").exists())
        self.assertTrue(self.project.output("survey-keep.html").exists())

    def test_prune_leaves_files_it_never_wrote(self):
        stranger = self.project.output("hand-written.html")
        stranger.write_text("<!-- not ours -->", encoding="utf-8")
        self.drop.unlink()
        render(self.project.config, "--prune")
        self.assertTrue(stranger.exists())

    def test_addressing_one_instance_still_sees_the_whole_glob(self):
        """--page narrows what is *built*, not what is enumerated, so the
        orphan list stays accurate."""
        self.drop.unlink()
        render(self.project.config, "--page", "survey:keep", "--prune")
        self.assertFalse(self.project.output("survey-drop.html").exists())
        self.assertTrue(self.project.output("survey-keep.html").exists())

    def test_a_run_that_never_visits_the_page_prunes_none_of_it(self):
        self.project.section_page()
        self.drop.unlink()
        render(self.project.config, "--page", "dashboard", "--prune")
        self.assertTrue(self.project.output("survey-drop.html").exists())


# ----------------------------------------------------- spec errors abort ----

class SpecErrorsAbort(ProjectCase):
    def test_bad_spec_writes_nothing_and_neighbours_still_render(self):
        self.project.kind_page()
        self.project.spec("good", valid_spec(id="good"))
        self.project.spec("bad", {"id": "bad", "title": "No sections"})
        r = render(self.project.config)
        self.assertEqual(r.returncode, 1)
        self.assertIn("SPEC", r.stderr)
        self.assertFalse(self.project.output("survey-bad.html").exists())
        self.assertTrue(self.project.output("survey-good.html").exists())

    def test_malformed_json_reports_a_position(self):
        self.project.kind_page()
        (self.project.dir / "questions" / "broken.json").write_text(
            '{"id": "x", "title": }', encoding="utf-8")
        r = render(self.project.config)
        self.assertEqual(r.returncode, 1)
        self.assertIn("not valid JSON", r.stderr)
        self.assertIn("line 1", r.stderr)

    def test_a_spec_that_goes_bad_keeps_its_previous_page(self):
        self.project.kind_page()
        path = self.project.spec("one", valid_spec(id="one"))
        render(self.project.config)
        before = self.project.output("survey-one.html").read_text(encoding="utf-8")
        path.write_text('{"id": "one", "title": "Broken now"}', encoding="utf-8")
        r = render(self.project.config)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(before,
                         self.project.output("survey-one.html").read_text(encoding="utf-8"))


# ------------------------------------------------------------- validator ----

class Validator(unittest.TestCase):
    """One case per class of malformed spec the schema claims to refuse."""

    def findings(self, spec):
        return questionnaire.validate(spec, Path("spec.json"))

    def assertRefused(self, spec, needle):
        found = self.findings(spec)
        self.assertTrue(found, f"expected a finding mentioning {needle!r}")
        self.assertTrue(any(needle in f for f in found),
                        f"{needle!r} not in {found}")

    def test_a_valid_spec_passes(self):
        self.assertEqual(self.findings(valid_spec()), [])

    def test_not_an_object(self):
        self.assertRefused([], "must be a JSON object")

    def test_missing_id(self):
        spec = valid_spec()
        del spec["id"]
        self.assertRefused(spec, "'id' is required")

    def test_id_charset(self):
        self.assertRefused(valid_spec(id="Not Valid"), "lowercase letters")

    def test_missing_title(self):
        spec = valid_spec()
        del spec["title"]
        self.assertRefused(spec, "'title' is required")

    def test_no_sections(self):
        self.assertRefused(valid_spec(sections=[]), "at least one section")

    def test_section_without_title(self):
        self.assertRefused(valid_spec(sections=[{"questions": [
            {"id": "q", "question": "?", "type": "text"}]}]), "'title' is required")

    def test_section_without_questions(self):
        self.assertRefused(valid_spec(sections=[{"title": "T", "questions": []}]),
                           "at least one entry")

    def test_duplicate_question_ids(self):
        spec = valid_spec()
        spec["sections"][0]["questions"][1]["id"] = "q01"
        self.assertRefused(spec, "duplicate question id")

    def test_single_needs_two_options(self):
        spec = valid_spec()
        spec["sections"][0]["questions"][0]["options"] = [{"key": "a", "label": "A"}]
        self.assertRefused(spec, "at least two options")

    def test_option_needs_a_key(self):
        spec = valid_spec()
        spec["sections"][0]["questions"][0]["options"][0] = {"label": "A"}
        self.assertRefused(spec, "'key' is required")

    def test_option_keys_are_unique(self):
        spec = valid_spec()
        spec["sections"][0]["questions"][0]["options"][1]["key"] = "a"
        self.assertRefused(spec, "option keys must be unique")

    def test_unknown_type(self):
        spec = valid_spec()
        spec["sections"][0]["questions"][0]["type"] = "dropdown"
        self.assertRefused(spec, "is unknown")

    def test_options_on_a_text_question(self):
        spec = valid_spec()
        spec["sections"][0]["questions"][1]["options"] = [{"key": "a", "label": "A"}]
        self.assertRefused(spec, "takes no options")

    def test_unit_outside_amount(self):
        spec = valid_spec()
        spec["sections"][0]["questions"][1]["unit"] = "€"
        self.assertRefused(spec, "belongs to an amount question")

    def test_unknown_key_anywhere(self):
        spec = valid_spec()
        spec["sections"][0]["questions"][0]["questoin"] = "typo"
        self.assertRefused(spec, "unknown key 'questoin'")

    def test_unknown_key_at_spec_level(self):
        self.assertRefused(valid_spec(langauge="de"), "unknown key 'langauge'")

    def test_meta_is_the_escape_hatch(self):
        spec = valid_spec()
        spec["sections"][0]["questions"][0]["meta"] = {"anything": ["at", "all"]}
        self.assertEqual(self.findings(spec), [])

    def test_show_if_to_a_missing_question(self):
        spec = valid_spec()
        spec["sections"][0]["questions"][1]["show-if"] = {"question": "nope",
                                                          "answer": ["a"]}
        self.assertRefused(spec, "not a question in this spec")

    def test_show_if_to_a_missing_option_key(self):
        spec = valid_spec()
        spec["sections"][0]["questions"][1]["show-if"] = {"question": "q01",
                                                          "answer": ["zz"]}
        self.assertRefused(spec, "which offers")

    def test_show_if_to_itself(self):
        spec = valid_spec()
        spec["sections"][0]["questions"][0]["show-if"] = {"question": "q01",
                                                          "answer": ["a"]}
        self.assertRefused(spec, "points at itself")

    def test_show_if_to_a_later_question(self):
        """Backwards-only is what makes a circular condition impossible."""
        spec = valid_spec()
        spec["sections"][0]["questions"][0]["options"] = [
            {"key": "a", "label": "A"}, {"key": "b", "label": "B"}]
        spec["sections"][0]["questions"].append(
            {"id": "q03", "question": "Later",
             "options": [{"key": "y", "label": "Y"}, {"key": "n", "label": "N"}]})
        spec["sections"][0]["questions"][0]["show-if"] = {"question": "q03",
                                                          "answer": ["y"]}
        self.assertRefused(spec, "asked later")

    def test_show_if_to_a_question_without_options(self):
        spec = valid_spec()
        spec["sections"][0]["questions"].append(
            {"id": "q03", "question": "Third", "type": "text",
             "show-if": {"question": "q02", "answer": ["a"]}})
        self.assertRefused(spec, "no options to match against")

    def test_every_finding_is_reported_at_once(self):
        spec = {"id": "Bad Id", "sections": [{"questions": []}]}
        found = self.findings(spec)
        self.assertGreaterEqual(len(found), 3, found)


# ------------------------------------------------------- rendered output ----

class RenderedQuestionnaire(ProjectCase):
    def setUp(self):
        super().setUp()
        self.project.kind_page()
        spec = valid_spec(id="rendered")
        spec["sections"][0]["questions"][1]["show-if"] = {"question": "q01",
                                                          "answer": ["a"]}
        self.project.spec("rendered", spec)
        self.assertEqual(render(self.project.config, "--check").returncode, 0)
        self.html = self.project.output("survey-rendered.html").read_text(encoding="utf-8")

    def test_self_contained(self):
        self.assertEqual(check_page(self.html), [])

    def test_every_question_is_in_the_document(self):
        """11.2: content is rendered, not assembled in the browser."""
        self.assertIn("Pick one", self.html)
        self.assertIn("Say something", self.html)
        self.assertEqual(self.html.count("data-screen='question'"), 2)

    def test_the_no_script_fallback_exists(self):
        self.assertEqual(self.html.count("<noscript>"), 1)
        self.assertIn("display: block !important", self.html)

    def test_the_data_block_carries_no_display_text_of_its_own(self):
        block = self.html.split("id='q-data'>")[1].split("</script>")[0]
        payload = json.loads(block.replace("\\u003c", "<").replace("\\u003e", ">")
                             .replace("\\u0026", "&"))
        self.assertEqual([q["id"] for q in payload["questions"]], ["q01", "q02"])
        self.assertNotIn("meta", json.dumps(payload))

    def test_meta_never_reaches_the_page(self):
        spec = valid_spec(id="secretive")
        spec["sections"][0]["questions"][0]["meta"] = {"routes-to": "nowhere-visible"}
        self.project.spec("secretive", spec)
        render(self.project.config)
        html = self.project.output("survey-secretive.html").read_text(encoding="utf-8")
        self.assertNotIn("nowhere-visible", html)

    def test_nothing_is_mandatory(self):
        """Both ways past a question, and a note, on every one of them."""
        for needle in ("data-mark='unclear'", "data-mark='skipped'", "data-note-open="):
            self.assertEqual(self.html.count(needle), 2, needle)

    def test_the_handback_block_is_present_and_empty(self):
        self.assertIn("id='q-handback'", self.html)
        self.assertIn("class='handback'", self.html)

    def test_the_footer_says_where_the_answers_live(self):
        self.assertIn("stay in this browser", self.html)

    def test_the_kind_check_catches_a_mismatch(self):
        spec = valid_spec(id="rendered")
        findings = questionnaire.check(spec, "<html></html>")
        self.assertTrue(any("data block" in f for f in findings))
        self.assertTrue(any("hand-back" in f for f in findings))


# ----------------------------------------------------------- fingerprints ----

class Fingerprints(unittest.TestCase):
    """Content-addressed identity (design-manual.md, 11.7). Every case here is
    an edit that must, or must not, cost an item its saved state."""

    def fp(self, *parts):
        return content_core.fingerprint(*parts)

    def test_six_hex_characters(self):
        value = self.fp("Collect the receipts")
        self.assertRegex(value, r"\A[0-9a-f]{6}\Z")

    def test_different_text_is_a_different_fingerprint(self):
        self.assertNotEqual(self.fp("Collect the receipts"),
                            self.fp("Collect the statements"))

    def test_inline_markup_does_not_change_it(self):
        plain = self.fp("Collect the receipts from the drawer")
        for dressed in ("Collect the **receipts** from the drawer",
                        "Collect the *receipts* from the drawer",
                        "Collect the `receipts` from the drawer",
                        "Collect the [receipts](docs/receipts.md) from the drawer"):
            self.assertEqual(plain, self.fp(dressed), dressed)

    def test_strikethrough_does_not_change_it(self):
        """Correction 2 × 4: if ``~~…~~`` is state, it cannot sit in the hash
        base — marking an item obsolete would discard its tick."""
        self.assertEqual(self.fp("Superseded by the new process"),
                         self.fp("~~Superseded by the new process~~"))

    def test_whitespace_is_collapsed(self):
        self.assertEqual(self.fp("Collect the receipts"),
                         self.fp("  Collect   the\n  receipts  "))

    def test_extra_parts_cannot_be_forged_from_the_text(self):
        """Tier 2 qualifies with the heading; a text that merely *contains* the
        heading must not land on the same fingerprint."""
        self.assertNotEqual(self.fp("Ask about it", "Records"),
                            self.fp("Ask about it Records"))
        self.assertNotEqual(self.fp("Ask about it", "Records"),
                            self.fp("Ask about it"))

    def test_control_characters_cannot_forge_the_separator(self):
        self.assertNotEqual(self.fp("Ask about it\x1fRecords"),
                            self.fp("Ask about it", "Records"))

    def test_strip_inline_is_exported_for_reuse(self):
        self.assertEqual(content_core.strip_inline("**Archive** — a *record*"),
                         "Archive — a record")


class VolatileInstances(unittest.TestCase):
    """A kind page with a countdown may not be served from yesterday's cache."""

    def key(self, volatile, day):
        real = cache.date

        class Frozen(real):
            @classmethod
            def today(cls):
                return real(2026, 8, day)

        cache.date = Frozen
        try:
            return cache.instance_key("shared", "page", "kind", Path(__file__), volatile)
        finally:
            cache.date = real

    def test_a_stable_instance_keys_the_same_on_another_day(self):
        self.assertEqual(self.key(False, 2), self.key(False, 3))

    def test_a_volatile_instance_keys_differently_on_another_day(self):
        self.assertNotEqual(self.key(True, 2), self.key(True, 3))

    def test_volatile_is_read_in_one_place_for_status_and_build(self):
        """--status and the build must never key an instance differently."""
        source = (ENGINE / "render.py").read_text(encoding="utf-8")
        keyed = source.count("cache.instance_key(")
        asked = source.count("instance_volatile(page, kind)") - 1   # minus the def
        self.assertEqual(keyed, 2, "instance_key is computed in two places")
        self.assertEqual(asked, keyed, "every one of them asks whether it is volatile")


class AppChromeInPrint(unittest.TestCase):
    """6b: printed, an interactive page is its content, never its controls."""

    def test_the_positioned_components_are_hidden(self):
        block = design_system.APP_CSS.split("@media print")[-1]
        for needle in (".progress", ".actionbar", ".toast"):
            self.assertIn(needle, block, needle)

    def test_base_css_already_covered_the_rest(self):
        self.assertIn("nav.toc, .btn { display: none; }", design_system.BASE_CSS)


class ContentAddressedStore(unittest.TestCase):
    """The garbage-collect step is JavaScript, so what is asserted here is its
    contract; the behaviour itself is driven in a real browser."""

    def test_make_still_works_with_one_argument(self):
        self.assertIn("function make(ns, opts)", design_system.STATE_JS)
        self.assertIn("(opts && opts.keys) || null", design_system.STATE_JS)

    def test_collection_is_persisted_not_merely_computed(self):
        self.assertIn("if (collect(data)) store.write(data)", design_system.STATE_JS)


class CheckRowComponent(unittest.TestCase):
    """6.26 — the row the checklist kind is built from."""

    def row(self, **over):
        args = {"rid": "a3f91c", "text": "Collect the receipts"}
        args.update(over)
        return design_system.check_row(**args)

    def test_open_row_is_not_pressed_and_offers_a_note(self):
        html = self.row()
        self.assertIn("aria-pressed='false'", html)
        self.assertIn("data-note-open='a3f91c'", html)
        self.assertIn("data-check-row='a3f91c'", html)

    def test_done_row_is_pressed(self):
        self.assertIn("aria-pressed='true'", self.row(state="done"))

    def test_obsolete_disables_the_tick_and_says_the_word(self):
        """Strikethrough alone would be a visual-only signal (2.3)."""
        html = self.row(state="obsolete")
        self.assertIn(" disabled>", html)
        self.assertIn("obsolete</span>", html)

    def test_every_state_still_reaches_its_note(self):
        for state in ("open", "done", "obsolete"):
            self.assertIn("data-note-open=", self.row(state=state), state)

    def test_the_tick_is_labelled_by_the_instruction(self):
        html = self.row()
        self.assertIn("aria-labelledby='ck-a3f91c-text'", html)
        self.assertIn("id='ck-a3f91c-text'", html)

    def test_it_passes_the_page_checks(self):
        html = f"<html><head><style>{design_system.TOKENS}</style></head><body>" \
               f"{self.row(state='done', detail='<p>x</p>')}</body></html>"
        self.assertEqual(check_page(html), [])


# --------------------------------------------------- the checklist parser ----

class ChecklistFixture(unittest.TestCase):
    """One case per correction the design owes its existence to, against the
    deliberately messy fixture. Every one of them is a bug a tidy example
    passes and a real maintained file fails."""

    @classmethod
    def setUpClass(cls):
        cls.doc = checklist.load(CHECKLIST_FIXTURE)
        cls.by_text = {i["text"]: i for i in cls.doc["items"]}

    def reload(self, source: str):
        """Parse an edited copy of the fixture without touching the fixture."""
        work = Path(tempfile.mkdtemp(prefix="checklist-edit-"))
        self.addCleanup(shutil.rmtree, work, True)
        path = work / "edited.md"
        path.write_text(source, encoding="utf-8")
        return checklist.load(path)

    def edited(self, old: str, new: str):
        source = CHECKLIST_FIXTURE.read_text(encoding="utf-8")
        self.assertIn(old, source, f"fixture no longer contains {old!r}")
        return self.reload(source.replace(old, new, 1))

    # -- the document parses at all ------------------------------------------

    def test_the_fixture_is_usable(self):
        self.assertEqual(checklist.validate(self.doc, CHECKLIST_FIXTURE), [])

    def test_frontmatter_carries_the_deadline_and_the_markers(self):
        self.assertEqual(self.doc["deadline"], date(2026, 8, 31))
        self.assertEqual(self.doc["deadline_label"], "Release window closes")
        self.assertEqual(self.doc["exclude"], ("\U0001f5c4️", "**Superseded"))
        self.assertEqual(self.doc["marker"], "RELEASE CHECKLIST CHANGES")

    # -- correction 1: exclusion is per block ---------------------------------

    def test_exclusion_consumes_nothing(self):
        """An excluded block issues no fingerprint and lands in no total: the
        pipeline is parse → exclude → fingerprint → render, count."""
        self.assertEqual(self.doc["excluded"], 3)     # one item, two paragraphs
        for item in self.doc["items"]:
            self.assertNotIn("\U0001f5c4", item["text"])
        blob = repr(self.doc["groups"])
        for gone in ("printed sign-off sheet", "Kept for the record",
                     "release calendar used to live here"):
            self.assertNotIn(gone, blob, gone)

    def test_exclusion_is_per_block_not_per_section(self):
        """The excluded item's neighbours in the same group are all still
        there — this is not drop_blocks."""
        group = next(g for g in self.doc["groups"] if g["title"] == "Before the branch")
        texts = [b["text"] for b in group["blocks"] if b["kind"] == "item"]
        self.assertIn("Agree what goes in and what waits", texts)
        self.assertIn("Check the dependency licences", texts)

    def test_removing_the_markers_brings_every_block_back(self):
        back = self.edited('exclude: ["🗄️", "**Superseded"]\n', "")
        self.assertEqual(back["excluded"], 0)
        self.assertEqual(len(back["items"]), len(self.doc["items"]) + 1)
        self.assertEqual(back["counts"]["open"], self.doc["counts"]["open"] + 1)

    def test_an_excluded_item_is_matched_without_its_variation_selector(self):
        """The selector is invisible in an editor; a marker that silently stops
        matching because of it is exactly the failure nobody would find."""
        stripped = self.edited("- [ ] 🗄️ Post the printed",
                               "- [ ] \U0001f5c4 Post the printed")
        self.assertEqual(stripped["excluded"], 3)

    # -- correction 2: the fingerprint base is the instruction only -----------

    def test_annotation_edit_preserves_state(self):
        """Adding navigation help is not a changed task."""
        after = self.edited("path: Deployments › Releases › History",
                            "path: Deployments › Releases › Rollbacks")
        self.assertEqual(self.fp("Know how to roll back"),
                         self.fp("Know how to roll back", after))

    def test_adding_a_due_date_preserves_state(self):
        after = self.edited("- [ ] Read the changelog end to end",
                            "- [ ] Read the changelog end to end\n      due: 2026-08-25")
        self.assertEqual(self.fp("Read the changelog end to end"),
                         self.fp("Read the changelog end to end", after))

    def test_adding_detail_preserves_state(self):
        after = self.edited("- [ ] Write the migration note",
                            "- [ ] Write the migration note\n      Two paragraphs is plenty.")
        self.assertEqual(self.fp("Write the migration note"),
                         self.fp("Write the migration note", after))

    def test_strikethrough_preserves_state(self):
        """Corrections 2 and 4 interact: if ``~~…~~`` is state it cannot sit in
        the hash base, or marking an item obsolete discards its tick."""
        after = self.edited("- [ ] Know how to roll back",
                            "- ~~[ ] Know how to roll back~~")
        moved = next(i for i in after["items"] if i["text"] == "Know how to roll back")
        self.assertEqual(moved["state"], "obsolete")
        self.assertEqual(self.fp("Know how to roll back"), moved["fp"])

    def test_rewording_an_item_does_change_it(self):
        """The other half of the contract: state evaporates precisely because
        the content it was about changed."""
        after = self.edited("- [ ] Tag the release", "- [ ] Tag the release candidate")
        self.assertNotIn(self.fp("Tag the release"),
                         [i["fp"] for i in after["items"]])

    def fp(self, text, doc=None):
        doc = doc or self.doc
        return next(i["fp"] for i in doc["items"] if i["text"] == text)

    # -- correction 3: interleaved prose and subheads render in place ---------

    def test_prose_renders_in_position(self):
        group = next(g for g in self.doc["groups"] if g["title"] == "Before the branch")
        shape = [b["kind"] for b in group["blocks"]]
        self.assertEqual(shape, ["prose", "item", "item", "prose", "prose",
                                 "item", "item", "prose", "prose", "subhead",
                                 "item", "item", "item"])

    def test_a_bold_only_line_is_its_own_block(self):
        group = next(g for g in self.doc["groups"] if g["title"] == "Before the branch")
        prose = [b["md"] for b in group["blocks"] if b["kind"] == "prose"]
        self.assertIn("**Both runs matter**", prose)

    def test_a_plain_list_is_prose_not_items(self):
        """A `-` line without a checkbox must not be counted as an item."""
        blob = "\n".join(b["md"] for g in self.doc["groups"]
                         for b in g["blocks"] if b["kind"] == "prose")
        self.assertIn("- the release notes live with the tag", blob)
        self.assertNotIn("the release notes live with the tag",
                         " ".join(i["text"] for i in self.doc["items"]))

    def test_a_preamble_before_the_first_group_is_kept(self):
        first = self.doc["groups"][0]
        self.assertIsNone(first["title"])
        self.assertTrue(first["blocks"])

    def test_the_subhead_stays_inside_its_group(self):
        item = self.by_text["Write the migration note"]
        self.assertEqual(item["group"], "Before the branch")
        self.assertEqual(item["subhead"], "Only when the release is a major one")

    def test_a_declared_annotation_is_one_and_an_unknown_key_is_detail(self):
        """Unknown keys pass through rather than erroring — this is a document
        a person owns."""
        item = self.by_text["Check the dependency licences"]
        self.assertEqual(item["annotations"]["path"], "Settings › Compliance › Licences")
        self.assertEqual(item["due"], date(2026, 8, 20))
        self.assertIn("owner: whoever cut the previous release", item["detail"])
        self.assertNotIn("owner", item["annotations"])

    # -- correction 4: item state is not binary ------------------------------

    def test_both_spellings_of_obsolete_are_obsolete(self):
        self.assertEqual(self.by_text["Announce the deprecation window"]["state"],
                         "obsolete")
        self.assertEqual(self.by_text["Ship the compatibility shim"]["state"],
                         "obsolete")

    def test_strikethrough_beats_the_checkbox(self):
        """``[x] ~~…~~`` is obsolete, not done — an item somebody struck out is
        not progress just because it was once ticked."""
        self.assertEqual(self.by_text["Ship the compatibility shim"]["state"],
                         "obsolete")

    def test_obsolete_is_outside_the_ratio(self):
        counts = self.doc["counts"]
        self.assertEqual(counts, {"open": 7, "done": 1, "obsolete": 2})
        self.assertEqual(self.doc["counted"], counts["open"] + counts["done"])
        self.assertEqual(len(self.doc["items"]),
                         counts["open"] + counts["done"] + counts["obsolete"])

    def test_a_partial_strikethrough_is_not_a_state(self):
        after = self.edited("- [ ] Tag the release",
                            "- [ ] Tag ~~the~~ release, ~~finally~~")
        moved = next(i for i in after["items"] if i["text"].startswith("Tag "))
        self.assertEqual(moved["state"], "open")

    # -- fingerprint tiers ----------------------------------------------------

    def test_tier_2_separates_identical_text_in_different_groups(self):
        before = self.by_text["Run the full test suite"]
        after = self.by_text["Run the **full** test suite"]
        self.assertEqual((before["tier"], after["tier"]), (2, 2))
        self.assertNotEqual(before["fp"], after["fp"])

    def test_tier_2_is_stable_across_an_unrelated_edit(self):
        """Only the colliding pair is group-qualified, so a heading rename may
        not move anything that was not colliding."""
        after = self.edited("## Rollback", "## Rolling back")
        for text in ("Tag the release", "Write the migration note"):
            self.assertEqual(self.fp(text), self.fp(text, after), text)
        self.assertEqual(self.fp("Run the full test suite"),
                         self.fp("Run the full test suite", after))

    def test_an_uncolliding_item_is_never_group_qualified(self):
        after = self.edited("## After the branch", "## Once the branch exists")
        self.assertEqual(self.fp("Tag the release"), self.fp("Tag the release", after))

    def test_tier_3_is_reported_and_refused(self):
        doc = checklist.load(CHECKLIST_REJECTED)
        findings = checklist.validate(doc, CHECKLIST_REJECTED)
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("read exactly the same", findings[0])
        self.assertIn("Run the full test suite", findings[0])

    def test_tier_3_still_produces_distinct_ids(self):
        """The positional fallback is computed — that is how the collision is
        found — it is simply never rendered."""
        doc = checklist.load(CHECKLIST_REJECTED)
        colliding = [i for i in doc["items"] if i["tier"] == 3]
        self.assertEqual(len(colliding), 2)
        self.assertEqual(len({i["fp"] for i in colliding}), 2)

    # -- drift ----------------------------------------------------------------

    def test_a_changed_source_produces_a_different_based_on(self):
        after = self.edited("- [ ] Tag the release", "- [ ] Tag the release build")
        self.assertNotEqual(self.doc["source_fp"], after["source_fp"])

    def test_reformatting_alone_does_not_read_as_drift(self):
        """``based-on`` is normalised, so re-wrapping a paragraph is not a
        reason to refuse a diff."""
        source = CHECKLIST_FIXTURE.read_text(encoding="utf-8")
        self.assertEqual(self.doc["source_fp"],
                         self.reload(source.replace("\n\n## Rollback",
                                                    "\n\n\n## Rollback"))["source_fp"])


class ChecklistProject(ProjectCase):
    """The rendered half, against the same messy fixture."""

    @classmethod
    def setUpClass(cls):
        cls.example = ROOT / "examples" / "checklist-project"

    def setUp(self):
        super().setUp()
        self.work = Path(tempfile.mkdtemp(prefix="checklist-project-"))
        self.addCleanup(shutil.rmtree, self.work, True)
        shutil.copytree(self.example, self.work / "project")
        self.config = self.work / "project" / ".render"
        self.source = (self.work / "project" / "docs" / "checklists"
                       / "2026-08-release.md")

    def render_page(self, *args):
        result = render(self.config, "--all", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return (self.config / "output" / "checklist-2026-08-release.html") \
            .read_text(encoding="utf-8")

    def doc(self):
        return checklist.load(self.source)

    def test_it_renders_and_checks(self):
        result = render(self.config, "--all", "--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(check_page(self.render_page()), [])

    def test_the_kind_check_returns_nothing_for_what_it_produces(self):
        html = self.render_page()
        self.assertEqual(checklist.check(self.doc(), html), [])

    def test_every_rendered_item_carries_its_fingerprint(self):
        html = self.render_page()
        rendered = re.findall(r"data-check-row='([^']*)'", html)
        self.assertEqual(sorted(rendered), sorted(i["fp"] for i in self.doc()["items"]))
        self.assertEqual(len(set(rendered)), len(rendered))

    def test_the_progress_denominator_leaves_obsolete_out(self):
        html = self.render_page()
        doc = self.doc()
        found = re.search(r"role='progressbar'[^>]*aria-valuemax='(\d+)'", html)
        self.assertEqual(int(found.group(1)),
                         doc["counts"]["open"] + doc["counts"]["done"])
        self.assertLess(int(found.group(1)), len(doc["items"]))

    def test_exclusion_reaches_no_part_of_the_page(self):
        """The other half of "exclusion consumes nothing": not the markup, not
        the data block, not the hand-back."""
        html = self.render_page()
        for gone in ("Post the printed sign-off sheet", "Kept for the record",
                     "release calendar used to live here"):
            self.assertNotIn(gone, html, gone)
        self.assertNotIn("\U0001f5c4", html)

    def test_prose_renders_between_the_rows_it_stood_between(self):
        html = self.render_page()
        order = [m.group(0) for m in re.finditer(
            r"data-check-row='([^']*)'|Both runs matter|Only when the release", html)]
        doc = self.doc()
        fp = {i["text"]: i["fp"] for i in doc["items"]}
        self.assertEqual(
            order[:6],
            [f"data-check-row='{fp['Agree what goes in and what waits']}'",
             f"data-check-row='{fp['Check the dependency licences']}'",
             "Both runs matter",
             f"data-check-row='{fp['Run the full test suite']}'",
             f"data-check-row='{fp['Read the changelog end to end']}'",
             "Only when the release"])

    def test_an_annotation_becomes_its_component(self):
        html = self.render_page()
        self.assertIn("class='crumbs'", html)
        self.assertIn("Compliance", html)
        self.assertIn("due 2026-08-20", html)

    def test_an_unknown_annotation_key_reaches_the_page_as_detail(self):
        html = self.render_page()
        self.assertIn("owner: whoever cut the previous release", html)

    def test_the_data_block_carries_no_excluded_content(self):
        html = self.render_page()
        block = html.split("id='ck-data'>")[1].split("</script>")[0]
        payload = json.loads(block.replace("\\u003c", "<").replace("\\u003e", ">")
                             .replace("\\u0026", "&"))
        self.assertEqual([i["fp"] for i in payload["items"]],
                         [i["fp"] for i in self.doc()["items"]])
        self.assertNotIn("Kept for the record", json.dumps(payload))
        self.assertEqual(payload["basedOn"], self.doc()["source_fp"])

    def test_the_page_never_writes_to_the_source_file(self):
        before = self.source.read_bytes()
        self.render_page()
        self.assertEqual(before, self.source.read_bytes())

    def test_a_countdown_page_is_volatile(self):
        """A deadline moves without the file moving, so the instance may not be
        served from yesterday's cache."""
        self.assertTrue(checklist.VOLATILE)

    def test_a_document_without_a_deadline_still_leads_with_one_number(self):
        source = self.source.read_text(encoding="utf-8")
        self.source.write_text(source.replace("deadline: 2026-08-31\n", ""),
                               encoding="utf-8")
        html = self.render_page()
        self.assertEqual(checklist.check(self.doc(), html), [])
        self.assertEqual(html.count("class='focus"), 1)
        self.assertEqual(check_page(html), [])

    def test_a_deadline_close_enough_to_matter_says_so_in_a_word(self):
        """2.3: colour never carries a statement on its own."""
        source = self.source.read_text(encoding="utf-8")
        soon = (date.today() + timedelta(days=2)).isoformat()
        self.source.write_text(source.replace("deadline: 2026-08-31",
                                              f"deadline: {soon}"), encoding="utf-8")
        html = self.render_page()
        self.assertIn("focus--warn", html)
        self.assertIn("Days left</span>", html)

    def test_an_overdue_deadline_counts_upwards(self):
        source = self.source.read_text(encoding="utf-8")
        past = (date.today() - timedelta(days=3)).isoformat()
        self.source.write_text(source.replace("deadline: 2026-08-31",
                                              f"deadline: {past}"), encoding="utf-8")
        html = self.render_page()
        self.assertIn("focus--crit", html)
        self.assertIn("Days overdue", html)
        self.assertIn(">3</div>", html)

    def test_the_deadline_falls_back_to_the_page_when_the_document_is_silent(self):
        source = self.source.read_text(encoding="utf-8")
        self.source.write_text(source.replace("deadline: 2026-08-31\n", ""),
                               encoding="utf-8")
        page = self.config / "pages" / "checklist" / "__init__.py"
        page.write_text(page.read_text(encoding="utf-8") + '\nDEADLINE = "2026-12-24"\n',
                        encoding="utf-8")
        self.assertIn("2026-12-24", self.render_page())

    def test_markers_fall_back_to_the_project_when_the_document_is_silent(self):
        source = self.source.read_text(encoding="utf-8")
        self.source.write_text(source.replace('exclude: ["🗄️", "**Superseded"]\n', ""),
                               encoding="utf-8")
        page = self.config / "pages" / "checklist" / "__init__.py"
        page.write_text(page.read_text(encoding="utf-8")
                        + '\nEXCLUDE_MARKERS = ("\\U0001f5c4\\ufe0f",)\n', encoding="utf-8")
        html = self.render_page()
        self.assertNotIn("Post the printed sign-off sheet", html)
        # Only the project's marker applies — the document's second one is gone
        # with the line that declared it.
        self.assertIn("release calendar used to live here", html)

    def test_the_overview_can_be_kept_in_step_with_the_list(self):
        """11.6: a focus card and tiles left at the rendered numbers would
        contradict the progress bar the moment anything is ticked."""
        html = self.render_page()
        for hook in ("id='ck-overview'", "data-tile='open'", "data-tile='done'",
                     "id='ck-next'", "data-group-open=", "data-share=",
                     "class='meter-row'"):
            self.assertIn(hook, html, hook)
        self.assertEqual(html.count("<section class='ck-group' data-group="), 3)

    def test_the_check_catches_an_overview_that_cannot_be_kept_in_step(self):
        """A change to tile() that dropped the hook must fail loudly rather
        than leave a stale number on an interactive page."""
        html = self.render_page().replace("data-tile='done'", "")
        findings = checklist.check(self.doc(), html)
        self.assertTrue(any("cannot be kept in step" in f for f in findings), findings)

    def test_the_data_block_carries_the_due_dates_the_script_orders_by(self):
        html = self.render_page()
        block = html.split("id='ck-data'>")[1].split("</script>")[0]
        payload = json.loads(block.replace("\\u003c", "<").replace("\\u003e", ">")
                             .replace("\\u0026", "&"))
        dated = {i["t"]: i.get("due") for i in payload["items"] if i.get("due")}
        self.assertEqual(dated, {"Check the dependency licences": "2026-08-20",
                                 "Tag the release": "2026-08-28"})

    def test_the_check_catches_a_page_that_lost_its_overview(self):
        findings = checklist.check(self.doc(), "<html></html>")
        self.assertTrue(any("overview is missing" in f for f in findings), findings)
        self.assertTrue(any("hand-back block is missing" in f for f in findings), findings)

    def test_the_check_catches_an_excluded_block_that_got_through(self):
        html = self.render_page().replace(
            "</main>", "<p>Kept for the record: the sheet above was retired two "
                       "years ago and is listed</p></main>")
        findings = checklist.check(self.doc(), html)
        self.assertTrue(any("excluded block reached the page" in f for f in findings),
                        findings)

    def test_a_refused_document_writes_nothing(self):
        shutil.copy(CHECKLIST_REJECTED,
                    self.work / "project" / "docs" / "checklists" / "clash.md")
        result = render(self.config, "--all")
        self.assertEqual(result.returncode, 1)
        self.assertIn("read exactly the same", result.stderr)
        self.assertFalse((self.config / "output" / "checklist-clash.html").exists())
        # The neighbour still renders — one bad document is not a bad project.
        self.assertTrue((self.config / "output"
                         / "checklist-2026-08-release.html").exists())


class ChecklistWithoutGroups(unittest.TestCase):
    """A document that never writes a `##` heading is an ordinary checklist,
    and every one of its items has to reach the page. The blocks before the
    first group are also where prose and items can interleave, so this is the
    one place the renderer has to keep document order rather than sort by
    kind."""

    def render(self, source):
        """The whole page, body and tail — ``check()`` reads both."""
        work = Path(tempfile.mkdtemp(prefix="checklist-flat-"))
        self.addCleanup(shutil.rmtree, work, True)
        path = work / "doc.md"
        path.write_text(source, encoding="utf-8")
        spec = checklist.load(path)
        self.assertEqual(checklist.validate(spec, path), [])
        ctx = kinds.BuildContext(object(), "lists", "doc", path,
                                 dict(checklist.STRINGS))
        body, tail = checklist.build(spec, ctx)
        return spec, body + tail

    def rows(self, html):
        return re.findall(r"data-check-row='([^']*)'", html)

    def row_at(self, spec, html, text):
        """Where an item's own row sits. Not where its text first appears —
        the overview names the next open item above every section, so a plain
        text search would compare against that copy instead."""
        fp = next(i["fp"] for i in spec["items"] if i["text"] == text)
        return html.index(f"data-check-row='{fp}'")

    FLAT = ("---\ntitle: T\n---\n\n# T\n\n"
            "- [x] Ship the build\n- [ ] Tell everyone about it\n")

    def test_every_item_reaches_the_page(self):
        spec, html = self.render(self.FLAT)
        self.assertEqual(sorted(self.rows(html)),
                         sorted(i["fp"] for i in spec["items"]))

    def test_the_kinds_own_check_agrees(self):
        """The assertion that caught this: rendered rows == fingerprints
        issued. It has to hold for a flat document too."""
        spec, html = self.render(self.FLAT)
        self.assertEqual(checklist.check(spec, html), [])

    def test_the_ungrouped_items_get_no_invented_group(self):
        _, html = self.render(self.FLAT)
        self.assertIn("<section class='ck-group'>", html)
        self.assertNotIn("data-group=", html)
        self.assertNotIn(checklist.STRINGS["ck_group_kicker"], html)

    def test_an_opening_paragraph_stays_above_the_overview(self):
        """A document that introduces itself and then names its groups keeps
        reading the way it did — the lead is what the change must not move."""
        _, html = self.render(
            "---\ntitle: T\n---\n\n# T\n\nWhat this list is for.\n\n"
            "## Build\n\n- [ ] Bump the version\n")
        self.assertIn("ck-lead", html)
        self.assertLess(html.index("What this list is for."),
                        html.index("id='ck-overview'"))

    def test_prose_between_items_keeps_its_place(self):
        spec, html = self.render("---\ntitle: T\n---\n\n# T\n\n- [ ] Bump the version\n\n"
                                 "An explanation of what comes next.\n\n"
                                 "- [ ] Tag the commit\n")
        self.assertNotIn("ck-lead", html)
        prose = html.index("An explanation of what comes next.")
        self.assertLess(self.row_at(spec, html, "Bump the version"), prose)
        self.assertLess(prose, self.row_at(spec, html, "Tag the commit"))

    def test_a_subhead_before_the_first_item_heads_it(self):
        spec, html = self.render("---\ntitle: T\n---\n\n# T\n\n### Once it is out\n\n"
                                 "- [ ] Tell everyone about it\n")
        self.assertNotIn("ck-lead", html)
        self.assertLess(html.index("Once it is out"),
                        self.row_at(spec, html, "Tell everyone about it"))

    def test_loose_items_and_named_groups_coexist(self):
        spec, html = self.render("---\ntitle: T\n---\n\n# T\n\n"
                                 "- [ ] Read the release notes\n\n"
                                 "## Build\n\n- [ ] Bump the version\n")
        self.assertEqual(sorted(self.rows(html)),
                         sorted(i["fp"] for i in spec["items"]))
        self.assertEqual(checklist.check(spec, html), [])
        # The unnamed blocks come first, as the document wrote them.
        self.assertLess(self.row_at(spec, html, "Read the release notes"),
                        self.row_at(spec, html, "Bump the version"))


class ChecklistRefusals(unittest.TestCase):
    """Strict about structure, permissive about prose."""

    def load(self, source):
        work = Path(tempfile.mkdtemp(prefix="checklist-bad-"))
        self.addCleanup(shutil.rmtree, work, True)
        path = work / "doc.md"
        path.write_text(source, encoding="utf-8")
        return checklist.validate(checklist.load(path), path)

    def test_a_document_with_no_items_is_refused(self):
        found = self.load("---\ntitle: T\n---\n\nOnly prose here.\n")
        self.assertTrue(any("no checklist items" in f for f in found), found)

    def test_an_unparseable_deadline_is_refused(self):
        found = self.load("---\ntitle: T\ndeadline: 31.08.2026\n---\n\n- [ ] a\n")
        self.assertTrue(any("not an ISO date" in f for f in found), found)

    def test_an_unparseable_due_date_is_refused(self):
        found = self.load("---\ntitle: T\n---\n\n- [ ] a\n      due: next Tuesday\n")
        self.assertTrue(any("not an ISO date" in f for f in found), found)

    def test_an_unusable_exclude_list_is_refused(self):
        found = self.load("---\ntitle: T\nexclude: 🗄️\n---\n\n- [ ] a\n")
        self.assertTrue(any("must be a list in brackets" in f for f in found), found)

    def test_prose_the_parser_did_not_anticipate_is_not_refused(self):
        """The deliberate opposite of the questionnaire's strict-unknown-keys:
        a document a person maintains cannot be rejected for containing a
        paragraph."""
        self.assertEqual(self.load(
            "---\ntitle: T\n---\n\n> a quote\n\n| a | table |\n|---|---|\n| 1 | 2 |\n\n"
            "```\na code block\n```\n\n#### a deep heading\n\n- [ ] a\n"
            "      strange: an unknown annotation key\n"), [])

    def test_every_finding_is_reported_at_once(self):
        found = self.load("---\ntitle: T\ndeadline: soon\nexclude: nope\n---\n\n"
                          "Only prose.\n")
        self.assertGreaterEqual(len(found), 3, found)


# ---------------------------------------------------- the hand-back grammar ----

class HandbackCli(unittest.TestCase):
    """``docs/handback.md`` documents the grammar; ``scripts/handback.py``
    is the shipped reference parser. The worked sample in the doc is run
    through the script here, so the two cannot drift: the doc's sample is
    the fixture the parser is held to."""

    @classmethod
    def setUpClass(cls):
        text = (ROOT / "docs" / "handback.md").read_text(encoding="utf-8")
        # Grammar templates carry <placeholders>; the worked samples never do.
        blocks = re.findall(r"^```text\n(.*?)^```", text, re.M | re.S)
        cls.samples = [b for b in blocks if "<" not in b]

    def cli(self, text, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "handback.py"), *args],
            input=text, capture_output=True, text=True, cwd=str(ROOT))

    def parse(self, text, *args):
        result = self.cli(text, "--json", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_the_file_carries_a_worked_sample_of_each_shape(self):
        self.assertEqual(len(self.samples), 1, "one worked sample expected")

    def test_the_changes_sample_parses(self):
        out = self.parse(self.samples[0])
        self.assertEqual(out["shape"], "changes")
        self.assertEqual(out["meta"]["based-on"], "8f2a1c")
        self.assertEqual(out["meta"]["source"], "docs/checklist.md")

    def test_a_state_change_carries_both_ends(self):
        item = self.parse(self.samples[0])["items"]["a3f91c"]
        self.assertEqual((item["was"], item["state"]), ("open", "done"))
        self.assertEqual(item["note"], "found them in the drawer")
        self.assertEqual(item["group"], "Records")

    def test_a_note_alone_is_reportable(self):
        """The item nobody ticked but somebody commented on is the whole point."""
        item = self.parse(self.samples[0])["items"]["b1c204"]
        self.assertIsNone(item["state"])
        self.assertEqual(item["note"], "did it by phone instead")

    def test_a_cleared_note_is_empty_not_absent(self):
        item = self.parse(self.samples[0])["items"]["c77e01"]
        self.assertEqual(item["note"], "")

    def test_the_control_listing_is_not_read_as_changes(self):
        out = self.parse(self.samples[0])
        self.assertEqual(sorted(out["items"]), ["a3f91c", "b1c204", "c77e01"])
        self.assertEqual(out["control"]["a3f91c"], {"state": "done",
                                                    "text": "Collect the receipts"})
        self.assertEqual(out["control"]["b1c204"], {"state": "open",
                                                    "text": "Ask about the invoice"})
        self.assertEqual(out["control"]["d09f31"],
                         {"state": "obsolete", "text": "Superseded by the new process"})

    def test_the_answers_shape_still_parses_exactly_as_in_version_1(self):
        """Version 2 added a shape; it did not redefine the first one."""
        block = ("### QUESTIONNAIRE ANSWERS\n"
                 "source: sample\ntitle: Sample\n"
                 "status: 1 of 3 answered · 1 unclear · 1 skipped\n\n"
                 "## Only section\n"
                 "[q01] Pick one\n→ (a) A\n   note: with a remark\n\n"
                 "[q02] Say something\n→ ? don't know — please follow up\n\n"
                 "[q03] And this\n→ (skipped)\n\n"
                 "[q04] Untouched\n→ (not answered)\n\n"
                 "### END QUESTIONNAIRE ANSWERS\n")
        out = self.parse(block)
        self.assertEqual(out["shape"], "answers")
        self.assertEqual(out["control"], {})
        self.assertEqual(out["items"]["q01"]["answers"],
                         [{"key": "a", "label": "A"}])
        self.assertEqual(out["items"]["q01"]["note"], "with a remark")
        self.assertEqual([out["items"][q]["state"] for q in ("q01", "q02", "q03", "q04")],
                         ["answered", "unclear", "skipped", "open"])

    def test_the_marker_bounds_the_block(self):
        """The parser has to find the block inside a longer message."""
        wrapped = f"chat before\n{self.samples[0]}\nchat after\n"
        out = self.parse(wrapped)
        self.assertEqual(out["meta"]["title"], "Filing checklist")

    def test_a_pinned_marker_overrides_detection(self):
        result = self.cli(self.samples[0], "--marker", "SOMETHING ELSE")
        self.assertEqual(result.returncode, 2, result.stdout)

    def test_a_missing_block_is_exit_2_with_a_reason(self):
        result = self.cli("nothing to see here\n")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no hand-back block", result.stderr)

    def test_a_truncated_paste_names_the_truncation(self):
        opened = self.samples[0].split("## Full state")[0]
        result = self.cli(f"chat before\n{opened}")
        self.assertEqual(result.returncode, 2)
        self.assertIn("truncated", result.stderr)

    def test_a_browser_copy_with_crlf_and_trailing_spaces_still_parses(self):
        mangled = self.samples[0].replace("\n", "  \r\n")
        out = self.parse(mangled)
        self.assertEqual(out["meta"]["title"], "Filing checklist")
        self.assertEqual(out["items"]["a3f91c"]["state"], "done")

    def test_lines_the_grammar_does_not_know_are_ignored_not_fatal(self):
        loose = self.samples[0].replace("+ note: found them in the drawer",
                                        "some stray sentence\n"
                                        "+ note: found them in the drawer")
        out = self.parse(loose)
        self.assertEqual(out["ignored"], ["some stray sentence"])
        self.assertEqual(out["items"]["a3f91c"]["note"], "found them in the drawer")


class ChecklistEditPlan(unittest.TestCase):
    """``--source`` joins a changes block against the maintained document and
    hands back exact line edits. What is worth asserting: the edits are
    verbatim and correctly addressed, drift is a hard stop, everything
    editorial stays out of the plan, and the script never writes."""

    @classmethod
    def setUpClass(cls):
        cls.example = ROOT / "examples" / "checklist-project"

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="handback-plan-"))
        self.addCleanup(shutil.rmtree, self.work, True)
        shutil.copytree(self.example, self.work / "project")
        self.source = (self.work / "project" / "docs" / "checklists"
                       / "2026-08-release.md")
        self.spec = checklist.load(self.source)
        self.by_state = {}
        for item in self.spec["items"]:
            self.by_state.setdefault(item["state"], []).append(item)

    def control(self, overrides=None):
        overrides = overrides or {}
        glyph = {"done": "☑ ", "open": "☐ "}
        lines = []
        for item in self.spec["items"]:
            state = overrides.get(item["fp"], item["state"])
            if state == "obsolete":
                lines.append(f"[{item['fp']}] ~~{item['text']}~~")
            else:
                lines.append(f"[{item['fp']}] {glyph[state]}{item['text']}")
        return "\n".join(lines)

    def block(self, changes, overrides=None, based_on=None):
        marker = self.spec["marker"]
        return (f"### {marker}\n"
                "source: docs/checklists/2026-08-release.md\n"
                f"title: {self.spec['title']}\n"
                f"based-on: {based_on or self.spec['source_fp']}\n"
                "status: n of m done · changed here\n\n"
                f"{changes}\n"
                "## Full state (control)\n"
                f"{self.control(overrides)}\n\n"
                f"### END {marker}\n")

    def plan(self, text):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "handback.py"),
             "--json", "--source", str(self.source)],
            input=text, capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["plan"]

    def test_a_tick_becomes_one_exact_line_edit(self):
        item = self.by_state["open"][0]
        plan = self.plan(self.block(f"[{item['fp']}] {item['text']}\n~ open → done\n",
                                    overrides={item["fp"]: "done"}))
        self.assertEqual([plan["drift"], plan["judgment"],
                          plan["control_mismatch"], plan["unmatched"]],
                         [False, [], [], []])
        self.assertEqual(len(plan["edits"]), 1)
        edit = plan["edits"][0]
        lines = self.source.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[edit["line"] - 1], edit["old"])
        self.assertIn("[ ]", edit["old"])
        self.assertEqual(edit["new"], edit["old"].replace("[ ]", "[x]", 1))

    def test_the_applied_edit_moves_the_item_and_nothing_else(self):
        item = self.by_state["open"][0]
        plan = self.plan(self.block(f"[{item['fp']}] {item['text']}\n~ open → done\n",
                                    overrides={item["fp"]: "done"}))
        edit = plan["edits"][0]
        lines = self.source.read_text(encoding="utf-8").splitlines(keepends=True)
        lines[edit["line"] - 1] = edit["new"] + "\n"
        self.source.write_text("".join(lines), encoding="utf-8")
        after = checklist.load(self.source)
        states = {i["fp"]: i["state"] for i in after["items"]}
        self.assertEqual(states.pop(item["fp"]), "done")
        self.assertEqual(states, {i["fp"]: i["state"] for i in self.spec["items"]
                                  if i["fp"] != item["fp"]})

    def test_done_to_open_is_the_reverse_edit(self):
        item = self.by_state["done"][0]
        plan = self.plan(self.block(f"[{item['fp']}] {item['text']}\n~ done → open\n",
                                    overrides={item["fp"]: "open"}))
        self.assertEqual(len(plan["edits"]), 1)
        self.assertIn("[ ]", plan["edits"][0]["new"])

    def test_drift_is_exit_3_and_no_plan(self):
        before = self.source.read_bytes()
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "handback.py"),
             "--source", str(self.source)],
            input=self.block("", based_on="000000"),
            capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("drift", result.stderr)
        self.assertIn(self.spec["source_fp"], result.stderr)
        self.assertEqual(self.source.read_bytes(), before)

    def test_a_note_alone_is_judgment_not_an_edit(self):
        item = self.by_state["open"][0]
        plan = self.plan(self.block(f"[{item['fp']}] {item['text']}\n"
                                    "+ note: did it by phone instead\n"))
        self.assertEqual(plan["edits"], [])
        self.assertEqual(len(plan["judgment"]), 1)
        self.assertIn("did it by phone instead", plan["judgment"][0]["why"])

    def test_an_unknown_fingerprint_is_reported_not_fatal(self):
        plan = self.plan(self.block("[ffffff] Something the file never had\n"
                                    "~ open → done\n"))
        self.assertEqual(plan["edits"], [])
        self.assertEqual(plan["unmatched"][0]["fp"], "ffffff")

    def test_a_control_listing_that_disagrees_is_reported(self):
        untouched = self.by_state["open"][1]
        plan = self.plan(self.block("", overrides={untouched["fp"]: "done"}))
        self.assertEqual([m["fp"] for m in plan["control_mismatch"]],
                         [untouched["fp"]])

    def test_a_change_already_in_the_file_is_a_warning_not_an_edit(self):
        item = self.by_state["done"][0]
        plan = self.plan(self.block(f"[{item['fp']}] {item['text']}\n~ open → done\n",
                                    overrides={item["fp"]: "done"}))
        self.assertEqual(plan["edits"], [])
        self.assertTrue(any(item["fp"] in w for w in plan["warnings"]))

    def test_the_script_never_writes_the_source(self):
        item = self.by_state["open"][0]
        before = self.source.read_bytes()
        self.plan(self.block(f"[{item['fp']}] {item['text']}\n~ open → done\n",
                             overrides={item["fp"]: "done"}))
        self.assertEqual(self.source.read_bytes(), before)


# ------------------------------------------------------------- index page ----

class IndexPage(ProjectCase):
    """The page nobody declares. What is worth asserting is not that it looks
    right — that is what ``check_page`` is for — but that it stays true to the
    output directory across the runs that could pull the two apart: a
    single-page render, a prune, a file deleted behind the engine's back."""

    def index(self):
        return self.project.output("index.html")

    def html(self):
        return self.index().read_text(encoding="utf-8")

    def links(self):
        return sorted(re.findall(r"class='idx-link' href='([^']+)'", self.html()))

    def test_it_appears_without_being_declared(self):
        self.project.section_page()
        r = render(self.project.config, "--all")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.index().exists())
        self.assertEqual(check_page(self.html()), [])
        self.assertEqual(self.links(), ["dashboard.html"])

    def test_every_link_points_at_a_file_that_exists(self):
        self.project.section_page()
        self.project.kind_page()
        self.project.spec("first", valid_spec(id="first"))
        self.project.spec("second", valid_spec(id="second", title="Second"))
        render(self.project.config, "--all")
        self.assertEqual(self.links(), ["dashboard.html", "survey-first.html",
                                        "survey-second.html"])
        for href in self.links():
            self.assertTrue(self.project.output(href).exists(), href)

    def test_it_never_lists_itself(self):
        self.project.section_page()
        render(self.project.config, "--all")
        render(self.project.config)
        self.assertNotIn("index.html", self.links())

    def test_the_card_carries_the_title_and_the_description(self):
        self.project.kind_page()
        self.project.spec("first", valid_spec(
            id="first", title="Release readiness",
            intro="**Four** questions before we cut a release.",
            estimate="two minutes"))
        render(self.project.config, "--all")
        html = self.html()
        self.assertIn("Release readiness", html)
        # The description arrives as markdown and reads as prose.
        self.assertIn("Four questions before we cut a release.", html)
        self.assertNotIn("**Four**", html)
        self.assertIn("two minutes", html)

    def test_a_kind_without_a_summary_still_gets_a_usable_card(self):
        """The hook is optional: the spec's own title has to carry the card."""
        record = index_module.instance_record(
            "survey", "first", object(), None,
            valid_spec(id="first", title="Only a title"), None,
            "survey-first.html", Path("/p/questions/first.json"), Path("/p"),
            {"idx_source": "Source"})
        self.assertEqual(record["title"], "Only a title")
        self.assertEqual(record["facts"], [["Source", "questions/first.json"]])

    def test_an_instance_with_no_title_anywhere_falls_back_to_its_stem(self):
        record = index_module.instance_record(
            "survey", "first", object(), None, "not a mapping", None,
            "survey-first.html", Path("/p/q.json"), Path("/p"),
            {"idx_source": "Source"})
        self.assertEqual(record["title"], "first")

    def test_rendering_one_page_keeps_the_cards_of_the_others(self):
        """The trap the manifest records exist for: a --page run enumerates
        one page, and must not report the project as having only one."""
        self.project.section_page()
        self.project.kind_page()
        self.project.spec("first", valid_spec(id="first"))
        render(self.project.config, "--all")
        r = render(self.project.config, "--page", "dashboard")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.links(), ["dashboard.html", "survey-first.html"])

    def test_a_pruned_instance_leaves_the_index(self):
        self.project.kind_page()
        self.project.spec("keep", valid_spec(id="keep"))
        drop = self.project.spec("drop", valid_spec(id="drop"))
        render(self.project.config, "--all")
        self.assertIn("survey-drop.html", self.links())
        drop.unlink()
        render(self.project.config, "--prune")
        self.assertEqual(self.links(), ["survey-keep.html"])

    def test_a_file_deleted_by_hand_leaves_the_index(self):
        """No event to notice: the record is dropped because the file is not
        there, which is the same rule that handles a prune."""
        self.project.section_page()
        self.project.kind_page()
        self.project.spec("first", valid_spec(id="first"))
        render(self.project.config, "--all")
        self.project.output("survey-first.html").unlink()
        render(self.project.config, "--page", "dashboard")
        self.assertEqual(self.links(), ["dashboard.html"])

    def test_an_unchanged_project_leaves_the_index_alone(self):
        self.project.section_page()
        render(self.project.config, "--all")
        before = self.html()
        r = render(self.project.config)
        self.assertEqual(before, self.html())
        self.assertNotIn("index.html", r.stdout)

    def test_it_can_be_switched_off(self):
        self.project.section_page()
        config = self.project.config / "config.py"
        config.write_text(config.read_text(encoding="utf-8") + "\nINDEX = False\n",
                          encoding="utf-8")
        r = render(self.project.config, "--all")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.index().exists())

    def test_the_file_name_can_be_moved(self):
        self.project.section_page()
        config = self.project.config / "config.py"
        config.write_text(config.read_text(encoding="utf-8")
                          + '\nINDEX_FILENAME = "start.html"\n', encoding="utf-8")
        render(self.project.config, "--all")
        self.assertFalse(self.index().exists())
        self.assertTrue(self.project.output("start.html").exists())

    def test_a_page_of_the_projects_own_keeps_the_name(self):
        """The project declared it; the engine only offers one."""
        self.project.section_page()
        page = self.project.config / "pages" / "dashboard" / "__init__.py"
        page.write_text(page.read_text(encoding="utf-8")
                        + '\nFILENAME = "index.html"\n', encoding="utf-8")
        r = render(self.project.config, "--all")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("is a page of this project", r.stderr)
        # Still the project's page, not a listing that replaced it.
        self.assertIn("<title>Project Dashboard</title>", self.html())
        self.assertNotIn("idx-link", self.html())

    def test_check_covers_it(self):
        self.project.section_page()
        r = render(self.project.config, "--all", "--check")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("+ index", r.stdout)

    def test_the_project_can_translate_it(self):
        self.project.section_page()
        config = self.project.config / "config.py"
        config.write_text(config.read_text(encoding="utf-8")
                          + '\nSTRINGS = {"idx_title": "Seiten"}\n', encoding="utf-8")
        render(self.project.config, "--all")
        self.assertIn("<title>Seiten</title>", self.html())


class PageDescription(ProjectCase):
    """A page's DESCRIPTION is read in exactly one place — the card the index
    gives it — and that card is the only thing saying what a page is for
    before someone opens it. Nothing else in a render depends on the field,
    which is precisely why leaving it out used to cost nothing and produce a
    bare card that passed every check."""

    def page(self):
        return self.project.config / "pages" / "dashboard" / "__init__.py"

    def undescribe(self, replacement=""):
        page = self.page()
        body = re.sub(r'(?m)^DESCRIPTION = .*$', replacement,
                      page.read_text(encoding="utf-8"))
        page.write_text(body, encoding="utf-8")

    def append_to_config(self, line):
        config = self.project.config / "config.py"
        config.write_text(config.read_text(encoding="utf-8") + line,
                          encoding="utf-8")

    def test_the_scaffolded_page_describes_itself(self):
        # If the template ever lost its DESCRIPTION, every project scaffolded
        # from it would start life with a finding.
        self.project.section_page()
        r = render(self.project.config, "--all", "--check")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_page_without_one_is_a_finding(self):
        self.project.section_page()
        self.undescribe()
        r = render(self.project.config, "--all", "--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no DESCRIPTION", r.stderr)
        self.assertIn("dashboard", r.stderr)

    def test_a_blank_one_is_not_a_description(self):
        self.project.section_page()
        self.undescribe('DESCRIPTION = "   "')
        r = render(self.project.config, "--all", "--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no DESCRIPTION", r.stderr)

    def test_the_page_still_renders_without_one(self):
        # A finding, not a refusal: the page is fine, its card is not.
        self.project.section_page()
        self.undescribe()
        r = render(self.project.config, "--all")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.project.output("dashboard.html").exists())

    def test_a_kind_page_is_never_asked_for_one(self):
        # Its cards come from the kind's summary() hook, one per instance.
        self.project.kind_page()
        self.project.spec("intake", valid_spec(id="intake"))
        r = render(self.project.config, "--all", "--check")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("no DESCRIPTION", r.stderr)

    def test_switching_the_index_off_retires_the_assertion(self):
        # No index, no card, nothing for the field to feed.
        self.project.section_page()
        self.undescribe()
        self.append_to_config("\nINDEX = False\n")
        r = render(self.project.config, "--all", "--check")
        self.assertEqual(r.returncode, 0, r.stderr)


class ExampleProjects(unittest.TestCase):
    """Every shipped example is a fixture: it has to actually render. Found by
    globbing rather than listed, so a new example cannot be added untested."""

    #: Pages the example declares. The index is not one of them — the engine
    #: adds it to every project, so counting it here would say nothing.
    EXPECTED = {"questionnaire-project": 2, "checklist-project": 1}

    def examples(self):
        return sorted(p for p in (ROOT / "examples").iterdir()
                      if (p / ".render" / "config.py").is_file())

    def test_every_example_is_covered_here(self):
        self.assertEqual([p.name for p in self.examples()], sorted(self.EXPECTED))

    def test_they_render_and_check(self):
        for source in self.examples():
            with self.subTest(example=source.name):
                work = Path(tempfile.mkdtemp(prefix="render-example-"))
                self.addCleanup(shutil.rmtree, work, True)
                shutil.copytree(source, work / "project")
                config = work / "project" / ".render"
                result = render(config, "--all", "--check")
                self.assertEqual(result.returncode, 0, result.stderr)
                rendered = sorted(p.name for p in (config / "output").glob("*.html"))
                self.assertIn("index.html", rendered)
                self.assertEqual(len(rendered) - 1, self.EXPECTED[source.name],
                                 rendered)
                for path in (config / "output").glob("*.html"):
                    self.assertEqual(check_page(path.read_text(encoding="utf-8")), [],
                                     f"{source.name}/{path.name}")


class EngineLocator(unittest.TestCase):
    """The locator scaffolded into a project has to find the installed engine
    without being told where it is — untestable from a checkout, where the
    plugin is simply there. It shipped sweeping two and three levels below the
    plugins directory while the marketplace installs four deep, at
    ``cache/<owner>/<plugin>/<version>/engine``, so every lookup failed unless
    CLAUDE_PLUGIN_ROOT happened to be set. Other plugins' engines carry the
    same three files, so only the manifest tells them apart."""

    LOCATOR = ROOT / "templates" / "engine_locator.py"

    def home(self):
        home = Path(tempfile.mkdtemp(prefix="render-home-"))
        self.addCleanup(shutil.rmtree, home, True)
        return home

    def install(self, home, name, version="0.1.0", owner="durchnull"):
        """One plugin install, laid out as the marketplace lays it out."""
        root = home / ".claude" / "plugins" / "cache" / owner / name / version
        engine = root / "engine"
        engine.mkdir(parents=True)
        for file in ("render.py", "design_system.py", "page_api.py"):
            (engine / file).write_text("", encoding="utf-8")
        (root / ".claude-plugin").mkdir()
        (root / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": name, "version": version}), encoding="utf-8")
        return engine.resolve()

    def resolve(self, home):
        """Run the locator with nothing but that home to go on."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("RENDER_ENGINE", "CLAUDE_PLUGIN_ROOT")}
        env["HOME"] = str(home)
        return subprocess.run([sys.executable, str(self.LOCATOR)],
                              capture_output=True, text=True, env=env)

    def test_finds_a_marketplace_install(self):
        home = self.home()
        engine = self.install(home, "render")
        found = self.resolve(home)
        self.assertEqual(found.returncode, 0, found.stderr)
        self.assertEqual(found.stdout.strip(), str(engine))

    def test_passes_over_a_foreign_plugin_with_the_same_signature(self):
        # The foreign plugin is deliberately the higher version, so ordering
        # alone would hand it the win: only the manifest can rule it out.
        home = self.home()
        self.install(home, "other-renderer", "9.0.0")
        engine = self.install(home, "render", "0.1.0")
        found = self.resolve(home)
        self.assertEqual(found.returncode, 0, found.stderr)
        self.assertEqual(found.stdout.strip(), str(engine))

    def test_a_foreign_plugin_alone_is_not_an_engine(self):
        home = self.home()
        self.install(home, "other-renderer")
        found = self.resolve(home)
        self.assertEqual(found.returncode, 1)
        self.assertIn("render engine not found", found.stderr)

    def test_the_highest_version_wins(self):
        home = self.home()
        self.install(home, "render", "0.9.0")
        engine = self.install(home, "render", "0.10.0")
        found = self.resolve(home)
        self.assertEqual(found.returncode, 0, found.stderr)
        self.assertEqual(found.stdout.strip(), str(engine))


class ScaffoldSync(ProjectCase):
    """The four files the plugin owns inside a project's config directory are
    the only ones a plugin update leaves behind — the engine is imported, not
    copied. Re-running init has to bring exactly those forward and exactly
    nothing else, because everything beside them is somebody's design."""

    OWNED = ("engine_locator.py", "render.py", "README.md", "pages/__init__.py")

    def sync(self, *args, target=None):
        return subprocess.run(
            [sys.executable, str(ENGINE / "scaffold.py"),
             str(target or self.project.config), *args],
            capture_output=True, text=True)

    def shipped(self, rel):
        return (ROOT / "templates" / rel).read_bytes()

    def mine(self, rel):
        return (self.project.config / rel).read_bytes()

    def fall_behind(self, rel="engine_locator.py"):
        """A copy from before whatever the template says today."""
        (self.project.config / rel).write_text("# an older copy\n", encoding="utf-8")

    def test_every_owned_file_ships_as_a_template(self):
        # The list is only trustworthy if each entry has something to copy.
        for rel in scaffold.PLUGIN_OWNED:
            self.assertTrue((ROOT / "templates" / rel).is_file(), rel)
        self.assertEqual(tuple(scaffold.PLUGIN_OWNED), self.OWNED)

    def test_it_fills_in_a_file_the_project_never_got(self):
        (self.project.config / "README.md").unlink()
        self.assertEqual(self.sync().returncode, 0)
        self.assertEqual(self.mine("README.md"), self.shipped("README.md"))

    def test_it_replaces_a_copy_that_fell_behind(self):
        self.fall_behind()
        result = self.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.mine("engine_locator.py"),
                         self.shipped("engine_locator.py"))
        self.assertIn("engine_locator.py", result.stdout)

    def test_it_leaves_the_projects_own_files_untouched(self):
        self.project.section_page()
        theirs = {}
        for rel in ("config.py", "content.py", "pages/dashboard/__init__.py"):
            path = self.project.config / rel
            path.write_text(path.read_text(encoding="utf-8") + "\n# theirs\n",
                            encoding="utf-8")
            theirs[rel] = path.read_bytes()
        self.fall_behind()
        self.assertEqual(self.sync().returncode, 0)
        for rel, before in theirs.items():
            self.assertEqual((self.project.config / rel).read_bytes(), before, rel)

    def test_check_reports_drift_without_writing(self):
        self.fall_behind()
        result = self.sync("--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("would refresh", result.stdout)
        self.assertNotEqual(self.mine("engine_locator.py"),
                            self.shipped("engine_locator.py"))

    def test_a_current_scaffold_needs_nothing(self):
        result = self.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Up to date", result.stdout)
        self.assertEqual(self.sync("--check").returncode, 0)

    def test_the_drift_note_claims_only_the_running_version(self):
        # The note names one version, and it is the one it is running — read
        # from the installation's own manifest. Naming the version that wrote
        # a project's copies would mean recording it somewhere and trusting
        # the record; which files differ is measured instead.
        self.fall_behind()
        line = scaffold.note(self.project.config)
        self.assertIn(scaffold.plugin_version(), line)
        self.assertNotIn("scaffolded by", line)

    def test_a_directory_that_is_not_a_config_is_refused(self):
        empty = Path(tempfile.mkdtemp(prefix="render-empty-"))
        self.addCleanup(shutil.rmtree, empty, True)
        result = self.sync(target=empty)
        self.assertEqual(result.returncode, 2)
        self.assertIn("/render:init", result.stderr)

    def test_the_engine_says_so_when_the_copies_are_behind(self):
        self.project.section_page()
        self.fall_behind()
        result = render(self.project.config, "--all")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/render:init refreshes", result.stderr)

    def test_a_current_project_is_not_nagged(self):
        self.project.section_page()
        result = render(self.project.config, "--all")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("/render:init refreshes", result.stderr)

    def test_a_missing_file_is_filled_in_but_never_nagged_about(self):
        # Absence may be a project that never wanted the file; only a copy
        # that exists and differs is unambiguously behind.
        self.project.section_page()
        (self.project.config / "README.md").unlink()
        result = render(self.project.config, "--all")
        self.assertNotIn("/render:init refreshes", result.stderr)
        self.assertEqual(self.sync().returncode, 0)
        self.assertEqual(self.mine("README.md"), self.shipped("README.md"))

    def test_the_note_survives_the_quiet_run_the_hook_makes(self):
        # The hook is the only render most projects ever trigger; a note it
        # swallows is a note nobody reads. A quiet run that renders
        # something carries the note with it.
        self.project.section_page()
        self.fall_behind()
        result = render(self.project.config, "-q")
        self.assertIn("/render:init refreshes", result.stderr)

    def test_a_quiet_run_with_nothing_to_say_does_not_nag_either(self):
        # The hook fires after every Write/Edit; a drifted project must not
        # hear the same line (or pay the byte compares) every single time.
        # The note waits for a run that has something else to report.
        self.project.section_page()
        render(self.project.config, "--all")
        self.fall_behind()
        result = render(self.project.config, "-q", "--if-configured")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("/render:init refreshes", result.stderr)
        # A person running it still hears about the drift, changes or not.
        result = render(self.project.config)
        self.assertIn("/render:init refreshes", result.stderr)


class ScaffoldModes(unittest.TestCase):
    """The write modes: boilerplate is emitted, never typed. What matters is
    that every emitted file is real (renders, runs, passes the checks), that
    nothing is ever overwritten, and that the refresh contract is untouched
    — everything these modes write is the project's from the first byte."""

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="scaffold-modes-"))
        self.addCleanup(shutil.rmtree, self.work, True)
        self.config = self.work / ".render"

    def scaffold(self, *args):
        return subprocess.run(
            [sys.executable, str(ENGINE / "scaffold.py"), str(self.config),
             *args], capture_output=True, text=True)

    def readme(self):
        """The example dashboard renders the project README; give it one
        long enough to clear the empty-section check."""
        (self.work / "README.md").write_text(
            "# Fixture Project\n\n"
            "A body with enough prose for the section to look like a real "
            "one.\n\n## A heading\n\n- a list item\n- another one\n"
            "- a third, for good measure\n\nOne closing paragraph so the "
            "rendered section is comfortably past the minimum body length "
            "the structural check insists on.\n", encoding="utf-8")

    def test_fresh_writes_the_whole_template_scaffold_byte_identically(self):
        result = self.scaffold("--fresh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(scaffold.qualifies(self.config))
        shipped = [p for p in (ROOT / "templates").rglob("*")
                   if p.is_file() and "__pycache__" not in p.parts]
        for path in shipped:
            rel = path.relative_to(ROOT / "templates")
            self.assertEqual((self.config / rel).read_bytes(),
                             path.read_bytes(), str(rel))

    def test_a_fresh_scaffold_renders_and_checks_clean(self):
        self.scaffold("--fresh")
        self.readme()
        result = render(self.config, "--all", "--check")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_fresh_refuses_a_directory_that_already_qualifies(self):
        self.scaffold("--fresh")
        result = self.scaffold("--fresh")
        self.assertEqual(result.returncode, 2)
        self.assertIn("plain refresh", result.stderr)

    def test_fresh_keeps_a_file_the_project_already_wrote(self):
        self.config.mkdir(parents=True)
        (self.config / "config.py").write_text("# already mine\n",
                                               encoding="utf-8")
        result = self.scaffold("--fresh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.config / "config.py").read_text(encoding="utf-8"),
                         "# already mine\n")
        self.assertIn("left alone", result.stdout)

    def test_a_kind_page_is_the_known_three_liner_and_renders(self):
        self.scaffold("--fresh")
        self.readme()
        result = self.scaffold("--new-page", "survey", "--kind", "questionnaire",
                               "--sources", "questions/*.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        declared = (self.config / "pages" / "survey" / "__init__.py") \
            .read_text(encoding="utf-8")
        self.assertIn('KIND = "questionnaire"', declared)
        self.assertIn('SOURCES = "questions/*.json"', declared)
        (self.work / "questions").mkdir()
        (self.work / "questions" / "s.json").write_text(json.dumps(
            {"id": "s", "title": "S", "sections": [
                {"title": "One", "questions": [
                    {"id": "q1", "question": "Well?", "type": "text"}]}]}),
            encoding="utf-8")
        result = render(self.config, "--all", "--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.config / "output" / "survey-s.html").is_file())

    def test_an_unknown_kind_is_noted_not_refused(self):
        # .render/kinds/<name>.py may be written right after the page is.
        self.scaffold("--fresh")
        result = self.scaffold("--new-page", "log", "--kind", "journal",
                               "--sources", "journal/*.md")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("journal", result.stdout)
        self.assertIn("does not exist yet", result.stdout)

    def test_a_section_page_carries_one_contract_complete_stub_each(self):
        self.scaffold("--fresh")
        result = self.scaffold("--new-page", "report", "--section", "overview",
                               "--section", "detail")
        self.assertEqual(result.returncode, 0, result.stderr)
        page = self.config / "pages" / "report"
        declared = (page / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('("overview", "01"', declared)
        self.assertIn('("detail", "02"', declared)
        for sid in ("overview", "detail"):
            stub = (page / f"{sid}.py").read_text(encoding="utf-8")
            for token in ("INPUTS", "LISTING", "VOLATILE", "def build"):
                self.assertIn(token, stub, sid)

    def test_the_scaffolded_stub_fails_the_render_loudly_not_quietly(self):
        # A stub that rendered an empty section would ship a hollow page;
        # raising keeps the page honest until somebody writes it.
        self.scaffold("--fresh")
        self.scaffold("--new-page", "report", "--section", "overview")
        result = render(self.config, "--page", "report")
        self.assertIn("scaffolded stub", result.stdout + result.stderr)

    def test_no_page_is_ever_overwritten(self):
        self.scaffold("--fresh")
        self.scaffold("--new-page", "report", "--section", "overview")
        before = (self.config / "pages" / "report" / "__init__.py").read_bytes()
        result = self.scaffold("--new-page", "report", "--kind",
                               "questionnaire", "--sources", "q/*.json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual((self.config / "pages" / "report" / "__init__.py")
                         .read_bytes(), before)

    def test_a_bad_page_id_is_refused(self):
        self.scaffold("--fresh")
        for bad in ("Report", "my-page", "page2"):
            result = self.scaffold("--new-page", bad, "--section", "s")
            self.assertEqual(result.returncode, 2, bad)

    def test_new_page_needs_exactly_one_flavour(self):
        self.scaffold("--fresh")
        result = self.scaffold("--new-page", "report")
        self.assertEqual(result.returncode, 2)
        result = self.scaffold("--new-page", "report", "--kind", "checklist",
                               "--sources", "d/*.md", "--section", "s")
        self.assertEqual(result.returncode, 2)

    def test_the_standalone_skeleton_runs_and_passes_the_checks(self):
        self.scaffold("--fresh")
        result = self.scaffold("--standalone", "notes")
        self.assertEqual(result.returncode, 0, result.stderr)
        run = subprocess.run(
            [sys.executable, str(self.config / "notes.py")],
            capture_output=True, text=True, cwd=str(self.work),
            env=dict(os.environ, RENDER_ENGINE=str(ENGINE)))
        self.assertEqual(run.returncode, 0, run.stderr)
        html = (self.config / "output" / "notes.html").read_text(encoding="utf-8")
        self.assertEqual(check_page(html), [])


class DesignManualCatalog(unittest.TestCase):
    """The manual is split: a core with a catalog, and reference files under
    docs/design/. The split only works if nothing can fall between the
    files — every reference heading is cataloged, every helper a heading
    names is a real page_api export, and no heading lives twice."""

    @classmethod
    def setUpClass(cls):
        cls.core = (ROOT / "design-manual.md").read_text(encoding="utf-8")
        cls.topics = {p.name: p.read_text(encoding="utf-8")
                      for p in sorted((ROOT / "docs" / "design").glob("*.md"))}
        cls.headings = {}          # section number -> (file, heading line)
        for name, text in cls.topics.items():
            for line in text.splitlines():
                m = re.match(r"^### ([\w.b]+) (.+)$", line)
                if m:
                    assert m.group(1) not in cls.headings, m.group(1)
                    cls.headings[m.group(1)] = (name, line)

    def test_the_five_topic_files_exist(self):
        self.assertEqual(sorted(self.topics),
                         ["charts.md", "chrome.md", "components.md",
                          "interactive.md", "longform.md"])

    def test_every_reference_heading_has_a_catalog_row(self):
        rows = set(re.findall(r"^\| ([\w.b]+) \|", self.core, re.M))
        missing = [num for num in self.headings if num not in rows]
        self.assertEqual(missing, [], "headings without a catalog row")

    def test_every_helper_a_heading_names_is_a_page_api_export(self):
        import page_api
        for num, (name, line) in self.headings.items():
            helpers = re.findall(r"`(\w+)\(\)`", line) + \
                      re.findall(r"`([A-Z][A-Z_]+)`", line)
            for helper in helpers:
                self.assertIn(helper, page_api.__all__, f"{name} {num}")

    def test_the_catalog_names_each_reference_file(self):
        for name in self.topics:
            self.assertIn(f"docs/design/{name}", self.core, name)

    def test_the_core_still_carries_the_load_bearing_tables(self):
        # The split moved the component reference out; the tokens stayed.
        for anchor in ("## 2. Colors", "## 3. Typography",
                       "## 10. Checklist before shipping",
                       "read the reference file for every helper"):
            self.assertIn(anchor, self.core, anchor)


# --------------------------------------------------- the markdown renderer ----

class Markdown(unittest.TestCase):
    """The shapes a written document actually uses — and the one rule that
    matters most: inside a fence, nothing is markup."""

    def md(self, text, **kw):
        return content_core.md_to_html(text, **kw)

    def test_a_fence_becomes_a_code_block_with_its_language(self):
        out = self.md("```python\nx = 1\n```")
        self.assertIn('<pre><code class="lang-python">', out)
        self.assertIn("x = 1", out)

    def test_a_fence_is_literal_text(self):
        out = self.md("```\n**not bold** and `not code` and [not a](link)\n```")
        for markup in ("<strong>", "<code>x", "<a href"):
            self.assertNotIn(markup, out)
        self.assertIn("**not bold**", out)

    def test_a_fence_escapes_its_content(self):
        self.assertIn("&lt;script&gt;", self.md("```\n<script>\n```"))

    def test_an_unclosed_fence_ends_with_the_document(self):
        out = self.md("intro\n\n```\nnever closed\n")
        self.assertIn("<pre>", out)
        self.assertIn("</code></pre>", out)

    def test_lists_nest_by_indentation(self):
        out = self.md("- one\n  - deeper\n- two")
        self.assertIn("<li>one<ul><li>deeper</li></ul></li>", out)
        self.assertEqual(out.count("<ul>"), 2)

    def test_a_numbered_list_after_a_bulleted_one_is_a_new_list(self):
        out = self.md("- a\n\n1. b\n")
        self.assertIn("<ul><li>a</li></ul>", out)
        self.assertIn("<ol><li>b</li></ol>", out)

    def test_an_indented_fence_belongs_to_its_item(self):
        out = self.md("1. step\n\n   ```sh\n   run it\n   ```\n")
        self.assertIn("<li>step<pre>", out)

    def test_a_wrapped_item_stays_one_item(self):
        out = self.md("- a line that continues\n  on the next line\n")
        self.assertEqual(out.count("<li>"), 1)
        self.assertIn("continues on the next", out)

    def test_two_trailing_spaces_break_the_line(self):
        self.assertIn("<br>", self.md("first  \nsecond"))
        self.assertNotIn("<br>", self.md("first\nsecond"))

    def test_checkboxes_still_become_marks(self):
        out = self.md("- [ ] open\n- [x] done")
        self.assertIn("title='open'", out)
        self.assertIn("title='done'", out)

    def test_headings_tables_and_quotes_are_unchanged(self):
        out = self.md("## Title\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n> quoted\n")
        self.assertIn("<h4>Title</h4>", out)          # heading_base=3 by default
        self.assertIn("<table>", out)
        self.assertIn("<blockquote><p>quoted</p></blockquote>", out)


class ChecklistFences(unittest.TestCase):
    """A checklist document that *shows* a checklist in a code sample."""

    DOC = ("# Release\n\n## Prepare\n\n- [ ] a real item\n\n"
           "```bash\n## not a heading\n- [ ] not an item\n```\n\n"
           "- [x] a second real item\n")

    def test_a_sample_contributes_no_items_and_no_groups(self):
        groups, excluded, title = checklist._parse_blocks(self.DOC, ())
        items = [b for g in groups for b in g["blocks"] if b["kind"] == "item"]
        self.assertEqual([i["text"] for i in items],
                         ["a real item", "a second real item"])
        self.assertEqual([g["title"] for g in groups], ["Prepare"])
        self.assertEqual(excluded, [])
        self.assertEqual(title, "Release")

    def test_the_sample_survives_as_prose(self):
        groups, _, _ = checklist._parse_blocks(self.DOC, ())
        prose = "\n".join(b["md"] for g in groups for b in g["blocks"]
                          if b["kind"] == "prose")
        self.assertIn("```bash", prose)
        self.assertIn("- [ ] not an item", prose)


# ---------------------------------------------------------- article pages ----

class ArticlePages(unittest.TestCase):
    """``scripts/article.py`` — one markdown document, one page, no config."""

    SOURCE = (
        "---\nkicker: Session log\nlede: A standfirst.\ndate: 2026-08-01\n---\n\n"
        "# The headline\n\n"
        "Opening prose with a [doc link](https://example.com/docs/a) in it.\n\n"
        "## A section\n\n"
        "1. first step\n   - a nested note\n2. second step\n\n"
        "```bash\ncurl -s https://example.com/install | sh\n```\n\n"
        "See [content_core.py](engine/content_core.py#L46) and "
        "<https://example.org/more>.\n"
    )

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="render-article-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.src = self.dir / "a-turn.md"
        self.src.write_text(self.SOURCE, encoding="utf-8")

    def run_script(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "article.py"), str(self.src), *args],
            capture_output=True, text=True, cwd=str(ROOT))

    def page(self, *args):
        result = self.run_script(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return (self.src.with_suffix(".html")).read_text(encoding="utf-8")

    def test_the_page_passes_the_engine_s_own_checks(self):
        self.assertEqual(check_page(self.page()), [])

    def test_the_headline_comes_from_the_document_and_is_not_repeated(self):
        html = self.page()
        self.assertIn("<h1>The headline</h1>", html)
        self.assertEqual(html.count("The headline"), 2)   # <title> and <h1>

    def test_an_explicit_title_wins(self):
        self.assertIn("<h1>Given by hand</h1>", self.page("--title", "Given by hand"))

    def test_frontmatter_reaches_the_masthead(self):
        html = self.page()
        self.assertIn("Session log", html)
        self.assertIn("A standfirst.", html)
        self.assertIn("2026-08-01", html)

    def test_the_first_section_sits_one_step_under_the_masthead(self):
        # The document leads with '#', so '##' has to land as h2, not h4.
        self.assertIn("<h2>A section</h2>", self.page())

    def test_a_document_that_starts_at_h2_lands_at_h2_as_well(self):
        self.src.write_text("## Only level\n\ntext\n", encoding="utf-8")
        self.assertIn("<h2>Only level</h2>", self.page())

    def test_external_links_become_label_plus_reference(self):
        html = self.page()
        self.assertIn("doc link [1]", html)
        self.assertNotIn("<a href", html)
        self.assertIn("example.com/docs/a", html)

    def test_a_link_into_the_project_keeps_its_label_and_is_not_listed(self):
        html = self.page()
        self.assertIn("content_core.py", html)
        self.assertNotIn("engine/content_core.py#L46</li>", html)

    def test_a_url_in_a_sample_keeps_everything_but_its_scheme(self):
        self.assertIn("curl -s example.com/install | sh", self.page())

    def test_nothing_fetchable_survives(self):
        self.assertNotIn("https://", self.page().replace("xmlns=", ""))

    def test_nested_lists_and_fences_render(self):
        html = self.page()
        self.assertIn("<li>first step<ul>", html)
        self.assertIn('<code class="lang-bash">', html)

    def test_a_missing_file_is_refused(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "article.py"), str(self.dir / "nope.md")],
            capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no such file", result.stderr)

    def test_the_output_path_is_honoured(self):
        out = self.dir / "elsewhere" / "page.html"
        result = self.run_script("-o", str(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(out.is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
