from __future__ import annotations

import json
import signal
import sqlite3
import subprocess
import sys
import time

from tests.helpers import create_store, env_with_fake_model, insert_epic


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
    deadline = time.time() + 5
    while time.time() < deadline:
        conn = sqlite3.connect(db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM bot_turns").fetchone()[0]
        finally:
            conn.close()
        if count:
            break
        time.sleep(0.01)
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

