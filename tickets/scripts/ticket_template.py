#!/usr/bin/env python3
"""Load, layer and validate ticket templates (references/template-schema.md).

Standard library only; Python 3.11 or later (tomllib).

    ticket_template.py validate <path|default> [--tracker github|jira]
    ticket_template.py resolve [--tracker github|jira] [--project-dir DIR]
                               [--config-dir DIR] [--template PATH]

`validate` reports every error at once and exits 1 when there are any.
`resolve` finds the configured template, layers it, applies the active
tracker's [per_tracker] overlay, validates the result and prints JSON:

    {"template": {...}, "tracker": "github", "source": "<path or default>",
     "chain": [...], "notice": null}

A configured template that is missing, unreadable or invalid never stops
`resolve`: it falls back to the built-in default and sets `notice` to one
line naming the path and the first error. Exit 2 only when the built-in
default itself is broken.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import tomllib

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = PLUGIN_ROOT / "templates" / "default.toml"
CONFIG_NAME = "plan-staged-rollout.toml"
TRACKERS = ("github", "jira")
MAX_CHAIN = 3

STR, INT, BOOL = "str", "int", "bool"


def _any_of(*kinds):
    return ("any", kinds)


# Schema spec. A dict is a table with fixed keys; ("map", spec) is a table
# with free keys whose values follow spec; ("list", spec) is an array; a
# ("enum", ...) tuple is a string from a closed set.
SECTION = {
    "title": STR, "required": BOOL, "guidance": STR,
    "no_identifiers": BOOL, "kind": ("enum", "ai_prompt", "acceptance"),
    "list_style": ("enum", "bullets", "numbered", "free"),
    "wrap": ("enum", "code"), "icon": STR,
}
CELL = _any_of(INT, STR)
MATRIX = {
    "rows": ("list", STR), "columns": ("list", STR),
    "cells": ("list", ("list", CELL)),
    "bump": {"when": STR, "cells": ("list", ("list", CELL))},
    "questions": ("list", STR),
}
FIELD = {
    "id": STR,
    "kind": ("enum", "number", "text", "select", "user", "date"),
    "values": ("map", STR), "default": STR,
    "confirm_values": ("list", STR), "ask_when": STR,
    "set_only_if": ("enum", "always", "investigated"), "guidance": STR,
    "repair": {"after_seconds": INT},
}
TABLES = {
    "body": {
        "sections": ("list", SECTION),
        "heading_level": INT,
        "list_style": ("enum", "bullets", "free"),
        "ai_prompt": {"requires": ("list", ("enum", "repo", "base_branch", "verification", "effort"))},
        "footer": {"text": STR, "provenance": STR, "timezone": STR},
    },
    "title": {
        "verb_first": BOOL, "prefix_one_of": ("list", STR),
        "keep_existing_tags": BOOL, "max_length": INT, "no_dates": BOOL,
    },
    "types": {"allowed": ("list", STR), "default": STR, "spike_when": STR},
    "labels": {"allowed": ("list", STR), "create": BOOL, "groups": ("map", ("list", STR)),
               "always": ("list", STR)},
    "priority": {"field": STR, "scale": ("list", STR), "default": STR, "rubric": ("map", STR)},
    "estimate": {
        "kind": ("enum", "points", "size", "none"), "field": STR,
        "scale": ("list", _any_of(INT, STR)), "ceiling": _any_of(INT, STR),
        "split_above": _any_of(INT, STR), "proposal_only": BOOL,
        "set_only_if": ("enum", "always", "investigated"),
        "comment": STR, "guide": STR, "matrix": MATRIX,
    },
    "fields": ("map", FIELD),
    "links": ("map", _any_of(STR, {"id": STR, "name": STR, "inward": STR, "outward": STR})),
    "intake": {"footer_keys": ("map", STR), "operational_checklist": ("list", STR)},
    "routing": {
        "owner": STR, "fallback": ("enum", "same-name-board", "stop", "none"),
        "repos": ("map", {"board": _any_of(INT, STR)}),
        "board_fields": ("map", STR),
    },
    "review": {"extra_checks": ("list", STR), "skip_when": ("list", STR), "max_questions": INT,
               "references": ("list", {"name": STR, "url": STR, "covers": STR, "points": ("list", STR)})},
    "work": {
        "branch": STR, "commit_style": STR, "merge_command": STR, "merge_ask_header": STR,
        "status": {"on_start": STR, "on_pr": STR},
        "attribution": {"commit_trailer": STR, "pr_footer": STR},
    },
}
TOP = {
    "schema": INT, "name": STR, "tracker": ("enum",) + TRACKERS,
    "extends": STR, "description": STR,
    **TABLES,
    "per_tracker": {t: TABLES for t in TRACKERS},
}


class TemplateError(Exception):
    """A template that cannot be used; `errors` lists every problem found."""

    def __init__(self, errors: list[str]):
        super().__init__(errors[0] if errors else "invalid template")
        self.errors = errors


# --------------------------------------------------------------- type check

def _type_ok(value, kind) -> bool:
    if kind == STR:
        return isinstance(value, str)
    if kind == INT:
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == BOOL:
        return isinstance(value, bool)
    return False


def _describe(spec) -> str:
    if isinstance(spec, str):
        return {"str": "a string", "int": "an integer", "bool": "true or false"}[spec]
    if isinstance(spec, dict):
        return "a table"
    tag = spec[0]
    if tag == "enum":
        return "one of " + ", ".join(repr(v) for v in spec[1:])
    if tag == "list":
        return "an array"
    if tag == "map":
        return "a table"
    if tag == "any":
        return " or ".join(_describe(k) for k in spec[1])
    return str(spec)


def check_shape(value, spec, path: str, errors: list[str]) -> None:
    """Unknown keys and wrong types, at every level."""
    if isinstance(spec, str):
        if not _type_ok(value, spec):
            errors.append(f"{path}: expected {_describe(spec)}, got {value!r}")
        return
    if isinstance(spec, dict):
        if not isinstance(value, dict):
            errors.append(f"{path}: expected a table")
            return
        for key, sub in value.items():
            if key not in spec:
                errors.append(f"{path}.{key}: unknown key" if path else f"{key}: unknown key")
                continue
            check_shape(sub, spec[key], f"{path}.{key}" if path else key, errors)
        return
    tag = spec[0]
    if tag == "enum":
        if value not in spec[1:]:
            errors.append(f"{path}: expected {_describe(spec)}, got {value!r}")
    elif tag == "list":
        if not isinstance(value, list):
            errors.append(f"{path}: expected an array")
            return
        for i, item in enumerate(value):
            check_shape(item, spec[1], f"{path}[{i}]", errors)
    elif tag == "map":
        if not isinstance(value, dict):
            errors.append(f"{path}: expected a table")
            return
        for key, sub in value.items():
            check_shape(sub, spec[1], f"{path}.{key}", errors)
    elif tag == "any":
        for kind in spec[1]:
            sub_errors: list[str] = []
            check_shape(value, kind, path, sub_errors)
            if not sub_errors:
                return
        errors.append(f"{path}: expected {_describe(spec)}, got {value!r}")


# ------------------------------------------------------------ cross checks

def _scale_index(scale: list, value) -> int | None:
    for i, item in enumerate(scale):
        if item == value and type(item) is type(value):
            return i
    return None


def _check_cell(cell, scale: list, path: str, errors: list[str]) -> None:
    if isinstance(cell, int) and not isinstance(cell, bool):
        if scale and _scale_index(scale, cell) is None:
            errors.append(f"{path}: {cell} is not in estimate.scale")
        return
    if cell in ("split", "-"):
        return
    if isinstance(cell, str) and cell.startswith("timebox:"):
        try:
            int(cell.split(":", 1)[1])
            return
        except ValueError:
            pass
    errors.append(f"{path}: cell must be a number, \"split\", \"timebox:<n>\" or \"-\", got {cell!r}")


def check_semantics(t: dict, errors: list[str], *, base: bool) -> None:
    """Rules that span keys. `base` is true for a template that names no
    tracker (only extended by others), which may omit `tracker`."""
    if t.get("schema") != 1:
        errors.append("schema: must be 1")
    if not t.get("name"):
        errors.append("name: required")
    if not base and "tracker" not in t:
        errors.append("tracker: required (github or jira)")

    fields = t.get("fields", {}) if isinstance(t.get("fields"), dict) else {}
    body = t.get("body", {}) if isinstance(t.get("body"), dict) else {}
    sections = body.get("sections", []) if isinstance(body.get("sections"), list) else []
    titles = [s.get("title") for s in sections if isinstance(s, dict)]
    for i, s in enumerate(sections):
        if isinstance(s, dict) and not s.get("title"):
            errors.append(f"body.sections[{i}].title: required")
    dupes = sorted({x for x in titles if x and titles.count(x) > 1})
    for d in dupes:
        errors.append(f"body.sections: title {d!r} appears more than once")
    if not sections and not base:
        errors.append("body.sections: at least one section is required")
    ai = [s for s in sections if isinstance(s, dict) and s.get("kind") == "ai_prompt"]
    if len(ai) > 1:
        errors.append("body.sections: more than one section has kind = \"ai_prompt\"")
    level = body.get("heading_level")
    if isinstance(level, int) and not 1 <= level <= 6:
        errors.append("body.heading_level: must be 1-6")

    types = t.get("types", {})
    if (isinstance(types, dict) and types.get("default") and types.get("allowed")
            and types["default"] not in types["allowed"]):
        errors.append(f"types.default: {types['default']!r} is not in types.allowed")

    labels = t.get("labels", {})
    if isinstance(labels, dict) and isinstance(labels.get("groups"), dict) and labels.get("allowed"):
        for group, members in labels["groups"].items():
            for m in members if isinstance(members, list) else []:
                if m not in labels["allowed"]:
                    errors.append(f"labels.groups.{group}: {m!r} is not in labels.allowed")

    pr = t.get("priority", {})
    if isinstance(pr, dict):
        scale = pr.get("scale") if isinstance(pr.get("scale"), list) else []
        if "scale" in pr and not scale:
            errors.append("priority.scale: must not be empty")
        if pr.get("default") is not None and scale and pr["default"] not in scale:
            errors.append(f"priority.default: {pr['default']!r} is not in priority.scale")
        for key in (pr.get("rubric") or {}) if isinstance(pr.get("rubric"), dict) else {}:
            if scale and key not in scale:
                errors.append(f"priority.rubric.{key}: not in priority.scale")
        f = pr.get("field")
        if f and f != "priority" and f not in fields:
            errors.append(f"priority.field: {f!r} is neither \"priority\" nor a [fields] key")

    est = t.get("estimate", {})
    if isinstance(est, dict) and est.get("kind") != "none":
        scale = est.get("scale") if isinstance(est.get("scale"), list) else []
        for key in ("ceiling", "split_above"):
            if key in est and scale and _scale_index(scale, est[key]) is None:
                errors.append(f"estimate.{key}: {est[key]!r} is not in estimate.scale")
        if est.get("kind") == "size" and any(not isinstance(x, str) for x in scale):
            errors.append("estimate.scale: kind = \"size\" needs string labels")
        if est.get("kind") == "points" and any(isinstance(x, bool) or not isinstance(x, int) for x in scale):
            errors.append("estimate.scale: kind = \"points\" needs integers")
        f = est.get("field")
        if f and f != "size" and f not in fields:
            errors.append(f"estimate.field: {f!r} is neither \"size\" nor a [fields] key")
        m = est.get("matrix")
        if isinstance(m, dict):
            if est.get("kind") == "size":
                errors.append("estimate.matrix: only kind = \"points\" takes a matrix")
            rows = m.get("rows") if isinstance(m.get("rows"), list) else []
            cols = m.get("columns") if isinstance(m.get("columns"), list) else []
            grids = [("estimate.matrix.cells", m.get("cells"))]
            if isinstance(m.get("bump"), dict):
                grids.append(("estimate.matrix.bump.cells", m["bump"].get("cells")))
                if not m["bump"].get("when"):
                    errors.append("estimate.matrix.bump.when: required")
            for path, grid in grids:
                if not isinstance(grid, list):
                    errors.append(f"{path}: required")
                    continue
                if len(grid) != len(rows):
                    errors.append(f"{path}: {len(grid)} rows, but matrix.rows has {len(rows)}")
                for r, row in enumerate(grid):
                    if not isinstance(row, list):
                        continue
                    if len(row) != len(cols):
                        errors.append(f"{path}[{r}]: {len(row)} cells, but matrix.columns has {len(cols)}")
                    for c, cell in enumerate(row):
                        _check_cell(cell, scale, f"{path}[{r}][{c}]", errors)

    for key, fdef in fields.items():
        if not isinstance(fdef, dict):
            continue
        p = f"fields.{key}"
        if "id" not in fdef:
            errors.append(f"{p}.id: required")
        if "kind" not in fdef:
            errors.append(f"{p}.kind: required")
        values = fdef.get("values") if isinstance(fdef.get("values"), dict) else None
        if fdef.get("kind") == "select" and not values:
            errors.append(f"{p}.values: required for kind = \"select\"")
        confirm = fdef.get("confirm_values") or []
        default = fdef.get("default", "unset")
        if values is not None:
            for v in confirm:
                if v not in values:
                    errors.append(f"{p}.confirm_values: {v!r} is not in {p}.values")
            if default != "unset" and default not in values:
                errors.append(f"{p}.default: {default!r} is neither \"unset\" nor in {p}.values")
        if default in confirm:
            errors.append(f"{p}.default: {default!r} is a guarded value (confirm_values) and can never be a default")
        if confirm and not fdef.get("ask_when"):
            errors.append(f"{p}.ask_when: required when confirm_values is set (it is the reason the skill gives when it asks)")
        if confirm and "set_only_if" in fdef:
            errors.append(f"{p}.set_only_if: a guarded field (confirm_values) is answered by the user, "
                          "never proposed by the session; drop one of the two")

    links = t.get("links", {})
    if isinstance(links, dict):
        parent = links.get("parent")
        if parent is not None and parent != "native" and parent not in fields:
            errors.append(f"links.parent: {parent!r} is neither \"native\" nor a [fields] key")
        for kind, ldef in links.items():
            if kind != "parent" and isinstance(ldef, str):
                errors.append(f"links.{kind}: expected a table with an id")
            if isinstance(ldef, dict) and "id" not in ldef:
                errors.append(f"links.{kind}.id: required")

    routing = t.get("routing", {})
    if isinstance(routing, dict):
        if routing and t.get("tracker") == "jira":
            errors.append("routing: GitHub only, but tracker is \"jira\"")
        for name, target in (routing.get("board_fields") or {}).items():
            if target not in ("priority", "size") and target not in fields:
                errors.append(f"routing.board_fields.{name}: {target!r} is neither priority, size nor a [fields] key")

    review = t.get("review", {})
    if (isinstance(review, dict) and isinstance(review.get("max_questions"), int)
            and review["max_questions"] < 1):
        errors.append("review.max_questions: must be at least 1")
    for i, ref in enumerate(review.get("references") or [] if isinstance(review, dict) else []):
        if isinstance(ref, dict):
            for key in ("name", "url", "covers"):
                if not ref.get(key):
                    errors.append(f"review.references[{i}].{key}: required")


# ----------------------------------------------------------------- loading

def deep_merge(base: dict, over: dict) -> dict:
    """Tables merge key by key; arrays and scalars replace. Tables whose keys
    are tied to a list (REPLACE_WHOLE) replace as a whole, so an overlay that
    changes a scale never inherits rubric entries for the old one."""
    return _merge(base, over, ())


REPLACE_WHOLE = {("priority", "rubric"), ("estimate", "matrix"), ("fields", "*", "values")}


def _replaces_whole(path: tuple[str, ...]) -> bool:
    if len(path) >= 2 and path[0] == "per_tracker":
        path = path[2:]
    return any(
        len(rule) == len(path) and all(r in ("*", p) for r, p in zip(rule, path, strict=True))
        for rule in REPLACE_WHOLE
    )


def _merge(base: dict, over: dict, path: tuple[str, ...]) -> dict:
    out = copy.deepcopy(base)
    for key, value in over.items():
        sub = (*path, key)
        if isinstance(value, dict) and isinstance(out.get(key), dict) and not _replaces_whole(sub):
            out[key] = _merge(out[key], value, sub)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _read_toml(path: Path) -> dict:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError:
        raise TemplateError([f"{path}: file not found"])
    except PermissionError:
        raise TemplateError([f"{path}: not readable"])
    except tomllib.TOMLDecodeError as exc:
        raise TemplateError([f"{path}: not valid TOML ({exc})"])
    except OSError as exc:
        raise TemplateError([f"{path}: {exc}"])


def resolve_ref(ref: str, relative_to: Path | None) -> Path | str:
    if ref == "default":
        return "default"
    p = Path(os.path.expanduser(ref))
    if not p.is_absolute() and relative_to is not None:
        p = relative_to / p
    return p.resolve()


def load_chain(ref: Path | str) -> tuple[list[dict], list[str], list[str]]:
    """Read a template and everything it extends; return the raw tables and
    their names (base first) and the shape errors (unknown keys, wrong
    types) of every file in the chain."""
    chain: list[tuple[str, dict]] = []
    shape_errors: list[str] = []
    seen: set[str] = set()
    current: Path | str = ref
    while True:
        key = "default" if current == "default" else str(current)
        if key in seen:
            raise TemplateError([f"extends: cycle through {key}"])
        seen.add(key)
        path = DEFAULT_PATH if current == "default" else Path(current)
        raw = _read_toml(path)
        file_errors: list[str] = []
        check_shape(raw, TOP, "", file_errors)
        shape_errors += [f"{key}: {e}" for e in file_errors]
        chain.append((key, raw))
        if len(chain) > MAX_CHAIN:
            raise TemplateError([f"extends: chain is deeper than {MAX_CHAIN} files"])
        if "extends" not in raw:
            break
        if current == "default":
            raise TemplateError(["the built-in default must not extend anything"])
        if not isinstance(raw["extends"], str):
            raise TemplateError(shape_errors)
        current = resolve_ref(raw["extends"], path.parent)
    chain.reverse()
    return [raw for _, raw in chain], [k for k, _ in chain], shape_errors


def compose(raws: list[dict], tracker: str | None) -> dict:
    """Layer the chain, base first. Each file's own [per_tracker] overlay is
    applied to that file before the next file is layered on top, so a
    child's top-level values always win over its base's overlay."""
    merged: dict = {}
    for raw in raws:
        layer = {k: v for k, v in raw.items() if k not in ("per_tracker", "extends")}
        if tracker:
            layer = deep_merge(layer, (raw.get("per_tracker") or {}).get(tracker, {}))
        merged = deep_merge(merged, layer)
    if tracker:
        merged["tracker"] = tracker
    est = merged.get("estimate")
    if isinstance(est, dict) and est.get("field") == "":
        del est["field"]  # "" clears an inherited field: propose only
    return merged


def validate_template(ref: Path | str, tracker: str | None = None) -> tuple[dict, list[str]]:
    raws, chain, errors = load_chain(ref)
    named = next((r["tracker"] for r in reversed(raws) if r.get("tracker") in TRACKERS), None)
    if tracker and named and tracker != named:
        raise TemplateError([f"tracker: template is for {named!r}, but {tracker!r} was requested"])
    active = tracker or named
    try:
        if active is None:
            # A base template: check it alone, then once per tracker overlay.
            check_semantics(compose(raws, None), errors, base=True)
            for t in TRACKERS:
                sub: list[str] = []
                check_semantics(compose(raws, t), sub, base=False)
                errors += [f"[{t}] {e}" for e in sub if f"[{t}] {e}" not in errors]
        else:
            check_semantics(compose(raws, active), errors, base=False)
    except (TypeError, AttributeError, KeyError, IndexError):
        # Wrong shapes can break cross-key checks; the shape errors say why.
        if not errors:
            raise
    if errors:
        raise TemplateError(errors)
    return compose(raws, active), chain


# ------------------------------------------------------------------ config

def _repo_root(project_dir: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(project_dir), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return Path(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None


def _config_entry(value, tracker: str | None, cfg: Path) -> tuple[str | None, str | None]:
    """Return (path, notice) for one config file's ticket_template value: a
    path for every tracker, or a table naming one path per tracker."""
    bad = f"{cfg}: ticket_template must be a file path or a table of tracker = path; using the built-in default template"
    if isinstance(value, str):
        return (value, None) if value.strip() else (None, bad)
    if not isinstance(value, dict) or set(value) - set(TRACKERS):
        return None, bad
    if any(not isinstance(v, str) or not v.strip() for v in value.values()):
        return None, bad
    if tracker is None:
        return None, f"{cfg}: ticket_template names one template per tracker, but no tracker was given; using the built-in default template"
    return value.get(tracker), None


def find_template_ref(project_dir: Path, config_dir: Path | None,
                      tracker: str | None = None) -> tuple[Path | str | None, str | None]:
    """Return (template reference, notice). Project config overrides user
    config key by key; in a per-tracker table each tracker is its own key.
    A config file that cannot be read is a notice."""
    user_dir = config_dir or Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    candidates = [user_dir / CONFIG_NAME]
    root = _repo_root(project_dir)
    if root:
        candidates.append(root / ".claude" / CONFIG_NAME)
    ref: Path | str | None = None
    for cfg in candidates:
        if not cfg.is_file():
            continue
        try:
            data = _read_toml(cfg)
        except TemplateError as exc:
            return None, f"{exc.errors[0]}; using the built-in default template"
        value = data.get("ticket_template")
        if value is None:
            continue
        entry, notice = _config_entry(value, tracker, cfg)
        if notice:
            return None, notice
        if entry is None:
            continue
        ref = resolve_ref(entry, cfg.parent)
    return ref, None


def resolve(tracker: str | None, project_dir: Path, config_dir: Path | None,
            template: str | None) -> dict:
    notice = None
    if template:
        ref: Path | str | None = resolve_ref(template, Path.cwd())
    else:
        ref, notice = find_template_ref(project_dir, config_dir, tracker)
    if ref is not None:
        try:
            resolved, chain = validate_template(ref, tracker)
            return {"template": resolved, "tracker": resolved.get("tracker"),
                    "source": str(ref), "chain": chain, "notice": None}
        except TemplateError as exc:
            first = exc.errors[0].removeprefix(f"{ref}: ")
            notice = f"Template {ref} could not be used ({first}); using the built-in default template"
    resolved, chain = validate_template("default", tracker)
    return {"template": resolved, "tracker": tracker, "source": "default",
            "chain": chain, "notice": notice}


# --------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="op", required=True)
    v = sub.add_parser("validate", help="validate one template file (or 'default')")
    v.add_argument("path")
    v.add_argument("--tracker", choices=TRACKERS)
    r = sub.add_parser("resolve", help="find, layer and validate the configured template")
    r.add_argument("--tracker", choices=TRACKERS)
    r.add_argument("--project-dir", default=".")
    r.add_argument("--config-dir")
    r.add_argument("--template", help="use this template file instead of the configured one")
    args = ap.parse_args(argv)

    if args.op == "validate":
        ref = resolve_ref(args.path, Path.cwd())
        try:
            resolved, chain = validate_template(ref, args.tracker)
        except TemplateError as exc:
            print(f"INVALID {args.path}: {len(exc.errors)} error(s)")
            for e in exc.errors:
                print(f"  - {e}")
            return 1
        trackers = [resolved["tracker"]] if resolved.get("tracker") else list(TRACKERS)
        print(f"OK {args.path} (chain: {' -> '.join(chain)}; trackers checked: {', '.join(trackers)})")
        return 0

    try:
        out = resolve(args.tracker, Path(args.project_dir).resolve(),
                      Path(args.config_dir) if args.config_dir else None, args.template)
    except TemplateError as exc:
        print(json.dumps({"error": "built-in default template is invalid", "details": exc.errors}))
        return 2
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
