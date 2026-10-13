"""Unit tests for jira_adapter.py, on synthetic fixtures only.

Run from the repo root:
    python -m unittest discover -s tickets/scripts/tests -v
"""

import copy
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "jira"
sys.path.insert(0, str(HERE.parent))

import jira_adapter as ja
import write_guard

# Keep the user's own plan-staged-rollout.toml (which may turn the write guard
# on) and the guard's relay tokens out of these tests.
os.environ["CLAUDE_CONFIG_DIR"] = tempfile.mkdtemp(prefix="psr-test-config-")

V2 = "mcp__plugin_atlassian_atlassian__"

# listJiraIssueComments, shaped as the live v2 server returns it (newest last
# here on purpose: the adapter sorts oldest first).
COMMENTS = {"data": {"startAt": 0, "maxResults": 100, "total": 2, "isLast": True,
                     "appliedContentFormat": "markdown", "comments": [
                         {"id": "11", "author": {"displayName": "Sam Example"},
                          "body": "Decided: keep the retry at three.",
                          "created": "2026-10-02T09:00:00.000+1300", "jsdPublic": True},
                         {"id": "10", "author": {"displayName": "Pat Example"},
                          "body": "Which job is this?", "created": "2026-10-01T09:00:00.000+1300",
                          "jsdPublic": True}]}}

# listJiraIssueTransitions, as the live v2 server returns it.
TRANSITIONS = {"data": {"transitions": [
    {"id": "41", "name": "Work in progress", "to": {"name": "Work in progress",
                                                     "statusCategory": {"key": "indeterminate"}}},
    {"id": "171", "name": "Send to review", "to": {"name": "In Review",
                                                   "statusCategory": {"key": "indeterminate"}}},
    {"id": "31", "name": "Closed", "to": {"name": "Dev Done", "statusCategory": {"key": "done"}}}]}}


def status_read(name, category="new"):
    """getJiraIssue through executeRead with responseFields, as the live v2 server returns it."""
    return {"data": {"key": "ABC-321", "fields": {"status": {"name": name,
                                                             "statusCategory": {"key": category}}}}}


def fixture(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def run_cli(*argv):
    out = io.StringIO()
    with redirect_stdout(out):
        code = ja.main([str(a) for a in argv])
    return code, json.loads(out.getvalue())


def fields_only(evidence):
    """What getJiraIssue returns for an explicit field list: no type, labels, parent or links."""
    data = copy.deepcopy(evidence)
    f = data["data"]["fields"]
    for name in ("issuetype", "labels", "parent", "issuelinks"):
        f.pop(name, None)
    return data


class AdapterCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.run_dir = self.dir / "run"
        self.tools = fixture("tools.json")
        self.env = ja.detect(self.tools["v2"])
        self.env_path = self.write("env.json", self.env)
        self.template_path = FIX / "template.json"
        self.template = fixture("template.json")
        self.evidence = fixture("readback-v2-evidence.json")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, data):
        path = self.dir / name
        path.write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")
        return path

    def build_run(self, draft=None, env=None):
        draft_path = self.write("draft.json", draft or fixture("draft-valid.json"))
        env_path = self.write("env-b.json", env) if env else self.env_path
        return run_cli("build", "--ticket", draft_path, "--template", self.template_path,
                       "--env", env_path, "--run", self.run_dir)

    def answer(self, body, results):
        """Play the model: write each relayed call's result file."""
        self.assertEqual(body["status"], "RELAY", body)
        for call in body["calls"]:
            stem = Path(call["result_file"]).stem
            value = results[stem] if stem in results else results[stem.rsplit("-", 1)[0]]
            Path(call["result_file"]).write_text(
                value if isinstance(value, str) else json.dumps(value), encoding="utf-8")
        return [Path(c["result_file"]).stem for c in body["calls"]]


class DetectTests(AdapterCase):
    def test_v2_prefix_and_tools(self):
        env = ja.detect(self.tools["v2"])
        self.assertEqual((env["status"], env["prefix"]), ("ok", V2))
        self.assertTrue(env["writes"])
        self.assertEqual(env["tools"]["link"], V2 + "executeWrite")

    def test_v1_only_server_is_refused(self):
        code, body = run_cli("detect", "--tools", self.write("t.json", self.tools["v1"]))
        self.assertEqual((code, body["status"]), (ja.EXIT_UNREACHABLE, "unsupported"))
        self.assertEqual(body["candidates"], ["mcp__plugin_productivity_atlassian__"])
        self.assertIn(ja.V2_ENDPOINT, body["message"])

    def test_read_only_server(self):
        env = ja.detect(self.tools["readonly"])
        self.assertFalse(env["writes"])
        self.assertIn("read-only", env["message"])

    def test_not_configured(self):
        code, body = run_cli("detect", "--tools", self.write("t.json", self.tools["none"]))
        self.assertEqual((code, body["status"]), (ja.EXIT_UNREACHABLE, "not-configured"))

    def test_prefers_full_v2_when_several_servers(self):
        env = ja.detect(self.tools["readonly"] + self.tools["v1"] + self.tools["v2"])
        self.assertEqual((env["status"], env["prefix"]), ("ok", V2))
        self.assertEqual(len(env["candidates"]), 2)  # the v1-only server is not one


