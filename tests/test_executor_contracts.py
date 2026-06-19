"""Unit tests for executor contracts and prompt parsing.

Covers valid classify/reply JSON, malformed JSON, optional graph handling,
and the final executor result shape — without changing existing agent
contracts.
"""

from __future__ import annotations

import json

import pytest

from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorRequest,
    ExecutorResult,
    ImplementationResult,
    Report,
    ResearchResult,
)
from vibecomfy.executor.prompts import (
    build_classify_messages,
    build_reply_messages,
    parse_classify_response,
    parse_reply_response,
)


# ── ExecutorRequest ──────────────────────────────────────────────────────────


class TestExecutorRequest:
    def test_minimal_request(self) -> None:
        req = ExecutorRequest(query="hello")
        assert req.query == "hello"
        assert req.graph is None
        assert req.session_id is None
        assert req.profile is None
        assert req.idempotency_key is None

    def test_full_request(self) -> None:
        graph = {"nodes": []}
        req = ExecutorRequest(
            query="set seed to 42",
            graph=graph,
            session_id="sess-1",
            profile="default",
            idempotency_key="idem-1",
        )
        assert req.graph == graph
        assert req.session_id == "sess-1"
        assert req.profile == "default"
        assert req.idempotency_key == "idem-1"

    def test_to_dict_minimal(self) -> None:
        req = ExecutorRequest(query="hello")
        d = req.to_dict()
        assert d == {"query": "hello"}

    def test_to_dict_full(self) -> None:
        graph = {"nodes": []}
        req = ExecutorRequest(
            query="set seed",
            graph=graph,
            session_id="sess-1",
            profile="default",
            idempotency_key="idem-1",
        )
        d = req.to_dict()
        assert d["query"] == "set seed"
        assert d["graph"] == graph
        assert d["session_id"] == "sess-1"
        assert d["profile"] == "default"
        assert d["idempotency_key"] == "idem-1"

    def test_from_payload_minimal(self) -> None:
        req = ExecutorRequest.from_payload({"query": "hello"})
        assert req.query == "hello"

    def test_from_payload_full(self) -> None:
        graph = {"nodes": []}
        req = ExecutorRequest.from_payload({
            "query": "edit graph",
            "graph": graph,
            "session_id": "s1",
            "profile": "default",
            "idempotency_key": "ik1",
        })
        assert req.graph == graph
        assert req.session_id == "s1"

    def test_from_payload_missing_query_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            ExecutorRequest.from_payload({})

    def test_from_payload_empty_query_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            ExecutorRequest.from_payload({"query": "   "})

    def test_from_payload_bad_graph_type_raises(self) -> None:
        with pytest.raises(ValueError, match="graph"):
            ExecutorRequest.from_payload({"query": "x", "graph": "not-a-dict"})


# ── ClassifyDecision ─────────────────────────────────────────────────────────


class TestClassifyDecision:
    def test_defaults(self) -> None:
        d = ClassifyDecision()
        assert d.research is False
        assert d.implement is False
        assert d.reply is True
        assert d.effort == "low"
        assert d.plan_summary == ""

    def test_respond_only_convenience(self) -> None:
        d = ClassifyDecision.respond_only()
        assert d.research is False
        assert d.implement is False
        assert d.reply is True

    def test_edit_convenience(self) -> None:
        d = ClassifyDecision.edit()
        assert d.research is True
        assert d.implement is True
        assert d.reply is True

    def test_edit_no_research(self) -> None:
        d = ClassifyDecision.edit(research=False)
        assert d.research is False
        assert d.implement is True

    def test_effort_clamped_to_low(self) -> None:
        d = ClassifyDecision(effort="extreme")
        assert d.effort == "low"

    def test_to_dict(self) -> None:
        d = ClassifyDecision(research=True, implement=False, reply=True, effort="medium", plan_summary="test plan")
        out = d.to_dict()
        assert out == {
            "research": True,
            "implement": False,
            "reply": True,
            "effort": "medium",
            "plan_summary": "test plan",
            "intent": "respond",
        }


# ── ResearchResult ───────────────────────────────────────────────────────────


