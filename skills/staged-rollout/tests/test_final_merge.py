"""Scripted check for `scripts/final_merge.py`.

Covers the decision on fixtures shaped like the two `gh api` responses (a
repository that allows merge commits, a squash-only repository, a ruleset that
narrows the settings, rebase-only, unreadable lookups) and the PR body line
each recorded method produces. The fixtures use generic values only.

Run from the repo root:
    python -m unittest discover -s skills/staged-rollout/tests -v
"""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts" / "final_merge.py"

spec = importlib.util.spec_from_file_location("final_merge", SCRIPT)
fm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fm)


def settings(merge=True, squash=True, rebase=True):
    return {"allow_merge_commit": merge, "allow_squash_merge": squash,
            "allow_rebase_merge": rebase}


def pr_rule(*methods):
    return {"type": "pull_request",
            "parameters": {"allowed_merge_methods": list(methods)}}


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fm.main(argv)
    return code, out.getvalue().strip(), err.getvalue()


class Decide(unittest.TestCase):
    def test_merge_commit_allowed_keeps_the_normal_merge(self):
        self.assertEqual(fm.decide(settings(), []), "merge")

    def test_squash_only_settings_give_squash(self):
        self.assertEqual(fm.decide(settings(merge=False, rebase=False), []), "squash")

    def test_ruleset_narrows_the_settings(self):
        rules = [pr_rule("squash")]
        self.assertEqual(fm.decide(settings(), rules), "squash")

    def test_every_pull_request_rule_must_allow_the_method(self):
        rules = [pr_rule("merge", "squash"), pr_rule("squash")]
        self.assertEqual(fm.decide(settings(), rules), "squash")

    def test_ruleset_cannot_widen_the_settings(self):
        rules = [pr_rule("merge", "squash", "rebase")]
        self.assertEqual(fm.decide(settings(merge=False), rules), "squash")

    def test_rules_of_other_types_and_without_methods_are_ignored(self):
        rules = [{"type": "deletion"}, {"type": "pull_request", "parameters": {}}]
        self.assertEqual(fm.decide(settings(), rules), "merge")

    def test_rebase_only_asks(self):
        self.assertEqual(fm.decide(settings(merge=False, squash=False), []), "ask")
        self.assertEqual(fm.decide(settings(), [pr_rule("rebase")]), "ask")

    def test_nothing_allowed_asks(self):
        self.assertEqual(fm.decide(settings(False, False, False), []), "ask")

    def test_unreadable_lookups_are_unchecked(self):
        self.assertEqual(fm.decide(None, []), "unchecked")
        self.assertEqual(fm.decide(settings(), None), "unchecked")
        self.assertEqual(fm.decide({"message": "Not Found"}, []), "unchecked")
        self.assertEqual(fm.decide({"allow_merge_commit": True}, []), "unchecked")


class Cli(unittest.TestCase):
    def write(self, tmp, name, data):
        path = Path(tmp) / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    def test_squash_only_repository_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.write(tmp, "repo.json", settings(merge=False))
            rules = self.write(tmp, "rules.json", [])
            code, word, _ = run(["decide", "--repo-json", repo, "--rules-json", rules])
            self.assertEqual((code, word), (0, "squash"))
            code, line, _ = run(["line", "--method", word])
            self.assertEqual(code, 0)
            self.assertIn("squash merge", line.lower())
            self.assertNotIn("normal merge", line)

    def test_merge_commit_repository_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.write(tmp, "repo.json", settings())
            rules = self.write(tmp, "rules.json", [])
            code, word, _ = run(["decide", "--repo-json", repo, "--rules-json", rules])
            self.assertEqual((code, word), (0, "merge"))
            code, line, _ = run(["line", "--method", word])
            self.assertIn("normal merge (merge commit), not squash", line)
            self.assertNotIn("not checked", line)

    def test_missing_or_broken_files_are_unchecked(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.write(tmp, "repo.json", settings())
            broken = Path(tmp) / "rules.json"
            broken.write_text("not json", encoding="utf-8")
            self.assertEqual(run(["decide", "--repo-json", repo])[1], "unchecked")
            self.assertEqual(run(["decide", "--repo-json", repo,
                                  "--rules-json", str(broken)])[1], "unchecked")
            self.assertEqual(run(["decide", "--repo-json", str(Path(tmp) / "none.json"),
                                  "--rules-json", str(broken)])[1], "unchecked")

    def test_unchecked_line_keeps_the_normal_merge_and_says_so(self):
        _, line, _ = run(["line", "--method", "unchecked"])
        self.assertIn("normal merge (merge commit), not squash", line)
        self.assertIn("were not checked", line)

    def test_unknown_method_is_refused(self):
        code, out, err = run(["line", "--method", "ask"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("unknown method", err)


if __name__ == "__main__":
    unittest.main()
