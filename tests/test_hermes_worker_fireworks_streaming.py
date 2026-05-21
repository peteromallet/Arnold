"""Tests for high-token streaming in the Hermes worker.

Fireworks rejects requests with ``max_tokens > 4096`` unless ``stream=true``.
Direct DeepSeek is intentionally kept on the same high-token streaming path so
it behaves like the known-good Fireworks DeepSeek route.
The hermes worker must:
  (a) detect high-token Fireworks/direct-DeepSeek models and force the streaming
      path, with reassembly hidden from the rest of megaplan; and
  (b) when a provider returns a real 400 (or any other error), propagate
      it as a hard failure rather than silently degrading to empty output.

These tests don't hit the network — they exercise the streaming flag plumbing
and the failure propagation by mocking ``AIAgent``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from megaplan._core import atomic_write_json, atomic_write_text, read_json, schemas_root
from megaplan.audits.robustness import checks_for_robustness
from megaplan.workers.hermes import (
    _no_op_stream,
    _provider_requires_streaming,
    _streaming_run_kwargs,
    parse_agent_output,
)
from megaplan.orchestration.parallel_critique import _run_check
from megaplan.prompts.critique import write_single_check_template
from megaplan.types import CliError, PlanState
from megaplan.workers import STEP_SCHEMA_FILENAMES


REPO_ROOT = Path(__file__).resolve().parents[1]


def _state(project_dir: Path, *, iteration: int = 1) -> PlanState:
    return {
        "name": "fireworks-streaming-test",
        "idea": "force streaming for fireworks",
        "current_state": "planned",
        "iteration": iteration,
        "created_at": "2026-04-01T00:00:00Z",
        "config": {
            "project_dir": str(project_dir),
            "auto_approve": False,
            "robustness": "standard",
        },
        "sessions": {},
        "plan_versions": [
            {
                "version": iteration,
                "file": f"plan_v{iteration}.md",
                "hash": "sha256:test",
                "timestamp": "2026-04-01T00:00:00Z",
            }
        ],
        "history": [],
        "meta": {
            "significant_counts": [],
            "weighted_scores": [],
            "plan_deltas": [],
            "recurring_critiques": [],
            "total_cost_usd": 0.0,
            "overrides": [],
            "notes": [],
        },
        "last_gate": {},
    }


def _scaffold(tmp_path: Path) -> tuple[Path, Path, PlanState]:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    state = _state(project_dir)
    atomic_write_text(plan_dir / "plan_v1.md", "# Plan\nDo it.\n")
    atomic_write_json(
        plan_dir / "plan_v1.meta.json",
        {
            "version": 1,
            "timestamp": "2026-04-01T00:00:00Z",
            "hash": "sha256:test",
            "success_criteria": [{"criterion": "criterion", "priority": "must"}],
            "questions": [],
            "assumptions": [],
        },
    )
    atomic_write_json(plan_dir / "faults.json", {"flags": []})
    return plan_dir, project_dir, state


def _critique_schema() -> dict:
    return read_json(schemas_root(REPO_ROOT) / STEP_SCHEMA_FILENAMES["critique"])


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_provider_requires_streaming_for_high_token_fireworks_and_direct_deepseek() -> None:
    # Fireworks + > 4096 → must stream
    assert _provider_requires_streaming("fireworks:accounts/fireworks/models/kimi-k2p6", 8192) is True
    assert _provider_requires_streaming("fireworks:foo", 4097) is True

    # Fireworks at the threshold — Fireworks itself only requires streaming
    # for ``> 4096``, so 4096 must NOT force streaming.
    assert _provider_requires_streaming("fireworks:foo", 4096) is False
    assert _provider_requires_streaming("fireworks:foo", None) is False

    # Direct DeepSeek mirrors the Fireworks high-token streaming path.
    assert _provider_requires_streaming("deepseek:deepseek-v4-pro", 16384) is True
    assert _provider_requires_streaming("deepseek:deepseek-v4-pro", 4096) is False

    # Other providers don't need this even at very high max_tokens
    assert _provider_requires_streaming("openrouter/anthropic/claude", 16384) is False
    assert _provider_requires_streaming("minimax:MiniMax-M2", 16384) is False
    assert _provider_requires_streaming(None, 16384) is False


def test_streaming_run_kwargs_returns_callback_only_when_required() -> None:
    from megaplan.workers.hermes import _streaming_run_kwargs, _StreamTracker

    # Fireworks high max_tokens → callback present
    kwargs = _streaming_run_kwargs("fireworks:foo", 8192)
    assert "stream_callback" in kwargs
    assert isinstance(kwargs["stream_callback"], _StreamTracker)

    # Direct DeepSeek high max_tokens mirrors Fireworks.
    assert "stream_callback" in _streaming_run_kwargs("deepseek:deepseek-v4-pro", 8192)

    # Other provider → empty kwargs (no streaming forced)
    assert _streaming_run_kwargs("openrouter/anthropic/claude", 16384) == {}
    assert _streaming_run_kwargs("fireworks:foo", 4096) == {}


# ---------------------------------------------------------------------------
# Streaming gets enabled end-to-end through parallel_critique
# ---------------------------------------------------------------------------


def test_run_check_uses_streaming_for_fireworks_high_max_tokens(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """End-to-end: a Fireworks model + max_tokens=8192 must hit the agent's
    streaming path.  We assert that ``stream_callback`` is forwarded to
    ``run_conversation`` so AIAgent flips on streaming and reassembles.
    """
    plan_dir, project_dir, state = _scaffold(tmp_path)
    check = checks_for_robustness("standard")[0]
    schema = _critique_schema()
    payload = {
        "checks": [
            {
                "id": check["id"],
                "question": check["question"],
                "guidance": check["guidance"],
                "prior_findings": [],
                "findings": [
                    {
                        "detail": "Streaming reassembled the response correctly for the fireworks call.",
                        "flagged": False,
                    }
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

    class FakeSessionDB:
        def __init__(self, db_path=None):
            pass

    class FakeAIAgent:
        instances: list["FakeAIAgent"] = []

        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            self.calls: list[dict[str, object]] = []
            self._print_fn = None
            self.__class__.instances.append(self)

        def run_conversation(self, **kwargs: object) -> dict[str, object]:
            self.calls.append(kwargs)
            return {
                "final_response": json.dumps(payload),
                "messages": [{"role": "assistant", "content": json.dumps(payload)}],
                "estimated_cost_usd": 0.0,
            }

    monkeypatch.setitem(sys.modules, "run_agent", ModuleType("run_agent"))
    monkeypatch.setitem(sys.modules, "hermes_state", ModuleType("hermes_state"))
    sys.modules["run_agent"].AIAgent = FakeAIAgent
    sys.modules["hermes_state"].SessionDB = FakeSessionDB

    _run_check(
        0,
        check,
        state=state,
        plan_dir=plan_dir,
        root=tmp_path,
        model="fireworks:accounts/fireworks/models/kimi-k2p6",
        schema=schema,
        project_dir=project_dir,
    )

    assert len(FakeAIAgent.instances) == 1
    agent = FakeAIAgent.instances[0]
    # max_tokens=32768 (parallel_critique default after merging main's Qwen-cap
    # values) > 4096, so the Fireworks streaming workaround must be active.
    assert agent.kwargs["max_tokens"] == 32768
    assert agent.calls, "agent should have been invoked"
    # The call must carry a stream_callback — that's how AIAgent decides to
    # request stream=true on the underlying chat.completions call.
    assert "stream_callback" in agent.calls[0]
    from megaplan.workers.hermes import _StreamTracker
    assert isinstance(agent.calls[0]["stream_callback"], _StreamTracker)


def test_run_check_does_not_force_streaming_for_other_providers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Sanity check: non-Fireworks providers must NOT receive a stream_callback.

    Streaming is a Fireworks-only quirk — adding it everywhere would change
    the wire format for every provider.
    """
    plan_dir, project_dir, state = _scaffold(tmp_path)
    check = checks_for_robustness("standard")[0]
    schema = _critique_schema()
    payload = {
        "checks": [
            {
                "id": check["id"],
                "question": check["question"],
                "guidance": check["guidance"],
                "prior_findings": [],
                "findings": [
                    {"detail": "Non-fireworks providers never need streaming.", "flagged": False}
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

    class FakeSessionDB:
        def __init__(self, db_path=None):
            pass

    class FakeAIAgent:
        instances: list["FakeAIAgent"] = []

        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            self.calls: list[dict[str, object]] = []
            self._print_fn = None
            self.__class__.instances.append(self)

        def run_conversation(self, **kwargs: object) -> dict[str, object]:
            self.calls.append(kwargs)
            return {
                "final_response": json.dumps(payload),
                "messages": [{"role": "assistant", "content": json.dumps(payload)}],
                "estimated_cost_usd": 0.0,
            }

    monkeypatch.setitem(sys.modules, "run_agent", ModuleType("run_agent"))
    monkeypatch.setitem(sys.modules, "hermes_state", ModuleType("hermes_state"))
    sys.modules["run_agent"].AIAgent = FakeAIAgent
    sys.modules["hermes_state"].SessionDB = FakeSessionDB

    _run_check(
        0,
        check,
        state=state,
        plan_dir=plan_dir,
        root=tmp_path,
        model="openrouter/anthropic/claude-opus-4.6",
        schema=schema,
        project_dir=project_dir,
    )

    agent = FakeAIAgent.instances[0]
    assert "stream_callback" not in agent.calls[0]


# ---------------------------------------------------------------------------
# Real Fireworks 400 must propagate (no silent degradation)
# ---------------------------------------------------------------------------


def test_run_check_propagates_fireworks_400(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """If Fireworks returns a real 400, the worker must raise — not return
    empty output.  This is what kept the bakeoff plan stalled at ``planned``
    state with an empty critique_output.json: the call failed but the worker
    must not paper over it.
    """
    plan_dir, project_dir, state = _scaffold(tmp_path)
    check = checks_for_robustness("standard")[0]
    schema = _critique_schema()

    class FakeSessionDB:
        def __init__(self, db_path=None):
            pass

    class FailingAIAgent:
        instances: list["FailingAIAgent"] = []

        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            self.__class__.instances.append(self)
            self._print_fn = None

        def run_conversation(self, **kwargs: object):
            # Mirror the real Fireworks SDK error shape — even with stream=true
            # set (we did our part), Fireworks can still 400 for other reasons
            # and the worker must surface it.
            raise RuntimeError(
                "Error code: 400 - {'error': {'message': 'Bad request', "
                "'param': 'messages', 'code': 'BAD_REQUEST', 'type': 'error'}, "
                "'request_id': 'chatcmpl-test'}"
            )

    monkeypatch.setitem(sys.modules, "run_agent", ModuleType("run_agent"))
    monkeypatch.setitem(sys.modules, "hermes_state", ModuleType("hermes_state"))
    sys.modules["run_agent"].AIAgent = FailingAIAgent
    sys.modules["hermes_state"].SessionDB = FakeSessionDB

    with pytest.raises(RuntimeError, match="400"):
        _run_check(
            0,
            check,
            state=state,
            plan_dir=plan_dir,
            root=tmp_path,
            model="fireworks:accounts/fireworks/models/kimi-k2p6",
            schema=schema,
            project_dir=project_dir,
        )


# ---------------------------------------------------------------------------
# parse_agent_output forwards run_kwargs to its summary fallback
# ---------------------------------------------------------------------------


def test_parse_agent_output_summary_prompt_carries_streaming_kwargs(tmp_path: Path) -> None:
    """The follow-up "summary" run_conversation call (used when the model
    finished with tool calls but no JSON) must also carry the stream_callback
    so it doesn't get rejected by Fireworks for the same max_tokens reason.
    """
    plan_dir, project_dir, state = _scaffold(tmp_path)
    check = checks_for_robustness("standard")[0]
    output_path = write_single_check_template(plan_dir, state, check, "critique_check_x.json")
    payload = {
        "checks": [
            {
                "id": check["id"],
                "question": check["question"],
                "guidance": check["guidance"],
                "prior_findings": [],
                "findings": [
                    {"detail": "Recovered JSON via the summary fallback prompt.", "flagged": False}
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

    class FakeAgent:
        def __init__(self, followup: dict[str, object]) -> None:
            self.followup = followup
            self.calls: list[dict[str, object]] = []

        def run_conversation(self, **kwargs: object) -> dict[str, object]:
            self.calls.append(kwargs)
            return self.followup

    initial_result = {
        "final_response": "",
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [{"function": {"name": "read_file", "arguments": "{}"}}],
            }
        ],
    }
    followup = {
        "final_response": json.dumps(payload),
        "messages": [{"role": "assistant", "content": json.dumps(payload)}],
    }
    agent = FakeAgent(followup)

    parse_agent_output(
        agent,
        initial_result,
        output_path=output_path,
        schema=_critique_schema(),
        step="critique",
        project_dir=project_dir,
        plan_dir=plan_dir,
        run_kwargs=_streaming_run_kwargs("fireworks:foo", 8192),
    )

    assert len(agent.calls) == 1
    from megaplan.workers.hermes import _StreamTracker
    assert isinstance(agent.calls[0].get("stream_callback"), _StreamTracker)
