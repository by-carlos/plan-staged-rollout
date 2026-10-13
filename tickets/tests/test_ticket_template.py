"""Script tests for ticket_template.py's config lookup (`resolve`).

No network and no git: each test writes a throwaway config directory and
points `resolve` at it. Run from anywhere:

    python -m unittest discover -s tickets/tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ticket_template

GH_TEMPLATE = 'extends = "default"\ntracker = "github"\n'
JIRA_TEMPLATE = 'extends = "default"\ntracker = "jira"\n'


class ConfigLookup(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.cfg = self.tmp / "cfg"
        self.cfg.mkdir()
        self.project = self.tmp / "project"
        self.project.mkdir()
        (self.cfg / "gh.toml").write_text(GH_TEMPLATE, encoding="utf-8")
        (self.cfg / "jira.toml").write_text(JIRA_TEMPLATE, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def config(self, body: str) -> None:
        (self.cfg / ticket_template.CONFIG_NAME).write_text(body, encoding="utf-8")

    def resolve(self, tracker: str | None) -> dict:
        return ticket_template.resolve(tracker, self.project, self.cfg, None)

    def test_string_applies_to_every_tracker(self):
        self.config('ticket_template = "gh.toml"\n')
        out = self.resolve("github")
        self.assertEqual(out["source"], str(self.cfg / "gh.toml"))
        self.assertIsNone(out["notice"])

    def test_string_for_the_other_tracker_falls_back_with_notice(self):
        self.config('ticket_template = "gh.toml"\n')
        out = self.resolve("jira")
        self.assertEqual(out["source"], "default")
        self.assertIn("template is for 'github'", out["notice"])

    def test_table_picks_the_requested_tracker(self):
        self.config('[ticket_template]\ngithub = "gh.toml"\njira = "jira.toml"\n')
        self.assertEqual(self.resolve("github")["source"], str(self.cfg / "gh.toml"))
        jira = self.resolve("jira")
        self.assertEqual(jira["source"], str(self.cfg / "jira.toml"))
        self.assertEqual(jira["tracker"], "jira")
        self.assertIsNone(jira["notice"])

    def test_table_without_the_tracker_is_a_missing_key(self):
        self.config('ticket_template = { github = "gh.toml" }\n')
        out = self.resolve("jira")
        self.assertEqual(out["source"], "default")
        self.assertIsNone(out["notice"])

    def test_table_with_unknown_tracker_is_a_notice(self):
        self.config('ticket_template = { gitlab = "gh.toml" }\n')
        out = self.resolve("github")
        self.assertEqual(out["source"], "default")
        self.assertIn("table of tracker = path", out["notice"])

    def test_table_without_a_tracker_argument_is_a_notice(self):
        self.config('ticket_template = { github = "gh.toml", jira = "jira.toml" }\n')
        out = self.resolve(None)
        self.assertEqual(out["source"], "default")
        self.assertIn("no tracker was given", out["notice"])

    def test_empty_string_is_a_notice(self):
        self.config('ticket_template = ""\n')
        self.assertIn("must be a file path", self.resolve("github")["notice"])


if __name__ == "__main__":
    unittest.main()
