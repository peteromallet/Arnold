from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_agent_skill_surfaces_are_synced() -> None:
    source = (ROOT / "docs" / "agent-skill" / "SKILL.md").read_text(encoding="utf-8")
    claude_bootstrap = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    bootstrap = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "name: vibecomfy" in source
    assert "docs/agent-skill/SKILL.md" in claude_bootstrap
    assert "name: vibecomfy" not in claude_bootstrap
    assert "canonical long-form agent instructions" in bootstrap
    assert "docs/agent-skill/SKILL.md" in bootstrap
    assert "name: vibecomfy" not in bootstrap


def test_agent_skill_sync_check_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/sync_agent_skill.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_install_user_updates_codex_agents_md(tmp_path: Path) -> None:
    for harness in (".claude", ".codex", ".hermes"):
        (tmp_path / harness / "skills").mkdir(parents=True)
    agents_md = tmp_path / ".codex" / "AGENTS.md"
    agents_md.write_text("# Existing Codex instructions\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/sync_agent_skill.py", "--install-user"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={
            "HOME": str(tmp_path),
            "HERMES_HOME": str(tmp_path / ".hermes"),
        },
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".claude" / "skills" / "vibecomfy").is_symlink()
    assert (tmp_path / ".codex" / "skills" / "vibecomfy").is_symlink()
    assert (tmp_path / ".hermes" / "skills" / "vibecomfy").is_symlink()
    updated_agents = agents_md.read_text(encoding="utf-8")
    assert "# Existing Codex instructions" in updated_agents
    assert "<!-- vibecomfy:skillsinker:begin -->" in updated_agents
    assert "`vibecomfy`" in updated_agents
