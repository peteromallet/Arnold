"""Tests for megaplan.observability.prompt_cache (T3)."""

import pytest
from megaplan.observability.prompt_cache import write_prompt_bytes, read_prompt_bytes


def test_write_read_roundtrip(tmp_path):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    path = write_prompt_bytes(
        plan_dir,
        "abc123",
        raw=b"hello world",
        canonical=b"canonical prompt",
        model_identity="gpt-4",
        params={"temperature": 0.7},
    )
    result = read_prompt_bytes(plan_dir, "abc123")
    assert result is not None
    assert result["raw"] == "hello world"
    assert result["canonical"] == "canonical prompt"
    assert result["model_identity"] == "gpt-4"
    assert result["params"] == {"temperature": 0.7}
    assert path.exists()


def test_idempotent_rewrite(tmp_path):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    p1 = write_prompt_bytes(plan_dir, "h1", raw=b"first", canonical=None, model_identity="m", params={})
    p2 = write_prompt_bytes(plan_dir, "h1", raw=b"second", canonical=None, model_identity="m", params={})
    assert p1 == p2
    result = read_prompt_bytes(plan_dir, "h1")
    assert result["raw"] == "first"


def test_read_unknown_hash_returns_none(tmp_path):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    assert read_prompt_bytes(plan_dir, "nonexistent") is None


def test_directory_does_not_preexist(tmp_path):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    store_dir = plan_dir / "evaluand_prompts"
    assert not store_dir.exists()
    path = write_prompt_bytes(
        plan_dir,
        "xyz",
        raw=b"data",
        canonical=None,
        model_identity="m",
        params={},
    )
    assert store_dir.exists()
    assert path.exists()
    result = read_prompt_bytes(plan_dir, "xyz")
    assert result is not None
