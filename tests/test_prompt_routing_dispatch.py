"""Prompt-routing dispatch tests for gate, review, and tiebreaker handler paths.

Proves that normal worker dispatch and handler ``prompt_override`` paths are
rendered through ``render_prompt_for_dispatch()`` or an approved seam path
(``render_step_message(StepInvocation(...))``) before model invocation.

These tests capture the current dispatch routing contract for the five
migrated sites (execute, finalize, critique, review, gate) plus tiebreaker.
"""

from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from arnold.pipelines.megaplan.model_seam import (
    render_prompt_for_dispatch,
    render_step_message,
    StepInvocation,
)


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _base_state(tmp_path: Path, *, name: str = "test-plan", mode: str = "code") -> dict[str, Any]:
    return {
        "name": name,
        "config": {"project_dir": str(tmp_path), "mode": mode},
        "idea": "Test idea.",
        "intent": "Test intent.",
        "user_notes": "",
        "meta": {"notes": []},
        "iteration": 1,
        "history": [],
        "sessions": {},
    }


def _setup_plan_dir(tmp_path: Path, state: dict[str, Any]) -> Path:
    plan_name = state.get("name", "test-plan")
    plan_dir = tmp_path / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan.json").write_text(
        json.dumps({"name": plan_name, "idea": state.get("idea", "")}), encoding="utf-8"
    )
    (plan_dir / "plan_v1.md").write_text("# Plan v1\n\nTest plan content.\n", encoding="utf-8")
    return plan_dir


def _setup_full_plan_dir(tmp_path: Path, state: dict[str, Any]) -> Path:
    """Create a plan directory with all files needed by gate/review prompt builders."""
    plan_dir = _setup_plan_dir(tmp_path, state)
    # plan_v1.meta.json
    (plan_dir / "plan_v1.meta.json").write_text(
        json.dumps({
            "success_criteria": [],
            "consolidated_plan": "# Consolidated\nTest\n",
            "tasks": [
                {"id": "T1", "description": "Implement test", "depends_on": [], "status": "pending",
                 "complexity": 3, "complexity_justification": "", "executor_notes": "",
                 "files_changed": [], "commands_run": [], "evidence_files": []},
                {"id": "T2", "description": "Verify criteria", "depends_on": [], "status": "pending",
                 "complexity": 2, "complexity_justification": "", "executor_notes": "",
                 "files_changed": [], "commands_run": [], "evidence_files": []},
            ],
            "sense_checks": [
                {"id": "SC1", "question": "Does it work?", "verdict": ""},
                {"id": "SC2", "question": "Is it documented?", "verdict": ""},
            ],
        }), encoding="utf-8"
    )
    # gate_signals_v1.json
    (plan_dir / "gate_signals_v1.json").write_text(
        json.dumps({
            "robustness": "standard",
            "signals": {
                "weighted_score": 0.85,
                "convergence_score": 0.9,
                "flag_counts": {"total": 0, "blocking": 0, "significant": 0},
            },
            "warnings": [],
        }), encoding="utf-8"
    )
    # flag_registry.json
    (plan_dir / "flag_registry.json").write_text(
        json.dumps({"flags": [], "resolved": []}), encoding="utf-8"
    )
    # finalize.json — needed by review prompt builder
    (plan_dir / "finalize.json").write_text(
        json.dumps({
            "tasks": [
                {"id": "T1", "description": "Implement test", "depends_on": [], "status": "done",
                 "complexity": 3, "complexity_justification": "", "executor_notes": "",
                 "files_changed": ["src/app.py"], "commands_run": ["python -m pytest"],
                 "evidence_files": ["test_output.txt"]},
                {"id": "T2", "description": "Verify criteria", "depends_on": [], "status": "done",
                 "complexity": 2, "complexity_justification": "", "executor_notes": "",
                 "files_changed": ["tests/test_app.py"], "commands_run": ["python -m pytest tests/"],
                 "evidence_files": []},
            ],
            "sense_checks": [
                {"id": "SC1", "question": "Does it work?"},
                {"id": "SC2", "question": "Is it documented?"},
            ],
        }), encoding="utf-8"
    )
    # execution.json — needed by review prompt builder
    (plan_dir / "execution.json").write_text(
        json.dumps({
            "plan_name": state.get("name", "test-plan"),
            "tasks": [
                {"id": "T1", "status": "done", "files_changed": ["src/app.py"],
                 "commands_run": ["python -m pytest"], "evidence_files": ["test_output.txt"]},
                {"id": "T2", "status": "done", "files_changed": ["tests/test_app.py"],
                 "commands_run": ["python -m pytest tests/"], "evidence_files": []},
            ],
            "sense_check_acknowledgments": [
                {"id": "SC1", "acknowledgment": "Verified."},
                {"id": "SC2", "acknowledgment": "Confirmed."},
            ],
            "output": "",
        }), encoding="utf-8"
    )
    return plan_dir


