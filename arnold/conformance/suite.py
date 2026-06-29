"""Conformance suite runner — aggregates Arnold conformance checks.

This module provides :func:`run_conformance_suite`, which accepts a registry,
pipelines, adapter kinds/invocations, and sample ``ContractResult`` instances,
wiring the four check domains into a single ``ConformanceSuiteResult`` while
keeping every underlying check callable independently.

The check domains
-----------------
* **Adapter protocol** — :mod:`arnold.conformance.checks` (fail-closed resolution,
  registry round-trips, smoke invocations).
* **Contract schema** — :mod:`arnold.conformance.checks` (JSON round-trip fidelity,
  schema-version skew detection, empty-schema-version acceptance).
* **Routing vocabulary** — :mod:`arnold.conformance.routing` (vocabulary coverage,
  edge consistency, resolve-edge normal/decision/override/halt/unmatched
  behaviour).
* **Join delegation** — :mod:`arnold.conformance.join` (delegation to
  ``stage.join``, child-result forwarding, context forwarding).
* **Generic Arnold anti-coupling** — :mod:`arnold.conformance.checks`
  (ratcheted detection of Megaplan imports outside the Megaplan pipeline).

No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from arnold.conformance import ConformanceCheckResult, ConformanceSuiteResult
from arnold.conformance.checks import (
    check_adapter_protocol_conformance,
    check_adapter_registry_round_trip,
    check_adapter_smoke_invocation,
    check_adapter_unknown_kind_fail_closed,
    check_contract_result_empty_schema_version_accepted,
    check_contract_result_schema_round_trip,
    check_contract_result_schema_version_skew,
    check_generic_arnold_megaplan_coupling,
    check_import_coupling,
    check_never_port_artifacts,
    check_package_name_staleness,
    check_public_workflow_layering,
    check_semantic_coupling,
)
from arnold.conformance.join import run_join_conformance_suite
from arnold.conformance.routing import run_routing_conformance_suite
from arnold.execution.registries import ExecutionRegistries
from arnold.pipeline.types import ContractResult, Pipeline


class JoinHooks(Protocol):
    def join_parallel_results(self, stage: Any, ctx: Any, child_results: list[Any]) -> Any: ...

_CHECK_ALLOWLIST_PATH = Path(__file__).resolve().parent / "_allowlist.txt"


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------


def run_conformance_suite(
    *,
    registry: ExecutionRegistries | None = None,
    pipelines: Sequence[Pipeline] | None = None,
    adapter_smoke_kinds: Sequence[tuple[str, Mapping[str, Any]]] | None = None,
    adapter_round_trip_kinds: Sequence[str] | None = None,
    sample_contracts: Sequence[ContractResult] | None = None,
    hooks: JoinHooks | Sequence[JoinHooks] | None = None,
    suite_id: str = "ar1-conformance",
) -> ConformanceSuiteResult:
    """Run Arnold conformance-check domains and aggregate into one result.

    Every underlying check function remains independently callable.  This
    runner is a convenience aggregator that preserves per-check diagnostics
    (``check_id``, ``passed``, ``message``, ``details``) without altering
    production pipeline semantics.

    Parameters
    ----------
    registry:
        The adapter registry to validate.  When *None* a fresh fail-closed
        ``ExecutionRegistries()`` is constructed inside the adapter
        checks.
    pipelines:
        One or more ``Pipeline`` instances to check for routing-vocabulary
        and resolve-edge conformance.  When *None* or empty, routing checks
        are skipped.
    adapter_smoke_kinds:
        Optional ``(kind, invocation)`` pairs for per-adapter smoke
        invocations.  Each pair must have *kind* already registered in
        *registry*.
    adapter_round_trip_kinds:
        Optional list of registered kind names whose adapters should survive
        a resolve → re-resolve round-trip.
    sample_contracts:
        Optional ``ContractResult`` instances to use in schema round-trip
        checks.  When *None*, the generic schema checks (skew detection,
        empty-version acceptance) still run, but per-contract round-trips
        use the default representative ``ContractResult`` from
        :func:`check_contract_result_schema_round_trip`.
    hooks:
        The hook implementation for join-delegation checks.  When *None*,
        conformance-local default join hooks are used (which delegate by default).
    suite_id:
        Identifier for the returned ``ConformanceSuiteResult``.

    Returns
    -------
    ConformanceSuiteResult
        Aggregate result with all individual checks preserved in ``checks``.
    """
    results: list[ConformanceCheckResult] = []

    # ------------------------------------------------------------------
    # Domain 1 — Adapter protocol
    # ------------------------------------------------------------------
    results.append(
        check_adapter_protocol_conformance(
            registry,
            smoke_kind=None,
            smoke_invocation=None,
        )
    )
    results.append(check_adapter_unknown_kind_fail_closed(registry))

    for kind, invocation in (adapter_smoke_kinds or []):
        results.append(
            check_adapter_smoke_invocation(
                registry or ExecutionRegistries(),
                kind,
                invocation,
            )
        )

    for kind in (adapter_round_trip_kinds or []):
        results.append(
            check_adapter_registry_round_trip(
                registry or ExecutionRegistries(),
                kind,
            )
        )

    # ------------------------------------------------------------------
    # Domain 2 — Contract result schema
    # ------------------------------------------------------------------
    results.append(check_contract_result_schema_version_skew())
    results.append(check_contract_result_empty_schema_version_accepted())

    if sample_contracts:
        for contract in sample_contracts:
            results.append(
                check_contract_result_schema_round_trip(contract=contract)
            )
    else:
        results.append(check_contract_result_schema_round_trip())

    # ------------------------------------------------------------------
    # Domain 3 — Routing vocabulary & resolve-edge
    # ------------------------------------------------------------------
    for pipeline in (pipelines or []):
        results.extend(run_routing_conformance_suite(pipeline))

    # ------------------------------------------------------------------
    # Domain 4 — Join delegation
    # ------------------------------------------------------------------
    hook_targets: Sequence[JoinHooks | None]
    if hooks is None:
        hook_targets = (None,)
    elif isinstance(hooks, Sequence):
        hook_targets = hooks
    else:
        hook_targets = (hooks,)
    for hook_target in hook_targets:
        results.extend(run_join_conformance_suite(hook_target))

    # ------------------------------------------------------------------
    # Domain 5 — Generic Arnold anti-coupling ratchet
    # ------------------------------------------------------------------
    results.append(check_generic_arnold_megaplan_coupling())
    allowlist = _read_check_allowlist(_CHECK_ALLOWLIST_PATH)
    results.append(check_import_coupling(allowlist=allowlist["import-coupling"]))
    results.append(
        check_package_name_staleness(
            allowlist=allowlist["package-name-staleness"]
        )
    )
    results.append(
        check_semantic_coupling(allowlist=allowlist["semantic-coupling"])
    )
    results.append(
        check_public_workflow_layering(
            allowlist=allowlist["public-workflow-layering"]
        )
    )
    results.append(
        check_never_port_artifacts(allowlist=allowlist["never-port-artifacts"])
    )

    return ConformanceSuiteResult(
        suite_id=suite_id,
        checks=tuple(results),
    )


def _read_check_allowlist(path: Path) -> dict[str, set[str]]:
    allowlist: dict[str, set[str]] = {
        "import-coupling": set(),
        "package-name-staleness": set(),
        "semantic-coupling": set(),
        "public-workflow-layering": set(),
        "never-port-artifacts": set(),
    }
    if not path.exists():
        return allowlist
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        check_id, item = parts
        if check_id in allowlist:
            allowlist[check_id].add(item)
    return allowlist


__all__ = [
    "run_conformance_suite",
]
