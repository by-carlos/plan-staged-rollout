"""Script tests for work_core.py, work-issue's deterministic half.

No network, no `gh` and no git: every input is a fixture from
fixtures/work/. Run from anywhere:

    python -m unittest discover -s tickets/tests -v
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ticket_template
import work_core as wc

FIX = ROOT / "fixtures" / "work"


def ticket(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def with_prompt(t: dict, text: str) -> dict:
    """The ticket with `text` as its AI prompt, as a fetch returns it: the section and the two keys."""
    t["sections"]["AI prompt"] = t["ai_prompt"] = text
    t["ai_prompt_section"] = "AI prompt"
    return t


def template(ref: str, tracker: str) -> dict:
    resolved, _ = ticket_template.validate_template(ref, tracker)
    return resolved


DEFAULT_GH = template("default", "github")
DEFAULT_JIRA = template("default", "jira")
ROUTED = template(str(FIX / "status-routed.toml"), "github")


def run(argv: list[str]) -> tuple[int, dict]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = wc.main(argv)
    return code, json.loads(out.getvalue())


class AssessTests(unittest.TestCase):
    def test_github_with_prompt_acts_on_its_own_repo(self):
        a = wc.assess(ticket("github-act.json"), ROUTED)
        self.assertEqual(a["mode"], "act")
        self.assertEqual(a["target"]["repo"], "example-org/widgets")
        self.assertIsNone(a["target"]["base_branch"])
        self.assertEqual(a["target"]["base_source"], "the repo's default branch")
        self.assertEqual(a["effort"], "high")
        self.assertTrue(a["plain_terms"].startswith("Exports fail"))
        self.assertEqual(a["warnings"], [])

    def test_github_without_prompt_is_guide_only(self):
        a = wc.assess(ticket("github-guide.json"), DEFAULT_GH)
        self.assertEqual(a["mode"], "guide")
        self.assertIsNone(a["ai_prompt"])
        self.assertIsNone(a["target"]["repo"])

    def test_empty_prompt_section_is_guide_only(self):
        t = ticket("github-act.json")
        with_prompt(t, "  \n")
        t["ai_prompt"] = t["ai_prompt_section"] = None
        self.assertEqual(wc.assess(t, DEFAULT_GH)["mode"], "guide")

    def test_jira_reads_repo_and_base_from_the_prompt(self):
        a = wc.assess(ticket("jira-act.json"), DEFAULT_JIRA)
        self.assertEqual(a["mode"], "act")
        self.assertEqual(a["target"]["repo"], "example-org/widgets")
        self.assertEqual(a["target"]["base_branch"], "develop")
        self.assertEqual(a["target"]["repo_source"], "the AI prompt")

    def test_jira_without_repo_or_base_asks(self):
        a = wc.assess(ticket("jira-ask.json"), DEFAULT_JIRA)
        self.assertEqual(a["mode"], "ask")
        self.assertEqual(a["needs_user"], ["repo", "base_branch"])

    def test_jira_user_answers_settle_the_ask(self):
        a = wc.assess(ticket("jira-ask.json"), DEFAULT_JIRA, repo="example-org/widgets", base="main")
        self.assertEqual(a["mode"], "act")
        self.assertEqual(a["target"]["repo_source"], "given by the user")

    def test_jira_two_repos_is_ambiguous(self):
        t = ticket("jira-act.json")
        with_prompt(t, "Change the exporter in repo `example-org/widgets` and the "
                    "client in `example-org/gadgets` repository.\nBase branch: main\nVerify: tests pass.")
        a = wc.assess(t, DEFAULT_JIRA)
        self.assertEqual(a["mode"], "ask")
        self.assertEqual(a["needs_user"], ["repo"])
        self.assertIn("more than one repo", a["warnings"][0])

    def test_branch_named_in_passing_is_not_the_base(self):
        t = ticket("jira-act.json")
        with_prompt(t, "Repository: https://github.com/example-org/widgets\n"
                    "Work on a new branch `feat/x` off `main`.\nVerify: tests pass.")
        a = wc.assess(t, DEFAULT_JIRA)
        self.assertEqual(a["target"]["repo"], "example-org/widgets")
        self.assertEqual(a["needs_user"], ["base_branch"])

    def test_github_prompt_naming_another_repo_asks(self):
        t = ticket("github-act.json")
        with_prompt(t, "> Repository: `example-org/gadgets`\n> Verify: tests pass.")
        a = wc.assess(t, DEFAULT_GH)
        self.assertEqual(a["mode"], "ask")
        self.assertEqual(a["needs_user"], ["repo"])

    def test_labelled_base_in_a_block_quote(self):
        t = ticket("github-act.json")
        with_prompt(t, "> **Base branch:** `release/2.x`\n> Verify: tests pass.")
        a = wc.assess(t, DEFAULT_GH)
        self.assertEqual(a["target"]["base_branch"], "release/2.x")

    def test_user_base_beats_the_prompt(self):
        a = wc.assess(ticket("jira-act.json"), DEFAULT_JIRA, base="hotfix")
        self.assertEqual(a["target"]["base_branch"], "hotfix")

    def test_missing_verification_warns(self):
        t = ticket("jira-act.json")
        with_prompt(t, "Repository: `example-org/widgets`\nBase branch: `develop`\nMake it UTF-8.")
        a = wc.assess(t, DEFAULT_JIRA)
        self.assertEqual(a["mode"], "act")
        self.assertIn("no way to verify", a["warnings"][0])

    def test_closed_ticket_is_flagged(self):
        t = ticket("jira-act.json")
        t["state"] = "Done"
        self.assertTrue(wc.assess(t, DEFAULT_JIRA)["closed"])

    def test_work_rules_default_and_template(self):
        self.assertEqual(wc.assess(ticket("github-act.json"), DEFAULT_GH)["work"]["merge_command"],
                         "gh pr merge {pr} --squash --delete-branch")
        self.assertIn("--match-head-commit", wc.assess(ticket("github-act.json"), ROUTED)["work"]["merge_command"])

    def test_cli_rejects_a_ticket_without_tracker(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "t.json"
            p.write_text("{}", encoding="utf-8")
            tp = Path(tmp) / "tmpl.json"
            tp.write_text(json.dumps({"template": DEFAULT_GH}), encoding="utf-8")
            code, out = run(["assess", "--ticket", str(p), "--template", str(tp)])
        self.assertEqual(code, 1)
        self.assertEqual(out["status"], "INVALID")


class BranchTests(unittest.TestCase):
    def test_default_pattern(self):
        self.assertEqual(wc.branch_name(DEFAULT_GH, "fix", "41", "Fix exports failing on accented names"),
                         "fix/41-fix-exports-failing-accented-names")

    def test_jira_key_and_tags(self):
        self.assertEqual(wc.branch_name(DEFAULT_JIRA, "feat", "WID-120", "[API] Add the export endpoint"),
                         "feat/WID-120-add-export-endpoint")

    def test_bad_type_and_bad_pattern(self):
        with self.assertRaises(wc.Invalid):
            wc.branch_name(DEFAULT_GH, "hotfix", "1", "x y")
        with self.assertRaises(wc.Invalid):
            wc.branch_name({"work": {"branch": "{owner}/{slug}"}}, "fix", "1", "x y")
        with self.assertRaises(wc.Invalid):
            wc.branch_name(DEFAULT_GH, "fix", "1", "x", slug="a..b")


class MergeGateTests(unittest.TestCase):
    DESC = ("Exports failed for names with accents. The export now writes UTF-8 and a test "
            "covers an accented name. Accented names now export intact.")

    def test_ask_opens_on_the_change_description(self):
        ask = wc.merge_ask(DEFAULT_GH, "https://github.com/example-org/widgets/pull/9", self.DESC, [], False)
        self.assertEqual(ask["header"], "Merge?")
        self.assertTrue(ask["question"].startswith("Change description: Exports failed"))
        self.assertEqual([o["label"] for o in ask["options"]], ["Merge now", "Not yet"])

    def test_open_acceptance_adds_deploy_first_and_a_warning(self):
        ask = wc.merge_ask(DEFAULT_GH, "https://x/pull/9", self.DESC, ["CI never reported"], True)
        self.assertEqual(ask["options"][0]["label"], "Deploy first (Recommended)")
        self.assertIn("⚠️ Warning: the change has a surface", ask["question"])
        self.assertIn("⚠️ Warning: CI never reported", ask["question"])

    def test_description_cannot_be_skipped_or_bloated(self):
        for bad in ("", " ".join(["word"] * 61), "Fixed `writer.py`", "See https://x for details"):
            with self.assertRaises(wc.Invalid):
                wc.merge_ask(DEFAULT_GH, "https://x/pull/9", bad, [], False)

    def test_merge_command_needs_confirm(self):
        with self.assertRaises(wc.Invalid):
            wc.merge_command(DEFAULT_GH, "9", False)
        self.assertEqual(wc.merge_command(DEFAULT_GH, "#9", True), "gh pr merge 9 --squash --delete-branch")

    def test_merge_command_takes_the_template_and_refuses_non_merges(self):
        self.assertEqual(wc.merge_command(ROUTED, "9", True),
                         "gh pr merge 9 --squash --delete-branch --match-head-commit HEAD")
        with self.assertRaises(wc.Invalid):
            wc.merge_command({"work": {"merge_command": "git push --force"}}, "9", True)

    def test_cli_without_confirm_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            tp = Path(tmp) / "tmpl.json"
            tp.write_text(json.dumps(DEFAULT_GH), encoding="utf-8")
            code, out = run(["merge-command", "--template", str(tp), "--pr", "9"])
        self.assertEqual(code, 1)
        self.assertIn("not been answered yes", out["message"])


class StatusTests(unittest.TestCase):
    def test_routed_board_payload(self):
        p = wc.status_payload(ROUTED, "github", "example-org/widgets", "on_start")
        self.assertEqual(p["board"], {"owner": "example-org", "number": 7, "values": {"Status": "In progress"}})
        self.assertEqual(p["repo"], "example-org/widgets")
        import github_adapter as ga
        path = Path(tempfile.mkdtemp()) / "status.json"
        path.write_text(json.dumps(p), encoding="utf-8")
        self.assertEqual(ga.load_payload(str(path))["board"]["number"], 7)  # set-fields accepts it

    def test_skips(self):
        self.assertIn("no status", wc.status_payload(DEFAULT_GH, "github", "example-org/widgets", "on_pr")["skip"])
        self.assertIn("no board", wc.status_payload(ROUTED, "github", "example-org/scratch", "on_pr")["skip"])

    def test_jira_gets_the_status_name_for_the_transition_op(self):
        self.assertEqual(wc.status_payload(ROUTED, "jira", "example-org/widgets", "on_pr"),
                         {"tracker": "jira", "status": "In review", "when": "on_pr"})
        self.assertIn("no status", wc.status_payload(DEFAULT_GH, "jira", "example-org/widgets", "on_pr")["skip"])

    def test_unrouted_repo_with_stop_fallback_asks(self):
        p = wc.status_payload(ROUTED, "github", "example-org/unknown", "on_pr")
        self.assertEqual(p["needs_user"], "board")
        self.assertEqual(wc.status_payload(ROUTED, "github", "example-org/unknown", "on_pr", board=7)["board"]["number"], 7)


def prompted(text: str) -> dict:
    """A GitHub ticket with no board field, so the AI prompt is the only tier source."""
    t = ticket("github-act.json")
    return with_prompt(dict(t, board={}), text)


BODY = "Repository: example-org/widgets\nBase branch: develop\nVerify: run the export tests."


SHAPES = {
    "plain": "Proposed model/effort: sonnet-med, a small fix\n" + BODY,
    "block-quoted": "\n".join(
        "> " + x for x in ("**Proposed model/effort:** sonnet-med, a small fix\n" + BODY).split("\n")),
    "code block": "```\nProposed model/effort: sonnet-med, a small fix\n" + BODY + "\n```",
}


class PromptTierTests(unittest.TestCase):
    """S8: the tier on the AI prompt's opening `Proposed model/effort:` line."""

    def test_three_shapes_give_the_tier(self):
        for shape, text in SHAPES.items():
            with self.subTest(shape):
                a = wc.assess(prompted(text), DEFAULT_GH)
                self.assertEqual(a["effort"], "sonnet-med")
                self.assertEqual(a["effort_source"], "the AI prompt's Proposed model/effort line")

    def test_fenced_prompt_still_yields_repo_and_base(self):
        a = wc.assess(prompted(SHAPES["code block"]), DEFAULT_GH)
        self.assertEqual(a["candidates"], {"repo": ["example-org/widgets"], "base_branch": ["develop"]})
        self.assertEqual(a["target"]["base_branch"], "develop")
        self.assertEqual(a["mode"], "act")

    def test_board_field_wins_over_the_prompt_line(self):
        t = ticket("github-act.json")
        t["ai_prompt"] = t["sections"]["AI prompt"] = "Proposed model/effort: opus-max\n" + BODY
        a = wc.assess(t, ROUTED)
        self.assertEqual((a["effort"], a["effort_source"]), ("high", "the board's Effort field"))

    def test_only_the_opening_line_counts(self):
        a = wc.assess(prompted("Fix the encoding.\nProposed model/effort: opus-max\n" + BODY), DEFAULT_GH)
        self.assertIsNone(a["effort"])
        self.assertIsNone(wc.assess(prompted("Fix the encoding. " + BODY), DEFAULT_GH)["effort"])

    def test_prose_after_the_tier_is_dropped(self):
        self.assertEqual(wc.prompt_tier("Proposed model/effort: Opus / high - hard to reproduce"), "Opus / high")


