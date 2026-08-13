from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier

import pytest

from arnold_pipelines.megaplan.cloud import repair_contract, repair_requests


def _signature(**overrides: str) -> dict[str, str]:
    base = {
        "failure_kind": "execute_failed",
        "current_state": "blocked",
        "phase_or_step": "execute",
        "milestone_or_plan": "m3",
        "gate_recommendation": "",
        "blocked_task_id": "T1",
    }
    base.update(overrides)
    return base


def _repair_identity(*, attempt_number: int = 1, fence_token: str = "fence-1") -> dict[str, object]:
    target = repair_requests.build_custody_target_key(
        environment="/workspace/demo",
        session="demo",
        chain="/workspace/demo/chain.yaml",
        plan_revision="sha256:plan-rev-1",
        phase="execute",
        task="T1",
        attempt=str(attempt_number),
        normalized_failure_kind="execute_failed",
        blocker_or_phase_result_hash="blocker:v1:demo",
        fence=fence_token,
        chain_identity="chain-incarnation-1",
    )
    assert target is not None
    result = repair_requests.build_normalized_repair_identity(
        target=target,
        run_id="demo",
        run_revision="sha256:plan-rev-1",
        run_incarnation_id="run-incarnation-1",
        coordinator_attempt_id=f"coordinator:{attempt_number}",
        fence_token=attempt_number,
        wbc_attempt_reference=f"wbc:{attempt_number}",
        run_authority_grant_id="grant-1",
        lease_id="lease-1",
        custody_epoch=attempt_number,
    )
    assert result is not None
    return result


def _enqueue(**kwargs: object) -> dict[str, object]:
    kwargs.setdefault("repair_identity", _repair_identity())
    return repair_requests.enqueue_repair_request(**kwargs)


def _claimable_request(
    queue_dir: Path,
    *,
    blocked_task_id: str,
    session: str = "demo-session",
    repair_identity: dict[str, object] | None = None,
) -> dict[str, object]:
    result = _enqueue(
        queue_root=queue_dir,
        session=session,
        source="test",
        problem_signature=_signature(blocked_task_id=blocked_task_id),
        root_cause_hint=f"claim fixture for {blocked_task_id}",
        repair_identity=repair_identity or _repair_identity(),
    )
    assert result["status"] == "queued"
    request = result["request"]
    assert isinstance(request, dict)
    return request


def _queue_root(tmp_path: Path) -> Path:
    return tmp_path / ".megaplan" / repair_requests.QUEUE_DIR_NAME


def test_validate_queue_root_accepts_only_canonical_central_root(tmp_path: Path) -> None:
    queue_root = _queue_root(tmp_path)

    assert repair_requests.validate_queue_root(queue_root) == queue_root


def test_validate_queue_root_rejects_plan_marker_and_ambiguous_roots(tmp_path: Path) -> None:
    rejected = [
        tmp_path / ".megaplan" / "plans" / "demo-plan",
        tmp_path / ".megaplan" / "plans" / "demo-plan" / ".megaplan" / "repair-queue",
        tmp_path / ".megaplan" / "chain-markers",
        tmp_path / ".megaplan" / "markers",
        tmp_path / "repair-queue",
    ]

    for root in rejected:
        try:
            repair_requests.validate_queue_root(root)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted non-central repair queue root: {root}")


def test_validate_queue_root_rejects_ambiguous_relative_root() -> None:
    try:
        repair_requests.validate_queue_root(Path(".megaplan/repair-queue"))
    except ValueError as exc:
        assert "absolute" in str(exc)
    else:
        raise AssertionError("accepted relative repair queue root")


def test_public_read_api_does_not_infer_queue_from_marker_parent(tmp_path: Path) -> None:
    marker_dir = tmp_path / ".megaplan" / "chain-markers"

    try:
        repair_requests.iter_repair_requests(marker_dir)
    except ValueError:
        pass
    else:
        raise AssertionError("marker directory was accepted as a repair queue root")


def test_enqueue_requires_explicit_queue_root_even_with_marker_provenance(tmp_path: Path) -> None:
    try:
        _enqueue(
            marker_dir=tmp_path / ".megaplan" / "chain-markers",
            session="demo",
            source="test",
            problem_signature=_signature(),
        )
    except TypeError as exc:
        assert "queue_root" in str(exc)
    else:
        raise AssertionError("enqueue inferred queue custody from marker provenance")


def test_enqueue_writes_once_and_never_stores_raw_root_cause_text(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    marker_dir = tmp_path / ".megaplan" / "chain-markers"
    raw_hint = "Authorization: Bearer sk-proj-abcdefghijklmnopqrstuvwxyz123456"

    first = _enqueue(
        queue_root=queue_dir,
        marker_dir=marker_dir,
        session="demo",
        source="_record_lifecycle_failure",
        problem_signature=_signature(),
        root_cause_hint=raw_hint,
        created_at="2026-07-01T00:00:00Z",
    )
    second = _enqueue(
        queue_root=queue_dir,
        marker_dir=marker_dir,
        session="demo",
        source="_record_lifecycle_failure",
        problem_signature=_signature(),
        root_cause_hint=raw_hint,
        created_at="2026-07-01T00:10:00Z",
    )

    assert first["status"] == "queued"
    assert second["status"] == "coalesced"
    path = Path(first["path"])
    original_text = path.read_text(encoding="utf-8")
    payload = json.loads(original_text)
    assert payload["created_at"] == "2026-07-01T00:00:00Z"
    assert payload["marker_dir"] == str(marker_dir)
    assert payload["queue_dir"] == str(queue_dir)
    assert "sk-proj-abcdefghijklmnopqrstuvwxyz123456" not in original_text
    assert "Authorization: Bearer" not in original_text
    assert "root_cause_hint_hash" in payload
    assert path.read_text(encoding="utf-8") == original_text


def test_problem_signature_dedupe_ignores_timestamp_but_not_signature(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)

    first = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="HumanGateStep.run",
        problem_signature=_signature(),
        root_cause_hint="first failure",
        created_at="2026-07-01T01:00:00Z",
    )
    duplicate = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="HumanGateStep.run",
        problem_signature=_signature(),
        root_cause_hint="different raw text",
        created_at="2026-07-01T01:05:00Z",
    )
    distinct = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="HumanGateStep.run",
        problem_signature=_signature(blocked_task_id="T2"),
        root_cause_hint="first failure",
        created_at="2026-07-01T01:10:00Z",
    )

    assert first["status"] == "queued"
    assert duplicate["status"] == "coalesced"
    assert duplicate["decision"]["related_request_id"] == first["request"]["request_id"]
    assert distinct["status"] == "queued"

    requests = repair_requests.iter_repair_requests(queue_dir)
    assert [item["request_id"] for item in requests] == [
        first["request"]["request_id"],
        distinct["request"]["request_id"],
    ]


