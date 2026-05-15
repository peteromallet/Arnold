from typing import TYPE_CHECKING, Any

from .library import (
    load_workflow_reference,
    workflow_from_file,
    workflow_from_id,
)
from .ready import (
    dynamic_ready_template_rows,
    ready_template_ids,
    repo_ready_template_id_for_path,
    repo_ready_template_ids,
    repo_ready_template_paths,
    workflow_from_ready,
)

if TYPE_CHECKING:
    from .models_loader import ModelEntry, ModelSource, ModelTarget, canonical_filename, load_registry, normalize_alias, stage_entry, stage_many

_LOADER_EXPORTS = {
    "ModelEntry",
    "ModelSource",
    "ModelTarget",
    "canonical_filename",
    "load_registry",
    "normalize_alias",
    "stage_entry",
    "stage_many",
}


def __getattr__(name: str) -> Any:
    if name in _LOADER_EXPORTS:
        from . import models_loader

        return getattr(models_loader, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "workflow_from_file",
    "load_workflow_reference",
    "workflow_from_id",
    "ready_template_ids",
    "dynamic_ready_template_rows",
    "repo_ready_template_id_for_path",
    "repo_ready_template_ids",
    "repo_ready_template_paths",
    "workflow_from_ready",
    "ModelEntry",
    "ModelSource",
    "ModelTarget",
    "canonical_filename",
    "load_registry",
    "normalize_alias",
    "stage_entry",
    "stage_many",
]
