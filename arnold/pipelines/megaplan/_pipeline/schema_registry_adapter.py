"""Compatibility shim: moved to ``arnold.pipelines.megaplan.schema_registry_adapter``.

This module re-exports the canonical implementation so that legacy imports
continue to work during the M7 purge window. New code should import from the
canonical path.
"""

from __future__ import annotations

from arnold.pipelines.megaplan.schema_registry_adapter import (
    MEGAPLAN_CONTRACT_SCHEMA_ROOT,
    create_contract_schema_registry,
    create_step_io_contract_context,
    derive_project_root_from_plan_dir,
    resolve_contract_schema_project_root,
)

__all__ = [
    "MEGAPLAN_CONTRACT_SCHEMA_ROOT",
    "create_contract_schema_registry",
    "create_step_io_contract_context",
    "derive_project_root_from_plan_dir",
    "resolve_contract_schema_project_root",
]
