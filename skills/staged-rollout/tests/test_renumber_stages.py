"""Scripted check for `scripts/renumber_stages.py` (frozen decisions D-9 and D-10).

Builds a throwaway `.plan/` with a stage index, ledger, stage files and an
optional `BLOCKED.md`, edits the index the way a caller would (a new stage
inserted mid-plan), and asserts that only unstarted stages are renumbered --
index, file names, ledger rows, `depends`, `BLOCKED.md` and prose -- with SF
still last. Also asserts each refusal happens before anything is written.

Run from the repo root:
    python -m unittest discover -s skills/staged-rollout/tests -v
"""

import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts" / "renumber_stages.py"
TEMPLATE = SKILL / "references" / "templates" / "PLAN.md"

spec = importlib.util.spec_from_file_location("renumber_stages", SCRIPT)
rn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rn)

SLUG = "demo"

# The caller inserted `S6 Fix: login` where it should run (before S2) and
# extended SF's depends; S2-S4 are unstarted and must shift up by one.
INDEX = [
    ("S0 Keystone", "stage-0-keystone.md", "—"),
    ("S1 Core", "stage-1-core.md", "S0"),
    ("S6 Fix: login", "stage-6-fix-login.md", "S1"),
    ("S2 Parser", "stage-2-parser.md", "S1"),
    ("S3 Writer", "stage-3-writer.md", "S1"),
    ("S4 Docs", "stage-4-docs.md", "S2, S3"),
    ("SF Plan review", "stage-f-review.md", "S4, S6"),
]
LEDGER = {"S0": "done", "S1": "doing", "S6": "todo", "S2": "todo", "S3": "todo",
          "S4": "todo", "SF": "todo"}


def build_plan(root, index=INDEX, ledger=LEDGER, blocked=None):
    plan = Path(root) / ".plan"
    plan.mkdir()
    rows = "\n".join(
        f"| {stage} | `{file}` | {deps} | direct | inline | sonnet | high | auto |"
        for stage, file, deps in index
    )
    (plan / "PLAN.md").write_text(
        "# Demo plan\n\nS4 waits on S2 and S3; S1 is the core.\n\n"
        "## Stage index & dependencies\n\n"
        "| Stage | File | Depends | mode | exec | model | effort | gate |\n"
        "|---|---|---|---|---|---|---|---|\n" + rows + "\n\n"
        "Plan flags: `merge: manual`\n\n### Runnable set\n\nText.\n",
        encoding="utf-8",
    )
    lrows = "\n".join(
        f"| {stage} | {ledger[stage.split()[0]]} | — | — | — |" for stage, _, _ in index
    )
    notes = "\n".join(f"### {stage}\nnotes for {stage.split()[0]}\n" for stage, _, _ in index)
    (plan / "LEDGER.md").write_text(
        "# Demo ledger\n\n## Status\n\n| Stage | Status | Verified | Date | Result |\n"
        "|---|---|---|---|---|\n" + lrows + "\n\n## Notes\n\n" + notes,
        encoding="utf-8",
    )
    for stage, file, _ in index:
        sid = stage.split()[0]
        (plan / file).write_text(
            f"# {stage}\n\nRuns after S1; hands S4 the result. Own ID is {sid}.\n",
            encoding="utf-8",
        )
    if blocked:
        (plan / "BLOCKED.md").write_text(blocked, encoding="utf-8")
    return plan


def edit_plan(plan, old, new):
    path = plan / "PLAN.md"
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new), encoding="utf-8")


def snapshot(plan):
    return {p.name: p.read_bytes() for p in plan.iterdir()}


def git(cwd, *args):
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd, capture_output=True, text=True, check=True,
    )


class RenumberBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def run_renumber(self, plan, branch_ids=()):
        return rn.renumber(plan, SLUG, branch_ids=set(branch_ids))

    def index_ids(self, plan):
        text = (plan / "PLAN.md").read_text(encoding="utf-8")
        return [m.group(1) for l in text.splitlines()
                if (m := re.match(r"\| (S\d+[a-z]?|SF) ", l))]

    def assertRefused(self, plan, pattern, **kw):
        before = snapshot(plan)
        with self.assertRaisesRegex(rn.Refusal, pattern):
            self.run_renumber(plan, **kw)
        self.assertEqual(snapshot(plan), before, "a refusal must not write anything")


