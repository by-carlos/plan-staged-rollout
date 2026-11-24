"""Scripted check for the plan review's risk-evidence step (issue #298).

The final review stage (SF) is read by a session, not run as code, so this pins
what can drift: the template carries the step, it points at `risk-paths.md`
instead of restating the list, it reuses the redo read rule, and the worked
example under `examples/risk-evidence/` reports exactly one stage.

Run from the repo root:
    python -m unittest discover -s skills/staged-rollout/tests -v
"""

import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
ROOT = SKILL.parents[1]
TEMPLATE = SKILL / "references" / "templates" / "stage-f-review.md"
RISK_PATHS = SKILL / "references" / "risk-paths.md"
EXAMPLE = ROOT / "examples" / "risk-evidence" / "README.md"


def step_text():
    text = TEMPLATE.read_text(encoding="utf-8")
    match = re.search(r"- \[ \] \*\*Risk evidence\.\*\*.*?(?=\n- \[ \] )", text, re.S)
    assert match, "stage-f-review.md has no Risk evidence step"
    return match.group(0)


class TemplateStep(unittest.TestCase):
    def test_step_points_at_the_single_risk_list(self):
        step = step_text()
        self.assertIn("risk-paths.md", step)
        self.assertTrue(RISK_PATHS.exists())
        # The list is defined once: no area's example paths are copied in.
        for sample in ("migrations/", "Dockerfile", "openapi.yaml", "*.proto"):
            self.assertNotIn(sample, step)

    def test_step_reuses_the_redo_read_rule(self):
        step = step_text()
        self.assertIn("`Coverage` list", step)
        self.assertIn("redo", step)

    def test_missing_check_is_a_plain_loose_end(self):
        step = step_text()
        self.assertIn("loose end", step)
        self.assertIn("`Fix:` stage", step)
        self.assertIn("fix rule below", step)


class WorkedExample(unittest.TestCase):
    def test_exactly_one_stage_is_reported(self):
        text = EXAMPLE.read_text(encoding="utf-8")
        reported = re.findall(r"^> \*\*(S\d+) ", text, re.M)
        self.assertEqual(reported, ["S2"])


if __name__ == "__main__":
    unittest.main()
