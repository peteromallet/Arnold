"""Pipeline registry — megaplan-owned policy authority.

This module is the backward-compatibility re-export surface for internal
``_pipeline`` consumers.  The canonical home for the Megaplan pipeline
registry was moved to :mod:`arnold_pipelines.megaplan.registry` during
the M3 burn-down (T17).

Pipeline discovery (scan roots, module loading, manifest reading) was
extracted to :mod:`arnold_pipelines.megaplan.runtime.discovery` during
T16.

A programmatic registration is still available for tests and local extensions::

    from arnold_pipelines.megaplan.registry import register_pipeline
    register_pipeline("my-pipeline", build_my_pipeline, description="…")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

# ── Re-export the canonical registry from its new non-legacy home ──────────
from arnold_pipelines.megaplan.registry import (  # noqa: F401
    _GLOBAL_REGISTRY,
    _builtin_megaplan_builder,
    _bridge_payload,
    _ensure_builtin_pipelines_registered,
    _override_catalog_from_module,
    _require_payload_int,
    _require_payload_key,
    _require_payload_str,
    _reserve_out_of_tree_quota,
    _unsupported_operation_result,
    PipelineRegistry,
    control_status_result_from_operation_result,
    describe_pipeline,
    dispatch_operation_for,
    get_pipeline,
    make_megaplan_registry,
    operation_registry_for,
    override_catalog_for,
    phase_tuple_from_operation_result,
    pipeline_metadata,
    read_pipeline_skill_md,
    register_pipeline,
    registered_pipelines,
    resume_result_from_operation_result,
    supported_operations_for,
)

# ── Discovery symbols (re-exported from runtime.discovery for backward compat) ──
from arnold_pipelines.megaplan.runtime.discovery import (  # noqa: F401
    CANONICAL_BUILTIN_PIPELINE,
    LEGACY_PIPELINE_ALIASES,
    Disposition,
    PipelineBuilder,
    _SCAN_ROOTS,
    _cli_name,
    _coerce_supported_operations,
    _get_scan_roots,
    _load_module_from_path,
    _load_trusted_pipeline_module,
    _make_deferred_builder,
    _manifest_discovery_enabled,
    _manifest_metadata,
    _module_metadata,
    _operation_registry_from_module,
    _package_prefix_for_module_file,
    _supported_operation_names,
    canonical_pipeline_name,
    discover_python_pipelines,
    scan_python_pipelines,
)


# ── Legacy function that still depends on _pipeline internals ───────────────
# run_pipeline_by_name imports from _pipeline.executor and _pipeline.types.
# It stays here until executor migration (T20/T21).


def run_pipeline_by_name(
    name: str,
    *,
    plan_dir: Path,
    artifact_root: Path | None = None,
    profile: Any = None,
    mode: str = "code",
    inputs: Mapping[str, Path] | None = None,
    state: Mapping[str, Any] | None = None,
    policy: Any = None,
) -> dict[str, Any]:
    """Look up a registered pipeline and run it under the executor.

    When ``policy`` is set (a :class:`RuntimePolicy` instance), the
    walk uses ``run_pipeline_with_policy`` (stall + cost + escalate
    guarded). Otherwise the bare executor is used. Returns the
    executor's result dict (``{state, final_stage, halt_reason?}``).
    """

    from arnold_pipelines.megaplan._pipeline.executor import (
        run_pipeline,
        run_pipeline_with_policy,
    )
    from arnold_pipelines.megaplan._pipeline.types import StepContext

    pipeline = get_pipeline(name)
    artifact_root = Path(artifact_root or plan_dir)
    inputs_dict: dict[str, Any] = dict(inputs or {})
    inputs_dict.setdefault("_pipeline", canonical_pipeline_name(name))
    ctx = StepContext(
        plan_dir=Path(plan_dir),
        state=dict(state or {}),
        profile=profile,
        mode=mode,
        inputs=inputs_dict,
        budget=None,
    )
    if policy is None:
        return run_pipeline(pipeline, ctx, artifact_root=artifact_root)
    return run_pipeline_with_policy(
        pipeline, ctx, artifact_root=artifact_root, policy=policy,
    )