def _mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")


def _make_args(tmp_path: Path, *, plan: str = "test-plan") -> argparse.Namespace:
    return argparse.Namespace(
        plan=plan, agent=None, hermes=None, phase_model=[],
        profile=None, fresh=False, persist=False, ephemeral=False,
        mode="code", robustness="standard",
    )


# ──────────────────────────────────────────────────────────────────────
# render_prompt_for_dispatch with prompt_override (no disk I/O needed)
# ──────────────────────────────────────────────────────────────────────


def test_render_prompt_for_dispatch_gate_with_prompt_override(
    tmp_path: Path,
) -> None:
    """render_prompt_for_dispatch for gate prompt_override routes through the seam."""
    state = _base_state(tmp_path)
    plan_dir = _setup_plan_dir(tmp_path, state)

    rendered = render_prompt_for_dispatch(
        "codex", "gate", state, plan_dir, root=tmp_path,
        prompt_override="Custom gate prompt override",
        schema={"type": "object", "properties": {"verdict": {"type": "string"}}},
    )

    assert rendered.prompt == "Custom gate prompt override"
    assert rendered.metadata.get("validation_step") == "gate"
    assert rendered.metadata.get("tier") is not None
    assert rendered.metadata.get("worker") is not None


def test_render_prompt_for_dispatch_review_with_prompt_override(
    tmp_path: Path,
) -> None:
    """render_prompt_for_dispatch for review prompt_override routes through the seam."""
    state = _base_state(tmp_path)
    plan_dir = _setup_plan_dir(tmp_path, state)

    rendered = render_prompt_for_dispatch(
        "codex", "review", state, plan_dir, root=tmp_path,
        prompt_override="Custom review prompt override",
        schema={"type": "object", "properties": {"task_verdicts": {"type": "array"}}},
    )

    assert rendered.prompt == "Custom review prompt override"
    assert rendered.metadata.get("validation_step") == "review"
    assert rendered.metadata.get("tier") is not None


def test_render_prompt_for_dispatch_gate_normal_path(
    tmp_path: Path,
) -> None:
    """render_prompt_for_dispatch works for step='gate' without prompt_override."""
    state = _base_state(tmp_path)
    state["plan_versions"] = [{"file": "plan_v1.md", "iteration": 1, "hash": "abc123"}]
    plan_dir = _setup_full_plan_dir(tmp_path, state)

    rendered = render_prompt_for_dispatch(
        "codex", "gate", state, plan_dir, root=tmp_path,
    )

    assert rendered.prompt is not None, "prompt must be non-None"
    assert len(rendered.prompt) > 0, "prompt must be non-empty"


def test_render_prompt_for_dispatch_review_normal_path(
    tmp_path: Path,
) -> None:
    """render_prompt_for_dispatch works for step='review' without prompt_override."""
    state = _base_state(tmp_path)
    state["plan_versions"] = [{"file": "plan_v1.md", "iteration": 1, "hash": "abc123"}]
    plan_dir = _setup_full_plan_dir(tmp_path, state)

    rendered = render_prompt_for_dispatch(
        "codex", "review", state, plan_dir, root=tmp_path,
    )

    assert rendered.prompt is not None, "prompt must be non-None"
    assert len(rendered.prompt) > 0, "prompt must be non-empty"


# ──────────────────────────────────────────────────────────────────────
# Worker mock dispatch: render_prompt_for_dispatch is always called
# ──────────────────────────────────────────────────────────────────────


