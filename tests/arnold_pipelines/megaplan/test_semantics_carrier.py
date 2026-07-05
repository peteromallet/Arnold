"""Mechanical enforcement of the M1 semantics carrier table.

Covers all 11 Megaplan handler refs defined in
``arnold_pipelines.megaplan.workflows.components``, classifying each as a
retained pure phase body or a report-semantic owner, and verifying the
no-hidden-routing claims from
``docs/arnold/megaplan-semantics-carrier-table.md``.

These tests are source-invariant: they scan handler source code via AST
rather than importing handlers, so they detect classification drift without
depending on runtime state.
"""

from __future__ import annotations

import ast
from typing import Any

import pytest

from arnold.workflow.handler_semantics import (
    ALL_HANDLER_NAMES,
    HANDLER_FILE_MAP,
    HANDLER_MODULE,
    M6_FANOUT_DISPATCH_CALLS,
    M6_FORBIDDEN_ROUTING_CALLS,
    M6_RETAINED_HANDLERS,
    M6_RETAINED_MODULE_RELS,
    MECHANICAL_TRANSITION_HANDLERS,
    PURE_PHASE_BODIES,
    REPORT_SEMANTIC_OWNERS,
    ROUTING_CALL_MARKERS,
    LocalRouteFunctionDetector,
    StateMutationVisitor,
    check_handler_body_purity,
    collect_call_names,
    find_function,
    handler_source,
    megaplan_root,
    parse_source,
)


# ---------------------------------------------------------------------------
# Tests: Completeness and classification coverage
# ---------------------------------------------------------------------------

class TestHandlerRefCompleteness:
    """Verify that all 11 handler refs in ALL_STEP_COMPONENTS are covered."""

    def test_all_step_components_count(self) -> None:
        """ALL_STEP_COMPONENTS must have exactly 12 entries (11 with handlers + HALT)."""
        from arnold_pipelines.megaplan.workflows.components import ALL_STEP_COMPONENTS

        assert len(ALL_STEP_COMPONENTS) == 12, (
            f"ALL_STEP_COMPONENTS has {len(ALL_STEP_COMPONENTS)} entries; expected 12"
        )

    def test_handler_ref_count(self) -> None:
        """Exactly 11 StepComponents must have non-None handler_ref."""
        from arnold_pipelines.megaplan.workflows.components import ALL_STEP_COMPONENTS

        components_with_handler = [
            c for c in ALL_STEP_COMPONENTS if c.metadata.get("handler_ref") is not None
        ]
        assert len(components_with_handler) == 11, (
            f"Expected 11 StepComponents with handler_ref; found {len(components_with_handler)}"
        )

    def test_halt_has_no_handler(self) -> None:
        """HALT must not have a handler_ref (it's a terminal step)."""
        from arnold_pipelines.megaplan.workflows.components import STEP_COMPONENTS_BY_ID

        halt = STEP_COMPONENTS_BY_ID.get("halt")
        assert halt is not None, "HALT component not found"
        handler_ref = halt.metadata.get("handler_ref")
        assert handler_ref is None, f"HALT should have no handler_ref; got {handler_ref!r}"

    def test_every_handler_ref_has_classification(self) -> None:
        """Every handler_ref in ALL_STEP_COMPONENTS maps to a name in our classification."""
        from arnold_pipelines.megaplan.workflows.components import ALL_STEP_COMPONENTS

        for component in ALL_STEP_COMPONENTS:
            handler_ref = component.metadata.get("handler_ref")
            if handler_ref is None:
                continue
            func_name = handler_ref.split(":")[-1]
            assert func_name in ALL_HANDLER_NAMES, (
                f"Handler '{func_name}' (from {component.id}) is not classified "
                f"in ALL_HANDLER_NAMES"
            )

    def test_every_classified_handler_has_component(self) -> None:
        """Every handler in our classification must appear in ALL_STEP_COMPONENTS."""
        from arnold_pipelines.megaplan.workflows.components import ALL_STEP_COMPONENTS

        component_handler_names: set[str] = set()
        for component in ALL_STEP_COMPONENTS:
            handler_ref = component.metadata.get("handler_ref")
            if handler_ref is not None:
                component_handler_names.add(handler_ref.split(":")[-1])

        for name in ALL_HANDLER_NAMES:
            assert name in component_handler_names, (
                f"Handler '{name}' is classified but not found in ALL_STEP_COMPONENTS"
            )

    def test_no_overlap_between_classifications(self) -> None:
        """No handler can be both pure and report-semantic owner."""
        overlap = REPORT_SEMANTIC_OWNERS & PURE_PHASE_BODIES
        assert len(overlap) == 0, f"Overlap between classifications: {overlap}"

    def test_all_11_handlers_accounted_for(self) -> None:
        """The union of pure and report-semantic owners must cover all 11 handlers."""
        all_classified = REPORT_SEMANTIC_OWNERS | PURE_PHASE_BODIES
        assert len(all_classified) == 11, (
            f"Expected 11 classified handlers; got {len(all_classified)}: "
            f"{sorted(all_classified)}"
        )


