"""Hermes Agent worker for megaplan — runs phases via AIAgent with OpenRouter."""

from __future__ import annotations

import hashlib
import html
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import TextIO

import re

from arnold_pipelines.megaplan.types import CliError, MOCK_ENV_VAR, PlanState
from arnold_pipelines.megaplan.prompts import create_hermes_prompt
from arnold_pipelines.megaplan.prompts._projection import check_prompt_size
from arnold_pipelines.megaplan.workers._impl import (
    STEP_SCHEMA_FILENAMES,
    WorkerResult,
    _check_mock_safe,
    _contains_mutating_deepseek_tool_markup,
    _deepseek_tool_markup_names,
    _json_decode_error_for_raw,
    _repair_worker_json_once,
    mock_worker_output,
    session_key_for,
)
from arnold_pipelines.megaplan._core import (
    list_batch_artifacts,
    creative_form_id,
    read_json,
    schemas_root,
    touch_active_step,
)
from arnold.execution.step_invocation import StepInvocation
from arnold_pipelines.megaplan.model_seam import (
    ModelBudgetError,
    ModelStructuralAuditError,
    ModelTier,
    capture_step_output,
    coerce_plan_markdown_payload,
    render_prompt_for_dispatch,
    render_step_message,
)
from arnold_pipelines.megaplan.execute.status_constants import TERMINAL_TASK_STATUSES


def _pre_dispatch_budget_check(
    agent,
    *,
    conversation_history,
    user_message,
    system,
    tool_manifest,
    schema,
    step,
    model_name,
    tier,
    worker,
):
    """Pre-dispatch combined-input budget guard.

    Builds a StepInvocation populating the text-budget fields and routes through
    render_step_message; ModelBudgetError must propagate so an oversized prompt
    cannot reach the provider.
    """
    metadata = {
        "system": system,
        "history": conversation_history,
        "prompt": user_message,
        "tools": tool_manifest,
        "schema": schema,
        "worker": worker,
        "model": model_name,
        "normalized_model": model_name,
        "validation_step": step,
        "tier": tier.value if isinstance(tier, ModelTier) else tier,
    }
    invocation = StepInvocation(kind="model", metadata=metadata)
    try:
        return render_step_message(invocation)
    except ModelBudgetError:
        raise


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


def _normalize_worker_options(worker_options: dict[str, object] | None) -> dict[str, object]:
    """Validate the small picklable worker-options surface used by fan-out callers."""
    if worker_options is None:
        return {}
    if not isinstance(worker_options, dict):
        raise CliError("invalid_args", "Hermes worker options must be a dict")

    normalized: dict[str, object] = {}
    for key in ("output_path", "template_path", "session_db_path"):
        value = worker_options.get(key)
        if value is None:
            continue
        if not isinstance(value, (str, Path)):
            raise CliError("invalid_args", f"Hermes worker option '{key}' must be a string path")
        normalized[key] = str(value)

    for key in ("check_id", "question"):
        value = worker_options.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            raise CliError("invalid_args", f"Hermes worker option '{key}' must be a string")
        normalized[key] = value

    resolved_model = worker_options.get("resolved_model")
    if resolved_model is not None:
        if not isinstance(resolved_model, str) or not resolved_model.strip():
            raise CliError("invalid_args", "Hermes worker option 'resolved_model' must be a non-empty string")
        normalized["resolved_model"] = resolved_model

    max_tokens = worker_options.get("max_tokens")
    if max_tokens is not None:
        try:
            normalized["max_tokens"] = int(max_tokens)
        except (TypeError, ValueError) as exc:
            raise CliError("invalid_args", "Hermes worker option 'max_tokens' must be an int") from exc
        if normalized["max_tokens"] <= 0:
            raise CliError("invalid_args", "Hermes worker option 'max_tokens' must be positive")

    reasoning_config = worker_options.get("reasoning_config")
    if reasoning_config is not None:
        if not isinstance(reasoning_config, dict):
            raise CliError("invalid_args", "Hermes worker option 'reasoning_config' must be a dict")
        normalized["reasoning_config"] = dict(reasoning_config)

    return normalized


def _import_hermes_runtime():
    """Resolve the vendored hermes runtime packages.

    The agent code now lives under ``arnold.agent``; ensure the agent directory
    is on ``sys.path`` so the vendored ``run_agent`` / ``hermes_state`` modules
    are resolvable by their legacy absolute names.
    """
    import importlib
    import sys
    from pathlib import Path

    import arnold.agent  # noqa: F401

    agent_dir = str(Path(arnold.agent.__file__).resolve().parent)
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)

    try:
        from run_agent import AIAgent
        from hermes_state import SessionDB
    except ImportError as exc:
        from arnold_pipelines.megaplan.types import CliError

        raise CliError(
            "agent_deps_missing",
            "hermes backend requires the bundled runtime packages: pip install arnold (or pip install -e . in a source checkout; '[agent]' is only a no-op compatibility extra).",
        ) from exc
    _install_content_tool_call_normalizer(AIAgent)
    return AIAgent, SessionDB


_CONTENT_TOOL_ALIASES = {
    "read": "read_file",
    "read_file": "read_file",
    "file_read": "read_file",
    "search": "search_files",
    "search_files": "search_files",
    "file_search": "search_files",
    "web_extract": "web_extract",
    "fetch_url": "web_extract",
    "web_search": "web_search",
}
_CONTENT_TOOL_NAMES = frozenset(_CONTENT_TOOL_ALIASES)
_CONTENT_ARG_ALIASES = {
    "read_file": {"filePath": "path", "filepath": "path"},
}
_XML_ATTR_RE = re.compile(
    r"(?P<key>[A-Za-z_][A-Za-z0-9_-]*)\s*=\s*"
    r"(?P<quote>[\"'])(?P<value>.*?)(?P=quote)",
    re.DOTALL,
)


def _coerce_xml_tool_value(raw: str) -> object:
    text = html.unescape(raw).strip()
    if re.fullmatch(r"-?\d+", text):
        try:
            return int(text)
        except ValueError:
            return text
    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)", text):
        try:
            return float(text)
        except ValueError:
            return text
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    return text


def _make_content_tool_call(name: str, args: dict[str, object], index: int) -> SimpleNamespace:
    normalized_name = _CONTENT_TOOL_ALIASES.get(name, name)
    for old_key, new_key in _CONTENT_ARG_ALIASES.get(normalized_name, {}).items():
        if old_key in args and new_key not in args:
            args[new_key] = args.pop(old_key)
    return SimpleNamespace(
        id=f"call_content_xml_{index}",
        type="function",
        function=SimpleNamespace(
            name=normalized_name,
            arguments=json.dumps(args, ensure_ascii=False),
        ),
    )


def _parse_xml_attrs(attrs: str) -> dict[str, object]:
    return {
        match.group("key"): _coerce_xml_tool_value(match.group("value"))
        for match in _XML_ATTR_RE.finditer(attrs or "")
    }


def _has_required_content_tool_args(name: str, args: dict[str, object]) -> bool:
    normalized_name = _CONTENT_TOOL_ALIASES.get(name, name)
    for old_key, new_key in _CONTENT_ARG_ALIASES.get(normalized_name, {}).items():
        if old_key in args and new_key not in args:
            args[new_key] = args.pop(old_key)

    required_by_tool = {
        "read_file": "path",
        "search_files": "pattern",
        "web_search": "query",
        "web_extract": "url",
    }
    required = required_by_tool.get(normalized_name)
    if required is None:
        return True
    value = args.get(required)
    return isinstance(value, str) and bool(value.strip())


def _parse_dsml_content_tool_calls(content: str) -> list[SimpleNamespace]:
    calls: list[SimpleNamespace] = []
    invoke_pattern = re.compile(
        r"<[^<>\s]*invoke\b(?P<attrs>[^<>]*\bname=[\"'](?P<name>[^\"']+)[\"'][^<>]*)>"
        r"(?P<body>.*?)"
        r"</[^<>\s]*invoke>",
        re.DOTALL,
    )
    param_pattern = re.compile(
        r"<[^<>\s]*parameter\b(?P<attrs>[^<>]*)>"
        r"(?P<value>.*?)"
        r"</[^<>\s]*parameter>",
        re.DOTALL,
    )
    name_pattern = re.compile(r"\bname=[\"'](?P<name>[^\"']+)[\"']")

    for match in invoke_pattern.finditer(content):
        name = match.group("name").strip().lower()
        if name not in _CONTENT_TOOL_NAMES:
            continue
        args: dict[str, object] = _parse_xml_attrs(match.group("attrs"))
        args.pop("name", None)
        for param in param_pattern.finditer(match.group("body")):
            name_match = name_pattern.search(param.group("attrs"))
            if not name_match:
                continue
            args[name_match.group("name")] = _coerce_xml_tool_value(param.group("value"))
        if not _has_required_content_tool_args(name, args):
            continue
        calls.append(_make_content_tool_call(name, args, len(calls)))
    return calls


def _parse_plain_xml_content_tool_calls(content: str) -> list[SimpleNamespace]:
    calls: list[SimpleNamespace] = []
    names = "|".join(sorted(re.escape(name) for name in _CONTENT_TOOL_NAMES))
    self_closing_pattern = re.compile(
        rf"<(?P<name>{names})\b(?P<attrs>[^<>]*)/>",
        re.DOTALL | re.IGNORECASE,
    )
    tool_pattern = re.compile(
        rf"<(?P<name>{names})\b(?P<attrs>[^>]*)>"
        r"(?P<body>.*?)"
        r"</(?P=name)>",
        re.DOTALL | re.IGNORECASE,
    )
    child_pattern = re.compile(
        r"<(?P<key>[A-Za-z_][A-Za-z0-9_-]*)\b[^>]*>"
        r"(?P<value>.*?)"
        r"</(?P=key)>",
        re.DOTALL,
    )

    for match in self_closing_pattern.finditer(content):
        name = match.group("name").strip().lower()
        args = _parse_xml_attrs(match.group("attrs"))
        if not _has_required_content_tool_args(name, args):
            continue
        calls.append(_make_content_tool_call(name, args, len(calls)))

    for match in tool_pattern.finditer(content):
        name = match.group("name").strip().lower()
        args = _parse_xml_attrs(match.group("attrs"))
        args.update({
            child.group("key"): _coerce_xml_tool_value(child.group("value"))
            for child in child_pattern.finditer(match.group("body"))
        })
        if not _has_required_content_tool_args(name, args):
            continue
        calls.append(_make_content_tool_call(name, args, len(calls)))
    return calls


def _content_xml_tool_calls(content: object) -> list[SimpleNamespace]:
    if not isinstance(content, str) or "<" not in content:
        return []
    return _parse_dsml_content_tool_calls(content) or _parse_plain_xml_content_tool_calls(content)


def _strip_content_xml_tool_calls(content: str) -> str | None:
    names = "|".join(sorted(re.escape(name) for name in _CONTENT_TOOL_NAMES))
    stripped = re.sub(
        r"<[^<>\s]*tool_calls\b[^<>]*>.*?</[^<>\s]*tool_calls>",
        "",
        content,
        flags=re.DOTALL,
    )
    stripped = re.sub(
        rf"<[^<>\s]*invoke\b[^<>]*\bname=[\"'](?:{names})[\"'][^<>]*>"
        r".*?</[^<>\s]*invoke>",
        "",
        stripped,
        flags=re.DOTALL | re.IGNORECASE,
    )
    stripped = re.sub(
        rf"<(?:{names})\b[^>]*/>",
        "",
        stripped,
        flags=re.DOTALL | re.IGNORECASE,
    )
    stripped = re.sub(
        rf"<(?:{names})\b[^>]*>.*?</(?:{names})>",
        "",
        stripped,
        flags=re.DOTALL | re.IGNORECASE,
    ).strip()
    return stripped or None


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


