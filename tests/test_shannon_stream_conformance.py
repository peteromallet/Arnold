"""Opt-in live conformance tests for Claude native stream-json.

These tests intentionally require local operator opt-in because they depend on a
logged-in Claude Code CLI. Normal unit and CI runs skip the whole module.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from megaplan.workers.shannon_stream import parse_shannon_stream_output


pytestmark = [
    pytest.mark.conformance,
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("MEGAPLAN_SHANNON_STREAM_CONFORMANCE") != "1",
        reason="set MEGAPLAN_SHANNON_STREAM_CONFORMANCE=1 to run live Claude stream conformance",
    ),
]


def _claude_binary() -> str:
    configured = os.environ.get("MEGAPLAN_SHANNON_STREAM_CLAUDE_BIN", "").strip()
    candidate = configured or shutil.which("claude")
    if not candidate:
        pytest.skip("claude binary is not available on PATH")
    return candidate


def _stream_user_message(prompt: str) -> str:
    return json.dumps(
        {"type": "user", "message": {"role": "user", "content": prompt}},
        separators=(",", ":"),
    )


def _event_type(event: dict[str, Any]) -> str:
    for key in ("type", "event", "event_type", "eventType", "kind", "name"):
        value = event.get(key)
        if value is not None:
            return str(value).strip().lower().replace("-", "_")
    message = event.get("message")
    if isinstance(message, dict) and message.get("role") is not None:
        return str(message["role"]).strip().lower().replace("-", "_")
    return "unknown"


def _decode_ndjson(raw: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        decoded = json.loads(line)
        assert isinstance(decoded, dict), f"line {line_number} was not a JSON object"
        events.append(decoded)
    assert events, "claude emitted no stream-json events"
    return events


def _run_claude_stream(
    tmp_path: Path,
    prompt: str,
    *,
    bypass_permissions: bool = False,
) -> subprocess.CompletedProcess[str]:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    claude_config_dir = tmp_path / "claude_config"
    claude_config_dir.mkdir()
    (claude_config_dir / "settings.json").write_text(
        json.dumps({"autoUpdates": False}) + "\n",
        encoding="utf-8",
    )

    command = [
        _claude_binary(),
        "--print",
        "--input-format=stream-json",
        "--output-format=stream-json",
    ]
    if bypass_permissions:
        command.extend(["--permission-mode", "bypassPermissions"])

    env = os.environ.copy()
    env["ANTHROPIC_API_KEY"] = ""
    env["CLAUDE_CONFIG_DIR"] = str(claude_config_dir)
    env["DISABLE_AUTOUPDATER"] = "1"
    env["CLAUDE_CODE_DISABLE_AUTOUPDATER"] = "1"
    env["CLAUDE_DISABLE_AUTOUPDATER"] = "1"

    completed = subprocess.run(
        command,
        cwd=project_dir,
        env=env,
        input=_stream_user_message(prompt),
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, (
        f"claude stream conformance failed with exit code {completed.returncode}\n"
        f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}"
    )
    return completed


def test_live_claude_stream_json_schema_contract(tmp_path: Path) -> None:
    completed = _run_claude_stream(
        tmp_path,
        "Return exactly this JSON object and no markdown: "
        '{"conformance":"schema","ok":true}',
    )

    events = _decode_ndjson(completed.stdout)
    event_types = {_event_type(event) for event in events}
    assert "init" in event_types or "system_init" in event_types
    assert "result" in event_types

    for event in events:
        event_type = _event_type(event)
        if event_type in {"init", "system_init", "assistant", "result", "rate_limit_event"}:
            assert isinstance(event, dict)

    parsed = parse_shannon_stream_output(completed.stdout)
    assert parsed.payload["conformance"] == "schema"
    assert parsed.payload["ok"] is True
    assert parsed.raw_output == completed.stdout


def test_parser_conformance_tolerates_required_event_drift_shapes() -> None:
    raw = "\n".join(
        json.dumps(event)
        for event in (
            {"event": "init", "sessionId": "session-from-init"},
            {
                "kind": "assistant",
                "message": {"content": [{"type": "text", "text": "working"}]},
                "tokenUsage": {"input_tokens": 1, "output_tokens": 2},
            },
            {
                "eventType": "rate_limit_event",
                "rateLimits": [
                    {"provider": "anthropic", "window": "5h", "remaining": 3},
                    {"provider": "anthropic", "window": "7d", "remaining": 10},
                ],
            },
            {
                "eventType": "result",
                "resultStatus": "success",
                "session": {"id": "session-from-result"},
                "structuredOutput": {"conformance": "drift", "ok": True},
            },
        )
    ) + "\n"

    parsed = parse_shannon_stream_output(raw)

    assert parsed.payload == {"conformance": "drift", "ok": True}
    assert parsed.session_id == "session-from-result"
    assert parsed.rate_limit == {
        "values": [
            {"provider": "anthropic", "window": "5h", "remaining": 3},
            {"provider": "anthropic", "window": "7d", "remaining": 10},
        ]
    }


def test_live_claude_bypass_permissions_executes_headless_write_tool(
    tmp_path: Path,
) -> None:
    output_name = "conformance-write.txt"
    token = "shannon-stream-headless-write-ok"
    completed = _run_claude_stream(
        tmp_path,
        "Use the filesystem write tool to create "
        f"./{output_name} containing exactly this text: {token}\n"
        "After the file exists, return exactly this JSON object and no markdown: "
        '{"conformance":"write","ok":true,"path":"conformance-write.txt"}',
        bypass_permissions=True,
    )

    project_file = tmp_path / "project" / output_name
    assert project_file.read_text(encoding="utf-8") == token

    parsed = parse_shannon_stream_output(completed.stdout)
    assert parsed.payload == {
        "conformance": "write",
        "ok": True,
        "path": output_name,
    }
