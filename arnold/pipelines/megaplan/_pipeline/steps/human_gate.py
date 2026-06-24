"""Human-gate step: pause execution and wait for human input.

Writes ``<plan_dir>/awaiting_user.json`` with pipeline name, version,
current stage id, choices, and the artifact path the user is being asked
to inspect. The process exits cleanly (the step returns ``halt``).

Resume semantics: on resume, the executor re-reads ``awaiting_user.json``
to find the choice, and this step returns it as the edge label. After
returning, the ``awaiting_user.json`` file is cleaned up.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from arnold.pipeline.steps.human_gate import (
    build_resume_reverify_schema,
    make_human_suspension,
    read_human_gate_checkpoint,
    write_human_gate_checkpoint,
)
from arnold.pipeline.types import ContractResult, ContractStatus
from arnold.pipelines.megaplan._pipeline.step_helpers import latest_artifact
from arnold.pipelines.megaplan._pipeline.types import StepContext, StepResult


@dataclass
class HumanDecisionStep:
    """Pause execution and wait for human input.

    Writes ``awaiting_user.json`` to the plan directory and returns a
    result whose ``next`` label is the user's choice (on resume) or
    ``halt`` (on initial pause).

    Resume semantics: the executor re-reads ``awaiting_user.json`` to
    find the choice, then this step returns it as the edge label.

    Compiler-injected fields (prefixed with ``_``) are set by the
    pipeline builder at construction time.  When any of ``_port`` /
    ``_content_type`` / ``_artifact_ref`` are configured the step
    embeds an ``x-arnold-resume`` declaration in the checkpoint's
    ``resume_input_schema`` via
    :func:`~arnold.pipeline.steps.human_gate.build_resume_reverify_schema`
    so that the consumer can re-verify the artifact on resume.
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

    # -- re-verification declaration fields --------------------------
    _port: str | None = None
    _content_type: str | None = None
    _artifact_ref: dict | None = None
    _invalid_policy: str = "resuspend"

    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        # Check if a resume choice was provided (resume path)
        choice = self._resume_choice
        awaiting_path = ctx.plan_dir / "awaiting_user.json"
        disk_data = read_human_gate_checkpoint(awaiting_path)
        if choice is None:
            if disk_data is not None:
                choice = disk_data.get("_resume_choice")

        if choice is not None and choice in self._choices:
            # Resume path: return the choice as the next label.
            # Clear _resume_choice so it is single-use — when looping back
            # around after a "continue" choice we must pause again, not loop
            # forever.
            object.__setattr__(self, "_resume_choice", None)
            suspension = make_human_suspension(disk_data) if disk_data is not None else None
            resume_schema = (
                suspension.resume_input_schema
                if suspension is not None
                else {}
            )
            if awaiting_path.exists():
                awaiting_path.unlink()
            contract_result = None
            if suspension is not None and "x-arnold-resume" in resume_schema:
                contract_result = ContractResult(
                    status=ContractStatus.COMPLETED,
                    payload={
                        "resume_reverify_checkpoint": dict(disk_data or {}),
                        "resume_reverify_suspension": suspension.to_json(),
                    },
                )
            return StepResult(
                outputs={},
                next=choice,
                contract_result=contract_result,
            )

        # Pause path: write awaiting_user.json via the neutral helper
        artifact_path = latest_artifact(ctx.plan_dir / self._artifact_stage)

        # Only build a re-verification declaration when at least one of
        # _port, _content_type, _artifact_ref is explicitly set.
        # This preserves no-declaration parity: when none of those
        # fields are configured, resume_input_schema is empty.
        _want_declaration = (
            self._port is not None
            or self._content_type is not None
            or self._artifact_ref is not None
        )
        declaration_artifact_path = None
        if artifact_path and _want_declaration:
            try:
                declaration_artifact_path = str(artifact_path.relative_to(ctx.plan_dir))
            except ValueError:
                declaration_artifact_path = str(artifact_path)
        resume_schema = build_resume_reverify_schema(
            port=self._port,
            content_type=self._content_type,
            artifact_path=declaration_artifact_path,
            artifact_ref=self._artifact_ref,
            invalid_policy=self._invalid_policy,
        )
        checkpoint = write_human_gate_checkpoint(
            awaiting_path,
            pipeline=self._pipeline_name,
            version=self._pipeline_version,
            artifact_stage=self._artifact_stage,
            resume_input_schema=resume_schema or None,
            stage=self.name,
            choices=self._choices,
            artifact_path=str(artifact_path) if artifact_path else None,
            message=(
                f"Pipeline '{self._pipeline_name}' paused at stage '{self.name}'. "
                f"Review the artifact and choose: {', '.join(self._choices)}"
            ),
        )
        suspension = make_human_suspension(checkpoint)
        return StepResult(
            outputs={"awaiting_user": awaiting_path},
            next="halt",
            state_patch={
                "_pipeline_paused": True,
                "_pipeline_paused_stage": self.name,
            },
            contract_result=ContractResult(
                status=ContractStatus.SUSPENDED,
                suspension=suspension,
            ),
        )