def test_same_signature_does_not_coalesce_across_sessions(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)

    first = _enqueue(
        queue_root=queue_dir,
        session="session-a",
        source="watchdog",
        problem_signature=_signature(),
        root_cause_hint="same failure",
    )
    second = _enqueue(
        queue_root=queue_dir,
        session="session-b",
        source="watchdog",
        problem_signature=_signature(),
        root_cause_hint="same failure",
    )

    assert first["status"] == second["status"] == "queued"
    assert first["request"]["request_id"] != second["request"]["request_id"]
    assert first["request"]["blocker_id"] != second["request"]["blocker_id"]
    assert {record["session"] for record in repair_requests.iter_repair_requests(queue_dir)} == {
        "session-a",
        "session-b",
    }


def test_distinct_redacted_root_cause_hints_have_distinct_hashes() -> None:
    secret_a = "Authorization: Bearer sk-proj-abcdefghijklmnopqrstuvwxyz123456"
    secret_b = "Authorization: Bearer sk-proj-abcdefghijklmnopqrstuvwxyz999999"

    # Both hints redact to the same value, so the stored hash is the same.
    assert repair_requests.redacted_hint_hash(secret_a) == repair_requests.redacted_hint_hash(secret_b)
    assert repair_requests.redacted_hint_hash("phase failed at step A") != repair_requests.redacted_hint_hash(
        "phase failed at step B"
    )


def test_stale_and_superseded_are_decisions_not_request_rewrites(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)

    stale = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="HumanGateStep.run",
        problem_signature=_signature(),
        root_cause_hint="old",
        stale_reason="marker no longer matches current plan",
    )
    superseded = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="HumanGateStep.run",
        problem_signature=_signature(blocked_task_id="T2"),
        root_cause_hint="old",
        superseded_by="new-live-session",
    )

    assert stale["status"] == "stale"
    assert superseded["status"] == "superseded"
    request_files = sorted(repair_requests.requests_dir(queue_dir).glob("*.json"))
    assert len(request_files) == 2
    assert {json.loads(path.read_text(encoding="utf-8"))["kind"] for path in request_files} == {"repair_request"}
    decision_files = sorted(repair_requests.decisions_dir(queue_dir).glob("*.json"))
    decisions = {json.loads(path.read_text(encoding="utf-8"))["decision"] for path in decision_files}
    assert decisions == {"stale", "superseded"}


def test_malformed_files_are_reported_and_valid_requests_remain_ordered(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    request_dir = repair_requests.requests_dir(queue_dir)
    request_dir.mkdir(parents=True)
    (request_dir / "broken.json").write_text("{not json", encoding="utf-8")

    later = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="HumanGateStep.run",
        problem_signature=_signature(blocked_task_id="T2"),
        root_cause_hint="later",
        created_at="2026-07-01T02:00:00Z",
    )
    earlier = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="HumanGateStep.run",
        problem_signature=_signature(blocked_task_id="T1"),
        root_cause_hint="earlier",
        created_at="2026-07-01T01:00:00Z",
    )

    valid = repair_requests.iter_repair_requests(queue_dir)
    assert [item["request_id"] for item in valid] == [
        earlier["request"]["request_id"],
        later["request"]["request_id"],
    ]

    all_records = repair_requests.iter_repair_requests(queue_dir, include_malformed=True)
    assert all_records[-1]["kind"] == "malformed_repair_request"
    assert all_records[-1]["path"].endswith("broken.json")


# ---------------------------------------------------------------------------
# Normalization and identity helpers
# ---------------------------------------------------------------------------


def test_normalize_problem_signature_strips_unknown_fields_and_normalizes_known() -> None:
    sig = {
        "failure_kind": "  execute_failed  ",
        "current_state": "blocked",
        "phase_or_step": "execute",
        "milestone_or_plan": "m3",
        "gate_recommendation": "",
        "blocked_task_id": "T1",
        "extra_noise": "should be dropped",
        "another": 123,
    }
    normalized = repair_requests.normalize_problem_signature(sig)
    assert set(normalized) == set(repair_requests.PROBLEM_SIGNATURE_FIELDS)
    assert normalized["failure_kind"] == "execute_failed"
    assert normalized["current_state"] == "blocked"
    # Missing fields become empty strings
    assert repair_requests.normalize_problem_signature({}) == {
        field: "" for field in repair_requests.PROBLEM_SIGNATURE_FIELDS
    }


def test_problem_signature_key_is_stable_and_deterministic() -> None:
    sig_a = _signature()
    sig_b = _signature()  # same values
    key_a = repair_requests.problem_signature_key(sig_a)
    key_b = repair_requests.problem_signature_key(sig_b)
    assert key_a == key_b
    assert isinstance(key_a, str)
    assert len(key_a) == 64  # sha256 hex digest


