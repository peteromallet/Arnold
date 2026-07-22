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
REBIND_SCHEMA = "arnold.megaplan.chain_execution_rebind.v1"
DRIFT_ERROR = "chain_execution_binding_drift"
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_FULL_SHA256 = re.compile(r"^[0-9a-f]{64}$")


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
    entry = {
        "kind": kind,
        "declared_path": path_value,
        "resolved_path": str(path),
        "sha256": _sha256_file(path) if path.is_file() else "",
        "exists": path.is_file(),
    }
    if path.is_file() and (kind == "north_star" or kind.startswith("milestone_brief:")):
        from arnold_pipelines.megaplan.planning.source_binding import (
            canonical_source_identity,
        )

        entry["semantic_sha256"] = canonical_source_identity(
            path,
            project_dir=project_root,
        )["semantic_sha256"]
    return entry


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


def _comparable_assets(identity: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            key: item.get(key)
            for key in ("kind", "declared_path", "resolved_path", "sha256", "exists")
        }
        for item in identity.get("assets") or []
        if isinstance(item, Mapping)
    ]


def _comparable(identity: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "chain_spec_sha256": identity.get("chain_spec_sha256"),
        "milestone_sequence": identity.get("milestone_sequence"),
        "assets": _comparable_assets(identity),
        "intended_initiative_revision": identity.get("intended_initiative_revision"),
        "initiative_path": identity.get("initiative_path"),
    }


def _future_source_reconciliation_is_safe(
    *,
    state: Any,
    expected: Mapping[str, Any],
    active: Mapping[str, Any],
    drift_fields: list[str],
) -> tuple[bool, list[str]]:
    allowed_fields = {"bundle_sha256", "chain_spec_sha256", "assets", "intended_initiative_revision"}
    if not set(drift_fields).issubset(allowed_fields):
        return False, []
    if expected.get("milestone_sequence") != active.get("milestone_sequence"):
        return False, []
    if expected.get("initiative_path") != active.get("initiative_path"):
        return False, []
    expected_assets = {
        str(item.get("kind")): item
        for item in _comparable_assets(expected)
        if isinstance(item, Mapping)
    }
    active_assets = {
        str(item.get("kind")): item
        for item in _comparable_assets(active)
        if isinstance(item, Mapping)
    }
    changed_kinds = sorted(
        kind
        for kind in set(expected_assets) | set(active_assets)
        if expected_assets.get(kind) != active_assets.get(kind)
    )
    if not changed_kinds:
        return False, []
    cutoff = int(getattr(state, "current_milestone_index", -1))
    if not getattr(state, "current_plan_name", None):
        cutoff -= 1
    for kind in changed_kinds:
        if not kind.startswith("milestone_brief:"):
            return False, changed_kinds
        try:
            index = int(kind.split(":", 1)[1])
        except ValueError:
            return False, changed_kinds
        if index <= cutoff:
            return False, changed_kinds
    revision = active.get("revision_verification")
    if not isinstance(revision, Mapping) or not revision.get("ok"):
        requirements = (getattr(state, "metadata", {}) or {}).get(
            "required_canonical_source_updates"
        )
        if not isinstance(requirements, Mapping):
            return False, changed_kinds
    return True, changed_kinds


def _reconciled_requirements_cover_revision_errors(
    state: Any,
    active: Mapping[str, Any],
) -> bool:
    errors = list(active.get("errors") or [])
    if not errors:
        return True
    requirements = (getattr(state, "metadata", {}) or {}).get(
        "required_canonical_source_updates"
    )
    if not isinstance(requirements, Mapping):
        return False
    active_assets = {
        str(item.get("kind")): item
        for item in active.get("assets") or []
        if isinstance(item, Mapping)
    }
    covered: set[str] = set()
    for requirement in requirements.values():
        if not isinstance(requirement, Mapping) or requirement.get("status") != "reconciled":
            continue
        index = requirement.get("milestone_index")
        expected = requirement.get("expected")
        if not isinstance(index, int) or not isinstance(expected, Mapping):
            continue
        kind = f"milestone_brief:{index}"
        active_asset = active_assets.get(kind) or {}
        if active_asset.get("semantic_sha256") == expected.get("semantic_sha256"):
            covered.add(f"asset_not_at_intended_revision:{kind}")
    return bool(errors) and set(errors).issubset(covered)