def _normalize_response_content_tool_calls(response) -> None:
    """Promote DeepSeek/Kimi XML content tool calls to OpenAI-style objects."""
    choices = getattr(response, "choices", None)
    if not choices:
        return
    message = getattr(choices[0], "message", None)
    if message is None or getattr(message, "tool_calls", None):
        return
    content = getattr(message, "content", None)
    if isinstance(content, str) and _contains_mutating_deepseek_tool_markup(content):
        recovered = _extract_json_from_mutating_tool_markup(content)
        if recovered:
            message.content = recovered
            return
        names = ", ".join(sorted(_deepseek_tool_markup_names(content)))
        raise CliError(
            "unsupported_tool_call_markup",
            "model emitted unsupported tool-call markup for a write operation "
            f"({names}); refusing to treat it as JSON output",
            extra={
                "raw_output": content,
                "unsupported_tool_call_markup": True,
                "unsupported_write_tool_call": True,
            },
        )
    parsed = _content_xml_tool_calls(content)
    if not parsed:
        return
    message.tool_calls = parsed
    message.content = _strip_content_xml_tool_calls(message.content or "")
    try:
        choices[0].finish_reason = "tool_calls"
    except Exception:
        pass


def _install_content_tool_call_normalizer(AIAgent) -> None:
    if getattr(AIAgent, "_megaplan_content_tool_call_normalizer", False):
        return

    original_api_call = AIAgent._interruptible_api_call
    original_streaming_api_call = AIAgent._interruptible_streaming_api_call

    def _api_call_with_content_tool_calls(self, api_kwargs: dict):
        response = original_api_call(self, api_kwargs)
        _normalize_response_content_tool_calls(response)
        return response

    def _streaming_api_call_with_content_tool_calls(self, api_kwargs: dict, *, on_first_delta: callable = None):
        response = original_streaming_api_call(self, api_kwargs, on_first_delta=on_first_delta)
        _normalize_response_content_tool_calls(response)
        return response

    AIAgent._interruptible_api_call = _api_call_with_content_tool_calls
    AIAgent._interruptible_streaming_api_call = _streaming_api_call_with_content_tool_calls
    AIAgent._megaplan_content_tool_call_normalizer = True


# Fireworks rejects requests with `max_tokens > 4096` unless `stream=true`.
# Direct DeepSeek and Kimi accept high-token non-streaming calls, but streaming
# keeps the transport observable and avoids quiet long-poll gaps.
# Streaming lives entirely inside the worker; downstream callers never see
# streaming semantics.
_HIGH_TOKEN_STREAM_MAX_TOKENS = 4096
_HIGH_TOKEN_STREAM_PROVIDERS = ("fireworks:", "deepseek:", "kimi:")


def _no_op_stream(_text: str) -> None:
    """Sentinel callback that activates run_agent's streaming path.

    AIAgent decides between streaming and non-streaming based on whether a
    stream consumer is registered.  We don't need the deltas, just the side
    effect of forcing ``stream=True`` on the underlying chat.completions call.
    """
    return None
_no_op_stream._megaplan_force_stream = True  # type: ignore[attr-defined]


class _StreamTracker:
    """Real streaming chunk consumer that counts tokens for heartbeat emission.

    Replaces the no-op sentinel so we get observable token throughput
    while still forcing ``stream=True`` on the provider.

    Tracks two independent streams of chunks:

    * ``tokens_emitted`` / ``last_token_at`` — incremented by ``__call__`` which
      is wired in as the agent's ``stream_callback``. This fires only on real
      ``content`` deltas.
    * ``reasoning_emitted`` / ``last_reasoning_at`` — incremented by
      ``on_reasoning`` which is wired in as the agent's ``reasoning_callback``.
      This fires only on ``reasoning_content`` (i.e. "thinking") deltas.

    Splitting the two means a reasoning model that streams thousands of
    ``reasoning_content`` deltas before its first ``content`` delta is no
    longer invisible to the heartbeat (where ``tokens_emitted_so_far`` would
    otherwise sit at 0 for the entire pre-content window — the exact failure
    mode that masked the 21-minute wedge observed on 2026-05-24).
    """

    def __init__(self) -> None:
        self.tokens_emitted: int = 0
        self.last_token_at: float = 0.0
        self.reasoning_emitted: int = 0
        self.last_reasoning_at: float = 0.0
        self.request_id: str | None = None

    def __call__(self, text: str) -> None:
        import time as _t
        self.tokens_emitted += 1  # rough: one "token" per chunk; fine-grained enough for heartbeat
        self.last_token_at = _t.monotonic()

    def on_reasoning(self, text: str) -> None:
        """Increment the reasoning counter. Wired in as ``reasoning_callback``."""
        import time as _t
        self.reasoning_emitted += 1
        self.last_reasoning_at = _t.monotonic()


_StreamTracker._megaplan_force_stream = True  # type: ignore[attr-defined]


def _extract_request_id(result: dict) -> str | None:
    """Best-effort extraction of provider request_id from a run_conversation result."""
    # Check common locations where litellm / the agent may stash it
    for key in ("request_id", "x-request-id", "id"):
        val = result.get(key)
        if isinstance(val, str) and val:
            return val
    # Check nested in headers / response
    headers = result.get("headers") or result.get("response_headers") or {}
    if isinstance(headers, dict):
        for hdr in ("x-request-id", "request-id", "x-amzn-requestid"):
            val = headers.get(hdr)
            if isinstance(val, str) and val:
                return val
    return None


def _emit_llm_start(
    plan_dir: Path,
    step: str,
    model: str | None,
    prompt_hash: str | None,
    is_streaming: bool,
) -> str:
    """Emit an llm_call_start event."""
    call_transaction_id = uuid.uuid4().hex
    try:
        from arnold_pipelines.megaplan.observability.events import emit, EventKind

        provider = (model or "").split(":")[0] if model else None
        emit(
            EventKind.LLM_CALL_START,
            plan_dir=plan_dir,
            phase=step,
            payload={
                "provider": provider,
                "model": model,
                "prompt_hash": prompt_hash,
                "streaming": is_streaming,
                "request_id": None,
                "call_transaction_id": call_transaction_id,
            },
        )
    except Exception:
        pass
    return call_transaction_id


def _emit_llm_end(
    plan_dir: Path,
    step: str,
    tokens_in: int,
    tokens_out: int,
    request_id: str | None,
    model: str | None = None,
    call_transaction_id: str | None = None,
) -> None:
    """Emit an llm_call_end event."""
    try:
        from arnold_pipelines.megaplan.observability.events import emit, EventKind

        emit(
            EventKind.LLM_CALL_END,
            plan_dir=plan_dir,
            phase=step,
            payload={
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "request_id": request_id,
                "model": model,
                "call_transaction_id": call_transaction_id,
            },
        )
    except Exception:
        pass


def _emit_llm_error(
    plan_dir: Path,
    step: str,
    error_message: str,
    retry_after_s: float | None = None,
) -> None:
    """Emit an llm_call_error event."""
    try:
        from arnold_pipelines.megaplan.observability.events import emit, EventKind

        error_code = "unknown"
        if "429" in error_message:
            error_code = "429"
        elif "timeout" in error_message.lower():
            error_code = "timeout"
        elif "context" in error_message.lower():
            error_code = "context_length_exceeded"
        elif "rate" in error_message.lower():
            error_code = "rate_limit"
        emit(
            EventKind.LLM_CALL_ERROR,
            plan_dir=plan_dir,
            phase=step,
            payload={
                "provider_error_code": error_code,
                "retry_after_s": retry_after_s or 0,
                "message": error_message[:500],
            },
        )
    except Exception:
        pass


# ── Worker-level wedge watchdog ──────────────────────────────────────────────
# A coarse, transport-agnostic backstop that sits ABOVE the in-agent
# stream-progress watchdog (run_agent._interruptible_streaming_api_call's
# `stream_progress_stall`, which is keyed on real non-whitespace chars) and the
# shannon subprocess idle watchdog (workers/_impl.run_command's `idle_timeout`).
#
# Those two catch their respective regimes (whitespace-keepalive freeze; silent
# subprocess). This one catches the regime that defeated both on 2026-05-24/28:
# the hermes worker's `run_conversation` producing NO chunk of ANY kind — not
# content, not reasoning, not even a keepalive — for ~17 minutes while the
# `megaplan auto` parent sat alive. It observes the same `_StreamTracker` the
# heartbeat uses and, on a full timeout of zero advancement in BOTH
# `tokens_emitted` and `reasoning_emitted`, calls `agent.interrupt()` (clean
# abort that aborts the in-flight request client and raises InterruptedError
# inside the agent loop) and flags the trip so `_run_attempt` re-raises it as a
# retryable `worker_stall`.
#
# Conservative by construction: it requires the FULL timeout of ZERO real
# progress (any new chunk — content OR reasoning — resets the clock), so a
# healthy long Opus/DeepSeek turn that keeps streaming is never killed.
#
# Tool-call awareness (2026-05-30 false-kill fix): an execute worker legitimately
# fires long terminal/Bash tool calls (e.g. `pytest --cov` over the engine,
# 4–6 min) during which the LLM emits ZERO stream chunks of any kind — it is
# BLOCKED awaiting the tool_result, not wedged. Counting that silence toward the
# stall timeout false-kills a HEALTHY worker mid-task (observed live: a worker
# passed a batch, fired a coverage Bash, sat at 279s, was killed at 300s; the
# retry re-ran the same long command and was re-killed → non-convergence). The
# watchdog therefore distinguishes two states via the agent's own
# ``_executing_tools`` flag (set True by ``AIAgent._execute_tool_calls`` for the
# WHOLE duration of a tool batch, including a single long Bash): while a tool is
# in flight, silence is EXPECTED and the clock is held; chunk-silence only counts
# toward the timeout when the worker is genuinely awaiting LLM tokens (no tool
# running). A truly dead worker — no tool in flight, no tokens — is STILL aborted.
DEFAULT_WORKER_STALL_TIMEOUT_SECONDS = 600.0
_WORKER_STALL_TIMEOUT_FLOOR_SECONDS = 60.0


def _worker_stall_timeout_seconds() -> float:
    """Resolve the worker-wedge watchdog timeout (env-overridable, floored).

    ``HERMES_WORKER_STALL_TIMEOUT`` overrides the 300s default. A misconfigured
    tiny value is clamped to a 60s floor so a healthy-but-slow long turn (e.g. a
    big Opus reasoning burst before its first streamed chunk) can never be
    false-aborted.
    """
    raw = os.getenv("HERMES_WORKER_STALL_TIMEOUT")
    if raw is None:
        return DEFAULT_WORKER_STALL_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_WORKER_STALL_TIMEOUT_SECONDS
    if value <= 0:
        return DEFAULT_WORKER_STALL_TIMEOUT_SECONDS
    return max(value, _WORKER_STALL_TIMEOUT_FLOOR_SECONDS)


