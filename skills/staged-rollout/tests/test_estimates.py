"""Scripted check for `scripts/estimates.py` and `effortlog.py usage`.

Builds a throwaway `.plan/` and transcript, and asserts the arithmetic the
skill relies on: ranges summed and taken along the longest `depends` chain,
what is left once stages close, `Actuals:` lines read back into a report, each
streamed message counted once, and calibration staying silent on too few rows.

Run from the repo root:
    python -m unittest discover -s skills/staged-rollout/tests -v
"""

import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


est = load("estimates")
el = load("effortlog")

# S1 and S2 both hang off S0 and run in parallel; SF waits on both.
PLAN = """# Demo

## Stage index & dependencies

| Stage | File | Depends | mode | exec | model | effort | gate | estimate |
|---|---|---|---|---|---|---|---|---|
| S0 Keystone | `stage-0-keystone.md` | — | direct | inline | opus | high | auto | 1–2h |
| S1 Parser | `stage-1-parser.md` | S0 | direct | inline | sonnet | med | auto | 2-4h |
| S2 Writer | `stage-2-writer.md` | S0 | direct | inline | sonnet | low | auto | 0.5h |
| SF Plan review | `stage-f-review.md` | S1, S2 | direct | inline | sonnet | med | auto | — |

Plan flags: `merge: manual` · `plan-dir: delete`
"""

LEDGER = """# Demo — build ledger

## Status

| Stage | Status | Verified | Date | Result |
|---|---|---|---|---|
| S0 Keystone | done | yes | 2026-10-01 | landed |
| S1 Parser | doing | — | 2026-10-02 | half |
| S2 Writer | skipped | — | — | not needed |
| SF Plan review | todo | — | — | — |

## Notes

### S0 Keystone

Actuals: 2026-10-01T10:00:00Z → 2026-10-01T11:30:00Z · 90 min · tokens in=10 out=200 cache_read=3000 cache_write=400 · subagents=1

### S1 Parser

Actuals: 2026-10-02T09:00:00Z → 2026-10-02T09:30:00Z · 30 min · tokens in=1 out=20 cache_read=300 cache_write=40 · subagents=0
Actuals: 2026-10-02T13:00:00Z → 2026-10-02T14:00:00Z · 60 min · tokens in=2 out=30 cache_read=500 cache_write=60 · subagents=0

### SF Plan review
_(empty)_
"""


