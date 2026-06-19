from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.executor import run_pipeline
from arnold.pipeline.hooks import NullExecutorHooks
from arnold.pipeline.native.compiler import compile_pipeline
from arnold.pipeline.native.runtime import run_native_pipeline
from arnold.pipeline.topology import compute_topology_hash
from arnold.pipeline.types import PipelineVerdict, StepContext, StepResult
from arnold.pipelines.megaplan.pipeline import (
    _build_legacy_graph_pipeline,
    build_pipeline,
    megaplan,
)
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.event_journal import NdjsonEventJournal, read_event_journal
from arnold.runtime.wal_fold import fold_journal, last_state_snapshot_projector
from tests.arnold.pipeline.native.parity_trace import (
    ParityTrace,
    diff_traces,
    inventory_artifacts,
    normalize_cursor,
    normalize_events,
    normalize_state,
)


EXPECTED_MEGAPLAN_TOPOLOGY_HASH = (
    "sha256:f11cd2e61fdb8fcb8aac558db6ceb5aef2a936cd2a58c0277a7e45523512ba30"
)

_PAYLOAD_KEY_BY_STAGE = {
    "prep": "prep_payload",
    "plan": "plan_payload",
    "critique": "critique_payload",
    "gate": "gate_payload",
    "revise": "revise_payload",
    "finalize": "finalize_payload",
    "execute": "execute_payload",
    "review": "review_payload",
    "tiebreaker": "tiebreaker_payload",
}

_NEXT_BY_STAGE = {
    "prep": "pass",
    "plan": "critique",
    "critique": "gate",
    "revise": "critique",
    "finalize": "execute",
    "execute": "review",
    "review": "halt",
    "tiebreaker": "proceed",
}


@dataclass
class _Scenario:
    name: str
    gate_labels: list[str]
    tiebreaker_labels: list[str] = field(default_factory=list)
    calls: dict[str, int] = field(default_factory=dict)

    def next_call(self, stage: str) -> int:
        call_index = self.calls.get(stage, 0) + 1
        self.calls[stage] = call_index
        return call_index

    def next_gate_label(self) -> str:
        if not self.gate_labels:
            return "proceed"
        return self.gate_labels.pop(0)

    def next_tiebreaker_label(self) -> str:
        if not self.tiebreaker_labels:
            return "proceed"
        return self.tiebreaker_labels.pop(0)


