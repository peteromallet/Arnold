"""Human-gate step: pause execution and wait for human input.

Writes ``<plan_dir>/awaiting_user.json`` with pipeline name, version,
current stage id, choices, and the artifact path the user is being asked
to inspect. The process exits cleanly (the step returns ``halt``).

Resume semantics: on resume, the executor re-reads ``awaiting_user.json``
to find the choice, and this step returns it as the edge label. After
returning, the ``awaiting_user.json`` file is cleaned up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from megaplan._pipeline.steps.agent import _latest_artifact
from megaplan._pipeline.types import StepContext, StepResult


@dataclass
class HumanGateStep:
    """Pause execution and wait for human input.

    Writes ``awaiting_user.json`` to the plan directory and returns a
    result whose ``next`` label is the user's choice (on resume) or
    ``halt`` (on initial pause).

    Resume semantics: the executor re-reads ``awaiting_user.json`` to
    find the choice, then this step returns it as the edge label.
    """

    name: str
    kind: str = "decide"
    prompt_key: str | None = None
    slot: str | None = None

    _artifact_stage: str = ""
    _choices: list[str] = field(default_factory=list)
    _pipeline_name: str = ""
    _pipeline_version: int = 1
    _resume_choice: str | None = None

    def run(self, ctx: StepContext) -> StepResult:
        # Check if a resume choice was provided (resume path)
        choice = self._resume_choice
        if choice is None:
            # Try reading from the plan dir (resume path)
            awaiting_path = ctx.plan_dir / "awaiting_user.json"
            if awaiting_path.exists():
                try:
                    data = json.loads(awaiting_path.read_text())
                    choice = data.get("_resume_choice")
                except (json.JSONDecodeError, KeyError):
                    pass

        if choice is not None and choice in self._choices:
            # Resume path: return the choice as the next label.
            # Clear _resume_choice so it is single-use — when looping back
            # around after a "continue" choice we must pause again, not loop
            # forever.
            object.__setattr__(self, "_resume_choice", None)
            # Clean up the awaiting file
            awaiting_path = ctx.plan_dir / "awaiting_user.json"
            if awaiting_path.exists():
                awaiting_path.unlink()
            return StepResult(
                outputs={},
                next=choice,
            )

        # Pause path: write awaiting_user.json
        artifact_path = _latest_artifact(ctx.plan_dir / self._artifact_stage)
        awaiting_data = {
            "pipeline": self._pipeline_name,
            "version": self._pipeline_version,
            "stage": self.name,
            "artifact_stage": self._artifact_stage,
            "artifact_path": str(artifact_path) if artifact_path else None,
            "choices": self._choices,
            "message": (
                f"Pipeline '{self._pipeline_name}' paused at stage '{self.name}'. "
                f"Review the artifact and choose: {', '.join(self._choices)}"
            ),
        }
        awaiting_path = ctx.plan_dir / "awaiting_user.json"
        awaiting_path.write_text(json.dumps(awaiting_data, indent=2))
        return StepResult(
            outputs={"awaiting_user": awaiting_path},
            next="halt",
            state_patch={
                "_pipeline_paused": True,
                "_pipeline_paused_stage": self.name,
            },
        )
