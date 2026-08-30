from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.worker_dispatch import (
    WorkerAdmissionRequest,
    build_authorized_linked_child_request,
)

from tests.cloud.dispatch_test_helpers import request


def test_linked_child_requires_terminal_parent_and_new_logical_id(tmp_path: Path) -> None:
    parent = request(tmp_path)
    child = build_authorized_linked_child_request(
        {**parent.__dict__, "terminal_outcome_event_id": "terminal"},
        selected_spec=parent.selected_spec,
        logical_dispatch_id="child",
        authorizing_event_id="authorization",
    )
    assert isinstance(child, WorkerAdmissionRequest)
    assert child.parent_logical_dispatch_id == parent.logical_dispatch_id
    assert child.authorizing_event_id == "authorization"


def test_linked_child_rejects_unresolved_parent(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no-launch or unresolved"):
        build_authorized_linked_child_request(
            {"kind": "unresolved_launch"},
            selected_spec="codex:gpt-5.5",
            logical_dispatch_id="child",
            authorizing_event_id="authorization",
        )
