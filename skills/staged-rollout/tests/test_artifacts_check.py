"""Scripted check for `scripts/artifacts_check.py`.

Covers the `## Artifacts` parsing rule on the shapes the example plans use
(paths, directories, brace lists, flags, config keys, paths outside the
repository), the three ledger lines, and one end-to-end run in a throwaway git
repository: a stage whose changed files fall outside its declared artifacts,
and one whose do not.

Run from the repo root:
    python -m unittest discover -s skills/staged-rollout/tests -v
"""

import contextlib
import importlib.util
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts" / "artifacts_check.py"

spec = importlib.util.spec_from_file_location("artifacts_check", SCRIPT)
ac = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ac)


def stage(artifacts):
    return f"# S0 — Demo\n\n## Goal\n\nDemo.\n\n## Artifacts\n\n{artifacts}\n"


class DeclaredPaths(unittest.TestCase):
    def test_paths_and_directories_are_read(self):
        text = stage("`feeds.toml`, `pyproject.toml` (new dependency: `feedparser`),\n"
                     "`feed_digest/fetch.py`, `tests/`. The state file (`state.db`) is\n"
                     "runtime data and is git-ignored.")
        self.assertEqual(ac.declared_paths(text),
                         ["feeds.toml", "pyproject.toml", "feed_digest/fetch.py",
                          "tests/", "state.db"])

    def test_flags_config_keys_and_outside_paths_are_skipped(self):
        text = stage("the `--write-page` flag in `uptime/cli.py`, the `[project.scripts]`\n"
                     "entry, server-only `/etc/feed-digest/env` and `~/.config/x`.")
        self.assertEqual(ac.declared_paths(text), ["uptime/cli.py"])

    def test_brace_lists_expand(self):
        text = stage("`templates/{PLAN,LEDGER,stage-N}.md`")
        self.assertEqual(ac.declared_paths(text),
                         ["templates/PLAN.md", "templates/LEDGER.md", "templates/stage-N.md"])

    def test_prose_only_and_missing_sections_declare_nothing(self):
        self.assertEqual(ac.declared_paths(stage("Any new stage rows this review spawns.")), [])
        self.assertEqual(ac.declared_paths("# S0 — Demo\n\n## Goal\n\nDemo.\n"), [])

    def test_only_the_artifacts_section_is_read(self):
        text = "## Steps\n\n- edit `other.py`\n\n## Artifacts\n\n`a.py`\n\n## Notes\n\n`b.py`\n"
        self.assertEqual(ac.declared_paths(text), ["a.py"])


class Classify(unittest.TestCase):
    def test_all_changes_declared_is_a_match(self):
        line = ac.classify(["uptime/cli.py", "tests/"], ["uptime/cli.py", "tests/test_cli.py"])
        self.assertEqual(line, "Artifacts check: match")

    def test_undeclared_changes_are_listed(self):
        line = ac.classify(["uptime/cli.py"], ["uptime/cli.py", "uptime/render.py", "x.py"])
        self.assertEqual(line, "Artifacts check: outside: uptime/render.py, x.py")

    def test_no_declared_paths_is_undeclared_never_a_mismatch(self):
        self.assertEqual(ac.classify([], ["anything.py"]), "Artifacts check: undeclared")

    def test_plan_files_and_placeholders_never_count(self):
        line = ac.classify(["a.py"], ["a.py", ".plan/LEDGER.md", "commands/.gitkeep"])
        self.assertEqual(line, "Artifacts check: match")

    def test_globs_match(self):
        self.assertEqual(ac.classify(["deploy/*.timer"], ["deploy/feed.timer"]),
                         "Artifacts check: match")
        self.assertEqual(ac.classify(["deploy/*.timer"], ["deploy/feed.service"]),
                         "Artifacts check: outside: deploy/feed.service")


class EndToEnd(unittest.TestCase):
    """A real repository: a plan branch, then a stage branch with its own work."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.git("init", "-q", "-b", "plan-demo")
        (self.root / ".plan").mkdir()
        (self.root / ".plan" / "LEDGER.md").write_text("ledger\n", encoding="utf-8")
        (self.root / "app.py").write_text("print(1)\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "scaffold")
        self.git("switch", "-q", "-c", "plan-demo-s0")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                        "-c", "commit.gpgsign=false", *args],
                       cwd=self.root, check=True, capture_output=True)

    def run_check(self, artifacts):
        stage_file = self.root / ".plan" / "stage-0-demo.md"
        stage_file.write_text(stage(artifacts), encoding="utf-8")
        out = io.StringIO()
        cwd = os.getcwd()
        os.chdir(self.root)
        try:
            with contextlib.redirect_stdout(out):
                code = ac.main(["--stage-file", str(stage_file), "--base", "plan-demo"])
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 0)
        return out.getvalue().strip()

    def change_files(self):
        (self.root / "app.py").write_text("print(2)\n", encoding="utf-8")
        (self.root / "lib").mkdir()
        (self.root / "lib" / "util.py").write_text("x = 1\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "work")
        (self.root / "notes.txt").write_text("untracked\n", encoding="utf-8")
        (self.root / ".plan" / "LEDGER.md").write_text("ledger, updated\n", encoding="utf-8")

    def test_stage_inside_its_declared_artifacts(self):
        self.change_files()
        line = self.run_check("`app.py`, `lib/`, `notes.txt`.")
        self.assertEqual(line, "Artifacts check: match")

    def test_stage_outside_its_declared_artifacts(self):
        self.change_files()
        line = self.run_check("`app.py` only.")
        self.assertEqual(line, "Artifacts check: outside: lib/util.py, notes.txt")


if __name__ == "__main__":
    unittest.main()