def _emit_worker_stalled(
    plan_dir: Path,
    step: str,
    *,
    provider: str | None,
    model: str | None,
    tokens_emitted: int,
    reasoning_emitted: int,
    seconds_since_progress: float,
    timeout_s: float,
    transport: str,
    subprocess_pid: int | None = None,
    stderr_tail: str | None = None,
    exception_type: str | None = None,
    exception_message: str | None = None,
) -> None:
    """Emit a structured ``worker_stalled`` (LLM_CALL_ERROR) diagnostic event.

    Captures everything needed to tell DeepSeek-vs-Claude and
    server-vs-network-vs-silent apart next time, instead of guessing: provider +
    model, tokens/reasoning emitted at abort, seconds since the last real chunk,
    the transport, and (when available) the subprocess pid + a stderr tail and
    any underlying httpx/SSE exception.
    """
    try:
        from arnold_pipelines.megaplan.observability.events import emit, EventKind

        payload: dict = {
            "event": "worker_stalled",
            "provider": provider,
            "model": model,
            "transport": transport,
            "tokens_emitted": tokens_emitted,
            "reasoning_emitted": reasoning_emitted,
            "seconds_since_last_token": round(seconds_since_progress, 1),
            "stall_timeout_s": timeout_s,
            "provider_error_code": "worker_stall",
        }
        if subprocess_pid is not None:
            payload["subprocess_pid"] = subprocess_pid
        if stderr_tail:
            payload["stderr_tail"] = stderr_tail[-2000:]
        if exception_type:
            payload["exception_type"] = exception_type
        if exception_message:
            payload["exception_message"] = exception_message[:500]
        emit(
            EventKind.LLM_CALL_ERROR,
            plan_dir=plan_dir,
            phase=step,
            payload=payload,
        )
    except Exception:
        pass


class _WorkerStallWatchdog:
    """Daemon-thread watchdog that aborts a wedged ``run_conversation``.

    Polls the shared ``_StreamTracker`` every second. The clock resets whenever
    EITHER ``tokens_emitted`` or ``reasoning_emitted`` advances (i.e. any new
    chunk arrived) OR a tool call is in flight on the agent. If none of those
    hold for the full ``timeout`` AND the agent has not already been interrupted,
    it calls ``agent.interrupt()`` — the same clean abort the gateway uses, which
    aborts the in-flight request client and raises ``InterruptedError`` inside
    the agent loop — and records the trip.

    Tool-in-flight is read from ``agent._executing_tools`` (set True by
    ``AIAgent._execute_tool_calls`` for the full duration of a tool batch,
    including a single long Bash/terminal call). A worker BLOCKED awaiting a
    tool_result emits zero stream chunks — that is expected, not a wedge — so we
    must NOT count that silence. Only genuine LLM-token silence (no tool running,
    no new chunk) advances toward the timeout. A truly dead worker (no tool in
    flight, no tokens) is still aborted.

    ``tripped`` is read back by ``_run_attempt`` after ``run_conversation``
    returns/raises so the stall is re-raised as a retryable ``worker_stall``
    rather than mistaken for a normal (empty) completion.
    """

    def __init__(self, agent, tracker: "_StreamTracker", timeout: float) -> None:
        self._agent = agent
        self._tracker = tracker
        self._timeout = timeout
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.tripped = False
        self.seconds_since_progress = 0.0
        self.tokens_at_trip = 0
        self.reasoning_at_trip = 0

    def __enter__(self) -> "_WorkerStallWatchdog":
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _tool_in_flight(self) -> bool:
        """True while the agent is executing a tool batch (incl. a long Bash).

        Reads the agent's own ``_executing_tools`` flag, which ``AIAgent``
        wraps around the WHOLE tool-execution span. Defaults to False if the
        agent doesn't expose it (e.g. a non-AIAgent fake), so the watchdog
        degrades to the original chunk-only behaviour.
        """
        return bool(getattr(self._agent, "_executing_tools", False))

    def _run(self) -> None:
        last_progress_at = time.monotonic()
        last_tokens = self._tracker.tokens_emitted
        last_reasoning = self._tracker.reasoning_emitted
        while not self._stop.wait(1.0):
            now = time.monotonic()
            tokens = self._tracker.tokens_emitted
            reasoning = self._tracker.reasoning_emitted
            if tokens != last_tokens or reasoning != last_reasoning:
                # Any new chunk (content OR reasoning) is real progress.
                last_tokens = tokens
                last_reasoning = reasoning
                last_progress_at = now
                continue
            if self._tool_in_flight():
                # A tool is running (e.g. a multi-minute `pytest --cov`). The
                # LLM is BLOCKED awaiting its tool_result and legitimately emits
                # zero chunks — this is NOT a wedge. Hold the clock so the long
                # tool call cannot trip the stall timeout. The instant the tool
                # returns and we go back to awaiting LLM tokens, the clock
                # resumes from here, so a genuine post-tool wedge is still caught.
                last_progress_at = now
                continue
            if now - last_progress_at >= self._timeout:
                self.tripped = True
                self.seconds_since_progress = now - last_progress_at
                self.tokens_at_trip = tokens
                self.reasoning_at_trip = reasoning
                try:
                    self._agent.interrupt("worker stall watchdog: no stream progress")
                except Exception:
                    pass
                return


def _start_heartbeat(
    plan_dir: Path,
    step: str,
    tracker: "_StreamTracker",
    stop_event: threading.Event,
    *,
    run_id: str | None = None,
) -> None:
    """Start a daemon thread that emits llm_token_heartbeat every ~1s.

    When ``run_id`` is provided the beat also bumps ``state.json``'s
    ``active_step.last_activity_at`` via ``touch_active_step`` whenever the
    stream tracker has observed new tokens since the previous beat. This is the
    *only* liveness signal a silently-streaming provider (e.g. DeepSeek on the
    execute phase) produces: ``quiet_mode`` agents write nothing to stderr, so
    the ``_ActivityStream`` stderr wrapper never fires, and without this the
    phase-idle monitor — which reads ``active_step.last_activity_at`` out of
    ``state.json`` — sees the timestamp frozen at phase-start and false-stalls a
    healthy long-running batch.

    The persisted content write is coalesced in ``_core.state``: each beat that
    observes progress refreshes the in-memory timestamp and bumps the file mtime
    cheaply, while the full state.json re-serialize happens at most once per
    persist interval.
    """

    def _beat() -> None:
        # Start at 0 (not -1) so a stream that emits *no* tokens never produces
        # a spurious first touch — a genuinely wedged stream must still be
        # allowed to idle-timeout.
        last_tokens = 0
        last_reasoning = 0
        while not stop_event.wait(1.0):
            try:
                from arnold_pipelines.megaplan.observability.events import emit, EventKind

                emit(
                    EventKind.LLM_TOKEN_HEARTBEAT,
                    plan_dir=plan_dir,
                    phase=step,
                    payload={
                        "tokens_emitted_so_far": tracker.tokens_emitted,
                        "last_token_at": tracker.last_token_at,
                        # Reasoning-stream visibility: a reasoning model that
                        # spends minutes in the "thinking" phase before its
                        # first content delta now shows non-zero progress here
                        # even though tokens_emitted_so_far is still 0. Without
                        # this, the only liveness signal during a long thinking
                        # phase was the elapsed wall-clock — masking real
                        # wedges (see 2026-05-24 DeepSeek-V4-Pro wedge).
                        "reasoning_emitted_so_far": tracker.reasoning_emitted,
                        "last_reasoning_at": tracker.last_reasoning_at,
                    },
                )
            except Exception:
                pass
            # Liveness: only touch state when the provider is actually
            # producing tokens (content OR reasoning), so a genuinely wedged
            # stream is still allowed to idle-timeout. touch_active_step
            # no-ops unless the on-disk run_id matches, preserving the
            # stale-worker guard.
            content_progress = tracker.tokens_emitted != last_tokens
            reasoning_progress = tracker.reasoning_emitted != last_reasoning
            if run_id and (content_progress or reasoning_progress):
                last_tokens = tracker.tokens_emitted
                last_reasoning = tracker.reasoning_emitted
                try:
                    touch_active_step(
                        plan_dir,
                        run_id=run_id,
                        kind="llm_stream",
                        detail=(
                            f"{tracker.tokens_emitted} chunks, "
                            f"{tracker.reasoning_emitted} reasoning"
                        ),
                    )
                except Exception:
                    pass

    t = threading.Thread(target=_beat, daemon=True)
    t.start()


def _provider_requires_streaming(model: str | None, max_tokens: int | None) -> bool:
    """Return True when this provider/max_tokens pair must use streaming.

    Fireworks requires streaming above the threshold. Direct DeepSeek is kept on
    the same high-token streaming path so `deepseek:*` behaves like the known
    good Fireworks DeepSeek route.
    """
    if not model or not isinstance(model, str):
        return False
    if not model.startswith(_HIGH_TOKEN_STREAM_PROVIDERS):
        return False
    if max_tokens is None:
        return False
    return max_tokens > _HIGH_TOKEN_STREAM_MAX_TOKENS


def _streaming_run_kwargs(model: str | None, max_tokens: int | None, *, plan_dir: Path | None = None) -> dict:
    """Build the run_conversation kwargs needed to force streaming when required.

    Returns only valid run_conversation kwargs — when streaming is forced,
    that's `stream_callback`. The callback IS a _StreamTracker; consumers that
    need the tracker for additional wiring (e.g. reasoning_callback in
    _run_attempt below) should read it back from the `stream_callback` key,
    NOT from a side-channel like `_megaplan_stream_tracker`. The previous
    contract returned both keys pointing at the same tracker, which broke
    forwarders (orchestration/prep_research.py:689,
    orchestration/parallel_critique.py:101, workers/hermes.py:_parse_hermes_result)
    that passed run_kwargs straight into run_conversation — those forwarders
    saw a kwarg the method doesn't accept and crashed with TypeError.
    """
    if _provider_requires_streaming(model, max_tokens):
        return {"stream_callback": _StreamTracker()}
    return {}


# Effort tokens (the profile `--depth` vocabulary) we recognize. They are
# forwarded to the route *unchanged*; each provider normalizes on its own terms.
# DeepSeek's direct API accepts high/max and maps low/medium→high and
# xhigh→max server-side (https://api-docs.deepseek.com/guides/thinking_mode),
# so passing the raw token preserves the `max` budget. OpenRouter only takes
# low/medium/high, so its xhigh/max clamp lives in the agent's request builder
# (run_agent._build_api_kwargs), where the route is known. `minimal` is
# special-cased here to disable thinking outright.
_KNOWN_EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max"})


def _reasoning_config_for_model(
    resolved_model: str | None, effort: str | None = None
) -> dict | None:
    """Return a reasoning override for a hermes model and requested depth.

    Two inputs feed the override:

    * model family — some families (qwen3, deepseek-r1) emit structured output
      inside reasoning/think tags, so thinking is forced *off* and depth is
      ignored. DeepSeek V4 worked through Fireworks without a reasoning
      override, so the direct DeepSeek API route stays aligned: no
      `thinking: disabled` override for `deepseek-v4-*`.
    * effort — the megaplan profile depth (`--depth`). When set, it is forwarded
      as ``{"enabled": True, "effort": <token>}`` and normalized per-route.
      ``minimal`` disables thinking; unknown tokens leave the provider default.

    Family wins over depth: an off-family model stays off regardless of effort.
    """
    model_lower = (resolved_model or "").lower()
    reasoning_off_families = (
        "qwen/qwen3",
        "deepseek/deepseek-r1",
    )
    if any(model_lower.startswith(prefix) for prefix in reasoning_off_families):
        return {"enabled": False}

    if effort is None:
        return None

    token = effort.strip().lower()
    if token == "minimal":
        return {"enabled": False}
    if token not in _KNOWN_EFFORTS:
        return None  # unknown token → leave the provider's default thinking mode
    return {"enabled": True, "effort": token}


