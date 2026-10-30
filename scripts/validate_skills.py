"""Validate project-level Codex skills and their registry."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LOCAL_LINK_PATTERN = re.compile(r"\[[^\]]+\]\((?![a-z]+://|#)([^)]+)\)")
REGISTRY_NAME_PATTERN = re.compile(r"^\| `([a-z0-9-]+)` \|", re.MULTILINE)


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    directory: Path
    entrypoint: Path


def parse_frontmatter(path: Path) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, [f"{path}: missing opening YAML frontmatter delimiter"]

    try:
        closing_index = next(
            index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"
        )
    except StopIteration:
        return {}, [f"{path}: missing closing YAML frontmatter delimiter"]

    metadata: dict[str, str] = {}
    for line_number, line in enumerate(lines[1:closing_index], start=2):
        if not line or line[0].isspace():
            continue
        if ":" not in line:
            errors.append(f"{path}:{line_number}: invalid top-level metadata")
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"\'')
    return metadata, errors


def validate_references(entrypoint: Path) -> list[str]:
    errors: list[str] = []
    text = entrypoint.read_text(encoding="utf-8")
    for raw_target in LOCAL_LINK_PATTERN.findall(text):
        target = raw_target.split("#", 1)[0].strip().strip("<>")
        if not target:
            continue
        resolved = (entrypoint.parent / target).resolve()
        try:
            resolved.relative_to(entrypoint.parent.resolve())
        except ValueError:
            errors.append(f"{entrypoint}: reference escapes skill directory: {raw_target}")
            continue
        if not resolved.is_file():
            errors.append(f"{entrypoint}: referenced file does not exist: {raw_target}")
    return errors


def discover_skills(skills_root: Path) -> tuple[list[Skill], list[str]]:
    skills: list[Skill] = []
    errors: list[str] = []
    if not skills_root.is_dir():
        return [], [f"Missing skills directory: {skills_root}"]

    for child in sorted(skills_root.iterdir()):
        if child.name.startswith("."):
            continue
        if not child.is_dir():
            errors.append(f"Unexpected file in skills directory: {child}")
            continue

        entrypoint = child / "SKILL.md"
        if not entrypoint.is_file():
            errors.append(f"{child}: missing SKILL.md")
            continue

        metadata, metadata_errors = parse_frontmatter(entrypoint)
        errors.extend(metadata_errors)
        name = metadata.get("name", "")
        description = metadata.get("description", "")
        if not name:
            errors.append(f"{entrypoint}: missing required metadata 'name'")
        elif not NAME_PATTERN.fullmatch(name):
            errors.append(f"{entrypoint}: invalid skill name '{name}'")
        elif name != child.name:
            errors.append(f"{entrypoint}: name '{name}' does not match directory '{child.name}'")
        if not description:
            errors.append(f"{entrypoint}: missing required metadata 'description'")
        elif len(description) < 20:
            errors.append(f"{entrypoint}: description is too short to be a useful trigger")

        errors.extend(validate_references(entrypoint))
        if name and description:
            skills.append(Skill(name, description, child, entrypoint))

    names: dict[str, list[Path]] = {}
    for skill in skills:
        names.setdefault(skill.name, []).append(skill.entrypoint)
    for name, paths in names.items():
        if len(paths) > 1:
            errors.append(f"Duplicate skill name '{name}': {', '.join(map(str, paths))}")
    return skills, errors


def validate_registry(registry_path: Path, skills: list[Skill]) -> list[str]:
    if not registry_path.is_file():
        return [f"Missing skill registry: {registry_path}"]

    registry_names = REGISTRY_NAME_PATTERN.findall(
        registry_path.read_text(encoding="utf-8")
    )
    errors: list[str] = []
    duplicates = sorted({name for name in registry_names if registry_names.count(name) > 1})
    if duplicates:
        errors.append(f"Duplicate registry entries: {', '.join(duplicates)}")

    discovered_names = {skill.name for skill in skills}
    registered_names = set(registry_names)
    missing = sorted(discovered_names - registered_names)
    unknown = sorted(registered_names - discovered_names)
    if missing:
        errors.append(f"Skills missing from registry: {', '.join(missing)}")
    if unknown:
        errors.append(f"Registry entries without a skill: {', '.join(unknown)}")
    return errors


def validate_project(root: Path) -> tuple[list[Skill], list[str]]:
    skills, errors = discover_skills(root / ".agents" / "skills")
    errors.extend(validate_registry(root / "docs" / "skills" / "registry.md", skills))
    return skills, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (defaults to the parent of scripts/)",
    )
    args = parser.parse_args(argv)
    skills, errors = validate_project(args.root.resolve())
    if errors:
        print(f"Skill validation failed with {len(errors)} error(s):", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    names = ", ".join(sorted(skill.name for skill in skills))
    print(f"Validated {len(skills)} skill(s): {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
