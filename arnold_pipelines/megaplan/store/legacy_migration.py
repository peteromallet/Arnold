"""Legacy local plan migration helpers."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Literal

from arnold_pipelines.megaplan.store.base import deterministic_idempotency_key, validate_plan_artifact_name
from arnold_pipelines.megaplan.store.file import FileStore

MigrationMode = Literal["orphan", "legacy-epic"]


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    return safe or hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _source_plans_root(source_home: Path, source_project: str) -> Path:
    return source_home.expanduser() / ".megaplan" / source_project / "plans"


def _iter_source_projects(source_home: Path) -> list[str]:
    root = source_home.expanduser() / ".megaplan"
    if not root.exists():
        return []
    return [
        path.name
        for path in sorted(root.iterdir())
        if path.is_dir() and (path / "plans").is_dir()
    ]


def _plan_files(plan_dir: Path) -> list[Path]:
    return [path for path in sorted(plan_dir.rglob("*")) if path.is_file()]


def _snapshot_plan_dir(plan_dir: Path) -> dict[str, Any]:
    files = []
    digest = hashlib.sha256()
    for path in _plan_files(plan_dir):
        rel = path.relative_to(plan_dir).as_posix()
        validate_plan_artifact_name(rel)
        data = path.read_bytes()
        file_sha = hashlib.sha256(data).hexdigest()
        files.append({"path": rel, "size_bytes": len(data), "sha256": file_sha})
        digest.update(rel.encode("utf-8") + b"\0" + file_sha.encode("ascii") + b"\0")
    return {
        "sha256": digest.hexdigest(),
        "files": files,
    }


def _legacy_plan_id(source_project: str, source_plan_id: str) -> str:
    return f"legacy-{_safe_id(source_project)}-{_safe_id(source_plan_id)}"


def _legacy_epic_title(source_project: str) -> str:
    return f"Legacy local plans: {source_project}"


def migrate_local_plans(
    *,
    source_home: Path,
    source_project: str | None,
    all_projects: bool,
    target_project_dir: Path,
    mode: MigrationMode,
    dry_run: bool,
) -> dict[str, Any]:
    if bool(source_project) == bool(all_projects):
        raise ValueError("Specify exactly one of --source-project or --all-projects")
    source_home = source_home.expanduser()
    target_project_dir = target_project_dir.expanduser().resolve()
    projects = _iter_source_projects(source_home) if all_projects else [str(source_project)]
    from arnold_pipelines.megaplan.store.multi import MultiStore

    target_root = MultiStore.canonical_filestore_root(target_project_dir)
    target = FileStore(target_root) if (not dry_run or target_root.exists()) else None
    result: dict[str, Any] = {
        "success": True,
        "step": "migrate-local-plans",
        "source_home": str(source_home),
        "target_project_dir": str(target_project_dir),
        "mode": mode,
        "dry_run": dry_run,
        "projects": [],
        "created": [],
        "skipped": [],
        "conflicts": [],
        "errors": [],
    }
    legacy_epic_ids: dict[str, str] = {}
    if mode == "legacy-epic":
        result["legacy_epic_ids"] = legacy_epic_ids
    for project in projects:
        plans_root = _source_plans_root(source_home, project)
        project_entry = {"source_project": project, "plans_root": str(plans_root), "plans": []}
        result["projects"].append(project_entry)
        if not plans_root.exists():
            result["errors"].append({"source_project": project, "error": "plans_root_missing"})
            continue
        legacy_epic_id: str | None = None
        if mode == "legacy-epic":
            title = _legacy_epic_title(project)
            existing = (
                next((epic for epic in target.list_epics(active_only=False, limit=500) if epic.title == title), None)
                if target is not None
                else None
            )
            if existing is not None:
                legacy_epic_id = existing.id
            elif not dry_run:
                if target is None:
                    target = FileStore(target_root)
                created_epic = target.create_epic(
                    title=title,
                    goal=f"Imported from pre-schema local megaplan plan directories for {project}.",
                    body="Legacy local plans imported by `megaplan migrate-local-plans`.",
                    home_backend="file",
                )
                legacy_epic_id = created_epic.id
            else:
                legacy_epic_id = f"dry-run-legacy-local-plans-{_safe_id(project)}"
            legacy_epic_ids[project] = legacy_epic_id
            project_entry["legacy_epic_id"] = legacy_epic_id
        for plan_dir in sorted(path for path in plans_root.iterdir() if path.is_dir()):
            snapshot = _snapshot_plan_dir(plan_dir)
            plan_id = _legacy_plan_id(project, plan_dir.name)
            provenance = {
                "source_project": project,
                "source_plan_id": plan_dir.name,
                "source_plan_dir": str(plan_dir),
                "snapshot_sha256": snapshot["sha256"],
                "files": snapshot["files"],
            }
            existing = target.load_plan(plan_id) if target is not None else None
            if existing is not None:
                existing_meta = existing.meta.get("legacy_migration") if isinstance(existing.meta, dict) else None
                if isinstance(existing_meta, dict) and existing_meta.get("snapshot_sha256") == snapshot["sha256"]:
                    result["skipped"].append({"plan_id": plan_id, "reason": "unchanged"})
                    project_entry["plans"].append({"plan_id": plan_id, "action": "skipped", "snapshot_sha256": snapshot["sha256"]})
                    continue
                conflict = {"plan_id": plan_id, "reason": "changed_source", "snapshot_sha256": snapshot["sha256"]}
                result["conflicts"].append(conflict)
                project_entry["plans"].append({"plan_id": plan_id, "action": "conflict", "snapshot_sha256": snapshot["sha256"]})
                continue
            if not dry_run:
                if target is None:
                    target = FileStore(target_root)
                target.create_plan(
                    sprint_id=None,
                    epic_id=legacy_epic_id,
                    name=plan_dir.name,
                    idea=f"Legacy local plan imported from {project}/{plan_dir.name}",
                    plan_id=plan_id,
                    meta={"legacy_migration": provenance},
                    idempotency_key=deterministic_idempotency_key("legacy-local-plan", project, plan_dir.name, snapshot["sha256"]),
                )
                for source_file in _plan_files(plan_dir):
                    rel = validate_plan_artifact_name(source_file.relative_to(plan_dir).as_posix())
                    target.write_plan_artifact(
                        plan_id,
                        rel,
                        source_file.read_bytes(),
                        idempotency_key=deterministic_idempotency_key("legacy-local-plan-artifact", plan_id, rel, snapshot["sha256"]),
                    )
            result["created"].append({"plan_id": plan_id, "snapshot_sha256": snapshot["sha256"], "file_count": len(snapshot["files"])})
            project_entry["plans"].append({"plan_id": plan_id, "action": "created", "snapshot_sha256": snapshot["sha256"]})
    result["success"] = not result["conflicts"] and not result["errors"]
    return result
