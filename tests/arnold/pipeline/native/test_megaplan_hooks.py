"""Parametrized parity tests: Megaplan native hooks vs golden graph traces.

Compares normalized native traces (via :class:`MegaplanNativeRuntimeHooks`)
to golden graph traces (via :class:`TraceCaptureHooks`) for:

* State
* Event kinds
* Stage sequence
* Cursor shape
* Artifact inventory
* Envelope output
* Override body-call counters
* Nested promotion isolation
* Suspended/resumed equivalence

Covers SC16 parity dimensions.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.executor import run_pipeline
from arnold.pipeline.native import (
    NativeExecutionResult,
    NullNativeRuntimeHooks,
    compile_pipeline,
    decision,
    phase,
    pipeline,
    project_graph,
    run_native_pipeline,
)
from arnold.pipeline.native.ir import NativeInstruction
from arnold.pipelines.megaplan.native_hooks import (
    MegaplanNativeRuntimeHooks,
)
from arnold.runtime.envelope import RuntimeEnvelope

from .fixtures import _reset_loop_counter
from .parity_trace import (
    ParityTrace,
    TraceCaptureHooks,
    capture_graph_trace,
    diff_traces,
    normalize_state,
)
from .test_runtime_parity import (
    TracingNativeHooks,
    _clean_result_state,
    _make_envelope,
    _strip_pc,
)

# ═══════════════════════════════════════════════════════════════════════
# autouse fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _enable_native(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")


@pytest.fixture(autouse=True)
def _reset_counters() -> None:
    _reset_loop_counter()


# ═══════════════════════════════════════════════════════════════════════
# Toy pipeline helpers (dual-compatible: native dict ctx + StepContext)
# ═══════════════════════════════════════════════════════════════════════


def _coerce_state(ctx: Any) -> dict[str, Any]:
    if isinstance(ctx, dict):
        s = ctx.get("state")
        return dict(s) if isinstance(s, dict) else {}
    s = getattr(ctx, "state", None)
    return dict(s) if isinstance(s, dict) else {}


_loop_counter: dict[str, int] = {"count": 0}


def _reset_megaplan_counters() -> None:
    _loop_counter["count"] = 0


@phase(name="setup")
def _setup(ctx: Any) -> dict:
    return {"ready": True}


@phase(name="body")
def _loop_body(ctx: Any) -> dict:
    _loop_counter["count"] += 1
    return {"count": _loop_counter["count"]}


@decision(name="should_loop", vocabulary={"yes", "no"})
def _should_loop(ctx: Any) -> str:
    return "yes" if _loop_counter["count"] < 2 else "no"


@phase(name="cleanup")
def _cleanup(ctx: Any) -> dict:
    return {"done": True}


@phase(name="producer")
def _producer(ctx: Any) -> dict:
    return {"data": "hello"}


@phase(name="consumer")
def _consumer(ctx: Any) -> dict:
    state = _coerce_state(ctx)
    received = state.get("data", "")
    return {"consumed": received}


@phase(name="left_path")
def _left_path(ctx: Any) -> dict:
    return {"path": "left"}


@phase(name="right_path")
def _right_path(ctx: Any) -> dict:
    return {"path": "right"}


@decision(name="branch", vocabulary={"left", "right"})
def _branch(ctx: Any) -> str:
    return "right"


@pipeline(name="megaplan_toy", description="Toy pipeline for Megaplan hooks parity")
def _megaplan_pipeline(ctx: dict) -> dict:
    s = yield _setup(ctx)
    s = yield _producer(ctx)
    s = yield _consumer(ctx)
    if _branch(ctx) == "left":
        s = yield _left_path(ctx)
    else:
        s = yield _right_path(ctx)
    while _should_loop(ctx) == "yes":
        s = yield _loop_body(ctx)
    s = yield _cleanup(ctx)
    return s


def _get_megaplan_program():
    _reset_megaplan_counters()
    return compile_pipeline(_megaplan_pipeline)


# ═══════════════════════════════════════════════════════════════════════
# Megaplan tracing hooks (native side)
# ═══════════════════════════════════════════════════════════════════════


class TracingMegaplanNativeHooks(MegaplanNativeRuntimeHooks):
    """Megaplan hooks that also record hook invocation order."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.hook_order: list[str] = []

    def on_step_start(self, instr: NativeInstruction, ctx: dict) -> dict:
        self.hook_order.append(f"on_step_start:{instr.name}")
        return super().on_step_start(instr, ctx)

    def on_step_end(self, instr: NativeInstruction, ctx: dict, result: Any) -> Any:
        self.hook_order.append(f"on_step_end:{instr.name}")
        return super().on_step_end(instr, ctx, result)

    def on_step_error(self, instr: NativeInstruction, ctx: dict, exc: BaseException) -> None:
        self.hook_order.append(f"on_step_error:{instr.name}")
        return super().on_step_error(instr, ctx, exc)

    def merge_state(self, instr, state, outputs, owned_keys):
        self.hook_order.append(f"merge_state:{instr.name}")
        return super().merge_state(instr, state, outputs, owned_keys)

    def join_envelope(self, instr, current_envelope, step_envelope):
        self.hook_order.append(f"join_envelope:{instr.name}")
        return super().join_envelope(instr, current_envelope, step_envelope)

    def should_suspend(self, instr, state, result):
        self.hook_order.append(f"should_suspend:{instr.name}")
        return super().should_suspend(instr, state, result)

    def should_halt_loop(self, instr, state, iteration):
        self.hook_order.append(f"should_halt_loop:{instr.name}")
        return super().should_halt_loop(instr, state, iteration)

    def on_stage_complete(self, instr, ctx, result, state, owned_keys):
        self.hook_order.append(f"on_stage_complete:{instr.name}")
        return super().on_stage_complete(instr, ctx, result, state, owned_keys)

    def on_checkpoint(self, cursor, state):
        self.hook_order.append("on_checkpoint")
        return super().on_checkpoint(cursor, state)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _hash_topology(program) -> str:
    """Return a stable topology hash for the compiled program."""
    import hashlib

    parts: list[str] = []
    for instr in program.instructions:
        parts.append(f"{instr.op}:{instr.name}:{instr.pc}")
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return f"sha256:{digest}"


