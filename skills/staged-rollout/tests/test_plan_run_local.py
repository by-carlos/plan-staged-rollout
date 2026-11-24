"""Scripted check for `scripts/plan_run_local.py`, the local stage driver.

Covers the readings the driver acts on -- the stage index, the ledger and
BLOCKED.md -- runnable-stage selection by gate and dependencies, the model
and effort flags, the settings, the opening-line check, the outcome of a
finished stage, and the driver loop end to end against a fake launcher in a
throwaway git clone, for each exit status a person acts on.

Run from the repo root:
    python -m unittest discover -s skills/staged-rollout/tests -v
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prl = load("plan_run_local")

PLAN = """\
# Demo — plan

## Stage index & dependencies

| Stage | File | Depends | mode | exec | model | effort | gate |
|---|---|---|---|---|---|---|---|
| S0 Core | `stage-0-core.md` | — | direct | inline | opus | high | auto |
| S1 CLI | `stage-1-cli.md` | S0 | direct | inline | sonnet | med | local |
| S2 Page | `stage-2-page.md` | S0 | direct | inline | sonnet | low | human |
| SF Plan review | `stage-f-review.md` | S1, S2 | direct | inline | opus | high | auto |

Plan flags: `merge: auto` · `plan-dir: delete`
"""

LEDGER = """\
# Demo — build ledger

## Status

| Stage | Status | Verified | Date | Result |
|---|---|---|---|---|
| S0 Core | {S0} | — | — | — |
| S1 CLI | {S1} | — | — | — |
| S2 Page | {S2} | — | — | — |
| SF Plan review | {SF} | — | — | — |

## Notes
"""


def ledger(**rows):
    statuses = {"S0": "todo", "S1": "todo", "S2": "todo", "SF": "todo", **rows}
    return prl.parse_ledger(LEDGER.format(**statuses))


# Four stages that can run side by side once S0 is done, one that waits on
# S1, and two `live` stages that are runnable together but never fired.
WIDE_IDS = ("S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "SF")
WIDE_PLAN = """\
# Wide — plan

## Stage index & dependencies

| Stage | File | Depends | mode | exec | model | effort | gate |
|---|---|---|---|---|---|---|---|
| S0 Core | `stage-0-core.md` | — | direct | inline | opus | high | auto |
| S1 Alpha | `stage-1-alpha.md` | S0 | direct | inline | sonnet | low | auto |
| S2 Beta | `stage-2-beta.md` | S0 | direct | inline | sonnet | low | auto |
| S3 Gamma | `stage-3-gamma.md` | S0 | direct | inline | sonnet | low | local |
| S4 Delta | `stage-4-delta.md` | S0 | direct | inline | sonnet | low | auto |
| S5 After alpha | `stage-5-after.md` | S1 | direct | inline | sonnet | low | auto |
| S6 Cutover | `stage-6-cutover.md` | S0 | direct | inline | opus | high | live |
| S7 Switch | `stage-7-switch.md` | S0 | direct | inline | opus | high | live |
| SF Plan review | `stage-f-review.md` | S1, S2, S3, S4, S5, S6, S7 | direct | inline | opus | high | auto |

