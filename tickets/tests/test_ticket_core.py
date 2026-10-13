"""Script tests for ticket_core.py's review filter.

No network: the template carries a guarded select field, built inline. Run from anywhere:

    python -m unittest discover -s tickets/tests -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ticket_core
import ticket_template

TEMPLATE, _ = ticket_template.validate_template("default", "jira")
TEMPLATE["fields"] = {
    "regulated_review": {"id": "customfield_00001", "kind": "select", "values": {"Yes": "1", "No": "2"},
                   "default": "unset", "confirm_values": ["Yes"],
                   "ask_when": "the work stores, transmits or processes cardholder data"},
}


class GuardedQuestion(unittest.TestCase):
    def test_question_quotes_ask_when_as_a_condition(self):
        raw = json.dumps([{"check": "guarded-field", "severity": "gap", "where": "Context",
                           "finding": "Regulated data is mentioned.", "question": "Is it Yes?",
                           "field": "regulated_review"}])
        out = ticket_core.review_filter(TEMPLATE, raw)
        q = out["questions"][0]
        self.assertEqual(q["severity"], "blocker")
        self.assertEqual(q["question"],
                         "Is this the case here: the work stores, transmits or processes cardholder "
                         "data? The regulated review field stays unset unless you choose a value.")


DRAFT = {"tracker": "jira", "target": {"site": "x", "project": "K"}, "type": "Story",
         "title": "List every server", "sections": {"Context": "- why", "Acceptance Criteria": "1. done"}}


class ReviewPrompt(unittest.TestCase):
    def test_source_is_quoted_for_the_fidelity_check(self):
        out = ticket_core.review_prompt(TEMPLATE, DRAFT, None, "Produce BackupFailureAudit evidence.")
        self.assertIn("## Source material", out)
        self.assertIn("````text\nProduce BackupFailureAudit evidence.\n````", out)

    def test_split_siblings_reach_the_reviewer(self):
        out = ticket_core.review_prompt(TEMPLATE, DRAFT, None, "Inventory, vaults and alerts.",
                                        ["Alert on failed backups"])
        self.assertIn("## Other tickets drafted from the same source", out)
        self.assertIn("- Alert on failed backups", out)
        self.assertNotIn("same source",
                         ticket_core.review_prompt(TEMPLATE, DRAFT, None, None, ["Alert on failed backups"]))

    def test_no_source_says_to_skip_the_check(self):
        out = ticket_core.review_prompt(TEMPLATE, DRAFT, None)
        self.assertIn("None given: skip the `source-fidelity` check.", out)

    def test_references_reach_the_reviewer_as_text(self):
        t = dict(TEMPLATE, review={"references": [
            {"name": "Team standards", "url": "https://example.com/s", "covers": "backups, access",
             "points": ["Split standard-setting from implementation"]}]})
        out = ticket_core.review_prompt(t, DRAFT, None)
        self.assertIn("- [Team standards](https://example.com/s) covers: backups, access\n"
                      "  - Split standard-setting from implementation", out)

    def test_a_reference_needs_name_url_and_covers(self):
        errors: list[str] = []
        ticket_template.check_semantics({"review": {"references": [{"name": "x"}]}}, errors, base=False)
        self.assertIn("review.references[0].url: required", errors)
        self.assertIn("review.references[0].covers: required", errors)

    def test_new_checks_carry_rubric_severity(self):
        severities = ticket_core.rubric_severities()
        self.assertEqual(severities["source-fidelity"], "gap")
        self.assertEqual(severities["unsourced-decision"], "gap")

    def test_always_asked_gaps_survive_the_question_cap(self):
        items = [{"check": "measurable-ac", "severity": "blocker", "where": "AC", "finding": "f",
                  "question": "q"}]
        items += [{"check": c, "severity": "gap", "where": "w", "finding": "f", "question": "q"}
                  for c in ("why", "scope", "size", "dependencies", "action")]
        items.append({"check": "source-fidelity", "severity": "nit", "where": "w", "finding": "f",
                      "question": "What is BackupFailureAudit?"})
        out = ticket_core.review_filter(TEMPLATE, json.dumps(items))
        checks = [q["check"] for q in out["questions"]]
        self.assertEqual(checks[:2], ["measurable-ac", "source-fidelity"])
        self.assertEqual(len(checks), 5)
        self.assertNotIn("source-fidelity", [g["check"] for g in out["gaps_dropped"]])


class SectionShape(unittest.TestCase):
    """Maintainer feedback in S7: numbered criteria, and an AI prompt that opens with a model/effort."""

    def errors(self, t: dict, sections: dict) -> list[str]:
        return ticket_core.check_draft(t, dict(DRAFT, sections=dict(sections, **{"In plain terms": "Why."})))[0]

    def test_bulleted_acceptance_criteria_are_an_error(self):
        errs = self.errors(TEMPLATE, {"Context": "- why", "Acceptance Criteria": "- done\n- tested"})
        self.assertIn("sections.Acceptance Criteria: must be a numbered list (1. 2. 3.), not bullets", errs)

    def test_numbered_criteria_with_nested_bullets_pass(self):
        errs = self.errors(TEMPLATE, {"Context": "- why", "Acceptance Criteria": "1. done\n   - detail\n2. tested"})
        self.assertEqual(errs, [])

    def test_ai_prompt_must_open_with_model_and_effort_when_required(self):
        t = json.loads(json.dumps(TEMPLATE))
        t["body"]["ai_prompt"] = {"requires": ["effort", "verification"]}
        base = {"Context": "- why", "Acceptance Criteria": "1. done"}
        errs = self.errors(t, dict(base, **{"AI prompt": "Do the thing. Verify by running it."}))
        self.assertIn("sections.AI prompt: must open with a 'Proposed model/effort: <tier>' line", errs)
        ok = dict(base, **{"AI prompt": "**Proposed model/effort:** sonnet-med\n\nDo the thing. Verify it."})
        self.assertEqual(self.errors(t, ok), [])



class AlwaysLabels(unittest.TestCase):
    """S7: the AI-drafted marker moved from a body footer to a label on every ticket."""

    def test_template_labels_are_added_once_after_the_drafts(self):
        t = {"labels": {"allowed": ["security"], "always": ["ai-written"]}}
        self.assertEqual(ticket_core.effective_labels(t, {"labels": ["security"]}), ["security", "ai-written"])
        self.assertEqual(ticket_core.effective_labels(t, {"labels": ["ai-written"]}), ["ai-written"])
        self.assertEqual(ticket_core.effective_labels({}, {}), [])

    def test_an_always_label_is_outside_the_closed_list_check(self):
        t = json.loads(json.dumps(TEMPLATE))
        t["labels"] = {"allowed": ["security"], "always": ["ai-written"]}
        d = dict(DRAFT, sections={"In plain terms": "Why.", "Context": "- why", "Acceptance Criteria": "1. done"})
        self.assertEqual(ticket_core.check_draft(t, d)[0], [])


class CodeWrap(unittest.TestCase):
    """A team's AI prompt can render in a code block; the draft holds it plain."""

    def test_wrapped_section_renders_fenced_and_refuses_a_hand_fence(self):
        t = json.loads(json.dumps(TEMPLATE))
        for s in t["body"]["sections"]:
            if s.get("kind") == "ai_prompt":
                s["wrap"] = "code"
        base = {"In plain terms": "Why.", "Context": "- why", "Acceptance Criteria": "1. done"}
        d = dict(DRAFT, sections=dict(base, **{"AI prompt": "Do it. Verify it."}))
        self.assertIn("## AI prompt\n\n```\nDo it. Verify it.\n```", ticket_core.render_body(t, d))
        fenced = dict(DRAFT, sections=dict(base, **{"AI prompt": "```\nDo it.\n```"}))
        self.assertIn("sections.AI prompt: write it without a code fence; the template adds one",
                      ticket_core.check_draft(t, fenced)[0])


