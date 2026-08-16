"""Maintenance package layering and lifecycle-mutation boundary conformance (M2, T24).

Static + dynamic proof that the Maintenance substrate holds its boundaries:

* Maintenance remains under ``arnold_pipelines.megaplan`` — the package lives
  at ``arnold_pipelines/megaplan/maintenance`` and no Maintenance module
  imports a neutral ``arnold.*`` package (no policy inversion);
* neutral ``arnold.*`` packages do not import Megaplan policy — the generic
  coupling ratchet still passes, and no neutral module imports the new
  ``arnold_pipelines.megaplan.maintenance`` package;
* Maintenance sources do not import lifecycle writers — no Maintenance module
  imports ``_core.state`` (``write_plan_state``), ``chain.spec``
  (``save_chain_state``), or ``orchestration.transition_policy``
  (``TransitionWriter``), and the writer names never appear in Maintenance
  source;
* no Maintenance module instantiates a lease, validator, attempt store,
  completion engine, queue, or transition writer (AST call scan);
* direct mutation requests — through ``boundaries``, the dispatch seam, and
  the chain seam — produce the typed ``M7BypassFinding`` with zero writer
  calls (writers monkeypatched to raise) and ``mutation_attempted=False``.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MAINTENANCE_ROOT = REPO_ROOT / "arnold_pipelines" / "megaplan" / "maintenance"
NEUTRAL_ARNOLD_ROOT = REPO_ROOT / "arnold"

#: Module paths that DEFINE the lifecycle/raw plan/chain truth writers.
LIFECYCLE_WRITER_MODULES: tuple[str, ...] = (
    "arnold_pipelines.megaplan._core.state",  # write_plan_state
    "arnold_pipelines.megaplan.chain.spec",  # save_chain_state
    "arnold_pipelines.megaplan.orchestration.transition_policy",  # TransitionWriter
)

#: Forbidden lifecycle/raw writer names in Maintenance source.
FORBIDDEN_WRITER_NAMES: tuple[str, ...] = (
    "write_plan_state",
    "save_chain_state",
    "TransitionWriter",
    "RuntimeTransitionWriter",
)

#: Authority/mutation substrate class names a Maintenance module must never
#: instantiate: leases, validators, attempt stores, completion engines,
#: queues, and transition writers.
FORBIDDEN_SUBSTRATE_CLASSES: tuple[str, ...] = (
    # leases
    "CustodyLeaseStore",
    "CapacityLease",
    "ExecutionLease",
    "LivenessLeasePublisher",
    # validators
    "RollbackValidator",
    # attempt stores
    "AttemptLedgerStore",
    "SqliteAttemptLedgerStore",
    # completion engines
    "CompletionSubject",
    "CompletionVerdict",
    "CompletionContext",
    "ManagedCompletionTurnResult",
    "SixHourAuditorCompletionEvidence",
    # queues
    "ManagedAgentQueueSweepResult",
    "QueueSprintsInput",
    "SubagentQueueError",
    # transition writers
    "TransitionWriter",
    "RuntimeTransitionWriter",
)


def _maintenance_modules() -> list[Path]:
    return sorted(MAINTENANCE_ROOT.glob("*.py"))


def _imported_module_names(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


# ---------------------------------------------------------------------------
# Static: package location and one-way import direction
# ---------------------------------------------------------------------------


def test_maintenance_package_remains_under_arnold_pipelines_megaplan() -> None:
    # The package lives exactly at arnold_pipelines/megaplan/maintenance and
    # there is no neutral-arnold mirror of it.
    assert MAINTENANCE_ROOT.is_dir()
    assert (MAINTENANCE_ROOT / "__init__.py").is_file()
    assert not (NEUTRAL_ARNOLD_ROOT / "maintenance").exists()


def test_maintenance_modules_never_import_neutral_arnold_packages() -> None:
    violations: dict[str, list[str]] = {}
    for source in _maintenance_modules():
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        hits = [
            name
            for name in _imported_module_names(tree)
            if name == "arnold" or name.startswith("arnold.")
        ]
        if hits:
            violations[source.name] = hits
    # The one allowed seam: a function-local import of the pure read helper
    # ``canonical_event_json`` from the neutral attempt-ledger module.  No
    # other neutral arnold.* module may be imported by Maintenance.
    assert set(violations) <= {"sources.py"}, violations
    if "sources.py" in violations:
        assert violations["sources.py"] == ["arnold.workflow.attempt_ledger_store"]


def test_maintenance_read_helper_seam_imports_no_store_classes() -> None:
    """The attempt-ledger seam imports only the pure canonicalization helper."""
    source = MAINTENANCE_ROOT / "sources.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == (
            "arnold.workflow.attempt_ledger_store"
        ):
            imported.extend(alias.name for alias in node.names)
    assert imported == ["canonical_event_json"], imported
    assert "AttemptLedgerStore" not in imported
    assert "SqliteAttemptLedgerStore" not in imported


def test_neutral_arnold_packages_do_not_import_maintenance_policy() -> None:
    violations: dict[str, list[str]] = {}
    for source in sorted(NEUTRAL_ARNOLD_ROOT.rglob("*.py")):
        if "__pycache__" in source.parts:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        hits = [
            name
            for name in _imported_module_names(tree)
            if name == "arnold_pipelines.megaplan.maintenance"
            or name.startswith("arnold_pipelines.megaplan.maintenance.")
        ]
        if hits:
            violations[str(source.relative_to(REPO_ROOT))] = hits
    assert violations == {}, (
        f"neutral arnold.* packages import Maintenance policy: {violations}"
    )


def test_generic_arnold_megaplan_coupling_ratchet_still_passes() -> None:
    from arnold.conformance.checks import check_generic_arnold_megaplan_coupling

    result = check_generic_arnold_megaplan_coupling()
    assert result.passed is True
    # The only coupled neutral modules are the known legacy adapter seams; the
    # new Maintenance policy is not among them (maintenance imports are
    # forbidden entirely by the scan above).
    assert result.details["unexpected"] == {}


# ---------------------------------------------------------------------------
# Static: no lifecycle writer imports or names in Maintenance sources
# ---------------------------------------------------------------------------


def test_maintenance_sources_do_not_import_lifecycle_writer_modules() -> None:
    violations: dict[str, list[str]] = {}
    for source in _maintenance_modules():
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        hits = [
            name
            for name in _imported_module_names(tree)
            if name in LIFECYCLE_WRITER_MODULES
        ]
        if hits:
            violations[source.name] = hits
    assert violations == {}, f"Maintenance imports lifecycle writer modules: {violations}"


def test_maintenance_sources_never_reference_lifecycle_writer_names() -> None:
    violations: dict[str, list[str]] = {}
    for source in _maintenance_modules():
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        hits = sorted(
            {
                node.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Name) and node.id in FORBIDDEN_WRITER_NAMES
            }
            | {
                attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Attribute)
                and node.attr in FORBIDDEN_WRITER_NAMES
            }
        )
        if hits:
            violations[source.name] = hits
    assert violations == {}, f"Maintenance references lifecycle writer names: {violations}"


# ---------------------------------------------------------------------------
# Static: no forbidden authority/mutation substrate instantiation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("substrate", FORBIDDEN_SUBSTRATE_CLASSES)
def test_no_maintenance_module_instantiates_forbidden_substrate(
    substrate: str,
) -> None:
    hits: dict[str, int] = {}
    for source in _maintenance_modules():
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        count = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else None
            if name is None and isinstance(func, ast.Attribute):
                name = func.attr
            if name == substrate:
                count += 1
        if count:
            hits[source.name] = count
    assert hits == {}, f"Maintenance instantiates {substrate}: {hits}"


def test_no_maintenance_module_imports_custody_or_attempt_store_packages() -> None:
    forbidden_packages = (
        "arnold_pipelines.megaplan.custody",
        "arnold_pipelines.megaplan.custody.lease_store",
        "arnold_pipelines.megaplan.custody.wbc_runtime",
        "arnold_pipelines.megaplan.orchestration.completion_contract",
        "arnold_pipelines.megaplan.runtime.capacity_lease",
        "arnold_pipelines.megaplan.resident.subagent",
        "arnold_pipelines.megaplan.resident.profile",
    )
    violations: dict[str, list[str]] = {}
    for source in _maintenance_modules():
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        hits = [
            name
            for name in _imported_module_names(tree)
            if name in forbidden_packages
            or any(name.startswith(pkg + ".") for pkg in forbidden_packages)
        ]
        if hits:
            violations[source.name] = hits
    assert violations == {}, f"Maintenance imports substrate packages: {violations}"


# ---------------------------------------------------------------------------
# Dynamic: direct mutation requests produce the typed M7 bypass finding with
# zero writer calls across every mutation-adjacent seam.
# ---------------------------------------------------------------------------


@pytest.fixture
def _guarded_writers(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    import arnold_pipelines.megaplan._core.state as core_state
    import arnold_pipelines.megaplan.chain.spec as chain_spec
    import arnold_pipelines.megaplan.orchestration.transition_policy as transition_policy

    calls: list[str] = []

    def _boom(name: str):
        def _raise(*args: Any, **kwargs: Any) -> Any:
            calls.append(name)
            raise AssertionError(f"{name} must never be called from Maintenance")

        return _raise

    monkeypatch.setattr(core_state, "write_plan_state", _boom("write_plan_state"))
    monkeypatch.setattr(chain_spec, "save_chain_state", _boom("save_chain_state"))
    monkeypatch.setattr(
        transition_policy, "TransitionWriter", _boom("TransitionWriter")
    )
    return calls


def test_boundaries_direct_mutation_requests_are_typed_inert_findings(
    _guarded_writers: list[str],
) -> None:
    from arnold_pipelines.megaplan.maintenance import boundaries

    for kind in ("plan_write", "chain_write"):
        finding = boundaries.bypass_finding(kind, f"direct {kind} write request")
        assert isinstance(finding, boundaries.M7BypassFinding)
        assert finding.kind.value == kind
        assert finding.seam == boundaries.M7_SEAM
        assert finding.mutation_attempted is False
        assert all(
            finding.writer_call_counts.get(writer, 0) == 0
            for writer in boundaries.FORBIDDEN_DIRECT_WRITERS
        )

    plan_finding = boundaries.plan_write_finding("plan truth write request")
    assert plan_finding.kind.value == "plan_write"
    chain_finding = boundaries.chain_write_finding("chain truth write request")
    assert chain_finding.kind.value == "chain_write"
    with pytest.raises(ValueError):
        boundaries.bypass_finding("ledger_write", "invalid kind")
    assert _guarded_writers == []


def test_dispatch_and_chain_seams_route_direct_mutations_to_typed_finding(
    _guarded_writers: list[str],
) -> None:
    from arnold_pipelines.megaplan.chain import chain_direct_write_finding
    from arnold_pipelines.megaplan.cloud.maintenance_dispatch import (
        direct_write_bypass_finding,
    )
    from arnold_pipelines.megaplan.maintenance.boundaries import M7BypassFinding

    dispatch_plan = direct_write_bypass_finding("plan", "dispatch direct plan write")
    dispatch_chain = direct_write_bypass_finding("chain", "dispatch direct chain write")
    chain_plan = chain_direct_write_finding("plan", "chain seam direct plan write")
    chain_chain = chain_direct_write_finding("chain", "chain seam direct chain write")

    for finding in (dispatch_plan, dispatch_chain, chain_plan, chain_chain):
        assert isinstance(finding, M7BypassFinding)
        assert finding.mutation_attempted is False
        assert finding.writer_call_counts == {
            "write_plan_state": 0,
            "save_chain_state": 0,
            "TransitionWriter": 0,
            "raw plan/chain writers": 0,
        }
    assert dispatch_plan.kind.value == "plan_write"
    assert chain_chain.kind.value == "chain_write"
    assert _guarded_writers == []


def test_maintenance_import_graph_does_not_load_chain_or_transition_writers() -> None:
    """Import every Maintenance module and assert no chain/transition writer
    module appears in sys.modules.

    Runs in a fresh subprocess so the assertion is not polluted by modules the
    test session already imported.  ``_core.state`` is deliberately excluded:
    it is a pre-existing transitive dependency of the legacy incident ledger
    (``maintenance.ledger -> incident.ledger -> incident.schema ->
    cloud.redact -> _core.state``), outside the Maintenance boundary;
    Maintenance sources themselves never import it (proven by the AST scan
    above).
    """
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent(
        """
        import importlib, sys
        import arnold_pipelines.megaplan.maintenance  # noqa: F401
        modules = [
            "identity", "contracts", "events", "handoffs", "sources",
            "observation", "ledger", "projections", "shadow", "boundaries",
        ]
        for name in modules:
            importlib.import_module(
                f"arnold_pipelines.megaplan.maintenance.{name}"
            )
        forbidden = {
            "arnold_pipelines.megaplan.orchestration.transition_policy",
            "arnold_pipelines.megaplan.chain.spec",
        }
        loaded = {name for name in sys.modules if name in forbidden}
        if loaded:
            print("FORBIDDEN_LOADED=" + ",".join(sorted(loaded)))
            sys.exit(1)
        print("OK")
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
        env={"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin"},
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "OK" in proc.stdout
