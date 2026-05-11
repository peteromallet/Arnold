from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vibecomfy.cli_loader import _ready_id_for
from vibecomfy.commands._workflow_path import resolve_workflow_path
from vibecomfy.ingest.loader import load_workflow_json
from vibecomfy.ingest.normalize import convert_to_vibe_format, detect_workflow_shape, normalize_to_api
from vibecomfy.metadata import OUTPUT_NODE_NAMES
from vibecomfy.node_packs import resolve_node_packs, unresolved_class_types
from vibecomfy.porting.assets import analyze_model_assets
from vibecomfy.porting.report import NodePackSuggestion, PortIssue, PortReport
from vibecomfy.porting.widget_aliases import widget_alias_analysis, widget_names_for_class
from vibecomfy.registry.ready import workflow_from_ready
from vibecomfy.scratchpad_loader import load_scratchpad
from vibecomfy.schema import schema_for, schema_registry_empty
from vibecomfy.workflow import ValidationIssue, VibeWorkflow


_OPAQUE_COMPONENT_CLASS_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

_KNOWN_RUNTIME_REQUIRED_INPUTS: dict[str, frozenset[str]] = {
    # VideoHelperSuite validates these at Comfy queue time. Keep this local
    # contract so port checks fail even when object_info/node_index is missing.
    "VHS_VideoCombine": frozenset(
        {
            "filename_prefix",
            "format",
            "frame_rate",
            "images",
            "loop_count",
            "pingpong",
            "save_output",
        }
    ),
}

_KNOWN_DYNAMIC_COMBO_SELECTORS: dict[str, frozenset[str]] = {
    "LTXVImgToVideoInplaceKJ": frozenset({"num_images"}),
    "LTXVAddGuideMulti": frozenset({"num_guides"}),
}


@dataclass(slots=True)
class LoadedPortSource:
    source_ref: str
    source_kind: str
    workflow: VibeWorkflow
    raw_workflow: dict[str, Any] | None = None
    source_path: str | None = None
    indexed_id: str | None = None
    source_hash: str | None = None


def analyze_source(
    source: str,
    *,
    schema_provider: Any | None = None,
    head_check_models: bool = False,
    head_client: Any | None = None,
) -> PortReport:
    loaded = load_port_source(source, schema_provider=schema_provider)
    workflow = loaded.workflow

    api_prompt: dict[str, Any] | None = None
    compile_issue: PortIssue | None = None
    try:
        api_prompt = workflow.compile("api")
    except Exception as exc:
        compile_issue = PortIssue(
            code="api_compile_failed",
            message=f"API compile failed: {type(exc).__name__}: {exc}",
            severity="error",
            detail={"source": source},
            recommendation="Fix graph structure before running validation or conversion.",
        )

    report = PortReport(
        source=source,
        provenance=_provenance(loaded),
        source_hash=loaded.source_hash,
        workflow_id=workflow.id,
        workflow_shape=_workflow_shape(workflow),
        node_counts=dict(sorted(Counter(node.class_type for node in workflow.nodes.values()).items())),
        output_mode="analysis",
        recommendations=_recommendations(source, loaded),
        metadata={
            "source_kind": loaded.source_kind,
            "source_path": loaded.source_path,
            "runtime_class_types": workflow.runtime_class_types(),
        },
    )

    for issue in workflow.helper_diagnostics():
        report.diagnostics.append(_port_issue_from_validation(issue, category="helper"))

    report.diagnostics.extend(_materialization_diagnostics(workflow))
    report.diagnostics.extend(_save_output_mapping_diagnostics(workflow, source_kind=loaded.source_kind))

    custom_node_analysis = _custom_node_analysis(workflow, schema_provider=schema_provider)
    report.metadata["custom_node_analysis"] = custom_node_analysis
    report.node_pack_suggestions.extend(custom_node_analysis["suggestions"])
    report.diagnostics.extend(custom_node_analysis["diagnostics"])

    if compile_issue is not None:
        report.diagnostics.append(compile_issue)
    report.diagnostics.extend(_known_runtime_required_input_diagnostics(api_prompt))
    report.diagnostics.extend(_known_dynamic_combo_selector_diagnostics(api_prompt))

    asset_analysis = analyze_model_assets(
        raw_workflow=loaded.raw_workflow,
        api_prompt=api_prompt,
        scratchpad_path=loaded.source_path if loaded.source_kind == "scratchpad" and loaded.source_path else None,
        ready_metadata=workflow.metadata,
        ready_requirements={
            "models": workflow.metadata.get("model_assets", workflow.requirements.models),
            "custom_nodes": workflow.requirements.custom_nodes,
        },
        head_check=head_check_models,
        head_client=head_client,
    )
    report.asset_candidates.extend(asset_analysis.candidates)
    report.asset_checks.extend(asset_analysis.checks)
    report.diagnostics.extend(asset_analysis.diagnostics)

    widget_analysis = _widget_analysis(api_prompt, raw_workflow=loaded.raw_workflow, schema_provider=schema_provider)
    report.metadata["widget_analysis"] = widget_analysis
    for alias in widget_analysis["unresolved_widget_aliases"]:
        report.diagnostics.append(
            PortIssue(
                code="widget_alias_unresolved",
                message=f"Input {alias['input']!r} on node {alias['node_id']} remains positional.",
                severity="warning",
                node_id=alias["node_id"],
                class_type=alias["class_type"],
                detail=alias,
                recommendation="Compare against object_info/widget schema before materializing a ready template.",
            )
        )
    for missing in widget_analysis["missing_compiled_widget_inputs"]:
        report.diagnostics.append(
            PortIssue(
                code="compiled_widget_input_missing",
                message=(
                    f"Node {missing['node_id']} ({missing['class_type']}) has positional widget "
                    f"{missing['widget_key']} but compiled API is missing required input {missing['expected_input']!r}."
                ),
                severity="error",
                node_id=missing["node_id"],
                class_type=missing["class_type"],
                detail=missing,
                recommendation="Add the class to compile-time widget aliasing or update the widget schema before RunPod validation.",
            )
        )

    validation_report = workflow.validate(schema_provider=schema_provider) if schema_provider is not None else workflow.validate()
    report.metadata["schema_validation"] = {
        "schema_provider": schema_provider is not None,
        "ok": validation_report.ok,
        "issue_count": len(validation_report.issues),
    }
    for issue in validation_report.issues:
        report.diagnostics.append(_port_issue_from_validation(issue, category="schema"))

    if report.asset_candidates:
        report.recommendations.append(f"Review model assets before RunPod validation; use `vibecomfy fetch {source} --dry-run` for URL-backed assets.")
    if any(issue.severity == "error" for issue in report.diagnostics):
        report.recommendations.append("Resolve error diagnostics before spending RunPod GPU time.")

    return report


