"""Scripted check for the discovery plan's written boundary (DECISIONS.md, #261).

`/plan-stages` scaffolds a vague or thin idea as a discovery plan whose Out of
scope names the build in a fixed frame, so the scope referee has a boundary to
judge a "now build it" stage against. This pins the frame in the command, in
the skill, and in the `drift-plan` fixture, so the three cannot drift apart.

Run from the repo root:
    python -m unittest discover -s skills/staged-rollout/tests -v
"""

import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
ROOT = SKILL.parents[1]
COMMAND = ROOT / "commands" / "plan-stages.md"
SKILL_MD = SKILL / "SKILL.md"
FIXTURE = SKILL / "tests" / "fixtures" / "drift-plan" / ".plan" / "PLAN.md"

FRAME = "`Building <subject> — that is the next plan.`"
FILLED = re.compile(r"Building (?!<subject>)\S.*? — that is the next plan\.")


def flat(path):
    """The file's text with line wraps folded to single spaces."""
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


class DiscoveryBoundTest(unittest.TestCase):
    def test_command_carries_the_frame(self):
        self.assertIn(FRAME, flat(COMMAND))

    def test_command_gates_building_anyway(self):
        text = flat(COMMAND)
        self.assertIn("Building anyway costs one sentence.", text)
        self.assertIn("*(Needs you — answered)*", text)
        self.assertIn("No reason, no build plan", text)

    def test_command_defines_thin_as_a_check(self):
        text = flat(COMMAND)
        self.assertIn(
            "a Done check names nothing a script could assert or a person "
            "could see, or no Done check covers the Outcome",
            text,
        )

    def test_command_treats_unbounded_scope_as_thin(self):
        text = flat(COMMAND)
        self.assertIn("**Unbounded** (a kind of thin)", text)
        self.assertIn("only the user's own list of what is in can", text)

    def test_skill_carries_the_frame(self):
        self.assertIn(FRAME, flat(SKILL_MD))

    def test_fixture_out_of_scope_is_bounded(self):
        text = flat(FIXTURE)
        match = re.search(r"\*\*Out of scope:\*\* (.*?) - \*\*Done", text)
        self.assertIsNotNone(match, "fixture has no Out of scope bullet")
        self.assertRegex(match.group(1), FILLED)


if __name__ == "__main__":
    unittest.main()