def _toolsets_for_phase(phase: str) -> list[str] | None:
    """Return toolsets for a given megaplan phase.

    Execute phase gets terminal + file access.
    Planning and critique phases get local file access by default.
    Prep orchestration stays read-only.
    Web tools are opt-in because local-code plans otherwise tend to waste turns
    trying Firecrawl or ``web_extract(file://...)`` instead of reading the repo.
    Gate and review get file only (judgment, not investigation).
    Finalize is a pure compiler and uses structured JSON response format without tools.
    """
    web_toolsets = ["web"] if _web_tools_enabled_for_hermes() else []
    prep_readonly_phases = {
        "prep",
        "prep-triage",
        "prep-research",
        "prep-distill",
        "prep_triage",
        "prep_research",
        "prep_distill",
    }
    if phase == "execute":
        return ["terminal", "file", *web_toolsets]
    if phase in prep_readonly_phases:
        return ["file-readonly", *web_toolsets]
    if phase in ("plan", "critique", "revise"):
        return ["file", *web_toolsets]
    if phase == "finalize":
        return None
    return ["file"]


def _web_tools_enabled_for_hermes() -> bool:
    raw = os.getenv("MEGAPLAN_HERMES_WEB_TOOLS", "")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Legacy template-phase constants preserved for backward-compatible fallback in
# deferred/unregistered phases. The authoritative template dispatch now reads
# TemplateRegistration.mode from the central registry (T7).
_TEMPLATE_FILE_PHASES = {"finalize", "review", "prep"}
_CUSTOM_TEMPLATE_PHASES = {"critique", "review"}


class _ActivityStream:
    def __init__(self, wrapped: TextIO, *, plan_dir: Path, run_id: str | None) -> None:
        self._wrapped = wrapped
        self._plan_dir = plan_dir
        self._run_id = run_id
        self._last_touch = 0.0

    def write(self, text: str) -> int:
        written = self._wrapped.write(text)
        self._touch("stderr", text)
        return written

    def flush(self) -> None:
        self._wrapped.flush()

    def isatty(self) -> bool:
        return self._wrapped.isatty()

    def fileno(self) -> int:
        return self._wrapped.fileno()

    def __getattr__(self, name: str) -> object:
        return getattr(self._wrapped, name)

    def _touch(self, kind: str, detail: str) -> None:
        now = time.monotonic()
        if now - self._last_touch < 2.0:
            return
        self._last_touch = now
        touch_active_step(
            self._plan_dir,
            run_id=self._run_id,
            kind=kind,
            detail=detail.strip(),
        )


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


def _build_output_template(step: str, schema: dict) -> str:
    """Build a JSON template from a schema for non-critique template-file phases."""
    return _schema_template(schema)


def parse_agent_output(
    agent,
    result: dict,
    *,
    output_path: Path | None,
    schema: dict,
    step: str,
    project_dir: Path,
    plan_dir: Path,
    plan_mode: str = "code",
    run_kwargs: dict | None = None,
    template_seed_text: str | None = None,
    check_id: str | None = None,
    question: str | None = None,
) -> tuple[dict, str]:
    """Parse a Hermes agent result into a structured payload.

    ``run_kwargs`` is forwarded to any follow-up ``agent.run_conversation``
    calls (template / summary fallbacks) so providers that require streaming
    (e.g. Fireworks at high max_tokens) keep streaming on those calls too.
    """
    extra_run_kwargs = run_kwargs or {}
    raw_output = result.get("final_response", "") or ""
    messages = result.get("messages", [])
    if _contains_mutating_deepseek_tool_markup(raw_output):
        names = ", ".join(sorted(_deepseek_tool_markup_names(raw_output)))
        raise CliError(
            "worker_parse_error",
            "Hermes worker returned unsupported tool-call markup for a write "
            f"operation while producing step '{step}' ({names}); the template "
            "was not filled",
            extra={
                "raw_output": raw_output,
                "unsupported_tool_call_markup": True,
                "unsupported_write_tool_call": True,
                **({"check_id": check_id} if check_id else {}),
                **({"question": question} if question else {}),
            },
        )
    parse_error: json.JSONDecodeError | None = _json_decode_error_for_raw(raw_output)
    repair_raw = raw_output
    template_unfilled = False

    # If final_response is empty and the model used tools, the agent loop exited
    # after tool calls without giving the model a chance to output JSON.
    # Make one more API call with the template to force structured output.
    if not raw_output.strip() and messages and any(m.get("tool_calls") for m in messages if m.get("role") == "assistant"):
        try:
            template = _schema_template(schema)
            summary_prompt = (
                "You have finished investigating. Now fill in this JSON template with your findings "
                "and output it as your response. Output ONLY the raw JSON, nothing else.\n\n"
                + template
            )
            # _pre_dispatch_budget_check sentinel: budget guard for dispatch
            _pre_dispatch_budget_check(
                agent,
                conversation_history=messages,
                user_message=summary_prompt,
                system=None,
                tool_manifest=None,
                schema=schema,
                step=step,
                model_name=getattr(agent, "model", None),
                tier=ModelTier.NON_ENFORCED,
                worker="hermes",
            )
            summary_result = agent.run_conversation(
                user_message=summary_prompt,
                conversation_history=messages,
                **extra_run_kwargs,
            )
            raw_output = summary_result.get("final_response", "") or ""
            messages = summary_result.get("messages", messages)
            if raw_output.strip():
                print(f"[hermes-worker] Got JSON from template prompt ({len(raw_output)} chars)", file=sys.stderr)
        except ModelBudgetError:
            raise
        except Exception as exc:
            print(f"[hermes-worker] Template prompt failed: {exc}", file=sys.stderr)

    # For template-file phases, check the template file FIRST — we told the
    # model to write there, so it's the primary output path.
    payload = None
    if output_path and output_path.exists():
        try:
            output_text = output_path.read_text(encoding="utf-8")
            candidate_payload = json.loads(output_text)
            if isinstance(candidate_payload, dict):
                # Check if the model actually filled in findings (not just the empty template)
                has_content = _template_has_content(candidate_payload, step)
                if has_content:
                    payload = candidate_payload
                    print(f"[hermes-worker] Read JSON from template file: {output_path}", file=sys.stderr)
                else:
                    template_unfilled = True
                    print(f"[hermes-worker] Template file exists but has no real content", file=sys.stderr)
        except json.JSONDecodeError as exc:
            parse_error = parse_error or exc
            try:
                repair_raw = output_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        except OSError:
            pass

    if payload is None and step == "plan" and _looks_like_plan_markdown(raw_output):
        payload = coerce_plan_markdown_payload(raw_output)

    # Try parsing the final text response
    if payload is None:
        payload = _parse_json_response(raw_output)
        if payload is None and parse_error is None:
            parse_error = _json_decode_error_for_raw(raw_output)

    # Fallback: some models (GLM-5) put JSON in reasoning/think tags
    # instead of content. Just grab it from there.
    if payload is None and messages:
        payload = _extract_json_from_reasoning(messages)
        if payload is not None:
            print(f"[hermes-worker] Extracted JSON from reasoning tags", file=sys.stderr)

    # Fallback: check all assistant message content fields (not just final_response)
    # The model may have output JSON in an earlier message before making more tool calls
    if payload is None and messages:
        for msg in reversed(messages):
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content", "")
            if isinstance(content, str) and content.strip():
                payload = _parse_json_response(content)
                if payload is not None:
                    print(f"[hermes-worker] Extracted JSON from assistant message content", file=sys.stderr)
                    break

    # Fallback: for execute phase, reconstruct from tool calls + git diff
    if payload is None and step == "execute":
        payload = _reconstruct_execute_payload(messages, project_dir, plan_dir, mode=plan_mode)
        if payload is not None:
            print(f"[hermes-worker] Reconstructed execute payload from tool calls", file=sys.stderr)

    # Fallback: the model may have written the JSON to a different file location
    if payload is None:
        schema_filename = STEP_SCHEMA_FILENAMES.get(step, f"{step}.json")
        for candidate in [
            plan_dir / f"{step}_output.json",  # template file path
            project_dir / schema_filename,
            plan_dir / schema_filename,
            project_dir / f"{step}.json",
        ]:
            if candidate.exists() and candidate != output_path:  # skip if already checked
                try:
                    candidate_text = candidate.read_text(encoding="utf-8")
                    payload = json.loads(candidate_text)
                    print(f"[hermes-worker] Read JSON from file written by model: {candidate}", file=sys.stderr)
                    break
                except json.JSONDecodeError as exc:
                    parse_error = parse_error or exc
                    repair_raw = candidate_text
                except OSError:
                    pass

    # Last resort for template-file phases: the model investigated and produced
    # text findings but didn't write valid JSON anywhere. Ask it to restructure
    # its analysis into JSON. This catches MiniMax's pattern of outputting markdown.
    if payload is None and output_path and messages:
        try:
            template = _schema_template(schema)
            summary_prompt = (
                "You have completed your investigation but your findings were not written as JSON. "
                "Take everything you found and fill in this JSON template. "
                "Output ONLY the raw JSON, nothing else — no markdown, no explanation.\n\n"
                + template
            )
            print(f"[hermes-worker] Attempting summary prompt to extract JSON from investigation", file=sys.stderr)
            # _pre_dispatch_budget_check sentinel: budget guard for dispatch
            _pre_dispatch_budget_check(
                agent,
                conversation_history=messages,
                user_message=summary_prompt,
                system=None,
                tool_manifest=None,
                schema=schema,
                step=step,
                model_name=getattr(agent, "model", None),
                tier=ModelTier.NON_ENFORCED,
                worker="hermes",
            )
            summary_result = agent.run_conversation(
                user_message=summary_prompt,
                conversation_history=messages,
                **extra_run_kwargs,
            )
            summary_output = summary_result.get("final_response", "") or ""
            if summary_output.strip():
                payload = _parse_json_response(summary_output)
                if payload is not None:
                    print(f"[hermes-worker] Got JSON from summary prompt ({len(summary_output)} chars)", file=sys.stderr)
        except ModelBudgetError:
            raise
        except Exception as exc:
            print(f"[hermes-worker] Summary prompt failed: {exc}", file=sys.stderr)

    if payload is None and parse_error is not None:
        repair_result_holder: dict[str, object] = {}

        def _repair_call(repair_prompt: str) -> str:
            # _pre_dispatch_budget_check sentinel: budget guard for dispatch
            _pre_dispatch_budget_check(
                agent,
                conversation_history=messages,
                user_message=repair_prompt,
                system=None,
                tool_manifest=None,
                schema=schema,
                step=step,
                model_name=getattr(agent, "model", None),
                tier=ModelTier.NON_ENFORCED,
                worker="hermes",
            )
            repair_result = agent.run_conversation(
                user_message=repair_prompt,
                conversation_history=messages,
                **extra_run_kwargs,
            )
            repair_result_holder["result"] = repair_result
            return str(repair_result.get("final_response", "") or "")

        try:
            repaired = _repair_worker_json_once(
                step,
                repair_raw or raw_output,
                _repair_call,
                parse_error=parse_error,
                validate=False,
                output_path=output_path,
                template_unchanged=template_unfilled,
                check_id=check_id,
                question=question,
            )
        except CliError as exc:
            raise CliError(
                "worker_parse_error",
                exc.message,
                extra=exc.extra,
            ) from exc
        if repaired is not None:
            payload, raw_output = repaired
            repair_result = repair_result_holder.get("result")
            if isinstance(repair_result, dict):
                messages = repair_result.get("messages", messages)
            print(f"[hermes-worker] Repaired malformed JSON with one retry", file=sys.stderr)

    if payload is None:
        if parse_error is not None:
            repair_result_holder: dict[str, object] = {}

            def _repair_call(repair_prompt: str) -> str:
                repair_result = agent.run_conversation(
                    user_message=repair_prompt,
                    conversation_history=messages,
                    **extra_run_kwargs,
                )
                repair_result_holder["result"] = repair_result
                return str(repair_result.get("final_response", "") or "")

            try:
                repaired = _repair_worker_json_once(
                    step,
                    repair_raw or raw_output,
                    _repair_call,
                    parse_error=parse_error,
                    validate=False,
                    output_path=output_path,
                    template_unchanged=template_unfilled,
                    check_id=check_id,
                    question=question,
                )
            except CliError as exc:
                raise CliError(
                    "worker_parse_error",
                    exc.message,
                    extra=exc.extra,
                ) from exc
            if repaired is not None:
                payload, raw_output = repaired
                repair_result = repair_result_holder.get("result")
                if isinstance(repair_result, dict):
                    messages = repair_result.get("messages", messages)
                print(f"[hermes-worker] Repaired malformed JSON with one retry", file=sys.stderr)

    if payload is None:
        if step == "critique" and template_unfilled:
            context = f" for check {check_id!r}" if check_id else ""
            detail = (
                f"; question {question!r}" if question else ""
            )
            raise CliError(
                "worker_parse_error",
                f"Hermes critique worker did not fill {output_path.name if output_path else 'the critique template'}"
                f"{context}{detail}",
                extra={
                    "raw_output": raw_output,
                    "model_output_parse_error": parse_error is not None,
                    "critique_template_unchanged": True,
                    **({"check_id": check_id} if check_id else {}),
                    **({"question": question} if question else {}),
                },
            )
        raise CliError(
            "worker_parse_error",
            f"Hermes worker returned invalid JSON for step '{step}': "
            f"could not extract JSON from response ({len(raw_output)} chars)",
            extra={"raw_output": raw_output, "model_output_parse_error": parse_error is not None},
        )

    result["final_response"] = raw_output
    result["messages"] = messages
    return payload, raw_output


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