Plan flags: `merge: auto` · `plan-dir: delete`
"""


def wide_ledger(**rows):
    statuses = {sid: "todo" for sid in WIDE_IDS}
    statuses.update({"S0": "done", **rows})
    lines = "\n".join(f"| {sid} Stage | {statuses[sid]} | — | — | — |" for sid in WIDE_IDS)
    return ("# Wide — build ledger\n\n## Status\n\n| Stage | Status | Verified | Date | Result |\n"
            f"|---|---|---|---|---|\n{lines}\n\n## Notes\n")


class Readings(unittest.TestCase):
    def test_index_reads_model_effort_gate_and_depends(self):
        stages = prl.parse_index(PLAN)
        self.assertEqual([s["id"] for s in stages], ["S0", "S1", "S2", "SF"])
        self.assertEqual(stages[1], {"id": "S1", "name": "S1 CLI", "depends": ["S0"],
                                     "model": "sonnet", "effort": "med", "gate": "local"})
        self.assertEqual(stages[3]["depends"], ["S1", "S2"])

    def test_absent_gate_column_reads_as_auto(self):
        text = PLAN.replace(" gate |", "").replace("|---|---|---|---|---|---|---|---|",
                                                   "|---|---|---|---|---|---|---|")
        text = "\n".join(l.rsplit(" |", 2)[0] + " |" if l.startswith("| S") else l
                         for l in text.splitlines())
        self.assertEqual({s["gate"] for s in prl.parse_index(text)}, {"auto"})

    def test_index_without_section_is_refused(self):
        with self.assertRaises(prl.PlanError):
            prl.parse_index("# nothing here\n")

    def test_ledger_and_blocked(self):
        rows = ledger(S0="done", S1="`doing`")
        self.assertEqual(rows["S0"]["status"], "done")
        self.assertEqual(rows["S1"]["status"], "doing")
        blocked = prl.parse_blocked("# Blocked\n\n### S1 CLI\n\nNeeds the API key rotated.\n\n### S2\n")
        self.assertEqual(blocked, {"S1": "Needs the API key rotated.", "S2": ""})

    def test_stage_arg(self):
        self.assertEqual([prl.stage_arg(s) for s in ("S0", "S12", "S3a", "SF")],
                         ["0", "12", "3a", "f"])


class Selection(unittest.TestCase):
    def setUp(self):
        self.stages = prl.parse_index(PLAN)

    def test_first_stage_has_no_dependencies(self):
        pick = prl.select(self.stages, ledger())
        self.assertEqual(pick["stage"]["id"], "S0")
        self.assertFalse(pick["complete"])

    def test_local_gate_is_fired_human_is_gated(self):
        pick = prl.select(self.stages, ledger(S0="done"))
        self.assertEqual(pick["stage"]["id"], "S1")
        self.assertEqual(pick["gated"], [{"id": "S2", "gate": "human", "known": True}])

    def test_unknown_gate_is_gated_and_flagged(self):
        stages = prl.parse_index(PLAN.replace("| low | human |", "| low | nightly |"))
        pick = prl.select(stages, ledger(S0="done", S1="done"))
        self.assertIsNone(pick["stage"])
        self.assertEqual(pick["gated"], [{"id": "S2", "gate": "nightly", "known": False}])

    def test_unsettled_dependency_is_not_runnable(self):
        pick = prl.select(self.stages, ledger(S0="done", S1="blocked", S2="skipped"))
        self.assertIsNone(pick["stage"])
        self.assertEqual(pick["waiting"], [{"id": "S1", "status": "blocked"}])

    def test_skipped_counts_as_settled(self):
        pick = prl.select(self.stages, ledger(S0="done", S1="done", S2="skipped"))
        self.assertEqual(pick["stage"]["id"], "SF")

    def test_complete(self):
        pick = prl.select(self.stages, ledger(S0="done", S1="done", S2="skipped", SF="done"))
        self.assertTrue(pick["complete"])
        self.assertIsNone(pick["stage"])

    def test_blocked_section_holds_a_todo_row(self):
        pick = prl.select(self.stages, ledger(), {"S0": "Waiting on the vendor."})
        self.assertIsNone(pick["stage"])
        self.assertEqual(pick["waiting"], [{"id": "S0", "status": "blocked"}])

    def test_blocked_section_on_a_done_row_is_ignored(self):
        pick = prl.select(self.stages, ledger(S0="done"), {"S0": ""})
        self.assertEqual(pick["stage"]["id"], "S1")

    def test_missing_ledger_row_reads_as_todo(self):
        self.assertEqual(prl.select(self.stages, {})["stage"]["id"], "S0")


class ParallelSelection(unittest.TestCase):
    def setUp(self):
        self.stages = {s["id"]: s for s in prl.parse_index(WIDE_PLAN)}
        self.index = list(self.stages.values())

    def pick(self, **rows):
        return prl.select(self.index, prl.parse_ledger(wide_ledger(**rows)))

    def test_the_whole_runnable_set_in_index_order(self):
        pick = self.pick()
        self.assertEqual([s["id"] for s in pick["runnable"]], ["S1", "S2", "S3", "S4"])
        self.assertEqual(pick["stage"]["id"], "S1")
        self.assertEqual([g["id"] for g in pick["gated"]], ["S6", "S7"])

    def test_a_stage_joins_the_set_when_its_dependency_is_done(self):
        self.assertNotIn("S5", [s["id"] for s in self.pick()["runnable"]])
        self.assertEqual([s["id"] for s in self.pick(S1="done")["runnable"]], ["S2", "S3", "S4", "S5"])

    def test_nothing_runnable_leaves_an_empty_set(self):
        pick = self.pick(S0="doing")
        self.assertEqual((pick["runnable"], pick["stage"]), ([], None))

    def test_next_to_start_skips_running_stages_and_their_dependents(self):
        s = self.stages
        self.assertEqual(prl.next_to_start([s["S1"], s["S5"], s["S2"]], [s["S1"]])["id"], "S2")
        self.assertIsNone(prl.next_to_start([s["S5"]], [s["S1"]]))
        self.assertEqual(prl.next_to_start([s["S5"]], [s["S2"]])["id"], "S5")

    def test_never_two_live_stages_at_once(self):
        s = self.stages
        self.assertIsNone(prl.next_to_start([s["S7"]], [s["S6"]]))
        self.assertEqual(prl.next_to_start([s["S7"], s["S2"]], [s["S6"]])["id"], "S2")
        self.assertEqual(prl.next_to_start([s["S7"]], [s["S2"]])["id"], "S7")


class Flags(unittest.TestCase):
    def test_effort_mapping(self):
        self.assertEqual(prl.effort_flag("med"), "medium")
        self.assertEqual(prl.effort_flag("high"), "high")
        self.assertEqual(prl.effort_flag(""), "")
        with self.assertRaises(prl.PlanError):
            prl.effort_flag("extreme")

    def test_settings_defaults(self):
        conf = prl.settings({})
        self.assertEqual(conf, {"launcher": "claude", "mode": "auto", "idle_seconds": 900.0,
                                "max_wait_seconds": 21600.0, "budget": "", "scrub": False})
        self.assertEqual(prl.settings({"CLAUDE_STAGE_MAX_WAIT_HOURS": "0"})["max_wait_seconds"], 0)
        self.assertTrue(prl.settings({"CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "1"})["scrub"])
        self.assertFalse(prl.settings({"CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "0"})["scrub"])

    def test_settings_refuse_bypass_and_bad_numbers(self):
        for env in ({"CLAUDE_STAGE_PERMISSION_MODE": "bypassPermissions"},
                    {"CLAUDE_STAGE_PERMISSION_MODE": "plan"},
                    {"CLAUDE_STAGE_IDLE_MINUTES": "0"},
                    {"CLAUDE_STAGE_MAX_WAIT_HOURS": "-1"},
                    {"CLAUDE_STAGE_MAX_BUDGET_USD": "lots"}):
            with self.assertRaises(prl.PlanError, msg=env):
                prl.settings(env)

    def test_stage_command(self):
        stage = prl.parse_index(PLAN)[1]
        conf = prl.settings({"CLAUDE_STAGE_MAX_BUDGET_USD": "5"})
        cmd = prl.stage_command(["claude"], stage, conf)
        self.assertEqual(cmd, [
            "claude", "-p", "/plan-staged-rollout:stage-run 1 --unattended --runner local",
            "--model", "sonnet", "--effort", "medium",
            "--output-format", "stream-json", "--verbose",
            "--permission-prompts", "none", "--permission-mode", "auto",
            "--max-budget-usd", "5"])

    def test_stage_without_model_or_effort_omits_the_flags(self):
        stage = {"id": "SF", "model": "", "effort": "", "gate": "auto"}
        cmd = prl.stage_command(["claude"], stage, prl.settings({}))
        self.assertNotIn("--model", cmd)
        self.assertNotIn("--effort", cmd)
        self.assertIn("/plan-staged-rollout:stage-run f --unattended --runner local", cmd)

    def test_version(self):
        self.assertEqual(prl.parse_version("2.1.268 (Claude Code)"), (2, 1, 268))
        self.assertIsNone(prl.parse_version("unknown"))


class InitCheck(unittest.TestCase):
    stage = {"id": "S1", "model": "sonnet", "effort": "med", "gate": "auto"}

    def test_match(self):
        init = {"permissionMode": "auto", "model": "claude-sonnet-5-5", "effort": "medium"}
        self.assertEqual(prl.check_init(init, self.stage, prl.settings({})), [])

    def test_auto_mode_disabled_falls_back_to_manual(self):
        init = {"permissionMode": "default", "model": "claude-sonnet-5-5", "effort": "medium"}
        problems = prl.check_init(init, self.stage, prl.settings({}))
        self.assertEqual(len(problems), 1)
        self.assertIn("auto mode is unavailable", problems[0])

    def test_manual_opt_in_accepts_default(self):
        init = {"permissionMode": "default", "model": "claude-sonnet-5-5"}
        conf = prl.settings({"CLAUDE_STAGE_PERMISSION_MODE": "manual"})
        self.assertEqual(prl.check_init(init, self.stage, conf), [])

    def test_model_and_effort_mismatch(self):
        init = {"permissionMode": "auto", "model": "claude-haiku-5-5", "effort": "low"}
        problems = prl.check_init(init, self.stage, prl.settings({}))
        self.assertEqual(len(problems), 2)

    def test_unreported_effort_is_not_a_mismatch(self):
        init = {"permissionMode": "auto", "model": "claude-sonnet-5-5"}
        self.assertEqual(prl.check_init(init, self.stage, prl.settings({})), [])


class Outcome(unittest.TestCase):
    def test_matrix(self):
        cases = [
            (("todo", "done", False, False), "done"),
            (("todo", "skipped", False, False), "done"),
            (("todo", "blocked", False, False), "stage-blocked"),
            (("todo", "doing", True, False), "stage-blocked"),
            (("todo", "doing", False, False), "stage-stopped"),
            (("todo", "todo", False, False), "stage-dead"),
            (("todo", "doing", False, True), "stage-dead"),
            (("doing", "doing", False, False), "stage-dead"),
            (("doing", "done", False, False), "done"),
            (("todo", "todo", False, False, True), "stage-stopped"),
            (("todo", "todo", False, True, True), "stage-dead"),
            # ended on the usage limit: whatever the row, unless it finished or blocked
            (("todo", "todo", False, False, False, True), "stage-limited"),
            (("todo", "doing", False, False, True, True), "stage-limited"),
            (("todo", "todo", False, True, False, True), "stage-limited"),
            (("todo", "done", False, False, False, True), "done"),
            (("todo", "doing", True, False, False, True), "stage-blocked"),
        ]
        for args, want in cases:
            self.assertEqual(prl.outcome(*args), want, args)


# The line a real `claude -p` (2.1.302) printed while the weekly limit was at 91%.
PROBE = {"type": "rate_limit_event", "rate_limit_info": {
    "status": "allowed_warning", "resetsAt": 1795518000, "rateLimitType": "seven_day", "utilization": 0.91,
    "overageStatus": "rejected", "isUsingOverage": False, "surpassedThreshold": 0.75,
    "unifiedWindows": {"five_hour": {"utilization": 0.64, "resetsAt": 1795449600},
                       "seven_day": {"utilization": 0.91, "resetsAt": 1795518000}}},
    "session_id": "a7ee2f2b"}
# The limit message an SDK session (2.1.302) wrote to its transcript.
HIT = {"type": "assistant", "error": "rate_limit", "isApiErrorMessage": True, "apiErrorStatus": 429,
       "apiError": "usage_limit_reached",
       "apiErrorParams": {"rate_limit_info": {"status": "rejected", "resetsAt": 1794228600,
                                              "rateLimitType": "five_hour", "isUsingOverage": False}},
       "message": {"content": [{"type": "text", "text": "You've hit your session limit · resets 1:50am"}]}}


class UsageReadings(unittest.TestCase):
    def test_five_hour_window_from_a_real_line(self):
        self.assertEqual(prl.five_hour(PROBE), {"percent": 64.0, "resets_at": 1795449600.0})

    def test_five_hour_window_at_the_top_level(self):
        event = {"type": "rate_limit_event", "rate_limit_info": {
            "status": "allowed", "rateLimitType": "five_hour", "utilization": 0.2, "resetsAt": 100}}
        self.assertEqual(prl.five_hour(event), {"percent": 20.0, "resets_at": 100.0})

    def test_no_five_hour_window(self):
        weekly = {"type": "rate_limit_event", "rate_limit_info": {
            "status": "allowed", "rateLimitType": "seven_day", "utilization": 0.2, "resetsAt": 100}}
        for event in (weekly, {"type": "result"}, {"type": "rate_limit_event"}, "text"):
            self.assertIsNone(prl.five_hour(event), event)

    def test_limit_hit_signs(self):
        rejected = {"type": "rate_limit_event", "rate_limit_info": {
            "status": "rejected", "resetsAt": 500, "rateLimitType": "five_hour", "isUsingOverage": False}}
        self.assertEqual(prl.limit_hit(rejected), {"resets_at": 500.0, "type": "five_hour"})
        self.assertEqual(prl.limit_hit(HIT), {"resets_at": 1794228600.0, "type": "five_hour"})
        bare = {"type": "assistant", "error": "rate_limit", "message": {"content": []}}
        self.assertEqual(prl.limit_hit(bare), {"resets_at": None, "type": None})

    def test_not_a_limit_hit(self):
        overage = {"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "isUsingOverage": True}}
        for event in (PROBE, overage, {"type": "assistant", "message": {}},
                      {"type": "assistant", "error": "overloaded"}):
            self.assertIsNone(prl.limit_hit(event), event)

    def test_transcript_limit(self):
        with tempfile.TemporaryDirectory() as config:
            folder = Path(config) / "projects" / "C--repo"
            folder.mkdir(parents=True)
            (folder / "abc-123.jsonl").write_text(
                json.dumps({"type": "user"}) + "\n" + json.dumps(HIT) + "\n", encoding="utf-8")
            env = {"CLAUDE_CONFIG_DIR": config}
            self.assertEqual(prl.transcript_limit("abc-123", env)["resets_at"], 1794228600.0)
            self.assertIsNone(prl.transcript_limit("other", env))
            self.assertIsNone(prl.transcript_limit("../x", env))
            self.assertIsNone(prl.transcript_limit(None, env))


class UsageGate(unittest.TestCase):
    def test_cutoff_before_any_jump(self):
        self.assertFalse(prl.gate_holds(None, None))
        self.assertFalse(prl.gate_holds(89.9, None))
        self.assertTrue(prl.gate_holds(90, None))

    def test_ceiling_with_a_measured_jump(self):
        self.assertFalse(prl.gate_holds(80, 15))   # lands on 95: does not pass it
        self.assertTrue(prl.gate_holds(80.1, 15))
        self.assertFalse(prl.gate_holds(93, 2))    # past the cutoff, but the jump fits
        self.assertTrue(prl.gate_holds(10, 90))
        self.assertFalse(prl.gate_holds(None, 90))

    def test_jump(self):
        a = {"percent": 40.0, "resets_at": 1000.0}
        self.assertEqual(prl.stage_jump(a, {"percent": 52.5, "resets_at": 1000.0}), 12.5)
        # the desktop app's reset carries milliseconds
        self.assertEqual(prl.stage_jump({"percent": 40.0, "resets_at": 1000.885},
                                        {"percent": 41.0, "resets_at": 1000.0}), 1.0)

    def test_jump_across_a_reset_is_discarded(self):
        a = {"percent": 80.0, "resets_at": 1000.0}
        self.assertIsNone(prl.stage_jump(a, {"percent": 5.0, "resets_at": 19000.0}))
        self.assertIsNone(prl.stage_jump(a, {"percent": 85.0, "resets_at": 19000.0}))
        self.assertIsNone(prl.stage_jump(None, a))
        self.assertIsNone(prl.stage_jump({"percent": 0.0, "resets_at": None}, a))
        self.assertIsNone(prl.stage_jump(a, {"percent": 70.0, "resets_at": 1000.0}))

    def test_seed_reading(self):
        self.assertIsNone(prl.seed_reading(None, None))
        seeded = prl.seed_reading(62, "2026-11-23T16:00:00.885Z")
        self.assertEqual(seeded["percent"], 62.0)
        self.assertAlmostEqual(seeded["resets_at"], 1795449600.885, places=3)
        self.assertEqual(prl.seed_reading(5, "1795449600")["resets_at"], 1795449600.0)
        for args in ((62, None), (None, "1"), (101, "1"), (5, "tomorrow")):
            with self.assertRaises(prl.PlanError, msg=args):
                prl.seed_reading(*args)

    def test_gate_line(self):
        reading = {"percent": 62.0, "resets_at": 1795449600.0}
        line = prl.gate_line("S1", reading, None, False)
        self.assertIn("62% of the 5-hour limit used, resets 2026-11-23 16:00 UTC", line)
        self.assertIn("holding at 90%", line)
        self.assertTrue(line.endswith("S1 starts"))
        self.assertIn("waits for the reset", prl.gate_line("S1", reading, 40.0, True))
        self.assertIn("no 5-hour reading yet", prl.gate_line("S0", None, None, False))


class RampUp(unittest.TestCase):
    def test_with_nothing_in_flight_it_is_the_gate(self):
        for percent, jump in ((None, None), (50.0, None), (89.9, None), (90.0, None),
                              (60.0, 30.0), (70.0, 30.0)):
            self.assertEqual(prl.ramp_allows(percent, jump, 0), not prl.gate_holds(percent, jump),
                             (percent, jump))

    def test_unmeasured_stages_stop_at_the_starting_count(self):
        self.assertEqual(prl.START_AT_ONCE, 2)
        self.assertTrue(prl.ramp_allows(10.0, None, 1))
        self.assertFalse(prl.ramp_allows(10.0, None, 2))
        self.assertTrue(prl.ramp_allows(None, None, 1))   # no reading at all
        self.assertFalse(prl.ramp_allows(None, None, 2))
        self.assertTrue(prl.ramp_allows(None, 5.0, 1))    # a jump, but no share since the reset
        self.assertFalse(prl.ramp_allows(None, 5.0, 2))

    def test_unmeasured_stages_still_hold_at_the_cutoff(self):
        self.assertFalse(prl.ramp_allows(90.0, None, 1))

    def test_each_stage_in_flight_and_the_next_count_one_jump(self):
        self.assertTrue(prl.ramp_allows(50.0, 10.0, 2))    # 50 + 10 × 3 = 80: a third starts
        self.assertTrue(prl.ramp_allows(50.0, 10.0, 3))    # 50 + 10 × 4 = 90: past the starting count
        self.assertFalse(prl.ramp_allows(50.0, 10.0, 4))   # 50 + 10 × 5 = 100
        self.assertTrue(prl.ramp_allows(65.0, 10.0, 2))    # 65 + 10 × 3 = 95, at the ceiling
        self.assertFalse(prl.ramp_allows(65.1, 10.0, 2))

    def test_no_cost_is_assumed_for_a_cheap_stage(self):
        # A measured jump of zero is taken as measured: no floor is put on it.
        self.assertTrue(prl.ramp_allows(40.0, 0.0, 12))

    def test_ramp_line(self):
        reading = {"percent": 50.0, "resets_at": 1_800_003_600.0}
        line = prl.ramp_line("S3", reading, 10.0, ["S1", "S2"], True)
        self.assertIn("2 in flight (S1, S2)", line)
        self.assertIn("50 + 10 × 3 = 80% against 95%", line)
        self.assertTrue(line.endswith("S3 starts beside them"))
        line = prl.ramp_line("S3", None, None, ["S1", "S2"], False)
        self.assertIn("no stage measured yet, so at most 2 at once", line)
        self.assertTrue(line.endswith("S3 waits for a stage to end"))
        self.assertIn("holding at 90%", prl.ramp_line("S2", {"percent": 91.0, "resets_at": None},
                                                       None, ["S1"], False))


class FakeClock:
    """The driver's clock and sleep: sleeping moves time on at once."""

    def __init__(self, start=1_800_000_000.0):
        self.now, self.slept = start, []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