class TestResearchResult:
    def test_defaults(self) -> None:
        r = ResearchResult()
        assert r.summary == ""
        assert r.sources == ()
        assert r.warnings == ()

    def test_with_data(self) -> None:
        r = ResearchResult(
            summary="found 3 templates",
            sources=({"name": "t1"}, {"name": "t2"}),
            warnings=("hivemind timeout",),
        )
        assert r.summary == "found 3 templates"
        assert len(r.sources) == 2
        assert len(r.warnings) == 1

    def test_to_dict(self) -> None:
        r = ResearchResult(
            summary="x",
            sources=({"k": "v"},),
            warnings=("w1",),
        )
        d = r.to_dict()
        assert d["summary"] == "x"
        assert d["sources"] == [{"k": "v"}]
        assert d["warnings"] == ["w1"]

    def test_immutable_tuples(self) -> None:
        r = ResearchResult(sources=({"a": 1},), warnings=("w",))
        # Tuple items cannot be reassigned (TypeError).
        with pytest.raises(TypeError):
            r.sources[0] = {"b": 2}  # type: ignore[index]
        # The frozen dataclass prevents field reassignment (FrozenInstanceError,
        # which is a subclass of AttributeError in CPython 3.11+).
        with pytest.raises(Exception):
            r.sources = ()  # type: ignore[misc]


# ── ImplementationResult ─────────────────────────────────────────────────────


class TestImplementationResult:
    def test_defaults(self) -> None:
        ir = ImplementationResult()
        assert ir.graph is None
        assert ir.delta == ()
        assert ir.message == ""

    def test_with_graph(self) -> None:
        g = {"nodes": [{"id": 1}]}
        ir = ImplementationResult(graph=g, message="added node")
        assert ir.graph == g
        assert ir.message == "added node"

    def test_with_delta(self) -> None:
        ops = ({"op": "set_field"},)
        ir = ImplementationResult(delta=ops, message="changed field")
        assert ir.delta == ops

    def test_to_dict(self) -> None:
        ir = ImplementationResult(graph={"n": 1}, message="done", delta=({"op": "add"},))
        d = ir.to_dict()
        assert d["graph"] == {"n": 1}
        assert d["message"] == "done"
        assert d["delta"] == [{"op": "add"}]


# ── Report ───────────────────────────────────────────────────────────────────


class TestReport:
    def test_default(self) -> None:
        r = Report()
        assert isinstance(r.plan, ClassifyDecision)
        assert r.research is None
        assert r.implementation is None

    def test_with_phases(self) -> None:
        plan = ClassifyDecision(research=True, implement=True)
        research = ResearchResult(summary="found")
        impl = ImplementationResult(message="edited")
        r = Report(plan=plan, research=research, implementation=impl)
        assert r.plan == plan
        assert r.research is research
        assert r.implementation is impl

    def test_to_dict(self) -> None:
        plan = ClassifyDecision(plan_summary="p")
        research = ResearchResult(summary="r")
        r = Report(plan=plan, research=research)
        d = r.to_dict()
        assert d["executor"]["plan"]["plan_summary"] == "p"
        assert d["executor"]["research"]["summary"] == "r"
        assert "implementation" not in d["executor"]


# ── ExecutorResult ───────────────────────────────────────────────────────────


class TestExecutorResult:
    def test_default_success(self) -> None:
        r = ExecutorResult()
        assert r.ok is True
        assert isinstance(r.report, Report)
        assert r.graph is None
        assert r.reply is None

    def test_success_convenience(self) -> None:
        graph = {"nodes": []}
        r = ExecutorResult.success(graph=graph, reply="done")
        assert r.ok is True
        assert r.graph == graph
        assert r.reply == "done"

    def test_failure_convenience(self) -> None:
        r = ExecutorResult.failure(kind="ProviderError", stage="classify", message="timeout")
        assert r.ok is False
        assert r.failure_kind == "ProviderError"
        assert r.failure_stage == "classify"
        assert r.failure_message == "timeout"

    def test_to_dict_success(self) -> None:
        plan = ClassifyDecision(plan_summary="chat turn")
        report = Report(plan=plan)
        r = ExecutorResult.success(report=report, reply="Hello!")
        d = r.to_dict()
        assert d["ok"] is True
        assert d["reply"] == "Hello!"
        assert d["report"]["executor"]["plan"]["plan_summary"] == "chat turn"
        assert "failure_kind" not in d

    def test_to_dict_failure(self) -> None:
        r = ExecutorResult.failure(kind="TimeoutError", stage="classify", message="timed out")
        d = r.to_dict()
        assert d["ok"] is False
        assert d["failure_kind"] == "TimeoutError"
        assert d["failure_stage"] == "classify"
        assert d["failure_message"] == "timed out"


# ── Prompt building ──────────────────────────────────────────────────────────