# ---------------------------------------------------------------------------
# Tests: Pure phase body invariants
#
# Pure handlers must not call routing functions. They may use
# workflow_transition only if listed in MECHANICAL_TRANSITION_HANDLERS
# (single deterministic step, not a branched routing decision).
# ---------------------------------------------------------------------------

class TestPurePhaseBodyInvariants:
    """Verify that pure phase bodies do not contain routing call markers."""

    @pytest.mark.parametrize("handler_name", sorted(PURE_PHASE_BODIES))
    def test_no_routing_call_markers(self, handler_name: str) -> None:
        """Pure handler must not call routing functions."""
        _, source = handler_source(handler_name)
        tree = parse_source(source)
        func = find_function(tree, handler_name)
        assert func is not None, f"Function '{handler_name}' not found in source"

        calls = collect_call_names(func)

        # Allow workflow_transition for mechanical single-step handlers
        if handler_name in MECHANICAL_TRANSITION_HANDLERS:
            calls.discard("workflow_transition")

        routing_calls = calls & ROUTING_CALL_MARKERS
        assert len(routing_calls) == 0, (
            f"Pure handler '{handler_name}' contains routing call markers: "
            f"{routing_calls}. Reclassify as report-semantic owner or remove "
            f"the routing logic."
        )


# ---------------------------------------------------------------------------
# Tests: No unclassified routing owners
#
# If any handler (pure or not) contains routing call markers, it must be
# classified as a report-semantic owner.
# ---------------------------------------------------------------------------

class TestNoUnclassifiedRoutingOwners:
    """Ensure no handler has routing markers without being classified."""

    def test_no_unclassified_routing(self) -> None:
        """Scan all 11 handler bodies for routing markers."""
        for handler_name in sorted(ALL_HANDLER_NAMES):
            _, source = handler_source(handler_name)
            tree = parse_source(source)
            func = find_function(tree, handler_name)
            if func is None:
                continue

            calls = collect_call_names(func)

            # Allow mechanical transition handlers to use workflow_transition
            if handler_name in MECHANICAL_TRANSITION_HANDLERS:
                calls.discard("workflow_transition")

            routing_calls = calls & ROUTING_CALL_MARKERS
            if routing_calls:
                assert handler_name in REPORT_SEMANTIC_OWNERS, (
                    f"Handler '{handler_name}' contains routing call markers "
                    f"({routing_calls}) but is NOT classified as a "
                    f"report-semantic owner. Add it to REPORT_SEMANTIC_OWNERS."
                )


# ---------------------------------------------------------------------------
# Tests: Handler file mapping integrity
# ---------------------------------------------------------------------------

class TestHandlerFileMapping:
    """Verify that the handler file mapping is correct and files are parseable."""

    @pytest.mark.parametrize("handler_name", sorted(ALL_HANDLER_NAMES))
    def test_source_file_exists_and_parseable(self, handler_name: str) -> None:
        """Each handler's source file must exist and be valid Python."""
        filepath, source = handler_source(handler_name)
        assert filepath.exists(), f"Source file not found: {filepath}"
        try:
            ast.parse(source)
        except SyntaxError as exc:
            pytest.fail(f"Handler source for '{handler_name}' has syntax error: {exc}")

    @pytest.mark.parametrize("handler_name", sorted(ALL_HANDLER_NAMES))
    def test_function_exists_in_source(self, handler_name: str) -> None:
        """Each handler function must exist in its mapped source file."""
        _, source = handler_source(handler_name)
        tree = parse_source(source)
        func = find_function(tree, handler_name)
        assert func is not None, (
            f"Function '{handler_name}' not found in {HANDLER_FILE_MAP[handler_name]}"
        )


# ---------------------------------------------------------------------------
# Tests: Handler module __all__ completeness
# ---------------------------------------------------------------------------

class TestHandlerModuleExports:
    """Verify that all 11 handler refs are exported from handlers/__init__.py."""

    def test_all_handlers_in_all(self) -> None:
        """All 11 handlers must be in handlers.__all__."""
        from arnold_pipelines.megaplan.handlers import __all__ as handler_all

        handler_all_set = set(handler_all)
        for name in ALL_HANDLER_NAMES:
            assert name in handler_all_set, (
                f"Handler '{name}' is not in handlers.__all__"
            )

    def test_no_extra_handlers_in_components(self) -> None:
        """Any handler in handlers.__all__ with a component ref must be classified."""
        from arnold_pipelines.megaplan.handlers import __all__ as handler_all
        from arnold_pipelines.megaplan.workflows.components import ALL_STEP_COMPONENTS

        component_handler_names: set[str] = set()
        for component in ALL_STEP_COMPONENTS:
            handler_ref = component.metadata.get("handler_ref")
            if handler_ref is not None:
                component_handler_names.add(handler_ref.split(":")[-1])

        in_both = set(handler_all) & component_handler_names
        unclassified = in_both - ALL_HANDLER_NAMES
        assert len(unclassified) == 0, (
            f"Handlers in both handlers.__all__ and StepComponents but not "
            f"classified: {unclassified}"
        )


# ---------------------------------------------------------------------------
# Tests: M6 retained-handler purity (handler body)
# ---------------------------------------------------------------------------


