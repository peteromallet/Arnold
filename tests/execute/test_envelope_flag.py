"""Tests for ``megaplan.execute._envelope`` — unified-execute flag parity.

Parametrises flag-on vs flag-off over representative finalize payloads,
asserting identical ``(agent, mode, model)`` resolution at the
``handle_execute_one_batch`` tier→spec call site.
"""

from __future__ import annotations

import copy
import os
from argparse import Namespace
from pathlib import Path

import pytest

import arnold_pipelines.megaplan.workers as worker_module
from arnold_pipelines.megaplan._core import resolve_dispatch_spec
from arnold_pipelines.megaplan.execute._binding.tier import select_batch_tier
from arnold_pipelines.megaplan.execute._envelope import unified_execute_enabled


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_tier_spec(
    args: Namespace,
    tier_spec: str | list[str],
) -> tuple[str, str, str | None]:
    """Replicate the batch.py ``_resolve_tier_spec`` helper for testing.

    Copies *args*, sets ``phase_model=["execute=<tier_spec>"]`` on the
    copy, and calls ``worker_module.resolve_agent_mode``.
    """
    selected_spec = tier_spec[0] if isinstance(tier_spec, list) else tier_spec
    tier_args = copy.copy(args)
    tier_args.phase_model = [f"execute={selected_spec}"]
    resolved = worker_module.resolve_agent_mode("execute", tier_args)
    return resolved.agent, resolved.mode, resolved.resolved_model or resolved.model


def _build_finalize_payload(
    tasks: list[dict],
) -> dict:
    """Build a minimal finalize-like payload from task dicts."""
    return {"tasks": tasks}


# ---------------------------------------------------------------------------
# Flag parity tests
# ---------------------------------------------------------------------------


