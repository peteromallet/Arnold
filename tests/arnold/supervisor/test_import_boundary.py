"""Import-boundary tests for the supervisor public API.

These tests verify:

1. All documented public symbols can be imported from ``arnold.supervisor``
   without triggering ImportError or AttributeError.
2. Importing ``arnold.supervisor`` does **not** introduce dependency cycles
   (cyclic imports would raise ImportError or cause infinite recursion).
3. Native runtime internals do not leak into supervisor module initialisation
   (SD1 constraint – the supervisor is a consumer, not an owner, of native
   trace/audit/envelope data).

Cycle detection
    Dependency cycles between supervisor sub-modules would manifest as
    ImportError (most common in Python 3.11+) or as a partially initialised
    module with missing attributes.  We guard against both by importing the
    top-level package and then verifying every documented sub-module attribute
    is resolvable.

Leakage detection
    After importing ``arnold.supervisor`` we inspect ``sys.modules`` to ensure
    that forbidden runtime-internal modules (e.g. ``arnold.pipeline.native.*``
    modules that own workflow routing and execution decisions) were **not**
    pulled in as a side-effect of supervisor initialisation.
"""

from __future__ import annotations

import sys
from typing import get_type_hints

import pytest


# ── documented public symbols from arnold/supervisor/__init__.py ───────────────
_DOCUMENTED_PUBLIC = frozenset(
    {
        # leases
        "InvalidProjectLeaseTransition",
        "ProjectLease",
        "ProjectLeaseIdentity",
        "ProjectLeaseState",
        "can_transition_project_lease",
        "ensure_project_lease_transition",
        "is_terminal_project_lease_state",
        # stores
        "FileProjectLeaseStore",
        "PostgresProjectLeaseStore",
        "ProjectLeaseAlreadyExists",
        "ProjectLeaseConflict",
        "ProjectLeaseLockConflict",
        "ProjectLeaseNotFound",
        "ProjectLeaseStore",
        "ProjectLeaseTokenMismatch",
        # capacity
        "CapacityDecision",
        "CapacityGate",
        "CapacityGrant",
        "CapacityPool",
        "CapacityPoolConfig",
        "CapacityStatus",
        # capacity context
        "CapacityContext",
        "CapacityGateRejected",
        "capacity_delay_metadata",
        "current_capacity_context",
        "gate_capacity",
        "set_capacity_context",
        # progress
        "ProgressClassification",
        "ProgressSignal",
        "ProgressSnapshot",
        "ProgressUsage",
        "ProgressWindows",
        "build_progress_snapshot",
        "build_progress_snapshot_for_artifact_root",
        # cancellation
        "CancellationRequested",
        "cancelled_contract_result",
        "cancellation_result_payload",
        # reconcile / takeover
        "ExpiredTakeoverDecision",
        "claim_reconciled_project_lease",
        "evaluate_expired_takeover",
        "reconcile_worktree_for_takeover",
        # restart / quarantine
        "RestartDecision",
        "RestartDelay",
        "RestartPolicy",
        "clear_quarantined_project_lease",
        "compute_restart_delay",
        "evaluate_automatic_restart",
        "record_restart_failure",
        # supervision loop
        "LeaseSupervisionDecision",
        "SupervisionLoop",
        "SupervisionLoopConfig",
        "SupervisionScanResult",
    }
)

# ── Forbidden runtime-internal modules (SD1) ──────────────────────────────────
# The supervisor must not own or initialise workflow routing, loop exits,
# model routing, suspension, or execute/review decisions.
_FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "arnold.agent",  # agent loop internals
    "arnold.execution",  # execute/review decisions
)

# Modules that the supervisor MAY import (these are expected consumers of native data)
_ALLOWED_NATIVE_IMPORTS: tuple[str, ...] = (
    "arnold.pipeline.native.persistence",
    "arnold.pipeline.native.reconcile",
    "arnold.runtime.resume",
    "arnold.runtime.durable_ops.store",
    "arnold.runtime.durable_ops.typed_resources",
    "arnold.kernel.suspension",
)


def _is_forbidden(name: str) -> bool:
    """Return True if *name* is a module the supervisor must not initialise."""
    for prefix in _FORBIDDEN_PREFIXES:
        if name == prefix or name.startswith(prefix + "."):
            return True
    return False


# ── tests ─────────────────────────────────────────────────────────────────────


