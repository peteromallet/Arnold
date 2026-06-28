"""CLI-owned workflow diagnostic normalization and rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold.workflow.compiler import CompileDiagnosticError
from arnold.workflow.diagnostics import AuthoringDiagnostic, DiagnosticSeverity
from arnold.workflow.source_compiler import SourceCompileError
from arnold.workflow.validation import ManifestValidationError, ManifestValidationIssue


_DEFAULT_COMPILE_SUGGESTION = "fix the workflow authoring data before compiling"


def diagnostic_envelope(
    diagnostics: object,
    *,
    source_path: str | Path | None = None,
    ok: bool = False,
    source_kind: str = "python",
) -> dict[str, Any]:
    """Return the stable CLI JSON diagnostic envelope."""

    path = str(source_path) if source_path is not None else None
    return {
        "ok": ok,
        "source": {"kind": source_kind, "path": path},
        "diagnostics": [
            normalize_diagnostic(diagnostic, source_path=source_path)
            for diagnostic in iter_diagnostics(diagnostics)
        ],
    }


def render_json_envelope(
    diagnostics: object,
    *,
    source_path: str | Path | None = None,
    ok: bool = False,
    source_kind: str = "python",
) -> str:
    """Render a machine-readable diagnostic envelope."""

    return json.dumps(
        diagnostic_envelope(
            diagnostics,
            source_path=source_path,
            ok=ok,
            source_kind=source_kind,
        ),
        sort_keys=True,
        indent=2,
    )


def render_human_diagnostics(
    diagnostics: object,
    *,
    source_path: str | Path | None = None,
) -> str:
    """Render source-oriented diagnostics for humans."""

    rendered: list[str] = []
    for diagnostic in iter_diagnostics(diagnostics):
        payload = normalize_diagnostic(diagnostic, source_path=source_path)
        location = _format_location(payload)
        rendered.append(
            f"{location}: {payload['severity']}: {payload['code']}: {payload['message']}"
        )
        snippet = _source_snippet(payload)
        if snippet is not None:
            rendered.append(snippet)
            marker = _caret_marker(payload)
            if marker is not None:
                rendered.append(marker)
        if payload.get("suggestion"):
            rendered.append(f"Fix: {payload['suggestion']}")
    return "\n".join(rendered)


def iter_diagnostics(value: object) -> tuple[object, ...]:
    """Flatten supported diagnostic containers into individual diagnostics."""

    if isinstance(value, SourceCompileError):
        return value.diagnostics
    if isinstance(value, ManifestValidationError):
        return tuple(value.issues)
    if isinstance(value, AuthoringDiagnostic):
        return (value,)
    if isinstance(value, CompileDiagnosticError):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        flattened: list[object] = []
        for item in value:
            flattened.extend(iter_diagnostics(item))
        return tuple(flattened)
    diagnostics = getattr(value, "diagnostics", None)
    if diagnostics is not None:
        return iter_diagnostics(diagnostics)
    return (value,)


def normalize_diagnostic(
    diagnostic: object,
    *,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    """Normalize one diagnostic to the CLI schema with agent-friendly aliases."""

    if isinstance(diagnostic, AuthoringDiagnostic):
        return _normalize_authoring_diagnostic(diagnostic, source_path=source_path)
    if isinstance(diagnostic, CompileDiagnosticError):
        return _normalize_compile_diagnostic(diagnostic, source_path=source_path)
    if isinstance(diagnostic, ManifestValidationIssue):
        return _normalize_manifest_validation_diagnostic(diagnostic, source_path=source_path)
    return _normalize_fallback_diagnostic(diagnostic, source_path=source_path)


def _normalize_authoring_diagnostic(
    diagnostic: AuthoringDiagnostic,
    *,
    source_path: str | Path | None,
) -> dict[str, Any]:
    payload = diagnostic.to_dict()
    span = diagnostic.source_span
    file_path = span.path if span is not None else _string_or_none(source_path)
    payload.update(
        {
            "file": file_path,
            "line": span.start_line if span is not None else None,
            "col": span.start_column if span is not None else None,
            "severity": diagnostic.severity.value,
            "code": diagnostic.code.value,
            "message": diagnostic.message,
            "suggestion": diagnostic.remediation,
        }
    )
    return payload


def _normalize_compile_diagnostic(
    diagnostic: CompileDiagnosticError,
    *,
    source_path: str | Path | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "file": _string_or_none(source_path),
        "line": None,
        "col": None,
        "severity": DiagnosticSeverity.ERROR.value,
        "code": "AWF_COMPILE_ERROR",
        "message": str(diagnostic),
        "suggestion": _DEFAULT_COMPILE_SUGGESTION,
    }
    if diagnostic.node_id is not None:
        payload["node_id"] = diagnostic.node_id
    if diagnostic.field is not None:
        payload["field"] = diagnostic.field
    return payload


def _normalize_manifest_validation_diagnostic(
    diagnostic: ManifestValidationIssue,
    *,
    source_path: str | Path | None,
) -> dict[str, Any]:
    span = diagnostic.source_span
    file_path = span.path if span is not None else _string_or_none(source_path)
    payload: dict[str, Any] = {
        "file": file_path,
        "line": span.start_line if span is not None else None,
        "col": span.start_column if span is not None else None,
        "severity": diagnostic.severity,
        "code": f"AWF_MANIFEST_VALIDATION_ERROR:{diagnostic.code}",
        "message": diagnostic.message,
        "suggestion": _manifest_validation_suggestion(diagnostic),
    }
    if span is not None:
        payload["source_span"] = {
            "path": span.path,
            "start_line": span.start_line,
            "start_column": span.start_column,
            "end_line": span.end_line,
            "end_column": span.end_column,
        }
    if diagnostic.node_id is not None:
        payload["node_id"] = diagnostic.node_id
    if diagnostic.edge_id is not None:
        payload["edge_id"] = diagnostic.edge_id
    if diagnostic.field is not None:
        payload["field"] = diagnostic.field
    if diagnostic.details:
        payload["details"] = dict(diagnostic.details)
    return payload


def _manifest_validation_suggestion(diagnostic: ManifestValidationIssue) -> str:
    if diagnostic.source_span is not None:
        if diagnostic.node_id is not None:
            return (
                f"edit the authored workflow source for node {diagnostic.node_id!r}"
                f" so manifest field {diagnostic.field or '<unknown>'} satisfies validation"
            )
        if diagnostic.edge_id is not None:
            return (
                f"edit the authored workflow source for edge {diagnostic.edge_id!r}"
                f" so manifest field {diagnostic.field or '<unknown>'} satisfies validation"
            )
        return "edit the authored workflow source at this span so the generated manifest satisfies validation"
    return (
        f"fix manifest-level invariant {diagnostic.field or diagnostic.code!r}"
        " and regenerate the manifest from valid source"
    )


def _normalize_fallback_diagnostic(
    diagnostic: object,
    *,
    source_path: str | Path | None,
) -> dict[str, Any]:
    return {
        "file": _string_or_none(source_path),
        "line": None,
        "col": None,
        "severity": DiagnosticSeverity.ERROR.value,
        "code": "AWF_ERROR",
        "message": str(diagnostic) or diagnostic.__class__.__name__,
        "suggestion": None,
    }


def _format_location(payload: Mapping[str, Any]) -> str:
    file_path = payload.get("file") or "<workflow-source>"
    line = payload.get("line")
    col = payload.get("col")
    return f"{file_path}:{line if line is not None else '?'}:{col if col is not None else '?'}"


def _source_snippet(payload: Mapping[str, Any]) -> str | None:
    file_path = payload.get("file")
    line = payload.get("line")
    if not isinstance(file_path, str) or not isinstance(line, int):
        return None
    try:
        lines = Path(file_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    if line < 1 or line > len(lines):
        return None
    return lines[line - 1]


def _caret_marker(payload: Mapping[str, Any]) -> str | None:
    source_span = payload.get("source_span")
    if not isinstance(source_span, Mapping):
        return None
    col = payload.get("col")
    if not isinstance(col, int):
        return None
    start_column = int(source_span.get("start_column") or col)
    end_column = source_span.get("end_column")
    width = 1
    if isinstance(end_column, int) and end_column > start_column:
        width = end_column - start_column
    return f"{' ' * max(col - 1, 0)}{'^' * width}"


def _string_or_none(value: str | Path | None) -> str | None:
    return str(value) if value is not None else None


__all__ = [
    "diagnostic_envelope",
    "iter_diagnostics",
    "normalize_diagnostic",
    "render_human_diagnostics",
    "render_json_envelope",
]
