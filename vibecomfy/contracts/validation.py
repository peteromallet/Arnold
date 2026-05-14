from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ContractIssue:
    """A single issue produced by a semantic contract validation."""

    code: str
    message: str
    severity: str = "error"  # "error" | "warning"
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContractReport:
    """Report from a semantic contract validation."""

    contract_name: str
    passed: bool
    issues: list[ContractIssue] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def add(self, code: str, message: str, *, severity: str = "error", **detail: Any) -> None:
        self.issues.append(ContractIssue(code=code, message=message, severity=severity, detail=dict(detail)))
        if severity == "error":
            self.passed = False

    def summary(self) -> str:
        errors = [i for i in self.issues if i.severity == "error"]
        warnings = [i for i in self.issues if i.severity == "warning"]
        lines = [
            f"Contract: {self.contract_name}",
            f"  passed: {self.passed}",
            f"  errors: {len(errors)}",
            f"  warnings: {len(warnings)}",
        ]
        for i in self.issues:
            lines.append(f"  [{i.severity.upper()}] {i.code}: {i.message}")
        return "\n".join(lines)

    def errors(self) -> list[ContractIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def warnings(self) -> list[ContractIssue]:
        return [i for i in self.issues if i.severity == "warning"]
