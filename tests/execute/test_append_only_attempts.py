"""Step 15: append-only attempt receipts across fences.

These tests exercise ``_stamp_result_envelopes`` directly because that is the
single function that (a) hands a dispatched batch's task/sense-check receipts a
stable ``attempt_id`` and (b) is called again when a later fence re-stamps the
same checkpoint.  The three guarantees from Step 15 are:

* fence-N receipts stay byte-addressable by their stable ``attempt_id`` after a
  later fence N+1 re-stamps the checkpoint (they are carried into
  ``prior_result_envelopes`` rather than dropped or overwritten);
* a subject that already holds an *accepted* receipt (done/completed/skipped) is
  never re-executed — it lands in ``append_only_attempts.skipped_reexecutions``
  and receives no new envelope; and
* the accepted receipt's original bytes (its status and attempt address) are
  never overwritten by the later fence.

The authority here is built only from the versioned ``DispatchIdentity`` (the
grant/fence record persisted beside the scope).  No labels, liveness, WBC
receipts, or rebuildable projections are used to create or widen authority.
"""

from __future__ import annotations

from pathlib import Path

from arnold_pipelines.megaplan.authority.batch_scope import RESULT_ENVELOPES_KEY
from arnold_pipelines.megaplan.authority.binding import (
    DispatchIdentity,
    TASK_RESULT_CAPABILITY,
)
from arnold_pipelines.megaplan.execute.batch import (
    PRIOR_RESULT_ENVELOPES_KEY,
    _stamp_result_envelopes,
)

_SUBJECT_IDS = ("T1", "T2", "T3")
_CAPABILITIES = (TASK_RESULT_CAPABILITY,)


def _identity(*, fence_token: int) -> DispatchIdentity:
    """A distinct dispatch identity per fence token.

    A later fence has both a new ``fence_token`` and a new ``dispatch_id`` so the
    identity digest differs and the resolver can tell fence-N receipts apart
    from fence-(N+1) receipts.
    """

    return DispatchIdentity.create(
        dispatch_id=f"dispatch-fence-{fence_token}",
        run_id="run-1",
        run_revision="revision-1",
        coordinator_attempt_id="coordinator-1",
        fence_token=fence_token,
        subject_ids=_SUBJECT_IDS,
        capabilities=_CAPABILITIES,
        prerequisite_digest="prereq-1",
        worker_id="worker-1",
    )


def _task_entry(task_id: str, status: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "status": status,
        "executor_notes": f"{task_id} {status}",
        "files_changed": [],
        "commands_run": [],
    }


def _attempt_id_of(envelope: dict[str, object]) -> str | None:
    attempt = envelope.get("attempt")
    if isinstance(attempt, dict):
        value = attempt.get("attempt_id")
        if isinstance(value, str):
            return value
    return None


def _status_of(envelope: dict[str, object]) -> str | None:
    evidence = envelope.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return None
    head = evidence[0]
    if not isinstance(head, dict):
        return None
    payload = head.get("payload")
    if not isinstance(payload, dict):
        return None
    result = payload.get("result")
    if not isinstance(result, dict):
        return None
    status = result.get("status")
    return status if isinstance(status, str) else None


def _subject_of(envelope: dict[str, object]) -> str | None:
    attempt = envelope.get("attempt")
    if isinstance(attempt, dict):
        value = attempt.get("subject_id")
        if isinstance(value, str):
            return value
    return None


def _fence_1_payload() -> dict[str, object]:
    """Fence 1: T1 and T3 are accepted (done); T2 is blocked (retryable)."""

    return {
        "task_updates": [
            _task_entry("T1", "done"),
            _task_entry("T2", "blocked"),
            _task_entry("T3", "done"),
        ],
        "sense_check_acknowledgments": [],
    }


_ARTIFACT_PATH = Path("execute_checkpoints/attempt_1/batch_1/tasks_deadbeefdead.json")