FAKE = textwrap.dedent('''\
    """Stands in for `claude -p`: acts on .plan/ as FAKE_MODE says."""
    import json, os, re, sys, time
    args = sys.argv[1:]
    prompt = args[args.index("-p") + 1]
    stage = "SF" if prompt.split()[1] == "f" else "S" + prompt.split()[1]
    model = args[args.index("--model") + 1] if "--model" in args else "claude-default"
    modes = json.loads(os.environ.get("FAKE_MODES", "{}"))  # per stage, for stages side by side
    mode = modes.get(stage, os.environ.get("FAKE_MODE", "done"))
    target = stage in modes or stage == os.environ.get("FAKE_STAGE", stage)
    trace = os.environ.get("FAKE_TRACE")
    if trace:  # one file per session: when it started and ended, for overlap checks
        trace = trace + "-" + stage + "-" + str(os.getpid())
        open(trace, "w").write("start " + repr(time.time()) + "\\n")
    reported = "default" if mode == "no-auto" else args[args.index("--permission-mode") + 1]
    print(json.dumps({"type": "system", "subtype": "init", "session_id": "fake-" + stage,
                      "permissionMode": reported, "model": "claude-" + model + "-5-5"}), flush=True)
    if mode == "idle":
        time.sleep(60)
    reset = os.environ.get("FAKE_RESET")
    def window(util):  # a rate_limit_event line as Claude Code 2.1.302 prints it
        print(json.dumps({"type": "rate_limit_event", "session_id": "fake-" + stage, "rate_limit_info": {
            "status": "allowed_warning", "rateLimitType": "seven_day", "utilization": 0.5,
            "unifiedWindows": {"five_hour": {"utilization": util, "resetsAt": int(reset)},
                               "seven_day": {"utilization": 0.5, "resetsAt": int(reset) + 86400}}}}), flush=True)
    windows = json.loads(os.environ.get("FAKE_WINDOWS", "{}"))
    if stage in windows:
        window(windows[stage][0])
    sibling = json.loads(os.environ.get("FAKE_AWAIT", "{}")).get(stage)
    if sibling and trace:  # stay in flight until that stage has started too (30 s at most)
        import glob
        until = time.time() + 30
        while time.time() < until and not glob.glob(os.environ["FAKE_TRACE"] + "-" + sibling + "-*"):
            time.sleep(0.05)
    time.sleep(json.loads(os.environ.get("FAKE_SLEEP", "{}")).get(stage, 0))
    if mode.startswith("limit"):
        counter = os.environ["FAKE_COUNTER"]
        hits = int(open(counter).read()) if os.path.exists(counter) else 0
        if target and hits < int(os.environ.get("FAKE_LIMIT_TIMES", "1")):
            open(counter, "w").write(str(hits + 1))
            info = {"status": "rejected", "rateLimitType": "five_hour", "isUsingOverage": False}
            if reset and mode == "limit":
                info["resetsAt"] = int(reset)
                print(json.dumps({"type": "rate_limit_event", "rate_limit_info": info}), flush=True)
            print(json.dumps({"type": "assistant", "error": "rate_limit", "session_id": "fake-" + stage,
                              "message": {"content": [{"type": "text", "text": "You've hit your session limit"}]}}),
                  flush=True)
            if mode == "limit-transcript":  # the reset only in the session's own transcript
                folder = os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "projects", "demo")
                os.makedirs(folder, exist_ok=True)
                with open(os.path.join(folder, "fake-" + stage + ".jsonl"), "w") as fh:
                    fh.write(json.dumps({"type": "assistant", "error": "rate_limit", "apiError": "usage_limit_reached",
                                         "apiErrorParams": {"rate_limit_info": {**info, "resetsAt": int(reset)}}}) + "\\n")
            print(json.dumps({"type": "result", "subtype": "success", "is_error": True,
                              "result": "You've hit your session limit", "session_id": "fake-" + stage}), flush=True)
            if trace:
                open(trace, "a").write("end " + repr(time.time()) + "\\n")
            sys.exit(1)
        mode = "done"
    lock = os.path.join(os.path.dirname(trace), "ledger.lock") if trace else None
    while lock:  # sessions side by side take turns at the ledger file
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL))
            break
        except FileExistsError:
            time.sleep(0.05)
    ledger = os.path.join(".plan", "LEDGER.md")
    text = open(ledger, encoding="utf-8").read()
    row = "done" if mode == "done" or not target else "doing"
    if mode in ("done", "block", "stop"):
        text = re.sub(r"^(\\| " + stage + r" [^|]*\\| )\\w+", r"\\g<1>" + row, text, flags=re.M)
        open(ledger, "w", encoding="utf-8").write(text)
        if mode == "block" and row == "doing":
            open(os.path.join(".plan", "BLOCKED.md"), "a", encoding="utf-8").write(
                "\\n### " + stage + "\\n\\nThe staging host is unreachable.\\n")
    if lock:
        os.remove(lock)
    if mode == "pr":  # pushes its stage branch, then its merge is refused: the row never moves
        import subprocess
        subprocess.run(["git", "branch", "plan-demo-s" + stage[1:].lower()], check=True)
    if stage in windows:
        window(windows[stage][1])
    if trace:
        open(trace, "a").write("end " + repr(time.time()) + "\\n")
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                      "result": "stage " + stage + " " + mode, "session_id": "fake-" + stage}), flush=True)
''')


