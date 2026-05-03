from __future__ import annotations

import json
import signal
import sqlite3
import subprocess
import sys
import time

from tests.helpers import create_store, env_with_fake_model, insert_epic

PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"


def _prepare_db(path, epic_id: str) -> None:
    store, conn = create_store(path)
    insert_epic(conn, epic_id)
    store.close()


def _run_cli(tmp_path, epic_id: str, script: list[dict], *extra: str):
    db_path = tmp_path / f"{epic_id}.db"
    _prepare_db(db_path, epic_id)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "arnold.cli",
            "turn",
            "--epic",
            epic_id,
            "--input",
            "hello",
            "--db",
            str(db_path),
            "--model-id",
            "fake",
            *extra,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env_with_fake_model(script),
    )


def test_cli_exit_codes_and_stdout_envelopes(tmp_path) -> None:
    completed = _run_cli(
        tmp_path,
        "epic_completed",
        [{"final_text": "done", "provider_request_id": "req_1"}],
    )
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["outcome"] == "completed"

    errored = _run_cli(
        tmp_path,
        "epic_errored",
        [{"provider_error": True, "error_details": {"code": "bad"}}],
    )
    assert errored.returncode == 1
    assert json.loads(errored.stdout)["outcome"] == "errored"

    blocked = _run_cli(
        tmp_path,
        "epic_blocked",
        [
            {
                "tool_requests": [
                    {
                        "name": "defer_to_caller",
                        "arguments": {"questions": ["Which scope?"]},
                    }
                ],
                "provider_request_id": "req_1",
            }
        ],
    )
    assert blocked.returncode == 2
    blocked_envelope = json.loads(blocked.stdout)
    assert blocked_envelope["outcome"] == "blocked_on_caller"
    assert blocked_envelope["questions"] == ["Which scope?"]


def test_cli_abort_exit_code_and_abandoned_turn(tmp_path) -> None:
    db_path = tmp_path / "abort.db"
    _prepare_db(db_path, "epic_abort")
    script = [
        {
            "tool_requests": [
                {
                    "name": "set_activity",
                    "arguments": {"description": f"step {index}"},
                }
                for index in range(2000)
            ],
            "provider_request_id": "req_1",
        }
    ]
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "arnold.cli",
            "turn",
            "--epic",
            "epic_abort",
            "--input",
            "hello",
            "--db",
            str(db_path),
            "--model-id",
            "fake",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env_with_fake_model(script),
    )
    started = False
    deadline = time.time() + 20
    while time.time() < deadline:
        conn = sqlite3.connect(db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM bot_turns").fetchone()[0]
        finally:
            conn.close()
        if count:
            started = True
            break
        time.sleep(0.01)
    assert started, "CLI subprocess did not create a turn before the interrupt deadline"
    proc.send_signal(signal.SIGINT)
    stdout, stderr = proc.communicate(timeout=10)
    assert proc.returncode == 3, stderr
    envelope = json.loads(stdout)
    assert envelope["outcome"] == "aborted"
    conn = sqlite3.connect(db_path)
    try:
        status = conn.execute("SELECT status FROM bot_turns").fetchone()[0]
    finally:
        conn.close()
    assert status == "abandoned"


def test_cli_attach_ingests_image_for_sqlite_epic(tmp_path) -> None:
    db_path = tmp_path / "attach.db"
    image_path = tmp_path / "upload.png"
    image_path.write_bytes(PNG_BYTES)
    _prepare_db(db_path, "epic_attach")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "arnold.cli",
            "turn",
            "--epic",
            "epic_attach",
            "--input",
            "look at this",
            "--attach",
            str(image_path),
            "--db",
            str(db_path),
            "--model-id",
            "fake",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env_with_fake_model([{"final_text": "seen", "provider_request_id": "req_1"}]),
    )

    assert completed.returncode == 0, completed.stderr
    envelope = json.loads(completed.stdout)
    assert envelope["outcome"] == "completed"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        image = conn.execute("SELECT * FROM images").fetchone()
        inbound = conn.execute(
            "SELECT * FROM messages WHERE direction = 'inbound'"
        ).fetchone()
    finally:
        conn.close()
    assert image["epic_id"] == "epic_attach"
    assert image["source"] == "caller_uploaded"
    assert image["storage_url"].startswith("images/epic_attach/")
    assert (tmp_path / "attach.db.blobs" / image["storage_url"]).is_file()
    assert inbound["has_image_attachment"] == 1


def test_cli_attach_without_epic_returns_envelope_error_without_state(tmp_path) -> None:
    db_path = tmp_path / "attach-no-epic.db"
    image_path = tmp_path / "upload.png"
    image_path.write_bytes(PNG_BYTES)

    errored = subprocess.run(
        [
            sys.executable,
            "-m",
            "arnold.cli",
            "turn",
            "--input",
            "look at this",
            "--attach",
            str(image_path),
            "--db",
            str(db_path),
            "--model-id",
            "fake",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env_with_fake_model([{"final_text": "unused", "provider_request_id": "req_1"}]),
    )

    assert errored.returncode == 1
    envelope = json.loads(errored.stdout)
    assert envelope["outcome"] == "errored"
    assert envelope["error"]["code"] == "attachments_require_epic"
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM images").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM bot_turns").fetchone()[0] == 0
    finally:
        conn.close()
    assert not (tmp_path / "attach-no-epic.db.blobs").exists()
