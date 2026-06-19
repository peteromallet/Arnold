from pathlib import Path


def test_megaplan_skill_files_are_portable_files() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    skills_root = repo_root / "arnold" / "pipelines" / "megaplan" / "skills"
    skill_files = sorted(skills_root.glob("*/SKILL.md"))

    assert skill_files, "expected bundled megaplan skill files"
    for path in skill_files:
        assert path.is_file(), f"{path} must be a file"
        assert not path.is_symlink(), f"{path} must not be a symlink"
