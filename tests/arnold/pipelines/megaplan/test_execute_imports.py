"""Canonical execute module import checks."""

from __future__ import annotations

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


def test_canonical_core_preserves_monkeypatch_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical = importlib.import_module("arnold.pipelines.megaplan.execute.core")
    sentinel = object()
    monkeypatch.setattr(canonical, "_capture_git_status_snapshot", sentinel)
    assert canonical._capture_git_status_snapshot is sentinel
