from __future__ import annotations

import json
from threading import Event

from agent_kit.envelope import serialize_for_diff, stable_json_dumps
from agent_kit.loop import run_turn
from agent_kit.model import FakeModel
from agent_kit.prompts import build_system_prompt
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


def test_no_epic_turn_loads_global_feedback_into_hot_context(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    style = store.create_feedback(
        kind="style",
        content="Keep replies short.",
        source="explicit_save_request",
    )
    observation = store.create_feedback(
        kind="friction",
        content="User had to repeat a section target.",
        source="agent_observation",
        context_snapshot={"user_message": "change X"},
    )
    model = FakeModel(script=[{"final_text": "done", "provider_request_id": "req_1"}])

    envelope = run_turn(
        epic_id=None,
        input="Start a new thing.",
        store=store,
        model=model,
        model_id="fake",
    )

    assert envelope.outcome == "completed"
    assert model.calls[0]["system"] == build_system_prompt(model.calls[0]["hot_context"])
    assert "Keep replies short." in model.calls[0]["system"]
    assert "User had to repeat a section target." in model.calls[0]["system"]
    assert model.calls[0]["hot_context"]["epic"] is None
    assert [row["id"] for row in model.calls[0]["hot_context"]["active_feedback"]] == [
        style["id"]
    ]
    assert [
        row["id"] for row in model.calls[0]["hot_context"]["unresolved_observations"]
    ] == [observation["id"]]
    prompt_snapshot = json.loads(
        conn.execute("SELECT prompt_snapshot FROM bot_turns").fetchone()["prompt_snapshot"]
    )
    assert prompt_snapshot["hot_context"]["active_feedback_count"] == 1
    assert prompt_snapshot["hot_context"]["unresolved_observation_count"] == 1
    assert prompt_snapshot["hot_context"]["recent_message_count"] == 0
    assert prompt_snapshot["hot_context"]["recent_tool_call_count"] == 0


def test_empty_model_response_without_progress_remains_error(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    envelope = run_turn(
        epic_id=None,
        input="hello",
        store=store,
        model=FakeModel(script=[{"final_text": "", "provider_request_id": "req_1"}]),
        model_id="fake",
    )

    assert envelope.outcome == "errored"
    assert envelope.error is not None
    assert envelope.error.code == "empty_model_response"
    assert envelope.reply == ""
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM system_logs WHERE event_type = ?",
            ("end_of_turn_empty_response",),
        ).fetchone()[0]
        == 1
    )


def test_end_of_turn_default_ack_after_substantive_tool_work(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    envelope = run_turn(
        epic_id=None,
        input="save this: keep messages under 200 words",
        store=store,
        model=FakeModel(
            script=[
                {
                    "tool_requests": [
                        {
                            "name": "save_feedback",
                            "arguments": {
                                "kind": "style",
                                "content": "Keep messages under 200 words.",
                                "source": "explicit_save_request",
                            },
                        }
                    ],
                    "provider_request_id": "req_1",
                },
                {"final_text": "", "provider_request_id": "req_2"},
            ]
        ),
        model_id="fake",
    )

    assert envelope.outcome == "completed"
    assert envelope.reply == "Done."
    assert [
        row["tool_name"]
        for row in conn.execute(
            "SELECT tool_name FROM tool_calls ORDER BY rowid"
        ).fetchall()
    ] == ["save_feedback", "send_message"]
    assert [
        row["event_type"]
        for row in conn.execute(
            """
            SELECT event_type FROM system_logs
            WHERE event_type LIKE 'end_of_turn_%'
            ORDER BY rowid
            """
        ).fetchall()
    ] == ["end_of_turn_no_message_sent", "end_of_turn_empty_response"]


def test_end_of_turn_logs_body_unchanged_when_expected(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    envelope = run_turn(
        epic_id="epic_1",
        input="change the part about scope",
        store=store,
        model=FakeModel(script=[{"final_text": "I checked it.", "provider_request_id": "req_1"}]),
        model_id="fake",
    )

    assert envelope.outcome == "completed"
    assert envelope.reply == "I checked it."
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM system_logs WHERE event_type = ?",
            ("end_of_turn_body_unchanged_when_expected",),
        ).fetchone()[0]
        == 1
    )


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
