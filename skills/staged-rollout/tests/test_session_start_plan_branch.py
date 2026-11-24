"""Scripted check that the session-start hook reads the plan from the plan
branch (issue #304).

A copy of `.plan/` left on main (or any non-plan branch) can be stale: the real
plan, on its `plan-*` branch, may have finished stages that copy still shows as
`todo`. The hook must announce from the plan branch when exactly one exists,
from the working tree when none does, and name the branches (announcing no
stage) when several do.

Run from the repo root:
    python -m unittest discover -s skills/staged-rollout/tests -v
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
ROOT = SKILL.parents[1]
HOOK = ROOT / "hooks" / "session-start"
FIXTURE = SKILL / "tests" / "fixtures" / "live-plan" / ".plan"

GIT_ID = ["-c", "user.name=Test", "-c", "user.email=test@example.invalid",
          "-c", "commit.gpgsign=false"]


def find_bash():
    for candidate in (shutil.which("bash"),
                      r"C:\Program Files\Git\bin\bash.exe",
                      r"C:\Program Files\Git\usr\bin\bash.exe"):
        if candidate and Path(candidate).exists():
            return candidate
    return None


def git(repo, *args):
    return subprocess.run(["git", *GIT_ID, "-C", str(repo), *args],
                          capture_output=True, text=True, check=True,
                          encoding="utf-8").stdout.strip()


def mark_all_done(plan_dir):
    ledger = Path(plan_dir) / "LEDGER.md"
    ledger.write_text(ledger.read_text(encoding="utf-8")
                      .replace("| todo |", "| done |"), encoding="utf-8")


def run_hook(repo):
    """The hook's additionalContext in `repo`, or "" when it emits nothing."""
    bash = find_bash()
    if bash is None:
        raise unittest.SkipTest("bash is not available")
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(ROOT))
    env.pop("COPILOT_CLI", None)
    env.pop("CURSOR_PLUGIN_ROOT", None)
    out = subprocess.run([bash, str(HOOK)], cwd=str(repo), env=env,
                         capture_output=True, text=True, check=True,
                         encoding="utf-8").stdout
    if not out.strip():
        return ""
    return json.loads(out)["hookSpecificOutput"]["additionalContext"]


class PlanBranchTest(unittest.TestCase):
    def setUp(self):
        if shutil.which("git") is None:
            self.skipTest("git is not available")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        # main carries the STALE copy: S1 and later still `todo`.
        shutil.copytree(FIXTURE, self.repo / ".plan")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "stale plan copy")

    def add_plan_branch(self, name, ref=None):
        """A plan branch whose ledger has every stage done; back on main."""
        git(self.repo, "switch", "-q", "-c", name, "main")
        mark_all_done(self.repo / ".plan")
        git(self.repo, "commit", "-q", "-am", "plan finished")
        if ref:
            git(self.repo, "update-ref", ref, name)
            git(self.repo, "switch", "-q", "main")
            git(self.repo, "branch", "-q", "-D", name)
        else:
            git(self.repo, "switch", "-q", "main")

    def test_no_plan_branch_reads_the_working_tree(self):
        context = run_hook(self.repo)
        self.assertIn("S1", context)
        self.assertIn("Build the API", context)
        self.assertNotIn("plan branch", context)

    def test_stale_copy_on_main_is_not_announced(self):
        self.add_plan_branch("plan-demo")
        context = run_hook(self.repo)
        self.assertNotIn("Build the API", context)
        self.assertIn("ready for closeout", context)
        self.assertIn("plan branch `plan-demo`", context)

    def test_remote_tracking_plan_branch_is_read(self):
        self.add_plan_branch("plan-demo", ref="refs/remotes/origin/plan-demo")
        context = run_hook(self.repo)
        self.assertNotIn("Build the API", context)
        self.assertIn("ready for closeout", context)
        self.assertIn("git show origin/plan-demo:.plan/", context)

    def test_local_and_remote_twin_count_once(self):
        self.add_plan_branch("plan-demo")
        git(self.repo, "update-ref", "refs/remotes/origin/plan-demo",
            "plan-demo")
        context = run_hook(self.repo)
        self.assertIn("ready for closeout", context)
        self.assertNotIn("Several plan branches", context)

    def test_several_plan_branches_name_them_and_announce_no_stage(self):
        self.add_plan_branch("plan-one")
        self.add_plan_branch("plan-two")
        context = run_hook(self.repo)
        self.assertIn("Several plan branches", context)
        self.assertIn("`plan-one`", context)
        self.assertIn("`plan-two`", context)
        self.assertNotIn("Build the API", context)
        self.assertNotIn("stage-run", context)
        self.assertNotIn("closeout", context)

    def test_branch_without_a_plan_folder_is_not_a_plan_branch(self):
        git(self.repo, "branch", "plan-notes", "main")
        git(self.repo, "switch", "-q", "plan-notes")
        git(self.repo, "rm", "-q", "-r", ".plan")
        git(self.repo, "commit", "-q", "-m", "notes, not a rollout")
        git(self.repo, "switch", "-q", "main")
        context = run_hook(self.repo)
        self.assertIn("Build the API", context)  # still the working tree

    def test_on_the_plan_branch_reads_its_working_tree(self):
        self.add_plan_branch("plan-demo")
        git(self.repo, "switch", "-q", "plan-demo")
        context = run_hook(self.repo)
        self.assertIn("ready for closeout", context)
        self.assertNotIn("read from the plan branch", context)

    def test_plan_branch_alone_announces_on_a_branch_without_plan(self):
        self.add_plan_branch("plan-demo")
        git(self.repo, "rm", "-q", "-r", ".plan")
        git(self.repo, "commit", "-q", "-m", "drop the stale copy")
        context = run_hook(self.repo)
        self.assertIn("ready for closeout", context)

    def test_no_plan_anywhere_emits_nothing(self):
        git(self.repo, "rm", "-q", "-r", ".plan")
        git(self.repo, "commit", "-q", "-m", "no plan")
        self.assertEqual(run_hook(self.repo), "")


if __name__ == "__main__":
    unittest.main()
