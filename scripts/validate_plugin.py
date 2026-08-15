#!/usr/bin/env python3
"""Validate this plugin's manifest and structure: the manifest parses and
carries the required fields, command/skill frontmatter is present, referenced
templates exist, and README links resolve. No external services or
dependencies."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_FILES = ["PLAN.md", "LEDGER.md", "stage-N.md", "README.md"]
MANIFEST_FIELDS = ["name", "version", "description"]
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

errors = []


def err(msg):
    errors.append(msg)


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        err(f"{path.relative_to(ROOT)}: invalid JSON ({e})")
        return None
    except FileNotFoundError:
        err(f"{path.relative_to(ROOT)}: file not found")
        return None


def parse_frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        err(f"{path.relative_to(ROOT)}: missing frontmatter block")
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        err(f"{path.relative_to(ROOT)}: unterminated frontmatter block")
        return {}
    fields = {}
    for line in parts[1].splitlines():
        if not line.strip() or line.startswith(" ") or line.startswith("\t"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def check_required(path, fields, required):
    for key in required:
        if not fields.get(key):
            err(f"{path.relative_to(ROOT)}: missing or empty '{key}' in frontmatter")


def validate_manifest():
    manifest = load_json(ROOT / ".claude-plugin" / "plugin.json")
    if manifest is None:
        return
    for key in MANIFEST_FIELDS:
        if not manifest.get(key):
            err(f"plugin.json: missing or empty '{key}'")
    version = manifest.get("version", "")
    if version and not SEMVER_RE.match(version):
        err(f"plugin.json: version '{version}' is not x.y.z semver")


def validate_commands():
    commands_dir = ROOT / "commands"
    if not commands_dir.is_dir():
        err("commands/: directory not found")
        return
    for path in sorted(commands_dir.glob("*.md")):
        fields = parse_frontmatter(path)
        check_required(path, fields, ["description"])


def validate_skills():
    skills_dir = ROOT / "skills"
    if not skills_dir.is_dir():
        err("skills/: directory not found")
        return
    for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            err(f"{skill_dir.relative_to(ROOT)}: missing SKILL.md")
            continue
        fields = parse_frontmatter(skill_md)
        check_required(skill_md, fields, ["name", "description"])

        templates_dir = skill_dir / "references" / "templates"
        if templates_dir.is_dir():
            for template in TEMPLATE_FILES:
                if not (templates_dir / template).is_file():
                    err(f"{templates_dir.relative_to(ROOT)}: missing referenced template '{template}'")


def validate_readme_links():
    for readme in sorted(ROOT.rglob("README.md")):
        if any(part in (".git", "_audit") for part in readme.relative_to(ROOT).parts):
            continue
        text = readme.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            target = target.strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target_path = target.split("#", 1)[0]
            if not target_path:
                continue
            resolved = (readme.parent / target_path).resolve()
            if not resolved.exists():
                err(f"{readme.relative_to(ROOT)}: broken link to '{target}'")


def main():
    validate_manifest()
    validate_commands()
    validate_skills()
    validate_readme_links()

    if errors:
        print(f"validate-plugin: {len(errors)} error(s):\n")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    print("validate-plugin: OK")


if __name__ == "__main__":
    main()
