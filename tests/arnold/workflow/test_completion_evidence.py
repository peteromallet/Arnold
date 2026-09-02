"""Focused C2 evidence-coordinate contract tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from arnold.workflow.completion.evidence import (
    CursorVector,
    EvidenceScope,
    EvidenceScopeMismatch,
    EvidenceWindow,
    ScalarCursor,
    admit_evidence,
    scope_matches,
)


def _scope(**changes):
    values = {
        "subject_id": "subject:1",
        "occurrence_id": "occurrence:1",
        "attempt_id": "attempt:1",
        "generation": 1,
        "source_lock": "source:v1",
        "runtime_lock": "runtime:v1",
        "dependency_lock": "deps:v1",
        "store_id": "store:primary",
        "store_incarnation": "incarnation:1",
        "restore_id": "restore:1",
        "restore_generation": 1,
        "evidence_window": EvidenceWindow(ScalarCursor(10), ScalarCursor(20)),
        "custody": {"run_id": "run:1", "receipt": "sha256:" + "a" * 64},
        "authority_fence": {"token": 4, "epoch": 2},
        "epoch": 2,
        "wbc_version": "wbc:v1",
        "admitted_child_set_digest": "sha256:" + "b" * 64,
    }
    values.update(changes)
    return EvidenceScope(**values)


def test_scalar_and_vector_cursors_are_ordered_and_content_addressed() -> None:
    first = ScalarCursor(position=3, inclusive=True, stream="events")
    second = ScalarCursor.from_dict(first.to_dict())
    assert second == first
    vector = CursorVector({"events": first, "effects": ScalarCursor(8)})
    assert CursorVector.from_dict(vector.to_dict()) == vector
    assert vector.vector_hash != CursorVector({"events": first, "effects": ScalarCursor(9)}).vector_hash


def test_window_boundaries_and_hash_include_inclusive_semantics() -> None:
    inclusive = EvidenceWindow(ScalarCursor(1), ScalarCursor(4), end_inclusive=True)
    exclusive = EvidenceWindow(ScalarCursor(1), ScalarCursor(4), end_inclusive=False)
    assert inclusive.contains(ScalarCursor(4))
    assert not exclusive.contains(ScalarCursor(4))
    assert inclusive.window_hash != exclusive.window_hash


def test_scope_hash_covers_every_replay_coordinate() -> None:
    base = _scope()
    fields = (
        "subject_id", "occurrence_id", "attempt_id", "generation", "source_lock",
        "runtime_lock", "dependency_lock", "store_id", "store_incarnation", "restore_id",
        "restore_generation", "custody", "authority_fence", "epoch", "wbc_version",
        "admitted_child_set_digest",
    )
    for field in fields:
        value = getattr(base, field)
        replacement = (value + ":changed") if isinstance(value, str) else (value + 1 if isinstance(value, int) else {"changed": True})
        payload = base.to_dict()
        payload["scope_hash"] = ""
        payload[field] = replacement
        assert EvidenceScope(**payload).scope_hash != base.scope_hash


def test_cross_scope_admission_rejects_without_time() -> None:
    base = _scope()
    with pytest.raises(EvidenceScopeMismatch, match="store_incarnation"):
        admit_evidence(base, _scope(store_incarnation="incarnation:2"))
    with pytest.raises(EvidenceScopeMismatch, match="cursor"):
        admit_evidence(base, base, cursor=ScalarCursor(21))
    assert not scope_matches(base, _scope(runtime_lock="runtime:v2"))


def test_scope_and_cursor_records_are_immutable_and_reject_clock_authority() -> None:
    with pytest.raises(ValueError, match="wall-clock"):
        ScalarCursor("2026-08-31T00:00:00Z")
    scope = _scope()
    with pytest.raises(FrozenInstanceError):
        scope.subject_id = "other"  # type: ignore[misc]
    with pytest.raises(ValueError, match="wall-clock"):
        EvidenceWindow("2026-08-31T00:00:00Z", ScalarCursor(2))
