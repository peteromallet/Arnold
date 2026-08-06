from __future__ import annotations

from copy import deepcopy
import ast
import inspect
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan._core import atomic_write_json, atomic_write_text
from arnold_pipelines.megaplan import auto
from arnold_pipelines.megaplan.flags import (
    update_flags_after_critique,
    update_flags_after_gate,
    update_flags_after_revise,
)
from arnold_pipelines.megaplan.handlers.plan import _build_verifiability_flags
from arnold_pipelines.megaplan.handlers.structured_output import promote_scratch
from arnold_pipelines.megaplan.orchestration import critique_custody
from arnold_pipelines.megaplan.orchestration import critique_runtime
from arnold_pipelines.megaplan.orchestration.critique_custody import (
    CritiqueCustodyError,
    assert_finalize_custody,
    bind_finalize_custody,
    migrate_legacy_critique_custody,
    prepare_critique_payload,
    validate_gate_input_custody,
    validate_finalize_resolution_coverage,
    write_critique_clearance,
    write_critique_production_receipt,
)
from arnold_pipelines.megaplan.orchestration.task_feasibility import (
    compile_task_feasibility,
)
from arnold_pipelines.megaplan.workers import WorkerResult
from arnold_pipelines.megaplan.custody.phase_wbc import activate_phase_wbc
from arnold_pipelines.megaplan.custody.worker_dispatch_wbc import (
    build_worker_dispatch_spec,
    query_worker_dispatch_manifest,
)


def _state(project_dir: Path, *, iteration: int = 1, robustness: str = "full") -> dict[str, Any]:
    return {
        "name": "custody-test",
        "iteration": iteration,
        "current_state": "critiqued",
        "config": {
            "mode": "code",
            "project_dir": str(project_dir),
            "robustness": robustness,
        },
        "plan_versions": [{"version": iteration, "file": f"plan_v{iteration}.md"}],
        "history": [],
        "meta": {"current_invocation_id": f"critique-invocation-{iteration}"},
        "last_gate": {},
    }


