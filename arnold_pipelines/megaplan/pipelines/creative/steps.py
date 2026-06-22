"""Step shells for the first-class ``creative`` pipeline."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline import StepContext
from arnold_pipelines.megaplan._pipeline.types import StepResult

from arnold_pipelines.megaplan._pipeline.step_helpers import next_version  # bridge: different signature
from arnold_pipelines.megaplan.pipelines.creative.prompts import render_prompt


def _root_dir(ctx: StepContext) -> Path:
    """Return the pipeline root directory from either Arnold or Megaplan context.

    Arnold StepContext has ``artifact_root``; Megaplan has ``plan_dir``.
    This bridge helper keeps the creative pipeline compatible with both runtimes.
    """
    root = getattr(ctx, 'artifact_root', None)
    if root is not None:
        return Path(root)
    return getattr(ctx, 'plan_dir')  # type: ignore[no-any-return]


@dataclass(frozen=True)
class CreativeStep:
    name: str = ""
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    form: str = ""
    primary_criterion: str | None = None
    next_label: str = "halt"

    def run(self, ctx: StepContext) -> StepResult:
        state = _creative_state(
            ctx.state,
            form=self.form,
            primary_criterion=self.primary_criterion,
        )
        inputs = _creative_inputs(ctx.inputs, state)
        render_ctx = dataclasses.replace(ctx, state=state, inputs=inputs)

        prompt_text = _render_prompt(render_ctx, self)
        out_dir = _root_dir(ctx) / self.name
        out_dir.mkdir(parents=True, exist_ok=True)
        version = next_version(out_dir)
        prompt_path = out_dir / f"prompt_v{version}.md"
        out = out_dir / f"v{version}.md"
        prompt_path.write_text(prompt_text, encoding="utf-8")
        out.write_text(_artifact_text(self, prompt_text, state), encoding="utf-8")

        artifacts = dict(state.get("_creative_artifacts", {}))
        artifacts[self.name] = str(out)
        return StepResult(
            outputs={self.name: out, f"{self.name}_prompt": prompt_path},
            next=self.next_label,
            state_patch={
                "config": state["config"],
                "_creative_artifacts": artifacts,
                "_creative_last_stage": self.name,
            },
        )


def _creative_state(
    raw_state: Any,
    *,
    form: str,
    primary_criterion: str | None,
) -> dict[str, Any]:
    state = dict(raw_state) if isinstance(raw_state, Mapping) else {}
    config = (
        dict(state.get("config", {}))
        if isinstance(state.get("config"), Mapping)
        else {}
    )
    config["mode"] = "creative"
    config["form"] = form
    if "project_dir" not in config:
        config["project_dir"] = str(state.get("project_dir") or ".")
    if primary_criterion is not None:
        config["primary_criterion"] = primary_criterion
    state["config"] = config
    artifacts = state.get("_creative_artifacts")
    state["_creative_artifacts"] = (
        dict(artifacts) if isinstance(artifacts, Mapping) else {}
    )
    return state


def _creative_inputs(
    inputs: Mapping[str, Any],
    state: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(inputs)
    merged.setdefault("_pipeline", "creative")
    artifacts = state.get("_creative_artifacts", {})
    if isinstance(artifacts, Mapping):
        for label, raw_path in artifacts.items():
            if isinstance(label, str) and raw_path:
                merged.setdefault(label, Path(raw_path))
    return merged


def _render_prompt(ctx: StepContext, step: CreativeStep) -> str:
    if step.prompt_key is None:
        previous = (
            ctx.state.get("_creative_artifacts", {})
            if isinstance(ctx.state, Mapping)
            else {}
        )
        if previous:
            lines = ["Finalize the creative run using these stage artifacts:"]
            lines.extend(f"- {name}: {path}" for name, path in sorted(previous.items()))
            return "\n".join(lines)
        return "Finalize the creative run."
    return render_prompt(
        step.prompt_key,
        ctx,
        params={
            "stage": step.name,
            "form": step.form,
            "primary_criterion": step.primary_criterion,
            "previous_artifacts": dict(ctx.state.get("_creative_artifacts", {}))
            if isinstance(ctx.state, Mapping)
            else {},
        },
    )


def _artifact_text(
    step: CreativeStep,
    prompt_text: str,
    state: Mapping[str, Any],
) -> str:
    artifacts = state.get("_creative_artifacts", {})
    prior = ""
    if isinstance(artifacts, Mapping) and artifacts:
        prior = "\n".join(
            f"- {name}: {path}" for name, path in sorted(artifacts.items())
        )
    if prior:
        prior = f"\n\nPrior stage artifacts:\n{prior}"
    criterion = ""
    config = state.get("config", {})
    if isinstance(config, Mapping):
        raw = config.get("primary_criterion")
        if isinstance(raw, str) and raw.strip():
            criterion = f"\n\nPrimary criterion: {raw.strip()}"
    return (
        f"# {step.name}\n\n"
        f"Form: {step.form or 'unknown'}"
        f"{criterion}"
        f"{prior}\n\n"
        f"Rendered prompt:\n\n{prompt_text}\n"
    )