class TestM6RetainedHandlerBodyPurity:
    """Verify that each M6 retained handler body is pure — no state
    mutation, no routing calls, no fanout dispatch."""

    @pytest.mark.parametrize("handler_name", sorted(M6_RETAINED_HANDLERS))
    def test_no_state_mutation(self, handler_name: str) -> None:
        """Retained handler must not assign to state[\"current_state\"]."""
        _, source = handler_source(handler_name)
        tree = parse_source(source)
        func = find_function(tree, handler_name)
        assert func is not None, f"Function '{handler_name}' not found in source"

        mutation_visitor = StateMutationVisitor()
        mutation_visitor.visit(func)
        assert len(mutation_visitor.violations) == 0, (
            f"M6 retained handler '{handler_name}' mutates state directly: "
            f"{mutation_visitor.violations}. M6 purity bar requires state "
            f"transitions to be expressed outside the handler body."
        )

    @pytest.mark.parametrize("handler_name", sorted(M6_RETAINED_HANDLERS))
    def test_no_routing_calls(self, handler_name: str) -> None:
        """Retained handler must not call workflow_transition / workflow_next."""
        _, source = handler_source(handler_name)
        tree = parse_source(source)
        func = find_function(tree, handler_name)
        assert func is not None, f"Function '{handler_name}' not found in source"

        calls = collect_call_names(func)
        routing = calls & M6_FORBIDDEN_ROUTING_CALLS
        assert len(routing) == 0, (
            f"M6 retained handler '{handler_name}' calls routing functions "
            f"directly: {sorted(routing)}. M6 purity bar requires routing "
            f"to be expressed in the workflow layer, not in handler bodies."
        )

    @pytest.mark.parametrize("handler_name", sorted(M6_RETAINED_HANDLERS))
    def test_no_fanout_dispatch(self, handler_name: str) -> None:
        """Retained handler must not perform handler-resident fanout dispatch."""
        _, source = handler_source(handler_name)
        tree = parse_source(source)
        func = find_function(tree, handler_name)
        assert func is not None, f"Function '{handler_name}' not found in source"

        calls = collect_call_names(func)
        fanout = calls & M6_FANOUT_DISPATCH_CALLS
        assert len(fanout) == 0, (
            f"M6 retained handler '{handler_name}' performs handler-resident "
            f"fanout dispatch: {sorted(fanout)}. M6 purity bar requires "
            f"fanout dispatch to be orchestrated outside the handler body."
        )


# ---------------------------------------------------------------------------
# Tests: M6 local route-decision functions
# ---------------------------------------------------------------------------


class TestM6NoLocalRouteDecisionFunctions:
    """Verify that retained handler modules do not define local helper
    functions that perform routing, state mutation, or fanout dispatch."""

    @pytest.mark.parametrize("handler_name", sorted(M6_RETAINED_HANDLERS))
    def test_no_local_route_functions(self, handler_name: str) -> None:
        """No local function (other than the main handler) may contain
        routing calls, state mutations, or fanout dispatch."""
        _, source = handler_source(handler_name)
        tree = parse_source(source)

        detector = LocalRouteFunctionDetector(
            handler_name=handler_name,
            forbidden_routing=M6_FORBIDDEN_ROUTING_CALLS,
            fanout_calls=M6_FANOUT_DISPATCH_CALLS,
        )
        detector.visit(tree)

        assert len(detector.violations) == 0, (
            f"M6 retained handler module for '{handler_name}' defines local "
            f"route-decision functions: {dict(detector.violations)}. "
            f"M6 purity bar requires routing decisions to live in the "
            f"workflow / orchestration layer, not inside handler modules."
        )


# ---------------------------------------------------------------------------
# Tests: M6 shared-handler-infrastructure purity
# ---------------------------------------------------------------------------


class TestM6SharedHandlerPurity:
    """Verify that the shared handler-infrastructure module (shared.py)
    does not contain routing logic or state-transition mutations inside
    its utility functions."""

    SHARED_MODULE_REL = "handlers/shared.py"

    def test_shared_functions_are_pure(self) -> None:
        """Each top-level function in shared.py must not contain forbidden
        routing calls, state-mutation assignments, or fanout dispatch."""
        root = megaplan_root()
        filepath = root / self.SHARED_MODULE_REL
        if not filepath.exists():
            raise FileNotFoundError(f"Shared module not found: {filepath}")
        source = filepath.read_text(encoding="utf-8")
        tree = parse_source(source)

        all_violations: dict[str, set[str]] = {}

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            func_violations = check_handler_body_purity(
                node,
                forbidden_routing=M6_FORBIDDEN_ROUTING_CALLS,
                fanout_calls=M6_FANOUT_DISPATCH_CALLS,
            )
            if func_violations:
                all_violations[node.name] = func_violations

        assert len(all_violations) == 0, (
            f"Shared handler-infrastructure module contains functions with "
            f"forbidden M6 patterns: {all_violations}. "
            f"M6 purity bar requires shared utility functions to delegate "
            f"routing and state transitions to the workflow layer."
        )
