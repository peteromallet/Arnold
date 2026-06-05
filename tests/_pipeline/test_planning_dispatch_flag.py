"""T25: planning compiler dispatches through discovered package behind a flag."""

from __future__ import annotations

import inspect
from unittest.mock import patch, sentinel

from arnold.pipelines.megaplan._pipeline import planning


def test_discovered_planning_helper_is_inline_env_default_on(monkeypatch) -> None:
    monkeypatch.delenv("MEGAPLAN_M6_DISCOVERED_PLANNING", raising=False)

    assert planning._discovered_planning_enabled() is True
    source = inspect.getsource(planning._discovered_planning_enabled)
    assert (
        'os.environ.get("MEGAPLAN_M6_DISCOVERED_PLANNING", "1") == "1"'
        in source
    )
    assert "flags" not in source


def test_compile_planning_pipeline_flag_off_uses_legacy_compiler(monkeypatch) -> None:
    monkeypatch.setenv("MEGAPLAN_M6_DISCOVERED_PLANNING", "0")

    with patch.object(
        planning,
        "_compile_legacy_planning_pipeline",
        return_value=sentinel.legacy_pipeline,
    ) as legacy_spy, patch(
        "arnold.pipelines.megaplan.pipelines.planning.build_pipeline",
        return_value=sentinel.discovered_pipeline,
    ) as discovered_spy:
        pipeline = planning.compile_planning_pipeline()

    assert pipeline is sentinel.legacy_pipeline
    legacy_spy.assert_called_once_with()
    discovered_spy.assert_not_called()


def test_compile_planning_pipeline_flag_on_uses_discovered_package(monkeypatch) -> None:
    monkeypatch.setenv("MEGAPLAN_M6_DISCOVERED_PLANNING", "1")

    with patch.object(
        planning,
        "_compile_legacy_planning_pipeline",
        return_value=sentinel.legacy_pipeline,
    ) as legacy_spy, patch(
        "arnold.pipelines.megaplan.pipelines.planning.build_pipeline",
        return_value=sentinel.discovered_pipeline,
    ) as discovered_spy:
        pipeline = planning.compile_planning_pipeline()

    assert pipeline is sentinel.discovered_pipeline
    discovered_spy.assert_called_once_with()
    legacy_spy.assert_not_called()