class WeightCheckTests(unittest.TestCase):
    """S8: copies plan-staged-rollout's stage-run weight check."""

    def check(self, tier, model="claude-sonnet-5-5", effort="high"):
        return wc.weight_check(tier, model, effort)

    def test_match(self):
        self.assertEqual(self.check("sonnet-high")["status"], "match")
        self.assertEqual(self.check("sonnet-med", effort="medium")["status"], "match")  # med = medium

    def test_effort_differing_either_way_stops(self):
        for tier, effort in (("sonnet-low", "high"), ("sonnet-high", "medium")):
            with self.subTest(tier):
                r = self.check(tier, effort=effort)
                self.assertEqual(r["status"], "mismatch")
                self.assertIn("type **go** (or just **.**)", r["line"])
        self.assertIn("This session is on Sonnet / medium; this ticket needs Sonnet / high.",
                      self.check("sonnet-high", effort="medium")["line"])

    def test_lighter_model_stops_heavier_alone_does_not(self):
        r = self.check("opus-high")
        self.assertEqual(r["status"], "mismatch")
        self.assertIn("needs Opus / high", r["line"])
        self.assertEqual(self.check("sonnet-high", model="claude-opus-5-5")["status"], "match")
        self.assertEqual(self.check("haiku", model="claude-fable-5-1", effort="low")["status"], "match")
        self.assertEqual(self.check("opus-high", model="claude-fable-5-1")["status"], "match")  # same class

    def test_unreadable_effort_is_said_not_a_mismatch(self):
        r = self.check("sonnet-high", effort="")
        self.assertEqual(r["status"], "match")
        self.assertIn("could not be read", r["line"])
        self.assertEqual(self.check("opus-high", effort="")["status"], "mismatch")  # model still counts

    def test_unrecognised_tier_or_model_asks(self):
        for tier, model in (("sonnet-ultracode", "claude-sonnet-5-5"), ("gpt9-max", "claude-sonnet-5-5"),
                            ("sonnet-high", "gpt-9"), ("sonnet-high", "")):
            with self.subTest((tier, model)):
                r = self.check(tier, model=model)
                self.assertEqual(r["status"], "ask")
                self.assertIn("do not guess", r["line"])

    def test_effort_only_tier_compares_effort_alone(self):
        self.assertEqual(self.check("high", model="gpt-9")["status"], "match")
        self.assertEqual(self.check("low")["status"], "mismatch")

    def test_no_tier_means_nothing_to_check(self):
        self.assertEqual(self.check("")["status"], "match")

    def test_cli(self):
        code, out = run(["weight-check", "--tier", "opus-high", "--model-id", "claude-sonnet-5-5",
                         "--effort", "high"])
        self.assertEqual((code, out["status"]), (0, "mismatch"))