class SectionIcon(unittest.TestCase):
    """A team's headings can carry an emoji; drafts and parsers keep the plain title."""

    def test_icon_renders_before_the_title(self):
        t = json.loads(json.dumps(TEMPLATE))
        for s in t["body"]["sections"]:
            if s["title"] == "Context":
                s["icon"] = "\U0001F4DA"
        d = dict(DRAFT, sections={"In plain terms": "Why.", "Context": "- why", "Acceptance Criteria": "1. done"})
        self.assertIn("## \U0001F4DA Context\n\n- why", ticket_core.render_body(t, d))
        self.assertEqual(ticket_core.check_draft(t, d)[0], [])

    def test_strip_icon_drops_only_a_symbol_word(self):
        self.assertEqual(ticket_core.strip_icon("ℹ️ In plain terms"), "In plain terms")
        self.assertEqual(ticket_core.strip_icon("\U0001F916 AI prompt"), "AI prompt")
        self.assertEqual(ticket_core.strip_icon("✅ Acceptance Criteria"), "Acceptance Criteria")
        self.assertEqual(ticket_core.strip_icon("Context"), "Context")
        self.assertEqual(ticket_core.strip_icon("État actuel"), "État actuel")
        self.assertEqual(ticket_core.strip_icon("\U0001F6AB"), "\U0001F6AB")

    def test_both_parsers_key_sections_by_plain_title(self):
        import github_adapter
        import jira_adapter
        body = "## ℹ️ In plain terms\n\nWhy.\n\n## \U0001F916 AI prompt\n\n```\nDo it.\n```\n"
        for parse in (jira_adapter.parse_sections, github_adapter.parse_sections):
            out = parse(body, 2)
            self.assertEqual(list(out), ["In plain terms", "AI prompt"])


if __name__ == "__main__":
    unittest.main()
