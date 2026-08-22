from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.m11_live_canary import CanarySafetyError, _digest
from arnold_pipelines.megaplan.cloud.m11_workflow_canary import (
    REQUIRED_SCENARIOS,
    admit_deployed_workflow_canary,
    verify_deployed_workflow_canary,
)
from arnold_pipelines.megaplan.cloud.m11_workflow_canary_runner import (
    run_deployed_workflow_canary,
)
from scripts.validate_native_representation_conformance import (
    validate_deployed_canary_proof_claim,
)


REVISION = "a" * 40


def _refresh_manifest_for(root: Path, changed: Path) -> None:
    evidence = root / "workflow-canary-evidence"
    manifest_path = root / "workflow-canary" / "frozen-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    relative = changed.relative_to(evidence).as_posix()
    record = next(item for item in manifest["files"] if item["path"] == relative)
    record["size"] = changed.stat().st_size
    record["sha256"] = "sha256:" + hashlib.sha256(changed.read_bytes()).hexdigest()
    manifest.pop("content_sha256", None)
    manifest["content_sha256"] = _digest(manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def _write_runtime(
    path: Path,
    *,
    deployment_target: str = "production",
    deployment_id: str = "deploy-1",
) -> dict:
    components = {
        name: {"ok": True}
        for name in (
            "interpreter",
            "editable_checkout",
            "pth_files",
            "imports",
            "source_lineage",
            "wrappers",
            "supervisor_command",
            "target_marker",
        )
    }
    components["interpreter"]["executable"] = sys.executable
    components["source_lineage"].update(
        {"revision": REVISION, "expected_revision": REVISION}
    )
    components["target_marker"]["fields"] = {
        "deployment_target": deployment_target,
        "deployment_id": deployment_id,
    }
    payload = {
        "schema": "arnold.megaplan.m11_bound_runtime_identity.v1",
        "valid": True,
        "strict": True,
        "expected_revision": REVISION,
        "components": components,
    }
    payload["content_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return payload


def _admit(tmp_path: Path) -> tuple[Path, dict, dict]:
    base = tmp_path / "m11-canaries"
    root = base / "m11-workflow-pending"
    root.mkdir(parents=True)
    runtime_path = root / "runtime.json"
    runtime = _write_runtime(runtime_path)
    admission = admit_deployed_workflow_canary(
        root=root,
        job_id="job-1",
        deployment_target="production",
        deployment_id="deploy-1",
        expected_revision=REVISION,
        runtime_receipt_path=runtime_path,
        base_root=base,
    )
    return root, runtime, admission


def test_admission_pins_exact_deployment_and_derives_runtime_identity(
    tmp_path: Path,
) -> None:
    root, runtime, admission = _admit(tmp_path)
    assert admission["deployment"] == {
        "target": "production",
        "id": "deploy-1",
        "expected_revision": REVISION,
    }
    assert admission["runtime_receipt"]["runtime_identity"] == (
        f"sha256:{runtime['content_sha256']}"
    )
    assert admission["required_scenarios"] == list(REQUIRED_SCENARIOS)
    assert (root / "workflow-canary" / "admission.json").is_file()


def test_admission_rejects_runtime_for_another_deployment(tmp_path: Path) -> None:
    base = tmp_path / "m11-canaries"
    root = base / "m11-workflow-wrong-target"
    root.mkdir(parents=True)
    runtime_path = root / "runtime.json"
    _write_runtime(runtime_path, deployment_id="other")
    with pytest.raises(CanarySafetyError, match="revision/deployment"):
        admit_deployed_workflow_canary(
            root=root,
            job_id="job-1",
            deployment_target="production",
            deployment_id="deploy-1",
            expected_revision=REVISION,
            runtime_receipt_path=runtime_path,
            base_root=base,
        )


def test_verifier_fails_closed_before_the_runner_freezes_evidence(
    tmp_path: Path,
) -> None:
    root, _, _ = _admit(tmp_path)
    with pytest.raises(CanarySafetyError):
        verify_deployed_workflow_canary(root=root, base_root=root.parent)
    assert not (root / "workflow-canary" / "verdict.json").exists()


def test_fully_shaped_self_hashed_forged_verdict_is_rejected(
    tmp_path: Path,
) -> None:
    root, _, admission = _admit(tmp_path)
    forged = {
        "schema": admission["schema"],
        "kind": "deployed_workflow_canary_semantic_verdict",
        "passed": True,
        "deployed_proof_status": "verified",
        "deployment": admission["deployment"],
        "admission_sha256": admission["content_sha256"],
        "scenarios": [
            {
                "scenario_id": scenario,
                "status": "verified",
                "semantic_proof": {"manufactured": True},
                "canonical_evidence": {"manufactured": True},
            }
            for scenario in REQUIRED_SCENARIOS
        ],
    }
    forged["content_sha256"] = _digest(forged)
    path = root / "workflow-canary" / "forged.json"
    path.write_text(json.dumps(forged), encoding="utf-8")
    row = {
        "id": "behavior-parity",
        "proof_categories": ["deployed_live_canary_receipt"],
        "proof_artifacts": [str(path.relative_to(tmp_path))],
        "deployed_proof_status": "verified",
    }
    assert validate_deployed_canary_proof_claim(row, repo_root=tmp_path) == [
        "row 'behavior-parity' claims deployed proof verified without a valid "
        "deployed workflow-canary verdict"
    ]


def test_caller_authored_pass_booleans_are_never_consumed(tmp_path: Path) -> None:
    root, _, _ = _admit(tmp_path)
    (root / "workflow-canary" / "job-receipt.json").write_text(
        json.dumps({"passed": True, "status": "verified"}),
        encoding="utf-8",
    )
    with pytest.raises(CanarySafetyError):
        verify_deployed_workflow_canary(root=root, base_root=root.parent)


def test_real_handler_runner_and_independent_verifier_round_trip(
    tmp_path: Path,
    isolate_nested_pytest_env: None,
) -> None:
    root, _, _ = _admit(tmp_path)
    project_dir = Path(__file__).resolve().parents[2]
    manifest = run_deployed_workflow_canary(
        root=root,
        project_dir=project_dir,
    )
    assert manifest["kind"] == "deployed_workflow_canary_frozen_manifest"
    verdict = verify_deployed_workflow_canary(root=root, base_root=root.parent)
    assert verdict["passed"] is True
    assert verdict["deployed_proof_status"] == "verified"
    assert {row["scenario_id"] for row in verdict["scenarios"]} == set(
        REQUIRED_SCENARIOS
    )
    assert verify_deployed_workflow_canary(
        root=root, base_root=root.parent
    ) == verdict
    gate_state = next(
        (root / "workflow-canary-evidence" / "three_gate_iterations").glob(
            ".megaplan/plans/*/state.json"
        )
    )
    state_payload = json.loads(gate_state.read_text(encoding="utf-8"))
    assert not state_payload.get("meta", {}).get("schema_parity_errors")
    row = {
        "id": "behavior-parity",
        "proof_categories": ["deployed_live_canary_receipt"],
        "proof_artifacts": [str((root / "workflow-canary" / "verdict.json").relative_to(tmp_path))],
        "deployed_proof_status": "verified",
    }
    assert validate_deployed_canary_proof_claim(row, repo_root=tmp_path) == []


def test_direct_store_fabrication_without_handler_provenance_is_rejected(
    tmp_path: Path,
) -> None:
    root, _, admission = _admit(tmp_path)
    evidence = root / "workflow-canary-evidence"
    evidence.mkdir()
    run = {
        "schema": "arnold.megaplan.m11_workflow_canary.run.v1",
        "kind": "deployed_workflow_canary_run",
        "producer_id": "megaplan.m11_workflow_canary.runner.v1",
        "adapter_id": "megaplan.m11_workflow_canary.deterministic_decision_adapter.v1",
        "admission_sha256": admission["content_sha256"],
        "job_id": admission["job_id"],
        "started_at": admission["admitted_at"],
        "completed_at": admission["admitted_at"],
        "scenarios": {
            scenario: {"plan_dir": f"{scenario}/fabricated"}
            for scenario in REQUIRED_SCENARIOS
        },
    }
    run["content_sha256"] = _digest(run)
    (evidence / "run.json").write_text(json.dumps(run), encoding="utf-8")
    manifest = {
        "schema": "arnold.megaplan.m11_workflow_canary.frozen_manifest.v1",
        "kind": "deployed_workflow_canary_frozen_manifest",
        "producer_id": "megaplan.m11_workflow_canary.runner.v1",
        "admission_sha256": admission["content_sha256"],
        "evidence_root": str(evidence),
        "frozen_at": admission["admitted_at"],
        "files": [
            {
                "path": "run.json",
                "size": (evidence / "run.json").stat().st_size,
                "sha256": "sha256:" + hashlib.sha256((evidence / "run.json").read_bytes()).hexdigest(),
            }
        ],
    }
    manifest["content_sha256"] = _digest(manifest)
    (root / "workflow-canary" / "frozen-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    with pytest.raises(CanarySafetyError, match="producer provenance|store"):
        verify_deployed_workflow_canary(root=root, base_root=root.parent)


def test_frozen_bundle_rejects_extra_stale_cross_stitched_and_misordered_evidence(
    tmp_path: Path,
    isolate_nested_pytest_env: None,
) -> None:
    root, _, _ = _admit(tmp_path)
    project_dir = Path(__file__).resolve().parents[2]
    run_deployed_workflow_canary(root=root, project_dir=project_dir)

    extra = root / "workflow-canary-evidence" / "after-freeze.json"
    extra.write_text("{}\n", encoding="utf-8")
    with pytest.raises(CanarySafetyError, match="inventory mismatch"):
        verify_deployed_workflow_canary(root=root, base_root=root.parent)
    extra.unlink()

    runtime = root / "runtime.json"
    runtime_bytes = runtime.read_bytes()
    runtime.write_bytes(runtime_bytes + b" ")
    with pytest.raises(CanarySafetyError, match="runtime receipt changed"):
        verify_deployed_workflow_canary(root=root, base_root=root.parent)
    runtime.write_bytes(runtime_bytes)

    run_path = root / "workflow-canary-evidence" / "run.json"
    run_bytes = run_path.read_bytes()
    manifest_path = root / "workflow-canary" / "frozen-manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    run = json.loads(run_bytes)
    run["scenarios"]["fresh_plan"]["plan_dir"] = run["scenarios"][
        "three_gate_iterations"
    ]["plan_dir"]
    run.pop("content_sha256", None)
    run["content_sha256"] = _digest(run)
    run_path.write_text(json.dumps(run), encoding="utf-8")
    _refresh_manifest_for(root, run_path)
    with pytest.raises(
        CanarySafetyError,
        match="scenario roots|fresh_plan|completion record",
    ):
        verify_deployed_workflow_canary(root=root, base_root=root.parent)
    run_path.write_bytes(run_bytes)
    manifest_path.write_bytes(manifest_bytes)

    run = json.loads(run_bytes)
    plan_dir = (
        root
        / "workflow-canary-evidence"
        / run["scenarios"]["fresh_plan"]["plan_dir"]
    )
    db_path = plan_dir / ".phase_wbc_attempts.sqlite3"
    db_bytes = db_path.read_bytes()
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        rowid, raw = connection.execute(
            "SELECT rowid, event_json FROM attempt_events ORDER BY sequence LIMIT 1"
        ).fetchone()
        event = json.loads(raw)
        event["sequence"] = 9
        connection.execute(
            "UPDATE attempt_events SET event_json = ? WHERE rowid = ?",
            (json.dumps(event, sort_keys=True), rowid),
        )
        connection.commit()
    finally:
        connection.close()
    for suffix in ("-wal", "-shm"):
        Path(str(db_path) + suffix).unlink(missing_ok=True)
    _refresh_manifest_for(root, db_path)
    with pytest.raises(CanarySafetyError, match="ordering"):
        verify_deployed_workflow_canary(root=root, base_root=root.parent)
    db_path.write_bytes(db_bytes)
    manifest_path.write_bytes(manifest_bytes)
