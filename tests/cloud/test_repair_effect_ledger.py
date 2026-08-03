from __future__ import annotations

import json
import subprocess
import sys
import threading

import pytest

from arnold_pipelines.megaplan.cloud import repair_requests
from arnold_pipelines.megaplan.cloud.repair_effect_ledger import (
    DECISION_ADOPTED,
    DECISION_INDETERMINATE,
    DECISION_IN_FLIGHT,
    RepairEffectLedger,
    STATE_COMPLETED,
    STATE_EXHAUSTED,
    STATE_INDETERMINATE,
)
from arnold_pipelines.megaplan.cloud.wrappers.repair_delegation import (
    RepairDelegation,
    delegate_to_simple_fixer,
)
from arnold_pipelines.megaplan.custody.contracts import CustodyTargetKey


def _identity(*, attempt: str = "1") -> dict:
    target = CustodyTargetKey(
        environment="cloud:test",
        session="session-1",
        chain="chain-1",
        plan_revision="revision-1",
        phase="execute",
        task="T1",
        attempt=attempt,
        normalized_failure_kind="stalled",
        blocker_or_phase_result_hash="sha256:blocker",
        fence=f"runner-fence:{attempt}",
        chain_identity="chain-incarnation-1",
    )
    identity = repair_requests.build_normalized_repair_identity(
        target=target,
        run_id="run-1",
        run_revision="revision-1",
        run_incarnation_id=f"run-incarnation-{attempt}",
        coordinator_attempt_id=f"coordinator-{attempt}",
        fence_token=int(attempt),
        wbc_attempt_reference=f"wbc-{attempt}",
        run_authority_grant_id=f"grant-{attempt}",
        lease_id=f"lease-{attempt}",
        custody_epoch=1,
    )
    assert identity is not None
    return identity


def _delegation(identity: dict, caller: str = "caller") -> RepairDelegation:
    occurrence = identity["occurrence"]
    target = CustodyTargetKey.from_dict(occurrence["target"])
    return RepairDelegation(
        caller_kind="wrapper",
        caller_id=caller,
        target=target,
        repair_identity=identity,
    )


def _queue(tmp_path) -> str:
    return str(tmp_path / ".megaplan" / "repair-queue")


def _run(queue: str, identity: dict, mutate, *, request: str):
    return delegate_to_simple_fixer(
        _delegation(identity, request),
        queue_dir=queue,
        mutate=mutate,
        actor=request,
        request_id=request,
        session_id="session-1",
    )


def test_completed_effect_is_adopted_after_store_and_claim_restart(tmp_path):
    queue = _queue(tmp_path)
    identity = _identity()
    calls: list[str] = []

    first = _run(
        queue,
        identity,
        lambda occurrence: calls.append("applied") or occurrence.occurrence_fingerprint + ":done",
        request="container-a",
    )
    assert first.delegated
    assert first.simple_fixer_outcome == "attempted"

    # New ledger connection + released/reacquired claim cannot replenish the
    # effect.  The callback would explode if it were re-driven.
    RepairEffectLedger(queue)
    second = _run(
        queue,
        identity,
        lambda _occurrence: (_ for _ in ()).throw(AssertionError("redriven")),
        request="container-b",
    )
    assert second.delegated
    assert second.simple_fixer_outcome == "adopted"
    assert calls == ["applied"]
    record = RepairEffectLedger(queue).inspect(identity)
    assert record is not None and record.state == STATE_COMPLETED
    assert record.total_attempts == 1

    # A genuinely new interpreter sees the same terminal effect and adopts
    # it; process-local state is not involved.
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json,sys; "
                "from arnold_pipelines.megaplan.cloud.repair_effect_ledger "
                "import RepairEffectLedger; "
                "r=RepairEffectLedger(sys.argv[1]).reserve("
                "json.loads(sys.argv[2]),owner_token='new-process',"
                "max_unchanged_attempts=2); print(r.decision)"
            ),
            queue,
            json.dumps(identity),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert probe.stdout.strip() == DECISION_ADOPTED


def test_two_container_contention_invokes_one_mutation(tmp_path):
    queue = _queue(tmp_path)
    identity = _identity()
    entered = threading.Event()
    release = threading.Event()
    results = []
    calls = 0
    call_lock = threading.Lock()

    def mutate(occurrence):
        nonlocal calls
        with call_lock:
            calls += 1
        entered.set()
        assert release.wait(timeout=5)
        return occurrence.occurrence_fingerprint + ":done"

    worker = threading.Thread(
        target=lambda: results.append(_run(queue, identity, mutate, request="container-a"))
    )
    worker.start()
    assert entered.wait(timeout=5)
    loser = _run(queue, identity, mutate, request="container-b")
    release.set()
    worker.join(timeout=5)

    assert calls == 1
    assert len(results) == 1 and results[0].delegated
    assert not loser.delegated
    assert loser.simple_fixer_outcome == "busy"


