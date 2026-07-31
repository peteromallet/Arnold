"""Producer-only runner for the deployed M11 workflow canary.

The runner drives real Megaplan handlers with a deterministic decision adapter.
The adapter replaces only model inference; custody, WBC, boundary, suspension,
tiebreaker, suite and acceptance writes remain owned by their production
entrypoints.  This module never writes the semantic verdict.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

from arnold.pipeline.types import EvidenceStatus, TrustClass
from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
from arnold_pipelines.megaplan._core.io import atomic_write_json, read_json
from arnold_pipelines.megaplan.chain.spec import ChainState
from arnold_pipelines.megaplan.cli import build_parser
from arnold_pipelines.megaplan.handlers import (
    handle_critique,
    handle_gate,
    handle_override,
    handle_plan,
    handle_prep,
    handle_revise,
    handle_tiebreaker_decide,
    handle_tiebreaker_run,
)
from arnold_pipelines.megaplan.handlers.init import handle_init
from arnold_pipelines.megaplan.handlers import shared as shared_handlers
from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
    AcceptanceSnapshot,
    run_acceptance_boundary,
)
from arnold_pipelines.megaplan.orchestration.completion_contract import (
    CompletionContext,
)
from arnold_pipelines.megaplan.orchestration.completion_io import (
    commit_acceptance_commit,
    prepare_acceptance_commit,
)
from arnold_pipelines.megaplan.orchestration.evidence_contract import EvidenceRef
from arnold_pipelines.megaplan.planning.state import STATE_TIEBREAKER_READY
from arnold_pipelines.megaplan.workers import WorkerResult
from arnold_pipelines.megaplan.workers._mock_payloads import _build_mock_payload

from .m11_live_canary import _atomic_json, _digest, _load_hashed_json, _sha256_file, _utc_now


RUN_KIND = "deployed_workflow_canary_run"
MANIFEST_KIND = "deployed_workflow_canary_frozen_manifest"
PRODUCER_ID = "megaplan.m11_workflow_canary.runner.v1"
ADAPTER_ID = "megaplan.m11_workflow_canary.deterministic_decision_adapter.v1"
SCENARIOS = (
    "fresh_plan",
    "resume_from_suspension",
    "three_gate_iterations",
    "tiebreaker",
)


class CanaryRunError(RuntimeError):
    pass


def _json_digest(value: Any) -> str:
    return "sha256:" + _digest(value)


def _worker(step: str, state: dict[str, Any], plan_dir: Path) -> WorkerResult:
    payload = _build_mock_payload(step, state, plan_dir)
    if step in {"plan", "revise"}:
        for criterion in payload.get("success_criteria", []):
            if (
                isinstance(criterion, dict)
                and criterion.get("priority") == "must"
                and not criterion.get("requires")
            ):
                criterion["requires"] = ["run_tests"]
    if step == "prep":
        payload["open_questions"] = [
            {
                "question": "Confirm the admitted deployment target.",
                "severity": "blocking",
            }
        ]
    if step == "gate":
        payload.update(
            {
                "recommendation": "ITERATE",
                "rationale": "Canary intentionally exercises another revision.",
                "signals_assessment": "Deterministic canary iteration.",
                "flag_resolutions": [],
            }
        )
    if step == "revise":
        payload["plan"] = (
            str(payload["plan"]).rstrip()
            + f"\n\nCanary revision generation: {int(state.get('iteration', 0)) + 1}.\n"
        )
    return WorkerResult(
        payload=payload,
        raw_output=json.dumps(payload, sort_keys=True),
        duration_ms=1,
        cost_usd=0.0,
        session_id=f"canary-{step}",
        worker_channel="deterministic-canary-adapter",
        auth_channel="local-runtime",
        auth_metadata={
            "producer_id": PRODUCER_ID,
            "adapter_id": ADAPTER_ID,
            "non_authoritative_model_decision": True,
        },
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=2,
    )


@contextmanager
def _deterministic_decisions() -> Iterator[None]:
    """Replace inference only while retaining the real handler write path."""

    original = shared_handlers.worker_module.run_step_with_worker

    def dispatch(
        step: str,
        state: dict[str, Any],
        plan_dir: Path,
        _args: argparse.Namespace,
        **_kwargs: Any,
    ) -> tuple[WorkerResult, str, str, bool]:
        return _worker(step, state, plan_dir), "canary-adapter", "canary", False

    shared_handlers.worker_module.run_step_with_worker = dispatch
    try:
        yield
    finally:
        shared_handlers.worker_module.run_step_with_worker = original


@contextmanager
def _deterministic_prep_decision() -> Iterator[None]:
    """Inject the prep model result while preserving ``handle_prep`` custody."""

    from arnold_pipelines.megaplan.orchestration import prep_research

    original = prep_research.run_prep_orchestration

    def dispatch(
        state: dict[str, Any],
        plan_dir: Path,
        *,
        root: Path,
    ) -> Any:
        del root
        worker = _worker("prep", state, plan_dir)
        return SimpleNamespace(
            worker=worker,
            agent="canary-adapter",
            mode="canary",
            refreshed=False,
            summary="Deterministic canary prep requested clarification.",
            artifacts=["prep.json"],
            prep_metrics_hash=_json_digest({"adapter_id": ADAPTER_ID}),
        )

    prep_research.run_prep_orchestration = dispatch
    try:
        yield
    finally:
        prep_research.run_prep_orchestration = original


@contextmanager
def _single_lens_critique() -> Iterator[None]:
    """Keep the canary in the real critique handler without process fan-out."""

    from arnold_pipelines.megaplan.orchestration import critique_runtime

    original = critique_runtime.select_active_checks

    def select(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        checks = list(original(*args, **kwargs))
        if not checks:
            raise CanaryRunError("canonical critique selected no checks")
        return checks[:1]

    critique_runtime.select_active_checks = select
    try:
        yield
    finally:
        critique_runtime.select_active_checks = original


def _args(plan: str, **overrides: Any) -> argparse.Namespace:
    values: dict[str, Any] = {
        "plan": plan,
        "agent": None,
        "hermes": None,
        "phase_model": [],
        "profile": None,
        "fresh": False,
        "persist": False,
        "ephemeral": False,
        "robustness": None,
        "auto_approve": None,
        "strict_notes": None,
        "progress_emitter": None,
        "actor": "workflow-canary",
        "reason": "deployed workflow canary",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _init(runtime_root: Path, project_dir: Path, scenario: str) -> tuple[str, Path]:
    runtime_root.mkdir(parents=True, exist_ok=False)
    parsed = build_parser().parse_args(["init"])
    args = argparse.Namespace(**vars(parsed))
    args.project_dir = str(project_dir)
    args.idea = f"Exercise canonical deployed workflow scenario {scenario}."
    args.name = f"canary-{scenario.replace('_', '-')}"
    args.robustness = "standard"
    args.prep_clarify = True
    response = handle_init(runtime_root, args)
    plan = str(response["plan"])
    return plan, runtime_root / ".megaplan" / "plans" / plan


def _load_state(plan_dir: Path) -> dict[str, Any]:
    payload = read_json(plan_dir / "state.json")
    if not isinstance(payload, dict):
        raise CanaryRunError(f"invalid state in {plan_dir}")
    return payload


class _ScenarioEvidenceProvider:
    kind = "workflow_canary_scenario"

    def collect(self, ctx: CompletionContext) -> EvidenceRef:
        marker = ctx.plan_dir / "scenario-produced.json"
        try:
            payload = read_json(marker)
        except Exception:
            payload = None
        valid = (
            isinstance(payload, dict)
            and payload.get("producer_id") == PRODUCER_ID
            and payload.get("adapter_id") == ADAPTER_ID
            and isinstance(payload.get("handler_outputs"), list)
            and bool(payload["handler_outputs"])
        )
        return EvidenceRef(
            kind=self.kind,
            status=EvidenceStatus.satisfied if valid else EvidenceStatus.unsatisfied,
            summary="canonical handler scenario evidence present" if valid else "missing canonical handler producer provenance",
            details={"marker": str(marker), "producer_id": payload.get("producer_id") if isinstance(payload, dict) else None},
            trust_class=TrustClass.evidence,
            provider=type(self).__name__,
            provider_version="1",
            source=str(marker),
        )


def _accept(
    *,
    plan_dir: Path,
    project_dir: Path,
    scenario: str,
    admission: dict[str, Any],
) -> dict[str, Any]:
    revision = str(admission["deployment"]["expected_revision"])
    runtime_identity = str(admission["runtime_receipt"]["runtime_identity"])
    tx_id = f"workflow-canary-{scenario}"
    snapshot = AcceptanceSnapshot(
        transaction_id=tx_id,
        chain_run_id=str(admission["job_id"]),
        milestone_label=scenario,
        milestone_index=0,
        plan_name=plan_dir.name,
        source_commit_ref=revision,
        runtime_identity=runtime_identity,
        evidence=(),
    )
    suite_command = (
        f"{sys.executable} -m pytest -q "
        "tests/cloud/test_m11_workflow_canary.py::test_admission_pins_exact_deployment_and_derives_runtime_identity"
    )
    result = run_acceptance_boundary(
        snapshot,
        project_dir=project_dir,
        plan_dir=plan_dir,
        state=_load_state(plan_dir),
        suite_config={
            "test_command": suite_command,
            "test_baseline_timeout": 180,
            "test_idle_timeout": 60,
        },
        mode="atomic",
        providers=(_ScenarioEvidenceProvider(),),
        require_full_boundary=False,
    )
    if not result.accepted:
        raise CanaryRunError(
            f"{scenario} acceptance failed: {list(result.failure_reasons)}"
        )
    spec_path = plan_dir / "canary-chain.yaml"
    spec_path.write_text(f"milestones:\n  - label: {scenario}\n", encoding="utf-8")
    commit_plan = prepare_acceptance_commit(
        plan_dir=plan_dir,
        spec_path=spec_path,
        result=result,
        state=ChainState(),
        contract_id="m11-workflow-canary",
        contract_boundary_id=f"canary:{scenario}",
        commit_ref=revision,
        tip_ref=revision,
    )
    committed = commit_acceptance_commit(commit_plan)
    if not committed.committed:
        raise CanaryRunError(
            f"{scenario} acceptance CAS failed: {list(committed.violations)}"
        )
    acceptance = {
        "snapshot_hash": snapshot.content_hash,
        "transaction_id": tx_id,
        "suite_identity": result.suite_identity,
        "suite_status": result.suite_status,
        "commands": list(result.commands),
        "committed_transaction": str(commit_plan.committed_tx_path.relative_to(plan_dir)),
        "chain_state": str(commit_plan.state_path.relative_to(plan_dir.parent.parent.parent)),
    }
    atomic_write_json(plan_dir / "acceptance-result.json", acceptance)
    return acceptance


def _produce_marker(plan_dir: Path, scenario: str, outputs: list[dict[str, Any]]) -> None:
    atomic_write_json(
        plan_dir / "scenario-produced.json",
        {
            "schema": "arnold.megaplan.m11_workflow_canary.scenario.v1",
            "scenario_id": scenario,
            "producer_id": PRODUCER_ID,
            "adapter_id": ADAPTER_ID,
            "handler_outputs": outputs,
            "produced_at": _utc_now(),
        },
    )


def _fresh(runtime_root: Path, project_dir: Path, admission: dict[str, Any]) -> Path:
    plan, plan_dir = _init(runtime_root, project_dir, "fresh_plan")
    with _deterministic_decisions():
        response = handle_plan(runtime_root, _args(plan))
    _produce_marker(plan_dir, "fresh_plan", [{"entrypoint": "handle_plan", "response": response}])
    _accept(plan_dir=plan_dir, project_dir=project_dir, scenario="fresh_plan", admission=admission)
    return plan_dir


def _resume(runtime_root: Path, project_dir: Path, admission: dict[str, Any]) -> Path:
    plan, plan_dir = _init(runtime_root, project_dir, "resume_from_suspension")
    state = _load_state(plan_dir)
    state["config"]["prep_clarify"] = True
    atomic_write_json(plan_dir / "state.json", state)
    with _deterministic_prep_decision():
        prep = handle_prep(runtime_root, _args(plan))
    override = handle_override(
        runtime_root,
        _args(plan, override_action="resume-clarify"),
    )
    _produce_marker(
        plan_dir,
        "resume_from_suspension",
        [
            {"entrypoint": "handle_prep", "response": prep},
            {"entrypoint": "handle_override", "response": override},
        ],
    )
    _accept(plan_dir=plan_dir, project_dir=project_dir, scenario="resume_from_suspension", admission=admission)
    return plan_dir


def _three_gates(runtime_root: Path, project_dir: Path, admission: dict[str, Any]) -> Path:
    plan, plan_dir = _init(runtime_root, project_dir, "three_gate_iterations")
    state = _load_state(plan_dir)
    state["config"]["adaptive_critique"] = False
    atomic_write_json(plan_dir / "state.json", state)
    outputs: list[dict[str, Any]] = []
    with _deterministic_decisions(), _single_lens_critique():
        outputs.append({"entrypoint": "handle_plan", "response": handle_plan(runtime_root, _args(plan))})
        outputs.append({"entrypoint": "handle_critique", "response": handle_critique(runtime_root, _args(plan))})
        for index in range(3):
            outputs.append({"entrypoint": "handle_gate", "iteration": index + 1, "response": handle_gate(runtime_root, _args(plan))})
            if index < 2:
                outputs.append({"entrypoint": "handle_revise", "response": handle_revise(runtime_root, _args(plan))})
                outputs.append({"entrypoint": "handle_critique", "response": handle_critique(runtime_root, _args(plan))})
    _produce_marker(plan_dir, "three_gate_iterations", outputs)
    _accept(plan_dir=plan_dir, project_dir=project_dir, scenario="three_gate_iterations", admission=admission)
    return plan_dir


def _tiebreaker(runtime_root: Path, project_dir: Path, admission: dict[str, Any]) -> Path:
    plan, plan_dir = _init(runtime_root, project_dir, "tiebreaker")
    state = _load_state(plan_dir)
    state["current_state"] = STATE_TIEBREAKER_READY
    state["iteration"] = 1
    plan_path = plan_dir / "plan_v1.md"
    plan_path.write_text("# Canary tiebreaker plan\n", encoding="utf-8")
    state["plan_versions"] = [
        {
            "version": 1,
            "file": plan_path.name,
            "hash": _sha256_file(plan_path),
            "timestamp": _utc_now(),
        }
    ]
    atomic_write_json(plan_dir / "state.json", state)
    atomic_write_json(
        plan_dir / "gate.json",
        {
            "tiebreaker_question": "Which admitted deterministic option is safer?",
            "tiebreaker_flag_ids": [],
            "tiebreaker_fuzzy_group_id": "canary-group",
        },
    )
    atomic_write_json(plan_dir / "tiebreaker_researcher.json", {"recommendation": "A", "evidence": ["canary"]})
    atomic_write_json(plan_dir / "tiebreaker_challenger.json", {"recommendation": "B", "evidence": ["canary"]})
    outputs: list[dict[str, Any]] = []
    for phase in ("tiebreaker_researcher", "tiebreaker_challenger", "tiebreaker_synthesis"):
        outputs.append(
            {
                "entrypoint": "handle_tiebreaker_run",
                "phase": phase,
                "response": handle_tiebreaker_run(runtime_root, _args(plan, node_id=phase)),
            }
        )
    outputs.append(
        {
            "entrypoint": "handle_tiebreaker_decide",
            "phase": "tiebreaker_decision",
            "response": handle_tiebreaker_decide(
                runtime_root,
                _args(
                    plan,
                    node_id="tiebreaker_decision",
                    action="pick",
                    pick="A",
                    rationale="Deterministic canary decision.",
                ),
            ),
        }
    )
    _produce_marker(plan_dir, "tiebreaker", outputs)
    _accept(plan_dir=plan_dir, project_dir=project_dir, scenario="tiebreaker", admission=admission)
    return plan_dir


def _checkpoint_sqlite(root: Path) -> None:
    resolved_root = root.resolve()
    for candidate in gc.get_objects():
        if not isinstance(candidate, SqliteAttemptLedgerStore):
            continue
        db_path = Path(getattr(candidate, "_db_path", "")).resolve()
        try:
            db_path.relative_to(resolved_root)
        except ValueError:
            continue
        candidate.close()
    gc.collect()
    for path in root.rglob("*.sqlite3"):
        connection = sqlite3.connect(path)
        try:
            row = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if row is not None and int(row[0]) != 0:
                raise CanaryRunError(f"SQLite checkpoint remained busy for {path}: {row}")
        finally:
            connection.close()
    gc.collect()
    # SQLite is allowed to leave empty/reusable WAL bookkeeping files after a
    # successful TRUNCATE checkpoint.  They are not evidence and would make
    # the frozen bundle platform-dependent, so remove only these validated
    # sidecars after every database reported a non-busy checkpoint.
    for sidecar in [
        path for path in root.rglob("*") if path.name.endswith(("-wal", "-shm"))
    ]:
        sidecar.unlink(missing_ok=True)
    leftovers = [path for path in root.rglob("*") if path.name.endswith(("-wal", "-shm"))]
    if leftovers:
        raise CanaryRunError(f"SQLite sidecars remain after checkpoint: {leftovers}")


def _inventory(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        records.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return records


def run_deployed_workflow_canary(
    *,
    root: Path,
    project_dir: Path,
) -> dict[str, Any]:
    workflow_dir = root / "workflow-canary"
    admission = _load_hashed_json(workflow_dir / "admission.json")
    evidence_root = root / "workflow-canary-evidence"
    if evidence_root.exists():
        raise CanaryRunError("workflow canary evidence already exists; use a fresh admitted root")
    started_at = _utc_now()
    evidence_root.mkdir(parents=True)
    prior_audit = os.environ.get("MEGAPLAN_AUDIT_DIR")
    os.environ["MEGAPLAN_AUDIT_DIR"] = str(evidence_root / "_audit")
    try:
        scenario_dirs = {
            "fresh_plan": _fresh(evidence_root / "fresh_plan", project_dir, admission),
            "resume_from_suspension": _resume(evidence_root / "resume_from_suspension", project_dir, admission),
            "three_gate_iterations": _three_gates(evidence_root / "three_gate_iterations", project_dir, admission),
            "tiebreaker": _tiebreaker(evidence_root / "tiebreaker", project_dir, admission),
        }
    finally:
        if prior_audit is None:
            os.environ.pop("MEGAPLAN_AUDIT_DIR", None)
        else:
            os.environ["MEGAPLAN_AUDIT_DIR"] = prior_audit
    _checkpoint_sqlite(evidence_root)
    run_record = {
        "schema": "arnold.megaplan.m11_workflow_canary.run.v1",
        "kind": RUN_KIND,
        "producer_id": PRODUCER_ID,
        "adapter_id": ADAPTER_ID,
        "admission_sha256": admission["content_sha256"],
        "job_id": admission["job_id"],
        "started_at": started_at,
        "completed_at": _utc_now(),
        "scenarios": {
            name: {"plan_dir": path.relative_to(evidence_root).as_posix()}
            for name, path in scenario_dirs.items()
        },
    }
    run_record["content_sha256"] = _digest(run_record)
    _atomic_json(evidence_root / "run.json", run_record, exclusive=True)
    manifest = {
        "schema": "arnold.megaplan.m11_workflow_canary.frozen_manifest.v1",
        "kind": MANIFEST_KIND,
        "producer_id": PRODUCER_ID,
        "admission_sha256": admission["content_sha256"],
        "evidence_root": str(evidence_root),
        "frozen_at": _utc_now(),
        "files": _inventory(evidence_root),
    }
    manifest["content_sha256"] = _digest(manifest)
    _atomic_json(workflow_dir / "frozen-manifest.json", manifest, exclusive=True)
    return manifest


__all__ = [
    "ADAPTER_ID",
    "CanaryRunError",
    "MANIFEST_KIND",
    "PRODUCER_ID",
    "RUN_KIND",
    "run_deployed_workflow_canary",
]
