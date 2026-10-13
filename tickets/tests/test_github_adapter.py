"""Script tests for the GitHub adapter and the body guard hook.

No network and no real `gh`: every call goes through a fake that returns
recorded-shape responses from fixtures/github/. Run from anywhere:

    python -m unittest discover -s tickets/tests -v
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
HOOKS = ROOT.parent / "hooks"  # the plugin's hooks sit at its root, beside tickets/

import github_adapter as ga
import ticket_template

# Keep the user's own plan-staged-rollout.toml (which may turn the write guard on) out of these tests.
os.environ["CLAUDE_CONFIG_DIR"] = tempfile.mkdtemp(prefix="psr-test-config-")

FIX = ROOT / "fixtures" / "github"
REPO = "example-org/widgets"


def fixture(name: str):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


class FakeGh:
    """Stands in for `gh`. Routes match by substring on the joined args; the
    first match wins. A list response is consumed in order, the last item
    repeating."""

    def __init__(self):
        self.routes: list[list] = []
        self.calls: list[tuple[list[str], str | None]] = []

    def on(self, needle: str, out="", rc: int = 0, err: str = ""):
        self.routes.append([needle, out, rc, err])
        return self

    def __call__(self, args, input_text=None):
        line = " ".join(args)
        self.calls.append((list(args), input_text))
        for route in self.routes:
            needle, out, rc, err = route
            if needle in line:
                if isinstance(out, list):
                    value = out.pop(0) if len(out) > 1 else out[0]
                else:
                    value = out
                if callable(value):
                    value = value(args, input_text)
                if not isinstance(value, str):
                    value = json.dumps(value)
                return subprocess.CompletedProcess(args, rc, value, err)
        return subprocess.CompletedProcess(args, 1, "", f"no route for: {line}")

    def seen(self, needle: str) -> list[tuple[list[str], str | None]]:
        return [c for c in self.calls if needle in " ".join(c[0])]


class AdapterCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self._env = os.environ.get("TICKETS_CACHE_DIR")
        os.environ["TICKETS_CACHE_DIR"] = str(self.tmp / "cache")
        self.fake = FakeGh()
        self._orig = ga.run_gh
        ga.run_gh = self.fake
        self.addCleanup(self._restore)

    def _restore(self):
        ga.run_gh = self._orig
        if self._env is None:
            os.environ.pop("TICKETS_CACHE_DIR", None)
        else:
            os.environ["TICKETS_CACHE_DIR"] = self._env

    # helpers -------------------------------------------------------------

    def run_op(self, *argv) -> tuple[int, dict]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = ga.main([str(a) for a in argv])
        text = buf.getvalue()
        return code, (json.loads(text) if text.strip() else {})

    def write(self, name: str, obj) -> str:
        path = self.tmp / name
        path.write_text(json.dumps(obj), encoding="utf-8")
        return str(path)

    def routed_template(self) -> str:
        resolved = ticket_template.resolve("github", ROOT, None, str(FIX / "routed.toml"))
        return self.write("template.json", resolved)

    def default_template(self) -> str:
        return self.write("default.json", ticket_template.resolve("github", self.tmp, None, None))

    def build(self, draft=None, template=None, *extra) -> tuple[int, dict]:
        draft_path = str(FIX / "draft-routed.json") if draft is None else self.write("draft.json", draft)
        self.fake.on("orgs/example-org/issue-types", json.dumps(fixture("issue-types.json")))
        return self.run_op("build", "--template", template or self.routed_template(),
                           "--draft", draft_path, *extra)

    def payload(self, **over) -> str:
        code, built = self.build()
        self.assertEqual(code, 0, built)
        built.update(over)
        built.pop("warnings", None)
        return self.write("payload.json", built)

    def api_response(self, issue: dict, number: int = 42, **over) -> dict:
        resp = {"number": number, "html_url": f"https://github.com/{REPO}/issues/{number}",
                "title": issue["title"], "body": issue["body"].replace("\n", "\r\n"),
                "labels": [{"name": x} for x in issue["labels"]], "state": "open",
                "type": {"name": issue["type"]} if issue.get("type") else None}
        resp.update(over)
        return resp


class BuildTests(AdapterCase):
    def test_routed_draft_maps_board_values_and_type(self):
        code, out = self.build()
        self.assertEqual(code, 0, out)
        self.assertEqual(out["board"], {"owner": "example-org", "number": 7,
                                        "values": {"Priority": "P1", "Size": "S", "Effort": "low"}})
        self.assertEqual(out["issue"]["type"], "Task")
        self.assertEqual(out["issue"]["labels"], ["bug"])
        self.assertIn("caf\u00e9 \u2713", out["issue"]["body"])
        self.assertEqual(out["proposal_only"], [])

    def test_uninvestigated_size_is_proposed_not_set(self):
        draft = fixture("draft-routed.json")
        draft["draft_notes"]["investigated"] = False
        code, out = self.build(draft)
        self.assertEqual(code, 0, out)
        self.assertNotIn("Size", out["board"]["values"])
        self.assertEqual([p["what"] for p in out["proposal_only"]], ["Size"])
        self.assertIn("not investigated", out["proposal_only"][0]["reason"])

    def test_estimate_above_the_ceiling_fails_the_build(self):
        resolved = json.loads(Path(self.routed_template()).read_text(encoding="utf-8"))
        template = resolved["template"]
        template["estimate"].pop("split_above", None)
        template["estimate"]["ceiling"] = "M"
        draft = fixture("draft-routed.json")
        draft["estimate"]["value"] = "L"
        code, out = self.build(draft, self.write("capped.json", resolved))
        self.assertEqual(code, ga.EXIT_INVALID, out)
        self.assertEqual(out["errors"], ["estimate.value: 'L' is above the ceiling ('M'); propose a split instead"])

    def test_owner_without_the_type_leaves_it_out(self):
        self.fake.on("orgs/example-org/issue-types", rc=1, err="HTTP 404")
        code, out = self.run_op("build", "--template", self.routed_template(),
                                "--draft", str(FIX / "draft-routed.json"))
        self.assertEqual(code, 0, out)
        self.assertNotIn("type", out["issue"])
        self.assertEqual(out["proposal_only"][0]["what"], "type")

    def test_repo_without_routing_stops_and_asks(self):
        draft = fixture("draft-routed.json")
        draft["target"]["repo"] = "example-org/elsewhere"
        code, out = self.build(draft)
        self.assertEqual(code, 1)
        self.assertEqual(out["needs_user"], "board")
        code, out = self.build(draft, None, "--board", "12")
        self.assertEqual((code, out["board"]["number"]), (0, 12))

    def test_repo_routed_to_none_proposes_everything(self):
        draft = fixture("draft-routed.json")
        draft["target"]["repo"] = "example-org/scratch"
        code, out = self.build(draft)
        self.assertEqual(code, 0, out)
        self.assertIsNone(out["board"])
        self.assertEqual({p["what"] for p in out["proposal_only"]}, {"Priority", "Size", "Effort"})

    def test_default_template_has_no_board(self):
        draft = fixture("draft-routed.json")
        draft.update(labels=[], fields={})
        code, out = self.build(draft, self.default_template())
        self.assertEqual(code, 0, out)
        self.assertIsNone(out["board"])
        self.assertEqual({p["what"] for p in out["proposal_only"]}, {"priority", "estimate"})

    def test_invalid_draft_lists_every_error_and_sends_nothing(self):
        draft = fixture("draft-routed.json")
        draft["labels"] = ["nonsense"]
        draft["sections"].pop("Acceptance Criteria")
        code, out = self.build(draft)
        self.assertEqual(code, 1)
        self.assertGreaterEqual(len(out["errors"]), 2)
        self.assertEqual(self.fake.seen("POST"), [])


class CreateTests(AdapterCase):
    def setUp(self):
        super().setUp()
        self.path = self.payload()
        self.issue = json.loads(Path(self.path).read_text(encoding="utf-8"))["issue"]
        self.fake.on("--paginate", "bug\ndocs\n")

    def test_roundtrip_with_crlf_and_non_ascii_is_verified(self):
        self.fake.on("issues --method POST", self.api_response(self.issue))
        code, out = self.run_op("create", "--payload", self.path, "--confirm")
        self.assertEqual((code, out["status"], out["key"]), (0, "VERIFIED", 42), out)
        self.assertTrue(all(f["ok"] for f in out["fields"]))
        sent = self.fake.seen("--method POST")[0][1]
        sent.encode("ascii")  # what crosses the process boundary is pure ASCII
        self.assertEqual(json.loads(sent)["body"], self.issue["body"])
        for banned in ("--body-file", "-F ", "--body @"):
            self.assertFalse(any(banned in " ".join(c[0]) for c in self.fake.calls))

    def test_mangled_body_is_repaired_once(self):
        mangled = self.api_response(self.issue, body="@C:/scratch/body.md")
        self.fake.on("issues --method POST", mangled)
        self.fake.on("issues/42 --method PATCH", self.api_response(self.issue))
        code, out = self.run_op("create", "--payload", self.path, "--confirm")
        self.assertEqual((code, out["status"]), (0, "REPAIRED"), out)
        patches = self.fake.seen("--method PATCH")
        self.assertEqual(len(patches), 1)
        self.assertEqual(list(json.loads(patches[0][1])), ["body"])

    def test_persistent_mismatch_fails_after_one_repair(self):
        mangled = self.api_response(self.issue, body="@C:/scratch/body.md")
        self.fake.on("issues --method POST", mangled)
        self.fake.on("issues/42 --method PATCH", mangled)
        code, out = self.run_op("create", "--payload", self.path, "--confirm")
        self.assertEqual((code, out["status"]), (2, "FAILED"), out)
        self.assertIn("body", out["message"])
        self.assertEqual(len(self.fake.seen("--method PATCH")), 1)

    def test_missing_label_is_refused_and_never_created(self):
        self.fake.routes.clear()
        self.fake.on("--paginate", "docs\n")
        code, out = self.run_op("create", "--payload", self.path, "--confirm")
        self.assertEqual(code, 1)
        self.assertIn("never creates labels", out["error"])
        self.assertEqual(self.fake.seen("--method POST"), [])

    def test_no_write_without_confirm(self):
        self.fake.calls.clear()
        code, _ = self.run_op("create", "--payload", self.path)
        self.assertEqual(code, 1)
        self.assertEqual(self.fake.calls, [])

    def test_denied_write_exits_3_with_the_saved_payload_path(self):
        self.fake.on("issues --method POST", rc=1, err="gh: Resource not accessible by integration (HTTP 403)")
        code, out = self.run_op("create", "--payload", self.path, "--confirm")
        self.assertEqual(code, 3)
        self.assertIn("Writes to GitHub are blocked in this session", out["message"])
        self.assertIn(self.path, out["message"])
        self.assertEqual(self.fake.seen("curl"), [])

    def test_unknown_outcome_points_at_duplicates(self):
        self.fake.on("issues --method POST", rc=1, err="connection reset")
        code, out = self.run_op("create", "--payload", self.path, "--confirm")
        self.assertEqual(code, 2)
        self.assertIn("duplicates", out["error"])


class BoardTests(AdapterCase):
    def board_routes(self, fields=None):
        self.fake.on("project field-list", fields if fields is not None else fixture("project-field-list.json"))
        self.fake.on("project view", {"id": "PVT_placeholder"})
        self.fake.on("project item-add", {"id": "ITEM1"})
        self.fake.on("project item-edit", "")
        self.fake.on("api graphql", fixture("graphql-board.json"))

    def test_sets_fields_and_reads_them_back_from_the_right_board(self):
        self.board_routes()
        code, out = self.run_op("set-fields", "--payload", self.payload(), "--number", 42, "--confirm")
        self.assertEqual((code, out["status"]), (0, "VERIFIED"), out)
        self.assertEqual(len(self.fake.seen("project item-edit")), 3)
        self.assertEqual({f["name"] for f in out["fields"]}, {"board.Priority", "board.Size", "board.Effort"})
        self.assertEqual(self.fake.seen("item-list"), [])

    def test_stale_cache_is_refreshed_once(self):
        stale = fixture("project-field-list.json")
        stale["fields"] = [f for f in stale["fields"] if f["name"] != "Effort"]
        cache = Path(os.environ["TICKETS_CACHE_DIR"]) / "board-fields.json"
        cache.parent.mkdir(parents=True)
        cache.write_text(json.dumps({"example-org/7": {"projectId": "PVT_old", "fields": {
            f["name"]: {"id": f["id"], "options": {o["name"]: o["id"] for o in f.get("options", [])}}
            for f in stale["fields"]}}}), encoding="utf-8")
        self.board_routes()
        code, out = self.run_op("set-fields", "--payload", self.payload(), "--number", 42, "--confirm")
        self.assertEqual((code, out["status"]), (0, "VERIFIED"), out)
        self.assertEqual(len(self.fake.seen("project field-list")), 1)

    def test_option_the_board_lacks_is_reported_by_name(self):
        self.board_routes()
        path = self.payload()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["board"]["values"]["Priority"] = "P9"
        path = self.write("payload-bad.json", data)
        code, out = self.run_op("set-fields", "--payload", path, "--number", 42, "--confirm")
        self.assertEqual((code, out["status"]), (2, "FAILED"), out)
        self.assertIn("P9", out["message"])

    def test_no_board_means_nothing_is_set(self):
        draft = fixture("draft-routed.json")
        draft["target"]["repo"] = "example-org/scratch"
        _, built = self.build(draft)
        built.pop("warnings", None)
        code, out = self.run_op("set-fields", "--payload", self.write("p.json", built),
                                "--number", 7, "--confirm")
        self.assertEqual((code, out["status"]), (0, "VERIFIED"))
        self.assertEqual(self.fake.seen("project"), [])


class ReadTests(AdapterCase):
    def test_fetch_returns_the_thread_and_the_ai_prompt(self):
        self.fake.on("issue view 42", fixture("issue-view.json"))
        code, out = self.run_op("fetch", "--repo", REPO, "--number", 42)
        self.assertEqual(code, 0, out)
        self.assertEqual(out["key"], "42")
        self.assertEqual(out["labels"], ["bug"])
        self.assertEqual(out["type"], "Task")
        self.assertEqual(out["parent"], "40")
        self.assertEqual(out["assignee"], "octocat")
        self.assertEqual(out["state"], "open")
        self.assertTrue(out["has_ai_prompt"])
        self.assertIn("Fix the query", out["ai_prompt"])
        self.assertEqual(list(out["sections"]), ["In plain terms", "Context", "Acceptance Criteria", "AI prompt"])
        self.assertNotIn("\r", out["body"])
        self.assertEqual([c["author"] for c in out["thread"]], ["octocat", "hubot"])
        self.assertEqual(out["links"], [
            {"kind": "blocks", "direction": "inward", "target": "41"},
            {"kind": "blocks", "direction": "outward", "target": "43"}])

    def test_fetch_without_an_ai_prompt_says_so(self):
        view = fixture("issue-view.json")
        view["body"] = view["body"].split("## AI prompt")[0]
        self.fake.on("issue view 42", view)
        code, out = self.run_op("fetch", "--repo", REPO, "--number", 42)
        self.assertEqual((code, out["has_ai_prompt"], out["ai_prompt"]), (0, False, None))

    def test_fetch_reads_the_shape_gh_returns_for_an_issue_with_no_relations(self):
        """Recorded from a live read: relation fields are empty node lists, type and parent null."""
        view = fixture("issue-view.json")
        view.update(issueType=None, parent=None, blockedBy={"nodes": [], "totalCount": 0},
                    blocking={"nodes": [], "totalCount": 0})
        self.fake.on("issue view 42", view)
        code, out = self.run_op("fetch", "--repo", REPO, "--number", 42)
        self.assertEqual((code, out["links"], out["type"], out["parent"]), (0, [], None, None))

    def test_fetch_falls_back_on_an_older_gh(self):
        view = fixture("issue-view.json")
        for key in ("issueType", "parent", "blockedBy", "blocking"):
            view.pop(key)
        self.fake.on("blockedBy", rc=1, err="Unknown JSON field: \"issueType\"")
        self.fake.on("issue view 42", view)
        code, out = self.run_op("fetch", "--repo", REPO, "--number", 42)
        self.assertEqual((code, out["links"], out["type"]), (0, [], None))

    def test_readback_then_diff_is_clean(self):
        path = self.payload()
        issue = json.loads(Path(path).read_text(encoding="utf-8"))["issue"]
        self.fake.on("repos/example-org/widgets/issues/42", self.api_response(issue))
        self.fake.on("api graphql", fixture("graphql-board.json"))
        code, actual = self.run_op("readback", "--payload", path, "--number", 42)
        self.assertEqual(code, 0, actual)
        self.assertEqual(actual["board"], {"Priority": "P1", "Size": "S", "Effort": "low"})
        code, out = self.run_op("diff", "--payload", path, "--actual", self.write("actual.json", actual))
        self.assertEqual((code, out["status"]), (0, "VERIFIED"), out)

    def test_diff_reports_each_difference_and_ignores_only_line_endings(self):
        path = self.payload()
        issue = json.loads(Path(path).read_text(encoding="utf-8"))["issue"]
        actual = {"title": issue["title"], "body": issue["body"].replace("\n", "\r\n").rstrip() + "  ",
                  "labels": ["BUG"], "type": "Task", "board": {"Priority": "P1", "Size": "M", "Effort": "low"}}
        code, out = self.run_op("diff", "--payload", path, "--actual", self.write("a.json", actual))
        self.assertEqual((code, out["status"]), (2, "FAILED"))
        bad = [f["name"] for f in out["fields"] if not f["ok"]]
        self.assertEqual(bad, ["board.Size"])
        actual["body"] = actual["body"].replace("Finance", "Finanxe")
        _, out = self.run_op("diff", "--payload", path, "--actual", self.write("a.json", actual))
        body = next(f for f in out["fields"] if f["name"] == "body")
        self.assertFalse(body["ok"])
        self.assertIn("first difference", body["detail"])

    def test_repair_fixes_the_board_field_and_rechecks(self):
        path = self.payload()
        issue = json.loads(Path(path).read_text(encoding="utf-8"))["issue"]
        wrong = fixture("graphql-board.json")
        right = fixture("graphql-board.json")
        wrong["data"]["repository"]["issue"]["projectItems"]["nodes"][0]["fieldValues"]["nodes"][2]["name"] = "XS"
        self.fake.on("repos/example-org/widgets/issues/42", self.api_response(issue))
        self.fake.on("api graphql", [wrong, right])
        self.fake.on("project field-list", fixture("project-field-list.json"))
        self.fake.on("project view", {"id": "PVT_placeholder"})
        self.fake.on("project item-add", {"id": "ITEM1"})
        self.fake.on("project item-edit", "")
        code, out = self.run_op("repair", "--payload", path, "--number", 42, "--confirm", "--no-wait")
        self.assertEqual((code, out["status"]), (0, "REPAIRED"), out)
        edits = self.fake.seen("project item-edit")
        self.assertEqual(len(edits), 1)
        self.assertIn("o4", edits[0][0])  # the Size option for "S"

    def test_duplicates_flags_the_exact_title_first(self):
        hits = {"items": [
            {"number": 5, "title": "Something close", "state": "open", "html_url": "u5"},
            {"number": 9, "title": "Restore the Monthly Sales report load time", "state": "closed", "html_url": "u9"}]}
        self.fake.on("search/issues", hits)
        code, out = self.run_op("duplicates", "--repo", REPO, "--title",
                                "Restore the monthly sales report load time")
        self.assertEqual(code, 0)
        self.assertEqual([h["number"] for h in out["hits"]], [9, 5])
        self.assertTrue(out["hits"][0]["exact"])
        self.assertIn("--method GET", " ".join(self.fake.calls[0][0]))


class LinkCommentDetectTests(AdapterCase):
    def link_payload(self, direction="inward"):
        path = self.payload()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["links"] = [{"kind": "blocks", "direction": direction, "target": "41"},
                         {"kind": "blocks", "direction": "outward", "target": "43"}]
        return self.write("linked.json", data)

    def test_first_link_is_read_back_before_the_rest(self):
        self.fake.on("issue edit", "")
        self.fake.on("issue view", {"blockedBy": {"nodes": [{"number": 41}], "totalCount": 1}, "blocking": {"nodes": [], "totalCount": 0}})
        code, out = self.run_op("link", "--payload", self.link_payload(), "--number", 42, "--confirm")
        self.assertEqual((code, out["status"]), (0, "VERIFIED"), out)
        order = [" ".join(c[0]) for c in self.fake.calls]
        self.assertLess(next(i for i, c in enumerate(order) if "--add-blocked-by" in c),
                        next(i for i, c in enumerate(order) if "issue view" in c))
        self.assertLess(next(i for i, c in enumerate(order) if "issue view" in c),
                        next(i for i, c in enumerate(order) if "--add-blocking" in c))

    def test_wrong_direction_stops_after_the_first_link(self):
        self.fake.on("issue edit", "")
        self.fake.on("issue view", {"blockedBy": {"nodes": [], "totalCount": 0}, "blocking": {"nodes": [{"number": 41}], "totalCount": 1}})
        code, out = self.run_op("link", "--payload", self.link_payload(), "--number", 42, "--confirm")
        self.assertEqual((code, out["status"]), (2, "FAILED"))
        self.assertEqual(len(self.fake.seen("issue edit")), 1)

    def test_unsupported_link_kind_is_a_validation_error(self):
        path = self.payload()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["links"] = [{"kind": "relates", "direction": "outward", "target": "1"}]
        code, _ = self.run_op("link", "--payload", self.write("p.json", data), "--number", 42, "--confirm")
        self.assertEqual(code, 1)

    def test_comment_is_verified_and_the_adapter_reads_the_file(self):
        body = self.tmp / "c.md"
        body.write_text("Estimate proposed \u2014 caf\u00e9\n", encoding="utf-8")
        self.fake.on("comments --method POST", lambda a, i: {
            "id": 77, "html_url": "u", "body": json.loads(i)["body"].replace("\n", "\r\n")})
        code, out = self.run_op("comment", "--repo", REPO, "--number", 42,
                                "--body-file", body, "--confirm")
        self.assertEqual((code, out["status"], out["key"]), (0, "VERIFIED", 77), out)
        self.assertFalse(any("--body-file" in " ".join(c[0]) for c in self.fake.calls))

    def test_detect_warns_on_a_public_repo(self):
        self.fake.on("auth status", "ok")
        self.fake.on("repos/example-org/widgets", {"visibility": "public", "has_issues": True,
                                                    "permissions": {"push": True}})
        code, out = self.run_op("detect", "--repo", REPO)
        self.assertEqual((code, out["status"], out["can_push"]), (0, "ok", True))
        self.assertIn("public", out["warnings"][0])

    def test_detect_stops_when_issues_are_disabled(self):
        self.fake.on("auth status", "ok")
        self.fake.on("repos/example-org/widgets", {"visibility": "private", "has_issues": False})
        code, out = self.run_op("detect", "--repo", REPO)
        self.assertEqual((code, out["status"]), (4, "not-configured"))

    def test_detect_without_login_exits_4(self):
        self.fake.on("auth status", rc=1, err="You are not logged in")
        code, out = self.run_op("detect", "--repo", REPO)
        self.assertEqual((code, out["status"]), (4, "not-configured"))


def find_bash() -> str | None:
    for candidate in ("C:/Program Files/Git/bin/bash.exe", "C:/Program Files (x86)/Git/bin/bash.exe"):
        if Path(candidate).exists():
            return candidate
    return None if os.name == "nt" else shutil.which("bash")


@unittest.skipUnless(find_bash(), "needs bash")
class HookTests(unittest.TestCase):
    def decision(self, command: str) -> str:
        proc = subprocess.run([find_bash(), str(HOOKS / "gh-body-guard")],
                              input=json.dumps({"tool_input": {"command": command}}),
                              capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        if not proc.stdout.strip():
            return "pass"  # no decision: the user's own permission rules apply
        return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]

    def test_denies_the_corrupting_shapes(self):
        for cmd in ("gh issue create --title t --body-file b.md",
                    "gh pr comment 3 -F b.md",
                    "gh issue edit 4 --body \"@b.md\"",
                    "cd x && gh issue create --body=@b.md",
                    "gh issue create --title t \\\n  --body-file body.md",
                    "GH_REPO=o/r gh issue create -t x --body-file b.md",
                    "gh issue create --title \"a|b\" --body-file body.md",
                    "command gh pr create -b @b.md",
                    "gh pr comment 3 -Fb.md"):
            self.assertEqual(self.decision(cmd), "deny", cmd)

    def test_allows_everything_else(self):
        for cmd in ("gh api repos/o/r/issues --input -",
                    "gh issue list --repo o/r",
                    "gh issue create --title t --body \"plain text\"",
                    "git status"):
            self.assertEqual(self.decision(cmd), "pass", cmd)

    def test_gh_words_in_another_command_are_not_a_gh_call(self):
        # A commit message that mentions gh, next to git's own -F, once read as
        # a gh issue --body-file call and was denied.
        for cmd in ("git commit -q -F - <<'EOF'\nfeat: x\n\ndenies gh issue creates from Bash\nEOF",
                    "git commit -F msg.txt -m \"see gh issue create\"",
                    "echo 'gh pr edit 3 -F b.md'",
                    "gh issue create --title t --body x && git commit -F msg.txt",
                    "git commit -F - <<EOF\nfix: gh issue create -F x\nEOF"):
            self.assertEqual(self.decision(cmd), "pass", cmd)

    def test_hook_config_points_at_the_script(self):
        config = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))
        command = config["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertIn("hooks/run-hook.cmd", command)
        self.assertTrue((HOOKS / "gh-body-guard").is_file())


if __name__ == "__main__":
    unittest.main()
