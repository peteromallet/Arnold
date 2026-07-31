from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.m11_live_canary import CanarySafetyError, _digest
from arnold_pipelines.megaplan.cloud.m11_workflow_canary import (
    REQUIRED_SCENARIOS,
    UNSUPPORTED_REASON,
    admit_deployed_workflow_canary,
    verify_deployed_workflow_canary,
)
from scripts.validate_native_representation_conformance import (
    validate_deployed_canary_proof_claim,
)


REVISION = "a" * 40


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


def test_current_verifier_is_immutably_pending_not_a_fake_pass(
    tmp_path: Path,
) -> None:
    root, _, _ = _admit(tmp_path)
    verdict = verify_deployed_workflow_canary(root=root, base_root=root.parent)
    assert verdict["passed"] is False
    assert verdict["deployed_proof_status"] == "pending"
    assert verdict["unsupported_reason"] == UNSUPPORTED_REASON
    assert {row["status"] for row in verdict["scenarios"]} == {"pending"}
    with pytest.raises(CanarySafetyError, match="append-only artifact"):
        verify_deployed_workflow_canary(root=root, base_root=root.parent)


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
    verdict = verify_deployed_workflow_canary(root=root, base_root=root.parent)
    assert verdict["passed"] is False