class UpdateTests(AdapterCase):
    """S7: re-run a ticket in place instead of creating a new one."""

    def test_update_edits_every_field_then_reads_back_without_new_links(self):
        draft = fixture("draft-valid.json")
        draft["links"] = [{"kind": "blocks", "direction": "inward", "target": "ABC-1"}]
        args = ["update", "--run", self.run_dir, "--key", "ABC-7", "--ticket", self.write("d.json", draft),
                "--template", self.template_path, "--env", self.env_path]
        code, body = run_cli(*args)
        self.assertEqual(body["status"], "INVALID", body)  # no --confirm, nothing sent
        code, body = run_cli(*args, "--confirm")
        call = body["calls"][0]
        self.assertEqual((call["tool"], call["arguments"]["issueIdOrKey"]), (V2 + "editJiraIssue", "ABC-7"))
        fields = call["arguments"]["fields"]
        self.assertEqual((fields["summary"], fields["priority"], fields["parent"]),
                         (draft["title"], {"name": "High"}, {"key": "ABC-100"}))
        self.assertTrue(fields["description"].startswith("## In plain terms"))
        self.assertEqual(call["arguments"]["contentFormat"], "markdown")
        stems = []
        for _ in range(3):
            stems += self.answer(body, {"edit": {"key": "ABC-7"}, "comment": {"id": "1"}})
            code, body = run_cli(*args, "--confirm")
            if not any(c["result_file"].endswith(("edit.json", "comment.json")) for c in body["calls"]):
                break
        self.assertEqual(stems, ["edit", "comment"])
        self.assertFalse([c for c in body["calls"] if "link" in Path(c["result_file"]).stem], body)


class BuildTests(AdapterCase):
    def test_valid_draft_builds_v2_call(self):
        code, body = self.build_run()
        self.assertEqual(code, ja.EXIT_OK, body)
        args = body["create"]["arguments"]
        self.assertEqual(body["create"]["tool"], V2 + "createJiraIssue")
        self.assertEqual((args["projectKey"], args["issueType"], args["priority"], args["parent"]),
                         ("ABC", "Story", "High", "ABC-100"))
        self.assertEqual(args["contentFormat"], "markdown")
        self.assertEqual(args["additional_fields"],
                         {"customfield_00000": 3, "customfield_00002": {"id": "90010"}})
        self.assertTrue(args["description"].startswith("## In plain terms\n\n"))
        self.assertTrue(args["description"].endswith("AI-assisted draft"))
        self.assertNotIn("## Out of scope", args["description"])
        payload = json.loads((self.run_dir / "payload.json").read_text(encoding="utf-8"))
        self.assertIn("sensitive_review", payload["expected"]["unset_guarded"])
        self.assertEqual(payload["comment"], "Estimate proposed by AI using https://example.com/estimation-guide")

    def test_every_error_reported_at_once(self):
        code, body = self.build_run(draft=fixture("draft-invalid.json"))
        self.assertEqual(code, ja.EXIT_INVALID)
        errors = "\n".join(body["errors"])
        for needle in ("target.project: required", "limit is 80", "type: 'Epic'",
                       "sections.Notes: not a section", "sections.Context: required",
                       "sections.Acceptance Criteria: required", "labels: 'misc'",
                       "at most one area label", "priority: 'Urgent'",
                       "estimate.value: 13 is not in", "fields.sensitive_review: 'Yes' is a guarded value",
                       "fields.colour: not declared", "links: kind 'duplicates'"):
            self.assertIn(needle, errors)
        self.assertFalse((self.run_dir / "payload.json").exists())

    def test_guarded_value_accepted_with_confirmation(self):
        draft = fixture("draft-valid.json")
        draft["fields"]["sensitive_review"] = "Yes"
        draft["draft_notes"]["confirmations"] = {"sensitive_review": "Yes"}
        code, body = self.build_run(draft=draft)
        self.assertEqual(code, ja.EXIT_OK, body)
        self.assertEqual(body["create"]["arguments"]["additional_fields"]["customfield_00001"],
                         {"id": "90001"})

    def test_guarded_confirmation_must_match_value(self):
        draft = fixture("draft-valid.json")
        draft["fields"]["sensitive_review"] = "Yes"
        draft["draft_notes"]["confirmations"] = {"sensitive_review": "No"}
        code, _body = self.build_run(draft=draft)
        self.assertEqual(code, ja.EXIT_INVALID)

    def test_estimate_withheld_until_investigated(self):
        draft = fixture("draft-valid.json")
        draft["draft_notes"]["investigated"] = False
        code, body = self.build_run(draft=draft)
        self.assertEqual(code, ja.EXIT_OK, body)
        self.assertNotIn("customfield_00000", body["create"]["arguments"]["additional_fields"])
        self.assertTrue(body["warnings"])

    def test_link_without_name_is_rejected(self):
        template = fixture("template.json")
        del template["links"]["blocks"]["name"]
        _payload, errors, _ = ja.build(fixture("draft-valid.json"), template, self.env)
        self.assertTrue(any("needs the link type name" in e for e in errors))

    def test_template_with_extends_is_refused(self):
        tpl = self.write("t.json", {"schema": 1, "name": "x", "extends": "default"})
        code, body = run_cli("build", "--ticket", FIX / "draft-valid.json", "--template", tpl,
                             "--env", self.env_path, "--run", self.run_dir)
        self.assertEqual(code, ja.EXIT_INVALID)
        self.assertIn("extends", body["message"])


