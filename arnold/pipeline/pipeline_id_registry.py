"""Source-controlled pipeline identity registry validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from arnold.kernel.ids import (
    WorkflowIdentity,
    derive_registry_runtime_id,
    workflow_identity,
)


@dataclass(frozen=True)
class PipelineIdRegistry:
    """Source-controlled package metadata for human pipeline aliases.

    The registry validates authored aliases and stable metadata.  It is not a
    runtime identity authority: runtime identity is always derived from the
    human alias plus the manifest hash supplied by the executing workflow.
    """

    pipelines: tuple[dict[str, Any], ...]

    @property
    def by_name(self) -> dict[str, dict[str, Any]]:
        return {str(item["name"]): dict(item) for item in self.pipelines}

    def resolve_runtime_identity(
        self,
        alias: str,
        manifest_hash: str,
    ) -> "RegistryRuntimeIdentity":
        """Validate *alias* against registry metadata and derive runtime identity.

        Registry ``stable_id`` and ``previous_stable_ids`` fields remain package
        metadata.  They never replace the canonical runtime formula, which is
        derived from ``alias`` plus ``manifest_hash`` through
        :class:`arnold.kernel.ids.WorkflowIdentity`.
        """

        return resolve_registry_runtime_identity(self, alias, manifest_hash)


class PipelineIdRegistryError(ValueError):
    """Raised when the pipeline ID registry violates the M1 metadata contract."""


@dataclass(frozen=True)
class RegistryRuntimeIdentity:
    """Registry-validated view of canonical runtime identity.

    ``registry_entry`` is retained as validation/provenance metadata only.  The
    runtime fields come from ``workflow_identity`` and therefore from the
    human alias plus manifest hash, not from registry stable IDs.
    """

    workflow_identity: WorkflowIdentity
    registry_entry: Mapping[str, Any]

    @property
    def alias(self) -> str:
        return self.workflow_identity.alias

    @property
    def manifest_hash(self) -> str:
        return self.workflow_identity.manifest_hash

    @property
    def pipeline_identity(self) -> str:
        return self.workflow_identity.pipeline_identity

    @property
    def registry_runtime_id(self) -> str:
        return derive_registry_runtime_id(self.alias, self.manifest_hash)


def load_pipeline_id_registry(path: str | Path) -> PipelineIdRegistry:
    """Load and validate a pipeline ID registry JSON file."""

    return _load_pipeline_id_registry_set((path,))


def load_pipeline_id_registries(paths: Iterable[str | Path]) -> PipelineIdRegistry:
    """Load and validate multiple registry files as one aggregate set."""

    return _load_pipeline_id_registry_set(paths)


def resolve_registry_runtime_identity(
    registry: PipelineIdRegistry,
    alias: str,
    manifest_hash: str,
) -> RegistryRuntimeIdentity:
    """Validate registry metadata, then derive identity from alias plus hash.

    If a registry row declares ``manifest_hash``, the caller-supplied
    ``manifest_hash`` must match it.  Matching is a freshness check on package
    metadata only; the registry row does not provide or override runtime
    ``pipeline_identity``.
    """

    identity = workflow_identity(alias, manifest_hash)
    entry = registry.by_name.get(identity.alias)
    if entry is None:
        raise PipelineIdRegistryError(
            f"pipeline alias {identity.alias!r} is not declared in registry metadata"
        )

    registry_manifest_hash = entry.get("manifest_hash")
    if (
        registry_manifest_hash is not None
        and registry_manifest_hash != identity.manifest_hash
    ):
        raise PipelineIdRegistryError(
            f"pipeline alias {identity.alias!r} registry manifest_hash "
            f"{registry_manifest_hash!r} does not match runtime manifest_hash "
            f"{identity.manifest_hash!r}"
        )

    return RegistryRuntimeIdentity(
        workflow_identity=identity,
        registry_entry=dict(entry),
    )


def _load_pipeline_id_registry_set(paths: Iterable[str | Path]) -> PipelineIdRegistry:
    path_list = [Path(path) for path in paths]
    aggregate = len(path_list) > 1
    pipelines: list[dict[str, Any]] = []
    errors: list[str] = []

    for path in path_list:
        data, load_errors = _load_registry_json(path)
        errors.extend(load_errors)
        if data is None:
            continue
        raw_pipelines = data.get("pipelines")
        assert isinstance(raw_pipelines, list)
        for index, raw in enumerate(raw_pipelines):
            if not isinstance(raw, Mapping):
                errors.append(_format_error(path, f"pipelines[{index}] must be an object", aggregate=aggregate))
                continue
            pipelines.append({"__registry_path__": str(path), **dict(raw)})

    if errors:
        raise PipelineIdRegistryError("; ".join(errors))
    return _validate_registry_items(pipelines, aggregate=aggregate)


def _load_registry_json(path: Path) -> tuple[Mapping[str, Any] | None, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        return None, [f"pipeline ID registry at {path} must be a JSON object"]
    raw_pipelines = data.get("pipelines")
    if not isinstance(raw_pipelines, list):
        return None, [f"pipeline ID registry at {path} requires a pipelines list"]
    return data, []


def _validate_registry_items(
    items: list[dict[str, Any]],
    *,
    aggregate: bool,
) -> PipelineIdRegistry:
    pipelines: list[dict[str, Any]] = []
    seen_names: dict[str, str] = {}
    seen_stable_ids: dict[str, str] = {}
    seen_seam_ids: dict[str, str] = {}
    seen_previous_stable_ids: dict[str, str] = {}
    errors: list[str] = []

    for item in items:
        registry_path = str(item.pop("__registry_path__", ""))
        name = item.get("name")
        if not isinstance(name, str) or not name:
            errors.append(_format_error(registry_path, "pipeline entry missing name", aggregate=aggregate))
            continue
        previous_name = seen_names.get(name)
        if previous_name is not None:
            errors.append(f"duplicate pipeline name {name!r} on {previous_name!r} and {name!r}")
        else:
            seen_names[name] = name

        stable_id = item.get("stable_id")
        contract_capable = bool(item.get("typed_contract_capable"))
        if contract_capable and (not isinstance(stable_id, str) or not stable_id):
            errors.append(f"pipeline {name!r} is typed contract-capable but missing stable_id")
        if isinstance(stable_id, str) and stable_id:
            previous = seen_stable_ids.get(stable_id)
            if previous is not None:
                errors.append(f"duplicate stable_id {stable_id!r} on {previous!r} and {name!r}")
            else:
                colliding_previous = seen_previous_stable_ids.get(stable_id)
                if colliding_previous is not None:
                    errors.append(
                        f"active stable_id {stable_id!r} on {name!r} collides with previous_stable_id on {colliding_previous!r}"
                    )
                seen_stable_ids[stable_id] = name
        for previous_stable_id in _iter_previous_stable_ids(item.get("previous_stable_ids")):
            if previous_stable_id == stable_id:
                errors.append(
                    f"pipeline {name!r} lists current stable_id {stable_id!r} in previous_stable_ids"
                )
                continue
            previous = seen_stable_ids.get(previous_stable_id)
            if previous is not None:
                errors.append(
                    f"previous_stable_id {previous_stable_id!r} on {name!r} collides with active stable_id on {previous!r}"
                )
                continue
            previous = seen_previous_stable_ids.get(previous_stable_id)
            if previous is not None:
                errors.append(
                    f"duplicate previous_stable_id {previous_stable_id!r} on {previous!r} and {name!r}"
                )
            else:
                seen_previous_stable_ids[previous_stable_id] = name

        for seam_id in _iter_seam_ids(item.get("seam_ids")):
            previous = seen_seam_ids.get(seam_id)
            if previous is not None:
                errors.append(f"duplicate seam_id {seam_id!r} on {previous!r} and {name!r}")
            else:
                seen_seam_ids[seam_id] = name
        pipelines.append(item)

    if errors:
        raise PipelineIdRegistryError("; ".join(errors))
    return PipelineIdRegistry(pipelines=tuple(pipelines))


def _format_error(path: str | Path, message: str, *, aggregate: bool = False) -> str:
    if aggregate:
        return f"{path}: {message}"
    return message


def _iter_seam_ids(value: Any) -> Iterable[str]:
    if not isinstance(value, list):
        return ()
    return (item for item in value if isinstance(item, str) and item)


def _iter_previous_stable_ids(value: Any) -> Iterable[str]:
    if not isinstance(value, list):
        return ()
    return (item for item in value if isinstance(item, str) and item)
