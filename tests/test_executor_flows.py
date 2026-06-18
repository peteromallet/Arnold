"""Executor smoke/regression tests for the full classify → research → implement → reply pipeline.

Covers respond-only, research-only, simple edit, and graph-describe flows
on ``default`` and ``openai`` profiles with fake model backend outputs.
Also includes profile-only smoke coverage for all four canonical profiles
(``default``, ``openai``, ``anthropic``, ``opensource``) that does not
require live adapters or credentials.

All model calls are faked and deterministic — no network, no ComfyUI boot,
no Arnold imports.
"""

from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path
from typing import Generator
from unittest import mock

import pytest

from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorRequest,
    ExecutorResult,
    ImplementationResult,
    Report,
    ResearchResult,
)
from vibecomfy.executor.core import run_executor
from vibecomfy.executor.profiles import set_profile_override_dir


# ── Profile fixture helpers ─────────────────────────────────────────────────

_BASE_PROFILE = """
[classify]
agent = "hermes"
model = "deepseek-v4-flash"
effort = "low"

[research]
agent = "hermes"
model = "deepseek-v4-pro"
effort = "medium"

[implement]
agent = "codex"
model = "gpt-5.4"
effort = "high"

[reply]
agent = "hermes"
model = "deepseek-v4-pro"
effort = "low"
"""


def _write_toml(dir_path: Path, name: str, content: str) -> Path:
    """Write a TOML profile file into *dir_path* and return its path."""
    file_path = dir_path / f"{name}.toml"
    file_path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return file_path


def _setup_profile_dir() -> Generator[Path, None, None]:
    """Create a temporary directory with the four canonical profiles."""
    with tempfile.TemporaryDirectory() as tmp:
        dir_path = Path(tmp)
        _write_toml(dir_path, "default", _BASE_PROFILE)
        _write_toml(
            dir_path,
            "openai",
            _BASE_PROFILE.replace('"codex"', '"codex"')
            .replace('"gpt-5.4"', '"gpt-5.5"'),
        )
        _write_toml(
            dir_path,
            "anthropic",
            _BASE_PROFILE.replace('"codex"', '"claude"')
            .replace('"gpt-5.4"', '"claude-sonnet-4-5"'),
        )
        _write_toml(
            dir_path,
            "opensource",
            _BASE_PROFILE.replace('"codex"', '"shannon"')
            .replace('"gpt-5.4"', '"openrouter/hermes-3-70b"'),
        )
        set_profile_override_dir(dir_path)
        yield dir_path
        set_profile_override_dir(None)


@pytest.fixture
def profile_dir() -> Generator[Path, None, None]:
    yield from _setup_profile_dir()


# ── Fake model backend helpers ───────────────────────────────────────────────


def _fake_classify_respond_only(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
) -> ClassifyDecision:
    """Return a respond-only classification (no research, no edit)."""
    return ClassifyDecision.respond_only(
        plan_summary="simple chat reply",
    )


def _fake_classify_research_only(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
) -> ClassifyDecision:
    """Return a research-only classification (research, no edit)."""
    return ClassifyDecision(
        research=True,
        implement=False,
        reply=True,
        effort="medium",
        plan_summary="research node types",
    )


def _fake_classify_simple_edit(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
) -> ClassifyDecision:
    """Return a simple edit classification (implement, no research)."""
    return ClassifyDecision.edit(
        research=False,
        effort="low",
        plan_summary="simple graph edit",
    )


def _fake_classify_graph_describe(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
) -> ClassifyDecision:
    """Return a graph-describe classification (research + implement)."""
    return ClassifyDecision.edit(
        research=True,
        effort="medium",
        plan_summary="describe and edit graph",
    )


def _fake_reply_respond_only(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
) -> str:
    """Return a respond-only fake reply."""
    return "I'm here to help with your ComfyUI workflow. What would you like to do?"


def _fake_reply_research_only(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
) -> str:
    """Return a research-only fake reply."""
    return "Based on my research, here are the relevant node types: KSampler, VAEDecode, CLIPTextEncode."