class DriveTests(AdapterCase):
    def create(self):
        return run_cli("create", "--run", self.run_dir, "--confirm")

    def walk_to_readback(self):
        self.assertEqual(self.build_run()[0], ja.EXIT_OK)
        _code, body = self.create()
        self.assertEqual(self.answer(body, {"create": {"data": {"key": "ABC-321", "id": "500001"}}}),
                         ["create"])
        _code, body = self.create()
        self.assertEqual(body["calls"][0]["arguments"]["inputs"],
                         {"linkType": "Blocks", "inwardIssue": "ABC-321", "outwardIssue": "ABC-200"})
        self.answer(body, {"link-1": {"data": {"ok": True}}})
        _code, body = self.create()
        self.answer(body, {"link-1-check": self.evidence})
        _code, body = self.create()
        self.assertEqual(body["calls"][0]["tool"], V2 + "addOrEditJiraIssueComment")
        self.answer(body, {"comment": {"data": {"commentId": "1"}}})
        _code, body = self.create()
        return body

    def test_no_write_without_confirm(self):
        self.build_run()
        code, body = run_cli("create", "--run", self.run_dir)
        self.assertEqual(code, ja.EXIT_INVALID)
        self.assertIn("without --confirm", body["message"])

    def test_full_create_verified(self):
        body = self.walk_to_readback()
        stems = self.answer(body, {"readback-fields": fields_only(self.evidence),
                                   "readback-evidence": self.evidence})
        self.assertEqual(stems, ["readback-fields", "readback-evidence"])
        fields_call = body["calls"][0]["arguments"]["fields"]
        self.assertIn("customfield_00001", fields_call)  # guarded field read by explicit id
        code, body = self.create()
        self.assertEqual((code, body["status"], body["key"]), (ja.EXIT_OK, "VERIFIED", "ABC-321"), body)
        self.assertEqual(body["url"], "https://jira.example.com/browse/ABC-321")
        self.assertTrue(all(r["ok"] for r in body["fields"]))
        self.assertNotIn("_repair", body["fields"][0])

    def test_automation_overwrite_is_repaired_once(self):
        body = self.walk_to_readback()
        overwritten = copy.deepcopy(self.evidence)
        overwritten["data"]["fields"]["customFields"]["Team"]["value"] = {"value": "Beta", "id": "90011"}
        self.answer(body, {"readback-fields": fields_only(overwritten), "readback-evidence": overwritten})
        code, body = self.create()
        self.assertEqual(body["calls"][0]["arguments"]["fields"], {"customfield_00002": {"id": "90010"}})
        self.answer(body, {"repair": {"data": {"key": "ABC-321"}}})
        code, body = self.create()
        self.assertEqual([Path(c["result_file"]).stem for c in body["calls"]],
                         ["readback-fields-2", "readback-evidence-2"])
        self.answer(body, {"readback-fields-2": fields_only(self.evidence),
                           "readback-evidence-2": self.evidence})
        code, body = self.create()
        self.assertEqual((code, body["status"]), (ja.EXIT_OK, "REPAIRED"), body)

    def test_still_wrong_after_repair_fails(self):
        body = self.walk_to_readback()
        bad = copy.deepcopy(self.evidence)
        bad["data"]["fields"]["priority"] = {"name": "Low"}
        self.answer(body, {"readback-fields": fields_only(bad), "readback-evidence": bad})
        code, body = self.create()
        self.answer(body, {"repair": {"data": {}}})
        code, body = self.create()
        self.answer(body, {"readback-fields-2": fields_only(bad), "readback-evidence-2": bad})
        code, body = self.create()
        self.assertEqual((code, body["status"]), (ja.EXIT_TRACKER, "FAILED"))
        self.assertIn("priority", body["message"])

    def test_guarded_value_set_by_automation_is_cleared(self):
        body = self.walk_to_readback()
        bad = copy.deepcopy(self.evidence)
        bad["data"]["fields"]["customFields"]["Sensitive data review"]["value"] = {"value": "Yes", "id": "90001"}
        self.answer(body, {"readback-fields": fields_only(bad), "readback-evidence": bad})
        _code, body = self.create()
        self.assertEqual(body["calls"][0]["arguments"]["fields"], {"customfield_00001": None})

    def test_hook_denial_stops_with_message(self):
        self.build_run()
        code, body = self.create()
        self.answer(body, {"create": "PreToolUse:mcp__plugin_atlassian_atlassian__createJiraIssue "
                                     "hook error: Atlassian writes are denied in this repo"})
        code, body = self.create()
        self.assertEqual((code, body["status"], body["blocker"]), (ja.EXIT_DENIED, "DENIED", "hook"))
        self.assertIn("Nothing was posted", body["message"])
        self.assertIn("payload.json", body["message"])

    def test_read_only_server_refuses_before_any_call(self):
        self.build_run(env=ja.detect(self.tools["readonly"] + self.tools["none"]))
        code, body = self.create()
        self.assertEqual((code, body["blocker"]), (ja.EXIT_DENIED, "read-only server"))

    def test_tracker_error_is_not_a_denial(self):
        self.build_run()
        code, body = self.create()
        self.answer(body, {"create": {"error": "Field 'customfield_00000' cannot be set. "
                                               "It is not on the appropriate screen."}})
        code, body = self.create()
        self.assertEqual((code, body["status"]), (ja.EXIT_TRACKER, "FAILED"))

    def test_unknown_create_searches_instead_of_reposting(self):
        self.build_run()
        code, body = self.create()
        self.answer(body, {"create": "Request timed out after 60 seconds"})
        code, body = self.create()
        self.assertEqual(body["calls"][0]["tool"], V2 + "searchJiraIssuesUsingJql")
        self.assertIn('summary ~ "\\"Add a retry', body["calls"][0]["arguments"]["jql"])
        self.answer(body, {"create-unknown-search": {"data": {"issues": [
            {"key": "ABC-321", "fields": {"summary": "Add a retry to the nightly export job"}}]}}})
        code, body = self.create()
        self.assertEqual((code, body["key"]), (ja.EXIT_TRACKER, "ABC-321"))
        self.assertIn("do not post again", body["message"])
        code, body = self.create()  # a re-run never re-emits the create
        self.assertNotEqual(body.get("status"), "RELAY")

    def test_reversed_first_link_stops(self):
        self.build_run()
        code, body = self.create()
        self.answer(body, {"create": {"data": {"key": "ABC-321"}}})
        code, body = self.create()
        self.answer(body, {"link-1": {"data": {}}})
        code, body = self.create()
        reversed_links = copy.deepcopy(self.evidence)
        reversed_links["data"]["fields"]["issuelinks"] = [
            {"type": {"name": "Blocks"}, "inwardIssue": {"key": "ABC-200"}}]
        self.answer(body, {"link-1-check": reversed_links})
        code, body = self.create()
        self.assertEqual((code, body["status"]), (ja.EXIT_TRACKER, "FAILED"))
        self.assertIn("cannot be deleted", body["message"])


