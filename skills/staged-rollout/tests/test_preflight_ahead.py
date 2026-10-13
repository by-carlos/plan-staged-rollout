"""Scripted check for PLAN.md protocol step 0.2 ("Sync the plan branch").

Builds a throwaway origin + clone, then runs the commands the template
documents against the equal, behind and ahead cases. Asserts the ahead check
`git rev-list --count origin/plan-<slug>..plan-<slug>` reports the unpushed
commits that `git merge --ff-only` lets through, and stays 0 for equal/behind.

Run from the repo root:
    python -m unittest discover -s skills/staged-rollout/tests -v
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

SLUG = "demo"
BRANCH = f"plan-{SLUG}"
TEMPLATE = (
    Path(__file__).resolve().parents[1] / "references" / "templates" / "PLAN.md"
)


def git(cwd, *args, check=True):
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd, capture_output=True, text=True, check=check,
    )


def commit(cwd, name):
    (Path(cwd) / name).write_text(name, encoding="utf-8")
    git(cwd, "add", name)
    git(cwd, "commit", "-m", name)


def ahead_count(cwd):
    return int(git(cwd, "rev-list", "--count", f"origin/{BRANCH}..{BRANCH}").stdout)


class PreflightAheadCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.origin = root / "origin.git"
        self.clone = root / "clone"
        self.other = root / "other"
        git(root, "init", "--bare", "-b", "main", str(self.origin))
        git(root, "clone", str(self.origin), str(self.clone))
        git(self.clone, "checkout", "-b", BRANCH)
        commit(self.clone, "base")
        git(self.clone, "push", "-u", "origin", BRANCH)
        git(root, "clone", str(self.origin), str(self.other))
        git(self.other, "checkout", BRANCH)

    def test_equal_passes(self):
        git(self.clone, "fetch", "origin")
        git(self.clone, "merge", "--ff-only", f"origin/{BRANCH}")
        self.assertEqual(ahead_count(self.clone), 0)

    def test_behind_fast_forwards_and_passes(self):
        commit(self.other, "remote-only")
        git(self.other, "push", "origin", BRANCH)
        git(self.clone, "fetch", "origin")
        git(self.clone, "merge", "--ff-only", f"origin/{BRANCH}")
        self.assertEqual(ahead_count(self.clone), 0)

    def test_ahead_is_not_caught_by_ff_only_but_is_by_the_check(self):
        commit(self.clone, "unpushed")
        git(self.clone, "fetch", "origin")
        merge = git(self.clone, "merge", "--ff-only", f"origin/{BRANCH}", check=False)
        self.assertEqual(merge.returncode, 0)
        self.assertIn("Already up to date", merge.stdout)
        self.assertEqual(ahead_count(self.clone), 1)

    def test_ahead_fetch_variant_already_refuses(self):
        git(self.clone, "checkout", "-b", "scratch")
        git(self.clone, "checkout", BRANCH)
        commit(self.clone, "unpushed")
        git(self.clone, "checkout", "scratch")
        fetch = git(self.clone, "fetch", "origin", f"{BRANCH}:{BRANCH}", check=False)
        self.assertNotEqual(fetch.returncode, 0)

    def test_template_documents_the_check(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("git rev-list --count\n      origin/plan-<slug>..plan-<slug>", text)
        self.assertNotIn("both refuse non-fast-forward", text)


if __name__ == "__main__":
    unittest.main()