def test_codex_mock_gate_calls_render_prompt_for_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex mock gate dispatch calls render_prompt_for_dispatch."""
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers._impl import run_codex_step

    _mock_env(monkeypatch)
    ensure_runtime_layout(tmp_path)
    state = _base_state(tmp_path)
    state["plan_versions"] = [{"file": "plan_v1.md", "iteration": 1, "hash": "abc123"}]
    plan_dir = _setup_full_plan_dir(tmp_path, state)

    calls: list[dict[str, Any]] = []
    original = render_prompt_for_dispatch

    def spy(*a: Any, **kw: Any) -> Any:
        calls.append({"args": a, "kwargs": dict(kw)})
        return original(*a, **kw)

    with patch(
        "arnold.pipelines.megaplan.workers._impl.render_prompt_for_dispatch",
        side_effect=spy,
    ):
        run_codex_step("gate", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert len(calls) >= 1, "mock worker must call render_prompt_for_dispatch for codex gate"


def test_codex_mock_gate_with_override_calls_render_prompt_for_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex mock gate dispatch with prompt_override calls render_prompt_for_dispatch."""
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers._impl import run_codex_step

    _mock_env(monkeypatch)
    ensure_runtime_layout(tmp_path)
    state = _base_state(tmp_path)
    state["plan_versions"] = [{"file": "plan_v1.md", "iteration": 1, "hash": "abc123"}]
    plan_dir = _setup_full_plan_dir(tmp_path, state)

    calls: list[dict[str, Any]] = []
    original = render_prompt_for_dispatch

    def spy(*a: Any, **kw: Any) -> Any:
        calls.append({"args": a, "kwargs": dict(kw)})
        return original(*a, **kw)

    with patch(
        "arnold.pipelines.megaplan.workers._impl.render_prompt_for_dispatch",
        side_effect=spy,
    ):
        run_codex_step(
            "gate", state, plan_dir, root=tmp_path, persistent=False, fresh=True,
            prompt_override="Override prompt",
        )

    assert len(calls) >= 1, "mock worker must call render_prompt_for_dispatch even with override"


def test_hermes_mock_gate_calls_render_prompt_for_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hermes mock gate dispatch calls render_prompt_for_dispatch."""
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.hermes import run_hermes_step

    _mock_env(monkeypatch)
    ensure_runtime_layout(tmp_path)
    state = _base_state(tmp_path)
    state["plan_versions"] = [{"file": "plan_v1.md", "iteration": 1, "hash": "abc123"}]
    plan_dir = _setup_full_plan_dir(tmp_path, state)

    calls: list[dict[str, Any]] = []
    original = render_prompt_for_dispatch

    def spy(*a: Any, **kw: Any) -> Any:
        calls.append({"args": a, "kwargs": dict(kw)})
        return original(*a, **kw)

    # hermes mock path calls mock_worker_output which uses _impl's import
    with patch(
        "arnold.pipelines.megaplan.workers._impl.render_prompt_for_dispatch",
        side_effect=spy,
    ):
        run_hermes_step("gate", state, plan_dir, root=tmp_path, fresh=True)

    assert len(calls) >= 1, "mock worker must call render_prompt_for_dispatch for hermes gate"


def test_hermes_mock_gate_with_override_calls_render_prompt_for_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hermes mock gate dispatch with prompt_override calls render_prompt_for_dispatch."""
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.hermes import run_hermes_step

    _mock_env(monkeypatch)
    ensure_runtime_layout(tmp_path)
    state = _base_state(tmp_path)
    state["plan_versions"] = [{"file": "plan_v1.md", "iteration": 1, "hash": "abc123"}]
    plan_dir = _setup_full_plan_dir(tmp_path, state)

    calls: list[dict[str, Any]] = []
    original = render_prompt_for_dispatch

    def spy(*a: Any, **kw: Any) -> Any:
        calls.append({"args": a, "kwargs": dict(kw)})
        return original(*a, **kw)

    with patch(
        "arnold.pipelines.megaplan.workers._impl.render_prompt_for_dispatch",
        side_effect=spy,
    ):
        run_hermes_step(
            "gate", state, plan_dir, root=tmp_path, fresh=True,
            prompt_override="Override prompt",
        )

    assert len(calls) >= 1, "mock worker must call render_prompt_for_dispatch even with override for hermes"


# ──────────────────────────────────────────────────────────────────────
# Handler-level: _build_gate_prompt_override
# ──────────────────────────────────────────────────────────────────────


def test_build_gate_prompt_override_produces_string_for_codex(
    tmp_path: Path,
) -> None:
    """_build_gate_prompt_override returns a string for codex agent."""
    from arnold.pipelines.megaplan.handlers.shared import _build_gate_prompt_override

    state = _base_state(tmp_path)
    state["plan_versions"] = [{"file": "plan_v1.md", "iteration": 1, "hash": "abc123"}]
    plan_dir = _setup_full_plan_dir(tmp_path, state)

    override = _build_gate_prompt_override(
        "codex", state, plan_dir, root=tmp_path, missing_flag_ids=["F-001"]
    )

    assert isinstance(override, str), "gate prompt override must be a string"
    assert len(override) > 0, "gate prompt override must be non-empty"
    assert "Gate retry" in override, "gate prompt override must indicate it is a retry"
    assert "F-001" in override, "gate prompt override must mention the missing flag"


