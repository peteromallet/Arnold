"""Critique result status helpers."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable


UNVERIFIABLE_STATUS = "unverifiable"
UNVERIFIABLE_PREFIX = "unverifiable:"


def unverifiable_detail(reason: str) -> str:
    reason = str(reason or "").strip()
    if reason.lower().startswith(UNVERIFIABLE_PREFIX):
        return reason
    return f"{UNVERIFIABLE_PREFIX} {reason or 'the check could not be verified'}"


def _finding_reason(finding: Any) -> str | None:
    if not isinstance(finding, dict):
        return None
    detail = finding.get("detail")
    if not isinstance(detail, str):
        return None
    stripped = detail.strip()
    if stripped.lower().startswith(UNVERIFIABLE_PREFIX):
        return stripped[len(UNVERIFIABLE_PREFIX):].strip() or stripped
    return None


def is_unverifiable_check(check: Any) -> bool:
    if not isinstance(check, dict):
        return False
    if check.get("status") == UNVERIFIABLE_STATUS:
        return True
    findings = check.get("findings", [])
    if not isinstance(findings, list):
        return False
    return any(_finding_reason(finding) is not None for finding in findings)


def annotate_unverifiable_checks(
    payload: dict[str, Any],
    *,
    check_specs: Iterable[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Annotate unverifiable checks and return their operator-facing records.

    The worker schema remains backward-compatible: a worker can report an
    unverifiable check as a normal non-flagged finding whose detail starts with
    ``unverifiable:``. After worker validation, we annotate the stored artifact
    with a check-level status and sidecar summary for downstream consumers.
    """
    spec_by_id = {
        spec.get("id"): spec
        for spec in check_specs
        if isinstance(spec, dict) and isinstance(spec.get("id"), str)
    }
    checks = payload.get("checks", [])
    if not isinstance(checks, list):
        return []

    records: list[dict[str, Any]] = []
    for check in checks:
        if not isinstance(check, dict) or not is_unverifiable_check(check):
            continue
        check["status"] = UNVERIFIABLE_STATUS
        reasons = [
            reason
            for finding in check.get("findings", [])
            if (reason := _finding_reason(finding)) is not None
        ]
        reason = check.get("unverifiable_reason")
        if not isinstance(reason, str) or not reason.strip():
            reason = reasons[0] if reasons else "the check could not be verified"
            check["unverifiable_reason"] = reason

        spec = spec_by_id.get(check.get("id"), {})
        complexity = spec.get("complexity")
        record: dict[str, Any] = {
            "id": check.get("id", ""),
            "question": check.get("question", ""),
            "reason": reason,
        }
        cause = check.get("unverifiable_cause")
        if isinstance(cause, str) and cause.strip():
            record["cause"] = cause.strip()
        retryable = check.get("unverifiable_retryable")
        if isinstance(retryable, bool):
            record["retryable"] = retryable
        error_kind = check.get("unverifiable_error_kind")
        if isinstance(error_kind, str) and error_kind.strip():
            record["error_kind"] = error_kind.strip()
        if isinstance(complexity, int):
            record["complexity"] = complexity
            if complexity >= 4:
                record["attention"] = "high_complexity_unverifiable"
        records.append(record)

    if records:
        payload["unverifiable_checks"] = records
    return records


_PATH_RE = re.compile(r"(?:\.\./[^\s,;:)]+|/[^\s,;:)]+)")


def unverifiable_cause_key(reason: str) -> str:
    text = " ".join(str(reason or "").strip().split())
    if not text:
        return "unspecified verification dependency"
    match = _PATH_RE.search(text)
    if match:
        return match.group(0).rstrip(".")
    lowered = text.lower()
    for marker in ("because ", "outside ", "missing ", "cannot access ", "can't access "):
        if marker in lowered:
            start = lowered.index(marker)
            return lowered[start:].rstrip(".")
    return lowered[:120].rstrip(".")


def build_unverifiable_warnings(records: Iterable[dict[str, Any]]) -> list[str]:
    records = [record for record in records if isinstance(record, dict)]
    if not records:
        return []

    warnings: list[str] = []
    by_cause: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_cause[unverifiable_cause_key(str(record.get("reason", "")))].append(record)

    for cause, grouped in sorted(by_cause.items()):
        if len(grouped) < 2:
            continue
        ids = ", ".join(str(item.get("id", "?")) for item in grouped)
        warnings.append(
            f"critique degraded: {len(grouped)} checks unverifiable because {cause} "
            f"({ids}) — likely a missing repo, dependency, or wrong project root; fix and re-run."
        )

    high_complexity = [
        record for record in records
        if record.get("attention") == "high_complexity_unverifiable"
    ]
    if high_complexity:
        ids = ", ".join(str(item.get("id", "?")) for item in high_complexity)
        warnings.append(
            "critique degraded: high-complexity check(s) unverifiable "
            f"({ids}); operator attention required before treating critique as complete."
        )
    return warnings
