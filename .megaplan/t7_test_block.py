
# ── T7: Control override resolver tests ──────────────────────────────


class TestControlOverrideResolver:
    """resolve_control_override priority: termination > transition > recovery."""

    def test_empty_entries_returns_none(self) -> None:
        """Empty control entries produce None."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        assert resolve_control_override([]) is None

    def test_single_termination_wins(self) -> None:
        """A single termination override resolves correctly."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "abort", "kind": "termination"},
        ])
        assert result == "abort"

    def test_single_transition_wins(self) -> None:
        """A single transition override resolves correctly."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "force_proceed", "kind": "transition"},
        ])
        assert result == "force_proceed"

    def test_single_recovery_wins(self) -> None:
        """A single recovery override resolves correctly."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "recover_blocked", "kind": "recovery"},
        ])
        assert result == "recover_blocked"

    def test_termination_beats_transition(self) -> None:
        """Termination (abort) has higher priority than transition (replan)."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "replan", "kind": "transition"},
            {"action": "abort", "kind": "termination"},
        ])
        assert result == "abort", (
            "termination must beat transition regardless of insertion order"
        )

    def test_termination_beats_transition_reverse_order(self) -> None:
        """Termination wins even when listed after transition entries."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "abort", "kind": "termination"},
            {"action": "replan", "kind": "transition"},
        ])
        assert result == "abort"

    def test_transition_beats_recovery(self) -> None:
        """Transition (force_proceed) has higher priority than recovery."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "recover_blocked", "kind": "recovery"},
            {"action": "force_proceed", "kind": "transition"},
        ])
        assert result == "force_proceed", (
            "transition must beat recovery regardless of insertion order"
        )

    def test_termination_beats_all(self) -> None:
        """Termination wins when all three kinds are present."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "resume_clarify", "kind": "recovery"},
            {"action": "force_proceed", "kind": "transition"},
            {"action": "abort", "kind": "termination"},
        ])
        assert result == "abort"

    def test_same_kind_first_wins(self) -> None:
        """Within the same kind, the first entry wins (stable sort)."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "force_proceed", "kind": "transition"},
            {"action": "replan", "kind": "transition"},
        ])
        assert result == "force_proceed", (
            "same-kind tie must preserve insertion order (first wins)"
        )

    def test_unknown_kind_falls_to_lowest_priority(self) -> None:
        """An unknown kind is treated as lowest priority (99)."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "unknown_thing", "kind": "unknown"},
            {"action": "recover_blocked", "kind": "recovery"},
        ])
        assert result == "recover_blocked", (
            "known recovery kind must beat unknown kind"
        )

    def test_resolve_control_override_in_catalog_integration(self) -> None:
        """resolve_control_override accepts entries shaped like on_step_start produces."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )
        from arnold.pipelines.megaplan.planning.operations import override_catalog

        catalog = override_catalog()
        entries = [
            {
                "action": "recover_blocked",
                "catalog_action": "recover-blocked",
                "kind": catalog["recover-blocked"]["kind"],
                "entry": {"action": "recover-blocked", "reason": "test"},
            },
            {
                "action": "abort",
                "catalog_action": "abort",
                "kind": catalog["abort"]["kind"],
                "entry": {"action": "abort", "reason": "test"},
            },
        ]
        result = resolve_control_override(entries, catalog)
        assert result == "abort", (
            "abort (termination) must beat recover-blocked (recovery)"
        )


class TestControlOverrideIntegration:
    """Integration: control overrides skip decision bodies via on_step_start."""

    @staticmethod
    def _make_ctx(
        overrides: list[dict[str, Any]] | None = None,
        *,
        extra_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a context dict with override entries in ``state.meta.overrides``."""
        state: dict[str, Any] = dict(extra_state or {})
        state.setdefault("meta", {})["overrides"] = (
            list(overrides) if overrides is not None else []
        )
        return {"state": state}

    @staticmethod
    def _make_instr(name: str = "test_phase"):
        from arnold.pipeline.native.ir import NativeInstruction

        return NativeInstruction(
            op="phase", name=name, pc=0, func=None, next_pc=None,
        )

    def test_control_override_sets_ctx_flag(self) -> None:
        """on_step_start sets __override_route__ in ctx for control overrides."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[{"action": "abort", "reason": "test"}],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert result.get("__override_route__") == "abort", (
            "termination override must set __override_route__ in ctx"
        )

    def test_transition_override_sets_ctx_flag(self) -> None:
        """on_step_start sets __override_route__ for transition overrides."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[{"action": "force-proceed", "reason": "test"}],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert result.get("__override_route__") == "force_proceed", (
            "transition override must set __override_route__ in ctx"
        )

    def test_recovery_override_sets_ctx_flag(self) -> None:
        """on_step_start sets __override_route__ for recovery overrides."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[{"action": "recover-blocked", "reason": "test"}],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert result.get("__override_route__") == "recover_blocked", (
            "recovery override must set __override_route__ in ctx"
        )

    def test_control_override_priority_in_ctx(self) -> None:
        """When multiple control overrides present, highest priority wins in ctx."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[
                {"action": "recover-blocked", "reason": "low"},
                {"action": "abort", "reason": "high"},
                {"action": "force-proceed", "reason": "mid"},
            ],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert result.get("__override_route__") == "abort", (
            "abort (termination) must beat force-proceed (transition) "
            "and recover-blocked (recovery)"
        )

    def test_additive_overrides_still_applied_with_control_override(self) -> None:
        """Additive overrides are applied even when a control override is present."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[
                {"action": "add-note", "note": "before abort", "source": "user"},
                {"action": "abort", "reason": "stop"},
                {"action": "set-profile", "profile": "thorough"},
            ],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)

        assert result.get("__override_route__") == "abort"

        state = result["state"]
        notes = state["meta"]["notes"]
        assert len(notes) == 1
        assert notes[0]["note"] == "before abort"
        assert state["config"]["profile"] == "thorough"

    def test_no_control_override_when_only_additive(self) -> None:
        """__override_route__ is NOT set when only additive overrides present."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[
                {"action": "add-note", "note": "just a note"},
                {"action": "set-profile", "profile": "thorough"},
            ],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert "__override_route__" not in result, (
            "__override_route__ must not be set when no control overrides present"
        )

    def test_control_override_preserves_existing_state(self) -> None:
        """State keys are preserved when a control override is resolved."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[{"action": "abort", "reason": "test"}],
            extra_state={"existing_key": "existing_val"},
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert result["state"]["existing_key"] == "existing_val", (
            "existing state keys must survive control override resolution"
        )
        assert result.get("__override_route__") == "abort"


class TestControlOverrideRuntimeIntegration:
    """End-to-end: control overrides short-circuit decision bodies at runtime.

    These tests prove the full resolver priority chain:
        halt > override > decision > normal
    """

    @pytest.fixture(autouse=True)
    def _enable_native_runtime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")

    def test_override_beats_decision_body(self) -> None:
        """When a control override is pending, the decision body is skipped.

        This proves: override > decision.
        """
        from arnold.pipeline.native import (
            NativeInstruction,
            NativeProgram,
            run_native_pipeline,
        )
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        def decision_func(ctx):
            return "then"

        def then_phase(ctx):
            ctx["state"]["branch"] = "then"
            return {"branch": "then"}

        def else_phase(ctx):
            ctx["state"]["branch"] = "else"
            return {"branch": "else"}

        instrs: list[NativeInstruction] = [
            NativeInstruction(
                op="decision", name="gate", pc=0,
                func=decision_func,
                branches={"abort": 1, "then": 2, "else": 3},
            ),
            NativeInstruction(
                op="phase", name="abort_target", pc=1,
                func=then_phase, next_pc=4,
            ),
            NativeInstruction(
                op="phase", name="then_target", pc=2,
                func=then_phase, next_pc=4,
            ),
            NativeInstruction(
                op="phase", name="else_target", pc=3,
                func=else_phase, next_pc=4,
            ),
            NativeInstruction(op="halt", name="end", pc=4, func=None),
        ]
        program = NativeProgram(
            name="test_override_beats_decision",
            instructions=tuple(instrs),
        )

        initial_state = {
            "meta": {
                "overrides": [{"action": "abort", "reason": "test"}],
            },
        }
        hooks = MegaplanNativeHooks()

        result = run_native_pipeline(
            program,
            initial_state=initial_state,
            hooks=hooks,
        )

        assert result.state.get("branch") == "then", (
            "override (abort) should route to abort_target (pc=1), "
            f"not to then_target (pc=2). state={result.state}"
        )

    def test_decision_beats_normal_when_no_override(self) -> None:
        """When no control override is present, the decision body runs normally.

        This proves: decision > normal.
        """
        from arnold.pipeline.native import (
            NativeInstruction,
            NativeProgram,
            run_native_pipeline,
        )
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        def decision_func(ctx):
            return "then"

        def then_phase(ctx):
            ctx["state"]["branch"] = "then"
            return {"branch": "then"}

        def else_phase(ctx):
            ctx["state"]["branch"] = "else"
            return {"branch": "else"}

        instrs: list[NativeInstruction] = [
            NativeInstruction(
                op="decision", name="gate", pc=0,
                func=decision_func,
                branches={"then": 1, "else": 2},
            ),
            NativeInstruction(
                op="phase", name="then_target", pc=1,
                func=then_phase, next_pc=3,
            ),
            NativeInstruction(
                op="phase", name="else_target", pc=2,
                func=else_phase, next_pc=3,
            ),
            NativeInstruction(op="halt", name="end", pc=3, func=None),
        ]
        program = NativeProgram(
            name="test_decision_beats_normal",
            instructions=tuple(instrs),
        )

        initial_state: dict[str, Any] = {}
        hooks = MegaplanNativeHooks()

        result = run_native_pipeline(
            program,
            initial_state=initial_state,
            hooks=hooks,
        )

        assert result.state.get("branch") == "then", (
            "decision body should run normally when no override is present"
        )

    def test_halt_beats_override_in_loop_guard(self) -> None:
        """When should_halt_loop fires, it beats any pending control override.

        This proves: halt > override.
        """
        from arnold.pipeline.native import (
            NativeInstruction,
            NativeLoopGuard,
            NativeProgram,
            run_native_pipeline,
        )
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        loop_count = {"count": 0}

        def loop_guard(ctx):
            loop_count["count"] += 1
            if loop_count["count"] <= 3:
                return "continue"
            return "exit"

        def body_phase(ctx):
            ctx["state"]["body_ran"] = ctx["state"].get("body_ran", 0) + 1
            return {}

        def exit_phase(ctx):
            ctx["state"]["exited"] = True
            return {}

        instrs: list[NativeInstruction] = [
            NativeInstruction(
                op="decision", name="loop_guard", pc=0,
                func=loop_guard,
                branches={"continue": 1, "exit": 2},
            ),
            NativeInstruction(
                op="phase", name="body", pc=1,
                func=body_phase, next_pc=0,
            ),
            NativeInstruction(
                op="phase", name="exit_target", pc=2,
                func=exit_phase, next_pc=3,
            ),
            NativeInstruction(op="halt", name="end", pc=3, func=None),
        ]
        program = NativeProgram(
            name="test_halt_beats_override",
            instructions=tuple(instrs),
            loop_guards=[
                NativeLoopGuard(
                    guard=loop_guard,
                    body=body_phase,
                    name="loop_guard",
                ),
            ],
        )

        class HaltThenOverrideHooks(MegaplanNativeHooks):
            def should_halt_loop(self, instr, state, iteration):
                if iteration >= 1:
                    return True, "halt_on_first_iteration"
                return False, None

        hooks = HaltThenOverrideHooks()

        initial_state = {
            "meta": {
                "overrides": [{"action": "force-proceed", "reason": "test"}],
            },
        }

        result = run_native_pipeline(
            program,
            initial_state=initial_state,
            hooks=hooks,
        )

        body_runs = result.state.get("body_ran", 0)
        assert body_runs == 1, (
            f"halt should beat override: expected 1 body run, got {body_runs}. "
            f"state={result.state}"
        )

    def test_decisions_without_overrides_work_normally(self) -> None:
        """Decision execution with Megaplan hooks but no overrides works."""
        from arnold.pipeline.native import (
            NativeInstruction,
            NativeProgram,
            run_native_pipeline,
        )
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        def decision_func(ctx):
            return "yes"

        def yes_phase(ctx):
            ctx["state"]["branch"] = "yes"
            return {"branch": "yes"}

        def no_phase(ctx):
            ctx["state"]["branch"] = "no"
            return {"branch": "no"}

        instrs: list[NativeInstruction] = [
            NativeInstruction(
                op="decision", name="gate", pc=0,
                func=decision_func,
                branches={"yes": 1, "no": 2},
            ),
            NativeInstruction(
                op="phase", name="yes_target", pc=1,
                func=yes_phase, next_pc=3,
            ),
            NativeInstruction(
                op="phase", name="no_target", pc=2,
                func=no_phase, next_pc=3,
            ),
            NativeInstruction(op="halt", name="end", pc=3, func=None),
        ]
        program = NativeProgram(
            name="test_normal_decision",
            instructions=tuple(instrs),
        )

        hooks = MegaplanNativeHooks()
        result = run_native_pipeline(
            program,
            initial_state={},
            hooks=hooks,
        )

        assert result.state.get("branch") == "yes"

    def test_override_beats_decision_priority_with_multiple_overrides(self) -> None:
        """Multiple overrides: highest priority (termination) beats decision.

        This is the combined priority test: override (termination) > decision.
        """
        from arnold.pipeline.native import (
            NativeInstruction,
            NativeProgram,
            run_native_pipeline,
        )
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        def decision_func(ctx):
            return "then"

        def abort_target(ctx):
            ctx["state"]["branch"] = "abort"
            return {"branch": "abort"}

        def force_target(ctx):
            ctx["state"]["branch"] = "force"
            return {"branch": "force"}

        def then_target(ctx):
            ctx["state"]["branch"] = "then"
            return {"branch": "then"}

        instrs: list[NativeInstruction] = [
            NativeInstruction(
                op="decision", name="gate", pc=0,
                func=decision_func,
                branches={"abort": 1, "force_proceed": 2, "then": 3},
            ),
            NativeInstruction(
                op="phase", name="abort_target", pc=1,
                func=abort_target, next_pc=4,
            ),
            NativeInstruction(
                op="phase", name="force_target", pc=2,
                func=force_target, next_pc=4,
            ),
            NativeInstruction(
                op="phase", name="then_target", pc=3,
                func=then_target, next_pc=4,
            ),
            NativeInstruction(op="halt", name="end", pc=4, func=None),
        ]
        program = NativeProgram(
            name="test_priority_chain",
            instructions=tuple(instrs),
        )

        hooks = MegaplanNativeHooks()
        initial_state = {
            "meta": {
                "overrides": [
                    {"action": "force-proceed", "reason": "low"},
                    {"action": "abort", "reason": "high"},
                ],
            },
        }

        result = run_native_pipeline(
            program,
            initial_state=initial_state,
            hooks=hooks,
        )

        assert result.state.get("branch") == "abort", (
            f"termination (abort) must beat transition (force-proceed). "
            f"state={result.state}"
        )


# ── helper ────────────────────────────────────────────────────────────

import contextlib
import os as _os


@contextlib.contextmanager
def _env_var(name: str, value: str):
    """Temporarily set an environment variable, restoring the original."""
    old = _os.environ.get(name)
    _os.environ[name] = value
    try:
        yield
    finally:
        if old is None:
            _os.environ.pop(name, None)
        else:
            _os.environ[name] = old