def test_build_gate_prompt_override_produces_string_for_hermes(
    tmp_path: Path,
) -> None:
    """_build_gate_prompt_override returns a string for hermes agent."""
    from arnold.pipelines.megaplan.handlers.shared import _build_gate_prompt_override

    state = _base_state(tmp_path)
    state["plan_versions"] = [{"file": "plan_v1.md", "iteration": 1, "hash": "abc123"}]
    plan_dir = _setup_full_plan_dir(tmp_path, state)

    override = _build_gate_prompt_override(
        "hermes", state, plan_dir, root=tmp_path, missing_flag_ids=["F-002", "F-003"]
    )

    assert isinstance(override, str), "gate prompt override must be a string"
    assert "F-002" in override, "gate prompt override must mention all missing flags"
    assert "F-003" in override, "gate prompt override must mention all missing flags"


def test_build_gate_prompt_override_produces_string_for_claude(
    tmp_path: Path,
) -> None:
    """_build_gate_prompt_override returns a string for claude agent."""
    from arnold.pipelines.megaplan.handlers.shared import _build_gate_prompt_override

    state = _base_state(tmp_path)
    state["plan_versions"] = [{"file": "plan_v1.md", "iteration": 1, "hash": "abc123"}]
    plan_dir = _setup_full_plan_dir(tmp_path, state)

    override = _build_gate_prompt_override(
        "claude", state, plan_dir, root=tmp_path, missing_flag_ids=["F-004"]
    )

    assert isinstance(override, str), "gate prompt override must be a string"
    assert "F-004" in override, "gate prompt override must mention the missing flag"


# ──────────────────────────────────────────────────────────────────────
# Handler-level: _build_review_prompt_override
# ──────────────────────────────────────────────────────────────────────


def test_build_review_prompt_override_produces_string_for_codex(
    tmp_path: Path,
) -> None:
    """_build_review_prompt_override returns a string for codex agent."""
    from arnold.pipelines.megaplan.handlers.review import _build_review_prompt_override

    state = _base_state(tmp_path)
    state["plan_versions"] = [{"file": "plan_v1.md", "iteration": 1, "hash": "abc123"}]
    plan_dir = _setup_full_plan_dir(tmp_path, state)

    override = _build_review_prompt_override(
        "codex", state, plan_dir, root=tmp_path, pre_check_flags=[]
    )

    assert isinstance(override, str), "review prompt override must be a string"
    assert len(override) > 0, "review prompt override must be non-empty"


def test_build_review_prompt_override_produces_string_for_hermes(
    tmp_path: Path,
) -> None:
    """_build_review_prompt_override returns a string for hermes agent."""
    from arnold.pipelines.megaplan.handlers.review import _build_review_prompt_override

    state = _base_state(tmp_path)
    state["plan_versions"] = [{"file": "plan_v1.md", "iteration": 1, "hash": "abc123"}]
    plan_dir = _setup_full_plan_dir(tmp_path, state)

    override = _build_review_prompt_override(
        "hermes", state, plan_dir, root=tmp_path,
        pre_check_flags=[{"id": "PF-1", "issue": "test"}],
    )

    assert isinstance(override, str), "review prompt override must be a string"
    assert len(override) > 0, "review prompt override must be non-empty"


# ──────────────────────────────────────────────────────────────────────
# Tiebreaker: prompt construction
# ──────────────────────────────────────────────────────────────────────


def test_tiebreaker_researcher_prompt_is_string(
    tmp_path: Path,
) -> None:
    """researcher_prompt returns a string suitable for prompt_override."""
    from arnold.pipelines.megaplan.prompts.tiebreaker_researcher import researcher_prompt

    state = _base_state(tmp_path)
    plan_dir = _setup_plan_dir(tmp_path, state)

    prompt = researcher_prompt(
        "Should we use REST or gRPC?", state, plan_dir, root=tmp_path
    )

    assert isinstance(prompt, str), "tiebreaker researcher prompt must be a string"
    assert len(prompt) > 0, "tiebreaker researcher prompt must be non-empty"


