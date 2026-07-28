"""Headless Shannon stream worker boundary.

Write-capable stream turns invoke native Claude with
``--permission-mode bypassPermissions``. That bypass is bounded by the OS user,
process environment, and host-level controls inherited by this process; the
resolved worktree ``cwd`` selects the project context but is not a filesystem
sandbox and does not confine filesystem access by itself.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable

from arnold_pipelines.megaplan.types import CliError, PlanState
from arnold_pipelines.megaplan._core import creative_form_id, read_json, schemas_root
from arnold_pipelines.megaplan.model_seam import ModelStructuralAuditError, audit_step_payload
from arnold_pipelines.megaplan.prompts import create_claude_prompt
from arnold_pipelines.megaplan.schemas import SCHEMAS, get_execution_schema_key
from arnold_pipelines.megaplan.workers._impl import (
    CommandResult,
    ProgressLivenessState,
    STEP_SCHEMA_FILENAMES,
    WorkerResult,
    _activity_callback_for_state,
    _external_worker_env,
    _normalize_step_payload_for_audit,
    run_command,
    resolve_work_dir,
    session_key_for,
)
from arnold_pipelines.megaplan.workers.shannon_session import (
    Turn,
    _seeded_rng_for_run,
    _serialize_session_plan,
    _shannon_run_nonce,
    plan_session,
)
_SHANNON_STREAM_READ_ONLY_ALLOWED_TOOLS = (
    "Read",
    "Grep",
    "Glob",
    "WebFetch",
    "WebSearch",
)
_SHANNON_STREAM_READ_ONLY_DISALLOWED_TOOLS = (
    "Bash",
    "Edit",
    "MultiEdit",
    "NotebookEdit",
    "TodoWrite",
    "Task",
    "Write",
)


def _normalize_stream_payload(step: str, payload: dict[str, Any]) -> dict[str, Any]:
    payload = _normalize_step_payload_for_audit(step, payload)
    if step != "execute":
        return payload
    normalized = dict(payload)
    updates = normalized.get("task_updates")
    if isinstance(updates, list):
        normalized_updates: list[Any] = []
        for update in updates:
            if not isinstance(update, dict):
                normalized_updates.append(update)
                continue
            item = dict(update)
            if item.get("status") == "completed":
                item["status"] = "done"
            normalized_updates.append(item)
        normalized["task_updates"] = normalized_updates
    return normalized


@dataclasses.dataclass(frozen=True)
class ShannonStreamCommand:
    """Native Claude stream launch plan."""

    command: list[str]
    cwd: Path
    stdin_text: str


@dataclasses.dataclass(frozen=True)
class _NativeStreamEvent:
    """Decoded native stream-json row with normalized routing fields."""

    event_type: str
    body: dict[str, Any]


@dataclasses.dataclass
class ShannonStreamLiveness:
    """Stream-specific progress classifier for ``run_command``.

    Native Claude stream-json has two independent progress sources:

    * parsed stdout NDJSON frames, which are immediate progress;
    * isolated Claude transcript ``.jsonl`` mtimes under ``CLAUDE_CONFIG_DIR``.

    A live direct child with an existing but non-advancing transcript is only
    ``alive_only`` so ``run_command`` can apply its grace cap. Missing
    transcripts or a known-dead child are ``stalled``.
    """

    claude_config_dir: Path
    work_dir: Path
    session_id: str | None = None
    child_alive: Callable[[], bool] | None = None

    _stdout_buffer: str = dataclasses.field(default="", init=False)
    _stdout_event_count: int = dataclasses.field(default=0, init=False)
    _last_probe_stdout_event_count: int = dataclasses.field(default=0, init=False)
    _last_transcript_mtime: float = dataclasses.field(default=0.0, init=False)
    _primed_transcript: bool = dataclasses.field(default=False, init=False)

    def activity_guard(self, kind: str, text: str) -> None:
        """Observe stdout chunks and count complete parseable NDJSON events."""
        if kind != "stdout" or not text:
            return
        self._stdout_buffer += text
        lines = self._stdout_buffer.splitlines(keepends=True)
        if lines and not lines[-1].endswith(("\n", "\r")):
            self._stdout_buffer = lines.pop()
        else:
            self._stdout_buffer = ""
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                self._stdout_event_count += 1

    def probe(self) -> ProgressLivenessState:
        """Return the current progress state for ``run_command``."""
        if self._stdout_event_count > self._last_probe_stdout_event_count:
            self._last_probe_stdout_event_count = self._stdout_event_count
            return "progressing"

        if self.child_alive is not None:
            try:
                if not bool(self.child_alive()):
                    return "stalled"
            except Exception:
                return "unknown"

        mtime = _max_shannon_stream_transcript_mtime(
            self.claude_config_dir,
            self.work_dir,
            session_id=self.session_id,
        )
        if mtime <= 0.0:
            return "stalled"

        if not self._primed_transcript:
            self._last_transcript_mtime = mtime
            self._primed_transcript = True
            return "alive_only"

        if mtime > self._last_transcript_mtime:
            self._last_transcript_mtime = mtime
            return "progressing"

        return "alive_only"


@dataclasses.dataclass(frozen=True)
class ShannonStreamConfig:
    """Stream-worker knobs only.

    M2 keeps the opt-in itself env-only in the availability/dispatch layer. This
    config intentionally covers only launch/runtime behavior unique to the
    native stream-json path.
    """

    execute_timeout_seconds: int
    stream_idle_timeout_seconds: float
    parser_max_unknown_events: int
    conformance_enabled: bool
    max_output_tokens: int
    session_roulette_enabled: bool
    session_compact_probability: float
    context_op_timeout_seconds: int
    context_op_delay_min_seconds: float
    context_op_delay_max_seconds: float
    handshake_probability: float
    handshake_delay_min_seconds: float
    handshake_delay_max_seconds: float
    readiness_timeout_seconds: int
    readiness_probe_forced: bool
    voice: str
    auth_channel: str
    api_key_dry_run: bool

    @classmethod
    def load(cls, env: dict[str, str] | None = None) -> "ShannonStreamConfig":
        env = os.environ if env is None else env

        def _get(name: str) -> str:
            return env.get(name, "").strip()

        def _truthy(name: str) -> bool | None:
            raw = _get(name).lower()
            if raw in {"1", "true", "yes", "on"}:
                return True
            if raw in {"0", "false", "no", "off"}:
                return False
            return None

        def _int_pos(name: str, default: int) -> int:
            raw = _get(name)
            if not raw:
                return default
            try:
                return max(1, int(raw))
            except ValueError:
                return default

        def _float_pos(name: str, default: float) -> float:
            raw = _get(name)
            if not raw:
                return default
            try:
                return max(0.0, float(raw))
            except ValueError:
                return default

        def _float_unit(name: str, default: float) -> float:
            raw = _get(name)
            if not raw:
                return default
            try:
                return min(1.0, max(0.0, float(raw)))
            except ValueError:
                return default

        roulette = _truthy("MEGAPLAN_SHANNON_STREAM_SESSION_ROULETTE")
        auth_channel = _get("MEGAPLAN_SHANNON_STREAM_AUTH_CHANNEL").lower()
        if auth_channel in {"api-key", "api"}:
            auth_channel = "api_key"
        if auth_channel not in {"", "subscription", "api_key"}:
            auth_channel = "subscription"
        return cls(
            execute_timeout_seconds=_int_pos(
                "MEGAPLAN_SHANNON_STREAM_EXECUTE_TIMEOUT_SECONDS",
                7200,
            ),
            stream_idle_timeout_seconds=_float_pos(
                "MEGAPLAN_SHANNON_STREAM_IDLE_TIMEOUT_SECONDS",
                300.0,
            ),
            parser_max_unknown_events=_int_pos(
                "MEGAPLAN_SHANNON_STREAM_PARSER_MAX_UNKNOWN_EVENTS",
                200,
            ),
            conformance_enabled=(
                _truthy("MEGAPLAN_SHANNON_STREAM_CONFORMANCE") is True
            ),
            max_output_tokens=_int_pos(
                "MEGAPLAN_SHANNON_STREAM_MAX_OUTPUT_TOKENS",
                _int_pos("MEGAPLAN_SHANNON_MAX_OUTPUT_TOKENS", 128000),
            ),
            session_roulette_enabled=True if roulette is None else bool(roulette),
            session_compact_probability=_float_unit(
                "MEGAPLAN_SHANNON_STREAM_SESSION_COMPACT_PROBABILITY",
                _float_unit("MEGAPLAN_SHANNON_SESSION_COMPACT_PROBABILITY", 0.25),
            ),
            context_op_timeout_seconds=_int_pos(
                "MEGAPLAN_SHANNON_STREAM_CONTEXT_OP_TIMEOUT_SECONDS",
                180,
            ),
            context_op_delay_min_seconds=_float_pos(
                "MEGAPLAN_SHANNON_STREAM_CONTEXT_OP_DELAY_MIN_SECONDS",
                0.0,
            ),
            context_op_delay_max_seconds=_float_pos(
                "MEGAPLAN_SHANNON_STREAM_CONTEXT_OP_DELAY_MAX_SECONDS",
                0.0,
            ),
            handshake_probability=0.0,
            handshake_delay_min_seconds=0.0,
            handshake_delay_max_seconds=0.0,
            readiness_timeout_seconds=60,
            readiness_probe_forced=False,
            voice="native_stream",
            auth_channel=auth_channel or "subscription",
            api_key_dry_run=(
                _truthy("MEGAPLAN_SHANNON_STREAM_API_DRY_RUN") is True
            ),
        )


def _shannon_stream_run_dir(plan_dir: Path, *, plan_id: str, step: str) -> Path:
    """Per-run artifact directory for native Claude stream launches."""
    return plan_dir / ".megaplan" / "runs" / plan_id / step / "shannon_stream"


def _claude_project_slug(work_dir: Path) -> str:
    """Match Claude's project key for transcript directory lookup."""
    return re.sub(r"[^a-zA-Z0-9_-]", "-", str(work_dir.resolve()))