class _DeterministicMegaplanStep:
    name: str
    kind = "produce"
    prompt_key = None
    slot = None
    produces = ()
    consumes = ()

    def __init__(self, stage: str, scenario: _Scenario) -> None:
        self.name = stage
        self._scenario = scenario

    def run(self, ctx: Any) -> StepResult:
        artifact_root = _artifact_root(ctx)
        call_index = self._scenario.next_call(self.name)
        artifact_path = artifact_root / self.name / "payload.json"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(
            json.dumps(
                {
                    "call": call_index,
                    "scenario": self._scenario.name,
                    "stage": self.name,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        payload_key = _PAYLOAD_KEY_BY_STAGE[self.name]
        payload: dict[str, Any] = {
            "call": call_index,
            "scenario": self._scenario.name,
            "stage": self.name,
        }
        next_label = _NEXT_BY_STAGE.get(self.name, "halt")
        verdict = None
        if self.name == "gate":
            next_label = self._scenario.next_gate_label()
            if next_label in {"iterate", "proceed", "tiebreaker", "escalate"}:
                payload["recommendation"] = next_label
                verdict = PipelineVerdict(score=1.0, recommendation=next_label)
            else:
                payload["next"] = next_label
        elif self.name == "tiebreaker":
            next_label = self._scenario.next_tiebreaker_label()
            payload["recommendation"] = next_label
            verdict = PipelineVerdict(score=1.0, recommendation=next_label)

        return StepResult(
            outputs={payload_key: payload},
            verdict=verdict,
            next=next_label,
        )


def _artifact_root(ctx: Any) -> Path:
    if isinstance(ctx, dict):
        return Path(str(ctx["artifact_root"]))
    if hasattr(ctx, "artifact_root"):
        return Path(str(ctx.artifact_root))
    # Megaplan StepContext uses ``plan_dir`` instead of ``artifact_root``.
    if hasattr(ctx, "plan_dir"):
        return Path(str(ctx.plan_dir))
    raise AttributeError(
        f"Cannot determine artifact root from context {type(ctx).__name__!r}"
    )


def _install_steps(monkeypatch: pytest.MonkeyPatch, scenario: _Scenario) -> None:
    from arnold.pipelines.megaplan import pipeline as pipeline_module

    for class_name, stage in (
        ("PrepStep", "prep"),
        ("PlanStep", "plan"),
        ("CritiqueStep", "critique"),
        ("GateStep", "gate"),
        ("ReviseStep", "revise"),
        ("FinalizeStep", "finalize"),
        ("ExecuteStep", "execute"),
        ("ReviewStep", "review"),
        ("TiebreakerStep", "tiebreaker"),
    ):
        monkeypatch.setattr(
            pipeline_module,
            class_name,
            lambda stage=stage: _DeterministicMegaplanStep(stage, scenario),
        )


class _TraceGraphHooks(NullExecutorHooks):
    def __init__(self, root: Path) -> None:
        super().__init__()
        self.stage_sequence: list[str] = []
        self.final_state: dict[str, Any] = {}
        self._root = root
        self._journal = NdjsonEventJournal(root)

    def on_stage_complete(
        self,
        stage: Any,
        ctx: StepContext,
        result: StepResult,
        state: Any,
        owned_keys: frozenset[str],
    ) -> None:
        del ctx, result, owned_keys
        if isinstance(state, dict):
            self.final_state = dict(state)
            _write_json(self._root / "state.json", self.final_state)
            self._journal.emit(
                "state_written",
                payload={"stage": stage.name, "state": self.final_state},
                phase=stage.name,
            )
        self.stage_sequence.append(stage.name)


class _TraceNativeHooks:
    def __init__(self, root: Path) -> None:
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeRuntimeHooks

        self._inner = MegaplanNativeRuntimeHooks(plan_dir=str(root))
        self.stage_sequence: list[str] = []
        self.final_state: dict[str, Any] = {}
        self.checkpoint: dict[str, Any] | None = None
        self._root = root
        self._journal = NdjsonEventJournal(root)

    def on_step_start(self, instr: Any, ctx: dict[str, Any]) -> dict[str, Any]:
        return self._inner.on_step_start(instr, ctx)

    def on_step_end(self, instr: Any, ctx: dict[str, Any], result: Any) -> Any:
        return self._inner.on_step_end(instr, ctx, result)

    def on_step_error(self, instr: Any, ctx: dict[str, Any], exc: BaseException) -> None:
        self._inner.on_step_error(instr, ctx, exc)

    def merge_state(
        self,
        instr: Any,
        state: dict[str, Any],
        outputs: dict[str, Any],
        owned_keys: frozenset[str],
    ) -> tuple[dict[str, Any], frozenset[str]]:
        return self._inner.merge_state(instr, state, outputs, owned_keys)

    def join_envelope(self, instr: Any, current_envelope: Any, step_envelope: Any) -> Any:
        return self._inner.join_envelope(instr, current_envelope, step_envelope)

    def should_suspend(
        self,
        instr: Any,
        state: dict[str, Any],
        result: Any,
    ) -> tuple[bool, str | None]:
        return self._inner.should_suspend(instr, state, result)

    def should_halt_loop(
        self,
        instr: Any,
        state: dict[str, Any],
        iteration: int,
    ) -> tuple[bool, str | None]:
        return self._inner.should_halt_loop(instr, state, iteration)

    def on_edge_traverse(
        self,
        instr: Any,
        state: dict[str, Any],
        label: str,
        target_pc: int,
    ) -> None:
        self._inner.on_edge_traverse(instr, state, label, target_pc)

    def resolve_step_io_policy(
        self,
        *,
        instr: Any,
        state: dict[str, Any],
        handoff_value: Any,
        schema_registry: Any = None,
    ) -> Any | None:
        return self._inner.resolve_step_io_policy(
            instr=instr,
            state=state,
            handoff_value=handoff_value,
            schema_registry=schema_registry,
        )

    def on_stage_complete(
        self,
        instr: Any,
        ctx: dict[str, Any],
        result: Any,
        state: dict[str, Any],
        owned_keys: frozenset[str],
    ) -> None:
        del ctx, result, owned_keys
        self.final_state = dict(state)
        _write_json(self._root / "state.json", self.final_state)
        self._journal.emit(
            "state_written",
            payload={"stage": instr.name, "state": self.final_state},
            phase=instr.name,
        )
        self.stage_sequence.append(instr.name)

    def on_checkpoint(self, cursor: dict[str, Any], state: dict[str, Any]) -> None:
        self._inner.on_checkpoint(cursor, state)
        self.checkpoint = dict(cursor)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str),
        encoding="utf-8",
    )


def _read_cursor(root: Path) -> dict[str, Any] | None:
    cursor_path = root / "resume_cursor.json"
    if not cursor_path.exists():
        return None
    return json.loads(cursor_path.read_text(encoding="utf-8"))


def _event_fold(root: Path) -> dict[str, Any]:
    folded = fold_journal(
        read_event_journal(root),
        kind_filter="state_written",
        projector=last_state_snapshot_projector,
        initial={},
    )
    return folded if isinstance(folded, dict) else {}


def _trace_from_root(
    *,
    topology_hash: str,
    stage_sequence: list[str],
    final_state: dict[str, Any],
    root: Path,
) -> ParityTrace:
    return ParityTrace(
        topology_hash=topology_hash,
        stage_sequence=list(stage_sequence),
        final_state=normalize_state(final_state),
        events=normalize_events(read_event_journal(root)),
        cursor=normalize_cursor(_read_cursor(root)),
        artifacts=inventory_artifacts(root),
        hook_order=[],
        accumulated_envelope=None,
    )


def _run_graph_trace(
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scenario_name: str,
    gate_labels: list[str],
    tiebreaker_labels: list[str] | None = None,
) -> ParityTrace:
    root = tmp_path / f"{scenario_name}-graph"
    root.mkdir()
    scenario = _Scenario(
        scenario_name,
        list(gate_labels),
        list(tiebreaker_labels or []),
    )
    _install_steps(monkeypatch, scenario)
    pipeline = build_pipeline()
    hooks = _TraceGraphHooks(root)

    run_pipeline(
        pipeline,
        {"fixture": {"name": scenario_name}},
        RuntimeEnvelope(
            plugin_id="megaplan",
            run_id=f"{scenario_name}-graph",
            artifact_root=str(root),
        ),
        hooks=hooks,
    )

    return _trace_from_root(
        topology_hash=compute_topology_hash(pipeline),
        stage_sequence=hooks.stage_sequence,
        final_state=hooks.final_state,
        root=root,
    )


def _run_native_trace(
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scenario_name: str,
    gate_labels: list[str],
    tiebreaker_labels: list[str] | None = None,
) -> ParityTrace:
    root = tmp_path / f"{scenario_name}-native"
    root.mkdir()
    scenario = _Scenario(
        scenario_name,
        list(gate_labels),
        list(tiebreaker_labels or []),
    )
    _install_steps(monkeypatch, scenario)
    hooks = _TraceNativeHooks(root)

    result = run_native_pipeline(
        compile_pipeline(megaplan),
        artifact_root=root,
        initial_state={"fixture": {"name": scenario_name}},
        initial_envelope=RuntimeEnvelope(
            plugin_id="megaplan",
            run_id=f"{scenario_name}-native",
            artifact_root=str(root),
        ),
        hooks=hooks,
    )

    return _trace_from_root(
        topology_hash=compute_topology_hash(build_pipeline()),
        stage_sequence=hooks.stage_sequence or [_stage_name(s) for s in result.stages],
        final_state=hooks.final_state or result.state,
        root=root,
    )


def _run_native_suspend_resume_trace(
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scenario_name: str,
    gate_labels: list[str],
    max_phases: int,
    tiebreaker_labels: list[str] | None = None,
) -> tuple[ParityTrace, Any, Any, dict[str, Any]]:
    root = tmp_path / f"{scenario_name}-native"
    root.mkdir()
    scenario = _Scenario(
        scenario_name,
        list(gate_labels),
        list(tiebreaker_labels or []),
    )
    _install_steps(monkeypatch, scenario)
    hooks = _TraceNativeHooks(root)
    program = compile_pipeline(megaplan)
    envelope = RuntimeEnvelope(
        plugin_id="megaplan",
        run_id=f"{scenario_name}-native",
        artifact_root=str(root),
    )

    suspended = run_native_pipeline(
        program,
        artifact_root=root,
        initial_state={"fixture": {"name": scenario_name}},
        initial_envelope=envelope,
        hooks=hooks,
        max_phases=max_phases,
    )
    cursor = _read_cursor(root)
    assert cursor is not None

    resumed = run_native_pipeline(
        program,
        artifact_root=root,
        initial_state={"fixture": {"name": "ignored-on-resume"}},
        initial_envelope=envelope,
        hooks=hooks,
        resume=True,
    )

    return (
        _trace_from_root(
            topology_hash=compute_topology_hash(build_pipeline()),
            stage_sequence=hooks.stage_sequence or [_stage_name(s) for s in resumed.stages],
            final_state=hooks.final_state or resumed.state,
            root=root,
        ),
        suspended,
        resumed,
        cursor,
    )


def _stage_name(stage_id: str) -> str:
    parts = stage_id.split("__")
    return parts[-2] if len(parts) >= 3 else stage_id


def _assert_trace_parity(
    *,
    graph: ParityTrace,
    native: ParityTrace,
    expected_stage_sequence: list[str],
    tmp_path: Path,
    scenario_name: str,
) -> None:
    assert graph.topology_hash == EXPECTED_MEGAPLAN_TOPOLOGY_HASH
    assert native.topology_hash == EXPECTED_MEGAPLAN_TOPOLOGY_HASH
    assert graph.topology_hash == compute_topology_hash(_build_legacy_graph_pipeline())

    assert graph.stage_sequence == expected_stage_sequence
    assert native.stage_sequence == expected_stage_sequence

    assert graph.final_state == normalize_state(_event_fold(tmp_path / f"{scenario_name}-graph"))
    assert native.final_state == normalize_state(_event_fold(tmp_path / f"{scenario_name}-native"))

    assert graph.cursor is None
    assert native.cursor is None

    diff = diff_traces(native, graph)
    assert {key: value for key, value in diff.items() if value != "match"} == {}


def _assert_persisted_shape(
    *,
    root: Path,
    trace: ParityTrace,
    terminal_stage: str,
) -> None:
    state_path = root / "state.json"
    assert state_path.exists()
    assert normalize_state(json.loads(state_path.read_text(encoding="utf-8"))) == trace.final_state
    assert normalize_state(_event_fold(root)) == trace.final_state
    assert trace.cursor is None
    assert _read_cursor(root) is None
    assert trace.final_state["gate_payload"]["next"].startswith("override ")
    assert trace.events[-1]["payload"]["stage"] == terminal_stage


@pytest.fixture(autouse=True)
def _enable_native_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")


def test_straight_through_gate_proceed_finalize_execute_review_parity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    graph = _run_graph_trace(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        scenario_name="straight-through",
        gate_labels=["proceed"],
    )
    native = _run_native_trace(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        scenario_name="straight-through",
        gate_labels=["proceed"],
    )

    _assert_trace_parity(
        graph=graph,
        native=native,
        expected_stage_sequence=[
            "prep",
            "plan",
            "critique",
            "gate",
            "finalize",
            "execute",
            "review",
        ],
        tmp_path=tmp_path,
        scenario_name="straight-through",
    )


def test_gate_revise_loop_then_proceed_parity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    graph = _run_graph_trace(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        scenario_name="revise-loop",
        gate_labels=["revise", "proceed"],
    )
    native = _run_native_trace(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        scenario_name="revise-loop",
        gate_labels=["revise", "proceed"],
    )

    _assert_trace_parity(
        graph=graph,
        native=native,
        expected_stage_sequence=[
            "prep",
            "plan",
            "critique",
            "gate",
            "revise",
            "critique",
            "gate",
            "finalize",
            "execute",
            "review",
        ],
        tmp_path=tmp_path,
        scenario_name="revise-loop",
    )


@pytest.mark.parametrize(
    ("scenario_name", "gate_labels", "tiebreaker_labels", "expected_stage_sequence"),
    [
        (
            "tiebreaker-proceed",
            ["tiebreaker"],
            ["proceed"],
            [
                "prep",
                "plan",
                "critique",
                "gate",
                "tiebreaker",
                "finalize",
                "execute",
                "review",
            ],
        ),
        (
            "gate-escalate",
            ["escalate"],
            [],
            [
                "prep",
                "plan",
                "critique",
                "gate",
                "finalize",
                "execute",
                "review",
            ],
        ),
        (
            "tiebreaker-escalate",
            ["tiebreaker"],
            ["escalate"],
            [
                "prep",
                "plan",
                "critique",
                "gate",
                "tiebreaker",
                "finalize",
                "execute",
                "review",
            ],
        ),
    ],
)
def test_tiebreaker_and_escalation_to_finalize_parity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scenario_name: str,
    gate_labels: list[str],
    tiebreaker_labels: list[str],
    expected_stage_sequence: list[str],
) -> None:
    graph = _run_graph_trace(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        scenario_name=scenario_name,
        gate_labels=gate_labels,
        tiebreaker_labels=tiebreaker_labels,
    )
    native = _run_native_trace(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        scenario_name=scenario_name,
        gate_labels=gate_labels,
        tiebreaker_labels=tiebreaker_labels,
    )

    _assert_trace_parity(
        graph=graph,
        native=native,
        expected_stage_sequence=expected_stage_sequence,
        tmp_path=tmp_path,
        scenario_name=scenario_name,
    )


