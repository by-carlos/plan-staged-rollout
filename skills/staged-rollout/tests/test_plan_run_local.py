"""Scripted check for `scripts/plan_run_local.py`, the local stage driver.

Covers the readings the driver acts on -- the stage index, the ledger and
BLOCKED.md -- runnable-stage selection by gate and dependencies, the model
and effort flags, the settings, the opening-line check, the outcome of a
finished stage, and the driver loop end to end against a fake launcher in a
throwaway git clone, for each exit status a person acts on.

Run from the repo root:
    python -m unittest discover -s skills/staged-rollout/tests -v
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
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


class Flags(unittest.TestCase):
    def test_effort_mapping(self):
        self.assertEqual(prl.effort_flag("med"), "medium")
        self.assertEqual(prl.effort_flag("high"), "high")
        self.assertEqual(prl.effort_flag(""), "")
        with self.assertRaises(prl.PlanError):
            prl.effort_flag("extreme")

    def test_settings_defaults(self):
        conf = prl.settings({})
        self.assertEqual(conf, {"launcher": "claude", "mode": "auto",
                                "idle_seconds": 900.0, "budget": "", "scrub": False})
        self.assertTrue(prl.settings({"CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "1"})["scrub"])
        self.assertFalse(prl.settings({"CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "0"})["scrub"])

    def test_settings_refuse_bypass_and_bad_numbers(self):
        for env in ({"CLAUDE_STAGE_PERMISSION_MODE": "bypassPermissions"},
                    {"CLAUDE_STAGE_PERMISSION_MODE": "plan"},
                    {"CLAUDE_STAGE_IDLE_MINUTES": "0"},
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
        ]
        for args, want in cases:
            self.assertEqual(prl.outcome(*args), want, args)


FAKE = textwrap.dedent('''\
    """Stands in for `claude -p`: acts on .plan/ as FAKE_MODE says."""
    import json, os, re, sys, time
    args = sys.argv[1:]
    prompt = args[args.index("-p") + 1]
    stage = "SF" if prompt.split()[1] == "f" else "S" + prompt.split()[1]
    model = args[args.index("--model") + 1] if "--model" in args else "claude-default"
    mode = os.environ.get("FAKE_MODE", "done")
    reported = "default" if mode == "no-auto" else args[args.index("--permission-mode") + 1]
    print(json.dumps({"type": "system", "subtype": "init", "session_id": "fake-" + stage,
                      "permissionMode": reported, "model": "claude-" + model + "-5-5"}), flush=True)
    if mode == "idle":
        time.sleep(60)
    ledger = os.path.join(".plan", "LEDGER.md")
    text = open(ledger, encoding="utf-8").read()
    row = "done" if mode == "done" or stage != os.environ.get("FAKE_STAGE", stage) else "doing"
    if mode in ("done", "block", "stop"):
        text = re.sub(r"^(\\| " + stage + r" [^|]*\\| )\\w+", r"\\g<1>" + row, text, flags=re.M)
        open(ledger, "w", encoding="utf-8").write(text)
        if mode == "block" and row == "doing":
            open(os.path.join(".plan", "BLOCKED.md"), "w", encoding="utf-8").write(
                "# Blocked\\n\\n### " + stage + "\\n\\nThe staging host is unreachable.\\n")
    if mode == "pr":  # pushes its stage branch, then its merge is refused: the row never moves
        import subprocess
        subprocess.run(["git", "branch", "plan-demo-s" + stage[1:].lower()], check=True)
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                      "result": "stage " + stage + " " + mode, "session_id": "fake-" + stage}), flush=True)
''')


class DriverLoop(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / ".plan").mkdir()
        (self.repo / ".plan" / "PLAN.md").write_text(PLAN, encoding="utf-8")
        (self.repo / ".plan" / "LEDGER.md").write_text(
            LEDGER.format(S0="todo", S1="todo", S2="todo", SF="todo"), encoding="utf-8")
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

    def drive(self, env=None, resume=None):
        env = {"FAKE_MODE": "done", "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "", **(env or {})}
        with mock.patch.dict(os.environ, env):
            driver = prl.Driver(self.repo, dict(os.environ),
                                launcher_argv=[sys.executable, str(self.fake)], grace_seconds=0)
            line = driver.run(resume=resume)
        return line, prl.read_json(driver.status_path)

    def ledger_now(self):
        return prl.parse_ledger((self.repo / ".plan" / "LEDGER.md").read_text(encoding="utf-8"))

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


if __name__ == "__main__":
    unittest.main()
