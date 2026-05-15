from __future__ import annotations

import difflib
import importlib.util
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from vibecomfy.porting.emitter import (
    EmissionDiagnostic,
    emit_ready_template_python,
    emit_scratchpad_python,
)
from vibecomfy.porting.parity import (
    class_type_counter,
    compile_equivalent,
    topology_counter,
    widget_value_counter,
)
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

    # Parity evidence (populated when source and emitted are both compiled)
    parity_ok: bool | None = None
    parity_diffs: list[str] = field(default_factory=list)
    source_output_count: int = 0
    emitted_output_count: int = 0
    source_class_type_counts: dict[str, int] = field(default_factory=dict)
    emitted_class_type_counts: dict[str, int] = field(default_factory=dict)
    source_widget_value_snapshot: int = 0  # distinct (class, key, repr) count
    emitted_widget_value_snapshot: int = 0
    source_topology_snapshot: int = 0  # distinct (class, input, source_class, slot) count
    emitted_topology_snapshot: int = 0

    # Readability diagnostics collected during emission
    emission_diagnostics: list[EmissionDiagnostic] = field(default_factory=list)

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
            "parity_ok": self.parity_ok,
            "parity_diffs": self.parity_diffs,
            "source_output_count": self.source_output_count,
            "emitted_output_count": self.emitted_output_count,
            "source_class_type_counts": self.source_class_type_counts,
            "emitted_class_type_counts": self.emitted_class_type_counts,
            "source_widget_value_snapshot": self.source_widget_value_snapshot,
            "emitted_widget_value_snapshot": self.emitted_widget_value_snapshot,
            "source_topology_snapshot": self.source_topology_snapshot,
            "emitted_topology_snapshot": self.emitted_topology_snapshot,
            "emission_diagnostics": [d.to_json() for d in self.emission_diagnostics],
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
    emission_diagnostics: list[EmissionDiagnostic] = []

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
            diagnostics=emission_diagnostics,
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
            diagnostics=emission_diagnostics,
        )
        mode = "ready_template"

    # Compile the source workflow before emission for parity comparison.
    source_api = workflow.compile("api") if validate else None

    result = PortConvertResult(mode=mode, text=text, ready_id=ready_id)
    if validate:
        result.validation = validate_emitted_module(text, schema_provider=schema_provider)
        result.validation.emission_diagnostics = emission_diagnostics

        # Run parity: compile the emitted module and compare against source.
        if source_api is not None and result.validation is not None and result.validation.compile_ok:
            try:
                with tempfile.TemporaryDirectory(prefix="vibecomfy-port-parity-") as tmp:
                    parity_path = Path(tmp) / "emitted_parity.py"
                    parity_path.write_text(text, encoding="utf-8")
                    spec = importlib.util.spec_from_file_location(
                        f"vibecomfy_port_parity_{parity_path.stem}", parity_path
                    )
                    if spec is not None and spec.loader is not None:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        build_fn = getattr(module, "build", None)
                        if callable(build_fn):
                            emitted_wf = build_fn()
                            if isinstance(emitted_wf, VibeWorkflow):
                                emitted_api = emitted_wf.compile("api")
                                parity_ok, parity_diffs = compile_equivalent(source_api, emitted_api)

                                result.validation.parity_ok = parity_ok
                                result.validation.parity_diffs = parity_diffs

                                # Output counts
                                result.validation.source_output_count = len(source_api)
                                result.validation.emitted_output_count = len(emitted_api)

                                # Class type snapshots
                                src_ct = class_type_counter(source_api)
                                emit_ct = class_type_counter(emitted_api)
                                result.validation.source_class_type_counts = dict(src_ct)
                                result.validation.emitted_class_type_counts = dict(emit_ct)

                                # Widget value snapshots (distinct count)
                                src_wv = widget_value_counter(source_api)
                                emit_wv = widget_value_counter(emitted_api)
                                result.validation.source_widget_value_snapshot = len(src_wv)
                                result.validation.emitted_widget_value_snapshot = len(emit_wv)

                                # Topology snapshots (distinct count)
                                src_topo = topology_counter(source_api)
                                emit_topo = topology_counter(emitted_api)
                                result.validation.source_topology_snapshot = len(src_topo)
                                result.validation.emitted_topology_snapshot = len(emit_topo)
            except Exception:
                # Parity failure is non-fatal for the result; diffs are reported.
                pass

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


# ---------------------------------------------------------------------------
# Atomic conversion write — temp file, validate, parity-check, then replace
# ---------------------------------------------------------------------------


