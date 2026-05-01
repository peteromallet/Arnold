"""Worker orchestration: running Claude and Codex steps."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from megaplan.audits.robustness import build_empty_template
from megaplan.forms.provocations import select_active_checks
from megaplan.schemas import SCHEMAS, get_execution_schema_key
from megaplan.types import (
    CliError,
    DEFAULT_AGENT_ROUTING,
    MOCK_ENV_VAR,
    PlanState,
    SessionInfo,
    parse_agent_spec,
)
from megaplan._core import (
    apply_session_update,
    configured_robustness,
    creative_form_id,
    detect_available_agents,
    phase_timeout_seconds,
    get_effective,
    json_dump,
    latest_plan_meta_path,
    load_config,
    now_utc,
    read_json,
    schemas_root,
)
from megaplan.prompts import (
    create_claude_prompt,
    create_codex_prompt,
    create_hermes_prompt,
    _resolve_prompt_root,
)


_EXECUTE_STEPS = {"execute", "loop_execute"}
_CODEX_TEMPLATE_WRITE_STEPS = {"critique", "review"}

# Shared mapping from step name to schema filename, used by both
# run_claude_step and run_codex_step.
STEP_SCHEMA_FILENAMES: dict[str, str] = {
    "plan": "plan.json",
    "prep": "prep.json",
    "revise": "revise.json",
    "critique": "critique.json",
    "gate": "gate.json",
    "finalize": "finalize.json",
    "execute": "execution.json",
    "loop_plan": "loop_plan.json",
    "loop_execute": "loop_execute.json",
    "review": "review.json",
    "tiebreaker_researcher": "tiebreaker_researcher.json",
    "tiebreaker_challenger": "tiebreaker_challenger.json",
}

# Derive required keys per step from SCHEMAS so they aren't duplicated.
_STEP_REQUIRED_KEYS: dict[str, list[str]] = {
    step: SCHEMAS[filename].get("required", [])
    for step, filename in STEP_SCHEMA_FILENAMES.items()
}


@dataclass
class CommandResult:
    command: list[str]
    cwd: Path
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int


@dataclass
class WorkerResult:
    payload: dict[str, Any]
    raw_output: str
    duration_ms: int
    cost_usd: float
    session_id: str | None = None
    trace_output: str | None = None
    rendered_prompt: str | None = None
    model_actual: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


# ---------------------------------------------------------------------------
# Worker working directory resolution (git-worktree isolation)
#
# When megaplan is invoked from a git worktree, the plan's stored project_dir
# may point at a *different* checkout (usually the main repo). To avoid
# subprocess workers writing source code into the wrong working tree, resolve
# the "working directory" at CLI entry (CWD, or an explicit --work-dir
# override) and pass *that* through to the worker's --add-dir / -C flags.
#
# Plan state files (.megaplan/plans/...) still live under project_dir; only
# the source-code working tree tracked by the subprocess changes.
# ---------------------------------------------------------------------------

_WORK_DIR_OVERRIDE: Path | None = None
_WORK_DIR_WARNED: bool = False


def set_work_dir_override(path: Path | str | None) -> None:
    """Set an explicit working directory for subprocess workers.

    Typically called once from the CLI entry point with either an explicit
    --work-dir value or ``Path.cwd()``. Pass ``None`` to clear the override
    (primarily useful in tests).
    """
    global _WORK_DIR_OVERRIDE, _WORK_DIR_WARNED
    _WORK_DIR_OVERRIDE = Path(path) if path is not None else None
    _WORK_DIR_WARNED = False


def resolve_work_dir(state: PlanState) -> Path:
    """Return the source-code working directory for worker subprocesses.

    Precedence:
    1. Explicit override set via :func:`set_work_dir_override` (e.g. from the
       CLI ``--work-dir`` flag).
    2. The plan's stored ``project_dir`` (persisted at ``megaplan init``).
    3. Current working directory (``Path.cwd()``) as a last-resort fallback
       when the plan has no ``project_dir`` recorded.

    If the resolved path differs from the plan's stored ``project_dir``, a
    one-time informational line is printed so operators notice worktree
    divergence. (Callers that want a visually-loud operator warning should
    invoke :func:`warn_if_work_dir_differs_from_project_dir` from the phase
    entry point — this function keeps the log terse because it fires on every
    worker invocation.)
    """
    global _WORK_DIR_WARNED
    try:
        project_dir = Path(state["config"]["project_dir"]).resolve()
    except Exception:
        project_dir = None
    if _WORK_DIR_OVERRIDE is not None:
        work_dir = _WORK_DIR_OVERRIDE
    elif project_dir is not None:
        work_dir = project_dir
    else:
        work_dir = Path.cwd()
    try:
        resolved_work = work_dir.resolve()
    except Exception:
        resolved_work = work_dir
    if (
        not _WORK_DIR_WARNED
        and project_dir is not None
        and resolved_work != project_dir
    ):
        print(
            f"[megaplan] Using plan's project_dir ({project_dir}) for "
            f"subprocess --add-dir. Override with --work-dir if needed.",
            flush=True,
        )
        _WORK_DIR_WARNED = True
    return work_dir


def warn_if_work_dir_differs_from_project_dir(state: PlanState) -> None:
    """Emit a visible WARNING if the resolved work_dir is narrower than the
    plan's stored ``project_dir``.

    Intended to be called at the top of any phase that spawns sandboxed
    subprocess workers (execute, review, etc.). The warning alerts the
    operator that codex will be sandboxed to a subset of the project tree,
    which silently breaks writes to sibling subrepos.
    """
    try:
        project_dir = Path(state["config"]["project_dir"]).resolve()
    except Exception:
        return
    work_dir = resolve_work_dir(state)
    try:
        resolved_work = work_dir.resolve()
    except Exception:
        resolved_work = work_dir
    if resolved_work == project_dir:
        return
    try:
        cwd = Path.cwd().resolve()
    except Exception:
        cwd = Path.cwd()
    # ANSI bold yellow + warning emoji for visual distinction. Printed to
    # stderr so it is not swallowed by output redirection of the primary
    # response payload.
    prefix = "\033[1;33m" if sys.stderr.isatty() else ""
    suffix = "\033[0m" if sys.stderr.isatty() else ""
    message = (
        f"{prefix}⚠️  WARNING: codex will be sandboxed to {resolved_work}, "
        f"but the plan's project_dir is {project_dir}. File writes outside "
        f"{resolved_work} will fail. Pass --work-dir {project_dir} or cd to "
        f"{project_dir} to match the plan.{suffix}"
    )
    # CWD context helps the operator see *why* work_dir ended up narrower.
    if cwd != project_dir and cwd != resolved_work:
        message += f"\n[megaplan] (current shell cwd: {cwd})"
    print(message, file=sys.stderr, flush=True)


def run_command(
    command: list[str],
    *,
    cwd: Path,
    stdin_text: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
) -> CommandResult:
    started = time.monotonic()
    timeout = timeout or get_effective("execution", "worker_timeout_seconds")
    try:
        process = subprocess.run(
            command,
            cwd=str(cwd),
            input=stdin_text,
            text=True,
            capture_output=True,
            env=env,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise CliError(
            "agent_not_found",
            f"Command not found: {command[0]}",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        def _coerce_timeout_output(value: Any) -> str:
            if value is None:
                return ""
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return str(value)

        raise CliError(
            "worker_timeout",
            f"Command timed out after {timeout}s: {' '.join(command[:3])}...",
            extra={"raw_output": _coerce_timeout_output(exc.stdout) + _coerce_timeout_output(exc.stderr)},
        ) from exc
    return CommandResult(
        command=command,
        cwd=cwd,
        returncode=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
        duration_ms=int((time.monotonic() - started) * 1000),
    )


_CODEX_ERROR_PATTERNS: list[tuple[str, str, str]] = [
    # (pattern_substring, error_code, human_message)
    # Keep transport failures ahead of generic HTTP/status matches so
    # thread IDs or unrelated numbers do not get misclassified as 429s.
    ("failed to lookup address information", "connection_error", "Codex could not resolve the backend host"),
    ("failed to connect to websocket", "connection_error", "Codex could not connect to the realtime backend"),
    ("stream disconnected before completion", "connection_error", "Codex connection dropped before completion"),
    ("error sending request for url", "connection_error", "Codex could not send the backend request"),
    ("nodename nor servname provided", "connection_error", "Codex could not resolve the backend host"),
    ("connection error", "connection_error", "Codex could not connect to the API"),
    ("connection refused", "connection_error", "Codex could not connect to the API"),
    ("rate limit", "rate_limit", "Codex hit a rate limit"),
    ("rate_limit", "rate_limit", "Codex hit a rate limit"),
    ("quota", "quota_exceeded", "Codex quota exceeded"),
    ("context length", "context_overflow", "Prompt exceeded Codex context length"),
    ("context_length", "context_overflow", "Prompt exceeded Codex context length"),
    ("maximum context", "context_overflow", "Prompt exceeded Codex context length"),
    ("too many tokens", "context_overflow", "Prompt exceeded Codex context length"),
    ("timed out", "worker_timeout", "Codex request timed out"),
    ("timeout", "worker_timeout", "Codex request timed out"),
    ("invalid_json_schema", "schema_error", "Codex request rejected: invalid JSON schema"),
    ("invalid_request_error", "schema_error", "Codex request rejected: invalid request"),
    ("internal server error", "api_error", "Codex API returned an internal error"),
    ("model not found", "model_error", "Codex model not found or unavailable"),
    ("permission denied", "permission_error", "Codex permission denied"),
    ("authentication", "auth_error", "Codex authentication failed"),
    ("unauthorized", "auth_error", "Codex authentication failed"),
]


def _codex_retry_guidance(step: str | None = None) -> str:
    if step in _EXECUTE_STEPS:
        return (
            "Re-run the same execute step on Codex once before changing agent; "
            "preserve the existing session path unless a fresh retry is explicitly needed."
        )
    return "Re-run the same step on Codex once before changing agent."


def _diagnose_codex_failure(raw: str, returncode: int) -> tuple[str, str]:
    """Parse Codex stderr/stdout for known error patterns. Returns (error_code, message)."""
    lower = raw.lower()
    for pattern, code, message in _CODEX_ERROR_PATTERNS:
        if pattern in lower:
            return code, f"{message}. {_codex_retry_guidance()}"
    if re.search(r"\bhttp\s*429\b", lower) or re.search(r"\b429\b", lower):
        return "rate_limit", f"Codex hit a rate limit (HTTP 429). {_codex_retry_guidance()}"
    if re.search(r"\bhttp\s*400\b", lower) or re.search(r"\b400\b", lower):
        return "schema_error", f"Codex API rejected request (HTTP 400). {_codex_retry_guidance()}"
    if re.search(r"\bhttp\s*500\b", lower) or re.search(r"\b500\b", lower):
        return "api_error", f"Codex API returned an internal error (HTTP 500). {_codex_retry_guidance()}"
    if re.search(r"\bhttp\s*502\b", lower) or re.search(r"\b502\b", lower):
        return "api_error", f"Codex API returned a gateway error (HTTP 502). {_codex_retry_guidance()}"
    if re.search(r"\bhttp\s*503\b", lower) or re.search(r"\b503\b", lower):
        return "api_error", f"Codex API service unavailable (HTTP 503). {_codex_retry_guidance()}"
    return "worker_error", (
        f"Codex step failed with exit code {returncode} (no recognized error pattern in output). "
        + _codex_retry_guidance()
    )


def _codex_timeout_for_step(step: str) -> int:
    configured_timeout = int(get_effective("execution", "worker_timeout_seconds"))
    return phase_timeout_seconds(step, configured_timeout_seconds=configured_timeout)


def _codex_exec_mode_flags(step: str) -> list[str]:
    if step in _EXECUTE_STEPS and _trusted_container():
        return []
    # All non-execute phases (plan, prep, critique, revise, gate, finalize,
    # review) need to write template artifacts (plan markdown, metadata JSON,
    # critique/review JSON, finalize.json). Without --full-auto codex defaults
    # to on-request approval, which fails silently when stdin is the prompt
    # (no tty). Default everything to --full-auto and let the workspace-write
    # sandbox plus writable_roots configuration constrain actual writes.
    return ["--full-auto"]


_ROLLOUT_MISSING_PATTERNS = (
    "no rollout found for thread id",
    "thread/resume failed",
)


# Patterns that indicate the worker's *session history* has absorbed an
# obsolete environmental failure (e.g. from an earlier invocation before the
# container was configured for trusted-mode). On a later invocation the model
# reads this history, believes the environment is still broken, and returns
# "blocked" without attempting commands — causing infinite retry loops.
# Detecting these in the raw output and invalidating the session forces a
# fresh start so the belief can't survive.
_POISONED_SESSION_PATTERNS: tuple[tuple[str, ...], ...] = (
    # Single-substring match (any one of these is enough).
    ("bwrap: creating new namespace failed",),
    # Multi-substring match (all substrings must be present).
    ("permission denied", "cannot start sandbox"),
    ("repository command execution", "unavailable", "sandbox"),
    ("permissions profile", "does not define any recognized filesystem entries"),
)


def _is_rollout_missing(raw: str) -> bool:
    """Detect Codex's signal that a session/thread id has no rollout.

    Happens when: container was restarted between phases and codex's session
    store (usually ``$HOME/.codex/sessions``) was wiped, but megaplan's plan
    state still has the session id and tries to ``codex exec resume <id>``.

    Match is case-insensitive on known substrings so minor wording changes
    upstream don't break recovery. Fall back to failing loudly if Codex
    introduces a new error string — false positives here would mask real
    session crashes.
    """
    if not raw:
        return False
    lowered = raw.lower()
    return any(pat in lowered for pat in _ROLLOUT_MISSING_PATTERNS)


def _is_poisoned_environmental_failure(raw: str) -> bool:
    """Detect obsolete sandbox/environment failure beliefs in worker output.

    Returns True when the raw output contains known-stale environment errors
    that a persistent session may have absorbed from a prior invocation
    (before trusted-container mode was enabled). See the comment on
    ``_POISONED_SESSION_PATTERNS`` above for motivation.

    The check is intentionally conservative: every pattern is a conjunction
    of substrings all of which must be present (case-insensitive). A single
    sandbox error combined with a generic "Permission denied" elsewhere in a
    long trace should not trigger unless the full phrase appears.
    """
    if not raw:
        return False
    lowered = raw.lower()
    for group in _POISONED_SESSION_PATTERNS:
        if all(sub in lowered for sub in group):
            return True
    return False


# System directories that should never be auto-promoted to a writable
# sandbox root. Used by :func:`_auto_writable_roots`. The check below
# matches the resolved path against these roots exactly *and* against
# direct children (e.g. /usr) — we never want to widen the sandbox to
# anything that broad even if the user happens to have project_dir at
# /usr/local/foo.
_AUTO_ROOT_FORBIDDEN: tuple[Path, ...] = (
    Path("/"),
    Path("/usr"),
    Path("/etc"),
    Path("/var"),
    Path("/private"),
    Path("/System"),
    Path("/Library"),
    Path("/bin"),
    Path("/sbin"),
    Path("/opt"),
    Path("/tmp"),
    Path.home(),
)


def _is_safe_auto_root(candidate: Path) -> bool:
    """Return True iff *candidate* is safe to auto-promote to a writable root.

    Excludes (a) system directories, (b) the user's home directory itself
    (granting write to ~ would defeat the sandbox), and (c) any path
    shallower than two levels below root (e.g. ``/Users``, ``/home``).
    """
    try:
        resolved = candidate.resolve()
    except Exception:
        return False
    # Reject filesystem root and very shallow paths.
    if len(resolved.parts) < 3:
        return False
    for forbidden in _AUTO_ROOT_FORBIDDEN:
        try:
            forbidden_resolved = forbidden.resolve()
        except Exception:
            continue
        if resolved == forbidden_resolved:
            return False
    return True


def _auto_writable_roots(work_dir: Path) -> list[str]:
    """Auto-detect additional writable roots that surround *work_dir*.

    Strategy: walk up from *work_dir* looking for a workspace marker — the
    nearest ancestor containing a ``.git`` directory or a sibling
    ``.megaplan/`` directory. If that ancestor is a strict parent of
    *work_dir* and passes :func:`_is_safe_auto_root`, return it as an
    additional writable root.

    This handles the common monorepo / multi-package workspace case where
    ``project_dir`` is a subdirectory (e.g. ``tools/``) but legitimate plan
    output writes to sibling directories (``effects/``, ``themes/``,
    ``animations/``). Without this, codex's ``workspace-write`` sandbox
    blocks those writes with ``sandbox denied creating '../foo' outside the
    writable root``.

    Disable with ``MEGAPLAN_NARROW_SANDBOX=1`` (e.g. for CI runs of
    untrusted plans where the narrow default is the safer choice).
    """
    if os.environ.get("MEGAPLAN_NARROW_SANDBOX", "").strip().lower() in {
        "1", "true", "yes", "on",
    }:
        return []
    try:
        start = Path(work_dir).resolve()
    except Exception:
        return []
    current = start.parent
    seen_root: Path | None = None
    while True:
        if seen_root is None:
            if (current / ".git").exists() or (current / ".megaplan").is_dir():
                seen_root = current
                break
        parent = current.parent
        if parent == current:
            break
        current = parent
    if seen_root is None or seen_root == start:
        return []
    if not _is_safe_auto_root(seen_root):
        return []
    return [str(seen_root)]


def _trusted_container() -> bool:
    """Return True when MEGAPLAN_TRUSTED_CONTAINER is set to a truthy value.

    In a locked-down container (Docker/Railway/Kubernetes without
    user-namespace capabilities), bubblewrap's default sandbox fails with
    ``bwrap: Creating new namespace failed: Permission denied`` because
    ``kernel.unprivileged_userns_clone`` is not settable by an unprivileged
    user. Per the official guidance at
    https://docs.docker.com/ai/sandboxes/agents/codex/ the operator is
    expected to rely on container-level isolation and bypass the Codex
    sandbox entirely. Setting ``MEGAPLAN_TRUSTED_CONTAINER=1`` on the
    worker environment activates that path.
    """
    return os.environ.get("MEGAPLAN_TRUSTED_CONTAINER", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _codex_child_env() -> dict[str, str]:
    env = os.environ.copy()
    # Nested Codex workers should not inherit the parent Codex session state.
    # Those variables can cause the child to attach to the outer thread/CI
    # context instead of behaving like an isolated worker invocation.
    env.pop("CODEX_THREAD_ID", None)
    env.pop("CODEX_CI", None)
    return env


def _merge_partial_output(raw_output: str, output_path: Path) -> str:
    merged = raw_output or ""
    try:
        partial = output_path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        partial = ""
    if partial and partial not in merged:
        if merged and not merged.endswith("\n"):
            merged += "\n"
        merged += "[partial_output_file]\n" + partial
    return merged


def extract_session_id(raw: str) -> str | None:
    # Try structured JSONL first (codex --json emits {"type":"thread.started","thread_id":"..."})
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and obj.get("thread_id"):
                return str(obj["thread_id"])
        except (json.JSONDecodeError, ValueError):
            continue
    # Fallback: unstructured text pattern
    match = re.search(r"\bsession[_ ]id[: ]+([0-9a-fA-F-]{8,})", raw)
    return match.group(1) if match else None


def parse_claude_envelope(raw: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliError("parse_error", f"Claude output was not valid JSON: {exc}", extra={"raw_output": raw}) from exc
    if isinstance(envelope, dict) and envelope.get("is_error"):
        message = envelope.get("result") or envelope.get("message") or "Claude returned an error"
        lower = str(message).lower()
        error_code = "worker_error"
        if any(pattern in lower for pattern in ("not logged in", "/login", "unauthorized", "authentication")):
            error_code = "auth_error"
        raise CliError(error_code, f"Claude step failed: {message}", extra={"raw_output": raw})
    # When using --json-schema, structured output lives in "structured_output"
    # rather than "result" (which may be empty).
    payload: Any = envelope
    if isinstance(envelope, dict):
        if "structured_output" in envelope and isinstance(envelope["structured_output"], dict):
            payload = envelope["structured_output"]
        elif "result" in envelope:
            payload = envelope["result"]
    if isinstance(payload, str):
        if not payload.strip():
            raise CliError("parse_error", "Claude returned empty result (check structured_output field)", extra={"raw_output": raw})
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise CliError("parse_error", f"Claude result payload was not valid JSON: {exc}", extra={"raw_output": raw}) from exc
    if not isinstance(payload, dict):
        raise CliError("parse_error", "Claude result payload was not an object", extra={"raw_output": raw})
    return envelope, payload


def _extract_json_candidates_from_raw(raw: str) -> list[dict[str, Any]]:
    """Extract plausible JSON payload objects from raw agent output."""

    def _iter_nested_json_dicts(value: Any) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        if isinstance(value, dict):
            candidates.append(value)
            prioritized_keys = (
                "structured_output",
                "result",
                "payload",
                "text",
                "message",
            )
            for key in prioritized_keys:
                if key not in value:
                    continue
                nested = value.get(key)
                candidates.extend(_iter_nested_json_dicts(nested))
            for nested in value.values():
                candidates.extend(_iter_nested_json_dicts(nested))
            return candidates
        if isinstance(value, list):
            for item in value:
                candidates.extend(_iter_nested_json_dicts(item))
            return candidates
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("{") or text.startswith("["):
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    return []
                return _iter_nested_json_dicts(parsed)
        return []

    candidates: list[dict[str, Any]] = []

    # Strategy 1: look for ```json ... ``` fenced blocks
    fenced = re.findall(r"```json\s*\n(.*?)```", raw, re.DOTALL)
    for block in fenced:
        try:
            obj = json.loads(block.strip())
            candidates.extend(_iter_nested_json_dicts(obj))
        except json.JSONDecodeError:
            continue
    # Strategy 2: parse JSONL/event-stream lines and inspect nested message fields.
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        candidates.extend(_iter_nested_json_dicts(obj))
    # Strategy 3: scan for the first decodable JSON object, even when
    # additional logs/traces are appended after it.
    decoder = json.JSONDecoder()
    search_start = 0
    while True:
        brace_start = raw.find("{", search_start)
        if brace_start < 0:
            break
        try:
            obj, _end = decoder.raw_decode(raw[brace_start:])
        except json.JSONDecodeError:
            search_start = brace_start + 1
            continue
        candidates.extend(_iter_nested_json_dicts(obj))
        search_start = brace_start + 1
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            marker = json_dump(candidate)
        except Exception:
            marker = repr(candidate)
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(candidate)
    return deduped


def _extract_json_from_raw(raw: str) -> dict[str, Any] | None:
    """Return the first plausible JSON object extracted from raw agent output."""
    candidates = _extract_json_candidates_from_raw(raw)
    if candidates:
        return candidates[0]
    return None


def _normalize_codex_payload(step: str, payload: dict[str, Any]) -> dict[str, Any]:
    if step == "revise" and "changes_summary" not in payload:
        normalized = dict(payload)
        flags_addressed = normalized.get("flags_addressed", [])
        if isinstance(flags_addressed, list) and flags_addressed:
            normalized["changes_summary"] = "Updated the plan to address the critique and gate feedback."
        else:
            normalized["changes_summary"] = "No critique flags were raised; refined the plan for execution."
        return normalized
    return payload


def parse_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = read_json(path)
    except FileNotFoundError as exc:
        raise CliError("parse_error", f"Output file {path.name} was not created") from exc
    except json.JSONDecodeError as exc:
        raise CliError("parse_error", f"Output file {path.name} was not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise CliError("parse_error", f"Output file {path.name} did not contain a JSON object")
    return payload


def _recover_codex_payload(
    step: str,
    *,
    plan_dir: Path,
    output_path: Path,
    raw: str,
) -> dict[str, Any] | None:
    payload = None
    file_recovered_candidates: list[dict[str, Any]] = []
    try:
        payload = parse_json_file(output_path)
    except CliError:
        try:
            file_raw = output_path.read_text(encoding="utf-8", errors="replace")
            file_recovered_candidates.extend(_extract_json_candidates_from_raw(file_raw))
        except OSError:
            pass
    if payload is None:
        fallback_names = {
            "critique": "critique_output.json",
        }
        fallback_name = fallback_names.get(step, f"{step}_output.json")
        fallback_path = plan_dir / fallback_name
        if fallback_path != output_path and fallback_path.exists():
            try:
                payload = parse_json_file(fallback_path)
            except CliError:
                try:
                    fallback_raw = fallback_path.read_text(encoding="utf-8", errors="replace")
                    file_recovered_candidates.extend(_extract_json_candidates_from_raw(fallback_raw))
                except OSError:
                    pass
    raw_candidates = _extract_json_candidates_from_raw(raw)
    candidate_payloads: list[dict[str, Any]] = []
    if payload is not None:
        candidate_payloads.append(payload)
    candidate_payloads.extend(file_recovered_candidates)
    candidate_payloads.extend(raw_candidates)
    valid_payloads: list[dict[str, Any]] = []
    for candidate in candidate_payloads:
        normalized = _normalize_codex_payload(step, candidate)
        try:
            validate_payload(step, normalized)
        except CliError:
            continue
        valid_payloads.append(normalized)
    if not valid_payloads:
        return None
    if step == "critique" and len(valid_payloads) > 1:
        def _findings_count(item: dict[str, Any]) -> int:
            checks = item.get("checks", [])
            return sum(len(check.get("findings", [])) for check in checks if isinstance(check, dict))

        return max(valid_payloads, key=_findings_count)
    return valid_payloads[0]


def validate_payload(step: str, payload: dict[str, Any]) -> None:
    if step == "execute":
        full_required = _STEP_REQUIRED_KEYS.get(step, [])
        missing_full = [key for key in full_required if key not in payload]
        if not missing_full:
            return
        batch_required = ["task_updates", "sense_check_acknowledgments"]
        missing_batch = [key for key in batch_required if key not in payload]
        if not missing_batch:
            return
        raise CliError(
            "parse_error",
            (
                "execute output missing required keys: "
                + ", ".join(missing_full)
                + ". Batch execute payloads may omit aggregate fields, "
                + "but must include task_updates and sense_check_acknowledgments."
            ),
        )
    required = _STEP_REQUIRED_KEYS.get(step)
    if required is None:
        return
    missing = [key for key in required if key not in payload]
    if missing:
        raise CliError("parse_error", f"{step} output missing required keys: {', '.join(missing)}")


def _mock_result(
    payload: dict[str, Any],
    *,
    trace_output: str | None = None,
) -> WorkerResult:
    return WorkerResult(
        payload=payload,
        raw_output=json_dump(payload),
        duration_ms=10,
        cost_usd=0.0,
        session_id=str(uuid.uuid4()),
        trace_output=trace_output,
    )


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(base_value, value)
            continue
        merged[key] = value
    return merged


def _default_mock_plan_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "plan": textwrap.dedent(
            f"""
            # Implementation Plan: Mock Planning Pass

            ## Overview
            Produce a concrete plan for: {state['idea']}. Keep the scope grounded in the repository and define validation before execution.

            ## Step 1: Inspect the current flow (`megaplan/workers.py`)
            **Scope:** Small
            1. **Inspect** the planner and prompt touch points before editing (`megaplan/workers.py:199`, `megaplan/prompts.py:29`).

            ## Step 2: Implement the smallest viable change (`megaplan/handlers.py`)
            **Scope:** Medium
            1. **Update** the narrowest set of files required to implement the idea (`megaplan/handlers.py:400`).
            2. **Capture** any non-obvious behavior with a short example.
               ```python
               result = "keep the plan structure consistent"
               ```

            ## Step 3: Verify the behavior (`tests/test_megaplan.py`)
            **Scope:** Small
            1. **Run** focused checks that prove the change works (`tests/test_megaplan.py:1`).

            ## Execution Order
            1. Inspect before editing so the plan stays repo-specific.
            2. Implement before expanding verification.

            ## Validation Order
            1. Run targeted tests first.
            2. Run broader checks after the core change lands.
            """
        ).strip(),
        "questions": ["Are there existing patterns in the repo that should be preserved?"],
        "success_criteria": [
            {"criterion": "A concrete implementation path exists.", "priority": "must"},
            {"criterion": "Verification is defined before execution.", "priority": "should"},
        ],
        "assumptions": ["The project directory is writable."],
    }
    return payload


def _default_mock_prep_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    del plan_dir
    return {
        "task_summary": str(state.get("idea", "")).strip() or "Prepare a concise engineering brief for the requested task.",
        "key_evidence": [],
        "relevant_code": [],
        "test_expectations": [],
        "constraints": [],
        "suggested_approach": "Inspect the code paths named in the task, read nearby tests first when they exist, then carry the distilled brief into planning.",
    }


def _loop_goal(state: dict[str, Any]) -> str:
    return str(state.get("idea", state.get("spec", {}).get("goal", "")))


def _default_mock_loop_plan_payload(state: dict[str, Any], plan_dir: Path) -> dict[str, Any]:
    spec = state.get("spec", {})
    goal = _loop_goal(state)
    return {
        "spec_updates": {
            "known_issues": spec.get("known_issues", []),
            "tried_and_failed": spec.get("tried_and_failed", []),
            "best_result_summary": f"Most recent mock planning pass for: {goal}",
        },
        "next_action": "Run the project command, inspect the failures, and prepare the next minimal fix.",
        "reasoning": "The loop spec is initialized and ready for an execution pass based on the current goal and retained context.",
    }


def _default_mock_loop_execute_payload(
    state: dict[str, Any],
    plan_dir: Path,
    *,
    prompt_override: str | None = None,
) -> dict[str, Any]:
    spec = state.get("spec", {})
    goal = _loop_goal(state)
    return {
        "diagnosis": f"Mock execution diagnosis for goal: {goal}",
        "fix_description": "Inspect the command failure, update the smallest relevant file, and rerun the command.",
        "files_to_change": list(spec.get("allowed_changes", []))[:3],
        "confidence": "medium",
        "outcome": "continue",
        "should_pause": False,
    }


def _default_mock_critique_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    iteration = state["iteration"] or 1
    robustness = configured_robustness(state)
    active_checks = select_active_checks(state, robustness, plan_dir=plan_dir)
    checks = build_empty_template(active_checks)
    if iteration == 1:
        return {
            "checks": [
                {
                    **check,
                    "findings": [
                        {
                            "detail": "Mock critique found a concrete repository issue that should be addressed before proceeding.",
                            "flagged": True,
                        }
                    ],
                }
                for check in checks
            ],
            "flags": [
                {
                    "id": "FLAG-001",
                    "concern": "The plan does not name the files or modules it expects to touch.",
                    "category": "completeness",
                    "severity_hint": "likely-significant",
                    "evidence": "Execution could drift because there is no repo-specific scope.",
                },
                {
                    "id": "FLAG-002",
                    "concern": "The plan does not define an observable verification command.",
                    "category": "correctness",
                    "severity_hint": "likely-significant",
                    "evidence": "Success cannot be demonstrated without a concrete check.",
                },
            ],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        }
    return {
        "checks": [
            {
                **check,
                "findings": [
                    {
                        "detail": "Mock critique verified the revised plan against the repository context and found no remaining issue.",
                        "flagged": False,
                    }
                ],
            }
            for check in checks
        ],
        "flags": [],
        "verified_flag_ids": [*(check["id"] for check in checks), "FLAG-001", "FLAG-002"],
        "disputed_flag_ids": [],
    }



def _default_mock_revise_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    return {
        "plan": textwrap.dedent(
            f"""
            # Implementation Plan: Mock Revision Pass

            ## Overview
            Refine the plan for: {state['idea']}. Tighten file-level scope and keep validation explicit.

            ## Step 1: Reconfirm file scope (`megaplan/handlers.py`)
            **Scope:** Small
            1. **Inspect** the exact edit points before changing the plan (`megaplan/handlers.py:540`).

            ## Step 2: Tighten the implementation slice (`megaplan/workers.py`)
            **Scope:** Medium
            1. **Limit** the plan to the smallest coherent change set (`megaplan/workers.py:256`).
            2. **Illustrate** the intended shape when it helps reviewers.
               ```python
               changes_summary = "Added explicit scope and verification details."
               ```

            ## Step 3: Reconfirm verification (`tests/test_workers.py`)
            **Scope:** Small
            1. **Run** a concrete verification command and record the expected proof point (`tests/test_workers.py:251`).

            ## Execution Order
            1. Re-scope the plan before adjusting implementation details.
            2. Re-run validation after the plan is tightened.

            ## Validation Order
            1. Start with the focused worker and handler tests.
            2. End with the broader suite if the focused checks pass.
            """
        ).strip(),
        "changes_summary": "Added explicit repo-scoping and verification steps.",
        "flags_addressed": ["FLAG-001", "FLAG-002"],
        "assumptions": ["The repository contains enough context for implementation."],
        "success_criteria": [
            {"criterion": "The plan identifies exact touch points before editing.", "priority": "must"},
            {"criterion": "A concrete verification command is defined.", "priority": "should"},
        ],
        "questions": [],
    }


def _default_mock_gate_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    recommendation = "ITERATE" if state["iteration"] == 1 else "PROCEED"
    return {
        "recommendation": recommendation,
        "rationale": (
            "First critique cycle still needs another pass."
            if recommendation == "ITERATE"
            else "Signals are strong enough to move into execution."
        ),
        "signals_assessment": (
            "Iteration 1 still carries unresolved significant flags and should revise."
            if recommendation == "ITERATE"
            else "Weighted score and loop trajectory support proceeding."
        ),
        "warnings": [],
        "settled_decisions": [],
        "flag_resolutions": [],
        "accepted_tradeoffs": [],
    }


def _default_mock_finalize_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    return {
        "tasks": [
            {
                "id": "T1",
                "description": f"Implement: {state['idea']}",
                "depends_on": [],
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            },
            {
                "id": "T2",
                "description": "Verify success criteria",
                "depends_on": [],
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            },
        ],
        "watch_items": ["Ensure repository state matches plan assumptions"],
        "sense_checks": [
            {
                "id": "SC1",
                "task_id": "T1",
                "question": "Verify implementation matches the stated idea.",
                "executor_note": "",
                "verdict": "",
            },
            {
                "id": "SC2",
                "task_id": "T2",
                "question": "Verify success criteria were actually checked.",
                "executor_note": "",
                "verdict": "",
            },
        ],
        "user_actions": [],
        "meta_commentary": "This is a mock finalize output.",
        "validation": {
            "plan_steps_covered": [
                {"plan_step_summary": f"Implement: {state['idea']}", "finalize_item_ids": ["T1"]},
                {"plan_step_summary": "Verify success criteria", "finalize_item_ids": ["T2"]},
            ],
            "orphan_tasks": [],
            "completeness_notes": "All plan steps mapped to tasks.",
            "coverage_complete": True,
        },
    }


def _task_ids_from_prompt_override(prompt_override: str | None) -> set[str] | None:
    if prompt_override is None:
        return None
    match = re.search(r"Only produce `?task_updates`? for these tasks:\s*\[([^\]]*)\]", prompt_override)
    if match is None:
        return None
    task_ids = {item.strip() for item in match.group(1).split(",") if item.strip()}
    return task_ids


def _default_mock_execute_payload(
    state: PlanState,
    plan_dir: Path,
    *,
    prompt_override: str | None = None,
) -> dict[str, Any]:
    target = Path(state["config"]["project_dir"]) / "IMPLEMENTED_BY_MEGAPLAN.txt"
    relative_target = str(target.relative_to(Path(state["config"]["project_dir"])))
    payload = {
        "output": "Mock execution completed successfully.",
        "files_changed": [relative_target],
        "commands_run": ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"],
        "deviations": [],
        "task_updates": [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "Implemented via mock worker output and wrote IMPLEMENTED_BY_MEGAPLAN.txt.",
                "files_changed": [relative_target],
                "commands_run": ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"],
            },
            {
                "task_id": "T2",
                "status": "done",
                "executor_notes": "Verified success criteria via mock worker output and command checks.",
                "files_changed": [],
                "commands_run": ["mock-verify success criteria"],
            },
        ],
        "sense_check_acknowledgments": [
            {
                "sense_check_id": "SC1",
                "executor_note": "Confirmed the implementation artifact was written for the main task.",
            },
            {
                "sense_check_id": "SC2",
                "executor_note": "Confirmed the verification-only task is backed by command evidence.",
            },
        ],
    }
    batch_task_ids = _task_ids_from_prompt_override(prompt_override)
    if batch_task_ids is None:
        return payload
    payload["task_updates"] = [
        task_update
        for task_update in payload["task_updates"]
        if task_update["task_id"] in batch_task_ids
    ]
    payload["sense_check_acknowledgments"] = [
        acknowledgment
        for acknowledgment in payload["sense_check_acknowledgments"]
        if acknowledgment["sense_check_id"] in {
            f"SC{task_id[1:]}"
            for task_id in batch_task_ids
            if task_id.startswith("T")
        }
    ]
    return payload


def _default_mock_review_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    meta = read_json(latest_plan_meta_path(plan_dir, state))
    criteria = []
    for entry in meta.get("success_criteria", []):
        if isinstance(entry, dict):
            name = entry.get("criterion", str(entry))
            priority = entry.get("priority", "must")
        else:
            name = str(entry)
            priority = "must"
        criteria.append({"name": name, "priority": priority, "pass": "pass", "evidence": "Mock execution and artifacts satisfy the criterion."})
    return {
        "review_verdict": "approved",
        "checks": [],
        "pre_check_flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
        "criteria": criteria,
        "issues": [],
        "rework_items": [],
        "summary": "Mock review passed.",
        "task_verdicts": [
            {
                "task_id": "T1",
                "reviewer_verdict": "Pass - mock verified with file-backed implementation evidence.",
                "evidence_files": [str((Path(state["config"]["project_dir"]) / "IMPLEMENTED_BY_MEGAPLAN.txt").relative_to(Path(state["config"]["project_dir"])))],
            },
            {
                "task_id": "T2",
                "reviewer_verdict": "Pass - verification task was reviewed via command evidence and executor notes rather than a changed file.",
                "evidence_files": [],
            },
        ],
        "sense_check_verdicts": [
            {"sense_check_id": "SC1", "verdict": "Confirmed."},
            {"sense_check_id": "SC2", "verdict": "Confirmed."},
        ],
    }


_MockPayloadBuilder = Callable[[dict[str, Any], Path], dict[str, Any]]

_MOCK_DEFAULTS: dict[str, _MockPayloadBuilder] = {
    "plan": _default_mock_plan_payload,
    "prep": _default_mock_prep_payload,
    "loop_plan": _default_mock_loop_plan_payload,
    "critique": _default_mock_critique_payload,
    "revise": _default_mock_revise_payload,
    "gate": _default_mock_gate_payload,
    "finalize": _default_mock_finalize_payload,
    "execute": _default_mock_execute_payload,
    "loop_execute": _default_mock_loop_execute_payload,
    "review": _default_mock_review_payload,
}


def _build_mock_payload(step: str, state: dict[str, Any], plan_dir: Path, **overrides: Any) -> dict[str, Any]:
    builder = _MOCK_DEFAULTS.get(step)
    if builder is None:
        raise CliError("unsupported_step", f"Mock worker does not support '{step}'")
    prompt_override = overrides.pop("prompt_override", None)
    if step in _EXECUTE_STEPS:
        if step == "loop_execute":
            return _deep_merge(_default_mock_loop_execute_payload(state, plan_dir, prompt_override=prompt_override), overrides)
        return _deep_merge(_default_mock_execute_payload(state, plan_dir, prompt_override=prompt_override), overrides)
    return _deep_merge(builder(state, plan_dir), overrides)


def _mock_plan(state: PlanState, plan_dir: Path) -> WorkerResult:
    return _mock_result(_build_mock_payload("plan", state, plan_dir))


def _mock_prep(state: PlanState, plan_dir: Path) -> WorkerResult:
    return _mock_result(_build_mock_payload("prep", state, plan_dir))


def _mock_loop_plan(state: PlanState, plan_dir: Path) -> WorkerResult:
    return _mock_result(_build_mock_payload("loop_plan", state, plan_dir))



def _mock_critique(state: PlanState, plan_dir: Path) -> WorkerResult:
    return _mock_result(_build_mock_payload("critique", state, plan_dir))


def _mock_revise(state: PlanState, plan_dir: Path) -> WorkerResult:
    return _mock_result(_build_mock_payload("revise", state, plan_dir))


def _mock_gate(state: PlanState, plan_dir: Path) -> WorkerResult:
    return _mock_result(_build_mock_payload("gate", state, plan_dir))


def _mock_finalize(state: PlanState, plan_dir: Path) -> WorkerResult:
    return _mock_result(_build_mock_payload("finalize", state, plan_dir))


def _mock_execute(state: PlanState, plan_dir: Path, *, prompt_override: str | None = None) -> WorkerResult:
    target = Path(state["config"]["project_dir"]) / "IMPLEMENTED_BY_MEGAPLAN.txt"
    target.write_text("mock execution completed\n", encoding="utf-8")
    return _mock_result(
        _build_mock_payload("execute", state, plan_dir, prompt_override=prompt_override),
        trace_output='{"event":"mock-execute"}\n',
    )


def _mock_loop_execute(state: PlanState, plan_dir: Path, *, prompt_override: str | None = None) -> WorkerResult:
    return _mock_result(
        _build_mock_payload("loop_execute", state, plan_dir, prompt_override=prompt_override),
        trace_output='{"event":"mock-loop-execute"}\n',
    )


def _mock_review(state: PlanState, plan_dir: Path) -> WorkerResult:
    return _mock_result(_build_mock_payload("review", state, plan_dir))


_MockHandler = Callable[..., WorkerResult]

_MOCK_DISPATCH: dict[str, _MockHandler] = {
    "plan": _mock_plan,
    "prep": _mock_prep,
    "loop_plan": _mock_loop_plan,
    "critique": _mock_critique,
    "revise": _mock_revise,
    "gate": _mock_gate,
    "finalize": _mock_finalize,
    "execute": _mock_execute,
    "loop_execute": _mock_loop_execute,
    "review": _mock_review,
}


def mock_worker_output(
    step: str,
    state: PlanState,
    plan_dir: Path,
    *,
    prompt_override: str | None = None,
    prompt_kwargs: dict[str, Any] | None = None,
) -> WorkerResult:
    del prompt_kwargs
    handler = _MOCK_DISPATCH.get(step)
    if handler is None:
        raise CliError("unsupported_step", f"Mock worker does not support '{step}'")
    if step in _EXECUTE_STEPS:
        result = handler(state, plan_dir, prompt_override=prompt_override)
    else:
        result = handler(state, plan_dir)
    try:
        root = _resolve_prompt_root(plan_dir, None)
        side_effect_paths = (
            plan_dir / "critique_output.json",
            plan_dir / "review_output.json",
        )
        preexisting_paths = {path for path in side_effect_paths if path.exists()}
        result.rendered_prompt = create_hermes_prompt(step, state, plan_dir, root=root)
        for path in side_effect_paths:
            if path.exists() and path not in preexisting_paths:
                path.unlink()
    except Exception:
        result.rendered_prompt = prompt_override
    return result


def session_key_for(step: str, agent: str, model: str | None = None) -> str:
    if step in {"plan", "revise"}:
        key = f"{agent}_planner"
    elif step == "critique":
        key = f"{agent}_critic"
    elif step == "gate":
        key = f"{agent}_gatekeeper"
    elif step == "finalize":
        key = f"{agent}_finalizer"
    elif step == "execute":
        key = f"{agent}_executor"
    elif step == "review":
        key = f"{agent}_reviewer"
    else:
        key = f"{agent}_{step}"
    if model:
        key += f"_{hashlib.sha256(model.encode()).hexdigest()[:8]}"
    return key


def update_session_state(step: str, agent: str, session_id: str | None, *, mode: str, refreshed: bool, model: str | None = None, existing_sessions: dict[str, Any] | None = None) -> tuple[str, SessionInfo] | None:
    """Build a session entry for the given step.

    Returns ``(key, entry)`` so the caller can store it on the state dict,
    or ``None`` when there is no session_id to record.
    """
    if not session_id:
        return None
    key = session_key_for(step, agent, model=model)
    if existing_sessions is None:
        existing_sessions = {}
    entry = {
        "id": session_id,
        "mode": mode,
        "created_at": existing_sessions.get(key, {}).get("created_at", now_utc()),
        "last_used_at": now_utc(),
        "refreshed": refreshed,
    }
    return key, entry


def run_claude_step(
    step: str,
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    fresh: bool,
    prompt_override: str | None = None,
    prompt_kwargs: dict[str, Any] | None = None,
) -> WorkerResult:
    if os.getenv(MOCK_ENV_VAR) == "1":
        return mock_worker_output(step, state, plan_dir, prompt_override=prompt_override, prompt_kwargs=prompt_kwargs)
    project_dir = Path(state["config"]["project_dir"])
    work_dir = resolve_work_dir(state)
    plan_mode = state["config"].get("mode", "code")
    schema_name = (
        get_execution_schema_key(plan_mode, form=creative_form_id(state))
        if step == "execute"
        else STEP_SCHEMA_FILENAMES[step]
    )
    schema_text = json.dumps(read_json(schemas_root(root) / schema_name))
    session_key = session_key_for(step, "claude")
    session = state["sessions"].get(session_key, {})
    session_id = session.get("id")
    command = ["claude", "-p", "--output-format", "json", "--json-schema", schema_text, "--add-dir", str(work_dir)]
    if step in _EXECUTE_STEPS:
        command.extend(["--permission-mode", "bypassPermissions"])
    if session_id and not fresh:
        command.extend(["--resume", session_id])
    else:
        session_id = str(uuid.uuid4())
        command.extend(["--session-id", session_id])
    prompt = prompt_override if prompt_override is not None else create_claude_prompt(
        step,
        state,
        plan_dir,
        root=root,
        **(prompt_kwargs or {}),
    )
    try:
        result = run_command(command, cwd=work_dir, stdin_text=prompt)
    except CliError as error:
        if error.code == "worker_timeout":
            error.extra["session_id"] = session_id
        # Mirror run_codex_step's poisoned-session recovery for Claude.
        resumed = bool(session.get("id")) and not fresh
        if (
            resumed
            and _trusted_container()
            and _is_poisoned_environmental_failure(
                str(error.extra.get("raw_output", ""))
            )
        ):
            print(
                "[megaplan] Detected poisoned session (obsolete sandbox failure belief); "
                "invalidating session and retrying with --fresh",
                flush=True,
            )
            state["sessions"].pop(session_key, None)
            return run_claude_step(
                step,
                state,
                plan_dir,
                root=root,
                fresh=True,
                prompt_override=prompt_override,
                prompt_kwargs=prompt_kwargs,
            )
        raise
    raw = result.stdout or result.stderr
    # Non-exception poisoned-session recovery. Only trigger when we resumed
    # (fresh sessions can't carry stale history).
    if (
        session.get("id")
        and not fresh
        and _trusted_container()
        and _is_poisoned_environmental_failure(raw)
    ):
        print(
            "[megaplan] Detected poisoned session (obsolete sandbox failure belief); "
            "invalidating session and retrying with --fresh",
            flush=True,
        )
        state["sessions"].pop(session_key, None)
        return run_claude_step(
            step,
            state,
            plan_dir,
            root=root,
            fresh=True,
            prompt_override=prompt_override,
            prompt_kwargs=prompt_kwargs,
        )
    envelope, payload = parse_claude_envelope(raw)
    try:
        validate_payload(step, payload)
    except CliError as error:
        raise CliError(error.code, error.message, extra={"raw_output": raw}) from error
    return WorkerResult(
        payload=payload,
        raw_output=raw,
        duration_ms=result.duration_ms,
        cost_usd=float(envelope.get("total_cost_usd", 0.0) or 0.0),
        session_id=str(envelope.get("session_id") or session_id),
        rendered_prompt=prompt,
    )


def run_codex_step(
    step: str,
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    persistent: bool,
    fresh: bool = False,
    json_trace: bool = False,
    prompt_override: str | None = None,
    prompt_kwargs: dict[str, Any] | None = None,
) -> WorkerResult:
    if os.getenv(MOCK_ENV_VAR) == "1":
        return mock_worker_output(step, state, plan_dir, prompt_override=prompt_override, prompt_kwargs=prompt_kwargs)
    project_dir = Path(state["config"]["project_dir"])
    work_dir = resolve_work_dir(state)
    plan_mode = state["config"].get("mode", "code")
    codex_schema_name = (
        get_execution_schema_key(plan_mode, form=creative_form_id(state))
        if step == "execute"
        else STEP_SCHEMA_FILENAMES[step]
    )
    schema_file = schemas_root(root) / codex_schema_name
    session_key = session_key_for(step, "codex")
    session = state["sessions"].get(session_key, {})
    out_handle = tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False)
    out_handle.close()
    output_path = Path(out_handle.name)
    prompt = prompt_override if prompt_override is not None else create_codex_prompt(
        step,
        state,
        plan_dir,
        root=root,
        **(prompt_kwargs or {}),
    )
    timeout_seconds = _codex_timeout_for_step(step)

    if persistent and session.get("id") and not fresh:
        # codex exec resume does not support --output-schema; we rely on
        # validate_payload() after parsing the output file instead. It also
        # does not accept --add-dir; resumed sessions keep the workspace that
        # was granted when the session was created.
        command = ["codex", "exec", "resume"]
        if _trusted_container() and step in _EXECUTE_STEPS:
            command.append("--dangerously-bypass-approvals-and-sandbox")
        command.extend(_codex_exec_mode_flags(step))
        if json_trace:
            command.append("--json")
        command.extend([
            "--skip-git-repo-check",
            "-o", str(output_path),
            str(session["id"]), "-",
        ])
    else:
        command = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "-C",
            str(work_dir),
            "--add-dir",
            str(plan_dir),
        ]
        if _trusted_container() and step in _EXECUTE_STEPS:
            # In a trusted container the surrounding runtime is the sandbox.
            # Skip the workspace-write sandbox (which requires user namespaces
            # that most container runtimes don't grant) and let Codex run
            # unsandboxed. The outer container boundary still contains writes.
            command.append("--dangerously-bypass-approvals-and-sandbox")
        else:
            # Allow projects to declare extra writable roots via state.config.
            # Useful when the project_dir is a subdirectory of a multi-package
            # workspace and tasks legitimately create files in sibling dirs
            # (e.g. tools/ as project_dir but plan creates animations/ at the
            # workspace root). Roots are passed verbatim to codex; relative
            # paths are resolved against work_dir.
            extra_roots: list[str] = []
            # Auto-widen the sandbox to the enclosing workspace root when
            # work_dir is a subdirectory of a larger checkout. Without this,
            # plans whose project_dir is e.g. ``tools/`` get blocked from
            # writing siblings like ``effects/`` even though they're part of
            # the same repo. Set MEGAPLAN_NARROW_SANDBOX=1 to opt out.
            extra_roots.extend(_auto_writable_roots(Path(work_dir)))
            try:
                state_path = plan_dir / "state.json"
                if state_path.is_file():
                    state_data = json.loads(state_path.read_text(encoding="utf-8"))
                    raw_extra = state_data.get("config", {}).get("extra_writable_roots", []) or []
                    if isinstance(raw_extra, list):
                        for root in raw_extra:
                            if not isinstance(root, str):
                                continue
                            resolved = (Path(work_dir) / root).resolve() if not Path(root).is_absolute() else Path(root).resolve()
                            extra_roots.append(str(resolved))
            except Exception:
                pass
            # Deduplicate while preserving order; ensures work_dir is first
            # (codex treats the first entry as the primary workspace).
            seen: set[str] = set()
            roots: list[str] = []
            for r in [str(work_dir), *extra_roots]:
                if r not in seen:
                    seen.add(r)
                    roots.append(r)
            roots_literal = ", ".join(f"\"{r}\"" for r in roots)
            command.extend([
                "-c",
                f"sandbox_workspace_write.writable_roots=[{roots_literal}]",
            ])
        command.extend([
            "-o",
            str(output_path),
        ])
        if not persistent:
            command.append("--ephemeral")
        command.extend(_codex_exec_mode_flags(step))
        if json_trace:
            command.append("--json")
        command.extend(["--output-schema", str(schema_file), "-"])

    try:
        result = run_command(
            command,
            cwd=Path.cwd(),
            stdin_text=prompt,
            env=_codex_child_env(),
            timeout=timeout_seconds,
        )
    except CliError as error:
        error.extra["raw_output"] = _merge_partial_output(
            str(error.extra.get("raw_output", "")),
            output_path,
        )
        # Recover from a lost session: container restarted since the session was
        # created, codex's rollout store is gone, but megaplan still has the id.
        # Clear the stale session and retry once with fresh=True.
        if not fresh and persistent and session.get("id") and _is_rollout_missing(
            str(error.extra.get("raw_output", ""))
        ):
            print(
                f"[megaplan] Codex session {session['id']} has no rollout "
                f"(container restart or session wipe); retrying {step} with a fresh session",
                flush=True,
            )
            # Drop the stale session id so later phases don't also try to resume it.
            state["sessions"].pop(session_key, None)
            return run_codex_step(
                step,
                state,
                plan_dir,
                root=root,
                persistent=persistent,
                fresh=True,
                json_trace=json_trace,
                prompt_override=prompt_override,
                prompt_kwargs=prompt_kwargs,
            )
        # Recover from a poisoned session: the history carries an obsolete
        # "sandbox is broken" belief from a pre-trusted-container run. Only
        # act when we're in trusted-container mode (so we know the belief is
        # stale) and we were resuming a session (fresh sessions can't carry
        # the poisoned history). See _is_poisoned_environmental_failure.
        if (
            not fresh
            and persistent
            and session.get("id")
            and _trusted_container()
            and _is_poisoned_environmental_failure(
                str(error.extra.get("raw_output", ""))
            )
        ):
            print(
                "[megaplan] Detected poisoned session (obsolete sandbox failure belief); "
                "invalidating session and retrying with --fresh",
                flush=True,
            )
            state["sessions"].pop(session_key, None)
            return run_codex_step(
                step,
                state,
                plan_dir,
                root=root,
                persistent=persistent,
                fresh=True,
                json_trace=json_trace,
                prompt_override=prompt_override,
                prompt_kwargs=prompt_kwargs,
            )
        if error.code == "worker_timeout":
            recovered_payload = _recover_codex_payload(
                step,
                plan_dir=plan_dir,
                output_path=output_path,
                raw=str(error.extra.get("raw_output", "")),
            )
            if recovered_payload is not None:
                timeout_session_id = session.get("id") if persistent else None
                if timeout_session_id is None:
                    timeout_session_id = extract_session_id(str(error.extra.get("raw_output", "")))
                return WorkerResult(
                    payload=recovered_payload,
                    raw_output=str(error.extra.get("raw_output", "")),
                    duration_ms=0,
                    cost_usd=0.0,
                    session_id=timeout_session_id,
                    trace_output=str(error.extra.get("raw_output", "")) if json_trace else None,
                    rendered_prompt=prompt,
                )
            timeout_session_id = session.get("id") if persistent else None
            if timeout_session_id is None:
                timeout_session_id = extract_session_id(error.extra.get("raw_output", ""))
            if timeout_session_id is not None:
                error.extra["session_id"] = timeout_session_id
            diagnosed_code, diagnosed_message = _diagnose_codex_failure(
                str(error.extra.get("raw_output", "")),
                124,
            )
            if diagnosed_code == "connection_error":
                raise CliError(
                    diagnosed_code,
                    diagnosed_message,
                    extra=error.extra,
                    valid_next=error.valid_next,
                    exit_code=error.exit_code,
                ) from error
            raise CliError(
                "worker_timeout",
                (
                    f"Codex {step} step timed out after {timeout_seconds}s before producing structured output. "
                    + _codex_retry_guidance(step)
                ),
                extra=error.extra,
                valid_next=error.valid_next,
                exit_code=error.exit_code,
            ) from error
        raise
    raw = result.stdout + result.stderr
    # Same rollout-missing recovery for the non-exception path (non-zero exit
    # without CliError being raised). See _is_rollout_missing for context.
    if (
        not fresh
        and persistent
        and session.get("id")
        and result.returncode != 0
        and _is_rollout_missing(raw)
    ):
        print(
            f"[megaplan] Codex session {session['id']} has no rollout "
            f"(container restart or session wipe); retrying {step} with a fresh session",
            flush=True,
        )
        state["sessions"].pop(session_key, None)
        return run_codex_step(
            step,
            state,
            plan_dir,
            root=root,
            persistent=persistent,
            fresh=True,
            json_trace=json_trace,
            prompt_override=prompt_override,
            prompt_kwargs=prompt_kwargs,
        )
    # Poisoned-session recovery on non-exception path: the worker exited 0 or
    # non-zero but produced output that still echoes an obsolete sandbox
    # failure belief. Same guard conditions as the CliError branch above.
    if (
        not fresh
        and persistent
        and session.get("id")
        and _trusted_container()
        and _is_poisoned_environmental_failure(raw)
    ):
        print(
            "[megaplan] Detected poisoned session (obsolete sandbox failure belief); "
            "invalidating session and retrying with --fresh",
            flush=True,
        )
        state["sessions"].pop(session_key, None)
        return run_codex_step(
            step,
            state,
            plan_dir,
            root=root,
            persistent=persistent,
            fresh=True,
            json_trace=json_trace,
            prompt_override=prompt_override,
            prompt_kwargs=prompt_kwargs,
        )
    if result.returncode != 0 and (not output_path.exists() or not output_path.read_text(encoding="utf-8").strip()):
        error_code, error_message = _diagnose_codex_failure(raw, result.returncode)
        raise CliError(error_code, error_message, extra={"raw_output": raw})
    payload = _recover_codex_payload(
        step,
        plan_dir=plan_dir,
        output_path=output_path,
        raw=raw,
    )
    if payload is None:
        raise CliError("parse_error", f"Output file {output_path.name} was not valid JSON and no fallback found", extra={"raw_output": raw})
    session_id = session.get("id") if persistent else None
    if persistent and not session_id:
        session_id = extract_session_id(raw)
        if not session_id:
            raise CliError(
                "worker_error",
                f"Could not determine Codex session id for persistent {step} step",
                extra={"raw_output": raw},
            )
    trace_output = raw if json_trace else None
    return WorkerResult(
        payload=payload,
        raw_output=raw,
        duration_ms=result.duration_ms,
        cost_usd=0.0,
        session_id=session_id,
        trace_output=trace_output,
        rendered_prompt=prompt,
    )


def _is_agent_available(agent: str) -> bool:
    """Check if an agent is available (CLI binary or vendored for hermes)."""
    if agent == "hermes":
        return (Path(__file__).resolve().parent / "agent" / "run_agent.py").is_file()
    return bool(shutil.which(agent))


def _agent_requested_explicitly(step: str, args: argparse.Namespace) -> bool:
    if getattr(args, "hermes", None) is not None:
        return True
    if getattr(args, "agent", None):
        return True
    for phase_model in getattr(args, "phase_model", None) or []:
        if "=" not in phase_model:
            continue
        phase_step, _phase_spec = phase_model.split("=", 1)
        if phase_step == step:
            return True
    return False


def _runtime_fallback_candidates(current_agent: str) -> list[str]:
    return [agent for agent in detect_available_agents() if agent != current_agent]


def resolve_agent_mode(step: str, args: argparse.Namespace, *, home: Path | None = None) -> tuple[str, str, bool, str | None]:
    """Returns (agent, mode, refreshed, model).

    Both agents default to persistent sessions.  Use --fresh to start a new
    persistent session (break continuity) or --ephemeral for a truly one-off
    call with no session saved.

    The model is extracted from compound agent specs (e.g. 'hermes:openai/gpt-5')
    or from --phase-model / --hermes CLI flags. None means use agent default.
    """
    model = None

    # Check --phase-model overrides first (highest priority)
    phase_models = getattr(args, "phase_model", None) or []
    for pm in phase_models:
        if "=" in pm:
            pm_step, pm_spec = pm.split("=", 1)
            if pm_step == step:
                agent, model = parse_agent_spec(pm_spec)
                break
    else:
        # Check --hermes flag
        hermes_flag = getattr(args, "hermes", None)
        if hermes_flag is not None:
            agent = "hermes"
            if isinstance(hermes_flag, str) and hermes_flag:
                model = hermes_flag
        else:
            # Check explicit --agent flag
            explicit = args.agent
            if explicit:
                agent, model = parse_agent_spec(explicit)
            else:
                # Fall back to config / defaults
                config = load_config(home)
                spec = config.get("agents", {}).get(step) or DEFAULT_AGENT_ROUTING[step]
                agent, model = parse_agent_spec(spec)

    # Validate agent availability
    explicit_agent = args.agent  # was an explicit --agent flag used?
    if not _is_agent_available(agent):
        # If explicitly requested (via --agent), fail immediately
        if explicit_agent and not any(pm.startswith(f"{step}=") for pm in (getattr(args, "phase_model", None) or [])):
            if agent == "hermes":
                raise CliError(
                    "agent_deps_missing",
                    "hermes backend requires: pip install 'megaplan-harness[agent]'",
                )
            raise CliError("agent_not_found", f"Agent '{agent}' not found on PATH")
        # For hermes via --hermes flag, give a specific error
        if getattr(args, "hermes", None) is not None or agent == "hermes":
            raise CliError(
                "agent_deps_missing",
                "hermes backend requires: pip install 'megaplan-harness[agent]'",
            )
        # Try fallback
        available = detect_available_agents()
        if not available:
            raise CliError(
                "agent_not_found",
                "No supported agents found. Install claude or codex, or pip install 'megaplan-harness[agent]' for hermes.",
            )
        fallback = available[0]
        args._agent_fallback = {
            "requested": agent,
            "resolved": fallback,
            "reason": f"{agent} not available",
        }
        agent = fallback
        model = None  # Reset model when falling back

    ephemeral = getattr(args, "ephemeral", False)
    fresh = getattr(args, "fresh", False)
    persist = getattr(args, "persist", False)
    conflicting = sum([fresh, persist, ephemeral])
    if conflicting > 1:
        raise CliError("invalid_args", "Cannot combine --fresh, --persist, and --ephemeral")
    if ephemeral:
        return agent, "ephemeral", True, model
    refreshed = fresh
    # Review with Claude: default to fresh to avoid self-bias (principle #5)
    if step == "review" and agent == "claude":
        if persist and not getattr(args, "confirm_self_review", False):
            raise CliError("invalid_args", "Claude review requires --confirm-self-review when using --persist")
        if not persist:
            refreshed = True
    return agent, "persistent", refreshed, model


def run_step_with_worker(
    step: str,
    state: PlanState,
    plan_dir: Path,
    args: argparse.Namespace,
    *,
    root: Path,
    resolved: tuple[str, str, bool, str | None] | None = None,
    prompt_override: str | None = None,
    prompt_kwargs: dict[str, Any] | None = None,
) -> tuple[WorkerResult, str, str, bool]:
    agent, mode, refreshed, model = resolved or resolve_agent_mode(step, args)
    effective_refreshed = refreshed
    explicit_agent = _agent_requested_explicitly(step, args)
    attempted_agents: set[str] = set()
    while True:
        attempted_agents.add(agent)
        try:
            if agent == "hermes":
                # Deferred import to avoid circular import (hermes_worker imports from workers)
                from megaplan.hermes_worker import run_hermes_step
                worker = run_hermes_step(
                    step,
                    state,
                    plan_dir,
                    root=root,
                    fresh=effective_refreshed,
                    model=model,
                    prompt_override=prompt_override,
                )
            elif agent == "claude":
                worker = run_claude_step(
                    step,
                    state,
                    plan_dir,
                    root=root,
                    fresh=effective_refreshed,
                    prompt_override=prompt_override,
                    prompt_kwargs=prompt_kwargs,
                )
            else:
                attempted_retry = False
                while True:
                    try:
                        worker = run_codex_step(
                            step,
                            state,
                            plan_dir,
                            root=root,
                            persistent=(mode == "persistent"),
                            fresh=effective_refreshed,
                            json_trace=(step == "execute"),
                            prompt_override=prompt_override,
                            prompt_kwargs=prompt_kwargs,
                        )
                        break
                    except CliError as error:
                        session_id = error.extra.get("session_id")
                        if (
                            attempted_retry
                            or step in _EXECUTE_STEPS
                            or error.code not in {"worker_timeout", "connection_error"}
                        ):
                            raise
                        attempted_retry = True
                        if mode == "persistent" and isinstance(session_id, str) and session_id:
                            apply_session_update(
                                state,
                                step,
                                agent,
                                session_id,
                                mode=mode,
                                refreshed=effective_refreshed,
                            )
                            effective_refreshed = False
                        continue
            return worker, agent, mode, effective_refreshed
        except CliError as error:
            if explicit_agent or error.code not in {"auth_error", "connection_error"}:
                raise
            fallback_candidates = [
                candidate
                for candidate in _runtime_fallback_candidates(agent)
                if candidate not in attempted_agents
            ]
            if not fallback_candidates:
                raise
            fallback_agent = fallback_candidates[0]
            args._agent_fallback = {
                "requested": agent,
                "resolved": fallback_agent,
                "reason": f"{agent} runtime unhealthy: {error.code}",
            }
            agent = fallback_agent
            model = None
            effective_refreshed = True
