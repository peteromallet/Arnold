"""Native-first ``folder_audit`` package internals."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from arnold.pipeline import Pipeline
from arnold.pipeline.types import Edge, Stage, StepContext, StepResult


name: str = "folder-audit"
description: str = "Deterministic directory-tree audit pipeline."
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("native",)
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "linear")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("audit", "folder-audit", "tree-walk")


def _default_worker(*, prompt: str, spec: str = "", **kwargs: Any) -> str:
    """Default audit worker stub."""
    return json.dumps([])


def _build_tree(
    path: Path,
    max_depth: int = 3,
    respect_gitignore: bool = True,
    skip_hidden: bool = True,
    _current_depth: int = 0,
    _relative_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Walk *path* and return a flat directory tree inventory."""
    if _current_depth > max_depth or not path.is_dir():
        return []

    if _relative_root is None:
        _relative_root = path

    gitignore_patterns: set[str] = set()
    if respect_gitignore:
        gitignore_path = path / ".gitignore"
        if gitignore_path.is_file():
            gitignore_patterns = {
                line.strip()
                for line in gitignore_path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            }

    children: list[dict[str, Any]] = []
    sub_results: list[dict[str, Any]] = []
    try:
        for child in sorted(path.iterdir()):
            name = child.name
            if skip_hidden and name.startswith("."):
                continue
            if name in gitignore_patterns or (
                child.is_dir() and f"{name}/" in gitignore_patterns
            ):
                continue

            is_dir = child.is_dir()
            children.append({"name": name, "type": "dir" if is_dir else "file"})
            if is_dir and _current_depth < max_depth:
                sub_results.extend(
                    _build_tree(
                        child,
                        max_depth=max_depth,
                        respect_gitignore=respect_gitignore,
                        skip_hidden=skip_hidden,
                        _current_depth=_current_depth + 1,
                        _relative_root=_relative_root,
                    )
                )
    except (OSError, PermissionError):
        pass

    try:
        rel = str(path.relative_to(_relative_root))
    except ValueError:
        rel = str(path)
    if rel in {".", ""}:
        rel = "."

    return [
        {
            "path": rel,
            "level": _current_depth,
            "children": children,
        },
        *sub_results,
    ]


def _summarize_children(
    children: list[dict[str, Any]], max_files: int = 50
) -> list[dict[str, Any]]:
    """Cap file listings while always keeping directories."""
    dirs = [child for child in children if child.get("type") == "dir"]
    files = [child for child in children if child.get("type") != "dir"]
    if len(files) <= max_files:
        return dirs + files
    kept = files[:max_files]
    omitted = len(files) - max_files
    return dirs + kept + [{"name": f"... ({omitted} more files)"}]