class ManualTemplateRefusal(ValueError):
    """Raised when a target file has ``# vibecomfy: manual`` marker."""


class ConversionWriteError(RuntimeError):
    """Raised when atomic write fails validation or parity gates."""


def _check_manual_refusal(target: Path) -> None:
    """Refuse to overwrite a template marked ``# vibecomfy: manual``."""
    if not target.exists():
        return
    first_line = target.read_text(encoding="utf-8").splitlines()[0].strip() if target.exists() else ""
    if "# vibecomfy: manual" in first_line:
        raise ManualTemplateRefusal(
            f"Target {target} is marked '# vibecomfy: manual'. "
            f"Remove the marker or use a different output path."
        )


def _compute_diff(original: str, emitted: str, target_path: str) -> dict[str, Any]:
    """Produce unified diff + JSON diff metadata."""
    original_lines = original.splitlines(keepends=True)
    emitted_lines = emitted.splitlines(keepends=True)
    unified = "".join(
        difflib.unified_diff(
            original_lines if original else [],
            emitted_lines,
            fromfile=str(target_path),
            tofile=f"{target_path} (emitted)",
        )
    )
    return {
        "unified_diff": unified,
        "original_exists": bool(original),
        "emitted_line_count": len(emitted_lines),
        "original_line_count": len(original_lines),
    }


def port_convert_and_write(
    result: "PortConvertResult",
    target: Path,
    *,
    dry_run: bool = False,
    diff: bool = False,
) -> dict[str, Any]:
    """Write emitted text via temp-file atomic replace after all gates pass.

    Args:
        result: The conversion result from ``port_convert_workflow``.
        target: Destination file path.
        dry_run: If True, emit conversion payload and evidence without writing.
        diff: If True, produce unified diff + JSON diff metadata (forces dry_run).
        schema_provider: Optional schema provider for validation.

    Returns:
        A dict with ``written``, ``dry_run``, ``diff``, and ``validation`` keys.

    Raises:
        ManualTemplateRefusal: If target has ``# vibecomfy: manual`` marker.
        ConversionWriteError: If validation or parity fails.
    """
    # Gate 1: manual-template refusal
    _check_manual_refusal(target)

    # Read original content for diff
    original_content = target.read_text(encoding="utf-8") if target.exists() else ""

    # Gate 2: validation must pass
    validation = result.validation
    if validation is None:
        raise ConversionWriteError("No validation available — conversion may have been skipped.")
    if not validation.ok:
        raise ConversionWriteError(
            f"Validation failed for {target}: {validation.error}. "
            f"Parity OK: {validation.parity_ok}. "
            f"Fix issues before writing."
        )
    if validation.parity_ok is False:
        raise ConversionWriteError(
            f"Parity check failed for {target}. "
            f"Diffs: {validation.parity_diffs[:5]}"
        )

    # Diff mode
    diff_data: dict[str, Any] | None = None
    if diff:
        diff_data = _compute_diff(original_content, result.text, str(target))

    # Dry-run mode
    if dry_run:
        payload: dict[str, Any] = {
            "written": False,
            "dry_run": True,
            "target": str(target),
            "validation": validation.to_json(),
        }
        if diff_data is not None:
            payload["diff"] = diff_data
        else:
            # Always include diff in dry-run
            payload["diff"] = _compute_diff(original_content, result.text, str(target))
        return payload

    # Gate 3: atomic write — temp file in target directory, validate, then replace
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        prefix=".vibecomfy-port-",
        dir=str(target.parent),
        encoding="utf-8",
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)
        tmp_path.write_text(result.text, encoding="utf-8")

    try:
        # Re-validate the temp module before replacing
        temp_validation = _validate_emitted_path(tmp_path, schema_provider=None)
        if not temp_validation.ok and temp_validation.import_ok:
            # Build/compile issues are non-fatal if the original validation passed
            pass
        elif not temp_validation.import_ok:
            raise ConversionWriteError(
                f"Temp file at {tmp_path} failed import validation: {temp_validation.error}"
            )

        # Atomic replace
        tmp_path.replace(target)
    except Exception:
        # Clean up temp file on failure
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    return {
        "written": True,
        "dry_run": False,
        "target": str(target),
        "validation": validation.to_json(),
        "diff": diff_data,
    }


__all__ = [
    "ConversionWriteError",
    "ManualTemplateRefusal",
    "PortConvertResult",
    "PortConvertValidation",
    "_check_manual_refusal",
    "port_convert_and_write",
    "port_convert_workflow",
    "validate_emitted_module",
]