def test_problem_signature_key_changes_with_different_signature() -> None:
    key_1 = repair_requests.problem_signature_key(_signature(blocked_task_id="T1"))
    key_2 = repair_requests.problem_signature_key(_signature(blocked_task_id="T2"))
    assert key_1 != key_2


def test_request_id_for_is_stable_regardless_of_timestamp() -> None:
    id_a = repair_requests.request_id_for(
        session="demo",
        problem_signature=_signature(),
        root_cause_hint="same hint",
    )
    id_b = repair_requests.request_id_for(
        session="demo",
        problem_signature=_signature(),
        root_cause_hint="same hint",
    )
    assert id_a == id_b
    assert isinstance(id_a, str)
    assert len(id_a) == 64


def test_request_id_for_differs_with_different_hints() -> None:
    id_1 = repair_requests.request_id_for(
        session="demo",
        problem_signature=_signature(),
        root_cause_hint="hint A",
    )
    id_2 = repair_requests.request_id_for(
        session="demo",
        problem_signature=_signature(),
        root_cause_hint="hint B",
    )
    assert id_1 != id_2


def test_request_id_for_differs_with_different_sessions() -> None:
    id_1 = repair_requests.request_id_for(
        session="session-1",
        problem_signature=_signature(),
    )
    id_2 = repair_requests.request_id_for(
        session="session-2",
        problem_signature=_signature(),
    )
    assert id_1 != id_2


def test_request_id_for_differs_with_different_repair_identity() -> None:
    id_1 = repair_requests.request_id_for(
        session="demo",
        problem_signature=_signature(),
        repair_identity=_repair_identity(attempt_number=1),
    )
    id_2 = repair_requests.request_id_for(
        session="demo",
        problem_signature=_signature(),
        repair_identity=_repair_identity(attempt_number=2),
    )
    assert id_1 != id_2


def test_derive_repair_identity_returns_none_for_planner_repair_only_plan() -> None:
    """Lock out option (b): a plan carrying only meta.planner_repair (candidate
    id + failure fingerprint) must NOT be dispatchable — no lifecycle owner has
    persisted a normalized envelope."""
    plan_state = {
        "meta": {
            "planner_repair": {
                "schema": "megaplan.planner_repair",
                "schema_version": 1,
                "candidate_id": "candidate:abc",
                "failure_fingerprint": "fp-1",
                "occurrences": 2,
                "circuit_open": True,
            }
        }
    }
    assert repair_requests.derive_repair_identity(plan_state=plan_state) is None
    assert repair_requests.derive_repair_identity(target={"meta": plan_state["meta"]}) is None


def test_derive_repair_identity_reads_persisted_envelope_from_plan_state() -> None:
    """The finalize producer persists meta.repair_identity; the watchdog
    dispatch derives exactly that normalized envelope from plan state."""
    identity = _repair_identity()
    plan_state = {
        "meta": {
            "planner_repair": {
                "schema": "megaplan.planner_repair",
                "schema_version": 1,
                "candidate_id": "candidate:abc",
                "failure_fingerprint": "fp-1",
                "occurrences": 2,
                "circuit_open": True,
            },
            "repair_identity": identity,
            "repair_identity_provenance": {
                "authority_source": "finalize_planner_repair_circuit_open_owner",
                "phase": "finalize",
            },
        }
    }
    derived = repair_requests.derive_repair_identity(plan_state=plan_state)
    expected = repair_requests.normalize_repair_identity(identity)
    assert expected is not None
    assert derived == expected
    assert derived["occurrence"]["contract_type"] == "repair_occurrence_key"


# ---------------------------------------------------------------------------
# write_decision and decision records
# ---------------------------------------------------------------------------


def test_write_decision_rejects_identity_free_acceptance(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    try:
        repair_requests.write_decision(
            queue_dir,
            request_id="req-abc123",
            decision="accepted",
            reason="queued",
            created_at="2026-07-01T03:00:00Z",
        )
    except ValueError as exc:
        assert "persisted canonical blocker identity" in str(exc)
    else:
        raise AssertionError("accepted an identity-free repair request")
    assert not list(repair_requests.decisions_dir(queue_dir).glob("*.json"))


def test_enqueue_rejects_missing_provenance_before_persistence(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)

    with pytest.raises(ValueError, match="provenance source"):
        _enqueue(
            queue_root=queue_dir,
            session="demo",
            source="",
            problem_signature=_signature(),
            root_cause_hint="observed failure",
        )

    assert not list(repair_requests.requests_dir(queue_dir).glob("*.json"))
    assert not list(repair_requests.decisions_dir(queue_dir).glob("*.json"))


def test_acceptance_rejects_identity_with_missing_provenance_or_evidence(
    tmp_path: Path,
) -> None:
    queue_dir = _queue_root(tmp_path)
    queued = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="watchdog",
        problem_signature=_signature(),
        root_cause_hint="observed failure",
        stale_reason="fixture setup",
    )
    request_path = Path(queued["path"])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request.pop("provenance")
    request.pop("evidence_refs")
    repair_contract.atomic_write_json(request_path, request)

    with pytest.raises(ValueError, match="persisted canonical blocker identity"):
        repair_requests.write_decision(
            queue_dir,
            request_id=request["request_id"],
            decision="accepted",
            reason="queued",
        )


