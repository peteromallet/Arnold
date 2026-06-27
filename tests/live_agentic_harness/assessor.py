"""Deep assessment of live agentic run artifacts.

The live agentic harness already verifies flow metadata (real dispatcher,
agentic model behavior, status == success).  This module inspects the actual
run artifacts to catch failures that metadata alone cannot:

* response.ok == false or response.error set
* readiness blockers
* graph unchanged when an edit was expected
* hard diagnostics (severity == error) from agent-edit turns
* upstream dependency failures such as Hivemind HTTP 500
* implementation_result.json reporting the graph is unchanged
* validation gates that failed for an apply/edit route
* (when enabled) an LLM intent judge that scores the edit against the query

The deterministic checks run first; the LLM judge is called afterward for
scenarios that expect a graph change.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from .intent_judge import judge_edit_intent

_ERROR_SEVERITIES = {"error", "fatal"}

# Critical upstream failures that should always fail a live run.
_UPSTREAM_FAILURE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"Hivemind HTTP error.*500", re.IGNORECASE),
    re.compile(r"HTTP Error 500", re.IGNORECASE),
    re.compile(r"Internal Server Error", re.IGNORECASE),
]

# Soft capacity warnings: surfaced so humans see them, but not treated as hard
# failures on their own (the run may still succeed via fallback evidence).
_SOFT_WARNING_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"HTTP Error 429", re.IGNORECASE),
    re.compile(r"Too Many Requests", re.IGNORECASE),
]


def _load_json(path: Path) -> dict[str, Any] | None:
    """Load a JSON artifact if it exists and is valid."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _walk(obj: Any) -> Any:
    """Recursively yield every dict/string node in a JSON-like structure."""
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)
    else:
        yield obj


def _collect_hard_diagnostics(response: Mapping[str, Any]) -> list[str]:
    """Return messages from any object with severity error/fatal."""
    issues: list[str] = []
    for node in _walk(response):
        if not isinstance(node, dict):
            continue
        if node.get("severity") not in _ERROR_SEVERITIES:
            continue
        message = node.get("message")
        if not isinstance(message, str):
            detail = node.get("detail")
            message = json.dumps(detail, sort_keys=True) if isinstance(detail, dict) else str(node)
        message = message.strip()
        if message and message not in issues:
            issues.append(message)
    return issues


def _collect_pattern_matches(
    response: Mapping[str, Any],
    patterns: list[re.Pattern[str]],
) -> list[str]:
    """Return distinct string values matching any of the supplied patterns."""
    issues: list[str] = []
    seen: set[str] = set()
    for node in _walk(response):
        if not isinstance(node, str):
            continue
        for pattern in patterns:
            if pattern.search(node):
                if node not in seen:
                    seen.add(node)
                    issues.append(node)
                break
    return issues


def _expects_graph_changed(
    scenario: Mapping[str, Any] | None,
    response: Mapping[str, Any] | None,
) -> bool:
    """Decide whether this scenario should have produced a graph change.

    Explicit scenario configuration wins, then we fall back to reading the
    agent's own classification/plan from the response.
    """
    if scenario is not None:
        assessment = scenario.get("assessment")
        if isinstance(assessment, dict) and "expect_graph_changed" in assessment:
            return bool(assessment["expect_graph_changed"])

    if response is None:
        return False

    plan = response.get("report", {}).get("executor", {}).get("plan") or {}
    if plan.get("implement") is True and plan.get("route") in {"adapt", "revise"}:
        return True

    return False