class TestBuildClassifyMessages:
    def test_basic(self) -> None:
        msgs = build_classify_messages("hello")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert "hello" in msgs[1]["content"]

    def test_with_graph(self) -> None:
        msgs = build_classify_messages("edit graph", has_graph=True)
        assert "canvas graph is attached" in msgs[1]["content"]

    def test_with_graph_summary(self) -> None:
        msgs = build_classify_messages("edit graph", has_graph=True, graph_summary="3 nodes, 2 edges")
        content = msgs[1]["content"]
        assert "3 nodes, 2 edges" in content

    def test_no_graph(self) -> None:
        msgs = build_classify_messages("chat question", has_graph=False)
        assert "canvas graph is attached" not in msgs[1]["content"]


class TestBuildReplyMessages:
    def test_basic(self) -> None:
        msgs = build_reply_messages("hello")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_with_plan(self) -> None:
        plan = ClassifyDecision(plan_summary="simple chat reply")
        msgs = build_reply_messages("hello", plan=plan)
        assert "simple chat reply" in msgs[1]["content"]

    def test_with_research(self) -> None:
        msgs = build_reply_messages("edit", research_summary="found 2 templates")
        assert "found 2 templates" in msgs[1]["content"]

    def test_with_implementation(self) -> None:
        msgs = build_reply_messages("edit", implementation_message="added KSsampler node")
        assert "added KSsampler node" in msgs[1]["content"]

    def test_full_context(self) -> None:
        plan = ClassifyDecision(plan_summary="edit with research")
        msgs = build_reply_messages(
            "edit",
            plan=plan,
            research_summary="found template",
            implementation_message="applied template",
        )
        content = msgs[1]["content"]
        assert "edit with research" in content
        assert "found template" in content
        assert "applied template" in content

    def test_research_implementation_prompt_requests_concise_rationale(self) -> None:
        msgs = build_reply_messages(
            "edit",
            research_summary="found a relevant custom-audio workflow",
            implementation_message="applied the custom-audio wiring pattern",
        )
        system = msgs[0]["content"]
        assert "include one brief reason" in system
        assert "chosen approach/source informed the edit" in system
        assert "Do not dump the research summary" in system
        assert "quality scores only when that metadata is explicitly present" in system


# ── Response parsers ─────────────────────────────────────────────────────────


class TestParseClassifyResponse:
    def test_valid_respond_only(self) -> None:
        raw = '{"research": false, "implement": false, "reply": true, "effort": "low", "plan_summary": "chat question"}'
        d = parse_classify_response(raw)
        assert d.research is False
        assert d.implement is False
        assert d.reply is True
        assert d.effort == "low"
        assert d.plan_summary == "chat question"

    def test_valid_edit(self) -> None:
        raw = '{"research": true, "implement": true, "reply": true, "effort": "medium", "plan_summary": "edit seed"}'
        d = parse_classify_response(raw)
        assert d.research is True
        assert d.implement is True
        assert d.effort == "medium"

    def test_missing_keys_default(self) -> None:
        raw = '{"reply": false}'
        d = parse_classify_response(raw)
        assert d.research is False
        assert d.implement is False
        assert d.reply is False
        assert d.effort == "low"
        assert d.plan_summary == ""

    def test_json_with_fences(self) -> None:
        raw = '```json\n{"research": false, "implement": false, "reply": true, "effort": "low", "plan_summary": "x"}\n```'
        d = parse_classify_response(raw)
        assert d.research is False

    def test_json_with_trailing_text(self) -> None:
        raw = '{"research": true, "implement": false, "reply": true, "effort": "low", "plan_summary": "ok"} (done)'
        d = parse_classify_response(raw)
        assert d.research is True

    def test_non_bool_coercion(self) -> None:
        raw = '{"research": "yes", "implement": 0, "reply": 1, "effort": "low", "plan_summary": ""}'
        d = parse_classify_response(raw)
        assert d.research is True  # "yes" is truthy
        assert d.implement is False  # 0 is falsy
        assert d.reply is True  # 1 is truthy

    def test_bad_effort_defaults(self) -> None:
        raw = '{"research": false, "implement": false, "reply": true, "effort": "extreme", "plan_summary": ""}'
        d = parse_classify_response(raw)
        assert d.effort == "low"  # clamped

    def test_malformed_json_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_classify_response("not json at all")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_classify_response("")

    def test_non_object_json_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_classify_response('["list", "not", "object"]')

    def test_plan_summary_stripped(self) -> None:
        raw = '{"research": false, "implement": false, "reply": true, "effort": "low", "plan_summary": "  hello world  "}'
        d = parse_classify_response(raw)
        assert d.plan_summary == "hello world"