def test_tiebreaker_challenger_prompt_is_string(
    tmp_path: Path,
) -> None:
    """challenger_prompt returns a string suitable for prompt_override."""
    from arnold.pipelines.megaplan.prompts.tiebreaker_challenger import challenger_prompt

    state = _base_state(tmp_path)
    plan_dir = _setup_plan_dir(tmp_path, state)

    researcher_data = {
        "question": "Should we use REST or gRPC?",
        "evidence": [],
        "options": [
            {"name": "REST", "pros": ["widely understood"], "cons": ["chatty"]},
            {"name": "gRPC", "pros": ["efficient"], "cons": ["complex"]},
        ],
        "recommendation": "REST",
    }

    prompt = challenger_prompt(
        "Should we use REST or gRPC?", researcher_data, state, plan_dir, root=tmp_path
    )

    assert isinstance(prompt, str), "tiebreaker challenger prompt must be a string"
    assert len(prompt) > 0, "tiebreaker challenger prompt must be non-empty"


# ──────────────────────────────────────────────────────────────────────
# run_step_with_worker → hermes mock dispatch
# ──────────────────────────────────────────────────────────────────────


def test_run_step_with_worker_gate_mock_calls_seam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_step_with_worker for hermes gate calls render_prompt_for_dispatch."""
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers._impl import run_step_with_worker

    _mock_env(monkeypatch)
    ensure_runtime_layout(tmp_path)
    state = _base_state(tmp_path)
    state["plan_versions"] = [{"file": "plan_v1.md", "iteration": 1, "hash": "abc123"}]
    plan_dir = _setup_full_plan_dir(tmp_path, state)
    args = _make_args(tmp_path)

    calls: list[dict[str, Any]] = []
    original = render_prompt_for_dispatch

    def spy(*a: Any, **kw: Any) -> Any:
        calls.append({"args": a, "kwargs": dict(kw)})
        return original(*a, **kw)

    with patch(
        "arnold.pipelines.megaplan.workers._impl.render_prompt_for_dispatch",
        side_effect=spy,
    ):
        run_step_with_worker(
            "gate", state, plan_dir, args, root=tmp_path,
            resolved=("hermes", "ephemeral", True, "openrouter/qwen/qwen3-coder"),
        )

    assert len(calls) >= 1, "mock worker must call render_prompt_for_dispatch via run_step_with_worker"


def test_run_step_with_worker_gate_mock_with_override_calls_seam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_step_with_worker with prompt_override calls render_prompt_for_dispatch."""
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers._impl import run_step_with_worker

    _mock_env(monkeypatch)
    ensure_runtime_layout(tmp_path)
    state = _base_state(tmp_path)
    state["plan_versions"] = [{"file": "plan_v1.md", "iteration": 1, "hash": "abc123"}]
    plan_dir = _setup_full_plan_dir(tmp_path, state)
    args = _make_args(tmp_path)

    calls: list[dict[str, Any]] = []
    original = render_prompt_for_dispatch

    def spy(*a: Any, **kw: Any) -> Any:
        calls.append({"args": a, "kwargs": dict(kw)})
        return original(*a, **kw)

    with patch(
        "arnold.pipelines.megaplan.workers._impl.render_prompt_for_dispatch",
        side_effect=spy,
    ):
        run_step_with_worker(
            "gate", state, plan_dir, args, root=tmp_path,
            resolved=("hermes", "ephemeral", True, "openrouter/qwen/qwen3-coder"),
            prompt_override="Override gate prompt",
        )

    assert len(calls) >= 1, "mock worker must call render_prompt_for_dispatch with prompt_override"


# ──────────────────────────────────────────────────────────────────────
# Non-mock override paths must still render through the seam
# ──────────────────────────────────────────────────────────────────────
def test_hermes_override_path_structurally_renders_through_seam() -> None:
    """Hermes override path must render through the seam."""
    from arnold.pipelines.megaplan.workers.hermes import run_hermes_step

    source = inspect.getsource(run_hermes_step)
    assert "prompt_text = prompt_override or create_hermes_prompt" in source
    assert "render_prompt_for_dispatch(" in source
    assert "prompt_override=prompt_text" in source
    assert "prompt = rendered_step.prompt" in source


def test_codex_override_path_structurally_renders_through_seam() -> None:
    """Codex override path must render through the seam."""
    from arnold.pipelines.megaplan.workers._impl import run_codex_step

    source = inspect.getsource(run_codex_step)
    assert "prompt_override=prompt_override" in source
    assert "render_prompt_for_dispatch(" in source
    assert "prompt = rendered_prompt.prompt" in source