def assess_live_output_dir(
    output_dir: Path | str,
    scenario: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Inspect live artifacts under *output_dir* and return an assessment.

    The returned dict has:

    * ``passed`` — True iff no error-level issues were found.
    * ``expect_graph_changed`` — whether the scenario expected an edit.
    * ``issue_count`` / ``error_count`` — counts.
    * ``issues`` — list of ``{"check", "severity", "detail"}`` dicts.
    """
    output_dir = Path(output_dir)
    response = _load_json(output_dir / "response.json")
    impl_result = _load_json(output_dir / "implementation_result.json")

    issues: list[dict[str, Any]] = []
    expect_graph_changed = _expects_graph_changed(scenario, response)

    if response is not None:
        # Top-level response health.
        if response.get("ok") is False:
            issues.append(
                {
                    "check": "response_ok",
                    "severity": "error",
                    "detail": f"response.ok is False: {response.get('error') or response.get('message')}",
                }
            )
        elif response.get("error"):
            issues.append(
                {
                    "check": "response_error_field",
                    "severity": "error",
                    "detail": f"response.error set: {response['error']}",
                }
            )

        # Readiness is also captured in flow_metadata, but surface it here if
        # the response carries it (e.g. blocked-prerequisite runs).
        readiness = response.get("readiness") or {}
        if readiness.get("ready") is False:
            issues.append(
                {
                    "check": "response_readiness",
                    "severity": "error",
                    "detail": f"Readiness not ready: {readiness.get('reason')}",
                }
            )

        if expect_graph_changed:
            if response.get("graph_unchanged") is True:
                issues.append(
                    {
                        "check": "graph_changed",
                        "severity": "error",
                        "detail": "Expected graph change but response.graph_unchanged is True.",
                    }
                )

            no_reason = response.get("no_candidate_reason")
            if no_reason in {"no_changes", "no_candidate"}:
                issues.append(
                    {
                        "check": "no_candidate_reason",
                        "severity": "error",
                        "detail": f"Expected edit but no_candidate_reason={no_reason!r}.",
                    }
                )

            outcome = response.get("outcome") or {}
            outcome_kind = outcome.get("kind")
            if outcome_kind in {"noop", "requires_custom_nodes"}:
                issues.append(
                    {
                        "check": "outcome_kind",
                        "severity": "error",
                        "detail": f"Expected edit but outcome.kind={outcome_kind!r}.",
                    }
                )

            gates = response.get("gates") or {}
            false_gates = [name for name, value in gates.items() if value is False]
            if false_gates:
                issues.append(
                    {
                        "check": "gates",
                        "severity": "error",
                        "detail": f"Expected edit but gates failed: {', '.join(sorted(false_gates))}.",
                    }
                )

        # LLM intent judge: score the candidate edit against the query when the
        # scenario expects a graph change.  This runs by default; set
        # ``assessment.skip_intent_judge: true`` in the scenario to disable it.
        if expect_graph_changed and not scenario.get("assessment", {}).get("skip_intent_judge"):
            verdict = judge_edit_intent(output_dir, scenario)
            if verdict.get("pass_") is False:
                issues.append(
                    {
                        "check": "intent_judge",
                        "severity": "error",
                        "detail": (
                            f"LLM intent judge failed: {verdict.get('rationale', 'no rationale')} "
                            f"criteria={verdict.get('criteria')}"
                        ),
                    }
                )
            elif verdict.get("pass_") is True:
                issues.append(
                    {
                        "check": "intent_judge",
                        "severity": "info",
                        "detail": (
                            f"LLM intent judge passed: {verdict.get('rationale', 'no rationale')} "
                            f"criteria={verdict.get('criteria')}"
                        ),
                    }
                )
            else:
                issues.append(
                    {
                        "check": "intent_judge",
                        "severity": "warning",
                        "detail": f"LLM intent judge could not run: {verdict.get('error')}",
                    }
                )

        # Any hard diagnostic anywhere in the response envelope.
        for msg in _collect_hard_diagnostics(response):
            issues.append(
                {
                    "check": "hard_diagnostic",
                    "severity": "error",
                    "detail": msg,
                }
            )

        # Critical upstream failures (Hivemind 500, etc.).
        for msg in _collect_pattern_matches(response, _UPSTREAM_FAILURE_PATTERNS):
            issues.append(
                {
                    "check": "upstream_failure",
                    "severity": "error",
                    "detail": msg,
                }
            )

        # Capacity/soft warnings: surfaced, but not counted as errors.
        for msg in _collect_pattern_matches(response, _SOFT_WARNING_PATTERNS):
            issues.append(
                {
                    "check": "soft_warning",
                    "severity": "warning",
                    "detail": msg,
                }
            )

    if impl_result is not None:
        impl_message = impl_result.get("message", "")
        if isinstance(impl_message, str):
            if expect_graph_changed and "unchanged" in impl_message.lower():
                issues.append(
                    {
                        "check": "implementation_result",
                        "severity": "error",
                        "detail": f"implementation_result reports unchanged: {impl_message}",
                    }
                )
        if impl_result.get("ok") is False:
            issues.append(
                {
                    "check": "implementation_result_ok",
                    "severity": "error",
                    "detail": f"implementation_result.ok is False: {impl_result.get('error') or impl_message}",
                }
            )

    # Deduplicate while preserving order.
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for issue in issues:
        key = (issue["check"], issue["severity"], issue["detail"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)

    errors = [issue for issue in deduped if issue["severity"] == "error"]
    return {
        "passed": len(errors) == 0,
        "expect_graph_changed": expect_graph_changed,
        "issue_count": len(deduped),
        "error_count": len(errors),
        "issues": deduped,
    }
