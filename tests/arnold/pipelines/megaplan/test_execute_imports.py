"""Canonical execute module import checks."""

from __future__ import annotations

import argparse
import importlib

import pytest


@pytest.mark.parametrize(
    ("canonical_module", "symbol"),
    [
        ("arnold.pipelines.megaplan.execute.batch", "handle_execute_one_batch"),
        ("arnold.pipelines.megaplan.execute.core", "handle_execute_one_batch"),
        ("arnold.pipelines.megaplan.execute._envelope", "unified_execute_enabled"),
        ("arnold.pipelines.megaplan.execute.aggregation", "_build_aggregate_execution_payload"),
        ("arnold.pipelines.megaplan.execute.merge", "_validate_and_merge_batch"),
        ("arnold.pipelines.megaplan.execute.quality", "run_quality_checks"),
        ("arnold.pipelines.megaplan.execute.timeout", "_recover_execute_timeout"),
    ],
)
def test_canonical_execute_modules_export_symbols(
    canonical_module: str,
    symbol: str,
) -> None:
    canonical = importlib.import_module(canonical_module)
    assert hasattr(canonical, symbol)


def test_canonical_envelope_preserves_cached_flag_state() -> None:
    canonical = importlib.import_module("arnold.pipelines.megaplan.execute._envelope")
    canonical._CACHED = True
    assert canonical._CACHED is True


def test_canonical_aggregation_preserves_monkeypatch_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical = importlib.import_module("arnold.pipelines.megaplan.execute.aggregation")
    sentinel = object()
    monkeypatch.setattr(canonical, "_capture_git_status_snapshot", sentinel)
    assert canonical._capture_git_status_snapshot is sentinel


def test_canonical_batch_preserves_monkeypatch_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical = importlib.import_module("arnold.pipelines.megaplan.execute.batch")
    sentinel = object()
    monkeypatch.setattr(canonical, "_capture_git_status_snapshot", sentinel)
    assert canonical._capture_git_status_snapshot is sentinel


def test_tier_spec_resolution_uses_requested_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical = importlib.import_module("arnold.pipelines.megaplan.execute.batch")
    calls: list[tuple[str, list[str]]] = []

    def fake_resolve_agent_mode(phase: str, args: argparse.Namespace):
        calls.append((phase, list(args.phase_model)))
        return ("codex", "low", False, "gpt-5.4")

    monkeypatch.setattr(
        canonical.worker_module,
        "resolve_agent_mode",
        fake_resolve_agent_mode,
    )

    args = argparse.Namespace(phase_model=[])
    assert canonical._resolve_tier_spec(args, "codex:gpt-5.4") == (
        "codex",
        "low",
        "gpt-5.4",
    )
    assert canonical._resolve_tier_spec(
        args,
        "codex:gpt-5.5",
        phase="critique",
    ) == ("codex", "low", "gpt-5.4")
    assert args.phase_model == []
    assert calls == [
        ("execute", ["execute=codex:gpt-5.4"]),
        ("critique", ["critique=codex:gpt-5.5"]),
    ]


def test_canonical_core_preserves_monkeypatch_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical = importlib.import_module("arnold.pipelines.megaplan.execute.core")
    sentinel = object()
    monkeypatch.setattr(canonical, "_capture_git_status_snapshot", sentinel)
    assert canonical._capture_git_status_snapshot is sentinel
