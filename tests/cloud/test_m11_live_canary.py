from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.m11_live_canary import (
    CanarySafetyError,
    _default_authority_check,
    finalize_canary,
    run_isolated_relaunch,
    validate_canary_root,
    verify_slot,
)
from arnold_pipelines.megaplan.custody.action_validator import GateResult


def _occurrence() -> dict[str, str]:
    return {
        "environment": "canary",
        "session": "m11-genuine-block-test",
        "chain": "canary-chain",
        "plan_revision": "abc123",
        "phase": "execute",
        "task": "T1",
        "attempt": "1",
        "normalized_failure_kind": "supervised_run_exhausted",
        "blocker_or_phase_result_hash": "sha256:blocker",
        "fence": "fence:1",
    }


class _Authorized:
    authorized = True
    gate_result = GateResult.AUTHORIZED

    def to_dict(self):
        return {"gate_result": "authorized", "checks": ["ra", "custody", "wbc"]}


def _authorized(*_args, **_kwargs):
    return _Authorized()


def _root(tmp_path: Path) -> tuple[Path, Path]:
    base = tmp_path / "m11-canaries"
    root = base / "m11-genuine-block-test"
    root.mkdir(parents=True)
    return base, root


def _command(interpreter: Path, worktree: Path, *, spec: Path | None = None) -> list[str]:
    return [
        str(interpreter),
        "-P",
        "-m",
        "arnold_pipelines.megaplan",
        "chain",
        "start",
        "--spec",
        str(spec or (worktree / "chain.yaml")),
        "--project-dir",
        str(worktree),
    ]


@pytest.fixture
def sleeping_popen():
    """Own and reap every fake child launched by the canary test."""

    children: list[subprocess.Popen] = []

    def launch(_command, **kwargs):
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"], **kwargs
        )
        children.append(child)
        return child

    yield launch

    for child in children:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)


def _write_hashed(path: Path, payload: dict) -> None:
    from arnold_pipelines.megaplan.cloud.m11_live_canary import _digest

    payload["content_sha256"] = _digest(payload)
    path.write_text(json.dumps(payload) + "\n")


def _strict_runtime_payload(worktree: Path) -> dict:
    import hashlib

    executable = Path(sys.executable).resolve()
    interpreter = {
        "ok": True,
        "executable": str(executable),
        "sha256": "sha256:" + hashlib.sha256(executable.read_bytes()).hexdigest(),
    }
    components = {
        name: {"ok": True}
        for name in (
            "editable_checkout",
            "pth_files",
            "imports",
            "source_lineage",
            "wrappers",
            "supervisor_command",
            "target_marker",
        )
    }
    components["interpreter"] = interpreter
    return {
        "schema": "arnold.megaplan.m11_bound_runtime_identity.v1",
        "valid": True,
        "strict": True,
        "expected_root": str(worktree.resolve()),
        "components": components,
    }


def _write_runtime(path: Path, worktree: Path) -> None:
    import hashlib

    payload = _strict_runtime_payload(worktree)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["content_sha256"] = hashlib.sha256(encoded).hexdigest()
    path.write_text(json.dumps(payload) + "\n")


def test_private_root_rejects_global_and_nested_paths(tmp_path: Path) -> None:
    base, root = _root(tmp_path)
    assert validate_canary_root(root, base_root=base) == root.resolve()
    with pytest.raises(CanarySafetyError):
        validate_canary_root(base, base_root=base)
    with pytest.raises(CanarySafetyError):
        validate_canary_root(root / "nested", base_root=base)
    with pytest.raises(CanarySafetyError):
        validate_canary_root(tmp_path / "other", base_root=base)


def test_current_source_rejects_nonaccepted_decision_outcome() -> None:
    from types import SimpleNamespace

    from arnold_pipelines.run_authority.contracts import Decision
    from arnold_pipelines.run_authority.current_source import (
        CurrentSourceRequest,
        _accepted_decision,
    )

    request = CurrentSourceRequest(
        "run",
        "revision",
        "coordinator",
        "grant",
        7,
        "attempt",
        "decision",
    )
    base = dict(
        decision_id="decision",
        run_id="run",
        run_revision="revision",
        subject_id="subject",
        attempt_id="attempt",
        grant_id="grant",
        coordinator_attempt_id="coordinator",
        fence_token=7,
        claim_id="claim",
        evidence_ids=("evidence",),
        idempotency_key="decision-key",
        payload={},
    )
    rejected = Decision(outcome="rejected", **base)
    accepted = Decision(outcome="accepted", **base)
    assert _accepted_decision(SimpleNamespace(decisions=(rejected,)), request) is None
    assert _accepted_decision(SimpleNamespace(decisions=(accepted,)), request) == accepted