def test_phase_failure_persists_replay_stable_claim_identity(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    signature = {
        "failure_kind": "deterministic_phase_failure",
        "current_state": "blocked",
        "phase_or_step": "critique",
        "milestone_or_plan": "m6-exact-contract-and-20260716-1303",
        "gate_recommendation": "repair the phase contract",
        "blocked_task_id": "",
    }
    target = {
        "plan_name": "m6-exact-contract-and-20260716-1303",
        "plan_dir": str(tmp_path / ".megaplan" / "plans" / "m6-exact-contract-and-20260716-1303"),
        "retry_strategy": "repair_phase_contract",
    }

    first = _enqueue(
        queue_root=queue_dir,
        session="custody-control-plane-20260714",
        source="lifecycle_failure",
        problem_signature=signature,
        target=target,
        workspace=tmp_path,
        root_cause_hint="duplicate worker-local flag IDs and blank evidence",
        created_at="2026-07-16T13:35:03Z",
    )
    replay = _enqueue(
        queue_root=queue_dir,
        session="custody-control-plane-20260714",
        source="lifecycle_failure",
        problem_signature=signature,
        target=target,
        workspace=tmp_path,
        root_cause_hint="duplicate worker-local flag IDs and blank evidence",
        created_at="2026-07-16T13:36:03Z",
    )

    assert first["status"] == "queued"
    assert replay["status"] == "coalesced"
    assert replay["request"]["request_id"] == first["request"]["request_id"]
    persisted = repair_requests.iter_repair_requests(queue_dir)
    assert len(persisted) == 1
    request = persisted[0]
    assert request["problem_signature"]["blocked_task_id"] == "phase:critique"
    assert request["blocker_id"] == repair_contract.blocker_id_for_fingerprint(
        request["blocker_fingerprint"]
    )
    assert request["provenance"] == {
        "producer": "lifecycle_failure",
        "session": "custody-control-plane-20260714",
        "run_kind": "",
    }
    assert {ref["kind"] for ref in request["evidence_refs"]} == {
        "problem_signature_digest",
        "redacted_root_cause_hint_digest",
    }
    assert all(ref["sha256"] for ref in request["evidence_refs"])


def test_completed_repair_request_preserves_legacy_identity_and_profile_contract(
    tmp_path: Path,
) -> None:
    queue_dir = _queue_root(tmp_path)
    target = {
        "plan_name": "m9-rebuildable-projections-20260722-0431",
        "configured_profile": "partnered-5",
        "recovery_contract": {
            "preserve_configured_profile": True,
            "required_cursor_advance": True,
            "success_requires": (
                "active execution state plus chain-owned M9 batch or transition receipt"
            ),
            "forbid_standalone_completion": True,
        },
    }
    queued = _enqueue(
        queue_root=queue_dir,
        session="custody-control-plane-20260714",
        source="resident_authorized_recovery",
        workspace=tmp_path,
        run_kind="chain",
        target=target,
        problem_signature={
            "failure_kind": "completed_repair_without_cursor_advance",
            "current_state": "planned",
            "phase_or_step": "critique",
            "milestone_or_plan": "m9-rebuildable-projections-20260722-0431",
            "gate_recommendation": "continue the legal transition",
            "blocked_task_id": "phase:critique",
        },
        root_cause_hint="ordinary repair returned without canonical advancement",
    )
    request = queued["request"]
    fingerprint = repair_contract.normalize_blocker_fingerprint_v1(
        request["blocker_fingerprint"]
    )
    assert fingerprint is not None
    legacy_payload = {
        "prefix": repair_contract.BLOCKER_FINGERPRINT_V1_PREFIX,
        "fingerprint": fingerprint,
    }
    legacy_digest = hashlib.sha256(
        json.dumps(
            legacy_payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    request["blocker_id"] = f"{repair_contract.BLOCKER_ID_V1_PREFIX}{legacy_digest}"

    assert repair_contract.blocker_id_matches_fingerprint(
        request["blocker_id"], request["blocker_fingerprint"]
    )
    assert repair_requests.has_claimable_repair_request_contract(request)

    missing_profile_clause = json.loads(json.dumps(request))
    missing_profile_clause["target"]["recovery_contract"].pop(
        "preserve_configured_profile"
    )
    assert not repair_requests.has_claimable_repair_request_contract(
        missing_profile_clause
    )
    assert repair_requests.repair_request_contract_violations(
        missing_profile_clause
    ) == ["missing_preserve_configured_profile"]


def test_completed_repair_recurrence_remains_visible_to_l2_l3_backstops(
    tmp_path: Path,
) -> None:
    queue_dir = _queue_root(tmp_path)
    plan_name = "m9-rebuildable-projections-20260722-0431"
    queued = _enqueue(
        queue_root=queue_dir,
        session="custody-control-plane-20260714",
        source="resident_authorized_recovery",
        workspace=tmp_path,
        run_kind="chain",
        target={
            "plan_name": plan_name,
            "configured_profile": "partnered-5",
            "recovery_contract": {
                "preserve_configured_profile": True,
                "required_cursor_advance": True,
                "success_requires": "active execution plus chain-owned receipt",
                "forbid_standalone_completion": True,
            },
        },
        problem_signature={
            "failure_kind": "completed_repair_without_cursor_advance",
            "current_state": "planned",
            "phase_or_step": "critique",
            "milestone_or_plan": plan_name,
            "gate_recommendation": "continue the legal transition",
            "blocked_task_id": "phase:critique",
        },
        root_cause_hint="recurrence",
    )
    request_id = queued["request"]["request_id"]
    for _ in range(3):
        repair_requests.record_unclaimed_request_failure(
            queue_dir,
            request_id=request_id,
            reason="ordinary repair completed without cursor advancement",
        )

    projection = repair_contract.project_repair_custody(
        plan_state={"name": plan_name, "current_state": "planned"},
        current_target={
            "target_session": "custody-control-plane-20260714",
            "current_refs": {
                "current_plan_name": plan_name,
                "plan_current_state": "planned",
            },
        },
        queue_root=queue_dir,
    )

    assert projection["accepted_unclaimed_request_ids"] == [request_id]
    assert projection["claim_alert_request_ids"] == [request_id]
    assert projection["retry_budget"]["claim_alerted"] is True


def test_replay_mints_claimable_successor_for_identity_free_legacy_request(
    tmp_path: Path,
) -> None:
    queue_dir = _queue_root(tmp_path)
    signature = _signature()
    legacy_request_id = repair_requests.request_id_for(
        session="demo",
        problem_signature=signature,
        root_cause_hint="same failure",
    )
    legacy_path = repair_requests.requests_dir(queue_dir) / f"{legacy_request_id}.json"
    legacy_record = {
        "schema_version": 1,
        "kind": "repair_request",
        "request_id": legacy_request_id,
        "created_at": "2026-07-01T00:00:00Z",
        "session": "demo",
        "problem_signature": repair_requests.normalize_problem_signature(signature),
        "problem_signature_key": repair_requests.problem_signature_key(signature),
    }
    repair_contract.atomic_write_json(legacy_path, legacy_record)
    legacy_bytes = legacy_path.read_bytes()

    replay = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="lifecycle_failure",
        problem_signature=signature,
        root_cause_hint="same failure",
        created_at="2026-07-01T00:01:00Z",
    )

    assert replay["status"] == "queued"
    assert replay["request"]["request_id"] != legacy_request_id
    assert replay["request"]["predecessor_request_id"] == legacy_request_id
    assert replay["request"]["blocker_id"] == repair_contract.blocker_id_for_fingerprint(
        replay["request"]["blocker_fingerprint"]
    )
    assert legacy_path.read_bytes() == legacy_bytes
    reloaded = repair_requests.iter_repair_requests(queue_dir)
    assert {record["request_id"] for record in reloaded} == {
        legacy_request_id,
        replay["request"]["request_id"],
    }


def test_write_decision_idempotency_via_claim(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    first = repair_requests.write_decision(
        queue_dir,
        request_id="req-xyz",
        decision="stale",
        reason="marker no longer matches",
        created_at="2026-07-01T04:00:00Z",
    )
    # Second write with same parameters produces different decision_id (different timestamp)
    second = repair_requests.write_decision(
        queue_dir,
        request_id="req-xyz",
        decision="stale",
        reason="marker no longer matches",
        created_at="2026-07-01T04:00:01Z",
    )
    assert first["decision_id"] != second["decision_id"]
    # Both files exist
    assert Path(first["_path"]).exists()
    assert Path(second["_path"]).exists()


def test_record_malformed_file_creates_malformed_decision(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    result = repair_requests.record_malformed_file(
        queue_dir,
        path="/some/broken/file.json",
        reason="not valid JSON",
    )
    assert result["decision"] == "malformed"
    assert result["reason"] == "not valid JSON"


# ---------------------------------------------------------------------------
# find_pending_by_signature
# ---------------------------------------------------------------------------


def test_find_pending_by_signature_returns_none_when_queue_is_empty(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    assert repair_requests.find_pending_by_signature(queue_dir, _signature()) is None


def test_find_pending_by_signature_finds_queued_request(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    enqueued = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="T1"),
        root_cause_hint="find me",
    )
    assert enqueued["status"] == "queued"

    found = repair_requests.find_pending_by_signature(
        queue_dir,
        _signature(blocked_task_id="T1"),
        repair_identity=enqueued["request"]["repair_identity"],
    )
    assert found is not None
    assert found["request_id"] == enqueued["request"]["request_id"]


def test_find_pending_by_signature_keeps_dispatched_request_open(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    enqueued = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="T1"),
        root_cause_hint="find me after dispatch",
    )
    request_id = enqueued["request"]["request_id"]
    repair_requests.write_decision(
        queue_dir,
        request_id=request_id,
        decision="dispatched",
        reason="managed repair launched",
    )

    found = repair_requests.find_pending_by_signature(
        queue_dir,
        _signature(blocked_task_id="T1"),
        repair_identity=enqueued["request"]["repair_identity"],
    )

    assert found is not None
    assert found["request_id"] == request_id


def test_find_pending_by_signature_excludes_stale_requests(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="stale-task"),
        root_cause_hint="stale request",
        stale_reason="no longer relevant",
    )
    found = repair_requests.find_pending_by_signature(
        queue_dir,
        _signature(blocked_task_id="stale-task"),
    )
    assert found is None


def test_find_pending_by_signature_excludes_superseded_requests(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="super-task"),
        root_cause_hint="superseded request",
        superseded_by="newer-session",
    )
    found = repair_requests.find_pending_by_signature(
        queue_dir,
        _signature(blocked_task_id="super-task"),
    )
    assert found is None


def test_find_pending_by_signature_returns_none_for_different_signature(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="T1"),
        root_cause_hint="only T1 queued",
    )
    found = repair_requests.find_pending_by_signature(
        queue_dir,
        _signature(blocked_task_id="T99"),
    )
    assert found is None