def _shannon_stream_transcript_paths(
    claude_config_dir: Path,
    work_dir: Path,
    *,
    session_id: str | None = None,
) -> list[Path]:
    """Find candidate isolated Claude transcript files for a work directory."""
    projects_root = claude_config_dir / "projects"
    if not projects_root.is_dir():
        return []
    paths: list[Path] = []
    try:
        if session_id:
            paths.extend(projects_root.glob(f"*/{session_id}.jsonl"))
        if not paths:
            project_dir = projects_root / _claude_project_slug(work_dir)
            if project_dir.is_dir():
                paths.extend(project_dir.glob("*.jsonl"))
    except OSError:
        return []
    return paths


def _max_shannon_stream_transcript_mtime(
    claude_config_dir: Path,
    work_dir: Path,
    *,
    session_id: str | None = None,
) -> float:
    newest = 0.0
    for path in _shannon_stream_transcript_paths(
        claude_config_dir,
        work_dir,
        session_id=session_id,
    ):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        newest = max(newest, mtime)
    return newest


def make_shannon_stream_liveness(
    *,
    claude_config_dir: Path,
    work_dir: Path,
    session_id: str | None = None,
    child_alive: Callable[[], bool] | None = None,
) -> ShannonStreamLiveness:
    """Build the stream activity guard/progress probe pair."""
    return ShannonStreamLiveness(
        claude_config_dir=claude_config_dir,
        work_dir=work_dir,
        session_id=session_id,
        child_alive=child_alive,
    )


