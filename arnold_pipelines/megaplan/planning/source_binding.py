"""Fail-closed provenance for file-backed canonical plan requirements."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from arnold_pipelines.megaplan._core import now_utc
from arnold_pipelines.megaplan.types import CliError, PlanState


SOURCE_BINDING_SCHEMA = "arnold.megaplan.canonical_source_binding.v1"
SOURCE_CHECK_SCHEMA = "arnold.megaplan.canonical_source_check.v1"
SOURCE_CHANGED_ERROR = "canonical_source_changed"
SOURCE_EVIDENCE_FILE = "canonical_source_binding.json"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _semantic_body(text: str) -> str:
    """Canonicalize non-load-bearing formatting without changing prose."""

    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            body = parts[2]
    lines = [line.rstrip() for line in body.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def canonical_source_identity(path: Path, *, project_dir: Path) -> dict[str, Any]:
    path = path.resolve(strict=False)
    project_dir = project_dir.resolve(strict=False)
    identity: dict[str, Any] = {
        "schema": SOURCE_BINDING_SCHEMA,
        "source_path": str(path),
        "project_relative_path": "",
        "exists": path.is_file(),
        "semantic_sha256": "",
        "file_sha256": "",
        "git_revision": "",
        "git_blob": "",
    }
    try:
        identity["project_relative_path"] = path.relative_to(project_dir).as_posix()
    except ValueError:
        pass
    if not path.is_file():
        identity["errors"] = ["canonical_source_missing"]
        return identity
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        identity["errors"] = [f"canonical_source_unreadable:{type(exc).__name__}"]
        return identity
    identity["semantic_sha256"] = _sha256(_semantic_body(text).encode("utf-8"))
    identity["file_sha256"] = _sha256(raw)
    git_root_text = _git(path.parent, "rev-parse", "--show-toplevel")
    if git_root_text:
        git_root = Path(git_root_text).resolve(strict=False)
        try:
            git_path = path.relative_to(git_root).as_posix()
        except ValueError:
            git_path = ""
        identity["git_revision"] = _git(git_root, "rev-parse", "HEAD")
        identity["git_blob"] = _git(git_root, "hash-object", "--", git_path) if git_path else ""
        identity["git_path"] = git_path
    identity["errors"] = []
    return identity


def capture_canonical_source_binding(
    state: PlanState,
    *,
    source_path: Path,
    project_dir: Path,
) -> dict[str, Any]:
    identity = canonical_source_identity(source_path, project_dir=project_dir)
    if not identity["exists"] or identity.get("errors"):
        raise CliError(
            "canonical_source_unavailable",
            f"Cannot bind canonical source {source_path}: {identity.get('errors')}",
        )
    meta = state.setdefault("meta", {})
    meta["canonical_source_binding"] = {
        "schema": SOURCE_BINDING_SCHEMA,
        "bound_at": now_utc(),
        "bound": identity,
    }
    return identity


def _binding_from_state(state: Mapping[str, Any]) -> Mapping[str, Any] | None:
    meta = state.get("meta")
    if not isinstance(meta, Mapping):
        return None
    binding = meta.get("canonical_source_binding")
    return binding if isinstance(binding, Mapping) else None


def source_binding_report(state: Mapping[str, Any]) -> dict[str, Any]:
    binding = _binding_from_state(state)
    if binding is None:
        return {
            "schema": SOURCE_CHECK_SCHEMA,
            "status": "not_applicable",
            "bound": None,
            "current": None,
            "changed_fields": [],
        }
    bound = binding.get("bound")
    if not isinstance(bound, Mapping):
        return {
            "schema": SOURCE_CHECK_SCHEMA,
            "status": "invalid_binding",
            "bound": None,
            "current": None,
            "changed_fields": ["binding"],
        }
    project_dir = Path(str((state.get("config") or {}).get("project_dir") or "."))
    source_path = Path(str(bound.get("source_path") or ""))
    rel = str(bound.get("project_relative_path") or "")
    if rel:
        source_path = project_dir / rel
    current = canonical_source_identity(source_path, project_dir=project_dir)
    changed_fields = [
        field
        for field in ("exists", "semantic_sha256")
        if bound.get(field) != current.get(field)
    ]
    status = "changed" if changed_fields or current.get("errors") else "match"
    return {
        "schema": SOURCE_CHECK_SCHEMA,
        "status": status,
        "bound": dict(bound),
        "current": current,
        "changed_fields": changed_fields,
    }


def _write_evidence(plan_dir: Path, evidence: Mapping[str, Any]) -> None:
    path = plan_dir / SOURCE_EVIDENCE_FILE
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(dict(evidence), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def record_source_check(
    plan_dir: Path,
    state: MutableMapping[str, Any],
    report: Mapping[str, Any],
    *,
    operation: str,
    outcome: str,
    reason: str = "",
) -> dict[str, Any]:
    evidence = {
        **dict(report),
        "checked_at": now_utc(),
        "operation": operation,
        "outcome": outcome,
        "reason": reason,
    }
    _write_evidence(plan_dir, evidence)
    meta = state.setdefault("meta", {})
    if isinstance(meta, dict):
        checks = meta.setdefault("canonical_source_checks", [])
        if isinstance(checks, list):
            checks.append(
                {
                    "checked_at": evidence["checked_at"],
                    "operation": operation,
                    "status": report.get("status"),
                    "outcome": outcome,
                    "bound_sha256": (report.get("bound") or {}).get("semantic_sha256"),
                    "current_sha256": (report.get("current") or {}).get("semantic_sha256"),
                    "reason": reason,
                }
            )
            del checks[:-50]
    return evidence


def assert_canonical_source_current(
    plan_dir: Path,
    state: PlanState,
    *,
    operation: str,
) -> dict[str, Any]:
    report = source_binding_report(state)
    if report["status"] in {"match", "not_applicable"}:
        record_source_check(plan_dir, state, report, operation=operation, outcome="admitted")
        return report
    record_source_check(
        plan_dir,
        state,
        report,
        operation=operation,
        outcome="blocked",
        reason="canonical source must be reconciled and the plan re-finalized",
    )
    raise CliError(
        SOURCE_CHANGED_ERROR,
        f"{operation} refused: canonical source binding is {report['status']}; "
        f"changed_fields={report['changed_fields']}. Run override replan to "
        "reconcile the source, then critique/gate/finalize again.",
        extra={"canonical_source_binding": report},
    )


def reconcile_canonical_source_for_replan(
    plan_dir: Path,
    state: PlanState,
    *,
    reason: str,
) -> dict[str, Any] | None:
    report = source_binding_report(state)
    if report["status"] == "not_applicable":
        return None
    current = report.get("current")
    if not isinstance(current, Mapping) or not current.get("exists") or current.get("errors"):
        record_source_check(
            plan_dir,
            state,
            report,
            operation="override replan",
            outcome="blocked",
            reason="canonical source is unavailable",
        )
        raise CliError(
            "canonical_source_unavailable",
            f"override replan refused: current canonical source is unavailable: {current}",
            extra={"canonical_source_binding": report},
        )
    if report["status"] == "match":
        return report
    source_path = Path(str(current["source_path"]))
    body = _semantic_body(source_path.read_text(encoding="utf-8")).rstrip("\n")
    snapshot = str(state.get("idea_snapshot_path") or "idea_snapshot.md")
    (plan_dir / snapshot).write_text(body, encoding="utf-8")
    state["idea"] = body
    binding = state.setdefault("meta", {}).setdefault("canonical_source_binding", {})
    binding["bound"] = dict(current)
    binding["bound_at"] = now_utc()
    binding["reconciled_from"] = (report.get("bound") or {}).get("semantic_sha256")
    binding["reconcile_reason"] = reason
    reconciled = source_binding_report(state)
    record_source_check(
        plan_dir,
        state,
        reconciled,
        operation="override replan",
        outcome="reconciled",
        reason=reason,
    )
    return reconciled