class LoopBase(unittest.TestCase):
    """A throwaway clone on `plan-demo` holding `plan` and `ledger`, and a
    fake launcher; `drive` runs the driver against them."""
    plan = PLAN
    ledger = LEDGER.format(S0="todo", S1="todo", S2="todo", SF="todo")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / ".plan").mkdir()
        (self.repo / ".plan" / "PLAN.md").write_text(self.plan, encoding="utf-8")
        (self.repo / ".plan" / "LEDGER.md").write_text(self.ledger, encoding="utf-8")
        self.fake = self.repo.parent / f"fake_claude_{os.getpid()}_{id(self)}.py"
        self.fake.write_text(FAKE, encoding="utf-8")
        self.git("init", "-q", "-b", "plan-demo")
        self.git("add", ".")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.invalid",
                 "commit", "-q", "-m", "plan")

    def tearDown(self):
        self.fake.unlink(missing_ok=True)
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def drive(self, env=None, resume=None, usage=None, clock=None, stagger=0):
        config = Path(self.tmp.name).parent / f"fake_config_{os.getpid()}_{id(self)}"
        self.addCleanup(lambda: __import__("shutil").rmtree(config, ignore_errors=True))
        env = {"FAKE_MODE": "done", "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "",
               "CLAUDE_CONFIG_DIR": str(config), "FAKE_COUNTER": str(config / "hits"),
               "FAKE_TRACE": str(config / "trace"), **(env or {})}
        config.mkdir(exist_ok=True)
        with mock.patch.dict(os.environ, env):
            driver = prl.Driver(self.repo, dict(os.environ), usage=usage,
                                launcher_argv=[sys.executable, str(self.fake)], grace_seconds=0)
            driver.stagger = stagger
            if clock:
                driver.clock, driver.sleep = clock.time, clock.sleep
            line = driver.run(resume=resume)
        self.trace_file = config / "trace"
        return line, prl.read_json(driver.status_path)

    def ledger_now(self):
        return prl.parse_ledger((self.repo / ".plan" / "LEDGER.md").read_text(encoding="utf-8"))

    def outcomes(self, state):
        return [(s["id"], s["outcome"]) for s in state["stages"]]


