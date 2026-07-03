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
import importlib
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Canonical classification (must match the semantics carrier table)
# ---------------------------------------------------------------------------

HANDLER_MODULE = "arnold_pipelines.megaplan.handlers"

# Report-semantic owners: handlers whose bodies own routing decisions
# (branching, loop-exits, suspension, override dispatch, non-mechanical
# state transitions).
REPORT_SEMANTIC_OWNERS: frozenset[str] = frozenset(
    {
        "handle_gate",
        "handle_review",
        "handle_override",
        "handle_tiebreaker_decide",
        "handle_finalize",
        "handle_critique",
        "handle_prep",
        "handle_revise",
        "handle_execute",
    }
)

# Pure phase bodies: handlers that compute outputs without owning routing.
PURE_PHASE_BODIES: frozenset[str] = frozenset(
    {
        "handle_plan",
        "handle_tiebreaker_run",
    }
)

# All 11 handler names.
ALL_HANDLER_NAMES: frozenset[str] = REPORT_SEMANTIC_OWNERS | PURE_PHASE_BODIES

# Routing call markers — function calls that indicate the handler owns or
# participates in routing decisions. These markers are forbidden in pure
# phase bodies and expected in report-semantic owners.
ROUTING_CALL_MARKERS: frozenset[str] = frozenset(
    {
        "workflow_transition",
        "workflow_next",
        "_next_progress_step",
        "_resolve_review_outcome",
        "_route_finalize_baseline_selection_failure_to_revise",
        "_apply_prep_clarify_gate",
        "_resolve_revise_transition",
        "_apply_gate_outcome",
        "_override_abort",
        "_override_force_proceed",
        "_override_replan",
        "_override_set_robustness",
        "_override_add_note",
    }
)

# Handler file mapping: handler_name → source file path (relative to megaplan root)
HANDLER_FILE_MAP: dict[str, str] = {
    "handle_prep": "handlers/plan.py",
    "handle_plan": "handlers/plan.py",
    "handle_critique": "handlers/critique.py",
    "handle_gate": "handlers/gate.py",
    "handle_revise": "handlers/critique.py",
    "handle_tiebreaker_run": "handlers/_tiebreaker_impl.py",
    "handle_tiebreaker_decide": "handlers/_tiebreaker_impl.py",
    "handle_finalize": "handlers/finalize.py",
    "handle_execute": "handlers/execute.py",
    "handle_review": "handlers/review.py",
    "handle_override": "handlers/override.py",
}

# Handlers that use workflow_transition for a single deterministic mechanical
# step (not a branched routing decision). These are pure phase bodies that
# are allowed to call workflow_transition.
MECHANICAL_TRANSITION_HANDLERS: frozenset[str] = frozenset(
    {
        "handle_tiebreaker_run",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _megaplan_root() -> Path:
    """Return the megaplan package root directory."""
    spec = importlib.util.find_spec("arnold_pipelines.megaplan")
    if spec is None or spec.origin is None:
        raise RuntimeError("Cannot locate arnold_pipelines.megaplan package")
    return Path(spec.origin).parent


def _handler_source(handler_name: str) -> tuple[Path, str]:
    """Return the file path and source text for a handler."""
    megaplan_root = _megaplan_root()
    rel = HANDLER_FILE_MAP[handler_name]
    filepath = megaplan_root / rel
    if not filepath.exists():
        raise FileNotFoundError(f"Handler source not found: {filepath}")
    return filepath, filepath.read_text(encoding="utf-8")


def _parse_source(source: str) -> ast.Module:
    return ast.parse(source)


def _find_function(node: ast.Module, func_name: str) -> ast.FunctionDef | None:
    """Find a top-level function definition by name."""
    for stmt in ast.iter_child_nodes(node):
        if isinstance(stmt, ast.FunctionDef) and stmt.name == func_name:
            return stmt
    return None


def _collect_call_names(node: ast.AST) -> set[str]:
    """Collect all function call names from an AST node."""
    names: set[str] = set()

    class CallCollector(ast.NodeVisitor):
        def visit_Call(self, call: ast.Call) -> None:
            if isinstance(call.func, ast.Name):
                names.add(call.func.id)
            elif isinstance(call.func, ast.Attribute):
                names.add(call.func.attr)
            self.generic_visit(call)

    CallCollector().visit(node)
    return names


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
        _, source = _handler_source(handler_name)
        tree = _parse_source(source)
        func = _find_function(tree, handler_name)
        assert func is not None, f"Function '{handler_name}' not found in source"

        calls = _collect_call_names(func)

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
            _, source = _handler_source(handler_name)
            tree = _parse_source(source)
            func = _find_function(tree, handler_name)
            if func is None:
                continue

            calls = _collect_call_names(func)

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
        filepath, source = _handler_source(handler_name)
        assert filepath.exists(), f"Source file not found: {filepath}"
        try:
            ast.parse(source)
        except SyntaxError as exc:
            pytest.fail(f"Handler source for '{handler_name}' has syntax error: {exc}")

    @pytest.mark.parametrize("handler_name", sorted(ALL_HANDLER_NAMES))
    def test_function_exists_in_source(self, handler_name: str) -> None:
        """Each handler function must exist in its mapped source file."""
        _, source = _handler_source(handler_name)
        tree = _parse_source(source)
        func = _find_function(tree, handler_name)
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
