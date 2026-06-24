"""Megaplan adapter for executor-selected native runtime dispatch."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.native.ir import NativeProgram
from arnold.pipeline.types import StepContext


class NativeMegaplanRunner:
    """Run the native Megaplan pipeline with Megaplan runtime hooks.

    The neutral executor discovers this adapter through the pipeline's
    ``resource_bundles`` and delegates explicit native-marked runs here.  This
    keeps Megaplan-specific hook, policy, and schema-registry wiring outside
    ``arnold.pipeline.executor`` while preserving the same execution inputs the
    graph path receives.
    """

    def run_native_pipeline(
        self,
        *,
        program: NativeProgram | None = None,
        artifact_root: str | Path,
        initial_state: Mapping[str, Any],
        resume: bool = False,
        initial_envelope: Any = None,
        schema_registry: Any = None,
        initial_context: StepContext | None = None,
    ) -> Any:
        from arnold.pipeline.native.compiler import compile_pipeline
        from arnold.pipeline.native.runtime import run_native_pipeline
        from arnold.pipeline.step_io_contract import StepIOContractContext
        from arnold.pipeline.step_io_telemetry import TELEMETRY_FILENAME
        from arnold.pipelines.megaplan._pipeline.schema_registry_adapter import (
            create_contract_schema_registry,
        )
        from arnold.pipelines.megaplan._pipeline.step_io_policy_adapter import (
            megaplan_step_io_policy_path,
        )
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeRuntimeHooks
        from arnold.pipelines.megaplan.pipeline import megaplan

        if program is None:
            program = compile_pipeline(megaplan)

        root = Path(artifact_root)
        raw_hook_extensions = (
            getattr(initial_context, "hook_extensions", None)
            if initial_context is not None
            else None
        )
        hook_extensions = (
            dict(raw_hook_extensions)
            if isinstance(raw_hook_extensions, Mapping)
            else {}
        )

        contract_context = hook_extensions.get("step_io_contract_context")
        if schema_registry is None and isinstance(contract_context, StepIOContractContext):
            schema_registry = contract_context.registry
        if schema_registry is None:
            schema_registry = create_contract_schema_registry(root)

        policy_data = hook_extensions.get("step_io_policy_data")
        policy_path = hook_extensions.get("step_io_policy_path")
        if policy_path is None:
            policy_path = str(megaplan_step_io_policy_path(root))

        telemetry_path = hook_extensions.get("step_io_telemetry_path")
        if telemetry_path is None:
            telemetry_path = root / TELEMETRY_FILENAME

        hooks = MegaplanNativeRuntimeHooks(
            plan_dir=str(root),
            policy_data=dict(policy_data) if isinstance(policy_data, dict) else None,
            policy_path=str(policy_path) if policy_path is not None else None,
        )

        return run_native_pipeline(
            program,
            artifact_root=root,
            initial_state=dict(initial_state),
            resume=resume,
            hooks=hooks,
            schema_registry=schema_registry,
            telemetry_path=telemetry_path,
            initial_envelope=initial_envelope,
        )


__all__ = ["NativeMegaplanRunner"]