class ReadTests(AdapterCase):
    def test_normalize_v2_and_rest_shapes(self):
        v2 = ja.normalize_issue(self.evidence)
        self.assertEqual((v2["issuetype"], v2["parent"], v2["labels"]), ("Story", "ABC-100", ["backend"]))
        self.assertEqual(v2["custom"]["customfield_00000"], 3)
        self.assertIsNone(v2["custom"]["customfield_00001"])
        self.assertEqual(v2["links"], [{"name": "Blocks", "direction": "outward", "target": "ABC-200"}])
        rest = ja.normalize_issue({"key": "ABC-1", "fields": {"customfield_00000": 5,
                                                              "issuetype": {"name": "Bug"}}})
        self.assertEqual((rest["custom"]["customfield_00000"], rest["issuetype"]), (5, "Bug"))

    def test_body_normalization_tolerates_round_trip(self):
        built = "## Context\n\n* one\n* two [link](https://x.y)\n\nAI-assisted draft"
        returned = "## Context\n\n- one  \n- two \\[link\\](https://x.y)\n\n\nAI-assisted draft\n"
        self.assertEqual(ja.norm_text(built), ja.norm_text(returned))
        self.assertNotEqual(ja.norm_text(built), ja.norm_text(built.replace("two", "three")))

    def test_fetch_parses_sections_and_ai_prompt(self):
        issue = copy.deepcopy(self.evidence)
        issue["data"]["fields"]["description"] += "\n\n## AI prompt\n\nRepo: org/repo, base main."
        (self.run_dir / "results").mkdir(parents=True)
        code, body = run_cli("fetch", "--run", self.run_dir, "--key", "ABC-321", "--site",
                             "https://jira.example.com", "--env", self.env_path,
                             "--template", self.template_path)
        self.assertEqual(self.answer(body, {"fetch": issue, "fetch-comments": COMMENTS}),
                         ["fetch", "fetch-comments"])
        code, body = run_cli("fetch", "--run", self.run_dir, "--key", "ABC-321", "--site",
                             "https://jira.example.com", "--env", self.env_path,
                             "--template", self.template_path)
        self.assertEqual(code, ja.EXIT_OK, body)
        self.assertTrue(body["has_ai_prompt"])
        self.assertEqual((body["ai_prompt_section"], body["ai_prompt"]), ("AI prompt", "Repo: org/repo, base main."))
        self.assertIn("Context", body["sections"])
        self.assertEqual(body["fields"], {"story_points": 3, "sensitive_review": None, "team": "Alpha"})
        self.assertEqual([c["author"] for c in body["thread"]], ["Pat Example", "Sam Example"])
        self.assertEqual(body["thread"][1], {"author": "Sam Example", "created_at": "2026-10-02T09:00:00.000+1300",
                                             "body": "Decided: keep the retry at three."})
        self.assertIsNone(body["thread_note"])

    def fetch_comments_with(self, env, comments_result):
        (self.run_dir / "results").mkdir(parents=True, exist_ok=True)
        args = ("fetch", "--run", self.run_dir, "--key", "ABC-321", "--site", "jira.example.com",
                "--env", self.write("env-c.json", env))
        _code, body = run_cli(*args)
        results = {"fetch": self.evidence}
        if comments_result is not None:
            results["fetch-comments"] = comments_result
        self.answer(body, results)
        return run_cli(*args)

    def test_fetch_says_when_comments_were_cut_off(self):
        page = copy.deepcopy(COMMENTS)
        page["data"]["total"] = 140
        _code, body = self.fetch_comments_with(self.env, page)
        self.assertEqual(body["thread_note"], "only the first 2 of 140 comments were read")

    def test_fetch_survives_a_failed_comment_read(self):
        code, body = self.fetch_comments_with(self.env, '{"isError": true, "error": "boom"}')
        self.assertEqual((code, body["thread"]), (ja.EXIT_OK, []))
        self.assertIn("comments were not read", body["thread_note"])

    def test_fetch_with_an_older_env_skips_comments(self):
        env = copy.deepcopy(self.env)
        del env["tools"]["comments"]
        code, body = self.fetch_comments_with(env, None)
        self.assertEqual((code, body["thread"]), (ja.EXIT_OK, []))
        self.assertIn("run detect again", body["thread_note"])

    def test_adf_comment_bodies_are_read_as_text(self):
        raw = {"key": "ABC-321", "fields": {"comment": {"total": 1, "comments": [{
            "id": "7", "author": {"displayName": "Pat Example"}, "created": "2026-10-01T09:00:00.000+1300",
            "body": {"type": "doc", "content": [{"type": "paragraph", "content": [
                {"type": "text", "text": "First line"}, {"type": "hardBreak"},
                {"type": "text", "text": "second line"}]}]}}]}}}
        comments, total = ja.parse_comments(raw)
        self.assertEqual((comments[0]["body"], total), ("First line\nsecond line", 1))

    def test_duplicates_children_then_keyword(self):
        self.build_run()
        _code, body = run_cli("duplicates", "--run", self.run_dir)
        jqls = [c["arguments"]["jql"] for c in body["calls"]]
        self.assertTrue(jqls[0].startswith("parent = ABC-100"))
        self.assertTrue(jqls[1].startswith('project = "ABC"'))
        hit = {"data": {"issues": [{"key": "ABC-9", "fields": {
            "summary": "Add a retry to the nightly export job", "status": {"name": "Done"}}}]}}
        self.answer(body, {"dup-children": {"data": {"issues": []}}, "dup-keyword": hit})
        _code, body = run_cli("duplicates", "--run", self.run_dir)
        self.assertEqual(body["hits"], [{"key": "ABC-9", "summary": "Add a retry to the nightly export job",
                                         "status": "Done", "match": "keyword", "words_matched": 3,
                                         "exact_title": True}])

    def issues(self, *rows):
        return {"data": {"issues": [{"key": k, "fields": {"summary": s, "status": {"name": "Open"}}}
                                    for k, s in rows]}}

    def test_keyword_search_ors_the_meaningful_words(self):
        self.build_run()
        _code, body = run_cli("duplicates", "--run", self.run_dir)
        jql = body["calls"][1]["arguments"]["jql"]
        self.assertIn('summary ~ "retry" OR summary ~ "nightly"', jql)
        self.assertNotIn(" AND summary", jql)
        for dropped in ('"Add"', '"a"', '"to"', '"the"'):
            self.assertNotIn(dropped, jql)

    def test_stop_words_and_short_words_are_dropped(self):
        self.assertEqual(ja.search_words("Fix the search so that it finds the source ticket"),
                         ["search", "finds", "source", "ticket"])

    def test_reworded_title_still_returns_the_source_ticket(self):
        self.build_run()
        _code, body = run_cli("duplicates", "--run", self.run_dir)
        other = ("ABC-7", "Nightly report layout")
        source = ("ABC-9", "Retry failed export runs overnight")
        self.answer(body, {"dup-children": self.issues(),
                           "dup-keyword": self.issues(other, source)})
        _code, body = run_cli("duplicates", "--run", self.run_dir)
        self.assertEqual([h["key"] for h in body["hits"]], ["ABC-9", "ABC-7"])
        self.assertEqual([h["words_matched"] for h in body["hits"]], [2, 1])

    def test_source_key_search_returns_its_ticket(self):
        draft = fixture("draft-valid.json")
        draft["draft_notes"]["source_key"] = "ABC-55"
        self.build_run(draft)
        _code, body = run_cli("duplicates", "--run", self.run_dir)
        jqls = {Path(c["result_file"]).stem: c["arguments"]["jql"] for c in body["calls"]}
        self.assertIn('key = ABC-55 OR text ~ "ABC-55"', jqls["dup-source"])
        source = ("ABC-55", "Unrelated wording entirely")
        self.answer(body, {"dup-children": self.issues(), "dup-source": self.issues(source),
                           "dup-keyword": self.issues(("ABC-7", "Export job retry"))})
        _code, body = run_cli("duplicates", "--run", self.run_dir)
        self.assertEqual(body["hits"][0]["key"], "ABC-55")
        self.assertEqual(body["hits"][0]["match"], "source")

    def test_build_rejects_a_source_key_that_is_not_an_issue_key(self):
        draft = fixture("draft-valid.json")
        draft["draft_notes"]["source_key"] = "not a key"
        code, body = self.build_run(draft)
        self.assertEqual(code, ja.EXIT_INVALID, body)
        self.assertTrue(any("source_key" in e for e in body["errors"]), body)