def test_reserved_then_crash_becomes_indeterminate_on_new_claim_owner(tmp_path):
    queue = _queue(tmp_path)
    identity = _identity()
    first_store = RepairEffectLedger(queue)
    reserved = first_store.reserve(identity, owner_token="owner-a", max_unchanged_attempts=2)
    assert reserved.reserved

    # Same claim/store restart observes in-flight and cannot invoke twice.
    same_owner = RepairEffectLedger(queue).reserve(
        identity, owner_token="owner-a", max_unchanged_attempts=2
    )
    assert same_owner.decision == DECISION_IN_FLIGHT

    # A different exact claim owner means the old reservation lost custody
    # without a durable outcome.  Ambiguity is terminal for automation.
    after_restart = RepairEffectLedger(queue).reserve(
        identity, owner_token="owner-b", max_unchanged_attempts=2
    )
    assert after_restart.decision == DECISION_INDETERMINATE
    assert after_restart.state == STATE_INDETERMINATE
    again = RepairEffectLedger(queue).reserve(
        identity, owner_token="owner-c", max_unchanged_attempts=2
    )
    assert again.decision == DECISION_INDETERMINATE
    assert again.total_attempts == 1


def test_applied_then_timeout_is_indeterminate_and_never_redriven(tmp_path):
    queue = _queue(tmp_path)
    identity = _identity()
    effects: list[str] = []

    def applied_then_timeout(_occurrence):
        effects.append("external-effect-applied")
        raise TimeoutError("provider response lost")

    first = _run(queue, identity, applied_then_timeout, request="container-a")
    assert not first.delegated
    assert first.simple_fixer_outcome == "indeterminate"

    second = _run(queue, identity, applied_then_timeout, request="container-b")
    assert not second.delegated
    assert second.simple_fixer_outcome == "indeterminate"
    assert effects == ["external-effect-applied"]
    record = RepairEffectLedger(queue).inspect(identity)
    assert record is not None and record.state == STATE_INDETERMINATE
    assert record.total_attempts == 1


def test_invalid_effect_result_is_indeterminate_and_never_redriven(tmp_path):
    queue = _queue(tmp_path)
    identity = _identity()
    calls = 0

    def invalid_result(_occurrence):
        nonlocal calls
        calls += 1
        return None

    first = _run(queue, identity, invalid_result, request="container-a")
    second = _run(queue, identity, invalid_result, request="container-b")
    assert first.simple_fixer_outcome == "indeterminate"
    assert second.simple_fixer_outcome == "indeterminate"
    assert calls == 1


def test_claim_release_does_not_reset_noop_budget_and_distinct_occurrence_is_fresh(tmp_path):
    queue = _queue(tmp_path)
    first_identity = _identity(attempt="1")
    first_key = repair_requests.repair_identity_key(first_identity)
    calls = 0

    def no_op(_occurrence):
        nonlocal calls
        calls += 1
        return first_key

    one = _run(queue, first_identity, no_op, request="claim-1")
    two = _run(queue, first_identity, no_op, request="claim-2")
    three = _run(queue, first_identity, no_op, request="claim-3")
    assert one.simple_fixer_outcome == "unchanged"
    assert two.simple_fixer_outcome == "exhausted"
    assert three.simple_fixer_outcome == "exhausted"
    assert calls == 2
    record = RepairEffectLedger(queue).inspect(first_identity)
    assert record is not None and record.state == STATE_EXHAUSTED
    assert record.total_attempts == 2

    second_identity = _identity(attempt="2")
    fresh = _run(
        queue,
        second_identity,
        lambda occurrence: occurrence.occurrence_fingerprint + ":done",
        request="claim-distinct",
    )
    assert fresh.delegated and fresh.simple_fixer_outcome == "attempted"
    assert repair_requests.repair_identity_key(first_identity) != repair_requests.repair_identity_key(
        second_identity
    )


def test_legacy_forged_and_stale_identity_cannot_reserve(tmp_path):
    ledger = RepairEffectLedger(_queue(tmp_path))
    with pytest.raises(ValueError, match="current normalized repair identity"):
        ledger.reserve(
            {"environment": "label-only"},
            owner_token="owner",
            max_unchanged_attempts=2,
        )

    stale = _identity()
    stale["lease_id"] = ""
    with pytest.raises(ValueError, match="current normalized repair identity"):
        ledger.reserve(stale, owner_token="owner", max_unchanged_attempts=2)

    with pytest.raises(ValueError, match="claim owner"):
        ledger.reserve(_identity(), owner_token="", max_unchanged_attempts=2)
