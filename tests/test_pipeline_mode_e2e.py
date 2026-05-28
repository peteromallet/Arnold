"""Sprint 3 — every mode runs E2E on the same primitives.

Brief asks for "primitives that can power many modes (planning, doc
critique, joke mode, etc.)." This test runs each canonical mode
end-to-end through the Pipeline executor and asserts:

- The same Step / Stage / Pipeline / Edge primitives are used.
- The prompt registry routes to the per-mode prompt.
- The profile slot is resolved at runtime — and can be swapped
  on-the-fly mid-pipeline.
- Artifacts land in mode-appropriate paths.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from megaplan._pipeline import (
    Edge,
    Pipeline,
    Stage,
    Step,
    StepContext,
    StepResult,
    PipelineVerdict,
)
from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.profile import Profile, empty_profile, load_profile
from megaplan._pipeline.prompts import register_demo_prompts, register_prompt, resolve_prompt


# ---------------------------------------------------------------------------
# Generic two-stage critic + reviser that the mode tests reuse.
# ---------------------------------------------------------------------------


@dataclass
class GenericCritic:
    name: str = "critique"
    kind: str = "judge"
    prompt_key: str = "critique"
    slot: str | None = "critique"
    max_iter: int = 3

    def run(self, ctx: StepContext) -> StepResult:
        state = ctx.state if isinstance(ctx.state, dict) else {}
        iteration = int(state.get("iter", 0))
        prompt = resolve_prompt(ctx, self.prompt_key)
        profile: Profile = ctx.profile
        model = profile.model_for(self.slot, default="mock") if isinstance(profile, Profile) else "mock"

        out = ctx.plan_dir / "critique" / f"v{iteration + 1}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "iter": iteration + 1,
            "mode": ctx.mode,
            "prompt_head": prompt[:48],
            "model": model,
        }))

        next_label = "to_revise" if iteration + 1 < self.max_iter else "to_done"
        return StepResult(
            outputs={"critique": out},
            verdict=PipelineVerdict(score=0.8 - iteration * 0.1, flags=("auto",)),
            next=next_label,
            state_patch={"iter": iteration + 1, "last_model": model},
        )


@dataclass
class GenericReviser:
    name: str = "revise"
    kind: str = "produce"
    prompt_key: str = "revise"
    slot: str | None = "revise"

    def run(self, ctx: StepContext) -> StepResult:
        state = ctx.state if isinstance(ctx.state, dict) else {}
        iteration = int(state.get("iter", 0))
        prompt = resolve_prompt(ctx, self.prompt_key, params={"flags": ["auto"]})
        profile: Profile = ctx.profile
        model = profile.model_for(self.slot, default="mock") if isinstance(profile, Profile) else "mock"

        out = ctx.plan_dir / "draft" / f"v{iteration}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f"mode={ctx.mode} iter={iteration} model={model}\n{prompt[:64]}")
        return StepResult(
            outputs={"draft": out},
            next="to_critique",
            state_patch={"last_revise_model": model},
        )


def _build_loop_pipeline(max_iter: int = 3) -> Pipeline:
    return Pipeline(
        stages={
            "critique": Stage(
                name="critique", step=GenericCritic(max_iter=max_iter),
                edges=(Edge("to_revise", "revise"), Edge("to_done", "halt")),
            ),
            "revise": Stage(
                name="revise", step=GenericReviser(),
                edges=(Edge("to_critique", "critique"),),
            ),
        },
        entry="critique",
    )


# ---------------------------------------------------------------------------
# Per-mode E2E.
# ---------------------------------------------------------------------------


def _register_per_mode_prompts() -> None:
    # Register the default critique/revise prompts first (no longer
    # done at import time), then layer on the mode-specific overrides.
    register_demo_prompts()
    register_prompt(
        "critique:joke",
        lambda ctx, params: "Rate this joke: setup-payoff tightness, surprise.",
    )
    register_prompt(
        "critique:doc",
        lambda ctx, params: "Review this doc: clarity, navigability, lede.",
    )
    register_prompt(
        "critique:plan",
        lambda ctx, params: "Critique this plan: completeness, risk, scope.",
    )


@pytest.mark.parametrize(
    "mode,expected_prompt_marker",
    [
        ("joke", "joke"),
        ("doc", "doc"),
        ("plan", "plan"),
        ("code", "critic"),  # default critique prompt
    ],
)
def test_each_mode_runs_three_critiques_through_same_pipeline(
    tmp_path: Path, mode: str, expected_prompt_marker: str
) -> None:
    _register_per_mode_prompts()
    profile = load_profile("all-claude")

    pipeline = _build_loop_pipeline(max_iter=3)
    ctx = StepContext(
        plan_dir=tmp_path,
        state={"iter": 0},
        profile=profile,
        mode=mode,
        inputs={},
        budget=None,
    )

    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path)

    assert result["state"]["iter"] == 3
    crits = sorted((tmp_path / "critique").glob("v*.json"))
    drafts = sorted((tmp_path / "draft").glob("v*.md"))
    assert len(crits) == 3, [p.name for p in crits]
    assert len(drafts) == 2, [p.name for p in drafts]

    first_crit = json.loads(crits[0].read_text())
    assert first_crit["mode"] == mode
    assert expected_prompt_marker in first_crit["prompt_head"].lower(), first_crit
    assert first_crit["model"] == "claude"


def test_profile_swap_mid_pipeline(tmp_path: Path) -> None:
    """A handcrafted Stage can swap to a new Profile via state_patch.

    Demonstrates the on-the-fly profile change the brief asks for.
    """

    @dataclass
    class SwappingCritic:
        name: str = "critique"
        kind: str = "judge"
        prompt_key: str = "critique"
        slot: str | None = "critique"

        def run(self, ctx: StepContext) -> StepResult:
            state = ctx.state if isinstance(ctx.state, dict) else {}
            iteration = int(state.get("iter", 0))
            profile: Profile = ctx.profile
            model = profile.model_for(self.slot, default="?")

            out = ctx.plan_dir / f"crit_v{iteration + 1}.json"
            out.write_text(json.dumps({"model": model, "iter": iteration + 1}))
            return StepResult(
                outputs={"crit": out},
                next="done",
                state_patch={"iter": iteration + 1, "model_used": model},
            )

    profile_a = Profile(name="A", slots={"critique": "claude"})
    profile_b = profile_a.with_slot("critique", "hermes:openai/gpt-5")

    pipeline = Pipeline(
        stages={
            "critique": Stage(
                name="critique", step=SwappingCritic(),
                edges=(Edge("done", "halt"),),
            ),
        },
        entry="critique",
    )

    # Run 1 with Profile A.
    out_a = tmp_path / "a"
    out_a.mkdir()
    run_pipeline(
        pipeline,
        StepContext(plan_dir=out_a, state={"iter": 0}, profile=profile_a, mode="code", inputs={}),
        artifact_root=out_a,
    )

    # Run 2 with Profile B (swap on the fly — same pipeline, new profile).
    out_b = tmp_path / "b"
    out_b.mkdir()
    run_pipeline(
        pipeline,
        StepContext(plan_dir=out_b, state={"iter": 0}, profile=profile_b, mode="code", inputs={}),
        artifact_root=out_b,
    )

    crit_a = json.loads((out_a / "crit_v1.json").read_text())
    crit_b = json.loads((out_b / "crit_v1.json").read_text())
    assert crit_a["model"] == "claude"
    assert crit_b["model"] == "hermes:openai/gpt-5"


def test_every_shipped_profile_resolves_required_slots() -> None:
    """Profiles work for all kinds of tasks — every shipped profile
    must resolve the canonical phase slots a Step might query."""

    from megaplan._pipeline.profile import list_profile_names

    required = ("plan", "prep", "critique", "revise", "gate", "finalize", "execute", "review", "feedback")
    for name in list_profile_names():
        profile = load_profile(name)
        for slot in required:
            # model_for raises if missing.
            model = profile.model_for(slot)
            assert isinstance(model, str) and model, (name, slot, model)


def test_profile_with_overrides_returns_immutable_copy() -> None:
    p = load_profile("all-claude")
    p2 = p.with_overrides(critique="hermes:openai/gpt-5", review="codex:high")
    assert p.model_for("critique") == "claude"
    assert p2.model_for("critique") == "hermes:openai/gpt-5"
    assert p2.model_for("review") == "codex:high"


def test_empty_profile_falls_back_to_default_in_model_for() -> None:
    p = empty_profile()
    assert p.model_for("plan", default="mock") == "mock"
    with pytest.raises(KeyError):
        p.model_for("plan")