def clean_parsed_payload(payload: dict, schema: dict, step: str) -> None:
    """Normalize a parsed Hermes payload before validation."""
    # Some providers flatten the single plan success criterion to top-level
    # fields even when the schema asks for success_criteria[]. Normalize that
    # common shape without weakening the plan schema for unrelated keys.
    if step == "plan":
        _normalize_flattened_plan_success_criterion(payload)
    if step == "execute":
        _strip_execute_bookkeeping_fields(payload)

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


def _resolve_hermes_cost(result: dict) -> tuple[float, int, int, int]:
    """Return ``(cost_usd, prompt_tokens, completion_tokens, total_tokens)``.

    hermes_cli reports ``estimated_cost_usd=0`` for Fireworks-hosted models
    (no pricing wired in). We fall back to the local Fireworks pricing table
    so phase receipts carry a non-zero cost, passing ``cache_read_tokens``
    so the cached prefix is billed at the cheaper cached rate instead of the
    full uncached input rate. Only a *zero* cost is overridden — a positive
    cost from hermes is trusted as-is.
    """
    cost_usd = float(result.get("estimated_cost_usd", 0.0) or 0.0)
    prompt_tokens = int(result.get("prompt_tokens", 0) or 0)
    completion_tokens = int(result.get("completion_tokens", 0) or 0)
    total_tokens = int(result.get("total_tokens", 0) or 0)
    cached_prompt_tokens = int(result.get("cache_read_tokens", 0) or 0)

    if cost_usd == 0.0 and (prompt_tokens > 0 or completion_tokens > 0):
        model_actual = result.get("model")
        if model_actual:
            from arnold_pipelines.megaplan.pricing import fireworks as fireworks_pricing

            cost_usd = fireworks_pricing.cost_from_usage(
                prompt_tokens,
                completion_tokens,
                model_actual,
                cached_prompt_tokens=cached_prompt_tokens,
            )
    return cost_usd, prompt_tokens, completion_tokens, total_tokens


