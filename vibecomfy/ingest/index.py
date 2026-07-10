from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from vibecomfy.index_types import IndexRow, WorkflowIndexRow


def index_workflows(root: str | Path) -> list[WorkflowIndexRow]:
    root = Path(root)
    entries: list[WorkflowIndexRow] = []
    if not root.exists():
        return entries
    official_root = _official_repo_root(root)
    official_metadata = _load_official_metadata(official_root) if official_root else {}
    for path in _workflow_json_paths(root, official_root):
        if path.name.endswith(".schema.json"):
            continue
        metadata = official_metadata.get(path.stem, {})
        entries.append(
            {
                "id": path.stem,
                "path": str(path),
                "source": "official" if official_root else "external",
                "media_type": _guess_media_type(path),
                **metadata,
            }
        )
    return entries


def write_index(path: str | Path, entries: Sequence[IndexRow]) -> None:
    Path(path).write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _guess_media_type(path: Path) -> str:
    text = str(path).lower()
    if "video" in text or "wan" in text:
        return "video"
    if "audio" in text:
        return "audio"
    if "3d" in text:
        return "3d"
    if "image" in text or "flux" in text or "sdxl" in text:
        return "image"
    return "unknown"


def _official_repo_root(root: Path) -> Path | None:
    candidates = [root]
    if root.name in {"templates", "packages", "blueprints"}:
        candidates.append(root.parent)
    for candidate in candidates:
        if candidate.name == "workflow_templates" or (candidate / "templates").exists() and (
            (candidate / "packages").exists() or (candidate / "blueprints").exists()
        ):
            return candidate
    return None


def _workflow_json_paths(root: Path, official_root: Path | None) -> list[Path]:
    if official_root is None:
        return sorted(root.rglob("*.json"))
    template_root = root if root.name == "templates" else official_root / "templates"
    if template_root.exists():
        return sorted(template_root.rglob("*.json"))
    return sorted(root.rglob("*.json"))


def _load_official_metadata(repo_root: Path) -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}
    for manifest in _official_manifest_paths(repo_root):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        package_id = _first_string(data, ("id", "name", "package_id", "title")) if isinstance(data, dict) else None
        package_id = package_id or manifest.parent.name
        for json_ref in _iter_json_refs(data):
            key = Path(json_ref).stem
            if not key or key.endswith(".schema"):
                continue
            metadata.setdefault(key, {})
            metadata[key].setdefault("package_id", package_id)
            metadata[key].setdefault("manifest_path", str(manifest))
    return metadata


def _official_manifest_paths(repo_root: Path) -> list[Path]:
    names = {"manifest.json", "package.json", "index.json"}
    roots = [repo_root / "packages", repo_root / "blueprints", repo_root / "packages" / "blueprints"]
    paths: list[Path] = []
    for candidate_root in roots:
        if not candidate_root.exists():
            continue
        paths.extend(path for path in candidate_root.rglob("*.json") if path.name in names)
    return sorted(paths)


def _iter_json_refs(value: Any):
    if isinstance(value, dict):
        for nested in value.values():
            yield from _iter_json_refs(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_json_refs(nested)
    elif isinstance(value, str) and value.endswith(".json"):
        yield value


def _first_string(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None
