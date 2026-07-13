"""Neutral human-gate step: pause execution and wait for human input.

Writes an awaiting-user checkpoint to ``ctx.artifact_root`` using the
generic :func:`arnold.runtime.state_persistence.atomic_write_json`.
The default filename is ``awaiting_user.json`` (parameterizable via
``_checkpoint_filename``).

Resume semantics: on resume, the executor re-reads the checkpoint to
find the user's choice, and the step returns it as the edge label.
After returning, the checkpoint file is cleaned up.

Boundary discipline: no ``megaplan`` imports.  No ``plan_dir``.
No ``typed_ports_on``.  Uses ``ctx.artifact_root``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.types import (
    EvidenceArtifactRef,
    HumanSuspension,
    StepContext,
    StepResult,
)
from arnold.runtime.state_persistence import atomic_write_json

_LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def build_resume_reverify_schema(
    *,
    port: str | None = None,
    content_type: str | None = None,
    artifact_path: str | None = None,
    artifact_ref: dict[str, Any] | None = None,
    invalid_policy: str = "resuspend",
) -> dict[str, Any]:
    """Build a ``resume_input_schema`` dict carrying an
    ``x-arnold-resume`` re-verification declaration.

    This is a **neutral** helper: no ``megaplan`` imports, no
    ``plan_dir``, no ``typed_ports_on``.  It is cursor-opaque — it
    does not interpret the opaque ``cursor`` value produced by the
    runtime.

    When none of the declaration fields are supplied the returned dict
    is empty, preserving no-declaration behaviour identically.

    Parameters
    ----------
    port:
        Port name declared for the producing step's output.
    content_type:
        Content type string (e.g. ``"text/markdown"``) for the
        artifact the consumer expects to re-verify.
    artifact_path:
        Resolved filesystem path to the artifact captured at
        suspend time.
    artifact_ref:
        Opaque reference dict (e.g. a display-ref ``to_json()``
        blob) that the consumer can match against
        ``display_refs`` at resume time.
    invalid_policy:
        Policy to apply when the re-verified artifact is invalid.
        Defaults to ``"resuspend"`` (re-suspend the pipeline).

    Returns
    -------
    dict
        A dict suitable for use as
        ``HumanSuspension.resume_input_schema``.  When no
        declaration fields are supplied the dict is empty,
        producing the same behaviour as the no-declaration path.
    """
    declaration: dict[str, Any] = {}
    if port is not None:
        declaration["port"] = port
    if content_type is not None:
        declaration["content_type"] = content_type
    if artifact_path is not None:
        declaration["artifact_path"] = artifact_path
    if artifact_ref is not None:
        declaration["artifact_ref"] = artifact_ref

    # No real declaration fields set → no-declaration parity.
    if not declaration:
        return {}

    declaration["invalid_policy"] = invalid_policy
    return {"x-arnold-resume": declaration}


def write_human_gate_checkpoint(
    checkpoint_path: Path,
    *,
    pipeline: str,
    version: int,
    artifact_stage: str,
    prompt: str = "",
    display_refs: tuple[EvidenceArtifactRef, ...] = (),
    resume_input_schema: Mapping[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Write an awaiting-user JSON checkpoint via :func:`atomic_write_json`.

    Parameters
    ----------
    checkpoint_path:
        Full path for the checkpoint file (e.g. ``<artifact_root>/awaiting_user.json``).
    pipeline:
        Name of the pipeline producing the checkpoint.
    version:
        Pipeline version integer.
    artifact_stage:
        Stage whose artifact the user is being asked to inspect.
    prompt:
        Human-readable prompt explaining what the user should review.
    display_refs:
        References to artifacts the user should examine.
    resume_input_schema:
        Optional re-verification declaration dict (e.g. from
        :func:`build_resume_reverify_schema`) to embed in the
        checkpoint so it is available to :func:`make_human_suspension`
        on resume.
    **extra:
        Additional keys injected into the checkpoint payload (e.g.
        ``stage``, ``choices``, ``message``).

    Returns
    -------
    dict
        The complete checkpoint dictionary that was written.
    """
    data: dict[str, Any] = {
        "pipeline": pipeline,
        "version": version,
        "artifact_stage": artifact_stage,
        "prompt": prompt,
        "display_refs": [ref.to_json() for ref in display_refs],
    }
    if resume_input_schema:
        data["resume_input_schema"] = dict(resume_input_schema)
    data.update(extra)
    atomic_write_json(checkpoint_path, data)
    return data


