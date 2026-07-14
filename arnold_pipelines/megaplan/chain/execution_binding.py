"""Immutable execution identity for drift-sensitive Megaplan chains.

The persisted chain cursor is mutable operational state.  This module keeps the
identity accepted before the first milestone separate from later observations,
so loading, resuming, or reconciling a cursor cannot silently adopt edited
chain, anchor, brief, source, or runtime inputs.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping

import yaml

from arnold_pipelines.megaplan.cloud.runtime_provenance import runtime_provenance
from arnold_pipelines.megaplan.types import CliError


BINDING_SCHEMA = "arnold.megaplan.chain_execution_binding.v1"
DRIFT_ERROR = "chain_execution_binding_drift"
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_revision(root: Path | None) -> str:
    return _git(root, "rev-parse", "HEAD") if root is not None else ""


def _git_commit_exists(root: Path, revision: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", f"{revision}^{{commit}}"],
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def _project_root(spec_path: Path) -> Path:
    resolved = spec_path.resolve(strict=False)
    for parent in resolved.parents:
        if parent.name == ".megaplan":
            return parent.parent
    top = _git(resolved.parent, "rev-parse", "--show-toplevel")
    return Path(top).resolve() if top else resolved.parent


def _raw_spec(spec_path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def binding_policy(spec_path: Path) -> dict[str, Any]:
    driver = _raw_spec(spec_path).get("driver")
    driver = driver if isinstance(driver, dict) else {}
    mode = str(driver.get("execution_binding") or "optional").strip().lower()
    if mode not in {"optional", "required"}:
        raise CliError(
            "invalid_spec",
            "driver.execution_binding must be `optional` or `required`",
        )
    return {
        "required": mode == "required",
        "mode": mode,
        "intended_initiative_revision": str(
            driver.get("intended_initiative_revision") or ""
        ).strip(),
        "initiative_path": str(driver.get("initiative_path") or "").strip(),
        "require_editable_runtime_match": bool(
            driver.get("require_editable_runtime_match", False)
        ),
    }


def _resolve_asset(path_value: str, *, spec_path: Path, project_root: Path) -> Path:
    value = Path(path_value).expanduser()
    if value.is_absolute():
        return value.resolve(strict=False)
    project_candidate = (project_root / value).resolve(strict=False)
    if project_candidate.exists():
        return project_candidate
    return (spec_path.parent / value).resolve(strict=False)


def _asset_entry(
    kind: str,
    path_value: str,
    *,
    spec_path: Path,
    project_root: Path,
) -> dict[str, Any]:
    path = _resolve_asset(path_value, spec_path=spec_path, project_root=project_root)
    return {
        "kind": kind,
        "declared_path": path_value,
        "resolved_path": str(path),
        "sha256": _sha256_file(path) if path.is_file() else "",
        "exists": path.is_file(),
    }


def _bundle_assets(
    raw: Mapping[str, Any], *, spec_path: Path, project_root: Path
) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    anchors = raw.get("anchors")
    if isinstance(anchors, Mapping):
        north_star = anchors.get("north_star")
        if isinstance(north_star, str) and north_star.strip():
            assets.append(
                _asset_entry(
                    "north_star",
                    north_star.strip(),
                    spec_path=spec_path,
                    project_root=project_root,
                )
            )
    milestones = raw.get("milestones")
    if not isinstance(milestones, list):
        return assets
    for index, milestone in enumerate(milestones):
        if not isinstance(milestone, Mapping):
            continue
        idea = milestone.get("idea")
        if isinstance(idea, str) and idea.strip():
            assets.append(
                _asset_entry(
                    f"milestone_brief:{index}",
                    idea.strip(),
                    spec_path=spec_path,
                    project_root=project_root,
                )
            )
        milestone_anchors = milestone.get("anchors")
        if isinstance(milestone_anchors, Mapping):
            milestone_north_star = milestone_anchors.get("north_star")
            if isinstance(milestone_north_star, str) and milestone_north_star.strip():
                assets.append(
                    _asset_entry(
                        f"milestone_north_star:{index}",
                        milestone_north_star.strip(),
                        spec_path=spec_path,
                        project_root=project_root,
                    )
                )
    return assets


def _revision_blob(root: Path, revision: str, relative_path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{revision}:{relative_path}"],
        check=False,
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


def _revision_comparable_spec_sha(value: bytes) -> str:
    """Hash authored spec semantics without the self-referential revision pin."""

    raw = yaml.safe_load(value.decode("utf-8"))
    if not isinstance(raw, dict):
        return ""
    driver = raw.get("driver")
    if isinstance(driver, dict) and "intended_initiative_revision" in driver:
        driver = dict(driver)
        driver["intended_initiative_revision"] = "<CONTENT_ADDRESSED_REVISION_PIN>"
        raw = dict(raw)
        raw["driver"] = driver
    return _sha256_bytes(
        json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def _revision_verification(
    *,
    policy: Mapping[str, Any],
    raw: Mapping[str, Any],
    spec_path: Path,
    project_root: Path,
    assets: list[dict[str, Any]],
) -> dict[str, Any]:
    revision = str(policy.get("intended_initiative_revision") or "")
    initiative_path = str(policy.get("initiative_path") or "").strip("/")
    errors: list[str] = []
    if not _FULL_SHA.fullmatch(revision):
        errors.append("intended_initiative_revision_unpinned")
    elif not _git_commit_exists(project_root, revision):
        errors.append("intended_initiative_revision_missing")
    if not initiative_path:
        errors.append("initiative_path_missing")

    checks: list[dict[str, Any]] = []
    if not errors:
        spec_blob = _revision_blob(project_root, revision, f"{initiative_path}/chain.yaml")
        active_hash = _revision_comparable_spec_sha(spec_path.read_bytes())
        expected_hash = (
            _revision_comparable_spec_sha(spec_blob) if spec_blob is not None else ""
        )
        checks.append(
            {
                "kind": "chain_spec",
                "revision_path": f"{initiative_path}/chain.yaml",
                "expected_sha256": expected_hash,
                "active_sha256": active_hash,
                "matches": bool(expected_hash) and expected_hash == active_hash,
            }
        )
        if not checks[-1]["matches"]:
            errors.append("chain_spec_not_at_intended_revision")

        for asset in assets:
            declared = str(asset.get("declared_path") or "")
            if declared.startswith(".megaplan/"):
                revision_path = declared
            elif str(asset.get("kind")) == "north_star":
                revision_path = f"{initiative_path}/{declared}"
            else:
                revision_path = f"{initiative_path}/{declared}"
            blob = _revision_blob(project_root, revision, revision_path)
            expected = _sha256_bytes(blob) if blob is not None else ""
            active = str(asset.get("sha256") or "")
            check = {
                "kind": asset.get("kind"),
                "revision_path": revision_path,
                "expected_sha256": expected,
                "active_sha256": active,
                "matches": bool(expected) and expected == active,
            }
            checks.append(check)
            if not check["matches"]:
                errors.append(f"asset_not_at_intended_revision:{asset.get('kind')}")

    return {
        "ok": not errors,
        "revision": revision,
        "initiative_path": initiative_path,
        "checks": checks,
        "errors": errors,
    }


def active_execution_identity(spec_path: Path) -> dict[str, Any]:
    spec_path = spec_path.resolve(strict=False)
    raw = _raw_spec(spec_path)
    policy = binding_policy(spec_path)
    project_root = _project_root(spec_path)
    milestones_raw = raw.get("milestones")
    milestones_raw = milestones_raw if isinstance(milestones_raw, list) else []
    milestone_sequence = [
        {
            "index": index,
            "label": str(item.get("label") or "") if isinstance(item, Mapping) else "",
            "idea": str(item.get("idea") or "") if isinstance(item, Mapping) else "",
        }
        for index, item in enumerate(milestones_raw)
    ]
    assets = _bundle_assets(raw, spec_path=spec_path, project_root=project_root)
    bundle_core = {
        "chain_spec_sha256": _sha256_file(spec_path),
        "milestone_sequence": milestone_sequence,
        "assets": assets,
        "intended_initiative_revision": policy["intended_initiative_revision"],
        "initiative_path": policy["initiative_path"],
    }
    bundle_sha256 = _sha256_bytes(
        json.dumps(bundle_core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    runtime = runtime_provenance()
    editable_root_text = str(runtime.get("editable_root") or "")
    editable_root = Path(editable_root_text) if editable_root_text else None
    runtime_identity = {
        "import_root": str(runtime.get("import_root") or ""),
        "source_revision": str(runtime.get("source_revision") or ""),
        "editable_root": editable_root_text,
        "editable_revision": _git_revision(editable_root),
    }
    revision_verification = _revision_verification(
        policy=policy,
        raw=raw,
        spec_path=spec_path,
        project_root=project_root,
        assets=assets,
    )
    errors = list(revision_verification["errors"])
    if any(not bool(asset.get("exists")) for asset in assets):
        errors.append("bundle_asset_missing")
    if not runtime_identity["source_revision"]:
        errors.append("runtime_revision_missing")
    if policy["require_editable_runtime_match"]:
        if not editable_root_text:
            errors.append("editable_runtime_missing")
        elif Path(runtime_identity["import_root"]).resolve(strict=False) != editable_root.resolve(
            strict=False
        ):
            errors.append("editable_runtime_import_root_mismatch")
        elif runtime_identity["editable_revision"] != runtime_identity["source_revision"]:
            errors.append("editable_runtime_revision_mismatch")
    return {
        "schema": BINDING_SCHEMA,
        "spec_path": str(spec_path),
        **bundle_core,
        "bundle_sha256": bundle_sha256,
        "runtime": runtime_identity,
        "revision_verification": revision_verification,
        "ready": not errors,
        "errors": errors,
    }


def _state_has_progress(state: Any) -> bool:
    return bool(
        getattr(state, "current_milestone_index", -1) >= 0
        or getattr(state, "current_plan_name", None)
        or getattr(state, "completed", None)
        or getattr(state, "last_state", None)
    )


def _comparable(identity: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "bundle_sha256": identity.get("bundle_sha256"),
        "chain_spec_sha256": identity.get("chain_spec_sha256"),
        "milestone_sequence": identity.get("milestone_sequence"),
        "assets": identity.get("assets"),
        "intended_initiative_revision": identity.get("intended_initiative_revision"),
        "initiative_path": identity.get("initiative_path"),
        "runtime": identity.get("runtime"),
    }


def execution_binding_report(spec_path: Path, state: Any) -> dict[str, Any]:
    policy = binding_policy(spec_path)
    binding = getattr(state, "metadata", {}).get("execution_binding")
    binding = binding if isinstance(binding, Mapping) else {}
    expected = binding.get("launched_identity")
    expected = expected if isinstance(expected, Mapping) else None
    if not policy["required"] and expected is None:
        return {
            "schema": BINDING_SCHEMA,
            "required": False,
            "status": "not_required",
            "drift_fields": [],
            "expected": None,
            "active": None,
        }
    active = active_execution_identity(spec_path)
    if expected is None:
        status = "missing" if policy["required"] else "not_required"
        drift_fields: list[str] = []
    else:
        expected_comparable = _comparable(expected)
        active_comparable = _comparable(active)
        drift_fields = [
            key
            for key in expected_comparable
            if expected_comparable.get(key) != active_comparable.get(key)
        ]
        status = "drift" if drift_fields or not active.get("ready") else "match"
    return {
        "schema": BINDING_SCHEMA,
        "required": policy["required"],
        "status": status,
        "drift_fields": drift_fields,
        "expected": dict(expected) if expected is not None else None,
        "active": active,
    }


def assert_execution_binding(
    spec_path: Path,
    state: Any,
    *,
    operation: str,
    allow_unbound_new: bool = True,
) -> dict[str, Any]:
    report = execution_binding_report(spec_path, state)
    if not report["required"]:
        return report
    if report["status"] == "missing" and allow_unbound_new and not _state_has_progress(state):
        return report
    if report["status"] != "match":
        active = report["active"]
        raise CliError(
            DRIFT_ERROR,
            f"{operation} refused: immutable chain execution binding is "
            f"{report['status']}; drift_fields={report['drift_fields']}; "
            f"active_errors={active.get('errors')}. Explicit operator-authorized "
            "content-addressed rebind is required.",
        )
    return report


def bind_execution_identity(spec_path: Path, state: Any) -> dict[str, Any]:
    policy = binding_policy(spec_path)
    report = execution_binding_report(spec_path, state)
    if not policy["required"]:
        return report
    if report["status"] != "missing":
        return assert_execution_binding(spec_path, state, operation="chain start")
    if _state_has_progress(state):
        raise CliError(
            DRIFT_ERROR,
            "chain start refused: progressed chain state has no immutable launch binding",
        )
    active = report["active"]
    if not active.get("ready"):
        raise CliError(
            DRIFT_ERROR,
            "chain start refused: execution identity is not launch-ready: "
            + ", ".join(str(item) for item in active.get("errors") or []),
        )
    metadata = dict(getattr(state, "metadata", {}) or {})
    metadata["execution_binding"] = {
        "schema": BINDING_SCHEMA,
        "bound_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "launched_identity": active,
    }
    state.metadata = metadata
    return execution_binding_report(spec_path, state)
