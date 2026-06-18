"""Tests for the POST /vibecomfy/agent-executor route helper.

Calls _handle_agent_executor directly (no aiohttp, no ComfyUI boot)
and monkeypatches run_executor to verify validation, respond-only,
and edit success envelopes without executing the real pipeline.
"""

from __future__ import annotations

from unittest import mock

import pytest

from vibecomfy.comfy_nodes.agent.routes import _handle_agent_executor
from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorRequest,
    ExecutorResult,
    ImplementationResult,
    Report,
    ResearchResult,
)

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_executor_success(
    *,
    reply: str = "Done.",
    graph: dict | None = None,
    plan: ClassifyDecision | None = None,
    research: ResearchResult | None = None,
    implementation: ImplementationResult | None = None,
) -> ExecutorResult:
    """Build a success ExecutorResult with minimal boilerplate."""
    return ExecutorResult.success(
        report=Report(
            plan=plan or ClassifyDecision.respond_only(),
            research=research,
            implementation=implementation,
        ),
        graph=graph,
        reply=reply,
    )


def _make_executor_failure(
    *,
    kind: str = "ProviderError",
    stage: str = "classify",
    message: str = "timeout",
) -> ExecutorResult:
    """Build a failure ExecutorResult."""
    return ExecutorResult.failure(kind=kind, stage=stage, message=message)


# ── invalid payloads ─────────────────────────────────────────────────────────


class TestInvalidPayloads:
    """Cover every validation path in _handle_agent_executor."""

    def test_non_dict_payload_returns_failure(self) -> None:
        result = _handle_agent_executor("not a dict")
        assert result.get("ok") is False
        assert result.get("stage") == "executor"
        assert "JSON object" in str(result.get("agent_failure_context", {}))

    def test_missing_query_returns_failure(self) -> None:
        result = _handle_agent_executor({})
        assert result.get("ok") is False
        ctx = result.get("agent_failure_context", {})
        assert "query" in str(ctx).lower()

    def test_empty_query_returns_failure(self) -> None:
        result = _handle_agent_executor({"query": "   "})
        assert result.get("ok") is False
        ctx = result.get("agent_failure_context", {})
        assert "query" in str(ctx).lower()

    def test_query_wrong_type_returns_failure(self) -> None:
        result = _handle_agent_executor({"query": 123})
        assert result.get("ok") is False

    def test_graph_not_dict_returns_failure(self) -> None:
        result = _handle_agent_executor({"query": "hello", "graph": "bad"})
        assert result.get("ok") is False
        ctx = result.get("agent_failure_context", {})
        assert "graph" in str(ctx).lower()

    def test_profile_not_string_returns_failure(self) -> None:
        result = _handle_agent_executor({"query": "hello", "profile": 99})
        assert result.get("ok") is False
        ctx = result.get("agent_failure_context", {})
        assert "profile" in str(ctx).lower()

    def test_session_id_not_string_returns_failure(self) -> None:
        result = _handle_agent_executor({"query": "hello", "session_id": []})
        assert result.get("ok") is False
        ctx = result.get("agent_failure_context", {})
        assert "session_id" in str(ctx).lower()

    def test_idempotency_key_not_string_returns_failure(self) -> None:
        result = _handle_agent_executor({"query": "hello", "idempotency_key": {}})
        assert result.get("ok") is False
        ctx = result.get("agent_failure_context", {})
        assert "idempotency_key" in str(ctx).lower()


# ── respond-only success ─────────────────────────────────────────────────────