@pytest.mark.parametrize(
    ("scenario_name", "override_label", "expected_stage_sequence", "terminal_stage"),
    [
        (
            "override-force-proceed",
            "override force-proceed",
            [
                "prep",
                "plan",
                "critique",
                "gate",
                "finalize",
                "execute",
                "review",
            ],
            "review",
        ),
        (
            "override-abort",
            "override abort",
            [
                "prep",
                "plan",
                "critique",
                "gate",
            ],
            "gate",
        ),
    ],
)
def test_gate_override_parity_preserves_routing_and_persistence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scenario_name: str,
    override_label: str,
    expected_stage_sequence: list[str],
    terminal_stage: str,
) -> None:
    assert override_label in {"override force-proceed", "override abort"}

    graph = _run_graph_trace(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        scenario_name=scenario_name,
        gate_labels=[override_label],
    )
    native = _run_native_trace(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        scenario_name=scenario_name,
        gate_labels=[override_label],
    )

    _assert_trace_parity(
        graph=graph,
        native=native,
        expected_stage_sequence=expected_stage_sequence,
        tmp_path=tmp_path,
        scenario_name=scenario_name,
    )

    assert graph.final_state["gate_payload"]["next"] == override_label
    assert native.final_state["gate_payload"]["next"] == override_label
    _assert_persisted_shape(
        root=tmp_path / f"{scenario_name}-graph",
        trace=graph,
        terminal_stage=terminal_stage,
    )
    _assert_persisted_shape(
        root=tmp_path / f"{scenario_name}-native",
        trace=native,
        terminal_stage=terminal_stage,
    )


