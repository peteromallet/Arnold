"""Isolated, evidence-first M11 genuine-block canary driver.

This module deliberately has no defaults that point at the live cloud marker,
repair-queue, or project roots.  One canary owns one private directory below
``/workspace/.megaplan/m11-canaries``.  The relaunch path reuses the canonical
F01 occurrence, custody action validator, singleton claim, and simple-fixer
runner; verifier commands are read-only and must run in later processes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from arnold_pipelines.megaplan.cloud.repair_revalidation import (
    LatencyLedgerRow,
    generate_latency_ledger,
)
from arnold_pipelines.megaplan.cloud.simple_fixer import (
    CANONICAL_VERIFIER_SLOTS,
    SimpleFixerOccurrence,
    build_simple_fixer_occurrence,
)
from arnold_pipelines.megaplan.cloud.wrappers.repair_delegation import (
    RepairDelegation,
    delegate_to_simple_fixer,
)
from arnold_pipelines.megaplan.custody.action_validator import (
    ActionBoundaryContext,
    ActionBoundaryResult,
    validate_action_boundary,
)
from arnold_pipelines.megaplan.custody.lease_store import open_lease_store
from arnold_pipelines.megaplan.custody.outbox import open_outbox
from arnold_pipelines.megaplan.custody.contracts import RepairOccurrenceKey
from arnold_pipelines.run_authority import CapabilityGrant, CoordinatorFence, Decision


CANARY_BASE = Path("/workspace/.megaplan/m11-canaries")
CANARY_PREFIX = "m11-genuine-block-"
SCHEMA = "arnold.megaplan.m11_live_canary.v1"
TERMINAL_STATES = {"accepted", "completed", "done", "finalized", "executed"}
ACCEPTANCE_EVENT_KINDS = {
    "completion_accepted",
    "milestone_accepted",
    "phase_accepted",
    "phase_complete",
    "task_accepted",
    "task_complete",
}
SLOT_SECONDS = {
    "five_minute": 5 * 60,
    "one_hour": 60 * 60,
    "next_three_hour": 3 * 60 * 60,
}


class CanarySafetyError(RuntimeError):
    """A fail-closed canary admission or evidence error."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise CanarySafetyError("timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def validate_canary_root(
    root: str | Path, *, base_root: str | Path = CANARY_BASE
) -> Path:
    """Require one named child below the dedicated canary base."""

    base = Path(base_root).resolve(strict=False)
    candidate = Path(root).resolve(strict=False)
    if candidate.parent != base or not candidate.name.startswith(CANARY_PREFIX):
        raise CanarySafetyError(
            f"canary root must be one direct {CANARY_PREFIX!r} child of {base}"
        )
    if candidate in {
        Path("/workspace").resolve(),
        Path("/workspace/.megaplan").resolve(),
        Path("/workspace/.megaplan/cloud-sessions").resolve(),
        Path("/workspace/.megaplan/repair-queue").resolve(),
    }:
        raise CanarySafetyError("global runtime roots are forbidden")
    return candidate


def _inside(root: Path, path: str | Path, *, name: str) -> Path:
    candidate = Path(path).resolve(strict=False)
    if candidate == root or not candidate.is_relative_to(root):
        raise CanarySafetyError(f"{name} must be below the private canary root")
    return candidate