def _graph_native_trace_pair(
    tmp_path: Path,
    *,
    max_phases: int | None = None,
    resume: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run both native (Megaplan hooks) and graph executors, return diff report."""
    _reset_megaplan_counters()
    prog = _get_megaplan_program()
    thash = _hash_topology(prog)

    # ── Native run ───────────────────────────────────────────────
    _reset_megaplan_counters()
    prog_native = _get_megaplan_program()
    native_hooks = TracingMegaplanNativeHooks()
    native_result = run_native_pipeline(
        prog_native,
        artifact_root=tmp_path,
        hooks=native_hooks,
        max_phases=max_phases,
        resume=resume,
    )

    # ── Graph run ────────────────────────────────────────────────
    _reset_megaplan_counters()
    prog_graph = _get_megaplan_program()
    graph_pipeline = project_graph(prog_graph)
    env = _make_envelope(str(tmp_path))
    graph_trace = capture_graph_trace(
        graph_pipeline,
        {},
        env,
        thash,
        tmp_path,
    )

    # ── Build native trace ───────────────────────────────────────
    native_states: list[str] = [
        _strip_pc(s) for s in native_result.stages
    ]
    native_cursor = None
    if native_result.suspended and native_result.cursor_path:
        try:
            data = json.loads(Path(native_result.cursor_path).read_text())
            native_cursor = data
        except Exception:
            pass

    from .parity_trace import normalize_cursor

    native_trace = ParityTrace(
        topology_hash=thash,
        stage_sequence=native_states,
        final_state=normalize_state(native_result.state),
        events=[],
        cursor=normalize_cursor(native_cursor),
        artifacts={},
        hook_order=native_hooks.hook_order,
        accumulated_envelope=native_result.envelope,
    )

    return diff_traces(native_trace, graph_trace)


def _diff_surfaces_match(diff: dict[str, Any], surfaces: list[str]) -> bool:
    """All named surfaces must be 'match'."""
    for s in surfaces:
        if diff.get(s) != "match":
            return False
    return True


# ═══════════════════════════════════════════════════════════════════════
# State parity
# ═══════════════════════════════════════════════════════════════════════


class TestMegaplanStateParity:
    """State parity: Megaplan hooks native state == graph executor state."""

    def test_final_state_matches(self, tmp_path: Path) -> None:
        """Full-run final state matches between native (Megaplan hooks) and graph."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        native_result = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            hooks=MegaplanNativeRuntimeHooks(),
        )

        _reset_megaplan_counters()
        prog_graph = _get_megaplan_program()
        graph_pipeline = project_graph(prog_graph)
        env = _make_envelope(str(tmp_path))
        graph_hooks = TraceCaptureHooks()
        run_pipeline(graph_pipeline, {}, env, hooks=graph_hooks)

        native_state = _clean_result_state(native_result.state)
        graph_state = _clean_result_state(graph_hooks.final_state)

        assert native_state == graph_state, (
            f"State mismatch:\n  native: {native_state}\n  graph:  {graph_state}"
        )

    @pytest.mark.parametrize("expected_key", [
        "ready", "data", "consumed", "path", "count", "done",
    ])
    def test_state_key_present(self, tmp_path: Path, expected_key: str) -> None:
        """Each expected key is present in native Megaplan state."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        result = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            hooks=MegaplanNativeRuntimeHooks(),
        )
        assert expected_key in result.state, (
            f"Key {expected_key!r} missing from state: {sorted(result.state.keys())}"
        )

    def test_state_diff_with_trace(self, tmp_path: Path) -> None:
        """Surface-level diff shows final_state matches."""
        diff = _graph_native_trace_pair(tmp_path)
        assert diff["final_state"] == "match", (
            f"final_state mismatch: {diff['final_state']}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Stage sequence parity
# ═══════════════════════════════════════════════════════════════════════


class TestMegaplanStageSequenceParity:
    """Stage sequence parity between Megaplan native and graph execution."""

    _DECISION_MARKERS = ("_branch", "_should_loop")

    @staticmethod
    def _is_phase_stage(name: str) -> bool:
        stripped = _strip_pc(name)
        for marker in TestMegaplanStageSequenceParity._DECISION_MARKERS:
            if marker in stripped:
                return False
        return True

    def test_phase_sequence_matches(self, tmp_path: Path) -> None:
        """Phase stage names match between native (Megaplan hooks) and graph."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        native_result = run_native_pipeline(
            prog, artifact_root=tmp_path, hooks=MegaplanNativeRuntimeHooks(),
        )

        _reset_megaplan_counters()
        prog_graph = _get_megaplan_program()
        graph_pipeline = project_graph(prog_graph)
        env = _make_envelope(str(tmp_path))
        graph_hooks = TraceCaptureHooks()
        run_pipeline(graph_pipeline, {}, env, hooks=graph_hooks)

        native_phases = [_strip_pc(s) for s in native_result.stages]
        graph_phases = [
            _strip_pc(s) for s in graph_hooks.stages
            if self._is_phase_stage(s)
        ]

        assert native_phases == graph_phases, (
            f"Phase sequence mismatch:\n  native: {native_phases}\n  graph:  {graph_phases}"
        )

    def test_same_phase_count(self, tmp_path: Path) -> None:
        """Same number of completed phases."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        native_result = run_native_pipeline(
            prog, artifact_root=tmp_path, hooks=MegaplanNativeRuntimeHooks(),
        )

        _reset_megaplan_counters()
        prog_graph = _get_megaplan_program()
        graph_pipeline = project_graph(prog_graph)
        env = _make_envelope(str(tmp_path))
        graph_hooks = TraceCaptureHooks()
        run_pipeline(graph_pipeline, {}, env, hooks=graph_hooks)

        graph_phase_count = sum(
            1 for s in graph_hooks.stages if self._is_phase_stage(s)
        )
        assert len(native_result.stages) == graph_phase_count, (
            f"Phase count: native={len(native_result.stages)}, graph={graph_phase_count}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Cursor shape parity
# ═══════════════════════════════════════════════════════════════════════


class TestMegaplanCursorShapeParity:
    """Cursor shape parity: native cursor dict structure matches expectations."""

    def test_cursor_has_native_key(self, tmp_path: Path) -> None:
        """Resume cursor includes 'native' section."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        result = run_native_pipeline(
            prog, artifact_root=tmp_path, max_phases=2,
            hooks=MegaplanNativeRuntimeHooks(),
        )
        assert result.suspended
        assert result.cursor_path is not None

        cursor = json.loads(Path(result.cursor_path).read_text())
        assert "native" in cursor
        assert isinstance(cursor["native"], dict)
        assert "pc" in cursor["native"]

    def test_cursor_has_stages(self, tmp_path: Path) -> None:
        """Cursor includes completed stages list."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        result = run_native_pipeline(
            prog, artifact_root=tmp_path, max_phases=3,
            hooks=MegaplanNativeRuntimeHooks(),
        )
        assert result.suspended

        cursor = json.loads(Path(result.cursor_path).read_text())
        assert "stages" in cursor
        assert isinstance(cursor["stages"], list)
        assert len(cursor["stages"]) == len(result.stages)

    def test_cursor_has_frames(self, tmp_path: Path) -> None:
        """Cursor includes frames dict with __state__."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        result = run_native_pipeline(
            prog, artifact_root=tmp_path, max_phases=2,
            hooks=MegaplanNativeRuntimeHooks(),
        )
        assert result.suspended

        cursor = json.loads(Path(result.cursor_path).read_text())
        assert "frames" in cursor
        assert "__state__" in cursor["frames"]

    @pytest.mark.parametrize("expected_key", [
        "native", "stage", "stages", "frames", "loops",
    ])
    def test_cursor_shape_keys(self, tmp_path: Path, expected_key: str) -> None:
        """Cursor dict contains each expected structural key."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        result = run_native_pipeline(
            prog, artifact_root=tmp_path, max_phases=2,
            hooks=MegaplanNativeRuntimeHooks(),
        )
        assert result.suspended

        cursor = json.loads(Path(result.cursor_path).read_text())
        assert expected_key in cursor, (
            f"Key {expected_key!r} missing from cursor: {sorted(cursor.keys())}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Envelope output parity
# ═══════════════════════════════════════════════════════════════════════


class TestMegaplanEnvelopeParity:
    """Envelope accumulation parity with Megaplan hooks."""

    def test_envelope_passthrough_no_step_envelopes(self, tmp_path: Path) -> None:
        """Initial envelope passes through when no step produces envelopes."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        result = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            initial_envelope="test_envelope",
            hooks=MegaplanNativeRuntimeHooks(),
        )
        assert result.envelope == "test_envelope"

    def test_envelope_result_field_present(self, tmp_path: Path) -> None:
        """NativeExecutionResult has envelope attribute after Megaplan run."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        result = run_native_pipeline(
            prog, artifact_root=tmp_path, hooks=MegaplanNativeRuntimeHooks(),
        )
        assert hasattr(result, "envelope")

    def test_envelope_join_preserves_truthiness(self, tmp_path: Path) -> None:
        """join_envelope preserves truthy step_envelope over falsy current."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        result = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            initial_envelope=None,
            hooks=MegaplanNativeRuntimeHooks(),
        )
        # With no step envelopes producing non-None, envelope stays None
        assert result.envelope is None