class TestParseReplyResponse:
    def test_valid_reply(self) -> None:
        raw = '{"reply": "I have set the seed to 42."}'
        text = parse_reply_response(raw)
        assert text == "I have set the seed to 42."

    def test_fallback_message_key(self) -> None:
        raw = '{"message": "The graph was edited successfully."}'
        text = parse_reply_response(raw)
        assert text == "The graph was edited successfully."

    def test_fallback_response_key(self) -> None:
        raw = '{"response": "All done."}'
        text = parse_reply_response(raw)
        assert text == "All done."

    def test_fallback_content_key(self) -> None:
        raw = '{"content": "Here you go."}'
        text = parse_reply_response(raw)
        assert text == "Here you go."

    def test_fallback_text_key(self) -> None:
        raw = '{"text": "Done."}'
        text = parse_reply_response(raw)
        assert text == "Done."

    def test_empty_reply_raises(self) -> None:
        raw = '{"reply": ""}'
        with pytest.raises(ValueError, match="reply"):
            parse_reply_response(raw)

    def test_no_valid_key_raises(self) -> None:
        raw = '{"unknown": "value"}'
        with pytest.raises(ValueError, match="reply"):
            parse_reply_response(raw)

    def test_reply_with_fences(self) -> None:
        raw = '```\n{"reply": "Done!"}\n```'
        text = parse_reply_response(raw)
        assert text == "Done!"

    def test_malformed_json_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_reply_response("not json")

    def test_strips_whitespace(self) -> None:
        raw = '{"reply": "  padded  "}'
        text = parse_reply_response(raw)
        assert text == "padded"


# ── Round-trip: classify → parse ─────────────────────────────────────────────


class TestClassifyRoundtrip:
    def test_respond_only_roundtrip(self) -> None:
        decision = ClassifyDecision.respond_only(plan_summary="chat")
        raw = json.dumps(decision.to_dict())
        parsed = parse_classify_response(raw)
        assert parsed == decision

    def test_edit_roundtrip(self) -> None:
        decision = ClassifyDecision.edit(research=True, effort="medium", plan_summary="set seed")
        raw = json.dumps(decision.to_dict())
        parsed = parse_classify_response(raw)
        assert parsed == decision

    def test_edit_no_research_roundtrip(self) -> None:
        decision = ClassifyDecision.edit(research=False, effort="low", plan_summary="simple edit")
        raw = json.dumps(decision.to_dict())
        parsed = parse_classify_response(raw)
        assert parsed == decision


# ── ExecutorResult round-trip ────────────────────────────────────────────────


class TestExecutorResultRoundtrip:
    def test_full_success_roundtrip(self) -> None:
        plan = ClassifyDecision(research=True, implement=True, reply=True, effort="medium", plan_summary="edit graph")
        research = ResearchResult(summary="found 2 templates", sources=({"id": "t1"},), warnings=("hivemind slow",))
        impl = ImplementationResult(graph={"nodes": [1]}, message="added node", delta=({"op": "add"},))
        report = Report(plan=plan, research=research, implementation=impl)
        result = ExecutorResult.success(report=report, graph={"nodes": [1]}, reply="Graph edited successfully.")

        d = result.to_dict()
        assert d["ok"] is True
        assert d["reply"] == "Graph edited successfully."
        assert d["graph"] == {"nodes": [1]}
        assert d["report"]["executor"]["plan"]["research"] is True
        assert d["report"]["executor"]["research"]["summary"] == "found 2 templates"
        assert d["report"]["executor"]["research"]["sources"] == [{"id": "t1"}]
        assert d["report"]["executor"]["research"]["warnings"] == ["hivemind slow"]
        assert d["report"]["executor"]["implementation"]["message"] == "added node"
        assert d["report"]["executor"]["implementation"]["delta"] == [{"op": "add"}]

    def test_failure_roundtrip(self) -> None:
        plan = ClassifyDecision.respond_only()
        report = Report(plan=plan)
        result = ExecutorResult.failure(kind="ProviderError", stage="classify", message="timeout", report=report)

        d = result.to_dict()
        assert d["ok"] is False
        assert d["failure_kind"] == "ProviderError"
        assert d["failure_stage"] == "classify"
        assert d["failure_message"] == "timeout"
        assert d["report"]["executor"]["plan"]["reply"] is True
