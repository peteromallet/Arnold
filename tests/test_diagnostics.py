from __future__ import annotations

from vibecomfy.diagnostics import (
    DiagnosticFinding,
    PatchSuggestion,
    finding_messages,
    findings_payload,
    patch_suggestions_payload,
)


def test_diagnostic_finding_payload_omits_empty_optional_fields() -> None:
    finding = DiagnosticFinding("missing_model", "model is missing", "error")

    assert finding.to_payload() == {
        "code": "missing_model",
        "message": "model is missing",
        "severity": "error",
    }


def test_diagnostic_finding_payload_preserves_doctor_aligned_fields() -> None:
    finding = DiagnosticFinding(
        "unknown_class_type",
        "Unknown node class",
        "warning",
        node_id="12",
        class_type="ExampleNode",
        detail={"class_type": "ExampleNode"},
    )

    assert finding.to_payload() == {
        "code": "unknown_class_type",
        "message": "Unknown node class",
        "severity": "warning",
        "node_id": "12",
        "class_type": "ExampleNode",
        "detail": {"class_type": "ExampleNode"},
    }


def test_diagnostic_helpers_convert_current_payload_shapes() -> None:
    findings = [
        DiagnosticFinding("a", "first", "warning"),
        DiagnosticFinding("b", "second", "error"),
    ]
    suggestions = [PatchSuggestion("seed", "set deterministic seed")]

    assert finding_messages(findings, severity="error") == ["second"]
    assert findings_payload(findings) == [finding.to_payload() for finding in findings]
    assert patch_suggestions_payload(suggestions) == [{"name": "seed", "rationale": "set deterministic seed"}]