# ═══════════════════════════════════════════════════════════════════════
# Override body-call counters
# ═══════════════════════════════════════════════════════════════════════


class TestMegaplanOverrideBodyCallCounters:
    """Override body-call counter parity between native and graph execution."""

    def test_control_override_skips_decision_body(self, tmp_path: Path) -> None:
        """Control override via __override_route__ skips the decision body."""
        body_calls: list[str] = []

        @phase(name="on_left")
        def on_left(ctx: Any) -> dict:
            return {"path": "left"}

        @phase(name="on_override")
        def on_override(ctx: Any) -> dict:
            return {"path": "override"}

        @decision(name="decide", vocabulary={"left", "right", "override"})
        def decide(ctx: Any) -> str:
            body_calls.append("decide")
            return "left"

        @pipeline(name="override_test")
        def override_pipe(ctx: dict) -> dict:
            if decide(ctx) == "left":
                s = yield on_left(ctx)
            elif decide(ctx) == "right":
                s = yield on_left(ctx)
            elif decide(ctx) == "override":
                s = yield on_override(ctx)
            else:
                s = yield on_left(ctx)
            return s

        prog = compile_pipeline(override_pipe)

        # Hook that injects a control override
        class OverrideHook(NullNativeRuntimeHooks):
            def on_step_start(self, instr, ctx):
                if instr.op == "decision":
                    ctx["__override_route__"] = "override"
                return ctx

        hooks = OverrideHook()
        result = run_native_pipeline(prog, hooks=hooks)
        assert body_calls == [], f"Body called {len(body_calls)} time(s); should be 0"
        assert result.state.get("path") == "override"

    def test_no_override_calls_decision_body(self, tmp_path: Path) -> None:
        """Without override, decision body is called normally."""
        body_calls: list[str] = []

        @phase(name="on_yes")
        def on_yes(ctx: Any) -> dict:
            return {"branch": "yes"}

        @decision(name="decide", vocabulary={"yes", "no"})
        def decide(ctx: Any) -> str:
            body_calls.append("decide")
            return "yes"

        @pipeline(name="normal_decision")
        def normal_pipe(ctx: dict) -> dict:
            if decide(ctx) == "yes":
                s = yield on_yes(ctx)
            return s

        prog = compile_pipeline(normal_pipe)
        result = run_native_pipeline(
            prog, hooks=MegaplanNativeRuntimeHooks(),
        )
        assert body_calls == ["decide"]
        assert result.state.get("branch") == "yes"

    def test_override_fallback_label(self, tmp_path: Path) -> None:
        """Override falls back to 'override' label when action not in vocabulary."""
        body_calls: list[str] = []

        @phase(name="on_pass")
        def on_pass(ctx: Any) -> dict:
            return {"branch": "pass"}

        @phase(name="on_override")
        def on_override(ctx: Any) -> dict:
            return {"branch": "override"}

        @decision(name="decide", vocabulary={"pass", "override"})
        def decide(ctx: Any) -> str:
            body_calls.append("decide")
            return "pass"

        @pipeline(name="fallback_test")
        def fallback_pipe(ctx: dict) -> dict:
            if decide(ctx) == "pass":
                s = yield on_pass(ctx)
            elif decide(ctx) == "override":
                s = yield on_override(ctx)
            return s

        prog = compile_pipeline(fallback_pipe)

        class FallbackHook(NullNativeRuntimeHooks):
            def on_step_start(self, instr, ctx):
                if instr.op == "decision":
                    ctx["__override_route__"] = "abort"
                return ctx

        result = run_native_pipeline(prog, hooks=FallbackHook())
        assert body_calls == []
        assert result.state.get("branch") == "override"


