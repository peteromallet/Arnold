from __future__ import annotations

from pathlib import Path

from arnold_pipelines.megaplan.authority.binding import (
    DispatchIdentity,
    TASK_RESULT_CAPABILITY,
)
from arnold_pipelines.megaplan.execute.wbc import build_execute_batch_dispatch_spec


def _dispatch(*, coordinator_attempt_id: str, fence_token: int) -> DispatchIdentity:
    return DispatchIdentity.create(
        dispatch_id="run-1:execute:batch:1:tasks",
        run_id="run-1",
        run_revision="revision-1",
        coordinator_attempt_id=coordinator_attempt_id,
        fence_token=fence_token,
        subject_ids=("T1",),
        capabilities=(TASK_RESULT_CAPABILITY,),
        prerequisite_digest="prereq-1",
        worker_id="worker-1",
    )


def _spec(tmp_path: Path, dispatch: DispatchIdentity):
    return build_execute_batch_dispatch_spec(
        plan_dir=tmp_path,
        state={},  # type: ignore[arg-type]
        dispatch_identity=dispatch,
        batch_number=1,
        batch_task_ids=["T1"],
        batch_sense_check_ids=[],
    )


def test_execute_wbc_attempt_identity_is_fenced_and_replayable(tmp_path: Path) -> None:
    first = _spec(tmp_path, _dispatch(coordinator_attempt_id="coord-1", fence_token=1))
    replay = _spec(tmp_path, _dispatch(coordinator_attempt_id="coord-1", fence_token=1))
    next_fence = _spec(tmp_path, _dispatch(coordinator_attempt_id="coord-2", fence_token=2))

    assert first.attempt_id == replay.attempt_id
    assert first.start_event.idempotency_key == replay.start_event.idempotency_key
    assert first.start_event.identity.invocation_id == "coord-1"
    assert first.start_event.identity.attempt_ordinal == 1
    assert next_fence.attempt_id != first.attempt_id
    assert next_fence.start_event.idempotency_key != first.start_event.idempotency_key
    assert next_fence.start_event.identity.invocation_id == "coord-2"
    assert next_fence.start_event.identity.attempt_ordinal == 2