def test_prior_fence_receipts_remain_byte_addressable_after_refence() -> None:
    """fence-N receipts stay addressable by their stable attempt_id after N+1."""

    identity_1 = _identity(fence_token=1)
    payload = _fence_1_payload()

    _stamp_result_envelopes(payload, identity=identity_1, artifact_path=_ARTIFACT_PATH)

    fence_1_envelopes = list(payload[RESULT_ENVELOPES_KEY])  # type: ignore[arg-type]
    assert len(fence_1_envelopes) == 3
    # Every fence-1 receipt has a stable, unique attempt address.
    fence_1_attempt_ids = {
        _subject_of(env): _attempt_id_of(env) for env in fence_1_envelopes
    }
    assert set(fence_1_attempt_ids) == {"T1", "T2", "T3"}
    assert len(set(fence_1_attempt_ids.values())) == 3

    # A later fence re-stamps the same checkpoint.
    identity_2 = _identity(fence_token=2)
    payload["task_updates"] = [
        _task_entry("T1", "done"),
        _task_entry("T2", "done"),
        _task_entry("T3", "done"),
    ]
    new_envelopes = _stamp_result_envelopes(
        payload, identity=identity_2, artifact_path=_ARTIFACT_PATH
    )

    prior = list(payload.get(PRIOR_RESULT_ENVELOPES_KEY, []))
    # fence-1 receipts survive in prior_result_envelopes, addressable by the
    # exact same stable attempt_id they were stamped with under fence 1.
    prior_attempt_ids = {
        _subject_of(env): _attempt_id_of(env) for env in prior if isinstance(env, dict)
    }
    for subject, attempt_id in fence_1_attempt_ids.items():
        assert prior_attempt_ids[subject] == attempt_id, (
            f"fence-1 receipt for {subject} lost its byte address after fence N+1"
        )

    # result_envelopes keeps ONLY envelopes bound to the current (fence-2)
    # identity, so the authority resolver stays a single-identity proof.
    current = payload[RESULT_ENVELOPES_KEY]
    assert isinstance(current, list)
    for env in current:
        assert _subject_of(env) != "T1"  # T1 was accepted -> not re-stamped
    # Ordinals continue from the highest persisted value, so no address collides
    # with a fence-1 attempt address.
    all_new_ordinals = sorted(env.attempt.ordinal for env in new_envelopes)
    fence_1_ordinals = sorted(
        env.get("attempt", {}).get("ordinal")  # type: ignore[union-attr]
        for env in fence_1_envelopes
        if isinstance(env, dict) and isinstance(env.get("attempt"), dict)
    )
    assert all(ordinal > max(fence_1_ordinals) for ordinal in all_new_ordinals)


def test_accepted_receipts_are_not_reexecuted_or_overwritten() -> None:
    """Accepted subjects are never re-executed and their receipts are preserved."""

    identity_1 = _identity(fence_token=1)
    payload = _fence_1_payload()

    _stamp_result_envelopes(payload, identity=identity_1, artifact_path=_ARTIFACT_PATH)

    identity_2 = _identity(fence_token=2)
    # Fence 2 tries to re-execute T1 and T3 (already accepted) and to flip T2
    # from blocked to done.  Only T2 should be re-stamped.
    payload["task_updates"] = [
        _task_entry("T1", "done"),
        _task_entry("T2", "done"),
        _task_entry("T3", "done"),
    ]
    new_envelopes = _stamp_result_envelopes(
        payload, identity=identity_2, artifact_path=_ARTIFACT_PATH
    )

    skipped = payload.get("append_only_attempts", {}).get("skipped_reexecutions", [])
    assert sorted(skipped) == ["T1", "T3"]

    # Only T2 (the retryable blocked task) received a new envelope under fence 2.
    new_subjects = {env.attempt.subject_id for env in new_envelopes}
    assert new_subjects == {"T2"}

    # The accepted receipts for T1 and T3 are NOT overwritten: their original
    # accepted status survives unchanged in the carried prior store, and they
    # do not appear in the current result_envelopes at all.
    current = payload[RESULT_ENVELOPES_KEY]
    assert isinstance(current, list)
    current_subjects = {_subject_of(env) for env in current if isinstance(env, dict)}
    assert "T1" not in current_subjects
    assert "T3" not in current_subjects

    prior = payload.get(PRIOR_RESULT_ENVELOPES_KEY, [])
    assert isinstance(prior, list)
    prior_status_by_subject = {
        _subject_of(env): _status_of(env) for env in prior if isinstance(env, dict)
    }
    assert prior_status_by_subject["T1"] == "done"
    assert prior_status_by_subject["T3"] == "done"
    # T2's blocked fence-1 attempt is also preserved as history (byte-addressable
    # append-only receipt), distinct from its new accepted fence-2 receipt.
    assert prior_status_by_subject["T2"] == "blocked"
