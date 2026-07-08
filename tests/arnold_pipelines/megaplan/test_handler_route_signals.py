from __future__ import annotations

import ast
from pathlib import Path

from arnold_pipelines.megaplan.route_dispatch import resolve_route_target_for_signal
from arnold_pipelines.megaplan.workflows.components import STEP_COMPONENTS_BY_ID

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "plan.py"
GATE_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "gate.py"
TIEBREAKER_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "_tiebreaker_impl.py"
TIEBREAKER_RUNTIME_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "orchestration" / "tiebreaker_runtime.py"
REVIEW_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "review.py"
OVERRIDE_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "override.py"
CRITIQUE_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "critique.py"
SHARED_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "shared.py"
ROUTE_DISPATCH_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "route_dispatch.py"
EXECUTE_HANDLER_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers" / "execute.py"
EXECUTE_BATCH_PATH = REPO_ROOT / "arnold_pipelines" / "megaplan" / "execute" / "batch.py"
FORBIDDEN_TRANSITION_HELPERS = {"workflow_transition", "workflow_next", "_next_progress_step"}
FORBIDDEN_CRITIQUE_HELPERS = {"run_parallel_critique"}
FORBIDDEN_GATE_TARGETS = {"finalize", "revise", "tiebreaker_run", "override", "halt", "gate"}
FORBIDDEN_TIEBREAKER_TARGETS = {"finalize", "critique", "override"}
FORBIDDEN_REVIEW_TARGETS = {"execute", "review", "halt", "finalize", "revise"}
FORBIDDEN_OVERRIDE_TARGETS = {"finalize", "revise", "halt"}
# Typed execute-policy functions that MUST be the sole authorities for
# execute route decisions.  If these imports disappear or are replaced by
# inline literals the checker must reject the change.
REQUIRED_EXECUTE_POLICY_CALLS = {
    "resolve_execute_entry_route",
    "evaluate_destructive_approval",
    "evaluate_no_review_terminal",
}
# Legacy next_step payloads written by the execute handler must be
# translated through these lookup maps or through projection helpers that
# resolve from source/policy metadata — never a bare string literal.
EXECUTE_NEXT_STEP_MAPS = {"_LEGACY_NEXT_STEP", "_NO_REVIEW_NEXT_STEP"}
EXECUTE_NEXT_STEP_PROJECTION_HELPERS = {
    "_blocked_execute_projection",
    "_no_review_terminal_projection",
}
# The batch auto-loop must route all next_step derivations through this
# compatibility mapper.
BATCH_NEXT_STEP_MAPPER = "_legacy_next_step_for_execute_policy"
# Route target strings that must never appear as bare literals in
# execute route-decision code (handler or batch auto-loop).
FORBIDDEN_EXECUTE_ROUTE_TARGETS = {"review", "halt", "finalize", "revise", "override", "plan"}


