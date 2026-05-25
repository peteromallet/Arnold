"""Hermes Agent worker for megaplan — runs phases via AIAgent with OpenRouter."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import TextIO

import re

from megaplan.types import CliError, MOCK_ENV_VAR, PlanState
from megaplan.workers._impl import (
    STEP_SCHEMA_FILENAMES,
    WorkerResult,
    mock_worker_output,
    session_key_for,
    validate_payload,
)
from megaplan._core import creative_form_id, read_json, schemas_root, touch_active_step
from megaplan.forms.provocations import select_active_checks
from megaplan.prompts import create_hermes_prompt


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


def _import_hermes_runtime():
    import megaplan.agent  # noqa: F401

    try:
        from run_agent import AIAgent
        from hermes_state import SessionDB
    except ImportError as exc:
        from megaplan.types import CliError

        raise CliError(
            "agent_deps_missing",
            "hermes backend requires: pip install 'megaplan-harness[agent]'",
        ) from exc
    return AIAgent, SessionDB


# Fireworks rejects requests with `max_tokens > 4096` unless `stream=true`.
# Direct DeepSeek accepts high-token non-streaming calls, but streaming keeps
# the transport closer to the Fireworks path and avoids quiet long-poll gaps.
# Streaming lives entirely inside the worker; downstream callers never see
# streaming semantics.
_HIGH_TOKEN_STREAM_MAX_TOKENS = 4096
_HIGH_TOKEN_STREAM_PROVIDERS = ("fireworks:", "deepseek:")


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
) -> None:
    """Emit an llm_call_start event."""
    try:
        from megaplan.observability.events import emit, EventKind

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
            },
        )
    except Exception:
        pass


def _emit_llm_end(
    plan_dir: Path,
    step: str,
    tokens_in: int,
    tokens_out: int,
    request_id: str | None,
) -> None:
    """Emit an llm_call_end event."""
    try:
        from megaplan.observability.events import emit, EventKind

        emit(
            EventKind.LLM_CALL_END,
            plan_dir=plan_dir,
            phase=step,
            payload={
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "request_id": request_id,
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
        from megaplan.observability.events import emit, EventKind

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
    phase-idle monitor — which watches the ``state.json`` mtime — sees the file
    frozen at phase-start and false-stalls a healthy long-running batch.
    """

    def _beat() -> None:
        # Start at 0 (not -1) so a stream that emits *no* tokens never produces
        # a spurious first touch — a genuinely wedged stream must still be
        # allowed to idle-timeout.
        last_tokens = 0
        last_reasoning = 0
        while not stop_event.wait(1.0):
            try:
                from megaplan.observability.events import emit, EventKind

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

    Execute phase gets full terminal + file + web access.
    Planning and critique phases get file + web (verify APIs against docs).
    Prep orchestration stays read-only even when it needs file/web research.
    Gate and review get file only (judgment, not investigation).
    Finalize is a pure compiler and uses structured JSON response format without tools.
    """
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
        return ["terminal", "file", "web"]
    if phase in prep_readonly_phases:
        return ["file-readonly", "web"]
    if phase in ("plan", "critique", "revise"):
        return ["file", "web"]
    if phase == "finalize":
        return None
    return ["file"]


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
    # For other phases: any non-empty array or non-empty string
    return any(
        (isinstance(v, list) and v) or (isinstance(v, str) and v.strip())
        for k, v in payload.items()
    )


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
) -> tuple[dict, str]:
    """Parse a Hermes agent result into a structured payload.

    ``run_kwargs`` is forwarded to any follow-up ``agent.run_conversation``
    calls (template / summary fallbacks) so providers that require streaming
    (e.g. Fireworks at high max_tokens) keep streaming on those calls too.
    """
    extra_run_kwargs = run_kwargs or {}
    raw_output = result.get("final_response", "") or ""
    messages = result.get("messages", [])

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
            summary_result = agent.run_conversation(
                user_message=summary_prompt,
                conversation_history=messages,
                **extra_run_kwargs,
            )
            raw_output = summary_result.get("final_response", "") or ""
            messages = summary_result.get("messages", messages)
            if raw_output.strip():
                print(f"[hermes-worker] Got JSON from template prompt ({len(raw_output)} chars)", file=sys.stderr)
        except Exception as exc:
            print(f"[hermes-worker] Template prompt failed: {exc}", file=sys.stderr)

    # For template-file phases, check the template file FIRST — we told the
    # model to write there, so it's the primary output path.
    payload = None
    if output_path and output_path.exists():
        try:
            candidate_payload = json.loads(output_path.read_text(encoding="utf-8"))
            if isinstance(candidate_payload, dict):
                # Check if the model actually filled in findings (not just the empty template)
                has_content = _template_has_content(candidate_payload, step)
                if has_content:
                    payload = candidate_payload
                    print(f"[hermes-worker] Read JSON from template file: {output_path}", file=sys.stderr)
                else:
                    print(f"[hermes-worker] Template file exists but has no real content", file=sys.stderr)
        except (json.JSONDecodeError, OSError):
            pass

    # Try parsing the final text response
    if payload is None:
        payload = _parse_json_response(raw_output)

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
                    payload = json.loads(candidate.read_text(encoding="utf-8"))
                    print(f"[hermes-worker] Read JSON from file written by model: {candidate}", file=sys.stderr)
                    break
                except (json.JSONDecodeError, OSError):
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
        except Exception as exc:
            print(f"[hermes-worker] Summary prompt failed: {exc}", file=sys.stderr)

    if payload is None:
        raise CliError(
            "worker_parse_error",
            f"Hermes worker returned invalid JSON for step '{step}': "
            f"could not extract JSON from response ({len(raw_output)} chars)",
            extra={"raw_output": raw_output},
        )

    result["final_response"] = raw_output
    result["messages"] = messages
    return payload, raw_output


def clean_parsed_payload(payload: dict, schema: dict, step: str) -> None:
    """Normalize a parsed Hermes payload before validation."""
    # Strip guide-only fields from critique checks (guidance/prior_findings
    # are in the template file to help the model, but not part of the schema)
    if step == "critique" and isinstance(payload.get("checks"), list):
        for check in payload["checks"]:
            if isinstance(check, dict):
                check.pop("guidance", None)
                check.pop("prior_findings", None)

    # Fill in missing required fields with safe defaults before validation.
    # Models often omit empty arrays/strings that megaplan requires.
    _fill_schema_defaults(payload, schema)

    # Normalize field aliases in nested arrays (e.g. critique flags use
    # "summary" instead of "concern", "detail" instead of "evidence").
    _normalize_nested_aliases(payload, schema)


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
            from megaplan.pricing import fireworks as fireworks_pricing

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
) -> WorkerResult:
    """Run a megaplan phase using Hermes Agent via OpenRouter.

    Structured output is enforced via the prompt (megaplan prompts already
    embed the JSON schema). The final response is parsed and validated.
    """
    if os.getenv(MOCK_ENV_VAR) == "1":
        return mock_worker_output(step, state, plan_dir, prompt_override=prompt_override)
    fresh = fresh or step != "execute"

    AIAgent, SessionDB = _import_hermes_runtime()
    # Logging is configured once at process startup by entry points such as
    # the CLI, gateway, and ACP adapter. Do not call configure_logging() from
    # this per-worker path: it mutates process-global logger state and is not
    # safe for in-process worker concurrency.

    project_dir = Path(state["config"]["project_dir"])
    plan_mode = state["config"].get("mode", "code")
    from megaplan.schemas import get_execution_schema_key
    schema_name = (
        get_execution_schema_key(plan_mode, form=creative_form_id(state))
        if step == "execute"
        else STEP_SCHEMA_FILENAMES[step]
    )
    schema = read_json(schemas_root(root) / schema_name)
    output_path: Path | None = None

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

    # Build prompt — megaplan prompts embed the JSON schema, but some models
    # ignore formatting instructions buried in long prompts.  Append a clear
    # reminder so the final response is valid JSON, not markdown.
    prompt = prompt_override if prompt_override is not None else create_hermes_prompt(
        step, state, plan_dir, root=root
    )
    # Add web search guidance for phases that have it
    if step in ("plan", "critique", "revise"):
        prompt += (
            "\n\nWEB SEARCH: You have web_search and web_extract tools. "
            "If the task involves a framework API you're not certain about — "
            "for example a specific Next.js feature, a particular import path, "
            "or a config flag that might have changed between versions — "
            "search for the current documentation before committing to an approach. "
            "Your training data may be outdated for newer framework features."
        )
    elif step == "execute":
        prompt += (
            "\n\nWEB SEARCH: You have web_search available. "
            "If you encounter an API you're not sure about while coding, "
            "search before writing — a quick lookup is cheaper than a build failure."
            "\n\nIMPORTANT: Do NOT rename, modify, or delete EVAL.ts or any test files. "
            "They are used for scoring after execution and must remain unchanged."
        )

    toolsets = _toolsets_for_phase(step)

    # Critique and review: use custom template writers that pre-populate IDs.
    # Other template-file phases: hermes_worker writes a generic template.
    if step == "critique":
        output_path = plan_dir / "critique_output.json"
    elif step == "review":
        from megaplan.prompts.review import _write_review_template
        output_path = _write_review_template(plan_dir, state)
        prompt += (
            f"\n\nOUTPUT FILE: {output_path}\n"
            "This file is your ONLY output. It contains a JSON template PRE-POPULATED with "
            "the task IDs and sense-check IDs you must review.\n"
            "Workflow:\n"
            "1. Read the file to see all the task IDs and sense-check IDs\n"
            "2. Investigate each task — cross-reference executor claims against the git diff\n"
            "3. Fill in every reviewer_verdict, evidence_files, verdict, criteria, and summary\n"
            "4. Write the completed JSON back to the file\n\n"
            "CRITICAL: You MUST fill in ALL task_verdicts and sense_check_verdicts entries. "
            "Do NOT leave reviewer_verdict or verdict fields empty. "
            "Do NOT put your results in a text response. The file is the only output that matters."
        )
    elif step in _TEMPLATE_FILE_PHASES and toolsets:
        output_path = plan_dir / f"{step}_output.json"
        output_path.write_text(
            _build_output_template(step, schema),
            encoding="utf-8",
        )
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

    # Resolve model provider — support direct API providers via prefix
    # e.g. "zhipu:glm-5.1" → base_url=Zhipu API, model="glm-5.1"
    # Uses the key pool for key rotation and cooldown on 429s.
    from megaplan.runtime.key_pool import resolve_model as _resolve_model, acquire_key, report_429
    resolved_model, agent_kwargs = _resolve_model(model)

    # Resolve the reasoning override from model family + profile depth. Off
    # families (which return structured output outside the content field) stay
    # disabled; otherwise the requested effort sets the thinking budget. DeepSeek
    # V4 with no effort yields None, matching the Fireworks route's default.
    _reasoning_off = _reasoning_config_for_model(resolved_model, effort)

    # Cap output tokens to prevent repetition loops (Qwen generates 330K+
    # of repeated text without a limit). Sized to fit large finalize.json
    # task graphs and multi-batch execute outputs on plans with ~15+ tasks.
    # Also drives the Fireworks streaming gate below — any value >4096 forces
    # streaming on `fireworks:*` models because Fireworks rejects >4096 max_tokens
    # without `stream=true`.
    agent_max_tokens = 65536 if step == "execute" else 32768

    _hermes_db_path = _worker_db_path(plan_dir, session_key)

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
        if not toolsets:
            current_agent.set_response_format(schema, name=f"megaplan_{step}")
        return current_agent

    def _rewrite_output_template(current_output_path: Path | None) -> Path | None:
        if current_output_path is None:
            return None
        if step == "critique":
            from megaplan._core import configured_robustness
            from megaplan.prompts import _write_critique_template

            robustness = configured_robustness(state)
            return _write_critique_template(
                plan_dir,
                state,
                select_active_checks(state, robustness, plan_dir=plan_dir),
            )
        if step == "review":
            from megaplan.prompts.review import _write_review_template
            return _write_review_template(plan_dir, state)
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
        run_kwargs = _streaming_run_kwargs(current_model or model, agent_max_tokens, plan_dir=plan_dir)
        tracker = run_kwargs.get("stream_callback")
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
        _emit_llm_start(plan_dir, step, resolved_model, prompt_hash, is_streaming)

        # Heartbeat thread for streaming calls
        heartbeat_stop = threading.Event()
        if is_streaming and tracker is not None:
            _start_heartbeat(plan_dir, step, tracker, heartbeat_stop, run_id=run_id)

        try:
            current_result = current_agent.run_conversation(
                user_message=prompt,
                conversation_history=conversation_history,
                **run_kwargs,
            )
        finally:
            if is_streaming:
                heartbeat_stop.set()
            # Clear the retry-error hook so it doesn't leak across attempts.
            if is_streaming and tracker is not None:
                try:
                    current_agent._megaplan_retry_error_callback = None
                except Exception:
                    pass

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
        )
        clean_parsed_payload(current_payload, schema, step)
        messages = current_result.get("messages", [])

        # Emit llm_call_end
        request_id = _extract_request_id(current_result)
        tokens_in = int(current_result.get("prompt_tokens", 0) or 0)
        tokens_out = int(current_result.get("completion_tokens", 0) or 0)
        _emit_llm_end(plan_dir, step, tokens_in, tokens_out, request_id)

        try:
            validate_payload(step, current_payload)
        except CliError as error:
            # For execute, try reconstructed payload if validation fails
            if step == "execute":
                reconstructed = _reconstruct_execute_payload(messages, project_dir, plan_dir, mode=plan_mode)
                if reconstructed is not None:
                    try:
                        validate_payload(step, reconstructed)
                        current_payload = reconstructed
                        print(
                            "[hermes-worker] Using reconstructed payload (original failed validation)",
                            file=activity_stderr,
                        )
                        error = None
                    except CliError:
                        pass
            if error is not None:
                raise CliError(error.code, error.message, extra={"raw_output": current_raw_output}) from error

        return current_result, current_payload, current_raw_output

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
        from megaplan.runtime.sandbox import install_sandbox
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
            from megaplan.orchestration.phase_result import ExternalError
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
                    from megaplan.runtime.key_pool import minimax_openrouter_model
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
        from megaplan.observability.events import emit, EventKind
        emit(
            EventKind.COST_RECORDED,
            plan_dir=plan_dir,
            phase=step,
            payload={
                "request_id": _extract_request_id(result),
                "cost_usd": float(cost_usd),
                "provider": (resolved_model or "").split(":")[0] if resolved_model else None,
                "model": result.get("model") or resolved_model,
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

    # Try to read checkpoint file for task updates
    task_updates = []
    checkpoint_files = sorted(plan_dir.glob("execution_batch_*.json"), reverse=True)
    for cp_file in checkpoint_files:
        try:
            cp_data = json.loads(cp_file.read_text(encoding="utf-8"))
            updates = cp_data.get("task_updates", [])
            if isinstance(updates, list):
                task_updates.extend(updates)
        except Exception:
            pass

    if mode == "doc":
        sections_written = sorted(
            {
                section
                for tu in task_updates
                for section in tu.get("sections_written", [])
                if isinstance(section, str) and section.strip()
            }
        )
        return {
            "output": f"[Reconstructed from tool calls] Made {len(tool_calls)} tool calls, wrote {len(sections_written)} sections.",
            "sections_written": sections_written,
            "commands_run": [],
            "deviations": ["Execute response reconstructed from tool calls — model failed to produce JSON report."],
            "task_updates": task_updates,
            "sense_check_acknowledgments": [],
        }

    files_list = sorted(files_changed)
    return {
        "output": f"[Reconstructed from tool calls] Made {len(tool_calls)} tool calls, changed {len(files_list)} files.",
        "files_changed": files_list,
        "commands_run": commands_run,
        "deviations": ["Execute response reconstructed from tool calls — model failed to produce JSON report."],
        "task_updates": task_updates,
        "sense_check_acknowledgments": [],
    }


def _fill_schema_defaults(payload: dict, schema: dict) -> None:
    """Fill missing required fields with safe defaults based on schema types.

    Models often omit empty arrays, empty strings, or optional-sounding fields
    that the schema marks as required. Rather than rejecting the response,
    fill them with type-appropriate defaults.
    """
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    for field in required:
        if field in payload:
            continue
        prop = properties.get(field, {})
        ptype = prop.get("type", "string")
        if ptype == "array":
            payload[field] = []
        elif ptype == "object":
            payload[field] = {}
        elif ptype == "boolean":
            payload[field] = False
        elif ptype in ("number", "integer"):
            payload[field] = 0
        else:
            payload[field] = ""


def _normalize_nested_aliases(payload: dict, schema: dict) -> None:
    """Normalize field aliases in nested array items.

    Models often use synonyms for required fields (e.g. "summary" instead of
    "concern", "detail" instead of "evidence"). This applies the alias mapping
    from merge._FIELD_ALIASES to nested objects in arrays.
    """
    from megaplan.execute.merge import _FIELD_ALIASES

    properties = schema.get("properties", {})
    for field, prop in properties.items():
        if prop.get("type") != "array" or field not in payload:
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
    props = schema.get("properties", {})
    if not isinstance(props, dict):
        return "{}"
    template = {}
    for key, prop in props.items():
        if not isinstance(prop, dict):
            template[key] = "..."
            continue
        ptype = prop.get("type", "string")
        if ptype == "string":
            desc = prop.get("description", "")
            template[key] = f"<{desc}>" if desc else "..."
        elif ptype == "array":
            items = prop.get("items", {})
            if isinstance(items, dict) and items.get("type") == "string":
                template[key] = ["..."]
            else:
                template[key] = []
        elif ptype == "boolean":
            template[key] = True
        elif ptype in ("number", "integer"):
            template[key] = 0
        elif ptype == "object":
            template[key] = {}
        else:
            template[key] = "..."
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
