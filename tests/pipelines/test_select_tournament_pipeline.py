from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from megaplan._pipeline import registry
from megaplan._pipeline.discovery.manifest import Manifest, read_manifest
from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.types import ParallelStage, PortRef, Stage, StepContext


PIPELINE_INIT = (
    Path(__file__).resolve().parents[2]
    / "megaplan"
    / "pipelines"
    / "select-tournament"
    / "__init__.py"
)


def test_select_tournament_manifest_is_static_and_discoverable() -> None:
    result = read_manifest(PIPELINE_INIT)
    assert isinstance(result, Manifest)
    assert result.name == "select-tournament"
    assert result.arnold_api_version == "1.0"
    assert result.entrypoint == "build_pipeline"
    assert result.capabilities == ("review",)


def test_select_tournament_manifest_first_scan_defers_import() -> None:
    scan_root = PIPELINE_INIT.parents[1]
    with patch.dict(
        "os.environ", {"MEGAPLAN_M6_MANIFEST_DISCOVERY": "1"}, clear=False
    ), patch.object(
        registry, "_get_scan_roots", lambda: [(scan_root, "megaplan.pipelines")]
    ), patch.object(registry, "_load_module_from_path") as load_spy:
        dispositions = registry.scan_python_pipelines()

    by_name = {d.cli_name: d for d in dispositions}
    assert "select-tournament" in by_name
    assert by_name["select-tournament"].status == "discovered"
    assert isinstance(by_name["select-tournament"].manifest, Manifest)
    assert load_spy.call_count == 0


def test_select_tournament_declares_ports_for_every_cross_stage_boundary(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    import importlib

    module = importlib.import_module("megaplan.pipelines.select-tournament")
    pipeline = module.build_pipeline(candidates=("a", "b", "c", "d"))

    assert pipeline.binding_map == {
        ("pairwise_bracket", "candidate_scores"): (
            "score_candidates",
            "candidate_scores",
        ),
        ("winner", "bracket_result"): ("pairwise_bracket", "bracket_result"),
    }

    score_stage = pipeline.stages["score_candidates"]
    assert isinstance(score_stage, ParallelStage)
    assert score_stage.produces

    for stage_name in ("pairwise_bracket", "winner"):
        stage = pipeline.stages[stage_name]
        assert isinstance(stage, Stage)
        assert stage.consumes
        assert all(isinstance(port_ref, PortRef) for port_ref in stage.consumes)
        for port_ref in stage.consumes:
            assert (stage_name, port_ref.port_name) in pipeline.binding_map


def test_select_tournament_runs_through_declared_ports(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    import importlib

    module = importlib.import_module("megaplan.pipelines.select-tournament")
    pipeline = module.build_pipeline(candidates=("a", "b", "c", "d"))
    plan_dir = tmp_path / "select-tournament"
    ctx = StepContext(plan_dir=plan_dir, state={}, profile={}, mode="select")

    result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)

    assert result["final_stage"] == "winner"
    assert result["state"]["select_tournament_winner"] == "d"
    winner = json.loads((plan_dir / "winner" / "v1.json").read_text())
    assert winner == {
        "score": 1.0,
        "seed": 3,
        "source_port": "bracket_result",
        "winner": "d",
    }
