"""Shared discovery helpers for shipped ``arnold_pipelines`` packages.

The helpers here are used by the CLI, generators, registry checks, and tests to
locate canonical ``build_pipeline()`` callables and the surrounding package
metadata (docs, generated assets, registry disposition).
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import arnold.pipeline as native_pipeline
import arnold.workflow as workflow


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ShippedPipelineInfo:
    """Metadata for one shipped or example pipeline package.

    Fields:
      - ``id``: canonical pipeline id (e.g. ``megaplan.jokes``).
      - ``public``: whether the package is public / maintained.
      - ``package_path``: importable package module path.
      - ``registry_id``: stable registry id, or ``None``.
      - ``docs_path``: path to the package SKILL.md or docs file, or ``None``.
      - ``generated_asset_path``: path to generated data directory, or ``None``.
      - ``disposition``: one of ``migrate``, ``archive``, ``delete``, ``whitelist``.
      - ``builder_contract``: expected builder family: ``workflow``, ``native``,
        or ``deferred-native``.
      - ``load_state``: actual discovery load state: ``workflow``,
        ``loadable-native``, ``deferred-native``, or ``not-loadable``.
      - ``canonical_builder_path``: import target for canonical builders, or
        ``None`` for deferred/deleted rows.
      - ``diagnostic``: operator-readable reason for deferred or failed load.
      - ``builder``: the canonical ``build_pipeline`` callable, or ``None``.
    """

    id: str
    public: bool
    package_path: str
    registry_id: str | None
    docs_path: str | None
    generated_asset_path: str | None
    disposition: str
    builder_contract: str
    load_state: str
    canonical_builder_path: str | None
    diagnostic: str | None = None
    builder: Callable[..., Any] | None = None


# Mapping from final package path (relative to repo root) to discovery metadata.
# This table is the source of truth for Phase 3; it is consumed by the inventory
# scanner in ``scripts/check_workflow_pipeline_inventory.py``.
_SHIPPED_PIPELINE_DISPOSITION: dict[str, dict[str, Any]] = {
    # Survivors (migrate)
    "arnold_pipelines/megaplan": {
        "id": "megaplan",
        "public": True,
        "registry_id": "megaplan.core",
        "docs_path": "arnold_pipelines/megaplan/SKILL.md",
        "disposition": "migrate",
        "migrated": True,
    },
    "arnold_pipelines/megaplan/pipelines/planning": {
        "id": "megaplan",
        "public": True,
        "registry_id": "megaplan.planning",
        "docs_path": "arnold_pipelines/megaplan/pipelines/planning/SKILL.md",
        "disposition": "migrate",
        "migrated": True,
    },
    "arnold_pipelines/megaplan/pipelines/doc": {
        "id": "doc",
        "public": True,
        "registry_id": "megaplan.doc",
        "docs_path": "arnold_pipelines/megaplan/pipelines/doc/SKILL.md",
        "disposition": "migrate",
        "migrated": True,
        "builder_contract": "native",
    },
    "arnold_pipelines/megaplan/pipelines/creative": {
        "id": "creative",
        "public": True,
        "registry_id": "megaplan.creative",
        "docs_path": "arnold_pipelines/megaplan/pipelines/creative/SKILL.md",
        "disposition": "migrate",
        "migrated": True,
        "builder_contract": "native",
    },
    "arnold_pipelines/megaplan/pipelines/jokes": {
        "id": "jokes",
        "public": True,
        "registry_id": "megaplan.jokes",
        "docs_path": "arnold_pipelines/megaplan/pipelines/jokes/SKILL.md",
        "disposition": "migrate",
        "migrated": True,
        "builder_contract": "native",
    },
    "arnold_pipelines/megaplan/pipelines/live_supervisor": {
        "id": "live-supervisor",
        "public": True,
        "registry_id": "megaplan.live_supervisor",
        "docs_path": "arnold_pipelines/megaplan/pipelines/live_supervisor/SKILL.md",
        "disposition": "migrate",
        "migrated": True,
        "builder_contract": "native",
    },
    "arnold_pipelines/megaplan/pipelines/select_tournament": {
        "id": "select-tournament",
        "public": True,
        "registry_id": "megaplan.select_tournament",
        "docs_path": "arnold_pipelines/megaplan/pipelines/select_tournament/SKILL.md",
        "disposition": "migrate",
        "migrated": True,
        "builder_contract": "native",
    },
    "arnold_pipelines/megaplan/pipelines/writing_panel_strict": {
        "id": "writing-panel-strict",
        "public": True,
        "registry_id": "megaplan.writing_panel_strict",
        "docs_path": "arnold_pipelines/megaplan/pipelines/writing_panel_strict/SKILL.md",
        "disposition": "migrate",
        "migrated": True,
        "builder_contract": "native",
    },
    "arnold/pipelines/megaplan/pipelines/doc": {
        "id": "legacy.megaplan.doc",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "delete",
        "migrated": False,
    },
    "arnold/pipelines/megaplan/pipelines/creative": {
        "id": "legacy.megaplan.creative",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "delete",
        "migrated": False,
    },
    "arnold/pipelines/megaplan/pipelines/jokes": {
        "id": "legacy.megaplan.jokes",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "delete",
        "migrated": False,
    },
    "arnold/pipelines/megaplan/pipelines/live_supervisor": {
        "id": "legacy.megaplan.live_supervisor",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "delete",
        "migrated": False,
    },
    "arnold/pipelines/megaplan/pipelines/epic_blitz.py": {
        "id": "legacy.megaplan.epic_blitz",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "delete",
        "migrated": False,
    },
    "arnold/pipelines/megaplan/pipelines/select_tournament": {
        "id": "legacy.megaplan.select_tournament",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "delete",
        "migrated": False,
    },
    "arnold/pipelines/megaplan/pipelines/writing_panel_strict": {
        "id": "legacy.megaplan.writing_panel_strict",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "delete",
        "migrated": False,
    },
    "arnold/pipelines/folder_audit": {
        "id": "legacy.folder_audit",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "archive",
        "migrated": False,
    },
    "arnold_pipelines/evidence_pack": {
        "id": "evidence_pack_verifier",
        "public": True,
        "registry_id": "evidence_pack.verifier",
        "docs_path": "arnold_pipelines/evidence_pack/SKILL.md",
        "disposition": "migrate",
        "migrated": True,
    },
    "arnold_pipelines/_template": {
        "id": "my-pipeline",
        "public": True,
        "registry_id": None,
        "docs_path": "arnold_pipelines/_template/SKILL.md",
        "disposition": "migrate",
        "migrated": True,
        "builder_contract": "workflow",
    },
    # Archives
    "arnold_pipelines/megaplan/pipelines/epic_blitz.py": {
        "id": "epic-blitz",
        "public": True,
        "registry_id": "megaplan.epic_blitz",
        "docs_path": "arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md",
        "disposition": "archive",
        "migrated": False,
        "builder_contract": "native",
    },
    "arnold_pipelines/megaplan/pipelines/epic-blitz": {
        "id": "megaplan.epic_blitz",
        "public": False,
        "registry_id": None,
        "docs_path": "arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md",
        "disposition": "archive",
        "migrated": False,
    },
    # Deletes (legacy duplicates)
    "arnold/pipelines/jokes": {
        "id": "legacy.arnold_pipelines.jokes",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "delete",
        "migrated": False,
    },
    "arnold/pipelines/creative": {
        "id": "legacy.arnold_pipelines.creative",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "delete",
        "migrated": False,
    },
    "arnold/pipelines/doc": {
        "id": "legacy.arnold_pipelines.doc",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "delete",
        "migrated": False,
    },
    "arnold/pipelines/live_supervisor": {
        "id": "legacy.arnold_pipelines.live_supervisor",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "delete",
        "migrated": False,
    },
    "arnold/pipelines/select_tournament": {
        "id": "legacy.arnold_pipelines.select_tournament",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "delete",
        "migrated": False,
    },
    "arnold/pipelines/writing_panel_strict.py": {
        "id": "legacy.arnold_pipelines.writing_panel_strict_py",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "delete",
        "migrated": False,
    },
    "arnold/pipelines/writing_panel_strict": {
        "id": "legacy.arnold_pipelines.writing_panel_strict",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "delete",
        "migrated": False,
    },
    "arnold/pipelines/__init__.py": {
        "id": "legacy.arnold_pipelines.init",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "delete",
        "migrated": False,
    },
    "arnold/pipelines/_authoring.py": {
        "id": "legacy.arnold_pipelines.authoring",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "delete",
        "migrated": False,
    },
    "arnold/pipelines/simplify_writing": {
        "id": "legacy.simplify_writing",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "archive",
        "migrated": False,
    },
    "arnold/pipelines/vibecomfy_executor": {
        "id": "legacy.vibecomfy_executor",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "archive",
        "migrated": False,
    },
    "arnold/pipelines/epic_blitz": {
        "id": "legacy.epic_blitz",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "archive",
        "migrated": False,
    },
    "arnold/pipelines/deliberation": {
        "id": "legacy.deliberation",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "archive",
        "migrated": False,
    },
    "arnold/pipelines/_deliberation_example": {
        "id": "legacy._deliberation_example",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "archive",
        "migrated": False,
    },
    "arnold/pipelines/briefs": {
        "id": "legacy.briefs",
        "public": False,
        "registry_id": None,
        "docs_path": None,
        "disposition": "archive",
        "migrated": False,
    },
    "arnold/pipelines/_template": {
        "id": "arnold._template",
        "public": True,
        "registry_id": None,
        "docs_path": "arnold/pipelines/_template/SKILL.md",
        "disposition": "migrate",
        "migrated": False,
    },
}


def _package_path_to_module(package_path: str) -> str:
    """Convert a package path like ``arnold_pipelines/megaplan/pipelines/jokes`` to a module name."""

    normalized = package_path[:-3] if package_path.endswith(".py") else package_path
    return normalized.replace("/", ".")


def _builder_target(package_path: str, info: dict[str, Any]) -> str | None:
    explicit = info.get("canonical_builder_path")
    if explicit is not None:
        return explicit
    if info.get("disposition", "migrate") != "migrate":
        return None
    return f"{_package_path_to_module(package_path)}:build_pipeline"


def _load_builder(package_path: str) -> Callable[..., Any] | None:
    """Import *package_path* and return its ``build_pipeline`` callable if valid."""

    module_name = _package_path_to_module(package_path)
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return None
    builder = getattr(module, "build_pipeline", None)
    if not callable(builder):
        return None
    return builder


def _classify_load_state(
    builder: Callable[..., Any] | None,
    builder_contract: str,
) -> tuple[str, str | None]:
    """Return the actual load state plus any diagnostic for a discovered row."""

    if builder_contract == "deferred-native":
        return "deferred-native", None
    if builder is None:
        return "not-loadable", "No callable canonical build_pipeline could be imported."
    try:
        built = builder()
    except Exception as exc:
        return "not-loadable", f"build_pipeline raised {type(exc).__name__}: {exc}"
    if isinstance(built, workflow.Pipeline):
        return "workflow", None
    if isinstance(built, native_pipeline.Pipeline):
        if getattr(built, "native_program", None) is not None:
            return "loadable-native", None
        return (
            "not-loadable",
            "Builder returned arnold.pipeline.Pipeline without native_program.",
        )
    return (
        "not-loadable",
        f"Builder returned unsupported {type(built).__module__}.{type(built).__name__}.",
    )


def discover_shipped_pipelines(
    *,
    include_archived: bool = False,
    include_deleted: bool = False,
    include_whitelist: bool = False,
) -> tuple[ShippedPipelineInfo, ...]:
    """Return discovery records for shipped / example pipeline roots.

    Only ``migrate`` roots are returned by default.  Use the flags to include
    archive/delete/whitelist rows.
    """

    results: list[ShippedPipelineInfo] = []
    for package_path, info in sorted(_SHIPPED_PIPELINE_DISPOSITION.items()):
        disposition = info.get("disposition", "migrate")
        if disposition == "archive" and not include_archived:
            continue
        if disposition == "delete" and not include_deleted:
            continue
        if disposition == "whitelist" and not include_whitelist:
            continue

        builder: Callable[..., Any] | None = None
        builder_contract = info.get("builder_contract", "workflow")
        canonical_builder_path = _builder_target(package_path, info)
        if (
            info.get("migrated")
            and disposition == "migrate"
            and builder_contract != "deferred-native"
        ):
            builder = _load_builder(package_path)
        load_state, load_diagnostic = _classify_load_state(builder, builder_contract)
        diagnostic = info.get("diagnostic") or load_diagnostic

        docs_path = info.get("docs_path")
        generated_asset_path = info.get("generated_asset_path")
        results.append(
            ShippedPipelineInfo(
                id=info.get("id", package_path),
                public=info.get("public", False),
                package_path=package_path,
                registry_id=info.get("registry_id"),
                docs_path=docs_path,
                generated_asset_path=generated_asset_path,
                disposition=disposition,
                builder_contract=builder_contract,
                load_state=load_state,
                canonical_builder_path=canonical_builder_path,
                diagnostic=diagnostic,
                builder=builder,
            )
        )
    return tuple(results)


def discover_migrated_pipelines() -> tuple[ShippedPipelineInfo, ...]:
    """Return only migrated ``migrate`` roots that expose a workflow builder."""

    return tuple(
        info
        for info in discover_shipped_pipelines()
        if info.disposition == "migrate" and info.builder is not None
    )


def load_builder(target: str) -> Callable[..., workflow.Pipeline]:
    """Load a ``package.module:build_pipeline`` target.

    Raises ``ValueError`` when the target is malformed or cannot be imported.
    """

    if ":" not in target:
        raise ValueError("builder target must be 'package.module:builder_name'")
    module_name, builder_name = target.rsplit(":", 1)
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        raise ValueError(f"cannot import module {module_name!r}: {exc}") from exc
    builder = getattr(module, builder_name, None)
    if builder is None or not callable(builder):
        raise ValueError(f"module {module_name!r} has no callable {builder_name!r}")
    return builder


__all__ = [
    "ShippedPipelineInfo",
    "discover_migrated_pipelines",
    "discover_shipped_pipelines",
    "load_builder",
]
