"""Tests for arnold.pipeline.llm_json.parse_llm_json.

Covers all four parse strategies plus the *multiple* parameter
and None-on-no-JSON behaviour.
"""

from __future__ import annotations

from typing import Any

import pytest

from arnold.pipeline.llm_json import parse_llm_json


# ── Strategy 1 — direct parse ──────────────────────────────────────────────


class TestDirectParse:
    """Strategy 1: direct json.loads of the whole string."""

    def test_direct_json_object(self) -> None:
        result = parse_llm_json(
            '{"questions": [{"q": "what?", "rationale": "why"}]}'
        )
        assert result == {"questions": [{"q": "what?", "rationale": "why"}]}

    def test_direct_json_with_whitespace(self) -> None:
        result = parse_llm_json(
            '  \n\n  {"questions": [{"q": "x", "rationale": "y"}]}  \n'
        )
        assert result == {"questions": [{"q": "x", "rationale": "y"}]}

    def test_direct_json_with_multiple_returns_list(self) -> None:
        """Direct parse of a dict with multiple=True returns a single-element list."""
        result = parse_llm_json(
            '{"key": "value"}', multiple=True
        )
        assert result == [{"key": "value"}]

    def test_direct_json_array_with_multiple(self) -> None:
        """Direct parse of a list-of-dicts with multiple=True returns the list."""
        result = parse_llm_json(
            '[{"a": 1}, {"b": 2}]', multiple=True
        )
        assert result == [{"a": 1}, {"b": 2}]

    def test_direct_json_array_single_mode_ignores(self) -> None:
        """A bare JSON array is not a dict, so single mode falls through."""
        result = parse_llm_json('[{"a": 1}]')
        assert result is None


# ── Strategy 2 — fenced block ──────────────────────────────────────────────


class TestFencedBlock:
    """Strategy 2: ```json ... ``` fenced block extraction."""

    def test_fenced_json_block(self) -> None:
        result = parse_llm_json(
            'Some preamble text\n```json\n{"questions": [{"q": "Q?", "rationale": "R"}]}\n```\nSome trailing text'
        )
        assert result == {"questions": [{"q": "Q?", "rationale": "R"}]}

    def test_fenced_json_block_with_extra_spaces(self) -> None:
        result = parse_llm_json(
            'Here is the output:\n\n```json\n{"key": "value"}\n```\n\nDone.'
        )
        assert result == {"key": "value"}

    def test_multiple_fenced_blocks_single_mode_returns_first(self) -> None:
        result = parse_llm_json(
            '```json\n{"first": true}\n```\n```json\n{"second": false}\n```'
        )
        assert result == {"first": True}

    def test_multiple_fenced_blocks_multiple_mode_returns_all(self) -> None:
        result = parse_llm_json(
            '```json\n{"first": true}\n```\n```json\n{"second": false}\n```',
            multiple=True,
        )
        assert result == [{"first": True}, {"second": False}]

    def test_fenced_array_with_multiple(self) -> None:
        result = parse_llm_json(
            '```json\n[{"a": 1}, {"b": 2}]\n```',
            multiple=True,
        )
        assert result == [{"a": 1}, {"b": 2}]


# ── Strategy 3 — embedded {}-scan ──────────────────────────────────────────


class TestEmbeddedScan:
    """Strategy 3: scan for first {}-delimited JSON object."""

    def test_embedded_json_object(self) -> None:
        result = parse_llm_json(
            'The response is {"questions": [{"q": "E?", "rationale": "E"}]} end.'
        )
        assert result == {"questions": [{"q": "E?", "rationale": "E"}]}

    def test_first_object_wins_with_multiple(self) -> None:
        result = parse_llm_json('{"first": true} some text {"second": false}')
        assert result == {"first": True}

    def test_multiple_embedded_multiple_mode(self) -> None:
        result = parse_llm_json(
            'a {"one": 1} b {"two": 2} c {"three": 3}',
            multiple=True,
        )
        assert result == [{"one": 1}, {"two": 2}, {"three": 3}]

    def test_nested_json_object(self) -> None:
        result = parse_llm_json(
            'Output: {"outer": {"inner": {"deep": true}}} done.'
        )
        assert result == {"outer": {"inner": {"deep": True}}}


# ── Strategy 4 — no dict found (None/[]) ───────────────────────────────────


class TestNoDictFound:
    """Strategy 4: graceful None/[] when no JSON dict is extractable."""

    def test_empty_string_returns_none(self) -> None:
        assert parse_llm_json("") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert parse_llm_json("   \n  \t  ") is None

    def test_array_only_returns_none(self) -> None:
        assert parse_llm_json("[1, 2, 3]") is None

    def test_scalar_only_returns_none(self) -> None:
        assert parse_llm_json('"just a string"') is None

    def test_unparsable_text_returns_none(self) -> None:
        assert parse_llm_json("This is not JSON at all.") is None

    def test_empty_string_multiple_returns_empty_list(self) -> None:
        assert parse_llm_json("", multiple=True) == []

    def test_whitespace_only_multiple_returns_empty_list(self) -> None:
        assert parse_llm_json("   \n  \t  ", multiple=True) == []

    def test_unparsable_multiple_returns_empty_list(self) -> None:
        assert parse_llm_json("no json here", multiple=True) == []


# ── Edge cases ─────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Additional edge cases for parse_llm_json."""

    def test_json_with_unicode(self) -> None:
        result = parse_llm_json('{"greeting": "héllo wörld"}')
        assert result == {"greeting": "héllo wörld"}

    def test_json_with_escaped_chars(self) -> None:
        result = parse_llm_json('{"path": "C:\\\\Users\\\\test"}')
        assert result == {"path": "C:\\Users\\test"}

    def test_multiple_dicts_in_fenced_and_embedded(self) -> None:
        """Fenced blocks are found before embedded scan."""
        text = '```json\n{"from_fence": true}\n```\nplus {"from_embed": false}'
        result = parse_llm_json(text)
        assert result == {"from_fence": True}

    def test_multiple_mode_fenced_plus_embedded(self) -> None:
        text = '```json\n{"from_fence": true}\n```\nplus {"from_embed": false}'
        result = parse_llm_json(text, multiple=True)
        assert len(result) == 2
        assert {"from_fence": True} in result
        assert {"from_embed": False} in result

    def test_broken_fence_skipped(self) -> None:
        """A broken fenced block is ignored; embedded scan still works."""
        text = '```json\nnot valid json at all\n```\nreal one: {"ok": true}'
        result = parse_llm_json(text)
        assert result == {"ok": True}

    def test_mixed_array_in_fence_multiple(self) -> None:
        text = '```json\n[{"a": 1}, {"b": 2}]\n```\n{"c": 3}'
        result = parse_llm_json(text, multiple=True)
        assert len(result) == 3
        assert {"a": 1} in result
        assert {"b": 2} in result
        assert {"c": 3} in result