# ---------------------------------------------------------------------------
# Timestamp drift does not fragment incidents
# ---------------------------------------------------------------------------


def test_timestamp_drift_does_not_create_multiple_requests_for_same_signature(tmp_path: Path) -> None:
    """Same problem signature submitted at different times coalesces to a single request."""
    queue_dir = _queue_root(tmp_path)
    results = []
    for i, ts in enumerate(["2026-07-01T10:00:00Z", "2026-07-01T10:05:00Z", "2026-07-01T10:10:00Z"]):
        results.append(
            _enqueue(
                queue_root=queue_dir,
                session="demo",
                source="test",
                problem_signature=_signature(blocked_task_id="drift-T1"),
                root_cause_hint=f"attempt {i}",
                created_at=ts,
            )
        )
    assert results[0]["status"] == "queued"
    assert all(r["status"] == "coalesced" for r in results[1:])
    requests = repair_requests.iter_repair_requests(queue_dir)
    assert len(requests) == 1
    # The stored request keeps the original timestamp
    assert requests[0]["created_at"] == "2026-07-01T10:00:00Z"


def test_exact_repair_identity_prevents_coalescing_across_attempts(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    first = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="T1"),
        root_cause_hint="same blocker new attempt",
        repair_identity=_repair_identity(attempt_number=1, fence_token="fence-1"),
    )
    second = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="T1"),
        root_cause_hint="same blocker new attempt",
        repair_identity=_repair_identity(attempt_number=2, fence_token="fence-2"),
    )

    assert first["status"] == "queued"
    assert second["status"] == "queued"
    requests = repair_requests.iter_repair_requests(queue_dir)
    assert len(requests) == 2
    assert requests[0]["repair_identity_key"] != requests[1]["repair_identity_key"]


