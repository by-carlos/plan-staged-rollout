"""Script tests for jira_adapter.py's read-back comparison.

No network. Run from anywhere:

    python -m unittest discover -s tickets/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import jira_adapter
import ticket_template

TEAM_ID = "00000000-0000-4000-8000-000000000001"


class TeamReadBack(unittest.TestCase):
    """Team is set by id and reads back as an object with id and name (as Jira returns it)."""

    def test_object_with_the_id_matches(self):
        self.assertTrue(jira_adapter.custom_matches({"kind": "text", "value": TEAM_ID},
                                                    {"id": TEAM_ID, "name": "Example Team"}))

    def test_object_with_another_id_does_not_match(self):
        self.assertFalse(jira_adapter.custom_matches({"kind": "text", "value": TEAM_ID},
                                                     {"id": "other", "name": "Platform"}))

    def test_plain_text_still_compares_as_text(self):
        self.assertTrue(jira_adapter.custom_matches({"kind": "text", "value": "a b"}, "a b"))



class InvestigatedFieldGate(unittest.TestCase):
    """A set_only_if field is withheld until the work was investigated; a
    delegated drafter's draft_notes.read counts as the investigation."""

    def run_build(self, notes: dict) -> tuple[dict, list[str], list[str]]:
        t, _ = ticket_template.validate_template("default", "jira")
        t.setdefault("fields", {})["effort"] = {"id": "customfield_00009", "kind": "text", "default": "unset",
                                 "set_only_if": "investigated"}
        ticket = {"tracker": "jira", "target": {"site": "example.atlassian.net", "project": "K"},
                  "type": "Story", "title": "List every server",
                  "sections": {"Context": "Why.", "Acceptance Criteria": "1. done"},
                  "fields": {"effort": "sonnet-high"}, "draft_notes": notes}
        return jira_adapter.build(ticket, t, {"status": "ok"})

    def test_withheld_without_an_investigation(self):
        payload, errors, warnings = self.run_build({"investigated": False})
        self.assertNotIn("customfield_00009", str(payload))
        self.assertIn("fields.effort: not set, the template sets it only after an investigation", warnings)

    def test_set_when_the_draft_records_what_was_read(self):
        payload, errors, warnings = self.run_build({"read": ["inventory/servers.csv"]})
        self.assertIn("customfield_00009", str(payload))

if __name__ == "__main__":
    unittest.main()