class GuardedCreate(AdapterCase):
    """guard_tracker_creates on: build needs the pipeline's evidence, and the
    hook lets through exactly the create call the adapter issued, once."""

    def setUp(self):
        super().setUp()
        self.cfg = self.dir / "cfg"
        self.cfg.mkdir()
        (self.cfg / "plan-staged-rollout.toml").write_text("guard_tracker_creates = true\n", encoding="utf-8")
        self._old = os.environ["CLAUDE_CONFIG_DIR"]
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.cfg)

    def tearDown(self):
        os.environ["CLAUDE_CONFIG_DIR"] = self._old
        super().tearDown()

    def evidence_files(self):
        self.write("template.json", {"template": ja.load_template(str(self.template_path)), "source": "test"})
        self.write("review-filtered.json", {"questions": [], "nits": [], "blockers": 0})
        self.write("estimate.json", {"outcome": "estimate"})

    def test_build_refuses_without_the_pipeline_evidence(self):
        code, body = self.build_run()
        self.assertEqual(code, ja.EXIT_INVALID, body)
        gate = [e for e in body["errors"] if e.startswith("pipeline gate")]
        self.assertEqual(len(gate), 3, gate)

    def test_build_refuses_a_template_other_than_the_resolved_one(self):
        self.evidence_files()
        other = ja.load_template(str(self.template_path))
        other["title"] = {"max_length": 7}
        self.write("template.json", {"template": other, "source": "test"})
        code, body = self.build_run()
        self.assertEqual(code, ja.EXIT_INVALID, body)
        self.assertTrue(any("differs from the one in template.json" in e for e in body["errors"]), body)

    def test_issued_create_passes_the_hook_once(self):
        self.evidence_files()
        code, body = self.build_run()
        self.assertEqual(code, ja.EXIT_OK, body)
        code, body = run_cli("create", "--run", self.run_dir, "--confirm")
        self.assertEqual(body["status"], "RELAY", body)
        call = body["calls"][0]
        event = {"tool_name": call["tool"], "tool_input": call["arguments"]}
        self.assertIsNone(write_guard.decide(event))  # passes, with no decision of its own
        self.assertEqual(write_guard.decide(event)[0], "deny")

    def test_hand_made_create_is_denied(self):
        event = {"tool_name": V2 + "createJiraIssue",
                 "tool_input": {"cloudId": "x", "projectKey": "ABC", "summary": "Hand made"}}
        decision, reason = write_guard.decide(event)
        self.assertEqual(decision, "deny")
        self.assertIn("create-issue", reason)

    def test_retyped_arguments_are_denied(self):
        self.evidence_files()
        self.build_run()
        _, body = run_cli("create", "--run", self.run_dir, "--confirm")
        args = dict(body["calls"][0]["arguments"], summary="Retyped title")
        self.assertEqual(write_guard.decide({"tool_name": body["calls"][0]["tool"], "tool_input": args})[0],
                         "deny")