def test_native_suspend_resume_from_stage_boundary_matches_graph_persistence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scenario_name = "suspend-resume"
    expected_stage_sequence = [
        "prep",
        "plan",
        "critique",
        "gate",
        "finalize",
        "execute",
        "review",
    ]

    graph = _run_graph_trace(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        scenario_name=scenario_name,
        gate_labels=["proceed"],
    )
    native, suspended, resumed, suspension_cursor = _run_native_suspend_resume_trace(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        scenario_name=scenario_name,
        gate_labels=["proceed"],
        max_phases=3,
    )

    assert suspended.suspended is True
    assert suspended.pc == suspension_cursor["native"]["pc"]
    assert suspended.state["critique_payload"]["stage"] == "critique"
    assert _stage_name(suspension_cursor["stage"]) == "critique"
    assert _stage_name(suspension_cursor["reentry_stage"]) == "gate"
    assert suspension_cursor["stage_reentry_points"]["critique"] == suspension_cursor[
        "stage"
    ]
    assert suspension_cursor["frames"]["__state__"]["fixture"] == {
        "name": scenario_name
    }

    assert resumed.suspended is False
    assert graph.stage_sequence == expected_stage_sequence
    assert native.stage_sequence == expected_stage_sequence
    assert graph.final_state == native.final_state
    assert resumed.state["fixture"] == {"name": scenario_name}
    assert resumed.state["review_payload"]["stage"] == "review"

    graph_root = tmp_path / f"{scenario_name}-graph"
    native_root = tmp_path / f"{scenario_name}-native"
    assert normalize_state(_event_fold(graph_root)) == graph.final_state
    assert normalize_state(_event_fold(native_root)) == native.final_state
    assert graph.events == native.events
    assert graph.artifacts == native.artifacts

    graph_state_path = graph_root / "state.json"
    native_state_path = native_root / "state.json"
    assert graph_state_path.exists()
    assert native_state_path.exists()
    assert normalize_state(json.loads(graph_state_path.read_text(encoding="utf-8"))) == (
        normalize_state(json.loads(native_state_path.read_text(encoding="utf-8")))
    )
    assert _read_cursor(graph_root) is None
    assert _read_cursor(native_root) == suspension_cursor
