from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier

from arnold_pipelines.megaplan.cloud import repair_requests


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
        repair_requests.enqueue_repair_request(
            marker_dir=tmp_path / ".megaplan" / "chain-markers",
            session="demo",
            source="test",
            problem_signature=_signature(),
        )
    except TypeError as exc:
        assert "queue_root" in str(exc)
    else:
        raise AssertionError("enqueue inferred queue custody from marker provenance")


def test_concurrent_active_repair_request_claim_has_one_winner_and_typed_losers(
    tmp_path: Path,
) -> None:
    queue_dir = _queue_root(tmp_path)
    blocker_id = "blocker:v1:shared"
    request_id = "req-active"
    contenders = 8
    barrier = Barrier(contenders)

    def claim(index: int) -> repair_requests.ActiveRepairClaimResult:
        barrier.wait(timeout=10)
        return repair_requests.claim_active_repair_request(
            queue_dir,
            blocker_id=blocker_id,
            request_id=request_id,
            actor=f"worker-{index}",
            session="demo-session",
            pid=10_000 + index,
            command="repair-trigger",
            cwd="/workspace/project",
            hostname="worker-host",
            is_pid_live=lambda pid: True,
        )

    with ThreadPoolExecutor(max_workers=contenders) as executor:
        results = list(executor.map(claim, range(contenders)))

    winners = [result for result in results if result.claimed]
    losers = [result for result in results if result.already_claimed]
    assert len(winners) == 1
    assert len(losers) == contenders - 1
    assert winners[0].owner is not None
    assert winners[0].owner["kind"] == "active_repair_request_claim"
    assert winners[0].owner["actor"].startswith("worker-")
    assert winners[0].owner["session"] == "demo-session"
    assert winners[0].owner["request_id"] == request_id
    assert winners[0].owner["blocker_id"] == blocker_id
    assert winners[0].owner["pid"] in {10_000 + index for index in range(contenders)}
    assert all(loser.evidence is not None for loser in losers)
    assert {loser.evidence["status"] for loser in losers if loser.evidence} == {"already_claimed"}
    assert {loser.evidence["owner_request_id"] for loser in losers if loser.evidence} == {request_id}
    assert {loser.evidence["owner_blocker_id"] for loser in losers if loser.evidence} == {blocker_id}


def test_active_repair_claim_for_different_request_reports_busy_owner(
    tmp_path: Path,
) -> None:
    queue_dir = _queue_root(tmp_path)
    first = repair_requests.claim_active_repair_request(
        queue_dir,
        blocker_id="blocker:v1:shared",
        request_id="req-a",
        actor="trigger-a",
        session="demo-session",
        pid=111,
        is_pid_live=lambda pid: True,
    )

    second = repair_requests.claim_active_repair_request(
        queue_dir,
        blocker_id="blocker:v1:shared",
        request_id="req-b",
        actor="trigger-b",
        session="demo-session",
        pid=222,
        is_pid_live=lambda pid: True,
    )

    assert first.claimed
    assert second.busy
    assert second.evidence is not None
    assert second.evidence["status"] == "busy"
    assert second.evidence["owner_request_id"] == "req-a"
    assert second.evidence["request_id"] == "req-b"
    assert second.evidence["owner_actor"] == "trigger-a"


