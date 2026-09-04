from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.orchestration import prep_research
from arnold_pipelines.megaplan.types import AgentMode
from arnold_pipelines.megaplan.workers import WorkerResult


@pytest.mark.parametrize("step", ["prep-triage", "prep-distill"])
def test_direct_prep_worker_binds_parent_wbc_and_unique_dispatch_key(
    tmp_path, monkeypatch: pytest.MonkeyPatch, step: str
) -> None:
    captured: dict[str, object] = {}
    wbc = object()
    resolved = AgentMode(
        agent="omp",
        mode="ephemeral",
        refreshed=True,
        model="openrouter/meta/muse-spark-1.3-contributor",
        effort="high",
        resolved_model="openrouter/meta/muse-spark-1.3-contributor",
    )

    def build(**kwargs: object) -> object:
        captured.update(kwargs)
        return wbc

    def run(
        _step: str, _state: object, _plan_dir: object, _args: object, **kwargs: object
    ):
        assert kwargs["wbc_dispatch"] is wbc
        return (
            WorkerResult(payload={}, raw_output="ok", duration_ms=1, cost_usd=0.0),
            "omp",
            "ephemeral",
            True,
        )

    monkeypatch.setattr(prep_research, "build_worker_dispatch_spec", build)
    monkeypatch.setattr(prep_research, "run_step_with_worker", run)
    monkeypatch.setattr(
        prep_research, "update_session_state", lambda *_args, **_kwargs: None
    )

    prep_research._run_prep_worker_step(
        step,
        {"sessions": {}},
        tmp_path,
        root=tmp_path,
        resolved=resolved,
        prompt="triage or distill",
    )

    assert captured["phase_step"] == "prep"
    assert captured["route_kind"] == "direct"
    assert captured["dispatch_key"] == step
    assert (
        captured["selected_spec"]
        == "omp:openrouter/meta/muse-spark-1.3-contributor:high"
    )


def test_direct_prep_worker_keeps_missing_parent_wbc_fail_closed(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def build(**kwargs: object) -> None:
        captured.update(kwargs)
        return None

    def run(*_args: object, **kwargs: object):
        assert kwargs["wbc_dispatch"] is None
        raise RuntimeError("production caller must reject missing WBC")

    monkeypatch.setattr(prep_research, "build_worker_dispatch_spec", build)
    monkeypatch.setattr(prep_research, "run_step_with_worker", run)

    with pytest.raises(RuntimeError, match="missing WBC"):
        prep_research._run_prep_worker_step(
            "prep-triage",
            {"sessions": {}},
            tmp_path,
            root=tmp_path,
            resolved=AgentMode(
                agent="omp",
                mode="ephemeral",
                refreshed=True,
                model="openrouter/meta/muse-spark-1.3-contributor",
                effort="high",
                resolved_model="openrouter/meta/muse-spark-1.3-contributor",
            ),
            prompt="triage",
        )
    assert captured["phase_step"] == "prep"