class CommentTests(AdapterCase):
    TEXT = "Working this in [PR 12](https://example.com/pr/12).\n\n* step one\n* step two"

    def comment(self, *extra):
        body_path = self.write("comment.md", self.TEXT)
        return run_cli("comment", "--run", self.run_dir, "--key", "ABC-321", "--site", "jira.example.com",
                       "--env", self.env_path, "--body", body_path, *extra)

    def posted(self, comments):
        _code, body = self.comment("--confirm")
        self.assertEqual(body["calls"][0]["tool"], V2 + "addOrEditJiraIssueComment")
        self.answer(body, {"comment": {"data": {"commentId": "99", "body": self.TEXT}}})
        _code, body = self.comment("--confirm")
        self.assertEqual(body["calls"][0]["arguments"]["inputs"]["orderBy"], "-created")
        self.answer(body, {"comment-check": {"data": {"total": len(comments), "comments": comments}}})
        return self.comment("--confirm")

    def test_no_comment_without_confirm(self):
        code, body = self.comment()
        self.assertEqual(code, ja.EXIT_INVALID)
        self.assertIn("without --confirm", body["message"])

    def test_comment_is_read_back_from_the_issue(self):
        stored = "Working this in [PR 12](https://example.com/pr/12).\n\n- step one  \n- step two\n"
        code, body = self.posted([{"id": "99", "author": {"displayName": "Me"}, "body": stored,
                                   "created": "2026-10-13T10:00:00.000+1300"}])
        self.assertEqual((code, body["status"], body["comment_id"]), (ja.EXIT_OK, "VERIFIED", "99"))
        self.assertEqual(body["url"], "https://jira.example.com/browse/ABC-321")
        code, again = self.comment("--confirm")  # a re-run never posts twice
        self.assertEqual((code, again["status"]), (ja.EXIT_OK, "VERIFIED"))

    def test_comment_missing_on_read_back_fails(self):
        code, body = self.posted([{"id": "5", "author": {}, "body": "older", "created": "2026-10-01"}])
        self.assertEqual((code, body["status"]), (ja.EXIT_TRACKER, "FAILED"))
        self.assertIn("not found", body["message"])

    def test_comment_with_other_text_fails(self):
        code, body = self.posted([{"id": "99", "author": {}, "body": "truncated", "created": "2026-10-13"}])
        self.assertEqual((code, body["status"], body["actual"]), (ja.EXIT_TRACKER, "FAILED", "truncated"))