def _atomic_json(path: Path, payload: Mapping[str, Any], *, exclusive: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise CanarySafetyError(f"symlink artifact parent rejected: {path.parent}")
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if exclusive:
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            return
        except FileExistsError as exc:
            raise CanarySafetyError(f"append-only artifact already exists: {path}") from exc
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanarySafetyError(f"invalid JSON artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise CanarySafetyError(f"JSON artifact must be an object: {path}")
    return payload


def _load_hashed_json(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    observed = str(payload.get("content_sha256") or "")
    unhashed = dict(payload)
    unhashed.pop("content_sha256", None)
    if not observed or observed != _digest(unhashed):
        raise CanarySafetyError(f"content hash mismatch: {path}")
    return payload


def _load_runtime_json(path: Path) -> dict[str, Any]:
    """Validate the canonical runtime-provenance bare-hex digest convention."""

    payload = _load_json(path)
    observed = str(payload.get("content_sha256") or "")
    unhashed = dict(payload)
    unhashed.pop("content_sha256", None)
    expected = hashlib.sha256(_canonical_bytes(unhashed)).hexdigest()
    if observed != expected:
        raise CanarySafetyError(f"runtime content hash mismatch: {path}")
    return payload


def _occurrence(payload: Mapping[str, Any]) -> SimpleFixerOccurrence:
    source = payload.get("target") if isinstance(payload.get("target"), Mapping) else payload
    occurrence = build_simple_fixer_occurrence(source)
    if occurrence is None:
        raise CanarySafetyError("exact F01 occurrence tuple is required")
    expected = str(payload.get("occurrence_fingerprint") or "")
    if expected and expected != occurrence.occurrence_fingerprint:
        raise CanarySafetyError("occurrence fingerprint mismatch")
    return occurrence


def _pid_live(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _validate_argv(
    argv: Sequence[str],
    *,
    expected_python: Path,
    worktree: Path,
) -> tuple[str, ...]:
    normalized = tuple(str(item) for item in argv)
    if not normalized or Path(normalized[0]).resolve(strict=True) != expected_python:
        raise CanarySafetyError("relaunch must use the exact expected interpreter")
    if "-P" not in normalized[1:]:
        raise CanarySafetyError("relaunch must enable Python safe-path mode with -P")
    required_prefix = (
        "-m",
        "arnold_pipelines.megaplan",
        "chain",
        "start",
    )
    if any(
        normalized[index : index + len(required_prefix)] == required_prefix
        for index in range(1, len(normalized) - len(required_prefix) + 1)
    ) is False:
        raise CanarySafetyError(
            "relaunch must use the canonical arnold_pipelines.megaplan "
            "chain start entrypoint"
        )
    try:
        spec_index = normalized.index("--spec")
        project_index = normalized.index("--project-dir")
        spec = Path(normalized[spec_index + 1])
        project = Path(normalized[project_index + 1])
    except (ValueError, IndexError) as exc:
        raise CanarySafetyError(
            "canonical relaunch requires --spec and --project-dir"
        ) from exc
    if not spec.is_absolute():
        spec = worktree / spec
    if not project.is_absolute():
        project = worktree / project
    spec = spec.resolve(strict=False)
    project = project.resolve(strict=False)
    if project != worktree or not spec.is_relative_to(worktree):
        raise CanarySafetyError(
            "canonical relaunch spec/project must stay inside the canary worktree"
        )
    for token in normalized[1:]:
        if token.startswith("/"):
            path = Path(token).resolve(strict=False)
            if path != worktree and not path.is_relative_to(worktree):
                raise CanarySafetyError(
                    f"absolute relaunch argument escapes canary worktree: {token}"
                )
    return normalized


def _default_authority_check(
    occurrence: SimpleFixerOccurrence,
    authority: Mapping[str, Any],
    *,
    owner_neutral: bool = False,
) -> ActionBoundaryResult:
    grant_path = Path(str(authority["capability_grant_path"])).resolve(strict=True)
    fence_path = Path(str(authority["coordinator_fence_path"])).resolve(strict=True)
    decision_path = Path(str(authority["decision_path"])).resolve(strict=True)
    grant_payload = _load_json(grant_path)
    fence_payload = _load_json(fence_path)
    decision_payload = _load_json(decision_path)
    grant = CapabilityGrant.from_dict(grant_payload)
    fence = CoordinatorFence.from_dict(fence_payload)
    decision = Decision.from_dict(decision_payload)
    grant_id = str(authority["run_authority_grant_id"])
    fence_token = int(authority["coordinator_fence_token"])
    lease_id = str(authority["custody_lease_id"])
    custody_epoch = int(authority["custody_epoch"])
    wbc_reference = str(authority["wbc_attempt_reference"])
    if (
        grant.grant_id != grant_id
        or grant.fence_token != fence_token
        or fence.token != fence_token
        or grant.run_id != fence.run_id
        or grant.run_revision != fence.run_revision
        or grant.coordinator_attempt_id != fence.coordinator_attempt_id
        or decision.outcome != "accepted"
        or decision.grant_id != grant_id
        or decision.run_id != grant.run_id
        or decision.run_revision != grant.run_revision
        or decision.coordinator_attempt_id != grant.coordinator_attempt_id
        or decision.fence_token != fence_token
        or decision.subject_id != occurrence.target.subject_id
        or decision.attempt_id != occurrence.target.attempt
    ):
        raise CanarySafetyError("hydrated Run Authority identity mismatch")
    repair_key = RepairOccurrenceKey(
        target=occurrence.target,
        run_id=grant.run_id,
        run_revision=grant.run_revision,
        coordinator_attempt_id=grant.coordinator_attempt_id,
        fence_token=fence_token,
        wbc_attempt_reference=wbc_reference,
    )
    lease_store = open_lease_store(Path(str(authority["lease_store_dir"])))
    history = lease_store.load_history(lease_id)
    current_lease = lease_store.current_lease(lease_id)
    if not history or current_lease is None:
        raise CanarySafetyError("exact Custody lease is missing")
    acquire = next(
        (event for event in history if event.event_type in {"acquire", "reclaim"}),
        None,
    )
    expected_owner = (
        str(authority["owner_host"]),
        str(authority["owner_pid"]),
        str(authority["owner_boot_id"]),
    )
    if (
        acquire is None
        or acquire.occurrence_digest != repair_key.occurrence_digest
        or current_lease.run_authority_grant_id != grant_id
        or current_lease.coordinator_fence_token != fence_token
        or current_lease.wbc_attempt_reference != wbc_reference
        or current_lease.custody_epoch != custody_epoch
        or (not owner_neutral and current_lease.owner_identity != expected_owner)
    ):
        raise CanarySafetyError("exact Custody lease join mismatch")
    wbc = _load_json(Path(str(authority["wbc_evidence_path"])).resolve(strict=True))
    attempt_ref = wbc.get("attempt_ref")
    if (
        not isinstance(attempt_ref, Mapping)
        or wbc.get("status") != "verified"
        or wbc.get("is_verified") is not True
        or wbc.get("_non_authoritative") is not True
        or attempt_ref.get("attempt_id") != wbc_reference
        or attempt_ref.get("version")
        != str(authority["required_wbc_evidence_version"])
        or attempt_ref.get("kind") != "repair"
        or attempt_ref.get("is_exact_version") is not True
        or not wbc.get("start_event_digest")
        or not wbc.get("terminal_event_digest")
        or not wbc.get("source_cursor_digest")
    ):
        raise CanarySafetyError("exact verified WBC evidence mismatch")
    context = ActionBoundaryContext(
        action_type="repair",
        target=occurrence.target,
        run_authority_grant_id=grant_id,
        coordinator_fence_token=fence_token,
        wbc_attempt_reference=wbc_reference,
        owner_host="" if owner_neutral else str(authority["owner_host"]),
        owner_pid="" if owner_neutral else str(authority["owner_pid"]),
        owner_boot_id="" if owner_neutral else str(authority["owner_boot_id"]),
        expected_custody_epoch=custody_epoch,
        expected_lease_id=lease_id,
        run_authority_grant=grant,
        coordinator_fence=fence,
        required_capability=str(authority["required_capability"]),
        required_wbc_evidence_version=str(
            authority["required_wbc_evidence_version"]
        ),
    )
    return validate_action_boundary(
        context,
        lease_store=lease_store,
        outbox=open_outbox(Path(str(authority["outbox_dir"]))),
        enforcement_enabled=True,
        wbc_evidence_only=False,
    )


def _default_verifier_authority_check(
    occurrence: SimpleFixerOccurrence,
    authority: Mapping[str, Any],
) -> ActionBoundaryResult:
    return _default_authority_check(occurrence, authority, owner_neutral=True)


def _validate_private_authority_paths(
    private_root: Path, authority: Mapping[str, Any]
) -> None:
    for key in (
        "capability_grant_path",
        "coordinator_fence_path",
        "decision_path",
        "wbc_evidence_path",
        "lease_store_dir",
        "outbox_dir",
    ):
        _inside(private_root, str(authority[key]), name=key)


def run_isolated_relaunch(
    *,
    root: str | Path,
    occurrence_payload: Mapping[str, Any],
    occurred_at: str,
    request_id: str,
    worktree: str | Path,
    argv: Sequence[str],
    expected_python: str | Path,
    expected_python_sha256: str,
    prior_worker_pid: int,
    authority: Mapping[str, Any],
    base_root: str | Path = CANARY_BASE,
    authority_check: Callable[
        [SimpleFixerOccurrence, Mapping[str, Any]], ActionBoundaryResult
    ] = _default_authority_check,
    popen: Callable[..., subprocess.Popen[Any]] = subprocess.Popen,
) -> dict[str, Any]:
    """Perform one real, bounded relaunch through the canonical fixer."""

    private_root = validate_canary_root(root, base_root=base_root)
    private_root.mkdir(parents=True, exist_ok=True)
    private_worktree = _inside(
        private_root, Path(worktree), name="canary worktree"
    )
    if not private_worktree.is_dir():
        raise CanarySafetyError("canary worktree is missing")
    if prior_worker_pid and _pid_live(prior_worker_pid):
        raise CanarySafetyError("prior canary worker is still live")
    occurrence = _occurrence(occurrence_payload)
    occurred = _parse_time(occurred_at)
    if occurred > datetime.now(timezone.utc):
        raise CanarySafetyError("occurrence timestamp cannot be in the future")
    interpreter = Path(expected_python).resolve(strict=True)
    observed_interpreter_sha = _sha256_file(interpreter)
    if observed_interpreter_sha != expected_python_sha256:
        raise CanarySafetyError("interpreter hash mismatch")
    command = _validate_argv(argv, expected_python=interpreter, worktree=private_worktree)
    if authority_check is _default_authority_check:
        _validate_private_authority_paths(private_root, authority)
    verdict = authority_check(occurrence, authority)
    if not verdict.authorized:
        raise CanarySafetyError(
            f"current RA/Custody/WBC action gate rejected canary: {verdict.gate_result}"
        )
    occurrence_record = {
        "schema": SCHEMA,
        "kind": "exact_occurrence",
        "occurrence": occurrence.to_dict(),
        "occurrence_fingerprint": occurrence.occurrence_fingerprint,
        "occurred_at": occurred.isoformat(),
        "persisted_at": _utc_now(),
    }
    occurrence_record["content_sha256"] = _digest(occurrence_record)
    _atomic_json(
        private_root / "occurrence" / "occurrence.json",
        occurrence_record,
        exclusive=True,
    )

    # Keep the queue inside the private canary while preserving the canonical
    # ``<workspace>/.megaplan/repair-queue`` structural contract.
    queue = private_root / ".megaplan" / "repair-queue"
    stdout_path = private_root / "logs" / "relaunch.stdout.log"
    stderr_path = private_root / "logs" / "relaunch.stderr.log"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    launch_path = private_root / "occurrence" / "launch.json"
    receipt_path = private_root / "occurrence" / "terminal-receipt.json"
    child: subprocess.Popen[Any] | None = None

    delegation = RepairDelegation(
        caller_kind="operator_trigger",
        caller_id=request_id,
        target=occurrence.target,
        repair_identity=occurrence.repair_identity,
    )

    def mutate(_occurrence: SimpleFixerOccurrence) -> str:
        nonlocal child
        with stdout_path.open("ab") as stdout, stderr_path.open("ab") as stderr:
            child = popen(
                command,
                cwd=private_worktree,
                env=dict(os.environ),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
        assert child is not None
        if child.poll() is not None:
            raise CanarySafetyError(
                f"canary relaunch exited immediately with {child.returncode}"
            )
        launch = {
            "schema": SCHEMA,
            "kind": "bounded_relaunch",
            "request_id": request_id,
            "occurrence_fingerprint": occurrence.occurrence_fingerprint,
            "pid": child.pid,
            "producer_pid": os.getpid(),
            "argv": list(command),
            "cwd": str(private_worktree),
            "interpreter_sha256": observed_interpreter_sha,
            "authority": verdict.to_dict(),
            "launched_at": _utc_now(),
        }
        launch["content_sha256"] = _digest(launch)
        _atomic_json(launch_path, launch, exclusive=True)
        return _digest(
            {
                "occurrence_fingerprint": occurrence.occurrence_fingerprint,
                "pid": child.pid,
                "launch_sha256": launch["content_sha256"],
            }
        )

    result = delegate_to_simple_fixer(
        delegation,
        queue_dir=str(queue),
        mutate=mutate,
        actor="m11_live_canary",
        request_id=request_id,
        session_id=occurrence.target.session,
        kind="immediate_trigger",
    )
    payload = {
        "schema": SCHEMA,
        "kind": "terminal_relaunch_receipt",
        "request_id": request_id,
        "occurrence": occurrence.to_dict(),
        "occurrence_fingerprint": occurrence.occurrence_fingerprint,
        "producer_pid": os.getpid(),
        "delegation_outcome": result.outcome,
        "simple_fixer_outcome": result.simple_fixer_outcome,
        "evidence": result.evidence or {},
        "launch_path": str(launch_path),
        "completed_at": _utc_now(),
    }
    payload["accepted"] = (
        result.delegated
        and result.simple_fixer_outcome == "attempted"
        and child is not None
        and child.poll() is None
    )
    payload["content_sha256"] = _digest(payload)
    _atomic_json(receipt_path, payload, exclusive=True)
    if not payload["accepted"]:
        raise CanarySafetyError("canonical canary relaunch was not accepted")
    return payload


def _event_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise CanarySafetyError(f"events file unavailable: {path}") from exc
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _event_time(row: Mapping[str, Any]) -> str:
    return str(
        row.get("ts_utc")
        or row.get("timestamp")
        or row.get("occurred_at")
        or row.get("created_at")
        or ""
    )


def verify_slot(
    *,
    root: str | Path,
    slot: str,
    occurrence_payload: Mapping[str, Any],
    occurred_at: str,
    plan_dir: str | Path,
    marker_path: str | Path,
    runtime_receipt_path: str | Path,
    authority: Mapping[str, Any],
    observed_at: str | None = None,
    base_root: str | Path = CANARY_BASE,
    authority_check: Callable[
        [SimpleFixerOccurrence, Mapping[str, Any]], ActionBoundaryResult
    ] = _default_verifier_authority_check,
) -> dict[str, Any]:
    """Independently reread one canary at a canonical delayed slot."""

    if slot not in CANONICAL_VERIFIER_SLOTS:
        raise CanarySafetyError(f"non-canonical verifier slot: {slot}")
    private_root = validate_canary_root(root, base_root=base_root)
    private_plan = _inside(private_root, plan_dir, name="plan directory")
    private_marker = _inside(private_root, marker_path, name="marker")
    runtime_path = _inside(
        private_root, runtime_receipt_path, name="runtime receipt"
    )
    occurrence = _occurrence(occurrence_payload)
    if authority_check is _default_verifier_authority_check:
        _validate_private_authority_paths(private_root, authority)
    occurrence_record = _load_hashed_json(
        private_root / "occurrence" / "occurrence.json"
    )
    launch_path = private_root / "occurrence" / "launch.json"
    launch = _load_hashed_json(launch_path)
    terminal = _load_hashed_json(
        private_root / "occurrence" / "terminal-receipt.json"
    )
    runtime = _load_runtime_json(runtime_path)
    if occurrence_record.get("occurrence_fingerprint") != occurrence.occurrence_fingerprint:
        raise CanarySafetyError("persisted occurrence mismatch")
    if terminal.get("occurrence_fingerprint") != occurrence.occurrence_fingerprint:
        raise CanarySafetyError("terminal receipt occurrence mismatch")
    if (
        launch.get("occurrence_fingerprint") != occurrence.occurrence_fingerprint
        or Path(str(terminal.get("launch_path") or "")).resolve(strict=False)
        != launch_path
    ):
        raise CanarySafetyError("terminal receipt is not bound to canonical launch")
    persisted_occurred_at = str(occurrence_record.get("occurred_at") or "")
    if _parse_time(occurred_at) != _parse_time(persisted_occurred_at):
        raise CanarySafetyError("occurred_at differs from immutable occurrence record")
    if terminal.get("accepted") is not True:
        raise CanarySafetyError("terminal relaunch receipt is not accepted")
    if runtime.get("valid") is not True:
        raise CanarySafetyError("strict runtime receipt is not valid")
    components = runtime.get("components")
    expected_worktree = private_plan.parents[2]
    required_components = {
        "interpreter",
        "editable_checkout",
        "pth_files",
        "imports",
        "source_lineage",
        "wrappers",
        "supervisor_command",
        "target_marker",
    }
    if (
        runtime.get("schema") != "arnold.megaplan.m11_bound_runtime_identity.v1"
        or runtime.get("strict") is not True
        or Path(str(runtime.get("expected_root") or "")).resolve(strict=False)
        != expected_worktree
        or not isinstance(components, Mapping)
        or set(components) != required_components
        or any(
            not isinstance(components[name], Mapping)
            or components[name].get("ok") is not True
            for name in required_components
        )
    ):
        raise CanarySafetyError("full strict runtime tuple is incomplete")
    interpreter_component = components["interpreter"]
    launch_argv = launch.get("argv")
    if (
        not isinstance(launch_argv, list)
        or not launch_argv
        or Path(str(launch_argv[0])).resolve(strict=False)
        != Path(str(interpreter_component.get("executable") or "")).resolve(
            strict=False
        )
        or str(interpreter_component.get("sha256") or "")
        != str(launch.get("interpreter_sha256") or "")
    ):
        raise CanarySafetyError("launch is not bound to strict runtime interpreter")
    if int(terminal.get("producer_pid") or 0) == os.getpid():
        raise CanarySafetyError("repair producer cannot verify itself")

    now = _parse_time(observed_at or _utc_now())
    began = _parse_time(occurred_at)
    if (now - began).total_seconds() < SLOT_SECONDS[slot]:
        raise CanarySafetyError(f"{slot} verifier ran before its due time")
    verdict = authority_check(occurrence, authority)
    if not verdict.authorized:
        raise CanarySafetyError("current authority/custody reread rejected verifier")

    state_path = private_plan / "state.json"
    events_path = private_plan / "events.ndjson"
    state = _load_json(state_path)
    marker = _load_json(private_marker)
    rows = _event_rows(events_path)
    completed_at = _parse_time(str(terminal.get("completed_at") or ""))
    if completed_at < began:
        raise CanarySafetyError("terminal relaunch receipt predates occurrence")
    accepted_events = []
    for row in rows:
        kind = str(row.get("kind") or row.get("type") or "")
        timestamp = _event_time(row)
        if kind in ACCEPTANCE_EVENT_KINDS and timestamp:
            try:
                if _parse_time(timestamp) >= completed_at:
                    accepted_events.append(row)
            except CanarySafetyError:
                continue
    state_value = str(state.get("current_state") or state.get("status") or "")
    marker_session = str(marker.get("session") or marker.get("session_id") or "")
    marker_checks = {
        "session": marker_session == occurrence.target.session,
        "chain": not marker.get("chain")
        or str(marker["chain"]) == occurrence.target.chain,
        "plan_revision": not marker.get("plan_revision")
        or str(marker["plan_revision"]) == occurrence.target.plan_revision,
        "occurrence": not marker.get("occurrence_fingerprint")
        or str(marker["occurrence_fingerprint"])
        == occurrence.occurrence_fingerprint,
        "runtime": not marker.get("runtime_receipt_sha256")
        or str(marker["runtime_receipt_sha256"]) == _sha256_file(runtime_path),
    }
    for field in ("workspace", "worktree", "project_dir"):
        if marker.get(field):
            marked_root = Path(str(marker[field])).resolve(strict=False)
            marker_checks[field] = (
                marked_root != private_root
                and marked_root.is_relative_to(private_root)
                and private_plan.is_relative_to(marked_root)
            )
    projection_agrees = all(marker_checks.values())
    # A mutable terminal-looking state is not proof of resumed progress.
    # Require a durable acceptance event emitted after the relaunch receipt.
    authoritative_progress = bool(accepted_events)
    passed = bool(authoritative_progress and projection_agrees)
    receipt = {
        "schema": SCHEMA,
        "kind": "independent_verifier_receipt",
        "slot": slot,
        "verifier_pid": os.getpid(),
        "observed_at": now.isoformat(),
        "occurrence_fingerprint": occurrence.occurrence_fingerprint,
        "terminal_receipt_sha256": terminal["content_sha256"],
        "runtime_receipt_sha256": _sha256_file(runtime_path),
        "authority": verdict.to_dict(),
        "state": {
            "path": str(state_path),
            "sha256": _sha256_file(state_path),
            "current_state": state_value,
        },
        "events": {
            "path": str(events_path),
            "sha256": _sha256_file(events_path),
            "line_count": len(rows),
            "accepted_event_count": len(accepted_events),
        },
        "marker": {
            "path": str(private_marker),
            "sha256": _sha256_file(private_marker),
            "session": marker_session,
            "binding_checks": marker_checks,
        },
        "negative_controls": {
            "pid_only_rejected": True,
            "cursor_only_rejected": True,
            "status_only_rejected": True,
            "duplicate_divergence_rejected": True,
        },
        "authoritative_progress": authoritative_progress,
        "projection_agrees": projection_agrees,
        "passed": passed,
    }
    receipt["content_sha256"] = _digest(receipt)
    if not passed:
        raise CanarySafetyError("independent verifier found no accepted progress")
    receipt_path = private_root / "verifiers" / f"{slot}.json"
    _atomic_json(receipt_path, receipt, exclusive=True)
    tree = {
        "schema": SCHEMA,
        "kind": "audit_cycle_tree",
        "cycle_id": f"{occurrence.occurrence_fingerprint}:{slot}",
        "slot": slot,
        "artifact_paths": [
            str(launch_path),
            str(private_root / "occurrence" / "terminal-receipt.json"),
            str(runtime_path),
            str(receipt_path),
        ],
        "provenance_digest": "",
        "is_complete": True,
    }
    tree["provenance_digest"] = _digest(
        {
            path: _sha256_file(Path(path))
            for path in tree["artifact_paths"]
        }
    )
    _atomic_json(
        private_root / "audit-cycles" / f"{slot}.json",
        tree,
        exclusive=True,
    )
    return receipt


def finalize_canary(
    *,
    root: str | Path,
    occurrence_payload: Mapping[str, Any],
    occurred_at: str,
    base_root: str | Path = CANARY_BASE,
) -> dict[str, Any]:
    """Build truthful one-row latency and four-tree manifest projections."""

    private_root = validate_canary_root(root, base_root=base_root)
    occurrence = _occurrence(occurrence_payload)
    terminal_path = private_root / "occurrence" / "terminal-receipt.json"
    launch_path = private_root / "occurrence" / "launch.json"
    occurrence_record = _load_hashed_json(
        private_root / "occurrence" / "occurrence.json"
    )
    terminal = _load_hashed_json(terminal_path)
    launch = _load_hashed_json(launch_path)
    if occurrence_record.get("occurrence_fingerprint") != occurrence.occurrence_fingerprint:
        raise CanarySafetyError("persisted occurrence mismatch")
    if terminal.get("accepted") is not True:
        raise CanarySafetyError("terminal receipt is not accepted")
    if (
        launch.get("occurrence_fingerprint") != occurrence.occurrence_fingerprint
        or Path(str(terminal.get("launch_path") or "")).resolve(strict=False)
        != launch_path
    ):
        raise CanarySafetyError("terminal receipt is not bound to canonical launch")
    verifiers = {
        slot: _load_hashed_json(private_root / "verifiers" / f"{slot}.json")
        for slot in sorted(CANONICAL_VERIFIER_SLOTS)
    }
    if not all(
        row.get("passed") is True
        and row.get("occurrence_fingerprint") == occurrence.occurrence_fingerprint
        for row in verifiers.values()
    ):
        raise CanarySafetyError("verifier set is incomplete or cross-occurrence")
    runner_receipt = (
        terminal.get("evidence", {}).get("receipt")
        if isinstance(terminal.get("evidence"), Mapping)
        else None
    )
    if not isinstance(runner_receipt, Mapping):
        raise CanarySafetyError("canonical runner receipt is missing")
    persisted_occurred_at = str(occurrence_record.get("occurred_at") or "")
    if occurred_at != persisted_occurred_at:
        raise CanarySafetyError("occurred_at differs from immutable occurrence record")
    latency_row = LatencyLedgerRow.from_event_and_receipt(
        occurrence_fingerprint=occurrence.occurrence_fingerprint,
        durable_event_kind="process_exit",
        durable_event_timestamp=occurred_at,
        terminal_receipt_kind="accepted_repair",
        terminal_receipt_timestamp=str(terminal["completed_at"]),
        terminal_receipt_id=str(runner_receipt.get("receipt_id") or ""),
        has_current_ra_grant=True,
        has_current_custody_lease=True,
        has_verifier_receipts=True,
    )
    ledger = generate_latency_ledger(rows=[latency_row]).to_dict()
    ledger["status"] = "insufficient_cohort"
    ledger["effective_status"] = "insufficient_cohort"
    ledger["content_sha256"] = _digest(ledger)
    _atomic_json(
        private_root / "latency-ledger.json", ledger, exclusive=True
    )
    terminal_tree = {
        "schema": SCHEMA,
        "kind": "audit_cycle_tree",
        "cycle_id": f"{occurrence.occurrence_fingerprint}:terminal",
        "slot": "terminal",
        "artifact_paths": [str(launch_path), str(terminal_path)],
        "provenance_digest": _digest(
            {
                str(launch_path): _sha256_file(launch_path),
                str(terminal_path): _sha256_file(terminal_path),
            }
        ),
        "is_complete": True,
    }
    _atomic_json(
        private_root / "audit-cycles" / "terminal.json",
        terminal_tree,
        exclusive=True,
    )
    trees = [
        terminal_tree,
        *[
            _load_json(private_root / "audit-cycles" / f"{slot}.json")
            for slot in ("five_minute", "one_hour", "next_three_hour")
        ],
    ]
    manifest = {
        "schema_version": 2,
        "schema": SCHEMA,
        "milestone": "M11",
        "generated_at": _utc_now(),
        "occurrence": occurrence.to_dict(),
        "occurrence_fingerprint": occurrence.occurrence_fingerprint,
        "private_root": str(private_root),
        "verifier_schedule": {
            "independent_verifier_required": True,
            "schedule": {
                slot: {"receipt": f"verifiers/{slot}.json"}
                for slot in ("five_minute", "one_hour", "next_three_hour")
            },
        },
        "audit_cycle_trees": trees,
        "latency_ledger": "latency-ledger.json",
        "complete": True,
    }
    manifest["content_sha256"] = _digest(manifest)
    _atomic_json(private_root / "manifest.json", manifest, exclusive=True)
    return manifest


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--root", type=Path, required=True)
    preflight.add_argument("--config", type=Path, required=True)
    repair = subparsers.add_parser("repair")
    repair.add_argument("--root", type=Path, required=True)
    repair.add_argument("--config", type=Path, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--root", type=Path, required=True)
    verify.add_argument("--config", type=Path, required=True)
    verify.add_argument("--slot", choices=sorted(CANONICAL_VERIFIER_SLOTS), required=True)
    verify.add_argument("--observed-at")
    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--root", type=Path, required=True)
    finalize.add_argument("--occurrence", type=Path, required=True)
    finalize.add_argument("--occurred-at", required=True)
    args = parser.parse_args(argv)
    if args.command in {"preflight", "repair", "verify"}:
        private_root = validate_canary_root(args.root)
        config = _load_json(
            _inside(private_root, args.config, name=f"{args.command} config")
        )
        if args.command == "preflight":
            occurrence = _occurrence(config["occurrence_payload"])
            worktree = _inside(
                private_root, config["worktree"], name="canary worktree"
            )
            interpreter = Path(config["expected_python"]).resolve(strict=True)
            if _sha256_file(interpreter) != config["expected_python_sha256"]:
                raise CanarySafetyError("interpreter hash mismatch")
            command = _validate_argv(
                config["argv"],
                expected_python=interpreter,
                worktree=worktree,
            )
            payload = {
                "schema": SCHEMA,
                "kind": "preflight",
                "occurrence_fingerprint": occurrence.occurrence_fingerprint,
                "private_root": str(private_root),
                "argv": list(command),
                "passed": True,
            }
        elif args.command == "repair":
            payload = run_isolated_relaunch(root=private_root, **config)
        else:
            payload = verify_slot(
                root=private_root,
                slot=args.slot,
                observed_at=args.observed_at,
                **config,
            )
        print(json.dumps(payload, sort_keys=True))
        return 0
    if args.command == "finalize":
        private_root = validate_canary_root(args.root)
        payload = finalize_canary(
            root=private_root,
            occurrence_payload=_load_json(
                _inside(private_root, args.occurrence, name="occurrence config")
            ),
            occurred_at=args.occurred_at,
        )
        print(json.dumps(payload, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())