class TestRespondOnlySuccess:
    """Monkeypatch run_executor to return a respond-only result."""

    def test_respond_only_minimal_payload(self) -> None:
        success = _make_executor_success(reply="Hello, world!")
        with mock.patch(
            "vibecomfy.executor.core.run_executor",
            return_value=success,
        ):
            result = _handle_agent_executor({"query": "say hi"})

        assert result.get("ok") is True
        assert result.get("reply") == "Hello, world!"
        assert "report" in result
        assert result["report"]["executor"]["plan"]["reply"] is True

    def test_respond_only_with_session_id(self) -> None:
        success = _make_executor_success(reply="Acknowledged.")
        with mock.patch(
            "vibecomfy.executor.core.run_executor",
            return_value=success,
        ):
            result = _handle_agent_executor({
                "query": "status check",
                "session_id": "sess-abc",
            })

        assert result.get("ok") is True
        assert result.get("reply") == "Acknowledged."

    def test_respond_only_with_profile(self) -> None:
        success = _make_executor_success(reply="Profile loaded.")
        with mock.patch(
            "vibecomfy.executor.core.run_executor",
            return_value=success,
        ):
            result = _handle_agent_executor({
                "query": "help",
                "profile": "default",
            })

        assert result.get("ok") is True
        assert result.get("reply") == "Profile loaded."

    def test_forwarded_payload_contains_all_fields(self) -> None:
        """Verify the ExecutorRequest forwarded to run_executor has every field."""
        captured: list = []

        def _capture(req: ExecutorRequest, client_id: str | None = None) -> ExecutorResult:
            captured.append((req, client_id))
            return _make_executor_success(reply="got it")

        with mock.patch(
            "vibecomfy.executor.core.run_executor",
            side_effect=_capture,
        ):
            _handle_agent_executor({
                "query": "edit seed",
                "graph": {"nodes": [{"id": 1}]},
                "profile": "default",
                "session_id": "sess-1",
                "idempotency_key": "ik-1",
            })

        assert len(captured) == 1
        req, client_id = captured[0]
        assert client_id is None
        assert req.query == "edit seed"
        assert req.graph == {"nodes": [{"id": 1}]}
        assert req.profile == "default"
        assert req.session_id == "sess-1"
        assert req.idempotency_key == "ik-1"


# ── edit success ─────────────────────────────────────────────────────────────


class TestEditSuccess:
    """Monkeypatch run_executor to return an edit (graph-modified) result."""

    def test_edit_with_graph_result(self) -> None:
        edited_graph = {"nodes": [{"id": 1, "type": "KSampler"}]}
        success = _make_executor_success(
            reply="Changed seed to 42.",
            graph=edited_graph,
            plan=ClassifyDecision.edit(plan_summary="seed edit"),
            implementation=ImplementationResult(
                graph=edited_graph, message="Applied template."
            ),
            research=ResearchResult(summary="found template"),
        )
        with mock.patch(
            "vibecomfy.executor.core.run_executor",
            return_value=success,
        ):
            result = _handle_agent_executor({
                "query": "set seed to 42",
                "graph": {"nodes": []},
                "profile": "default",
            })

        assert result.get("ok") is True
        assert result.get("reply") == "Changed seed to 42."
        assert result.get("graph") == edited_graph
        report = result["report"]["executor"]
        assert report["plan"]["implement"] is True
        assert report["implementation"]["message"] == "Applied template."
        assert report["research"]["summary"] == "found template"

    def test_edit_with_delta(self) -> None:
        """ImplementationResult with delta but no top-level graph."""
        success = ExecutorResult.success(
            report=Report(
                plan=ClassifyDecision.edit(plan_summary="add node"),
                implementation=ImplementationResult(
                    delta=({"op": "add", "type": "KSampler"},),
                    message="added KSampler",
                ),
            ),
            graph=None,
            reply="Added a KSampler node.",
        )
        with mock.patch(
            "vibecomfy.executor.core.run_executor",
            return_value=success,
        ):
            result = _handle_agent_executor({
                "query": "add a sampler",
                "graph": {"nodes": []},
            })

        assert result.get("ok") is True
        assert result.get("reply") == "Added a KSampler node."
        assert result.get("graph") is None
        impl = result["report"]["executor"]["implementation"]
        assert impl["delta"] == [{"op": "add", "type": "KSampler"}]


# ── failure propagation ──────────────────────────────────────────────────────


class TestFailurePropagation:
    """Monkeypatch run_executor to return failure results."""

    def test_failure_envelope_returned(self) -> None:
        failure = _make_executor_failure(
            kind="ProviderError",
            stage="classify",
            message="Model unavailable.",
        )
        with mock.patch(
            "vibecomfy.executor.core.run_executor",
            return_value=failure,
        ):
            result = _handle_agent_executor({"query": "help"})

        assert result.get("ok") is False
        assert result.get("failure_kind") == "ProviderError"
        assert result.get("failure_stage") == "classify"
        assert result.get("failure_message") == "Model unavailable."

    def test_exception_in_run_executor_produces_failure(self) -> None:
        with mock.patch(
            "vibecomfy.executor.core.run_executor",
            side_effect=RuntimeError("Worker crashed"),
        ):
            result = _handle_agent_executor({"query": "help"})

        assert result.get("ok") is False
        ctx = result.get("agent_failure_context", {})
        assert "Worker crashed" in str(ctx)


