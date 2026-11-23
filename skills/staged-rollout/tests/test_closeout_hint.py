"""Scripted check for the closeout launch hint (issue #296).

`/plan-close` defines one recommended model and effort for closeout, in
`commands/plan-close.md`; every message that sends the user to closeout names
it. This pins that the definition exists, that the session-start hook's
all-done message carries it (the hook reads it from the command file, so there
is no second copy to drift), and that the other closeout handoffs point at it.

Run from the repo root:
    python -m unittest discover -s skills/staged-rollout/tests -v
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
ROOT = SKILL.parents[1]
PLAN_CLOSE = ROOT / "commands" / "plan-close.md"
HOOK = ROOT / "hooks" / "session-start"
FIXTURE = SKILL / "tests" / "fixtures" / "live-plan" / ".plan"

HINT = re.compile(r"^> \*\*(model `[^`]+`, effort `[^`]+`)\*\*", re.MULTILINE)

# Every file that hands the user to closeout and so must point at the hint.
HANDOFFS = [
    ROOT / "commands" / "stage-run.md",
    ROOT / "commands" / "plan-run-local.md",
    ROOT / "commands" / "plan-run-cloud.md",
    SKILL / "references" / "templates" / "PLAN.md",
    ROOT / "examples" / "feed-digest" / ".plan" / "PLAN.md",
    ROOT / "examples" / "uptime-page" / ".plan" / "PLAN.md",
]


def flat(path):
    """The file's text with line wraps folded to single spaces."""
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def find_bash():
    candidates = [shutil.which("bash"),
                  r"C:\Program Files\Git\bin\bash.exe",
                  r"C:\Program Files\Git\usr\bin\bash.exe"]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def hook_context(plan_dir):
    """Run the session-start hook in a repo whose .plan/ is `plan_dir`."""
    bash = find_bash()
    if bash is None:
        raise unittest.SkipTest("bash is not available")
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(plan_dir, Path(tmp) / ".plan")
        ledger = Path(tmp) / ".plan" / "LEDGER.md"
        ledger.write_text(ledger.read_text(encoding="utf-8")
                          .replace("| todo |", "| done |"), encoding="utf-8")
        env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(ROOT))
        env.pop("COPILOT_CLI", None)
        env.pop("CURSOR_PLUGIN_ROOT", None)
        out = subprocess.run([bash, str(HOOK)], cwd=tmp, env=env,
                             capture_output=True, text=True, check=True,
                             encoding="utf-8").stdout
    return json.loads(out)["hookSpecificOutput"]["additionalContext"]


class CloseoutHintTest(unittest.TestCase):
    def test_plan_close_defines_one_hint(self):
        text = PLAN_CLOSE.read_text(encoding="utf-8")
        hints = HINT.findall(text)
        self.assertEqual(len(hints), 1, "exactly one model/effort definition")
        self.assertIn("## Launch hint", text)

    def test_all_done_hook_names_the_model_and_effort(self):
        hint = HINT.search(PLAN_CLOSE.read_text(encoding="utf-8")).group(1)
        context = hook_context(FIXTURE)
        self.assertIn("ready for closeout", context)
        self.assertIn(hint, context)
        self.assertRegex(context, r"model `\w+`")
        self.assertRegex(context, r"effort `\w+`")

    def test_every_handoff_points_at_the_hint(self):
        for path in HANDOFFS:
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertIn("Launch hint", flat(path))


if __name__ == "__main__":
    unittest.main()