class Renumbering(RenumberBase):
    def test_only_unstarted_stages_are_renumbered_and_sf_stays_last(self):
        plan = build_plan(self.root)
        changed = self.run_renumber(plan)
        self.assertEqual(changed, [("S6", "S2"), ("S2", "S3"), ("S3", "S4"), ("S4", "S5")])
        self.assertEqual(self.index_ids(plan), ["S0", "S1", "S2", "S3", "S4", "S5", "SF"])

        plan_text = (plan / "PLAN.md").read_text(encoding="utf-8")
        self.assertIn("| S5 Docs | `stage-5-docs.md` | S3, S4 |", plan_text)
        self.assertIn("| SF Plan review | `stage-f-review.md` | S5, S2 |", plan_text)
        self.assertIn("S5 waits on S3 and S4; S1 is the core.", plan_text)

        ledger = (plan / "LEDGER.md").read_text(encoding="utf-8")
        self.assertIn("| S2 Fix: login | todo |", ledger)
        self.assertIn("| S5 Docs | todo |", ledger)
        self.assertIn("### S3 Parser\nnotes for S2", ledger.replace("S3 Parser\nnotes for S3", "S3 Parser\nnotes for S2"))
        self.assertIn("| S1 Core | doing |", ledger)

        names = sorted(p.name for p in plan.iterdir())
        self.assertEqual(
            names,
            ["LEDGER.md", "PLAN.md", "stage-0-keystone.md", "stage-1-core.md",
             "stage-2-fix-login.md", "stage-3-parser.md", "stage-4-writer.md",
             "stage-5-docs.md", "stage-f-review.md"],
        )
        prose = (plan / "stage-3-parser.md").read_text(encoding="utf-8")
        self.assertEqual(
            prose, "# S3 Parser\n\nRuns after S1; hands S5 the result. Own ID is S2.\n".replace(
                "Own ID is S2", "Own ID is S3"),
        )
        # started stages are untouched except for references to renumbered ones
        self.assertEqual(
            (plan / "stage-1-core.md").read_text(encoding="utf-8"),
            "# S1 Core\n\nRuns after S1; hands S5 the result. Own ID is S1.\n",
        )
        self.assertEqual(
            (plan / "stage-0-keystone.md").read_text(encoding="utf-8").splitlines()[0],
            "# S0 Keystone",
        )

    def test_second_run_changes_nothing(self):
        plan = build_plan(self.root)
        self.run_renumber(plan)
        before = snapshot(plan)
        self.assertEqual(self.run_renumber(plan), [])
        self.assertEqual(snapshot(plan), before)

    def test_blocked_sections_and_their_references_are_rewritten(self):
        blocked = "### S1\nWaiting on S3 to be reviewed.\n"
        plan = build_plan(self.root, blocked=blocked)
        self.run_renumber(plan)
        self.assertEqual(
            (plan / "BLOCKED.md").read_text(encoding="utf-8"),
            "### S1\nWaiting on S4 to be reviewed.\n",
        )

    def test_swap_of_two_numbers_does_not_collide(self):
        index = [
            ("S0 Keystone", "stage-0-keystone.md", "—"),
            ("S2 Parser", "stage-2-parser.md", "S0"),
            ("S1 Writer", "stage-1-writer.md", "S0"),
            ("SF Plan review", "stage-f-review.md", "S1, S2"),
        ]
        ledger = {"S0": "done", "S1": "todo", "S2": "todo", "SF": "todo"}
        plan = build_plan(self.root, index, ledger)
        self.assertEqual(self.run_renumber(plan), [("S2", "S1"), ("S1", "S2")])
        self.assertTrue((plan / "stage-1-parser.md").is_file())
        self.assertTrue((plan / "stage-2-writer.md").is_file())
        self.assertEqual(self.index_ids(plan), ["S0", "S1", "S2", "SF"])

    def test_a_started_suffixed_id_is_read_and_kept(self):
        index = [
            ("S0 Keystone", "stage-0-keystone.md", "—"),
            ("S1b Late fix", "stage-1b-late-fix.md", "S0"),
            ("S2 Parser", "stage-2-parser.md", "S1b"),
            ("SF Plan review", "stage-f-review.md", "S2"),
        ]
        ledger = {"S0": "done", "S1b": "done", "S2": "todo", "SF": "todo"}
        plan = build_plan(self.root, index, ledger)
        self.assertEqual(self.run_renumber(plan), [])
        self.assertTrue((plan / "stage-1b-late-fix.md").is_file())
        self.assertEqual(self.index_ids(plan), ["S0", "S1b", "S2", "SF"])