def run_hermes_step(
    step: str,
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    fresh: bool,
    model: str | None = None,
    effort: str | None = None,
    prompt_override: str | None = None,
    output_path: Path | None = None,
    worker_options: dict[str, object] | None = None,
) -> WorkerResult:
    """Run a megaplan phase using Hermes Agent via OpenRouter.

    Structured output is enforced via the prompt (megaplan prompts already
    embed the JSON schema). The final response is parsed and validated.
    """
    if os.getenv(MOCK_ENV_VAR) == "1":
        _check_mock_safe()
        return mock_worker_output(step, state, plan_dir, prompt_override=prompt_override)
    fresh = fresh or step != "execute"
    if step == "execute" and os.getenv("MEGAPLAN_HERMES_EXECUTE_PERSIST_SESSION") != "1":
        fresh = True

    AIAgent, SessionDB = _import_hermes_runtime()
    # Logging is configured once at process startup by entry points such as
    # the CLI, gateway, and ACP adapter. Do not call configure_logging() from
    # this per-worker path: it mutates process-global logger state and is not
    # safe for in-process worker concurrency.

    project_dir = Path(state["config"]["project_dir"])
    plan_mode = state["config"].get("mode", "code")
    from arnold_pipelines.megaplan.schemas import get_execution_schema_key
    schema_name = (
        get_execution_schema_key(plan_mode, form=creative_form_id(state))
        if step == "execute"
        else STEP_SCHEMA_FILENAMES[step]
    )
    schema = read_json(schemas_root(root) / schema_name)
    normalized_worker_options = _normalize_worker_options(worker_options)
    from arnold_pipelines.megaplan.runtime.key_pool import resolve_model as _resolve_model, acquire_key, report_429
    resolved_model, agent_kwargs = _resolve_model(model)
    effective_resolved_model = str(normalized_worker_options.get("resolved_model") or resolved_model or "")
    explicit_output_path = output_path
    if explicit_output_path is None and normalized_worker_options.get("output_path"):
        explicit_output_path = Path(str(normalized_worker_options["output_path"]))
    template_path = normalized_worker_options.get("template_path")
    template_seed_path = (
        Path(str(template_path))
        if template_path is not None
        else None
    )
    template_seed_text: str | None = None
    if template_seed_path is not None and template_seed_path.exists():
        template_seed_text = template_seed_path.read_text(encoding="utf-8")
    output_path = explicit_output_path

    # Session management
    session_key = session_key_for(step, "hermes", model=model)
    session = state["sessions"].get(session_key, {})
    session_id = session.get("id") if not fresh else None

    # Reload conversation history for session continuity
    conversation_history = None
    if session_id:
        try:
            db = SessionDB()
            conversation_history = db.get_messages_as_conversation(session_id)
        except Exception:
            conversation_history = None

    # Generate new session ID if needed
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())

    toolsets = _toolsets_for_phase(step)
    seam_tier = ModelTier.ENFORCED if not toolsets else ModelTier.NON_ENFORCED

    # Build prompt — megaplan prompts embed the JSON schema, but some models
    # ignore formatting instructions buried in long prompts.  Append a clear
    # reminder so the final response is valid JSON, not markdown.
    prompt_text = prompt_override
    rendered_step = render_prompt_for_dispatch(
        "hermes",
        step,
        state,
        plan_dir,
        root=root,
        model=resolved_model,
        normalized_model=resolved_model,
        tier=seam_tier,
        schema=schema,
        prompt_override=prompt_text,
    )
    prompt = rendered_step.prompt
    # Add web search guidance only when the web toolset is actually enabled.
    # Local project files must be read with file tools; web_extract cannot
    # process file:// URLs or absolute local paths reliably.
    has_web_tools = bool(toolsets and "web" in toolsets)
    if has_web_tools and step in ("plan", "critique", "revise"):
        prompt += (
            "\n\nWEB SEARCH: You have web_search and web_extract tools. "
            "Use file tools for local repository paths; do not use web_extract "
            "for file:// URLs or absolute local filesystem paths. "
            "If the task involves a framework API you're not certain about — "
            "for example a specific Next.js feature, a particular import path, "
            "or a config flag that might have changed between versions — "
            "search for the current documentation before committing to an approach. "
            "Your training data may be outdated for newer framework features."
        )
    elif step == "execute":
        prompt += (
            "\n\nLOCAL FILES: Use file and terminal tools for local repository paths. "
        )
        if has_web_tools:
            prompt += (
                "\n\nWEB SEARCH: You have web_search available. "
                "If you encounter an API you're not sure about while coding, "
                "search before writing — a quick lookup is cheaper than a build failure."
            )
        prompt += (
            "\n\nIMPORTANT: Do NOT rename, modify, or delete EVAL.ts or any test files. "
            "They are used for scoring after execution and must remain unchanged."
        )

    # ── Template dispatch via central registry (T7) ─────────────────────
    # Replaces the historical hardcoded if/elif chain with authoritative
    # TemplateRegistration.mode lookup so file_fill semantics are data-driven
    # rather than step-specific conditional.
    from arnold_pipelines.megaplan.template_registry import get_template_registration

    reg = get_template_registration(step)
    reg_mode = reg.mode if reg else None
    has_file_tool = bool(toolsets and "file" in toolsets)

    def _append_file_fill_instructions(fpath: Path, *, pre_populated: bool = False) -> None:
        """Append strict scratch-file fill instructions to *prompt*."""
        lines = [f"\n\nOUTPUT FILE: {fpath}"]
        if pre_populated:
            lines.append(
                "This file is your ONLY output. It contains a JSON template PRE-POPULATED with "
                "the task IDs and sense-check IDs you must review."
            )
            lines.append(
                "Workflow:\n"
                "1. Read the file to see all the task IDs and sense-check IDs\n"
                "2. Investigate each task — cross-reference executor claims against the git diff\n"
                "3. Fill in every reviewer_verdict, evidence_files, verdict, criteria, and summary\n"
                "4. Write the completed JSON back to the file\n\n"
                "CRITICAL: You MUST fill in ALL task_verdicts and sense_check_verdicts entries. "
                "Do NOT leave reviewer_verdict or verdict fields empty. "
                "Do NOT put your results in a text response. The file is the only output that matters."
            )
        else:
            lines.append(
                "This file is your ONLY output. It contains a JSON template with the structure to fill in.\n"
                "Workflow:\n"
                "1. Start by reading the file to see the structure\n"
                "2. Do your work\n"
                "3. Read the file, add your results, write it back\n\n"
                "Do NOT put your results in a text response. The file is the only output that matters."
            )
        nonlocal prompt
        prompt += "\n".join(lines)

    def _append_inline_json() -> None:
        """Append inline structured-JSON instructions to *prompt*."""
        nonlocal prompt
        template = _schema_template(schema)
        prompt += (
            "\n\nIMPORTANT: Your final response MUST be a single valid JSON object. "
            "Do NOT use markdown. Do NOT wrap in code fences. Output ONLY raw JSON "
            "matching this template:\n\n" + template
        )

    if reg_mode == "file_fill":
        # ── file_fill: create scratch file for EVERY file_fill phase ─
        scratch = reg.scratch_filename
        output_path = output_path or template_seed_path or (plan_dir / scratch)
        if template_seed_text is not None and output_path.parent != plan_dir:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(template_seed_text, encoding="utf-8")
        elif reg.builder is not None and not output_path.exists():
            output_path = reg.builder(plan_dir, state)
        else:
            # Generic fallback for registered file_fill phases without a seed.
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if not output_path.exists():
                output_path.write_text(
                    template_seed_text if template_seed_text is not None
                    else _build_output_template(step, schema),
                    encoding="utf-8",
                )

        if has_file_tool:
            _append_file_fill_instructions(
                output_path, pre_populated=reg.pre_populated
            )
        else:
            # No file tools — still created the scratch (SD3 parity), but
            # give inline instructions since the worker cannot fill files.
            _append_inline_json()
    elif reg_mode in ("deferred", None):
        # ── deferred / unknown: preserve pre-T7 behaviour ────────────
        if step in _TEMPLATE_FILE_PHASES and toolsets:
            output_path = output_path or template_seed_path or (plan_dir / f"{step}_output.json")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                template_seed_text if template_seed_text is not None
                else _build_output_template(step, schema),
                encoding="utf-8",
            )
            _append_file_fill_instructions(output_path)
        else:
            _append_inline_json()
    else:
        # ── markdown_exempt, subloop_exempt, batch_assembly ──────────
        # No structured-output template.  The prompt already carries any
        # needed instructions from create_hermes_prompt / prompt_override.
        pass

    try:
        check_prompt_size(prompt, phase=step)
    except CliError as error:
        if step != "review" or error.code != "prompt_oversized":
            raise
        prompt = compact_review_prompt(
            state,
            plan_dir,
            root,
            prompt_size_error=error.extra,
            projection_capabilities=projection_capabilities,
        )
        if output_path is not None:
            prompt += (
                f"\n\nOUTPUT FILE: {output_path}\n"
                "This file is your ONLY output. It contains a JSON template with the structure to fill in.\n"
                "Workflow:\n"
                "1. Start by reading the file to see the structure\n"
                "2. Do your work\n"
                "3. Read the file, add your results, write it back\n\n"
                "Do NOT put your results in a text response. The file is the only output that matters."
            )
        else:
            template = _schema_template(schema)
            prompt += (
                "\n\nIMPORTANT: Your final response MUST be a single valid JSON object. "
                "Do NOT use markdown. Do NOT wrap in code fences. Output ONLY raw JSON "
                "matching this template:\n\n" + template
            )
        check_prompt_size(prompt, phase=step)

    # Belt-and-suspenders: ensure the seed template is on disk for file_fill
    # phases even when the dispatch block above couldn't write it (e.g. because
    # output_path.parent == plan_dir and the path already existed).  Uses
    # registry lookup instead of hardcoded step membership (T7).
    if (
        output_path is not None
        and template_seed_text is not None
        and reg_mode == "file_fill"
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(template_seed_text, encoding="utf-8")

    rendered_prompt = prompt

    # Build an explicit activity stream that wraps stderr with step-touch
    # side-effects.  This replaces the old approach of mutating sys.stdout
    # and sys.stderr globally — instead the stream is passed explicitly to
    # AIAgent (output_stream) and used via the activity_print helper.
    active_step = state.get("active_step")
    _raw_run_id = active_step.get("run_id") if isinstance(active_step, dict) else None
    run_id = _raw_run_id if isinstance(_raw_run_id, str) else None
    activity_stderr = _ActivityStream(sys.stderr, plan_dir=plan_dir, run_id=run_id)

    def activity_print(*args, **kwargs):
        kwargs.pop('file', None)
        print(*args, file=activity_stderr, **kwargs)

    # Resolve the reasoning override from model family + profile depth. Off
    # families (which return structured output outside the content field) stay
    # disabled; otherwise the requested effort sets the thinking budget. DeepSeek
    # V4 with no effort yields None, matching the Fireworks route's default.
    _reasoning_off = normalized_worker_options.get("reasoning_config")
    if _reasoning_off is None:
        _reasoning_off = _reasoning_config_for_model(
            effective_resolved_model or resolved_model,
            effort,
        )

    # Cap output tokens to prevent repetition loops (Qwen generates 330K+
    # of repeated text without a limit). Sized to fit large finalize.json
    # task graphs and multi-batch execute outputs on plans with ~15+ tasks.
    # Also drives the Fireworks streaming gate below — any value >4096 forces
    # streaming on `fireworks:*` models because Fireworks rejects >4096 max_tokens
    # without `stream=true`.
    agent_max_tokens = int(
        normalized_worker_options.get("max_tokens")
        or (65536 if step == "execute" else 32768)
    )

    db_override = normalized_worker_options.get("session_db_path")
    _hermes_db_path = (
        Path(str(db_override))
        if db_override is not None
        else _worker_db_path(plan_dir, session_key)
    )

    def _make_agent(agent_model: str, extra_kwargs: dict):
        current_agent = AIAgent(
            model=agent_model,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            enabled_toolsets=toolsets,
            session_id=session_id,
            session_db=SessionDB(db_path=_hermes_db_path),
            max_tokens=agent_max_tokens,
            reasoning_config=_reasoning_off,
            output_stream=activity_stderr,
            **extra_kwargs,
        )
        current_agent._print_fn = activity_print
        if seam_tier is ModelTier.ENFORCED:
            current_agent.set_response_format(schema, name=f"megaplan_{step}")
        return current_agent

    def _rewrite_output_template(current_output_path: Path | None) -> Path | None:
        if current_output_path is None:
            return None
        if template_seed_text is not None:
            current_output_path.parent.mkdir(parents=True, exist_ok=True)
            current_output_path.write_text(template_seed_text, encoding="utf-8")
            return current_output_path
        # ── Registry-aware rewrite for fallback/retry paths (T7) ──────
        # Use central registry to decide which template writer to invoke
        # when a retry (e.g. MiniMax→OpenRouter) needs a fresh seed.
        from arnold_pipelines.megaplan.template_registry import get_template_registration
        _retry_reg = get_template_registration(step)
        if (
            _retry_reg is not None
            and _retry_reg.mode == "file_fill"
            and _retry_reg.builder is not None
        ):
            return _retry_reg.builder(plan_dir, state)
        current_output_path.write_text(
            _build_output_template(step, schema),
            encoding="utf-8",
        )
        return current_output_path

    def _failure_reason(exc: Exception) -> str:
        if isinstance(exc, CliError):
            return exc.message
        return str(exc) or exc.__class__.__name__

    def _run_attempt(current_agent, current_output_path: Path | None, *, current_model: str | None = None) -> tuple[dict, dict, str]:
        # Force streaming for providers that require it at this max_tokens
        # (e.g. Fireworks rejects max_tokens > 4096 unless stream=true).
        # The streaming response is reassembled inside run_agent into the
        # same shape non-streaming returns, so the rest of megaplan is
        # unchanged.

        _MAX_EMPTY_RETRIES = 3
        for _empty_attempt in range(1, _MAX_EMPTY_RETRIES + 1):
            run_kwargs = _streaming_run_kwargs(current_model or model, agent_max_tokens, plan_dir=plan_dir)
            tracker = run_kwargs.get("stream_callback")
            # Execute is where both transports wedged (the 2026-05-24/28 silent
            # ~17-min hangs: DeepSeek SSE AND Claude/anthropic). For execute we
            # ALWAYS attach a _StreamTracker so the worker-stall watchdog below
            # has a progress signal regardless of provider — registering a
            # stream_callback also forces streaming on the Claude/anthropic path
            # (run_agent._has_stream_consumers()), giving it the same observable
            # token throughput DeepSeek already had. Non-execute phases keep the
            # prior behaviour (tracker only when the provider requires streaming)
            # so structured-output/finalize calls are untouched.
            if tracker is None and step == "execute":
                tracker = _StreamTracker()
                run_kwargs["stream_callback"] = tracker
            is_streaming = isinstance(tracker, _StreamTracker)

            # Wire the reasoning_callback to the tracker so reasoning_emitted_so_far
            # advances on every reasoning_content delta. Without this, a reasoning
            # model (DeepSeek-V4-Pro, DeepSeek-R1) that streams reasoning before
            # producing its first content delta is invisible to the heartbeat:
            # tokens_emitted_so_far stays at 0 while chunks pour in (the exact
            # failure mode that masked the 21-minute wedge on 2026-05-24).
            if is_streaming and tracker is not None:
                current_agent.reasoning_callback = tracker.on_reasoning
                # Surface silent in-agent retries (TimeoutError / APITimeoutError
                # that the retry loop catches and reissues without emitting any
                # event) as llm_call_error so observability sees the wedge fast.
                current_agent._megaplan_retry_error_callback = (
                    lambda info: _emit_llm_error(
                        plan_dir,
                        step,
                        (
                            f"{info.get('error_type', 'APIError')}: "
                            f"{info.get('error_message', '')} "
                            f"(retry {info.get('retry_count', 0)}/"
                            f"{info.get('max_retries', 0)}, "
                            f"streaming_timeout="
                            f"{info.get('is_streaming_timeout', False)})"
                        ),
                        retry_after_s=None,
                    )
                )

            # Emit llm_call_start
            prompt_text = rendered_prompt or prompt_override or ""
            prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:16] if prompt_text else None
            call_transaction_id = _emit_llm_start(
                plan_dir,
                step,
                effective_resolved_model or resolved_model,
                prompt_hash,
                is_streaming,
            )

            # Heartbeat thread for streaming calls
            heartbeat_stop = threading.Event()
            if is_streaming and tracker is not None:
                _start_heartbeat(plan_dir, step, tracker, heartbeat_stop, run_id=run_id)

            # Worker-wedge watchdog: aborts run_conversation if the tracker sees
            # ZERO new chunks (content or reasoning) for the full stall timeout.
            # Active whenever a tracker is wired (all execute calls + any
            # streaming non-execute call), covering BOTH the DeepSeek SSE and the
            # Claude/anthropic transports.
            from contextlib import nullcontext

            watchdog: "_WorkerStallWatchdog | None" = None
            if is_streaming and tracker is not None:
                watchdog = _WorkerStallWatchdog(
                    current_agent, tracker, _worker_stall_timeout_seconds()
                )
            watchdog_ctx = watchdog if watchdog is not None else nullcontext()

            def _raise_worker_stall(cause: BaseException | None) -> "CliError":
                """Emit the worker_stalled diagnostic + build the retryable error.

                Used for BOTH abort shapes: the agent loop catches
                ``InterruptedError`` internally and RETURNS a result with
                ``interrupted=True`` (the common case), but a deeper streaming
                abort can also propagate ``InterruptedError`` — both must land
                here so the stall is never mistaken for a normal completion.
                """
                timeout_s = _worker_stall_timeout_seconds()
                _emit_worker_stalled(
                    plan_dir,
                    step,
                    provider=(current_model or model or "").split(":", 1)[0] or None,
                    model=effective_resolved_model or resolved_model,
                    tokens_emitted=watchdog.tokens_at_trip,
                    reasoning_emitted=watchdog.reasoning_at_trip,
                    seconds_since_progress=watchdog.seconds_since_progress,
                    timeout_s=timeout_s,
                    transport="hermes_in_process",
                    exception_type=type(cause).__name__ if cause is not None else None,
                    exception_message=str(cause) if cause is not None else None,
                )
                return CliError(
                    "worker_stall",
                    (
                        f"Hermes worker stalled on step '{step}': no stream "
                        f"progress (content or reasoning) for "
                        f"{watchdog.seconds_since_progress:.0f}s "
                        f"(timeout={timeout_s:.0f}s, "
                        f"tokens={watchdog.tokens_at_trip}, "
                        f"reasoning={watchdog.reasoning_at_trip})"
                    ),
                    extra={"raw_output": ""},
                )

            # _pre_dispatch_budget_check sentinel: budget guard for dispatch
            _pre_dispatch_budget_check(
                current_agent,
                conversation_history=conversation_history,
                user_message=prompt,
                system=None,
                tool_manifest=list(toolsets) if toolsets else None,
                schema=schema,
                step=step,
                model_name=effective_resolved_model or resolved_model or current_model,
                tier=seam_tier,
                worker="hermes",
            )
            try:
                with watchdog_ctx:
                    current_result = current_agent.run_conversation(
                        user_message=prompt,
                        conversation_history=conversation_history,
                        **run_kwargs,
                    )
            except InterruptedError as interrupt_exc:
                # Defensive: a deeper streaming abort propagated InterruptedError.
                if watchdog is not None and watchdog.tripped:
                    raise _raise_worker_stall(interrupt_exc) from interrupt_exc
                raise
            finally:
                if is_streaming:
                    heartbeat_stop.set()
                # Clear the retry-error hook so it doesn't leak across attempts.
                if is_streaming and tracker is not None:
                    try:
                        current_agent._megaplan_retry_error_callback = None
                    except Exception:
                        pass
                # Clear any interrupt flag so a retry on the same agent object
                # (or a reused session) starts clean.
                try:
                    current_agent.clear_interrupt()
                except Exception:
                    pass

            # Common abort shape: the agent loop caught our watchdog's
            # InterruptedError internally and RETURNED a result flagged
            # interrupted=True. Detect the tripped watchdog here so a wedge is
            # surfaced as a retryable worker_stall rather than parsed as a
            # (truncated/empty) normal completion.
            if watchdog is not None and watchdog.tripped:
                raise _raise_worker_stall(None)

            _raise_for_terminal_provider_failure(current_result, step=step)

            try:
                current_payload, current_raw_output = parse_agent_output(
                    current_agent,
                    current_result,
                    output_path=current_output_path,
                    schema=schema,
                    step=step,
                    project_dir=project_dir,
                    plan_dir=plan_dir,
                    plan_mode=plan_mode,
                    run_kwargs=run_kwargs,
                    template_seed_text=template_seed_text,
                    check_id=str(normalized_worker_options.get("check_id") or "") or None,
                    question=str(normalized_worker_options.get("question") or "") or None,
                )
            except CliError as exc:
                # Retry on transient empty responses (e.g. context overflow
                # or API hiccup that returns nothing). Uses exponential
                # backoff: 2s, 4s, 8s.
                if (
                    _empty_attempt < _MAX_EMPTY_RETRIES
                    and exc.code == "worker_parse_error"
                    and "0 chars" in exc.message
                ):
                    delay = 2**_empty_attempt
                    print(
                        f"[hermes-worker] Empty response on attempt "
                        f"{_empty_attempt}/{_MAX_EMPTY_RETRIES}, "
                        f"retrying in {delay}s...",
                        file=sys.stderr,
                    )
                    time.sleep(delay)
                    continue
                raise

            clean_parsed_payload(current_payload, schema, step)
            messages = current_result.get("messages", [])

            # Emit llm_call_end
            request_id = _extract_request_id(current_result)
            tokens_in = int(current_result.get("prompt_tokens", 0) or 0)
            tokens_out = int(current_result.get("completion_tokens", 0) or 0)
            _emit_llm_end(
                plan_dir,
                step,
                tokens_in,
                tokens_out,
                request_id,
                model=effective_resolved_model or resolved_model,
                call_transaction_id=call_transaction_id,
            )

            try:
                capture_outcome = capture_step_output(
                    StepInvocation(
                        kind="model",
                        metadata={
                            "tier": seam_tier.value,
                            "worker": "hermes",
                            "model": effective_resolved_model or resolved_model,
                            "normalized_model": effective_resolved_model or resolved_model,
                            "validation_step": step,
                            "compatibility_validation_step": step,
                            "schema": schema,
                        },
                    ),
                    current_payload,
                )
                current_payload = dict(capture_outcome.legacy_payload)
            except (CliError, ModelStructuralAuditError) as error:
                # For execute, try reconstructed payload if validation fails
                reconstructed: dict | None = None
                if step == "execute":
                    reconstructed = _reconstruct_execute_payload(messages, project_dir, plan_dir, mode=plan_mode)
                if reconstructed is not None:
                    try:
                        capture_outcome = capture_step_output(
                            StepInvocation(
                                kind="model",
                                metadata={
                                    "tier": seam_tier.value,
                                    "worker": "hermes",
                                    "model": effective_resolved_model or resolved_model,
                                    "normalized_model": effective_resolved_model or resolved_model,
                                    "validation_step": step,
                                    "compatibility_validation_step": step,
                                    "schema": schema,
                                },
                            ),
                            reconstructed,
                        )
                        current_payload = dict(capture_outcome.legacy_payload)
                        print(
                            f"[hermes-worker] Using reconstructed {step} payload (original failed validation)",
                            file=activity_stderr,
                        )
                        error = None
                    except (CliError, ModelStructuralAuditError):
                        pass
                if error is not None:
                    if isinstance(error, CliError):
                        raise CliError(error.code, error.message, extra={"raw_output": current_raw_output}) from error
                    raise CliError(
                        "worker_structural_audit_failed",
                        str(error),
                        extra={"raw_output": current_raw_output},
                    ) from error

            return current_result, current_payload, current_raw_output

        # Exhausted all retries -- this line is unreachable because the last
        # iteration either returns or propagates the exception.
        raise CliError(
            "worker_parse_error",
            f"Hermes worker returned empty response for step '{step}' after "
            f"{_MAX_EMPTY_RETRIES} attempts",
        )

    agent = _make_agent(resolved_model, agent_kwargs)
    # Don't set response_format when tools are enabled — many models
    # (Qwen, GLM-5) hang or produce garbage when both are active.
    # The JSON template in the prompt is sufficient; _parse_json_response
    # handles code fences and markdown wrapping.

    # Install the project_dir sandbox whenever a toolset is active.  This
    # pins TERMINAL_CWD and wraps the terminal/write_file/patch handlers so
    # the model can't escape the worktree even if its prompt context tells
    # it to (see megaplan/sandbox.py).  Phases without tools (no toolsets)
    # don't need it.
    from contextlib import ExitStack
    _sandbox_stack = ExitStack()
    if toolsets:
        from arnold_pipelines.megaplan.runtime.sandbox import install_sandbox
        _sandbox_stack.enter_context(install_sandbox(project_dir))

    # Run — with fallback to OpenRouter for MiniMax if primary API fails
    started = time.monotonic()
    try:
        try:
            result, payload, raw_output = _run_attempt(agent, output_path)
        except Exception as exc:
            # Emit llm_call_error
            _emit_llm_error(plan_dir, step, str(exc))
            provider = (model or "").split(":", 1)[0] if model else "unknown"
            from arnold_pipelines.megaplan.orchestration.phase_result import ExternalError
            external_error = ExternalError.from_exception(exc, provider=provider)
            # Report 429 to key pool so it cools down this key
            exc_str = str(exc)
            if "429" in exc_str:
                if model and model.startswith("minimax:"):
                    report_429("minimax", agent_kwargs.get("api_key", ""), cooldown_secs=60)
                elif model and model.startswith("zhipu:"):
                    # Quota exhaustion needs a long cooldown (hours, not seconds)
                    cooldown = 3600 if "Limit Exhausted" in exc_str else 120
                    report_429("zhipu", agent_kwargs.get("api_key", ""), cooldown_secs=cooldown)
                    print(f"[hermes-worker] Z.AI key cooled down for {cooldown}s", file=activity_stderr)
                elif model and model.startswith("kimi:"):
                    report_429("kimi", agent_kwargs.get("api_key", ""), cooldown_secs=120)
                    print(f"[hermes-worker] Kimi key cooled down for 120s", file=activity_stderr)
                elif model and model.startswith("deepseek:"):
                    report_429("deepseek", agent_kwargs.get("api_key", ""), cooldown_secs=120)
                elif model and model.startswith("fireworks:"):
                    report_429("fireworks", agent_kwargs.get("api_key", ""), cooldown_secs=120)
            if model and model.startswith("minimax:"):
                or_key = acquire_key("openrouter")
                if or_key:
                    if isinstance(exc, CliError):
                        print(
                            f"[hermes-worker] MiniMax returned bad content ({_failure_reason(exc)}), falling back to OpenRouter",
                            file=activity_stderr,
                        )
                    else:
                        print(f"[hermes-worker] MiniMax failed ({exc}), falling back to OpenRouter", file=activity_stderr)
                    from arnold_pipelines.megaplan.runtime.key_pool import minimax_openrouter_model
                    fallback_model = minimax_openrouter_model(model[len("minimax:"):])
                    output_path = _rewrite_output_template(output_path)
                    agent = _make_agent(
                        fallback_model,
                        {
                            "base_url": "https://openrouter.ai/api/v1",
                            "api_key": or_key,
                        },
                    )
                    try:
                        result, payload, raw_output = _run_attempt(agent, output_path)
                    except Exception as fallback_exc:
                        _emit_llm_error(plan_dir, step, str(fallback_exc))
                        fallback_error = ExternalError.from_exception(
                            fallback_exc,
                            provider="openrouter",
                        )
                        raise CliError(
                            "worker_error",
                            (
                                f"Hermes worker failed for step '{step}' "
                                f"(both MiniMax and OpenRouter): primary={_failure_reason(exc)}; "
                                f"fallback={_failure_reason(fallback_exc)}"
                            ),
                            extra={
                                "session_id": session_id,
                                "_external_error": (
                                    external_error.to_dict()
                                    if external_error is not None
                                    else None
                                ),
                                "_fallback_external_error": (
                                    fallback_error.to_dict()
                                    if fallback_error is not None
                                    else None
                                ),
                            },
                        ) from fallback_exc
                elif isinstance(exc, CliError):
                    raise
                else:
                    raise CliError(
                        "worker_error",
                        f"Hermes worker failed for step '{step}': {exc}",
                        extra={
                            "session_id": session_id,
                            "_external_error": (
                                external_error.to_dict()
                                if external_error is not None
                                else None
                            ),
                        },
                    ) from exc
            elif isinstance(exc, CliError):
                raise
            else:
                raise CliError(
                    "worker_error",
                    f"Hermes worker failed for step '{step}': {exc}",
                    extra={
                        "session_id": session_id,
                        "_external_error": (
                            external_error.to_dict()
                            if external_error is not None
                            else None
                        ),
                    },
                ) from exc
    finally:
        _sandbox_stack.close()
    elapsed_ms = int((time.monotonic() - started) * 1000)

    cost_usd, prompt_tokens, completion_tokens, total_tokens = _resolve_hermes_cost(result)

    # Emit cost_recorded
    try:
        from arnold_pipelines.megaplan.observability.events import emit, EventKind
        emit(
            EventKind.COST_RECORDED,
            plan_dir=plan_dir,
            phase=step,
            payload={
                "request_id": _extract_request_id(result),
                "cost_usd": float(cost_usd),
                "provider": (
                    (effective_resolved_model or resolved_model or "").split(":")[0]
                    if (effective_resolved_model or resolved_model)
                    else None
                ),
                "model": result.get("model") or effective_resolved_model or resolved_model,
            },
        )
    except Exception:
        pass

    return WorkerResult(
        payload=payload,
        raw_output=raw_output,
        duration_ms=elapsed_ms,
        cost_usd=float(cost_usd),
        session_id=session_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        rendered_prompt=rendered_prompt,
        model_actual=result.get("model"),
    )


