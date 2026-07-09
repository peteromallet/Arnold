"""Semantic-carrier AST scanners and handler purity checks for Megaplan.

This module provides production-calibre AST visitors, classification data,
and purity-check helpers that the checker, diagnostics, and source-compiler
consumers reuse.  It replaces the duplicated scanner implementations that
previously lived only in test code.

Bridge / re-export resolution is preserved for:

* ``handlers/__init__.py`` — master re-export hub
* ``handlers/tiebreaker.py`` — tiebreaker bridge (re-exports from
  ``_tiebreaker_impl.py``)
* ``handlers/_tiebreaker_impl.py`` — canonical tiebreaker implementation
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Any


# ── Handler classification (must match the semantics carrier table) ────────

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


# ── M6 handler-purity bar — constants ──────────────────────────────────────

# Handlers retained under M6 that must meet the raised purity bar.
# These handlers must NOT directly mutate current_state / next_step, emit
# workflow_transition / workflow_next, perform handler-resident fanout
# dispatch, or define local route-decision functions.
M6_RETAINED_HANDLERS: frozenset[str] = frozenset(
    {
        "handle_critique",
        "handle_gate",
        "handle_tiebreaker_decide",
        "handle_tiebreaker_run",
        "handle_finalize",
        "handle_execute",
        "handle_review",
        "handle_override",
    }
)

# Source files housing retained handlers plus the shared handler-infra module.
M6_RETAINED_MODULE_RELS: frozenset[str] = frozenset(
    {
        "handlers/critique.py",
        "handlers/gate.py",
        "handlers/_tiebreaker_impl.py",
        "handlers/finalize.py",
        "handlers/execute.py",
        "handlers/review.py",
        "handlers/override.py",
        "handlers/shared.py",
    }
)

# Routing/dispatch calls that are forbidden in M6 retained handler bodies.
M6_FORBIDDEN_ROUTING_CALLS: frozenset[str] = frozenset(
    {
        "workflow_transition",
        "workflow_next",
    }
)

# Handler-resident fanout-dispatch calls — these perform parallel /
# multi-worker dispatch inside the handler itself and violate the M6
# purity bar.
M6_FANOUT_DISPATCH_CALLS: frozenset[str] = frozenset(
    {
        "run_parallel_critique",
        "run_parallel_review",
    }
)


# ── AST helpers ────────────────────────────────────────────────────────────


def megaplan_root() -> Path:
    """Return the megaplan package root directory."""
    spec = importlib.util.find_spec("arnold_pipelines.megaplan")
    if spec is None or spec.origin is None:
        raise RuntimeError("Cannot locate arnold_pipelines.megaplan package")
    return Path(spec.origin).parent


def handler_source(handler_name: str) -> tuple[Path, str]:
    """Return the file path and source text for a handler."""
    root = megaplan_root()
    rel = HANDLER_FILE_MAP[handler_name]
    filepath = root / rel
    if not filepath.exists():
        raise FileNotFoundError(f"Handler source not found: {filepath}")
    return filepath, filepath.read_text(encoding="utf-8")


def parse_source(source: str) -> ast.Module:
    return ast.parse(source)


def find_function(node: ast.Module, func_name: str) -> ast.FunctionDef | None:
    """Find a top-level function definition by name."""
    for stmt in ast.iter_child_nodes(node):
        if isinstance(stmt, ast.FunctionDef) and stmt.name == func_name:
            return stmt
    return None


def collect_call_names(node: ast.AST) -> set[str]:
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


def is_state_subscript_assign(
    target: ast.expr, key: str, *, var_name: str = "state"
) -> bool:
    """Return True when *target* is ``var_name["key"]`` subscript form."""
    if not isinstance(target, ast.Subscript):
        return False
    if not isinstance(target.value, ast.Name):
        return False
    if target.value.id != var_name:
        return False
    # Python 3.9+: slice is directly the Constant
    if isinstance(target.slice, ast.Constant):
        return target.slice.value == key
    # Older Python: slice wrapped in ast.Index
    if isinstance(target.slice, ast.Index):
        inner = target.slice.value  # type: ignore[attr-defined]
        if isinstance(inner, ast.Constant):
            return inner.value == key
        if isinstance(inner, ast.Str):
            return inner.s == key
    return False


class StateMutationVisitor(ast.NodeVisitor):
    """Collects descriptions of ``state["current_state"]`` / ``state["next_step"]``
    and ``response["next_step"]`` / ``response["state"]`` assignment sites."""

    def __init__(self) -> None:
        self.violations: list[str] = []

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if is_state_subscript_assign(target, "current_state", var_name="state"):
                self.violations.append('state["current_state"] = ...')
            elif is_state_subscript_assign(target, "next_step", var_name="state"):
                self.violations.append('state["next_step"] = ...')
            elif is_state_subscript_assign(target, "next_step", var_name="response"):
                self.violations.append('response["next_step"] = ...')
            elif is_state_subscript_assign(target, "state", var_name="response"):
                self.violations.append('response["state"] = ...')
        self.generic_visit(node)


class LocalRouteFunctionDetector(ast.NodeVisitor):
    """Collects names of local helper functions that contain forbidden
    routing / mutation / fanout patterns."""

    def __init__(
        self,
        *,
        handler_name: str,
        forbidden_routing: frozenset[str],
        fanout_calls: frozenset[str],
    ) -> None:
        self.handler_name = handler_name
        self.forbidden_routing = forbidden_routing
        self.fanout_calls = fanout_calls
        # func_name -> set of violation descriptions
        self.violations: dict[str, set[str]] = {}

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Skip all M6 retained handlers (they are checked separately via the
        # body-purity tests).  A module may house multiple retained handlers
        # (e.g. _tiebreaker_impl.py); we must not flag one as a "local route
        # function" of another.
        if node.name in M6_RETAINED_HANDLERS:
            self.generic_visit(node)
            return

        func_violations: set[str] = set()

        # Check for state-mutation assignments
        mutation_visitor = StateMutationVisitor()
        mutation_visitor.visit(node)
        for v in mutation_visitor.violations:
            func_violations.add(f"state mutation: {v}")

        # Check for forbidden routing calls
        calls = collect_call_names(node)
        routing = calls & self.forbidden_routing
        if routing:
            func_violations.add(f"routing calls: {sorted(routing)}")

        # Check for fanout dispatch calls
        fanout = calls & self.fanout_calls
        if fanout:
            func_violations.add(f"fanout dispatch: {sorted(fanout)}")

        if func_violations:
            self.violations[node.name] = func_violations

        # Recurse into nested function defs
        self.generic_visit(node)


def check_handler_body_purity(
    func: ast.FunctionDef,
    *,
    forbidden_routing: frozenset[str] | None = None,
    fanout_calls: frozenset[str] | None = None,
) -> set[str]:
    """Return a set of violation descriptions found in *func*'s body.

    By default uses the M6 retained-handler purity bar, but callers may
    override via keyword arguments.
    """
    if forbidden_routing is None:
        forbidden_routing = M6_FORBIDDEN_ROUTING_CALLS
    if fanout_calls is None:
        fanout_calls = M6_FANOUT_DISPATCH_CALLS

    violations: set[str] = set()

    # State-mutation
    mutation_visitor = StateMutationVisitor()
    mutation_visitor.visit(func)
    for v in mutation_visitor.violations:
        violations.add(f"state mutation: {v}")

    # Routing / next-step calls
    calls = collect_call_names(func)
    routing = calls & forbidden_routing
    if routing:
        violations.add(f"routing calls: {sorted(routing)}")

    # Fanout dispatch
    fanout = calls & fanout_calls
    if fanout:
        violations.add(f"fanout dispatch: {sorted(fanout)}")

    return violations


__all__ = [
    # Classification data
    "ALL_HANDLER_NAMES",
    "HANDLER_FILE_MAP",
    "HANDLER_MODULE",
    "M6_FANOUT_DISPATCH_CALLS",
    "M6_FORBIDDEN_ROUTING_CALLS",
    "M6_RETAINED_HANDLERS",
    "M6_RETAINED_MODULE_RELS",
    "MECHANICAL_TRANSITION_HANDLERS",
    "PURE_PHASE_BODIES",
    "REPORT_SEMANTIC_OWNERS",
    "ROUTING_CALL_MARKERS",
    # AST helpers
    "collect_call_names",
    "find_function",
    "handler_source",
    "is_state_subscript_assign",
    "megaplan_root",
    "parse_source",
    # Visitors
    "LocalRouteFunctionDetector",
    "StateMutationVisitor",
    # Purity check
    "check_handler_body_purity",
]
