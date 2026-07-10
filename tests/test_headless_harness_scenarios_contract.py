"""HEADLESS HARNESS CONTRACT TESTS.

Contract tests for headless CLI/JSON/schema surfaces that do not need a live
model, ComfyUI server, or browser.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tests.live_agentic_harness.guard import guard_output_dir


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ready() -> dict[str, Any]:
    return {"ready": True, "route": "openrouter", "model": "contract-model"}


def _inspect_result() -> Any:
    from vibecomfy.executor.contracts import ClassifyDecision, ExecutorResult, Report

    return ExecutorResult.success(
        report=Report(
            plan=ClassifyDecision(
                route="inspect",
                task="inspect_graph",
                intent="explain_graph",
                plan_summary="Explain the attached graph without editing it.",
                known_graph_context="A minimal test graph was supplied.",
            )
        ),
        graph={"1": {"class_type": "CheckpointLoaderSimple"}},
        reply="This graph loads a checkpoint and needs no browser state.",
    )


def _dry_run_result() -> Any:
    from vibecomfy.executor.contracts import ClassifyDecision, ExecutorResult, Report

    return ExecutorResult.success(
        report=Report(
            plan=ClassifyDecision(
                route="inspect",
                task="inspect_graph",
                intent="explain_graph",
                plan_summary="Classify-only graph explanation.",
            )
        ),
        reply="[dry-run] classified route: inspect",
    )


def test_graph_explanation_contract_schema_does_not_claim_live_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    from vibecomfy.agent.contracts import HeadlessAgentRequest
    from vibecomfy.agent import service as svc

    output_dir = tmp_path / "graph-explanation"
    request = HeadlessAgentRequest(
        query="Explain this graph without changing it.",
        graph={"1": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
        output_dir=output_dir,
        live=False,
    )

    monkeypatch.setattr(svc, "_check_live_readiness", lambda request: _ready())
    monkeypatch.setattr("vibecomfy.executor.core.run_executor", lambda *args, **kwargs: _inspect_result())

    result = svc.run_headless(request, entrypoint="contract_test")

    assert result.status == "success"
    response = _read_json(output_dir / "response.json")
    classification = _read_json(output_dir / "classification.json")
    flow_metadata = _read_json(output_dir / "flow_metadata.json")

    assert response["ok"] is True
    assert response["route"] == "inspect"
    assert response["reply"]
    assert classification["route"] == "inspect"
    assert classification["task"] == "inspect_graph"
    assert flow_metadata["flow_kind"] == "live_agentic_headless"
    assert flow_metadata["entrypoint"] == "contract_test"
    assert flow_metadata["live"] is False
    assert flow_metadata["status"] == "success"
    assert not (output_dir / "research.json").exists()
    assert not (output_dir / "implementation_payload.json").exists()
    assert guard_output_dir(output_dir)["live_agentic_success"] is False


def test_dry_run_contract_schema_is_classify_only_and_not_live_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    from vibecomfy.agent.contracts import HeadlessAgentRequest
    from vibecomfy.agent import service as svc

    calls: list[dict[str, Any]] = []

    def fake_run_executor(*args: Any, **kwargs: Any) -> Any:
        calls.append({"args": args, "kwargs": kwargs})
        return _dry_run_result()

    output_dir = tmp_path / "dry-run"
    request = HeadlessAgentRequest(
        query="Dry-run classify this graph.",
        graph={"1": {"class_type": "KSampler", "inputs": {}}},
        output_dir=output_dir,
        dry_run=True,
        live=False,
    )

    monkeypatch.setattr(svc, "_check_live_readiness", lambda request: _ready())
    monkeypatch.setattr("vibecomfy.executor.core.run_executor", fake_run_executor)

    result = svc.run_headless(request, entrypoint="contract_test")

    assert result.status == "dry_run"
    assert calls and calls[0]["kwargs"]["classify_only"] is True
    response = _read_json(output_dir / "response.json")
    classification = _read_json(output_dir / "classification.json")
    flow_metadata = _read_json(output_dir / "flow_metadata.json")

    assert response["ok"] is True
    assert classification["route"] == "inspect"
    assert flow_metadata["dry_run"] is True
    assert flow_metadata["live"] is False
    assert flow_metadata["status"] == "dry_run"
    assert not (output_dir / "research.json").exists()
    assert not (output_dir / "implementation_result.json").exists()
    assert guard_output_dir(output_dir)["live_agentic_success"] is False


def test_cli_json_contract_exposes_artifact_schema_without_live_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    from vibecomfy.agent import __main__ as cli
    from vibecomfy.agent import service as svc

    output_dir = tmp_path / "cli"

    def fake_run_headless(request: Any, *, entrypoint: str) -> Any:
        from vibecomfy.agent.artifacts import synthesize_headless_artifacts
        from vibecomfy.agent.service import HeadlessAgentResult

        response = {"ok": True, "route": "inspect", "reply": "schema ok"}
        artifacts = synthesize_headless_artifacts(
            request=request.to_dict(),
            result=_dry_run_result(),
            response=response,
            output_dir=request.output_dir_path,
            status="dry_run",
            readiness=_ready(),
            entrypoint=entrypoint,
        )
        return HeadlessAgentResult(
            status="dry_run",
            ok=True,
            response=response,
            artifacts=artifacts,
            readiness=_ready(),
            request=request,
        )

    monkeypatch.setattr(svc, "run_headless", fake_run_headless)

    exit_code = cli.main(
        [
            "--query",
            "Explain this graph.",
            "--dry-run",
            "--no-live",
            "--output-dir",
            str(output_dir),
            "--json",
        ]
    )

    assert os.environ["VIBECOMFY_HEADLESS"] == "1"
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "dry_run"
    assert payload["ok"] is True
    assert payload["artifacts"]["output_dir"] == str(output_dir)
    assert payload["request"]["live"] is False
    assert payload["request"]["dry_run"] is True
    assert guard_output_dir(output_dir)["live_agentic_success"] is False