def _fake_reply_hotshot(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
) -> str:
    """Return a fake reply referencing Hotshot XL research."""
    return "Hotshot XL is an SDXL-based text-to-video model. You can insert it before SVD-XT as a frame generator."


def _fake_reply_edit(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
) -> str:
    """Return an edit fake reply."""
    return "The graph has been updated with the requested changes."


def _fake_reply_graph_describe(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
) -> str:
    """Return a graph-describe fake reply."""
    return "I've analyzed your graph and applied the node template. The graph now has a KSampler connected to VAEDecode."


def _fake_handle_agent_edit(payload: dict, **kwargs: Any) -> dict:
    """Fake handle_agent_edit that returns a successful edit result."""
    input_graph = payload.get("graph", {})
    nodes = input_graph.get("nodes", [])
    edited_nodes = list(nodes) + [{"id": len(nodes) + 1, "type": "KSampler"}]
    return {
        "graph": {"nodes": edited_nodes},
        "message": "Added a KSampler node to the graph.",
    }


def _fake_classify_explain_graph(
    query: str,
    *,
    route: str = "",
    model: str = "",
    has_graph: bool = False,
    graph_summary: str | None = None,
) -> ClassifyDecision:
    """Return an explain-graph classification (implement only, no research)."""
    return ClassifyDecision(
        research=False,
        implement=True,
        reply=True,
        effort="medium",
        plan_summary="explain what the graph does",
        intent="explain_graph",
    )


def _fake_reply_explain_graph(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    implementation_message: str | None = None,
) -> str:
    """Return a fake reply for an explain-graph request."""
    return "This workflow loads a checkpoint, encodes prompts, samples a latent, decodes it, and saves the image."


def _fake_handle_agent_edit_explain(payload: dict, **kwargs: Any) -> dict:
    """Fake handle_agent_edit that returns an explanation without editing."""
    input_graph = payload.get("graph", {})
    classification = payload.get("executor_classification", {})
    intent = classification.get("intent") if isinstance(classification, dict) else ""
    return {
        "graph": input_graph,
        "message": f"Explanation generated for intent={intent}: the workflow is a text-to-image pipeline.",
    }


def _empty_hivemind_client(query: str, timeout: float) -> dict[str, Any]:
    """Deterministic Hivemind client that returns no results."""
    return {"results": []}


# ── Respond-only flow tests ──────────────────────────────────────────────────


