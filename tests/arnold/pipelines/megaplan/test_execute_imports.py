"""Compatibility checks for canonical execute modules and legacy facades."""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    ("legacy_module", "canonical_module", "symbol"),
    [
        ("megaplan.execute.batch", "arnold.pipelines.megaplan.execute.batch", "handle_execute_one_batch"),
        ("megaplan.execute.core", "arnold.pipelines.megaplan.execute.core", "handle_execute_one_batch"),
        ("megaplan.execute._envelope", "arnold.pipelines.megaplan.execute._envelope", "unified_execute_enabled"),
        ("megaplan.execute.aggregation", "arnold.pipelines.megaplan.execute.aggregation", "_build_aggregate_execution_payload"),
        ("megaplan.execute.merge", "arnold.pipelines.megaplan.execute.merge", "_validate_and_merge_batch"),
        ("megaplan.execute.quality", "arnold.pipelines.megaplan.execute.quality", "run_quality_checks"),
        ("megaplan.execute.timeout", "arnold.pipelines.megaplan.execute.timeout", "_recover_execute_timeout"),
    ],
)
def test_legacy_execute_modules_alias_canonical_modules(
    legacy_module: str,
    canonical_module: str,
    symbol: str,
) -> None:
    legacy = importlib.import_module(legacy_module)
    canonical = importlib.import_module(canonical_module)
    assert legacy is canonical
    assert getattr(legacy, symbol) is getattr(canonical, symbol)


def test_legacy_envelope_alias_preserves_cached_flag_state() -> None:
    legacy = importlib.import_module("megaplan.execute._envelope")
    canonical = importlib.import_module("arnold.pipelines.megaplan.execute._envelope")
    legacy._CACHED = True
    assert canonical._CACHED is True


def test_legacy_aggregation_alias_preserves_monkeypatch_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = importlib.import_module("megaplan.execute.aggregation")
    canonical = importlib.import_module("arnold.pipelines.megaplan.execute.aggregation")
    sentinel = object()
    monkeypatch.setattr(legacy, "_capture_git_status_snapshot", sentinel)
    assert canonical._capture_git_status_snapshot is sentinel


def test_legacy_batch_alias_preserves_monkeypatch_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = importlib.import_module("megaplan.execute.batch")
    canonical = importlib.import_module("arnold.pipelines.megaplan.execute.batch")
    sentinel = object()
    monkeypatch.setattr(legacy, "_capture_git_status_snapshot", sentinel)
    assert canonical._capture_git_status_snapshot is sentinel


def test_legacy_core_alias_preserves_monkeypatch_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = importlib.import_module("megaplan.execute.core")
    canonical = importlib.import_module("arnold.pipelines.megaplan.execute.core")
    sentinel = object()
    monkeypatch.setattr(legacy, "_capture_git_status_snapshot", sentinel)
    assert canonical._capture_git_status_snapshot is sentinel
