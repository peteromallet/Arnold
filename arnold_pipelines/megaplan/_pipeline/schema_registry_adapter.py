"""Megaplan-owned adapters for neutral schema registry root resolution."""

from __future__ import annotations

import os
from pathlib import Path

from arnold.pipeline.schema_registry import ContractSchemaRegistry
from arnold.pipeline.step_io_contract import StepIOContractContext, StepIOOperation


_PLAN_DIR_MARKER = (".megaplan", "plans")
MEGAPLAN_CONTRACT_SCHEMA_ROOT = "MEGAPLAN_CONTRACT_SCHEMA_ROOT"


def derive_project_root_from_plan_dir(path: str | os.PathLike[str]) -> Path | None:
    """Return the project root when *path* sits under ``.megaplan/plans/<plan>``."""

    resolved = Path(path).expanduser().resolve()
    for candidate in (resolved, *resolved.parents):
        parent = candidate.parent
        grandparent = parent.parent
        if parent.name == _PLAN_DIR_MARKER[1] and grandparent.name == _PLAN_DIR_MARKER[0]:
            return grandparent.parent
    return None


def resolve_contract_schema_project_root(
    explicit_root: str | os.PathLike[str] | None = None,
) -> Path | None:
    """Resolve the project root for Megaplan contract schemas.

    Precedence:
    1. explicit context root supplied by the caller
    2. ``MEGAPLAN_CONTRACT_SCHEMA_ROOT`` environment override
    3. project root derived from a ``.megaplan/plans/<plan>`` path
    """

    if explicit_root is not None:
        resolved = Path(explicit_root).expanduser().resolve()
        return derive_project_root_from_plan_dir(resolved) or resolved

    env_root = os.getenv(MEGAPLAN_CONTRACT_SCHEMA_ROOT)
    if env_root:
        return Path(env_root).expanduser().resolve()

    return None


def create_contract_schema_registry(
    explicit_root: str | os.PathLike[str] | None = None,
) -> ContractSchemaRegistry | None:
    """Create a neutral registry from the Megaplan-resolved project root."""

    project_root = resolve_contract_schema_project_root(explicit_root)
    if project_root is None:
        return None
    return ContractSchemaRegistry(project_root)


def create_step_io_contract_context(
    *,
    operation: StepIOOperation | str,
    explicit_root: str | os.PathLike[str] | None = None,
    fail_closed_on_write: bool = True,
) -> StepIOContractContext:
    """Create a Step IO context with Megaplan-owned schema-root resolution."""

    return StepIOContractContext(
        operation=operation,
        registry=create_contract_schema_registry(explicit_root),
        fail_closed_on_write=fail_closed_on_write,
    )