def _materialization_diagnostics(workflow: VibeWorkflow) -> list[PortIssue]:
    issues: list[PortIssue] = []
    for node in workflow.nodes.values():
        class_type = str(node.class_type)
        if class_type == "None":
            issues.append(
                PortIssue(
                    code="unmaterialized_node_class",
                    message=(
                        f"Node {node.id} has class_type 'None'; the workflow was converted without a real "
                        "runtime node class for this operation."
                    ),
                    severity="error",
                    node_id=node.id,
                    class_type=class_type,
                    detail={"category": "materialization"},
                    recommendation=(
                        "Re-export with all custom/core nodes available, or replace this source with a fully "
                        "materialized API workflow before conversion or RunPod validation."
                    ),
                )
            )
        elif _OPAQUE_COMPONENT_CLASS_RE.match(class_type):
            issues.append(
                PortIssue(
                    code="opaque_component_node_class",
                    message=(
                        f"Node {node.id} uses opaque component class {class_type!r}; headless API execution "
                        "will not know this class unless the component is inlined."
                    ),
                    severity="error",
                    node_id=node.id,
                    class_type=class_type,
                    detail={"category": "materialization"},
                    recommendation=(
                        "Inline component/subgraph definitions with graphbuilder or ComfyUI's converter before "
                        "materializing a ready template."
                    ),
                )
            )
    return issues


def _known_runtime_required_input_diagnostics(api_prompt: dict[str, Any] | None) -> list[PortIssue]:
    if api_prompt is None:
        return []

    issues: list[PortIssue] = []
    for node_id, node in sorted(api_prompt.items(), key=lambda item: _sort_key(item[0])):
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type") or "")
        required_inputs = _KNOWN_RUNTIME_REQUIRED_INPUTS.get(class_type)
        if not required_inputs:
            continue
        inputs = node.get("inputs")
        provided = set(inputs) if isinstance(inputs, dict) else set()
        for input_name in sorted(required_inputs - provided):
            issues.append(
                PortIssue(
                    code="known_runtime_required_input_missing",
                    message=(
                        f"Node {node_id} ({class_type}) is missing runtime-required input "
                        f"{input_name!r}; Comfy will reject this prompt at queue time."
                    ),
                    severity="error",
                    node_id=str(node_id),
                    class_type=class_type,
                    detail={
                        "category": "runtime_contract",
                        "input": input_name,
                        "source": "committed_runtime_required_inputs",
                    },
                    recommendation="Materialize the input explicitly in the Python workflow before RunPod validation.",
                )
            )
    return issues


