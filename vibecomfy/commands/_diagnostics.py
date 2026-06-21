from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    severity: str
    recoverable: bool
    details: Mapping[str, Any] | None = None


def diagnostic_to_json(diagnostic: Diagnostic) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": diagnostic.code,
        "message": diagnostic.message,
        "severity": diagnostic.severity,
        "recoverable": diagnostic.recoverable,
    }
    if diagnostic.details is not None:
        payload["details"] = dict(diagnostic.details)
    return payload


def diagnostics_to_json(diagnostics: list[Diagnostic] | tuple[Diagnostic, ...]) -> list[dict[str, Any]]:
    return [diagnostic_to_json(diagnostic) for diagnostic in diagnostics]


def diagnostic_to_text(diagnostic: Diagnostic) -> str:
    prefix = f"{diagnostic.severity}: {diagnostic.code}"
    if diagnostic.recoverable:
        prefix = f"{prefix} (recoverable)"
    return f"{prefix}: {diagnostic.message}"


def diagnostics_to_text(diagnostics: list[Diagnostic] | tuple[Diagnostic, ...]) -> str:
    return "\n".join(diagnostic_to_text(diagnostic) for diagnostic in diagnostics)


__all__ = [
    "Diagnostic",
    "diagnostic_to_json",
    "diagnostic_to_text",
    "diagnostics_to_json",
    "diagnostics_to_text",
]