def run(module, *argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = module.main(list(argv))
    return code, buf.getvalue()


class PlanTotals(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "PLAN.md").write_text(PLAN, encoding="utf-8")
        (self.dir / "LEDGER.md").write_text(LEDGER, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_ranges(self):
        self.assertEqual(est.parse_range("1–2h"), (1.0, 2.0))
        self.assertEqual(est.parse_range("0.5-1h"), (0.5, 1.0))
        self.assertEqual(est.parse_range("2h"), (2.0, 2.0))
        self.assertIsNone(est.parse_range("—"))
        for bad in ("2-1h", "1-2", "about an hour"):
            with self.assertRaises(est.PlanError):
                est.parse_range(bad)

    def test_summed_and_elapsed(self):
        code, out = run(est, "plan", "--plan-dir", str(self.dir))
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["plan"]["summed"], [3.5, 6.5])
        # Longest chain is S0 -> S1 -> SF; S2 runs beside S1.
        self.assertEqual(data["plan"]["elapsed"], [3.0, 6.0])
        self.assertEqual(data["plan"]["unestimated"], ["SF"])
        self.assertIn("summed 3.5–6.5h · elapsed 3–6h", data["line"])
        # Done and skipped stages drop out of what is left.
        self.assertEqual(data["remaining"]["summed"], [2.0, 4.0])

    def test_missing_column_refused(self):
        (self.dir / "PLAN.md").write_text(PLAN.replace(" estimate |", " note |"), encoding="utf-8")
        code, _ = run(est, "plan", "--plan-dir", str(self.dir))
        self.assertEqual(code, 2)

    def test_report_reads_actuals(self):
        code, out = run(est, "report", "--plan-dir", str(self.dir))
        self.assertEqual(code, 0)
        self.assertIn("| S0 Keystone | done | 1–2h | 1.5h | 3410 | 200 | 1 |", out)
        # Two sessions on S1 are summed, not the last one kept.
        self.assertIn("| S1 Parser | doing | 2-4h | 1.5h | 903 | 50 | 2 |", out)
        self.assertIn("summed 3.0h over 2 measured stage(s)", out)
        self.assertIn("out 250", out)
        self.assertIn("**Not measured:** S2, SF", out)


class Usage(unittest.TestCase):
    def test_streamed_message_counted_once(self):
        usage = {"input_tokens": 1, "output_tokens": 50,
                 "cache_read_input_tokens": 100, "cache_creation_input_tokens": 10}
        rows = [
            {"type": "user", "timestamp": "2026-10-01T10:00:00Z"},
            {"type": "assistant", "timestamp": "2026-10-01T10:01:00Z",
             "message": {"id": "m1", "usage": usage}},
            {"type": "assistant", "timestamp": "2026-10-01T10:01:01Z",
             "message": {"id": "m1", "usage": usage}},
            {"type": "assistant", "timestamp": "2026-10-01T10:20:00Z",
             "message": {"id": "m2", "usage": usage}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            got = el.sum_usage(path)
        self.assertEqual(got["tokens"], {"in": 2, "out": 100, "cache_read": 200, "cache_write": 20})
        self.assertEqual(got["start"], "2026-10-01T10:00:00Z")
        self.assertEqual(got["finish"], "2026-10-01T10:20:00Z")

    def test_actuals_line_round_trips(self):
        line = el.actuals_line({
            "start": "2026-10-01T10:00:00Z", "finish": "2026-10-01T10:20:00Z",
            "elapsed_minutes": 20, "subagents": 2,
            "tokens": {"in": 2, "out": 100, "cache_read": 200, "cache_write": 20},
        })
        m = est.ACTUALS_RE.search(line)
        self.assertIsNotNone(m)
        self.assertEqual((m["min"], m["out"], m["cw"]), ("20", "100", "20"))


class Calibrate(unittest.TestCase):
    def write_log(self, rows):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".ndjson", delete=False, encoding="utf-8")
        tmp.write("\n".join(json.dumps(r) for r in rows))
        tmp.close()
        self.addCleanup(os.unlink, tmp.name)
        return tmp.name

    def test_too_few_rows_says_nothing(self):
        log = self.write_log([{"source": "stage-run", "estimate": "1-2h", "elapsed_minutes": 90}])
        _, out = run(est, "calibrate", "--log", log)
        self.assertIsNone(json.loads(out)["factor"])

    def test_median_ratio(self):
        rows = [
            {"source": "stage-run", "target": f"p/S{i}", "estimate": "1-3h",
             "elapsed_minutes": m, "outcome": "stage-done"}
            for i, m in enumerate((60, 120, 240))
        ]
        rows.append({"source": "work-issue", "target": "9", "estimate": "1-3h",
                     "elapsed_minutes": 999, "outcome": "merged"})
        rows.append({"source": "stage-run", "target": "p/S8", "estimate": None,
                     "elapsed_minutes": 999, "outcome": "stage-done"})
        # Unfinished: never counted, however long it ran.
        rows.append({"source": "stage-run", "target": "p/S9", "estimate": "1-3h",
                     "elapsed_minutes": 999, "outcome": "stage-doing"})
        _, out = run(est, "calibrate", "--log", self.write_log(rows))
        data = json.loads(out)
        self.assertEqual(data["rows"], 3)
        self.assertEqual(data["factor"], 1.0)

    def test_resumed_stage_summed(self):
        # Two sessions of one stage (60 + 60 min) against one 1-3h estimate.
        rows = [
            {"source": "stage-run", "target": "p/S0", "estimate": "1-3h",
             "elapsed_minutes": 60, "outcome": "stage-doing"},
            {"source": "stage-run", "target": "p/S0", "estimate": "1-3h",
             "elapsed_minutes": 60, "outcome": "stage-done"},
        ] + [
            {"source": "stage-run", "target": f"p/S{i}", "estimate": "1-3h",
             "elapsed_minutes": 120, "outcome": "stage-done"}
            for i in (1, 2)
        ]
        _, out = run(est, "calibrate", "--log", self.write_log(rows))
        data = json.loads(out)
        self.assertEqual((data["rows"], data["factor"]), (3, 1.0))

    def test_no_log(self):
        with mock.patch.dict(os.environ, {"CLAUDE_EFFORT_LOG": ""}):
            _, out = run(est, "calibrate")
        self.assertEqual(json.loads(out)["rows"], 0)


if __name__ == "__main__":
    unittest.main()
