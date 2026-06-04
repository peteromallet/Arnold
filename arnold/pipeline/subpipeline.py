"""Neutral subpipeline invocation and promotion for Arnold.

Provides explicit input/output mapping, isolated child artifact scope,
a promotion function that returns a :class:`StateDelta`, and a
settings-merge helper.

All types are neutral dataclasses with zero megaplan imports.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping


# ── Subpipeline invocation ─────────────────────────────────────────────────


@dataclass(frozen=True)
class SubpipelineInvocation:
    """Describes a subpipeline call from a parent pipeline.

    ``child_pipeline`` is the pipeline to run as a child.
    ``input_map`` maps parent artifact/state keys to child input keys.
    ``output_map`` maps child result keys back to parent keys.
    ``artifact_subdir`` is the subdirectory under the parent's artifact
    root where child artifacts are written.  Defaults to ``child_pipeline``'s
    name when not set.
    ``settings_overrides`` are additional settings merged into the child's
    settings with parent precedence.
    """

    child_pipeline: Any
    input_map: Mapping[str, str] = field(default_factory=dict)
    output_map: Mapping[str, str] = field(default_factory=dict)
    artifact_subdir: str | None = None
    settings_overrides: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChildRunResult:
    """The result of running a child pipeline.

    ``final_state`` is the child's state dict after completion.
    ``final_stage`` names the terminal stage the child reached.
    ``artifacts`` maps artifact labels to their on-disk paths.
    ``status`` is the child's exit status (``\"completed\"``, ``\"halted\"``,
    ``\"error\"``).
    ``status_detail`` carries additional error/status information.
    """

    final_state: Mapping[str, Any] = field(default_factory=dict)
    final_stage: str | None = None
    artifacts: Mapping[str, Path] = field(default_factory=dict)
    status: str = "completed"
    status_detail: str | None = None


# ── Promotion ──────────────────────────────────────────────────────────────


def promote(
    child_result: ChildRunResult,
    parent_state: Mapping[str, Any],
    *,
    output_map: Mapping[str, str] | None = None,
) -> "StateDelta":
    """Promote a child pipeline result into a :class:`StateDelta` for the parent.

    Returns a :class:`StateDelta` that the parent executor should apply.
    Does **not** mutate *parent_state* directly — the caller owns the
    mutation decision.

    Parameters
    ----------
    child_result:
        The result returned by :func:`run_subpipeline`.
    parent_state:
        The parent's current state dict (read-only, not mutated).
    output_map:
        Optional mapping from child artifact keys to parent state keys.
        When provided, child artifacts are promoted into the delta under
        the parent keys.

    Returns
    -------
    StateDelta:
        A delta carrying the child's final state under the
        ``subloop:<name>:state`` key (when available) and promoted
        artifact entries from *output_map*.
    """
    from arnold.pipeline.state import StateDelta

    patches: list[dict[str, Any]] = []

    # Promote child final state
    if child_result.final_state:
        patches.append(dict(child_result.final_state))

    # Promote artifacts per output_map
    if output_map:
        artifact_patch: dict[str, Any] = {}
        for child_key, parent_key in output_map.items():
            if child_key in child_result.artifacts:
                artifact_patch[parent_key] = str(child_result.artifacts[child_key])
        if artifact_patch:
            patches.append(artifact_patch)

    return StateDelta(patches=tuple(patches))


# ── Settings merge ─────────────────────────────────────────────────────────


def merge_settings(
    parent_settings: Mapping[str, Any],
    child_defaults: Mapping[str, Any],
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge parent settings with child defaults, reporting precedence.

    Precedence (highest to lowest):
    1. *overrides* (explicit invocation-level overrides)
    2. *parent_settings* (parent's settings override child defaults)
    3. *child_defaults* (child pipeline's own defaults)

    This function is purely mechanical — it does **not** interpret
    plugin-specific settings keys.  Callers (Megaplan, executor) own the
    semantics of merged settings.

    Returns a new ``dict`` combining all three layers.
    """
    merged: dict[str, Any] = dict(child_defaults)
    merged.update(parent_settings)
    if overrides:
        merged.update(overrides)
    return merged


# ── Subpipeline runner ─────────────────────────────────────────────────────


