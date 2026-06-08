"""Tests for the symmetric envelope subprocess handshake.

Covers:
- parent writes ``.envelope-in.json`` + ``MEGAPLAN_ENVELOPE_IN`` env var
- child consumes the sidecar AND pops the env var (no grandchild leak)
- grandchildren get a FRESH per-spawn sidecar (nested-spawn leak gate)
- outbound ``.envelope-out.json`` sidecar
- tagged-stderr fallback for envelope egress
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from arnold.pipelines.megaplan._pipeline.envelope import (
    ENVELOPE_ENV_VAR,
    ENVELOPE_IN_FILENAME,
    ENVELOPE_OUT_FILENAME,
    ENVELOPE_STDERR_TAG,
    EMPTY_ENVELOPE,
    consume_envelope_in,
    format_envelope_stderr_tag,
    make_envelope,
    parse_envelope_stderr_tag,
    read_envelope_out,
    write_envelope_in,
    write_envelope_out,
    _envelope_ctx,
)


def test_write_envelope_in_writes_sidecar_and_returns_env(tmp_path):
    env = make_envelope(taint="tainted", cost=1.5, lineage=("a", "b"))
    overrides = write_envelope_in(tmp_path, env)
    assert overrides == {ENVELOPE_ENV_VAR: str(tmp_path / ENVELOPE_IN_FILENAME)}
    payload = json.loads((tmp_path / ENVELOPE_IN_FILENAME).read_text())
    assert payload["taint"] == "tainted"
    assert payload["cost"] == 1.5
    assert payload["lineage"] == ["a", "b"]


def test_consume_envelope_in_pops_env_var(tmp_path, monkeypatch):
    env = make_envelope(taint="tainted", cost=2.0)
    overrides = write_envelope_in(tmp_path, env)
    monkeypatch.setenv(ENVELOPE_ENV_VAR, overrides[ENVELOPE_ENV_VAR])
    loaded = consume_envelope_in()
    assert loaded == env
    # Critical: env var is popped so grandchildren do not inherit it.
    assert ENVELOPE_ENV_VAR not in os.environ


def test_consume_envelope_in_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv(ENVELOPE_ENV_VAR, raising=False)
    assert consume_envelope_in() is None


def test_nested_spawn_grandchild_gets_fresh_envelope_and_no_leak(
    tmp_path, monkeypatch
):
    """Parent->child->grandchild: grandchild's sidecar path differs and
    ``MEGAPLAN_ENVELOPE_IN`` is unset inside the child immediately after consume.

    This is SC7's gate: a grandchild spawn must not inherit the parent's env;
    every spawn writes a fresh ``.envelope-in.json`` in its own subdir.
    """
    parent_env = make_envelope(taint="tainted", cost=1.0, lineage=("parent",))
    child_env = make_envelope(taint="tainted", cost=4.0, lineage=("parent", "child"))

    parent_dir = tmp_path / "parent"
    grandchild_dir = tmp_path / "parent" / "grandchild"
    parent_dir.mkdir()
    grandchild_dir.mkdir(parents=True)

    # 1. Parent writes its sidecar + sets env for child spawn.
    parent_overrides = write_envelope_in(parent_dir, parent_env)
    parent_path = parent_overrides[ENVELOPE_ENV_VAR]
    monkeypatch.setenv(ENVELOPE_ENV_VAR, parent_path)

    # 2. Child consumes — env MUST be popped at this moment, before child can
    # spawn anything of its own.
    loaded_in_child = consume_envelope_in()
    assert loaded_in_child == parent_env
    assert ENVELOPE_ENV_VAR not in os.environ, (
        "env var must be popped immediately after child consumption — "
        "otherwise grandchildren inherit parent envelope by env-leak"
    )

    # 3. Child spawns grandchild: writes a FRESH per-spawn sidecar in a NEW dir
    # with a new envelope (child has joined its own cost).
    grand_overrides = write_envelope_in(grandchild_dir, child_env)
    grand_path = grand_overrides[ENVELOPE_ENV_VAR]
    assert grand_path != parent_path, "grandchild path must differ from parent's"
    assert Path(grand_path).parent == grandchild_dir

    # 4. Grandchild env override visible.
    monkeypatch.setenv(ENVELOPE_ENV_VAR, grand_path)
    loaded_in_grandchild = consume_envelope_in()
    assert loaded_in_grandchild == child_env
    assert loaded_in_grandchild != parent_env
    assert ENVELOPE_ENV_VAR not in os.environ


def test_outbound_sidecar_roundtrip(tmp_path):
    env = make_envelope(taint="tainted", cost=3.3, lineage=("x",))
    path = write_envelope_out(tmp_path, env)
    assert path.name == ENVELOPE_OUT_FILENAME
    assert read_envelope_out(tmp_path) == env


def test_outbound_sidecar_absent_returns_none(tmp_path):
    assert read_envelope_out(tmp_path) is None


def test_tagged_stderr_fallback_roundtrip():
    env = make_envelope(taint="tainted", cost=0.5)
    line = format_envelope_stderr_tag(env)
    assert line.startswith(ENVELOPE_STDERR_TAG)
    stderr = f"some-noise\n{line}\nmore-noise\n"
    parsed = parse_envelope_stderr_tag(stderr)
    assert parsed == env


def test_tagged_stderr_fallback_returns_none_when_absent():
    assert parse_envelope_stderr_tag("nothing tagged here\n") is None


def test_apply_envelope_handshake_in_auto(tmp_path, monkeypatch):
    """``_apply_envelope_handshake`` merges env override into progress_env when
    ``_envelope_ctx`` is set; no-op when unset."""
    from arnold.pipelines.megaplan.auto import _apply_envelope_handshake

    run_kwargs: dict = {}
    # No envelope set: handshake is a no-op.
    _apply_envelope_handshake(run_kwargs, tmp_path)
    assert "progress_env" not in run_kwargs

    env = make_envelope(taint="tainted", cost=2.0)
    token = _envelope_ctx.set(env)
    try:
        run_kwargs = {"progress_env": {"FOO": "bar"}}
        _apply_envelope_handshake(run_kwargs, tmp_path)
        assert run_kwargs["progress_env"]["FOO"] == "bar"
        assert run_kwargs["progress_env"][ENVELOPE_ENV_VAR] == str(
            tmp_path / ENVELOPE_IN_FILENAME
        )
        assert (tmp_path / ENVELOPE_IN_FILENAME).exists()
    finally:
        _envelope_ctx.reset(token)

    # No plan_dir: handshake is also a no-op.
    token = _envelope_ctx.set(env)
    try:
        run_kwargs = {}
        _apply_envelope_handshake(run_kwargs, None)
        assert "progress_env" not in run_kwargs
    finally:
        _envelope_ctx.reset(token)