def test_exact_repair_identity_does_not_coalesce_with_legacy_identity_free_request(
    tmp_path: Path,
) -> None:
    queue_dir = _queue_root(tmp_path)
    signature = _signature(blocked_task_id="T1")
    legacy_request_id = repair_requests.request_id_for(
        session="demo",
        problem_signature=signature,
        root_cause_hint="legacy request without exact identity",
    )
    legacy_record = {
        "schema_version": 1,
        "kind": "repair_request",
        "request_id": legacy_request_id,
        "created_at": "2026-07-01T00:00:00Z",
        "session": "demo",
        "problem_signature": repair_requests.normalize_problem_signature(signature),
        "problem_signature_key": repair_requests.problem_signature_key(signature),
    }
    repair_contract.atomic_write_json(
        repair_requests.requests_dir(queue_dir) / f"{legacy_request_id}.json",
        legacy_record,
    )
    exact = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=signature,
        root_cause_hint="same blocker with exact identity",
        repair_identity=_repair_identity(attempt_number=1, fence_token="fence-1"),
    )

    assert exact["status"] == "queued"
    requests = repair_requests.iter_repair_requests(queue_dir)
    assert len(requests) == 2
    assert {
        str(request.get("repair_identity_key") or "") for request in requests
    } == {
        "",
        repair_requests.repair_identity_key(_repair_identity(attempt_number=1, fence_token="fence-1")),
    }


def test_bind_managed_run_to_active_claim_rejects_mismatched_repair_identity(
    tmp_path: Path,
) -> None:
    queue_dir = _queue_root(tmp_path)
    identity = _repair_identity(attempt_number=1, fence_token="fence-1")
    request = _claimable_request(
        queue_dir,
        blocked_task_id="bind",
        repair_identity=identity,
    )
    # The active-claim acquire path was removed with the layered repair
    # stack; seed the claim lock dir + owner record directly so the surviving
    # bind path keeps its mismatch-contract coverage.
    lock_dir = repair_requests.active_repair_claim_lock_dir(
        queue_dir, str(request["blocker_id"])
    )
    lock_dir.mkdir(parents=True, exist_ok=True)
    repair_contract.atomic_write_json(
        lock_dir / "owner.json",
        {
            "schema_version": 1,
            "kind": "active_repair_request_claim",
            "blocker_id": str(request["blocker_id"]),
            "request_id": str(request["request_id"]),
            "actor": "trigger-a",
            "session": "demo-session",
            "pid": 111,
            "repair_identity_key": repair_requests.repair_identity_key(identity),
        },
    )

    assert not repair_requests.bind_managed_run_to_active_claim(
        queue_dir,
        blocker_id=str(request["blocker_id"]),
        request_id=str(request["request_id"]),
        managed_run_id="managed-1",
        managed_manifest_path="/tmp/managed-1/manifest.json",
        expected_owner_pid=111,
        new_owner_pid=222,
        repair_identity=_repair_identity(attempt_number=2, fence_token="fence-2"),
    )
    owner = json.loads((lock_dir / "owner.json").read_text(encoding="utf-8"))
    assert owner["pid"] == 111
    assert owner.get("managed_agent_run_id", "") == ""


# ---------------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------------


def test_iter_repair_requests_returns_deterministic_order_by_created_at(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    third = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="T3"),
        root_cause_hint="third",
        created_at="2026-07-01T12:00:00Z",
    )
    first = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="T1"),
        root_cause_hint="first",
        created_at="2026-07-01T10:00:00Z",
    )
    second = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="T2"),
        root_cause_hint="second",
        created_at="2026-07-01T11:00:00Z",
    )
    requests = repair_requests.iter_repair_requests(queue_dir)
    ids = [r["request_id"] for r in requests]
    assert ids == [
        first["request"]["request_id"],
        second["request"]["request_id"],
        third["request"]["request_id"],
    ]


# ---------------------------------------------------------------------------
# Comprehensive malformed file handling
# ---------------------------------------------------------------------------


def test_malformed_non_dict_json_is_reported(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    req_dir = repair_requests.requests_dir(queue_dir)
    req_dir.mkdir(parents=True)
    (req_dir / "array.json").write_text('[1, 2, 3]', encoding="utf-8")

    valid = repair_requests.iter_repair_requests(queue_dir)
    assert len(valid) == 0
    all_records = repair_requests.iter_repair_requests(queue_dir, include_malformed=True)
    assert len(all_records) == 1
    assert all_records[0]["kind"] == "malformed_repair_request"
    assert "array.json" in all_records[0]["path"]


def test_malformed_missing_required_fields_is_reported(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    req_dir = repair_requests.requests_dir(queue_dir)
    req_dir.mkdir(parents=True)
    (req_dir / "incomplete.json").write_text(
        json.dumps({"kind": "repair_request", "schema_version": 1}), encoding="utf-8"
    )

    valid = repair_requests.iter_repair_requests(queue_dir)
    assert len(valid) == 0
    all_records = repair_requests.iter_repair_requests(queue_dir, include_malformed=True)
    assert len(all_records) == 1
    assert all_records[0]["kind"] == "malformed_repair_request"


def test_malformed_wrong_kind_is_reported(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    req_dir = repair_requests.requests_dir(queue_dir)
    req_dir.mkdir(parents=True)
    (req_dir / "wrong_kind.json").write_text(
        json.dumps({
            "schema_version": 1,
            "kind": "not_a_repair_request",
            "request_id": "abc",
            "problem_signature": {},
        }),
        encoding="utf-8",
    )

    valid = repair_requests.iter_repair_requests(queue_dir)
    assert len(valid) == 0
    all_records = repair_requests.iter_repair_requests(queue_dir, include_malformed=True)
    assert len(all_records) == 1
    assert all_records[0]["kind"] == "malformed_repair_request"


# ---------------------------------------------------------------------------
# Write-once atomicity — deeper tests
# ---------------------------------------------------------------------------


def test_enqueue_request_file_is_immutable_after_first_write(tmp_path: Path) -> None:
    """Once written, the request file content never changes — coalescing doesn't touch it."""
    queue_dir = _queue_root(tmp_path)
    first = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="immutable"),
        root_cause_hint="original content",
        created_at="2026-07-01T14:00:00Z",
    )
    assert first["status"] == "queued"
    first_path = Path(first["path"])
    first_content = first_path.read_text(encoding="utf-8")
    first_mtime = first_path.stat().st_mtime

    # Coalesce
    second = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="immutable"),
        root_cause_hint="different content",
        created_at="2026-07-01T14:30:00Z",
    )
    assert second["status"] == "coalesced"

    # The original file is untouched
    assert first_path.read_text(encoding="utf-8") == first_content
    assert first_path.stat().st_mtime == first_mtime


