"""Resident-owned delegated-agent dispatch and durable lifecycle tracking.

Normal resident delegation uses a detached Codex supervisor with a canonical
manifest, streaming log, and final-result file.  The older synchronous Hermes
launcher remains available only when callers explicitly select it.
"""

from __future__ import annotations

import asyncio
import argparse
from collections.abc import Awaitable, Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import logging
import os
import re
import signal
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Literal

from .config import ResidentConfig
from .provenance import (
    DelegationProvenanceError,
    discord_origin_projection,
    environment_with_provenance,
    normalize_delegation_provenance,
    provenance_from_environment,
    stable_identity,
)

LOGGER = logging.getLogger(__name__)
MANAGED_RUN_SCHEMA = "arnold-resident-agent-run-v1"
MANAGED_RUN_KIND = "resident_delegated_agent"
MANAGED_RUN_CUSTODIAN = "arnold.megaplan.resident"
LEGACY_MANAGED_RUN_SCHEMA = "arnold-subagent-run-v1"
DEFAULT_MANAGED_RUN_ROOT = Path(".megaplan/plans/resident-subagents")
DEFAULT_DELEGATED_TASK_KIND = "routine"
DEFAULT_DELEGATED_DIFFICULTY = 4
DELEGATED_TASK_KINDS = (
    "routine",
    "lookup",
    "extraction",
    "mechanical",
    "coding",
    "debugging",
    "research",
    "root_cause",
    "architecture",
    "migration",
    "review",
    "autonomous",
)
DelegatedTaskKind = Literal[
    "routine",
    "lookup",
    "extraction",
    "mechanical",
    "coding",
    "debugging",
    "research",
    "root_cause",
    "architecture",
    "migration",
    "review",
    "autonomous",
]
_BOUNDED_TASK_KINDS = frozenset({"lookup", "extraction", "mechanical"})
_HIGH_RISK_TASK_KINDS = frozenset(
    {"root_cause", "architecture", "migration", "review", "autonomous"}
)
_VALID_DELEGATED_EFFORTS = frozenset(
    {"minimal", "low", "medium", "high", "xhigh", "max"}
)
_ACTIVE_STATUSES = frozenset({"launching", "running"})
_TERMINAL_STATUSES = frozenset({"completed", "failed", "interrupted"})
_DELIVERY_RETRY_BASE_S = 30
_DELIVERY_RETRY_MAX_S = 60 * 60
_DELIVERY_MAX_ATTEMPTS = 8
_MAX_COMPLETION_DELIVERY_CHARS = 7_600
FINAL_SUMMARY_INSTRUCTION = (
    "Your FINAL response will be sent directly to the user as a Discord reply. "
    "Make it a concise, user-facing summary that stands on its own. State the outcome, "
    "the important changes or findings, verification performed, and any remaining operational "
    "caveat. Do not include internal handoff notes, ask a follow-up question, or merely say that "
    "work is complete. Never expose credentials or other secrets. Preserve and follow all "
    "task-specific instructions above."
)

# resident/ -> megaplan/ -> skills/subagent-launcher/launch_hermes_agent.py
LAUNCHER_PATH = (
    Path(__file__).resolve().parent.parent / "skills" / "subagent-launcher" / "launch_hermes_agent.py"
)


@dataclass(frozen=True)
class SubagentResult:
    ok: bool
    final_text: str
    stderr: str
    returncode: int
    error: str | None = None
    run_id: str | None = None
    status: str | None = None
    manifest_path: str | None = None
    log_path: str | None = None
    result_path: str | None = None
    pid: int | None = None


@dataclass(frozen=True)
class ManagedAgentDeliverySweepResult:
    scanned: int = 0
    delivered: int = 0
    retry_pending: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass(frozen=True)
class ManagedCompletionTurnResult:
    """Durable output of the resident's independent completion-verification turn."""

    final_text: str
    verification_outcome: str
    turn_id: str | None = None
    outbound_message_id: str | None = None


@dataclass(frozen=True)
class DelegatedTaskRoute:
    """Resolved GPT-5.6 route for one resident-managed task."""

    task_kind: DelegatedTaskKind
    difficulty: int
    model: str
    reasoning_effort: str
    route_class: str


