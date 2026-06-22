"""Megaplan runtime adapters and helpers.

This package houses Megaplan-owned adapters (e.g., Step IO policy,
schema registry, pipeline discovery) that bridge Arnold pipeline contracts
with Megaplan planning conventions.

These modules were rehomed from ``arnold_pipelines.megaplan._pipeline``
during the M3 burn-down to keep the production surface free of legacy
``_pipeline`` imports.
"""

from arnold_pipelines.megaplan.runtime.schema_registry_adapter import (  # noqa: F401
    MEGAPLAN_CONTRACT_SCHEMA_ROOT,
    create_contract_schema_registry,
    create_step_io_contract_context,
    derive_project_root_from_plan_dir,
    resolve_contract_schema_project_root,
)

from arnold_pipelines.megaplan.runtime.artifacts import (  # noqa: F401
    latest_artifact,
    next_version,
)

from arnold_pipelines.megaplan.runtime.step_io_policy_adapter import (  # noqa: F401
    STEP_IO_POLICY_ENV,
    STEP_IO_READ_LENIENT_ENV,
    has_megaplan_step_io_self_validation_marker,
    load_megaplan_step_io_policy,
    load_megaplan_step_io_policy_path,
    megaplan_policy_for_envelope,
    megaplan_step_io_policy_path,
    megaplan_step_io_read_lenient_escape_on,
    record_megaplan_step_io_self_validation_marker,
    resolve_megaplan_step_io_policy,
    write_megaplan_step_io_policy,
)

from arnold_pipelines.megaplan.runtime.discovery import (  # noqa: F401
    CANONICAL_BUILTIN_PIPELINE,
    Disposition,
    _SCAN_ROOTS,
    _cli_name,
    _get_scan_roots,
    canonical_pipeline_name,
    discover_python_pipelines,
    scan_python_pipelines,
)
