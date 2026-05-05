from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_agent_skill_surfaces_are_synced() -> None:
    source = (ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert (ROOT / "AGENTS.md").read_text(encoding="utf-8") == source
    assert (ROOT / ".claude" / "skills" / "vibecomfy" / "SKILL.md").read_text(encoding="utf-8") == source
    assert (ROOT / "CLAUDE.md").is_symlink()
    assert str((ROOT / "CLAUDE.md").readlink()) == "AGENTS.md"


def test_openai_agent_metadata_exists() -> None:
    metadata = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")

    assert 'display_name: "VibeComfy"' in metadata
    assert "$vibecomfy" in metadata
    assert "allow_implicit_invocation: true" in metadata


def test_agent_skill_sync_check_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/sync_agent_skill.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