def _bound_import_root_covers_editable_metadata_mismatch(
    expected: Mapping[str, Any],
    active: Mapping[str, Any],
) -> bool:
    """Accept unrelated global editable metadata only for the bound import root.

    A shared supervisor interpreter can expose ``direct_url.json`` for another
    editable Arnold checkout even though this process was launched with the
    immutable chain runtime first on ``PYTHONPATH``.  Once a chain is bound, the
    imported source root is the execution fact that must remain invariant.  Do
    not make a later, process-global package metadata observation stronger than
    that bound fact; equally, do not accept a different import root or any
    additional launch-readiness error.
    """

    if set(active.get("errors") or []) != {"editable_runtime_import_root_mismatch"}:
        return False
    expected_runtime = expected.get("runtime")
    active_runtime = active.get("runtime")
    if not isinstance(expected_runtime, Mapping) or not isinstance(active_runtime, Mapping):
        return False
    expected_import = str(expected_runtime.get("import_root") or "").strip()
    expected_editable = str(expected_runtime.get("editable_root") or "").strip()
    active_import = str(active_runtime.get("import_root") or "").strip()
    if not expected_import or not expected_editable or not active_import:
        return False
    return (
        Path(expected_import).resolve(strict=False)
        == Path(expected_editable).resolve(strict=False)
        == Path(active_import).resolve(strict=False)
    )


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
        safe_future, changed_asset_kinds = _future_source_reconciliation_is_safe(
            state=state,
            expected=expected,
            active=active,
            drift_fields=drift_fields,
        )
        bound_import_root_match = _bound_import_root_covers_editable_metadata_mismatch(
            expected,
            active,
        )
        active_ready = (
            bool(active.get("ready"))
            or _reconciled_requirements_cover_revision_errors(state, active)
            or bound_import_root_match
        )
        if safe_future:
            status = "reconcile_required"
        else:
            status = "drift" if drift_fields or not active_ready else "match"
    return {
        "schema": BINDING_SCHEMA,
        "required": policy["required"],
        "status": status,
        "drift_fields": drift_fields,
        "bound_import_root_match": bound_import_root_match if expected is not None else False,
        "changed_asset_kinds": changed_asset_kinds if expected is not None else [],
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
    if report["status"] not in {"match", "reconcile_required"}:
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


def _identity_labels(identity: Mapping[str, Any]) -> list[str]:
    sequence = identity.get("milestone_sequence")
    if not isinstance(sequence, list):
        return []
    labels: list[str] = []
    for expected_index, item in enumerate(sequence):
        if not isinstance(item, Mapping):
            return []
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            return []
        label = str(item.get("label") or "").strip()
        if index != expected_index or not label:
            return []
        labels.append(label)
    return labels if len(set(labels)) == len(labels) else []


def _completed_labels(state: Any) -> list[str]:
    completed = getattr(state, "completed", None)
    if not isinstance(completed, list):
        return []
    labels: list[str] = []
    for item in completed:
        if not isinstance(item, Mapping):
            raise CliError(
                DRIFT_ERROR,
                "chain rebind refused: malformed completed milestone record",
            )
        label = str(item.get("label") or item.get("milestone") or "").strip()
        if not label:
            raise CliError(
                DRIFT_ERROR,
                "chain rebind refused: completed milestone label is missing",
            )
        labels.append(label)
    if len(set(labels)) != len(labels):
        raise CliError(
            DRIFT_ERROR,
            "chain rebind refused: completed milestone labels are ambiguous",
        )
    return labels


def rebind_execution_identity(
    spec_path: Path,
    state: Any,
    *,
    expected_previous_bundle_sha256: str,
    expected_active_bundle_sha256: str,
    expected_current_milestone: str,
    expected_current_plan: str,
    expected_next_milestone: str,
    reason: str,
    actor: str = "operator",
) -> dict[str, Any]:
    """Adopt an explicitly content-addressed successor chain without moving its cursor.

    Rebinding is intentionally narrower than ordinary reconciliation.  The
    operator must name both immutable bundle identities and the exact
    current/next cursor.  Completed and current milestones must be an
    unchanged prefix of both identities; only the future suffix may differ.
    """

    no_current_plan_guard = expected_current_plan == "@none"
    arguments = {
        "expected_previous_bundle_sha256": expected_previous_bundle_sha256,
        "expected_active_bundle_sha256": expected_active_bundle_sha256,
        "expected_current_milestone": expected_current_milestone,
        "expected_current_plan": expected_current_plan,
        "expected_next_milestone": expected_next_milestone,
        "reason": reason,
        "actor": actor,
    }
    if any(not str(value or "").strip() for value in arguments.values()):
        raise CliError(DRIFT_ERROR, "chain rebind refused: every rebind guard is required")
    guarded_current_plan = "" if no_current_plan_guard else expected_current_plan
    if not _FULL_SHA256.fullmatch(expected_previous_bundle_sha256):
        raise CliError(DRIFT_ERROR, "chain rebind refused: previous bundle SHA-256 is invalid")
    if not _FULL_SHA256.fullmatch(expected_active_bundle_sha256):
        raise CliError(DRIFT_ERROR, "chain rebind refused: active bundle SHA-256 is invalid")

    report = execution_binding_report(spec_path, state)
    if not report.get("required"):
        raise CliError(DRIFT_ERROR, "chain rebind refused: execution binding is not required")
    if report.get("status") not in {"drift", "reconcile_required"}:
        raise CliError(
            DRIFT_ERROR,
            f"chain rebind refused: binding status is {report.get('status')!r}, not drift",
        )
    previous = report.get("expected")
    active = report.get("active")
    if not isinstance(previous, Mapping) or not isinstance(active, Mapping):
        raise CliError(DRIFT_ERROR, "chain rebind refused: expected or active identity is missing")
    if previous.get("bundle_sha256") != expected_previous_bundle_sha256:
        raise CliError(
            DRIFT_ERROR,
            "chain rebind refused: previous bundle SHA-256 does not match persisted binding",
        )
    if active.get("bundle_sha256") != expected_active_bundle_sha256:
        raise CliError(
            DRIFT_ERROR,
            "chain rebind refused: active bundle SHA-256 does not match validated source",
        )
    if not active.get("ready"):
        raise CliError(
            DRIFT_ERROR,
            "chain rebind refused: active execution identity is not ready: "
            + ", ".join(str(item) for item in active.get("errors") or []),
        )

    previous_labels = _identity_labels(previous)
    active_labels = _identity_labels(active)
    if not previous_labels or not active_labels:
        raise CliError(
            DRIFT_ERROR,
            "chain rebind refused: milestone sequence is missing, duplicated, or malformed",
        )
    try:
        current_index = int(getattr(state, "current_milestone_index"))
    except (TypeError, ValueError):
        raise CliError(
            DRIFT_ERROR,
            "chain rebind refused: current milestone index is ambiguous",
        ) from None
    if (
        current_index < 0
        or current_index >= len(previous_labels)
        or current_index >= len(active_labels)
    ):
        raise CliError(
            DRIFT_ERROR,
            "chain rebind refused: current milestone index is outside a bound sequence",
        )

    completed_labels = _completed_labels(state)
    if len(completed_labels) != current_index:
        raise CliError(
            DRIFT_ERROR,
            "chain rebind refused: completed prefix does not equal the current cursor",
        )
    if (
        previous_labels[:current_index] != completed_labels
        or active_labels[:current_index] != completed_labels
    ):
        raise CliError(DRIFT_ERROR, "chain rebind refused: completed milestone prefix changed")
    if previous_labels[current_index] != expected_current_milestone:
        raise CliError(
            DRIFT_ERROR,
            "chain rebind refused: persisted current milestone does not match the guard",
        )
    if active_labels[current_index] != expected_current_milestone:
        raise CliError(
            DRIFT_ERROR,
            "chain rebind refused: active source changed the current milestone",
        )
    if str(getattr(state, "current_plan_name", "") or "") != guarded_current_plan:
        raise CliError(DRIFT_ERROR, "chain rebind refused: current plan does not match the guard")
    next_index = current_index + 1
    if next_index >= len(active_labels):
        raise CliError(DRIFT_ERROR, "chain rebind refused: active source has no guarded successor")
    if active_labels[next_index] != expected_next_milestone:
        raise CliError(
            DRIFT_ERROR,
            "chain rebind refused: active next milestone does not match the guard",
        )
    if (
        expected_next_milestone in completed_labels
        or expected_next_milestone == expected_current_milestone
    ):
        raise CliError(
            DRIFT_ERROR,
            "chain rebind refused: guarded successor is already completed or current",
        )

    rebound_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    event_core = {
        "schema": REBIND_SCHEMA,
        "rebound_at": rebound_at,
        "actor": actor,
        "reason": reason,
        "from_bundle_sha256": expected_previous_bundle_sha256,
        "to_bundle_sha256": expected_active_bundle_sha256,
        "current_milestone_index": current_index,
        "current_milestone": expected_current_milestone,
        "current_plan": guarded_current_plan,
        "next_milestone": expected_next_milestone,
        "completed_prefix": completed_labels,
    }
    event = {
        **event_core,
        "content_sha256": _sha256_bytes(
            json.dumps(event_core, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ),
    }
    metadata = dict(getattr(state, "metadata", {}) or {})
    binding = dict(metadata.get("execution_binding") or {})
    events = binding.get("rebind_events")
    events = list(events) if isinstance(events, list) else []
    events.append(event)
    binding.update(
        {
            "schema": BINDING_SCHEMA,
            "launched_identity": dict(active),
            "last_rebound_at": rebound_at,
            "rebind_events": events,
        }
    )
    metadata["execution_binding"] = binding
    state.metadata = metadata
    rebound_report = execution_binding_report(spec_path, state)
    if rebound_report.get("status") != "match":
        raise CliError(
            DRIFT_ERROR,
            "chain rebind refused: rebound identity did not verify as an exact match",
        )
    return {"event": event, "execution_binding": rebound_report}


def expected_worker_launch_values(
    spec_path: Path | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Extract expected worker launch parameters from the active execution identity.

    Returns a dict with *expected_source_ref*, *expected_installed_package_path*,
    and *expected_runtime_revision* when a bound chain execution identity exists.
    Returns empty strings for all fields when no binding is available (e.g. plan-
    level dispatch without a chain spec).

    Model and configured-spec are runtime dispatch choices not stored in the
    binding, so their expected values are always returned empty.
    """
    empty: dict[str, Any] = {
        "expected_source_ref": "",
        "expected_installed_package_path": "",
        "expected_runtime_revision": "",
        "expected_model": None,
        "expected_spec": "",
    }
    if spec_path is None or root is None:
        return empty
    try:
        identity = active_execution_identity(spec_path)
    except Exception:
        return empty
    runtime = identity.get("runtime")
    if not isinstance(runtime, dict):
        return empty
    return {
        "expected_source_ref": str(identity.get("intended_initiative_revision") or ""),
        "expected_installed_package_path": str(runtime.get("import_root") or ""),
        "expected_runtime_revision": str(runtime.get("source_revision") or ""),
        "expected_model": None,
        "expected_spec": "",
    }
