"""Native bundle coverage for the deliberation pipeline."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.executor import run_pipeline, run_pipeline_resume
from arnold.pipeline.hooks import NullExecutorHooks
from arnold.pipeline.native import run_native_pipeline
from arnold.pipeline.native.hooks import NullNativeRuntimeHooks
from arnold.pipeline.native.ir import NativeProgram
from arnold.pipeline.topology import compute_topology_hash
from arnold.pipeline.types import ParallelStage, StepContext, StepResult
from arnold.pipelines.deliberation.pipelines import (
    _native_bundle,
    build_initial_pipeline,
    build_pipeline,
)
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.event_journal import NdjsonEventJournal, read_event_journal
from arnold.runtime.wal_fold import fold_journal, last_state_snapshot_projector
from tests.arnold.pipelines.megaplan.parity_harness import (
    MegaplanParityHarness,
    normalize_cursor_narrow,
    normalize_state_narrow,
)


EXPECTED_STAGE_SEQUENCE: tuple[str, ...] = (
    "question_gen",
    "human_gate",
    "draft_plan",
    "layer_high_panel",
    "layer_high_synth",
    "layer_mid_panel",
    "layer_mid_synth",
    "layer_low_panel",
    "layer_low_synth",
    "final_report",
)

EXPECTED_NATIVE_PHASES: tuple[str, ...] = (
    "question_gen",
    "draft_plan",
    "layer_high_panel",
    "layer_high_synth",
    "layer_mid_panel",
    "layer_mid_synth",
    "layer_low_panel",
    "layer_low_synth",
    "final_report",
)

EXPECTED_DELIBERATION_TOPOLOGY_HASH = (
    "sha256:7c68a095e89feec2286bc337bfb1a9633c1cd602a334023b5b162f4dbbb977df"
)

_CHECKPOINT_SKIP_NAMES = frozenset({
    ".events.init_ts",
    ".events.seq",
    "awaiting_user.json",
    "events.ndjson",
    "resume_cursor.json",
    "state.json",
})

PROFILE: dict[str, Any] = {
    "question_gen": "dummy",
    "draft_plan": "dummy",
    "layer_high_panel": {
        "abstraction_level": "high",
        "panel_personas": ["critic_a", "critic_b"],
    },
    "layer_high_synth": "dummy",
    "layer_mid_panel": {
        "abstraction_level": "mid",
        "panel_personas": ["critic_c"],
    },
    "layer_mid_synth": "dummy",
    "layer_low_panel": {
        "abstraction_level": "low",
        "panel_personas": ["critic_d"],
    },
    "layer_low_synth": "dummy",
    "final_report": "dummy",
}


def _prompt_source(ctx: StepContext, params: Any = None) -> str:
    del ctx, params
    return "{questions}\n{answers}\n{plan}\n{panel_reviews}"


def _worker(
    prompt: str = "",
    step_name: str = "",
    pipeline_name: str = "",
    inputs: dict[str, str] | None = None,
    mode: str = "",
) -> str:
    del prompt, pipeline_name, mode
    inputs = inputs or {}
    if step_name == "question_gen":
        return json.dumps(
            {"questions": [{"q": "What matters?", "rationale": "scope"}]}
        )
    if step_name == "draft_plan":
        assert inputs["answers"].startswith("{")
        return json.dumps(
            {
                "plan_version": 0,
                "sections": [{"title": "Draft", "content": "Do it."}],
            }
        )
    if step_name.endswith("_synth"):
        return json.dumps(
            {
                "plan_version": 1,
                "sections": [{"title": step_name, "content": "Revised."}],
                "changelog": [
                    {
                        "critique": "tighten",
                        "verdict": "accept",
                        "reason": "material",
                        "applied_change": "tightened",
                    }
                ],
            }
        )
    if step_name == "final_report":
        return "# Final report\n"
    return f"review from {step_name}"


def _workers() -> dict[str, Any]:
    return {"dummy": _worker}


def _program() -> NativeProgram:
    program = _native_bundle(
        profile=PROFILE,
        workers=_workers(),
        prompts=_prompt_source,
    )
    assert isinstance(program, NativeProgram)
    return program


@dataclass(frozen=True)
class _DeliberationTrace:
    topology_hash: str
    stage_sequence: tuple[str, ...]
    state: dict[str, Any] | None
    event_fold: dict[str, Any] | None
    resume_cursor: dict[str, Any] | None
    artifacts: dict[str, str]
    awaiting_user: dict[str, Any] | None

    def as_harness_dict(self) -> dict[str, Any]:
        return {
            "topology_hash": self.topology_hash,
            "stage_sequence": list(self.stage_sequence),
            "state": self.state,
            "envelope": None,
            "resume_cursor": self.resume_cursor,
            "artifact_inventory": self.artifacts,
            "event_fold": self.event_fold,
        }


class _GraphTraceHooks(NullExecutorHooks):
    def __init__(self, root: Path, *, suspend_before: str | None = None) -> None:
        super().__init__()
        self.stage_sequence: list[str] = []
        self.final_state: dict[str, Any] | None = None
        self.resume_cursor: dict[str, Any] | None = None
        self._root = root
        self._journal = NdjsonEventJournal(root)
        self._suspend_before = suspend_before
        self._suspended = False

    def should_halt_loop(
        self,
        stage: Any,
        state: dict[str, Any],
        iteration: int,
    ) -> tuple[bool, str | None]:
        del state, iteration
        if (
            self._suspend_before is not None
            and not self._suspended
            and stage.name == self._suspend_before
        ):
            self._suspended = True
            self.resume_cursor = {"stage": stage.name, "input": None}
            _write_json(self._root / "resume_cursor.json", self.resume_cursor)
            return True, f"suspend_before_{stage.name}"
        return False, None

    def on_step_end(
        self,
        stage: Any,
        ctx: StepContext,
        result: StepResult,
    ) -> StepResult:
        del stage, ctx
        contract = result.contract_result
        payload = getattr(contract, "payload", None)
        if not isinstance(payload, dict):
            return result
        label = payload.get("label")
        artifact_path = payload.get("artifact_path")
        if not isinstance(label, str) or not artifact_path:
            return result
        return replace(
            result,
            outputs={**dict(result.outputs), label: str(artifact_path)},
            contract_result=None,
        )

    def join_parallel_results(
        self,
        stage: ParallelStage,
        ctx: StepContext,
        child_results: list[StepResult],
    ) -> StepResult:
        result = super().join_parallel_results(stage, ctx, child_results)
        panel_reviews = _latest_panel_reviews(self._root)
        if panel_reviews is None:
            return result
        return replace(
            result,
            outputs={**dict(result.outputs), "panel_reviews": panel_reviews},
        )

    def on_stage_complete(
        self,
        stage: Any,
        ctx: StepContext,
        result: StepResult,
        state: Any,
        owned_keys: frozenset[str],
    ) -> None:
        del ctx, owned_keys
        json_state = _jsonable(state) if isinstance(state, dict) else {}
        assert isinstance(json_state, dict)
        self.final_state = json_state
        _write_json(self._root / "state.json", json_state)
        self._journal.emit(
            "state_written",
            payload={"stage": stage.name, "state": json_state},
            phase=stage.name,
        )

        skipped_by_pre_stage_suspend = (
            self._suspended
            and self._suspend_before == stage.name
            and not getattr(result, "outputs", {})
        )
        if not skipped_by_pre_stage_suspend:
            self.stage_sequence.append(stage.name)


class _NativeTraceHooks(NullNativeRuntimeHooks):
    def __init__(self, root: Path) -> None:
        super().__init__()
        self.final_state: dict[str, Any] | None = None
        self._root = root
        self._journal = NdjsonEventJournal(root)

    def on_stage_complete(
        self,
        instr: Any,
        ctx: dict[str, Any],
        result: Any,
        state: dict[str, Any],
        owned_keys: frozenset[str],
    ) -> None:
        del ctx, result, owned_keys
        json_state = _jsonable(state)
        assert isinstance(json_state, dict)
        self.final_state = json_state
        _write_json(self._root / "state.json", json_state)
        self._journal.emit(
            "state_written",
            payload={"stage": instr.name, "state": json_state},
            phase=instr.name,
        )

    def on_checkpoint(self, cursor: dict[str, Any], state: dict[str, Any]) -> None:
        json_state = _jsonable(state)
        assert isinstance(json_state, dict)
        self.final_state = json_state
        _write_json(self._root / "state.json", json_state)


def _stage_sequence(result: Any) -> tuple[str, ...]:
    stages: list[str] = []
    for stage_id in result.stages:
        parts = stage_id.split("__")
        if len(parts) >= 2:
            stages.append(parts[-2])
    return tuple(stages)


def _native_stage_sequence(result: Any) -> tuple[str, ...]:
    seq = list(_stage_sequence(result))
    if result.suspended and result.cursor_path:
        cursor_path = Path(result.cursor_path)
        if cursor_path.exists():
            cursor = json.loads(cursor_path.read_text(encoding="utf-8"))
            native = cursor.get("native") if isinstance(cursor, dict) else {}
            if (
                isinstance(native, dict)
                and native.get("suspension_kind") == "human_gate"
                and "human_gate" not in seq
            ):
                seq.append("human_gate")
    return tuple(seq)


def _pipeline() -> Any:
    return build_pipeline(profile=PROFILE, workers=_workers(), prompts=_prompt_source)


def _run_graph_trace(
    root: Path,
    *,
    resume: bool = False,
    resume_choice: str | None = None,
    suspend_before: str | None = None,
) -> _DeliberationTrace:
    root.mkdir(parents=True, exist_ok=True)
    pipeline = _pipeline()
    hooks = _GraphTraceHooks(root, suspend_before=suspend_before)
    envelope = RuntimeEnvelope(
        plugin_id="deliberation_native_parity",
        run_id="graph",
        artifact_root=str(root),
    )

    # Force graph execution for the baseline trace.  Using the process-local
    # kill-switch keeps the runtime-identity marker out of the persisted state
    # so the parity harness compares native and graph state cleanly.
    import os

    previous_runtime = os.environ.get("ARNOLD_PIPELINE_RUNTIME")
    os.environ["ARNOLD_PIPELINE_RUNTIME"] = "graph"
    try:
        if resume:
            if resume_choice is not None:
                _write_graph_resume_choice(root, resume_choice)
            run_pipeline_resume(pipeline, {}, envelope, hooks=hooks)
        else:
            run_pipeline(pipeline, {}, envelope, hooks=hooks)
    finally:
        if previous_runtime is None:
            os.environ.pop("ARNOLD_PIPELINE_RUNTIME", None)
        else:
            os.environ["ARNOLD_PIPELINE_RUNTIME"] = previous_runtime
        awaiting_path = root / "awaiting_user.json"
        cursor_path = root / "resume_cursor.json"
        if awaiting_path.exists() and not cursor_path.exists():
            cursor = {"stage": "human_gate", "input": None}
            _write_json(cursor_path, cursor)
            hooks.resume_cursor = cursor

    cursor_active = hooks.resume_cursor is not None or (root / "awaiting_user.json").exists()
    return _trace_from_root(
        root,
        stage_sequence=tuple(hooks.stage_sequence),
        state=hooks.final_state,
        cursor_active=cursor_active,
    )


def _run_native_trace(
    root: Path,
    *,
    resume: bool = False,
    human_input: dict[str, str] | None = None,
    max_phases: int | None = None,
) -> _DeliberationTrace:
    program = _program()
    root.mkdir(parents=True, exist_ok=True)
    hooks = _NativeTraceHooks(root)

    if resume:
        result = run_native_pipeline(
            program,
            artifact_root=root,
            resume=True,
            human_input=human_input,
            max_phases=max_phases,
            hooks=hooks,
        )
    else:
        result = run_native_pipeline(
            program,
            artifact_root=root,
            initial_state={},
            max_phases=max_phases,
            hooks=hooks,
        )

    return _trace_from_root(
        root,
        stage_sequence=_native_stage_sequence(result),
        state=hooks.final_state or result.state,
        cursor_active=result.suspended,
    )


def _trace_from_root(
    root: Path,
    *,
    stage_sequence: tuple[str, ...],
    state: dict[str, Any] | None,
    cursor_active: bool,
) -> _DeliberationTrace:
    events = read_event_journal(root)
    folded = fold_journal(
        events,
        kind_filter="state_written",
        projector=last_state_snapshot_projector,
        initial=None,
    )
    cursor_path = root / "resume_cursor.json"
    resume_cursor = (
        json.loads(cursor_path.read_text(encoding="utf-8"))
        if cursor_active and cursor_path.exists()
        else None
    )
    awaiting_path = root / "awaiting_user.json"
    awaiting_user = (
        json.loads(awaiting_path.read_text(encoding="utf-8"))
        if awaiting_path.exists()
        else None
    )

    return _DeliberationTrace(
        topology_hash=compute_topology_hash(_pipeline()),
        stage_sequence=stage_sequence,
        state=_normalize_deliberation_state(state, awaiting_active=awaiting_user is not None),
        event_fold=_normalize_deliberation_state(
            folded,
            awaiting_active=awaiting_user is not None,
        ),
        resume_cursor=normalize_cursor_narrow(resume_cursor),
        artifacts=_artifact_inventory(root),
        awaiting_user=awaiting_user,
    )


def _normalize_deliberation_state(
    state: dict[str, Any] | None,
    *,
    awaiting_active: bool,
) -> dict[str, Any] | None:
    normalized = normalize_state_narrow(state)
    if normalized is None:
        return None
    normalized.pop("answers", None)
    if not awaiting_active:
        normalized.pop("_pipeline_paused", None)
        normalized.pop("_pipeline_paused_stage", None)
        normalized.pop("awaiting_user", None)
    return normalized


def _artifact_inventory(root: Path) -> dict[str, str]:
    inventory: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.name in _CHECKPOINT_SKIP_NAMES:
            continue
        rel = path.relative_to(root).as_posix()
        inventory[rel] = f"sha256:{_content_digest(path, root)}"
    return inventory


def _content_digest(path: Path, root: Path) -> str:
    raw = path.read_bytes()
    data = raw.replace(str(root).encode("utf-8"), b"<artifact-root>")
    return hashlib.sha256(data).hexdigest()


def _latest_panel_reviews(root: Path) -> str | None:
    for panel_name in ("layer_low_panel", "layer_mid_panel", "layer_high_panel"):
        panel_root = root / panel_name
        if not panel_root.is_dir():
            continue
        files = sorted(path for path in panel_root.glob("*/v*.md") if path.is_file())
        if not files:
            continue
        return "\n\n".join(path.read_text(encoding="utf-8") for path in files)
    return None


def _write_answers(root: Path) -> None:
    _write_json(
        root / "answers.json",
        {"answers": [{"q": "What matters?", "a": "Reliable resume."}]},
    )


def _write_graph_resume_choice(root: Path, choice: str) -> None:
    awaiting_path = root / "awaiting_user.json"
    awaiting = json.loads(awaiting_path.read_text(encoding="utf-8"))
    awaiting["_resume_choice"] = choice
    awaiting_path.write_text(json.dumps(awaiting, sort_keys=True), encoding="utf-8")

    cursor_path = root / "resume_cursor.json"
    cursor = (
        json.loads(cursor_path.read_text(encoding="utf-8"))
        if cursor_path.exists()
        else {"stage": "human_gate"}
    )
    cursor["input"] = {"answers": str(root / "answers.json")}
    _write_json(cursor_path, cursor)


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _jsonable(dataclasses.asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _with_stage_sequence(
    trace: _DeliberationTrace,
    stage_sequence: tuple[str, ...],
) -> _DeliberationTrace:
    return dataclasses.replace(trace, stage_sequence=stage_sequence)


def _assert_harness_parity(native: _DeliberationTrace, graph: _DeliberationTrace) -> None:
    report = MegaplanParityHarness().compare_native_to_graph(
        native.as_harness_dict(),
        graph.as_harness_dict(),
        topology_hash=EXPECTED_DELIBERATION_TOPOLOGY_HASH,
    )

    assert report["topology_hash"] == "match"
    assert report["stage_sequence"] == "match"
    assert report["state"] == "match"
    assert report["resume_cursor"] == "match"
    assert report["artifact_inventory"] == "match"
    assert report["event_fold"] == "match"


@pytest.fixture(autouse=True)
def _enable_native_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")


class TestDeliberationNativeBundle:
    def test_build_initial_pipeline_attaches_native_program(
        self,
    ) -> None:
        graph = build_initial_pipeline(profile=PROFILE, workers=_workers())
        assert isinstance(graph.native_program, NativeProgram)
        assert [phase.name for phase in graph.native_program.phases] == list(
            EXPECTED_NATIVE_PHASES
        )
        assert tuple(graph.resource_bundles) == ()

        manifest_graph = build_pipeline()
        assert isinstance(manifest_graph.native_program, NativeProgram)
        assert tuple(manifest_graph.resource_bundles) == ()
        assert tuple(manifest_graph.stages) == ("manifest_introspection",)

    def test_human_gate_uses_native_metadata(self) -> None:
        program = _program()
        decision_instr = next(
            instr
            for instr in program.instructions
            if instr.op == "decision" and instr.name == "human_gate"
        )

        assert getattr(decision_instr.func, "__decision_human_gate__") is True
        assert (
            getattr(decision_instr.func, "__decision_artifact_stage__")
            == "question_gen"
        )
        assert getattr(decision_instr.func, "__decision_choices__") == (
            "answers_collected",
        )
        assert decision_instr.branches == {"answers_collected": 2}

    def test_full_graph_native_parity_after_human_gate_resume(
        self,
        tmp_path: Path,
    ) -> None:
        graph_root = tmp_path / "graph"
        native_root = tmp_path / "native"

        graph_suspended = _run_graph_trace(graph_root)
        native_suspended = _run_native_trace(native_root)

        assert graph_suspended.stage_sequence == ("question_gen", "human_gate")
        assert native_suspended.stage_sequence == ("question_gen", "human_gate")
        assert native_suspended.awaiting_user is not None
        assert native_suspended.awaiting_user["stage"] == "human_gate"
        assert native_suspended.awaiting_user["choices"] == ["answers_collected"]
        assert native_suspended.resume_cursor is not None
        native_cursor = native_suspended.resume_cursor
        native_payload = native_cursor.get("native", {})
        assert native_payload["suspension_kind"] == "human_gate"
        assert native_cursor["artifact_stage"] == "question_gen"
        assert native_cursor["choices"] == ["answers_collected"]

        _write_answers(graph_root)
        _write_answers(native_root)

        graph_resumed = _run_graph_trace(
            graph_root,
            resume=True,
            resume_choice="answers_collected",
        )
        native_resumed = _run_native_trace(
            native_root,
            resume=True,
            human_input={"choice": "answers_collected"},
        )
        graph_full = _with_stage_sequence(
            graph_resumed,
            graph_suspended.stage_sequence[:-1] + graph_resumed.stage_sequence,
        )

        assert graph_full.stage_sequence == EXPECTED_STAGE_SEQUENCE
        assert native_resumed.stage_sequence == EXPECTED_STAGE_SEQUENCE
        _assert_harness_parity(native_resumed, graph_full)
        assert (native_root / "draft_plan" / "plan" / "v1.json").exists()
        assert (graph_root / "draft_plan" / "plan" / "v1.json").exists()

    def test_resume_after_layer_panel_barrier_matches_graph_trace(
        self,
        tmp_path: Path,
    ) -> None:
        graph_root = tmp_path / "graph_barrier"
        native_root = tmp_path / "native_barrier"

        graph_initial = _run_graph_trace(graph_root)
        native_initial = _run_native_trace(native_root)
        assert graph_initial.stage_sequence == ("question_gen", "human_gate")
        assert native_initial.stage_sequence == ("question_gen", "human_gate")

        _write_answers(graph_root)
        _write_answers(native_root)

        graph_barrier = _run_graph_trace(
            graph_root,
            resume=True,
            resume_choice="answers_collected",
            suspend_before="layer_high_synth",
        )
        native_barrier = _run_native_trace(
            native_root,
            resume=True,
            human_input={"choice": "answers_collected"},
            max_phases=2,
        )

        assert graph_barrier.stage_sequence == (
            "human_gate",
            "draft_plan",
            "layer_high_panel",
        )
        assert native_barrier.stage_sequence == (
            "question_gen",
            "human_gate",
            "draft_plan",
            "layer_high_panel",
        )
        assert graph_barrier.resume_cursor == {
            "stage": "layer_high_synth",
            "input": None,
        }
        assert native_barrier.resume_cursor is not None
        assert native_barrier.resume_cursor["reentry_stage"].endswith(
            "__layer_high_synth__pc4"
        )
        assert native_barrier.resume_cursor["native"]["pc"] == 4

        graph_resumed = _run_graph_trace(graph_root, resume=True)
        native_resumed = _run_native_trace(native_root, resume=True)
        graph_full = _with_stage_sequence(
            graph_resumed,
            (
                graph_initial.stage_sequence[:-1]
                + graph_barrier.stage_sequence
                + graph_resumed.stage_sequence
            ),
        )

        assert graph_full.stage_sequence == EXPECTED_STAGE_SEQUENCE
        assert native_resumed.stage_sequence == EXPECTED_STAGE_SEQUENCE
        _assert_harness_parity(native_resumed, graph_full)

    def test_native_suspend_resume_reaches_draft_and_preserves_panels(
        self,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "deliberation"
        program = _program()

        first = run_native_pipeline(
            program,
            artifact_root=root,
            initial_state={"meta": {"executor": "native"}},
        )

        assert first.suspended is True
        assert _stage_sequence(first) == ("question_gen",)

        awaiting_path = root / "awaiting_user.json"
        cursor_path = root / "resume_cursor.json"
        awaiting = json.loads(awaiting_path.read_text(encoding="utf-8"))
        cursor = json.loads(cursor_path.read_text(encoding="utf-8"))
        assert awaiting["stage"] == "human_gate"
        assert awaiting["artifact_stage"] == "question_gen"
        assert awaiting["choices"] == ["answers_collected"]
        assert cursor["native"]["suspension_kind"] == "human_gate"

        (root / "answers.json").write_text(
            json.dumps(
                {"answers": [{"q": "What matters?", "a": "Reliable resume."}]}
            ),
            encoding="utf-8",
        )
        awaiting["_resume_choice"] = "answers_collected"
        awaiting_path.write_text(json.dumps(awaiting), encoding="utf-8")

        second = run_native_pipeline(program, artifact_root=root, resume=True)

        assert second.suspended is False
        assert _stage_sequence(second) == EXPECTED_STAGE_SEQUENCE
        assert not awaiting_path.exists()
        assert (root / "draft_plan" / "plan" / "v1.json").exists()
        assert (root / "final_report" / "report" / "v1.md").exists()
        assert (root / "layer_high_panel" / "critic_a" / "v1.md").exists()
        assert (root / "layer_high_panel" / "critic_b" / "v1.md").exists()
        assert (root / "layer_mid_panel" / "critic_c" / "v1.md").exists()
        assert (root / "layer_low_panel" / "critic_d" / "v1.md").exists()
        assert str(second.state["plan"]).endswith("layer_low_synth/plan/v1.json")