def linked(key, state="open", blocks=(), blocked_by=(), **extra):
    links = [{"kind": "blocks", "direction": "outward", "target": k} for k in blocks]
    links += [{"kind": "blocks", "direction": "inward", "target": k} for k in blocked_by]
    return {"tracker": "github", "key": key, "title": f"Ticket {key}", "url": f"https://example.test/{key}",
            "state": state, "links": links, "sections": {}, **extra}


class UnblockedTests(unittest.TestCase):
    """S8: after a merge, the tickets that are now free to work."""

    def test_only_tickets_whose_blockers_are_all_done_are_offered(self):
        merged = linked("1", blocks=["2", "3", "4", "5"])
        prompt = "Proposed model/effort: sonnet-low\n" + BODY
        others = [
            linked("2", blocked_by=["1"], sections={"AI prompt": prompt},
                   ai_prompt=prompt, ai_prompt_section="AI prompt"),
            linked("3", blocked_by=["1", "9"]),               # 9 is still open
            linked("4", state="closed", blocked_by=["1"]),    # already done
            linked("9", state="open"),
            linked("8", state="closed"),
            linked("6", blocked_by=["1", "8"]),               # not blocked by merged: ignored
        ]
        r = wc.unblocked(merged, others, DEFAULT_GH)
        self.assertEqual([u["key"] for u in r["unblocked"]], ["2"])
        self.assertEqual(r["unblocked"][0]["tier"], "sonnet-low")
        self.assertEqual(r["unblocked"][0]["command"], "/tickets:work-issue 2")
        self.assertEqual(r["unblocked"][0]["mode"], "act")
        self.assertEqual(r["still_blocked"][0]["waiting_on"], ["9"])
        self.assertEqual([c["key"] for c in r["already_closed"]], ["4"])
        self.assertEqual([c["key"] for c in r["unchecked"]], ["5"])  # never fetched: not offered

    def test_a_blocker_that_was_not_fetched_is_unchecked_not_offered(self):
        r = wc.unblocked(linked("1", blocks=["3"]), [linked("3", blocked_by=["1", "9"])], DEFAULT_GH)
        self.assertEqual(r["unblocked"], [])
        self.assertIn("9", r["unchecked"][0]["reason"])

    def test_jira_blocks_links(self):
        def jira(key, state, links, **kw):
            return dict(tracker="jira", key=key, title=key, url=None, state=state, links=links,
                        sections={}, **kw)
        out = {"name": "Blocks", "direction": "outward"}
        inn = {"name": "Blocks", "direction": "inward"}
        merged = jira("WID-1", "Done", [dict(out, target="WID-2")])
        r = wc.unblocked(merged, [jira("WID-2", "To Do", [dict(inn, target="WID-1")],
                                       fields={"effort": "opus-high"})], DEFAULT_JIRA)
        self.assertEqual(r["unblocked"][0]["command"], "/tickets:work-issue WID-2")
        self.assertEqual(r["unblocked"][0]["tier"], "opus-high")
        self.assertEqual(r["unblocked"][0]["mode"], "guide")  # no AI prompt: guide-only, no tier check

    def test_jira_done_category_counts_whatever_the_status_is_called(self):
        def jira(key, state, links, **kw):
            return dict(tracker="jira", key=key, title=key, url=None, state=state, links=links,
                        sections={}, **kw)
        inn = {"name": "Blocks", "direction": "inward"}
        merged = jira("WID-1", "Dev Done", [{"name": "Blocks", "direction": "outward", "target": "WID-2"}],
                      status_category="done")
        others = [jira("WID-2", "Backlog", [dict(inn, target="WID-1"), dict(inn, target="WID-3")],
                       status_category="new"),
                  jira("WID-3", "Dev Done", [], status_category="done")]
        self.assertEqual([u["key"] for u in wc.unblocked(merged, others, DEFAULT_JIRA)["unblocked"]], ["WID-2"])
        others[1]["status_category"] = "indeterminate"
        self.assertEqual(wc.unblocked(merged, others, DEFAULT_JIRA)["still_blocked"][0]["waiting_on"], ["WID-3"])

    def test_cli(self):
        d = Path(tempfile.mkdtemp())
        (d / "m.json").write_text(json.dumps(linked("1", blocks=["2"])), encoding="utf-8")
        (d / "o.json").write_text(json.dumps([linked("2", blocked_by=["1"])]), encoding="utf-8")
        tp = d / "t.json"
        tp.write_text(json.dumps(DEFAULT_GH), encoding="utf-8")
        code, out = run(["unblocked", "--merged", str(d / "m.json"), "--others", str(d / "o.json"),
                         "--template", str(tp)])
        self.assertEqual((code, [u["key"] for u in out["unblocked"]]), (0, ["2"]))


if __name__ == "__main__":
    unittest.main()
