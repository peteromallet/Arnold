from __future__ import annotations

import pytest

from megaplan.worktrees import (
    TaskIdentityError,
    build_task_identity_map,
    decode_original_task_id,
    encode_original_task_id,
    identity_map_payload,
    make_task_identity,
    validate_trailer_identity,
)


def test_task_identity_handles_path_unicode_control_shell_and_trailer_chars() -> None:
    raw_ids = [
        "src/../../T:1",
        "unicodé/任务",
        "control\nTask\t2",
        "shell;$(rm -rf .)",
        "Trailer: Value\nTask-Key: injected",
    ]

    identity_map = build_task_identity_map(
        [{"id": raw_id, "status": "pending"} for raw_id in raw_ids]
    )

    assert set(identity_map) == set(raw_ids)
    task_keys = [identity.task_key for identity in identity_map.values()]
    assert len(task_keys) == len(set(task_keys))
    for raw_id, identity in identity_map.items():
        assert "/" not in identity.task_key
        assert "\\" not in identity.task_key
        assert "\n" not in identity.task_key
        assert ":" not in identity.task_key
        assert identity.task_key == identity.task_key.lower()
        assert decode_original_task_id(identity.original_task_id_encoded) == raw_id
        trailers = identity.trailer_fields()
        assert trailers["Task-Key"] == identity.task_key
        assert raw_id not in trailers.values()
        assert validate_trailer_identity(trailers, identity_map) == identity


def test_task_identity_payload_contains_registry_safe_metadata_only() -> None:
    raw_id = "Task-Key: raw\nT/7"
    identity = make_task_identity(raw_id)
    payload = identity_map_payload({raw_id: identity})

    assert payload[raw_id] == identity.registry_identity()
    registry_identity = payload[raw_id]
    assert registry_identity["task_key"] == identity.task_key
    assert registry_identity["original_task_id_encoded"] == encode_original_task_id(raw_id)
    assert raw_id not in registry_identity.values()


def test_task_identity_rejects_unicode_normalized_duplicate_task_ids() -> None:
    with pytest.raises(TaskIdentityError) as excinfo:
        build_task_identity_map(
            [
                {"id": "é", "status": "pending"},
                {"id": "e\u0301", "status": "pending"},
            ]
        )

    assert excinfo.value.code == "duplicate_normalized_task_id"


def test_task_identity_rejects_mismatched_trailer_key() -> None:
    identity_map = build_task_identity_map([{"id": "T1", "status": "pending"}])
    identity = identity_map["T1"]
    trailers = identity.trailer_fields()
    trailers["Task-Key"] = "wrong-key"

    with pytest.raises(TaskIdentityError) as excinfo:
        validate_trailer_identity(trailers, identity_map)

    assert excinfo.value.code == "task_key_mismatch"
