from __future__ import annotations

import os

from arnold_pipelines.megaplan.chain import (
    _plan_has_live_active_step as legacy_chain_has_live_active_step,
)
from arnold_pipelines.megaplan.supervisor.chain_runner import (
    _plan_has_live_active_step as supervisor_has_live_active_step,
)


def _classifiers() -> tuple:
    return (legacy_chain_has_live_active_step, supervisor_has_live_active_step)


def test_dead_pid_does_not_make_active_step_live() -> None:
    state = {
        "active_step": {
            "phase": "execute",
            "worker_pid": -1,
            "session_id": "resumable-model-session-is-not-liveness",
        }
    }

    assert all(classifier(state) is False for classifier in _classifiers())


def test_phase_or_session_presence_without_pid_is_not_liveness() -> None:
    state = {"active_step": {"phase": "review", "session_id": "session-123"}}

    assert all(classifier(state) is False for classifier in _classifiers())


def test_current_process_pid_makes_active_step_live() -> None:
    state = {"active_step": {"phase": "execute", "worker_pid": os.getpid()}}

    assert all(classifier(state) is True for classifier in _classifiers())
