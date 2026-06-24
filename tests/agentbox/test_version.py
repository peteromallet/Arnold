from __future__ import annotations

from agentbox.version import agentbox_version


def test_agentbox_version_returns_version_string() -> None:
    result = agentbox_version()

    assert "agentbox" in result
    assert isinstance(result["agentbox"], str)
    assert result["agentbox"]
