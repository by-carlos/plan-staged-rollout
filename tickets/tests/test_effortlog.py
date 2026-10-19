"""Script tests for effortlog.py's create-issue `tally` subcommand.

The script lives under skills/staged-rollout, but these tests sit here so the
CI step that already runs tickets/tests covers them. No network. Run from
anywhere:

    python -m unittest discover -s tickets/tests -v
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "skills" / "staged-rollout" / "scripts"))

import effortlog

FILTERED = {
    "questions": [
        {"check": "guarded-field", "severity": "blocker", "question": "q1"},
        {"check": "scope", "severity": "gap", "question": "q2"},
        {"check": "links", "severity": "gap", "question": "q3"},
    ],
    "nits": [{"check": "title", "severity": "nit"}],
    "blockers": 1,
    "gaps_dropped": [{"check": "x", "severity": "gap"}, {"check": "y", "severity": "gap"}],
    "errors": [],
}
GITHUB_DRAFT = {"tracker": "github", "target": {"repo": "owner/repo"}, "title": "t"}
JIRA_DRAFT = {"tracker": "jira", "target": {"site": "acme.atlassian.net", "project": "WID"}, "title": "t"}


class TallyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name) / "work"
        self.work.mkdir()
        self.log = Path(self._tmp.name) / "logs" / "effort.ndjson"

    def write(self, name: str, data: dict) -> None:
        (self.work / name).write_text(json.dumps(data), encoding="utf-8")

    def tally(self, *extra: str, log: str | None = None) -> tuple[int, str, str]:
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_EFFORT_LOG"}
        if log is not None:
            env["CLAUDE_EFFORT_LOG"] = log
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = effortlog.main(["tally", "--work", str(self.work), *extra])
        return code, out.getvalue(), err.getvalue()

    def rows(self) -> list[dict]:
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def test_unset_writes_nothing(self):
        self.write("draft.json", GITHUB_DRAFT)
        self.write("review-filtered.json", FILTERED)
        code, out, _ = self.tally("--gate", "posted")
        self.assertEqual(code, 0)
        self.assertIn("nothing logged", out)
        self.assertFalse(self.log.parent.exists())
        self.assertEqual(sorted(p.name for p in self.work.iterdir()), ["draft.json", "review-filtered.json"])

    def test_empty_value_counts_as_unset(self):
        self.write("draft.json", GITHUB_DRAFT)
        code, _, _ = self.tally("--gate", "posted", log="")
        self.assertEqual(code, 0)
        self.assertFalse(self.log.exists())

    def test_set_appends_one_row_with_every_field(self):
        self.write("draft.json", GITHUB_DRAFT)
        self.write("review-filtered.json", FILTERED)
        code, _, _ = self.tally("--gate", "posted", "--ticket", "205", log=str(self.log))
        self.assertEqual(code, 0)
        (row,) = self.rows()
        self.assertEqual(row["source"], "create-issue")
        self.assertEqual(row["project"], "owner/repo")
        self.assertEqual(row["ticket"], "205")
        self.assertEqual(row["review"], "ran")
        self.assertIsNone(row["skip_reason"])
        self.assertEqual(row["blockers"], 1)
        self.assertEqual(row["gaps"], 2)
        self.assertEqual(row["questions_asked"], 3)
        self.assertEqual(row["nits_applied"], 1)
        self.assertEqual(row["gaps_dropped"], 2)
        self.assertEqual(row["gate"], "posted")
        self.assertTrue(row["changed_text"])
        self.assertIn("ts", row)
        self.assertIn("session_id", row)

    def test_rows_append(self):
        self.write("draft.json", GITHUB_DRAFT)
        self.tally("--gate", "posted", log=str(self.log))
        self.tally("--gate", "not-posted", log=str(self.log))
        self.assertEqual([r["gate"] for r in self.rows()], ["posted", "not-posted"])

    def test_not_posted_has_no_ticket(self):
        self.write("draft.json", GITHUB_DRAFT)
        self.write("review-filtered.json", FILTERED)
        self.tally("--gate", "not-posted", log=str(self.log))
        self.assertEqual(self.rows()[0]["ticket"], "not posted")

    def test_skipped_review(self):
        self.write("draft.json", JIRA_DRAFT)
        self.write("review-skipped.json", {"reason": "trivial typo fix"})
        self.tally("--gate", "edited-first", log=str(self.log))
        (row,) = self.rows()
        self.assertEqual(row["review"], "skipped")
        self.assertEqual(row["skip_reason"], "trivial typo fix")
        self.assertEqual(row["project"], "acme.atlassian.net/WID")
        self.assertEqual(row["questions_asked"], 0)
        self.assertEqual(row["gate"], "edited-first")
        self.assertFalse(row["changed_text"])

    def test_changed_text_rules(self):
        self.write("draft.json", GITHUB_DRAFT)
        no_nits = dict(FILTERED, nits=[])
        self.write("review-filtered.json", no_nits)
        self.tally("--gate", "posted", log=str(self.log))
        self.tally("--gate", "posted", "--answers-edited", log=str(self.log))
        self.write("review-filtered.json", FILTERED)
        self.tally("--gate", "posted", log=str(self.log))
        self.assertEqual([r["changed_text"] for r in self.rows()], [False, True, True])

    def test_failure_is_one_line_and_never_raises(self):
        self.write("draft.json", GITHUB_DRAFT)
        (self.work / "review-filtered.json").write_text("{not json", encoding="utf-8")
        code, _, err = self.tally("--gate", "posted", log=str(self.log))
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertFalse(self.log.exists())

    def test_unwritable_destination_is_one_line(self):
        self.write("draft.json", GITHUB_DRAFT)
        blocker = Path(self._tmp.name) / "file"
        blocker.write_text("x", encoding="utf-8")
        code, _, err = self.tally("--gate", "posted", log=str(blocker / "sub" / "log.ndjson"))
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_bad_gate_is_rejected(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.tally("--gate", "maybe", log=str(self.log))


if __name__ == "__main__":
    unittest.main()
