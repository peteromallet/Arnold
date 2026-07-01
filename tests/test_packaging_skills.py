from pathlib import Path

from arnold_pipelines.megaplan.cli.skills import _GLOBAL_TARGETS, _resolve_bundle_path


def test_subagent_launcher_skill_bundle_is_portable() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    skill_dir = repo_root / "arnold_pipelines" / "megaplan" / "skills" / "subagent-launcher"
    skill_file = skill_dir / "SKILL.md"

    assert skill_file.is_file()
    assert not skill_file.is_symlink()
    assert (skill_dir / "launch_hermes_agent.py").is_file()
    assert (skill_dir / "fan.py").is_file()


def test_subagent_launcher_is_synced_to_agent_skill_dirs() -> None:
    targets = [
        target
        for target in _GLOBAL_TARGETS
        if target.get("data") == "skills/subagent-launcher"
    ]

    assert {
        (target["agent"], target["path"], target["install"])
        for target in targets
    } == {
        ("claude", ".claude/skills/subagent-launcher", "symlink"),
        ("codex", ".codex/skills/subagent-launcher", "symlink"),
        ("hermes", ".hermes/skills/subagent-launcher", "symlink"),
        ("agents", ".agents/skills/subagent-launcher", "symlink"),
    }

    skill_dir = _resolve_bundle_path("skills/subagent-launcher")
    assert skill_dir.is_dir()
    assert (skill_dir / "SKILL.md").is_file()
    assert (skill_dir / "launch_hermes_agent.py").is_file()
