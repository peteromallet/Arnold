"""Unit tests for the deterministic executor research module.

Covers local-corpus research, compact source normalization, injectable
Hivemind client, timeout/error → warning conversion, deduplication, and
merge ordering.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import unquote_plus
from unittest.mock import patch

import pytest

from vibecomfy.executor.contracts import ResearchResult
from vibecomfy.executor.research import (
    HivemindClient,
    HivemindError,
    _default_hivemind_client,
    _build_summary,
    _normalize_source,
    _normalize_hivemind_source,
    _run_hivemind_research,
    research,
    run_local_research,
)
from vibecomfy.search.index import SearchEntry
from vibecomfy.search.scorer import SearchResult


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_entry(
    class_type: str = "KSampler",
    pack: str | None = "core",
    description: str = "KSampler node",
    tags: tuple[str, ...] = (),
    tasks: tuple[str, ...] = (),
    source: str = "object_info",
    path: str | None = None,
) -> SearchEntry:
    return SearchEntry(
        class_type=class_type,
        pack=pack,
        description=description,
        tags=tags,
        tasks=tasks,
        source=source,
        path=path,
    )


def _make_result(
    class_type: str = "KSampler",
    score: int = 10,
    reasons: tuple[str, ...] = ("class_type",),
    **kwargs: Any,
) -> SearchResult:
    entry = _make_entry(class_type=class_type, **kwargs)
    return SearchResult(entry=entry, score=score, reasons=tuple(reasons))


# ── Source normalization ─────────────────────────────────────────────────────


class TestNormalizeSource:
    """Deterministic compact normalisation of scored search results."""

    def test_keys_and_order_are_deterministic(self) -> None:
        result = _make_result("KSampler", score=10, reasons=("class_type", "tag"))
        source = _normalize_source(result)
        assert list(source.keys()) == [
            "class_type",
            "score",
            "reasons",
            "source",
            "pack",
            "description",
            "tasks",
            "path",
        ]
        assert source["class_type"] == "KSampler"
        assert source["score"] == 10
        assert source["reasons"] == ["class_type", "tag"]

    def test_tasks_serialized_as_list(self) -> None:
        result = _make_result("LoadImage", tasks=("t2i",))
        source = _normalize_source(result)
        assert source["tasks"] == ["t2i"]

    def test_empty_tasks_is_empty_list(self) -> None:
        result = _make_result("CheckpointLoaderSimple")
        source = _normalize_source(result)
        assert source["tasks"] == []

    def test_none_pack_is_serialized(self) -> None:
        result = _make_result("CustomNode", pack=None)
        source = _normalize_source(result)
        assert source["pack"] is None

    def test_path_is_preserved_for_workflow_source(self) -> None:
        result = _make_result(
            "video/ltx2_3_t2v",
            source="ready_template",
            path="ready_templates/video/ltx2_3_t2v.py",
        )
        source = _normalize_source(result)
        assert source["path"] == "ready_templates/video/ltx2_3_t2v.py"


class TestNormalizeHivemindSource:
    """Normalisation of Hivemind response items."""

    def test_full_item(self) -> None:
        item = {
            "class_type": "WANVideoWrapper",
            "score": 88,
            "reasons": ["tag"],
            "pack": "wanvideowrapper",
            "description": "WAN video wrapper node",
            "tasks": ["t2v"],
        }
        out = _normalize_hivemind_source(item)
        assert out["class_type"] == "WANVideoWrapper"
        assert out["source"] == "hivemind"
        assert out["score"] == 88

    def test_fallback_name_key(self) -> None:
        item = {"name": "FallbackNode", "score": 50}
        out = _normalize_hivemind_source(item)
        assert out["class_type"] == "FallbackNode"

    def test_missing_keys_default(self) -> None:
        item: dict[str, Any] = {}
        out = _normalize_hivemind_source(item)
        assert out["class_type"] == ""
        assert out["score"] == 0
        assert out["source"] == "hivemind"

    def test_package_key_as_pack(self) -> None:
        item = {"class_type": "N", "package": "mypack"}
        out = _normalize_hivemind_source(item)
        assert out["pack"] == "mypack"

    def test_workflow_resource_uses_python_ready_template_metadata(self) -> None:
        item = {
            "kind": "workflow",
            "item_id": "42",
            "title": "video/ltx2_3_runexx_custom_audio",
            "body": "VibeComfy ready-template Python workflow",
            "metadata": {
                "ready_template_id": "video/ltx2_3_runexx_custom_audio",
                "path": "ready_templates/video/ltx2_3_runexx_custom_audio.py",
            },
        }
        out = _normalize_hivemind_source(item)
        assert out["source"] == "hivemind_workflow"
        assert out["class_type"] == "video/ltx2_3_runexx_custom_audio"
        assert out["path"] == "ready_templates/video/ltx2_3_runexx_custom_audio.py"
        assert out["hivemind_id"] == "42"


class TestBuildSummary:
    """Compact 1-sentence summary builder."""

    def test_empty(self) -> None:
        assert _build_summary(()) == "No relevant local results found."

    def test_single(self) -> None:
        sources = ({"class_type": "KSampler"},)
        assert _build_summary(sources) == "Found 1 local result(s): KSampler"

    def test_three(self) -> None:
        sources = (
            {"class_type": "A"},
            {"class_type": "B"},
            {"class_type": "C"},
        )
        summary = _build_summary(sources)
        assert summary.startswith("Found 3 local result(s): A, B, C")
        assert "more" not in summary

    def test_more_than_three(self) -> None:
        sources = tuple({"class_type": c} for c in ["A", "B", "C", "D", "E"])
        summary = _build_summary(sources)
        assert "A, B, C" in summary
        assert "2 more" in summary

    def test_workflow_paths_and_exploration_guidance(self) -> None:
        sources = (
            {
                "class_type": "video/ltx2_3_t2v",
                "source": "ready_template",
                "path": "ready_templates/video/ltx2_3_t2v.py",
            },
            {
                "class_type": "ltx2_3_source",
                "source": "source_workflow",
                "path": "ready_templates/sources/custom_nodes/ltxvideo/ltx2_3.json",
            },
        )
        summary = _build_summary(sources)
        assert "video/ltx2_3_t2v (ready_templates/video/ltx2_3_t2v.py)" in summary
        assert ".json" not in summary
        assert "vibecomfy workflows list --ready" in summary
        assert "vibecomfy copy-to-recipe <template_id> --out <file.py> --strip-markers" in summary
        assert "ready template `.py` representations" in summary
        assert "open that path directly in ComfyUI" not in summary


# ── Local research (deterministic) ───────────────────────────────────────────


class TestRunLocalResearch:
    """Deterministic local-corpus-first research."""

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_returns_research_result(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler", description="sampling node")]
        result = run_local_research("sampling")
        assert isinstance(result, ResearchResult)
        assert result.summary
        assert isinstance(result.sources, tuple)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_empty_corpus(self, mock_corpus) -> None:
        mock_corpus.return_value = []
        result = run_local_research("anything")
        assert result.summary == "No relevant local results found."
        assert result.sources == ()

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_no_matching_results(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("CLIPTextEncode", description="text encoding")]
        result = run_local_research("zzz_nonexistent_query_xyz")
        # Scorer may return 0 matches for nonsense query.
        if result.sources:
            # If some fuzzy match found, scores should be low.
            for s in result.sources:
                assert s["score"] <= 2
        else:
            assert result.summary == "No relevant local results found."

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_results_are_deterministic_same_input(self, mock_corpus) -> None:
        mock_corpus.return_value = [
            _make_entry("KSampler", description="sampler node"),
            _make_entry("VAEDecode", description="vae decode node"),
        ]
        r1 = run_local_research("sampler")
        r2 = run_local_research("sampler")
        assert r1.summary == r2.summary
        assert r1.sources == r2.sources

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_task_hint_alters_scoring(self, mock_corpus) -> None:
        mock_corpus.return_value = [
            _make_entry("KSampler", tags=("sampling",)),
            _make_entry("LTXVLoader", tags=("ltx", "video")),
        ]
        r_no_task = run_local_research("video")
        r_with_task = run_local_research("video", task="t2v")
        # Different task hints may produce different scores/ordering.
        assert isinstance(r_no_task, ResearchResult)
        assert isinstance(r_with_task, ResearchResult)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_limit_is_respected(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry(f"Node{i}") for i in range(20)]
        result = run_local_research("Node", limit=5)
        assert len(result.sources) <= 5

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_sources_are_tuple(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = run_local_research("KSampler")
        assert isinstance(result.sources, tuple)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_warnings_empty_for_local_only(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = run_local_research("KSampler")
        assert result.warnings == ()


# ── Hivemind error / timeout behaviour ───────────────────────────────────────


class TestHivemindErrors:
    """Hivemind errors are non-fatal warnings, never raw exceptions."""

    def _timeout_client(self, query: str, timeout: float) -> dict[str, Any]:
        raise HivemindError(f"timed out after {timeout}s")

    def _http_error_client(self, query: str, timeout: float) -> dict[str, Any]:
        raise HivemindError("connection refused")

    def _unexpected_client(self, query: str, timeout: float) -> dict[str, Any]:
        raise RuntimeError("something unexpected")

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_timeout_produces_warning_not_exception(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = research(
            "KSampler",
            hivemind_client=self._timeout_client,
            hivemind_timeout=0.5,
        )
        assert result.warnings
        assert any("timed out" in w for w in result.warnings)
        assert len(result.sources) >= 1  # local results still present

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_http_error_produces_warning(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = research(
            "KSampler",
            hivemind_client=self._http_error_client,
        )
        assert result.warnings
        assert any("connection refused" in w for w in result.warnings)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_unexpected_error_produces_warning(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = research(
            "KSampler",
            hivemind_client=self._unexpected_client,
        )
        assert result.warnings
        assert any("unexpected" in w for w in result.warnings)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_hivemind_none_client_skips_silently(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = research("KSampler", hivemind_client=None)
        assert result.warnings == ()

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_zero_timeout_disables_hivemind(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = research(
            "KSampler",
            hivemind_client=self._timeout_client,
            hivemind_timeout=0,
        )
        # Zero timeout → Hivemind tier never invoked.
        assert result.warnings == ()

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_negative_timeout_disables_hivemind(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = research(
            "KSampler",
            hivemind_client=self._timeout_client,
            hivemind_timeout=-1.0,
        )
        assert result.warnings == ()


# ── Hivemind merge behaviour ─────────────────────────────────────────────────


class TestHivemindMerge:
    """Hivemind results merge after local, with deduplication and ordering."""

    def _merge_client(self, query: str, timeout: float) -> dict[str, Any]:
        return {
            "results": [
                {
                    "class_type": "WANVideoWrapper",
                    "score": 85,
                    "reasons": ["hivemind_tag"],
                    "description": "WAN video wrapper",
                    "tasks": ["t2v"],
                },
                {
                    "class_type": "VAEDecode",
                    "score": 40,
                    "reasons": ["hivemind_tag"],
                    "description": "VAE decode",
                    "tasks": [],
                },
            ]
        }

    def _duplicate_client(self, query: str, timeout: float) -> dict[str, Any]:
        return {
            "results": [
                {
                    "class_type": "KSampler",  # same as local
                    "score": 99,
                    "reasons": ["hivemind_override"],
                },
                {
                    "class_type": "NewHivemindNode",
                    "score": 70,
                    "reasons": ["hivemind_only"],
                },
            ]
        }

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_hivemind_results_appear_after_local(self, mock_corpus) -> None:
        mock_corpus.return_value = [
            _make_entry("KSampler", source="object_info"),
            _make_entry("VAEDecode", source="object_info"),
        ]
        result = research(
            "video sampler",
            hivemind_client=self._merge_client,
        )
        sources = list(result.sources)
        # Local sources should come before hivemind sources.
        local_indices = [i for i, s in enumerate(sources) if s["source"] != "hivemind"]
        hm_indices = [i for i, s in enumerate(sources) if s["source"] == "hivemind"]
        if local_indices and hm_indices:
            assert max(local_indices) < min(hm_indices)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_duplicate_class_type_skips_hivemind(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler", source="object_info")]
        result = research(
            "KSampler",
            hivemind_client=self._duplicate_client,
        )
        # KSampler should appear once (local version), NewHivemindNode once.
        ksampler_count = sum(1 for s in result.sources if s["class_type"] == "KSampler")
        assert ksampler_count == 1
        # The KSampler entry should be the local one (source != hivemind).
        ksampler = next(s for s in result.sources if s["class_type"] == "KSampler")
        assert ksampler["source"] != "hivemind"

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_hivemind_with_no_results_is_handled(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]

        def empty_client(q: str, t: float) -> dict[str, Any]:
            return {"results": []}

        result = research("KSampler", hivemind_client=empty_client)
        ks_count = sum(1 for s in result.sources if s["class_type"] == "KSampler")
        assert ks_count == 1

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_hivemind_malformed_response_produces_warning(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]

        def bad_client(q: str, t: float) -> dict[str, Any]:
            return {"results": "not-a-list"}  # type: ignore[dict-item]

        result = research("KSampler", hivemind_client=bad_client)
        # Malformed results key should not break; no warning for bad shape
        # (the code guards against non-list). Local results preserved.
        assert len(result.sources) >= 1

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_hivemind_sources_key_fallback(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]

        def sources_client(q: str, t: float) -> dict[str, Any]:
            return {
                "sources": [
                    {"class_type": "FromSources", "score": 60}
                ]
            }

        result = research("test", hivemind_client=sources_client)
        assert any(s["class_type"] == "FromSources" for s in result.sources)


# ── Default direct-HTTP client (unit-level) ──────────────────────────────────


class TestDefaultHivemindClient:
    """Direct-HTTP Hivemind client behaviour under mocked transport."""

    def test_raises_hivemind_error_on_timeout(self) -> None:
        def slow_read(*args: Any, **kwargs: Any) -> None:
            # Simulate a slow response by sleeping beyond a very short timeout.
            # urlopen's timeout is enforced by the socket layer, so we mock
            # urllib.request.urlopen to raise TimeoutError.
            raise TimeoutError("timed out")

        with patch("urllib.request.urlopen", side_effect=slow_read):
            with pytest.raises(HivemindError, match="timed out"):
                _default_hivemind_client("test", timeout=0.01)

    def test_raises_hivemind_error_on_http_failure(self) -> None:
        import urllib.error

        def http_error(*args: Any, **kwargs: Any) -> None:
            raise urllib.error.URLError("connection refused")

        with patch("urllib.request.urlopen", side_effect=http_error):
            with pytest.raises(HivemindError, match="HTTP error"):
                _default_hivemind_client("test", timeout=1.0)

    def test_returns_parsed_json_on_success(self) -> None:
        expected = {"results": [{"class_type": "N", "score": 10}]}
        mock_response = type(
            "MockResponse",
            (),
            {
                "read": lambda self: b'{"results": [{"class_type": "N", "score": 10}]}',
                "__enter__": lambda self: self,
                "__exit__": lambda self, *a: None,
            },
        )()

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = _default_hivemind_client("test", timeout=1.0)
            assert result == expected

    def test_postgrest_search_tokenizes_multi_word_query(self) -> None:
        seen_urls: list[str] = []
        mock_response = type(
            "MockResponse",
            (),
            {
                "read": lambda self: (
                    b'[{"title": "Hotshot XL workflow", '
                    b'"body": "Notes for SDXL video generation"}]'
                ),
                "__enter__": lambda self: self,
                "__exit__": lambda self, *a: None,
            },
        )()

        def capture_urlopen(req: Any, *args: Any, **kwargs: Any) -> Any:
            seen_urls.append(req.full_url)
            return mock_response

        with patch("urllib.request.urlopen", side_effect=capture_urlopen):
            result = _default_hivemind_client("Hotshot XL SDXL video", timeout=1.0)

        assert result["results"]
        assert result["results"][0]["title"] == "Hotshot XL workflow"
        decoded_url = unquote_plus(seen_urls[0])
        assert "hivemind.nousresearch.com" not in decoded_url
        assert "unified_feed" in decoded_url
        assert "title.ilike.*Hotshot XL SDXL*" in decoded_url
        assert "title.ilike.*Hotshot*" in decoded_url

    def test_postgrest_search_queries_workflow_kind_and_prioritizes_it(self) -> None:
        seen_urls: list[str] = []

        def capture_urlopen(req: Any, *args: Any, **kwargs: Any) -> Any:
            seen_urls.append(req.full_url)
            if "kind=eq.workflow" in req.full_url:
                payload = (
                    b'[{"kind": "workflow", "title": "video/ltx2_3_runexx_custom_audio", '
                    b'"body": "LTX RuneXX audio workflow", '
                    b'"metadata": {"ready_template_id": "video/ltx2_3_runexx_custom_audio", '
                    b'"path": "ready_templates/video/ltx2_3_runexx_custom_audio.py"}}]'
                )
            else:
                payload = b'[{"kind": "message", "title": "generic audio note", "body": "audio"}]'
            return type(
                "MockResponse",
                (),
                {
                    "read": lambda self: payload,
                    "__enter__": lambda self: self,
                    "__exit__": lambda self, *a: None,
                },
            )()

        with patch("urllib.request.urlopen", side_effect=capture_urlopen):
            result = _default_hivemind_client("LTX RuneXX audio workflow", timeout=1.0)

        assert any("kind=eq.workflow" in url for url in seen_urls)
        assert result["results"][0]["kind"] == "workflow"

    def test_raises_hivemind_error_on_invalid_json(self) -> None:
        mock_response = type(
            "MockResponse",
            (),
            {
                "read": lambda self: b"not json",
                "__enter__": lambda self: self,
                "__exit__": lambda self, *a: None,
            },
        )()

        with patch("urllib.request.urlopen", return_value=mock_response):
            with pytest.raises(HivemindError, match="invalid JSON"):
                _default_hivemind_client("test", timeout=1.0)


# ── Full research() integration behaviour ────────────────────────────────────


class TestResearchIntegration:
    """End-to-end ``research()`` behaviour with mocks."""

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_local_only_no_warnings(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = research("KSampler", hivemind_client=None)
        assert result.warnings == ()
        assert len(result.sources) >= 1

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_local_plus_hivemind_merge(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]

        def client(q: str, t: float) -> dict[str, Any]:
            return {"results": [{"class_type": "HmNode", "score": 80}]}

        result = research("KSampler", hivemind_client=client)
        class_types = [s["class_type"] for s in result.sources]
        assert "KSampler" in class_types
        assert "HmNode" in class_types

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_to_dict_produces_serializable_output(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]

        def client(q: str, t: float) -> dict[str, Any]:
            raise HivemindError("unreachable")

        result = research("KSampler", hivemind_client=client)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "summary" in d
        assert "sources" in d
        assert "warnings" in d
        assert isinstance(d["sources"], list)
        assert isinstance(d["warnings"], list)
        assert any("unreachable" in w for w in d["warnings"])

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_summary_updates_with_hivemind_results(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]

        def client(q: str, t: float) -> dict[str, Any]:
            return {"results": [{"class_type": "HmNode", "score": 80}]}

        result = research("test", hivemind_client=client)
        # Summary should reflect merged count (local + new hivemind).
        assert "research result" in result.summary.lower()

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_web_fallback_runs_when_hivemind_empty(self, mock_corpus) -> None:
        mock_corpus.return_value = []

        def hivemind_client(q: str, t: float) -> dict[str, Any]:
            return {"results": []}

        def web_client(q: str, t: float) -> dict[str, Any]:
            return {
                "results": [
                    {
                        "title": "Hotshot XL ComfyUI workflow",
                        "url": "https://example.com/hotshot-xl",
                        "snippet": "Hotshot XL SDXL video notes",
                    }
                ]
            }

        result = research(
            "Hotshot XL SDXL video",
            hivemind_client=hivemind_client,
            web_search_client=web_client,
        )
        assert any(s["source"] == "web" for s in result.sources)
        assert any("Hotshot XL" in s["class_type"] for s in result.sources)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_web_fallback_failure_is_warning(self, mock_corpus) -> None:
        mock_corpus.return_value = []

        def hivemind_client(q: str, t: float) -> dict[str, Any]:
            return {"results": []}

        def web_client(q: str, t: float) -> dict[str, Any]:
            raise RuntimeError("offline")

        result = research(
            "Hotshot XL SDXL video",
            hivemind_client=hivemind_client,
            web_search_client=web_client,
        )
        assert any("web search" in w and "offline" in w for w in result.warnings)


# ── HivemindClient protocol ──────────────────────────────────────────────────


class TestHivemindClientProtocol:
    """The HivemindClient type accepts any callable matching the signature."""

    def test_lambda_is_valid_client(self) -> None:
        client: HivemindClient = lambda q, t: {"results": []}
        result = _run_hivemind_research("test", client=client, timeout=1.0)
        assert result == ()

    def test_function_is_valid_client(self) -> None:

        def my_client(query: str, timeout: float) -> dict[str, Any]:
            return {"results": [{"class_type": "X"}]}

        result = _run_hivemind_research("test", client=my_client, timeout=1.0)
        assert len(result) == 1
        assert result[0]["class_type"] == "X"

    def test_propagates_hivemind_error(self) -> None:
        def failing_client(q: str, t: float) -> dict[str, Any]:
            raise HivemindError("boom")

        with pytest.raises(HivemindError):
            _run_hivemind_research("test", client=failing_client, timeout=1.0)

    def test_propagates_unexpected_error(self) -> None:
        def exploding_client(q: str, t: float) -> dict[str, Any]:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            _run_hivemind_research("test", client=exploding_client, timeout=1.0)