class WaitTests(AdapterCase):
    def check(self, *extra):
        return run_cli("wait", "--run", self.run_dir, "--key", "ABC-9", "--site", "jira.example.com",
                       "--env", self.env_path, *extra)

    def tick(self, result, *extra):
        _code, body = self.check(*extra)
        self.assertEqual(body["calls"][0]["arguments"]["name"], "getJiraIssue")
        self.answer(body, {Path(body["calls"][0]["result_file"]).stem: result})
        return self.check(*extra)

    def test_waits_then_clears_on_the_done_category(self):
        code, body = self.tick(status_read("Work in progress", "indeterminate"))
        self.assertEqual((code, body["status"], body["checks"]), (ja.EXIT_OK, "WAITING", 1))
        done = status_read("Dev Done", "done")
        done["data"]["fields"]["resolution"] = {"name": "Resolved"}
        code, body = self.tick(done)  # a later tick reads afresh
        self.assertEqual((body["status"], body["state"], body["checks"]), ("CLEARED", "Dev Done", 2))

    def test_done_as_wont_do_is_abandoned(self):
        done = status_read("Closed", "done")
        done["data"]["fields"]["resolution"] = {"name": "Won't Do"}
        self.assertEqual(self.tick(done)[1]["status"], "ABANDONED")

    def test_checks_once_then_times_out(self):
        _code, body = self.tick(status_read("Backlog"), "--hours", "0")
        self.assertEqual(body["status"], "WAITING")
        _code, body = self.check("--hours", "0")
        self.assertEqual(body["status"], "TIMEOUT")

    def test_a_failed_check_is_retried_twice_then_stops(self):
        for expected in ("WAITING", "WAITING"):
            code, body = self.tick('{"isError": true, "error": "upstream 502"}')
            self.assertEqual((code, body["status"]), (ja.EXIT_OK, expected))
        code, body = self.tick('{"isError": true, "error": "upstream 502"}')
        self.assertEqual((code, body["status"]), (ja.EXIT_TRACKER, "FAILED"))

    def test_unreadable_category_fails_rather_than_waiting_forever(self):
        code, body = self.tick({"data": {"key": "ABC-9", "fields": {"status": {"name": "Odd"}}}})
        self.assertEqual((code, body["status"]), (ja.EXIT_TRACKER, "FAILED"))

    def test_evidence_view_category_name_maps_to_its_key(self):
        read = ja.normalize_issue({"data": {"key": "ABC-1", "fields": {
            "status": {"name": "Backlog", "statusCategory": {"name": "To Do"}}}}})
        self.assertEqual(read["status_category"], "new")


