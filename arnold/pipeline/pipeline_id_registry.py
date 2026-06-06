"""Source-controlled pipeline identity registry validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class PipelineIdRegistry:
    pipelines: tuple[dict[str, Any], ...]

    @property
    def by_name(self) -> dict[str, dict[str, Any]]:
        return {str(item["name"]): dict(item) for item in self.pipelines}


class PipelineIdRegistryError(ValueError):
    """Raised when the pipeline ID registry violates the M1 metadata contract."""


def load_pipeline_id_registry(path: str | Path) -> PipelineIdRegistry:
    """Load and validate a pipeline ID registry JSON file."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise PipelineIdRegistryError("pipeline ID registry must be a JSON object")
    raw_pipelines = data.get("pipelines")
    if not isinstance(raw_pipelines, list):
        raise PipelineIdRegistryError("pipeline ID registry requires a pipelines list")

    pipelines: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    seen_stable_ids: dict[str, str] = {}
    seen_seam_ids: dict[str, str] = {}
    seen_previous_stable_ids: dict[str, str] = {}
    errors: list[str] = []

    for index, raw in enumerate(raw_pipelines):
        if not isinstance(raw, Mapping):
            errors.append(f"pipelines[{index}] must be an object")
            continue
        item = dict(raw)
        name = item.get("name")
        if not isinstance(name, str) or not name:
            errors.append(f"pipelines[{index}] missing name")
            continue
        if name in seen_names:
            errors.append(f"duplicate pipeline name {name!r}")
        seen_names.add(name)

        stable_id = item.get("stable_id")
        contract_capable = bool(item.get("typed_contract_capable"))
        if contract_capable and (not isinstance(stable_id, str) or not stable_id):
            errors.append(f"pipeline {name!r} is typed contract-capable but missing stable_id")
        if isinstance(stable_id, str) and stable_id:
            previous = seen_stable_ids.get(stable_id)
            if previous is not None:
                errors.append(f"duplicate stable_id {stable_id!r} on {previous!r} and {name!r}")
            else:
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


def _iter_seam_ids(value: Any) -> Iterable[str]:
    if not isinstance(value, list):
        return ()
    return (item for item in value if isinstance(item, str) and item)


def _iter_previous_stable_ids(value: Any) -> Iterable[str]:
    if not isinstance(value, list):
        return ()
    return (item for item in value if isinstance(item, str) and item)