class TestRespondOnlyFlow:
    """Smoke tests for the respond-only executor flow (no research, no edit)."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_respond_only_default_profile(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Respond-only with default profile returns a success result with reply."""
        request = ExecutorRequest(query="What is a KSampler?", profile="default")
        result = run_executor(request)

        assert result.ok is True
        assert result.reply == "I'm here to help with your ComfyUI workflow. What would you like to do?"
        assert result.report.plan.research is False
        assert result.report.plan.implement is False
        assert result.report.plan.reply is True
        assert result.report.research is None
        assert result.report.implementation is None
        assert result.graph is None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_respond_only_openai_profile(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Respond-only with openai profile returns a success result with reply."""
        request = ExecutorRequest(query="How do I add a node?", profile="openai")
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert result.report.plan.research is False
        assert result.report.plan.implement is False
        assert result.report.research is None
        assert result.report.implementation is None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_respond_only_no_profile_defaults_to_default(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """When no profile is specified, the default profile is used."""
        request = ExecutorRequest(query="hello")
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_respond_only_result_to_dict(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """The result can be serialized to a dict with expected keys."""
        request = ExecutorRequest(query="status", profile="default")
        result = run_executor(request)
        d = result.to_dict()

        assert d["ok"] is True
        assert "reply" in d
        assert "report" in d
        assert d.get("graph") is None
        assert d["report"]["executor"]["plan"]["research"] is False
        assert d["report"]["executor"]["plan"]["implement"] is False

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_respond_only_with_session_id(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Respond-only with session_id still works."""
        request = ExecutorRequest(
            query="help", profile="default", session_id="sess-test-1"
        )
        result = run_executor(request)
        assert result.ok is True
        assert result.reply is not None


# ── Research-only flow tests ─────────────────────────────────────────────────


class TestResearchOnlyFlow:
    """Smoke tests for the research-only executor flow (research → reply, no edit)."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_research_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_research_only)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_research_only_default_profile(
        self, mock_corpus, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Research-only with default profile runs research and reply phases."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="K-Sampler node for ComfyUI",
                pack="core",
                tags=("sampling",),
                tasks=("t2i",),
                source="object_info",
            ),
        ]

        request = ExecutorRequest(
            query="What sampling nodes are available?", profile="default"
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert "KSampler" in result.reply
        assert result.report.plan.research is True
        assert result.report.plan.implement is False
        # Research phase should have produced a result.
        assert result.report.research is not None
        assert isinstance(result.report.research, ResearchResult)
        assert len(result.report.research.summary) > 0
        assert result.report.implementation is None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_research_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_research_only)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_research_only_openai_profile(
        self, mock_corpus, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Research-only with openai profile."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="VAEDecode",
                description="VAE Decode node",
                pack="core",
                source="object_info",
            ),
        ]

        request = ExecutorRequest(
            query="What VAE nodes exist?", profile="openai"
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert result.report.plan.research is True
        assert result.report.research is not None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_research_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_research_only)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_research_only_sources_in_result(
        self, mock_corpus, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Research results include source references."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="CLIPTextEncode",
                description="CLIP text encoder",
                pack="core",
                source="object_info",
            ),
        ]

        request = ExecutorRequest(query="text encoding nodes", profile="default")
        result = run_executor(request)

        assert result.report.research is not None
        sources = result.report.research.sources
        assert len(sources) >= 1
        assert sources[0]["class_type"] == "CLIPTextEncode"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_research_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_research_only)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch(
        "vibecomfy.executor.core._default_hivemind_client",
        side_effect=_empty_hivemind_client,
    )
    def test_research_only_empty_corpus(
        self, mock_hivemind, mock_corpus, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Research with empty corpus still succeeds (no sources, but no crash)."""
        mock_corpus.return_value = []

        request = ExecutorRequest(query="nonexistent node", profile="default")
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert result.report.research is not None
        assert len(result.report.research.sources) == 0

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_research_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_hotshot)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_research_hotshot_xl_query(
        self, mock_corpus, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """A Hotshot XL workflow query flows through classify → research → reply."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="HotshotXL",
                description="Hotshot XL SDXL-based text-to-video node",
                pack="hotshot-xl",
                tags=("video", "sdxl"),
                tasks=("i2v",),
                source="curated",
            ),
        ]

        request = ExecutorRequest(
            query="How do I add Hotshot XL to an SVD-XT workflow?",
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert "Hotshot" in result.reply
        assert result.report.plan.research is True
        assert result.report.plan.implement is False
        assert result.report.research is not None
        sources = result.report.research.sources
        assert any("Hotshot" in s.get("class_type", "") for s in sources)


# ── Simple edit flow tests ───────────────────────────────────────────────────


class TestSimpleEditFlow:
    """Smoke tests for the simple edit executor flow (implement → reply, no research)."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_simple_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_edit)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_simple_edit_default_profile(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Simple edit with default profile runs implement and reply phases."""
        input_graph = {"nodes": [{"id": 1, "type": "VAEDecode"}]}
        request = ExecutorRequest(
            query="add a KSampler node",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply == "The graph has been updated with the requested changes."
        assert result.report.plan.research is False
        assert result.report.plan.implement is True
        assert result.report.research is None
        assert result.report.implementation is not None
        assert result.report.implementation.message == "Added a KSampler node to the graph."
        # The edited graph should be returned.
        assert result.graph is not None
        assert len(result.graph["nodes"]) == 2

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_simple_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_edit)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_simple_edit_openai_profile(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Simple edit with openai profile."""
        input_graph = {"nodes": [{"id": 1, "type": "LoadImage"}]}
        request = ExecutorRequest(
            query="add a sampler",
            graph=input_graph,
            profile="openai",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert result.report.plan.implement is True
        assert result.report.implementation is not None
        assert result.graph is not None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_simple_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_edit)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_simple_edit_no_graph_skips_implementation(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """When no graph is attached, implementation is skipped gracefully."""
        request = ExecutorRequest(query="add a node", profile="default")
        result = run_executor(request)

        assert result.ok is True
        # Implementation should have a skip message, but edit still succeeds.
        assert result.report.implementation is not None
        assert "no graph" in result.report.implementation.message.lower()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_simple_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_edit)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_simple_edit_with_session_id_forwarded(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Session ID is forwarded to handle_agent_edit."""
        input_graph = {"nodes": [{"id": 1}]}
        request = ExecutorRequest(
            query="edit graph",
            graph=input_graph,
            profile="default",
            session_id="sess-edit-1",
        )
        result = run_executor(request)

        assert result.ok is True
        # Verify handle_agent_edit was called with session_id.
        call_args = mock_edit.call_args[0][0]
        assert call_args["session_id"] == "sess-edit-1"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_simple_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_edit)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    def test_simple_edit_result_to_dict(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Edit result serializes correctly."""
        input_graph = {"nodes": [{"id": 1}]}
        request = ExecutorRequest(
            query="add KSampler",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)
        d = result.to_dict()

        assert d["ok"] is True
        assert "graph" in d
        assert d["report"]["executor"]["plan"]["implement"] is True
        assert d["report"]["executor"]["implementation"]["message"] is not None


# ── Graph-describe flow tests ────────────────────────────────────────────────


class TestGraphDescribeFlow:
    """Smoke tests for the graph-describe executor flow (research + implement → reply)."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_graph_describe)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_graph_describe)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_graph_describe_default_profile(
        self, mock_corpus, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Graph-describe with default profile runs research, implement, and reply."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="K-Sampler for ComfyUI",
                pack="core",
                source="object_info",
            ),
        ]

        input_graph = {
            "nodes": [
                {"id": 1, "type": "CLIPTextEncode"},
                {"id": 2, "type": "VAEDecode"},
            ]
        }
        request = ExecutorRequest(
            query="describe my graph and add a KSampler",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert "KSampler" in result.reply
        assert result.report.plan.research is True
        assert result.report.plan.implement is True
        assert result.report.research is not None
        assert result.report.implementation is not None
        assert result.graph is not None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_graph_describe)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_graph_describe)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_graph_describe_openai_profile(
        self, mock_corpus, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Graph-describe with openai profile."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="Sampling node",
                pack="core",
                source="object_info",
            ),
        ]

        input_graph = {"nodes": [{"id": 1, "type": "LoadImage"}]}
        request = ExecutorRequest(
            query="what's in my graph and add a sampler",
            graph=input_graph,
            profile="openai",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert result.report.plan.research is True
        assert result.report.plan.implement is True
        assert result.report.research is not None
        assert result.report.implementation is not None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_graph_describe)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_graph_describe)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    @mock.patch(
        "vibecomfy.executor.core._default_hivemind_client",
        side_effect=_empty_hivemind_client,
    )
    def test_graph_describe_research_failure_non_fatal(
        self, mock_hivemind, mock_corpus, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """When research fails (empty corpus), the pipeline still completes."""
        mock_corpus.return_value = []

        input_graph = {"nodes": [{"id": 1}]}
        request = ExecutorRequest(
            query="describe and edit my graph",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert result.report.research is not None
        # Research summary should indicate no results.
        assert "No relevant local results found" in result.report.research.summary

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_graph_describe)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_graph_describe)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit)
    @mock.patch("vibecomfy.executor.research.build_search_corpus")
    def test_graph_describe_with_graph_summary_context(
        self, mock_corpus, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Classify receives graph summary when a graph is attached."""
        from vibecomfy.search.index import SearchEntry

        mock_corpus.return_value = [
            SearchEntry(
                class_type="KSampler",
                description="K-Sampler",
                pack="core",
                source="object_info",
            ),
        ]

        input_graph = {
            "nodes": [
                {"id": 1, "class_type": "CLIPTextEncode"},
                {"id": 2, "class_type": "KSampler"},
                {"id": 3, "class_type": "VAEDecode"},
            ]
        }
        request = ExecutorRequest(
            query="describe my pipeline and suggest improvements",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        # Verify classify was called with has_graph=True.
        classify_call_kwargs = mock_classify.call_args.kwargs
        assert classify_call_kwargs.get("has_graph") is True


# ── Explain-graph flow tests ─────────────────────────────────────────────────


class TestExplainGraphFlow:
    """Smoke tests for the explain-graph executor flow (implement → reply, no research)."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_explain_graph)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_explain_graph)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit_explain)
    def test_explain_workflow_query(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Asking 'what does this workflow do?' routes through classify → implement → reply."""
        input_graph = {
            "nodes": [
                {"id": 1, "class_type": "CheckpointLoaderSimple"},
                {"id": 2, "class_type": "CLIPTextEncode"},
                {"id": 3, "class_type": "EmptyLatentImage"},
                {"id": 4, "class_type": "KSampler"},
                {"id": 5, "class_type": "VAEDecode"},
                {"id": 6, "class_type": "SaveImage"},
            ]
        }
        request = ExecutorRequest(
            query="What does this workflow do?",
            graph=input_graph,
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is True
        assert result.reply is not None
        assert result.report.plan.research is False
        assert result.report.plan.implement is True
        assert result.report.plan.intent == "explain_graph"
        assert result.report.research is None
        assert result.report.implementation is not None
        assert "explain" in result.report.implementation.message.lower()
        assert result.graph is not None


# ── Profile-only smoke coverage ──────────────────────────────────────────────


class TestProfileSmokeCoverage:
    """Profile-only smoke tests: verify each canonical profile resolves through
    the executor without live adapters or credentials.  Uses respond-only
    flow (the simplest path) to exercise profile resolution + classify + reply."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_default_profile_executor_smoke(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Default profile resolves and produces a success result."""
        request = ExecutorRequest(query="hello", profile="default")
        result = run_executor(request)
        assert result.ok is True
        assert result.reply is not None
        # Verify classify was called with default profile's agent/model.
        assert mock_classify.call_args.kwargs["route"] == "hermes"
        assert mock_classify.call_args.kwargs["model"] == "deepseek-v4-flash"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_openai_profile_executor_smoke(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """OpenAI profile resolves and produces a success result."""
        request = ExecutorRequest(query="hello", profile="openai")
        result = run_executor(request)
        assert result.ok is True
        assert result.reply is not None
        # Verify classify was called with openai profile's agent/model.
        assert mock_classify.call_args.kwargs["route"] == "hermes"
        assert mock_classify.call_args.kwargs["model"] == "deepseek-v4-flash"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_anthropic_profile_executor_smoke(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Anthropic profile resolves and produces a success result."""
        request = ExecutorRequest(query="hello", profile="anthropic")
        result = run_executor(request)
        assert result.ok is True
        assert result.reply is not None
        assert mock_classify.call_args.kwargs["route"] == "hermes"
        assert mock_classify.call_args.kwargs["model"] == "deepseek-v4-flash"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_opensource_profile_executor_smoke(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Opensource profile resolves and produces a success result."""
        request = ExecutorRequest(query="hello", profile="opensource")
        result = run_executor(request)
        assert result.ok is True
        assert result.reply is not None
        assert mock_classify.call_args.kwargs["route"] == "hermes"
        assert mock_classify.call_args.kwargs["model"] == "deepseek-v4-flash"

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_no_profile_defaults_to_default(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """When profile is None, the default profile is used."""
        request = ExecutorRequest(query="hello", profile=None)
        result = run_executor(request)
        assert result.ok is True
        assert result.reply is not None

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_all_profiles_produce_deterministic_output_shape(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Every profile produces the same output shape."""
        for profile_name in ("default", "openai", "anthropic", "opensource"):
            request = ExecutorRequest(query="hello", profile=profile_name)
            result = run_executor(request)
            d = result.to_dict()
            assert "ok" in d
            assert "reply" in d
            assert "report" in d
            assert d.get("graph") is None
            assert d["report"]["executor"]["plan"]["research"] is False
            assert d["report"]["executor"]["plan"]["implement"] is False


# ── Edge case / regression tests ─────────────────────────────────────────────


class TestExecutorEdgeCases:
    """Regression tests for edge cases in executor flows."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_missing_profile_file_fails_gracefully(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Requesting a nonexistent profile returns a failure result, not an exception."""
        request = ExecutorRequest(query="hello", profile="nonexistent_profile_xyz")
        result = run_executor(request)
        assert result.ok is False
        assert result.failure_stage == "profile"
        assert result.failure_kind is not None
        assert len(result.failure_message) > 0

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_idempotency_key_passed_through(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """Idempotency keys don't cause errors (they are passed through)."""
        request = ExecutorRequest(
            query="hello", profile="default", idempotency_key="ik-test-1"
        )
        result = run_executor(request)
        assert result.ok is True

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_reply_only_never_invokes_handle_agent_edit(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """When classify says implement=false, handle_agent_edit is never called."""
        with mock.patch(
            "vibecomfy.executor.core.handle_agent_edit"
        ) as mock_edit:
            request = ExecutorRequest(
                query="just chatting",
                graph={"nodes": [{"id": 1}]},
                profile="default",
            )
            result = run_executor(request)
            assert result.ok is True
            mock_edit.assert_not_called()

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_respond_only)
    def test_empty_graph_is_still_valid(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """An empty graph (nodes: []) passes through without errors."""
        request = ExecutorRequest(
            query="help",
            graph={"nodes": []},
            profile="default",
        )
        result = run_executor(request)
        assert result.ok is True
        assert result.reply is not None


# ── Failure handling smoke tests ─────────────────────────────────────────────


class TestExecutorFailureHandling:
    """Verify the executor captures failures as ExecutorResult.failure, never raises."""

    @mock.patch("vibecomfy.executor.core.run_classify_turn")
    @mock.patch("vibecomfy.executor.core.run_reply_turn")
    def test_classify_provider_error_is_captured(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """When classify raises ProviderError, the executor returns failure."""
        from vibecomfy.comfy_nodes.agent.provider import ProviderError

        mock_classify.side_effect = ProviderError("Model timeout")
        request = ExecutorRequest(query="test", profile="default")
        result = run_executor(request)

        assert result.ok is False
        assert result.failure_stage == "classify"
        assert result.failure_kind == "ProviderError"
        assert len(result.failure_message) > 0

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_respond_only)
    @mock.patch("vibecomfy.executor.core.run_reply_turn")
    def test_reply_provider_error_is_captured(
        self, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """When reply raises ProviderError, the executor returns failure."""
        from vibecomfy.comfy_nodes.agent.provider import ProviderError

        mock_reply.side_effect = ProviderError("Reply timeout")
        request = ExecutorRequest(query="test", profile="default")
        result = run_executor(request)

        assert result.ok is False
        assert result.failure_stage == "reply"
        assert result.failure_kind == "ProviderError"
        assert len(result.failure_message) > 0

    @mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=_fake_classify_simple_edit)
    @mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply_edit)
    @mock.patch("vibecomfy.executor.core.handle_agent_edit")
    def test_implement_error_is_captured(
        self, mock_edit, mock_reply, mock_classify, profile_dir: Path
    ) -> None:
        """When handle_agent_edit raises, the executor returns failure."""
        mock_edit.side_effect = RuntimeError("Edit engine crashed")
        request = ExecutorRequest(
            query="edit graph",
            graph={"nodes": [{"id": 1}]},
            profile="default",
        )
        result = run_executor(request)

        assert result.ok is False
        assert result.failure_stage == "implement"

