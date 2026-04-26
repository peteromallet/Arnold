from __future__ import annotations

import importlib.util
from pathlib import Path

from vibecomfy.workflow import VibeWorkflow


READY_ROOT = Path(__file__).resolve().parents[2] / "ready_templates"


def ready_template_ids() -> list[str]:
    if not READY_ROOT.exists():
        return []
    return sorted(
        path.relative_to(READY_ROOT).with_suffix("").as_posix()
        for path in READY_ROOT.rglob("*.py")
        if path.name != "__init__.py" and not path.name.startswith("_")
    )


def workflow_from_ready(template_id: str) -> VibeWorkflow:
    path = _resolve_ready_path(template_id)
    spec = importlib.util.spec_from_file_location(f"vibecomfy_ready_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not import ready template {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    build = getattr(module, "build", None)
    if build is None:
        raise ValueError(f"Ready template {template_id} must define build()")
    workflow = build()
    if not isinstance(workflow, VibeWorkflow):
        raise TypeError(f"Ready template {template_id} build() must return VibeWorkflow, got {type(workflow).__name__}")
    workflow.metadata["ready_template"] = _template_id_for_path(path)
    return workflow


def _resolve_ready_path(template_id: str) -> Path:
    candidates = [
        READY_ROOT / f"{template_id}.py",
        READY_ROOT / template_id,
    ]
    if "/" not in template_id:
        candidates.extend(READY_ROOT.glob(f"*/{template_id}.py"))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise KeyError(f"Ready template not found: {template_id}")


def _template_id_for_path(path: Path) -> str:
    return path.relative_to(READY_ROOT).with_suffix("").as_posix()
