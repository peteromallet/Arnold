from __future__ import annotations

import copy
import hashlib
import json
import secrets
from pathlib import Path

import pytest

from scripts.validate_maintenance_runtime_consolidation_evidence import (
    canonical_sha256,
    validate_manifest,
)

SHA40 = "a" * 40
SHA256 = "b" * 64


def _write(path: Path, data: bytes = b"evidence") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _receipt(invocation_id: str, model: str, identity: str, *, role: str = "HARD") -> dict:
    return {
        "invocation_id": invocation_id,
        "task_id": invocation_id.split("-")[0],
        "role": role,
        "label": invocation_id,
        "model": model,
        "command": ["python", "worker"],
        "command_digest": SHA256,
        "brief_digest": SHA256,
        "allowance_digest": SHA256,
        "stdout_digest": SHA256,
        "stderr_digest": SHA256,
        "start_timestamp": "2026-08-20T00:00:00Z",
        "process_identity": identity,
        "status": "completed",
        "exit_status": 0,
    }


def _fixture(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / f"mrc-t0.3-test-{secrets.token_hex(6)}"
    manifest_path = root / "docs/arnold/maintenance-runtime-consolidation-evidence/manifest.json"
    artifact_path = root / "artifacts/proof.json"
    artifact_digest = _write(artifact_path, b"proof")
    schema_path = manifest_path.with_name("manifest.schema.v1.json")
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text("{}", encoding="utf-8")
    g0_path = root / "inputs/g0.json"
    g0_digest = _write(g0_path, b"g0")
    source_path = root / "inputs/source.json"
    source_digest = _write(source_path, b"source")
    allowances = []
    for task_id, production in (("H1", ["src/hard.py"]), ("X1", ["src/xhard.py"])):
        allowance = {
            "allowance_id": f"allowance-{task_id}",
            "task_id": task_id,
            "production_files": production,
            "tests": [f"tests/{task_id.lower()}.py"],
            "fixtures": [],
            "exports": [],
            "helpers": [],
            "generated_surfaces": [],
            "lifecycle_state": "active",
            "active": True,
        }
        allowance["allowance_digest"] = canonical_sha256({key: allowance[key] for key in ("production_files", "tests", "fixtures", "exports", "helpers", "generated_surfaces", "lifecycle_state", "active")})
        allowances.append(allowance)
    invocations = [
        _receipt("H1-impl", "openai-codex/gpt-5.6-luna", "pid-h1-impl"),
        _receipt("X1-pre", "grok-4.6", "pid-x1-pre", role="XHARD-REVIEW"),
        _receipt("X1-impl", "grok-4.6", "pid-x1-impl", role="XHARD"),
        _receipt("X1-post", "grok-4.6", "pid-x1-post", role="XHARD-REVIEW"),
        {**_receipt("F1-revision", "grok-4.6", "pid-revision", role="XHARD-REVISION"), "commit": SHA40},
        {**_receipt("F1-rereview", "grok-4.6", "pid-rereview", role="XHARD-REVIEW"), "verdict": "accepted"},
        _receipt("J1-grok", "grok-4.6", "pid-judgment", role="judgment"),
        _receipt("G1-review", "openai-codex/gpt-5.6-luna", "pid-g1-review", role="HARD-REVIEW"),
        _receipt("G2-review", "grok-4.6", "pid-g2-review", role="XHARD-REVIEW"),
    ]
    manifest = {
        "schema": "maintenance-runtime-consolidation-evidence",
        "schema_version": "maintenance-runtime-consolidation-evidence.v1",
        "manifest_version": "v1",
        "integration": {
            "integration_base_sha": SHA40,
            "integration_current_sha": SHA40,
            "branch": "integration/test",
            "worktree": str(root),
            "g0_selection_manifest": {"path": str(g0_path.relative_to(root)), "sha256": g0_digest},
        },
        "source_inputs": [{"path": str(source_path.relative_to(root)), "sha256": source_digest, "provenance": "read_only"}],
        "selected_behaviors": [
            {"behavior_id": "hard-behavior", "source_commit": SHA40, "source_hunk": "h-hard", "task_ids": ["H1"]},
            {"behavior_id": "xhard-behavior", "source_commit": SHA40, "source_hunk": "h-xhard", "task_ids": ["X1"]},
        ],
        "tasks": [
            {"task_id": "H1", "label": "ordinary hard", "difficulty": "HARD", "selected_source_commits": [SHA40], "selected_source_hunks": ["h-hard"], "selected_behavior_ids": ["hard-behavior"], "input_sha": SHA40, "output_sha": SHA40, "commit": SHA40, "complete_allowance_id": "allowance-H1", "implementer": {"invocation_id": "H1-impl", "model": "openai-codex/gpt-5.6-luna", "process_identity": "pid-h1-impl"}, "focused_test_receipts": [], "gate_id": "G1"},
            {"task_id": "X1", "label": "xhard lifecycle", "difficulty": "XHARD", "selected_source_commits": [SHA40], "selected_source_hunks": ["h-xhard"], "selected_behavior_ids": ["xhard-behavior"], "input_sha": SHA40, "output_sha": SHA40, "commit": SHA40, "complete_allowance_id": "allowance-X1", "implementer": {"invocation_id": "X1-impl", "model": "grok-4.6", "process_identity": "pid-x1-impl"}, "focused_test_receipts": [], "gate_id": "G2"},
        ],
        "gates": [
            {"gate_id": "G1", "label": "ordinary review", "task_ids": ["H1"], "reviewer": {"invocation_id": "G1-review", "role": "HARD-REVIEW", "model": "openai-codex/gpt-5.6-luna", "process_identity": "pid-g1-review"}, "verdict": "accepted", "evidence": []},
            {"gate_id": "G2", "label": "xhard post review", "task_ids": ["X1"], "reviewer": {"invocation_id": "G2-review", "role": "XHARD-REVIEW", "model": "grok-4.6", "process_identity": "pid-g2-review"}, "verdict": "accepted", "evidence": []},
        ],
        "review_invocations": [
            {"task_id": "X1", "phase": "pre_review", "invocation_id": "X1-pre", "role": "XHARD-REVIEW", "model": "grok-4.6", "process_identity": "pid-x1-pre", "disposition": "approved"},
            {"task_id": "X1", "phase": "implementation", "invocation_id": "X1-impl", "role": "XHARD", "model": "grok-4.6", "process_identity": "pid-x1-impl", "disposition": "implemented"},
            {"task_id": "X1", "phase": "post_review", "invocation_id": "X1-post", "role": "XHARD-REVIEW", "model": "grok-4.6", "process_identity": "pid-x1-post", "disposition": "accepted"},
        ],
        "findings": [{"finding_id": "F1", "severity": "must", "proposed_revision_class": "[XHARD-REVISION]", "adjudicated_revision_class": "[XHARD-REVISION]", "classification_disposition": "accepted", "revision_invocation_id": "F1-revision", "revision_commit": SHA40, "counterexample_evidence": [{"path": str(artifact_path.relative_to(root)), "sha256": artifact_digest}], "re_review_invocation_id": "F1-rereview", "re_review_verdict": "accepted", "superseded_artifact_digests": [SHA256]}],
        "material_judgments": [{"judgment_id": "J1", "label": "boundary", "model": "grok-4.6", "question": "Which boundary is authoritative?", "evidence_inputs": [], "decisive_recommendation": "A", "rejected_alternatives": ["B"], "affected_contracts": ["T0.3"], "downstream_route": ["T0.3"], "invocation_id": "J1-grok"}],
        "allowances": allowances,
        "shards": [{"shard_id": "shard-1", "command": "pytest focused", "source_sha": SHA40, "interpreter": "python", "runtime_digest": SHA256, "spec_digest": SHA256, "venv_digest": SHA256, "disposable_root": str(root / "disposable"), "status": "passed", "artifact_path": str(artifact_path.relative_to(root)), "artifact_digest": artifact_digest}],
        "candidate_install_receipts": [{"receipt_id": "install-1", "path": str(artifact_path.relative_to(root)), "sha256": artifact_digest}],
        "live_state_snapshots": [{"receipt_id": "before-1", "path": str(artifact_path.relative_to(root)), "sha256": artifact_digest}, {"receipt_id": "after-1", "path": str(artifact_path.relative_to(root)), "sha256": artifact_digest}],
        "canary_rollback_receipts": [{"receipt_id": "rollback-1", "path": str(artifact_path.relative_to(root)), "sha256": artifact_digest}],
        "broad_suite_receipts": [{"receipt_id": "broad-1", "path": str(artifact_path.relative_to(root)), "sha256": artifact_digest, "authoritative": True}],
        "invocation_receipts": invocations,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    schema_path.write_text("{}", encoding="utf-8")
    return manifest_path, manifest


def codes(path: Path) -> set[str]:
    return {issue.code for issue in validate_manifest(path)}


def test_empty_scaffold_reports_stable_missing_records(tmp_path: Path):
    path, _ = _fixture(tmp_path)
    path.write_text(json.dumps({"schema": "maintenance-runtime-consolidation-evidence", "schema_version": "maintenance-runtime-consolidation-evidence.v1"}), encoding="utf-8")
    found = codes(path)
    assert found == {"MISSING_RECORD"}


def test_complete_synthetic_evidence_passes(tmp_path: Path):
    path, _ = _fixture(tmp_path)
    assert validate_manifest(path) == []


@pytest.mark.parametrize(("collection", "code"), [("tasks", "DUPLICATE_ID"), ("gates", "DUPLICATE_ID"), ("shards", "DUPLICATE_ID"), ("findings", "DUPLICATE_ID"), ("material_judgments", "DUPLICATE_ID")])
def test_duplicate_ids_fail(tmp_path: Path, collection: str, code: str):
    path, manifest = _fixture(tmp_path)
    item = copy.deepcopy(manifest[collection][0])
    manifest[collection].append(item)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert code in codes(path)


def test_reused_invocation_id_fails(tmp_path: Path):
    path, manifest = _fixture(tmp_path)
    manifest["invocation_receipts"].append(copy.deepcopy(manifest["invocation_receipts"][0]))
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert "DUPLICATE_INVOCATION_ID" in codes(path)


def test_wrong_model_routing_fails(tmp_path: Path):
    path, manifest = _fixture(tmp_path)
    manifest["tasks"][0]["implementer"]["model"] = "grok-4.6"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert "WRONG_MODEL_ROUTE" in codes(path)


def test_incomplete_revision_chain_fails(tmp_path: Path):
    path, manifest = _fixture(tmp_path)
    manifest["findings"][0]["re_review_invocation_id"] = "missing"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert "INCOMPLETE_REVISION_CHAIN" in codes(path)


def test_missing_grok_receipt_fails(tmp_path: Path):
    path, manifest = _fixture(tmp_path)
    manifest["material_judgments"][0]["invocation_id"] = "missing"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert "MISSING_GROK_RECEIPT" in codes(path)


def test_overlapping_allowances_fail(tmp_path: Path):
    path, manifest = _fixture(tmp_path)
    duplicate = copy.deepcopy(manifest["allowances"][1])
    duplicate["allowance_id"] = "allowance-overlap"
    duplicate["production_files"] = ["src"]
    duplicate["allowance_digest"] = canonical_sha256({key: duplicate[key] for key in ("production_files", "tests", "fixtures", "exports", "helpers", "generated_surfaces", "lifecycle_state", "active")})
    manifest["allowances"].append(duplicate)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert "OVERLAPPING_ALLOWANCE" in codes(path)


def test_missing_file_and_digest_mismatch_fail(tmp_path: Path):
    path, manifest = _fixture(tmp_path)
    manifest["shards"][0]["artifact_path"] = "missing.json"
    manifest["shards"][0]["artifact_digest"] = SHA256
    path.write_text(json.dumps(manifest), encoding="utf-8")
    found = codes(path)
    assert "MISSING_FILE" in found
    manifest["shards"][0]["artifact_path"] = "artifacts/proof.json"
    manifest["shards"][0]["artifact_digest"] = SHA256
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert "DIGEST_MISMATCH" in codes(path)


def test_unmapped_selected_behavior_fails(tmp_path: Path):
    path, manifest = _fixture(tmp_path)
    manifest["selected_behaviors"][0]["task_ids"] = ["H1", "X1"]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert "UNMAPPED_SELECTED_BEHAVIOR" in codes(path)


def test_second_broad_suite_fails(tmp_path: Path):
    path, manifest = _fixture(tmp_path)
    manifest["broad_suite_receipts"].append(copy.deepcopy(manifest["broad_suite_receipts"][0]))
    manifest["broad_suite_receipts"][1]["receipt_id"] = "broad-2"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert "SECOND_BROAD_SUITE" in codes(path)


def test_reviewer_implementer_identity_equality_fails(tmp_path: Path):
    path, manifest = _fixture(tmp_path)
    manifest["gates"][0]["reviewer"]["process_identity"] = "pid-h1-impl"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert "SELF_REVIEW" in codes(path)


def test_ox_alpha_route_valid_for_every_role(tmp_path: Path):
    path, manifest = _fixture(tmp_path)
    ox = "openrouter/stealth/ox-alpha"
    for task in manifest["tasks"]:
        task["implementer"]["model"] = ox
    for gate in manifest["gates"]:
        gate["reviewer"]["model"] = ox
    for review in manifest["review_invocations"]:
        review["model"] = ox
    for judgment in manifest["material_judgments"]:
        judgment["model"] = ox
    for receipt in manifest["invocation_receipts"]:
        receipt["model"] = ox
        receipt["resolved_model"] = ox
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_manifest(path) == []


def test_non_terminal_gate_verdict_does_not_decide_or_double_count(tmp_path: Path):
    path, manifest = _fixture(tmp_path)
    pending = copy.deepcopy(manifest["gates"][1])
    pending["gate_id"] = "G2-pending"
    pending["verdict"] = "PENDING"
    manifest["gates"].append(pending)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_manifest(path) == []


def test_xhard_without_deciding_review_fails(tmp_path: Path):
    path, manifest = _fixture(tmp_path)
    manifest["gates"][1]["verdict"] = "PENDING"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert "WRONG_HARD_REVIEW_ORDER" in codes(path)


def test_xhard_with_second_deciding_review_fails(tmp_path: Path):
    path, manifest = _fixture(tmp_path)
    manifest["invocation_receipts"].append(_receipt("X1-re-review", "grok-4.6", "pid-x1-rereview", role="XHARD-REVIEW"))
    manifest["gates"].append({"gate_id": "G2b", "label": "duplicate xhard review", "task_ids": ["X1"], "reviewer": {"invocation_id": "X1-re-review", "role": "XHARD-REVIEW", "model": "grok-4.6", "process_identity": "pid-x1-rereview"}, "verdict": "PASS", "evidence": []})
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert "WRONG_HARD_REVIEW_ORDER" in codes(path)


def test_xhard_hollow_rejected_dispatch_before_deciding_review_passes(tmp_path: Path):
    path, manifest = _fixture(tmp_path)
    hollow = {**_receipt("X1-hollow", "grok-4.6", "pid-x1-hollow", role="XHARD-REVIEW"), "bootstrap_exception": True, "status": "rejected_incomplete_dispatch"}
    manifest["invocation_receipts"].append(hollow)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_manifest(path) == []


def test_xhard_without_implementation_receipt_fails(tmp_path: Path):
    path, manifest = _fixture(tmp_path)
    manifest["tasks"][1].pop("implementer")
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert "MISSING_REFERENCE" in codes(path)


def test_ordinary_task_cannot_claim_xhard_lifecycle_phases(tmp_path: Path):
    path, manifest = _fixture(tmp_path)
    manifest["review_invocations"].append({"task_id": "H1", "phase": "pre_review", "invocation_id": "H1-pre", "role": "HARD-REVIEW", "model": "openai-codex/gpt-5.6-luna", "process_identity": "pid-h1-pre", "disposition": "approved"})
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert "WRONG_HARD_REVIEW_ORDER" in codes(path)