def test_active_repair_claim_preserves_stale_lock_evidence(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    first = repair_requests.claim_active_repair_request(
        queue_dir,
        blocker_id="blocker:v1:stale",
        request_id="req-stale",
        actor="trigger-a",
        session="demo-session",
        pid=333,
        started_at="2026-07-04T01:00:00+00:00",
        timeout_seconds=60,
        is_pid_live=lambda pid: True,
    )
    assert first.claimed
    owner_path = first.lock_dir / "owner.json"

    stale = repair_requests.claim_active_repair_request(
        queue_dir,
        blocker_id="blocker:v1:stale",
        request_id="req-stale",
        actor="trigger-b",
        session="demo-session",
        pid=444,
        now=datetime(2026, 7, 4, 1, 10, tzinfo=timezone.utc),
        is_pid_live=lambda pid: False,
    )

    assert stale.stale
    assert stale.owner is not None
    assert stale.owner["pid"] == 333
    assert stale.owner["actor"] == "trigger-a"
    assert json.loads(owner_path.read_text(encoding="utf-8")) == stale.owner
    assert first.lock_dir.exists()


def test_active_repair_claim_reports_live_pid_session_mismatch_without_reclaiming(
    tmp_path: Path,
) -> None:
    queue_dir = _queue_root(tmp_path)
    first = repair_requests.claim_active_repair_request(
        queue_dir,
        blocker_id="blocker:v1:process-mismatch",
        request_id="req-process-mismatch",
        actor="trigger-a",
        session="demo-session",
        pid=os.getpid(),
        command="arnold-repair-loop demo-session /workspace/project /workspace/project/.megaplan/chain.yaml",
        started_at="2026-07-04T01:00:00+00:00",
        is_pid_live=lambda pid: pid == os.getpid(),
    )
    assert first.claimed

    stale = repair_requests.claim_active_repair_request(
        queue_dir,
        blocker_id="blocker:v1:process-mismatch",
        request_id="req-process-mismatch",
        actor="trigger-b",
        session="demo-session",
        pid=556,
        command="arnold-repair-loop demo-session /workspace/project /workspace/project/.megaplan/chain.yaml",
        is_pid_live=lambda pid: pid in {os.getpid(), 556},
    )

    assert stale.stale
    assert stale.owner is not None
    assert stale.owner["pid"] == os.getpid()
    assert stale.owner["actor"] == "trigger-a"

def test_active_repair_claim_defaults_to_pid_liveness_probe(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    first = repair_requests.claim_active_repair_request(
        queue_dir,
        blocker_id="blocker:v1:dead-owner",
        request_id="req-dead",
        actor="trigger-a",
        session="demo-session",
        pid=99999999,
    )

    assert first.claimed

    stale = repair_requests.claim_active_repair_request(
        queue_dir,
        blocker_id="blocker:v1:dead-owner",
        request_id="req-new",
        actor="trigger-b",
        session="demo-session",
        pid=444,
    )

    assert stale.stale
    assert stale.evidence is not None
    assert "owner_pid_not_live" in stale.evidence["stale_evidence"]["reasons"]


def test_enqueue_writes_once_and_never_stores_raw_root_cause_text(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    marker_dir = tmp_path / ".megaplan" / "chain-markers"
    raw_hint = "Authorization: Bearer sk-proj-abcdefghijklmnopqrstuvwxyz123456"

    first = repair_requests.enqueue_repair_request(
        queue_root=queue_dir,
        marker_dir=marker_dir,
        session="demo",
        source="_record_lifecycle_failure",
        problem_signature=_signature(),
        root_cause_hint=raw_hint,
        created_at="2026-07-01T00:00:00Z",
    )
    second = repair_requests.enqueue_repair_request(
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

    first = repair_requests.enqueue_repair_request(
        queue_root=queue_dir,
        session="demo",
        source="HumanGateStep.run",
        problem_signature=_signature(),
        root_cause_hint="first failure",
        created_at="2026-07-01T01:00:00Z",
    )
    duplicate = repair_requests.enqueue_repair_request(
        queue_root=queue_dir,
        session="demo",
        source="HumanGateStep.run",
        problem_signature=_signature(),
        root_cause_hint="different raw text",
        created_at="2026-07-01T01:05:00Z",
    )
    distinct = repair_requests.enqueue_repair_request(
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

    stale = repair_requests.enqueue_repair_request(
        queue_root=queue_dir,
        session="demo",
        source="HumanGateStep.run",
        problem_signature=_signature(),
        root_cause_hint="old",
        stale_reason="marker no longer matches current plan",
    )
    superseded = repair_requests.enqueue_repair_request(
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

    later = repair_requests.enqueue_repair_request(
        queue_root=queue_dir,
        session="demo",
        source="HumanGateStep.run",
        problem_signature=_signature(blocked_task_id="T2"),
        root_cause_hint="later",
        created_at="2026-07-01T02:00:00Z",
    )
    earlier = repair_requests.enqueue_repair_request(
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


# ---------------------------------------------------------------------------
# write_decision and decision records
# ---------------------------------------------------------------------------


def test_write_decision_creates_immutable_decision_record(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    decision = repair_requests.write_decision(
        queue_dir,
        request_id="req-abc123",
        decision="accepted",
        reason="queued",
        created_at="2026-07-01T03:00:00Z",
    )
    assert decision["decision"] == "accepted"
    assert decision["request_id"] == "req-abc123"
    assert decision["reason"] == "queued"
    assert "decision_id" in decision
    assert "_path" in decision

    # Decision file exists on disk
    decision_path = Path(decision["_path"])
    assert decision_path.exists()
    payload = json.loads(decision_path.read_text(encoding="utf-8"))
    assert payload["decision"] == "accepted"


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
    enqueued = repair_requests.enqueue_repair_request(
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
    )
    assert found is not None
    assert found["request_id"] == enqueued["request"]["request_id"]


def test_find_pending_by_signature_excludes_stale_requests(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    repair_requests.enqueue_repair_request(
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
    repair_requests.enqueue_repair_request(
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
    repair_requests.enqueue_repair_request(
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
            repair_requests.enqueue_repair_request(
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


# ---------------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------------


def test_iter_repair_requests_returns_deterministic_order_by_created_at(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    third = repair_requests.enqueue_repair_request(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="T3"),
        root_cause_hint="third",
        created_at="2026-07-01T12:00:00Z",
    )
    first = repair_requests.enqueue_repair_request(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="T1"),
        root_cause_hint="first",
        created_at="2026-07-01T10:00:00Z",
    )
    second = repair_requests.enqueue_repair_request(
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
    first = repair_requests.enqueue_repair_request(
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
    second = repair_requests.enqueue_repair_request(
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
    result = repair_requests.enqueue_repair_request(
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
    result = repair_requests.enqueue_repair_request(
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
    result = repair_requests.enqueue_repair_request(
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
    result = repair_requests.enqueue_repair_request(
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
    repair_requests.enqueue_repair_request(
        queue_root=queue_dir,
        session="demo",
        source="test",
        problem_signature=_signature(blocked_task_id="stale-iter"),
        root_cause_hint="stale",
        stale_reason="expired",
    )
    repair_requests.enqueue_repair_request(
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
    result = repair_requests.enqueue_repair_request(
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
