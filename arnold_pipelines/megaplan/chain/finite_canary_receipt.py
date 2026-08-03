"""Strict launch admission for finite-canary completion and stable-exit receipts."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from arnold_pipelines.megaplan.types import CliError


_COMPLETION_SCHEMA = "arnold.megaplan.finite_canary_receipt.v1"
_STABLE_EXIT_SCHEMA = "arnold.critique_ledger.stable_exit_receipt.v1"
_PHASES = ["init", "plan", "critique", "gate", "finalize"]
_STATES = ["initialized", "planned", "critiqued", "gated", "finalized"]
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_GIT_OBJECT = re.compile(r"[0-9a-f]{40}\Z")
_COMPLETION_ROLES = {
    "canary_spec",
    "proof_map",
    "traceability",
    "run_receipt",
    "independent_conformance_receipt",
    "host_zero_recovery_fence_receipt",
    "host_predeploy_receipt",
    "v2_terminal_fence_receipt",
    "detached_reviewer_source",
    "dispatch_ledger",
    "phase_receipts_manifest",
    "privilege_receipts_manifest",
    "plan_state",
    "gate_result",
    "cloud_spec",
    "custody_manifest",
    "unfinished_work_ledger",
    "supersession_index",
    "finite_canary_operational_route",
}
_SUBSTRATES = [
    {"id": "cloud-observation-preflight-repair-v2", "disposition": "CONSUMED_BOUNDED_SUBSTRATE"},
    {"id": "t1.9-zero-recovery-launcher", "disposition": "CONSUMED_ON_SUCCESS"},
]
_OBLIGATION_IDS = [
    "F1.platform_capacity_storage_hardening",
    "F1.physically_minimal_image",
    "F1.cross_pipeline_model_isolation",
    "F1.t1_5_monotonic_consumed_grant",
    "F1.production_recovery_owner",
    "F1.exact_occurrence_handoff",
    "F1.notification_occurrence_version_custody",
    "F1.t1_5_topology_retirement",
    "F1.t1_7_transactional_storage",
    "F1.t1_10_notification_policy",
    "F2.t1_1_universal_admission",
    "F2.t1_2_attempt_model_handling",
    "F2.provider_attested_model_identity",
    "F2.t1_3_transport_integration",
    "F2.t1_4_t1_6_release_closure",
]
_DEFERRED = [
    {
        "id": item,
        "phase": item.split(".", 1)[0],
        "status": "DEFERRED_POST_CANARY",
        "operational_disposition": "NOT_CONSUMED_OPERATIONAL_CANARY",
    }
    for item in _OBLIGATION_IDS
]
_STABLE_PROOFS = {
    "built_image_smoke": "built-image-smoke-receipt.json",
    "prelaunch_receipts_manifest": "prelaunch-receipts-manifest.json",
    "conformance": "conformance-receipt.json",
    "completion": "completion-receipt.json",
    "terminal_stop": "terminal-stop-receipt.json",
    "fresh_clone_reconstruction": "fresh-clone-reconstruction-receipt.json",
}


def _fail(label: str, spec_path: Path, detail: str) -> CliError:
    return CliError(
        "launch_precondition_failed",
        f"{label} failed for {spec_path}: {detail}",
    )


def _strict_json(path: Path, *, label: str, spec_path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicates,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise _fail(label, spec_path, f"receipt evidence is not strict JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise _fail(label, spec_path, f"receipt evidence must be a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(payload: dict[str, Any], digest_field: str) -> bool:
    unsigned = dict(payload)
    digest = unsigned.pop(digest_field, None)
    return bool(
        isinstance(digest, str)
        and _SHA256.fullmatch(digest)
        and hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == digest
    )


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None


def _repo_file(raw_path: str, root: Path, *, label: str, spec_path: Path) -> Path:
    relative = PurePosixPath(raw_path)
    if (
        relative.is_absolute()
        or raw_path != relative.as_posix()
        or raw_path in {".", ".."}
        or ".." in relative.parts
    ):
        raise _fail(label, spec_path, f"evidence path is not normalized repository-relative: {raw_path!r}")
    lexical = root / Path(*relative.parts)
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise _fail(label, spec_path, f"evidence path contains a symlink: {raw_path!r}")
    target = lexical.resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise _fail(label, spec_path, f"evidence path escapes the project root: {raw_path!r}") from exc
    if not target.is_file():
        raise _fail(label, spec_path, f"receipt evidence is missing: {raw_path}")
    return target


def _require_clean_head(path: Path, root: Path, *, label: str, spec_path: Path) -> None:
    relative = path.relative_to(root).as_posix()
    commands = (
        ["git", "cat-file", "-e", f"HEAD:{relative}"],
        ["git", "diff", "--quiet", "HEAD", "--", relative],
    )
    for command in commands:
        result = subprocess.run(
            command,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise _fail(label, spec_path, f"receipt evidence is untracked, stale, or dirty in HEAD: {relative}")


def _artifacts(
    payload: dict[str, Any],
    root: Path,
    *,
    label: str,
    spec_path: Path,
) -> dict[str, tuple[Path, str]]:
    rows = payload.get("artifacts")
    if not isinstance(rows, list) or len(rows) != len(_COMPLETION_ROLES):
        raise _fail(label, spec_path, "finite canary artifact role count is inexact")
    roles: list[str] = []
    paths: list[str] = []
    result: dict[str, tuple[Path, str]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"role", "path", "sha256"}:
            raise _fail(label, spec_path, "finite canary artifact fields are ambiguous")
        role = row.get("role")
        raw_path = row.get("path")
        digest = row.get("sha256")
        if (
            not isinstance(role, str)
            or role not in _COMPLETION_ROLES
            or not isinstance(raw_path, str)
            or not isinstance(digest, str)
            or not _SHA256.fullmatch(digest)
        ):
            raise _fail(label, spec_path, "finite canary artifact identity is invalid")
        path = _repo_file(raw_path, root, label=label, spec_path=spec_path)
        if _sha256(path) != digest:
            raise _fail(label, spec_path, f"finite canary artifact hash mismatch: {raw_path}")
        _require_clean_head(path, root, label=label, spec_path=spec_path)
        roles.append(role)
        paths.append(raw_path)
        result[role] = (path, digest)
    if set(roles) != _COMPLETION_ROLES or len(set(roles)) != len(roles):
        raise _fail(label, spec_path, "finite canary artifact roles are missing, extra, or duplicated")
    if len(set(paths)) != len(paths):
        raise _fail(label, spec_path, "finite canary artifact paths are duplicated")
    return result


def _validate_custody(
    payload: dict[str, Any],
    artifacts: dict[str, tuple[Path, str]],
    *,
    label: str,
    spec_path: Path,
) -> None:
    custody = _strict_json(artifacts["custody_manifest"][0], label=label, spec_path=spec_path)
    obligations = custody.get("deferred_obligations")
    normalized = [
        {key: row.get(key) for key in _DEFERRED[0]}
        for row in obligations
        if isinstance(row, dict)
    ] if isinstance(obligations, list) else None
    supersession = _strict_json(artifacts["supersession_index"][0], label=label, spec_path=spec_path)
    route = _strict_json(artifacts["finite_canary_operational_route"][0], label=label, spec_path=spec_path)
    if (
        custody.get("schema") != "arnold.critique_ledger.unfinished_work_custody.v4"
        or custody.get("operational_substrates") != _SUBSTRATES
        or normalized != _DEFERRED
        or len({row["id"] for row in normalized or []}) != len(_DEFERRED)
        or payload.get("operational_substrates") != _SUBSTRATES
        or payload.get("deferred_obligations") != _DEFERRED
        or route.get("schema") != "arnold.critique_ledger.finite_canary_operational_route.v2"
        or route.get("profile") != "ZERO_RECOVERY_NONROOT_FINITE_CANARY"
        or route.get("additional_bindings", {}).get("effects")
        != {
            "automatic_recovery": "DISABLED_FAIL_CLOSED",
            "notifications": "DISABLED_FAIL_CLOSED",
            "residents_watchdogs_timers": "ABSENT",
        }
        or supersession.get("schema") != "arnold.critique_ledger.supersession_index.v2"
        or supersession.get("current_operational_route", {}).get("sha256")
        != artifacts["finite_canary_operational_route"][1]
    ):
        raise _fail(label, spec_path, "custody, route, supersession, substrate, or deferred-obligation semantics are invalid")


def _validate_completion(
    payload: dict[str, Any],
    receipt_path: Path,
    root: Path,
    *,
    label: str,
    spec_path: Path,
) -> None:
    if set(payload) != {
        "schema", "status", "phases", "terminal_state", "artifacts",
        "subject", "issued_at", "completed_at", "receipt_digest",
        "operational_substrates", "deferred_obligations",
    }:
        raise _fail(label, spec_path, "finite canary receipt has ambiguous top-level fields")
    issued = _utc(payload.get("issued_at"))
    completed = _utc(payload.get("completed_at"))
    if (
        payload.get("status") != "passed"
        or payload.get("phases") != _PHASES
        or payload.get("terminal_state") != "finalized"
        or issued is None
        or completed is None
        or completed < issued
        or not _canonical_digest(payload, "receipt_digest")
    ):
        raise _fail(label, spec_path, "finite canary status, phases, chronology, terminal state, or digest is invalid")
    subject = payload.get("subject")
    subject_fields = {
        "canary_id", "plan_name", "source_commit", "source_tree",
        "engine_commit", "engine_tree", "cloud", "canary_spec_sha256",
    }
    cloud_fields = {
        "provider", "host", "port", "predecessor_container",
        "predecessor_container_id", "canary_container", "image_id", "workspace",
        "predecessor_workspace", "workspace_bind_source",
    }
    if (
        not isinstance(subject, dict)
        or set(subject) != subject_fields
        or not isinstance(subject.get("cloud"), dict)
        or set(subject["cloud"]) != cloud_fields
        or subject["cloud"].get("provider") != "ssh"
        or type(subject["cloud"].get("port")) is not int
        or any(not _GIT_OBJECT.fullmatch(str(subject.get(key))) for key in ("source_commit", "source_tree", "engine_commit", "engine_tree"))
        or not _SHA256.fullmatch(str(subject.get("canary_spec_sha256")))
        or any(not isinstance(subject["cloud"].get(key), str) or not subject["cloud"].get(key) for key in cloud_fields - {"port"})
    ):
        raise _fail(label, spec_path, "finite canary subject is invalid")
    artifacts = _artifacts(payload, root, label=label, spec_path=spec_path)
    if subject["canary_spec_sha256"] != artifacts["canary_spec"][1]:
        raise _fail(label, spec_path, "subject does not bind the canary spec")
    try:
        canary = yaml.safe_load(artifacts["canary_spec"][0].read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise _fail(label, spec_path, f"canary spec is invalid: {exc}") from exc
    if (
        not isinstance(canary, dict)
        or canary.get("schema") != "arnold.megaplan.finite_canary.v1"
        or canary.get("canary_id") != subject.get("canary_id")
        or canary.get("plan_name") != subject.get("plan_name")
        or canary.get("engine_commit") != subject.get("engine_commit")
        or canary.get("engine_tree") != subject.get("engine_tree")
        or canary.get("phases") != _PHASES
        or canary.get("terminal_state") != "finalized"
    ):
        raise _fail(label, spec_path, "canary spec does not bind the exact subject")
    proof = _strict_json(artifacts["proof_map"][0], label=label, spec_path=spec_path)
    trace = _strict_json(artifacts["traceability"][0], label=label, spec_path=spec_path)
    claims = proof.get("claims")
    if (
        set(proof) != {"schema", "implementation", "launch_manifest", "claims", "excluded_claims"}
        or proof.get("schema") != "arnold.megaplan.finite_canary_proof_map.v1"
        or proof.get("implementation") != {"commit": subject["engine_commit"], "tree": subject["engine_tree"]}
        or not isinstance(claims, list)
        or not claims
        or any(not isinstance(row, dict) or set(row) != {"claim", "evidence"} or not all(isinstance(value, str) and value for value in row.values()) for row in claims)
        or len({row["claim"] for row in claims}) != len(claims)
        or trace.get("schema") != "arnold.megaplan.finite_canary_traceability.v1"
        or trace.get("implementation_commit") != subject["engine_commit"]
        or trace.get("implementation_tree") != subject["engine_tree"]
        or trace.get("fresh_workspace") != subject["cloud"]["workspace"]
        or trace.get("predecessor_workspace") != subject["cloud"]["predecessor_workspace"]
        or trace.get("workspace_bind_source") != subject["cloud"]["workspace_bind_source"]
    ):
        raise _fail(label, spec_path, "proof map or traceability does not bind the exact subject")
    run = _strict_json(artifacts["run_receipt"][0], label=label, spec_path=spec_path)
    phase_results = run.get("phase_results")
    dispatches = run.get("dispatches")
    if (
        run.get("schema") != "arnold.megaplan.finite_canary_run_receipt.v2"
        or run.get("status") != "passed"
        or run.get("canary_id") != subject["canary_id"]
        or run.get("plan_name") != subject["plan_name"]
        or run.get("phases") != _PHASES
        or phase_results != [
            {"phase": phase, "returncode": 0, "state": state}
            for phase, state in zip(_PHASES, _STATES, strict=True)
        ]
        or run.get("terminal_state") != "finalized"
        or run.get("failure") is not None
        or run.get("source_commit") != subject["source_commit"]
        or run.get("source_tree") != subject["source_tree"]
        or run.get("canary_spec_sha256") != artifacts["canary_spec"][1]
        or run.get("dispatch_integrity") != "complete"
        or not isinstance(dispatches, list)
        or len(dispatches) != 8
        or [row.get("event") for row in dispatches if isinstance(row, dict)] != [event for _ in _PHASES[1:] for event in ("start", "terminal")]
        or [row.get("phase") for row in dispatches if isinstance(row, dict)] != [phase for phase in _PHASES[1:] for _ in (0, 1)]
        or any(not isinstance(row, dict) or row.get("attempt") != 1 or any(row.get(key) is not False for key in ("retry", "fallback", "json_repair", "adaptive_routing")) for row in dispatches)
        or not _canonical_digest(run, "receipt_digest")
    ):
        raise _fail(label, spec_path, "run receipt is not one exact successful finite run")
    state = _strict_json(artifacts["plan_state"][0], label=label, spec_path=spec_path)
    gate = _strict_json(artifacts["gate_result"][0], label=label, spec_path=spec_path)
    if state.get("current_state") != "finalized" or state.get("active_step") not in (None, "") or gate.get("recommendation") != "PROCEED":
        raise _fail(label, spec_path, "plan state or gate is not terminal and accepted")
    conformance = _strict_json(artifacts["independent_conformance_receipt"][0], label=label, spec_path=spec_path)
    review_inputs = conformance.get("review_input_sha256")
    reviewer = conformance.get("reviewer")
    conformance_unsigned = dict(conformance)
    attestation_digest = conformance_unsigned.pop("attestation_digest", None)
    required_review_inputs = {
        role: digest
        for role, (_path, digest) in artifacts.items()
        if role != "independent_conformance_receipt"
    }
    if (
        set(conformance) != {
            "schema", "status", "subject", "run_receipt_sha256", "checks",
            "reviewer", "reviewed_at", "trust_anchor", "review_input_sha256",
            "review_execution", "attestation_digest",
        }
        or conformance.get("schema") != "arnold.megaplan.finite_canary_conformance_receipt.v1"
        or conformance.get("status") != "passed"
        or conformance.get("subject") != subject
        or conformance.get("run_receipt_sha256") != artifacts["run_receipt"][1]
        or conformance.get("checks")
        != [
            "exact_phase_order",
            "single_dispatch_pairs",
            "terminal_finalized",
            "artifact_hashes",
            "zero_recovery_fence",
            "workspace_isolation",
        ]
        or not isinstance(reviewer, dict)
        or set(reviewer) != {"kind", "identity", "source_sha256"}
        or reviewer.get("kind") != "detached_host_process"
        or reviewer.get("identity") != "arnold.chain.finite_canary_validator"
        or reviewer.get("source_sha256") != artifacts["detached_reviewer_source"][1]
        or artifacts["detached_reviewer_source"][0].relative_to(root).as_posix()
        != "arnold_pipelines/megaplan/chain/finite_canary_receipt.py"
        or conformance.get("trust_anchor") != "arnold.detached_host_reviewer.v1"
        or conformance.get("review_execution")
        != {"mode": "detached_subprocess", "exit_code": 0, "result": "passed"}
        or _utc(conformance.get("reviewed_at")) is None
        or review_inputs != required_review_inputs
        or not isinstance(attestation_digest, str)
        or not _SHA256.fullmatch(attestation_digest)
        or hashlib.sha256(
            json.dumps(
                conformance_unsigned,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        != attestation_digest
    ):
        raise _fail(label, spec_path, "independent conformance does not bind the run, proof map, validator, and traceability")
    fence = _strict_json(artifacts["host_zero_recovery_fence_receipt"][0], label=label, spec_path=spec_path)
    units = fence.get("units")
    if (
        fence.get("status") != "passed"
        or not isinstance(units, list)
        or len(units) != 8
        or any(not isinstance(row, dict) or row.get("state") not in {"masked", "absent"} for row in units)
        or fence.get("forbidden_sessions") != []
        or fence.get("forbidden_processes") != []
        or fence.get("systemd_jobs", []) != []
    ):
        raise _fail(label, spec_path, "v2 fence is not closed and process-empty")
    terminal = _strict_json(artifacts["v2_terminal_fence_receipt"][0], label=label, spec_path=spec_path)
    if (
        terminal.get("status") != "passed"
        or terminal.get("subject") != subject
        or terminal.get("canary_lifecycle") != "stopped"
        or terminal.get("restart_policy") != "no"
        or terminal.get("host_units_masked") is not True
        or terminal.get("forbidden_sessions") != []
        or terminal.get("forbidden_processes") != []
    ):
        raise _fail(label, spec_path, "terminal stop/no-background fence is invalid")
    predeploy = _strict_json(artifacts["host_predeploy_receipt"][0], label=label, spec_path=spec_path)
    if (
        predeploy.get("schema") != "arnold.cloud.zero_recovery_predeploy.v1"
        or predeploy.get("capacity_observation", {}).get("verdict") != "GO"
        or predeploy.get("target", {}).get("host") != subject["cloud"]["host"]
        or predeploy.get("target", {}).get("canary_container") != subject["cloud"]["canary_container"]
    ):
        raise _fail(label, spec_path, "provider preflight does not bind the exact admitted subject")
    _validate_custody(payload, artifacts, label=label, spec_path=spec_path)
    _require_clean_head(receipt_path, root, label=label, spec_path=spec_path)


def _validate_stable_exit(
    payload: dict[str, Any],
    receipt_path: Path,
    root: Path,
    *,
    label: str,
    spec_path: Path,
) -> None:
    required = {
        "schema", "status", "accepted_candidate", "receipt_digests",
        "predecessor", "successor", "runtime_absence", "host_control_state",
        "custody", "deferred_obligations", "observed_at",
    }
    candidate = payload.get("accepted_candidate")
    digests = payload.get("receipt_digests")
    host = payload.get("host_control_state")
    custody = payload.get("custody")
    if (
        set(payload) != required
        or payload.get("status") != "passed"
        or not isinstance(candidate, dict)
        or set(candidate) != {
            "implementation_commit", "implementation_tree", "manifest_commit",
            "manifest_tree", "image_id", "image_digest", "independent_review_sha256",
        }
        or any(not isinstance(value, str) or not value for value in candidate.values())
        or not isinstance(digests, dict)
        or set(digests) != set(_STABLE_PROOFS)
        or any(not _SHA256.fullmatch(str(value)) for value in digests.values())
        or payload.get("predecessor") != {"state": "stopped", "preserved": True, "persistently_fenced": True}
        or payload.get("successor") != {"terminal": "finalized", "state": "stopped"}
        or payload.get("runtime_absence") != {
            "systemd_jobs": [], "tmux_sessions": [], "processes": [],
            "notifier": False, "fixer": False, "resident": False,
            "watchdog": False, "timer": False,
        }
        or not isinstance(host, dict)
        or set(host) != {
            "path", "uid", "gid", "mode", "symlink_free", "global_marker_v2",
            "global_marker_transaction_independent", "containment_reproved_for_exit",
            "per_attempt_receipts_transaction_bound",
        }
        or host.get("uid") != 0
        or host.get("gid") != 0
        or host.get("mode") != "0700"
        or any(host.get(key) is not True for key in (
            "symlink_free", "global_marker_v2", "global_marker_transaction_independent",
            "containment_reproved_for_exit", "per_attempt_receipts_transaction_bound",
        ))
        or not isinstance(custody, dict)
        or set(custody) != {
            "follow_up_commit", "follow_up_tree", "remote_ref", "custody_anchor",
            "prelaunch_tag", "postcanary_tag", "runnable_integration_ref",
            "fresh_clone_receipt_sha256",
        }
        or any(not isinstance(value, str) or not value for value in custody.values())
        or not _SHA256.fullmatch(str(custody.get("fresh_clone_receipt_sha256")))
        or payload.get("deferred_obligations") != _OBLIGATION_IDS
        or _utc(payload.get("observed_at")) is None
    ):
        raise _fail(label, spec_path, "stable-exit receipt failed strict semantic verification")
    for role, filename in _STABLE_PROOFS.items():
        proof = receipt_path.with_name(filename)
        if proof.is_symlink() or not proof.is_file() or _sha256(proof) != digests[role]:
            raise _fail(label, spec_path, f"stable-exit proof digest mismatch: {role}")
        try:
            proof.resolve().relative_to(root)
        except ValueError as exc:
            raise _fail(label, spec_path, f"stable-exit proof escapes project root: {role}") from exc
        _require_clean_head(proof, root, label=label, spec_path=spec_path)
    _require_clean_head(receipt_path, root, label=label, spec_path=spec_path)


def validate_finite_canary_receipt(
    receipt_path: Path,
    root: Path,
    spec_path: Path,
    *,
    label: str,
) -> None:
    """Validate a completion or stable-exit receipt and all bound evidence."""

    receipt_path = receipt_path.resolve(strict=False)
    root = root.resolve()
    try:
        receipt_path.relative_to(root)
    except ValueError as exc:
        raise _fail(label, spec_path, "receipt path escapes the project root") from exc
    if not receipt_path.is_file():
        raise _fail(label, spec_path, f"finite canary receipt missing at {receipt_path}")
    payload = _strict_json(receipt_path, label=label, spec_path=spec_path)
    schema = payload.get("schema")
    if schema == _COMPLETION_SCHEMA:
        _validate_completion(payload, receipt_path, root, label=label, spec_path=spec_path)
        return
    if schema == _STABLE_EXIT_SCHEMA:
        _validate_stable_exit(payload, receipt_path, root, label=label, spec_path=spec_path)
        return
    raise _fail(label, spec_path, f"unsupported finite canary receipt schema: {schema!r}")
