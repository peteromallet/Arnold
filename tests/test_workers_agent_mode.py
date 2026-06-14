"""Direct agent-mode and session-state tests for megaplan.workers."""

from __future__ import annotations

from argparse import Namespace

import pytest
from unittest.mock import patch

from arnold.pipelines.megaplan.types import CliError
from arnold.pipelines.megaplan.workers import resolve_agent_mode, session_key_for, update_session_state
from tests._workers_helpers import FakeShutil


def test_session_key_for_matches_new_roles() -> None:
    assert session_key_for("plan", "claude") == "claude_planner"
    assert session_key_for("revise", "codex") == "codex_planner"
    assert session_key_for("critique", "codex") == "codex_critic"
    assert session_key_for("gate", "claude") == "claude_gatekeeper"
    assert session_key_for("execute", "claude") == "claude_executor"

def test_resolve_agent_mode_uses_configured_fallback() -> None:
    with patch("arnold.pipelines.megaplan.workers._impl.shutil.which", side_effect=lambda name: None if name == "claude" else "/usr/bin/codex"):
        with patch("arnold.pipelines.megaplan.workers._impl.detect_available_agents", return_value=["codex"]):
            with patch("arnold.pipelines.megaplan.workers._impl.load_config", return_value={"agents": {"plan": "claude"}}):
                args = Namespace(agent=None, ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[])
                agent, mode, refreshed, model = resolve_agent_mode("plan", args)
    assert agent == "codex"
    assert mode == "persistent"
    assert refreshed is False
    assert args._agent_fallback["requested"] == "claude"

def test_resolve_agent_mode_for_review_claude_defaults_to_fresh() -> None:
    with patch("arnold.pipelines.megaplan._core.io.shutil", FakeShutil("bun", "tmux", "claude")):
        agent, mode, refreshed, model = resolve_agent_mode("review", Namespace(agent="claude", ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]))
    assert agent == "claude"
    assert mode == "persistent"
    assert refreshed is True

def test_session_key_for_all_steps() -> None:
    assert session_key_for("plan", "claude") == "claude_planner"
    assert session_key_for("revise", "claude") == "claude_planner"
    assert session_key_for("critique", "claude") == "claude_critic"
    assert session_key_for("gate", "claude") == "claude_gatekeeper"
    assert session_key_for("execute", "claude") == "claude_executor"
    assert session_key_for("review", "claude") == "claude_reviewer"
    assert session_key_for("plan", "codex") == "codex_planner"
    assert session_key_for("revise", "codex") == "codex_planner"
    assert session_key_for("critique", "codex") == "codex_critic"
    assert session_key_for("gate", "codex") == "codex_gatekeeper"
    assert session_key_for("execute", "codex") == "codex_executor"
    assert session_key_for("review", "codex") == "codex_reviewer"

def test_session_key_for_unknown_step_uses_step_name() -> None:
    assert session_key_for("custom", "claude") == "claude_custom"

def test_session_key_differs_by_model() -> None:
    """Session keys incorporate resolved model hash for session isolation."""
    import hashlib
    base_key = session_key_for("plan", "codex")
    key_default = session_key_for("plan", "codex", model="gpt-5.5")
    key_pinned = session_key_for("plan", "codex", model="gpt-5.3-codex")
    # No-model key is bare
    assert base_key == "codex_planner"
    # Model-aware keys include hash
    assert key_default == "codex_planner_" + hashlib.sha256("gpt-5.5".encode()).hexdigest()[:8]
    assert key_pinned == "codex_planner_" + hashlib.sha256("gpt-5.3-codex".encode()).hexdigest()[:8]
    # Different models produce different keys
    assert key_default != key_pinned
    assert key_default != base_key
    # Claude models also differ
    claude_default = session_key_for("plan", "claude", model="claude-opus-4-7")
    claude_pinned = session_key_for("plan", "claude", model="sonnet-4.6")
    assert claude_default == "claude_planner_" + hashlib.sha256("claude-opus-4-7".encode()).hexdigest()[:8]
    assert claude_pinned == "claude_planner_" + hashlib.sha256("sonnet-4.6".encode()).hexdigest()[:8]
    assert claude_default != claude_pinned
    # Model=None stays bare
    assert session_key_for("critique", "claude") == "claude_critic"
    assert session_key_for("critique", "claude", model=None) == "claude_critic"

