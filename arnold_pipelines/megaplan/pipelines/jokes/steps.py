"""Step shells for the standalone ``jokes`` pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.runtime.artifacts import next_version
from arnold.pipeline import StepContext, StepResult
from arnold_pipelines.megaplan.pipelines.jokes.prompts import render_prompt


@dataclass(frozen=True)
class JokeStep:
    name: str
    prompt_key: str | None
    topic: str
    next_label: str = "halt"
    kind: str = "produce"
    slot: str | None = None
    produces: tuple = ()
    consumes: tuple = ()

    def run(self, ctx: StepContext) -> StepResult:
        state = _joke_state(ctx.state, topic=self.topic)
        prompt_text = render_prompt(
            self.prompt_key or self.name,
            topic=state["joke_topic"],
            previous=state["_joke_artifacts"],
        )

        out_dir = Path(ctx.artifact_root) / self.name
        out_dir.mkdir(parents=True, exist_ok=True)
        version = next_version(out_dir)
        prompt_path = out_dir / f"prompt_v{version}.md"
        artifact_path = out_dir / f"v{version}.md"
        prompt_path.write_text(prompt_text, encoding="utf-8")
        artifact_path.write_text(
            _artifact_text(self.name, prompt_text, state),
            encoding="utf-8",
        )

        artifacts = dict(state["_joke_artifacts"])
        artifacts[self.name] = str(artifact_path)
        patch: dict[str, Any] = {
            "joke_topic": state["joke_topic"],
            "_joke_artifacts": artifacts,
            "_joke_last_stage": self.name,
        }
        if self.next_label == "halt":
            patch["joke_artifact"] = str(artifact_path)

        return StepResult(
            outputs={self.name: artifact_path, f"{self.name}_prompt": prompt_path},
            next=self.next_label,
            state_patch=patch,
        )


def _joke_state(raw_state: Any, *, topic: str) -> dict[str, Any]:
    state = dict(raw_state) if isinstance(raw_state, Mapping) else {}
    state["joke_topic"] = str(state.get("joke_topic") or topic)
    artifacts = state.get("_joke_artifacts")
    state["_joke_artifacts"] = (
        dict(artifacts) if isinstance(artifacts, Mapping) else {}
    )
    return state


def _artifact_text(
    stage: str,
    prompt_text: str,
    state: Mapping[str, Any],
) -> str:
    previous = state.get("_joke_artifacts", {})
    prior = ""
    if isinstance(previous, Mapping) and previous:
        prior = "\n\nPrior artifacts:\n" + "\n".join(
            f"- {name}: {path}" for name, path in sorted(previous.items())
        )
    return (
        f"# jokes/{stage}\n\n"
        f"Topic: {state['joke_topic']}"
        f"{prior}\n\n"
        f"Rendered prompt:\n\n{prompt_text}\n"
    )


__all__ = ["JokeStep"]
