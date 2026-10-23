"""Script tests for write_guard.py (the opt-in tracker-create guard) and the
ticket_core commands that leave its evidence: prepare, review-skip and
review-filter's review-filtered.json. The Jira relay-token round trip is in
tickets/scripts/tests/test_jira_adapter.py, beside its fixtures.

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
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ticket_core
import ticket_template
import write_guard

V2 = "mcp__plugin_atlassian_atlassian__"


class GuardCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self._old = os.environ.get("CLAUDE_CONFIG_DIR")
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.dir)

    def tearDown(self):
        if self._old is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = self._old
        self.tmp.cleanup()

    def guard_on(self):
        (self.dir / "plan-staged-rollout.toml").write_text("guard_tracker_creates = true\n", encoding="utf-8")

    def decide(self, tool, tool_input):
        return write_guard.decide({"tool_name": tool, "tool_input": tool_input})


class Off(GuardCase):
    def test_off_by_default_stays_out_of_every_decision(self):
        self.assertIsNone(self.decide(V2 + "createJiraIssue", {"summary": "x"}))
        self.assertIsNone(self.decide("Bash", {"command": "gh issue create --title x --body y"}))

    def test_false_and_broken_config_leave_it_off(self):
        cfg = self.dir / "plan-staged-rollout.toml"
        cfg.write_text("guard_tracker_creates = false\n", encoding="utf-8")
        self.assertFalse(write_guard.guard_enabled())
        cfg.write_text("guard_tracker_creates = [\n", encoding="utf-8")
        self.assertFalse(write_guard.guard_enabled())


class On(GuardCase):
    def setUp(self):
        super().setUp()
        self.guard_on()

    def test_execute_write_create_is_denied_and_link_is_not(self):
        self.assertEqual(self.decide(V2 + "executeWrite", {"name": "createJiraIssue"})[0], "deny")
        self.assertIsNone(self.decide(V2 + "executeWrite", {"name": "createJiraIssueLink"}))

    def test_bash_issue_creates_are_denied(self):
        for cmd in ("gh issue create --title x --body y",
                    "cd repo && gh issue create -t x -b y",
                    "gh api repos/o/r/issues -f title=x",
                    "gh api repos/o/r/issues --input body.json",
                    "gh api -X POST repos/o/r/issues",
                    "gh  issue create -t x",
                    "GH_REPO=o/r gh issue create -t x",
                    "command gh issue create -t x",
                    "echo $(gh issue create -t x)",
                    "gh api repos/o/r/issues \\\n  --method POST",
                    "gh api repos/o/r/issues \\\n  -f title=x"):
            self.assertEqual(self.decide("Bash", {"command": cmd})[0], "deny", cmd)

    def test_other_gh_calls_pass(self):
        for cmd in ("gh issue list", "gh issue edit 4 --body x", "gh api repos/o/r/issues",
                    "gh api repos/o/r/issues/4/comments -f body=x", "gh pr create --fill", "ls",
                    "git commit -F - <<'EOF'\nfeat: x\n\ndenies gh issue create from Bash\nEOF",
                    "git commit -m \"block gh api repos/o/r/issues -f title=x\"",
                    "gh api repos/o/r/issues && git commit -F m.txt",
                    "gh api repos/o/r/issues -X GET -f state=closed",
                    "cat <<EOF > notes.md\ngh issue create -t x\nEOF",
                    "git commit -m 'a | gh issue create'"):
            self.assertIsNone(self.decide("Bash", {"command": cmd}), cmd)

    def test_token_ignores_the_server_prefix_and_expires(self):
        spec = {"tool": V2 + "createJiraIssue", "arguments": {"summary": "x"}}
        write_guard.issue_token(spec)
        self.assertIsNone(self.decide("mcp__other__createJiraIssue", {"summary": "x"}))
        write_guard.issue_token(spec)
        token = next((self.dir / "plan-staged-rollout" / "allowed-writes").glob("*.json"))
        old = token.stat().st_mtime - write_guard.TOKEN_TTL - 60
        os.utime(token, (old, old))
        self.assertEqual(self.decide(V2 + "createJiraIssue", {"summary": "x"})[0], "deny")

    def test_issued_token_passes_with_no_decision_once(self):
        spec = {"tool": V2 + "createJiraIssue", "arguments": {"summary": "y"}}
        self.assertTrue(write_guard.issue_token(spec))
        self.assertIsNone(self.decide(V2 + "createJiraIssue", {"summary": "y"}))
        decision, reason = self.decide(V2 + "createJiraIssue", {"summary": "y"})
        self.assertEqual(decision, "deny")
        self.assertIn("create --confirm", reason)

    def test_unwritable_token_folder_never_fails_the_adapter(self):
        (self.dir / "plan-staged-rollout").write_text("a file where a folder should be", encoding="utf-8")
        self.assertFalse(write_guard.issue_token({"tool": V2 + "createJiraIssue", "arguments": {}}))

    def test_hook_cli_prints_a_decision(self):
        event = json.dumps({"tool_name": "Bash", "tool_input": {"command": "gh issue create -t x"}})
        out = io.StringIO()
        with contextlib.redirect_stdout(out), unittest.mock.patch("sys.stdin", io.StringIO(event)):
            write_guard.run_hook()
        self.assertEqual(json.loads(out.getvalue())["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_hook_cli_reads_utf8_even_on_a_cp1252_stdin(self):
        args = {"summary": "x", "description": "## ℹ️ In plain terms"}
        self.assertTrue(write_guard.issue_token({"tool": V2 + "createJiraIssue", "arguments": args}))
        event = json.dumps({"tool_name": V2 + "createJiraIssue", "tool_input": args}, ensure_ascii=False)
        stdin = io.TextIOWrapper(io.BytesIO(event.encode("utf-8")), encoding="cp1252", errors="surrogateescape")
        stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        with unittest.mock.patch("sys.stdin", stdin), unittest.mock.patch("sys.stdout", stdout):
            write_guard.main(["hook"])
            stdout.flush()
            printed = stdout.buffer.getvalue()
        self.assertEqual(printed, b"", "a token issued for this exact call should pass with no decision")


class Gate(GuardCase):
    def test_reports_each_missing_step(self):
        errors = write_guard.pipeline_gate(self.dir, {})
        self.assertEqual(len(errors), 3)
        for word in ("template.json", "review", "estimate.json"):
            self.assertTrue(any(word in e for e in errors), word)

    def test_review_skip_counts_as_a_review(self):
        t, _ = ticket_template.validate_template("default", "jira")
        (self.dir / "template.json").write_text(json.dumps({"template": t, "source": "default"}), encoding="utf-8")
        (self.dir / "estimate.json").write_text("{}", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            ticket_core.main(["review-skip", "--work", str(self.dir), "--reason", "skip_when: automated"])
        self.assertEqual(write_guard.pipeline_gate(self.dir, t), [])


class Prepare(GuardCase):
    def run_core(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = ticket_core.main([str(a) for a in argv])
        return code, out.getvalue()

    def test_resolves_then_checks_then_writes_the_review_prompt(self):
        work = self.dir / "work"
        code, out = self.run_core("prepare", "--work", work, "--tracker", "jira", "--project-dir", self.dir)
        self.assertEqual(code, 0, out)
        self.assertTrue((work / "template.json").is_file())
        self.assertIn("draft", json.loads(out)["next"])

        (work / "draft.json").write_text(json.dumps({"tracker": "jira", "title": "x", "sections": {}}),
                                         encoding="utf-8")
        code, out = self.run_core("prepare", "--work", work, "--tracker", "jira", "--project-dir", self.dir)
        self.assertEqual(code, 1, out)
        self.assertFalse((work / "review-prompt.md").exists())

    def test_review_filter_writes_its_output_beside_the_review(self):
        t, _ = ticket_template.validate_template("default", "jira")
        tpath = self.dir / "template.json"
        tpath.write_text(json.dumps(t), encoding="utf-8")
        review = self.dir / "review.json"
        review.write_text("[]", encoding="utf-8")
        code, _ = self.run_core("review-filter", "--template", tpath, review)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads((self.dir / "review-filtered.json").read_text(encoding="utf-8"))["blockers"], 0)


if __name__ == "__main__":
    unittest.main()