def _known_dynamic_combo_selector_diagnostics(api_prompt: dict[str, Any] | None) -> list[PortIssue]:
    if api_prompt is None:
        return []

    issues: list[PortIssue] = []
    for node_id, node in sorted(api_prompt.items(), key=lambda item: _sort_key(item[0])):
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type") or "")
        selectors = _KNOWN_DYNAMIC_COMBO_SELECTORS.get(class_type)
        if not selectors:
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            inputs = {}
        for selector in sorted(selectors):
            dotted_inputs = sorted(name for name in inputs if name.startswith(f"{selector}."))
            if not dotted_inputs or selector in inputs:
                continue
            issues.append(
                PortIssue(
                    code="dynamic_combo_selector_missing",
                    message=(
                        f"Node {node_id} ({class_type}) has dynamic inputs for {selector!r} "
                        "but is missing the selector input; Comfy will pass flat dotted inputs at execution."
                    ),
                    severity="error",
                    node_id=str(node_id),
                    class_type=class_type,
                    detail={
                        "category": "runtime_contract",
                        "selector": selector,
                        "dotted_inputs": dotted_inputs,
                        "source": "committed_dynamic_combo_contract",
                    },
                    recommendation=(
                        f"Materialize {selector!r} with the selected option count alongside the "
                        f"{selector}.* dynamic inputs."
                    ),
                )
            )
    return issues


def _save_output_mapping_diagnostics(workflow: VibeWorkflow, *, source_kind: str) -> list[PortIssue]:
    if source_kind not in {"ready", "scratchpad"}:
        return []
    output_directory = _configured_output_directory(workflow)
    if output_directory is None:
        return []

    output_root = Path(output_directory).expanduser().resolve()
    issues: list[PortIssue] = []
    for node in workflow.runtime_nodes().values():
        if node.class_type not in OUTPUT_NODE_NAMES:
            continue
        values = {**node.widgets, **node.inputs}
        prefix = values.get("filename_prefix", values.get("widget_0"))
        if isinstance(prefix, str):
            issue = _save_prefix_mapping_issue(node.id, node.class_type, prefix, output_root)
            if issue is not None:
                issues.append(issue)
        for field in ("output_directory", "output_dir", "output_path", "save_path", "folder", "folder_path"):
            value = values.get(field)
            if isinstance(value, str):
                issue = _absolute_save_path_mapping_issue(node.id, node.class_type, field, value, output_root)
                if issue is not None:
                    issues.append(issue)
    return issues


def _save_prefix_mapping_issue(
    node_id: str,
    class_type: str,
    prefix: str,
    output_root: Path,
) -> PortIssue | None:
    path = Path(prefix).expanduser()
    if not path.is_absolute() and ".." not in path.parts:
        return None
    candidate = path if path.is_absolute() else output_root / path
    if _is_relative_to(candidate.resolve(), output_root):
        return None
    return PortIssue(
        code="save_output_path_outside_output_directory",
        message=(
            f"Save node {node_id} uses filename_prefix {prefix!r}, which resolves outside configured "
            f"output_directory {str(output_root)!r}."
        ),
        severity="warning",
        node_id=node_id,
        class_type=class_type,
        detail={
            "category": "outputs",
            "field": "filename_prefix",
            "value": prefix,
            "output_directory": str(output_root),
        },
        recommendation="Use a relative filename_prefix under output_directory so run metadata can map Comfy outputs to artifacts.",
    )


def _absolute_save_path_mapping_issue(
    node_id: str,
    class_type: str,
    field: str,
    value: str,
    output_root: Path,
) -> PortIssue | None:
    path = Path(value).expanduser()
    if not path.is_absolute():
        return None
    if _is_relative_to(path.resolve(), output_root):
        return None
    return PortIssue(
        code="save_output_path_outside_output_directory",
        message=(
            f"Save node {node_id} sets {field}={value!r}, which is outside configured "
            f"output_directory {str(output_root)!r}."
        ),
        severity="warning",
        node_id=node_id,
        class_type=class_type,
        detail={
            "category": "outputs",
            "field": field,
            "value": value,
            "output_directory": str(output_root),
        },
        recommendation="Save artifacts under the configured output_directory or mirror that path in comfy_configuration.",
    )


