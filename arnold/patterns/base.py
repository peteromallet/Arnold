"""Pure base pattern constructors.

Stability:
    public: ``agent``, ``external_call``, ``merge``, ``subpipeline``
    internal: module-level normalization helpers

These constructors return DSL ``Step`` values with durable refs.  They reject
live callables, closures, and callable instances.
"""

from __future__ import annotations

from typing import Any, Mapping

from arnold.workflow import (
    Capability,
    Input,
    Output,
    SourceSpan,
    Step,
    SubpipelineRef,
    WorkflowPolicy,
)
from arnold.patterns._core import _as_hook_ref, _as_optional_hook_ref


def agent(
    step_id: str,
    *,
    task: str,
    prompt_ref: str | object,
    outputs: tuple[str, ...] = ("result",),
    capabilities: tuple[Capability, ...] = (),
    policy: WorkflowPolicy | None = None,
    source_span: SourceSpan | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Step:
    """Return an explicit agent step using a durable prompt hook ref."""

    hook = _as_hook_ref(prompt_ref, node_id=step_id, field="prompt_ref")
    merged_metadata = dict(metadata or {})
    merged_metadata["task"] = task
    merged_metadata["prompt_ref"] = hook.spec
    return Step(
        id=step_id,
        kind="agent",
        outputs=tuple(Output(name) for name in outputs),
        capabilities=capabilities,
        policy=policy,
        source_span=source_span,
        metadata=merged_metadata,
    )


def external_call(
    step_id: str,
    *,
    endpoint_ref: str | object,
    inputs: tuple[str, ...] = (),
    outputs: tuple[str, ...] = ("result",),
    capabilities: tuple[Capability, ...] = (),
    policy: WorkflowPolicy | None = None,
    source_span: SourceSpan | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Step:
    """Return an explicit external-call step using a durable endpoint ref."""

    hook = _as_hook_ref(endpoint_ref, node_id=step_id, field="endpoint_ref")
    merged_metadata = dict(metadata or {})
    merged_metadata["endpoint_ref"] = hook.spec
    return Step(
        id=step_id,
        kind="external_call",
        inputs=tuple(Input(name) for name in inputs),
        outputs=tuple(Output(name) for name in outputs),
        capabilities=capabilities,
        policy=policy,
        source_span=source_span,
        metadata=merged_metadata,
    )


def merge(
    step_id: str,
    *,
    inputs: tuple[str, ...] = (),
    outputs: tuple[str, ...] = ("result",),
    reducer_ref: str | object | None = None,
    capabilities: tuple[Capability, ...] = (),
    policy: WorkflowPolicy | None = None,
    source_span: SourceSpan | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Step:
    """Return an explicit merge step with an optional durable reducer ref."""

    hook = _as_optional_hook_ref(reducer_ref, node_id=step_id, field="reducer_ref")
    merged_metadata = dict(metadata or {})
    if hook is not None:
        merged_metadata["reducer_ref"] = hook.spec
    return Step(
        id=step_id,
        kind="merge",
        inputs=tuple(Input(name) for name in inputs),
        outputs=tuple(Output(name) for name in outputs),
        capabilities=capabilities,
        policy=policy,
        source_span=source_span,
        metadata=merged_metadata,
    )


def subpipeline(
    step_id: str,
    *,
    manifest_hash: str,
    alias: str | None = None,
    capabilities: tuple[Capability, ...] = (),
    policy: WorkflowPolicy | None = None,
    source_span: SourceSpan | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Step:
    """Return an explicit subpipeline step referencing a nested manifest by hash."""

    return Step(
        id=step_id,
        kind="subpipeline",
        capabilities=capabilities,
        policy=policy,
        source_span=source_span,
        subpipeline=SubpipelineRef(manifest_hash=manifest_hash, alias=alias),
        metadata=metadata or {},
    )