class TestEnvelopeFlagParity:
    """Flag-on vs flag-off produce identical ``(agent, mode, model)``."""

    # A tier_map that maps complexity → tier spec strings in agent-spec format.
    # Use hermes with distinct model names so resolution produces different
    # (agent, mode, model) tuples per tier (parity is tested, not correctness).
    TIER_MAP: dict[int, str] = {
        1: "hermes:openai/gpt-4.1-mini",
        2: "hermes:openai/gpt-4.1-mini",
        3: "hermes:openai/gpt-4.1",
        4: "hermes:openai/gpt-4.1",
        5: "hermes:openai/gpt-4.5-preview",
    }

    @pytest.fixture
    def args(self) -> Namespace:
        """Minimal argparse.Namespace for resolve_agent_mode."""
        return Namespace(
            phase_model=[],
            model=None,
            agent=None,
            mode=None,
            thinking=None,
            effort=None,
            reasoning_effort=None,
            agent_mode=None,
            plan=None,
        )

    # -- happy path: mixed complexity tasks --------------------------------

    def test_mixed_complexity_same_resolution(self, args):
        """Tasks with complexity 2 and 4 → max=4 → same spec for both paths."""
        payload = _build_finalize_payload(
            [
                {
                    "id": "T1",
                    "complexity": 2,
                    "complexity_justification": "Simple.",
                    "depends_on": [],
                },
                {
                    "id": "T2",
                    "complexity": 4,
                    "complexity_justification": "Complex.",
                    "depends_on": [],
                },
            ]
        )
        batch_ids = ["T1", "T2"]

        # Flag-off path: compute_batch_complexity + tier_map.get
        from arnold_pipelines.megaplan._core import compute_batch_complexity

        complexity_off = compute_batch_complexity(payload, batch_ids)
        spec_off = self.TIER_MAP.get(complexity_off)

        # Flag-on path: select_batch_tier + resolve_dispatch_spec
        complexity_on = select_batch_tier(payload, batch_ids)
        spec_on = resolve_dispatch_spec(
            {"execute": self.TIER_MAP}, "execute", complexity_on
        )

        assert complexity_off == complexity_on
        assert spec_off == spec_on

        if spec_off and spec_on:
            agent_off, mode_off, model_off = _resolve_tier_spec(args, spec_off)
            agent_on, mode_on, model_on = _resolve_tier_spec(args, spec_on)
            assert (agent_off, mode_off, model_off) == (agent_on, mode_on, model_on)

    # -- single task with complexity ---------------------------------------

    def test_single_task_same_resolution(self, args):
        """Single task at complexity 3 → same spec for both paths."""
        payload = _build_finalize_payload(
            [
                {
                    "id": "T1",
                    "complexity": 3,
                    "complexity_justification": "Moderate.",
                    "depends_on": [],
                }
            ]
        )
        batch_ids = ["T1"]

        from arnold_pipelines.megaplan._core import compute_batch_complexity

        complexity_off = compute_batch_complexity(payload, batch_ids)
        spec_off = self.TIER_MAP.get(complexity_off)

        complexity_on = select_batch_tier(payload, batch_ids)
        spec_on = resolve_dispatch_spec(
            {"execute": self.TIER_MAP}, "execute", complexity_on
        )

        assert complexity_off == complexity_on
        assert spec_off == spec_on

        if spec_off and spec_on:
            agent_off, mode_off, model_off = _resolve_tier_spec(args, spec_off)
            agent_on, mode_on, model_on = _resolve_tier_spec(args, spec_on)
            assert (agent_off, mode_off, model_off) == (agent_on, mode_on, model_on)

    # -- injected verification task with missing complexity -----------------

    def test_missing_complexity_same_fallback(self, args):
        """Injected verification task with missing complexity → max still works.

        The fail-safe in ``compute_batch_complexity`` / ``select_batch_tier``
        returns the highest tier (10) for tasks missing complexity.
        Both paths must agree.
        """
        payload = _build_finalize_payload(
            [
                {
                    "id": "T1",
                    "complexity": 2,
                    "complexity_justification": "Simple.",
                    "depends_on": [],
                },
                {
                    "id": "T2",
                    # missing complexity → treated as highest tier (10)
                    "complexity_justification": "Verification task.",
                    "depends_on": ["T1"],
                },
            ]
        )
        batch_ids = ["T1", "T2"]

        from arnold_pipelines.megaplan._core import compute_batch_complexity

        complexity_off = compute_batch_complexity(payload, batch_ids)
        spec_off = self.TIER_MAP.get(complexity_off)

        complexity_on = select_batch_tier(payload, batch_ids)
        spec_on = resolve_dispatch_spec(
            {"execute": self.TIER_MAP}, "execute", complexity_on
        )

        assert complexity_off == complexity_on
        assert spec_off == spec_on

        if spec_off and spec_on:
            agent_off, mode_off, model_off = _resolve_tier_spec(args, spec_off)
            agent_on, mode_on, model_on = _resolve_tier_spec(args, spec_on)
            assert (agent_off, mode_off, model_off) == (agent_on, mode_on, model_on)

    def test_chain_tier_values_use_selected_element_on_both_paths(self, args):
        payload = _build_finalize_payload(
            [
                {
                    "id": "T1",
                    "complexity": 4,
                    "complexity_justification": "Complex.",
                    "depends_on": [],
                }
            ]
        )
        batch_ids = ["T1"]
        tier_map = {
            4: ["codex:gpt-5.5", "claude:claude-sonnet-4-6"],
        }

        from arnold_pipelines.megaplan._core import compute_batch_complexity

        complexity_off = compute_batch_complexity(payload, batch_ids)
        spec_off = tier_map.get(complexity_off)

        complexity_on = select_batch_tier(payload, batch_ids)
        spec_on = resolve_dispatch_spec({"execute": tier_map}, "execute", complexity_on)

        assert complexity_off == complexity_on == 4
        assert spec_off == ["codex:gpt-5.5", "claude:claude-sonnet-4-6"]
        assert spec_on == "codex:gpt-5.5"

        agent_off, mode_off, model_off = _resolve_tier_spec(args, spec_off)
        agent_on, mode_on, model_on = _resolve_tier_spec(args, spec_on)
        assert (agent_off, mode_off, model_off) == (agent_on, mode_on, model_on)

    # -- empty batch → fail-safe returns 5 for both paths ------------------

    def test_empty_batch_same_fallback(self, args):
        """Empty batch → both paths return highest tier (10)."""
        payload = _build_finalize_payload([])
        batch_ids: list[str] = []

        from arnold_pipelines.megaplan._core import compute_batch_complexity

        complexity_off = compute_batch_complexity(payload, batch_ids)
        spec_off = self.TIER_MAP.get(complexity_off)

        complexity_on = select_batch_tier(payload, batch_ids)
        spec_on = resolve_dispatch_spec(
            {"execute": self.TIER_MAP}, "execute", complexity_on
        )

        assert complexity_off == complexity_on
        assert spec_off == spec_on

    # -- tier ordinal missing from tier_map → both return None ------------

    def test_ordinal_missing_from_map(self, args):
        """When the ordinal has no mapping, both paths return None/default."""
        # Use a tier_map that has no entry for complexity 5
        sparse_map: dict[int, str] = {1: "hermes:openai/gpt-4.1-mini"}
        payload = _build_finalize_payload(
            [
                {
                    "id": "T1",
                    "complexity": 10,
                    "complexity_justification": "Extreme.",
                    "depends_on": [],
                }
            ]
        )
        batch_ids = ["T1"]

        from arnold_pipelines.megaplan._core import compute_batch_complexity

        complexity_off = compute_batch_complexity(payload, batch_ids)
        spec_off = sparse_map.get(complexity_off)

        complexity_on = select_batch_tier(payload, batch_ids)
        spec_on = resolve_dispatch_spec(
            {"execute": sparse_map}, "execute", complexity_on
        )

        assert complexity_off == complexity_on
        assert spec_off is None
        assert spec_on is None


