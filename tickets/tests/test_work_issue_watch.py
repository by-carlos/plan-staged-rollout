"""Tests for the `--after` watch loop printed in skills/work-issue/SKILL.md.

The loop is run exactly as the skill prints it, against a stand-in `gh` and a
`sleep` that returns at once. Run from anywhere:

    python3 -m unittest discover -s tickets/tests -v
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "skills" / "work-issue" / "SKILL.md"


def watch_loop() -> str:
    section = SKILL.read_text(encoding="utf-8").split("**Arm the watch**", 1)[1]
    block = re.search(r"```bash\n(.*?)\n *```", section, re.DOTALL).group(1)
    return (block.replace("<owner/repo>", "example-org/widgets")
            .replace("<blocker>", "41"))


@unittest.skipIf(os.name == "nt", "stands in for gh with a shell script on PATH")
class WatchLoopTests(unittest.TestCase):
    def run_loop(self, gh: str) -> tuple[int, str, int]:
        """Run the loop with `gh` as the body of the stand-in; `$n` there is
        the number of the call. Returns exit code, output and calls made."""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        count = tmp / "calls"
        counting = f'n=$(( $(cat "{count}" 2>/dev/null || echo 0) + 1 ))\necho "$n" > "{count}"\n'
        for name, body in (("gh", counting + gh), ("sleep", "exit 0")):
            (tmp / name).write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
            (tmp / name).chmod(0o755)
        env = {**os.environ, "PATH": f"{tmp}{os.pathsep}{os.environ['PATH']}", "TMPDIR": str(tmp)}
        proc = subprocess.run(["bash", "-c", watch_loop()], env=env, capture_output=True,
                              text=True, timeout=60, check=False)
        return proc.returncode, proc.stdout.strip(), int(count.read_text())

    def test_fires_when_the_blocker_closes(self):
        code, out, calls = self.run_loop(
            'if [ "$n" -lt 3 ]; then echo "open "; else echo "closed completed"; fi')
        self.assertEqual((code, out, calls), (0, "blocker #41 closed: closed completed", 3))

    def test_reports_the_error_after_repeated_failures(self):
        code, out, calls = self.run_loop('echo "gh: Not Found (HTTP 404)" >&2; exit 1')
        self.assertEqual((code, calls), (1, 30), out)
        self.assertIn("30 lookups of blocker #41 failed in a row", out)
        self.assertIn("gh: Not Found (HTTP 404)", out)

    def test_a_success_resets_the_failure_count(self):
        # 29 failures, one good read, 29 more, then the close: never 30 in a row.
        code, out, calls = self.run_loop(
            'if [ "$n" -eq 30 ]; then echo "open "\n'
            'elif [ "$n" -eq 60 ]; then echo "closed not_planned"\n'
            'else exit 1; fi')
        self.assertEqual((code, out, calls), (0, "blocker #41 closed: closed not_planned", 60))


if __name__ == "__main__":
    unittest.main()