def _configured_output_directory(workflow: VibeWorkflow) -> str | None:
    values: dict[str, Any] = {}
    metadata_config = workflow.metadata.get("comfy_configuration")
    if isinstance(metadata_config, dict):
        values.update(metadata_config)
    env_config = os.environ.get("VIBECOMFY_COMFY_CONFIGURATION")
    if env_config:
        try:
            parsed = json.loads(env_config)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            values.update(parsed)
    output_directory = values.get("output_directory")
    return str(output_directory) if output_directory else None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def load_port_source(source: str, *, schema_provider: Any | None = None) -> LoadedPortSource:
    ready_id = _ready_id_for(source)
    if ready_id is not None:
        workflow = workflow_from_ready(ready_id)
        path = workflow.source.path
        return LoadedPortSource(
            source_ref=source,
            source_kind="ready",
            workflow=workflow,
            source_path=path,
            indexed_id=ready_id,
            source_hash=_hash_file(path) if path else None,
        )

    source_path = Path(source)
    if source_path.is_file() and source_path.suffix.lower() == ".py":
        workflow = load_scratchpad(source_path)
        return LoadedPortSource(
            source_ref=source,
            source_kind="scratchpad",
            workflow=workflow,
            source_path=str(source_path),
            source_hash=_hash_file(source_path),
        )

    resolved_path: str | None = None
    indexed_id: str | None = None
    try:
        resolved_path = resolve_workflow_path(source)
        if source != resolved_path:
            indexed_id = source
    except FileNotFoundError:
        if source_path.is_file():
            resolved_path = str(source_path)
        else:
            raise

    resolved = Path(resolved_path)
    if resolved.suffix.lower() == ".py":
        workflow = load_scratchpad(resolved)
        return LoadedPortSource(
            source_ref=source,
            source_kind="scratchpad",
            workflow=workflow,
            source_path=str(resolved),
            indexed_id=indexed_id,
            source_hash=_hash_file(resolved),
        )
    if resolved.suffix.lower() != ".json":
        raise FileNotFoundError(source)

    raw = load_workflow_json(resolved)
    api = normalize_to_api(raw, schema_provider=schema_provider)
    workflow = convert_to_vibe_format(
        api,
        source_path=str(resolved),
        workflow_id=indexed_id or resolved.stem,
        schema_provider=schema_provider,
    )
    return LoadedPortSource(
        source_ref=source,
        source_kind="indexed_json" if indexed_id else "raw_json",
        workflow=workflow,
        raw_workflow=raw,
        source_path=str(resolved),
        indexed_id=indexed_id,
        source_hash=_hash_file(resolved),
    )


def _provenance(loaded: LoadedPortSource) -> dict[str, Any]:
    provenance = dict(loaded.workflow.source.provenance)
    provenance.update(
        {
            "source_ref": loaded.source_ref,
            "source_kind": loaded.source_kind,
            "source_path": loaded.source_path,
            "indexed_id": loaded.indexed_id,
            "workflow_source_id": loaded.workflow.source.id,
            "workflow_source_type": loaded.workflow.source.source_type,
        }
    )
    if loaded.raw_workflow is not None:
        provenance["raw_workflow_shape"] = detect_workflow_shape(loaded.raw_workflow)
    return provenance


def _workflow_shape(workflow: VibeWorkflow) -> dict[str, Any]:
    runtime_nodes = workflow.runtime_nodes()
    return {
        "nodes": len(workflow.nodes),
        "runtime_nodes": len(runtime_nodes),
        "helper_nodes": len(workflow.nodes) - len(runtime_nodes),
        "edges": len(workflow.edges),
        "inputs": len(workflow.inputs),
        "outputs": len(workflow.outputs),
    }


def _recommendations(source: str, loaded: LoadedPortSource) -> list[str]:
    return [
        f"Run `vibecomfy validate {source}` after port fixes.",
        f"Run `vibecomfy nodes install-plan {source}` before installing custom nodes.",
        f"Use `vibecomfy port convert {source} --out out/scratchpads/<name>.py` for Python scratchpad materialization.",
    ]


def _port_issue_from_validation(issue: ValidationIssue, *, category: str) -> PortIssue:
    detail = dict(issue.detail)
    node_id = detail.pop("node_id", None)
    class_type = detail.pop("class_type", None)
    return PortIssue(
        code=issue.code,
        message=issue.message,
        severity=issue.severity if issue.severity in {"error", "warning", "info"} else "warning",
        node_id=node_id,
        class_type=class_type,
        detail={"category": category, **detail},
    )


