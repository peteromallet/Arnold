"""T35: canonical Megaplan-shaped fixture gate for the manifest runtime.

The fixture is built by ``tests/arnold/execution/canonical_manifest.py`` and
contains every shape from ``tests/fixtures/workflow/canonical_megaplan_shapes.yaml``
plus execution policies.  Tests fake-run it through ``arnold.execution.run`` with
``FakeBackend`` and assert deterministic final state and required journal events.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml

from arnold.execution import ExecutionRegistries, ExecutionState, run
from arnold.execution.backend import NodeOutcome, NodeState
from arnold.kernel import ControlBinding, ControlTarget, ControlTransition, ControlTransitionType, read_event_journal
from arnold.manifest import NodeRef, manifest_coordinate
from tests.arnold.execution.canonical_manifest import HASH_A, canonical_execution_manifest

FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "workflow" / "canonical_megaplan_shapes.yaml"
GOLDEN_RUNTIME_PATH = (
    Path(__file__).parent.parent.parent
    / "fixtures"
    / "golden"
    / "workflow_manifest_runtime"
    / "fresh-planning.json"
)


class _AllowingCapabilityHandler:
    def check(self, requirement_id: str, *, route: str, context: dict[str, Any]) -> Any:
        del route, context
        from arnold.kernel import CapabilityCheck, CapabilityId

        return CapabilityCheck(
            capability_id=CapabilityId(namespace="runtime", name=requirement_id),
            allowed=True,
            reason="allowed by test fixture",
        )


class _AllowingAuthorityHandler:
    def verify(self, authority_id: str, *, action: str, evidence: dict[str, Any], context: dict[str, Any]) -> bool:
        del authority_id, action, evidence, context
        return True


class _RecordingEffectHandler:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(
        self,
        effect_id: str,
        *,
        route: str,
        payload: dict[str, Any],
        idempotency_key: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del route, context
        self.calls.append((effect_id, {"payload": payload, "idempotency_key": idempotency_key}))
        return {"effect_id": effect_id, "idempotency_key": idempotency_key}


class _KindControlHandler:
    def __init__(self, kind: str) -> None:
        self.kind = kind

    def apply(
        self,
        transition_id: str,
        *,
        transition_type: str,
        binding: ControlBinding,
        context: dict[str, Any],
    ) -> ControlTransition:
        del transition_type
        enum_value = self.kind.replace("supervisor_promotion", "supervisor-promotion")
        return ControlTransition(
            transition_type=ControlTransitionType(enum_value),
            source=ControlTarget(node_ref=context.get("source_node", "")),
            target=ControlTarget(node_ref=binding.target.node_ref),
            trigger=transition_id,
            payload_schema_hash="sha256:" + "0" * 64,
            policy_ref=binding.policy_ref,
            idempotency_key=f"idem-{transition_id}",
        )


class _SimpleReducerHandler:
    def reduce(
        self,
        reducer_id: str,
        *,
        inputs: tuple[dict[str, Any], ...],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del reducer_id, context
        return {"joined": "".join(str(i.get("value", "")) for i in inputs)}


def _load_shapes() -> dict[str, Any]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)["shapes"]


def _shape_nodes(shape: dict[str, Any]) -> set[str]:
    return {node["id"] for node in shape.get("nodes", [])}


def _build_registries(*, allow_authority: bool = True) -> ExecutionRegistries:
    effects = _RecordingEffectHandler()
    authorities = _AllowingAuthorityHandler() if allow_authority else None
    kwargs: dict[str, Any] = {
        "capabilities": {"human:operator": _AllowingCapabilityHandler()},
        "effects": {"fx.compensate": effects},
        "reducers": {"tests.arnold.patterns._fixtures:reducer": _SimpleReducerHandler()},
        "controls": {
            "ctrl.promote": _KindControlHandler("supervisor_promotion"),
            "overlay.dynamic": _KindControlHandler("overlay"),
        },
    }
    if allow_authority:
        kwargs["authorities"] = {"resume-auth": authorities}
    return ExecutionRegistries(**kwargs)


def _child_manifest() -> Any:
    from arnold.manifest import WorkflowManifest, WorkflowNode

    return WorkflowManifest(
        id="canonical-megaplan-child",
        nodes=(WorkflowNode(id="child1", kind="noop"),),
    )


def _deterministic_backend(fake_backend_factory, tmp_path: Path, **kwargs: Any) -> Any:
    now = datetime(2026, 6, 22, 0, 0, 0, tzinfo=timezone.utc)
    defaults = {
        "run_id": "run:canonical-gate",
        "now": now,
        "init_ts": now,
        "branch_selections": {
            "branch-decide": "branch-decide-branch-plan",
            "override-decide": "override-decide-override-primary",
            "tourney-judge": "tourney-judge-tourney-winner",
            "tourney-tiebreak-1": "tourney-tiebreak-1-tourney-winner",
        },
        "child_behaviors": {
            "fan:child:0": {"value": "a"},
            "fan:child:1": {"value": "b"},
        },
        "reducer_results": {"tests.arnold.patterns._fixtures:reducer": {"joined": "ab"}},
        "child_manifests": {"inner": _child_manifest()},
        "subpipeline_results": {
            "inner": NodeOutcome(state=NodeState.COMPLETED, outputs={"child": True})
        },
    }
    defaults.update(kwargs)
    return fake_backend_factory(**defaults)


def test_compiles_and_matches_fixture_shapes() -> None:
    manifest = canonical_execution_manifest()
    shapes = _load_shapes()
    manifest_node_ids = {node.id for node in manifest.nodes}

    for shape_name, shape in shapes.items():
        expected = _shape_nodes(shape)
        missing = expected - manifest_node_ids
        assert not missing, f"shape {shape_name!r} missing nodes: {missing}"


def test_manifest_runtime_payload_preserves_legacy_route_fields() -> None:
    data = json.loads(GOLDEN_RUNTIME_PATH.read_text(encoding="utf-8"))

    assert data["schema_version"] == "workflow-manifest-runtime.golden.v1"
    assert data["source_golden"] == "tests/fixtures/golden/pipeline_fresh_run.json"
    assert data["routes"] == [
        "prep",
        "plan",
        "critique",
        "gate",
        "revise",
        "finalize",
        "execute",
        "review",
    ]
    assert "seed" not in data["normalization"]

    manifest_contract = data["manifest_contract"]
    assert manifest_contract["schema_version"] == "arnold.workflow.manifest.v1"
    assert manifest_contract["id"] == data["case"]
    route_steps = {
        metadata["behavioral_step"]
        for item in manifest_contract["nodes"] + manifest_contract["edges"]
        if (metadata := item.get("route_metadata", {})).get("behavioral_step")
    }
    assert set(data["routes"]) <= route_steps


def test_happy_path_runs_to_completion(tmp_path: Path, fake_backend_factory) -> None:
    manifest = canonical_execution_manifest()
    backend = _deterministic_backend(fake_backend_factory, tmp_path)

    result = run(
        manifest,
        artifact_root=tmp_path,
        registries=_build_registries(),
        backend=backend,
    )

    assert result.state is ExecutionState.COMPLETED
    events = read_event_journal(tmp_path)
    kinds = [e.kind for e in events]

    assert "manifest_loaded" in kinds
    assert "manifest_validated" in kinds
    assert "node_completed" in kinds
    assert "branch_selected" in kinds
    assert "loop_iteration" in kinds
    assert "reducer_completed" in kinds
    assert "subpipeline_entered" in kinds
    assert "subpipeline_exited" in kinds
    assert "budget_reserved" in kinds
    assert "budget_settled" in kinds
    assert "control_transition" in kinds

    completed = {
        e.payload["node_ref"]
        for e in events
        if e.kind == "node_completed" and e.payload.get("child_key") is None
    }
    assert "tourney-winner" in completed
    assert "overlay-extra" in completed
    assert "promote-supervisor" in completed

    loop_iterations = [
        e.payload["iteration"]
        for e in events
        if e.kind == "loop_iteration" and e.payload.get("node_ref") == "loop"
    ]
    assert loop_iterations == [1, 2, 3]


def test_replay_from_three_distinct_resume_cursors(tmp_path: Path, fake_backend_factory) -> None:
    manifest = canonical_execution_manifest()
    registries = _build_registries()
    cursor_points = ["start", "gate", "tourney-judge"]

    for idx, node_id in enumerate(cursor_points):
        root = tmp_path / f"replay-{idx}"
        backend = _deterministic_backend(
            fake_backend_factory,
            root,
            run_id=f"run:replay-{idx}",
        )
        cursor = manifest_coordinate(manifest.id, manifest.manifest_hash or "").cursor(
            node=NodeRef(node_id),
            reentry_id="resume",
        )

        result = run(
            manifest,
            artifact_root=root,
            registries=registries,
            backend=backend,
            resume_cursor=cursor,
        )

        assert result.state is ExecutionState.COMPLETED, f"resume from {node_id} failed"
        events = read_event_journal(root)
        assert any(e.kind == "node_resumed" for e in events)


def test_resume_from_suspension_cursor(tmp_path: Path, fake_backend_factory) -> None:
    manifest = canonical_execution_manifest()
    registries = _build_registries()

    # First run suspends at gate.
    suspending_backend = _deterministic_backend(
        fake_backend_factory,
        tmp_path,
        node_behaviors={"gate": NodeOutcome(state=NodeState.SUSPENDED, suspension_route_id="operator")},
    )
    first = run(
        manifest,
        artifact_root=tmp_path,
        registries=registries,
        backend=suspending_backend,
    )
    assert first.state is ExecutionState.SUSPENDED
    assert first.resume_cursor is not None
    assert first.resume_cursor.node is not None
    assert first.resume_cursor.node.id == "gate"

    events_before = read_event_journal(tmp_path)
    assert any(e.kind == "node_suspended" for e in events_before)
    assert not any(
        e.kind == "node_started" and e.payload.get("node_ref") == "revise"
        for e in events_before
    )

    # Resume with a backend that completes gate.
    resuming_backend = _deterministic_backend(
        fake_backend_factory,
        tmp_path,
        run_id="run:resume",
        reentry_id="resume",
    )
    second = run(
        manifest,
        artifact_root=tmp_path,
        registries=registries,
        backend=resuming_backend,
        resume_cursor=first.resume_cursor,
    )

    assert second.state is ExecutionState.COMPLETED
    events_after = read_event_journal(tmp_path)
    assert any(e.kind == "node_resumed" for e in events_after)
    assert any(
        e.kind == "node_started" and e.payload.get("node_ref") == "revise"
        for e in events_after
    )


def test_execute_authority_failure_on_resume(tmp_path: Path, fake_backend_factory) -> None:
    manifest = canonical_execution_manifest()
    registries = _build_registries()
    cursor = manifest_coordinate(manifest.id, manifest.manifest_hash or "").cursor(
        node=NodeRef("gate"),
        reentry_id="resume",
    )
    backend = _deterministic_backend(
        fake_backend_factory,
        tmp_path,
        authority_results={"resume": False},
    )

    result = run(
        manifest,
        artifact_root=tmp_path,
        registries=registries,
        backend=backend,
        resume_cursor=cursor,
    )

    assert result.state is ExecutionState.QUARANTINED
    events = read_event_journal(tmp_path)
    assert any(e.kind == "resume_rejected" for e in events)
    assert any(d.code == "authority_denied" for d in result.diagnostics)


def test_compensation_on_failure(tmp_path: Path, fake_backend_factory) -> None:
    manifest = canonical_execution_manifest()
    handler = _RecordingEffectHandler()
    registries = ExecutionRegistries(
        capabilities={"human:operator": _AllowingCapabilityHandler()},
        effects={"fx.compensate": handler},
        reducers={"tests.arnold.patterns._fixtures:reducer": _SimpleReducerHandler()},
        controls={
            "ctrl.promote": _KindControlHandler("supervisor_promotion"),
            "overlay.dynamic": _KindControlHandler("overlay"),
        },
        authorities={"resume-auth": _AllowingAuthorityHandler()},
    )
    backend = _deterministic_backend(
        fake_backend_factory,
        tmp_path,
        node_behaviors={"overlay": NodeOutcome(state=NodeState.FAILED, error="overlay boom")},
    )

    result = run(
        manifest,
        artifact_root=tmp_path,
        registries=registries,
        backend=backend,
    )

    assert result.state is ExecutionState.FAILED
    events = read_event_journal(tmp_path)
    assert any(e.kind == "compensation_started" for e in events)
    assert any(e.kind == "compensation_step_completed" for e in events)
    assert any(e.kind == "compensation_completed" for e in events)
    assert any(call[0] == "fx.compensate" for call in handler.calls)


def test_escalation_on_retry_exhaustion(tmp_path: Path, fake_backend_factory) -> None:
    manifest = canonical_execution_manifest()
    registries = _build_registries()
    backend = _deterministic_backend(
        fake_backend_factory,
        tmp_path,
        node_behaviors={"retry-fragile": NodeOutcome(state=NodeState.FAILED, error="boom")},
    )

    result = run(
        manifest,
        artifact_root=tmp_path,
        registries=registries,
        backend=backend,
    )

    assert result.state is ExecutionState.FAILED
    events = read_event_journal(tmp_path)
    escalation = [e for e in events if e.kind == "escalation_routed"]
    assert len(escalation) == 1
    assert escalation[0].payload["source_node"] == "retry-fragile"
    completed = {
        e.payload["node_ref"]
        for e in events
        if e.kind == "node_completed" and e.payload.get("child_key") is None
    }
    assert "escalate-supervisor" in completed


def test_supervisor_promotion_control_transition(tmp_path: Path, fake_backend_factory) -> None:
    manifest = canonical_execution_manifest()
    registries = _build_registries()
    backend = _deterministic_backend(fake_backend_factory, tmp_path)

    run(
        manifest,
        artifact_root=tmp_path,
        registries=registries,
        backend=backend,
    )

    events = read_event_journal(tmp_path)
    promotions = [
        e for e in events
        if e.kind == "control_transition" and e.payload.get("kind") == "supervisor_promotion"
    ]
    assert len(promotions) == 1
    assert promotions[0].payload["source_node"] == "gate"
    assert promotions[0].payload["target_node"] == "promote-supervisor"


def test_dynamic_overlay_routes_isolated_target(tmp_path: Path, fake_backend_factory) -> None:
    manifest = canonical_execution_manifest()
    original_hash = manifest.manifest_hash
    registries = _build_registries()
    backend = _deterministic_backend(fake_backend_factory, tmp_path)

    result = run(
        manifest,
        artifact_root=tmp_path,
        registries=registries,
        backend=backend,
    )

    assert result.state is ExecutionState.COMPLETED
    assert manifest.manifest_hash == original_hash
    events = read_event_journal(tmp_path)
    overlays = [
        e for e in events
        if e.kind == "control_transition" and e.payload.get("kind") == "overlay"
    ]
    assert len(overlays) == 1
    assert overlays[0].payload["source_node"] == "overlay"
    assert overlays[0].payload["target_node"] == "overlay-extra"


def test_deterministic_final_state(tmp_path: Path, fake_backend_factory) -> None:
    manifest = canonical_execution_manifest()
    registries = _build_registries()

    def _run(root: Path) -> Any:
        backend = _deterministic_backend(
            fake_backend_factory,
            root,
            run_id="run:determinism",
        )
        return run(
            manifest,
            artifact_root=root,
            registries=registries,
            backend=backend,
        )

    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    result_a = _run(root_a)
    result_b = _run(root_b)

    assert result_a.state is ExecutionState.COMPLETED
    assert result_b.state is ExecutionState.COMPLETED
    assert result_a.outputs == result_b.outputs

    events_a = read_event_journal(root_a)
    events_b = read_event_journal(root_b)
    assert len(events_a) == len(events_b)

    def _normalize(event: Any) -> dict[str, Any]:
        return {
            "family": event.family.value,
            "kind": event.kind,
            "payload": {
                **event.payload,
                "scope_stack": tuple(event.payload.get("scope_stack", ())),
            },
        }

    assert [_normalize(e) for e in events_a] == [_normalize(e) for e in events_b]