# ---------------------------------------------------------------------------
# Envelope flag behaviour
# ---------------------------------------------------------------------------


class TestUnifiedExecuteEnabled:
    """Tests for the ``unified_execute_enabled()`` flag reader."""

    def test_default_off(self, monkeypatch):
        """Without the env var set, returns False."""
        monkeypatch.delenv("MEGAPLAN_UNIFIED_EXECUTE", raising=False)
        import importlib
        import arnold_pipelines.megaplan.execute._envelope as mod

        importlib.reload(mod)
        assert not mod.unified_execute_enabled()

    def test_explicit_zero_is_off(self, monkeypatch):
        """MEGAPLAN_UNIFIED_EXECUTE=0 → False."""
        monkeypatch.setenv("MEGAPLAN_UNIFIED_EXECUTE", "0")
        # Reset module cache by re-importing
        import importlib
        import arnold_pipelines.megaplan.execute._envelope as mod

        importlib.reload(mod)
        assert not mod.unified_execute_enabled()

    def test_explicit_false_is_off(self, monkeypatch):
        """MEGAPLAN_UNIFIED_EXECUTE=false → False."""
        monkeypatch.setenv("MEGAPLAN_UNIFIED_EXECUTE", "false")
        import importlib
        import arnold_pipelines.megaplan.execute._envelope as mod

        importlib.reload(mod)
        assert not mod.unified_execute_enabled()

    def test_explicit_one_is_on(self, monkeypatch):
        """MEGAPLAN_UNIFIED_EXECUTE=1 → True."""
        monkeypatch.setenv("MEGAPLAN_UNIFIED_EXECUTE", "1")
        import importlib
        import arnold_pipelines.megaplan.execute._envelope as mod

        importlib.reload(mod)
        assert mod.unified_execute_enabled()

    def test_explicit_true_is_on(self, monkeypatch):
        """MEGAPLAN_UNIFIED_EXECUTE=true → True."""
        monkeypatch.setenv("MEGAPLAN_UNIFIED_EXECUTE", "true")
        import importlib
        import arnold_pipelines.megaplan.execute._envelope as mod

        importlib.reload(mod)
        assert mod.unified_execute_enabled()

    def test_arbitrary_string_is_on(self, monkeypatch):
        """MEGAPLAN_UNIFIED_EXECUTE=yes → True (any non-falsy string)."""
        monkeypatch.setenv("MEGAPLAN_UNIFIED_EXECUTE", "yes")
        import importlib
        import arnold_pipelines.megaplan.execute._envelope as mod

        importlib.reload(mod)
        assert mod.unified_execute_enabled()
