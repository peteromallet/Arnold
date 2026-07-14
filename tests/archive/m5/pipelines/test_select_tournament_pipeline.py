from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.skip("archived legacy tournament pipeline; native contract coverage is active elsewhere", allow_module_level=True)

from arnold.pipeline import (
    Edge,
    ParallelStage,
    Pipeline,
    Port,
    PortRef,
    Stage,
    run_pipeline,
)
from arnold.pipelines.megaplan._pipeline.behavioral_manifest import (
    RuntimeTopologyProjectionError,
    capsule_definition_identity_projection,
    runtime_topology_projection_for_pipeline,
)
from arnold.pipelines.megaplan._pipeline import registry
from arnold.pipeline.discovery.manifest import Manifest, read_manifest
from arnold.pipeline.contracts import PortBindError
from arnold.pipeline.native import NativeProgram
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.pipelines.megaplan.pipelines.select_tournament.pipeline import (
    _bind_or_raise,
)


PIPELINE_INIT = (
    Path(__file__).resolve().parents[4]
    / "arnold"
    / "pipelines"
    / "megaplan"
    / "pipelines"
    / "select_tournament"
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
        registry, "_get_scan_roots", lambda: [(scan_root, "arnold.pipelines.megaplan.pipelines")]
    ):
        dispositions = registry.scan_python_pipelines()

    by_name = {d.cli_name: d for d in dispositions}
    assert "select-tournament" in by_name
    assert by_name["select-tournament"].status == "discovered"
    assert isinstance(by_name["select-tournament"].manifest, Manifest)


def test_select_tournament_declares_ports_for_every_cross_stage_boundary(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    import importlib

    module = importlib.import_module("arnold.pipelines.megaplan.pipelines.select_tournament")
    pipeline = module.build_pipeline(candidates=("a", "b", "c", "d"))

    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.native_program, NativeProgram)
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