def _function_node(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {path}")


def _dict_literal_strings(path: Path, name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name and isinstance(node.value, ast.Dict):
                    values: set[str] = set()
                    for value in node.value.values:
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            values.add(value.value)
                    return values
    raise AssertionError(f"{name} not found in {path}")


def _called_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Name):
            names.add(child.func.id)
        elif isinstance(child.func, ast.Attribute):
            names.add(child.func.attr)
    return names


def _string_constants(node: ast.AST) -> set[str]:
    return {
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    }


class TestPrepSignals:
    def test_handle_prep_does_not_pass_explicit_next_step(self) -> None:
        func = _function_node(PLAN_PATH, "handle_prep")
        finish_calls = [
            call for call in ast.walk(func)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "_finish_step"
        ]
        assert finish_calls, "handle_prep must call _finish_step"
        assert all(
            keyword.arg != "next_step" for call in finish_calls for keyword in call.keywords
        )

    def test_handle_prep_avoids_transition_helpers(self) -> None:
        calls = _called_names(_function_node(PLAN_PATH, "handle_prep"))
        assert calls.isdisjoint(FORBIDDEN_TRANSITION_HELPERS)


class TestGateSignals:
    def test_handle_gate_does_not_pass_explicit_next_step(self) -> None:
        func = _function_node(GATE_PATH, "handle_gate")
        finish_calls = [
            call for call in ast.walk(func)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "_finish_step"
        ]
        assert finish_calls, "handle_gate must call _finish_step"
        assert all(
            keyword.arg != "next_step" for call in finish_calls for keyword in call.keywords
        )

    def test_handle_gate_avoids_transition_helpers(self) -> None:
        calls = _called_names(_function_node(GATE_PATH, "handle_gate"))
        assert calls.isdisjoint(FORBIDDEN_TRANSITION_HELPERS)

    def test_gate_route_signal_helper_uses_route_labels_not_targets(self) -> None:
        func = _function_node(GATE_PATH, "_build_gate_route_signal")
        strings = _string_constants(func)
        assert {"blocked_preflight", "escalate"} <= strings
        assert FORBIDDEN_GATE_TARGETS.isdisjoint(strings)


class TestCritiqueSignals:
    def test_handle_critique_avoids_transition_and_fanout_helpers(self) -> None:
        calls = _called_names(_function_node(CRITIQUE_PATH, "handle_critique"))
        assert calls.isdisjoint(FORBIDDEN_TRANSITION_HELPERS | FORBIDDEN_CRITIQUE_HELPERS)

    def test_handle_revise_avoids_transition_helpers(self) -> None:
        calls = _called_names(_function_node(CRITIQUE_PATH, "handle_revise"))
        assert calls.isdisjoint(FORBIDDEN_TRANSITION_HELPERS)


class TestTiebreakerSignals:
    def test_handle_tiebreaker_decide_avoids_transition_helpers(self) -> None:
        calls = _called_names(_function_node(TIEBREAKER_PATH, "handle_tiebreaker_decide"))
        assert calls.isdisjoint(FORBIDDEN_TRANSITION_HELPERS)

    def test_tiebreaker_route_signal_helper_uses_route_labels_not_targets(self) -> None:
        func = _function_node(TIEBREAKER_RUNTIME_PATH, "_route_signal_for_tiebreaker_action")
        strings = _string_constants(func)
        assert {"proceed", "iterate", "escalate"} <= strings
        assert FORBIDDEN_TIEBREAKER_TARGETS.isdisjoint(strings)

    def test_runtime_decide_phase_body_emits_labels_not_parent_targets(self) -> None:
        func = _function_node(TIEBREAKER_RUNTIME_PATH, "handle_tiebreaker_decide")
        strings = _string_constants(func)
        assert {"route_signal", "decision"} <= strings
        assert {"finalize", "critique", "override add-note"}.isdisjoint(strings)


class TestReviewSignals:
    def test_handle_review_avoids_transition_helpers(self) -> None:
        calls = _called_names(_function_node(REVIEW_PATH, "handle_review"))
        assert calls.isdisjoint(FORBIDDEN_TRANSITION_HELPERS)

    def test_review_outcome_resolver_delegates_route_authority_to_policy_helpers(self) -> None:
        func = _function_node(REVIEW_PATH, "_resolve_review_outcome")
        calls = _called_names(func)
        assert {
            "_review_infrastructure_retry_decision",
            "_review_rework_decision",
            "_review_cap_exhausted_blocked_decision",
            "_review_force_proceeded_decision",
            "_review_deferred_human_decision",
            "_review_pass_decision",
            "_review_rework_cap_config_key",
        } <= calls
        assert not [
            call
            for call in ast.walk(func)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "ReviewRouteDecision"
        ], "_resolve_review_outcome must not construct ReviewRouteDecision directly"

    def test_review_outcome_resolver_avoids_handler_owned_cap_literals(self) -> None:
        strings = _string_constants(_function_node(REVIEW_PATH, "_resolve_review_outcome"))
        assert {
            "max_review_rework_cycles",
            "max_robust_review_rework_cycles",
        }.isdisjoint(strings)

    def test_review_blocked_next_step_only_loops_retryable_review(self) -> None:
        from arnold_pipelines.megaplan.handlers.review import (
            ReviewRouteDecision,
            _compat_next_step_for_review_route,
        )
        from arnold_pipelines.megaplan.outcomes import ReviewDecisionResult, ReviewOutcome
        from arnold_pipelines.megaplan.planning.state import STATE_BLOCKED, STATE_EXECUTED

        assert _compat_next_step_for_review_route(
            ReviewRouteDecision(
                result=ReviewDecisionResult.BLOCKED,
                next_state=STATE_EXECUTED,
                route_signal=ReviewOutcome.BLOCKED,
            )
        ) == "review"
        assert _compat_next_step_for_review_route(
            ReviewRouteDecision(
                result=ReviewDecisionResult.BLOCKED,
                next_state=STATE_BLOCKED,
                route_signal=ReviewOutcome.BLOCKED,
            )
        ) is None

    def test_review_rework_routes_back_to_scoped_execute_before_re_review(self, monkeypatch, tmp_path: Path) -> None:
        import arnold_pipelines.megaplan.handlers.review as review_handler
        from arnold_pipelines.megaplan.outcomes import ReviewDecisionResult, ReviewOutcome
        from arnold_pipelines.megaplan.planning.state import STATE_FINALIZED

        monkeypatch.setattr(review_handler, "get_effective", lambda *_args: 2)
        issues: list[str] = []

        decision = review_handler._resolve_review_outcome(
            tmp_path,
            "needs_rework",
            verdict_count=1,
            total_tasks=1,
            check_count=1,
            total_checks=1,
            missing_evidence=[],
            robustness="standard",
            state={"config": {}, "history": []},
            issues=issues,
            criteria=[{"priority": "should", "pass": "fail", "criterion": "tighten docs"}],
            rework_items=[{"issue": "tighten docs", "severity": "advisory"}],
        )

        assert decision.result is ReviewDecisionResult.NEEDS_REWORK
        assert decision.route_signal is ReviewOutcome.REWORK
        assert decision.next_state == STATE_FINALIZED
        assert review_handler._compat_next_step_for_review_route(decision) == "execute"
        assert issues == []

    def test_review_rework_cap_with_blockers_routes_to_recoverable_block(self, monkeypatch, tmp_path: Path) -> None:
        import arnold_pipelines.megaplan.handlers.review as review_handler
        from arnold_pipelines.megaplan.outcomes import ReviewDecisionResult, ReviewOutcome
        from arnold_pipelines.megaplan.planning.state import STATE_BLOCKED

        monkeypatch.setattr(review_handler, "get_effective", lambda *_args: 1)
        issues: list[str] = []

        decision = review_handler._resolve_review_outcome(
            tmp_path,
            "needs_rework",
            verdict_count=1,
            total_tasks=1,
            check_count=1,
            total_checks=1,
            missing_evidence=[],
            robustness="standard",
            state={
                "config": {},
                "history": [{"step": "review", "result": ReviewDecisionResult.NEEDS_REWORK.value}],
            },
            issues=issues,
            criteria=[{"priority": "must", "pass": "fail", "criterion": "prove rollback safety"}],
            rework_items=[{"issue": "missing rollback proof"}],
        )

        assert decision.result is ReviewDecisionResult.BLOCKED
        assert decision.route_signal is ReviewOutcome.BLOCKED
        assert decision.next_state == STATE_BLOCKED
        assert review_handler._compat_next_step_for_review_route(decision) is None
        assert any("recoverable blocked" in issue for issue in issues)

    def test_review_rework_cap_without_blockers_force_proceeds_advisory_only(self, monkeypatch, tmp_path: Path) -> None:
        import arnold_pipelines.megaplan.handlers.review as review_handler
        from arnold_pipelines.megaplan.outcomes import ReviewDecisionResult, ReviewOutcome
        from arnold_pipelines.megaplan.planning.state import STATE_DONE

        monkeypatch.setattr(review_handler, "get_effective", lambda *_args: 1)
        issues: list[str] = []

        decision = review_handler._resolve_review_outcome(
            tmp_path,
            "needs_rework",
            verdict_count=1,
            total_tasks=1,
            check_count=1,
            total_checks=1,
            missing_evidence=[],
            robustness="standard",
            state={
                "config": {},
                "history": [{"step": "review", "result": ReviewDecisionResult.NEEDS_REWORK.value}],
            },
            issues=issues,
            criteria=[{"priority": "should", "pass": "fail", "criterion": "polish summary"}],
            rework_items=[{"issue": "rename heading", "severity": "advisory"}],
        )

        assert decision.result is ReviewDecisionResult.FORCE_PROCEEDED
        assert decision.route_signal is ReviewOutcome.FORCE_PROCEEDED
        assert decision.next_state == STATE_DONE
        assert review_handler._compat_next_step_for_review_route(decision) is None
        assert any("Force-proceeding to done" in issue for issue in issues)

    def test_review_deferred_human_uses_suspend_resume_surface(self, monkeypatch, tmp_path: Path) -> None:
        import arnold_pipelines.megaplan.handlers.review as review_handler
        from arnold_pipelines.megaplan.outcomes import ReviewDecisionResult, ReviewOutcome
        from arnold_pipelines.megaplan.planning.state import STATE_AWAITING_HUMAN_VERIFY

        monkeypatch.setattr(review_handler, "get_effective", lambda *_args: 2)

        decision = review_handler._resolve_review_outcome(
            tmp_path,
            "approved",
            verdict_count=1,
            total_tasks=1,
            check_count=1,
            total_checks=1,
            missing_evidence=[],
            robustness="standard",
            state={"config": {}, "history": []},
            issues=[],
            criteria=[{"priority": "must", "pass": "deferred_human", "criterion": "human UX validation"}],
        )

        assert decision.result is ReviewDecisionResult.SUCCESS
        assert decision.route_signal is ReviewOutcome.DEFERRED_HUMAN
        assert decision.next_state == STATE_AWAITING_HUMAN_VERIFY
        assert review_handler._compat_next_step_for_review_route(decision) is None


class TestOverrideSignals:
    def test_handle_override_avoids_transition_helpers(self) -> None:
        calls = _called_names(_function_node(OVERRIDE_PATH, "handle_override"))
        assert calls.isdisjoint(FORBIDDEN_TRANSITION_HELPERS)

    def test_override_action_output_uses_matrix_route_labels_not_targets(self) -> None:
        from arnold_pipelines.megaplan.workflows.override_matrix import ROUTE_SIGNAL_BY_ACTION

        strings = set(ROUTE_SIGNAL_BY_ACTION.values())
        assert {
            "abort",
            "adopt_execution",
            "force_proceed",
            "replan",
            "recover_blocked",
            "resume_clarify",
            "add_note",
            "set_robustness",
            "set_profile",
            "set_model",
            "set_vendor",
        } <= strings
        assert FORBIDDEN_OVERRIDE_TARGETS.isdisjoint(strings)


class TestSharedRouteHelpers:
    def test_shared_finish_step_avoids_transition_mutation_helpers(self) -> None:
        calls = _called_names(_function_node(SHARED_PATH, "_finish_step"))
        assert "workflow_transition" not in calls

    def test_shared_finish_step_uses_workflow_route_dispatch_helper(self) -> None:
        calls = _called_names(_function_node(SHARED_PATH, "_finish_step"))
        assert "resolve_route_target_for_signal" in calls

    def test_workflow_route_dispatch_helper_reads_declared_route_bindings(self) -> None:
        source = ROUTE_DISPATCH_PATH.read_text(encoding="utf-8")
        assert "STEP_COMPONENTS_BY_ID" in source
        assert "route_bindings" in source

    def test_front_half_route_dispatch_ignores_component_route_metadata_mutation(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.route_dispatch._component_route_bindings_for_step",
            lambda step: (
                (
                    {
                        "id": "gate:proceed",
                        "label": "proceed",
                        "target_ref": "halt",
                        "condition_ref": "mutated",
                    },
                )
                if step == "gate"
                else tuple(STEP_COMPONENTS_BY_ID[step].metadata.get("route_bindings", ()))
            ),
        )

        assert resolve_route_target_for_signal("gate", "proceed") == "finalize"

    def test_tiebreaker_alias_route_dispatch_ignores_legacy_component_metadata(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.route_dispatch._component_route_bindings_for_step",
            lambda step: (
                (
                    {
                        "id": "tiebreaker_decide:proceed",
                        "label": "proceed",
                        "target_ref": "halt",
                        "condition_ref": "mutated",
                    },
                )
                if step == "tiebreaker_decide"
                else tuple(STEP_COMPONENTS_BY_ID[step].metadata.get("route_bindings", ()))
            ),
        )

        assert resolve_route_target_for_signal("tiebreaker_decide", "proceed") == "finalize"


class TestExecuteSignals:
    """S4: Execute handler and batch auto-loop must not own route decisions.

    Handler-owned execute route decisions, hidden auto-loop scheduler
    branches, and handler-local ``next_step`` assignment patterns are
    rejected at the checker/linter level so they cannot silently regress.

    These tests use the same AST-inspection strategy as the other
    ``Test*Signals`` classes: they parse the source files and assert
    that the required typed-policy surfaces are present while forbidden
    patterns (transition helpers, bare route-target literals, direct
    ``next_step`` string assignments) are absent.
    """

    # ── execute handler (handlers/execute.py) ──────────────────────────

    def test_handle_execute_avoids_transition_helpers(self) -> None:
        """The execute handler must never call legacy transition helpers."""
        calls = _called_names(_function_node(EXECUTE_HANDLER_PATH, "handle_execute"))
        assert calls.isdisjoint(FORBIDDEN_TRANSITION_HELPERS), (
            f"handle_execute must not call {sorted(calls & FORBIDDEN_TRANSITION_HELPERS)}"
        )

    def test_handle_execute_imports_typed_policy(self) -> None:
        """handle_execute module must import typed execute-policy functions."""
        source = EXECUTE_HANDLER_PATH.read_text(encoding="utf-8")
        assert "from arnold_pipelines.megaplan.execute.policy import" in source, (
            "execute handler must import from execute.policy"
        )

    def test_enforce_entry_route_calls_policy(self) -> None:
        """``_enforce_entry_route`` (called by handle_execute) must delegate
        to ``resolve_execute_entry_route`` — the handler-local helper is the
        bridge between the typed policy and legacy error raising."""
        calls = _called_names(
            _function_node(EXECUTE_HANDLER_PATH, "_enforce_entry_route")
        )
        assert "resolve_execute_entry_route" in calls, (
            "_enforce_entry_route must call resolve_execute_entry_route"
        )

    def test_enforce_approval_gate_calls_policy(self) -> None:
        """``_enforce_approval_gate`` (called by handle_execute) must delegate
        to ``evaluate_destructive_approval`` — the handler-local helper is the
        bridge between the typed policy and legacy error raising."""
        calls = _called_names(
            _function_node(EXECUTE_HANDLER_PATH, "_enforce_approval_gate")
        )
        assert "evaluate_destructive_approval" in calls, (
            "_enforce_approval_gate must call evaluate_destructive_approval"
        )

    def test_handle_execute_uses_no_review_terminal_policy(self) -> None:
        """No-review terminal must route through evaluate_no_review_terminal."""
        calls = _called_names(_function_node(EXECUTE_HANDLER_PATH, "handle_execute"))
        assert "evaluate_no_review_terminal" in calls, (
            "handle_execute must call evaluate_no_review_terminal for no-review routing"
        )

    def test_handle_execute_uses_policy_projection_helpers_for_terminal_next_step(self) -> None:
        """Terminal next-step derivation must route through policy-backed projections."""
        calls = _called_names(_function_node(EXECUTE_HANDLER_PATH, "handle_execute"))
        assert EXECUTE_NEXT_STEP_PROJECTION_HELPERS <= calls, (
            "handle_execute must call policy-backed projection helpers for blocked/no-review next-step routing"
        )

    def test_handle_execute_next_step_assignments_use_lookup_maps(self) -> None:
        """All ``response['next_step']`` writes must use ``_LEGACY_NEXT_STEP``
        or ``_NO_REVIEW_NEXT_STEP`` lookup maps, or values projected from the
        explicit execute/finalize policy helpers — never a bare string literal.

        We walk the AST of ``handle_execute`` and collect every
        ``response[...] = ...`` assignment whose subscript is the string
        ``'next_step'``.  The assigned value must come from a lookup map, or
        from a subscript of a local variable whose value was created by one of
        the approved projection helpers.
        """
        func = _function_node(EXECUTE_HANDLER_PATH, "handle_execute")
        projection_names: dict[str, str] = {}
        for node in ast.walk(func):
            if not isinstance(node, ast.Assign):
                continue
            if len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            if not isinstance(node.value, ast.Call):
                continue
            if not isinstance(node.value.func, ast.Name):
                continue
            projection_names[target.id] = node.value.func.id
        violations: list[int] = []
        for node in ast.walk(func):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Subscript):
                    continue
                if not isinstance(target.slice, ast.Constant):
                    continue
                if target.slice.value != "next_step":
                    continue
                # The assigned value must be a name (map[key]) or subscript (map[key])
                if isinstance(node.value, ast.Name):
                    if node.value.id not in EXECUTE_NEXT_STEP_MAPS:
                        violations.append(node.lineno)
                elif isinstance(node.value, ast.Subscript):
                    if isinstance(node.value.value, ast.Name):
                        source_name = node.value.value.id
                        if source_name not in EXECUTE_NEXT_STEP_MAPS and projection_names.get(source_name) not in EXECUTE_NEXT_STEP_PROJECTION_HELPERS:
                            violations.append(node.lineno)
                    else:
                        violations.append(node.lineno)
                elif isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    violations.append(node.lineno)
        assert not violations, (
            f"handle_execute assigns next_step via bare literal/unknown name "
            f"at lines {violations}; must use {EXECUTE_NEXT_STEP_MAPS}"
        )

    def test_handle_execute_no_bare_route_targets_in_route_logic(self) -> None:
        """The execute handler must not embed bare route-target string
        literals in its route-decision code path.  ``_enforce_entry_route``
        and ``_enforce_approval_gate`` are the two helper functions that
        translate typed outcomes into legacy errors; neither should contain
        hardcoded target refs like ``'halt'``, ``'review'``, ``'finalize'``.

        We tolerate the string ``'execute'`` in error messages because it
        refers to the phase name, not a route target.
        """
        for helper_name in ("_enforce_entry_route", "_enforce_approval_gate"):
            strings = _string_constants(
                _function_node(EXECUTE_HANDLER_PATH, helper_name)
            )
            intersection = strings & FORBIDDEN_EXECUTE_ROUTE_TARGETS
            assert not intersection, (
                f"{helper_name} contains forbidden route-target literal(s): {intersection}"
            )

    # ── batch auto-loop (execute/batch.py) ─────────────────────────────

    def test_auto_loop_avoids_transition_helpers(self) -> None:
        """The batch auto-loop must never call legacy transition helpers."""
        calls = _called_names(
            _function_node(EXECUTE_BATCH_PATH, "handle_execute_auto_loop")
        )
        assert calls.isdisjoint(FORBIDDEN_TRANSITION_HELPERS), (
            f"handle_execute_auto_loop must not call "
            f"{sorted(calls & FORBIDDEN_TRANSITION_HELPERS)}"
        )

    def test_auto_loop_uses_resolve_single_batch_next_step(self) -> None:
        """All next-step decisions must flow through resolve_single_batch_next_step."""
        calls = _called_names(
            _function_node(EXECUTE_BATCH_PATH, "handle_execute_auto_loop")
        )
        assert "resolve_single_batch_next_step" in calls, (
            "handle_execute_auto_loop must call resolve_single_batch_next_step"
        )

    def test_auto_loop_uses_legacy_next_step_mapper(self) -> None:
        """Every next_step legacy assignment must pass through the
        ``_legacy_next_step_for_execute_policy`` compatibility mapper so
        there is no hidden local branch that writes a bare string."""
        calls = _called_names(
            _function_node(EXECUTE_BATCH_PATH, "handle_execute_auto_loop")
        )
        assert BATCH_NEXT_STEP_MAPPER in calls, (
            f"handle_execute_auto_loop must call {BATCH_NEXT_STEP_MAPPER}"
        )

    def test_auto_loop_no_bare_next_step_string_literals(self) -> None:
        """The auto-loop must never write a bare string literal into
        ``response['next_step']``.  Every such assignment must go through
        the ``_legacy_next_step_for_execute_policy`` mapper or a policy
        lookup map."""
        func = _function_node(EXECUTE_BATCH_PATH, "handle_execute_auto_loop")
        helper_funcs: dict[str, ast.FunctionDef] = {}
        tree = ast.parse(EXECUTE_BATCH_PATH.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                helper_funcs[node.name] = node

        violations: list[tuple[str, int]] = []
        for check_func in [func] + list(helper_funcs.values()):
            for node in ast.walk(check_func):
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if not isinstance(target, ast.Subscript):
                        continue
                    if not isinstance(target.slice, ast.Constant):
                        continue
                    if target.slice.value != "next_step":
                        continue
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        violations.append((check_func.name, node.lineno))
        assert not violations, (
            f"bare string literal next_step assignments at: {violations}"
        )

    def test_calibration_tier_spec_calls_resolve_batch_tier(self) -> None:
        """Tier routing must flow through ``resolve_batch_tier`` (not hidden
        inline tier selection).  The auto-loop delegates to
        ``handle_execute_one_batch``, which calls ``_calibration_tier_spec``,
        which is the bridge to the typed tier policy.  We verify that bridge
        actually calls the policy function."""
        calls = _called_names(
            _function_node(EXECUTE_BATCH_PATH, "_calibration_tier_spec")
        )
        assert "resolve_batch_tier" in calls, (
            "_calibration_tier_spec must call resolve_batch_tier"
        )

    # ── EXECUTE component route_bindings ───────────────────────────────

    def test_execute_component_has_no_route_bindings(self) -> None:
        """The EXECUTE step component must not carry authoritative
        ``route_bindings``.  Execute route authority lives in the typed
        policy surface and ``workflow.pypeline``, not in component metadata.

        This mirrors the topology-golden test from T4 and serves as a
        fast-fail lint-level check.
        """
        from arnold_pipelines.megaplan.workflows.components import STEP_COMPONENTS_BY_ID

        execute_component = STEP_COMPONENTS_BY_ID["execute"]
        bindings = execute_component.metadata.get("route_bindings", ())
        assert bindings == (), (
            "EXECUTE step component must not carry authoritative route_bindings; "
            "route authority is in EXECUTE_POLICY.route_surface / workflow.pypeline"
        )

    # ── route dispatch: execute component bindings must stay empty ──────
    #
    # Unlike gate / tiebreaker, execute is NOT a front-half routing step,
    # so the route-dispatch module will honour component bindings if they
    # exist.  The protection is therefore structural: the component must
    # never carry authoritative bindings (tested above).  There is no
    # monkeypatch-ignores test for execute because the dispatch correctly
    # reads component metadata for non-front-half steps.
