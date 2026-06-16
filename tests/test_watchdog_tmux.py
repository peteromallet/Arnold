"""Tests for watchdog tmux enrichment."""

from __future__ import annotations

from pathlib import Path

from arnold.pipelines.megaplan.watchdog.tmux_scan import enrich_with_tmux


def test_enrich_discovers_tmux_sessions(monkeypatch, tmp_path):
    plan_dir = tmp_path / "my-plan"
    plan_dir.mkdir()

    class _FakeSession:
        def __init__(self, name: str) -> None:
            self.name = name

        def exists(self) -> bool:
            return self.name == "my-plan-live"

    def _fake_detect(pattern: str) -> list[str]:
        if "my-plan" in pattern:
            return ["my-plan-live", "my-plan-dead"]
        return []

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.watchdog.tmux_scan.TmuxSession",
        _FakeSession,
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.watchdog.tmux_scan.detect_orphans",
        _fake_detect,
    )

    result = enrich_with_tmux((), (plan_dir,))
    info = result[plan_dir]
    assert "my-plan-live" in info.session_names
    assert "my-plan-dead" in info.orphans
