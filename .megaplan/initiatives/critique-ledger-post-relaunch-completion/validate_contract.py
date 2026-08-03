#!/usr/bin/env python3
"""Deterministically validate the Critique Ledger follow-up handoff contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

from arnold_pipelines.megaplan.chain.spec import load_spec


INITIATIVE = Path(__file__).resolve().parent
ROOT = INITIATIVE.parents[2]
SHA256 = re.compile(r"^[0-9a-f]{64}$")

OBLIGATIONS = {
    "F1.platform_capacity_storage_hardening": "f1-owner-storage-recovery-hardening",
    "F1.physically_minimal_image": "f1-owner-storage-recovery-hardening",
    "F1.cross_pipeline_model_isolation": "f1-owner-storage-recovery-hardening",
    "F1.t1_5_monotonic_consumed_grant": "f1-owner-storage-recovery-hardening",
    "F1.production_recovery_owner": "f1-owner-storage-recovery-hardening",
    "F1.exact_occurrence_handoff": "f1-owner-storage-recovery-hardening",
    "F1.notification_occurrence_version_custody": "f1-owner-storage-recovery-hardening",
    "F1.t1_5_topology_retirement": "f1-owner-storage-recovery-hardening",
    "F1.t1_7_transactional_storage": "f1-owner-storage-recovery-hardening",
    "F1.t1_10_notification_policy": "f1-owner-storage-recovery-hardening",
    "F2.t1_1_universal_admission": "f2-admission-model-effect-release-closure",
    "F2.t1_2_attempt_model_handling": "f2-admission-model-effect-release-closure",
    "F2.provider_attested_model_identity": "f2-admission-model-effect-release-closure",
    "F2.t1_3_transport_integration": "f2-admission-model-effect-release-closure",
    "F2.t1_4_t1_6_release_closure": "f2-admission-model-effect-release-closure",
}

PRELAUNCH_GATES = {
    "accepted_finite_canary_candidate",
    "trusted_host_control_state",
    "bounded_fence_reclaim",
    "durable_failure_reconciliation",
    "built_image_four_phase_smoke",
    "live_capacity_and_predeploy",
    "finite_canary_and_stable_exit",
    "remote_custody_and_fresh_clone",
}

STABLE_EXIT_PROOFS = [
    ".megaplan/initiatives/critique-ledger-safe-v3-canary/built-image-smoke-receipt.json",
    ".megaplan/initiatives/critique-ledger-safe-v3-canary/prelaunch-receipts-manifest.json",
    ".megaplan/initiatives/critique-ledger-safe-v3-canary/conformance-receipt.json",
    ".megaplan/initiatives/critique-ledger-safe-v3-canary/completion-receipt.json",
    ".megaplan/initiatives/critique-ledger-safe-v3-canary/stable-exit-receipt.json",
    ".megaplan/initiatives/critique-ledger-safe-v3-canary/fresh-clone-reconstruction-receipt.json",
]

KNOWN_ATTEMPTS = [
    ("B8-build", "IMAGE_BUILD", "c0e5e745d796d01deb962129f834978127f3adc0", "0dc3d1e8c5d58ae5d09aa676148efadeb2f78ce8", None),
    ("B9-build", "IMAGE_BUILD", "cd120d8c585c078418583ba5142c966ac5554a12", "025d719eb1318a2ff1f52673b79ef0014be7a1b2", None),
    ("B10-build", "IMAGE_BUILD", "04178bf31748aa746a36e7e736c0ee38d441b666", "7c67c7c63dc8d065a2f63663cba73e4566ed4c0e", None),
    ("B10-smoke", "OFFLINE_STRUCTURAL_SMOKE", "04178bf31748aa746a36e7e736c0ee38d441b666", "7c67c7c63dc8d065a2f63663cba73e4566ed4c0e", "/var/lib/arnold-zero-recovery/critique-ledger-b10-offline-smoke.json"),
    ("B11-smoke", "OFFLINE_STRUCTURAL_SMOKE", "d610d1420a9851f2d3c0be27cf1cada5413b4f0f", "1e9153d8ceda3834dc1f7b658322c7afbe16e05b", "/var/lib/arnold-zero-recovery/critique-ledger-b11-offline-smoke.json"),
    ("B12-smoke", "OFFLINE_STRUCTURAL_SMOKE", "cc5cd5b3c435d1694a574eb23c8ec3ead52d70a2", "5494ba3a87b3f1522ac3639f5f00c1f08402f696", "/var/lib/arnold-zero-recovery/critique-ledger-b12-offline-smoke.json"),
    ("B13-smoke", "OFFLINE_STRUCTURAL_SMOKE", "63f8c0ae02e951361bab81949bec661f101a2f7e", "49afa570cb237185f91ef88782165d74a8c5f95c", "/var/lib/arnold-zero-recovery/critique-ledger-b13-offline-smoke.json"),
    ("B14-smoke", "OFFLINE_STRUCTURAL_SMOKE", "38a7608ff435d08ce7a16d0e632f08a5c29a1f2e", "17f5cbcf0cc281f7d5969848b64425b58ce16682", "/var/lib/arnold-zero-recovery/critique-ledger-b14-offline-smoke.json"),
    ("B15-smoke", "OFFLINE_STRUCTURAL_SMOKE", "4fbe51cdd7b04053bafccc5dba5d3fac0dd436aa", "f7869b70e2bdce0b06c37b6726b113280e85e78d", "/var/lib/arnold-zero-recovery/critique-ledger-b15-offline-smoke.json"),
    ("B16-smoke", "OFFLINE_STRUCTURAL_SMOKE", "05c874c875a9e81d2015c1bcce8746cbba540299", "6f332c32e17f3e9e1c99d3acdc168adb5c691d24", "/var/lib/arnold-zero-recovery/critique-ledger-b16-offline-smoke.json"),
    ("B17-smoke", "OFFLINE_STRUCTURAL_SMOKE", "dbb98ff2596063b4632b3e9d392b882a5808b7ec", "5115448b5da9ae95899f21f911d154ab9d1a97d0", "/var/lib/arnold-zero-recovery/critique-ledger-b17-offline-smoke.json"),
    ("B18-smoke", "OFFLINE_STRUCTURAL_SMOKE", "e1d26430b54d3121fa545a677eb6a5189fbb248e", "75bd6a645cfb49d267e4d985f88881beeda94b7b", "/var/lib/arnold-zero-recovery/critique-ledger-b18-offline-smoke.json"),
    ("B19-smoke", "OFFLINE_STRUCTURAL_SMOKE", "301abcae4187931eac4f97efdd4fac0120b068d9", "f743e9ecddccdaf95b0546960018630771f9468f", "/var/lib/arnold-zero-recovery/critique-ledger-b19-offline-smoke.json"),
    ("B20-smoke", "OFFLINE_STRUCTURAL_SMOKE", "be3ca786094013c3a0350b6860bbb042b63b1cc2", "602e5311d76d1163069834da9186e5380168c005", "/var/lib/arnold-zero-recovery/critique-ledger-b20-offline-smoke.json"),
    ("B21-smoke", "OFFLINE_STRUCTURAL_SMOKE", "29ee2bfd63b6f466c10e60baaaaffee45aa8bd81", "d78c2e2facea5ff0b14bb503c4cb0b7d9901caea", "/var/lib/arnold-zero-recovery/critique-ledger-b21-offline-smoke.json"),
    ("B22-smoke", "OFFLINE_STRUCTURAL_SMOKE", "4e2fca8a294eb18526aa88576c0818487730d26c", "a38dbd6a84e1205286f9e65c04996b23116071f2", "/var/lib/arnold-zero-recovery/critique-ledger-b22-offline-smoke.json"),
    ("B23-smoke", "OFFLINE_STRUCTURAL_SMOKE", "7c9256b210cefb998dec57929e41b5a799faf314", "55161ca5def9fb1688ca911d80afd94ba2df7eb4", "/var/lib/arnold-zero-recovery/critique-ledger-b23-offline-smoke.json"),
    ("B24-smoke", "OFFLINE_STRUCTURAL_SMOKE", "a172a7a7556984f76d86625f3d0953d089f45004", "461672f91b169fa961b9839ab51a6647bdd6f0f9", "/var/lib/arnold-zero-recovery/critique-ledger-b24-offline-smoke.json"),
    ("B25-smoke", "OFFLINE_STRUCTURAL_SMOKE", "117efa9e35307981b16379f9bc8204e5a5ec0695", "13995f708ab68240dfd08fa41430735cb66985b0", "/var/lib/arnold-zero-recovery/critique-ledger-b25-offline-smoke.json"),
]

B26_PASS = {
    "id": "B26-smoke",
    "commit": "9a8edcf11a488b5dfb47e5c4ef7defb17e3ba6d2",
    "tree": "1de51fd479e0bcffc8fb9f951cb27982ad9ee036",
    "path": "/var/lib/arnold-zero-recovery/critique-ledger-b26-offline-smoke.json",
    "sha256": "cf0967638b2c84097ced4dfc113735bbd66db1a8925d00d7080bdf7242669487",
    "receipt_digest": "7a656459d4aace827e8b180eb025117b609262311641c15ce495ba87042cf64f",
    "production_image": "sha256:261642f73da83b4704b33b02b9b1c14f17c56d4cafb633c98cac4f938d6421ed",
    "derived_image": "sha256:74d24afc0af67ff6ae5de7d40ece647067873168793936f6d5d58e1a4a8742a7",
    "verifier_receipt_digest": "99c4420ac9440d539753e0a261781f6fc8588f974fa7e2ed07ee86cb2106e373",
}

B27_PASS = {
    "id": "B27-smoke",
    "commit": "0a3fbb56e48c5de98a455224c444a522ff31bf07",
    "tree": "beb5d68bfcbdd7b0867a139ec19885dbb260e57d",
    "path": "/var/lib/arnold-zero-recovery/critique-ledger-b27-offline-smoke.json",
    "sha256": "77c39d4763641724aa3355210c3ccdcbb6deb8a8253b560d416a9f47d3f1e454",
    "receipt_digest": "173288c2fcd0aa793f894a3a995de1512447b4e9bbf6744fc241d2227d505b9b",
    "production_image": "sha256:c5687c73d88307ab9d7847585aaa371d27fab1e1286283b6456dbbf0d269470d",
    "derived_image": "sha256:71ef320bd30fe70211e9885c6972994a5f61c9625cc24bba9aecc2874082fb6e",
    "verifier_receipt_digest": "bae9f5e69d7d2eaf3106ac5652c77be2608fc7c643d708d5c24af74bf2b08184",
}

A27_REPAIR = {
    "id": "A27",
    "commit": "185e8d97732ff25e5e5d6a00b6877b7a46f08129",
    "tree": "a7c204b757fe0673516d1e9e22a1308b73b0d778",
}

A28_REPAIR = {
    "id": "A28",
    "commit": "4845a10a043f7d53ea235789d2603ad3869d212a",
    "tree": "5b2b48a45617f5ddae20075240f061239c884ffb",
}

B28_PASS = {
    "id": "B28-smoke",
    "commit": "d7194ec75dd27c9dc549af603effbdc4f11371ab",
    "tree": "0872e11712cb796cf0be2d65e7f4846bb54211d7",
    "path": "/var/lib/arnold-zero-recovery/critique-ledger-b28-offline-smoke.json",
    "sha256": "2fa22ddcaeb92bb005cf24dfd8392b2e1e72206f7290c964b52a63549ef253d0",
    "receipt_digest": "3ec46ea9f0992d606da5f34c84d76a58c7c8650f51c79d9538d1682d78bf6d40",
    "production_image": "sha256:c1dcccbd0381bb8d578c14b9a0edfcbb24eddf9d70c537f1063a9e065feba878",
    "derived_image": "sha256:5677ed0b6a888be55ce4aaf1cedbfc57d3037f1e55b6ca1e8e19067029f99476",
    "verifier_receipt_digest": "fa98493c808093164446284204a7ba433f18a2934137a2d98c5ecac462381d40",
}

FAILED_LIVE_TRANSACTION_ID = "404dd858567d48ffbe8cb7c27d85185a"

OPERATION_IDS = [
    "critique-ledger-zero-byte-bootstrap-20260803-034217z",
    "critique-ledger-capacity-reserve-remediation-20260803-0349z",
    "critique-ledger-capacity-reserve-fallback-20260803-0350z",
    "critique-ledger-failed-build-capacity-reset-20260803-0400z",
    "critique-ledger-failed-build-capacity-reset-corrected-20260803-0404z",
]

OPERATION_SUPERSESSION = {
    "critique-ledger-capacity-reserve-fallback-20260803-0350z": "critique-ledger-capacity-reserve-remediation-20260803-0349z",
    "critique-ledger-failed-build-capacity-reset-corrected-20260803-0404z": "critique-ledger-failed-build-capacity-reset-20260803-0400z",
}


class ContractError(RuntimeError):
    pass


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs_no_duplicates)
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_path(value: str) -> Path:
    path = (ROOT / value).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ContractError(f"evidence path escapes repository: {value}") from exc
    return path


def _validate_obligations(custody: dict[str, Any]) -> None:
    rows = custody.get("deferred_obligations")
    if not isinstance(rows, list) or len(rows) != 15:
        raise ContractError("deferred_obligations must contain exactly 15 rows")
    expected_fields = {
        "id", "phase", "status", "operational_disposition", "owner_milestone",
        "acceptance_gate", "evidence_ref", "required_claim_id",
    }
    ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != expected_fields:
            raise ContractError("deferred obligation has an inexact schema")
        obligation_id = row.get("id")
        ids.append(obligation_id)
        owner = OBLIGATIONS.get(obligation_id)
        if (
            owner is None
            or row.get("phase") != obligation_id.split(".", 1)[0]
            or row.get("status") != "DEFERRED_POST_CANARY"
            or row.get("operational_disposition") != "NOT_CONSUMED_OPERATIONAL_CANARY"
            or row.get("owner_milestone") != owner
            or row.get("acceptance_gate") != "INDEPENDENT_COMPLETION_MANIFEST_REQUIRED"
            or row.get("evidence_ref") != f"proof-map.json#/{owner}"
            or row.get("required_claim_id") != obligation_id
        ):
            raise ContractError(f"invalid deferred obligation: {obligation_id!r}")
    if ids != list(OBLIGATIONS) or len(ids) != len(set(ids)):
        raise ContractError("deferred obligation order/set/uniqueness drift")


def _validate_prelaunch_gates(custody: dict[str, Any], *, require_live: bool) -> None:
    gates = custody.get("prelaunch_release_gates")
    if not isinstance(gates, list) or len(gates) != len(PRELAUNCH_GATES):
        raise ContractError("prelaunch_release_gates has an inexact count")
    expected_fields = {
        "id", "blocking_phase", "owner", "status", "acceptance_gate", "evidence",
    }
    ids: list[str] = []
    for gate in gates:
        if not isinstance(gate, dict) or set(gate) != expected_fields:
            raise ContractError("prelaunch gate has an inexact schema")
        gate_id = gate.get("id")
        ids.append(gate_id)
        evidence = gate.get("evidence")
        if (
            gate_id not in PRELAUNCH_GATES
            or gate.get("blocking_phase") != "T6.2_PRELAUNCH"
            or gate.get("status") not in {"PENDING", "ACCEPTED"}
            or gate.get("acceptance_gate") != "INDEPENDENT_EXACT_EVIDENCE_REQUIRED"
            or not isinstance(gate.get("owner"), str)
            or not gate.get("owner")
            or not isinstance(evidence, dict)
            or set(evidence) != {"path", "sha256", "status"}
        ):
            raise ContractError(f"invalid prelaunch gate: {gate_id!r}")
        if gate.get("status") == "PENDING":
            if evidence != {"path": None, "sha256": None, "status": "PENDING"}:
                raise ContractError(f"pending gate fabricated evidence: {gate_id}")
        elif (
            evidence.get("status") != "ACCEPTED"
            or not isinstance(evidence.get("path"), str)
            or not SHA256.fullmatch(str(evidence.get("sha256")))
        ):
            raise ContractError(f"accepted gate lacks exact evidence: {gate_id}")
        else:
            evidence_path = _repo_path(evidence["path"])
            if not evidence_path.is_file() or _sha256(evidence_path) != evidence["sha256"]:
                raise ContractError(f"accepted gate evidence hash mismatch: {gate_id}")
        if require_live and gate.get("status") != "ACCEPTED":
            raise ContractError(f"live gate is not accepted: {gate_id}")
    if set(ids) != PRELAUNCH_GATES or len(ids) != len(set(ids)):
        raise ContractError("prelaunch gate set/uniqueness drift")


def _validate_attempt_history(custody: dict[str, Any], *, require_live: bool = False) -> None:
    attempts = custody.get("prelaunch_attempts")
    if not isinstance(attempts, list) or len(attempts) != len(KNOWN_ATTEMPTS) + 3:
        raise ContractError("prelaunch attempt history is incomplete")
    expected_fields = {"id", "kind", "candidate", "status", "failure", "remote_receipt"}
    ids: list[str] = []
    for index, attempt in enumerate(attempts):
        if index == len(KNOWN_ATTEMPTS):
            if not isinstance(attempt, dict):
                raise ContractError("B26 passing smoke has an invalid schema")
            ids.append(attempt.get("id"))
            if (
                set(attempt) != {
                    "id", "kind", "candidate", "status", "result", "remote_receipt",
                    "receipt_digest", "image", "verifier_receipt_digest", "phases",
                    "privilege_receipt_count", "independent_review",
                }
                or attempt.get("id") != B26_PASS["id"]
                or attempt.get("kind") != "OFFLINE_STRUCTURAL_SMOKE"
                or attempt.get("candidate") != {"commit": B26_PASS["commit"], "tree": B26_PASS["tree"]}
                or attempt.get("status") != "PASSED_EXIT_0_INDEPENDENT_SOL_GO_NOT_LIVE_GATE"
                or attempt.get("result") != {"exit_code": 0, "phase_status": "ALL_EXACT_PHASES_PASSED", "terminal_state": "finalized"}
                or attempt.get("remote_receipt") != {
                    "path": B26_PASS["path"],
                    "sha256": B26_PASS["sha256"],
                    "status": "REMOTE_SHA_DECLARED_COPY_REQUIRED",
                }
                or attempt.get("receipt_digest") != B26_PASS["receipt_digest"]
                or attempt.get("image") != {
                    "production": B26_PASS["production_image"],
                    "derived": B26_PASS["derived_image"],
                }
                or attempt.get("verifier_receipt_digest") != B26_PASS["verifier_receipt_digest"]
                or attempt.get("phases") != ["init", "plan", "critique", "gate", "finalize"]
                or attempt.get("privilege_receipt_count") != 4
                or attempt.get("independent_review") != {
                    "reviewer": "Sol",
                    "decision": "GO",
                    "artifact": {"path": None, "sha256": None, "status": "NO_LOCAL_ARTIFACT_PRESENT"},
                }
            ):
                raise ContractError("B26 passing smoke binding drift")
            continue
        if index == len(KNOWN_ATTEMPTS) + 1:
            if not isinstance(attempt, dict):
                raise ContractError("B27 passing smoke has an invalid schema")
            ids.append(attempt.get("id"))
            review = attempt.get("independent_review")
            pending_review = review == {"path": None, "sha256": None, "status": "PENDING_SOL_ACCEPTANCE"}
            accepted_review = (
                isinstance(review, dict)
                and set(review) == {"path", "sha256", "status", "reviewer", "decision"}
                and review.get("reviewer") == "Sol"
                and review.get("decision") == "GO"
                and review.get("status") == "ACCEPTED"
                and isinstance(review.get("path"), str)
                and SHA256.fullmatch(str(review.get("sha256"))) is not None
            )
            if accepted_review:
                review_path = _repo_path(review["path"])
                accepted_review = review_path.is_file() and _sha256(review_path) == review["sha256"]
            expected_status = (
                "PASSED_EXIT_0_PENDING_INDEPENDENT_SOL_ACCEPTANCE_NOT_LIVE_GATE"
                if pending_review
                else "PASSED_EXIT_0_INDEPENDENT_SOL_GO_NOT_LIVE_GATE"
            )
            if (
                set(attempt) != {
                    "id", "kind", "candidate", "status", "result", "remote_receipt",
                    "receipt_digest", "image", "verifier_receipt_digest", "phases",
                    "privilege_receipt_count", "independent_review", "repair_lineage",
                }
                or attempt.get("id") != B27_PASS["id"]
                or attempt.get("kind") != "OFFLINE_STRUCTURAL_SMOKE"
                or attempt.get("candidate") != {"commit": B27_PASS["commit"], "tree": B27_PASS["tree"]}
                or attempt.get("status") != expected_status
                or attempt.get("result") != {"exit_code": 0, "phase_status": "ALL_EXACT_PHASES_PASSED", "terminal_state": "finalized"}
                or attempt.get("remote_receipt") != {
                    "path": B27_PASS["path"],
                    "sha256": B27_PASS["sha256"],
                    "status": "REMOTE_SHA_DECLARED_COPY_AND_INDEPENDENT_REVIEW_REQUIRED",
                }
                or attempt.get("receipt_digest") != B27_PASS["receipt_digest"]
                or attempt.get("image") != {
                    "production": B27_PASS["production_image"],
                    "derived": B27_PASS["derived_image"],
                }
                or attempt.get("verifier_receipt_digest") != B27_PASS["verifier_receipt_digest"]
                or attempt.get("phases") != ["init", "plan", "critique", "gate", "finalize"]
                or attempt.get("privilege_receipt_count") != 4
                or attempt.get("repair_lineage") != {
                    "repair": A27_REPAIR,
                    "launch": {"id": "B27", "commit": B27_PASS["commit"], "tree": B27_PASS["tree"]},
                    "tests": {"passed": 169, "skipped": 1},
                    "change": "NARROW_ABSENT_TMUX_SOCKET_CLASSIFIER_PLUS_FAIL_CLOSED_UNKNOWN_REGRESSION",
                }
                or not (pending_review or accepted_review)
            ):
                raise ContractError("B27 passing smoke binding drift")
            continue
        if index == len(KNOWN_ATTEMPTS) + 2:
            if not isinstance(attempt, dict):
                raise ContractError("B28 passing smoke has an invalid schema")
            ids.append(attempt.get("id"))
            review = attempt.get("independent_review")
            pending_review = review == {"path": None, "sha256": None, "status": "PENDING_SOL_ACCEPTANCE"}
            accepted_review = (
                isinstance(review, dict)
                and set(review) == {"path", "sha256", "status", "reviewer", "decision"}
                and review.get("reviewer") == "Sol"
                and review.get("decision") == "GO"
                and review.get("status") == "ACCEPTED"
                and isinstance(review.get("path"), str)
                and SHA256.fullmatch(str(review.get("sha256"))) is not None
            )
            if accepted_review:
                review_path = _repo_path(review["path"])
                accepted_review = review_path.is_file() and _sha256(review_path) == review["sha256"]
            expected_status = (
                "PASSED_EXIT_0_PENDING_INDEPENDENT_SOL_ACCEPTANCE_NOT_LIVE_GATE"
                if pending_review
                else "PASSED_EXIT_0_INDEPENDENT_SOL_GO_NOT_LIVE_GATE"
            )
            if (
                set(attempt) != {
                    "id", "kind", "candidate", "status", "result", "remote_receipt",
                    "receipt_digest", "image", "verifier_receipt_digest", "phases",
                    "privilege_receipt_count", "independent_review", "repair_lineage",
                    "retry_isolation",
                }
                or attempt.get("id") != B28_PASS["id"]
                or attempt.get("kind") != "OFFLINE_STRUCTURAL_SMOKE"
                or attempt.get("candidate") != {"commit": B28_PASS["commit"], "tree": B28_PASS["tree"]}
                or attempt.get("status") != expected_status
                or attempt.get("result") != {"exit_code": 0, "phase_status": "ALL_EXACT_PHASES_PASSED", "terminal_state": "finalized"}
                or attempt.get("remote_receipt") != {
                    "path": B28_PASS["path"],
                    "sha256": B28_PASS["sha256"],
                    "status": "REMOTE_SHA_DECLARED_COPY_AND_INDEPENDENT_REVIEW_REQUIRED",
                }
                or attempt.get("receipt_digest") != B28_PASS["receipt_digest"]
                or attempt.get("image") != {
                    "production": B28_PASS["production_image"],
                    "derived": B28_PASS["derived_image"],
                }
                or attempt.get("verifier_receipt_digest") != B28_PASS["verifier_receipt_digest"]
                or attempt.get("phases") != ["init", "plan", "critique", "gate", "finalize"]
                or attempt.get("privilege_receipt_count") != 4
                or attempt.get("repair_lineage") != {
                    "repair": A28_REPAIR,
                    "launch": {"id": "B28", "commit": B28_PASS["commit"], "tree": B28_PASS["tree"]},
                    "tests": {"passed": 171, "skipped": 1},
                    "change": "ADMIT_ONLY_INERT_AF_UNIX_SOCKETS_THEN_COUNT_AND_SEAL_STILL_REJECT_OTHER_SPECIAL_LINKED_OBJECTS",
                }
                or attempt.get("retry_isolation") != {
                    "workspace": "/opt/megaplan-cloud/workspace/critique-ledger-safe-v3-canary-attempt-2-20260803",
                    "container": "megaplan-cloud-agent-finite-canary-2",
                    "preserves_attempt": "B27-live-attempt-1",
                }
                or not (pending_review or accepted_review)
            ):
                raise ContractError("B28 passing smoke binding drift")
            if require_live and not accepted_review:
                raise ContractError("B28 passing smoke lacks independent Sol acceptance")
            continue
        if not isinstance(attempt, dict) or set(attempt) != expected_fields:
            raise ContractError("prelaunch attempt has an inexact schema")
        attempt_id = attempt.get("id")
        ids.append(attempt_id)
        candidate = attempt.get("candidate")
        receipt = attempt.get("remote_receipt")
        if (
            not isinstance(attempt_id, str)
            or not isinstance(candidate, dict)
            or set(candidate) != {"commit", "tree"}
            or not all(re.fullmatch(r"[0-9a-f]{40}", str(candidate.get(key))) for key in ("commit", "tree"))
            or not isinstance(attempt.get("failure"), str)
            or not attempt.get("failure")
            or not isinstance(receipt, dict)
            or set(receipt) != {"path", "sha256", "status"}
        ):
            raise ContractError(f"invalid prelaunch attempt: {attempt_id!r}")
        if index < len(KNOWN_ATTEMPTS):
            expected_id, kind, commit, tree, remote_path = KNOWN_ATTEMPTS[index]
            expected_status = (
                "FAILED_ATTEMPT_THEN_LATER_REBUILD_SUCCEEDED_NOT_SMOKE_ACCEPTED"
                if expected_id == "B10-build"
                else "FAILED_NOT_ACCEPTED"
            )
            if (
                attempt_id != expected_id
                or attempt.get("kind") != kind
                or candidate != {"commit": commit, "tree": tree}
                or receipt.get("path") != remote_path
                or attempt.get("status") != expected_status
            ):
                raise ContractError(f"known attempt history drift: {expected_id}")
        if receipt.get("sha256") is None:
            if receipt.get("status") not in {"REMOTE_COPY_REQUIRED", "REMOTE_PATH_NOT_RECORDED_IN_LOCAL_AUTHORITY"}:
                raise ContractError(f"pending receipt has invalid disposition: {attempt_id}")
        elif not SHA256.fullmatch(str(receipt.get("sha256"))):
            raise ContractError(f"attempt receipt has invalid hash: {attempt_id}")
    if len(ids) != len(set(ids)):
        raise ContractError("prelaunch attempt IDs are not unique")


def _validate_live_deploy_attempts(custody: dict[str, Any]) -> None:
    attempts = custody.get("live_deploy_attempts")
    if not isinstance(attempts, list) or len(attempts) != 1:
        raise ContractError("live deploy attempt history is incomplete")
    attempt = attempts[0]
    expected = {
        "transaction_id": FAILED_LIVE_TRANSACTION_ID,
        "status": "FAILED_FAIL_CLOSED_NO_CANARY_CREATED",
        "durable_failure_receipt": {
            "path": f"/var/lib/arnold-zero-recovery/{FAILED_LIVE_TRANSACTION_ID}.host-zero-recovery-fence-apply-failure.json",
            "sha256": None,
            "status": "REMOTE_COPY_AND_RECONCILIATION_REQUIRED",
        },
        "marker_published": False,
        "stage": "verify_no_recovery_sessions",
        "error": "tmux_observation_unknown",
        "recovery_units": {"count": 8, "state": "ALL_INACTIVE_MASKED_PERSISTENT"},
        "canary_created": False,
        "observed_tmux": {
            "returncode": 1,
            "stderr": "error connecting to /tmp/tmux-0/default (No such file or directory)",
        },
        "root_cause": "NARROW_CLASSIFIER_TREATED_ABSENT_TMUX_SOCKET_AS_UNKNOWN",
        "repair": A27_REPAIR,
        "retry_status": "B27_LIVE_ATTEMPT_TERMINAL_RECONCILED",
    }
    if attempt != expected:
        raise ContractError("failed live deploy transaction binding drift")


def _validate_live_canary_attempts(custody: dict[str, Any]) -> None:
    attempts = custody.get("live_canary_attempts")
    if not isinstance(attempts, list) or len(attempts) != 1:
        raise ContractError("live canary attempt history is incomplete")
    attempt = attempts[0]
    expected = {
        "id": "B27-live-attempt-1",
        "candidate": {"commit": B27_PASS["commit"], "tree": B27_PASS["tree"]},
        "status": "failed",
        "terminal_state": "failed",
        "run_receipt": {
            "path": None,
            "sha256": "710707648e66e37b2c57684faa135eb324f36b163796d45210763657ad6d4e17",
            "digest": "ac95bf39a39c946b73a56a08625d8d15e57f8673764365c0d4ad3354826085bd",
            "status": "PATH_NOT_PROVIDED_IMPORT_REQUIRED",
        },
        "dispatch_integrity": {
            "status": "partial",
            "start_dispatches": [
                {"phase": "plan", "count": 1, "provider": "Codex", "model": "gpt-5.6-sol", "reasoning": "high"}
            ],
            "terminal_dispatch_count": 0,
            "terminal_dispatch_absence_reason": "finite_model_boundary_failed",
        },
        "root_evidence": {
            "source": "plan_v1_raw",
            "observed_excerpt": (
                "finite model boundary failed: CliError:finite-model runtime contains a special or linked object | "
                "CliError:source object is not trusted-owner non-writable: "
                ".../.zero-recovery-plan-worker-output.json | "
                "CliError:plan artifact permissions are unsafe..."
            ),
            "actual_output": {"empty": True, "uid": 65532, "gid": 65532, "mode": "0600"},
            "primary_cause": "REAL_CODEX_CREATED_AF_UNIX_IPC_SOCKET_UNDER_ISOLATED_CODEX_HOME_OFFLINE_FAKE_DID_NOT_MODEL_IT",
            "boundary_effect": "RUNTIME_VALIDATOR_REJECTED_SOCKET_BEFORE_OUTPUT_RECLAIM",
            "cascading_errors": ["OUTPUT_OWNER_NONWRITABLE_REJECTION", "PLAN_ARTIFACT_PERMISSION_REJECTION"],
        },
        "container": {
            "id_prefix": "c6289bc3",
            "full_id": None,
            "stopped": True,
            "exit_code": 137,
            "oom_killed": False,
            "reconciled_stop": True,
        },
        "workspace": {
            "path": "/opt/megaplan-cloud/workspace/critique-ledger-safe-v3-canary-20260802",
            "owner": "root",
            "mode": "0700",
            "sealed": True,
            "preserved": True,
        },
        "background_effects": {"loop_started": False, "notifications_sent": False},
        "reconciliation": "TERMINAL_RECONCILED_REMOTE_RECEIPT_IMPORT_PENDING",
        "repair": A28_REPAIR,
    }
    if attempt != expected:
        raise ContractError("B27 live canary terminal binding drift")


def _validate_operation_reconciliation(*, require_live: bool) -> None:
    manifest_path = INITIATIVE / "evidence/operation-reconciliation-manifest.json"
    manifest = _load_json(manifest_path)
    if set(manifest) != {"schema", "status", "authority_rule", "independent_review", "operations"}:
        raise ContractError("operation reconciliation manifest has an inexact schema")
    if (
        manifest.get("schema") != "arnold.critique_ledger.operation_reconciliation_manifest.v1"
        or manifest.get("authority_rule") != "INTENTS_ARE_IMMUTABLE; EFFECTIVE_STATUS_IS_APPEND_ONLY; AMBIGUITY_IS_TERMINAL_NO_REDISPATCH"
    ):
        raise ContractError("operation reconciliation authority drift")
    review = manifest.get("independent_review")
    if not isinstance(review, dict) or set(review) != {"path", "sha256", "status"}:
        raise ContractError("operation reconciliation review schema drift")
    if review.get("status") == "PENDING":
        if review != {"path": None, "sha256": None, "status": "PENDING"}:
            raise ContractError("pending operation review fabricates evidence")
    elif (
        review.get("status") != "ACCEPTED"
        or not isinstance(review.get("path"), str)
        or not SHA256.fullmatch(str(review.get("sha256")))
    ):
        raise ContractError("operation reconciliation review is invalid")
    else:
        review_path = _repo_path(review["path"])
        if not review_path.is_file() or _sha256(review_path) != review["sha256"]:
            raise ContractError("operation reconciliation review hash mismatch")
    operations = manifest.get("operations")
    if not isinstance(operations, list) or len(operations) != len(OPERATION_IDS):
        raise ContractError("operation reconciliation has an inexact operation count")
    seen: list[str] = []
    edges: dict[str, str] = {}
    for row in operations:
        if not isinstance(row, dict) or set(row) != {
            "operation_id", "intent", "supersedes", "maximum_dispatches_by_effect",
            "terminal", "effective_status",
        }:
            raise ContractError("operation reconciliation row has an inexact schema")
        operation_id = row.get("operation_id")
        seen.append(operation_id)
        intent = row.get("intent")
        terminal = row.get("terminal")
        maxima = row.get("maximum_dispatches_by_effect")
        if (
            not isinstance(intent, dict)
            or set(intent) != {"path", "sha256", "authority_commit"}
            or not SHA256.fullmatch(str(intent.get("sha256")))
            or not re.fullmatch(r"[0-9a-f]{40}", str(intent.get("authority_commit")))
            or not isinstance(maxima, list)
            or not maxima
            or any(value != 1 for value in maxima)
            or not isinstance(terminal, dict)
            or set(terminal) != {"path", "sha256", "status", "dispatch_counts"}
        ):
            raise ContractError(f"invalid operation reconciliation row: {operation_id!r}")
        intent_path = _repo_path(str(intent.get("path")))
        intent_payload = _load_json(intent_path)
        effects = intent_payload.get("admitted_effects_in_order")
        if effects is None:
            effects = [intent_payload.get("admitted_effect")]
        expected_supersedes = intent_payload.get("supersedes_failed_operation")
        if (
            intent_payload.get("operation_id") != operation_id
            or intent_payload.get("status") != "AUTHORIZED_PENDING_SINGLE_DISPATCH"
            or _sha256(intent_path) != intent.get("sha256")
            or not isinstance(effects, list)
            or len(effects) != len(maxima)
            or any(not isinstance(effect, dict) or effect.get("maximum_dispatches") != 1 for effect in effects)
            or row.get("supersedes") != expected_supersedes
        ):
            raise ContractError(f"operation intent binding drift: {operation_id}")
        if expected_supersedes is not None:
            edges[operation_id] = expected_supersedes
        if row.get("effective_status") == "PENDING_RECONCILIATION":
            if terminal != {"path": None, "sha256": None, "status": "PENDING_RECONCILIATION", "dispatch_counts": None}:
                raise ContractError(f"pending operation fabricates terminal evidence: {operation_id}")
        else:
            counts = terminal.get("dispatch_counts")
            if (
                row.get("effective_status") not in {"COMPLETED", "FAILED_NO_EFFECT", "AMBIGUOUS_CONSUMED_NO_REDISPATCH"}
                or terminal.get("status") != row.get("effective_status")
                or not isinstance(counts, list)
                or len(counts) != len(maxima)
                or any(not isinstance(count, int) or count < 0 or count > limit for count, limit in zip(counts, maxima))
                or not isinstance(terminal.get("path"), str)
                or not SHA256.fullmatch(str(terminal.get("sha256")))
            ):
                raise ContractError(f"invalid terminal operation outcome: {operation_id}")
            terminal_path = _repo_path(terminal["path"])
            if not terminal_path.is_file() or _sha256(terminal_path) != terminal["sha256"]:
                raise ContractError(f"terminal operation receipt hash mismatch: {operation_id}")
    if seen != OPERATION_IDS or len(seen) != len(set(seen)) or edges != OPERATION_SUPERSESSION:
        raise ContractError("operation set/order/supersession drift")
    for start in edges:
        visited: set[str] = set()
        current = start
        while current in edges:
            if current in visited:
                raise ContractError("operation supersession cycle")
            visited.add(current)
            current = edges[current]
    if require_live:
        if manifest.get("status") != "ACCEPTED" or review.get("status") != "ACCEPTED":
            raise ContractError("operation reconciliation is not independently accepted")
        if any(row.get("effective_status") == "PENDING_RECONCILIATION" for row in operations):
            raise ContractError("operation reconciliation still has pending outcomes")
    elif manifest.get("status") not in {"PENDING_REMOTE_RECEIPT_IMPORT_AND_INDEPENDENT_RECONCILIATION", "ACCEPTED"}:
        raise ContractError("invalid operation reconciliation status")


def _validate_host_control_state_contract(custody: dict[str, Any]) -> None:
    contract = custody.get("trusted_host_control_state_contract")
    if not isinstance(contract, dict) or set(contract) != {
        "global_containment_marker", "per_attempt_records", "failure_evidence",
    }:
        raise ContractError("trusted host control-state contract has an inexact schema")
    marker = contract.get("global_containment_marker")
    records = contract.get("per_attempt_records")
    failures = contract.get("failure_evidence")
    if marker != {
        "schema": "arnold.cloud.zero_recovery_marker.v2",
        "exact_fields": ["schema", "profile", "scope", "active"],
        "transaction_independent": True,
        "publish_after": [
            "durable_unit_containment_proof",
            "durable_systemd_job_containment_proof",
            "durable_session_containment_proof",
            "durable_process_containment_proof",
        ],
        "canonical_reuse": "ALLOWED_ONLY_AFTER_FRESH_DURABLE_CONTAINMENT_REPROOF",
        "mismatch": "HARD_NO_GO",
    }:
        raise ContractError("global containment marker contract drift")
    if records != {
        "records": ["intent", "apply", "verify", "failure"],
        "exact_binding_fields": ["transaction_id", "transaction_digest", "action"],
        "fresh_retry": "NEW_SUPPORTED_TRANSACTION_AND_FRESH_EVIDENCE",
    }:
        raise ContractError("per-attempt transaction record contract drift")
    if failures != {
        "pre_intent": "NO_MUTATION_FAIL_CLOSED_SUPPORTED_CALLER_CAPTURED_TYPED_ERROR",
        "post_intent_partial_post_prune": "DURABLE_O_EXCL_HOST_FAILURE_RECEIPT",
    }:
        raise ContractError("failure evidence authority split drift")


def _validate_route(route: dict[str, Any]) -> None:
    bindings = route.get("additional_bindings")
    if not isinstance(bindings, dict):
        raise ContractError("route additional_bindings missing")
    for name in ("trusted_host_control_state", "bounded_fence_reclaim", "stable_exit"):
        value = bindings.get(name)
        if not isinstance(value, dict) or value.get("status") != "PRELAUNCH_REQUIRED":
            raise ContractError(f"route binding {name} is not PRELAUNCH_REQUIRED")
    host = bindings["trusted_host_control_state"]
    identity = host.get("directory_identity")
    if (
        host.get("location") != "fixed_host_path_outside_all_historical_and_canary_workspaces"
        or identity != {"type": "directory", "uid": 0, "gid": 0, "mode": "0700", "symlink_free": True}
        or host.get("writes") != "dirfd_relative_no_follow_atomic_file_and_directory_fsync"
        or host.get("global_marker_exact_fields") != ["schema", "profile", "scope", "active"]
        or host.get("global_marker_publication") != "only_after_durable_unit_job_session_process_containment_proof"
        or host.get("global_marker_reuse") != "same_canonical_marker_after_fresh_durable_containment_reproof"
        or host.get("per_attempt_record_exact_fields") != ["transaction_id", "transaction_digest", "action"]
        or host.get("fresh_retry") != "new_supported_transaction_and_fresh_evidence"
        or host.get("global_marker_mismatch") != "HARD_NO_GO"
    ):
        raise ContractError("trusted host control-state contract drift")
    fence = bindings["bounded_fence_reclaim"]
    if (
        fence.get("all_eight_units_before_prune") != "absent_or_inactive_and_masked"
        or fence.get("systemd_jobs") != "emitter_parser_exact_empty_recovery_set"
        or fence.get("persistent_masks") != "crash_safe_before_prune"
        or fence.get("pre_intent_failure") != "no_mutation_fail_closed_supported_caller_captured_typed_error"
        or fence.get("post_intent_failure") != "durable_O_EXCL_host_failure_receipt"
        or fence.get("built_image_four_phase_smoke") != "REQUIRED_BEFORE_DEPLOY"
    ):
        raise ContractError("bounded fence/reclaim contract drift")


def _validate_chain_and_proof_map(chain: dict[str, Any], proof_map: dict[str, Any]) -> None:
    completion_path = ".megaplan/initiatives/critique-ledger-safe-v3-canary/completion-receipt.json"
    stable_path = ".megaplan/initiatives/critique-ledger-safe-v3-canary/stable-exit-receipt.json"
    expected_preconditions = [
        ("artifact", completion_path, {"kind": "exists"}),
        ("artifact", stable_path, {"kind": "exists"}),
        ("git_tracked", ".megaplan/initiatives/critique-ledger-safe-v3-canary", None),
        ("git_tracked", ".megaplan/initiatives/critique-ledger-post-relaunch-completion", None),
    ]
    preconditions = chain.get("launch_preconditions")
    if not isinstance(preconditions, list) or len(preconditions) != len(expected_preconditions):
        raise ContractError("chain launch precondition count drift")
    for row, (kind, path, check) in zip(preconditions, expected_preconditions):
        if (
            not isinstance(row, dict)
            or row.get("kind") != kind
            or row.get("path") != path
            or row.get("check") != check
        ):
            raise ContractError("chain launch precondition drift")
    milestones = chain.get("milestones")
    expected_labels = [
        "f0-finite-canary-handoff-admission",
        "f1-owner-storage-recovery-hardening",
        "f2-admission-model-effect-release-closure",
        "f3-cl2-real-work-and-publication",
        "f4-cl3-cl5-epic-completion",
        "f5-product-release-and-deploy",
        "f6-production-acceptance",
        "f7-evidence-and-incident-closeout",
        "f8-seven-day-durability",
    ]
    if not isinstance(milestones, list) or [row.get("label") for row in milestones if isinstance(row, dict)] != expected_labels:
        raise ContractError("chain milestone order/set drift")
    if milestones[0].get("depends_on") not in (None, []) or milestones[1].get("depends_on") != [expected_labels[0]]:
        raise ContractError("F0/F1 dependency boundary drift")
    for index in range(2, len(milestones)):
        if milestones[index].get("depends_on") != [expected_labels[index - 1]]:
            raise ContractError("follow-up milestone dependency drift")
    if proof_map.get("f0-finite-canary-handoff-admission") != [
        "evidence/critique-ledger-recovery/T6.2/handoff-admission/completion-manifest.json"
    ]:
        raise ContractError("F0 proof map drift")
    if proof_map.get("finite-canary-stable-exit") != STABLE_EXIT_PROOFS:
        raise ContractError("stable-exit proof map drift")
    if proof_map.get("finite-canary-prelaunch-history") != [
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/evidence/operation-reconciliation-manifest.json",
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/custody-manifest.json",
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/UNFINISHED_WORK.md",
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/RUNBOOK.md",
    ]:
        raise ContractError("prelaunch history proof map drift")


def _validate_supersession(*, require_live: bool) -> None:
    index = _load_json(INITIATIVE / "supersession-index.json")
    if index.get("schema") != "arnold.critique_ledger.supersession_index.v2":
        raise ContractError("supersession index schema drift")
    operation_rows = index.get("operation_supersession")
    if not isinstance(operation_rows, list) or [
        (row.get("operation_id"), row.get("superseded_by")) for row in operation_rows if isinstance(row, dict)
    ] != [
        ("critique-ledger-capacity-reserve-remediation-20260803-0349z", "critique-ledger-capacity-reserve-fallback-20260803-0350z"),
        ("critique-ledger-failed-build-capacity-reset-20260803-0400z", "critique-ledger-failed-build-capacity-reset-corrected-20260803-0404z"),
    ]:
        raise ContractError("operation supersession index drift")
    attempts = index.get("prelaunch_attempt_supersession")
    known_ids = [row[0] for row in KNOWN_ATTEMPTS]
    if (
        not isinstance(attempts, dict)
        or attempts.get("ordered_rejected_attempts") != known_ids
        or attempts.get("passing_successor") != B28_PASS["id"]
        or attempts.get("rule") != "SUPERSESSION_PRESERVES_FAILURE_EVIDENCE_AND_NEVER_IMPLIES_SUCCESS"
    ):
        raise ContractError("attempt supersession index drift")
    accepted = attempts.get("accepted_successor")
    if require_live:
        if accepted != B28_PASS["id"]:
            raise ContractError("latest passing smoke is not independently accepted")
        if attempts.get("status") != "ACCEPTED_STRICTLY_LATER_SMOKE":
            raise ContractError("strictly later smoke is not accepted")
    elif accepted == B26_PASS["id"]:
        if attempts.get("status") != "B26_SOL_GO_B27_LIVE_FAILED_B28_PASS_PENDING_SOL_ACCEPTANCE_AND_LIVE_RETRY":
            raise ContractError("latest passing smoke pending disposition drift")
    elif accepted != B28_PASS["id"] or attempts.get("status") != "ACCEPTED_STRICTLY_LATER_SMOKE":
        raise ContractError("invalid accepted smoke successor")


def _validate_runbook() -> None:
    runbook = (INITIATIVE / "RUNBOOK.md").read_text(encoding="utf-8")
    required = [
        "do not use ordinary `cloud deploy`, `cloud chain`,",
        "`cloud supervise`",
        "Never redispatch",
        "Hard NO-GO default",
        "F0 may write only its admission manifest",
        "generic command is not a fallback",
    ]
    if any(text not in runbook for text in required):
        raise ContractError("incident runbook lost a fail-closed route rule")


def _validate_readme(route_path: Path) -> None:
    readme = (INITIATIVE / "README.md").read_text(encoding="utf-8")
    digest = _sha256(route_path)
    if f"SHA-256 `{digest}`" not in readme:
        raise ContractError("README route digest is stale")
    supersession = _load_json(INITIATIVE / "supersession-index.json")
    current = supersession.get("current_operational_route")
    if not isinstance(current, dict) or current.get("sha256") != digest:
        raise ContractError("supersession index route digest is stale")


def _validate_stable_exit_receipt(*, require_live: bool) -> None:
    path = ROOT / ".megaplan/initiatives/critique-ledger-safe-v3-canary/stable-exit-receipt.json"
    if not path.exists():
        if require_live:
            raise ContractError("stable-exit receipt is missing")
        return
    payload = _load_json(path)
    required = {
        "schema", "status", "accepted_candidate", "receipt_digests",
        "predecessor", "successor", "runtime_absence", "host_control_state",
        "custody", "deferred_obligations", "observed_at",
    }
    candidate = payload.get("accepted_candidate")
    digests = payload.get("receipt_digests")
    predecessor = payload.get("predecessor")
    successor = payload.get("successor")
    absence = payload.get("runtime_absence")
    host = payload.get("host_control_state")
    custody = payload.get("custody")
    if (
        set(payload) != required
        or payload.get("schema") != "arnold.critique_ledger.stable_exit_receipt.v1"
        or payload.get("status") != "passed"
        or not isinstance(candidate, dict)
        or set(candidate) != {
            "implementation_commit", "implementation_tree", "manifest_commit",
            "manifest_tree", "image_id", "image_digest", "independent_review_sha256",
        }
        or any(not isinstance(candidate.get(key), str) or not candidate.get(key) for key in candidate)
        or not isinstance(digests, dict)
        or set(digests) != {
            "built_image_smoke", "prelaunch_receipts_manifest", "conformance",
            "completion", "terminal_stop", "fresh_clone_reconstruction",
        }
        or any(not SHA256.fullmatch(str(value)) for value in digests.values())
        or predecessor != {"state": "stopped", "preserved": True, "persistently_fenced": True}
        or successor != {"terminal": "finalized", "state": "stopped"}
        or not isinstance(absence, dict)
        or absence != {
            "systemd_jobs": [], "tmux_sessions": [], "processes": [],
            "notifier": False, "fixer": False, "resident": False,
            "watchdog": False, "timer": False,
        }
        or not isinstance(host, dict)
        or host.get("uid") != 0
        or host.get("gid") != 0
        or host.get("mode") != "0700"
        or host.get("symlink_free") is not True
        or set(host) != {
            "path", "uid", "gid", "mode", "symlink_free", "global_marker_v2",
            "global_marker_transaction_independent", "containment_reproved_for_exit",
            "per_attempt_receipts_transaction_bound",
        }
        or host.get("global_marker_v2") is not True
        or host.get("global_marker_transaction_independent") is not True
        or host.get("containment_reproved_for_exit") is not True
        or host.get("per_attempt_receipts_transaction_bound") is not True
        or not isinstance(custody, dict)
        or set(custody) != {
            "follow_up_commit", "follow_up_tree", "remote_ref", "custody_anchor",
            "prelaunch_tag", "postcanary_tag", "runnable_integration_ref",
            "fresh_clone_receipt_sha256",
        }
        or any(not isinstance(custody.get(key), str) or not custody.get(key) for key in custody)
        or not SHA256.fullmatch(str(custody.get("fresh_clone_receipt_sha256")))
        or payload.get("deferred_obligations") != list(OBLIGATIONS)
        or not isinstance(payload.get("observed_at"), str)
        or not payload.get("observed_at")
    ):
        raise ContractError("stable-exit receipt failed strict verification")
    if require_live:
        digest_paths = {
            "built_image_smoke": STABLE_EXIT_PROOFS[0],
            "prelaunch_receipts_manifest": STABLE_EXIT_PROOFS[1],
            "conformance": STABLE_EXIT_PROOFS[2],
            "completion": STABLE_EXIT_PROOFS[3],
            "terminal_stop": ".megaplan/initiatives/critique-ledger-safe-v3-canary/terminal-stop-receipt.json",
            "fresh_clone_reconstruction": STABLE_EXIT_PROOFS[5],
        }
        for name, relative in digest_paths.items():
            proof_path = _repo_path(relative)
            if not proof_path.is_file() or _sha256(proof_path) != digests[name]:
                raise ContractError(f"stable-exit proof digest mismatch: {name}")


def validate(*, require_live: bool = False) -> None:
    custody = _load_json(INITIATIVE / "custody-manifest.json")
    if custody.get("schema") != "arnold.critique_ledger.unfinished_work_custody.v4":
        raise ContractError("custody manifest schema must be v4")
    _validate_obligations(custody)
    _validate_attempt_history(custody, require_live=require_live)
    _validate_live_deploy_attempts(custody)
    _validate_live_canary_attempts(custody)
    _validate_prelaunch_gates(custody, require_live=require_live)
    _validate_host_control_state_contract(custody)
    reconciliation = custody.get("live_operation_reconciliation")
    if reconciliation != {
        "path": ".megaplan/initiatives/critique-ledger-post-relaunch-completion/evidence/operation-reconciliation-manifest.json",
        "sha256": "9cf695c56250738f3dd67cc269aa220449b6636c7c6ee990ce79f1a8dd29c23b",
        "status": "PENDING_REMOTE_RECEIPT_IMPORT_AND_INDEPENDENT_RECONCILIATION",
        "launch_disposition": "HARD_NO_GO",
        "immutable_intent_count": 5,
        "rule": "DO_NOT_REWRITE_INTENTS_OR_REDISPATCH_AMBIGUOUS_OPERATIONS",
    }:
        if not (
            isinstance(reconciliation, dict)
            and set(reconciliation) == {"path", "sha256", "status", "launch_disposition", "immutable_intent_count", "rule"}
            and reconciliation.get("path") == ".megaplan/initiatives/critique-ledger-post-relaunch-completion/evidence/operation-reconciliation-manifest.json"
            and reconciliation.get("status") == "ACCEPTED"
            and reconciliation.get("launch_disposition") == "ADMITTED_BY_F0"
            and reconciliation.get("immutable_intent_count") == 5
            and reconciliation.get("rule") == "DO_NOT_REWRITE_INTENTS_OR_REDISPATCH_AMBIGUOUS_OPERATIONS"
            and SHA256.fullmatch(str(reconciliation.get("sha256")))
            and _sha256(INITIATIVE / "evidence/operation-reconciliation-manifest.json")
            == reconciliation.get("sha256")
        ):
            raise ContractError("custody operation reconciliation pointer drift")
    if _sha256(INITIATIVE / "evidence/operation-reconciliation-manifest.json") != reconciliation.get("sha256"):
        raise ContractError("custody operation reconciliation hash mismatch")
    _validate_operation_reconciliation(require_live=require_live)
    route_path = INITIATIVE / "finite-canary-operational-route.json"
    _validate_route(_load_json(route_path))
    proof_map = _load_json(INITIATIVE / "proof-map.json")
    chain_path = INITIATIVE / "chain.yaml"
    chain = yaml.safe_load(chain_path.read_text(encoding="utf-8"))
    if not isinstance(chain, dict):
        raise ContractError("chain.yaml must contain a mapping")
    try:
        load_spec(chain_path)
    except Exception as exc:
        raise ContractError(f"installed chain parser rejected chain.yaml: {exc}") from exc
    _validate_chain_and_proof_map(chain, proof_map)
    _validate_supersession(require_live=require_live)
    _validate_runbook()
    _validate_readme(route_path)
    _validate_stable_exit_receipt(require_live=require_live)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-live", action="store_true")
    args = parser.parse_args()
    validate(require_live=args.require_live)
    print("critique-ledger follow-up contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