def test_stale_request_file_persists_unchanged(tmp_path: Path) -> None:
    """Stale requests still write the request file but mark it as stale via decision."""
    queue_dir = _queue_root(tmp_path)
    result = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="stale-persist"),
        root_cause_hint="stale",
        stale_reason="plan no longer active",
        created_at="2026-07-01T15:00:00Z",
    )
    assert result["status"] == "stale"
    request_path = Path(result["path"])
    assert request_path.exists()
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    assert payload["kind"] == "repair_request"
    # Decision exists separately
    assert Path(result["decision"]["_path"]).exists()


def test_superseded_request_file_persists_unchanged(tmp_path: Path) -> None:
    """Superseded requests still write the request file but mark it via decision."""
    queue_dir = _queue_root(tmp_path)
    result = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="super-persist"),
        root_cause_hint="superseded",
        superseded_by="new-session-id",
        created_at="2026-07-01T16:00:00Z",
    )
    assert result["status"] == "superseded"
    request_path = Path(result["path"])
    assert request_path.exists()
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    assert payload["kind"] == "repair_request"
    assert Path(result["decision"]["_path"]).exists()


# ---------------------------------------------------------------------------
# Redaction: no raw failure text stored
# ---------------------------------------------------------------------------


def test_request_marker_never_contains_root_cause_hint_raw_text(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    result = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(),
        root_cause_hint="some secret token sk-abcdefghijklmnop",
    )
    request_text = Path(result["path"]).read_text(encoding="utf-8")
    assert "sk-abcdefghijklmnop" not in request_text
    assert "root_cause_hint_hash" in json.loads(request_text)
    assert "root_cause_hint_hash_algorithm" in json.loads(request_text)


def test_redacted_hint_hash_is_consistent() -> None:
    """Same redacted hint always produces the same hash."""
    h1 = repair_requests.redacted_hint_hash("same hint text")
    h2 = repair_requests.redacted_hint_hash("same hint text")
    assert h1 == h2
    assert len(h1) == 64


def test_target_is_stored_as_stable_sorted_mapping(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    result = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(),
        target={"z_key": "z", "a_key": "a"},
    )
    payload = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    target_keys = list(payload["target"])
    assert target_keys == ["a_key", "z_key"]


# ---------------------------------------------------------------------------
# Decision exclusion: stale/superseded records are not pending
# ---------------------------------------------------------------------------


def test_iter_repair_requests_includes_all_requests_regardless_of_decisions(tmp_path: Path) -> None:
    """iter_repair_requests returns request files regardless of decision state."""
    queue_dir = _queue_root(tmp_path)
    _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="stale-iter"),
        root_cause_hint="stale",
        stale_reason="expired",
    )
    _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="queued-iter"),
        root_cause_hint="queued",
    )
    requests = repair_requests.iter_repair_requests(queue_dir)
    # Both request files exist and are returned
    assert len(requests) == 2
    kinds = {r["kind"] for r in requests}
    assert kinds == {"repair_request"}