class DriverLoop(LoopBase):
    def test_runs_until_a_gated_stage(self):
        line, state = self.drive()
        self.assertTrue(line.startswith("STATUS: gated"), line)
        self.assertIn("S2 (gate human)", line)
        self.assertEqual([(s["id"], s["outcome"]) for s in state["stages"]],
                         [("S0", "done"), ("S1", "done")])
        self.assertEqual(state["stages"][1]["effort"], "medium")
        self.assertEqual(state["state"], "exited")
        self.assertEqual(state["line"], line)
        self.assertTrue(Path(state["stages"][0]["log"]).is_file())

    def test_plan_complete(self):
        ledger = self.repo / ".plan" / "LEDGER.md"
        ledger.write_text(LEDGER.format(S0="done", S1="done", S2="skipped", SF="todo"), encoding="utf-8")
        line, state = self.drive()
        self.assertTrue(line.startswith("STATUS: plan-complete"), line)
        self.assertIn("plan-close", line)

    def test_blocked_stage_stops_the_run(self):
        line, state = self.drive({"FAKE_MODE": "block", "FAKE_STAGE": "S1"})
        self.assertTrue(line.startswith("STATUS: stage-blocked"), line)
        self.assertIn("staging host is unreachable", line)
        self.assertEqual(state["stage"], "S1")

    def test_stopped_stage(self):
        line, _ = self.drive({"FAKE_MODE": "stop", "FAKE_STAGE": "S0"})
        self.assertTrue(line.startswith("STATUS: stage-stopped"), line)

    def test_a_recorded_block_skips_the_grace_wait(self):
        with mock.patch.object(prl.time, "sleep") as slept, \
                mock.patch.dict(os.environ, {"FAKE_MODE": "block", "FAKE_STAGE": "S0",
                                             "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": ""}):
            driver = prl.Driver(self.repo, dict(os.environ),
                                launcher_argv=[sys.executable, str(self.fake)], grace_seconds=5)
            line = driver.run()
        self.assertTrue(line.startswith("STATUS: stage-blocked"), line)
        self.assertNotIn(mock.call(5), slept.call_args_list)

    def test_unmerged_stage_branch_is_a_stop_not_a_dead_run(self):
        line, state = self.drive({"FAKE_MODE": "pr"})
        self.assertTrue(line.startswith("STATUS: stage-stopped"), line)
        self.assertIn("after pushing its stage branch", line)
        self.assertTrue(state["stages"][0]["pushed"])
        self.assertEqual(self.ledger_now()["S0"]["status"], "todo")

    def test_an_old_stage_branch_does_not_count_as_a_push(self):
        self.git("branch", "plan-demo-s0")
        line, state = self.drive({"FAKE_MODE": "silent"})
        self.assertTrue(line.startswith("STATUS: stage-dead"), line)
        self.assertFalse(state["stages"][0]["pushed"])

    def test_env_scrub_is_named_in_the_mismatch(self):
        line, _ = self.drive({"FAKE_MODE": "no-auto", "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "1"})
        self.assertIn("CLAUDE_CODE_SUBPROCESS_ENV_SCRUB is set", line)

    def test_auto_mode_unavailable_stops_before_work(self):
        line, state = self.drive({"FAKE_MODE": "no-auto"})
        self.assertTrue(line.startswith("STATUS: launch-mismatch"), line)
        self.assertIn("auto mode is unavailable", line)
        self.assertEqual(self.ledger_now()["S0"]["status"], "todo")
        self.assertEqual(state["stages"][0]["outcome"], "launch-mismatch")

    def test_idle_session_is_stopped_and_reported_dead(self):
        line, state = self.drive({"FAKE_MODE": "idle", "CLAUDE_STAGE_IDLE_MINUTES": "0.03"})
        self.assertTrue(line.startswith("STATUS: stage-dead"), line)
        self.assertIn("idle threshold", line)
        self.assertEqual(state["stages"][0]["killed"], "idle")

    def test_driver_never_writes_the_ledger_on_a_dead_run(self):
        before = (self.repo / ".plan" / "LEDGER.md").read_bytes()
        self.drive({"FAKE_MODE": "idle", "CLAUDE_STAGE_IDLE_MINUTES": "0.03"})
        self.assertEqual((self.repo / ".plan" / "LEDGER.md").read_bytes(), before)
        self.assertFalse((self.repo / ".plan" / "BLOCKED.md").exists())

    def test_resume_runs_the_named_stage_first(self):
        ledger = self.repo / ".plan" / "LEDGER.md"
        ledger.write_text(LEDGER.format(S0="doing", S1="todo", S2="todo", SF="todo"), encoding="utf-8")
        line, state = self.drive(resume="S0")
        self.assertEqual(state["stages"][0]["id"], "S0")
        self.assertEqual(state["stages"][0]["outcome"], "done")

    def test_protected_branch_is_refused(self):
        self.git("branch", "-m", "main")
        line, _ = self.drive()
        self.assertTrue(line.startswith("STATUS: protected-branch"), line)

    def test_bad_setting(self):
        line, _ = self.drive({"CLAUDE_STAGE_PERMISSION_MODE": "bypassPermissions"})
        self.assertTrue(line.startswith("STATUS: bad-setting"), line)

    def test_state_lives_in_the_git_dir(self):
        _, state = self.drive()
        path = Path(state["status_file"]).resolve()
        self.assertIn((self.repo / ".git").resolve(), path.parents)

    def test_a_live_driver_is_not_doubled(self):
        _, state = self.drive()
        path = Path(state["status_file"])
        state["state"] = "running"
        path.write_text(json.dumps({**state, "updated": prl.now()}), encoding="utf-8")
        line, _ = self.drive()
        self.assertTrue(line.startswith("STATUS: already-running"), line)

    # --- the usage limit ---

    def test_a_limit_hit_waits_for_the_reset_and_resumes_the_stage(self):
        clock = FakeClock()
        reset = clock.now + 3600
        line, state = self.drive({"FAKE_MODE": "limit", "FAKE_STAGE": "S0", "FAKE_RESET": str(int(reset))},
                                 clock=clock)
        self.assertTrue(line.startswith("STATUS: gated"), line)
        self.assertEqual(self.outcomes(state), [("S0", "stage-limited"), ("S0", "done"), ("S1", "done")])
        self.assertEqual(state["stages"][0]["limit"], {"resets_at": reset, "type": "five_hour"})
        self.assertEqual([w["why"] for w in state["waits"]], ["limit"])
        self.assertGreaterEqual(clock.now, reset + prl.RESET_MARGIN_SECONDS)
        self.assertTrue(all(s <= prl.HEARTBEAT_SECONDS for s in clock.slept))
        self.assertEqual(self.ledger_now()["S0"]["status"], "done")

    def test_a_reset_read_from_the_transcript(self):
        clock = FakeClock()
        reset = clock.now + 600
        line, state = self.drive({"FAKE_MODE": "limit-transcript", "FAKE_STAGE": "S0",
                                  "FAKE_RESET": str(int(reset))}, clock=clock)
        self.assertEqual(self.outcomes(state)[:2], [("S0", "stage-limited"), ("S0", "done")])
        self.assertEqual(state["stages"][0]["limit"]["resets_at"], reset)

    def test_a_limit_hit_with_no_reset_stops_for_a_person(self):
        line, state = self.drive({"FAKE_MODE": "limit-noreset", "FAKE_STAGE": "S0"}, clock=FakeClock())
        self.assertTrue(line.startswith("STATUS: stage-limited"), line)
        self.assertIn("no reset time could be read", line)
        self.assertIn("--resume S0", line)
        self.assertNotIn("waits", state)

    def test_a_reset_past_the_longest_wait_stops(self):
        clock = FakeClock()
        line, state = self.drive({"FAKE_MODE": "limit", "FAKE_STAGE": "S0",
                                  "FAKE_RESET": str(int(clock.now + 3 * 86400))}, clock=clock)
        self.assertTrue(line.startswith("STATUS: stage-limited"), line)
        self.assertIn("CLAUDE_STAGE_MAX_WAIT_HOURS", line)
        self.assertEqual(clock.slept, [])

    def test_a_second_hit_straight_after_the_reset_stops(self):
        clock = FakeClock()
        line, state = self.drive({"FAKE_MODE": "limit", "FAKE_STAGE": "S0", "FAKE_LIMIT_TIMES": "2",
                                  "FAKE_RESET": str(int(clock.now + 60))}, clock=clock)
        self.assertTrue(line.startswith("STATUS: stage-limited"), line)
        self.assertIn("again straight after", line)
        self.assertEqual(self.outcomes(state), [("S0", "stage-limited"), ("S0", "stage-limited")])

    def test_the_gate_holds_the_first_stage_on_the_seeded_share(self):
        clock = FakeClock()
        reset = clock.now + 1800
        line, state = self.drive(usage={"percent": 92.0, "resets_at": reset}, clock=clock)
        self.assertEqual(state["waits"][0]["why"], "gate")
        self.assertEqual(state["waits"][0]["id"], "S0")
        self.assertGreaterEqual(clock.now, reset + prl.RESET_MARGIN_SECONDS)
        self.assertEqual(self.outcomes(state), [("S0", "done"), ("S1", "done")])

    def test_a_low_seeded_share_holds_nothing(self):
        clock = FakeClock()
        line, state = self.drive(usage={"percent": 50.0, "resets_at": clock.now + 1800}, clock=clock)
        self.assertNotIn("waits", state)
        self.assertEqual(clock.slept, [])

    def test_the_gate_holds_on_the_largest_measured_jump(self):
        clock = FakeClock()
        reset = clock.now + 7200
        line, state = self.drive({"FAKE_WINDOWS": json.dumps({"S0": [0.40, 0.70]}),
                                  "FAKE_RESET": str(int(reset))}, clock=clock)
        self.assertEqual(state["stages"][0]["usage_window"]["jump"], 30.0)
        self.assertEqual(state["usage"]["max_jump"], 30.0)
        # 70% + 30 points would pass 95%: S1 waits for the reset, then runs
        self.assertEqual([(w["id"], w["why"]) for w in state["waits"]], [("S1", "gate")])
        self.assertEqual(self.outcomes(state), [("S0", "done"), ("S1", "done")])
        self.assertNotIn("usage gate skipped", line)

    def test_a_hold_past_the_longest_wait_stops_before_the_stage(self):
        clock = FakeClock()
        line, state = self.drive(usage={"percent": 92.0, "resets_at": clock.now + 10 * 3600}, clock=clock)
        self.assertTrue(line.startswith("STATUS: usage-held"), line)
        self.assertIn("S0 waits for the reset", line)
        self.assertEqual(state["stages"], [])
        self.assertEqual(clock.slept, [])

    def test_a_window_that_just_reset_is_not_held(self):
        clock = FakeClock()
        # S0 moves the share by 97 points in a window that has already reset by S1
        line, state = self.drive({"FAKE_WINDOWS": json.dumps({"S0": [0.0, 0.97]}),
                                  "FAKE_RESET": str(int(clock.now - 10))}, clock=clock)
        self.assertEqual(self.outcomes(state), [("S0", "done"), ("S1", "done")])
        self.assertNotIn("waits", state)
        self.assertIn("just reset", state["usage"]["gate"])

    def test_no_reading_says_once_the_gate_was_skipped(self):
        line, state = self.drive()
        self.assertEqual(line.count("usage gate skipped"), 1)
        self.assertIn("no 5-hour reading yet", state["usage"]["gate"])

    def test_next_reports_the_gate(self):
        out = Path(self.tmp.name).parent / f"next_{os.getpid()}_{id(self)}.json"
        self.addCleanup(lambda: out.unlink(missing_ok=True))
        with open(out, "w", encoding="utf-8") as fh, mock.patch.object(sys, "stdout", fh):
            prl.main(["next", "--repo", str(self.repo), "--usage-percent", "91",
                      "--usage-resets-at", str(int(prl.time.time()) + 3600)])
        gate = json.loads(out.read_text(encoding="utf-8"))["usage_gate"]
        self.assertTrue(gate["hold"])
        self.assertIn("S0 waits for the reset", gate["line"])

    # --- a dead or hung driver, and orphaned stage sessions ---

    def status_path(self):
        return prl.state_dir(self.repo, "plan-demo") / "status.json"

    def status_text(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            prl.main(["status", "--repo", str(self.repo)])
        return out.getvalue()

    def sleeper(self):
        """A live process standing in for a stage session an earlier driver left."""
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        return proc

    def dead_pid(self):
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        return proc.pid

    def recorded(self, pid, state="running", minutes_ago=10):
        stamp = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        log = str(self.status_path().parent / "S0.jsonl")
        data = {"state": state, "plan_branch": "plan-demo", "started": "2026-11-25T08:00:00Z",
                "updated": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), "stages": [],
                "current": {"id": "S0", "model": "opus", "effort": "high", "gate": "auto",
                            "started": "2026-11-25T08:01:00Z", "log": log, "pid": pid}}
        prl.write_json(self.status_path(), data)
        return data

    def test_each_stage_session_records_its_process_id(self):
        _, state = self.drive()
        self.assertTrue(all(isinstance(s.get("pid"), int) for s in state["stages"]), state["stages"])

    def test_status_reports_a_stale_heartbeat_as_gone(self):
        data = self.recorded(self.dead_pid())
        text = self.status_text()
        self.assertTrue(text.startswith("Driver gone"), text)
        self.assertIn(data["updated"], text)
        self.assertIn("S0: was running", text)
        self.assertIn("no longer running", text)

    def test_status_reads_a_fresh_heartbeat_as_running(self):
        self.recorded(self.sleeper().pid, minutes_ago=0)
        text = self.status_text()
        self.assertTrue(text.startswith("Driver running"), text)
        self.assertIn("still running", text)

    def test_a_live_recorded_session_refuses_a_second_start(self):
        proc = self.sleeper()
        self.recorded(proc.pid)
        before = self.status_path().read_bytes()
        for resume in (None, "S0"):
            line, _ = self.drive(resume=resume)
            self.assertTrue(line.startswith("STATUS: stage-session-alive"), line)
            self.assertIn(f"S0's session from an earlier driver (process {proc.pid})", line)
            self.assertIn("S0.jsonl", line)
        self.assertEqual(self.status_path().read_bytes(), before)
        self.assertFalse((self.status_path().parent / "S0.jsonl").exists())
        self.assertEqual(self.ledger_now()["S0"]["status"], "todo")
        proc.kill()
        proc.wait()
        line, _ = self.drive()
        self.assertTrue(line.startswith("STATUS: gated"), line)

    def recorded_side_by_side(self, pids, minutes_ago=10):
        stamp = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        records = [{"id": sid, "model": "sonnet", "effort": "low", "gate": "auto",
                    "started": "2026-11-25T08:01:00Z", "pid": pid,
                    "log": str(self.status_path().parent / f"{sid}.jsonl")}
                   for sid, pid in zip(("S1", "S2"), pids)]
        prl.write_json(self.status_path(), {
            "state": "running", "plan_branch": "plan-demo", "started": "2026-11-25T08:00:00Z",
            "updated": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), "stages": [], "in_flight": records})

    def test_status_lists_every_stage_in_flight(self):
        self.recorded_side_by_side([self.sleeper().pid, self.dead_pid()], minutes_ago=0)
        text = self.status_text()
        self.assertTrue(text.startswith("Driver running"), text)
        self.assertIn("S1: running since", text)
        self.assertIn("S2: running since", text)
        self.assertIn("S1's session, process", text)
        self.assertIn("still running", text)
        self.assertIn("no longer running", text)

    def test_every_live_recorded_session_is_named(self):
        first, second = self.sleeper(), self.sleeper()
        self.recorded_side_by_side([first.pid, second.pid])
        line, _ = self.drive()
        self.assertTrue(line.startswith("STATUS: stage-session-alive"), line)
        self.assertIn(f"S1's session from an earlier driver (process {first.pid})", line)
        self.assertIn(f"S2's session from an earlier driver (process {second.pid})", line)
        self.assertIn("are still running", line)

    def test_git_timeout_is_a_named_status(self):
        real = subprocess.run

        def run(cmd, *args, **kwargs):
            if "fetch" in cmd:
                raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))
            return real(cmd, *args, **kwargs)

        with mock.patch.object(prl.subprocess, "run", side_effect=run):
            line, state = self.drive()
        self.assertTrue(line.startswith("STATUS: git-timeout"), line)
        self.assertIn("`git fetch --quiet origin plan-demo` gave no answer", line)
        self.assertIn("while fetching origin/plan-demo", line)
        self.assertEqual((state["state"], state["status"]), ("exited", "git-timeout"))

    def watched(self, env=None, block_fetch=False):
        """Run a driver with a short stale limit in a thread; return what the
        watchdog emitted and whether it asked the process to exit."""
        release = threading.Event()
        self.addCleanup(release.set)
        emitted, exited = [], threading.Event()
        env = {"FAKE_MODE": "done", "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "", **(env or {})}
        refresh = prl.PlanSource.refresh
        patches = [mock.patch.dict(os.environ, env)]
        if block_fetch:  # a fetch from a remote that never answers
            patches.append(mock.patch.object(prl.PlanSource, "refresh",
                                             lambda source: release.wait(30) or refresh(source)))
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        driver = prl.Driver(self.repo, dict(os.environ),
                            launcher_argv=[sys.executable, str(self.fake)], grace_seconds=0)
        driver.stale, driver.watch_every = 1.0, 0.05
        driver.emit = emitted.append
        driver.exit = lambda code: exited.set()
        result = []
        runner = threading.Thread(target=lambda: result.append(driver.run()), daemon=True)
        runner.start()
        self.assertTrue(exited.wait(20), "the watchdog never fired")
        release.set()
        runner.join(30)
        return emitted, prl.read_json(driver.status_path), result

    def test_watchdog_reports_a_stalled_main_loop(self):
        emitted, state, result = self.watched(block_fetch=True)
        self.assertEqual(len(emitted), 1, emitted)
        self.assertTrue(emitted[0].startswith("STATUS: driver-hung"), emitted[0])
        self.assertIn("while fetching origin/plan-demo", emitted[0])
        self.assertEqual((state["state"], state["status"], state["line"]),
                         ("exited", "driver-hung", emitted[0]))
        self.assertEqual(result, emitted)  # the main loop stops at its next step, writing nothing
        self.assertEqual(self.ledger_now()["S0"]["status"], "todo")

    def test_watchdog_stops_the_stage_session_in_flight(self):
        # The fake goes quiet for 60 s and the loop beats once a minute: past a 1 s limit.
        emitted, state, _ = self.watched({"FAKE_MODE": "idle"})
        self.assertIn("while running S0's session", emitted[0])
        self.assertIn("stopped S0's session (process", emitted[0])
        self.assertFalse(prl.pid_alive(state["in_flight"][0]["pid"]))


class ParallelLoop(LoopBase):
    """The driver keeping several stage sessions in flight, on WIDE_PLAN."""
    plan = WIDE_PLAN
    ledger = wide_ledger()

    def spans(self):
        """Each fake session's (stage, start, end), in start order."""
        out = []
        for path in self.trace_file.parent.glob("trace-*"):
            marks = dict(line.split() for line in path.read_text().splitlines())
            out.append((path.name.split("-")[1], float(marks["start"]), float(marks.get("end", "inf"))))
        return sorted(out, key=lambda s: s[1])

    def most_at_once(self):
        events = sorted([(s, 1) for _, s, _ in self.spans()] + [(e, -1) for _, _, e in self.spans()],
                        key=lambda x: (x[0], x[1]))
        most = now = 0
        for _, d in events:
            now += d
            most = max(most, now)
        return most

    def span(self, sid, nth=0):
        return [s for s in self.spans() if s[0] == sid][nth]

    def test_two_start_together_and_a_third_only_after_one_ends(self):
        line, state = self.drive({"FAKE_AWAIT": json.dumps({"S1": "S2"}), "FAKE_SLEEP": json.dumps({"S2": 3})})
        self.assertTrue(line.startswith("STATUS: gated"), line)
        self.assertIn("S6 (gate live), S7 (gate live)", line)
        self.assertEqual(sorted(sid for sid, out in self.outcomes(state)),
                         ["S1", "S2", "S3", "S4", "S5"])
        self.assertTrue(all(out == "done" for _, out in self.outcomes(state)))
        s1, s2, s3 = self.span("S1"), self.span("S2"), self.span("S3")
        self.assertLess(s2[1], s1[2], "S1 and S2 did not run side by side")
        self.assertGreaterEqual(s3[1], s1[2], "S3 started before a stage ended, with nothing measured")
        self.assertEqual(self.most_at_once(), prl.START_AT_ONCE)
        self.assertFalse({"S6", "S7"} & {s[0] for s in self.spans()}, "a live stage was started")

    def test_a_stage_never_starts_beside_the_one_it_depends_on(self):
        self.drive({"FAKE_SLEEP": json.dumps({"S1": 2, "S2": 2})})
        self.assertGreaterEqual(self.span("S5")[1], self.span("S1")[2])

    def test_a_measured_jump_lets_more_than_the_starting_count_run(self):
        reset = int(prl.time.time()) + 3600
        windows = {sid: [0.10, 0.15] for sid in ("S1", "S2", "S3", "S4", "S5")}
        line, state = self.drive({"FAKE_WINDOWS": json.dumps(windows), "FAKE_RESET": str(reset),
                                  "FAKE_AWAIT": json.dumps({"S1": "S2", "S2": "S4", "S3": "S4"})})
        self.assertTrue(line.startswith("STATUS: gated"), line)
        self.assertGreaterEqual(self.span("S3")[1], self.span("S1")[2])
        self.assertGreater(self.most_at_once(), prl.START_AT_ONCE)
        self.assertEqual(state["usage"]["max_jump"], 5.0)
        self.assertNotIn("waits", state)

    def test_short_usage_starts_nothing_new_until_the_reset(self):
        clock = FakeClock()
        reset = clock.now + 3600
        windows = {"S1": [0.50, 0.80], "S2": [0.50, 0.80]}
        line, state = self.drive({"FAKE_WINDOWS": json.dumps(windows), "FAKE_RESET": str(int(reset)),
                                  "FAKE_SLEEP": json.dumps({"S1": 1, "S2": 4})}, clock=clock)
        self.assertTrue(line.startswith("STATUS: gated"), line)
        # 80% + 30 points for S2 in flight and for S3 passes 95%: S3 waits for S2, then for the reset
        self.assertEqual([(w["id"], w["why"]) for w in state["waits"]], [("S3", "gate")])
        self.assertGreaterEqual(self.span("S3")[1], self.span("S2")[2])
        self.assertGreaterEqual(clock.now, reset + prl.RESET_MARGIN_SECONDS)
        self.assertEqual(len(state["stages"]), 5)

    def test_a_stop_lets_the_stages_in_flight_finish_and_starts_nothing(self):
        line, state = self.drive({"FAKE_MODES": json.dumps({"S1": "block"}), "FAKE_AWAIT": json.dumps({"S1": "S2"}),
                                  "FAKE_SLEEP": json.dumps({"S2": 3})})
        self.assertTrue(line.startswith("STATUS: stage-blocked · S1 is blocked"), line)
        self.assertEqual(sorted(self.outcomes(state)), [("S1", "stage-blocked"), ("S2", "done")])
        self.assertEqual({s[0] for s in self.spans()}, {"S1", "S2"})
        self.assertEqual(state["stage"], "S1")
        self.assertEqual(state["in_flight"], [])

    def test_every_stop_is_named_on_the_one_line(self):
        line, state = self.drive({"FAKE_MODES": json.dumps({"S1": "block", "S2": "stop"}),
                                  "FAKE_AWAIT": json.dumps({"S1": "S2"}), "FAKE_SLEEP": json.dumps({"S2": 2})})
        self.assertTrue(line.startswith("STATUS: stage-blocked · S1 is blocked"), line)
        self.assertIn(" · also stage-stopped: S2 stopped short of `done`", line)
        self.assertEqual([s["status"] for s in state["stops"]], ["stage-blocked", "stage-stopped"])

    def test_a_limit_hit_beside_a_running_stage_waits_for_it_then_the_reset(self):
        clock = FakeClock()
        reset = clock.now + 3600
        line, state = self.drive({"FAKE_MODES": json.dumps({"S1": "limit"}), "FAKE_RESET": str(int(reset)),
                                  "FAKE_AWAIT": json.dumps({"S1": "S2"}), "FAKE_SLEEP": json.dumps({"S2": 3})}, clock=clock)
        self.assertTrue(line.startswith("STATUS: gated"), line)
        self.assertEqual([(w["id"], w["why"]) for w in state["waits"]], [("S1", "limit")])
        self.assertEqual(self.outcomes(state)[:2], [("S1", "stage-limited"), ("S2", "done")])
        self.assertIn(("S1", "done"), self.outcomes(state))
        self.assertGreaterEqual(self.span("S3")[1], self.span("S2")[2], "S3 started while the limit was out")
        self.assertGreaterEqual(clock.now, reset + prl.RESET_MARGIN_SECONDS)

    def test_a_git_timeout_lets_the_stages_in_flight_end_unread(self):
        calls, real = [], prl.PlanSource.refresh

        def refresh(source):
            # Fetches: before S1, before S2, before S3 (held: two in flight), then
            # the one reading S1's result while S2 still runs, which never answers.
            calls.append(1)
            if len(calls) == 4:
                raise prl.GitTimeout("`git fetch --quiet origin plan-demo` gave no answer in 120 s")
            return real(source)

        with mock.patch.object(prl.PlanSource, "refresh", refresh):
            line, state = self.drive({"FAKE_AWAIT": json.dumps({"S1": "S2"}),
                                      "FAKE_SLEEP": json.dumps({"S1": 3, "S2": 8})})
        self.assertTrue(line.startswith("STATUS: git-timeout"), line)
        self.assertIn("S2 ran on to its end unread", line)
        self.assertEqual(sorted(self.outcomes(state)), [("S1", "unread"), ("S2", "unread")])
        self.assertEqual(state["in_flight"], [])
        self.assertEqual({s[0] for s in self.spans()}, {"S1", "S2"})

    def test_resume_takes_several_stages(self):
        (self.repo / ".plan" / "LEDGER.md").write_text(wide_ledger(S1="doing", S2="doing"), encoding="utf-8")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-am", "doing")
        line, state = self.drive(resume="S1,S2", env={"FAKE_AWAIT": json.dumps({"S1": "S2"})})
        self.assertEqual([s[0] for s in self.spans()[:2]], ["S1", "S2"])
        self.assertLess(self.span("S2")[1], self.span("S1")[2])
        self.assertIn(("S1", "done"), self.outcomes(state))
        self.assertIn(("S2", "done"), self.outcomes(state))

    def test_starts_are_staggered(self):
        clock = FakeClock()
        line, state = self.drive({"FAKE_AWAIT": json.dumps({"S1": "S2"})}, clock=clock, stagger=60)
        self.assertIn(60, clock.slept)
        self.assertLess(self.span("S2")[1], self.span("S1")[2])

    def test_next_names_the_stages_that_start_together(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            prl.main(["next", "--repo", str(self.repo)])
        data = json.loads(out.getvalue())
        self.assertEqual([s["id"] for s in data["runnable"]], ["S1", "S2", "S3", "S4"])
        self.assertEqual((data["runnable"][2]["model"], data["runnable"][2]["gate"]), ("sonnet", "local"))
        self.assertEqual(data["start_together"], ["S1", "S2"])
        self.assertEqual(data["stage"]["id"], "S1")
        with contextlib.redirect_stdout(out := io.StringIO()):
            prl.main(["next", "--repo", str(self.repo), "--usage-percent", "92",
                      "--usage-resets-at", str(int(prl.time.time()) + 3600)])
        self.assertEqual(json.loads(out.getvalue())["start_together"], [])


if __name__ == "__main__":
    unittest.main()
