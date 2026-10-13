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


if __name__ == "__main__":
    unittest.main()