def test_select_tournament_private_bind_uses_lowered_authored_declarations(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    import importlib

    module = importlib.import_module("arnold.pipelines.megaplan.pipelines.select_tournament")

    class _Step:
        produces = ()
        consumes = ()

        def run(self, ctx):  # pragma: no cover
            raise NotImplementedError

    pipeline = Pipeline(
        stages={
            "src": Stage(
                name="src",
                step=_Step(),
                edges=(Edge(label="sink", target="sink"),),
                writes=(Port(name="alpha", content_type="text/markdown"),),
            ),
            "sink": Stage(
                name="sink",
                step=_Step(),
                edges=(),
                reads=(PortRef(port_name="alpha", content_type="text/markdown"),),
            ),
        },
        entry="src",
    )

    bound = _bind_or_raise(pipeline)

    assert bound.binding_map == {("sink", "alpha"): ("src", "alpha")}


def test_select_tournament_private_bind_rejects_drifted_authored_declarations(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    import importlib

    module = importlib.import_module("arnold.pipelines.megaplan.pipelines.select_tournament")

    class _Step:
        produces = ()
        consumes = ()

        def run(self, ctx):  # pragma: no cover
            raise NotImplementedError

    pipeline = Pipeline(
        stages={
            "src": Stage(
                name="src",
                step=_Step(),
                edges=(Edge(label="sink", target="sink"),),
                writes=(Port(name="alpha", content_type="text/markdown"),),
                produces=(Port(name="other", content_type="text/markdown"),),
            ),
            "sink": Stage(
                name="sink",
                step=_Step(),
                edges=(),
                reads=(PortRef(port_name="alpha", content_type="text/markdown"),),
            ),
        },
        entry="src",
    )

    with pytest.raises(PortBindError, match="bind failed: no_match"):
        _bind_or_raise(pipeline)


def test_select_tournament_runs_through_declared_ports(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    import importlib

    module = importlib.import_module("arnold.pipelines.megaplan.pipelines.select_tournament")
    pipeline = module.build_pipeline(candidates=("a", "b", "c", "d"))
    plan_dir = tmp_path / "select-tournament"

    result = run_pipeline(
        pipeline,
        initial_state={},
        envelope=RuntimeEnvelope(artifact_root=str(plan_dir)),
    )

    assert result.state["select_tournament_winner"] == "d"
    winner = json.loads((plan_dir / "winner" / "v1.json").read_text())
    assert winner == {
        "score": 1.0,
        "seed": 3,
        "source_port": "bracket_result",
        "winner": "d",
    }


def test_select_tournament_non_default_candidates_drive_native_program(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    import importlib

    module = importlib.import_module("arnold.pipelines.megaplan.pipelines.select_tournament")
    pipeline = module.build_pipeline(candidates=("red", "green", "blue"))
    plan_dir = tmp_path / "select-tournament-custom"

    assert pipeline.native_program is not None
    parallel_block = pipeline.native_program.parallel_blocks[0]
    assert parallel_block.branches == (
        "candidate_score_0",
        "candidate_score_1",
        "candidate_score_2",
    )
    assert pipeline.stages["score_candidates"].max_workers == 3

    result = run_pipeline(
        pipeline,
        initial_state={},
        envelope=RuntimeEnvelope(artifact_root=str(plan_dir)),
    )

    assert result.state["select_tournament_winner"] == "blue"
    winner = json.loads((plan_dir / "winner" / "v1.json").read_text())
    assert winner["winner"] == "blue"
    scores = json.loads((plan_dir / "score_candidates" / "v1.json").read_text())
    assert [candidate["candidate"] for candidate in scores["candidates"]] == [
        "red",
        "green",
        "blue",
    ]


def test_select_tournament_mirror_is_compatibility_shim() -> None:
    import arnold.pipelines.megaplan.pipelines.select_tournament as canonical
    import arnold.pipelines.megaplan.pipelines.select_tournament.pipeline as canonical_pipeline
    import arnold_pipelines.megaplan.pipelines.select_tournament as mirror
    import arnold_pipelines.megaplan.pipelines.select_tournament.pipeline as mirror_pipeline

    assert mirror.build_pipeline is canonical.build_pipeline
    assert mirror_pipeline.build_pipeline is canonical_pipeline.build_pipeline
    assert mirror.__all__ == canonical.__all__
    assert not hasattr(mirror, "_build_legacy_graph_pipeline")


def test_select_tournament_runtime_topology_projection_is_stable(monkeypatch) -> None:
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    import importlib

    module = importlib.import_module("arnold.pipelines.megaplan.pipelines.select_tournament")
    first_pipeline = module.build_pipeline(candidates=("a", "b", "c", "d"))
    second_pipeline = module.build_pipeline(candidates=("a", "b", "c", "d"))

    first = runtime_topology_projection_for_pipeline(first_pipeline)
    second = runtime_topology_projection_for_pipeline(second_pipeline)

    assert first.runtime_topology_hash == second.runtime_topology_hash
    assert first.canonical_bytes == second.canonical_bytes
    assert first.runtime_topology_hash.startswith("sha256:")
    assert first.as_dict()["projection"] == "megaplan.runtime-topology"
    assert first.entry == "score_candidates"
    assert any(
        row == {
            "stage": "pairwise_bracket",
            "port": "candidate_scores",
            "source_stage": "score_candidates",
            "source_port": "candidate_scores",
        }
        for row in first.binding_map
    )


def test_select_tournament_runtime_topology_hash_changes_for_topology_fixture(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    import importlib

    module = importlib.import_module("arnold.pipelines.megaplan.pipelines.select_tournament")
    four_candidates = module.build_pipeline(candidates=("a", "b", "c", "d"))
    five_candidates = module.build_pipeline(candidates=("a", "b", "c", "d", "e"))

    before = runtime_topology_projection_for_pipeline(four_candidates)
    after = runtime_topology_projection_for_pipeline(five_candidates)

    assert after.runtime_topology_hash != before.runtime_topology_hash
    before_stage = next(
        stage for stage in before.stages if stage["name"] == "score_candidates"
    )
    after_stage = next(
        stage for stage in after.stages if stage["name"] == "score_candidates"
    )
    assert before_stage["max_workers"] == 4
    assert after_stage["max_workers"] == 5


def test_runtime_topology_name_lookup_requires_explicit_import() -> None:
    with pytest.raises(RuntimeTopologyProjectionError, match="allow_import=True"):
        runtime_topology_projection_for_pipeline("select-tournament")


def test_runtime_topology_name_lookup_uses_registry_only_when_allowed(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    projection = runtime_topology_projection_for_pipeline(
        "select-tournament",
        allow_import=True,
    )

    assert projection.pipeline_name == "select-tournament"
    assert projection.runtime_topology_hash.startswith("sha256:")


def test_capsule_definition_identity_keeps_static_and_runtime_separate() -> None:
    static_only = capsule_definition_identity_projection(
        static_behavioral_hash="sha256:static",
    )
    replayable = capsule_definition_identity_projection(
        static_behavioral_hash="sha256:static",
        runtime_topology_hash="sha256:runtime",
    )

    assert static_only["identity_mode"] == "static-only"
    assert static_only["replay_ready"] is False
    assert replayable["identity_mode"] == "static+runtime-topology"
    assert replayable["replay_ready"] is True
    assert replayable["definition_identity_hash"] != static_only["definition_identity_hash"]
