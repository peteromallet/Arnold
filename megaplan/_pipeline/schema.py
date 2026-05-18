"""Pydantic v2 models for YAML-defined pipeline specifications.

This module defines the canonical schema for ``pipeline.yaml`` files.
Every top-level field declared here maps directly to a YAML key.
Validation here is *structural* only — mode rejection based on
``supported_modes`` is a runtime check in the ``run`` command path,
NOT pydantic validation.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


# ── Input specification ───────────────────────────────────────────────


class InputSpec(BaseModel):
    """A named input to the pipeline (e.g. a file path)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    kind: Literal["file"] = "file"
    required: bool = True


# ── Stage variants ────────────────────────────────────────────────────


class _BaseStage(BaseModel):
    """Shared fields for all stage kinds."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str  # Discriminator — set by subclasses
    inputs: list[str] = Field(default_factory=list)
    produces: str | None = None  # Free-form tag — no contract validation


class ReviewerSpec(BaseModel):
    """A single reviewer within a panel stage."""

    model_config = ConfigDict(extra="forbid")

    id: str
    prompt: str  # .md path relative to pipeline dir, or PromptRegistry key


class AgentStepSpec(_BaseStage):
    """Single-model step: one prompt → one output."""

    kind: Literal["agent"] = "agent"
    prompt: str
    inputs: list[str] = Field(default_factory=list)
    produces: str | None = None


class PanelStepSpec(_BaseStage):
    """Fan-out panel: N reviewers run in parallel, each with its own prompt."""

    kind: Literal["panel"] = "panel"
    reviewers: list[ReviewerSpec]
    inputs: list[str] = Field(default_factory=list)
    produces: str | None = None
    merge: Literal["none"] | None = None  # "none" only for now; structural merge deferred


class GateStepSpec(_BaseStage):
    """Structured gate: agent emits Verdict → routed edges.

    Uses the existing gate executor semantics (Verdict.recommendation
    matched against kind="gate" edges). Prompt resolves via the same
    .md / PromptRegistry path as agent steps.
    """

    kind: Literal["gate"] = "gate"
    prompt: str
    inputs: list[str] = Field(default_factory=list)
    produces: str | None = None


class HumanGateStepSpec(_BaseStage):
    """Pause-and-resume gate: human inspects an artifact and chooses."""

    kind: Literal["human_gate"] = "human_gate"
    artifact: str  # Stage ID whose output the human inspects
    choices: list[str]  # e.g. ["continue", "stop"]


# Discriminated union of all stage types
StageSpec = Annotated[
    AgentStepSpec | PanelStepSpec | GateStepSpec | HumanGateStepSpec,
    Field(discriminator="kind"),
]


# ── Edge specification ────────────────────────────────────────────────


class EdgeSpec(BaseModel):
    """A labelled transition from one stage to another.

    ``from_`` maps to the YAML key ``from`` (Python reserved word,
    aliased via pydantic). ``when`` is the label on the edge —
    human_gate emits it as the user's choice, gate stages emit it
    as the Verdict recommendation name.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: str = Field(alias="from")
    when: str
    to: str


# ── Top-level pipeline specification ──────────────────────────────────


class PipelineSpec(BaseModel):
    """The root object of a ``pipeline.yaml`` file.

    Validated structurally:
    * Stage IDs must be unique.
    * Edge ``from`` must reference an existing stage ID.
    * Edge ``to`` must reference an existing stage ID or the sentinel ``"done"``.
    * Reviewer IDs within each panel must be unique.
    * ``<stage>.*`` input-ref syntax is only valid for panel stages.
    * ``supported_modes`` is stored but NOT validated — runtime check only.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    version: int
    description: str
    inputs: list[InputSpec] = Field(default_factory=list)
    supported_modes: list[str] | None = None
    default_profile: str
    recommended_profiles: list[str] | None = None
    stages: list[StageSpec]
    edges: list[EdgeSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_references(self) -> PipelineSpec:
        stage_ids: set[str] = set()
        panel_ids: set[str] = set()

        # 1. Unique stage IDs + track panel stages
        for stage in self.stages:
            if stage.id in stage_ids:
                raise ValueError(
                    f"Duplicate stage id '{stage.id}' — stage ids must be unique"
                )
            stage_ids.add(stage.id)
            if stage.kind == "panel":
                panel_ids.add(stage.id)

            # 2. Unique reviewer IDs per panel
            if stage.kind == "panel":
                reviewer_ids: set[str] = set()
                for reviewer in stage.reviewers:
                    if reviewer.id in reviewer_ids:
                        raise ValueError(
                            f"Duplicate reviewer id '{reviewer.id}' "
                            f"in panel stage '{stage.id}' — reviewer ids must be unique per panel"
                        )
                    reviewer_ids.add(reviewer.id)

        # 3. Validate input refs: <stage>.* syntax only for panel stages
        for stage in self.stages:
            for ref in stage.inputs:
                if ref.endswith(".*"):
                    base_stage = ref[:-2]  # strip .*
                    if base_stage not in stage_ids:
                        raise ValueError(
                            f"Stage '{stage.id}' references '{ref}' but "
                            f"stage '{base_stage}' does not exist"
                        )
                    if base_stage not in panel_ids:
                        raise ValueError(
                            f"Stage '{stage.id}' uses '{ref}' syntax but "
                            f"'{base_stage}' is not a panel stage "
                            f"(kind={self._stage_kind(base_stage)})"
                        )
                elif ref not in stage_ids:
                    # Check if it's a defined input name (not a stage reference)
                    input_names = {inp.name for inp in self.inputs}
                    if ref not in input_names:
                        raise ValueError(
                            f"Stage '{stage.id}' references input '{ref}' which is "
                            f"neither a declared input name nor an existing stage id"
                        )

        # 4. Validate human_gate artifact references
        for stage in self.stages:
            if stage.kind == "human_gate":
                if stage.artifact not in stage_ids:
                    raise ValueError(
                        f"human_gate stage '{stage.id}' references artifact "
                        f"'{stage.artifact}' which is not an existing stage id"
                    )

        # 5. Validate edges
        for edge in self.edges:
            if edge.from_ not in stage_ids:
                raise ValueError(
                    f"Edge from '{edge.from_}' references a stage that does not exist"
                )
            if edge.to not in stage_ids and edge.to != "done":
                raise ValueError(
                    f"Edge to '{edge.to}' must be an existing stage id or 'done'"
                )

        return self

    def _stage_kind(self, stage_id: str) -> str | None:
        for stage in self.stages:
            if stage.id == stage_id:
                return stage.kind
        return None