def test_session_key_used_consistently_in_apply_session_update() -> None:
    """apply_session_update uses model-aware session keys."""
    import hashlib
    from arnold.pipelines.megaplan._core.state import apply_session_update
    from arnold.pipelines.megaplan.workers._impl import session_key_for as skf

    state: dict = {"sessions": {}, "config": {}}
    resolved_model = "gpt-5.5"
    apply_session_update(
        state, "plan", "codex", "sess-123",
        mode="persistent", refreshed=True, model=resolved_model,
    )
    expected_key = skf("plan", "codex", model=resolved_model)
    assert expected_key in state["sessions"]
    assert state["sessions"][expected_key]["id"] == "sess-123"
    assert state["sessions"][expected_key]["mode"] == "persistent"
    # Different model creates different key
    apply_session_update(
        state, "plan", "codex", "sess-456",
        mode="persistent", refreshed=True, model="gpt-5.3-codex",
    )
    other_key = skf("plan", "codex", model="gpt-5.3-codex")
    assert other_key in state["sessions"]
    assert expected_key != other_key
    assert state["sessions"][other_key]["id"] == "sess-456"

def test_resolve_agent_mode_cli_flag_override() -> None:
    with patch("arnold.pipelines.megaplan.workers._impl.shutil.which", return_value="/usr/bin/codex"):
        agent, mode, refreshed, model = resolve_agent_mode("plan", Namespace(agent="codex", ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]))
    assert agent == "codex"

def test_resolve_agent_mode_config_override() -> None:
    with patch("arnold.pipelines.megaplan.workers._impl.shutil.which", return_value="/usr/bin/codex"):
        with patch("arnold.pipelines.megaplan.workers._impl.load_config", return_value={"agents": {"plan": "codex"}}):
            agent, mode, refreshed, model = resolve_agent_mode("plan", Namespace(agent=None, ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]))
    assert agent == "codex"


def test_resolve_agent_mode_resolves_symbolic_default_routing_through_vendor() -> None:
    with patch("arnold.pipelines.megaplan.workers._impl._is_agent_available", return_value=True):
        with patch("arnold.pipelines.megaplan.workers._impl.load_config", return_value={"vendor": "codex", "agents": {}}):
            agent, mode, refreshed, model = resolve_agent_mode(
                "plan",
                Namespace(
                    agent=None,
                    vendor=None,
                    ephemeral=False,
                    fresh=False,
                    persist=False,
                    confirm_self_review=False,
                    hermes=None,
                    phase_model=[],
                ),
            )

    assert agent == "codex"
    assert mode == "persistent"
    assert refreshed is False


def test_resolve_agent_mode_rejects_unresolved_premium_before_dispatch() -> None:
    with pytest.raises(CliError, match="Unresolved premium placeholder reached worker dispatch"):
        resolve_agent_mode(
            "plan",
            Namespace(
                agent=None,
                vendor=None,
                ephemeral=False,
                fresh=False,
                persist=False,
                confirm_self_review=False,
                hermes=None,
                phase_model=["plan=premium:low"],
            ),
        )


def test_resolve_agent_mode_explicit_missing_raises() -> None:
    with patch("arnold.pipelines.megaplan.workers._impl.shutil.which", return_value=None):
        with pytest.raises(CliError, match="not found"):
            resolve_agent_mode("plan", Namespace(agent="nosuchagent", ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]))

def test_resolve_agent_mode_no_agents_raises() -> None:
    with patch("arnold.pipelines.megaplan.workers._impl.shutil.which", return_value=None):
        with patch("arnold.pipelines.megaplan.workers._impl.load_config", return_value={}):
            with patch("arnold.pipelines.megaplan.workers._impl.detect_available_agents", return_value=[]):
                with pytest.raises(CliError, match="No supported agents"):
                    resolve_agent_mode("plan", Namespace(agent=None, ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]))