def route_delegated_task(
    *,
    task_kind: DelegatedTaskKind = DEFAULT_DELEGATED_TASK_KIND,
    difficulty: int = DEFAULT_DELEGATED_DIFFICULTY,
) -> DelegatedTaskRoute:
    """Route resident delegation by task kind and D1-D10 difficulty.

    Luna is intentionally limited to bounded/mechanical D1-D3 work. Terra is
    the routine default. Ambiguous or high-risk kinds, and all D7-D10 work,
    use Sol/high. Explicit launch model/effort overrides are applied after
    this policy so existing callers retain their escape hatch.
    """

    if task_kind not in DELEGATED_TASK_KINDS:
        raise ValueError(
            f"task_kind must be one of {', '.join(DELEGATED_TASK_KINDS)}; got {task_kind!r}"
        )
    if isinstance(difficulty, bool) or not isinstance(difficulty, int) or not 1 <= difficulty <= 10:
        raise ValueError(f"difficulty must be an integer from 1 to 10; got {difficulty!r}")
    if task_kind in _HIGH_RISK_TASK_KINDS or difficulty >= 7:
        return DelegatedTaskRoute(
            task_kind=task_kind,
            difficulty=difficulty,
            model="gpt-5.6-sol",
            reasoning_effort="high",
            route_class="ambiguous_or_high_risk",
        )
    if task_kind in _BOUNDED_TASK_KINDS and difficulty <= 3:
        return DelegatedTaskRoute(
            task_kind=task_kind,
            difficulty=difficulty,
            model="gpt-5.6-luna",
            reasoning_effort="low",
            route_class="bounded_mechanical",
        )
    return DelegatedTaskRoute(
        task_kind=task_kind,
        difficulty=difficulty,
        model="gpt-5.6-terra",
        reasoning_effort="medium",
        route_class="routine",
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _delivery_prompt(task: str) -> str:
    return f"{task.rstrip()}\n\n[Completion delivery contract]\n{FINAL_SUMMARY_INSTRUCTION}\n"


_RESIDENT_MESSAGE_ID_RE = re.compile(r"^msg_[A-Za-z0-9]{8,64}$")
_RESIDENT_CONVERSATION_ID_RE = re.compile(r"^rconv_[A-Za-z0-9]{8,64}$")


def _is_discord_snowflake(value: object) -> bool:
    text = str(value or "").strip()
    return text.isascii() and text.isdigit() and 0 < len(text) <= 20 and int(text) > 0


def _resolve_resident_message_id(
    value: str,
    *,
    project_root: str | Path | None,
    conversation_id: str | None,
) -> tuple[str, str] | None:
    """Resolve an Arnold message record id to its durable Discord snowflake."""

    if not project_root or not _RESIDENT_MESSAGE_ID_RE.fullmatch(value):
        return None
    record_path = Path(project_root).resolve() / ".megaplan" / "resident" / "messages" / f"{value}.json"
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(record, dict) or str(record.get("id") or "") != value:
        return None
    if str(record.get("direction") or "") != "inbound":
        return None
    if conversation_id and str(record.get("conversation_id") or "") != conversation_id:
        return None
    discord_message_id = str(record.get("discord_message_id") or "").strip()
    if not _is_discord_snowflake(discord_message_id):
        return None
    return discord_message_id, value


def _find_resident_source_record_id(
    *,
    project_root: str | Path | None,
    conversation_id: str | None,
    discord_message_id: str,
) -> str | None:
    """Find the one inbound source record matching an immutable Discord id."""

    if not project_root or not conversation_id or not _is_discord_snowflake(discord_message_id):
        return None
    messages_dir = Path(project_root).resolve() / ".megaplan" / "resident" / "messages"
    matches: list[str] = []
    for path in messages_dir.glob("msg_*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(record, dict):
            continue
        record_id = str(record.get("id") or "")
        if (
            _RESIDENT_MESSAGE_ID_RE.fullmatch(record_id)
            and str(record.get("direction") or "") == "inbound"
            and str(record.get("conversation_id") or "") == conversation_id
            and str(record.get("discord_message_id") or "") == discord_message_id
        ):
            matches.append(record_id)
    return matches[0] if len(matches) == 1 else None


def _discord_origin_from_resident_request(
    request_id: object,
    *,
    project_root: str | Path | None,
) -> dict[str, str | None] | None:
    """Recover safe Discord provenance from an inbound resident message id.

    Message content, author metadata, and idempotency material deliberately do
    not cross into the managed-run manifest.  Only transport routing fields
    needed to reply to the original inbound message are retained.
    """

    resident_message_id = str(request_id or "").strip()
    if not project_root or not _RESIDENT_MESSAGE_ID_RE.fullmatch(resident_message_id):
        return None
    resident_root = Path(project_root).resolve() / ".megaplan" / "resident"
    message_path = resident_root / "messages" / f"{resident_message_id}.json"
    try:
        message = json.loads(message_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(message, dict):
        return None
    conversation_id = str(message.get("conversation_id") or "").strip()
    if (
        str(message.get("id") or "") != resident_message_id
        or str(message.get("direction") or "") != "inbound"
        or not _RESIDENT_CONVERSATION_ID_RE.fullmatch(conversation_id)
    ):
        return None
    discord_message_id = str(message.get("discord_message_id") or "").strip()
    if not _is_discord_snowflake(discord_message_id):
        return None

    conversation_path = resident_root / "resident_conversations" / f"{conversation_id}.json"
    try:
        conversation = json.loads(conversation_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(conversation, dict):
        return None
    conversation_key = str(conversation.get("conversation_key") or "").strip()
    if (
        str(conversation.get("id") or "") != conversation_id
        or str(conversation.get("transport") or "") != "discord"
        or not conversation_key.startswith("discord:")
    ):
        return None

    origin: dict[str, str | None] = {
        "transport": "discord",
        "conversation_id": conversation_id,
        "conversation_key": conversation_key,
        "message_id": discord_message_id,
        "reply_to_message_id": discord_message_id,
        "guild_id": None,
        "channel_id": None,
        "thread_id": None,
        "dm_user_id": None,
        "reply_target_source_record_id": resident_message_id,
    }
    for key in ("guild_id", "channel_id", "thread_id", "dm_user_id"):
        raw = conversation.get(key)
        origin[key] = str(raw) if raw is not None and str(raw) else None
    return origin


def _discord_origin(
    value: Mapping[str, Any] | None,
    *,
    project_root: str | Path | None = None,
) -> dict[str, str | None] | None:
    if not isinstance(value, Mapping) or value.get("transport") != "discord":
        return None
    conversation_key = str(value.get("conversation_key") or "").strip()
    reply_to_message_id = str(
        value.get("reply_to_message_id")
        or value.get("discord_message_id")
        or value.get("message_id")
        or ""
    ).strip()
    if not conversation_key.startswith("discord:") or not reply_to_message_id:
        return None
    conversation_id = str(
        value.get("resident_conversation_id") or value.get("conversation_id") or ""
    ).strip() or None
    source_record_id: str | None = None
    if not _is_discord_snowflake(reply_to_message_id):
        resolved = _resolve_resident_message_id(
            reply_to_message_id,
            project_root=project_root,
            conversation_id=conversation_id,
        )
        if resolved is None:
            return None
        reply_to_message_id, source_record_id = resolved
    allowed = (
        "conversation_id",
        "conversation_key",
        "message_id",
        "reply_to_message_id",
        "guild_id",
        "channel_id",
        "thread_id",
        "dm_user_id",
    )
    origin: dict[str, str | None] = {"transport": "discord"}
    for key in allowed:
        raw = value.get(key)
        origin[key] = str(raw) if raw is not None and str(raw) else None
    origin["conversation_id"] = conversation_id
    origin["conversation_key"] = conversation_key
    origin["reply_to_message_id"] = reply_to_message_id
    message_id = str(
        origin.get("message_id") or value.get("discord_message_id") or ""
    ).strip()
    if _is_discord_snowflake(message_id):
        origin["message_id"] = message_id
    if not _is_discord_snowflake(message_id):
        if source_record_id and message_id == source_record_id:
            origin["message_id"] = reply_to_message_id
        elif message_id:
            resolved_message = _resolve_resident_message_id(
                message_id,
                project_root=project_root,
                conversation_id=conversation_id,
            )
            origin["message_id"] = resolved_message[0] if resolved_message else None
    if source_record_id:
        origin["reply_target_source_record_id"] = source_record_id
    else:
        stored_source = str(
            value.get("source_record_id")
            or value.get("reply_target_source_record_id")
            or ""
        ).strip()
        if _RESIDENT_MESSAGE_ID_RE.fullmatch(stored_source):
            resolved_source = _resolve_resident_message_id(
                stored_source,
                project_root=project_root,
                conversation_id=conversation_id,
            )
            if resolved_source is not None and resolved_source[0] == reply_to_message_id:
                origin["reply_target_source_record_id"] = stored_source
    if not origin.get("reply_target_source_record_id"):
        recovered_source = _find_resident_source_record_id(
            project_root=project_root,
            conversation_id=conversation_id,
            discord_message_id=reply_to_message_id,
        )
        if recovered_source:
            origin["reply_target_source_record_id"] = recovered_source
    return origin


def _canonical_launch_provenance(
    value: Mapping[str, Any] | None,
    *,
    project_root: Path,
    request_id: str | None,
) -> dict[str, Any]:
    """Resolve every launch to one Discord envelope or explicit N/A custody."""

    inherited = provenance_from_environment(strict=True)
    candidate: Mapping[str, Any] | None = value
    if candidate is None:
        candidate = inherited
    elif inherited is not None and inherited.get("applicability") == "applicable":
        if candidate.get("applicability") == "not_applicable" or candidate.get("transport") in {
            "non_discord",
            "not_applicable",
        }:
            raise DelegationProvenanceError(
                "a Discord-origin child launch cannot discard inherited custody"
            )
        candidate = {**inherited, **dict(candidate)}
    if candidate is not None and candidate.get("applicability") == "ambiguous":
        raise DelegationProvenanceError("Discord launch provenance is ambiguous")
    if candidate is not None and (
        candidate.get("transport") == "discord" or candidate.get("applicability") == "applicable"
    ):
        origin = _discord_origin(candidate, project_root=project_root)
        if origin is None:
            raise DelegationProvenanceError(
                "Discord launch provenance requires one exact, resolvable reply target"
            )
        merged = {**dict(candidate), **origin}
        merged["resident_conversation_id"] = origin.get("conversation_id")
        merged["source_record_id"] = (
            origin.get("reply_target_source_record_id")
            or candidate.get("source_record_id")
            or candidate.get("reply_target_source_record_id")
        )
        merged["discord_message_id"] = origin.get("message_id")
        source_record_id = str(merged.get("source_record_id") or "")
        file_messages_dir = project_root / ".megaplan" / "resident" / "messages"
        if _RESIDENT_MESSAGE_ID_RE.fullmatch(source_record_id) and file_messages_dir.exists():
            resolved_source = _resolve_resident_message_id(
                source_record_id,
                project_root=project_root,
                conversation_id=str(origin.get("conversation_id") or "") or None,
            )
            if resolved_source is None or resolved_source[0] != origin.get("message_id"):
                raise DelegationProvenanceError(
                    "source_record_id does not match the original Discord message"
                )
        normalized = normalize_delegation_provenance(merged)
        if inherited is not None and inherited.get("applicability") == "applicable":
            for field in (
                "correlation_id",
                "custody_id",
                "resident_conversation_id",
                "source_record_id",
                "conversation_key",
                "discord_message_id",
                "reply_to_message_id",
                "guild_id",
                "channel_id",
                "thread_id",
                "dm_user_id",
            ):
                if normalized.get(field) != inherited.get(field):
                    raise DelegationProvenanceError(
                        f"child launch {field} conflicts with inherited Discord custody"
                    )
        return normalized
    if candidate is not None:
        # A resident message record is positive evidence of Discord origin.  It
        # must never be reclassified as not_applicable merely because a caller
        # supplied an explicit non-Discord envelope or because recovery failed.
        # VP todo ids use a different shape, preserving scheduled-launch
        # compatibility while making stale/malformed Discord custody fail closed.
        if _RESIDENT_MESSAGE_ID_RE.fullmatch(str(request_id or "")):
            recovered = _discord_origin_from_resident_request(
                request_id, project_root=project_root
            )
            if recovered is None:
                raise DelegationProvenanceError(
                    "Discord-origin request_id cannot be bound to durable custody"
                )
            return normalize_delegation_provenance(
                {
                    **recovered,
                    "applicability": "applicable",
                    "resident_conversation_id": recovered["conversation_id"],
                    "source_record_id": recovered["reply_target_source_record_id"],
                    "discord_message_id": recovered["message_id"],
                    "source_kind": "resident_request_recovery",
                }
            )
        return normalize_delegation_provenance(candidate)

    recovered = _discord_origin_from_resident_request(request_id, project_root=project_root)
    if recovered is not None:
        return normalize_delegation_provenance(
            {
                **recovered,
                "applicability": "applicable",
                "resident_conversation_id": recovered["conversation_id"],
                "source_record_id": recovered["reply_target_source_record_id"],
                "discord_message_id": recovered["message_id"],
                "source_kind": "resident_request_recovery",
            }
        )
    if _RESIDENT_MESSAGE_ID_RE.fullmatch(str(request_id or "")):
        raise DelegationProvenanceError(
            "Discord-origin request_id cannot be bound to durable custody"
        )
    return normalize_delegation_provenance(
        {
            "transport": "non_discord",
            "applicability": "not_applicable",
            "source_kind": "explicit_non_discord",
        }
    )


def _result_from_manifest(manifest_path: Path, payload: Mapping[str, Any]) -> SubagentResult:
    status = str(payload.get("status") or "unknown")
    return SubagentResult(
        ok=status not in {"failed", "interrupted"},
        final_text="",
        stderr="",
        returncode=int(payload.get("returncode") or 0),
        run_id=str(payload.get("run_id") or manifest_path.parent.name),
        status=status,
        manifest_path=str(manifest_path),
        log_path=str(payload.get("log_path") or manifest_path.parent / "run.log"),
        result_path=str(payload.get("result_path") or manifest_path.parent / "result.md"),
        pid=payload.get("pid") if isinstance(payload.get("pid"), int) else None,
    )


def _existing_idempotent_launch(root: Path, launch_key: str) -> tuple[Path, dict[str, Any]] | None:
    for path in root.glob("*/manifest.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if isinstance(payload, dict) and payload.get("launch_idempotency_key") == launch_key:
            return path, payload
    return None


def launch_codex_subagent_detached(
    *,
    task: str,
    project_dir: str | None = None,
    model: str = "gpt-5.6-terra",
    reasoning_effort: str = "medium",
    task_kind: DelegatedTaskKind = DEFAULT_DELEGATED_TASK_KIND,
    difficulty: int = DEFAULT_DELEGATED_DIFFICULTY,
    route_class: str = "routine",
    run_root: str | Path = DEFAULT_MANAGED_RUN_ROOT,
    request_id: str | None = None,
    launch_origin: Mapping[str, Any] | None = None,
    retry_of_run_id: str | None = None,
) -> SubagentResult:
    """Launch a durable, fully-permissioned Codex worker managed by Arnold.

    The supervisor process owns the manifest transitions and durable output, so
    the Discord resident can return immediately without losing lifecycle state.
    """
    project_root = Path(project_dir or Path.cwd()).resolve()
    provenance = _canonical_launch_provenance(
        launch_origin,
        project_root=project_root,
        request_id=request_id,
    )
    is_discord = provenance["applicability"] == "applicable"
    origin = discord_origin_projection(provenance) if is_discord else None
    requested_root = Path(run_root)
    root = (
        project_root / requested_root
        if not requested_root.is_absolute() and requested_root == DEFAULT_MANAGED_RUN_ROOT
        else requested_root.resolve()
    )
    root.mkdir(parents=True, exist_ok=True)
    task_digest = hashlib.sha256(task.encode("utf-8")).hexdigest()
    # Discord launch identity is owned by the inbound source record.  A model
    # or compatibility caller may still provide request_id, but it cannot
    # sever custody or turn the same inbound request into duplicate workers.
    launch_selector = str(
        provenance["source_record_id"]
        if is_discord
        else request_id or stable_identity("task", task_digest)
    )
    launch_key = stable_identity(
        "resident-launch",
        provenance.get("correlation_id") or "not-applicable",
        launch_selector,
        task_digest,
        retry_of_run_id or "",
    )
    launch_lock = root / ".launch.lock"
    launch_handle = launch_lock.open("a+b")
    fcntl.flock(launch_handle.fileno(), fcntl.LOCK_EX)
    existing = _existing_idempotent_launch(root, launch_key)
    if existing is not None:
        fcntl.flock(launch_handle.fileno(), fcntl.LOCK_UN)
        launch_handle.close()
        return _result_from_manifest(*existing)
    run_id = f"subagent-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    prompt_path = run_dir / "prompt.md"
    manifest_path = run_dir / "manifest.json"
    log_path = run_dir / "run.log"
    result_path = run_dir / "result.md"
    prompt = _delivery_prompt(task)
    prompt_path.write_text(prompt, encoding="utf-8")
    result_path.touch()
    manifest: dict[str, object] = {
        "schema_version": MANAGED_RUN_SCHEMA,
        "run_kind": MANAGED_RUN_KIND,
        "custodian": MANAGED_RUN_CUSTODIAN,
        "run_id": run_id,
        "backend": "codex",
        "model": model,
        "reasoning_effort": reasoning_effort,
        "task_kind": task_kind,
        "difficulty": difficulty,
        "route_class": route_class,
        "sandbox": "danger-full-access",
        "project_dir": str(project_root),
        "manifest_path": str(manifest_path),
        "prompt_path": str(prompt_path),
        "log_path": str(log_path),
        "full_log_path": str(log_path),
        "result_path": str(result_path),
        "task_sha256": task_digest,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "launch_idempotency_key": launch_key,
        "correlation_id": provenance.get("correlation_id") or run_id,
        "custody_id": provenance.get("custody_id") or stable_identity("resident-custody", run_id),
        "launch_provenance": provenance,
        "status": "launching",
        "created_at": _utc_now(),
    }
    if retry_of_run_id:
        manifest["retry_of_run_id"] = retry_of_run_id
    if is_discord:
        manifest["request_id"] = provenance["source_record_id"]
        if request_id and request_id != provenance["source_record_id"]:
            manifest["caller_request_id"] = request_id
        manifest["resident_conversation_id"] = provenance["resident_conversation_id"]
        manifest["source_record_id"] = provenance["source_record_id"]
    elif request_id:
        manifest["request_id"] = request_id
    if origin is not None:
        manifest["discord_origin"] = origin
        manifest["completion_delivery"] = {
            "transport": "discord",
            "status": "pending",
            "attempt_count": 0,
            "custody_id": manifest["custody_id"],
            "outbox_id": stable_identity("discord-outbox", run_id, origin["reply_to_message_id"]),
            "idempotency_key": f"resident-subagent-completion:{run_id}",
            "reply_target": {
                "conversation_key": origin["conversation_key"],
                "message_id": origin["reply_to_message_id"],
                "source_record_id": provenance["source_record_id"],
            },
            "state_history": [
                {"status": "pending", "at": manifest["created_at"], "evidence": "outbox_committed_before_launch"}
            ],
        }
    else:
        manifest["completion_delivery"] = {
            "transport": "non_discord",
            "status": "not_applicable",
            "attempt_count": 0,
            "custody_id": manifest["custody_id"],
            "evidence": "launch_provenance_explicitly_non_discord",
        }
    _atomic_json(manifest_path, manifest)
    # Once the manifest exists, concurrent/restarted callers can return its
    # durable identity without creating a second worker.  Process start is a
    # recoverable transition from this point onward.
    fcntl.flock(launch_handle.fileno(), fcntl.LOCK_UN)
    launch_handle.close()
    argv = [
        sys.executable,
        "-m",
        "arnold_pipelines.megaplan.resident.subagent_worker",
        "--run-codex",
        str(manifest_path),
    ]
    worker_provenance = {**provenance, "root_run_id": run_id} if is_discord else provenance
    with log_path.open("ab") as log_handle:
        process = subprocess.Popen(
            argv,
            # Always load the worker implementation from this Arnold checkout.
            # The delegated Codex process uses manifest["project_dir"] later;
            # using it here could import an older resident package from the
            # target checkout before the standardized launcher is deployed.
            cwd=str(Path(__file__).resolve().parents[3]),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=environment_with_provenance(worker_provenance),
        )
    # Preserve worker fields or a terminal transition written by an unusually
    # fast child between Popen and this parent-side lifecycle update.
    current = json.loads(manifest_path.read_text(encoding="utf-8"))
    current.setdefault("pid", process.pid)
    current.setdefault("started_at", _utc_now())
    if current.get("status") == "launching":
        current["status"] = "running"
    _atomic_json(manifest_path, current)
    status = str(current.get("status") or "running")
    return SubagentResult(
        ok=status not in {"failed", "interrupted"},
        final_text="",
        stderr="",
        returncode=int(current.get("returncode") or 0),
        run_id=run_id,
        status=status,
        manifest_path=str(manifest_path),
        log_path=str(log_path),
        result_path=str(result_path),
        pid=process.pid,
    )


def _run_codex_manifest(manifest_path: Path) -> int:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prompt = Path(str(manifest["prompt_path"])).read_text(encoding="utf-8")
    result_path = Path(str(manifest["result_path"]))
    argv = [
        "codex",
        "exec",
        "--sandbox",
        "danger-full-access",
        "-m",
        str(manifest["model"]),
        "-c",
        f"model_reasoning_effort={manifest['reasoning_effort']}",
        "--output-last-message",
        str(result_path),
        prompt,
    ]
    worker: subprocess.Popen[bytes] | None = None
    interrupted_signal: int | None = None

    def _interrupt(signum: int, _frame: object) -> None:
        nonlocal interrupted_signal
        interrupted_signal = signum
        raise KeyboardInterrupt

    prior_handlers = {
        signum: signal.signal(signum, _interrupt)
        for signum in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        launch_provenance = manifest.get("launch_provenance")
        worker_env = None
        if isinstance(launch_provenance, Mapping):
            worker_provenance = dict(launch_provenance)
            if worker_provenance.get("applicability") == "applicable":
                worker_provenance["root_run_id"] = str(
                    manifest.get("run_id") or manifest_path.parent.name
                )
            worker_env = environment_with_provenance(worker_provenance)
        worker = subprocess.Popen(
            argv,
            cwd=str(manifest["project_dir"]),
            stdin=subprocess.DEVNULL,
            env=worker_env,
        )
        # Reload before updating so the supervisor PID written by the launch
        # process cannot be lost to a parent/child manifest race.
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.update({"worker_started_at": _utc_now(), "worker_pid": worker.pid})
        _atomic_json(manifest_path, manifest)
        returncode = worker.wait()
        # Codex writes the final response to result_path while its complete
        # stream is inherited by the supervisor and appended to run.log.
        result_path.touch(exist_ok=True)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.update(
            {
                "status": "completed" if returncode == 0 else "failed",
                "returncode": returncode,
                "finished_at": _utc_now(),
            }
        )
        _atomic_json(manifest_path, manifest)
        return returncode
    except BaseException as exc:
        if worker is not None and worker.poll() is None:
            worker.terminate()
            try:
                worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        status = "interrupted" if interrupted_signal is not None else "failed"
        manifest.update(
            {
                "status": status,
                "error": "managed Codex worker failed",
                "error_class": exc.__class__.__name__,
                "finished_at": _utc_now(),
            }
        )
        if interrupted_signal is not None:
            manifest["signal"] = interrupted_signal
            manifest["returncode"] = 128 + interrupted_signal
        _atomic_json(manifest_path, manifest)
        if interrupted_signal is not None:
            return 128 + interrupted_signal
        return 1
    finally:
        for signum, handler in prior_handlers.items():
            signal.signal(signum, handler)


def _pid_matches_manifest(pid: int, manifest_path: Path) -> bool:
    """Return true only when the live PID is this managed wrapper.

    Matching the manifest path avoids reporting an unrelated process after PID
    reuse. Non-Linux hosts simply report the persisted lifecycle state.
    """
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8")
    except (OSError, UnicodeError):
        return False
    return (
        "arnold_pipelines.megaplan.resident.subagent" in cmdline
        and str(manifest_path) in cmdline
    )


def _managed_run_roots(
    *,
    project_root: str | Path,
    workspace_root: str | Path | None,
) -> set[Path]:
    roots = {Path(project_root).resolve() / DEFAULT_MANAGED_RUN_ROOT}
    workspace = Path(workspace_root).resolve() if workspace_root else None
    if workspace and workspace.is_dir():
        roots.update(workspace.glob("*/.megaplan/plans/resident-subagents"))
        roots.update(workspace.glob("*/*/.megaplan/plans/resident-subagents"))
    return roots


def _managed_manifest_paths(
    *,
    project_root: str | Path,
    workspace_root: str | Path | None,
) -> list[Path]:
    paths: list[Path] = []
    for root in sorted(_managed_run_roots(project_root=project_root, workspace_root=workspace_root)):
        if root.is_dir():
            paths.extend(sorted(root.glob("*/manifest.json")))
    return paths


def _is_managed_manifest(payload: Mapping[str, Any]) -> bool:
    return (
        payload.get("schema_version") == MANAGED_RUN_SCHEMA
        and payload.get("run_kind") == MANAGED_RUN_KIND
        and payload.get("custodian") == MANAGED_RUN_CUSTODIAN
    )


@contextmanager
def _delivery_lock(manifest_path: Path) -> Iterator[None]:
    """Serialize delivery claims across resident processes without locking a replaced inode."""

    lock_path = manifest_path.parent / ".completion-delivery.lock"
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _repair_manifest_delivery_provenance(manifest: dict[str, Any]) -> bool:
    """Backfill delivery provenance for manifests launched by stale residents."""

    changed = False
    existing_delivery = manifest.get("completion_delivery")
    if isinstance(existing_delivery, Mapping):
        provider_ids = [
            str(value)
            for value in existing_delivery.get("discord_message_ids", [])
            if str(value).strip()
        ]
        # Provider acceptance evidence is stronger than a later compatibility
        # migration.  Old delivered records may lack today's provenance schema,
        # but they must never be downgraded or redriven after Discord message
        # IDs and a delivered timestamp were durably persisted.
        if provider_ids and _parse_timestamp(existing_delivery.get("delivered_at")):
            if existing_delivery.get("status") != "delivered":
                delivery = dict(existing_delivery)
                diagnostic = {
                    key: delivery.pop(key)
                    for key in (
                        "last_error",
                        "last_error_class",
                        "last_error_category",
                        "migration_evidence",
                    )
                    if delivery.get(key) not in (None, "")
                }
                history = list(delivery.get("state_history") or [])
                history.append(
                    {
                        "status": "delivered",
                        "at": _utc_now(),
                        "evidence": "provider_message_ids_prevented_migration_redrive",
                    }
                )
                delivery.update(
                    {
                        "status": "delivered",
                        "migration_diagnostic": diagnostic,
                        "migration_evidence": (
                            "historical provider acceptance preserved; no redrive"
                        ),
                        "state_history": history[-20:],
                        "updated_at": _utc_now(),
                    }
                )
                manifest["completion_delivery"] = delivery
                return True
            return False
    project_root = str(manifest.get("project_dir") or "").strip() or None
    raw_origin = manifest.get("discord_origin")
    existing_provenance: dict[str, Any] | None = None
    if isinstance(manifest.get("launch_provenance"), Mapping):
        try:
            candidate_provenance = normalize_delegation_provenance(
                manifest["launch_provenance"]
            )
        except DelegationProvenanceError:
            candidate_provenance = None
        if candidate_provenance is not None and candidate_provenance.get("applicability") == "applicable":
            existing_provenance = candidate_provenance

    origin: dict[str, Any] | None
    if existing_provenance is not None:
        expected_origin = discord_origin_projection(existing_provenance)
        supplied_origin = _discord_origin(raw_origin, project_root=project_root)
        if raw_origin is not None and (
            supplied_origin is None
            or any(
                supplied_origin.get(field) != expected_origin.get(field)
                for field in (
                    "conversation_id",
                    "conversation_key",
                    "message_id",
                    "reply_to_message_id",
                    "guild_id",
                    "channel_id",
                    "thread_id",
                    "dm_user_id",
                )
            )
        ):
            delivery = dict(manifest.get("completion_delivery") or {})
            delivery.update(
                {
                    "transport": "discord",
                    "status": "failed",
                    "attempt_count": int(delivery.get("attempt_count") or 0),
                    "last_error": "Discord custody failed: compatibility origin conflicts with immutable launch provenance",
                    "last_error_class": "ProvenanceCustodyMismatch",
                    "last_error_category": "invalid_reply_target",
                    "updated_at": _utc_now(),
                }
            )
            manifest["completion_delivery"] = delivery
            return True
        origin = expected_origin
    else:
        origin = _discord_origin(raw_origin, project_root=project_root)
    if origin is None:
        origin = _discord_origin_from_resident_request(
            manifest.get("request_id"),
            project_root=project_root,
        )
    if origin is None:
        existing_provenance = manifest.get("launch_provenance")
        if (
            isinstance(existing_provenance, Mapping)
            and existing_provenance.get("applicability") == "applicable"
        ):
            delivery = dict(manifest.get("completion_delivery") or {})
            delivery.update(
                {
                    "transport": "discord",
                    "status": "failed",
                    "attempt_count": int(delivery.get("attempt_count") or 0),
                    "last_error": "Discord custody failed: durable launch provenance is no longer valid",
                    "last_error_class": "InvalidDelegationProvenance",
                    "last_error_category": "invalid_reply_target",
                    "migration_evidence": "reply target was not inferred from mutable state",
                    "updated_at": _utc_now(),
                }
            )
            manifest["completion_delivery"] = delivery
            return True
        if (
            isinstance(existing_provenance, Mapping)
            and existing_provenance.get("applicability") == "not_applicable"
        ):
            delivery = dict(manifest.get("completion_delivery") or {})
            if delivery.get("status") != "not_applicable":
                delivery.update(
                    {
                        "transport": "non_discord",
                        "status": "not_applicable",
                        "attempt_count": int(delivery.get("attempt_count") or 0),
                        "evidence": "launch_provenance_explicitly_non_discord",
                    }
                )
                manifest["completion_delivery"] = delivery
                return True
            return False
        discord_hint = (
            isinstance(raw_origin, Mapping) and raw_origin.get("transport") == "discord"
        ) or bool(_RESIDENT_MESSAGE_ID_RE.fullmatch(str(manifest.get("request_id") or "")))
        if discord_hint:
            delivery = dict(manifest.get("completion_delivery") or {})
            delivery.update(
                {
                    "transport": "discord",
                    "status": "unknown" if raw_origin is None else "failed",
                    "attempt_count": int(delivery.get("attempt_count") or 0),
                    "last_error": (
                        "Legacy Discord custody is unknown: source provenance cannot be recovered"
                        if raw_origin is None
                        else "Legacy Discord custody failed validation: reply target is malformed"
                    ),
                    "last_error_class": "UnrecoverableLegacyProvenance",
                    "last_error_category": "invalid_reply_target",
                    "migration_evidence": "no reply target inferred from mutable cursors or final text",
                    "updated_at": _utc_now(),
                }
            )
            manifest["completion_delivery"] = delivery
            return True
        if manifest.get("launch_provenance") is None:
            manifest["launch_provenance"] = normalize_delegation_provenance(
                {
                    "transport": "non_discord",
                    "applicability": "not_applicable",
                    "source_kind": "legacy_non_discord_backfill",
                }
            )
            manifest["completion_delivery"] = {
                "transport": "non_discord",
                "status": "not_applicable",
                "attempt_count": 0,
                "evidence": "legacy manifest had no Discord provenance hint",
            }
            return True
        return False
    if existing_provenance is not None:
        provenance = existing_provenance
    else:
        try:
            provenance = normalize_delegation_provenance(
                {
                    **origin,
                    "applicability": "applicable",
                    "resident_conversation_id": origin.get("conversation_id"),
                    "source_record_id": origin.get("reply_target_source_record_id"),
                    "discord_message_id": origin.get("message_id"),
                    "correlation_id": manifest.get("correlation_id"),
                    "custody_id": manifest.get("custody_id"),
                    "source_kind": "manifest_backfill",
                }
            )
        except DelegationProvenanceError:
            return False
    if manifest.get("discord_origin") != origin:
        manifest["discord_origin"] = discord_origin_projection(provenance)
        changed = True
    for key, value in (
        ("launch_provenance", provenance),
        ("correlation_id", provenance["correlation_id"]),
        ("custody_id", provenance["custody_id"]),
        ("resident_conversation_id", provenance["resident_conversation_id"]),
        ("source_record_id", provenance["source_record_id"]),
    ):
        if manifest.get(key) != value:
            manifest[key] = value
            changed = True
    if not isinstance(manifest.get("completion_delivery"), dict):
        run_id = str(manifest.get("run_id") or "legacy-run")
        manifest["completion_delivery"] = {
            "transport": "discord",
            "status": "pending",
            "attempt_count": 0,
            "provenance_recovered": True,
            "custody_id": provenance["custody_id"],
            "outbox_id": stable_identity(
                "discord-outbox", run_id, provenance["reply_to_message_id"]
            ),
            "idempotency_key": f"resident-subagent-completion:{run_id}",
            "reply_target": {
                "conversation_key": provenance["conversation_key"],
                "message_id": provenance["reply_to_message_id"],
                "source_record_id": provenance["source_record_id"],
            },
        }
        changed = True
    else:
        delivery = dict(manifest["completion_delivery"])
        run_id = str(manifest.get("run_id") or "legacy-run")
        stored_target = delivery.get("reply_target")
        expected_target = {
            "conversation_key": provenance["conversation_key"],
            "message_id": provenance["reply_to_message_id"],
            "source_record_id": provenance["source_record_id"],
        }
        if existing_provenance is not None and isinstance(stored_target, Mapping) and any(
            stored_target.get(key) != value for key, value in expected_target.items()
        ):
            delivery.update(
                {
                    "status": "failed",
                    "last_error": "Discord custody failed: outbox target conflicts with immutable launch provenance",
                    "last_error_class": "ProvenanceCustodyMismatch",
                    "last_error_category": "invalid_reply_target",
                    "updated_at": _utc_now(),
                }
            )
            manifest["completion_delivery"] = delivery
            return True
        additions = {
            "custody_id": provenance["custody_id"],
            "outbox_id": stable_identity(
                "discord-outbox", run_id, provenance["reply_to_message_id"]
            ),
            "idempotency_key": f"resident-subagent-completion:{run_id}",
            "reply_target": expected_target,
        }
        for key, value in additions.items():
            if delivery.get(key) != value:
                delivery[key] = value
                changed = True
        manifest["completion_delivery"] = delivery
    return changed


def _delivery_request_identity(manifest: Mapping[str, Any]) -> tuple[str, ...] | None:
    launch_key = str(manifest.get("launch_idempotency_key") or "").strip()
    if launch_key:
        return "launch_idempotency_key", launch_key
    request_id = str(manifest.get("request_id") or "").strip()
    if not request_id:
        return None
    origin = manifest.get("discord_origin")
    if not isinstance(origin, Mapping):
        return None
    conversation = str(origin.get("conversation_id") or origin.get("conversation_key") or "").strip()
    reply_target = str(origin.get("reply_to_message_id") or "").strip()
    if not conversation or not reply_target:
        return None
    return request_id, conversation, reply_target


def _newer_delivery_run(
    manifest_path: Path,
    manifest: Mapping[str, Any],
) -> str | None:
    """Return the newest sibling run for the same logical resident request."""

    identity = _delivery_request_identity(manifest)
    created_at = _parse_timestamp(manifest.get("created_at"))
    if identity is None or created_at is None:
        return None
    run_id = str(manifest.get("run_id") or manifest_path.parent.name)
    current_order = (created_at, run_id)
    newest: tuple[datetime, str] | None = None
    for sibling_path in manifest_path.parent.parent.glob("*/manifest.json"):
        if sibling_path == manifest_path:
            continue
        try:
            sibling = json.loads(sibling_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(sibling, dict) or not _is_managed_manifest(sibling):
            continue
        _repair_manifest_delivery_provenance(sibling)
        if _delivery_request_identity(sibling) != identity:
            continue
        sibling_created_at = _parse_timestamp(sibling.get("created_at"))
        if sibling_created_at is None:
            continue
        sibling_run_id = str(sibling.get("run_id") or sibling_path.parent.name)
        candidate = (sibling_created_at, sibling_run_id)
        if candidate > current_order and (newest is None or candidate > newest):
            newest = candidate
    return newest[1] if newest is not None else None


def _delivery_claim(
    manifest_path: Path,
    *,
    now: datetime,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Claim one terminal delivery, persisting intent before the Discord call."""

    with _delivery_lock(manifest_path):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        if not isinstance(manifest, dict) or not _is_managed_manifest(manifest):
            return None
        provenance_changed = _repair_manifest_delivery_provenance(manifest)
        delivery = manifest.get("completion_delivery")
        origin = manifest.get("discord_origin")
        if not isinstance(delivery, dict) or not isinstance(origin, dict):
            if provenance_changed:
                _atomic_json(manifest_path, manifest)
            return None
        # A completed provider send is terminal even when a legacy manifest
        # cannot satisfy today's launch-provenance schema. Persist any truthful
        # state repair above, but never revalidate it into a sendable/failure
        # state or redrive it.
        if delivery.get("status") == "delivered":
            if provenance_changed:
                _atomic_json(manifest_path, manifest)
            return None
        try:
            provenance = normalize_delegation_provenance(
                manifest.get("launch_provenance") or {},
            )
        except DelegationProvenanceError:
            delivery.update(
                {
                    "status": "failed",
                    "last_error": "Discord delivery failed: durable provenance is missing or ambiguous",
                    "last_error_class": "InvalidDelegationProvenance",
                    "last_error_category": "invalid_reply_target",
                    "updated_at": now.isoformat(),
                }
            )
            manifest["completion_delivery"] = delivery
            _atomic_json(manifest_path, manifest)
            return None
        if provenance.get("source_record_id") != manifest.get("source_record_id"):
            delivery.update(
                {
                    "status": "failed",
                    "last_error": "Discord delivery failed: source-record custody mismatch",
                    "last_error_class": "InvalidDelegationProvenance",
                    "last_error_category": "invalid_reply_target",
                    "updated_at": now.isoformat(),
                }
            )
            manifest["completion_delivery"] = delivery
            _atomic_json(manifest_path, manifest)
            return None
        delivery_status = str(delivery.get("status") or "pending")
        if delivery_status in {
            "delivered",
            "failed",
            "not_applicable",
            "superseded",
            "unknown",
        }:
            if provenance_changed:
                _atomic_json(manifest_path, manifest)
            return None
        superseded_by = _newer_delivery_run(manifest_path, manifest)
        if superseded_by is not None:
            delivery.update(
                {
                    "status": "superseded",
                    "superseded_by_run_id": superseded_by,
                    "superseded_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            )
            manifest["completion_delivery"] = delivery
            _atomic_json(manifest_path, manifest)
            return None
        # A prior process can stop after Discord accepts the message but before
        # evidence is persisted. Record the ambiguity before using the stable
        # provider nonce for a duplicate-safe recovery attempt.
        if delivery_status == "sending" or delivery.get("claim_state") == "sending":
            history = list(delivery.get("state_history") or [])
            history.append(
                {
                    "status": "unknown",
                    "at": now.isoformat(),
                    "evidence": "process_restarted_with_inflight_provider_attempt",
                    "attempt_id": delivery.get("attempt_id"),
                }
            )
            delivery["state_history"] = history[-20:]
            delivery["last_unknown_at"] = now.isoformat()
        next_attempt_at = _parse_timestamp(delivery.get("next_attempt_at"))
        if next_attempt_at is not None and next_attempt_at > now:
            return None

        status = str(manifest.get("status") or "unknown")
        if status in _ACTIVE_STATUSES:
            pid = manifest.get("pid")
            if isinstance(pid, int) and _pid_matches_manifest(pid, manifest_path):
                return None
            status = "interrupted"
            manifest.update(
                {
                    "status": status,
                    "finished_at": manifest.get("finished_at") or now.isoformat(),
                    "lifecycle_error": "managed supervisor was no longer running",
                }
            )
        if status not in _TERMINAL_STATUSES:
            return None

        normalized_origin = _discord_origin(
            origin,
            project_root=str(manifest.get("project_dir") or "") or None,
        )
        if normalized_origin is None:
            delivery.update(
                {
                    "status": "failed",
                    "last_error": "Discord delivery failed: invalid reply target",
                    "last_error_class": "InvalidDiscordOrigin",
                    "last_error_category": "invalid_reply_target",
                    "last_http_status": None,
                    "last_http_body_category": "not_applicable",
                    "updated_at": now.isoformat(),
                }
            )
            manifest["completion_delivery"] = delivery
            _atomic_json(manifest_path, manifest)
            return None
        if normalized_origin != origin:
            manifest["discord_origin"] = normalized_origin

        outbox_payload = delivery.get("payload")
        if not isinstance(outbox_payload, Mapping):
            content, result_kind = _completion_message(manifest, manifest_path)
            delivery["payload"] = {
                "content": content,
                "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "result_kind": result_kind,
                "materialized_at": now.isoformat(),
            }

        attempt = int(delivery.get("attempt_count") or 0) + 1
        if attempt > _DELIVERY_MAX_ATTEMPTS:
            delivery.update(
                {
                    "status": "failed",
                    "last_error": "Discord delivery failed: retry budget exhausted",
                    "last_error_class": "DeliveryRetryExhausted",
                    "last_error_category": "retry_exhausted",
                    "updated_at": now.isoformat(),
                }
            )
            manifest["completion_delivery"] = delivery
            _atomic_json(manifest_path, manifest)
            return None
        run_id = str(manifest.get("run_id") or manifest_path.parent.name)
        nonce = str(
            delivery.get("discord_nonce")
            or hashlib.sha256(f"resident-subagent-completion:{run_id}".encode("utf-8")).hexdigest()[:20]
        )
        delivery.update(
            {
                "status": "pending",
                "claim_state": "sending",
                "attempt_count": attempt,
                "last_attempt_at": now.isoformat(),
                "attempt_id": f"{run_id}:{attempt}",
                "discord_nonce": nonce,
            }
        )
        history = list(delivery.get("state_history") or [])
        history.append(
            {
                "status": "pending",
                "at": now.isoformat(),
                "evidence": "provider_attempt_claimed",
                "attempt_id": f"{run_id}:{attempt}",
            }
        )
        delivery["state_history"] = history[-20:]
        delivery.pop("next_attempt_at", None)
        manifest["completion_delivery"] = delivery
        _atomic_json(manifest_path, manifest)
        return manifest, normalized_origin


def _completion_turn_claim(
    manifest_path: Path,
    *,
    now: datetime,
) -> dict[str, Any] | None:
    """Claim one terminal run for a normal resident verification turn.

    This claim shares the completion-delivery lock and lives in the canonical
    run manifest.  A completed claim is immutable; an in-flight claim is only
    reclaimable after the resident's normal stale-turn timeout window.
    """

    with _delivery_lock(manifest_path):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        if not _is_managed_manifest(manifest):
            return None
        provenance_changed = _repair_manifest_delivery_provenance(manifest)
        if str(manifest.get("status") or "") not in _TERMINAL_STATUSES:
            if provenance_changed:
                _atomic_json(manifest_path, manifest)
            return None
        delivery = manifest.get("completion_delivery")
        if not isinstance(delivery, Mapping) or delivery.get("transport") != "discord":
            if provenance_changed:
                _atomic_json(manifest_path, manifest)
            return None
        if str(delivery.get("status") or "") in {
            "delivered", "failed", "not_applicable", "superseded", "suppressed", "unknown"
        }:
            return None
        completion = dict(manifest.get("resident_completion_turn") or {})
        if completion.get("status") == "completed":
            return None
        next_attempt_at = _parse_timestamp(completion.get("next_attempt_at"))
        if next_attempt_at is not None and next_attempt_at > now:
            return None
        claimed_at = _parse_timestamp(completion.get("claimed_at"))
        if (
            completion.get("status") == "running"
            and claimed_at is not None
            and (now - claimed_at).total_seconds() < 300
        ):
            return None
        attempt = int(completion.get("attempt_count") or 0) + 1
        run_id = str(manifest.get("run_id") or manifest_path.parent.name)
        completion.update(
            {
                "schema_version": "arnold-resident-completion-turn-v1",
                "trigger_id": stable_identity("resident-completion-turn", run_id),
                "status": "running",
                "attempt_count": attempt,
                "claimed_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        )
        completion.pop("next_attempt_at", None)
        manifest["resident_completion_turn"] = completion
        _atomic_json(manifest_path, manifest)
        return manifest


def _finish_completion_turn(
    manifest_path: Path,
    *,
    now: datetime,
    result: ManagedCompletionTurnResult,
) -> None:
    safe_text = result.final_text.strip()
    if not safe_text:
        safe_text = (
            "Verification outcome: unknown. The resident completion turn produced no "
            "user-facing verification summary, so the delegated result is not being treated as proof."
        )
    with _delivery_lock(manifest_path):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        completion = dict(manifest.get("resident_completion_turn") or {})
        completion.update(
            {
                "status": "completed",
                "verification_outcome": result.verification_outcome,
                "resident_turn_id": result.turn_id,
                "outbound_message_id": result.outbound_message_id,
                "summary_sha256": hashlib.sha256(safe_text.encode("utf-8")).hexdigest(),
                "completed_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        )
        manifest["resident_completion_turn"] = completion
        delivery = dict(manifest.get("completion_delivery") or {})
        delivery["payload"] = {
            "content": safe_text,
            "content_sha256": hashlib.sha256(safe_text.encode("utf-8")).hexdigest(),
            "result_kind": "resident_verified_summary",
            "verification_outcome": result.verification_outcome,
            "resident_turn_id": result.turn_id,
            "materialized_at": now.isoformat(),
        }
        manifest["completion_delivery"] = delivery
        _atomic_json(manifest_path, manifest)


def record_completion_turn_id(manifest_path: Path, turn_id: str) -> None:
    """Fence the canonical resident turn identity before model execution begins."""

    with _delivery_lock(manifest_path):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        completion = dict(manifest.get("resident_completion_turn") or {})
        existing = str(completion.get("resident_turn_id") or "")
        if existing and existing != turn_id:
            raise RuntimeError("resident completion turn identity changed")
        completion["resident_turn_id"] = turn_id
        completion["updated_at"] = _utc_now()
        manifest["resident_completion_turn"] = completion
        _atomic_json(manifest_path, manifest)


def _retry_completion_turn(manifest_path: Path, *, now: datetime, exc: Exception) -> str:
    """Persist a bounded retry without ever falling back to the unverified result."""

    with _delivery_lock(manifest_path):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        completion = dict(manifest.get("resident_completion_turn") or {})
        attempt = max(1, int(completion.get("attempt_count") or 1))
        if attempt >= _DELIVERY_MAX_ATTEMPTS:
            run_id = str(manifest.get("run_id") or manifest_path.parent.name)
            content = (
                "Verification outcome: unknown. The resident could not establish an independent "
                f"verification turn for delegated run {run_id} after bounded retries. The delegated "
                "terminal result is not being treated as proof; operator inspection is required."
            )
            completion.update(
                {
                    "status": "completed",
                    "verification_outcome": "unknown",
                    "last_error_class": exc.__class__.__name__,
                    "last_error": "resident completion verification retry budget exhausted",
                    "summary_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    "completed_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            )
            manifest["resident_completion_turn"] = completion
            delivery = dict(manifest.get("completion_delivery") or {})
            delivery["payload"] = {
                "content": content,
                "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "result_kind": "resident_verification_unavailable",
                "verification_outcome": "unknown",
                "materialized_at": now.isoformat(),
            }
            manifest["completion_delivery"] = delivery
            _atomic_json(manifest_path, manifest)
            return "unknown"
        delay_s = min(_DELIVERY_RETRY_MAX_S, _DELIVERY_RETRY_BASE_S * (2 ** min(attempt - 1, 7)))
        completion.update(
            {
                "status": "retry_pending",
                "last_error_class": exc.__class__.__name__,
                "last_error": "resident completion verification turn failed",
                "next_attempt_at": datetime.fromtimestamp(now.timestamp() + delay_s, timezone.utc).isoformat(),
                "updated_at": now.isoformat(),
            }
        )
        manifest["resident_completion_turn"] = completion
        _atomic_json(manifest_path, manifest)
        return "retry_pending"


def _completion_message(manifest: Mapping[str, Any], manifest_path: Path) -> tuple[str, str]:
    run_id = str(manifest.get("run_id") or manifest_path.parent.name)
    status = str(manifest.get("status") or "unknown")
    result_path = Path(str(manifest.get("result_path") or "result.md"))
    if not result_path.is_absolute():
        result_path = manifest_path.parent / result_path
    if status == "completed":
        try:
            with result_path.open("r", encoding="utf-8", errors="replace") as handle:
                final_text = handle.read(_MAX_COMPLETION_DELIVERY_CHARS + 1).strip()
        except OSError:
            final_text = ""
        if final_text:
            from agentbox.redaction import redact_text

            safe_text = redact_text(final_text)
            if len(safe_text) > _MAX_COMPLETION_DELIVERY_CHARS:
                suffix = f"\n\n[Result truncated for Discord; durable run: {run_id}]"
                safe_text = safe_text[: _MAX_COMPLETION_DELIVERY_CHARS - len(suffix)].rstrip() + suffix
            return safe_text, "final_result"
        return (
            f"The managed subagent finished run {run_id}, but it produced no deliverable final "
            "message. The run is not being reported as a successful result.",
            "missing_result",
        )
    return (
        f"The managed subagent did not complete this request successfully (run {run_id}, "
        f"status: {status}). No successful final result was produced.",
        "terminal_failure",
    )


def _finish_delivery(
    manifest_path: Path,
    *,
    now: datetime,
    message_ids: list[str],
    result_kind: str,
) -> None:
    with _delivery_lock(manifest_path):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        delivery = dict(manifest.get("completion_delivery") or {})
        history = list(delivery.get("state_history") or [])
        history.append(
            {
                "status": "delivered",
                "at": now.isoformat(),
                "evidence": "provider_message_ids_persisted",
                "attempt_id": delivery.get("attempt_id"),
            }
        )
        delivery.update(
            {
                "status": "delivered",
                "delivered_at": now.isoformat(),
                "discord_message_ids": message_ids,
                "result_kind": result_kind,
                "updated_at": now.isoformat(),
                "state_history": history[-20:],
            }
        )
        delivery.pop("claim_state", None)
        manifest["completion_delivery"] = delivery
        _atomic_json(manifest_path, manifest)


def _optional_http_status(exc: Exception) -> int | None:
    candidates = [getattr(exc, "status", None), getattr(exc, "status_code", None)]
    response = getattr(exc, "response", None)
    if response is not None:
        candidates.extend([getattr(response, "status", None), getattr(response, "status_code", None)])
    for candidate in candidates:
        try:
            status = int(candidate)
        except (TypeError, ValueError):
            continue
        if 100 <= status <= 599:
            return status
    return None


def _optional_discord_error_code(exc: Exception) -> int | None:
    try:
        code = int(getattr(exc, "code", None))
    except (TypeError, ValueError):
        return None
    return code if code > 0 else None


def _http_body_category(exc: Exception, *, http_status: int | None) -> str:
    body = getattr(exc, "text", None)
    if body is None:
        response = getattr(exc, "response", None)
        body = getattr(response, "text", None) if response is not None else None
    if isinstance(body, Mapping) or isinstance(body, (list, tuple)):
        return "json"
    if isinstance(body, bytes):
        return "binary" if body else "empty"
    if isinstance(body, str):
        stripped = body.strip()
        if not stripped:
            return "empty"
        if stripped[:1] in {"{", "["}:
            return "json"
        return "text"
    return "unavailable" if http_status is not None else "not_applicable"


def _delivery_error_evidence(exc: Exception) -> dict[str, object]:
    """Return actionable failure evidence without persisting remote response text."""

    status = _optional_http_status(exc)
    discord_code = _optional_discord_error_code(exc)
    detail = str(exc).lower()
    if "reply target" in detail or "snowflake" in detail:
        category = "invalid_reply_target"
    elif status == 429:
        category = "rate_limited"
    elif status == 401:
        category = "unauthorized"
    elif status == 403:
        category = "forbidden"
    elif status == 404:
        category = "not_found"
    elif status is not None and status >= 500:
        category = "server_error"
    elif status is not None and status >= 400:
        category = "client_error"
    elif isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        category = "timeout"
    elif isinstance(exc, (ConnectionError, OSError)):
        category = "network_error"
    else:
        category = "runtime_error"
    body_category = _http_body_category(exc, http_status=status)
    qualifiers = []
    if status is not None:
        qualifiers.append(f"HTTP {status}")
    if discord_code is not None:
        qualifiers.append(f"Discord code {discord_code}")
    qualifiers.append(f"body={body_category}")
    summary = f"Discord delivery failed: {category} ({'; '.join(qualifiers)})"
    return {
        "last_error": summary,
        "last_error_class": exc.__class__.__name__,
        "last_error_category": category,
        "last_http_status": status,
        "last_discord_error_code": discord_code,
        "last_http_body_category": body_category,
    }


def _retry_delivery(manifest_path: Path, *, now: datetime, exc: Exception) -> str:
    with _delivery_lock(manifest_path):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        delivery = dict(manifest.get("completion_delivery") or {})
        attempt = max(1, int(delivery.get("attempt_count") or 1))
        delay_s = min(_DELIVERY_RETRY_MAX_S, _DELIVERY_RETRY_BASE_S * (2 ** min(attempt - 1, 7)))
        next_attempt = now.timestamp() + delay_s
        evidence = _delivery_error_evidence(exc)
        history = list(delivery.get("error_history") or [])
        history.append(
            {
                "attempt_id": delivery.get("attempt_id"),
                "attempted_at": delivery.get("last_attempt_at") or now.isoformat(),
                **evidence,
            }
        )
        category = str(evidence["last_error_category"])
        permanent = category in {
            "invalid_reply_target",
            "unauthorized",
            "forbidden",
            "not_found",
            "client_error",
        }
        exhausted = attempt >= _DELIVERY_MAX_ATTEMPTS
        status = "failed" if permanent or exhausted else "retry_pending"
        state_history = list(delivery.get("state_history") or [])
        state_history.append(
            {
                "status": status,
                "at": now.isoformat(),
                "evidence": (
                    "permanent_provider_rejection"
                    if permanent
                    else "retry_budget_exhausted"
                    if exhausted
                    else "retryable_provider_failure"
                ),
                "attempt_id": delivery.get("attempt_id"),
            }
        )
        delivery.update(
            {
                "status": status,
                "updated_at": now.isoformat(),
                "error_history": history[-10:],
                "state_history": state_history[-20:],
                **evidence,
            }
        )
        delivery.pop("claim_state", None)
        if status == "retry_pending":
            delivery["next_attempt_at"] = datetime.fromtimestamp(
                next_attempt, timezone.utc
            ).isoformat()
        else:
            delivery.pop("next_attempt_at", None)
        manifest["completion_delivery"] = delivery
        _atomic_json(manifest_path, manifest)
        return status


async def sweep_managed_agent_deliveries(
    *,
    outbound: Any,
    project_root: str | Path = ".",
    workspace_root: str | Path | None = "/workspace",
    now: datetime | None = None,
    completion_turn_handler: Callable[
        [Path, Mapping[str, Any]], Awaitable[ManagedCompletionTurnResult]
    ] | None = None,
) -> ManagedAgentDeliverySweepResult:
    """Reply with terminal managed-agent results and persist retry-safe evidence."""

    from .runtime import OutboundMessage

    now = now or datetime.now(timezone.utc)
    paths = _managed_manifest_paths(project_root=project_root, workspace_root=workspace_root)
    delivered = retry_pending = skipped = failed = 0
    for manifest_path in paths:
        if completion_turn_handler is not None:
            completion_claim = _completion_turn_claim(manifest_path, now=now)
            if completion_claim is not None:
                try:
                    completion_result = await completion_turn_handler(
                        manifest_path, completion_claim
                    )
                except Exception as exc:
                    verification_disposition = _retry_completion_turn(
                        manifest_path, now=now, exc=exc
                    )
                    retry_pending += int(verification_disposition == "retry_pending")
                    failed += int(verification_disposition == "unknown")
                    LOGGER.exception(
                        "Resident completion verification turn failed run_id=%s",
                        completion_claim.get("run_id") or manifest_path.parent.name,
                    )
                    continue
                _finish_completion_turn(
                    manifest_path,
                    now=now,
                    result=completion_result,
                )
            try:
                current = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                skipped += 1
                continue
            completion_state = current.get("resident_completion_turn")
            if (
                str(current.get("status") or "") in _TERMINAL_STATUSES
                and isinstance(current.get("completion_delivery"), Mapping)
                and current["completion_delivery"].get("transport") == "discord"
                and (
                    not isinstance(completion_state, Mapping)
                    or completion_state.get("status") != "completed"
                )
            ):
                skipped += 1
                continue
        try:
            before_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            before_delivery = before_payload.get("completion_delivery")
            before_status = (
                str(before_delivery.get("status") or "")
                if isinstance(before_delivery, Mapping)
                else ""
            )
        except (OSError, ValueError, TypeError):
            before_status = ""
        claim = _delivery_claim(manifest_path, now=now)
        if claim is None:
            try:
                after_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                after_delivery = after_payload.get("completion_delivery")
                after_status = (
                    str(after_delivery.get("status") or "")
                    if isinstance(after_delivery, Mapping)
                    else ""
                )
            except (OSError, ValueError, TypeError):
                after_status = ""
            if after_status == "failed" and before_status != "failed":
                failed += 1
            else:
                skipped += 1
            continue
        manifest, origin = claim
        delivery = dict(manifest.get("completion_delivery") or {})
        payload = delivery.get("payload")
        if not isinstance(payload, Mapping):
            # New claims always materialize before returning. Treat an absent
            # payload as failed custody rather than re-reading mutable output.
            disposition = _retry_delivery(
                manifest_path,
                now=now,
                exc=RuntimeError("durable outbox payload missing"),
            )
            retry_pending += int(disposition == "retry_pending")
            failed += int(disposition == "failed")
            continue
        content = str(payload.get("content") or "")
        result_kind = str(payload.get("result_kind") or "missing_result")
        metadata: dict[str, Any] = {
            "managed_agent_run_id": manifest.get("run_id") or manifest_path.parent.name,
            "discord_reply_to_message_id": origin["reply_to_message_id"],
            "completion_delivery": True,
            "discord_nonce": dict(manifest.get("completion_delivery") or {}).get("discord_nonce"),
            "notification_safety_context": {
                "project_dir": manifest.get("project_dir"),
                "notification_context": manifest.get("notification_context"),
                "launch_provenance": manifest.get("launch_provenance"),
            },
        }
        # Fake outbound sinks remain usable for deterministic delivery tests,
        # while the production Discord boundary independently reclassifies
        # durable manifest context immediately before the network send.
        if str(getattr(outbound, "delivery_environment", "")).lower() == "production":
            from arnold_pipelines.megaplan.notification_safety import (
                classify_user_notification,
            )

            safety = classify_user_notification(
                payload=metadata["notification_safety_context"], env={}
            )
            if not safety.allowed:
                delivery.update(
                    {
                        "status": "suppressed",
                        "claim_state": "suppressed",
                        "last_error": "",
                        "last_error_class": "",
                        "last_error_category": "test_execution_suppressed",
                        "suppression_reason": safety.reason,
                        "updated_at": now.isoformat(),
                    }
                )
                history = list(delivery.get("state_history") or [])
                history.append(
                    {
                        "status": "suppressed",
                        "at": now.isoformat(),
                        "evidence": "notification_safety_policy",
                        "reason": safety.reason,
                    }
                )
                delivery["state_history"] = history[-20:]
                manifest["completion_delivery"] = delivery
                _atomic_json(manifest_path, manifest)
                skipped += 1
                continue
        try:
            run_id = manifest.get("run_id") or manifest_path.parent.name
            await outbound.send(
                OutboundMessage(
                    conversation_key=str(origin["conversation_key"]),
                    content=content,
                    idempotency_key=f"resident-subagent-completion:{run_id}",
                    metadata=metadata,
                )
            )
        except Exception as exc:
            evidence = _delivery_error_evidence(exc)
            disposition = _retry_delivery(manifest_path, now=now, exc=exc)
            if disposition == "retry_pending":
                retry_pending += 1
            else:
                failed += 1
            LOGGER.warning(
                "Managed agent completion delivery disposition=%s run_id=%s error_class=%s "
                "error_category=%s http_status=%s body_category=%s",
                disposition,
                manifest.get("run_id") or manifest_path.parent.name,
                exc.__class__.__name__,
                evidence["last_error_category"],
                evidence["last_http_status"],
                evidence["last_http_body_category"],
            )
            continue
        message_ids = [str(value) for value in metadata.get("discord_message_ids", []) if str(value)]
        _finish_delivery(
            manifest_path,
            now=now,
            message_ids=message_ids,
            result_kind=result_kind,
        )
        delivered += 1
    return ManagedAgentDeliverySweepResult(
        scanned=len(paths),
        delivered=delivered,
        retry_pending=retry_pending,
        skipped=skipped,
        failed=failed,
    )


def list_managed_resident_agents(
    *,
    project_root: str | Path = ".",
    workspace_root: str | Path | None = "/workspace",
    recent_limit: int = 10,
) -> dict[str, Any]:
    """Build bounded hot-context status for resident-delegated agents.

    Runtime manifests remain under ``plans/`` and are deliberately separate
    from Arnold workflow-internal subagents. The workspace scan preserves
    visibility for resident launches targeting sibling checkouts.
    """
    roots = _managed_run_roots(project_root=project_root, workspace_root=workspace_root)

    rows: list[dict[str, Any]] = []
    for root in sorted(roots):
        if not root.is_dir():
            continue
        for manifest_path in root.glob("*/manifest.json"):
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            schema = payload.get("schema_version")
            if schema not in {MANAGED_RUN_SCHEMA, LEGACY_MANAGED_RUN_SCHEMA}:
                continue
            if schema == MANAGED_RUN_SCHEMA and (
                payload.get("run_kind") != MANAGED_RUN_KIND
                or payload.get("custodian") != MANAGED_RUN_CUSTODIAN
            ):
                continue
            persisted_status = str(payload.get("status") or "unknown")
            pid = payload.get("pid")
            process_matches = isinstance(pid, int) and _pid_matches_manifest(pid, manifest_path)
            live = persisted_status in _ACTIVE_STATUSES and process_matches
            observed_status = persisted_status
            if persisted_status in _ACTIVE_STATUSES and not process_matches:
                observed_status = "interrupted"

            def artifact_path(field: str, fallback: str) -> str:
                raw = payload.get(field) or fallback
                path = Path(str(raw))
                if not path.is_absolute():
                    path = manifest_path.parent / path
                return str(path.resolve())

            rows.append(
                {
                    "run_id": payload.get("run_id") or manifest_path.parent.name,
                    "run_kind": payload.get("run_kind") or MANAGED_RUN_KIND,
                    "status": observed_status,
                    "persisted_status": persisted_status,
                    "live": live,
                    "pid": pid,
                    "backend": payload.get("backend"),
                    "model": payload.get("model"),
                    "reasoning_effort": payload.get("reasoning_effort"),
                    "task_kind": payload.get("task_kind"),
                    "difficulty": payload.get("difficulty"),
                    "route_class": payload.get("route_class"),
                    "request_id": payload.get("request_id"),
                    "caller_request_id": payload.get("caller_request_id"),
                    "correlation_id": payload.get("correlation_id"),
                    "custody_id": payload.get("custody_id"),
                    "source_record_id": payload.get("source_record_id"),
                    "task_sha256": payload.get("task_sha256"),
                    "task_excerpt": payload.get("task_excerpt"),
                    "project_dir": payload.get("project_dir"),
                    "created_at": payload.get("created_at"),
                    "started_at": payload.get("started_at"),
                    "finished_at": payload.get("finished_at"),
                    "manifest_path": str(manifest_path.resolve()),
                    "full_log_path": artifact_path(
                        "full_log_path", str(payload.get("log_path") or "run.log")
                    ),
                    "result_path": artifact_path("result_path", "result.md"),
                    "discord_origin": payload.get("discord_origin"),
                    "launch_provenance": payload.get("launch_provenance"),
                    "completion_delivery": payload.get("completion_delivery"),
                }
            )
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    running = [row for row in rows if row["live"]]
    recent = [row for row in rows if not row["live"]][:max(0, recent_limit)]
    delivery_status_counts: dict[str, int] = {}
    terminal_delivery_status_counts: dict[str, int] = {}
    for row in rows:
        delivery = row.get("completion_delivery")
        status = (
            str(delivery.get("status") or "pending")
            if isinstance(delivery, dict)
            else "not_applicable"
        )
        delivery_status_counts[status] = delivery_status_counts.get(status, 0) + 1
        if row["status"] in _TERMINAL_STATUSES:
            terminal_delivery_status_counts[status] = (
                terminal_delivery_status_counts.get(status, 0) + 1
            )
    return {
        "schema_version": MANAGED_RUN_SCHEMA,
        "scope": "resident-delegated agents only; excludes workflow-internal subagents",
        "run_root": str((Path(project_root).resolve() / DEFAULT_MANAGED_RUN_ROOT)),
        "running": running,
        "recent": recent,
        "running_count": len(running),
        "recent_count": len(recent),
        "delivery_status_counts": delivery_status_counts,
        "terminal_delivery_status_counts": terminal_delivery_status_counts,
        "delivery_attention_count": sum(
            count
            for status, count in terminal_delivery_status_counts.items()
            if status in {"pending", "retry_pending", "failed", "unknown"}
        ),
    }


async def launch_subagent_task(
    config: ResidentConfig,
    *,
    task: str,
    toolsets: str | None = None,
    project_dir: str | None = None,
    backend: str = "codex",
    background: bool = True,
    model: str | None = None,
    reasoning_effort: str | None = None,
    task_kind: DelegatedTaskKind = DEFAULT_DELEGATED_TASK_KIND,
    difficulty: int = DEFAULT_DELEGATED_DIFFICULTY,
    request_id: str | None = None,
    launch_origin: Mapping[str, Any] | None = None,
    retry_of_run_id: str | None = None,
) -> SubagentResult:
    """Dispatch ``task`` through the resident-owned delegated-agent seam.

    Managed Codex is the canonical resident path.  ``backend="hermes"`` is an
    explicit compatibility mode for old synchronous callers; its stdout carries
    the final response and it does not claim the managed lifecycle schema.
    """
    if backend == "codex":
        if not background:
            raise ValueError(
                "Codex resident subagents must use background=True for durable lifecycle tracking"
            )
        route = route_delegated_task(task_kind=task_kind, difficulty=difficulty)
        selected_effort = reasoning_effort or route.reasoning_effort
        if selected_effort not in _VALID_DELEGATED_EFFORTS:
            raise ValueError(
                "reasoning_effort must be one of "
                f"{', '.join(sorted(_VALID_DELEGATED_EFFORTS))}; got {selected_effort!r}"
            )
        return launch_codex_subagent_detached(
            task=task,
            project_dir=project_dir,
            model=model or route.model,
            reasoning_effort=selected_effort,
            task_kind=route.task_kind,
            difficulty=route.difficulty,
            route_class=(
                "explicit_override"
                if model is not None or reasoning_effort is not None
                else route.route_class
            ),
            request_id=request_id,
            launch_origin=launch_origin,
            retry_of_run_id=retry_of_run_id,
        )
    if backend != "hermes":
        raise ValueError(f"unsupported subagent backend: {backend}")
    compatibility_provenance = _canonical_launch_provenance(
        launch_origin,
        project_root=Path(project_dir or Path.cwd()).resolve(),
        request_id=request_id,
    )
    if compatibility_provenance["applicability"] == "applicable":
        raise ValueError(
            "Hermes compatibility launches are synchronous and cannot satisfy durable Discord custody"
        )
    if not LAUNCHER_PATH.exists():
        raise FileNotFoundError(f"hermes launcher not found: {LAUNCHER_PATH}")

    argv: list[str] = [
        sys.executable,
        str(LAUNCHER_PATH),
        "--model",
        config.subagent_model_name,
        "--toolsets",
        toolsets or config.special_requests_subagent_toolsets,
        "--max-tokens",
        str(config.special_requests_subagent_max_tokens),
    ]
    if project_dir:
        argv += ["--project-dir", str(project_dir)]

    # Multi-line prompts are brittle on argv — write to a query file instead.
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(_delivery_prompt(task))
        query_path = handle.name
    argv += ["--query-file", query_path]

    timeout_s = float(config.special_requests_subagent_timeout_s)
    try:
        completed = await asyncio.to_thread(_run_subprocess, argv, timeout_s)
    finally:
        try:
            Path(query_path).unlink(missing_ok=True)
        except OSError:
            LOGGER.debug("could not remove subagent query file %s", query_path, exc_info=True)

    return completed


def _build_local_seam_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m arnold_pipelines.megaplan.resident.subagent",
        description="Supported local seam for resident-managed delegated agents",
    )
    sub = parser.add_subparsers(dest="action", required=True)
    launch = sub.add_parser(
        "launch",
        help="Launch a durable Codex agent, inheriting resident delegation provenance",
    )
    task_source = launch.add_mutually_exclusive_group(required=True)
    task_source.add_argument("--task")
    task_source.add_argument("--task-file")
    launch.add_argument("--project-dir")
    launch.add_argument("--model")
    launch.add_argument(
        "--reasoning-effort", choices=sorted(_VALID_DELEGATED_EFFORTS)
    )
    launch.add_argument("--task-kind", choices=DELEGATED_TASK_KINDS, default=DEFAULT_DELEGATED_TASK_KIND)
    launch.add_argument("--difficulty", type=int, default=DEFAULT_DELEGATED_DIFFICULTY)
    launch.add_argument("--request-id")
    launch.add_argument("--retry-of-run-id")
    return parser


def _local_launch_task(args: argparse.Namespace) -> str:
    if args.task_file:
        try:
            return Path(args.task_file).expanduser().read_text(encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"cannot read --task-file: {exc}") from exc
    return str(args.task or "")


def _main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    # Private worker compatibility; deliberately absent from the public parser.
    if len(raw) == 2 and raw[0] == "--run-codex":
        return _run_codex_manifest(Path(raw[1]))
    args = _build_local_seam_parser().parse_args(raw)
    if args.action == "launch":
        task = _local_launch_task(args).strip()
        if not task:
            raise SystemExit("delegated task must not be empty")
        result = asyncio.run(
            launch_subagent_task(
                ResidentConfig(),
                task=task,
                project_dir=args.project_dir,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                task_kind=args.task_kind,
                difficulty=args.difficulty,
                request_id=args.request_id,
                retry_of_run_id=args.retry_of_run_id,
            )
        )
        print(json.dumps(result.__dict__, sort_keys=True))
        return 0 if result.ok else 1
    raise SystemExit(f"unsupported resident subagent action: {args.action}")


if __name__ == "__main__":
    raise SystemExit(_main())


def _run_subprocess(argv: list[str], timeout_s: float) -> SubagentResult:
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return SubagentResult(
            ok=False,
            final_text="",
            stderr=str(exc),
            returncode=-1,
            error=f"subagent timed out after {timeout_s:.0f}s",
        )
    final_text = (completed.stdout or "").strip()
    stderr = completed.stderr or ""
    returncode = completed.returncode
    ok = returncode == 0 and bool(final_text)
    error: str | None = None
    if not ok:
        tail = stderr.strip()[:500]
        error = f"subagent exit {returncode}" + (f": {tail}" if tail else " (no stdout)")
    return SubagentResult(
        ok=ok,
        final_text=final_text,
        stderr=stderr,
        returncode=returncode,
        error=error,
    )