def run_subpipeline(
    invocation: SubpipelineInvocation,
    parent_ctx: Any,
    *,
    runner: Callable[[Any, Any, Path | None], ChildRunResult] | None = None,
) -> ChildRunResult:
    """Run a child pipeline under isolated artifact scope.

    1. Resolves the child artifact root as
       ``parent_ctx.artifact_root / subdir`` where *subdir* is
       ``invocation.artifact_subdir`` or the child pipeline's name.
    2. Builds child inputs from *parent_ctx* using ``invocation.input_map``.
    3. Runs the child pipeline via *runner* (or a default that calls
       ``child_pipeline.run(child_ctx)``).
    4. Returns a :class:`ChildRunResult`.

    Parameters
    ----------
    invocation:
        The :class:`SubpipelineInvocation` describing the child call.
    parent_ctx:
        The parent's execution context (duck-typed — must have
        ``artifact_root``, ``state``, and optionally ``inputs``).
    runner:
        Optional custom runner callable.  When ``None``, the child
        pipeline is invoked via its ``run(ctx)`` method.

    Returns
    -------
    ChildRunResult:
        The result of the child pipeline execution.
    """
    child_pipeline = invocation.child_pipeline

    # Resolve child artifact subdir
    subdir = invocation.artifact_subdir
    if subdir is None:
        subdir = getattr(child_pipeline, "name", "child")

    parent_root = Path(getattr(parent_ctx, "artifact_root", ""))
    child_root = parent_root / subdir
    child_root.mkdir(parents=True, exist_ok=True)

    # Build child inputs from input_map
    child_inputs: dict[str, Any] = {}
    if invocation.input_map:
        parent_inputs = getattr(parent_ctx, "inputs", {}) or {}
        parent_state = getattr(parent_ctx, "state", {}) or {}
        for parent_key, child_key in invocation.input_map.items():
            # Look in parent inputs first, then parent state
            value = None
            if isinstance(parent_inputs, Mapping):
                value = parent_inputs.get(parent_key)
            if value is None and isinstance(parent_state, Mapping):
                value = parent_state.get(parent_key)
            if value is not None:
                child_inputs[child_key] = value

    # Build child context (duck-typed)
    child_ctx = dataclasses.replace(
        parent_ctx,
        artifact_root=str(child_root),
        inputs=child_inputs,
    ) if dataclasses.is_dataclass(parent_ctx) and not isinstance(parent_ctx, type) else _make_child_ctx(
        parent_ctx, str(child_root), child_inputs
    )

    # Run child
    if runner is not None:
        result = runner(child_pipeline, child_ctx, child_root)
    else:
        run_fn = getattr(child_pipeline, "run", None)
        if run_fn is None:
            return ChildRunResult(
                status="error",
                status_detail="child pipeline has no run() method",
            )
        result = run_fn(child_ctx)
        # If result is a dict (pipeline-level result), wrap it
        if isinstance(result, dict):
            result = ChildRunResult(
                final_state=result.get("state", {}),
                final_stage=result.get("final_stage"),
                artifacts=result.get("artifacts", {}),
                status=result.get("status", "completed"),
            )
        elif not isinstance(result, ChildRunResult):
            # StepResult-like — promote to ChildRunResult
            result = ChildRunResult(
                final_state=(
                    dict(getattr(result, "state_patch", {}))
                    if hasattr(result, "state_patch")
                    else {}
                ),
                final_stage=getattr(result, "next", None),
                status="completed",
            )

    return result


def _make_child_ctx(
    parent_ctx: Any,
    child_root: str,
    child_inputs: dict[str, Any],
) -> Any:
    """Build a child context when *parent_ctx* is not a dataclass."""
    # Try to construct a compatible context object
    ctx_type = type(parent_ctx)
    try:
        # Attempt copy-construction with common fields
        new_ctx = object.__new__(ctx_type)
        for field_name in ("artifact_root", "state", "inputs", "mode",
                           "resource_handles", "envelope", "profile",
                           "budget", "plan_dir"):
            if hasattr(parent_ctx, field_name):
                if field_name == "artifact_root":
                    setattr(new_ctx, field_name, child_root)
                elif field_name == "inputs":
                    setattr(new_ctx, field_name, child_inputs)
                elif field_name == "plan_dir":
                    setattr(new_ctx, field_name, Path(child_root))
                else:
                    setattr(new_ctx, field_name, getattr(parent_ctx, field_name))
        return new_ctx
    except Exception:
        # Fallback: return parent_ctx as-is (caller's responsibility)
        return parent_ctx