class TransitionTests(AdapterCase):
    def move(self, status="In review", *extra, env_path=None):
        return run_cli("transition", "--run", self.run_dir, "--key", "ABC-321", "--site", "jira.example.com",
                       "--env", env_path or self.env_path, "--status", status, *extra)

    def test_moves_by_target_status_not_transition_name_and_reads_back(self):
        _code, body = self.move()
        self.assertEqual(self.answer(body, {"transition-before": status_read("Backlog"),
                                            "transition-options": TRANSITIONS}),
                         ["transition-before", "transition-options"])
        code, body = self.move()  # no --confirm: reads only
        self.assertEqual(code, ja.EXIT_INVALID)
        self.assertIn("without --confirm", body["message"])
        _code, body = self.move("In review", "--confirm")
        call = body["calls"][0]
        self.assertEqual((call["tool"], call["arguments"]["transitionId"]),
                         (V2 + "transitionJiraIssue", "171"))
        self.answer(body, {"transition": {"data": {"status": "In Review"}}})
        _code, body = self.move("In review", "--confirm")
        self.answer(body, {"transition-check": status_read("In Review", "indeterminate")})
        code, body = self.move("In review", "--confirm")
        self.assertEqual((code, body["status"], body["from_status"], body["changed"]),
                         (ja.EXIT_OK, "VERIFIED", "Backlog", True))

    def test_already_there_changes_nothing(self):
        _code, body = self.move()
        self.answer(body, {"transition-before": status_read("In Review"), "transition-options": TRANSITIONS})
        code, body = self.move("In review", "--confirm")
        self.assertEqual((code, body["status"], body["changed"]), (ja.EXIT_OK, "VERIFIED", False))

    def test_unreachable_status_lists_what_is_reachable(self):
        _code, body = self.move("In progress")
        self.answer(body, {"transition-before": status_read("Backlog"), "transition-options": TRANSITIONS})
        code, body = self.move("In progress", "--confirm")
        self.assertEqual((code, body["status"]), (ja.EXIT_TRACKER, "FAILED"))
        self.assertEqual(body["reachable"], ["Dev Done", "In Review", "Work in progress"])
        self.assertFalse((self.run_dir / "results" / "transition.json").exists())

    def test_denied_transition_is_exit_3(self):
        _code, body = self.move()
        self.answer(body, {"transition-before": status_read("Backlog"), "transition-options": TRANSITIONS})
        _code, body = self.move("In review", "--confirm")
        self.answer(body, {"transition": "The user doesn't want to proceed with this tool use."})
        code, body = self.move("In review", "--confirm")
        self.assertEqual((code, body["status"]), (ja.EXIT_DENIED, "DENIED"))


if __name__ == "__main__":
    unittest.main()