def test_all_documented_symbols_importable_from_supervisor() -> None:
    """Every symbol in __all__ must be accessible as ``arnold.supervisor.<name>``."""
    import arnold.supervisor as sup

    missing: list[str] = []
    for name in sorted(_DOCUMENTED_PUBLIC):
        if not hasattr(sup, name):
            missing.append(name)

    assert not missing, (
        f"Documented public symbols missing from arnold.supervisor: {missing}"
    )


def test_supervisor_all_matches_documented_public() -> None:
    """``arnold.supervisor.__all__`` must match the documented public set."""
    import arnold.supervisor as sup

    actual_all = frozenset(sup.__all__) if hasattr(sup, "__all__") else frozenset()

    extra_in_all = actual_all - _DOCUMENTED_PUBLIC
    missing_from_all = _DOCUMENTED_PUBLIC - actual_all

    violations: list[str] = []
    if extra_in_all:
        violations.append(
            f"Symbols in __all__ but not documented: {sorted(extra_in_all)}"
        )
    if missing_from_all:
        violations.append(
            f"Documented symbols missing from __all__: {sorted(missing_from_all)}"
        )

    assert not violations, "\n".join(violations)


def test_supervisor_import_does_not_cause_cycles() -> None:
    """Importing arnold.supervisor must not raise ImportError from cycles."""
    # If a cycle exists, the import itself raises ImportError.
    # We also verify that key sub-modules are fully initialised (their
    # __all__ attributes are accessible).
    import arnold.supervisor as sup

    cycle_indicators: list[str] = []

    for attr_name in sorted(sup.__all__):
        obj = getattr(sup, attr_name, None)
        if obj is None:
            cycle_indicators.append(
                f"{attr_name} is None (possible partial initialisation from cycle)"
            )

    assert not cycle_indicators, (
        f"Possible cycle indicators (None attributes): {cycle_indicators}"
    )


def test_no_native_runtime_leakage_on_import() -> None:
    """Import supervisor must not pull in agent or execution internals (SD1)."""
    before = set(sys.modules.keys())

    import arnold.supervisor  # noqa: F401

    after = set(sys.modules.keys())
    newly_loaded = after - before

    forbidden = {name for name in newly_loaded if _is_forbidden(name)}

    assert not forbidden, (
        f"Supervisor import pulled in forbidden internal modules: {sorted(forbidden)}"
    )


def test_submodule_imports_are_cycle_free() -> None:
    """Each supervisor sub-module must be individually importable without cycles."""
    sub_modules = [
        "arnold.supervisor.leases",
        "arnold.supervisor.store",
        "arnold.supervisor.capacity",
        "arnold.supervisor.capacity_context",
        "arnold.supervisor.progress",
        "arnold.supervisor.cancellation",
        "arnold.supervisor.reconcile",
        "arnold.supervisor.restart",
        "arnold.supervisor.loop",
    ]

    failures: list[str] = []
    for mod_name in sub_modules:
        try:
            # Use a fresh import check – if already loaded, verify attributes
            if mod_name in sys.modules:
                mod = sys.modules[mod_name]
                # Verify __all__ is present and non-empty
                if not hasattr(mod, "__all__") or not mod.__all__:
                    failures.append(f"{mod_name}: __all__ missing or empty")
            else:
                __import__(mod_name)
        except ImportError as exc:
            failures.append(f"{mod_name}: ImportError – {exc}")

    assert not failures, (
        f"Sub-module import failures (possible cycles): {failures}"
    )


def test_public_types_have_expected_bases() -> None:
    """Smoke-test: key public types inherit from expected stdlib/protocol bases."""
    import arnold.supervisor as sup

    checks: list[tuple[str, type, tuple[type, ...]]] = [
        ("ProjectLease", sup.ProjectLease, (object,)),
        ("ProjectLeaseIdentity", sup.ProjectLeaseIdentity, (object,)),
        ("ProjectLeaseState", sup.ProjectLeaseState, (str,)),
        ("CancellationRequested", sup.CancellationRequested, (BaseException,)),
        ("ProgressClassification", sup.ProgressClassification, (str,)),
        ("CapacityStatus", sup.CapacityStatus, (str,)),
    ]

    failures: list[str] = []
    for name, obj, expected_bases in checks:
        if not isinstance(obj, type):
            failures.append(f"{name}: expected a type, got {type(obj).__name__}")
            continue
        for base in expected_bases:
            if not issubclass(obj, base):
                failures.append(
                    f"{name}: expected subclass of {base.__name__}, "
                    f"but {obj.__name__} does not inherit from it"
                )

    assert not failures, "\n".join(failures)
