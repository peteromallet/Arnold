"""Helpers for shaping SWE-bench instance context into megaplan prompts."""

from __future__ import annotations

from typing import Any


def _read_value(source: Any, key: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _read_problem_statement(prepared: Any) -> str:
    instance = _read_value(prepared, "instance")
    for source in (instance, _read_value(prepared, "metadata"), prepared):
        value = _read_value(source, "problem_statement")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "No SWE-bench problem statement was provided."


def _read_fail_to_pass(prepared: Any) -> list[str]:
    metadata = _read_value(prepared, "metadata")
    value = _read_value(metadata, "fail_to_pass")
    if not isinstance(value, list):
        return []
    return [test_id.strip() for test_id in value if isinstance(test_id, str) and test_id.strip()]


def read_prompt(prepared: Any) -> str:
    """Build a planner-facing prompt for a SWE-bench instance."""

    problem_statement = _read_problem_statement(prepared)
    fail_to_pass = _read_fail_to_pass(prepared)

    sections = [
        "SWE-bench problem statement:",
        problem_statement,
    ]

    if fail_to_pass:
        test_lines = "\n".join(f"- {test_id}" for test_id in fail_to_pass)
        sections.extend(
            [
                "",
                "VERIFICATION TESTS",
                "------------------",
                test_lines,
                "",
                "Your plan MUST include a final task that runs these exact tests to verify the fix works.",
                "Run the EXISTING repo tests listed above - do NOT create new test files. If any test fails, read the error and iterate until all pass.",
            ]
        )
    else:
        sections.extend(
            [
                "",
                "No specific FAIL_TO_PASS verification tests were provided.",
            ]
        )

    return "\n".join(sections)
