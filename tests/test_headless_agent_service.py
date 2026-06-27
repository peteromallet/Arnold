from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest


def _import_service() -> Any:
    from vibecomfy.agent import service as svc

    return svc


def _make_success_result(monkeypatch: pytest.MonkeyPatch) -> Any:
    from vibecomfy.executor.contracts import ClassifyDecision, ExecutorResult, Report

    result = ExecutorResult.success(
        report=Report(plan=ClassifyDecision.respond_only()),
        graph=None,
        reply="hello from headless",
    )
    return result


def test_run_headless_success_writes_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    svc = _import_service()

    from vibecomfy.agent.contracts import HeadlessAgentRequest

    output_dir = tmp_path / "out"
    request = HeadlessAgentRequest(
        query="explain this graph",
        output_dir=output_dir,
    )

    monkeypatch.setattr(
        svc,
        "_check_live_readiness",
        lambda request: {"ready": True, "route": "openrouter", "model": "model"},
    )
    result = _make_success_result(monkeypatch)
    monkeypatch.setattr(
        "vibecomfy.executor.core.run_executor",
        lambda *args, **kwargs: result,
    )

    run_result = svc.run_headless(request, entrypoint="test")

    assert run_result.status == "success"
    assert run_result.ok is True
    assert (output_dir / "request.json").is_file()
    assert (output_dir / "response.json").is_file()
    assert (output_dir / "flow_metadata.json").is_file()
    assert (output_dir / "classification.json").is_file()
    flow_metadata = _read_json(output_dir / "flow_metadata.json")
    assert flow_metadata["flow_kind"] == "live_agentic_headless"
    assert flow_metadata["dispatcher"] == "real"
    assert flow_metadata["model_behavior"] == "agentic"
    assert flow_metadata["frontend"] == "not_used"
    assert flow_metadata["entrypoint"] == "test"


def test_run_headless_blocked_when_not_ready(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    svc = _import_service()

    from vibecomfy.agent.contracts import HeadlessAgentRequest

    output_dir = tmp_path / "out"
    request = HeadlessAgentRequest(query="do something", output_dir=output_dir)

    monkeypatch.setattr(
        svc,
        "_check_live_readiness",
        lambda request: {"ready": False, "reason": "no key"},
    )
    sys.modules.pop("vibecomfy.executor.core", None)

    run_result = svc.run_headless(request)

    assert run_result.status == "blocked_prerequisite"
    assert run_result.ok is False
    assert "no key" in (run_result.error or "")
    assert "vibecomfy.executor.core" not in sys.modules
    assert (output_dir / "flow_metadata.json").is_file()


def test_run_headless_dry_run_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    svc = _import_service()

    from vibecomfy.agent.contracts import HeadlessAgentRequest

    output_dir = tmp_path / "out"
    request = HeadlessAgentRequest(
        query="classify this",
        output_dir=output_dir,
        dry_run=True,
    )

    monkeypatch.setattr(
        svc,
        "_check_live_readiness",
        lambda request: {"ready": True, "route": "openrouter"},
    )
    result = _make_success_result(monkeypatch)
    monkeypatch.setattr(
        "vibecomfy.executor.core.run_executor",
        lambda *args, **kwargs: result,
    )

    run_result = svc.run_headless(request)

    assert run_result.status == "dry_run"
    assert run_result.ok is True


def test_run_headless_validation_failure_writes_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    svc = _import_service()

    class InvalidRequest:
        output_dir_path = tmp_path / "out"

        def to_executor_request(self) -> Any:
            raise ValueError("bad request")

        def to_dict(self) -> dict[str, Any]:
            return {"query": "bad", "output_dir": str(self.output_dir_path)}

    readiness_calls: list[Any] = []
    monkeypatch.setattr(
        svc,
        "_check_live_readiness",
        lambda request: readiness_calls.append(request) or {"ready": True},
    )

    run_result = svc.run_headless(InvalidRequest())

    assert run_result.status == "validation_failure"
    assert run_result.ok is False
    assert "bad request" in (run_result.error or "")
    assert readiness_calls == []
    assert (tmp_path / "out" / "response.json").is_file()


def test_run_headless_executor_failure_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    svc = _import_service()

    from vibecomfy.agent.contracts import HeadlessAgentRequest
    from vibecomfy.executor.contracts import ExecutorResult

    output_dir = tmp_path / "out"
    request = HeadlessAgentRequest(query="fail this", output_dir=output_dir)

    monkeypatch.setattr(
        svc,
        "_check_live_readiness",
        lambda request: {"ready": True, "route": "openrouter"},
    )
    failure = ExecutorResult.failure(
        kind="ProviderError",
        stage="classify",
        message="model timed out",
    )
    monkeypatch.setattr(
        "vibecomfy.executor.core.run_executor",
        lambda *args, **kwargs: failure,
    )

    run_result = svc.run_headless(request)

    assert run_result.status == "executor_failure"
    assert run_result.ok is False
    assert run_result.error == "model timed out"
    assert (output_dir / "flow_metadata.json").is_file()


def test_service_refuses_import_without_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    import sys

    monkeypatch.delenv("VIBECOMFY_HEADLESS", raising=False)
    sys.modules.pop("vibecomfy.agent.service", None)
    with pytest.raises(RuntimeError, match="VIBECOMFY_HEADLESS=1"):
        importlib.import_module("vibecomfy.agent.service")


def _read_json(path: Path) -> Any:
    import json

    return json.loads(path.read_text(encoding="utf-8"))