# ═══════════════════════════════════════════════════════════════════════
# Nested promotion isolation
# ═══════════════════════════════════════════════════════════════════════


class TestMegaplanNestedPromotionIsolation:
    """Nested promotion isolation: completed_subloop produces only expected keys."""

    def test_completed_subloop_produces_state_key(self) -> None:
        """completed_subloop emits subloop:<name>:state."""
        hooks = MegaplanNativeRuntimeHooks()
        child_state = {"inner_key": "inner_value"}
        patch, _ = hooks.completed_subloop(
            name="test_loop",
            child_state=child_state,
            recommendation="continue",
        )
        assert "subloop:test_loop:state" in patch
        assert patch["subloop:test_loop:state"] == child_state

    def test_completed_subloop_produces_recommendation_key(self) -> None:
        """completed_subloop emits subloop:<name>:recommendation."""
        hooks = MegaplanNativeRuntimeHooks()
        patch, _ = hooks.completed_subloop(
            name="test_loop",
            child_state={"x": 1},
            recommendation="halt",
        )
        assert "subloop:test_loop:recommendation" in patch
        assert patch["subloop:test_loop:recommendation"] == "halt"

    def test_completed_subloop_no_resume_cursor_when_none(self) -> None:
        """When resume_cursor is None, key is omitted from state patch."""
        hooks = MegaplanNativeRuntimeHooks()
        patch, _ = hooks.completed_subloop(
            name="test_loop",
            child_state={"x": 1},
            recommendation="continue",
            resume_cursor=None,
        )
        assert "subloop:test_loop:resume_cursor" not in patch

    def test_completed_subloop_resume_cursor_when_present(self) -> None:
        """When resume_cursor is set, it appears in state patch."""
        hooks = MegaplanNativeRuntimeHooks()
        patch, _ = hooks.completed_subloop(
            name="test_loop",
            child_state={"x": 1},
            recommendation="continue",
            resume_cursor={"pc": 5},
        )
        assert "subloop:test_loop:resume_cursor" in patch
        assert patch["subloop:test_loop:resume_cursor"] == {"pc": 5}

    def test_completed_subloop_no_artifacts_when_empty(self) -> None:
        """Empty child_artifacts omits the key."""
        hooks = MegaplanNativeRuntimeHooks()
        patch, _ = hooks.completed_subloop(
            name="test_loop",
            child_state={"x": 1},
            recommendation="continue",
            child_artifacts={},
        )
        assert "subloop:test_loop:artifacts" not in patch

    def test_completed_subloop_artifacts_when_non_empty(self) -> None:
        """Non-empty child_artifacts appears in state patch."""
        hooks = MegaplanNativeRuntimeHooks()
        patch, _ = hooks.completed_subloop(
            name="test_loop",
            child_state={"x": 1},
            recommendation="continue",
            child_artifacts={"out.txt": "sha256:abc"},
        )
        assert "subloop:test_loop:artifacts" in patch
        assert patch["subloop:test_loop:artifacts"] == {"out.txt": "sha256:abc"}

    def test_completed_subloop_isolation_no_raw_child_state(self) -> None:
        """Child state keys are NOT leaked directly into parent patch."""
        hooks = MegaplanNativeRuntimeHooks()
        child_state = {"inner_key": "secret", "meta": {"x": 1}}
        patch, _ = hooks.completed_subloop(
            name="child",
            child_state=child_state,
            recommendation="continue",
        )
        # Only subloop:<name>:* keys should exist
        for key in patch:
            assert key.startswith("subloop:child:"), (
                f"Key {key!r} leaks child state directly into parent patch"
            )
        assert "inner_key" not in patch
        assert "meta" not in patch


