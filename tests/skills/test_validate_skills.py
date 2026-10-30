from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts" / "validate_skills.py"
SPEC = importlib.util.spec_from_file_location("validate_skills", VALIDATOR_PATH)
assert SPEC and SPEC.loader
validate_skills = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validate_skills
SPEC.loader.exec_module(validate_skills)


class SkillValidatorTests(unittest.TestCase):
    def create_repository(self, root: Path, skills: dict[str, str], registry: list[str]) -> None:
        skills_root = root / ".agents" / "skills"
        skills_root.mkdir(parents=True)
        for directory_name, skill_text in skills.items():
            skill_directory = skills_root / directory_name
            skill_directory.mkdir()
            (skill_directory / "SKILL.md").write_text(
                textwrap.dedent(skill_text).lstrip(), encoding="utf-8"
            )

        registry_path = root / "docs" / "skills" / "registry.md"
        registry_path.parent.mkdir(parents=True)
        rows = "\n".join(f"| `{name}` | Test description |" for name in registry)
        registry_path.write_text(f"| Skill | Description |\n|---|---|\n{rows}\n", encoding="utf-8")

    def test_current_repository_is_valid(self) -> None:
        skills, errors = validate_skills.validate_project(REPOSITORY_ROOT)
        self.assertEqual([], errors)
        self.assertEqual(14, len(skills))

    def test_reports_duplicate_metadata_names(self) -> None:
        skill = """
            ---
            name: duplicate
            description: Handle a sufficiently described test workflow.
            ---
            # Test
        """
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as directory:
            root = Path(directory)
            self.create_repository(root, {"duplicate": skill, "other": skill}, ["duplicate"])
            _, errors = validate_skills.validate_project(root)
        self.assertTrue(any("Duplicate skill name 'duplicate'" in error for error in errors))

    def test_reports_missing_skill_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as directory:
            root = Path(directory)
            skills_root = root / ".agents" / "skills"
            (skills_root / "missing-entrypoint").mkdir(parents=True)
            registry_path = root / "docs" / "skills" / "registry.md"
            registry_path.parent.mkdir(parents=True)
            registry_path.write_text(
                "| Skill | Description |\n|---|---|\n| `missing-entrypoint` | Test |\n",
                encoding="utf-8",
            )
            _, errors = validate_skills.validate_project(root)
        self.assertTrue(any("missing SKILL.md" in error for error in errors))

    def test_reports_missing_required_metadata(self) -> None:
        skill = """
            ---
            metadata:
              short-description: Missing required fields
            ---
            # Invalid skill
        """
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as directory:
            root = Path(directory)
            self.create_repository(root, {"missing-metadata": skill}, [])
            _, errors = validate_skills.validate_project(root)
        self.assertTrue(any("missing required metadata 'name'" in error for error in errors))
        self.assertTrue(
            any("missing required metadata 'description'" in error for error in errors)
        )

    def test_reports_invalid_name_and_directory_mismatch(self) -> None:
        skill = """
            ---
            name: Invalid_Name
            description: Handle a workflow with intentionally invalid metadata naming.
            ---
            # Invalid name
        """
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as directory:
            root = Path(directory)
            self.create_repository(root, {"valid-directory": skill}, [])
            _, errors = validate_skills.validate_project(root)
        self.assertTrue(any("invalid skill name 'Invalid_Name'" in error for error in errors))

    def test_reports_missing_referenced_file(self) -> None:
        skill = """
            ---
            name: linked-skill
            description: Handle a workflow with a required local reference.
            ---
            Read [the policy](references/policy.md).
        """
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as directory:
            root = Path(directory)
            self.create_repository(root, {"linked-skill": skill}, ["linked-skill"])
            _, errors = validate_skills.validate_project(root)
        self.assertTrue(any("referenced file does not exist" in error for error in errors))

    def test_reports_registry_mismatch(self) -> None:
        skill = """
            ---
            name: actual-skill
            description: Handle an actual workflow used by this test fixture.
            ---
            # Actual skill
        """
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as directory:
            root = Path(directory)
            self.create_repository(root, {"actual-skill": skill}, ["unknown-skill"])
            _, errors = validate_skills.validate_project(root)
        self.assertIn("Skills missing from registry: actual-skill", errors)
        self.assertIn("Registry entries without a skill: unknown-skill", errors)

    def test_reports_duplicate_registry_entries(self) -> None:
        skill = """
            ---
            name: registered-skill
            description: Handle a workflow used to test duplicate registry rows.
            ---
            # Registered skill
        """
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as directory:
            root = Path(directory)
            self.create_repository(
                root,
                {"registered-skill": skill},
                ["registered-skill", "registered-skill"],
            )
            _, errors = validate_skills.validate_project(root)
        self.assertIn("Duplicate registry entries: registered-skill", errors)

    def test_cli_returns_failure_for_invalid_repository(self) -> None:
        skill = """
            ---
            name: invalid-cli-skill
            ---
            # Missing description
        """
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as directory:
            root = Path(directory)
            self.create_repository(root, {"invalid-cli-skill": skill}, ["invalid-cli-skill"])
            error_output = io.StringIO()
            with redirect_stderr(error_output):
                exit_code = validate_skills.main(["--root", str(root)])
        self.assertEqual(1, exit_code)
        self.assertIn("Skill validation failed", error_output.getvalue())


if __name__ == "__main__":
    unittest.main()