def _write_claude_stream_settings(claude_config_dir: Path) -> Path:
    """Write the isolated Claude settings needed for deterministic launches."""
    claude_config_dir.mkdir(parents=True, exist_ok=True)
    settings_path = claude_config_dir / "settings.json"
    data: dict[str, Any] = {}
    if settings_path.exists():
        try:
            loaded = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            loaded = {}
        if isinstance(loaded, dict):
            data = loaded
    data["autoUpdates"] = False
    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return settings_path


def _scrub_claude_code_env(env: dict[str, str]) -> None:
    keep = {"CLAUDE_CODE_MAX_OUTPUT_TOKENS"}
    for name in list(env):
        if name == "CLAUDECODE" or (
            name.startswith("CLAUDE_CODE_") and name not in keep
        ):
            env.pop(name, None)


def _resolve_shannon_stream_api_key() -> tuple[str | None, str | None]:
    narrow_key = os.environ.get("MEGAPLAN_SHANNON_STREAM_API_KEY", "").strip()
    if narrow_key:
        return narrow_key, "MEGAPLAN_SHANNON_STREAM_API_KEY"
    inherited_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if inherited_key:
        return inherited_key, "ANTHROPIC_API_KEY"
    return None, None


def _shannon_stream_auth_metadata(config: ShannonStreamConfig) -> dict[str, Any]:
    key, source = _resolve_shannon_stream_api_key()
    return {
        "worker_channel": "shannon_stream",
        "auth_channel": config.auth_channel,
        "provider": "claude",
        "api_key_present": config.auth_channel == "api_key" and bool(key),
        "api_key_source": source if config.auth_channel == "api_key" else None,
        "dry_run": config.auth_channel == "api_key" and config.api_key_dry_run and not key,
    }