def test_default_gate_hydrates_real_grant_fence_lease_and_wbc(
    tmp_path: Path,
) -> None:
    from arnold_pipelines.megaplan.cloud.simple_fixer import (
        build_simple_fixer_occurrence,
    )
    from arnold_pipelines.megaplan.custody.lease_store import open_lease_store
    from arnold_pipelines.megaplan.custody.contracts import RepairOccurrenceKey
    from arnold_pipelines.megaplan.custody.outbox import (
        OutboxRecord,
        OutboxRecordStatus,
        OutboxRecordType,
        open_outbox,
    )
    from arnold_pipelines.run_authority import (
        CapabilityGrant,
        CoordinatorFence,
        Decision,
    )
    from arnold_pipelines.megaplan.wbc_adapter import (
        WbcAttemptRef,
        WbcBoundaryEvidence,
    )

    occurrence = build_simple_fixer_occurrence(_occurrence())
    assert occurrence is not None
    grant = CapabilityGrant(
        grant_id="grant-canary",
        run_id="run-canary",
        run_revision="rev-canary",
        coordinator_attempt_id="coord-canary",
        fence_token=7,
        subject_ids=(occurrence.target.subject_id,),
        capabilities=("repair",),
        evidence_ids=("evidence-canary",),
    )
    fence = CoordinatorFence("run-canary", "rev-canary", "coord-canary", 7)
    grant_path = tmp_path / "grant.json"
    fence_path = tmp_path / "fence.json"
    decision_path = tmp_path / "decision.json"
    grant_path.write_text(json.dumps(grant.to_dict()))
    fence_path.write_text(json.dumps(fence.to_dict()))
    decision_path.write_text(
        json.dumps(
            Decision(
                decision_id="decision-canary",
                run_id=grant.run_id,
                run_revision=grant.run_revision,
                subject_id=occurrence.target.subject_id,
                attempt_id=occurrence.target.attempt,
                grant_id=grant.grant_id,
                coordinator_attempt_id=grant.coordinator_attempt_id,
                fence_token=fence.token,
                claim_id="claim-canary",
                outcome="accepted",
                evidence_ids=("evidence-canary",),
                idempotency_key="decision-canary",
                payload={},
            ).to_dict()
        )
    )
    lease_dir = tmp_path / "leases"
    outbox_dir = tmp_path / "outbox"
    lease_id = "lease-canary"
    attempt = "wbc-canary"
    repair_key = RepairOccurrenceKey(
        target=occurrence.target,
        run_id=grant.run_id,
        run_revision=grant.run_revision,
        coordinator_attempt_id=grant.coordinator_attempt_id,
        fence_token=fence.token,
        wbc_attempt_reference=attempt,
    )
    open_lease_store(lease_dir).acquire(
        lease_id=lease_id,
        owner_host="host-canary",
        owner_pid="123",
        owner_boot_id="boot-canary",
        run_authority_grant_id=grant.grant_id,
        coordinator_fence_token=fence.token,
        wbc_attempt_reference=attempt,
        occurrence_digest=repair_key.occurrence_digest,
        custody_epoch=3,
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    )
    open_outbox(outbox_dir).write_record(
        OutboxRecord(
            outbox_id="outbox-canary",
            lease_id=lease_id,
            record_type=OutboxRecordType.CROSS_OWNER_ATTEMPT,
            status=OutboxRecordStatus.PENDING,
            occurred_at=datetime.now(timezone.utc).isoformat(),
            idempotency_key="outbox-canary",
            wbc_attempt_reference=attempt,
            run_authority_grant_id=grant.grant_id,
            coordinator_fence_token=fence.token,
            occurrence_digest=repair_key.occurrence_digest,
            custody_epoch=3,
            payload={"schema_version": "wbc-v1"},
        )
    )
    wbc_path = tmp_path / "wbc.json"
    wbc_path.write_text(
        json.dumps(
            WbcBoundaryEvidence.verified(
                WbcAttemptRef.exact(attempt, "wbc-v1", kind="repair"),
                start_event_digest="sha256:start",
                terminal_event_digest="sha256:terminal",
                last_sequence=2,
                source_cursor_digest="sha256:cursor",
            ).to_dict()
        )
    )
    authority = {
        "capability_grant_path": str(grant_path),
        "coordinator_fence_path": str(fence_path),
        "decision_path": str(decision_path),
        "run_authority_grant_id": grant.grant_id,
        "coordinator_fence_token": fence.token,
        "custody_lease_id": lease_id,
        "custody_epoch": 3,
        "wbc_attempt_reference": attempt,
        "owner_host": "host-canary",
        "owner_pid": "123",
        "owner_boot_id": "boot-canary",
        "required_capability": "repair",
        "required_wbc_evidence_version": "wbc-v1",
        "wbc_evidence_path": str(wbc_path),
        "lease_store_dir": str(lease_dir),
        "outbox_dir": str(outbox_dir),
    }
    assert _default_authority_check(occurrence, authority).authorized
    assert _default_authority_check(
        occurrence, {**authority, "owner_pid": "different"}, owner_neutral=True
    ).authorized
    with pytest.raises(CanarySafetyError, match="identity mismatch"):
        _default_authority_check(
            occurrence, {**authority, "coordinator_fence_token": 8}
        )