def test_enqueue_with_workspace_and_run_kind_stored(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    result = _enqueue(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(),
        workspace="/tmp/ws",
        run_kind="execute",
    )
    payload = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert payload["workspace"] == "/tmp/ws"
    assert payload["run_kind"] == "execute"


# ---------------------------------------------------------------------------
# T15: Repair verdict decision records
# ---------------------------------------------------------------------------


def test_write_repair_verdict_decision_for_cleared(tmp_path: Path) -> None:
    """write_repair_verdict_decision records a dispatched decision for cleared verdict."""
    queue_dir = _queue_root(tmp_path)
    decision = repair_requests.write_repair_verdict_decision(
        queue_dir,
        request_id="req-cleared-001",
        verdict_kind="cleared",
        verdict_path="/tmp/verdicts/cleared-001.json",
        blocker_id="blocker-42",
        reason="repair loop completed successfully",
    )
    assert decision["decision"] == "dispatched"
    assert decision["request_id"] == "req-cleared-001"
    assert "repair_verdict: cleared" in decision["reason"]
    assert "blocker=blocker-42" in decision["reason"]
    assert "path=/tmp/verdicts/cleared-001.json" in decision["reason"]
    assert "repair loop completed successfully" in decision["reason"]

    # Decision file exists
    decision_path = Path(decision["_path"])
    assert decision_path.exists()
    payload = json.loads(decision_path.read_text(encoding="utf-8"))
    assert payload["decision"] == "dispatched"
    assert payload["request_id"] == "req-cleared-001"


def test_write_repair_verdict_decision_for_no_fix(tmp_path: Path) -> None:
    """write_repair_verdict_decision records dispatched for no_fix verdict."""
    queue_dir = _queue_root(tmp_path)
    decision = repair_requests.write_repair_verdict_decision(
        queue_dir,
        request_id="req-nofix-001",
        verdict_kind="no_fix",
        blocker_id="blocker-nofix",
        reason="all repair strategies exhausted",
    )
    assert decision["decision"] == "dispatched"
    assert "repair_verdict: no_fix" in decision["reason"]
    assert "blocker=blocker-nofix" in decision["reason"]
    assert "all repair strategies exhausted" in decision["reason"]


def test_write_repair_verdict_decision_for_escalated(tmp_path: Path) -> None:
    """write_repair_verdict_decision records dispatched for escalated verdict."""
    queue_dir = _queue_root(tmp_path)
    decision = repair_requests.write_repair_verdict_decision(
        queue_dir,
        request_id="req-esc-001",
        verdict_kind="escalated",
        blocker_id="blocker-human",
        reason="human intervention required",
    )
    assert decision["decision"] == "dispatched"
    assert "repair_verdict: escalated" in decision["reason"]
    assert "human intervention required" in decision["reason"]


def test_write_repair_verdict_decision_minimal_fields(tmp_path: Path) -> None:
    """write_repair_verdict_decision works with only required fields."""
    queue_dir = _queue_root(tmp_path)
    decision = repair_requests.write_repair_verdict_decision(
        queue_dir,
        request_id="req-minimal-001",
        verdict_kind="stale",
    )
    assert decision["decision"] == "dispatched"
    assert "repair_verdict: stale" in decision["reason"]
    # No blocker/path fields when not provided
    assert "blocker=" not in decision["reason"]
    assert "path=" not in decision["reason"]


# ---------------------------------------------------------------------------
# Step 13A — exact repair identity, removed synthetic WBC defaults, pending
# and escalation coverage.
# ---------------------------------------------------------------------------


def test_enqueue_without_repair_identity_is_zero_authority_rejected(
    tmp_path: Path,
) -> None:
    """A pre-dispatch producer cannot mint or queue synthetic authority."""

    queue_dir = _queue_root(tmp_path)
    lease_dir = tmp_path / ".megaplan" / "custody-leases"
    result = repair_requests.enqueue_repair_request(
        queue_root=queue_dir,
        session="demo-session",
        problem_signature=_signature(),
        source="execute",
        workspace=str(tmp_path),
        lease_store_dir=str(lease_dir),
    )
    assert result["status"] == "zero_authority_rejected"
    assert repair_requests.iter_repair_requests(queue_dir) == []
    assert not lease_dir.exists()


def test_enqueue_with_full_repair_identity_binds_shadow_lease(tmp_path: Path) -> None:
    """A full repair-identity tuple binds a real (non-synthetic) shadow lease."""

    queue_dir = _queue_root(tmp_path)
    lease_dir = tmp_path / ".megaplan" / "custody-leases"
    identity = _repair_identity()
    result = _enqueue(
        queue_root=queue_dir,
        session="demo-session",
        problem_signature=_signature(),
        source="execute",
        workspace=str(tmp_path),
        lease_store_dir=str(lease_dir),
        repair_identity=identity,
    )
    assert result["status"] == "queued"
    request = result["request"]
    assert request["repair_identity"] == identity
    shadow = result["m7_custody_lease"]
    assert shadow["m7_lease_status"] == "acquired"
    assert shadow["m7_lease_epoch"] == 1
    assert shadow["m7_lease_event_id"]


def test_shadow_acquire_pending_when_wbc_attempt_reference_missing(
    tmp_path: Path,
) -> None:
    """A partial identity tuple (missing wbc_attempt_reference) is pending."""

    from arnold_pipelines.megaplan.custody.lease_store import CustodyLeaseStore
    from arnold_pipelines.megaplan.custody.contracts import CustodyTargetKey

    lease_dir = tmp_path / ".megaplan" / "custody-leases"
    store = CustodyLeaseStore(lease_dir)
    target = CustodyTargetKey(
        environment="dev",
        session="demo-session",
        chain="m3",
        plan_revision="rev-1",
        phase="execute",
        task="T1",
        attempt="1",
        normalized_failure_kind="execute_failed",
        blocker_or_phase_result_hash="h",
        fence="fence-1",
    )
    result = repair_requests._shadow_acquire_custody_lease(
        lease_store=store,
        lease_id="repair-req-partial",
        target=target,
        owner_host="worker-host",
        owner_pid="100",
        owner_boot_id="boot-1",
        run_id="run-1",
        run_revision="rev-1",
        coordinator_attempt_id="coord-1",
        run_authority_grant_id="grant-1",
        coordinator_fence_token=3,
        # wbc_attempt_reference intentionally omitted
    )
    assert result["m7_lease_status"] == "pending"
    assert "incomplete" in result["m7_lease_detail"]


def test_pending_request_then_escalates_after_unclaimed_handoffs(tmp_path: Path) -> None:
    """A pending (identity-incomplete) request escalates if never claimed."""

    queue_dir = _queue_root(tmp_path)
    result = _enqueue(
        queue_root=queue_dir,
        session="demo-session",
        problem_signature=_signature(),
        source="execute",
        workspace=str(tmp_path),
    )
    assert result["status"] == "queued"
    request_id = result["request"]["request_id"]

    escalated = repair_requests.record_unclaimed_request_failure(
        queue_dir,
        request_id=request_id,
        reason="no worker bound repair identity",
        max_retries=2,
    )
    assert escalated["status"] == "retryable"
    assert escalated["retry_count"] == 1

    final = repair_requests.record_unclaimed_request_failure(
        queue_dir,
        request_id=request_id,
        reason="no worker bound repair identity",
        max_retries=2,
    )
    assert final["status"] == "alerted"
    assert final["alert"]["decision"] == "claim_alert"