def _custom_node_analysis(workflow: VibeWorkflow, *, schema_provider: Any | None) -> dict[str, Any]:
    runtime_class_types = set(workflow.runtime_class_types())
    helper_class_types_excluded = sorted(
        {node.class_type for node in workflow.nodes.values() if node.id not in workflow.runtime_nodes()}
    )
    if schema_provider is None or schema_registry_empty(schema_provider):
        missing = {class_type for class_type in runtime_class_types if _class_in_known_pack(class_type)}
        unresolved: list[str] = []
        status = "schema_provider_unavailable" if schema_provider is None else "schema_provider_empty"
    else:
        missing = {class_type for class_type in runtime_class_types if schema_for(schema_provider, class_type) is None}
        unresolved = unresolved_class_types(missing)
        status = "analyzed"

    packs = resolve_node_packs(missing)
    suggestions = [
        NodePackSuggestion(
            pack_name=pack.name,
            repo=pack.repo,
            matched_classes=sorted(missing & pack.classes),
            missing_classes=sorted(missing & pack.classes),
            pip_packages=list(pack.pip_packages),
        )
        for pack in packs
    ]
    diagnostics = [
        PortIssue(
            code="unresolved_runtime_class",
            message=f"Runtime class {class_type!r} is not present in schema data and no known node pack maps it.",
            severity="error",
            class_type=class_type,
            detail={"category": "custom_nodes", "runtime_class_type": class_type},
            recommendation="Add this class to node-pack metadata or install/update object_info before RunPod validation.",
        )
        for class_type in unresolved
    ]
    return {
        "status": status,
        "runtime_class_types": sorted(runtime_class_types),
        "helper_class_types_excluded": helper_class_types_excluded,
        "missing_runtime_class_types": sorted(missing),
        "unresolved_runtime_class_types": unresolved,
        "suggestions": suggestions,
        "diagnostics": diagnostics,
    }


def _class_in_known_pack(class_type: str) -> bool:
    return bool(resolve_node_packs({class_type}))


def _widget_analysis(
    api_prompt: dict[str, Any] | None,
    *,
    raw_workflow: dict[str, Any] | None,
    schema_provider: Any | None,
) -> dict[str, Any]:
    analysis = widget_alias_analysis(api_prompt, raw_workflow=raw_workflow, schema_provider=schema_provider)
    analysis["missing_compiled_widget_inputs"] = _missing_compiled_widget_inputs(
        api_prompt,
        schema_provider=schema_provider,
    )
    return analysis


def _missing_compiled_widget_inputs(
    api_prompt: dict[str, Any] | None,
    *,
    schema_provider: Any | None,
) -> list[dict[str, Any]]:
    if api_prompt is None:
        return []

    missing: list[dict[str, Any]] = []
    for node_id, node in sorted(api_prompt.items(), key=lambda item: _sort_key(item[0])):
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type") or "")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        names = widget_names_for_class(class_type)
        if not names:
            continue
        required_inputs = _required_schema_inputs(schema_provider, class_type)
        for index, expected in enumerate(names):
            if expected is None or expected.startswith("unused_"):
                continue
            widget_key = f"widget_{index}"
            if widget_key not in inputs or expected in inputs:
                continue
            if required_inputs is None and not _class_in_known_pack(class_type):
                continue
            if required_inputs is not None and expected not in required_inputs:
                continue
            missing.append(
                {
                    "node_id": str(node_id),
                    "class_type": class_type,
                    "widget_key": widget_key,
                    "expected_input": expected,
                    "widget_value": inputs[widget_key],
                    "schema_required": required_inputs is not None,
                }
            )
    return missing


def _required_schema_inputs(schema_provider: Any | None, class_type: str) -> set[str] | None:
    schema = schema_for(schema_provider, class_type)
    if schema is None:
        return None
    inputs = getattr(schema, "inputs", None)
    if not isinstance(inputs, dict):
        return None
    required: set[str] = set()
    for name, spec in inputs.items():
        if bool(getattr(spec, "required", False)):
            required.add(str(name))
    return required


def _sort_key(value: Any) -> tuple[int, str]:
    try:
        return (int(value), str(value))
    except (TypeError, ValueError):
        return (10**12, str(value))


def _hash_file(path: str | Path) -> str | None:
    try:
        return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


__all__ = ["LoadedPortSource", "analyze_source", "load_port_source"]
