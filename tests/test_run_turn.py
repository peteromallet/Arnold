from __future__ import annotations

import json
from threading import Event

from agent_kit.envelope import serialize_for_diff, stable_json_dumps
from agent_kit.loop import run_turn
from agent_kit.model import FakeModel
from tests.helpers import create_store, insert_epic


def test_run_turn_tool_flow_events_join_tool_calls(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    seen = []
    envelope = run_turn(
        epic_id="epic_1",
        input="hello",
        store=store,
        model=FakeModel(
            script=[
                {
                    "tool_requests": [
                        {
                            "name": "set_activity",
                            "arguments": {"description": "drafting"},
                        }
                    ],
                    "provider_request_id": "req_1",
                },
                {"final_text": "done", "provider_request_id": "req_2"},
            ]
        ),
        model_id="fake",
        on_event=seen.append,
    )
    assert envelope.outcome == "completed"
    assert envelope.reply == "done"
    assert seen == envelope.events
    assert [event.kind for event in envelope.events] == ["activity", "tool_call"]
    tool_calls = conn.execute("SELECT * FROM tool_calls").fetchall()
    assert len(tool_calls) == 2
    assert {row["id"] for row in tool_calls} == {
        event.tool_call_id for event in envelope.events
    }
    assert conn.execute("SELECT COUNT(*) FROM bot_turns").fetchone()[0] == 1


def test_state_delta_deterministic_for_same_input_and_seed(tmp_path) -> None:
    deltas = []
    for index in range(2):
        store, conn = create_store(tmp_path / f"arnold_{index}.db")
        insert_epic(conn)
        envelope = run_turn(
            epic_id="epic_1",
            input="same",
            store=store,
            model=FakeModel(seed="same"),
            model_id="fake",
        )
        deltas.append(stable_json_dumps(envelope.state_delta))
    assert deltas[0] == deltas[1]


def test_python_and_cli_diff_projection_match(tmp_path) -> None:
    from subprocess import run
    import sys

    script = [{"final_text": "same reply", "provider_request_id": "req_1"}]
    py_store, py_conn = create_store(tmp_path / "python.db")
    cli_store, cli_conn = create_store(tmp_path / "cli.db")
    insert_epic(py_conn)
    insert_epic(cli_conn)
    py_envelope = run_turn(
        epic_id="epic_1",
        input="hello",
        store=py_store,
        model=FakeModel(script=script),
        model_id="fake",
    )
    result = run(
        [
            sys.executable,
            "-m",
            "arnold.cli",
            "turn",
            "--epic",
            "epic_1",
            "--input",
            "hello",
            "--db",
            str(tmp_path / "cli.db"),
            "--model-id",
            "fake",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={
            **__import__("os").environ,
            "ARNOLD_FAKE_MODEL_SCRIPT": json.dumps(script),
        },
    )
    assert result.returncode == 0, result.stderr
    cli_envelope = json.loads(result.stdout)
    py_projection = py_envelope.to_dict()
    py_projection["turn_id"] = cli_envelope["turn_id"]
    for py_event, cli_event in zip(
        py_projection["events"],
        cli_envelope["events"],
        strict=True,
    ):
        py_event["ts"] = cli_event["ts"]
        py_event["tool_call_id"] = cli_event["tool_call_id"]
    assert serialize_for_diff(py_projection) == serialize_for_diff(cli_envelope)


def test_streaming_events_match_envelope_events(tmp_path) -> None:
    from subprocess import run
    import sys

    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    store.close()
    script = [
        {
            "tool_requests": [
                {"name": "set_activity", "arguments": {"description": "drafting"}}
            ],
            "provider_request_id": "req_1",
        },
        {"final_text": "done", "provider_request_id": "req_2"},
    ]
    result = run(
        [
            sys.executable,
            "-m",
            "arnold.cli",
            "turn",
            "--epic",
            "epic_1",
            "--input",
            "hello",
            "--db",
            str(tmp_path / "arnold.db"),
            "--model-id",
            "fake",
            "--stream-events",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={
            **__import__("os").environ,
            "ARNOLD_FAKE_MODEL_SCRIPT": json.dumps(script),
        },
    )
    assert result.returncode == 0, result.stderr
    envelope = json.loads(result.stdout)
    streamed = [json.loads(line) for line in result.stderr.splitlines()]
    assert streamed == envelope["events"]
    assert [event["kind"] for event in streamed] == ["activity", "tool_call"]


def test_abort_marks_turn_abandoned_and_returns_aborted(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    cancel_event = Event()
    cancel_event.set()
    envelope = run_turn(
        epic_id="epic_1",
        input="hello",
        store=store,
        model=FakeModel(script=[{"final_text": "unused"}]),
        model_id="fake",
        cancel_event=cancel_event,
    )
    assert envelope.outcome == "aborted"
    turn = conn.execute("SELECT status FROM bot_turns").fetchone()
    assert turn["status"] == "abandoned"


def test_set_activity_event_shape_has_no_duplicate_tool_event(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    envelope = run_turn(
        epic_id="epic_1",
        input="hello",
        store=store,
        model=FakeModel(
            script=[
                {
                    "tool_requests": [
                        {
                            "name": "set_activity",
                            "arguments": {"description": "drafting"},
                        }
                    ],
                    "provider_request_id": "req_1",
                },
                {"final_text": "done", "provider_request_id": "req_2"},
            ]
        ),
        model_id="fake",
    )
    activity_events = [
        event for event in envelope.events if event.name == "set_activity"
    ]
    assert len(activity_events) == 1
    assert activity_events[0].kind == "activity"
    assert activity_events[0].text == "drafting"
    assert activity_events[0].tool_call_id
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM tool_calls WHERE id = ?",
            (activity_events[0].tool_call_id,),
        ).fetchone()[0]
        == 1
    )
    assert not [
        event
        for event in envelope.events
        if event.name == "set_activity" and event.kind == "tool_call"
    ]