def test_real_relaunch_persists_exact_receipt_and_private_artifacts(
    tmp_path: Path,
    sleeping_popen,
) -> None:
    base, root = _root(tmp_path)
    worktree = root / "worktree"
    worktree.mkdir()
    interpreter = Path(sys.executable).resolve()
    import hashlib

    digest = hashlib.sha256(interpreter.read_bytes()).hexdigest()
    receipt = run_isolated_relaunch(
        root=root,
        occurrence_payload=_occurrence(),
        occurred_at=datetime.now(timezone.utc).isoformat(),
        request_id="request-1",
        worktree=worktree,
        argv=_command(interpreter, worktree),
        expected_python=interpreter,
        expected_python_sha256=f"sha256:{digest}",
        prior_worker_pid=99999999,
        authority={},
        base_root=base,
        authority_check=_authorized,
        popen=sleeping_popen,
    )
    launch = json.loads((root / "occurrence" / "launch.json").read_text())
    assert receipt["accepted"] is True
    assert receipt["simple_fixer_outcome"] == "attempted"
    assert launch["argv"][1] == "-P"
    assert Path(launch["cwd"]) == worktree
    occurrence_record = json.loads(
        (root / "occurrence" / "occurrence.json").read_text()
    )
    persisted_hash = occurrence_record.pop("content_sha256")
    from arnold_pipelines.megaplan.cloud.m11_live_canary import _digest

    assert persisted_hash == _digest(occurrence_record)
    assert (root / "occurrence" / "terminal-receipt.json").is_file()
    assert (root / ".megaplan" / "repair-queue").is_dir()


def test_relaunch_rejects_non_safe_path_and_escape(tmp_path: Path) -> None:
    base, root = _root(tmp_path)
    worktree = root / "worktree"
    worktree.mkdir()
    interpreter = Path(sys.executable).resolve()
    import hashlib

    digest = "sha256:" + hashlib.sha256(interpreter.read_bytes()).hexdigest()
    kwargs = dict(
        root=root,
        occurrence_payload=_occurrence(),
        occurred_at=datetime.now(timezone.utc).isoformat(),
        request_id="request-1",
        worktree=worktree,
        expected_python=interpreter,
        expected_python_sha256=digest,
        prior_worker_pid=99999999,
        authority={},
        base_root=base,
        authority_check=_authorized,
    )
    with pytest.raises(CanarySafetyError, match="safe-path"):
        run_isolated_relaunch(
            argv=[
                str(interpreter),
                "-m",
                "arnold_pipelines.megaplan",
                "chain",
                "start",
                "--spec",
                str(worktree / "chain.yaml"),
                "--project-dir",
                str(worktree),
            ],
            **kwargs,
        )
    with pytest.raises(CanarySafetyError, match="inside"):
        run_isolated_relaunch(
            argv=_command(interpreter, worktree, spec=tmp_path / "outside.py"),
            **kwargs,
        )
    with pytest.raises(CanarySafetyError, match="canonical"):
        run_isolated_relaunch(
            argv=[str(interpreter), "-P", "-c", "print('not a chain')"],
            **kwargs,
        )


def test_no_real_relaunch_callback_means_no_success(tmp_path: Path) -> None:
    base, root = _root(tmp_path)
    worktree = root / "worktree"
    worktree.mkdir()
    interpreter = Path(sys.executable).resolve()
    import hashlib

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("relaunch unavailable")

    with pytest.raises(CanarySafetyError, match="was not accepted"):
        run_isolated_relaunch(
            root=root,
            occurrence_payload=_occurrence(),
            occurred_at=datetime.now(timezone.utc).isoformat(),
            request_id="request-no-relaunch",
            worktree=worktree,
            argv=_command(interpreter, worktree),
            expected_python=interpreter,
            expected_python_sha256=(
                "sha256:" + hashlib.sha256(interpreter.read_bytes()).hexdigest()
            ),
            prior_worker_pid=99999999,
            authority={},
            base_root=base,
            authority_check=_authorized,
            popen=unavailable,
        )
    terminal = json.loads(
        (root / "occurrence" / "terminal-receipt.json").read_text()
    )
    assert terminal["accepted"] is False


