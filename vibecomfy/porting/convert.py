from __future__ import annotations

import importlib.util
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from vibecomfy.porting.emitter import emit_ready_template_python, emit_scratchpad_python
from vibecomfy.workflow import ValidationIssue, ValidationReport, VibeWorkflow


PortConvertMode = Literal["scratchpad", "ready_template"]


@dataclass(slots=True)
class PortConvertValidation:
    ok: bool
    import_ok: bool = False
    build_ok: bool = False
    compile_ok: bool = False
    schema_ok: bool | None = None
    issues: list[ValidationIssue] = field(default_factory=list)
    api_node_count: int = 0
    error: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "import_ok": self.import_ok,
            "build_ok": self.build_ok,
            "compile_ok": self.compile_ok,
            "schema_ok": self.schema_ok,
            "issues": [asdict(issue) for issue in self.issues],
            "api_node_count": self.api_node_count,
            "error": self.error,
        }


@dataclass(slots=True)
class PortConvertResult:
    mode: PortConvertMode
    text: str
    ready_id: str | None = None
    validation: PortConvertValidation | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "ready_id": self.ready_id,
            "validation": self.validation.to_json() if self.validation is not None else None,
        }


def port_convert_workflow(
    workflow: VibeWorkflow,
    *,
    ready_id: str | None = None,
    source_path: str | None = None,
    provenance: dict[str, Any] | None = None,
    source_hash: str | None = None,
    workflow_shape: dict[str, Any] | None = None,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    schema_provider: Any | None = None,
    validate: bool = True,
) -> PortConvertResult:
    if ready_id is None:
        complete_provenance = _conversion_provenance(
            workflow,
            source_path=source_path,
            provenance=provenance,
            source_hash=source_hash,
            workflow_shape=workflow_shape,
            output_mode="scratchpad",
            ready_id=None,
        )
        text = emit_scratchpad_python(
            workflow,
            workflow_id=workflow.id,
            source_path=source_path,
            provenance=complete_provenance,
            registered_inputs=registered_inputs,
        )
        mode: PortConvertMode = "scratchpad"
    else:
        _validate_ready_id(ready_id)
        complete_provenance = _conversion_provenance(
            workflow,
            source_path=source_path,
            provenance=provenance,
            source_hash=source_hash,
            workflow_shape=workflow_shape,
            output_mode="ready_template",
            ready_id=ready_id,
        )
        text = emit_ready_template_python(
            workflow,
            ready_metadata=_ready_metadata(workflow, ready_id=ready_id, source_path=source_path, provenance=complete_provenance),
            ready_requirements=_ready_requirements(workflow),
            template_id=ready_id,
            registered_inputs=registered_inputs,
        )
        mode = "ready_template"

    result = PortConvertResult(mode=mode, text=text, ready_id=ready_id)
    if validate:
        result.validation = validate_emitted_module(text, schema_provider=schema_provider)
    return result


def validate_emitted_module(text: str, *, schema_provider: Any | None = None) -> PortConvertValidation:
    with tempfile.TemporaryDirectory(prefix="vibecomfy-port-convert-") as tmp:
        path = Path(tmp) / "emitted.py"
        path.write_text(text, encoding="utf-8")
        return _validate_emitted_path(path, schema_provider=schema_provider)


def _validate_emitted_path(path: Path, *, schema_provider: Any | None) -> PortConvertValidation:
    try:
        spec = importlib.util.spec_from_file_location(f"vibecomfy_port_convert_{path.stem}", path)
        if spec is None or spec.loader is None:
            return PortConvertValidation(ok=False, error=f"Could not import emitted module {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as exc:
        return PortConvertValidation(ok=False, error=f"import failed: {type(exc).__name__}: {exc}")

    build = getattr(module, "build", None)
    if not callable(build):
        return PortConvertValidation(ok=False, import_ok=True, error="build() missing")

    try:
        workflow = build()
    except Exception as exc:
        return PortConvertValidation(ok=False, import_ok=True, error=f"build failed: {type(exc).__name__}: {exc}")
    if not isinstance(workflow, VibeWorkflow):
        return PortConvertValidation(
            ok=False,
            import_ok=True,
            error=f"build() returned {type(workflow).__name__}, expected VibeWorkflow",
        )

    try:
        api = workflow.compile("api")
    except Exception as exc:
        return PortConvertValidation(
            ok=False,
            import_ok=True,
            build_ok=True,
            error=f"compile failed: {type(exc).__name__}: {exc}",
        )

    report = workflow.validate(schema_provider=schema_provider) if schema_provider is not None else ValidationReport(ok=True)
    return PortConvertValidation(
        ok=report.ok,
        import_ok=True,
        build_ok=True,
        compile_ok=True,
        schema_ok=report.ok if schema_provider is not None else None,
        issues=report.issues,
        api_node_count=len(api),
        error=None if report.ok else "schema validation failed",
    )


def _source_provenance(workflow: VibeWorkflow, *, source_path: str | None) -> dict[str, Any]:
    provenance = dict(workflow.source.provenance)
    if source_path is not None:
        provenance.setdefault("source_path", source_path)
    provenance.setdefault("source_id", workflow.source.id)
    provenance.setdefault("source_type", workflow.source.source_type)
    if workflow.source.path is not None:
        provenance.setdefault("source_workflow_path", workflow.source.path)
    return provenance


def _conversion_provenance(
    workflow: VibeWorkflow,
    *,
    source_path: str | None,
    provenance: dict[str, Any] | None,
    source_hash: str | None,
    workflow_shape: dict[str, Any] | None,
    output_mode: PortConvertMode,
    ready_id: str | None,
) -> dict[str, Any]:
    merged = _source_provenance(workflow, source_path=source_path)
    if provenance:
        merged.update(provenance)
    if source_hash is not None:
        merged["source_hash"] = source_hash
    if workflow_shape is not None:
        merged["workflow_shape"] = dict(workflow_shape)
    merged["output_mode"] = output_mode
    if ready_id is not None:
        merged["ready_id"] = ready_id
    return merged


def _validate_ready_id(ready_id: str) -> None:
    parts = ready_id.split("/", 1)
    if len(parts) != 2 or not all(parts):
        raise ValueError("ready_id must have the form 'kind/name'")


def _ready_metadata(
    workflow: VibeWorkflow,
    *,
    ready_id: str,
    source_path: str | None,
    provenance: dict[str, Any] | None,
) -> dict[str, Any]:
    metadata = dict(workflow.metadata)
    metadata["ready_template"] = ready_id
    if source_path is not None:
        metadata.setdefault("source_workflow", source_path)
    if provenance:
        metadata.setdefault("provenance", dict(provenance))
    return metadata


def _ready_requirements(workflow: VibeWorkflow) -> dict[str, Any]:
    model_assets = workflow.metadata.get("model_assets")
    models = model_assets if isinstance(model_assets, list) else list(workflow.requirements.models)
    return {
        "models": models,
        "custom_nodes": list(workflow.requirements.custom_nodes),
    }


__all__ = [
    "PortConvertResult",
    "PortConvertValidation",
    "port_convert_workflow",
    "validate_emitted_module",
]