def test_resolve_agent_mode_conflicting_flags_raises() -> None:
    with patch("arnold.pipelines.megaplan.workers._impl.shutil.which", return_value="/usr/bin/claude"):
        with pytest.raises(CliError, match="Cannot combine"):
            resolve_agent_mode("plan", Namespace(agent=None, ephemeral=True, fresh=True, persist=False, confirm_self_review=False, hermes=None, phase_model=[]))

def test_resolve_agent_mode_ephemeral_mode() -> None:
    with patch("arnold.pipelines.megaplan.workers._impl.shutil.which", return_value="/usr/bin/claude"):
        agent, mode, refreshed, model = resolve_agent_mode("plan", Namespace(agent="claude", ephemeral=True, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]))
    assert mode == "ephemeral"
    assert refreshed is True

def test_resolve_agent_mode_no_config_default_routing_resolves_through_vendor() -> None:
    """When load_config returns an empty dict (no user config), no explicit
    --agent, and no phase_model, the DEFAULT_AGENT_ROUTING symbolic premium
    fallback must resolve through effective_premium_vendor to a concrete
    dispatchable agent."""
    with patch("arnold.pipelines.megaplan.workers._impl.shutil.which", side_effect=lambda name: "/usr/bin/codex" if name == "codex" else None):
        with patch("arnold.pipelines.megaplan.workers._impl.load_config", return_value={}):
            with patch("arnold.pipelines.megaplan.workers._impl.effective_premium_vendor", return_value="codex"):
                with patch("arnold.pipelines.megaplan.workers._impl.detect_available_agents", return_value=["codex"]):
                    agent, mode, refreshed, model = resolve_agent_mode(
                        "critique_evaluator",
                        Namespace(agent=None, vendor=None, ephemeral=False, fresh=False,
                                  persist=False, confirm_self_review=False, hermes=None,
                                  phase_model=[]),
                    )
    assert agent == "codex"
    assert mode == "persistent"
    assert refreshed is False


def test_update_session_state_preserves_created_at() -> None:
    result = update_session_state(
        "gate",
        "claude",
        "session-123",
        mode="persistent",
        refreshed=False,
        existing_sessions={"claude_gatekeeper": {"created_at": "2026-01-01T00:00:00Z"}},
    )
    assert result is not None
    key, entry = result
    assert key == "claude_gatekeeper"
    assert entry["created_at"] == "2026-01-01T00:00:00Z"

def test_update_session_state_returns_none_for_no_session_id() -> None:
    result = update_session_state("plan", "claude", None, mode="persistent", refreshed=False)
    assert result is None

def test_update_session_state_creates_new_entry() -> None:
    result = update_session_state("plan", "claude", "sess-abc", mode="persistent", refreshed=False)
    assert result is not None
    key, entry = result
    assert key == "claude_planner"
    assert entry["id"] == "sess-abc"
    assert entry["mode"] == "persistent"

def test_update_session_state_preserves_token_snapshot_for_same_session() -> None:
    existing = {
        "codex_executor": {
            "id": "sess-abc",
            "mode": "persistent",
            "last_total_tokens": {"input_tokens": 1000},
        }
    }
    result = update_session_state(
        "execute",
        "codex",
        "sess-abc",
        mode="persistent",
        refreshed=False,
        existing_sessions=existing,
    )
    assert result is not None
    _key, entry = result
    assert entry["last_total_tokens"] == {"input_tokens": 1000}

def test_update_session_state_does_not_copy_token_snapshot_to_new_session() -> None:
    existing = {
        "codex_executor": {
            "id": "old-session",
            "mode": "persistent",
            "last_total_tokens": {"input_tokens": 1000},
        }
    }
    result = update_session_state(
        "execute",
        "codex",
        "new-session",
        mode="persistent",
        refreshed=True,
        existing_sessions=existing,
    )
    assert result is not None
    _key, entry = result
    assert "last_total_tokens" not in entry
