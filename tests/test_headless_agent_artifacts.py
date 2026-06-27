from __future__ import annotations

import json
from pathlib import Path

from vibecomfy.agent.artifacts import synthesize_headless_artifacts
from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorResult,
    ImplementationResult,
    Report,
    ResearchResult,
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_headless_artifacts_redact_metadata_and_write_phase_payloads(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    request = {
        "query": "adapt this graph",
        "graph": {"nodes": [{"id": 1, "class_type": "LoadImage"}]},
        "session_id": "session-1",
        "extra": {
            "api_key": "sk-secret",
            "nested": {"access_token": "token-secret"},
        },
    }
    result = ExecutorResult.success(
        report=Report(
            plan=ClassifyDecision(
                research=True,
                implement=True,
                route="adapt",
                task="research_precedent",
                research_goal="Find useful precedent.",
            ),
            research=ResearchResult(
                summary="Found precedent.",
                sources=({"url": "https://example.test", "api_key": "source-secret"},),
            ),
            implementation=ImplementationResult(
                graph={"nodes": [{"id": 2}]},
                message="Applied edit.",
                durable_response={"session_id": "session-1", "turn_id": "0001"},
            ),
        ),
        graph={"nodes": [{"id": 2}]},
        reply="Done.",
    )

    manifest = synthesize_headless_artifacts(
        request=request,
        result=result,
        response={
            "ok": True,
            "route": "adapt",
            "reply": "Done.",
            "debug": {"provider_token": "response-secret"},
        },
        output_dir=output_dir,
        status="success",
        readiness={"ready": True, "api_key": "readiness-secret"},
        entrypoint="test",
    )

    assert manifest["manifest"] == [
        "request.json",
        "response.json",
        "flow_metadata.json",
        "classification.json",
        "research.json",
        "implementation_payload.json",
        "implementation_result.json",
    ]
    assert _read_json(output_dir / "request.json")["extra"]["api_key"] == "<redacted>"
    assert (
        _read_json(output_dir / "request.json")["extra"]["nested"]["access_token"]
        == "<redacted>"
    )
    assert _read_json(output_dir / "flow_metadata.json")["readiness"]["api_key"] == "<redacted>"
    assert _read_json(output_dir / "response.json")["debug"]["provider_token"] == "<redacted>"
    assert _read_json(output_dir / "research.json")["sources"][0]["api_key"] == "<redacted>"

    implementation_payload = _read_json(output_dir / "implementation_payload.json")
    assert implementation_payload["route"] == "adapt"
    assert implementation_payload["executor_route"] == "adapt"
    assert implementation_payload["executor_classification"]["route"] == "adapt"
    assert implementation_payload["graph"] == request["graph"]
    assert implementation_payload["execution_protocol_notes"]["research_goal"] == (
        "Find useful precedent."
    )
    assert implementation_payload["execution_protocol_notes"]["research_summary"] == (
        "Found precedent."
    )
    assert _read_json(output_dir / "implementation_result.json")["message"] == "Applied edit."


def test_headless_artifacts_copy_only_real_durable_turn_files(tmp_path: Path) -> None:
    turn_dir = tmp_path / "sessions" / "session-1" / "turns" / "0001"
    turn_dir.mkdir(parents=True)
    (turn_dir / "request.json").write_text('{"query": "real"}\n', encoding="utf-8")
    (turn_dir / "response.json").write_text('{"ok": true, "route": "inspect"}\n', encoding="utf-8")
    (turn_dir / "chat.json").write_text('{"messages": []}\n', encoding="utf-8")

    output_dir = tmp_path / "out"
    manifest = synthesize_headless_artifacts(
        request={"query": "synthetic"},
        result=ExecutorResult.success(
            report=Report(plan=ClassifyDecision(route="inspect", task="inspect_graph")),
            reply="inspected",
        ),
        response={
            "ok": True,
            "route": "inspect",
            "detail_json_path": str(turn_dir / "response.json"),
        },
        output_dir=output_dir,
        status="success",
    )

    assert sorted(manifest["copied_turn_artifacts"]) == [
        "chat.json",
        "request.json",
        "response.json",
    ]
    assert manifest["optional_model_artifacts"] == {
        "messages.jsonl": False,
        "model_request.json": False,
        "model_response.json": False,
    }
    assert not (output_dir / "messages.jsonl").exists()
    assert not (output_dir / "model_request.json").exists()
    assert not (output_dir / "model_response.json").exists()
    assert _read_json(output_dir / "request.json") == {"query": "real"}


def test_headless_artifacts_copy_model_files_when_turn_produced_them(tmp_path: Path) -> None:
    turn_dir = tmp_path / "sessions" / "session-1" / "turns" / "0002"
    turn_dir.mkdir(parents=True)
    (turn_dir / "response.json").write_text('{"ok": true}\n', encoding="utf-8")
    (turn_dir / "messages.jsonl").write_text('{"role": "user"}\n', encoding="utf-8")
    (turn_dir / "model_request.json").write_text('{"messages": []}\n', encoding="utf-8")
    (turn_dir / "model_response.json").write_text('{"turns": []}\n', encoding="utf-8")

    output_dir = tmp_path / "out"
    manifest = synthesize_headless_artifacts(
        request={"query": "edit"},
        result=ExecutorResult.success(
            report=Report(
                plan=ClassifyDecision(route="revise", task="edit_graph"),
                implementation=ImplementationResult(message="edited"),
            ),
            reply="edited",
        ),
        response={"ok": True, "detail_json_path": str(turn_dir / "response.json")},
        output_dir=output_dir,
        status="success",
    )

    assert manifest["optional_model_artifacts"] == {
        "messages.jsonl": True,
        "model_request.json": True,
        "model_response.json": True,
    }
    assert (output_dir / "messages.jsonl").read_text(encoding="utf-8") == '{"role": "user"}\n'
    assert (output_dir / "model_request.json").is_file()
    assert (output_dir / "model_response.json").is_file()
