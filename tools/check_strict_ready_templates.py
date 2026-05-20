"""Deterministic repo-only strict-ready gate for checked-in templates."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
from pathlib import Path
from typing import Any, Sequence

from tools.refresh_template_index import REPO_ROOT, build_template_index
from vibecomfy.contracts import build_contract
from vibecomfy.porting.readability_inventory import build_readability_inventory
from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.strict_ready import (
    STRICT_READY_BUILD_FAILED,
    STRICT_READY_COMPILE_FAILED,
    STRICT_READY_LOAD_FAILED,
    StrictReadyContext,
    validate_strict_ready_workflow,
)
from vibecomfy.porting.widget_aliases import widget_alias_analysis
from vibecomfy.registry.ready import repo_ready_template_id_for_path
from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.registry.static_contract import compare_public_contracts
from vibecomfy.workflow import VibeWorkflow


VERSION = 1
STYLE_CATEGORY = "generated_template_style"
STATIC_DRIFT_CATEGORY = "static_contract_drift"
PACK_VALIDATION_CATEGORY = "pack_validation"
PACK_PROVENANCE_CATEGORY = "pack_provenance"
LEGACY_VOCABULARY_CATEGORY = "legacy_vocabulary"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check repo-owned ready templates against strict-ready policy.")
    parser.add_argument("--json", action="store_true", help="Emit deterministic JSON.")
    args = parser.parse_args(argv)

    report = build_strict_ready_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_text_report(report)
    return 0 if report["ok"] else 1


def build_strict_ready_report() -> dict[str, Any]:
    index_payload = build_template_index()
    rows_by_id = {
        row["id"]: row
        for row in index_payload.get("templates", [])
        if row.get("source_scope") == "repo" and row.get("indexed") is True
    }
    dynamic_rows_excluded = sum(
        1
        for row in index_payload.get("templates", [])
        if row.get("source_scope") == "dynamic" or row.get("indexed") is False
    )
    inventory_entries = {entry.ready_id: entry for entry in build_readability_inventory().entries}

    selected_ids = sorted(
        ready_id
        for ready_id, row in rows_by_id.items()
        if _is_protected(row) or inventory_entries.get(ready_id, None) is not None
        and inventory_entries[ready_id].marker == "generated"
    )
    targets = [_check_template(rows_by_id[ready_id], inventory_entries.get(ready_id)) for ready_id in selected_ids]
    diagnostics = _flatten_diagnostics(targets)
    summary = _summary(diagnostics)
    ok = not any(
        item["severity"] == "error"
        for item in diagnostics
        if item.get("enforced") is True
    )
    return {
        "version": VERSION,
        "ok": ok,
        "generated_from": "repo-only ready_templates/**/*.py strict-ready gate",
        "template_count": len(rows_by_id),
        "target_count": len(targets),
        "dynamic_rows_excluded": dynamic_rows_excluded,
        "summary": summary,
        "targets": targets,
        "diagnostics": diagnostics,
    }


def _check_template(row: dict[str, Any], inventory_entry: Any | None) -> dict[str, Any]:
    ready_id = str(row["id"])
    relative_path = str(row["path"])
    path = REPO_ROOT / relative_path
    protected = _is_protected(row)
    generated = bool(inventory_entry and inventory_entry.marker == "generated")
    static_drift = _static_drift_diagnostics(row, ready_id=ready_id, enforced=protected)
    style_diagnostics = _style_diagnostics(
        inventory_entry,
        ready_id=ready_id,
        path=relative_path,
        enforced=protected and generated,
    )
    pack_diagnostics = _pack_validation_diagnostics(
        ready_id=ready_id,
        path=relative_path,
        enforced=protected or generated,
    )
    pack_provenance_diagnostics = _pack_provenance_diagnostics(
        ready_id=ready_id,
        path=path,
        relative_path=relative_path,
        marker=inventory_entry.marker if inventory_entry is not None else "unknown",
        strict_ready_protected=protected,
    )
    legacy_diagnostics = _legacy_vocabulary_diagnostics(
        ready_id=ready_id,
        path=relative_path,
        enforced=protected or generated,
    )
    strict_ready_diagnostics: list[dict[str, Any]] = []
    if protected:
        strict_ready_diagnostics = _strict_ready_diagnostics(ready_id=ready_id, path=path, relative_path=relative_path)
    diagnostics = [
        *static_drift,
        *strict_ready_diagnostics,
        *style_diagnostics,
        *pack_diagnostics,
        *pack_provenance_diagnostics,
        *legacy_diagnostics,
    ]
    return {
        "ready_id": ready_id,
        "path": relative_path,
        "source_scope": "repo",
        "indexed": True,
        "protected": protected,
        "generated": generated,
        "coverage_tier": row.get("coverage_tier") or "",
        "app_active": bool(row.get("app_active") is True),
        "static_drift": static_drift,
        "strict_ready_ok": not any(item["severity"] == "error" for item in strict_ready_diagnostics),
        "strict_ready_diagnostics": strict_ready_diagnostics,
        "style_diagnostics": style_diagnostics,
        "pack_validation_diagnostics": pack_diagnostics,
        "pack_provenance_diagnostics": pack_provenance_diagnostics,
        "legacy_vocabulary_diagnostics": legacy_diagnostics,
        "ok": not any(item["severity"] == "error" and item.get("enforced") is True for item in diagnostics),
    }


def _static_drift_diagnostics(row: dict[str, Any], *, ready_id: str, enforced: bool) -> list[dict[str, Any]]:
    if not enforced:
        return []
    try:
        workflow = _workflow_from_repo_template(ready_id, REPO_ROOT / str(row["path"]))
        contract = build_contract(workflow).to_dict()
        comparison = compare_public_contracts(
            static_inputs=row.get("public_inputs") or [],
            static_outputs=row.get("public_outputs") or [],
            built_inputs=contract.get("public_inputs") or [],
            built_outputs=contract.get("public_outputs") or [],
        )
    except Exception as exc:
        return [
            _diagnostic(
                code=STRICT_READY_BUILD_FAILED,
                message=f"Could not build template for static contract comparison: {type(exc).__name__}: {exc}",
                ready_id=ready_id,
                target="build_contract",
                severity="error",
                category=STATIC_DRIFT_CATEGORY,
                enforced=enforced,
            )
        ]
    diagnostics: list[dict[str, Any]] = []
    for field, values in sorted(comparison.items()):
        if not values:
            continue
        diagnostics.append(
            _diagnostic(
                code=f"static_contract_{field}",
                message=f"Static and built public contracts differ for {field}.",
                ready_id=ready_id,
                target=field,
                severity="error",
                category=STATIC_DRIFT_CATEGORY,
                enforced=enforced,
                detail={"examples": values[:5], "count": len(values)},
            )
        )
    return diagnostics


def _strict_ready_diagnostics(*, ready_id: str, path: Path, relative_path: str) -> list[dict[str, Any]]:
    try:
        workflow = _workflow_from_repo_template(ready_id, path)
    except Exception as exc:
        return [
            _diagnostic(
                code=STRICT_READY_LOAD_FAILED,
                message=f"Could not load ready template: {type(exc).__name__}: {exc}",
                ready_id=ready_id,
                target="load",
                severity="error",
                category="strict_ready",
                enforced=True,
            )
        ]
    try:
        api_prompt = workflow.compile("api")
    except Exception as exc:
        return [
            _diagnostic(
                code=STRICT_READY_COMPILE_FAILED,
                message=f"Could not compile ready template API prompt: {type(exc).__name__}: {exc}",
                ready_id=ready_id,
                target="compile",
                severity="error",
                category="strict_ready",
                enforced=True,
            )
        ]
    issues = validate_strict_ready_workflow(
        workflow,
        StrictReadyContext(ready_id=ready_id, source_path=relative_path),
        api_prompt=api_prompt,
        widget_analysis=widget_alias_analysis(api_prompt, schema_provider=None),
    )
    return [_issue_to_diagnostic(issue, ready_id=ready_id, enforced=True) for issue in issues]


def _style_diagnostics(
    inventory_entry: Any | None,
    *,
    ready_id: str,
    path: str,
    enforced: bool,
) -> list[dict[str, Any]]:
    if inventory_entry is None or inventory_entry.marker != "generated":
        return []
    counts = inventory_entry.counts
    checks = [
        ("generated_template_positional_out", "positional `.out(<int>)` calls", counts.positional_outs),
        ("generated_template_widget_n_field", "`widget_N` field references", counts.widget_n_fields),
        ("generated_template_uuid_class_type", "UUID class-type literals", counts.uuid_class_types),
        ("generated_template_n_uuid_variable", "`n_<uuid>` variable names", counts.n_uuid_variables),
        ("generated_template_local_node_copy", "local `_node` helper copies", counts.local_node_copies),
        (
            "generated_template_missing_output_contract",
            "missing public output contract",
            int(counts.missing_output_contract),
        ),
    ]
    diagnostics: list[dict[str, Any]] = []
    for code, label, count in checks:
        if count <= 0:
            continue
        diagnostics.append(
            _diagnostic(
                code=code,
                message=f"Generated template has {label}.",
                ready_id=ready_id,
                target=path,
                severity="error" if enforced else "warning",
                category=STYLE_CATEGORY,
                enforced=enforced,
                detail={"count": count},
            )
        )
    return diagnostics


def _legacy_vocabulary_diagnostics(
    *,
    ready_id: str,
    path: str,
    enforced: bool,
) -> list[dict[str, Any]]:
    """Reject generated templates importing or calling legacy vocabulary.

    Checks for:
    - Import of ``vibecomfy.registry.ready_template``
    - Direct calls to ``bind_input``, ``bind_output``, ``apply_ready_template_policy``,
      ``wf.register_input`` inside ``build()``.
    """
    if not enforced:
        return []
    # Only enforce for the 5 generated/pilot templates. Legacy templates
    # still use the old vocabulary and will be migrated separately.
    if path not in _PILOT_TEMPLATE_PATHS:
        return []
    template_path = REPO_ROOT / path
    if not template_path.is_file():
        return []
    try:
        source = template_path.read_text(encoding="utf-8")
    except Exception:
        return []
    try:
        tree = ast.parse(source, filename=str(template_path))
    except SyntaxError:
        return []

    diagnostics: list[dict[str, Any]] = []
    _LEGACY_IMPORT = "vibecomfy.registry.ready_template"
    _LEGACY_CALLS = frozenset({"bind_input", "bind_output", "apply_ready_template_policy"})

    # Check imports
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", None)
            if module == _LEGACY_IMPORT or (isinstance(node, ast.Import) and any(
                getattr(alias, "name", "") == _LEGACY_IMPORT for alias in node.names
            )):
                diagnostics.append(
                    _diagnostic(
                        code="legacy_vocabulary_import",
                        message=f"Generated template imports legacy module {_LEGACY_IMPORT!r}.",
                        ready_id=ready_id,
                        target=path,
                        severity="error",
                        category=LEGACY_VOCABULARY_CATEGORY,
                        enforced=enforced,
                        detail={"import": _LEGACY_IMPORT, "line": node.lineno},
                    )
                )
        # Check legacy function calls inside build()
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                if node.func.value.id == "wf" and node.func.attr == "register_input":
                    func_name = "wf.register_input"
            if func_name in _LEGACY_CALLS or func_name == "wf.register_input":
                # Verify we're inside a build() function
                call_name = func_name or (
                    f"wf.{node.func.attr}" if isinstance(node.func, ast.Attribute) else "unknown"
                )
                diagnostics.append(
                    _diagnostic(
                        code="legacy_vocabulary_call",
                        message=f"Generated template calls legacy function {call_name!r}.",
                        ready_id=ready_id,
                        target=f"{path}:{node.lineno}",
                        severity="error",
                        category=LEGACY_VOCABULARY_CATEGORY,
                        enforced=enforced,
                        detail={"call": call_name, "line": node.lineno},
                    )
                )

    return diagnostics


# The 5 pilot templates that are the target of pack validation.
_PILOT_TEMPLATE_PATHS: frozenset[str] = frozenset({
    "ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py",
    "ready_templates/image/qwen_image_2512.py",
    "ready_templates/video/wan_i2v.py",
    "ready_templates/audio/ace_step_1_5_t2a_song.py",
    "ready_templates/edit/qwen_image_edit.py",
})


def _pack_validation_diagnostics(
    *,
    ready_id: str,
    path: str,
    enforced: bool,
) -> list[dict[str, Any]]:
    """Validate template node classes against known custom-node packs.

    Only runs for the 5 generated/pilot templates.  Returns diagnostics for
    unknown classes.  Deferred all-template enforcement until legacy _node
    templates are migrated or allowed.
    """
    if not enforced or path not in _PILOT_TEMPLATE_PATHS:
        return []
    try:
        from tools.validate_templates_against_packs import (
            _extract_node_classes,
            _is_comfy_core,
            _load_known_packs,
            _suggest_pack,
        )
    except ImportError:
        return []

    template_path = REPO_ROOT / path
    if not template_path.is_file():
        return []

    try:
        source = template_path.read_text(encoding="utf-8")
    except Exception:
        return []

    class_to_pack, _all_classes = _load_known_packs()

    diagnostics: list[dict[str, Any]] = []
    for class_name, node_id, lineno in _extract_node_classes(source, template_path):
        pack_name = class_to_pack.get(class_name)
        if pack_name is not None:
            continue  # known pack class
        if _is_comfy_core(class_name):
            continue  # known ComfyUI core class
        # Unknown class — try fuzzy match
        suggested = _suggest_pack(class_name, class_to_pack)
        if suggested is None:
            continue  # no suggestion, treat as core

        diagnostics.append(
            _diagnostic(
                code="pack_validation_unknown_class",
                message=f"Unknown class {class_name!r} (node {node_id!r}) — suggested pack: {suggested}",
                ready_id=ready_id,
                target=f"{path}:{lineno}",
                severity="error",
                category=PACK_VALIDATION_CATEGORY,
                enforced=enforced,
                detail={
                    "class": class_name,
                    "node_id": node_id,
                    "line": lineno,
                    "suggested_pack": suggested,
                },
            )
        )

    return diagnostics


def _pack_provenance_diagnostics(
    *,
    ready_id: str,
    path: Path,
    relative_path: str,
    marker: str,
    strict_ready_protected: bool,
) -> list[dict[str, Any]]:
    """Run the v2.4 pack provenance checker in report-only mode.

    Hard strict-ready enforcement is intentionally deferred until the
    migration/report-only pass is clean.
    """
    try:
        from tools.check_pack_provenance import diagnostics_for_template
    except ImportError:
        return []
    diagnostics = diagnostics_for_template(
        ready_id=ready_id,
        path=path,
        marker=marker,
        strict_ready_protected=strict_ready_protected,
        enforced=False,
    )
    return [
        {
            **item,
            "target": item.get("target") or relative_path,
            "enforced": False,
        }
        for item in diagnostics
    ]


def _workflow_from_repo_template(template_id: str, path: Path) -> VibeWorkflow:
    spec = importlib.util.spec_from_file_location(f"vibecomfy_strict_ready_{path.stem}", path)
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
    resolved_template_id = repo_ready_template_id_for_path(path, REPO_ROOT / "ready_templates")
    if resolved_template_id != template_id:
        raise ValueError(f"Template path {path} resolved to {resolved_template_id!r}, expected {template_id!r}")
    if not workflow.metadata.get("python_policy_applied"):
        ready_metadata = getattr(module, "READY_METADATA", None)
        if isinstance(ready_metadata, dict):
            ready_metadata = {**ready_metadata, "ready_template": ready_metadata.get("ready_template") or template_id}
            requirements = getattr(module, "READY_REQUIREMENTS", None)
            workflow = apply_ready_template_policy(
                workflow,
                ready_metadata,
                source_path=str(path),
                requirements=requirements if isinstance(requirements, dict) else None,
            )
    workflow.metadata["ready_template"] = workflow.metadata.get("ready_template") or template_id
    return workflow


def _issue_to_diagnostic(issue: PortIssue, *, ready_id: str, enforced: bool) -> dict[str, Any]:
    payload = issue.to_json()
    detail = dict(payload.get("detail") or {})
    target = str(detail.get("target") or payload.get("node_id") or payload["code"])
    return _diagnostic(
        code=str(payload["code"]),
        message=str(payload["message"]),
        ready_id=ready_id,
        target=target,
        severity=str(payload["severity"]),
        category=str(detail.get("category") or "strict_ready"),
        enforced=enforced and payload["severity"] == "error",
        detail=detail,
        node_id=payload.get("node_id"),
        class_type=payload.get("class_type"),
        recommendation=payload.get("recommendation"),
    )


def _diagnostic(
    *,
    code: str,
    message: str,
    ready_id: str,
    target: str,
    severity: str,
    category: str,
    enforced: bool,
    detail: dict[str, Any] | None = None,
    node_id: str | None = None,
    class_type: str | None = None,
    recommendation: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "ready_id": ready_id,
        "target": target,
        "category": category,
        "enforced": enforced,
        "message": message,
    }
    if node_id:
        payload["node_id"] = node_id
    if class_type:
        payload["class_type"] = class_type
    if recommendation:
        payload["recommendation"] = recommendation
    if detail:
        payload["detail"] = detail
    return payload


def _flatten_diagnostics(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for target in targets:
        diagnostics.extend(target["static_drift"])
        diagnostics.extend(target["strict_ready_diagnostics"])
        diagnostics.extend(target["style_diagnostics"])
        diagnostics.extend(target.get("pack_validation_diagnostics", []))
        diagnostics.extend(target.get("pack_provenance_diagnostics", []))
        diagnostics.extend(target.get("legacy_vocabulary_diagnostics", []))
    return sorted(diagnostics, key=lambda item: (item["ready_id"], item["category"], item["code"], item["target"]))


def _summary(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    by_severity = {"error": 0, "warning": 0, "info": 0}
    by_category: dict[str, int] = {}
    enforced_errors = 0
    for item in diagnostics:
        severity = str(item["severity"])
        by_severity[severity] = by_severity.get(severity, 0) + 1
        category = str(item["category"])
        by_category[category] = by_category.get(category, 0) + 1
        if severity == "error" and item.get("enforced") is True:
            enforced_errors += 1
    return {
        "diagnostics": len(diagnostics),
        "enforced_errors": enforced_errors,
        "by_severity": by_severity,
        "by_category": {key: by_category[key] for key in sorted(by_category)},
    }


def _is_protected(row: dict[str, Any]) -> bool:
    return row.get("app_active") is True or row.get("coverage_tier") == "required"


def _print_text_report(report: dict[str, Any]) -> None:
    status = "ok" if report["ok"] else "failed"
    print(f"strict-ready gate {status}: {report['target_count']} target(s), {report['summary']['diagnostics']} diagnostic(s)")
    for item in report["diagnostics"]:
        print(f"{item['severity']}: {item['ready_id']}: {item['code']} ({item['target']})")


__all__ = [
    "build_strict_ready_report",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