class StartedStagesKeepTheirNumber(RenumberBase):
    """S2 is out of order in the index; once started it must not move."""

    def check_s2_kept(self, plan, **kw):
        changed = self.run_renumber(plan, **kw)
        self.assertNotIn("S2", [old for old, _ in changed])
        self.assertTrue((plan / "stage-2-parser.md").is_file())
        self.assertIn("| S2 Parser | `stage-2-parser.md` |",
                      (plan / "PLAN.md").read_text(encoding="utf-8"))
        # the inserted stage, ahead of S2 in the index, takes the next free number
        self.assertIn(("S6", "S3"), changed)

    def test_non_todo_status(self):
        for status in ("doing", "done", "blocked", "skipped"):
            with self.subTest(status=status):
                root = Path(tempfile.mkdtemp(dir=self.root))
                plan = build_plan(root, ledger={**LEDGER, "S2": status})
                self.check_s2_kept(plan)

    def test_existing_stage_branch(self):
        plan = build_plan(self.root)
        self.check_s2_kept(plan, branch_ids={"S2"})

    def test_blocked_section(self):
        plan = build_plan(self.root, blocked="### S2\nWaiting on a reviewer.\n")
        self.check_s2_kept(plan)


class Refusals(RenumberBase):
    def test_suffixed_id_on_an_unstarted_stage(self):
        index = [(s.replace("S6 ", "S6b "), f.replace("6-", "6b-"), d) for s, f, d in INDEX]
        plan = build_plan(self.root, index, {**LEDGER, "S6b": "todo"})
        self.assertRefused(plan, "suffixed IDs are never created")

    def test_stage_cell_without_an_id(self):
        plan = build_plan(self.root)
        edit_plan(plan, "| S2 Parser |", "| Parser |")
        self.assertRefused(plan, "does not start with an ID")

    def test_file_cell_outside_the_grammar(self):
        for bad in ("stage-2-Parser.md", "stage-2-pa rser.md", "stage-2-../x.md",
                    "stage-2-parser.txt", "../stage-2-parser.md"):
            with self.subTest(file=bad):
                plan = build_plan(Path(tempfile.mkdtemp(dir=self.root)))
                edit_plan(plan, "`stage-2-parser.md`", f"`{bad}`")
                self.assertRefused(plan, "outside the grammar")

    def test_file_cell_without_backticks(self):
        plan = build_plan(self.root)
        edit_plan(plan, "`stage-2-parser.md`", "stage-2-parser.md")
        self.assertRefused(plan, "outside the grammar")

    def test_file_cell_naming_another_stage(self):
        plan = build_plan(self.root)
        edit_plan(plan, "`stage-2-parser.md`", "`stage-3-parser.md`")
        self.assertRefused(plan, "names a different stage ID")

    def test_path_that_escapes_the_plan_dir(self):
        plan = build_plan(self.root)
        outside = self.root / "outside.md"
        outside.write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(rn.Refusal, "resolves outside"):
            rn.safe_file(plan, "../outside.md")

    def test_symlinked_stage_file(self):
        plan = build_plan(self.root)
        target = self.root / "elsewhere.md"
        target.write_text("# S3 Writer\n", encoding="utf-8")
        (plan / "stage-3-writer.md").unlink()
        try:
            os.symlink(target, plan / "stage-3-writer.md")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available here")
        self.assertRefused(plan, "is a symlink")

    def test_symlink_is_refused_even_where_symlinks_cannot_be_made(self):
        plan = build_plan(self.root)
        real = rn.Path.is_symlink
        with mock.patch.object(
            rn.Path, "is_symlink",
            lambda p: p.name == "stage-3-writer.md" or real(p),
        ):
            self.assertRefused(plan, "stage-3-writer.md is a symlink")

    def test_symlinked_plan_dir(self):
        plan = build_plan(self.root)
        link = self.root / "link"
        try:
            os.symlink(plan, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available here")
        with self.assertRaisesRegex(rn.Refusal, "not a plain directory"):
            self.run_renumber(link)

    def test_duplicate_id(self):
        index = INDEX[:4] + [("S2 Again", "stage-2-again.md", "S1")] + INDEX[4:]
        plan = build_plan(self.root, index, LEDGER)
        self.assertRefused(plan, "S2 appears twice")

    def test_sf_not_last(self):
        index = INDEX[-1:] + INDEX[:-1]
        plan = build_plan(self.root, index)
        self.assertRefused(plan, "SF must be the last row")

    def test_depends_on_a_stage_below_it_in_the_index(self):
        index = [(s, f, "S4" if s.startswith("S2") else d) for s, f, d in INDEX]
        plan = build_plan(self.root, index)
        self.assertRefused(plan, "put S4's row above S2's")

    def test_depends_on_an_unknown_stage(self):
        index = [(s, f, "S9" if s.startswith("S2") else d) for s, f, d in INDEX]
        plan = build_plan(self.root, index)
        self.assertRefused(plan, "S9, which is not in the stage index")

    def test_depends_cell_that_is_not_an_id(self):
        index = [(s, f, "S1; rm -rf" if s.startswith("S2") else d) for s, f, d in INDEX]
        plan = build_plan(self.root, index)
        self.assertRefused(plan, "not a stage ID")

    def test_stage_with_no_ledger_row(self):
        plan = build_plan(self.root)
        path = plan / "LEDGER.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("| S3 Writer | todo |", "| X3 Writer | todo |"),
                        encoding="utf-8")
        self.assertRefused(plan, "S3 has no row in LEDGER.md")

    def test_missing_stage_file(self):
        plan = build_plan(self.root)
        (plan / "stage-3-writer.md").unlink()
        self.assertRefused(plan, "stage-3-writer.md does not exist")

    def test_target_name_taken_by_a_stray_file(self):
        plan = build_plan(self.root)
        (plan / "stage-2-fix-login.md").write_text("stray", encoding="utf-8")
        self.assertRefused(plan, "already exists and is not a stage being renumbered")

    def test_slug_outside_the_grammar(self):
        plan = build_plan(self.root)
        with self.assertRaisesRegex(rn.Refusal, "plan slug"):
            rn.renumber(plan, "Bad Slug", branch_ids=set())

    def test_not_valid_utf8(self):
        plan = build_plan(self.root)
        (plan / "stage-3-writer.md").write_bytes(b"\xff\xfe\x00bad")
        self.assertRefused(plan, "not valid UTF-8")