def build_shannon_stream_env(
    *,
    plan_dir: Path,
    state: PlanState,
    step: str,
    config: ShannonStreamConfig | None = None,
    turn_id: str | None = None,
) -> tuple[dict[str, str], Path]:
    """Build the environment for native ``claude --print`` stream execution.

    The base is the shared external-worker env so progress/session isolation
    stays aligned with the other workers. Stream-specific policy is layered on
    top: Claude Code parent env is scrubbed, subscription mode uses the normal
    Claude config so the logged-in OAuth state remains available, and API-key
    mode keeps Claude config/state isolated under run artifacts.
    """
    cfg = config or ShannonStreamConfig.load()
    plan_id = str(state.get("name", ""))
    run_dir = _shannon_stream_run_dir(plan_dir, plan_id=plan_id, step=step)

    env = _external_worker_env(turn_id=turn_id or f"plan_worker_{plan_id}")
    _scrub_claude_code_env(env)
    if cfg.auth_channel == "subscription":
        env["ANTHROPIC_API_KEY"] = ""
        claude_config_dir = Path.home() / ".claude"
    elif cfg.auth_channel == "api_key":
        claude_config_dir = run_dir / "claude_config"
        claude_config_dir.mkdir(parents=True, exist_ok=True)
        _write_claude_stream_settings(claude_config_dir)
        api_key, _source = _resolve_shannon_stream_api_key()
        if api_key:
            env["ANTHROPIC_API_KEY"] = api_key
        elif cfg.api_key_dry_run:
            env["ANTHROPIC_API_KEY"] = ""
        else:
            raise CliError(
                "auth_error",
                "Shannon stream API-key auth requires ANTHROPIC_API_KEY or "
                "MEGAPLAN_SHANNON_STREAM_API_KEY. Set "
                "MEGAPLAN_SHANNON_STREAM_API_DRY_RUN=1 only for adapter "
                "plumbing proof without live API billing.",
                extra={
                    "worker_channel": "shannon_stream",
                    "auth_channel": "api_key",
                    "source": "shannon_stream_auth",
                },
            )
    else:
        raise CliError(
            "auth_error",
            f"Unsupported Shannon stream auth channel: {cfg.auth_channel}",
            extra={"worker_channel": "shannon_stream", "auth_channel": cfg.auth_channel},
        )
    auth_metadata = _shannon_stream_auth_metadata(cfg)
    env["MEGAPLAN_WORKER_CHANNEL"] = auth_metadata["worker_channel"]
    env["MEGAPLAN_SHANNON_STREAM_AUTH_CHANNEL"] = auth_metadata["auth_channel"]
    env["MEGAPLAN_SHANNON_STREAM_API_DRY_RUN_ACTIVE"] = (
        "1" if auth_metadata["dry_run"] else "0"
    )
    if cfg.auth_channel == "api_key":
        env["CLAUDE_CONFIG_DIR"] = str(claude_config_dir)
    env.setdefault("CLAUDE_CODE_MAX_OUTPUT_TOKENS", str(cfg.max_output_tokens))
    env["DISABLE_AUTOUPDATER"] = "1"
    env["CLAUDE_CODE_DISABLE_AUTOUPDATER"] = "1"
    env["CLAUDE_DISABLE_AUTOUPDATER"] = "1"
    return env, claude_config_dir


def _stream_stdin_user_message(prompt: str) -> str:
    return json.dumps(
        {"type": "user", "message": {"role": "user", "content": prompt}},
        separators=(",", ":"),
    )


def build_shannon_stream_command(
    *,
    state: PlanState,
    prompt: str,
    read_only: bool = False,
    model: str | None = None,
    resume_session_id: str | None = None,
    session_id: str | None = None,
    read_only_tool_policy_supported: bool = True,
) -> ShannonStreamCommand:
    """Build a native ``claude --print`` stream-json command.

    Write-capable turns use Claude's explicit bypass mode. Read-only turns must
    never use bypass; they either mirror Shannon's allow/deny tool policy or
    fail closed when that native tool policy is unavailable.
    """
    if resume_session_id and session_id:
        raise CliError(
            "invalid_args",
            "Native Claude stream command cannot use both --resume and --session-id.",
        )
    if read_only and not read_only_tool_policy_supported:
        raise CliError(
            "read_only_unsupported",
            "Native Claude stream read-only mode requires --allowedTools and "
            "--disallowedTools support.",
        )

    command = [
        "claude",
        "--print",
        "--verbose",
        "--input-format=stream-json",
        "--output-format=stream-json",
    ]
    if model is not None:
        command.extend(["--model", model])
    if resume_session_id is not None:
        command.extend(["--resume", resume_session_id])
    elif session_id is not None:
        command.extend(["--session-id", session_id])

    if read_only:
        command.extend(
            [
                "--allowedTools",
                *_SHANNON_STREAM_READ_ONLY_ALLOWED_TOOLS,
                "--disallowedTools",
                *_SHANNON_STREAM_READ_ONLY_DISALLOWED_TOOLS,
            ]
        )
    else:
        command.extend(["--permission-mode", "bypassPermissions"])

    return ShannonStreamCommand(
        command=command,
        cwd=resolve_work_dir(state),
        stdin_text=_stream_stdin_user_message(prompt),
    )


def _first_present(mapping: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value))
    if isinstance(value, str):
        try:
            return max(0, int(float(value)))
        except ValueError:
            return None
    return None