def test_verifiers_and_finalize_emit_truthful_one_row_evidence(
    tmp_path: Path,
) -> None:
    base, root = _root(tmp_path)
    plan = root / "worktree" / ".megaplan" / "plans" / "canary"
    plan.mkdir(parents=True)
    marker = root / "markers" / "m11-genuine-block-test.json"
    marker.parent.mkdir()
    marker.write_text(
        json.dumps({"session": "m11-genuine-block-test"}) + "\n"
    )
    occurred = datetime.now(timezone.utc) - timedelta(hours=4)
    accepted = occurred + timedelta(minutes=2)
    (plan / "state.json").write_text(json.dumps({"current_state": "done"}))
    (plan / "events.ndjson").write_text("")
    runtime = root / "runtime" / "strict-tuple.json"
    runtime.parent.mkdir()
    _write_runtime(runtime, root / "worktree")
    occurrence = _occurrence()
    # Verifier must be independent of this synthetic terminal producer.
    terminal = {
        "accepted": True,
        "producer_pid": os.getpid() + 100000,
        "occurrence_fingerprint": "",
        "completed_at": accepted.isoformat(),
        "launch_path": str(root / "occurrence" / "launch.json"),
        "evidence": {
            "receipt": {
                "receipt_id": "sha256:runner",
                "emitted_at": accepted.isoformat(),
            }
        },
    }
    from arnold_pipelines.megaplan.cloud.simple_fixer import (
        build_simple_fixer_occurrence,
    )

    fp = build_simple_fixer_occurrence(occurrence).occurrence_fingerprint
    terminal["occurrence_fingerprint"] = fp
    from arnold_pipelines.megaplan.cloud.m11_live_canary import _digest

    terminal["content_sha256"] = _digest(terminal)
    terminal_path = root / "occurrence" / "terminal-receipt.json"
    terminal_path.parent.mkdir()
    terminal_path.write_text(json.dumps(terminal) + "\n")
    _write_hashed(
        root / "occurrence" / "launch.json",
        {
            "occurrence_fingerprint": fp,
            "cwd": str(root / "worktree"),
            "argv": [str(Path(sys.executable).resolve())],
            "interpreter_sha256": _strict_runtime_payload(root / "worktree")["components"][
                "interpreter"
            ]["sha256"],
        },
    )
    occurrence_record = {
        "schema": "arnold.megaplan.m11_live_canary.v1",
        "kind": "exact_occurrence",
        "occurrence": build_simple_fixer_occurrence(occurrence).to_dict(),
        "occurrence_fingerprint": fp,
        "occurred_at": occurred.isoformat(),
        "persisted_at": occurred.isoformat(),
    }
    occurrence_record["content_sha256"] = _digest(occurrence_record)
    (root / "occurrence" / "occurrence.json").write_text(
        json.dumps(occurrence_record) + "\n"
    )

    common_verify = dict(
        root=root,
        occurrence_payload=occurrence,
        occurred_at=occurred.isoformat(),
        plan_dir=plan,
        marker_path=marker,
        runtime_receipt_path=runtime,
        authority={},
        observed_at=datetime.now(timezone.utc).isoformat(),
        base_root=base,
        authority_check=_authorized,
    )
    with pytest.raises(CanarySafetyError, match="no accepted progress"):
        verify_slot(slot="five_minute", **common_verify)

    (plan / "state.json").write_text(json.dumps({"current_state": "executing"}))
    (plan / "events.ndjson").write_text(
        json.dumps(
            {"kind": "task_accepted", "ts_utc": accepted.isoformat()}
        )
        + "\n"
    )
    for slot in ("five_minute", "one_hour", "next_three_hour"):
        receipt = verify_slot(slot=slot, **common_verify)
        assert receipt["passed"] is True
        assert receipt["authoritative_progress"] is True

    manifest = finalize_canary(
        root=root,
        occurrence_payload=occurrence,
        occurred_at=occurred.isoformat(),
        base_root=base,
    )
    ledger = json.loads((root / "latency-ledger.json").read_text())
    assert manifest["complete"] is True
    assert len(manifest["audit_cycle_trees"]) == 4
    assert set(manifest["verifier_schedule"]["schedule"]) == {
        "five_minute",
        "one_hour",
        "next_three_hour",
    }
    assert ledger["sample_count"] == 1
    assert len(ledger["latency_ledger_rows"]) == 1
    assert ledger["slo_met"] is False
    assert ledger["status"] == "insufficient_cohort"