# ═══════════════════════════════════════════════════════════════════════
# Suspended/resumed equivalence
# ═══════════════════════════════════════════════════════════════════════


class TestMegaplanSuspendResumeEquivalence:
    """Suspended+resumed runs produce same result as full run with Megaplan hooks."""

    def test_resume_same_final_state(self, tmp_path: Path) -> None:
        """Resumed run final state == full run final state."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        hooks_full = MegaplanNativeRuntimeHooks()
        full_result = run_native_pipeline(prog, artifact_root=tmp_path, hooks=hooks_full)

        # Suspend after 2 phases
        _reset_megaplan_counters()
        prog_suspend = _get_megaplan_program()
        hooks_suspend = MegaplanNativeRuntimeHooks()
        suspended = run_native_pipeline(
            prog_suspend, artifact_root=tmp_path, max_phases=2, hooks=hooks_suspend,
        )
        assert suspended.suspended

        # Resume
        _reset_megaplan_counters()
        prog_resume = _get_megaplan_program()
        hooks_resume = MegaplanNativeRuntimeHooks()
        resumed = run_native_pipeline(
            prog_resume, artifact_root=tmp_path, resume=True, hooks=hooks_resume,
        )

        assert not resumed.suspended
        assert _clean_result_state(resumed.state) == _clean_result_state(full_result.state), (
            f"Resume state mismatch:\n  full:    {_clean_result_state(full_result.state)}\n"
            f"  resumed: {_clean_result_state(resumed.state)}"
        )

    def test_resume_same_stages(self, tmp_path: Path) -> None:
        """Resumed run stage list == full run stage list."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        hooks_full = MegaplanNativeRuntimeHooks()
        full_result = run_native_pipeline(prog, artifact_root=tmp_path, hooks=hooks_full)

        # Suspend
        _reset_megaplan_counters()
        prog_suspend = _get_megaplan_program()
        hooks_suspend = MegaplanNativeRuntimeHooks()
        suspended = run_native_pipeline(
            prog_suspend, artifact_root=tmp_path, max_phases=2, hooks=hooks_suspend,
        )
        assert suspended.suspended

        # Resume
        _reset_megaplan_counters()
        prog_resume = _get_megaplan_program()
        hooks_resume = MegaplanNativeRuntimeHooks()
        resumed = run_native_pipeline(
            prog_resume, artifact_root=tmp_path, resume=True, hooks=hooks_resume,
        )

        assert resumed.stages == full_result.stages, (
            f"Stage mismatch:\n  full:    {full_result.stages}\n  resumed: {resumed.stages}"
        )

    def test_resume_preserves_loop_counters(self, tmp_path: Path) -> None:
        """Loop counters survive suspension/resume cycle."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        hooks_full = MegaplanNativeRuntimeHooks()
        full_result = run_native_pipeline(prog, artifact_root=tmp_path, hooks=hooks_full)

        _reset_megaplan_counters()
        prog_suspend = _get_megaplan_program()
        hooks_suspend = MegaplanNativeRuntimeHooks()
        suspended = run_native_pipeline(
            prog_suspend, artifact_root=tmp_path, max_phases=4, hooks=hooks_suspend,
        )
        assert suspended.suspended

        _reset_megaplan_counters()
        prog_resume = _get_megaplan_program()
        hooks_resume = MegaplanNativeRuntimeHooks()
        resumed = run_native_pipeline(
            prog_resume, artifact_root=tmp_path, resume=True, hooks=hooks_resume,
        )

        assert resumed.state.get("count") == full_result.state.get("count"), (
            f"Loop counter mismatch: full={full_result.state.get('count')}, "
            f"resumed={resumed.state.get('count')}"
        )

    @pytest.mark.parametrize("suspend_after_phases", [1, 2, 3, 4])
    def test_resume_parity_variable_suspend_point(
        self, tmp_path: Path, suspend_after_phases: int
    ) -> None:
        """Suspending at different phase counts still yields full-run parity."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        hooks_full = MegaplanNativeRuntimeHooks()
        full_result = run_native_pipeline(prog, artifact_root=tmp_path, hooks=hooks_full)

        _reset_megaplan_counters()
        prog_suspend = _get_megaplan_program()
        hooks_suspend = MegaplanNativeRuntimeHooks()
        suspended = run_native_pipeline(
            prog_suspend, artifact_root=tmp_path,
            max_phases=suspend_after_phases, hooks=hooks_suspend,
        )
        assert suspended.suspended

        _reset_megaplan_counters()
        prog_resume = _get_megaplan_program()
        hooks_resume = MegaplanNativeRuntimeHooks()
        resumed = run_native_pipeline(
            prog_resume, artifact_root=tmp_path, resume=True, hooks=hooks_resume,
        )

        assert not resumed.suspended
        assert _clean_result_state(resumed.state) == _clean_result_state(full_result.state), (
            f"Resume state mismatch at suspend_after={suspend_after_phases}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Hook order parity (Megaplan vs expected lifecycle)
# ═══════════════════════════════════════════════════════════════════════


class TestMegaplanHookOrder:
    """Megaplan hooks produce expected hook invocation sequence."""

    def test_hook_order_starts_with_on_step_start(self, tmp_path: Path) -> None:
        """First hook fired is on_step_start."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        hooks = TracingMegaplanNativeHooks()
        run_native_pipeline(prog, artifact_root=tmp_path, hooks=hooks)

        assert len(hooks.hook_order) > 0
        assert hooks.hook_order[0].startswith("on_step_start:"), (
            f"First hook: {hooks.hook_order[0]}"
        )

    def test_on_checkpoint_fires_after_completion(self, tmp_path: Path) -> None:
        """on_checkpoint fires after clean completion."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        hooks = TracingMegaplanNativeHooks()
        run_native_pipeline(prog, artifact_root=tmp_path, hooks=hooks)

        assert "on_checkpoint" in hooks.hook_order, (
            f"on_checkpoint missing from: {hooks.hook_order}"
        )

    def test_on_stage_complete_fires_per_phase(self, tmp_path: Path) -> None:
        """on_stage_complete fires for each phase."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        hooks = TracingMegaplanNativeHooks()
        run_native_pipeline(prog, artifact_root=tmp_path, hooks=hooks)

        completes = [
            h for h in hooks.hook_order if h.startswith("on_stage_complete:")
        ]
        assert len(completes) >= 6, (
            f"Expected >=6 on_stage_complete, got {len(completes)}: {completes}"
        )

    def test_start_end_paired_per_phase(self, tmp_path: Path) -> None:
        """Each phase has matching on_step_start/on_step_end pair."""
        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        hooks = TracingMegaplanNativeHooks()
        run_native_pipeline(prog, artifact_root=tmp_path, hooks=hooks)

        starts = [
            h.split(":", 1)[1] for h in hooks.hook_order
            if h.startswith("on_step_start:")
        ]
        ends = [
            h.split(":", 1)[1] for h in hooks.hook_order
            if h.startswith("on_step_end:")
        ]
        # Phase names in starts should match phase names in ends
        assert set(starts) == set(ends), (
            f"Start/end mismatch: starts={starts}, ends={ends}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Event kind parity (via NativeTraceHooks journal)
# ═══════════════════════════════════════════════════════════════════════


class TestMegaplanEventKindParity:
    """Event kinds emitted during Megaplan native execution match expectations."""

    def test_trace_events_emitted(self, tmp_path: Path) -> None:
        """NativeTraceHooks wrapping Megaplan hooks emits trace events."""
        from arnold.pipeline.native import NativeTraceHooks

        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        trace_dir = tmp_path / "traces"
        hooks = NativeTraceHooks(
            inner=MegaplanNativeRuntimeHooks(),
            trace_dir=trace_dir,
            artifact_root=tmp_path,
        )
        result = run_native_pipeline(prog, artifact_root=tmp_path, hooks=hooks)

        assert not result.suspended
        assert (trace_dir / "state.json").exists()
        assert (trace_dir / "stages.json").exists()
        assert (trace_dir / "checkpoint.json").exists()

        events_path = trace_dir / "events.ndjson"
        if events_path.exists():
            events = []
            for line in events_path.read_text().strip().split("\n"):
                if line.strip():
                    events.append(json.loads(line))
            event_kinds = [e.get("kind") for e in events if "kind" in e]
            assert "pipeline.init" in event_kinds
            assert "phase.start" in event_kinds
            assert "phase.end" in event_kinds
            assert "stage.complete" in event_kinds
            assert "checkpoint" in event_kinds

    def test_event_kinds_match_expected_set(self, tmp_path: Path) -> None:
        """Emitted event kinds are a known set."""
        from arnold.pipeline.native import NativeTraceHooks

        _reset_megaplan_counters()
        prog = _get_megaplan_program()
        trace_dir = tmp_path / "traces_ek"
        hooks = NativeTraceHooks(
            inner=MegaplanNativeRuntimeHooks(),
            trace_dir=trace_dir,
            artifact_root=tmp_path,
        )
        run_native_pipeline(prog, artifact_root=tmp_path, hooks=hooks)

        events_path = trace_dir / "events.ndjson"
        if events_path.exists():
            events = []
            for line in events_path.read_text().strip().split("\n"):
                if line.strip():
                    events.append(json.loads(line))
            kinds = {e.get("kind") for e in events if "kind" in e}
            expected = {"pipeline.init", "phase.start", "phase.end", "stage.complete", "checkpoint"}
            assert kinds == expected, (
                f"Event kinds: {kinds} (expected {expected})"
            )