def _compute_summary(folders: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate classification counts for audit output."""
    total_items = 0
    counts: dict[str, int] = {}
    for folder in folders:
        for item in folder.get("items", []):
            total_items += 1
            classification = str(item.get("classification", "unknown"))
            counts[classification] = counts.get(classification, 0) + 1

    return {
        "total_folders": len(folders),
        "total_items": total_items,
        **counts,
    }


def _next_version_path(artifact_root: str | Path) -> Path:
    """Ensure the artifact root exists and return it as a path."""
    root = Path(artifact_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass
class IngestStep:
    """Walk the target directory and store the resulting tree."""

    name: str = "ingest"
    kind: str = "ingest"

    def run(self, ctx: StepContext) -> StepResult:
        target_dir = Path(str(ctx.state.get("target_dir", "."))).resolve()
        max_depth = int(ctx.state.get("max_depth", 3))
        respect_gitignore = bool(ctx.state.get("respect_gitignore", True))
        skip_hidden = bool(ctx.state.get("skip_hidden", True))
        tree = _build_tree(
            target_dir,
            max_depth=max_depth,
            respect_gitignore=respect_gitignore,
            skip_hidden=skip_hidden,
        )
        return StepResult(
            next="audit",
            state_patch={"tree": tree, "target_dir": str(target_dir)},
        )


@dataclass
class AuditStep:
    """Classify the directory tree with a supplied worker."""

    _worker: Callable[..., Any] | None = None
    _pipeline_name: str = name
    _chunk_size: int = 50
    _max_workers: int = 1
    name: str = "audit"
    kind: str = "audit"

    def run(self, ctx: StepContext) -> StepResult:
        if self._worker is None:
            raise RuntimeError(
                "AuditStep has no worker — supply _worker=... to AuditStep() "
                "or pass worker=... to build_pipeline()"
            )

        profile = ctx.state.get("profile", "")
        if isinstance(profile, dict):
            spec = str(profile.get("audit", ""))
        elif isinstance(profile, str):
            spec = profile
        else:
            spec = ""

        prompt = json.dumps(ctx.state.get("tree", []), indent=2)
        raw = self._worker(prompt=prompt, spec=spec)
        result_data: Any = json.loads(raw)
        if isinstance(result_data, list):
            result_data = {"folders": result_data}

        folders = list(result_data.get("folders", []))
        audit_result = {
            "folders": folders,
            "summary": result_data.get("summary", _compute_summary(folders)),
            "settled_decisions": result_data.get("settled_decisions", []),
        }

        artifact_root = _next_version_path(ctx.artifact_root)
        raw_dir = artifact_root / "audit_raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "v1.md").write_text(prompt, encoding="utf-8")

        return StepResult(next="done", state_patch={"audit": audit_result})


@dataclass
class EmitStep:
    """Write ``audit.json`` and ``audit.md`` artifacts."""

    name: str = "emit"
    kind: str = "emit"

    def run(self, ctx: StepContext) -> StepResult:
        artifact_root = _next_version_path(ctx.artifact_root)
        audit_data = dict(ctx.state.get("audit", {}))
        folders = list(audit_data.get("folders", []))

        json_path = artifact_root / "audit.json"
        json_path.write_text(
            json.dumps(audit_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        md_lines = ["# Folder Audit\n"]
        for folder in folders:
            folder_path = folder.get("path", "?")
            purpose = folder.get("inferred_purpose", "")
            suffix = f" — {purpose}" if purpose else ""
            md_lines.append(f"- `{folder_path}`{suffix}")
            for item in folder.get("items", []):
                classification = item.get("classification", "")
                class_suffix = (
                    f" † {classification}"
                    if classification and classification != "fit"
                    else ""
                )
                md_lines.append(
                    f"  - {item.get('name', '?')} ({item.get('type', 'file')}){class_suffix}"
                )

        md_path = artifact_root / "audit.md"
        md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
        return StepResult(
            next="halt",
            outputs={"audit_json": json_path, "audit_md": md_path},
        )


def _build_projected_pipeline(worker: Callable[..., Any] | None = None) -> Pipeline:
    active_worker = worker if worker is not None else _default_worker
    return Pipeline(
        stages={
            "ingest": Stage(
                name="ingest",
                step=IngestStep(),
                edges=(Edge(label="audit", target="audit"),),
            ),
            "audit": Stage(
                name="audit",
                step=AuditStep(_worker=active_worker, _pipeline_name=name),
                edges=(Edge(label="done", target="emit"),),
            ),
            "emit": Stage(
                name="emit",
                step=EmitStep(),
                edges=(Edge(label="halt", target="halt"),),
            ),
        },
        entry="ingest",
    )


def build_pipeline(worker: Callable[..., Any] | None = None) -> Pipeline:
    """Build the projected Arnold pipeline with attached native program."""
    from arnold.pipelines.folder_audit.native import build_native_program

    projected = _build_projected_pipeline(worker=worker)
    return Pipeline(
        stages=projected.stages,
        entry=projected.entry,
        resource_bundles=projected.resource_bundles,
        native_program=build_native_program(),
    )


__all__ = [
    "AuditStep",
    "EmitStep",
    "IngestStep",
    "_build_tree",
    "_compute_summary",
    "_default_worker",
    "_next_version_path",
    "_summarize_children",
    "arnold_api_version",
    "build_pipeline",
    "capabilities",
    "default_profile",
    "description",
    "driver",
    "entrypoint",
    "name",
    "recommended_profiles",
    "supported_modes",
]
