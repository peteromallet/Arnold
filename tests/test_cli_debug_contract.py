from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.cli import build_parser
from vibecomfy.comfy_nodes.agent.contracts import DiagnosticRecord
from vibecomfy.comfy_nodes.agent.session import iter_turn_records


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture()
def editor_sessions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    comfy = tmp_path / "ComfyUI"
    repo = tmp_path / "vibecomfy"
    root = comfy / "out" / "editor_sessions"
    turn_dir = root / "abc123session" / "turns" / "0001"
    _write_json(
        root / "abc123session" / "session_state.json",
        {
            "baseline_turn_id": "0001",
            "turns": {
                "0001": {
                    "state": "accepted",
                    "agent_edit_protocol": "v2",
                    "accepted_at": "2026-06-03T12:00:00",
                    "submitted_client_live_canvas_token": "live:1:hash",
                }
            },
        },
    )
    _write_json(
        turn_dir / "request.json",
        {"task": "make it brighter", "route": "agent-edit"},
    )
    _write_json(
        turn_dir / "response.json",
        {
            "ok": True,
            "graph": {"nodes": [{"id": 1}, {"id": 2}]},
            "gates": {
                "ui_fidelity_ok": True,
                "state_match_ok": True,
                "queue_validate_ok": True,
            },
            "canvas_apply_allowed": True,
            "queue_allowed": False,
            "done_summary": "Added a sampler.",
        },
    )
    monkeypatch.setenv("COMFY_DIR", str(comfy))
    monkeypatch.setenv("VIBECOMFY_REPO", str(repo))
    monkeypatch.setenv("VIBECOMFY_PORT", "65530")
    return root


def _run_cli(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


def test_iter_turn_records_yields_diagnostic_records(editor_sessions: Path) -> None:
    records = list(iter_turn_records(editor_sessions, "abc123session"))
    assert len(records) == 1
    record = records[0]
    assert isinstance(record, DiagnosticRecord)
    assert record.session_id == "abc123session"
    assert record.turn_id == "0001"
    assert record.ok is True
    assert record.lifecycle == "accepted"
    assert record.outcome == "✅ APPLIED"
    assert record.candidate_nodes == 2
    assert record.task == "make it brighter"
    assert record.route == "agent-edit"
    assert record.fidelity_ok is True


def test_cli_iter_turns_matches_diagnostic_records(
    editor_sessions: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run_cli(["debug", "log", "--json"]) == 0
    cli_rows = json.loads(capsys.readouterr().out)
    assert len(cli_rows) == 1

    records = list(iter_turn_records(editor_sessions, "abc123session"))
    record = records[0]
    row = cli_rows[0]
    assert row["session"] == record.session_id
    assert row["turn"] == record.turn_id
    assert row["outcome"] == record.outcome
    assert row["task"] == record.task
    assert row["route"] == record.route
    assert row["fid"] == record.fidelity_ok
    assert row["cand_nodes"] == record.candidate_nodes


def test_iter_turn_records_ignores_missing_session(editor_sessions: Path) -> None:
    records = list(iter_turn_records(editor_sessions, "no-such-session"))
    assert records == []


def test_diagnostic_record_from_dict_ignores_unknown_fields() -> None:
    payload = {
        "session_id": "s",
        "turn_id": "t",
        "unknown_future_field": "ignored",
    }
    record = DiagnosticRecord.from_dict(payload)
    assert record.session_id == "s"
    assert record.turn_id == "t"
    assert record.to_dict()["session_id"] == "s"
