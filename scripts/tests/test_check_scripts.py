import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check_docs_truth as truth  # noqa: E402
import check_links as links  # noqa: E402
import check_plugin_validate as pv  # noqa: E402
import check_retired_names as retired  # noqa: E402


class RetiredNames(unittest.TestCase):
    def hits(self, text):
        return retired.find_hits("f.md", text)

    def test_the_bare_old_name_hits(self):
        self.assertEqual(len(self.hits("run `/plan-run` now")), 1)
        self.assertEqual(len(self.hits("a /plan-run.")), 1)

    def test_current_longer_names_do_not_hit(self):
        self.assertEqual(self.hits("`/plan-run-local` and /plan-run-cloud"), [])

    def test_singular_triage_hits_but_plural_does_not(self):
        self.assertEqual(len(self.hits("/triage-issue")), 1)
        self.assertEqual(self.hits("/triage-issues"), [])

    def test_hit_carries_the_line_number(self):
        self.assertEqual(self.hits("ok\n/plan-run")[0][1], 2)


class Links(unittest.TestCase):
    PATHS = {"a.md", "docs/b.md", "docs/img.png"}

    def check(self, a, b="# Title\n\n## Second part\n"):
        return links.check_files({"a.md": a, "docs/b.md": b}, self.PATHS)

    def test_valid_links_and_anchors_pass(self):
        text = "[b](docs/b.md#second-part) [img](docs/img.png) [self](#top)\n\n# Top\n"
        self.assertEqual(self.check(text), [])

    def test_missing_file_hits(self):
        self.assertEqual(len(self.check("[x](docs/missing.md)")), 1)

    def test_missing_anchor_hits(self):
        self.assertEqual(len(self.check("[x](docs/b.md#nope)")), 1)
        self.assertEqual(len(self.check("[x](#nope)")), 1)

    def test_code_is_not_scanned(self):
        text = "```\n[x](missing.md)\n```\nand `[y](missing.md)`\n"
        self.assertEqual(self.check(text), [])

    def test_external_links_are_skipped(self):
        self.assertEqual(self.check("[x](https://example.com/none#x)"), [])

    def test_heading_slug_keeps_code_text_and_drops_punctuation(self):
        self.assertEqual(
            links.slugify("1. Plan — `plan-stages <project idea>`"),
            "1-plan--plan-stages-project-idea",
        )

    def test_duplicate_headings_get_a_suffix(self):
        self.assertEqual(links.anchors_of("# A\n# A\n"), {"a", "a-1"})


class DocsTruth(unittest.TestCase):
    SOURCES = {"stage-run": "argument-hint: <N> [--unattended]", "plan-close": "x"}

    def test_unknown_plugin_command_hits(self):
        hits = truth.doc_hits("d.md", "run `/plan-nonexistent` now", self.SOURCES)
        self.assertEqual(len(hits), 1)

    def test_unrelated_slash_words_are_ignored(self):
        self.assertEqual(truth.doc_hits("d.md", "see /usr/bin and /clear", self.SOURCES), [])

    def test_path_segments_are_not_commands(self):
        self.assertEqual(truth.doc_hits("d.md", "skills/stage-runner/x", self.SOURCES), [])

    def test_unknown_flag_on_a_known_command_hits(self):
        hits = truth.doc_hits("d.md", "`/stage-run 3 --bogus`", self.SOURCES)
        self.assertEqual(len(hits), 1)
        self.assertEqual(truth.doc_hits("d.md", "`/stage-run 3 --unattended`", self.SOURCES), [])

    def test_reference_needs_a_row_per_command_naming_its_flags(self):
        sources = {"stage-run": "argument-hint: <N> [--unattended]"}
        self.assertEqual(len(truth.reference_hits(sources, "no table", {"stage-run"})), 1)
        row = "| `/stage-run <N>` | runs | none |"
        self.assertEqual(len(truth.reference_hits(sources, row, {"stage-run"})), 1)
        row = "| `/stage-run <N>` | runs | `--unattended` |"
        self.assertEqual(truth.reference_hits(sources, row, {"stage-run"}), [])


class PluginValidate(unittest.TestCase):
    WARNING = "  ❯ root: CLAUDE.md at the plugin root is not loaded as project context."
    SUMMARY = "✘ Validation failed (--strict treats warnings as errors)"

    def test_only_the_known_warning_passes(self):
        self.assertEqual(pv.judge(1, self.WARNING + "\n" + self.SUMMARY), [])

    def test_another_warning_fails(self):
        out = self.WARNING + "\n  ❯ skills: something else\n" + self.SUMMARY
        self.assertEqual(len(pv.judge(1, out)), 1)

    def test_an_error_fails(self):
        out = self.WARNING + "\n✘ plugin.json: invalid\n" + self.SUMMARY
        self.assertEqual(len(pv.judge(1, out)), 1)

    def test_nonzero_exit_with_no_finding_fails(self):
        self.assertEqual(len(pv.judge(1, "boom")), 1)


if __name__ == "__main__":
    unittest.main()