def read_human_gate_checkpoint(checkpoint_path: Path) -> dict[str, Any] | None:
    """Read a human-gate checkpoint from *checkpoint_path*.

    Returns ``None`` when the file is missing, unreadable, malformed JSON,
    or not a ``dict``.
    """
    if not checkpoint_path.exists():
        return None
    try:
        data = json.loads(checkpoint_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def make_human_suspension(
    checkpoint: dict[str, Any],
    *,
    resume_cursor: str | None = None,
) -> HumanSuspension:
    """Create a :class:`HumanSuspension` from a human-gate checkpoint.

    Parameters
    ----------
    checkpoint:
        The checkpoint dict (as returned by :func:`read_human_gate_checkpoint`).
    resume_cursor:
        Opaque cursor string the runtime uses to re-enter the pipeline
        at the correct stage.

    Returns
    -------
    HumanSuspension
        A typed interaction envelope carrying the prompt, display refs,
        resume cursor, and any ``resume_input_schema`` declaration
        embedded in the checkpoint.
    """
    display_refs = tuple(
        EvidenceArtifactRef.from_json(r)
        for r in (checkpoint.get("display_refs") or ())
    )
    resume_schema = checkpoint.get("resume_input_schema")
    return HumanSuspension(
        kind="human",
        prompt=str(checkpoint.get("prompt", "")),
        display_refs=display_refs,
        resume_input_schema=dict(resume_schema) if isinstance(resume_schema, dict) else {},
        resume_cursor=resume_cursor,
    )


# ---------------------------------------------------------------------------
# HumanGateStep
# ---------------------------------------------------------------------------


@dataclass
class HumanGateStep:
    """A neutral human-gate step that pauses execution for human input.

    Writes a checkpoint file (default ``awaiting_user.json``) to
    ``ctx.artifact_root`` and returns a :class:`StepResult` whose
    ``next`` label is ``"halt"``.

    On resume the step re-reads the checkpoint from disk.  If the
    checkpoint carries a ``_resume_choice`` key whose value is a valid
    choice, the step returns that choice as the ``next`` label and
    cleans up the checkpoint file.

    Compiler-injected fields (prefixed with ``_``) are set by the
    pipeline builder at construction time.
    """

    name: str
    kind: str = "decide"
    prompt_key: str | None = None
    slot: str | None = None

    # -- compiler-injected configuration ---------------------------------
    _artifact_stage: str = ""
    _choices: list[str] = field(default_factory=list)
    _pipeline_name: str = ""
    _pipeline_version: int = 1
    _resume_choice: str | None = None
    _checkpoint_filename: str = "awaiting_user.json"
    _prompt: str = ""
    _display_refs: tuple[EvidenceArtifactRef, ...] = field(default_factory=tuple)

    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        """Execute the human-gate step.

        On first invocation (no resume choice), writes the checkpoint
        and halts.  On resume (a valid ``_resume_choice`` is present
        on the instance or in the on-disk checkpoint), returns the
        choice as the ``next`` edge label and cleans up.
        """
        checkpoint_path = Path(ctx.artifact_root) / self._checkpoint_filename

        # ── resolve the resume choice ──
        choice: str | None = self._resume_choice
        if choice is None:
            on_disk = read_human_gate_checkpoint(checkpoint_path)
            if on_disk is not None:
                choice = on_disk.get("_resume_choice")
                if not isinstance(choice, str):
                    choice = None

        # ── resume path ──
        if choice is not None and choice in self._choices:
            # Single-use: clear the instance-level choice so a loop-back
            # does not keep resuming forever.
            object.__setattr__(self, "_resume_choice", None)
            if checkpoint_path.exists():
                checkpoint_path.unlink()
            return StepResult(
                outputs={},
                next=choice,
            )

        # ── pause path ──
        write_human_gate_checkpoint(
            checkpoint_path,
            pipeline=self._pipeline_name,
            version=self._pipeline_version,
            artifact_stage=self._artifact_stage,
            prompt=self._prompt,
            display_refs=self._display_refs,
            stage=self.name,
            choices=self._choices,
            message=(
                f"Pipeline '{self._pipeline_name}' paused at stage "
                f"'{self.name}'.  Review the artifact and choose: "
                f"{', '.join(self._choices)}"
            ),
        )
        _enqueue_human_gate_repair_request(
            ctx,
            pipeline_name=self._pipeline_name,
            artifact_stage=self._artifact_stage,
            step_name=self.name,
            prompt=self._prompt,
        )
        return StepResult(
            outputs={"awaiting_user": str(checkpoint_path)},
            next="halt",
            state_patch={
                "_pipeline_paused": True,
                "_pipeline_paused_stage": self.name,
            },
        )


def _enqueue_human_gate_repair_request(
    ctx: StepContext,
    *,
    pipeline_name: str,
    artifact_stage: str,
    step_name: str,
    prompt: str,
) -> None:
    hook_extensions = ctx.hook_extensions if isinstance(ctx.hook_extensions, Mapping) else {}
    plan_dir = str(hook_extensions.get("plan_dir") or "").strip()
    workspace_path = str(hook_extensions.get("workspace_path") or "").strip()
    queue_root = str(hook_extensions.get("repair_queue_root") or "").strip()
    session = str(
        hook_extensions.get("chain_session")
        or hook_extensions.get("session")
        or ""
    ).strip()
    if not plan_dir or not workspace_path or not queue_root or not session:
        return
    hook = hook_extensions.get("human_gate_repair_request_hook")
    if not callable(hook):
        return
    try:
        hook(
            queue_root=queue_root,
            marker_dir=plan_dir,
            session=session,
            workspace=workspace_path,
            run_kind=str(hook_extensions.get("run_kind") or "plan"),
            plan_name=str(hook_extensions.get("plan_name") or ""),
            pipeline_name=pipeline_name,
            artifact_stage=artifact_stage,
            step_name=step_name,
            prompt=prompt,
        )
    except Exception:
        _LOG.warning(
            "Best-effort human-gate repair enqueue failed for plan_dir=%s session=%s",
            plan_dir,
            session,
            exc_info=True,
        )