def _extract_json_from_reasoning(messages: list) -> dict | None:
    """Extract JSON from the last assistant message's reasoning field.

    Some models (GLM-5) wrap their entire response in think/reasoning tags,
    so the content field is empty but reasoning contains valid JSON.
    """
    for msg in reversed(messages):
        if msg.get("role") != "assistant":
            continue
        for field in ("reasoning", "reasoning_content"):
            text = msg.get(field)
            if isinstance(text, str) and text.strip():
                result = _parse_json_response(text)
                if result is not None:
                    return result
        # Also check reasoning_details (list of dicts with "content")
        details = msg.get("reasoning_details")
        if isinstance(details, list):
            for item in details:
                if isinstance(item, dict):
                    text = item.get("content", "")
                    if isinstance(text, str) and text.strip():
                        result = _parse_json_response(text)
                        if result is not None:
                            return result
    return None


def _reconstruct_execute_payload(
    messages: list,
    project_dir: Path,
    plan_dir: Path,
    *,
    mode: str = "code",
) -> dict | None:
    """Reconstruct an execute phase response from tool calls and git state.

    When the model did the work via tools but couldn't produce the JSON
    report (e.g., response trapped in think tags, or timeout), build the
    response from what actually happened.
    """
    import subprocess

    # Collect tool calls from messages
    tool_calls = []
    files_changed = set()
    commands_run = []
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            if not isinstance(fn, dict):
                continue
            name = fn.get("name", "")
            args_raw = fn.get("arguments", "{}")
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except (json.JSONDecodeError, TypeError):
                args = {}
            if not isinstance(args, dict):
                args = {}

            tool_calls.append({"name": name, "args": args})

            if name in ("write_file", "patch", "edit_file", "apply_patch"):
                path = args.get("path", "")
                if isinstance(path, str) and path:
                    try:
                        rel = str(Path(path).relative_to(project_dir))
                    except ValueError:
                        rel = path
                    files_changed.add(rel)
            elif name in ("terminal", "shell"):
                cmd = args.get("command", "")
                if isinstance(cmd, str) and cmd:
                    commands_run.append(cmd)

    if mode != "doc":
        try:
            diff_result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=project_dir,
                capture_output=True, text=True, timeout=10, check=False,
            )
            if diff_result.returncode == 0:
                for line in diff_result.stdout.splitlines():
                    if line.strip():
                        files_changed.add(line.strip())
        except Exception:
            pass

        try:
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_dir,
                capture_output=True, text=True, timeout=10, check=False,
            )
            if status_result.returncode == 0:
                for line in status_result.stdout.splitlines():
                    if line.startswith("?? ") or line.startswith("A  ") or line.startswith("M  "):
                        fname = line[3:].strip()
                        if fname and not fname.startswith(".megaplan/"):
                            files_changed.add(fname)
        except Exception:
            pass

    if not tool_calls and not files_changed:
        return None

    def _batch_sort_key(path: Path, prefix: str) -> int:
        stem = path.stem
        try:
            return int(stem[len(prefix) :])
        except ValueError:
            return -1

    def _validated_task_updates(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        raw_updates = payload.get("task_updates")
        if not isinstance(raw_updates, list):
            return []
        valid: list[dict[str, Any]] = []
        for item in raw_updates:
            if not isinstance(item, dict):
                continue
            task_id = item.get("task_id")
            status = item.get("status")
            executor_notes = item.get("executor_notes")
            files_changed = item.get("files_changed")
            commands_run = item.get("commands_run")
            if not isinstance(task_id, str) or not task_id.strip():
                continue
            if status not in TERMINAL_TASK_STATUSES:
                continue
            if not isinstance(executor_notes, str) or not executor_notes.strip():
                continue
            if not isinstance(files_changed, list) or not isinstance(commands_run, list):
                continue
            valid.append(item)
        return valid

    def _validated_sense_check_acknowledgments(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        raw_acks = payload.get("sense_check_acknowledgments")
        if not isinstance(raw_acks, list):
            return []
        valid: list[dict[str, Any]] = []
        for item in raw_acks:
            if not isinstance(item, dict):
                continue
            sense_check_id = item.get("sense_check_id")
            executor_note = item.get("executor_note")
            if not isinstance(sense_check_id, str) or not sense_check_id.strip():
                continue
            if not isinstance(executor_note, str) or not executor_note.strip():
                continue
            valid.append(item)
        return valid

    latest_batch_output_payload: dict[str, Any] | None = None
    latest_batch_output_path: Path | None = None
    batch_output_files = sorted(
        plan_dir.glob("execute_batch_*_output.json"),
        key=lambda path: _batch_sort_key(path, "execute_batch_"),
        reverse=True,
    )
    for batch_output_path in batch_output_files:
        try:
            loaded = json.loads(batch_output_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(loaded, dict):
            continue
        latest_batch_output_payload = loaded
        latest_batch_output_path = batch_output_path
        break

    task_updates: list[dict[str, Any]] = []
    sense_check_acknowledgments: list[dict[str, Any]] = []
    if latest_batch_output_payload is not None:
        task_updates.extend(_validated_task_updates(latest_batch_output_payload))
        sense_check_acknowledgments.extend(
            _validated_sense_check_acknowledgments(latest_batch_output_payload)
        )

    # If the scratch output is missing or contains no usable controlled-field
    # updates, fall back to the latest audited checkpoint.  Batch-scope
    # authority validation still rejects any update that does not belong to
    # the active batch; reconstruction must not promote pending placeholders.
    if not task_updates:
        checkpoint_files = sorted(list_batch_artifacts(plan_dir), reverse=True)
        for checkpoint_path in checkpoint_files:
            try:
                cp_data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            checkpoint_updates = _validated_task_updates(cp_data)
            if checkpoint_updates:
                task_updates.extend(checkpoint_updates)
                sense_check_acknowledgments.extend(
                    _validated_sense_check_acknowledgments(cp_data)
                )
                break

    output_text = (
        latest_batch_output_payload.get("output")
        if isinstance(latest_batch_output_payload, dict)
        else None
    )
    if not isinstance(output_text, str) or not output_text.strip():
        output_text = None

    extra_deviations: list[str] = []
    if isinstance(latest_batch_output_payload, dict):
        raw_deviations = latest_batch_output_payload.get("deviations")
        if isinstance(raw_deviations, list):
            extra_deviations.extend(
                item for item in raw_deviations if isinstance(item, str) and item.strip()
            )

    if mode == "doc":
        sections_written = sorted(
            {
                section
                for tu in task_updates
                for section in tu.get("sections_written", [])
                if isinstance(section, str) and section.strip()
            }
        )
        deviations = [
            "Execute response reconstructed from tool calls — model failed to produce JSON report."
        ]
        for deviation in extra_deviations:
            if deviation not in deviations:
                deviations.append(deviation)
        return {
            "output": output_text
            or f"[Reconstructed from tool calls] Made {len(tool_calls)} tool calls, wrote {len(sections_written)} sections.",
            "sections_written": sections_written,
            "commands_run": [],
            "deviations": deviations,
            "task_updates": task_updates,
            "sense_check_acknowledgments": sense_check_acknowledgments,
        }

    files_list = sorted(files_changed)
    if isinstance(latest_batch_output_payload, dict):
        raw_files_changed = latest_batch_output_payload.get("files_changed")
        if isinstance(raw_files_changed, list):
            files_list = sorted(
                {
                    *files_list,
                    *(
                        item
                        for item in raw_files_changed
                        if isinstance(item, str) and item.strip()
                    ),
                }
            )
        raw_commands_run = latest_batch_output_payload.get("commands_run")
        if isinstance(raw_commands_run, list):
            for command in raw_commands_run:
                if isinstance(command, str) and command and command not in commands_run:
                    commands_run.append(command)
    deviations = [
        "Execute response reconstructed from tool calls — model failed to produce JSON report."
    ]
    for deviation in extra_deviations:
        if deviation not in deviations:
            deviations.append(deviation)
    return {
        "output": output_text
        or f"[Reconstructed from tool calls] Made {len(tool_calls)} tool calls, changed {len(files_list)} files.",
        "files_changed": files_list,
        "commands_run": commands_run,
        "deviations": deviations,
        "task_updates": task_updates,
        "sense_check_acknowledgments": sense_check_acknowledgments,
    }


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


def _parse_json_response(text: str) -> dict | None:
    """Extract a JSON object from a model response.

    Tries in order:
    1. Direct JSON parse
    2. Repair common JSON issues (escaped newlines in structural positions)
    3. Extract from ```json ... ``` code block
    4. Find first { ... } JSON object in the text

    Each step also tries the repaired version.
    """
    text = text.strip()
    if not text:
        return None

    for candidate in [text, _repair_json(text)]:
        # Direct parse
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

        # Extract from code block
        import re
        code_block = re.search(r'```(?:json)?\s*\n(.*?)\n```', candidate, re.DOTALL)
        if code_block:
            block_text = code_block.group(1)
            for block_candidate in [block_text, _repair_json(block_text)]:
                try:
                    parsed = json.loads(block_candidate)
                    if isinstance(parsed, dict):
                        return parsed
                except (json.JSONDecodeError, TypeError):
                    pass

        # Find first JSON object
        decoder = json.JSONDecoder()
        for i, ch in enumerate(candidate):
            if ch != '{':
                continue
            try:
                parsed, end = decoder.raw_decode(candidate[i:])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue

    return None


def _looks_like_plan_markdown(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped:
        return False
    if stripped.startswith("# "):
        return True
    if "## Overview" in text:
        return True
    return bool(re.search(r"(?m)^#{2,3}\s+Step\s+\d+:\s+.+$", text))


def _repair_json(text: str) -> str:
    """Fix common JSON issues from LLM output.

    Models sometimes mix escaped and literal newlines, or produce
    backslash-n outside of strings where real whitespace is needed.
    """
    # Replace literal \n that appear outside of JSON strings with actual newlines.
    # This handles the case where the model outputs [\n    "item"] instead of
    # [\n    "item"] — the \n is structural whitespace, not string content.
    result = []
    in_string = False
    escape = False
    i = 0
    while i < len(text):
        ch = text[i]
        if escape:
            result.append(ch)
            escape = False
            i += 1
            continue
        if ch == '\\' and in_string:
            escape = True
            result.append(ch)
            i += 1
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            result.append(ch)
            i += 1
            continue
        # Outside a string, replace \n with actual newline
        if not in_string and ch == '\\' and i + 1 < len(text) and text[i + 1] == 'n':
            result.append('\n')
            i += 2
            continue
        result.append(ch)
        i += 1
    return ''.join(result)
