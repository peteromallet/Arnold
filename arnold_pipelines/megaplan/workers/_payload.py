"""Shared worker payload helpers (B11 vendored from the deleted hermes worker).

The hermes worker module was deleted with the SDK; these payload-recovery,
template, and normalization helpers are still consumed by the neutral workers
(``workers/_impl.py``, ``workers/omp.py``, orchestration fan-out, and the
tiered-execute fallback contract).  They are pure functions with no
agent-runtime dependency.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.types import CliError

# ---------------------------------------------------------------------------
# Session DB path helpers
# ---------------------------------------------------------------------------


def _sanitize_db_name(identifier: str) -> str:
    """Sanitize a task/session identifier for use as a safe filename component."""
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', identifier)
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    return sanitized or "default"


def _worker_db_path(plan_dir: Path, identifier: str) -> Path:
    """Derive a per-worker SessionDB path from a plan directory and stable identifier."""
    sanitized = _sanitize_db_name(identifier)
    return plan_dir / '.hermes_state' / f'state_{sanitized}.db'


# ---------------------------------------------------------------------------
# JSON recovery from model tool markup
# ---------------------------------------------------------------------------


def _extract_json_from_mutating_tool_markup(content: str) -> str | None:
    """Try to recover JSON output from DeepSeek/Kimi write-style tool markup.

    Some models answer "fill in the JSON template" by emitting a
    ``<write_file path=...>``, ``<invoke name="write_file">`` or
    ``<bash>...</bash>`` block containing the JSON payload.  When that
    happens, treat the written content as the worker's actual response
    instead of rejecting it.
    """
    if not content or "<" not in content:
        return None

    candidates: list[str] = []

    def _balanced_json_blocks(text: str) -> list[str]:
        """Return top-level brace/bracket-delimited blocks honoring string escapes."""
        blocks: list[str] = []
        i = 0
        n = len(text)
        while i < n:
            c = text[i]
            if c not in ("{", "["):
                i += 1
                continue
            opener, closer = ("{", "}") if c == "{" else ("[", "]")
            stack = [opener]
            j = i + 1
            in_str = False
            esc = False
            while j < n and stack:
                ch = text[j]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                else:
                    if ch == '"':
                        in_str = True
                    elif ch == opener:
                        stack.append(opener)
                    elif ch == closer:
                        stack.pop()
                j += 1
            if not stack:
                blocks.append(text[i:j])
            i = j
        return blocks

    # Helper: add a candidate, optionally stripping markdown fences later.
    def _add_candidate(text: str) -> None:
        if text and text.strip():
            candidates.append(text.strip())

    # Tool names we are willing to treat as JSON-delivery wrappers.  Includes
    # both mutating tools and read/search/shell tools that models sometimes
    # emit when asked for structured output.
    _JSON_TOOL_NAMES = (
        "write_file|file_write|write|edit_file|patch|apply_patch|delete_file|"
        "bash|run_command|run_shell|terminal|shell|"
        "read_file|file_read|read|"
        "search_files|search|file_search"
    )

    # 1. Plain XML tags: <write_file ...> ... </write_file>
    tag_pattern = re.compile(
        rf"<(?P<tag>{_JSON_TOOL_NAMES})\b[^>]*>"
        r"(?P<body>.*?)"
        r"</(?P=tag)>",
        re.DOTALL | re.IGNORECASE,
    )
    heredoc_pattern = re.compile(
        r"<<\\?['\"]?(\w+)\\?['\"]?[^\n]*\n(.*?)\n\s*\1\s*$",
        re.DOTALL | re.IGNORECASE,
    )
    for match in tag_pattern.finditer(content):
        body = match.group("body")
        # Prefer an explicit <content> child if present.
        content_match = re.search(
            r"<content\b[^>]*>(.*?)</content>", body, re.DOTALL | re.IGNORECASE
        )
        if content_match:
            _add_candidate(content_match.group(1))
            _add_candidate(body)
        else:
            _add_candidate(body)
        # For shell tags, a heredoc is a common way the model writes JSON.
        if match.group("tag").lower() in {"bash", "run_command", "run_shell", "terminal", "shell"}:
            heredoc_match = heredoc_pattern.search(body)
            if heredoc_match:
                _add_candidate(heredoc_match.group(2))

    # 2. <invoke name="write_file"> ... <parameter name="content">...</parameter> ...
    invoke_pattern = re.compile(
        rf"<[^<>\s]*invoke\b[^<>]*\bname=[\"'](?P<name>{_JSON_TOOL_NAMES})[\"'][^<>]*>"
        r"(?P<body>.*?)"
        r"</[^<>\s]*invoke>",
        re.DOTALL | re.IGNORECASE,
    )
    param_pattern = re.compile(
        r"<[^<>\s]*parameter\b[^<>]*\bname=[\"']content[\"'][^<>]*>"
        r"(?P<value>.*?)"
        r"</[^<>\s]*parameter>",
        re.DOTALL | re.IGNORECASE,
    )
    for match in invoke_pattern.finditer(content):
        body = match.group("body")
        for param in param_pattern.finditer(body):
            _add_candidate(param.group("value"))
        # Also look for nested <content> children.
        content_match = re.search(
            r"<content\b[^>]*>(.*?)</content>", body, re.DOTALL | re.IGNORECASE
        )
        if content_match:
            _add_candidate(content_match.group(1))
        _add_candidate(body)

    # 3. DSML-style tags: <｜DSML｜invoke name="write_file"> ...
    #    <｜DSML｜parameter name="content">...</｜DSML｜parameter> ...
    dsml_prefix = "\uff5cDSML\uff5c"
    dsml_invoke_pattern = re.compile(
        rf"<{re.escape(dsml_prefix)}invoke\b[^<>]*\bname=[\"'](?P<name>{_JSON_TOOL_NAMES})[\"'][^<>]*>"
        rf"(?P<body>.*?)"
        rf"</{re.escape(dsml_prefix)}invoke>",
        re.DOTALL | re.IGNORECASE,
    )
    dsml_param_pattern = re.compile(
        rf"<{re.escape(dsml_prefix)}parameter\b[^<>]*\bname=[\"']content[\"'][^<>]*>"
        rf"(?P<value>.*?)"
        rf"</{re.escape(dsml_prefix)}parameter>",
        re.DOTALL | re.IGNORECASE,
    )
    dsml_content_pattern = re.compile(
        rf"<{re.escape(dsml_prefix)}content\b[^<>]*>(.*?)</{re.escape(dsml_prefix)}content>",
        re.DOTALL | re.IGNORECASE,
    )
    for match in dsml_invoke_pattern.finditer(content):
        body = match.group("body")
        for param in dsml_param_pattern.finditer(body):
            _add_candidate(param.group("value"))
        for content_match in dsml_content_pattern.finditer(body):
            _add_candidate(content_match.group(1))
        _add_candidate(body)

    # 4. Self-closing tags with a content= attribute.
    self_closing_pattern = re.compile(
        rf"<({_JSON_TOOL_NAMES})\b[^>]*\bcontent=[\"'](?P<value>[^\"']+)[\"'][^>]*/>",
        re.DOTALL | re.IGNORECASE,
    )
    for match in self_closing_pattern.finditer(content):
        _add_candidate(match.group("value"))

    # 5. Strip all recognized tool markup and look for any remaining JSON.
    stripped = content
    for match in sorted(
        re.finditer(
            rf"<({_JSON_TOOL_NAMES})\b[^>]*>.*?</(\1)>",
            stripped,
            re.DOTALL | re.IGNORECASE,
        ),
        key=lambda m: m.start(),
        reverse=True,
    ):
        stripped = stripped[: match.start()] + stripped[match.end() :]
    stripped = re.sub(r"<[^<>\s]*invoke\b[^<>]*>.*?</[^<>\s]*invoke>", "", stripped, flags=re.DOTALL | re.IGNORECASE)
    stripped = re.sub(r"<\uff5cDSML\uff5cinvoke\b[^<>]*>.*?</\uff5cDSML\uff5cinvoke>", "", stripped, flags=re.DOTALL | re.IGNORECASE)
    stripped = re.sub(r"<\uff5cDSML\uff5cparameter\b[^<>]*>.*?</\uff5cDSML\uff5cparameter>", "", stripped, flags=re.DOTALL | re.IGNORECASE)
    for block in _balanced_json_blocks(stripped):
        _add_candidate(block)

    # 6. Fall back to balanced JSON-ish blocks anywhere in the original markup.
    for block in _balanced_json_blocks(content):
        _add_candidate(block)

    for candidate in candidates:
        if not candidate:
            continue
        # Strip markdown fences if the model wrapped the JSON.
        cleaned = candidate
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()
        try:
            json.loads(cleaned)
            return cleaned
        except json.JSONDecodeError:
            continue
    return None


def _deescape_double_encoded_json(raw: str) -> str | None:
    """Return one decoded JSON-source layer for an escaped object response.

    Some coding endpoints return an object-shaped JSON string without the
    outer JSON-string quotes, for example ``{\"title\":\"Plan\"}``.  That
    response is neither valid JSON nor ordinary prose.  Decode only this exact
    shape and leave valid JSON, fenced output, and unrelated backslash-heavy
    text untouched.
    """
    text = str(raw).strip()
    if not (text.startswith("{") and text.endswith("}") and '\\"' in text):
        return None
    try:
        decoded = json.loads(f'"{text}"')
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, str) else None


# ---------------------------------------------------------------------------
# Output template seeding
# ---------------------------------------------------------------------------


def _template_has_content(payload: dict, step: str) -> bool:
    """Check if a template-file payload has real content (not just the empty template)."""
    if step == "critique":
        # For critique: check if any check has non-empty findings
        checks = payload.get("checks", [])
        if isinstance(checks, list):
            for check in checks:
                if isinstance(check, dict):
                    findings = check.get("findings", [])
                    if isinstance(findings, list) and findings:
                        return True
        # Also check flags array
        flags = payload.get("flags", [])
        if isinstance(flags, list) and flags:
            return True
        return False
    if step == "review":
        # For review: the template is pre-populated with task IDs and sense-check
        # IDs (empty verdicts). Check that at least one verdict was filled in, or
        # that summary/review_verdict has content.
        review_verdict = payload.get("review_verdict", "")
        if isinstance(review_verdict, str) and review_verdict.strip():
            return True
        summary = payload.get("summary", "")
        if isinstance(summary, str) and summary.strip():
            return True
        for tv in payload.get("task_verdicts", []):
            if isinstance(tv, dict) and tv.get("reviewer_verdict", "").strip():
                return True
        for sc in payload.get("sense_check_verdicts", []):
            if isinstance(sc, dict) and sc.get("verdict", "").strip():
                return True
        return False
    if step == "execute":
        output = payload.get("output", "")
        if isinstance(output, str) and output.strip():
            return True
        for key in ("files_changed", "commands_run", "deviations"):
            value = payload.get(key, [])
            if isinstance(value, list) and value:
                return True
        task_updates = payload.get("task_updates", [])
        if isinstance(task_updates, list):
            for update in task_updates:
                if not isinstance(update, dict):
                    continue
                status = update.get("status")
                if isinstance(status, str) and status.strip() and status != "pending":
                    return True
                executor_notes = update.get("executor_notes", "")
                if isinstance(executor_notes, str) and executor_notes.strip():
                    return True
                for key in ("files_changed", "commands_run"):
                    value = update.get(key, [])
                    if isinstance(value, list) and value:
                        return True
        acknowledgments = payload.get("sense_check_acknowledgments", [])
        if isinstance(acknowledgments, list):
            for acknowledgment in acknowledgments:
                if not isinstance(acknowledgment, dict):
                    continue
                executor_note = acknowledgment.get("executor_note", "")
                if isinstance(executor_note, str) and executor_note.strip():
                    return True
        return False
    # For other phases: any non-empty array or non-empty string
    return any(
        (isinstance(v, list) and v) or (isinstance(v, str) and v.strip())
        for k, v in payload.items()
    )


def _preferred_schema_type(prop: dict) -> str:
    ptype = prop.get("type", "string")
    if isinstance(ptype, list):
        non_null = [item for item in ptype if item != "null"]
        if non_null:
            return str(non_null[0])
        return "null"
    return str(ptype)


def _schema_allows_null(prop: dict) -> bool:
    ptype = prop.get("type")
    return ptype == "null" or (isinstance(ptype, list) and "null" in ptype)


def _schema_template(schema: dict) -> str:
    """Generate a JSON template from a schema showing required keys with placeholder values."""
    def _template_value(prop: dict) -> object:
        ptype = _preferred_schema_type(prop)
        if ptype == "string":
            desc = prop.get("description", "")
            enum = prop.get("enum")
            if isinstance(enum, list) and enum:
                return enum[0]
            return f"<{desc}>" if desc else "..."
        if ptype == "array":
            items = prop.get("items", {})
            if isinstance(items, dict) and _preferred_schema_type(items) == "string":
                return ["..."]
            if isinstance(items, dict) and _preferred_schema_type(items) == "object":
                item_template = _template_object(items)
                return [item_template] if item_template else []
            return []
        if ptype == "boolean":
            return True
        if ptype in ("number", "integer"):
            return 0
        if ptype == "object":
            if _schema_allows_null(prop):
                return None
            return _template_object(prop)
        if ptype == "null":
            return None
        return "..."

    def _template_object(object_schema: dict) -> dict[str, object]:
        props = object_schema.get("properties", {})
        if not isinstance(props, dict):
            return {}
        return {
            key: _template_value(prop) if isinstance(prop, dict) else "..."
            for key, prop in props.items()
        }

    props = schema.get("properties", {})
    if not isinstance(props, dict):
        return "{}"
    template = _template_object(schema)
    return json.dumps(template, indent=2)


def _build_output_template(step: str, schema: dict) -> str:
    """Build a JSON template from a schema for non-critique template-file phases."""
    return _schema_template(schema)


# ---------------------------------------------------------------------------
# Terminal provider failure surfacing
# ---------------------------------------------------------------------------

_TERMINAL_STREAMING_TIMEOUT_MARKERS = (
    "streaming deadline retry ceiling reached",
    "streaming deadline hit again",
)


def _raise_for_terminal_provider_failure(result: dict, *, step: str) -> None:
    """Surface exhausted provider streaming timeouts before output parsing."""

    if result.get("failed") is not True:
        return
    reason = result.get("error")
    if not isinstance(reason, str):
        return
    normalized = reason.strip().lower()
    if not any(marker in normalized for marker in _TERMINAL_STREAMING_TIMEOUT_MARKERS):
        return
    raise CliError(
        "streaming_timeout",
        f"Hermes provider timeout exhausted for step '{step}': {reason.strip()}",
        extra={"provider_failure_category": "timeout"},
    )


# ---------------------------------------------------------------------------
# Payload normalization before strict validation
# ---------------------------------------------------------------------------


def _normalize_flattened_plan_success_criterion(payload: dict) -> None:
    has_flattened_criterion = any(
        key in payload for key in ("criterion", "priority", "requires")
    )
    if not has_flattened_criterion:
        return

    criterion = payload.pop("criterion", None)
    priority = payload.pop("priority", None)
    requires = payload.pop("requires", None)
    if not isinstance(criterion, str) or not criterion.strip():
        return

    entry = {
        "criterion": criterion.strip(),
        "priority": priority if priority in {"must", "should", "info"} else "must",
        "requires": requires if isinstance(requires, list) else [],
    }
    existing = payload.get("success_criteria")
    if isinstance(existing, list):
        existing.insert(0, entry)
    else:
        payload["success_criteria"] = [entry]


def _strip_execute_bookkeeping_fields(payload: dict) -> None:
    # Executors sometimes include batch-level progress fields in the final
    # envelope. They are useful while working but are not part of execution.json.
    payload.pop("batch_id", None)
    payload.pop("status", None)
    payload.pop("batch_status", None)


_SEVERITY_HINT_CANONICAL = {
    "likely-significant": "likely-significant",
    "likely-minor": "likely-minor",
    "uncertain": "uncertain",
    "significant": "likely-significant",
    "major": "likely-significant",
    "minor": "likely-minor",
    "minor-concern": "likely-minor",
    "low": "likely-minor",
    "cosmetic": "likely-minor",
}


def _normalize_critique_flag_severity(payload: dict) -> None:
    """Map free-form severity_hint values onto the allowed schema enum."""
    flags = payload.get("flags")
    if not isinstance(flags, list):
        return
    for flag in flags:
        if not isinstance(flag, dict):
            continue
        hint = flag.get("severity_hint")
        if not isinstance(hint, str):
            continue
        canonical = _SEVERITY_HINT_CANONICAL.get(hint.lower())
        if canonical is not None:
            flag["severity_hint"] = canonical
        else:
            flag["severity_hint"] = "uncertain"


def _normalize_nested_aliases(payload: dict, schema: dict) -> None:
    """Normalize field aliases in nested array items.

    Models often use synonyms for required fields (e.g. "summary" instead of
    "concern", "detail" instead of "evidence"). This applies the alias mapping
    from merge._FIELD_ALIASES to nested objects in arrays.
    """
    from arnold_pipelines.megaplan.execute.merge import _FIELD_ALIASES

    properties = schema.get("properties", {})
    for field, prop in properties.items():
        if _preferred_schema_type(prop) != "array" or field not in payload:
            continue
        items_schema = prop.get("items", {})
        if items_schema.get("type") != "object":
            continue
        required = items_schema.get("required", [])
        items = payload[field]
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            for req_field in required:
                if req_field in item and item[req_field]:
                    continue  # Already has a non-empty value
                aliases = _FIELD_ALIASES.get(req_field, ())
                for alias in aliases:
                    if alias in item and item[alias]:
                        item[req_field] = item[alias]
                        break


def clean_parsed_payload(payload: dict, schema: dict, step: str) -> None:
    """Normalize a parsed worker payload before validation."""
    # Some providers flatten the single plan success criterion to top-level
    # fields even when the schema asks for success_criteria[]. Normalize that
    # common shape without weakening the plan schema for unrelated keys.
    if step == "plan":
        _normalize_flattened_plan_success_criterion(payload)
    if step == "execute":
        _strip_execute_bookkeeping_fields(payload)
    if step == "review":
        # review_completion_status is a handler-owned scratch extension
        # field (handlers/review.py _REVIEW_SCRATCH_EXTENSION_FIELDS); the
        # capture path re-promotes it later.  Drop it before the strict
        # additionalProperties audit so omp local-strict workers do not fail
        # the exact payload, matching the codex/hermes capture behavior.
        payload.pop("review_completion_status", None)

    # Strip guide-only fields from critique checks (guidance/prior_findings
    # are in the template file to help the model, but not part of the schema)
    if step == "critique" and isinstance(payload.get("checks"), list):
        for check in payload["checks"]:
            if isinstance(check, dict):
                check.pop("guidance", None)
                check.pop("prior_findings", None)

    # Normalize field aliases in nested arrays (e.g. critique flags use
    # "summary" instead of "concern", "detail" instead of "evidence").
    _normalize_nested_aliases(payload, schema)

    # Coerce common model drift in critique flag severity hints so the
    # structural audit does not reject an otherwise usable payload.
    if step == "critique":
        _normalize_critique_flag_severity(payload)


# ---------------------------------------------------------------------------
# Plan markdown recovery
# ---------------------------------------------------------------------------


def _recover_plan_payload_from_raw_markdown(
    payload: dict,
    raw_markdown: str,
) -> dict | None:
    """Promote substantive raw plan markdown without inventing plan steps.

    Some workers return a valid implementation plan as their raw response but
    leave only a summary in the structured ``plan`` field. Recovery is allowed
    only when the raw text has both an implementation-plan heading and at least
    one explicit step; otherwise the normal validation failure remains intact.
    """

    markdown = str(raw_markdown or "").strip()
    if not markdown.startswith("# Implementation Plan"):
        return None
    if not any(line.lstrip().startswith("### Step ") for line in markdown.splitlines()):
        return None
    recovered = dict(payload) if isinstance(payload, dict) else {}
    recovered["plan"] = markdown
    return recovered


__all__ = [
    "clean_parsed_payload",
    "_build_output_template",
    "_deescape_double_encoded_json",
    "_extract_json_from_mutating_tool_markup",
    "_raise_for_terminal_provider_failure",
    "_recover_plan_payload_from_raw_markdown",
    "_sanitize_db_name",
    "_worker_db_path",
]
