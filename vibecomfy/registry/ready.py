from __future__ import annotations

import importlib.util
from pathlib import Path
import warnings

from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.workflow import VibeWorkflow


READY_ROOT = Path(__file__).resolve().parents[2] / "ready_templates"
_WARNED_COLLISIONS: set[str] = set()


def ready_template_ids() -> list[str]:
    seen: dict[str, Path] = {}
    for root in _ready_roots():
        if not root.exists():
            continue
        for path in _template_paths(root):
            template_id = path.relative_to(root).with_suffix("").as_posix()
            if template_id in seen:
                _warn_collision(template_id, path, seen[template_id])
                continue
            seen[template_id] = path
    return sorted(seen)


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
    resolved_template_id = _template_id_for_path(path)
    if not workflow.metadata.get("python_policy_applied"):
        ready_metadata = getattr(module, "READY_METADATA", None)
        if isinstance(ready_metadata, dict):
            ready_metadata = {**ready_metadata, "ready_template": ready_metadata.get("ready_template") or resolved_template_id}
            requirements = getattr(module, "READY_REQUIREMENTS", None)
            workflow = apply_ready_template_policy(
                workflow,
                ready_metadata,
                source_path=str(path),
                requirements=requirements if isinstance(requirements, dict) else None,
            )
    workflow.metadata["ready_template"] = workflow.metadata.get("ready_template") or resolved_template_id
    return workflow


def _resolve_ready_path(template_id: str) -> Path:
    for root in _ready_roots():
        candidates = [
            root / f"{template_id}.py",
            root / template_id,
        ]
        if "/" not in template_id and root.exists():
            candidates.extend(root.glob(f"*/{template_id}.py"))
        for candidate in candidates:
            if candidate.is_file():
                return candidate
    raise KeyError(f"Ready template not found: {template_id}")


def _template_id_for_path(path: Path) -> str:
    resolved = path.resolve()
    for root in _ready_roots():
        try:
            return resolved.relative_to(root.resolve()).with_suffix("").as_posix()
        except ValueError:
            continue
    return path.with_suffix("").name


def _ready_roots() -> list[Path]:
    from vibecomfy.extras import ensure_plugins_loaded, registered_ready_roots

    ensure_plugins_loaded()
    roots = [
        READY_ROOT,
        Path.cwd() / "vibecomfy_extras" / "ready_templates",
        Path.home() / ".vibecomfy" / "ready_templates",
        *registered_ready_roots(),
    ]
    deduped: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.expanduser().resolve()
        if resolved not in seen:
            deduped.append(resolved)
            seen.add(resolved)
    return deduped


def _template_paths(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if path.name != "__init__.py" and not path.name.startswith("_")
    )


def _warn_collision(template_id: str, candidate: Path, winner: Path) -> None:
    if template_id in _WARNED_COLLISIONS:
        return
    warnings.warn(
        f"Ready template id collision for {template_id!r}; using {winner} and ignoring {candidate}",
        RuntimeWarning,
        stacklevel=2,
    )
    _WARNED_COLLISIONS.add(template_id)


def _reset_for_tests() -> None:
    _WARNED_COLLISIONS.clear()