def _extract_nested_dict(value: Any, names: tuple[str, ...]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    for name in names:
        nested = value.get(name)
        if isinstance(nested, dict):
            return nested
    return None


def _extract_session_id(value: dict[str, Any]) -> str | None:
    raw = _first_present(
        value,
        (
            "session_id",
            "sessionId",
            "sessionID",
            "conversation_id",
            "conversationId",
        ),
    )
    if raw is None and isinstance(value.get("session"), dict):
        raw = _first_present(
            value["session"],
            ("id", "session_id", "sessionId", "conversation_id", "conversationId"),
        )
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _extract_usage(value: dict[str, Any]) -> dict[str, int]:
    usage = _extract_nested_dict(
        value,
        (
            "usage",
            "token_usage",
            "tokenUsage",
            "tokens",
            "token_counts",
            "tokenCounts",
        ),
    )
    if usage is None:
        usage = value
    prompt = _coerce_int(
        _first_present(
            usage,
            (
                "prompt_tokens",
                "input_tokens",
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
            ),
        )
    )
    completion = _coerce_int(
        _first_present(usage, ("completion_tokens", "output_tokens", "response_tokens"))
    )
    total = _coerce_int(_first_present(usage, ("total_tokens", "tokens_total", "total")))
    if total is None:
        total = (prompt or 0) + (completion or 0)
    return {
        "prompt_tokens": prompt or 0,
        "completion_tokens": completion or 0,
        "total_tokens": total or 0,
    }


def _json_object_from_text(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _extract_payload(value: dict[str, Any]) -> dict[str, Any] | None:
    direct = _first_present(
        value,
        (
            "structured_output",
            "structuredOutput",
            "payload",
            "result",
            "output",
            "data",
        ),
    )
    if isinstance(direct, dict):
        return direct
    if isinstance(direct, str):
        parsed = _json_object_from_text(direct)
        if parsed is not None:
            return parsed
    message = value.get("message")
    if isinstance(message, dict):
        nested = _extract_payload(message)
        if nested is not None:
            return nested
        content = message.get("content")
    else:
        content = value.get("content")
    if isinstance(content, str):
        return _json_object_from_text(content)
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str):
                parsed = _json_object_from_text(text)
                if parsed is not None:
                    return parsed
            nested = _extract_payload(block)
            if nested is not None:
                return nested
    return None


def _normalize_stream_event(value: Any) -> _NativeStreamEvent:
    if not isinstance(value, dict):
        raise CliError(
            "parse_error",
            "Claude stream-json event was not an object.",
            extra={"event": value},
        )
    event_type = _first_present(
        value,
        ("type", "event", "event_type", "eventType", "kind", "name"),
    )
    if event_type is None and isinstance(value.get("message"), dict):
        event_type = value["message"].get("role")
    return _NativeStreamEvent(str(event_type or "unknown"), value)


def _is_error_status(value: dict[str, Any]) -> bool:
    if bool(value.get("is_error") or value.get("isError")):
        return True
    status = _first_present(
        value,
        ("status", "result_status", "resultStatus", "subtype", "outcome"),
    )
    if status is None:
        return False
    return str(status).strip().lower() in {
        "error",
        "failed",
        "failure",
        "cancelled",
        "canceled",
        "timeout",
    }


def _native_error_from_event(value: dict[str, Any], raw: str) -> CliError:
    error = _first_present(value, ("error", "message", "result", "payload", "data"))
    if isinstance(error, dict):
        message = _first_present(error, ("message", "error", "details", "detail"))
        code = _first_present(error, ("code", "error_code", "errorCode", "type"))
    else:
        message = error
        code = _first_present(value, ("code", "error_code", "errorCode"))
    text = str(message or "Claude stream returned an error")
    lowered = text.lower()
    error_code = str(code or "worker_error")
    if any(
        pattern in lowered
        for pattern in ("not logged in", "/login", "unauthorized", "authentication")
    ):
        error_code = "auth_error"
    elif "rate limit" in lowered or "429" in lowered:
        error_code = "rate_limit"
    return CliError(error_code, f"Claude stream failed: {text}", extra={"raw_output": raw})


def _normalize_rate_limit_window(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    window = dict(value)
    nested = _first_present(
        window,
        ("rate_limit", "rateLimit", "limit", "window", "usage", "quota"),
    )
    if isinstance(nested, dict):
        merged = dict(nested)
        for key in ("provider", "model", "resource", "scope"):
            if key in window and key not in merged:
                merged[key] = window[key]
        window = merged
    elif isinstance(window.get("payload"), dict):
        window = dict(window["payload"])
    return window or None


def _collect_rate_limit_windows(value: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[Any] = []
    saw_list = False
    for key in (
        "rate_limits",
        "rateLimits",
        "rate_limit_windows",
        "rateLimitWindows",
        "windows",
    ):
        item = value.get(key)
        if isinstance(item, list):
            saw_list = True
            candidates.extend(item)
    if not saw_list:
        candidates.append(value)
    windows: list[dict[str, Any]] = []
    for candidate in candidates:
        normalized = _normalize_rate_limit_window(candidate)
        if normalized is not None:
            windows.append(normalized)
    return windows


def _pack_rate_limit(windows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not windows:
        return None
    if len(windows) == 1:
        return windows[0]
    return {"values": windows}


def parse_shannon_stream_output(
    raw: str,
    *,
    duration_ms: int = 0,
    max_unknown_events: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> WorkerResult:
    """Parse native Claude ``stream-json`` NDJSON into a ``WorkerResult``.

    The native stream contract is intentionally defensive. It accepts common
    field drift for session IDs, result payloads, token usage, final status, and
    rate-limit windows, but success still requires a final interpretable
    ``result`` event. Unknown events are retained in trace metadata instead of
    being silently discarded.
    """
    lines = [line for line in raw.splitlines() if line.strip()]
    if not lines:
        raise CliError(
            "parse_error",
            "Claude stream-json output was empty.",
            extra={"raw_output": raw},
        )

    session_id: str | None = None
    model_actual: str | None = None
    prompt_tokens = completion_tokens = total_tokens = 0
    cost_usd = 0.0
    final_result: dict[str, Any] | None = None
    assistant_events: list[dict[str, Any]] = []
    unknown_events: list[dict[str, Any]] = []
    rate_limit_windows: list[dict[str, Any]] = []

    for line_number, line in enumerate(lines, start=1):
        try:
            decoded = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CliError(
                "parse_error",
                f"Claude stream-json line {line_number} was not valid JSON: {exc}",
                extra={"raw_output": raw, "line": line},
            ) from exc
        event = _normalize_stream_event(decoded)
        event_key = event.event_type.strip().lower().replace("-", "_")
        body = event.body
        session_id = _extract_session_id(body) or session_id
        model_actual = (
            str(body.get("model") or body.get("model_actual") or model_actual or "")
            or None
        )
        usage = _extract_usage(body)
        prompt_tokens = max(prompt_tokens, usage["prompt_tokens"])
        completion_tokens = max(completion_tokens, usage["completion_tokens"])
        total_tokens = max(total_tokens, usage["total_tokens"])
        if "cost_usd" in body or "costUsd" in body or "total_cost_usd" in body:
            try:
                cost_usd = float(
                    _first_present(body, ("cost_usd", "costUsd", "total_cost_usd"))
                    or cost_usd
                )
            except (TypeError, ValueError):
                pass

        if _is_error_status(body) or event_key in {"error", "native_error"}:
            raise _native_error_from_event(body, raw)
        if event_key in {"init", "system_init"}:
            continue
        if event_key == "assistant":
            assistant_events.append(body)
            continue
        if event_key in {"rate_limit_event", "rate_limit", "rate_limits"}:
            rate_limit_windows.extend(_collect_rate_limit_windows(body))
            continue
        if event_key == "result":
            final_result = body
            continue
        unknown_events.append(body)

    if max_unknown_events is not None and len(unknown_events) > max_unknown_events:
        unknown_events = unknown_events[:max_unknown_events]

    if final_result is None:
        raise CliError(
            "parse_error",
            "Claude stream-json output did not include a final result event.",
            extra={"raw_output": raw},
        )
    if _is_error_status(final_result):
        raise _native_error_from_event(final_result, raw)

    payload = _extract_payload(final_result)
    if payload is None:
        raise CliError(
            "parse_error",
            "Claude stream-json result event did not contain an interpretable payload.",
            extra={"raw_output": raw},
        )

    usage = _extract_usage(final_result)
    prompt_tokens = usage["prompt_tokens"] or prompt_tokens
    completion_tokens = usage["completion_tokens"] or completion_tokens
    total_tokens = usage["total_tokens"] or total_tokens
    session_id = _extract_session_id(final_result) or session_id

    trace_metadata = dict(metadata or {})
    trace_output = json.dumps(
        {
            "stream_event_count": len(lines),
            "unknown_events": unknown_events,
            "assistant_event_count": len(assistant_events),
            **({"metadata": trace_metadata} if trace_metadata else {}),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return WorkerResult(
        payload=payload,
        raw_output=raw,
        duration_ms=duration_ms,
        cost_usd=cost_usd,
        session_id=session_id,
        trace_output=trace_output,
        model_actual=model_actual,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        rate_limit=_pack_rate_limit(rate_limit_windows),
        worker_channel=trace_metadata.get("worker_channel"),
        auth_channel=trace_metadata.get("auth_channel"),
        auth_metadata=trace_metadata or None,
    )


def _session_id_from_stream_output(raw: str) -> str | None:
    """Best-effort session id extraction for non-envelope slash turns."""
    session_id: str | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            decoded = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            session_id = _extract_session_id(decoded) or session_id
    return session_id


def _with_failure_context(error: CliError, *, raw_output: str, session_id: str | None) -> CliError:
    existing_raw = str(error.extra.get("raw_output", ""))
    error.extra["raw_output"] = raw_output or existing_raw
    if session_id is not None:
        error.extra.setdefault("session_id", session_id)
    return error


def _raise_for_native_stream_failure(
    *,
    returncode: int,
    raw_output: str,
    session_id: str | None,
) -> None:
    lowered = raw_output.lower()
    code = "worker_error"
    message = f"Claude stream worker failed with exit code {returncode}."
    if any(token in lowered for token in ("permission denied", "not allowed", "denied by permissions")):
        code = "permission_error"
        message = (
            "Claude stream worker hit a native permission denial. Stream "
            "write-mode bypassPermissions is bounded by the OS user and process "
            "environment; cwd selects project context but is not a filesystem "
            "sandbox."
        )
    elif any(token in lowered for token in ("not logged in", "/login", "unauthorized", "authentication")):
        code = "auth_error"
        message = "Claude stream worker authentication failed."
    elif "rate limit" in lowered or "429" in lowered:
        code = "rate_limit"
        message = "Claude stream worker hit a rate limit."
    raise CliError(
        code,
        message,
        extra={"raw_output": raw_output, **({"session_id": session_id} if session_id else {})},
    )


def _run_native_stream_turn(
    turn: Turn,
    *,
    step: str,
    state: PlanState,
    plan_dir: Path,
    config: ShannonStreamConfig,
    env: dict[str, str],
    claude_config_dir: Path,
    model: str | None,
    read_only: bool,
    prompt: str,
) -> CommandResult:
    if turn.pre_sleep_s > 0:
        time.sleep(turn.pre_sleep_s)
    launch = build_shannon_stream_command(
        state=state,
        prompt=prompt,
        read_only=read_only,
        model=model,
        resume_session_id=turn.session_id if turn.resume else None,
        session_id=None if turn.resume else turn.session_id,
    )
    liveness = make_shannon_stream_liveness(
        claude_config_dir=claude_config_dir,
        work_dir=launch.cwd,
        session_id=turn.session_id,
    )
    return run_command(
        launch.command,
        cwd=launch.cwd,
        stdin_text=launch.stdin_text,
        env=env,
        timeout=turn.timeout,
        activity_callback=_activity_callback_for_state(state, plan_dir),
        activity_guard=liveness.activity_guard,
        idle_timeout=config.stream_idle_timeout_seconds,
        progress_liveness_probe=liveness.probe,
        progress_liveness_grace_timeout=config.stream_idle_timeout_seconds,
    )


def run_shannon_stream_step(
    step: str,
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    fresh: bool,
    prompt_override: str | None = None,
    prompt_kwargs: dict[str, Any] | None = None,
    effort: str | None = None,
    session_agent: str = "shannon",
    model: str | None = None,
    read_only: bool = False,
    output_path: Path | None = None,
) -> WorkerResult:
    """Run one phase through Claude's native stream-json channel."""
    config = ShannonStreamConfig.load()
    fresh = fresh or step != "execute"
    if effort is not None:
        raise CliError(
            "invalid_args",
            "Native Claude stream worker does not support an effort argument.",
        )

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    base_prompt = (
        prompt_override
        if prompt_override is not None
        else create_claude_prompt(
            step,
            state,
            plan_dir,
            root=root,
            **(prompt_kwargs or {}),
        )
    )
    plan_mode = state["config"].get("mode", "code")
    schema_name = (
        get_execution_schema_key(plan_mode, form=creative_form_id(state))
        if step == "execute"
        else STEP_SCHEMA_FILENAMES[step]
    )
    schema = SCHEMAS.get(schema_name) or read_json(schemas_root(root) / schema_name)
    schema_text = json.dumps(schema)
    from arnold_pipelines.megaplan.workers.shannon import _append_json_output_contract

    prompt = _append_json_output_contract(
        base_prompt,
        step=step,
        schema_text=schema_text,
    )

    env, claude_config_dir = build_shannon_stream_env(
        plan_dir=plan_dir,
        state=state,
        step=step,
        config=config,
        turn_id=f'plan_worker_{state["name"]}',
    )
    auth_metadata = _shannon_stream_auth_metadata(config)
    session_key = session_key_for(
        step,
        session_agent,
        model=model,
        worker_channel=auth_metadata["worker_channel"],
        auth_channel=auth_metadata["auth_channel"],
        auth_metadata=auth_metadata,
    )
    sessions = state.get("sessions", {})
    session = sessions.get(session_key, {}) if isinstance(sessions, dict) else {}
    legacy_key = session_key_for(step, session_agent, model=model)
    if (
        not session
        and isinstance(sessions, dict)
        and session_key != legacy_key
        and legacy_key in sessions
    ):
        fresh = True
    stored_session_id = session.get("id") if isinstance(session, dict) else None
    persisted_session_id = stored_session_id
    session_nonce = _shannon_run_nonce(state, step)
    session_rng = _seeded_rng_for_run(state, step, nonce=session_nonce)
    plan = plan_session(
        step,
        stored_id=stored_session_id,
        fresh=fresh,
        cfg=config,
        rng=session_rng,
    )
    auth_metadata["resolved_model"] = model
    auth_metadata["session_agent"] = session_agent
    auth_metadata["session_strategy"] = plan.kind
    main_turn = dataclasses.replace(plan.main, body=prompt, delivery="stdin")
    session_id = main_turn.session_id

    for pre_turn in plan.pre_turns:
        if pre_turn.expect == "non_empty":
            main_turn = dataclasses.replace(main_turn, resume=False)
            continue
        try:
            pre_result = _run_native_stream_turn(
                pre_turn,
                step=step,
                state=state,
                plan_dir=plan_dir,
                config=config,
                env=env,
                claude_config_dir=claude_config_dir,
                model=model,
                read_only=read_only,
                prompt=pre_turn.body,
            )
        except CliError:
            main_turn = dataclasses.replace(
                main_turn,
                session_id=plan_session(
                    step,
                    stored_id=None,
                    fresh=True,
                    cfg=config,
                    rng=_seeded_rng_for_run(state, step, nonce=session_nonce + 1),
                ).main.session_id,
                resume=False,
            )
            session_id = main_turn.session_id
            continue
        raw_pre_output = (pre_result.stdout or "") + (pre_result.stderr or "")
        landed = _session_id_from_stream_output(raw_pre_output)
        if pre_result.returncode != 0 or (pre_turn.body.startswith("/clear") and not landed):
            main_turn = dataclasses.replace(
                main_turn,
                session_id=plan_session(
                    step,
                    stored_id=None,
                    fresh=True,
                    cfg=config,
                    rng=_seeded_rng_for_run(state, step, nonce=session_nonce + 1),
                ).main.session_id,
                resume=False,
            )
            session_id = main_turn.session_id
            continue
        if landed and landed != pre_turn.session_id:
            main_turn = dataclasses.replace(main_turn, session_id=landed)
            session_id = landed

    shannon_plan = _serialize_session_plan(plan)
    shannon_plan["session_id"] = session_id
    shannon_plan["main"]["delivery"] = "stdin"
    shannon_plan["main"]["resume"] = main_turn.resume

    try:
        command_result = _run_native_stream_turn(
            main_turn,
            step=step,
            state=state,
            plan_dir=plan_dir,
            config=config,
            env=env,
            claude_config_dir=claude_config_dir,
            model=model,
            read_only=read_only,
            prompt=prompt,
        )
    except CliError as error:
        if error.code in ("worker_timeout", "worker_stall"):
            sessions = state.get("sessions")
            if isinstance(sessions, dict):
                entry = sessions.get(session_key)
                entry_id = entry.get("id") if isinstance(entry, dict) else None
                if entry_id is not None and entry_id in {main_turn.session_id, persisted_session_id}:
                    sessions.pop(session_key, None)
        raw = str(error.extra.get("raw_output", ""))
        raise _with_failure_context(
            error,
            raw_output=raw,
            session_id=main_turn.session_id,
        ) from error

    raw_stdout = command_result.stdout or ""
    raw_stderr = command_result.stderr or ""
    raw_output = raw_stdout + raw_stderr

    if command_result.returncode != 0:
        try:
            parse_shannon_stream_output(
                raw_stdout,
                duration_ms=command_result.duration_ms,
                max_unknown_events=config.parser_max_unknown_events,
                metadata=auth_metadata,
            )
        except CliError as error:
            raise _with_failure_context(
                error,
                raw_output=raw_output,
                session_id=main_turn.session_id,
            ) from error
        _raise_for_native_stream_failure(
            returncode=command_result.returncode,
            raw_output=raw_output,
            session_id=main_turn.session_id,
        )

    try:
        result = parse_shannon_stream_output(
            raw_stdout,
            duration_ms=command_result.duration_ms,
            max_unknown_events=config.parser_max_unknown_events,
            metadata=auth_metadata,
        )
    except CliError as error:
        raise _with_failure_context(
            error,
            raw_output=raw_output,
            session_id=main_turn.session_id,
        ) from error

    payload = _normalize_stream_payload(step, result.payload)
    try:
        audit_step_payload(step, payload)
    except ModelStructuralAuditError as error:
        raise _with_failure_context(
            CliError("parse_error", str(error), extra={"raw_output": raw_output}),
            raw_output=raw_output,
            session_id=result.session_id or main_turn.session_id,
        ) from error
    except CliError as error:
        raise _with_failure_context(
            error,
            raw_output=raw_output,
            session_id=result.session_id or main_turn.session_id,
        ) from error

    result.payload = payload
    result.raw_output = raw_output
    result.rendered_prompt = prompt
    shannon_plan["worker_channel"] = auth_metadata["worker_channel"]
    shannon_plan["auth_channel"] = auth_metadata["auth_channel"]
    shannon_plan["auth_metadata"] = auth_metadata
    result.shannon_plan = shannon_plan
    result.worker_channel = auth_metadata["worker_channel"]
    result.auth_channel = auth_metadata["auth_channel"]
    result.auth_metadata = auth_metadata
    if result.session_id is None:
        result.session_id = main_turn.session_id
    if result.session_id is not None:
        result.shannon_plan["session_id"] = result.session_id
    return result
