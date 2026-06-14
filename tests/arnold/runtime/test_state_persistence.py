from __future__ import annotations

import json
from pathlib import Path

from arnold.runtime import (
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
    runtime_state_lock,
)


def test_atomic_write_helpers_create_parent_directories(tmp_path: Path) -> None:
    byte_path = tmp_path / "nested" / "data.bin"
    text_path = tmp_path / "nested" / "data.txt"
    json_path = tmp_path / "nested" / "data.json"

    atomic_write_bytes(byte_path, b"bytes")
    atomic_write_text(text_path, "text")
    atomic_write_json(json_path, {"b": 2, "a": 1})

    assert byte_path.read_bytes() == b"bytes"
    assert text_path.read_text(encoding="utf-8") == "text"
    assert json.loads(json_path.read_text(encoding="utf-8")) == {"a": 1, "b": 2}


def test_runtime_state_lock_creates_lock_file(tmp_path: Path) -> None:
    lock_path = tmp_path / "locks" / "state.lock"

    with runtime_state_lock(lock_path):
        assert lock_path.exists()
