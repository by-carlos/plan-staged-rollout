#!/usr/bin/env python3
"""Verify a completed staged rollout from the outside.

Pass/fail for an "on the run" proof-of-concept run is a command result, not a
transcript to read. This script asserts, against a clone of the repository the
plan ran in:

  1. every stage branch exists, and its work reached the plan branch;
  2. every stage's pull request is closed as merged;
  3. `.plan/LEDGER.md` has every row settled (`done` or `skipped`) — nothing
     left at `doing`, `todo` or `blocked`;
  4. the working edits each stage claimed are actually on the plan branch;
  5. nothing was merged into the default branch.

Stdlib only, Python 3.11+. Reads every repository file through `git show
<ref>:<path>`, so it does not care which branch is checked out, and prefers
`origin/<branch>` over a local ref so it judges what was actually pushed.

Usage:

    python3 verify_run.py [--repo PATH] [--manifest PATH] [--pr-states PATH]

The manifest (default `.plan/verify-manifest.json` on the plan branch) names
the branches and, per stage, the paths and content the stage claimed. See this
directory's README for its shape.

Pull-request state comes from `--pr-states` (default `.plan/pr-states.json`),
a file the final stage writes from the GitHub MCP server — there is no `gh` in
a routine run, and this script makes no network call of its own.

Exit status is 0 only when every check passes.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

SETTLED = {"done", "skipped"}


class GitError(RuntimeError):
    pass


def git(repo, *args, check=True):
    proc = subprocess.run(
        ["git", "--no-pager", *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc


def rev_exists(repo, ref):
    return git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False).returncode == 0


def resolve_branch(repo, name):
    """Prefer the pushed ref; fall back to a local one. None if neither exists."""
    for ref in (f"refs/remotes/origin/{name}", f"refs/heads/{name}"):
        if rev_exists(repo, ref):
            return ref
    return None


def show(repo, ref, path):
    proc = git(repo, "show", f"{ref}:{path}", check=False)
    return proc.stdout if proc.returncode == 0 else None


def path_exists(repo, ref, path):
    return git(repo, "cat-file", "-e", f"{ref}:{path}", check=False).returncode == 0


def is_ancestor(repo, maybe_ancestor, ref):
    return git(repo, "merge-base", "--is-ancestor", maybe_ancestor, ref, check=False).returncode == 0


def changed_paths(repo, base, ref):
    out = git(repo, "diff", "--name-only", f"{base}...{ref}").stdout
    return [line for line in out.splitlines() if line.strip()]


class Report:
    """Collects check results and prints them as they are decided."""

    def __init__(self):
        self.failures = 0
        self.checks = 0

    def record(self, ok, label, detail=""):
        self.checks += 1
        if not ok:
            self.failures += 1
        mark = "PASS" if ok else "FAIL"
        line = f"[{mark}] {label}"
        # `detail` explains a failure, so it is noise on a passing check.
        if detail and not ok:
            line += f"\n         {detail}"
        print(line)
        return ok

    def section(self, title):
        print(f"\n--- {title} ---")


def parse_ledger(text):
    """Return [(stage_label, status)] from the ledger's status table.

    The table is the contract (`| Stage | Status | Verified | Date | Result |`),
    so rows are read positionally after the header and its separator.
    """
    rows = []
    seen_header = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            if seen_header and rows:
                break
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not seen_header:
            if cells and cells[0].lower() == "stage":
                seen_header = True
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if len(cells) >= 2:
            rows.append((cells[0], cells[1].strip("`").lower()))
    return rows


def check_ledger(report, repo, plan_ref, stages):
    report.section("Ledger")
    text = show(repo, plan_ref, ".plan/LEDGER.md")
    if not report.record(text is not None, ".plan/LEDGER.md exists on the plan branch"):
        return
    rows = parse_ledger(text)
    report.record(bool(rows), "the ledger status table has rows", f"parsed {len(rows)} row(s)")
    for label, status in rows:
        report.record(
            status in SETTLED,
            f"ledger row {label!r} is settled",
            f"status is {status!r}, expected one of {sorted(SETTLED)}",
        )
    expected = {s["id"] for s in stages}
    present = {label.split()[0] for label, _ in rows if label.split()}
    missing = sorted(expected - present)
    report.record(not missing, "every manifest stage has a ledger row", f"missing: {', '.join(missing)}")


def check_stage(report, repo, stage, plan_ref, pr_states):
    sid = stage["id"]
    report.section(f"Stage {sid} — {stage.get('title', '')}".rstrip(" —"))

    branch_ref = resolve_branch(repo, stage["branch"])
    if not report.record(
        branch_ref is not None,
        f"{sid}: stage branch {stage['branch']!r} exists",
        "neither origin/ nor a local ref resolves; a deleted branch also fails here",
    ):
        branch_ref = None

    pr = pr_states.get(sid)
    if report.record(pr is not None, f"{sid}: pull-request state was captured", f"no entry for {sid!r} in the PR-state file"):
        merged = bool(pr.get("merged"))
        closed = str(pr.get("state", "")).lower() == "closed"
        report.record(
            merged and closed,
            f"{sid}: PR #{pr.get('number', '?')} is closed as merged",
            f"state={pr.get('state')!r} merged={pr.get('merged')!r}",
        )
        base = pr.get("base")
        report.record(
            base == stage["plan_branch"],
            f"{sid}: PR targeted the plan branch, not elsewhere",
            f"base={base!r}, expected {stage['plan_branch']!r}",
        )

    # Work reached the plan branch. A squash merge leaves the stage tip
    # unreachable from the plan branch, so ancestry is sufficient but not
    # necessary: fall back to asserting the stage's changed paths are present.
    if branch_ref:
        if is_ancestor(repo, branch_ref, plan_ref):
            report.record(True, f"{sid}: stage branch is an ancestor of the plan branch")
        else:
            base = git(repo, "merge-base", plan_ref, branch_ref, check=False)
            if base.returncode != 0:
                report.record(False, f"{sid}: stage branch shares history with the plan branch", base.stderr.strip())
            else:
                paths = changed_paths(repo, base.stdout.strip(), branch_ref)
                missing = [
                    p for p in paths
                    if path_exists(repo, branch_ref, p) and not path_exists(repo, plan_ref, p)
                ]
                report.record(
                    bool(paths) and not missing,
                    f"{sid}: the branch's work is present on the plan branch (squash merge)",
                    f"{len(paths)} changed path(s); missing on plan branch: {', '.join(missing) or 'none'}"
                    if paths else "the stage branch changed nothing",
                )

    for path in stage.get("expect_paths", []):
        report.record(
            path_exists(repo, plan_ref, path),
            f"{sid}: {path} exists on the plan branch",
        )
    for path, needle in stage.get("expect_contains", []):
        body = show(repo, plan_ref, path)
        report.record(
            body is not None and needle in body,
            f"{sid}: {path} contains {needle!r} on the plan branch",
            "file is absent" if body is None else "file is present but the content is missing",
        )


def check_default_branch(report, repo, default_ref, plan_ref, stages, manifest):
    report.section("Default branch is untouched")
    report.record(
        not is_ancestor(repo, plan_ref, default_ref),
        f"the plan branch has NOT been merged into {manifest['default_branch']!r}",
        "the plan tip is reachable from the default branch — the final merge is the maintainer's, "
        "and must not have happened before verification",
    )
    for stage in stages:
        branch_ref = resolve_branch(repo, stage["branch"])
        if branch_ref:
            report.record(
                not is_ancestor(repo, branch_ref, default_ref),
                f"{stage['id']}: stage branch has NOT been merged into the default branch",
            )
    leaked = [
        p for stage in stages for p in stage.get("expect_paths", [])
        if path_exists(repo, default_ref, p)
    ]
    report.record(
        not leaked,
        "no stage's files appear on the default branch",
        f"present on {manifest['default_branch']}: {', '.join(sorted(set(leaked)))}",
    )


def load_json_arg(repo, plan_ref, explicit, default_path, what):
    if explicit:
        return json.loads(Path(explicit).read_text(encoding="utf-8"))
    local = Path(repo) / default_path
    if local.exists():
        return json.loads(local.read_text(encoding="utf-8"))
    body = show(repo, plan_ref, default_path) if plan_ref else None
    if body is None:
        raise SystemExit(
            f"error: no {what} found — looked for {default_path} in the working tree "
            f"and on the plan branch. Pass an explicit path."
        )
    return json.loads(body)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=".", help="path to a clone of the repository the plan ran in")
    parser.add_argument("--manifest", help="path to the verification manifest (default: .plan/verify-manifest.json)")
    parser.add_argument("--pr-states", help="path to the captured PR states (default: .plan/pr-states.json)")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        raise SystemExit(f"error: {repo} is not a git clone")

    manifest = load_json_arg(repo, None, args.manifest, ".plan/verify-manifest.json", "manifest")
    plan_branch = manifest["plan_branch"]
    default_branch = manifest["default_branch"]
    stages = manifest["stages"]
    for stage in stages:
        stage.setdefault("plan_branch", plan_branch)

    print(f"Verifying plan branch {plan_branch!r} against default branch {default_branch!r} in {repo}")

    plan_ref = resolve_branch(repo, plan_branch)
    default_ref = resolve_branch(repo, default_branch)
    if plan_ref is None:
        raise SystemExit(f"error: plan branch {plan_branch!r} not found (fetch first?)")
    if default_ref is None:
        raise SystemExit(f"error: default branch {default_branch!r} not found (fetch first?)")
    print(f"  plan branch    -> {plan_ref} ({git(repo, 'rev-parse', '--short', plan_ref).stdout.strip()})")
    print(f"  default branch -> {default_ref} ({git(repo, 'rev-parse', '--short', default_ref).stdout.strip()})")

    pr_states = load_json_arg(repo, plan_ref, args.pr_states, ".plan/pr-states.json", "PR-state file")

    report = Report()
    check_ledger(report, repo, plan_ref, stages)
    for stage in stages:
        check_stage(report, repo, stage, plan_ref, pr_states)
    check_default_branch(report, repo, default_ref, plan_ref, stages, manifest)

    print(f"\n{report.checks - report.failures}/{report.checks} checks passed.")
    if report.failures:
        print(f"VERIFICATION FAILED — {report.failures} check(s) failed.")
        return 1
    print("VERIFICATION PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