class BranchesAndCli(RenumberBase):
    def repo_with_plan(self):
        repo = self.root / "repo"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        plan = build_plan(repo)
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "plan")
        return repo, plan

    def test_branch_stage_ids_reads_local_remote_and_redo_branches(self):
        repo, _ = self.repo_with_plan()
        for name in (f"plan-{SLUG}-s2", f"plan-{SLUG}-s3-redo-1", f"plan-{SLUG}",
                     f"plan-{SLUG}-extra-s9", "plan-other-s4", f"feat/plan-{SLUG}-s8"):
            git(repo, "branch", name)
        git(repo, "update-ref", f"refs/remotes/origin/plan-{SLUG}-s7", "HEAD")
        self.assertEqual(rn.branch_stage_ids(repo, SLUG), {"S2", "S3", "S7"})

    def test_cli_keeps_a_stage_that_has_a_branch(self):
        repo, plan = self.repo_with_plan()
        git(repo, "branch", f"plan-{SLUG}-s2")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--slug", SLUG, "--plan-dir", str(plan)],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("S6 -> S3", proc.stdout)
        self.assertNotIn("S2 ->", proc.stdout)
        self.assertTrue((plan / "stage-2-parser.md").is_file())

    def test_cli_refuses_with_exit_2_and_writes_nothing(self):
        _, plan = self.repo_with_plan()
        (plan / "stage-3-writer.md").unlink()
        before = snapshot(plan)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--slug", SLUG, "--plan-dir", str(plan)],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("stage-3-writer.md does not exist", proc.stderr)
        self.assertEqual(snapshot(plan), before)

    def test_cli_outside_a_git_repo_cannot_tell_started_stages(self):
        plan = build_plan(self.root)
        before = snapshot(plan)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--slug", SLUG, "--plan-dir", str(plan)],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("cannot list branches", proc.stderr)
        self.assertEqual(snapshot(plan), before)


class TemplateIntegration(unittest.TestCase):
    def test_template_points_the_new_stage_sentence_at_the_script(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("renumber_stages.py", text)


if __name__ == "__main__":
    unittest.main()