def test_deterministic_verifiability_flags_carry_source_criterion_evidence() -> None:
    criteria = [
        {
            "criterion": "Architecture remains clear to a human reviewer.",
            "priority": "should",
            "requires": ["subjective_judgment"],
        }
    ]

    flags = _build_verifiability_flags(criteria, {"codex": {"file_read"}})

    assert len(flags) == 1
    assert flags[0]["concern"] == flags[0]["evidence"]
    assert flags[0]["evidence"] == (
        "verifiability_audit: verdict='human_only'; "
        "rationale='Some required capabilities need human verification.'; "
        "missing_capabilities=['subjective_judgment']; "
        "source=success_criteria[0]: criterion='Architecture remains clear to a "
        "human reviewer.'; priority='should'; requires=['subjective_judgment']"
    )
    payload = {
        "checks": [],
        "flags": flags,
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    prepare_critique_payload(payload, expected_check_ids=[])
    assert payload["flags"][0]["id"].startswith("CF-")


def _oversized_payload(*, two_findings: bool = False) -> dict[str, Any]:
    findings = [
        {
            "detail": "Step 2 combines protocol, migration, and broad test objectives; split it.",
            "flagged": True,
        }
    ]
    flags = [
        {
            "id": "scope-god-task-2",
            "concern": "Step 2 is an oversized god-task.",
            "category": "completeness",
            "severity_hint": "likely-significant",
            "evidence": findings[0]["detail"],
            "source_check_id": "scope",
        }
    ]
    if two_findings:
        findings.append(
            {
                "detail": "Step 8 combines three independently reviewable consumers; split it.",
                "flagged": True,
            }
        )
        flags.append(
            {
                "id": "scope-god-task-8",
                "concern": "Step 8 is an oversized god-task.",
                "category": "completeness",
                "severity_hint": "likely-significant",
                "evidence": findings[1]["detail"],
                "source_check_id": "scope",
            }
        )
    return {
        "checks": [{"id": "scope", "question": "Are tasks bounded?", "findings": findings}],
        "flags": flags,
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }


def _producer_binding(
    invocation_id: str = "critique-invocation-1",
    *,
    producer: str = "codex",
    transport: str = "inline_response",
    scratch_status: str = "unmodified",
) -> dict[str, Any]:
    return {
        "schema_version": "megaplan-critique-producer-binding-v1",
        "invocation_id": invocation_id,
        "attempt_index": 0,
        "attempt_id": f"{invocation_id}:0",
        "producer": producer,
        "provider": "openai" if producer == "codex" else None,
        "selected_spec": "codex:gpt-5.4" if producer == "codex" else None,
        "model_actual": "gpt-5.4" if producer == "codex" else None,
        "session_id": None,
        "transport": transport,
        "scratch_status": scratch_status,
        "registered_scratch_artifact": "critique_output.json",
        "output_path_attested": False,
    }


def _persist_critique(
    plan_dir: Path,
    state: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    iteration = state["iteration"]
    atomic_write_text(plan_dir / f"plan_v{iteration}.md", f"# Plan v{iteration}\n\nOversized work.\n")
    atomic_write_text(plan_dir / f"critique_raw_v{iteration}.txt", "raw producer critique")
    prepare_critique_payload(payload, expected_check_ids=["scope"])
    atomic_write_json(plan_dir / f"critique_v{iteration}.json", payload)
    receipt = write_critique_production_receipt(
        plan_dir,
        state,
        payload,
        expected_check_ids=["scope"],
        producer_binding=_producer_binding(state["meta"]["current_invocation_id"]),
    )
    update_flags_after_critique(plan_dir, payload, iteration=iteration)
    return receipt


def _admitted_graph() -> dict[str, Any]:
    payload = {
        "task_contract_version": 2,
        "validation_jobs": [],
        "tasks": [
            {
                "id": "T1",
                "objective": "Implement the bounded critique custody contract.",
                "description": "Implement one independently verifiable contract slice.",
                "kind": "code",
                "complexity": 5,
                "estimated_minutes": 10,
                "depends_on": [],
                "dependency_reasons": {},
                "routing_group": "custody",
                "write_set": {"paths": ["src/custody.py", "tests/test_custody.py"], "complete": True},
                "narrow_tests": {"selectors": ["tests/test_custody.py"], "max_seconds": 120, "max_runs": 2},
                "checkpoint": {"required": False, "max_interval_seconds": 300, "records": []},
            }
        ],
    }
    payload["graph_report"] = compile_task_feasibility(payload, {})
    assert payload["graph_report"]["admitted"] is True
    return payload


def test_valid_oversized_task_finding_survives_normalization_and_reaches_gate(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    payload = _oversized_payload()

    receipt = _persist_critique(plan_dir, state, payload)
    gate_input = validate_gate_input_custody(plan_dir, state)
    canonical_id = payload["flags"][0]["id"]

    assert canonical_id.startswith("CF-")
    assert payload["flags"][0]["producer_flag_id"] == "scope-god-task-2"
    assert receipt["finding_count"] == 1
    assert receipt["normalization"] == {
        "flagged_check_findings": 1,
        "canonical_flags": 1,
        "loss_count": 0,
    }
    assert gate_input["flag_ids"] == [canonical_id]
    assert gate_input["loss_count"] == 0


def _rewrite_receipt_digest(receipt: dict[str, Any]) -> None:
    receipt.pop("receipt_digest", None)
    receipt["receipt_digest"] = critique_custody._digest(receipt)


def _legacy_unbound_fixture(plan_dir: Path, state: dict[str, Any]) -> Path:
    """Reproduce the exact v1-on-v2-filename shape from the preserved r5 run."""
    payload = _oversized_payload()
    receipt = _persist_critique(plan_dir, state, payload)
    iteration = int(state["iteration"])
    producer_path = plan_dir / f"critique_check_scope_producer_v{iteration}.json"
    atomic_write_json(producer_path, payload)
    receipt["schema_version"] = "megaplan-critique-custody-v1"
    receipt.pop("producer_binding")
    receipt.pop("producer_binding_digest")
    receipt["raw_sources"].append(
        {"artifact": producer_path.name, "sha256": critique_custody.sha256_file(producer_path)}
    )
    _rewrite_receipt_digest(receipt)
    receipt_path = plan_dir / f"critique_custody_v{iteration}.json"
    atomic_write_json(receipt_path, receipt)

    critique_sha = receipt["critique_sha256"]
    state["current_state"] = "gated"
    state["history"] = [
        {
            "step": "critique",
            "result": "success",
            "duration_ms": 1234,
            "output_file": receipt["critique_artifact"],
            "artifact_hash": critique_sha,
        }
    ]
    atomic_write_json(plan_dir / "state.json", state)
    atomic_write_json(
        plan_dir / f"step_receipt_critique_v{iteration}.json",
        {
            "phase": "critique",
            "iteration": iteration,
            "duration_ms": 1234,
            "upstream_artifact_hashes": [receipt["plan_sha256"]],
        },
    )
    custody_binding = {
        "schema_version": "megaplan-critique-custody-v1",
        "receipt": receipt_path.name,
        "receipt_sha256": critique_custody.sha256_file(receipt_path),
        "finding_count": receipt["finding_count"],
        "finding_ids": receipt["finding_ids"],
        "flag_ids": receipt["flag_ids"],
        "loss_count": 0,
        "admitted": True,
    }
    atomic_write_json(
        plan_dir / f"gate_signals_v{iteration}.json",
        {"signals": {"critique_custody": custody_binding}},
    )
    atomic_write_json(
        plan_dir / f"step_receipt_gate_v{iteration}.json",
        {
            "phase": "gate",
            "iteration": iteration,
            "upstream_artifact_hashes": [critique_sha],
        },
    )
    gate_payload = {
        "recommendation": "PROCEED",
        "signals": {"critique_custody": custody_binding},
    }
    atomic_write_json(plan_dir / f"gate_v{iteration}.json", gate_payload)
    atomic_write_json(plan_dir / "gate.json", gate_payload)
    clearance = {
        "schema_version": "megaplan-critique-clearance-v1",
        "source_receipts": [
            {"artifact": receipt_path.name, "sha256": critique_custody.sha256_file(receipt_path)}
        ],
        "admitted": True,
    }
    clearance["clearance_digest"] = critique_custody._digest(clearance)
    atomic_write_json(plan_dir / "critique_clearance.json", clearance)
    return receipt_path


def test_exact_legacy_unbound_fixture_migrates_without_rewriting_source(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path, iteration=2)
    receipt_path = _legacy_unbound_fixture(plan_dir, state)
    source_before = receipt_path.read_bytes()
    source_sha = critique_custody.sha256_file(receipt_path)

    [migration] = migrate_legacy_critique_custody(
        plan_dir,
        iteration=2,
        expected_source_sha256=source_sha,
        actor="operator:test",
        reason="admit preserved pre-v2 custody without inventing provenance",
    )

    assert receipt_path.read_bytes() == source_before
    assert migration["custody_status"] == "legacy_unbound"
    assert migration["producer_binding"]["producer_identity"] is None
    assert migration["producer_binding"]["invocation_identity"] is None
    critique_custody._validate_receipt_at_path(
        plan_dir, receipt_path, json.loads(receipt_path.read_text())
    )


def test_legacy_migration_survives_clearance_rewrite_and_finalize_validation(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path, iteration=2)
    receipt_path = _legacy_unbound_fixture(plan_dir, state)
    old_clearance_sha = critique_custody.sha256_file(
        plan_dir / "critique_clearance.json"
    )
    [migration] = migrate_legacy_critique_custody(
        plan_dir,
        iteration=2,
        expected_source_sha256=critique_custody.sha256_file(receipt_path),
        actor="operator:test",
        reason="admit legacy custody before normal clearance refresh",
    )
    receipt = critique_custody.read_json(receipt_path)
    [finding_id] = receipt["finding_ids"]
    update_flags_after_gate(
        plan_dir,
        [
            {
                "flag_id": finding_id,
                "action": "accept_tradeoff",
                "evidence": "The gate reviewed the exact preserved concern.",
                "rationale": "The remaining risk is explicit, bounded, and accepted.",
            }
        ],
    )

    clearance = write_critique_clearance(plan_dir, state)

    assert critique_custody.sha256_file(plan_dir / "critique_clearance.json") != old_clearance_sha
    stored_clearance_row = next(
        row
        for row in migration["lineage_evidence"]
        if row["role"] == "critique_clearance"
    )
    assert stored_clearance_row["sha256"] == old_clearance_sha
    graph = _admitted_graph()
    graph["critique_resolution_coverage"] = [
        {
            "finding_id": finding_id,
            "task_ids": ["T1"],
            "resolution_evidence": "T1 preserves the bounded accepted-risk contract.",
        }
    ]
    bind_finalize_custody(plan_dir, graph, clearance)

    assert_finalize_custody(plan_dir, graph)


def test_legacy_migration_accepts_bound_post_migration_state_history_append(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    receipt_path = _legacy_unbound_fixture(plan_dir, _state(tmp_path, iteration=2))
    source_before = receipt_path.read_bytes()
    [migration] = migrate_legacy_critique_custody(
        plan_dir,
        iteration=2,
        expected_source_sha256=critique_custody.sha256_file(receipt_path),
        actor="operator:test",
        reason="admit legacy custody before later workflow attempts",
    )
    stored_state_sha = next(
        row["sha256"]
        for row in migration["lineage_evidence"]
        if row["role"] == "state_history"
    )
    state = critique_custody.read_json(plan_dir / "state.json")
    state["history"].append(
        {
            "step": "finalize",
            "result": "failed",
            "invocation_id": "finalize-attempt-9",
            "wbc_attempt_id": "93b18c0b-423b-53e8-b063-523648c5c4aa",
        }
    )
    atomic_write_json(plan_dir / "state.json", state)

    assert critique_custody.sha256_file(plan_dir / "state.json") != stored_state_sha
    assert receipt_path.read_bytes() == source_before
    critique_custody._validate_receipt_at_path(
        plan_dir, receipt_path, critique_custody.read_json(receipt_path)
    )


def test_legacy_migration_rejects_mutated_bound_critique_history_row(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    receipt_path = _legacy_unbound_fixture(plan_dir, _state(tmp_path, iteration=2))
    migrate_legacy_critique_custody(
        plan_dir,
        iteration=2,
        expected_source_sha256=critique_custody.sha256_file(receipt_path),
        actor="operator:test",
        reason="admit legacy custody before later workflow attempts",
    )
    state = critique_custody.read_json(plan_dir / "state.json")
    state["history"][0]["artifact_hash"] = "sha256:" + "0" * 64
    atomic_write_json(plan_dir / "state.json", state)

    with pytest.raises(
        CritiqueCustodyError,
        match="state history lacks exactly one matching successful critique result",
    ):
        critique_custody._validate_receipt_at_path(
            plan_dir, receipt_path, critique_custody.read_json(receipt_path)
        )


def test_legacy_migration_rejects_post_admission_immutable_lineage_mutation(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    receipt_path = _legacy_unbound_fixture(plan_dir, _state(tmp_path, iteration=2))
    migrate_legacy_critique_custody(
        plan_dir,
        iteration=2,
        expected_source_sha256=critique_custody.sha256_file(receipt_path),
        actor="operator:test",
        reason="admit immutable legacy lineage",
    )
    critique_step_path = plan_dir / "step_receipt_critique_v2.json"
    critique_step = critique_custody.read_json(critique_step_path)
    critique_step["untrusted_extra_field"] = "mutation after admission"
    atomic_write_json(critique_step_path, critique_step)

    with pytest.raises(
        CritiqueCustodyError,
        match="legacy immutable lineage changed for critique_step_receipt",
    ):
        critique_custody._validate_receipt_at_path(
            plan_dir, receipt_path, critique_custody.read_json(receipt_path)
        )


def test_legacy_migration_rejects_post_admission_source_artifact_mutation(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    receipt_path = _legacy_unbound_fixture(plan_dir, _state(tmp_path, iteration=2))
    receipt = critique_custody.read_json(receipt_path)
    migrate_legacy_critique_custody(
        plan_dir,
        iteration=2,
        expected_source_sha256=critique_custody.sha256_file(receipt_path),
        actor="operator:test",
        reason="admit immutable legacy source artifacts",
    )
    raw_source_path = plan_dir / receipt["raw_sources"][0]["artifact"]
    atomic_write_text(raw_source_path, "mutated after migration\n")

    with pytest.raises(CritiqueCustodyError, match="raw source hash mismatch"):
        critique_custody._validate_receipt_at_path(
            plan_dir, receipt_path, critique_custody.read_json(receipt_path)
        )


def test_legacy_migration_is_idempotent_across_publish_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    receipt_path = _legacy_unbound_fixture(plan_dir, _state(tmp_path, iteration=2))
    source_sha = critique_custody.sha256_file(receipt_path)
    real_link = critique_custody.os.link
    failed = False

    def crash_once(source: object, target: object) -> None:
        nonlocal failed
        if not failed and str(target).endswith("critique_custody_legacy_migration_v2.json"):
            failed = True
            raise OSError("simulated crash before publish")
        real_link(source, target)

    monkeypatch.setattr(critique_custody.os, "link", crash_once)
    kwargs = {
        "iteration": 2,
        "expected_source_sha256": source_sha,
        "actor": "operator:test",
        "reason": "crash-safe migration",
    }
    with pytest.raises(OSError, match="simulated crash"):
        migrate_legacy_critique_custody(plan_dir, **kwargs)
    assert not (plan_dir / "critique_custody_legacy_migration_v2.json").exists()

    [first] = migrate_legacy_critique_custody(plan_dir, **kwargs)
    sidecar = plan_dir / "critique_custody_legacy_migration_v2.json"
    before = sidecar.read_bytes()
    [second] = migrate_legacy_critique_custody(plan_dir, **kwargs)
    assert second == first
    assert sidecar.read_bytes() == before


def test_legacy_migration_rejects_artifact_hash_divergence(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    receipt_path = _legacy_unbound_fixture(plan_dir, _state(tmp_path, iteration=2))
    receipt = json.loads(receipt_path.read_text())
    receipt["raw_sources"][0]["sha256"] = "sha256:" + "0" * 64
    _rewrite_receipt_digest(receipt)
    atomic_write_json(receipt_path, receipt)

    with pytest.raises(CritiqueCustodyError, match="raw source hash mismatch"):
        migrate_legacy_critique_custody(
            plan_dir,
            iteration=2,
            expected_source_sha256=critique_custody.sha256_file(receipt_path),
            actor="operator:test",
            reason="must reject divergent evidence",
        )


def test_legacy_migration_rejects_wrong_source_cas_and_gate_lineage(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    receipt_path = _legacy_unbound_fixture(plan_dir, _state(tmp_path, iteration=2))
    with pytest.raises(CritiqueCustodyError, match="expected sha256"):
        migrate_legacy_critique_custody(
            plan_dir,
            iteration=2,
            expected_source_sha256="sha256:" + "f" * 64,
            actor="operator:test",
            reason="CAS mismatch",
        )

    gate = json.loads((plan_dir / "gate_v2.json").read_text())
    gate["recommendation"] = "ITERATE"
    gate["signals"]["critique_custody"]["receipt_sha256"] = "sha256:" + "0" * 64
    atomic_write_json(plan_dir / "gate_v2.json", gate)
    with pytest.raises(CritiqueCustodyError, match="versioned gate does not bind"):
        migrate_legacy_critique_custody(
            plan_dir,
            iteration=2,
            expected_source_sha256=critique_custody.sha256_file(receipt_path),
            actor="operator:test",
            reason="lineage mismatch",
        )


def test_gate_rejects_self_consistent_receipt_copied_from_older_iteration(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    payload = _oversized_payload()
    _persist_critique(plan_dir, state, payload)
    old_receipt = (plan_dir / "critique_custody_v1.json").read_bytes()
    state["iteration"] = 2
    state["plan_versions"].append({"version": 2, "file": "plan_v2.md"})
    atomic_write_text(plan_dir / "plan_v2.md", "# Plan v2\n")
    atomic_write_json(plan_dir / "critique_v2.json", payload)
    (plan_dir / "critique_custody_v2.json").write_bytes(old_receipt)

    with pytest.raises(CritiqueCustodyError, match="does not match current iteration"):
        validate_gate_input_custody(plan_dir, state)


def test_gate_rejects_rehashed_receipt_pointing_at_wrong_critique_path(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    payload = _oversized_payload()
    _persist_critique(plan_dir, state, payload)
    receipt_path = plan_dir / "critique_custody_v1.json"
    receipt = json.loads(receipt_path.read_text())
    atomic_write_json(plan_dir / "copied_critique.json", payload)
    receipt["critique_artifact"] = "copied_critique.json"
    receipt["critique_sha256"] = critique_custody.sha256_file(
        plan_dir / "copied_critique.json"
    )
    _rewrite_receipt_digest(receipt)
    atomic_write_json(receipt_path, receipt)

    with pytest.raises(CritiqueCustodyError, match="exact current canonical artifact"):
        validate_gate_input_custody(plan_dir, state)


def test_gate_rejects_tampered_producer_attempt_even_with_rehashed_receipt(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    _persist_critique(plan_dir, state, _oversized_payload())
    receipt_path = plan_dir / "critique_custody_v1.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["producer_binding"]["attempt_index"] = 9
    receipt["producer_binding"]["attempt_id"] = (
        f"{receipt['producer_binding']['invocation_id']}:9"
    )
    _rewrite_receipt_digest(receipt)
    atomic_write_json(receipt_path, receipt)

    with pytest.raises(CritiqueCustodyError, match="producer binding digest mismatch"):
        validate_gate_input_custody(plan_dir, state)


def test_receipt_restart_is_idempotent_and_never_rewrites(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    payload = _oversized_payload()
    first = _persist_critique(plan_dir, state, payload)
    path = plan_dir / "critique_custody_v1.json"
    before = path.read_bytes()

    restarted = write_critique_production_receipt(
        plan_dir,
        state,
        payload,
        expected_check_ids=["scope"],
        producer_binding=_producer_binding(),
    )

    assert restarted == first
    assert path.read_bytes() == before


def test_receipt_restart_rejects_corrupted_existing_receipt(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    payload = _oversized_payload()
    _persist_critique(plan_dir, state, payload)
    path = plan_dir / "critique_custody_v1.json"
    existing = json.loads(path.read_text())
    existing["receipt_digest"] = "sha256:" + "0" * 64
    atomic_write_json(path, existing)

    with pytest.raises(CritiqueCustodyError, match="invalid digest"):
        write_critique_production_receipt(
            plan_dir,
            state,
            payload,
            expected_check_ids=["scope"],
            producer_binding=_producer_binding(),
        )


def test_concurrent_receipt_creation_is_create_once(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    payload = _oversized_payload()
    atomic_write_text(plan_dir / "plan_v1.md", "# Plan v1\n")
    atomic_write_text(plan_dir / "critique_raw_v1.txt", "raw producer critique")
    prepare_critique_payload(payload, expected_check_ids=["scope"])
    atomic_write_json(plan_dir / "critique_v1.json", payload)

    def publish(invocation: str) -> str:
        try:
            write_critique_production_receipt(
                plan_dir,
                state,
                deepcopy(payload),
                expected_check_ids=["scope"],
                producer_binding=_producer_binding(invocation),
            )
            return "published"
        except CritiqueCustodyError as error:
            assert error.code == "critique_custody_receipt_conflict"
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(publish, ("inv-a", "inv-b")))

    assert sorted(outcomes) == ["conflict", "published"]
    receipt = json.loads((plan_dir / "critique_custody_v1.json").read_text())
    assert receipt["producer_binding"]["invocation_id"] in {"inv-a", "inv-b"}


@pytest.mark.parametrize("producer", ["codex", "shannon"])
def test_inline_critique_producers_ignore_preexisting_valid_scratch(
    tmp_path: Path,
    producer: str,
) -> None:
    scratch_payload = _oversized_payload()
    atomic_write_json(tmp_path / "critique_output.json", scratch_payload)
    inline_payload = {"source": producer}
    worker = WorkerResult(payload=inline_payload, raw_output="", duration_ms=1, cost_usd=0)

    status, promoted = promote_scratch(
        tmp_path,
        "critique_output.json",
        frozenset(scratch_payload),
        worker,
        seed_json="{}",
        file_fill_instructed=False,
    )

    assert status == "unmodified"
    assert promoted is inline_payload


def test_hermes_critique_uses_only_registered_filled_path(tmp_path: Path) -> None:
    scratch_payload = _oversized_payload()
    atomic_write_json(tmp_path / "critique_output.json", scratch_payload)
    atomic_write_json(tmp_path / "wrong_output.json", {"wrong": True})
    worker = WorkerResult(payload={"source": "inline"}, raw_output="", duration_ms=1, cost_usd=0)

    status, promoted = promote_scratch(
        tmp_path,
        "critique_output.json",
        frozenset(scratch_payload),
        worker,
        seed_json="{}",
        file_fill_instructed=True,
    )

    assert status == "filled"
    assert promoted == scratch_payload


def test_hermes_stale_or_wrong_path_scratch_is_not_adopted(tmp_path: Path) -> None:
    seed = json.dumps(_oversized_payload(), sort_keys=True)
    (tmp_path / "critique_output.json").write_text(seed, encoding="utf-8")
    atomic_write_json(tmp_path / "wrong_output.json", _oversized_payload())
    inline_payload = {"source": "fallback"}
    worker = WorkerResult(payload=inline_payload, raw_output="", duration_ms=1, cost_usd=0)

    status, promoted = promote_scratch(
        tmp_path,
        "critique_output.json",
        frozenset(_oversized_payload()),
        worker,
        seed_json=seed,
        file_fill_instructed=True,
    )

    assert status == "unmodified"
    assert promoted is inline_payload


def test_orphan_recovery_quarantines_even_valid_stale_critique_scratch(
    tmp_path: Path,
) -> None:
    atomic_write_json(tmp_path / "critique_output.json", _oversized_payload())

    quarantined = auto._quarantine_phase_outputs(tmp_path, "critique")

    assert quarantined == ["critique_output.json"]
    assert not (tmp_path / "critique_output.json").exists()
    assert (tmp_path / "critique_output.json.orphaned").exists()


def test_runtime_producer_binding_captures_available_hermes_attempt_identity(
    tmp_path: Path,
) -> None:
    atomic_write_json(tmp_path / "critique_output.json", _oversized_payload())
    worker = WorkerResult(
        payload=_oversized_payload(),
        raw_output="",
        duration_ms=1,
        cost_usd=0,
        session_id="session-1",
        model_actual="glm-5.2",
        attempt_index=1,
        attempted_specs=("hermes:deepseek:model-a", "hermes:zhipu:glm-5.2"),
    )

    binding = critique_runtime._critique_producer_binding(
        {"meta": {"current_invocation_id": "inv-1"}},
        worker,
        agent="hermes",
        scratch_filename="critique_output.json",
        scratch_status="filled",
        plan_dir=tmp_path,
        parallel_reduced=False,
    )

    assert binding["attempt_id"] == "inv-1:1"
    assert binding["selected_spec"] == "hermes:zhipu:glm-5.2"
    assert binding["provider"] == "zhipu"
    assert binding["model_actual"] == "glm-5.2"
    assert binding["scratch_sha256"] == critique_custody.sha256_file(
        tmp_path / "critique_output.json"
    )


def test_parallel_reducer_receipt_binds_phase_children_and_rejects_manifest_tamper(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    state["active_step"] = {
        "phase": "critique",
        "run_id": "run-parallel",
    }
    phase = activate_phase_wbc(
        state=state,
        plan_dir=plan_dir,
        step="critique",
        agent="hermes",
    )
    assert phase is not None
    child = build_worker_dispatch_spec(
        plan_dir=plan_dir,
        state=state,
        step="critique",
        agent="hermes",
        selected_spec="hermes:zhipu:glm-5.2",
        route_kind="subprocess",
        dispatch_key="critique:scope:initial",
    )
    assert child is not None
    child.run(
        lambda _start: WorkerResult(
            payload={}, raw_output="", duration_ms=1, cost_usd=0, session_id=None
        )
    )
    payload = _oversized_payload()
    prepare_critique_payload(payload, expected_check_ids=["scope"])
    atomic_write_text(plan_dir / "plan_v1.md", "# Plan v1\n")
    atomic_write_text(plan_dir / "critique_raw_v1.txt", "parallel reducer")
    atomic_write_json(plan_dir / "critique_v1.json", payload)
    producer_path = plan_dir / "critique_check_scope_producer_v1.json"
    atomic_write_json(producer_path, payload)
    manifest = {
        "schema_version": "megaplan-parallel-critique-child-manifest-v1",
        "iteration": 1,
        "invocation_id": state["meta"]["current_invocation_id"],
        "phase_attempt_id": phase["attempt_id"],
        "expected_check_ids": ["scope"],
        "dispatches": query_worker_dispatch_manifest(
            plan_dir, phase_attempt_id=phase["attempt_id"]
        ),
        "producer_artifacts": [
            {
                "check_id": "scope",
                "producer_artifact": producer_path.name,
                "producer_sha256": critique_custody.sha256_file(producer_path),
            }
        ],
    }
    manifest["manifest_digest"] = critique_custody._digest(manifest)
    manifest_path = plan_dir / "critique_parallel_manifest_v1.json"
    atomic_write_json(manifest_path, manifest)
    worker = WorkerResult(
        payload=payload,
        raw_output="parallel",
        duration_ms=1,
        cost_usd=0,
        session_id=None,
        auth_metadata={
            "parallel_critique": {
                "manifest_artifact": manifest_path.name,
                "manifest_sha256": critique_custody.sha256_file(manifest_path),
                "manifest_digest": manifest["manifest_digest"],
                "phase_attempt_id": phase["attempt_id"],
                "invocation_id": state["meta"]["current_invocation_id"],
                "child_dispatch_count": 1,
            }
        },
    )
    binding = critique_runtime._critique_producer_binding(
        state,
        worker,
        agent="hermes",
        scratch_filename="critique_output.json",
        scratch_status="not_applicable",
        plan_dir=plan_dir,
        parallel_reduced=True,
    )
    state["meta"]["current_invocation_id"] = "stale-evaluator-invocation"
    with pytest.raises(CritiqueCustodyError, match="active critique phase"):
        critique_runtime._critique_producer_binding(
            state,
            worker,
            agent="hermes",
            scratch_filename="critique_output.json",
            scratch_status="not_applicable",
            plan_dir=plan_dir,
            parallel_reduced=True,
        )
    state["meta"]["current_invocation_id"] = phase["invocation_id"]
    write_critique_production_receipt(
        plan_dir,
        state,
        payload,
        expected_check_ids=["scope"],
        producer_binding=binding,
    )
    update_flags_after_critique(plan_dir, payload, iteration=1)

    manifest["expected_check_ids"] = ["scope", "injected"]
    manifest["manifest_digest"] = critique_custody._digest(
        {key: value for key, value in manifest.items() if key != "manifest_digest"}
    )
    atomic_write_json(manifest_path, manifest)
    with pytest.raises(CritiqueCustodyError, match="child manifest artifact hash mismatch"):
        validate_gate_input_custody(plan_dir, state)


def test_parallel_critique_establishes_phase_before_scatter() -> None:
    source = inspect.getsource(critique_runtime.handle_critique)
    parallel_dispatch = source.index("worker = run_parallel_critique(")
    assert source.rindex("set_active_step(", 0, parallel_dispatch) < parallel_dispatch
    assert source.rindex("activate_phase_wbc(", 0, parallel_dispatch) < parallel_dispatch
    assert source.rindex("save_state_merge_meta(", 0, parallel_dispatch) < parallel_dispatch


def test_unbound_critique_output_recovery_is_statically_retired() -> None:
    source = inspect.getsource(critique_runtime)
    functions = {
        node.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "_recover_valid_critique_output" not in functions
    assert "_normalize_critique_payload_for_recovery" not in functions


def test_registered_critique_seed_boundary_precedes_each_sequential_dispatch() -> None:
    source = inspect.getsource(critique_runtime.handle_critique)
    tree = ast.parse(source)
    seed_lines = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_seed_registered_critique_scratch"
    ]
    dispatch_lines = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_run_worker"
        and node.lineno > min(seed_lines)
    ]

    assert len(seed_lines) == len(dispatch_lines) == 2
    assert all(any(0 < dispatch - seed <= 3 for seed in seed_lines) for dispatch in dispatch_lines)


def test_effectively_clean_or_lost_gate_input_fails_closed(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    payload = _oversized_payload()
    _persist_critique(plan_dir, state, payload)

    erased = deepcopy(payload)
    erased["flags"] = []
    atomic_write_json(plan_dir / "critique_v1.json", erased)

    with pytest.raises(CritiqueCustodyError, match="hash mismatch"):
        validate_gate_input_custody(plan_dir, state)


def test_partial_mapping_remains_blocking_at_finalize(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    payload = _oversized_payload(two_findings=True)
    _persist_critique(plan_dir, state, payload)
    first_id, second_id = [flag["id"] for flag in payload["flags"]]

    atomic_write_text(plan_dir / "plan_v2.md", "# Plan v2\n\nStep 2 is split; Step 8 is not.\n")
    state["iteration"] = 2
    state["plan_versions"].append({"version": 2, "file": "plan_v2.md"})
    update_flags_after_revise(
        plan_dir,
        [{"id": first_id, "resolution": "addressed", "reason": "Split into T2a/T2b.", "where": "Step 2"}],
        plan_file="plan_v2.md",
        summary="Split Step 2.",
    )
    update_flags_after_gate(
        plan_dir,
        [{"flag_id": first_id, "action": "verify_fixed", "evidence": "plan_v2.md Step 2", "rationale": ""}],
    )

    with pytest.raises(CritiqueCustodyError, match=second_id):
        write_critique_clearance(plan_dir, state)


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda payload: payload["checks"][0]["findings"][0].update(flagged="yes"), "critique_findings_malformed"),
        (lambda payload: payload["flags"].append(deepcopy(payload["flags"][0])), "critique_finding_identity_invalid"),
        (
            lambda payload: payload["flags"].append(
                {**deepcopy(payload["flags"][0]), "id": "scope-god-task-2-duplicate"}
            ),
            "critique_finding_identity_invalid",
        ),
        (lambda payload: payload["checks"][0]["findings"][0].update(silent_drop=True), "critique_findings_malformed"),
    ],
)
def test_malformed_duplicated_unmapped_or_lossy_findings_fail_closed(
    mutation, code: str
) -> None:
    payload = _oversized_payload()
    mutation(payload)
    with pytest.raises(CritiqueCustodyError) as caught:
        prepare_critique_payload(payload, expected_check_ids=["scope"])
    assert caught.value.code == code


def test_reducer_reassigns_duplicate_worker_local_ids_deterministically() -> None:
    payload = {
        "checks": [
            {
                "id": "correctness",
                "question": "Is it correct?",
                "findings": [{"detail": "Correctness evidence.", "flagged": True}],
            },
            {
                "id": "scope",
                "question": "Is it bounded?",
                "findings": [{"detail": "Scope evidence.", "flagged": True}],
            },
        ],
        "flags": [
            {
                "id": "FLAG-001",
                "concern": "Correctness concern.",
                "category": "correctness",
                "severity_hint": "likely-significant",
                "evidence": "Correctness evidence.",
                "source_check_id": "correctness",
            },
            {
                "id": "FLAG-001",
                "concern": "Scope concern.",
                "category": "completeness",
                "severity_hint": "likely-significant",
                "evidence": "Scope evidence.",
                "source_check_id": "scope",
            },
        ],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    replay = deepcopy(payload)

    prepare_critique_payload(payload, expected_check_ids=["correctness", "scope"])
    prepare_critique_payload(replay, expected_check_ids=["correctness", "scope"])

    assert payload == replay
    assert len({flag["id"] for flag in payload["flags"]}) == 2
    assert all(flag["id"].startswith("CF-") for flag in payload["flags"])
    assert [flag["producer_flag_id"] for flag in payload["flags"]] == [
        "FLAG-001",
        "FLAG-001",
    ]


def test_reducer_preserves_ambiguous_canonical_reference_for_registry_validation() -> None:
    prior_id = "CF-E2E56F8ACC6B03976EA9"
    payload = {
        "checks": [
            {
                "id": "correctness",
                "question": "Is it correct?",
                "findings": [
                    {"detail": "Current correctness evidence.", "flagged": True}
                ],
            },
            {
                "id": "scope",
                "question": "Is it bounded?",
                "findings": [{"detail": "Current scope evidence.", "flagged": True}],
            },
        ],
        "flags": [
            {
                "id": prior_id,
                "concern": "Current correctness concern.",
                "category": "correctness",
                "severity_hint": "likely-significant",
                "evidence": "Current correctness evidence.",
                "source_check_id": "correctness",
            },
            {
                "id": prior_id,
                "concern": "Current scope concern.",
                "category": "completeness",
                "severity_hint": "likely-significant",
                "evidence": "Current scope evidence.",
                "source_check_id": "scope",
            },
        ],
        "verified_flag_ids": [prior_id],
        "disputed_flag_ids": [],
    }

    prepare_critique_payload(payload, expected_check_ids=["correctness", "scope"])

    assert payload["verified_flag_ids"] == [prior_id]
    assert {flag["producer_flag_id"] for flag in payload["flags"]} == {prior_id}
    assert prior_id not in {flag["id"] for flag in payload["flags"]}


def test_reducer_rejects_ambiguous_opaque_reference() -> None:
    payload = {
        "checks": [
            {
                "id": "correctness",
                "question": "Is it correct?",
                "findings": [
                    {"detail": "Current correctness evidence.", "flagged": True}
                ],
            },
            {
                "id": "scope",
                "question": "Is it bounded?",
                "findings": [{"detail": "Current scope evidence.", "flagged": True}],
            },
        ],
        "flags": [
            {
                "id": "FLAG-001",
                "concern": "Current correctness concern.",
                "category": "correctness",
                "severity_hint": "likely-significant",
                "evidence": "Current correctness evidence.",
                "source_check_id": "correctness",
            },
            {
                "id": "FLAG-001",
                "concern": "Current scope concern.",
                "category": "completeness",
                "severity_hint": "likely-significant",
                "evidence": "Current scope evidence.",
                "source_check_id": "scope",
            },
        ],
        "verified_flag_ids": ["FLAG-001"],
        "disputed_flag_ids": [],
    }

    with pytest.raises(
        CritiqueCustodyError, match="critique_finding_reference_ambiguous"
    ):
        prepare_critique_payload(payload, expected_check_ids=["correctness", "scope"])

def test_reducer_reassigns_unique_local_id_reused_for_different_findings() -> None:
    def payload(detail: str) -> dict[str, Any]:
        return {
            "checks": [
                {
                    "id": "verification",
                    "question": "Is the criterion verifiable?",
                    "findings": [{"detail": detail, "flagged": True}],
                }
            ],
            "flags": [
                {
                    "id": "verifiability-0",
                    "concern": detail,
                    "category": "verifiability",
                    "severity_hint": "likely-minor",
                    "evidence": detail,
                    "source_check_id": "verification",
                }
            ],
            "verified_flag_ids": ["verifiability-0"],
            "disputed_flag_ids": [],
        }

    first = payload("Criterion 11 requires human verification.")
    second = payload("Criterion 12 requires human verification.")

    prepare_critique_payload(first, expected_check_ids=["verification"])
    prepare_critique_payload(second, expected_check_ids=["verification"])

    first_id = first["flags"][0]["id"]
    second_id = second["flags"][0]["id"]
    assert first_id.startswith("CF-")
    assert second_id.startswith("CF-")
    assert first_id != second_id
    assert first["flags"][0]["producer_flag_id"] == "verifiability-0"
    assert second["flags"][0]["producer_flag_id"] == "verifiability-0"
    assert first["verified_flag_ids"] == [first_id]
    assert second["verified_flag_ids"] == [second_id]


def test_clearance_migrates_reused_legacy_nonblocking_producer_slot(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)

    def payload(detail: str) -> dict[str, Any]:
        return {
            "checks": [
                {
                    "id": "scope",
                    "question": "Is the criterion verifiable?",
                    "findings": [{"detail": detail, "flagged": True}],
                }
            ],
            "flags": [
                {
                    "id": "verifiability-0",
                    "concern": detail,
                    "category": "verifiability",
                    "severity_hint": "likely-minor",
                    "evidence": detail,
                    "source_check_id": "scope",
                }
            ],
            "verified_flag_ids": ["verifiability-0"],
            "disputed_flag_ids": [],
        }

    canonical_ids: list[str] = []
    for iteration, detail in enumerate(
        (
            "Criterion 11 requires human verification.",
            "Criterion 12 requires human verification.",
        ),
        start=1,
    ):
        state["iteration"] = iteration
        if iteration > 1:
            state["plan_versions"].append(
                {"version": iteration, "file": f"plan_v{iteration}.md"}
            )
        current = payload(detail)
        receipt = _persist_critique(plan_dir, state, current)
        canonical_id = str(receipt["findings"][0]["finding_id"])
        canonical_ids.append(canonical_id)

        critique_path = plan_dir / f"critique_v{iteration}.json"
        persisted = critique_custody.read_json(critique_path)
        persisted["flags"][0]["id"] = "verifiability-0"
        persisted["flags"][0].pop("producer_flag_id", None)
        persisted["verified_flag_ids"] = ["verifiability-0"]
        atomic_write_json(critique_path, persisted)

        receipt_path = plan_dir / f"critique_custody_v{iteration}.json"
        legacy_receipt = critique_custody.read_json(receipt_path)
        legacy_receipt["critique_sha256"] = critique_custody.sha256_file(critique_path)
        legacy_receipt["critique_payload_digest"] = critique_custody._digest(persisted)
        legacy_receipt["flag_ids"] = ["verifiability-0"]
        legacy_receipt["findings"][0]["flag_id"] = "verifiability-0"
        legacy_receipt.pop("receipt_digest", None)
        legacy_receipt["receipt_digest"] = critique_custody._digest(legacy_receipt)
        atomic_write_json(receipt_path, legacy_receipt)

    atomic_write_json(
        plan_dir / "faults.json",
        {
            "flags": [
                {
                    "id": "verifiability-0",
                    "concern": "Criterion 12 requires human verification.",
                    "category": "verifiability",
                    "severity_hint": "likely-minor",
                    "evidence": "Criterion 12 requires human verification.",
                    "raised_in": "critique_v2.json",
                    "status": "open",
                    "severity": "minor",
                    "verified": True,
                    "verified_in": "critique_v2.json",
                }
            ]
        },
    )

    clearance = write_critique_clearance(plan_dir, state)

    assert clearance["finding_ids"] == [canonical_ids[1]]
    assert clearance["resolutions"] == [
        {
            "finding_id": canonical_ids[1],
            "flag_id": "verifiability-0",
            "disposition": "tracked_nonblocking_observation",
            "evidence": "Criterion 12 requires human verification.",
            "verified_in": "critique_v2.json",
        }
    ]


def test_clearance_accepts_explicit_gate_tradeoff_for_significant_finding(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    payload = _oversized_payload()
    _persist_critique(plan_dir, state, payload)
    finding_id = payload["flags"][0]["id"]
    update_flags_after_gate(
        plan_dir,
        [
            {
                "flag_id": finding_id,
                "action": "accept_tradeoff",
                "evidence": "The bounded gate reviewed the exact remaining concern.",
                "rationale": "The risk is explicit, bounded, and accepted by the gate.",
            }
        ],
    )

    clearance = write_critique_clearance(plan_dir, state)

    assert clearance["resolutions"] == [
        {
            "finding_id": finding_id,
            "flag_id": finding_id,
            "disposition": "minor_tradeoff",
            "evidence": "The risk is explicit, bounded, and accepted by the gate.",
        }
    ]


def test_clearance_accepts_carried_tradeoff_with_traceable_plan_mutation() -> None:
    """A later gate may omit an old tradeoff envelope after revise fixed it."""
    flag = {
        "id": "CF-carried-tradeoff",
        "status": "accepted_tradeoff",
        "addressed_in": "plan_v2.md",
        "resolution": {
            "kind": "fixed",
            "claim": "The plan records the bounded bridge and its authority-neutrality guard.",
            "where": "Step 14 gate_status",
        },
    }
    finding = {
        "finding_id": "CF-carried-tradeoff",
        "flag_id": "CF-carried-tradeoff",
        "blocking": True,
    }

    resolution = critique_custody._resolution_for_finding(
        flag,
        finding,
        current_plan_name="plan_v2.md",
        current_plan_sha256="sha256:current-plan",
        source_plan_name="plan_v1.md",
        source_plan_sha256="sha256:source-plan",
        plan_version_order={"plan_v1.md": 1, "plan_v2.md": 2},
        gate_expected=True,
    )

    assert resolution == {
        "finding_id": "CF-carried-tradeoff",
        "flag_id": "CF-carried-tradeoff",
        "disposition": "verified_plan_mutation",
        "plan_artifact": "plan_v2.md",
        "plan_sha256": "sha256:current-plan",
        "evidence": "The plan records the bounded bridge and its authority-neutrality guard.",
    }


def test_clearance_rejects_reused_legacy_slot_with_blocking_occurrence(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    first = _oversized_payload()
    first_receipt = _persist_critique(plan_dir, state, first)
    first_receipt["findings"][0]["flag_id"] = "worker-slot-0"
    first_receipt["flag_ids"] = ["worker-slot-0"]
    first_receipt.pop("receipt_digest", None)
    first_receipt["receipt_digest"] = critique_custody._digest(first_receipt)
    atomic_write_json(plan_dir / "critique_custody_v1.json", first_receipt)
    first_payload = critique_custody.read_json(plan_dir / "critique_v1.json")
    first_payload["flags"][0]["id"] = "worker-slot-0"
    first_payload["flags"][0].pop("producer_flag_id", None)
    atomic_write_json(plan_dir / "critique_v1.json", first_payload)
    first_receipt["critique_sha256"] = critique_custody.sha256_file(
        plan_dir / "critique_v1.json"
    )
    first_receipt["critique_payload_digest"] = critique_custody._digest(first_payload)
    first_receipt.pop("receipt_digest", None)
    first_receipt["receipt_digest"] = critique_custody._digest(first_receipt)
    atomic_write_json(plan_dir / "critique_custody_v1.json", first_receipt)

    state["iteration"] = 2
    state["plan_versions"].append({"version": 2, "file": "plan_v2.md"})
    second = _oversized_payload()
    second["flags"][0]["concern"] = "A different blocking concern."
    second["flags"][0]["evidence"] = second["checks"][0]["findings"][0]["detail"]
    second_receipt = _persist_critique(plan_dir, state, second)
    second_receipt["findings"][0]["flag_id"] = "worker-slot-0"
    second_receipt["flag_ids"] = ["worker-slot-0"]
    second_payload = critique_custody.read_json(plan_dir / "critique_v2.json")
    second_payload["flags"][0]["id"] = "worker-slot-0"
    second_payload["flags"][0].pop("producer_flag_id", None)
    atomic_write_json(plan_dir / "critique_v2.json", second_payload)
    second_receipt["critique_sha256"] = critique_custody.sha256_file(
        plan_dir / "critique_v2.json"
    )
    second_receipt["critique_payload_digest"] = critique_custody._digest(second_payload)
    second_receipt.pop("receipt_digest", None)
    second_receipt["receipt_digest"] = critique_custody._digest(second_receipt)
    atomic_write_json(plan_dir / "critique_custody_v2.json", second_receipt)

    with pytest.raises(CritiqueCustodyError, match="blocking occurrence"):
        write_critique_clearance(plan_dir, state)

def test_clearance_binds_exact_final_graph_and_execute_rejects_missing_or_mutated_custody(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    payload = _oversized_payload()
    _persist_critique(plan_dir, state, payload)
    canonical_id = payload["flags"][0]["id"]
    atomic_write_text(plan_dir / "plan_v2.md", "# Plan v2\n\nSplit Step 2 into bounded tasks.\n")
    state["iteration"] = 2
    state["plan_versions"].append({"version": 2, "file": "plan_v2.md"})
    update_flags_after_revise(
        plan_dir,
        [
            {
                "id": canonical_id,
                "resolution": "addressed",
                "reason": "Split into bounded tasks.",
                "where": "Step 2",
            }
        ],
        plan_file="plan_v2.md",
        summary="Split the task.",
    )
    update_flags_after_gate(
        plan_dir,
        [{"flag_id": canonical_id, "action": "verify_fixed", "evidence": "plan_v2.md Step 2", "rationale": ""}],
    )
    clearance = write_critique_clearance(plan_dir, state)
    graph = _admitted_graph()
    graph["critique_resolution_coverage"] = [
        {
            "finding_id": clearance["finding_ids"][0],
            "task_ids": ["T1"],
            "resolution_evidence": "T1 implements the bounded split from plan_v2.md Step 2.",
        }
    ]

    with pytest.raises(CritiqueCustodyError) as missing:
        assert_finalize_custody(plan_dir, graph)
    assert missing.value.code == "finalize_critique_custody_missing"

    bind_finalize_custody(plan_dir, graph, clearance)
    assert_finalize_custody(plan_dir, graph)
    graph["tasks"][0]["objective"] = "Regenerate a different oversized objective after clearance."
    with pytest.raises(CritiqueCustodyError, match="graph hash differs"):
        assert_finalize_custody(plan_dir, graph)


def test_finalizer_partial_or_unknown_finding_mapping_fails_closed() -> None:
    graph = _admitted_graph()
    graph["critique_resolution_coverage"] = [
        {"finding_id": "CF-ONE", "task_ids": ["T1"], "resolution_evidence": "Mapped."}
    ]
    clearance = {"finding_ids": ["CF-ONE", "CF-TWO"]}
    with pytest.raises(CritiqueCustodyError) as partial:
        validate_finalize_resolution_coverage(graph, clearance)
    assert partial.value.code == "finalize_critique_coverage_invalid"

    graph["critique_resolution_coverage"].append(
        {"finding_id": "CF-TWO", "task_ids": ["T404"], "resolution_evidence": "Missing task."}
    )
    with pytest.raises(CritiqueCustodyError, match="unknown task_ids"):
        validate_finalize_resolution_coverage(graph, clearance)


def test_equivalent_35_task_linear_graph_is_deterministically_rejected() -> None:
    tasks: list[dict[str, Any]] = []
    for index in range(1, 36):
        task_id = f"T{index}"
        dependency = f"T{index - 1}" if index > 1 else None
        tasks.append(
            {
                "id": task_id,
                "objective": f"Implement bounded objective {index}.",
                "description": f"Implement slice {index}.",
                "kind": "code",
                "complexity": 4,
                "estimated_minutes": 5,
                "depends_on": [dependency] if dependency else [],
                "dependency_reasons": (
                    {
                        dependency: {
                            "kind": "consumes_output",
                            "reason": "Consumes prior contract.",
                            "required_output": dependency,
                        }
                    }
                    if dependency
                    else {}
                ),
                "routing_group": "",
                "write_set": {"paths": [f"src/task_{index}.py"], "complete": True},
                "narrow_tests": {"selectors": [], "max_seconds": 0, "max_runs": 0},
                "checkpoint": {"required": False, "max_interval_seconds": 300, "records": []},
            }
        )
    report = compile_task_feasibility(
        {"task_contract_version": 2, "validation_jobs": [], "tasks": tasks},
        {"phase_timeout_seconds": 3600},
    )
    assert report["admitted"] is False
    assert report["task_count"] == 35
    assert report["seriality"] == 1.0
    assert "serial_graph_unjustified" in {item["code"] for item in report["diagnostics"]}
