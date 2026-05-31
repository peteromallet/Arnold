"""Unit tests for megaplan._pipeline.identity.behavioral_manifest.

Five contract units:
1. Equal on identical inputs (determinism)
2. Flip on prompt change
3. Flip on routing change
4. Flip on Step source change via monkeypatch
5. Flip on arnold_api_version change
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from megaplan._pipeline.identity import ManifestHash, behavioral_manifest
from megaplan._pipeline.types import Edge, Pipeline, Stage, StepContext, StepResult


# ── Minimal Step fixtures at module level (inspect.getsource-friendly) ───────

@dataclass(frozen=True)
class _StepV1:
    """Test step — source version A; name must be in _NODE_REGISTRY."""
    name: str = "majority_vote"
    kind: str = "join"
    prompt_key: str | None = None
    slot: str | None = None

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="v1_alpha_unique")


@dataclass(frozen=True)
class _StepV2:
    """Test step — source version B; same name, different run() body."""
    name: str = "majority_vote"
    kind: str = "join"
    prompt_key: str | None = None
    slot: str | None = None

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="v2_beta_distinct")


@dataclass(frozen=True)
class _PromptStep:
    """Test step that declares a prompt_key."""
    name: str = "majority_vote"
    kind: str = "join"
    prompt_key: str = "test_prompt"
    slot: str | None = None

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="halt")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_pipeline(step: Any) -> Pipeline:
    return Pipeline(
        stages={"s": Stage(name="s", step=step, edges=(Edge(label="halt", target="halt"),))},
        entry="s",
    )


def _cfg(*, routing_taken: dict | None = None, prompts: dict | None = None) -> Any:
    return SimpleNamespace(routing_taken=routing_taken or {}, prompts=prompts or {})


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_manifest_equal_on_identical():
    """Identical inputs produce identical ManifestHash values (determinism)."""
    graph = _make_pipeline(_StepV1())
    config = _cfg()
    h1 = behavioral_manifest(graph, config)
    h2 = behavioral_manifest(graph, config)
    assert isinstance(h1, str)
    assert h1 == h2


def test_manifest_flips_on_prompt_change():
    """Changing a prompt body produces a different ManifestHash."""
    graph = _make_pipeline(_PromptStep())
    h1 = behavioral_manifest(graph, _cfg(prompts={"test_prompt": "hello world"}))
    h2 = behavioral_manifest(graph, _cfg(prompts={"test_prompt": "goodbye world"}))
    assert h1 != h2


def test_manifest_flips_on_routing_change():
    """Changing routing_taken produces a different ManifestHash."""
    graph = _make_pipeline(_StepV1())
    h1 = behavioral_manifest(graph, _cfg(routing_taken={"gate": "proceed"}))
    h2 = behavioral_manifest(graph, _cfg(routing_taken={"gate": "iterate"}))
    assert h1 != h2


def test_manifest_flips_on_step_source_change(monkeypatch):
    """Monkeypatching a registered step's run() implementation changes the manifest.

    Uses _StepV2.run (defined at module level) as the replacement so that
    inspect.getsource can locate the new source in this test file.
    """
    step = _StepV1()
    graph = _make_pipeline(step)
    config = _cfg()
    h1 = behavioral_manifest(graph, config)

    monkeypatch.setattr(_StepV1, "run", _StepV2.run)
    h2 = behavioral_manifest(graph, config)
    assert h1 != h2


def test_manifest_flips_on_abi_version_change(monkeypatch):
    """Changing arnold_api_version produces a different ManifestHash."""
    from megaplan._pipeline import patterns

    graph = _make_pipeline(_StepV1())
    config = _cfg()
    h1 = behavioral_manifest(graph, config)

    monkeypatch.setattr(patterns, "arnold_api_version", "0.0.0-modified-for-test")
    h2 = behavioral_manifest(graph, config)
    assert h1 != h2
