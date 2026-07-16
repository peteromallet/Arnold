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
from datetime import datetime, timedelta, timezone
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
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from agentbox.redaction import redact_text
from arnold_pipelines.megaplan.managed_agent import (
    ACTIVE_STATUSES as SHARED_ACTIVE_STATUSES,
    MANAGED_AGENT_CUSTODIAN,
    MANAGED_AGENT_SCHEMA,
    is_managed_manifest,
    managed_run_roots,
    validate_automatic_managed_manifest,
    observed_status as shared_observed_status,
)

from .config import ResidentConfig
from .git_custody import (
    GitCustodyError,
    render_git_custody_contract,
    resolve_launch_git_custody,
    validate_git_custody_evidence,
)
from .provenance import (
    DelegationProvenanceError,
    discord_origin_projection,
    environment_with_provenance,
    normalize_delegation_provenance,
    provenance_from_environment,
    stable_identity,
)
from .query_relationship import relationship_from_environment_or_project

LOGGER = logging.getLogger(__name__)
MANAGED_RUN_SCHEMA = MANAGED_AGENT_SCHEMA
MANAGED_RUN_KIND = "resident_delegated_agent"
MANAGED_RUN_CUSTODIAN = MANAGED_AGENT_CUSTODIAN
LEGACY_MANAGED_RUN_SCHEMA = "arnold-subagent-run-v1"
DEFAULT_MANAGED_RUN_ROOT = Path(".megaplan/plans/resident-subagents")
DEFAULT_DELEGATED_TASK_KIND = "routine"
DEFAULT_DELEGATED_DIFFICULTY = 4
DEFAULT_DELEGATED_WORK_INTENT = "auto"
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
DELEGATED_WORK_INTENTS = ("auto", "execution", "review", "speculative")
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
DelegatedWorkIntent = Literal["auto", "execution", "review", "speculative"]
_BOUNDED_TASK_KINDS = frozenset({"lookup", "extraction", "mechanical"})
_HIGH_RISK_TASK_KINDS = frozenset(
    {"root_cause", "architecture", "migration", "review", "autonomous"}
)
_VALID_DELEGATED_EFFORTS = frozenset(
    {"minimal", "low", "medium", "high", "xhigh", "max"}
)
_NON_EXECUTION_TASK_KINDS = frozenset(
    {"lookup", "extraction", "research", "root_cause", "architecture", "review"}
)
_ACTIVE_STATUSES = SHARED_ACTIVE_STATUSES
_TERMINAL_STATUSES = frozenset(
    {"completed", "failed", "interrupted", "cancelled", "superseded"}
)
_CONTROL_TERMINAL_STATUSES = frozenset({"cancelled", "superseded"})
_DELIVERY_RETRY_BASE_S = 30
_DELIVERY_RETRY_MAX_S = 60 * 60
_DELIVERY_MAX_ATTEMPTS = 8
_MAX_COMPLETION_DELIVERY_CHARS = 7_600
QUEUE_SCHEMA = "arnold-resident-subagent-queue-v1"
QUEUE_REFERENCE_SCHEMA = "arnold-resident-subagent-reference-v1"
QUEUE_CROSS_REQUEST_AUTHORIZATION_SCHEMA = (
    "arnold-resident-cross-request-queue-authorization-v1"
)
QUEUE_TRIGGER_POLICY = "on_predecessor_success"
MAX_QUEUE_CHAIN_DEPTH = 32
MAX_QUEUE_PROMPT_CHARS = 16_000
MAX_QUEUE_HOT_CONTEXT_ROWS = 8
_QUEUE_RETRY_BASE_S = 5
_QUEUE_RETRY_MAX_S = 5 * 60
_QUEUE_MAX_LAUNCH_ATTEMPTS = 3
MAX_DELEGATED_TASK_CHARS = 32_000
MAX_DELEGATED_PROMPT_CHARS = 40_000
MAX_FOLLOWUP_MESSAGE_CHARS = 32_000
MAX_AGENT_DESCRIPTION_CHARS = 180
MAX_MODEL_SESSION_LOG_PREFIX_BYTES = 1024 * 1024
FOLLOWUP_SCHEMA = "arnold-resident-agent-followup-v1"
AGGREGATION_SCHEMA = "arnold-resident-agent-aggregation-v1"
AGGREGATION_ROLES = frozenset({"synthesis_delivery_owner", "internal_contributor"})
DISCORD_FOLLOWUP_WINDOW = timedelta(minutes=15)
_RUN_ID_RE = re.compile(r"^subagent-[0-9]{8}-[0-9]{6}-[A-Za-z0-9]{8}$")
_RESIDENT_TURN_ID_RE = re.compile(r"^turn_[A-Za-z0-9]{12,64}$")
_FOLLOWUP_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_SYNTHESIS_GROUP_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
_CODEX_SESSION_RE = re.compile(
    r"(?im)^session id:\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\s*$"
)
_CODEX_JSON_SESSION_RE = re.compile(
    r'"(?:thread_id|session_id)"\s*:\s*"'
    r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
    re.IGNORECASE,
)
FINAL_SUMMARY_INSTRUCTION = (
    "Your FINAL response will be sent directly to the user as a Discord reply. "
    "Make it a concise, user-facing summary that stands on its own. State the outcome, "
    "the important changes or findings, verification performed, and any remaining operational "
    "caveat. Do not include internal handoff notes, ask a follow-up question, or merely say that "
    "work is complete. Never expose credentials or other secrets. Preserve and follow all "
    "task-specific instructions above."
)
DELEGATION_DELIVERY_INSTRUCTION_SCHEMA = (
    "arnold-resident-delegation-delivery-instruction-v1"
)
DELEGATION_DELIVERY_INSTRUCTION_HEADER = (
    "[Resident delegation execution/delivery instruction — canonical v1]"
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
    description: str | None = None


@dataclass(frozen=True)
class SubagentFollowupResult:
    """Durable acceptance evidence for one resident-managed follow-up."""

    ok: bool
    followup_id: str
    target_run_id: str
    parent_run_id: str
    lineage_root_run_id: str
    continuation_run_id: str
    status: str
    evidence_path: str
    message_path: str
    continuation_manifest_path: str
    model_session_id: str | None = None
    idempotent_replay: bool = False


class SubagentFollowupError(ValueError):
    """A follow-up target or custody/session binding is unsafe or ambiguous."""


class SubagentQueueError(ValueError):
    """A queued successor contract is unsafe, invalid, or ambiguous."""


@dataclass(frozen=True)
class DiscordFollowupTarget:
    """One unambiguous managed lineage launched from an exact Discord source."""

    run_id: str
    lineage_root_run_id: str
    manifest_path: str
    launch_anchor: str
    launch_anchor_field: str


@dataclass(frozen=True)
class ManagedAgentDeliverySweepResult:
    scanned: int = 0
    delivered: int = 0
    retry_pending: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass(frozen=True)
class ManagedAgentQueueSweepResult:
    """Durable reconciliation result for resident-managed successor queues."""

    scanned: int = 0
    waiting: int = 0
    launched: int = 0
    retry_pending: int = 0
    failed_closed: int = 0
    skipped: int = 0


@dataclass(frozen=True)
class ManagedCompletionTurnResult:
    """Durable output of the resident's independent completion-verification turn."""

    final_text: str
    verification_outcome: str
    turn_id: str | None = None
    outbound_message_id: str | None = None


class _ProviderAcceptanceEvidenceMissing(RuntimeError):
    """A send returned, but no durable Discord message identity was exposed."""


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


def resolve_delegated_work_intent(
    *,
    task_kind: DelegatedTaskKind,
    work_intent: DelegatedWorkIntent = DEFAULT_DELEGATED_WORK_INTENT,
) -> Literal["execution", "review", "speculative"]:
    """Resolve one explicit instruction mode for every managed child launch.

    The compatibility default is deliberately conservative for analysis-shaped
    task kinds. Resident execution normally arrives as routine, mechanical,
    coding, debugging, migration, or autonomous work. Callers can explicitly
    downgrade any task to review/speculative, but no caller can omit the final
    resolved mode from the launch prompt and manifest.
    """

    if task_kind not in DELEGATED_TASK_KINDS:
        raise ValueError(
            f"task_kind must be one of {', '.join(DELEGATED_TASK_KINDS)}; got {task_kind!r}"
        )
    if work_intent not in DELEGATED_WORK_INTENTS:
        raise ValueError(
            "work_intent must be one of "
            f"{', '.join(DELEGATED_WORK_INTENTS)}; got {work_intent!r}"
        )
    if work_intent != "auto":
        return work_intent
    return "review" if task_kind in _NON_EXECUTION_TASK_KINDS else "execution"


def _delegation_delivery_instruction(
    work_intent: Literal["execution", "review", "speculative"],
) -> str:
    common = (
        "This instruction is appended by the resident launch boundary and does not expand the "
        "user's authority. Preserve the inherited immutable Discord/delegation provenance; never "
        "replace, reconstruct, or reinterpret its source envelope."
    )
    if work_intent == "execution":
        applicable = (
            "This is execution work: complete and proportionally verify the explicitly authorized "
            "implementation in an isolated worktree, then integrate it into the clearly identified "
            "target branch using the repository's non-destructive workflow. If the request is actually "
            "tentative/speculative, the target is materially ambiguous, or authorization does not cover "
            "an effect, keep the work isolated and report the exact gate instead. A local implementation "
            "does not authorize push, remote merge, deployment, restart, destructive cleanup, credential "
            "changes, or any other external effect unless the user or established policy explicitly "
            "authorizes that effect."
        )
    elif work_intent == "review":
        applicable = (
            "This is review/analysis work: inspect and verify without mutating repositories, branches, "
            "services, external systems, or user-visible state. Findings may recommend execution, but "
            "must not implement, integrate, push, deploy, restart, or otherwise perform it unless a newer "
            "authorized instruction explicitly changes the task."
        )
    else:
        applicable = (
            "This is speculative/tentative work: do not integrate or perform external effects. Prefer "
            "read-only analysis; when a prototype is necessary, keep it on an isolated disposable branch, "
            "label it unintegrated, and report the target or authorization decision needed before delivery."
        )
    return (
        f"{DELEGATION_DELIVERY_INSTRUCTION_HEADER}\n"
        f"- schema: {DELEGATION_DELIVERY_INSTRUCTION_SCHEMA}\n"
        f"- resolved work intent: {work_intent}\n"
        f"{applicable} {common}"
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def concise_agent_description(description: object, task: str) -> str:
    """Return one durable human-readable launch line.

    Callers should supply the purpose-built description. The deterministic
    fallback keeps legacy/direct callers compatible while ensuring every new
    manifest still has a useful description.
    """

    if isinstance(description, str):
        supplied = " ".join(redact_text(description).split())
        if len(supplied) > MAX_AGENT_DESCRIPTION_CHARS:
            raise ValueError(
                f"agent description exceeds {MAX_AGENT_DESCRIPTION_CHARS} characters"
            )
        if supplied:
            return supplied.rstrip(".") + "."
    # Compatibility callers may predate semantic descriptions.  Never turn a
    # truncated raw task into a fake summary; use an explicit generic fallback.
    return "Handle the delegated resident request."


def _request_ref(
    relationship: Mapping[str, Any] | None, key: str
) -> Mapping[str, Any] | None:
    value = relationship.get(key) if isinstance(relationship, Mapping) else None
    return value if isinstance(value, Mapping) else None


def _aggregation_key(
    provenance: Mapping[str, Any],
    *,
    synthesis_group: str | None,
    task_digest: str,
    description: str,
    request_id: str | None,
) -> str:
    current_source = str(
        provenance.get("source_record_id")
        or provenance.get("custody_id")
        or "not-applicable"
    )
    if synthesis_group:
        return stable_identity(
            "resident-synthesis-group",
            provenance.get("resident_conversation_id") or "not-applicable",
            current_source,
            synthesis_group,
        )
    return stable_identity(
        "resident-single-delivery",
        provenance.get("resident_conversation_id") or "not-applicable",
        current_source,
        task_digest,
        description,
        request_id or "",
    )


def _render_query_relationship(relationship: Mapping[str, Any] | None) -> str:
    if not isinstance(relationship, Mapping):
        return ""
    root = _request_ref(relationship, "root_request") or {}
    current = _request_ref(relationship, "current_request") or {}
    earlier = _request_ref(relationship, "earlier_request") or {}
    return (
        "[Query relationship and delivery ownership]\n"
        f"- classification: {relationship.get('classification') or 'independent'}\n"
        f"- root request source/message: {root.get('source_record_id') or 'n/a'} / "
        f"{root.get('discord_message_id') or 'n/a'}\n"
        f"- root semantic description: {root.get('description') or 'unavailable'}\n"
        f"- earlier request source/message: {earlier.get('source_record_id') or 'n/a'} / "
        f"{earlier.get('discord_message_id') or 'n/a'}\n"
        f"- current follow-up source/message: {current.get('source_record_id') or 'n/a'} / "
        f"{current.get('discord_message_id') or 'n/a'}\n"
        f"- current semantic description: {current.get('description') or 'unavailable'}\n"
        "The current/newer request is the sole delivery and aggregation target. Consolidate relevant "
        "earlier work into one reply; internal reviewers report through the synthesis owner and must "
        "not emit independent user-facing completions.\n"
    )


def _delivery_transition_now(fixed_now: datetime | None) -> datetime:
    """Timestamp a state transition, or preserve an injected deterministic clock."""

    return fixed_now or datetime.now(timezone.utc)


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _git_revision_without_process(root: Path) -> str | None:
    """Resolve HEAD without spawning git in the latency-sensitive launch path."""

    git_path = root / ".git"
    try:
        if git_path.is_file():
            marker = git_path.read_text(encoding="utf-8").strip()
            if not marker.startswith("gitdir:"):
                return None
            git_dir = Path(marker.split(":", 1)[1].strip())
            if not git_dir.is_absolute():
                git_dir = (root / git_dir).resolve()
        else:
            git_dir = git_path
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        if re.fullmatch(r"[0-9a-fA-F]{40}", head):
            return head.lower()
        if not head.startswith("ref:"):
            return None
        ref = head.split(":", 1)[1].strip()
        candidates = [git_dir / ref]
        commondir_path = git_dir / "commondir"
        if commondir_path.is_file():
            common = Path(commondir_path.read_text(encoding="utf-8").strip())
            if not common.is_absolute():
                common = (git_dir / common).resolve()
            candidates.append(common / ref)
        for candidate in candidates:
            if candidate.is_file():
                revision = candidate.read_text(encoding="utf-8").strip()
                if re.fullmatch(r"[0-9a-fA-F]{40}", revision):
                    return revision.lower()
    except OSError:
        return None
    return None


def _delegated_context_directory(
    *,
    project_root: Path,
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    runtime_root = Path(__file__).resolve().parents[3]
    conversation_id = (
        str(provenance.get("resident_conversation_id") or "") or None
        if provenance.get("applicability") == "applicable"
        else None
    )
    store_root = str(os.environ.get("MEGAPLAN_RESIDENT_STORE_ROOT") or "").strip() or None
    base = "python -P -m arnold_pipelines.megaplan resident"
    store_arg = ' --store-root "$MEGAPLAN_RESIDENT_STORE_ROOT"' if store_root else ""
    return {
        "project_worktree": str(project_root),
        "resident_runtime_source": str(runtime_root),
        "resident_runtime_revision": _git_revision_without_process(runtime_root),
        "project_equals_runtime_source": project_root == runtime_root,
        "resident_conversation_id": conversation_id,
        "routes": {
            "context_root": f"{base} context --node root{store_arg}",
            "targeted_context": f"{base} context --node '<node_id>'{store_arg}",
            "context_search": (
                f"{base} context-search --scope '<scope>' --query '<query>'{store_arg}"
            ),
            "reply_ancestry": f"{base} read-reply-chain --cursor '<cursor>'{store_arg}",
        },
    }


def _render_delegated_context_directory(directory: Mapping[str, Any]) -> str:
    routes = directory.get("routes") if isinstance(directory.get("routes"), Mapping) else {}
    return (
        "[Delegated context directory]\n"
        "The full resident/cloud/conversation state is deliberately not embedded. Use these bounded "
        "routes only when the task needs more evidence.\n"
        f"- project worktree: {directory.get('project_worktree')}\n"
        f"- resident runtime source: {directory.get('resident_runtime_source')}\n"
        f"- resident runtime revision: {directory.get('resident_runtime_revision') or 'unknown'}\n"
        f"- project is runtime source: {directory.get('project_equals_runtime_source')}\n"
        f"- resident conversation: {directory.get('resident_conversation_id') or 'not applicable'}\n"
        f"- context root: {routes.get('context_root')}\n"
        f"- targeted node: {routes.get('targeted_context')}\n"
        f"- scoped search: {routes.get('context_search')}\n"
        f"- older reply ancestry: {routes.get('reply_ancestry')}\n"
        "The immutable Discord source envelope is inherited in the process environment. Never replace "
        "it with a recent-message guess. The project worktree may differ from the pinned resident runtime; "
        "inspect both before resident-code changes, preserve concurrent dirty work, and publish/deploy only "
        "after explicit tree/revision reconciliation.\n"
    )


def _delivery_prompt(
    task: str,
    timezone_name: str = "UTC",
    *,
    task_kind: DelegatedTaskKind = DEFAULT_DELEGATED_TASK_KIND,
    work_intent: DelegatedWorkIntent = DEFAULT_DELEGATED_WORK_INTENT,
    context_directory: Mapping[str, Any] | None = None,
    query_relationship: Mapping[str, Any] | None = None,
    contributors: list[Mapping[str, Any]] | None = None,
    git_custody: Mapping[str, Any] | None = None,
) -> str:
    if DELEGATION_DELIVERY_INSTRUCTION_HEADER in task:
        raise ValueError(
            "delegated task contains the reserved resident delivery instruction marker"
        )
    resolved_work_intent = resolve_delegated_work_intent(
        task_kind=task_kind,
        work_intent=work_intent,
    )
    delivery_instruction = _delegation_delivery_instruction(resolved_work_intent)
    prompt = (
        f"{task.rstrip()}\n\n"
        f"{delivery_instruction}\n\n"
        "[Completion delivery contract]\n"
        "[User-time presentation rule]\n"
        f"Render absolute user-visible times in {timezone_name} with local date/time, timezone "
        "abbreviation, and numeric UTC offset. Keep stored/control-plane/evidence timestamps in "
        "UTC and keep relative durations relative.\n\n"
    )
    if context_directory is not None:
        prompt += _render_delegated_context_directory(context_directory) + "\n"
    if resolved_work_intent == "execution" and git_custody is not None:
        prompt += render_git_custody_contract(git_custody) + "\n"
    relationship_context = _render_query_relationship(query_relationship)
    if relationship_context:
        prompt += relationship_context + "\n"
    if contributors:
        prompt += (
            "[Internal contributor evidence to synthesize]\n"
            + json.dumps(contributors, sort_keys=True)
            + "\nWait for every listed contributor manifest to become terminal, then read and "
            "consolidate its durable result. They are evidence inputs, not independent "
            "user-facing delivery owners.\n\n"
        )
    prompt += f"{FINAL_SUMMARY_INSTRUCTION}\n"
    if len(prompt) > MAX_DELEGATED_PROMPT_CHARS:
        raise ValueError(
            f"delegated prompt exceeds {MAX_DELEGATED_PROMPT_CHARS} characters; "
            "put large evidence in durable files and provide bounded routes"
        )
    return prompt


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
        description=str(payload.get("description") or "") or None,
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


def _manifest_aggregation_key(payload: Mapping[str, Any]) -> str | None:
    aggregation = payload.get("aggregation")
    if isinstance(aggregation, Mapping) and aggregation.get("key"):
        return str(aggregation["key"])
    # Legacy manifests did not declare an explicit synthesis group.  Never
    # retroactively collapse them merely because they share a request root.
    return None


def _transfer_aggregation_delivery_ownership(
    root: Path,
    *,
    aggregation_key: str,
    new_owner_run_id: str,
    at: str,
) -> None:
    """Make one newest run the synthesis/delivery owner for a logical query."""

    for path in root.glob("*/manifest.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            continue
        if not isinstance(payload, dict) or not _is_managed_manifest(payload):
            continue
        if _manifest_aggregation_key(payload) != aggregation_key:
            continue
        prior_run_id = str(payload.get("run_id") or path.parent.name)
        aggregation = dict(payload.get("aggregation") or {})
        aggregation.update(
            {
                "schema_version": AGGREGATION_SCHEMA,
                "key": aggregation_key,
                "role": "internal_contributor",
                "delivery_owner_run_id": new_owner_run_id,
                "superseded_at": at,
            }
        )
        payload["aggregation"] = aggregation
        delivery = payload.get("completion_delivery")
        if isinstance(delivery, dict) and delivery.get("status") not in {
            "delivered",
            "failed",
            "not_applicable",
            "superseded",
            "suppressed",
            "unknown",
        }:
            delivery.update(
                {
                    "status": "superseded",
                    "superseded_at": at,
                    "superseded_by_run_id": new_owner_run_id,
                    "superseded_reason": "new_synthesis_delivery_owner_for_logical_request",
                    "updated_at": at,
                }
            )
            history = list(delivery.get("state_history") or [])
            history.append(
                {
                    "status": "superseded",
                    "at": at,
                    "evidence": "single_logical_request_delivery_owner_transferred",
                    "delivery_owner_run_id": new_owner_run_id,
                }
            )
            delivery["state_history"] = history[-20:]
            payload["completion_delivery"] = delivery
        _atomic_json(path, payload)


def _aggregation_contributor_refs(
    root: Path, *, aggregation_key: str
) -> list[dict[str, Any]]:
    """Return bounded durable inputs that the synthesis owner must consume."""

    contributors: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/manifest.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            continue
        if (
            not isinstance(payload, dict)
            or not _is_managed_manifest(payload)
            or _manifest_aggregation_key(payload) != aggregation_key
        ):
            continue
        result_path = Path(str(payload.get("result_path") or "result.md"))
        if not result_path.is_absolute():
            result_path = path.parent / result_path
        contributors.append(
            {
                "run_id": str(payload.get("run_id") or path.parent.name),
                "description": str(payload.get("description") or ""),
                "status": str(payload.get("status") or "unknown"),
                "aggregation_role": str(
                    (payload.get("aggregation") or {}).get("role") or "unknown"
                ),
                "delivery_status": str(
                    (payload.get("completion_delivery") or {}).get("status")
                    or "not_applicable"
                ),
                "manifest_path": str(path.resolve()),
                "result_path": str(result_path.resolve()),
            }
        )
    return contributors[-20:]


def _read_managed_resident_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise SubagentFollowupError(f"cannot read managed run manifest: {path}") from exc
    if not isinstance(payload, dict) or not _is_managed_manifest(payload):
        raise SubagentFollowupError(f"target is not a resident-managed agent run: {path}")
    run_id = str(payload.get("run_id") or path.parent.name)
    if run_id != path.parent.name:
        raise SubagentFollowupError("managed run manifest identity does not match its directory")
    return payload


def _queue_artifact_path(
    manifest_path: Path,
    manifest: Mapping[str, Any],
    field: str,
    fallback: str,
) -> Path:
    raw = Path(str(manifest.get(field) or fallback))
    resolved = raw.resolve() if raw.is_absolute() else (manifest_path.parent / raw).resolve()
    try:
        resolved.relative_to(manifest_path.parent.resolve())
    except ValueError as exc:
        raise SubagentQueueError(
            f"predecessor {field} escapes its managed run directory"
        ) from exc
    if len(str(resolved)) > 4096:
        raise SubagentQueueError(f"predecessor {field} reference is too long")
    return resolved


def _queue_predecessor_references(
    manifest_path: Path, manifest: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Return typed, path-only predecessor references; never inline artifact bytes."""

    run_id = str(manifest.get("run_id") or manifest_path.parent.name)
    refs = []
    for artifact_type, field, fallback in (
        ("manifest", "manifest_path", "manifest.json"),
        ("result", "result_path", "result.md"),
        ("log", "full_log_path", str(manifest.get("log_path") or "run.log")),
    ):
        path = _queue_artifact_path(manifest_path, manifest, field, fallback)
        refs.append(
            {
                "schema_version": QUEUE_REFERENCE_SCHEMA,
                "run_id": run_id,
                "artifact_type": artifact_type,
                "path": str(path),
                "content_inlined": False,
            }
        )
    return refs


def _render_queue_references(
    *, predecessor_run_id: str, references: list[dict[str, Any]]
) -> str:
    lines = [
        "[Queued predecessor references — bounded typed refs only]",
        f"- schema: {QUEUE_REFERENCE_SCHEMA}",
        f"- predecessor_run_id: {predecessor_run_id}",
        "- instruction: inspect only the artifacts needed for the authored prompt; full content is not embedded",
    ]
    for ref in references:
        lines.append(f"- {ref['artifact_type']}: {ref['path']}")
    return "\n".join(lines)


def _queue_provenance_identity(value: Mapping[str, Any]) -> tuple[object, ...]:
    return tuple(
        value.get(field)
        for field in (
            "applicability",
            "transport",
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
        )
    )


def _queue_mapping_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(dict(value), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _queue_store_root(project_root: Path) -> Path:
    configured = str(os.environ.get("MEGAPLAN_RESIDENT_STORE_ROOT") or "").strip()
    return (
        Path(configured).resolve()
        if configured
        else project_root / ".megaplan" / "resident"
    )


def _authoritative_queue_request(
    project_root: Path, provenance: Mapping[str, Any]
) -> dict[str, str]:
    """Resolve one Discord envelope against its immutable inbound record."""

    normalized = normalize_delegation_provenance(provenance)
    if normalized.get("applicability") != "applicable":
        raise SubagentQueueError(
            "cross-request queue authorization requires Discord provenance"
        )
    source_record_id = str(normalized.get("source_record_id") or "")
    conversation_id = str(normalized.get("resident_conversation_id") or "")
    if not _RESIDENT_MESSAGE_ID_RE.fullmatch(source_record_id):
        raise SubagentQueueError(
            "cross-request queue authorization source record is malformed"
        )
    store_root = _queue_store_root(project_root)
    message_path = store_root / "messages" / f"{source_record_id}.json"
    try:
        raw = message_path.read_bytes()
        message = json.loads(raw)
    except (OSError, TypeError, ValueError) as exc:
        raise SubagentQueueError(
            "cross-request queue authorization source record is unavailable"
        ) from exc
    reply = message.get("discord_reply_provenance") if isinstance(message, dict) else None
    scope = reply.get("scope") if isinstance(reply, Mapping) else None
    author_id = str(reply.get("source_author_id") or "") if isinstance(reply, Mapping) else ""
    if (
        not isinstance(message, dict)
        or message.get("id") != source_record_id
        or message.get("direction") != "inbound"
        or message.get("conversation_id") != conversation_id
        or str(message.get("discord_message_id") or "")
        != str(normalized.get("discord_message_id") or "")
        or not isinstance(reply, Mapping)
        or reply.get("transport") != "discord"
        or str(reply.get("source_message_id") or "")
        != str(normalized.get("discord_message_id") or "")
        or str(reply.get("conversation_key") or "")
        != str(normalized.get("conversation_key") or "")
        or not _is_discord_snowflake(author_id)
        or not isinstance(scope, Mapping)
        or str(scope.get("channel_id") or "")
        != str(normalized.get("channel_id") or "")
        or str(scope.get("dm_user_id") or "")
        != str(normalized.get("dm_user_id") or "")
    ):
        raise SubagentQueueError(
            "cross-request queue authorization source record conflicts with provenance"
        )
    conversation_path = store_root / "resident_conversations" / f"{conversation_id}.json"
    try:
        conversation = json.loads(conversation_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise SubagentQueueError(
            "cross-request queue authorization conversation is unavailable"
        ) from exc
    if (
        not isinstance(conversation, dict)
        or conversation.get("id") != conversation_id
        or conversation.get("transport") != "discord"
        or conversation.get("conversation_key") != normalized.get("conversation_key")
    ):
        raise SubagentQueueError(
            "cross-request queue authorization conversation conflicts with provenance"
        )
    return {
        "source_record_id": source_record_id,
        "record_sha256": hashlib.sha256(raw).hexdigest(),
        "subject_sha256": hashlib.sha256(
            f"discord-subject\0{author_id}".encode("utf-8")
        ).hexdigest(),
    }


def _cross_request_queue_authorization(
    root: Path,
    *,
    project_root: Path,
    predecessor_run_id: str,
    predecessor: Mapping[str, Any],
    current_provenance: Mapping[str, Any],
    require_active_caller: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Bind one exact dependency to a later same-subject request, fail closed."""

    predecessor_provenance = predecessor.get("launch_provenance")
    if not isinstance(predecessor_provenance, Mapping):
        raise SubagentQueueError("predecessor lacks immutable launch provenance")
    predecessor_provenance = normalize_delegation_provenance(predecessor_provenance)
    if (
        predecessor_provenance.get("applicability") != "applicable"
        or current_provenance.get("applicability") != "applicable"
    ):
        raise SubagentQueueError(
            "cross-request queue authorization requires two Discord envelopes"
        )
    if predecessor_provenance.get("resident_conversation_id") != current_provenance.get(
        "resident_conversation_id"
    ):
        raise SubagentQueueError(
            "cross-request queue authorization changed resident conversation"
        )
    current_request = _authoritative_queue_request(project_root, current_provenance)
    predecessor_request = _authoritative_queue_request(
        project_root, predecessor_provenance
    )
    if current_request["subject_sha256"] != predecessor_request["subject_sha256"]:
        raise SubagentQueueError(
            "cross-request queue authorization changed Discord subject"
        )

    caller_run_id = str(current_provenance.get("root_run_id") or "")
    if not _RUN_ID_RE.fullmatch(caller_run_id):
        return _resident_turn_queue_authorization(
            project_root=project_root,
            predecessor_run_id=predecessor_run_id,
            predecessor=predecessor,
            predecessor_provenance=predecessor_provenance,
            current_provenance=current_provenance,
            current_request=current_request,
            predecessor_request=predecessor_request,
            require_active_caller=require_active_caller,
        )
    caller_path = root / caller_run_id / "manifest.json"
    try:
        caller = _read_managed_resident_manifest(caller_path)
    except SubagentFollowupError as exc:
        raise SubagentQueueError(
            "cross-request queue authorization caller manifest is unavailable"
        ) from exc
    if require_active_caller and str(caller.get("status") or "") not in {
        "launching",
        "running",
    }:
        raise SubagentQueueError(
            "cross-request queue authorization caller is not active"
        )
    caller_provenance = caller.get("launch_provenance")
    if (
        not isinstance(caller_provenance, Mapping)
        or _queue_provenance_identity(
            normalize_delegation_provenance(caller_provenance)
        )
        != _queue_provenance_identity(current_provenance)
        or Path(str(caller.get("project_dir") or "")).resolve() != project_root
    ):
        raise SubagentQueueError(
            "cross-request queue authorization caller does not own current custody"
        )
    if caller.get("work_intent") != predecessor.get("work_intent"):
        raise SubagentQueueError(
            "cross-request queue authorization cannot broaden work intent"
        )
    prompt_path = Path(str(caller.get("prompt_path") or ""))
    if prompt_path.parent.resolve() != caller_path.parent.resolve():
        raise SubagentQueueError(
            "cross-request queue authorization caller prompt path is invalid"
        )
    try:
        caller_prompt = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SubagentQueueError(
            "cross-request queue authorization caller prompt is unavailable"
        ) from exc
    caller_prompt_sha256 = hashlib.sha256(caller_prompt.encode("utf-8")).hexdigest()
    if (
        caller_prompt_sha256 != caller.get("prompt_sha256")
        or re.search(
            rf"(?<![A-Za-z0-9]){re.escape(predecessor_run_id)}(?![A-Za-z0-9])",
            caller_prompt,
        )
        is None
    ):
        raise SubagentQueueError(
            "cross-request queue authorization does not explicitly name predecessor"
        )

    relationship = caller.get("query_relationship")
    current_source = str(current_provenance.get("source_record_id") or "")
    if not isinstance(relationship, Mapping):
        raise SubagentQueueError(
            "cross-request queue authorization lacks current query relationship"
        )
    for field in ("current_request", "delivery_owner", "aggregation_owner"):
        ref = relationship.get(field)
        if not isinstance(ref, Mapping) or ref.get("source_record_id") != current_source:
            raise SubagentQueueError(
                "cross-request queue authorization changed current delivery ownership"
            )
    if relationship.get("conversation_id") != current_provenance.get(
        "resident_conversation_id"
    ):
        raise SubagentQueueError(
            "cross-request queue authorization relationship changed conversation"
        )
    aggregation = caller.get("aggregation")
    delivery = caller.get("completion_delivery")
    reply_target = delivery.get("reply_target") if isinstance(delivery, Mapping) else None
    if (
        not isinstance(aggregation, Mapping)
        or aggregation.get("role") != "internal_contributor"
        or not aggregation.get("key")
        or not aggregation.get("synthesis_group")
        or aggregation.get("delivery_target_source_record_id") != current_source
        or not isinstance(delivery, Mapping)
        or delivery.get("status") not in {"suppressed", "superseded"}
        or not isinstance(reply_target, Mapping)
        or reply_target.get("source_record_id") != current_source
    ):
        raise SubagentQueueError(
            "cross-request queue authorization lacks conflict-free aggregation custody"
        )

    authorization = {
        "schema_version": QUEUE_CROSS_REQUEST_AUTHORIZATION_SCHEMA,
        "mode": "same_subject_same_conversation_explicit_predecessor",
        "predecessor_run_id": predecessor_run_id,
        "resident_conversation_id": current_provenance.get(
            "resident_conversation_id"
        ),
        "subject_sha256": current_request["subject_sha256"],
        "current_source_record_id": current_source,
        "current_source_record_sha256": current_request["record_sha256"],
        "predecessor_source_record_id": predecessor_request["source_record_id"],
        "predecessor_source_record_sha256": predecessor_request["record_sha256"],
        "caller_run_id": caller_run_id,
        "caller_task_sha256": caller.get("task_sha256"),
        "caller_prompt_sha256": caller_prompt_sha256,
        "caller_provenance_sha256": _queue_mapping_digest(current_provenance),
        "predecessor_provenance_sha256": _queue_mapping_digest(
            predecessor_provenance
        ),
        "query_relationship_sha256": _queue_mapping_digest(relationship),
        "aggregation_key": aggregation.get("key"),
        "synthesis_group": aggregation.get("synthesis_group"),
        "delivery_target_source_record_id": current_source,
    }
    return authorization, dict(aggregation), dict(relationship)


def _resident_turn_queue_authorization(
    *,
    project_root: Path,
    predecessor_run_id: str,
    predecessor: Mapping[str, Any],
    predecessor_provenance: Mapping[str, Any],
    current_provenance: Mapping[str, Any],
    current_request: Mapping[str, str],
    predecessor_request: Mapping[str, str],
    require_active_caller: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Authorize a cross-request queue from its durable resident root turn.

    Root Discord turns are not managed subagents and therefore never have a
    ``root_run_id``.  Their immutable launch envelope does carry the resident
    turn id committed before tool execution.  Validate that turn and its exact
    inbound message rather than requiring an impossible subagent manifest.
    """

    turn_id = str(current_provenance.get("resident_turn_id") or "")
    if not _RESIDENT_TURN_ID_RE.fullmatch(turn_id):
        raise SubagentQueueError(
            "cross-request queue authorization lacks immutable caller root_run_id "
            "or resident_turn_id"
        )
    store_root = _queue_store_root(project_root)
    turn_path = store_root / "turns" / f"{turn_id}.json"
    try:
        turn_raw = turn_path.read_bytes()
        turn = json.loads(turn_raw)
    except (OSError, TypeError, ValueError) as exc:
        raise SubagentQueueError(
            "cross-request queue authorization caller turn is unavailable"
        ) from exc
    current_source = str(current_provenance.get("source_record_id") or "")
    triggered = turn.get("triggered_by_message_ids") if isinstance(turn, Mapping) else None
    if (
        not isinstance(turn, Mapping)
        or turn.get("id") != turn_id
        or not isinstance(triggered, list)
        or triggered != [current_source]
    ):
        raise SubagentQueueError(
            "cross-request queue authorization caller turn does not own current custody"
        )
    if require_active_caller and str(turn.get("status") or "") not in {
        "in_progress",
        "running",
    }:
        raise SubagentQueueError(
            "cross-request queue authorization caller turn is not active"
        )

    message_path = store_root / "messages" / f"{current_source}.json"
    try:
        message = json.loads(message_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise SubagentQueueError(
            "cross-request queue authorization source record is unavailable"
        ) from exc
    reply = message.get("discord_reply_provenance") if isinstance(message, Mapping) else None
    ancestors = reply.get("ancestors") if isinstance(reply, Mapping) else None
    reference_text = "\n".join(
        [str(message.get("content") or "")]
        + [
            str(row.get("content") or "")
            for row in (ancestors or [])
            if isinstance(row, Mapping) and row.get("status") == "available"
        ]
    )
    if re.search(
        rf"(?<![A-Za-z0-9]){re.escape(predecessor_run_id)}(?![A-Za-z0-9])",
        reference_text,
    ) is None:
        raise SubagentQueueError(
            "cross-request queue authorization does not explicitly name predecessor"
        )

    relationship = relationship_from_environment_or_project(
        current_source, project_root=project_root
    )
    if not isinstance(relationship, Mapping):
        raise SubagentQueueError(
            "cross-request queue authorization lacks current query relationship"
        )
    for field in ("current_request", "delivery_owner", "aggregation_owner"):
        ref = relationship.get(field)
        if not isinstance(ref, Mapping) or ref.get("source_record_id") != current_source:
            raise SubagentQueueError(
                "cross-request queue authorization changed current delivery ownership"
            )
    if relationship.get("conversation_id") != current_provenance.get(
        "resident_conversation_id"
    ):
        raise SubagentQueueError(
            "cross-request queue authorization relationship changed conversation"
        )
    if predecessor.get("work_intent") not in DELEGATED_WORK_INTENTS:
        raise SubagentQueueError(
            "cross-request queue authorization predecessor work intent is invalid"
        )

    aggregation_key = stable_identity(
        "resident-root-turn-successor", current_source, predecessor_run_id
    )
    synthesis_group = stable_identity(
        "resident-root-turn-synthesis", turn_id, predecessor_run_id
    )
    aggregation = {
        "schema_version": AGGREGATION_SCHEMA,
        "key": aggregation_key,
        "synthesis_group": synthesis_group,
        "role": "internal_contributor",
        "delivery_owner_run_id": None,
        "delivery_target_source_record_id": current_source,
        "contributors": [],
    }
    turn_authority = {
        "id": turn.get("id"),
        "triggered_by_message_ids": list(triggered),
        "prompt_snapshot": turn.get("prompt_snapshot"),
        "started_at": turn.get("started_at"),
    }
    authorization = {
        "schema_version": QUEUE_CROSS_REQUEST_AUTHORIZATION_SCHEMA,
        "mode": "same_subject_same_conversation_explicit_predecessor",
        "authorization_source": "resident_root_turn",
        "predecessor_run_id": predecessor_run_id,
        "resident_conversation_id": current_provenance.get(
            "resident_conversation_id"
        ),
        "subject_sha256": current_request["subject_sha256"],
        "current_source_record_id": current_source,
        "current_source_record_sha256": current_request["record_sha256"],
        "predecessor_source_record_id": predecessor_request["source_record_id"],
        "predecessor_source_record_sha256": predecessor_request["record_sha256"],
        "caller_turn_id": turn_id,
        "caller_turn_authority_sha256": _queue_mapping_digest(turn_authority),
        "caller_provenance_sha256": _queue_mapping_digest(current_provenance),
        "predecessor_provenance_sha256": _queue_mapping_digest(
            predecessor_provenance
        ),
        "query_relationship_sha256": _queue_mapping_digest(relationship),
        "aggregation_key": aggregation_key,
        "synthesis_group": synthesis_group,
        "delivery_target_source_record_id": current_source,
    }
    return authorization, aggregation, dict(relationship)


def _queue_has_conflicting_delivered_owner(
    root: Path, *, aggregation_key: str, successor_run_id: str
) -> bool:
    for path in root.glob("*/manifest.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            continue
        if str(row.get("run_id") or path.parent.name) == successor_run_id:
            continue
        if _manifest_aggregation_key(row) != aggregation_key:
            continue
        aggregation = row.get("aggregation")
        delivery = row.get("completion_delivery")
        if (
            isinstance(aggregation, Mapping)
            and aggregation.get("role") == "synthesis_delivery_owner"
            and isinstance(delivery, Mapping)
            and delivery.get("status") == "delivered"
        ):
            return True
    return False


def _queue_ancestor_ids(root: Path, predecessor_run_id: str) -> list[str]:
    """Walk immutable predecessor links and fail closed on cycles or excessive depth."""

    ancestors: list[str] = []
    seen: set[str] = set()
    current = predecessor_run_id
    while current:
        if current in seen:
            raise SubagentQueueError(f"queued dependency cycle detected at {current}")
        if len(ancestors) >= MAX_QUEUE_CHAIN_DEPTH:
            raise SubagentQueueError(
                f"queued dependency depth exceeds {MAX_QUEUE_CHAIN_DEPTH}"
            )
        seen.add(current)
        ancestors.append(current)
        path = root / current / "manifest.json"
        if not path.is_file():
            raise SubagentQueueError(f"queued predecessor manifest is missing: {current}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError) as exc:
            raise SubagentQueueError(
                f"queued predecessor manifest is unreadable: {current}"
            ) from exc
        queue = payload.get("queue")
        current = (
            str(queue.get("predecessor_run_id") or "")
            if isinstance(queue, Mapping)
            else ""
        )
    return ancestors


def _validate_queue_authorization(
    predecessor: Mapping[str, Any], successor: Mapping[str, Any], *, manifest_path: Path
) -> None:
    predecessor_provenance = predecessor.get("launch_provenance")
    successor_provenance = successor.get("launch_provenance")
    if not isinstance(predecessor_provenance, Mapping) or not isinstance(
        successor_provenance, Mapping
    ):
        raise SubagentQueueError("queued dependency lacks immutable launch provenance")
    same_request = _queue_provenance_identity(
        predecessor_provenance
    ) == _queue_provenance_identity(successor_provenance)
    for field in ("project_dir", "work_intent"):
        if predecessor.get(field) != successor.get(field):
            raise SubagentQueueError(
                f"queued successor cannot broaden predecessor {field} authorization"
            )
    predecessor_aggregation = predecessor.get("aggregation")
    successor_aggregation = successor.get("aggregation")
    if not isinstance(predecessor_aggregation, Mapping) or not isinstance(
        successor_aggregation, Mapping
    ):
        raise SubagentQueueError("queued dependency lacks aggregation custody")
    if successor_aggregation.get("role") != "synthesis_delivery_owner":
        raise SubagentQueueError("queued successor must be the sole synthesis delivery owner")
    if same_request:
        if predecessor_aggregation.get("key") != successor_aggregation.get("key"):
            raise SubagentQueueError("queued successor changed logical delivery ownership")
        return
    queue = successor.get("queue")
    authorization = (
        queue.get("cross_request_authorization") if isinstance(queue, Mapping) else None
    )
    if not isinstance(authorization, Mapping):
        raise SubagentQueueError("queued successor provenance differs from predecessor")
    recomputed, aggregation, relationship = _cross_request_queue_authorization(
        manifest_path.parent.parent,
        project_root=Path(str(successor.get("project_dir") or "")).resolve(),
        predecessor_run_id=str(queue.get("predecessor_run_id") or ""),
        predecessor=predecessor,
        current_provenance=normalize_delegation_provenance(successor_provenance),
        require_active_caller=False,
    )
    if dict(authorization) != recomputed:
        raise SubagentQueueError("cross-request queue authorization evidence changed")
    if (
        successor.get("query_relationship") != relationship
        or successor_aggregation.get("key") != aggregation.get("key")
        or successor_aggregation.get("synthesis_group")
        != aggregation.get("synthesis_group")
        or successor_aggregation.get("delivery_target_source_record_id")
        != successor_provenance.get("source_record_id")
    ):
        raise SubagentQueueError(
            "cross-request queued successor changed current aggregation custody"
        )
    delivery = successor.get("completion_delivery")
    reply_target = delivery.get("reply_target") if isinstance(delivery, Mapping) else None
    if (
        not isinstance(reply_target, Mapping)
        or reply_target.get("source_record_id") != successor_provenance.get("source_record_id")
        or _queue_has_conflicting_delivered_owner(
            manifest_path.parent.parent,
            aggregation_key=str(successor_aggregation.get("key") or ""),
            successor_run_id=str(successor.get("run_id") or manifest_path.parent.name),
        )
    ):
        raise SubagentQueueError(
            "cross-request queued successor has a delivery ownership conflict"
        )


def _recover_idempotent_cross_request_queue(
    manifest_path: Path, manifest: dict[str, Any]
) -> dict[str, Any]:
    """Requeue one zero-attempt false terminal after its contract validates again."""

    queue = manifest.get("queue")
    delivery = manifest.get("completion_delivery")
    if (
        manifest.get("status") != "failed"
        or not isinstance(queue, dict)
        or queue.get("attention") != "invalid_dependency_contract"
        or int(queue.get("attempt_count") or 0) != 0
        or not isinstance(queue.get("cross_request_authorization"), Mapping)
        or not isinstance(delivery, Mapping)
        or delivery.get("status") != "pending"
    ):
        return manifest
    predecessor_run_id = str(queue.get("predecessor_run_id") or "")
    predecessor_path = manifest_path.parent.parent / predecessor_run_id / "manifest.json"
    try:
        predecessor = _read_managed_resident_manifest(predecessor_path)
        ancestors = _queue_ancestor_ids(
            manifest_path.parent.parent, predecessor_run_id
        )
        if queue.get("ancestor_run_ids") != ancestors:
            raise SubagentQueueError("queued dependency ancestry changed after commit")
        if queue.get("trigger_policy") != QUEUE_TRIGGER_POLICY:
            raise SubagentQueueError("queued trigger policy is unsupported")
        if queue.get("predecessor_references") != _queue_predecessor_references(
            predecessor_path, predecessor
        ):
            raise SubagentQueueError("queued predecessor references changed after commit")
        _validate_queue_authorization(
            predecessor, manifest, manifest_path=manifest_path
        )
    except (SubagentFollowupError, SubagentQueueError, OSError, ValueError):
        return manifest

    recovered_at = _utc_now()
    for field in ("failed_at", "last_validation_error"):
        queue.pop(field, None)
    queue.update(
        {
            "state": "waiting_predecessor",
            "attention": "waiting_for_predecessor",
            "predecessor_status": str(predecessor.get("status") or "unknown"),
            "recovered_at": recovered_at,
            "recovery_reason": "idempotent_replay_revalidated_dependency_contract",
            "updated_at": recovered_at,
        }
    )
    for field in (
        "terminal_outcome",
        "finished_at",
        "error",
        "error_class",
    ):
        manifest.pop(field, None)
    manifest.update(
        {
            "status": "queued",
            "queue": queue,
            "updated_at": recovered_at,
        }
    )
    history = list(manifest.get("status_history") or [])
    history.append(
        {
            "status": "queued",
            "at": recovered_at,
            "evidence": "idempotent_replay_revalidated_dependency_contract",
        }
    )
    manifest["status_history"] = history[-100:]
    _atomic_json(manifest_path, manifest)
    return manifest


def _queue_result_is_valid(
    predecessor_path: Path, predecessor: Mapping[str, Any]
) -> tuple[bool, str | None]:
    if predecessor.get("status") != "completed":
        return False, "predecessor_not_completed"
    if predecessor.get("terminal_outcome") not in {None, "completed"}:
        return False, "predecessor_terminal_outcome_invalid"
    if int(predecessor.get("returncode") or 0) != 0:
        return False, "predecessor_returncode_nonzero"
    try:
        result_path = _queue_artifact_path(
            predecessor_path, predecessor, "result_path", "result.md"
        )
        stat = result_path.stat()
    except (OSError, SubagentQueueError):
        return False, "predecessor_result_missing"
    if not result_path.is_file() or stat.st_size <= 0:
        return False, "predecessor_result_empty_or_invalid"
    return True, None


def _find_managed_run(
    run_id: str,
    *,
    project_root: Path,
    workspace_root: str | Path | None,
) -> tuple[Path, dict[str, Any], tuple[Path, ...]]:
    if not _RUN_ID_RE.fullmatch(run_id):
        raise SubagentFollowupError("run_id is malformed")
    roots = tuple(
        sorted(
            _managed_run_roots(project_root=project_root, workspace_root=workspace_root),
            key=str,
        )
    )
    matches = [
        root / run_id / "manifest.json"
        for root in roots
        if (root / run_id / "manifest.json").is_file()
    ]
    if not matches:
        raise SubagentFollowupError(f"unknown resident-managed run_id: {run_id}")
    unique = {path.resolve() for path in matches}
    if len(unique) != 1:
        raise SubagentFollowupError(f"run_id has ambiguous workspace ownership: {run_id}")
    manifest_path = unique.pop()
    return manifest_path, _read_managed_resident_manifest(manifest_path), roots


def find_discord_followup_target(
    *,
    source_record_id: str,
    discord_message_id: str,
    resident_conversation_id: str,
    conversation_key: str,
    reply_received_at: datetime,
    project_root: str | Path,
    workspace_root: str | Path | None = "/workspace",
) -> DiscordFollowupTarget | None:
    """Find the sole recent lineage launched from an exact Discord message.

    The launch anchor is the managed supervisor's ``started_at`` timestamp,
    falling back to the pre-launch manifest ``created_at`` timestamp for legacy
    records.  A reply is eligible when its durable resident ``sent_at`` is on
    or after that anchor and no later than exactly 15 minutes after it.  More
    than one matching lineage, duplicated run ownership across roots, malformed
    provenance, or a non-UTC/unparseable timestamp fails closed.
    """

    received = reply_received_at
    if received.tzinfo is None:
        received = received.replace(tzinfo=timezone.utc)
    received = received.astimezone(timezone.utc)
    candidates: list[tuple[datetime, str, str, Path, str]] = []
    seen_run_paths: dict[str, Path] = {}
    for manifest_path in _managed_manifest_paths(
        project_root=project_root,
        workspace_root=workspace_root,
    ):
        try:
            manifest = _read_managed_resident_manifest(manifest_path)
            provenance = normalize_delegation_provenance(
                manifest.get("launch_provenance") or {}
            )
        except (SubagentFollowupError, DelegationProvenanceError):
            continue
        if provenance.get("applicability") != "applicable":
            continue
        if any(
            (
                provenance.get("source_record_id") != source_record_id,
                provenance.get("discord_message_id") != discord_message_id,
                provenance.get("reply_to_message_id") != discord_message_id,
                provenance.get("resident_conversation_id")
                != resident_conversation_id,
                provenance.get("conversation_key") != conversation_key,
            )
        ):
            continue
        run_id = str(manifest.get("run_id") or manifest_path.parent.name)
        resolved_path = manifest_path.resolve()
        prior_path = seen_run_paths.get(run_id)
        if prior_path is not None and prior_path != resolved_path:
            return None
        seen_run_paths[run_id] = resolved_path
        anchor_field = "started_at" if manifest.get("started_at") else "created_at"
        anchor = _parse_timestamp(manifest.get(anchor_field))
        if anchor is None:
            continue
        anchor = anchor.astimezone(timezone.utc)
        age = received - anchor
        if age < timedelta(0) or age > DISCORD_FOLLOWUP_WINDOW:
            continue
        candidates.append(
            (
                anchor,
                run_id,
                _lineage_root_id(manifest, manifest_path),
                resolved_path,
                anchor_field,
            )
        )
    if not candidates:
        return None
    lineages = {candidate[2] for candidate in candidates}
    if len(lineages) != 1:
        # A Discord reply contains no run selector. Guessing between two agent
        # conversations launched from one source would cross session custody.
        return None
    anchor, run_id, lineage_root_run_id, manifest_path, anchor_field = max(
        candidates, key=lambda item: (item[0], item[1])
    )
    return DiscordFollowupTarget(
        run_id=run_id,
        lineage_root_run_id=lineage_root_run_id,
        manifest_path=str(manifest_path),
        launch_anchor=anchor.isoformat(),
        launch_anchor_field=anchor_field,
    )


def _manifest_session_ids(
    manifest_path: Path,
    manifest: Mapping[str, Any],
    *,
    allow_multiple: bool = False,
) -> set[str]:
    found: set[str] = set()
    model_session = manifest.get("model_session")
    if isinstance(model_session, Mapping):
        session_id = str(model_session.get("session_id") or "").strip().lower()
        if session_id:
            if not re.fullmatch(
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                session_id,
            ):
                raise SubagentFollowupError("managed run has a malformed model session id")
            found.add(session_id)
    log_path = Path(str(manifest.get("log_path") or manifest_path.parent / "run.log"))
    log_text = _model_session_log_prefix(log_path)
    # Only the first CLI header/event owns this run. Later tool output may quote
    # another run's log verbatim and must not become session-ownership evidence.
    text_matches = _CODEX_SESSION_RE.findall(log_text)
    json_matches = _CODEX_JSON_SESSION_RE.findall(log_text)
    if text_matches:
        found.add(text_matches[0].lower())
    elif json_matches:
        found.add(json_matches[0].lower())
    if len(found) > 1 and not allow_multiple:
        raise SubagentFollowupError("managed run exposes multiple model session ids")
    return found


def _model_session_log_prefix(log_path: Path) -> str:
    """Read only the authoritative opening portion of a managed worker log."""

    try:
        with log_path.open("rb") as handle:
            return handle.read(MAX_MODEL_SESSION_LOG_PREFIX_BYTES).decode(
                "utf-8", errors="replace"
            )
    except OSError:
        return ""


def _lineage_root_id(manifest: Mapping[str, Any], manifest_path: Path) -> str:
    return str(
        manifest.get("lineage_root_run_id")
        or manifest.get("root_run_id")
        or manifest.get("run_id")
        or manifest_path.parent.name
    )


def _lineage_manifests(
    root: Path, lineage_root_run_id: str
) -> dict[str, tuple[Path, dict[str, Any]]]:
    rows: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in root.glob("*/manifest.json"):
        try:
            payload = _read_managed_resident_manifest(path)
        except SubagentFollowupError:
            continue
        run_id = str(payload.get("run_id") or path.parent.name)
        claimed_root = _lineage_root_id(payload, path)
        if run_id == lineage_root_run_id or claimed_root == lineage_root_run_id:
            rows[run_id] = (path, payload)
    return rows


def _lineage_tip(
    rows: Mapping[str, tuple[Path, dict[str, Any]]],
) -> tuple[Path, dict[str, Any]]:
    parent_ids = {
        str(payload.get("parent_run_id"))
        for _, payload in rows.values()
        if payload.get("parent_run_id")
    }
    leaves = [entry for run_id, entry in rows.items() if run_id not in parent_ids]
    if len(leaves) != 1:
        raise SubagentFollowupError("managed model session lineage has ambiguous branch ownership")
    return leaves[0]


def _compatible_followup_provenance(
    target: Mapping[str, Any], caller: Mapping[str, Any]
) -> None:
    target_normalized = normalize_delegation_provenance(target)
    caller_normalized = normalize_delegation_provenance(caller)
    if target_normalized["applicability"] != caller_normalized["applicability"]:
        raise SubagentFollowupError("follow-up provenance transport conflicts with target custody")
    if target_normalized["applicability"] != "applicable":
        return
    for field in (
        "resident_conversation_id",
        "conversation_key",
        "guild_id",
        "channel_id",
        "thread_id",
        "dm_user_id",
    ):
        if target_normalized.get(field) != caller_normalized.get(field):
            raise SubagentFollowupError(
                f"follow-up provenance {field} conflicts with target session ownership"
            )


def _session_owner_lineage(
    session_id: str,
    *,
    roots: tuple[Path, ...],
) -> str | None:
    owners: set[str] = set()
    for root in roots:
        for path in root.glob("*/manifest.json"):
            try:
                payload = _read_managed_resident_manifest(path)
            except SubagentFollowupError:
                continue
            try:
                ids = _manifest_session_ids(path, payload, allow_multiple=True)
            except SubagentFollowupError:
                # An unrelated malformed legacy record must not deny service.
                # If it contains the requested session identity, however, safe
                # ownership cannot be established and continuation fails closed.
                log_path = Path(str(payload.get("log_path") or path.parent / "run.log"))
                raw = json.dumps(payload, sort_keys=True) + _model_session_log_prefix(
                    log_path
                )
                if session_id in raw.lower():
                    raise SubagentFollowupError(
                        "model session id has ambiguous malformed ownership evidence"
                    )
                continue
            if session_id in ids:
                if len(ids) > 1:
                    raise SubagentFollowupError(
                        "model session id appears in a multi-session managed run"
                    )
                owners.add(_lineage_root_id(payload, path))
    if len(owners) > 1:
        raise SubagentFollowupError("model session id has ambiguous managed-run ownership")
    return next(iter(owners), None)


def _followup_result(
    record: Mapping[str, Any], *, idempotent_replay: bool
) -> SubagentFollowupResult:
    return SubagentFollowupResult(
        ok=True,
        followup_id=str(record["followup_id"]),
        target_run_id=str(record["target_run_id"]),
        parent_run_id=str(record["parent_run_id"]),
        lineage_root_run_id=str(record["lineage_root_run_id"]),
        continuation_run_id=str(record["continuation_run_id"]),
        status=str(record.get("status") or "continuation_started"),
        evidence_path=str(record["evidence_path"]),
        message_path=str(record["message_path"]),
        continuation_manifest_path=str(record["continuation_manifest_path"]),
        model_session_id=(
            str(record["model_session_id"])
            if record.get("model_session_id")
            else None
        ),
        idempotent_replay=idempotent_replay,
    )


def follow_up_managed_subagent(
    *,
    run_id: str,
    message: str,
    project_dir: str | Path | None = None,
    idempotency_key: str | None = None,
    workspace_root: str | Path | None = "/workspace",
    caller_provenance: Mapping[str, Any] | None = None,
    expected_target_source_record_id: str | None = None,
    expected_target_discord_message_id: str | None = None,
    query_relationship: Mapping[str, Any] | None = None,
    aggregation_role: str = "synthesis_delivery_owner",
    synthesis_group: str | None = None,
) -> SubagentFollowupResult:
    """Durably append ``message`` to the unique persistent session lineage.

    A continuation supervisor is created for both active and terminal parents.
    An active parent is interrupted only through its exact manifest-bound
    resident supervisor, after a unique persistent session is proven; the
    continuation waits for that parent to become terminal before resuming the
    same session.  The caller's validated resident provenance is the
    continuation's provenance; target provenance is used only to authorize the
    same immutable conversation ownership.
    """

    message = message.strip()
    if not message:
        raise SubagentFollowupError("follow-up message must not be empty")
    if len(message) > MAX_FOLLOWUP_MESSAGE_CHARS:
        raise SubagentFollowupError(
            f"follow-up message exceeds {MAX_FOLLOWUP_MESSAGE_CHARS} characters"
        )
    if idempotency_key is not None and not _FOLLOWUP_KEY_RE.fullmatch(idempotency_key):
        raise SubagentFollowupError("idempotency_key is malformed")
    if aggregation_role not in AGGREGATION_ROLES:
        raise SubagentFollowupError("follow-up aggregation_role is invalid")
    synthesis_group = str(synthesis_group or "").strip() or None
    if aggregation_role == "internal_contributor" and synthesis_group is None:
        raise SubagentFollowupError(
            "internal contributor follow-ups require synthesis_group"
        )
    if synthesis_group is not None and not _SYNTHESIS_GROUP_RE.fullmatch(synthesis_group):
        raise SubagentFollowupError("follow-up synthesis_group is malformed")
    inherited_provenance = (
        normalize_delegation_provenance(caller_provenance)
        if caller_provenance is not None
        else provenance_from_environment(strict=True)
    )
    if inherited_provenance is None:
        raise SubagentFollowupError(
            "resident follow-up requires inherited delegation provenance"
        )
    caller_provenance = inherited_provenance

    project_root = Path(project_dir or Path.cwd()).resolve()
    target_path, target, roots = _find_managed_run(
        run_id, project_root=project_root, workspace_root=workspace_root
    )
    target_provenance = target.get("launch_provenance")
    if not isinstance(target_provenance, Mapping):
        raise SubagentFollowupError("target run has no canonical launch provenance")
    try:
        _compatible_followup_provenance(target_provenance, caller_provenance)
        normalized_target_provenance = normalize_delegation_provenance(
            target_provenance
        )
    except DelegationProvenanceError as exc:
        raise SubagentFollowupError("target run provenance is malformed") from exc
    if (
        expected_target_source_record_id is not None
        and normalized_target_provenance.get("source_record_id")
        != expected_target_source_record_id
    ):
        raise SubagentFollowupError(
            "target run source custody changed after Discord reply matching"
        )
    if (
        expected_target_discord_message_id is not None
        and normalized_target_provenance.get("discord_message_id")
        != expected_target_discord_message_id
    ):
        raise SubagentFollowupError(
            "target run Discord message custody changed after reply matching"
        )

    lineage_root_run_id = _lineage_root_id(target, target_path)
    root = target_path.parent.parent
    followups_dir = root / lineage_root_run_id / "followups"
    followups_dir.mkdir(parents=True, exist_ok=True)
    message_sha256 = hashlib.sha256(message.encode("utf-8")).hexdigest()
    selector = idempotency_key or message_sha256
    caller_sha256 = hashlib.sha256(
        json.dumps(caller_provenance, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    followup_id = stable_identity(
        "followup",
        lineage_root_run_id,
        caller_provenance.get("custody_id") or caller_provenance.get("source_record_id"),
        selector,
    )
    evidence_path = followups_dir / f"{followup_id}.json"
    message_path = followups_dir / f"{followup_id}.md"

    with (root / ".followup.lock").open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        existing: dict[str, Any] | None = None
        if evidence_path.is_file():
            try:
                loaded = json.loads(evidence_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError) as exc:
                raise SubagentFollowupError("existing follow-up evidence is unreadable") from exc
            if not isinstance(loaded, dict):
                raise SubagentFollowupError("existing follow-up evidence is malformed")
            if (
                loaded.get("message_sha256") != message_sha256
                or loaded.get("requester_provenance_sha256") != caller_sha256
                or loaded.get("aggregation_role", "synthesis_delivery_owner")
                != aggregation_role
                or loaded.get("synthesis_group") != synthesis_group
            ):
                raise SubagentFollowupError(
                    "idempotency key is already bound to different follow-up content or custody"
                )
            existing = loaded
            if existing.get("continuation_run_id"):
                return _followup_result(existing, idempotent_replay=True)

        rows = _lineage_manifests(root, lineage_root_run_id)
        if run_id not in rows:
            raise SubagentFollowupError("target run is not in its claimed lineage")
        for lineage_run_id, (_lineage_path, lineage_manifest) in rows.items():
            lineage_provenance = lineage_manifest.get("launch_provenance")
            if not isinstance(lineage_provenance, Mapping):
                raise SubagentFollowupError(
                    "managed model session lineage contains missing provenance"
                )
            try:
                _compatible_followup_provenance(
                    target_provenance, lineage_provenance
                )
            except DelegationProvenanceError as exc:
                raise SubagentFollowupError(
                    "managed model session lineage contains malformed provenance"
                ) from exc
            parent_id = str(lineage_manifest.get("parent_run_id") or "")
            if (
                lineage_run_id != lineage_root_run_id
                and (not parent_id or parent_id not in rows)
            ):
                raise SubagentFollowupError(
                    "managed model session lineage contains an orphaned continuation"
                )
        tip_path, tip = _lineage_tip(rows)
        parent_run_id = str(
            (existing or {}).get("parent_run_id")
            or tip.get("run_id")
            or tip_path.parent.name
        )
        if existing and parent_run_id not in rows:
            raise SubagentFollowupError("recorded follow-up parent is missing from lineage")
        if existing:
            tip_path, tip = rows[parent_run_id]

        parent_status = str(tip.get("status") or "unknown")
        parent_live = (
            parent_status in _ACTIVE_STATUSES
            and isinstance(tip.get("pid"), int)
            and _pid_matches_manifest(int(tip["pid"]), tip_path)
        )
        if parent_status in _ACTIVE_STATUSES and not parent_live:
            raise SubagentFollowupError(
                "target lineage tip claims an active state without a matching supervisor"
            )
        if parent_status not in _ACTIVE_STATUSES and parent_status not in {
            "completed",
            "failed",
            "interrupted",
        }:
            raise SubagentFollowupError(
                f"target lineage tip has unsafe non-continuable status: {parent_status}"
            )

        parent_session_ids = _manifest_session_ids(tip_path, tip)
        model_session_id = next(iter(parent_session_ids), None)
        if model_session_id is None:
            raise SubagentFollowupError(
                f"{('active' if parent_live else 'terminal')} target has no uniquely "
                "recoverable persistent model session"
            )
        if model_session_id is not None:
            owner = _session_owner_lineage(model_session_id, roots=roots)
            if owner is not None and owner != lineage_root_run_id:
                raise SubagentFollowupError("model session is owned by another managed-run lineage")

        if existing is None:
            accepted_at = _utc_now()
            record = {
                "schema_version": FOLLOWUP_SCHEMA,
                "followup_id": followup_id,
                "target_run_id": run_id,
                "parent_run_id": parent_run_id,
                "lineage_root_run_id": lineage_root_run_id,
                "message_path": str(message_path),
                "message_sha256": message_sha256,
                "idempotency_key": selector,
                "requester_provenance": caller_provenance,
                "requester_provenance_sha256": caller_sha256,
                "aggregation_role": aggregation_role,
                "synthesis_group": synthesis_group,
                "query_relationship": (
                    dict(query_relationship)
                    if isinstance(query_relationship, Mapping)
                    else None
                ),
                "parent_status_at_acceptance": parent_status,
                "status": "accepted",
                "accepted_at": accepted_at,
                "updated_at": accepted_at,
                "evidence_path": str(evidence_path),
                "state_history": [
                    {
                        "status": "accepted",
                        "at": accepted_at,
                        "evidence": "followup_message_and_custody_committed",
                    }
                ],
            }
            message_path.write_text(message + "\n", encoding="utf-8")
            _atomic_json(evidence_path, record)
        else:
            record = existing

        try:
            continuation = launch_codex_subagent_detached(
                task=message,
                description=(
                    f"Follow up on {str(tip.get('description') or target.get('description')).rstrip('.')}"
                    if tip.get("description") or target.get("description")
                    else None
                ),
                project_dir=str(
                    tip.get("project_dir")
                    or target.get("project_dir")
                    or project_root
                ),
                model=str(tip.get("model") or target.get("model") or "gpt-5.6-terra"),
                reasoning_effort=str(
                    tip.get("reasoning_effort") or target.get("reasoning_effort") or "medium"
                ),
                task_kind=str(tip.get("task_kind") or target.get("task_kind") or "routine"),
                work_intent=str(
                    tip.get("work_intent")
                    or target.get("work_intent")
                    or DEFAULT_DELEGATED_WORK_INTENT
                ),
                difficulty=int(tip.get("difficulty") or target.get("difficulty") or 4),
                route_class="resident_followup_continuation",
                run_root=root,
                launch_origin=caller_provenance,
                parent_run_id=parent_run_id,
                lineage_root_run_id=lineage_root_run_id,
                continued_session_id=model_session_id,
                followup_id=followup_id,
                parent_manifest_path=tip_path,
                interrupt_parent=parent_live,
                query_relationship=query_relationship,
                aggregation_role=aggregation_role,
                synthesis_group=synthesis_group,
            )
        except Exception as exc:
            failed_at = _utc_now()
            record["status"] = "launch_failed"
            record["updated_at"] = failed_at
            record["error_class"] = exc.__class__.__name__
            record["state_history"] = list(record.get("state_history") or []) + [
                {
                    "status": "launch_failed",
                    "at": failed_at,
                    "evidence": "continuation_supervisor_launch_failed",
                }
            ]
            _atomic_json(evidence_path, record)
            raise

        started_at = _utc_now()
        record.update(
            {
                "status": "continuation_started",
                "updated_at": started_at,
                "continuation_run_id": continuation.run_id,
                "continuation_manifest_path": continuation.manifest_path,
                "model_session_id": model_session_id,
            }
        )
        record["state_history"] = list(record.get("state_history") or []) + [
            {
                "status": "continuation_started",
                "at": started_at,
                "evidence": (
                    "continuation_queued_to_interrupt_active_parent"
                    if parent_live
                    else "terminal_lineage_continuation_supervisor_started"
                ),
                "continuation_run_id": continuation.run_id,
            }
        ]
        _atomic_json(evidence_path, record)
        return _followup_result(record, idempotent_replay=False)


def _spawn_managed_supervisor(
    manifest_path: Path, manifest: Mapping[str, Any]
) -> tuple[subprocess.Popen[bytes], dict[str, Any]]:
    """Start the manifest-bound supervisor and durably record its launch."""

    argv = [
        sys.executable,
        "-m",
        "arnold_pipelines.megaplan.resident.subagent_worker",
        "--run-codex",
        str(manifest_path),
    ]
    provenance = manifest.get("launch_provenance")
    worker_provenance = dict(provenance) if isinstance(provenance, Mapping) else {}
    if worker_provenance.get("applicability") == "applicable":
        worker_provenance["root_run_id"] = str(
            manifest.get("run_id") or manifest_path.parent.name
        )
    log_path = _queue_artifact_path(
        manifest_path, manifest, "full_log_path", str(manifest.get("log_path") or "run.log")
    )
    with log_path.open("ab") as log_handle:
        process = subprocess.Popen(
            argv,
            cwd=str(Path(__file__).resolve().parents[3]),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=environment_with_provenance(worker_provenance),
        )
    current = json.loads(manifest_path.read_text(encoding="utf-8"))
    current.setdefault("pid", process.pid)
    current.setdefault("started_at", _utc_now())
    if current.get("status") == "launching":
        current["status"] = "running"
        current["updated_at"] = _utc_now()
        history = list(current.get("status_history") or [])
        history.append(
            {
                "status": "running",
                "at": current["updated_at"],
                "evidence": "resident_supervisor_started",
            }
        )
        current["status_history"] = history[-100:]
    queue = current.get("queue")
    if isinstance(queue, dict):
        queue.update(
            {
                "state": "running",
                "attention": "none",
                "supervisor_started_at": current.get("started_at"),
                "updated_at": current.get("updated_at"),
            }
        )
        current["queue"] = queue
    _atomic_json(manifest_path, current)
    return process, current


def launch_codex_subagent_detached(
    *,
    task: str,
    description: str | None = None,
    project_dir: str | None = None,
    model: str = "gpt-5.6-terra",
    reasoning_effort: str = "medium",
    task_kind: DelegatedTaskKind = DEFAULT_DELEGATED_TASK_KIND,
    work_intent: DelegatedWorkIntent = DEFAULT_DELEGATED_WORK_INTENT,
    difficulty: int = DEFAULT_DELEGATED_DIFFICULTY,
    route_class: str = "routine",
    run_root: str | Path = DEFAULT_MANAGED_RUN_ROOT,
    request_id: str | None = None,
    launch_origin: Mapping[str, Any] | None = None,
    retry_of_run_id: str | None = None,
    parent_run_id: str | None = None,
    lineage_root_run_id: str | None = None,
    continued_session_id: str | None = None,
    followup_id: str | None = None,
    parent_manifest_path: str | Path | None = None,
    interrupt_parent: bool = False,
    query_relationship: Mapping[str, Any] | None = None,
    aggregation_role: str = "synthesis_delivery_owner",
    synthesis_group: str | None = None,
    depends_on_run_id: str | None = None,
    queue_max_launch_attempts: int = _QUEUE_MAX_LAUNCH_ATTEMPTS,
) -> SubagentResult:
    """Launch a durable, fully-permissioned Codex worker managed by Arnold.

    The supervisor process owns the manifest transitions and durable output, so
    the Discord resident can return immediately without losing lifecycle state.
    """
    if len(task) > MAX_DELEGATED_TASK_CHARS:
        raise ValueError(
            f"delegated task exceeds {MAX_DELEGATED_TASK_CHARS} characters; "
            "store large evidence durably and pass paths/routes"
        )
    if DELEGATION_DELIVERY_INSTRUCTION_HEADER in task:
        raise ValueError(
            "delegated task contains the reserved resident delivery instruction marker"
        )
    if depends_on_run_id and len(task) > MAX_QUEUE_PROMPT_CHARS:
        raise ValueError(
            f"queued successor prompt exceeds {MAX_QUEUE_PROMPT_CHARS} characters"
        )
    if not 1 <= queue_max_launch_attempts <= 10:
        raise ValueError("queue_max_launch_attempts must be between 1 and 10")
    project_root = Path(project_dir or Path.cwd()).resolve()
    requested_root = Path(run_root)
    root = (
        project_root / requested_root
        if not requested_root.is_absolute() and requested_root == DEFAULT_MANAGED_RUN_ROOT
        else requested_root.resolve()
    )
    predecessor_path: Path | None = None
    predecessor: dict[str, Any] | None = None
    predecessor_references: list[dict[str, Any]] = []
    cross_request_authorization: dict[str, Any] | None = None
    queue_aggregation_key: str | None = None
    current_provenance = _canonical_launch_provenance(
        launch_origin,
        project_root=project_root,
        request_id=request_id,
    )
    provenance = current_provenance
    requested_work_intent = work_intent
    if depends_on_run_id:
        if not _RUN_ID_RE.fullmatch(depends_on_run_id):
            raise SubagentQueueError("predecessor run_id is malformed")
        predecessor_path = root / depends_on_run_id / "manifest.json"
        if not predecessor_path.is_file():
            raise SubagentQueueError(
                f"unknown predecessor run_id in project custody: {depends_on_run_id}"
            )
        try:
            predecessor = _read_managed_resident_manifest(predecessor_path)
        except SubagentFollowupError as exc:
            raise SubagentQueueError(str(exc)) from exc
        predecessor_project = Path(str(predecessor.get("project_dir") or "")).resolve()
        if predecessor_project != project_root:
            raise SubagentQueueError(
                "queued successor must inherit the predecessor project directory"
            )
        predecessor_provenance = predecessor.get("launch_provenance")
        if not isinstance(predecessor_provenance, Mapping):
            raise SubagentQueueError("predecessor lacks immutable launch provenance")
        predecessor_provenance = normalize_delegation_provenance(predecessor_provenance)
        same_request = _queue_provenance_identity(
            current_provenance
        ) == _queue_provenance_identity(predecessor_provenance)
        if same_request:
            provenance = predecessor_provenance
            request_id = str(predecessor.get("request_id") or "") or None
        else:
            (
                cross_request_authorization,
                current_aggregation,
                current_relationship,
            ) = _cross_request_queue_authorization(
                root,
                project_root=project_root,
                predecessor_run_id=depends_on_run_id,
                predecessor=predecessor,
                current_provenance=current_provenance,
                require_active_caller=True,
            )
            provenance = current_provenance
            request_id = str(current_provenance.get("source_record_id") or "") or None
            query_relationship = current_relationship
            queue_aggregation_key = str(current_aggregation["key"])
            synthesis_group = str(current_aggregation["synthesis_group"])
        model = str(predecessor.get("model") or model)
        reasoning_effort = str(predecessor.get("reasoning_effort") or reasoning_effort)
        task_kind = str(predecessor.get("task_kind") or task_kind)
        predecessor_work_intent = str(
            predecessor.get("work_intent") or requested_work_intent
        )
        if (
            requested_work_intent != "auto"
            and requested_work_intent != predecessor_work_intent
        ):
            raise SubagentQueueError(
                "queued successor must inherit predecessor work_intent; "
                f"requested {requested_work_intent!r}, predecessor has "
                f"{predecessor_work_intent!r}"
            )
        work_intent = predecessor_work_intent
        difficulty = int(predecessor.get("difficulty") or difficulty)
        route_class = (
            "queued_successor" if same_request else "queued_cross_request_successor"
        )
        if same_request:
            query_relationship = (
                dict(predecessor["query_relationship"])
                if isinstance(predecessor.get("query_relationship"), Mapping)
                else None
            )
        predecessor_aggregation = predecessor.get("aggregation")
        if not isinstance(predecessor_aggregation, Mapping) or not predecessor_aggregation.get(
            "key"
        ):
            raise SubagentQueueError("predecessor lacks logical aggregation custody")
        aggregation_role = "synthesis_delivery_owner"
        if same_request:
            synthesis_group = (
                str(predecessor_aggregation.get("synthesis_group") or "") or None
            )
        predecessor_references = _queue_predecessor_references(
            predecessor_path, predecessor
        )
        _queue_ancestor_ids(root, depends_on_run_id)
    root.mkdir(parents=True, exist_ok=True)
    is_discord = provenance["applicability"] == "applicable"
    agent_description = concise_agent_description(description, task)
    resolved_work_intent = resolve_delegated_work_intent(
        task_kind=task_kind,
        work_intent=work_intent,
    )
    if aggregation_role not in AGGREGATION_ROLES:
        raise ValueError(
            "aggregation_role must be synthesis_delivery_owner or internal_contributor"
        )
    synthesis_group = str(synthesis_group or "").strip() or None
    if synthesis_group is not None and not _SYNTHESIS_GROUP_RE.fullmatch(synthesis_group):
        raise ValueError("synthesis_group must be a stable 1..80 character identifier")
    if aggregation_role == "internal_contributor" and synthesis_group is None:
        raise ValueError("internal_contributor launches require an explicit synthesis_group")
    if query_relationship is None and is_discord:
        query_relationship = relationship_from_environment_or_project(
            str(provenance.get("source_record_id") or "") or None,
            project_root=project_root,
        )
    if isinstance(query_relationship, Mapping):
        current_ref = _request_ref(query_relationship, "current_request") or {}
        if (
            str(current_ref.get("source_record_id") or "")
            != str(provenance.get("source_record_id") or "")
        ):
            raise DelegationProvenanceError(
                "query relationship current request conflicts with launch provenance"
            )
    origin = discord_origin_projection(provenance) if is_discord else None
    task_digest = hashlib.sha256(task.encode("utf-8")).hexdigest()
    relationship_digest = hashlib.sha256(
        json.dumps(
            dict(query_relationship) if isinstance(query_relationship, Mapping) else None,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
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
        resolved_work_intent,
        agent_description,
        aggregation_role,
        synthesis_group or "",
        relationship_digest,
        retry_of_run_id or "",
        parent_run_id or "",
        lineage_root_run_id or "",
        continued_session_id or "",
        followup_id or "",
        depends_on_run_id or "",
    )
    launch_lock = root / ".launch.lock"
    launch_handle = launch_lock.open("a+b")
    fcntl.flock(launch_handle.fileno(), fcntl.LOCK_EX)
    existing = _existing_idempotent_launch(root, launch_key)
    if existing is not None:
        existing_path, existing_manifest = existing
        existing = (
            existing_path,
            _recover_idempotent_cross_request_queue(
                existing_path, existing_manifest
            ),
        )
        fcntl.flock(launch_handle.fileno(), fcntl.LOCK_UN)
        launch_handle.close()
        return _result_from_manifest(*existing)
    created_at = _utc_now()
    aggregation_key = (
        (
            queue_aggregation_key
            or str((predecessor.get("aggregation") or {})["key"])
        )
        if predecessor is not None
        else (
            _aggregation_key(
                provenance,
                synthesis_group=synthesis_group,
                task_digest=task_digest,
                description=agent_description,
                request_id=request_id,
            )
            if is_discord
            else stable_identity("resident-single-delivery", launch_key)
        )
    )
    contributors = (
        _aggregation_contributor_refs(root, aggregation_key=aggregation_key)
        if aggregation_role == "synthesis_delivery_owner"
        else []
    )
    if aggregation_role == "synthesis_delivery_owner" and any(
        contributor.get("aggregation_role") == "synthesis_delivery_owner"
        and contributor.get("delivery_status") == "delivered"
        for contributor in contributors
    ):
        fcntl.flock(launch_handle.fileno(), fcntl.LOCK_UN)
        launch_handle.close()
        raise ValueError("synthesis_group already has a delivered owner")
    run_id = f"subagent-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    prompt_path = run_dir / "prompt.md"
    manifest_path = run_dir / "manifest.json"
    log_path = run_dir / "run.log"
    result_path = run_dir / "result.md"
    git_custody_evidence_path = run_dir / "git-custody-evidence.json"
    context_directory = _delegated_context_directory(
        project_root=project_root,
        provenance=provenance,
    )
    git_custody = resolve_launch_git_custody(
        project_root=project_root,
        runtime_root=str(context_directory["resident_runtime_source"]),
        evidence_path=git_custody_evidence_path,
    )
    effective_task = task
    if depends_on_run_id:
        effective_task = (
            f"{task.rstrip()}\n\n"
            + _render_queue_references(
                predecessor_run_id=depends_on_run_id,
                references=predecessor_references,
            )
        )
    prompt = _delivery_prompt(
        effective_task,
        str(provenance.get("timezone_name") or "UTC"),
        task_kind=task_kind,
        work_intent=resolved_work_intent,
        context_directory=context_directory,
        query_relationship=query_relationship,
        contributors=contributors,
        git_custody=git_custody,
    )
    prompt_path.write_text(prompt, encoding="utf-8")
    result_path.touch()
    if aggregation_role == "synthesis_delivery_owner":
        _transfer_aggregation_delivery_ownership(
            root,
            aggregation_key=aggregation_key,
            new_owner_run_id=run_id,
            at=created_at,
        )
    manifest: dict[str, object] = {
        "schema_version": MANAGED_RUN_SCHEMA,
        "run_kind": MANAGED_RUN_KIND,
        "custodian": MANAGED_RUN_CUSTODIAN,
        "run_id": run_id,
        "backend": "codex",
        "model": model,
        "reasoning_effort": reasoning_effort,
        "task_kind": task_kind,
        "work_intent": resolved_work_intent,
        "delegation_delivery_instruction": {
            "schema_version": DELEGATION_DELIVERY_INSTRUCTION_SCHEMA,
            "resolved_work_intent": resolved_work_intent,
            "sha256": hashlib.sha256(
                _delegation_delivery_instruction(resolved_work_intent).encode("utf-8")
            ).hexdigest(),
        },
        "description": agent_description,
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
        "context_directory": context_directory,
        "git_custody": git_custody,
        "launch_idempotency_key": launch_key,
        "correlation_id": provenance.get("correlation_id") or run_id,
        "custody_id": provenance.get("custody_id") or stable_identity("resident-custody", run_id),
        "launch_provenance": provenance,
        "query_relationship": dict(query_relationship) if isinstance(query_relationship, Mapping) else None,
        "aggregation": {
            "schema_version": AGGREGATION_SCHEMA,
            "key": aggregation_key,
            "synthesis_group": synthesis_group,
            "role": aggregation_role,
            "delivery_owner_run_id": (
                run_id if aggregation_role == "synthesis_delivery_owner" else None
            ),
            "delivery_target_source_record_id": provenance.get("source_record_id"),
            "contributors": contributors,
        },
        "status": "queued" if depends_on_run_id else "launching",
        "created_at": created_at,
        "updated_at": created_at,
        "status_history": [
            {
                "status": "queued" if depends_on_run_id else "launching",
                "at": created_at,
                "evidence": (
                    "successor_committed_waiting_for_predecessor_terminal_evidence"
                    if depends_on_run_id
                    else "manifest_committed_before_process_launch"
                ),
            }
        ],
    }
    if depends_on_run_id:
        manifest["queue"] = {
            "schema_version": QUEUE_SCHEMA,
            "trigger_policy": QUEUE_TRIGGER_POLICY,
            "state": "waiting_predecessor",
            "predecessor_run_id": depends_on_run_id,
            "successor_run_id": run_id,
            "authored_prompt": {
                "sha256": task_digest,
                "size_chars": len(task),
                "description": agent_description,
            },
            "predecessor_references": predecessor_references,
            "ancestor_run_ids": _queue_ancestor_ids(root, depends_on_run_id),
            "attempt_count": 0,
            "max_launch_attempts": queue_max_launch_attempts,
            "created_at": created_at,
            "updated_at": created_at,
            "attention": "waiting_for_predecessor",
        }
        if cross_request_authorization is not None:
            manifest["queue"]["cross_request_authorization"] = (
                cross_request_authorization
            )
        manifest["parent_run_id"] = depends_on_run_id
        manifest["lineage_root_run_id"] = str(
            predecessor.get("lineage_root_run_id")
            or predecessor.get("run_id")
            or depends_on_run_id
        )
        manifest["lineage_key"] = stable_identity(
            "resident-session-lineage", manifest["lineage_root_run_id"]
        )
    if retry_of_run_id:
        manifest["retry_of_run_id"] = retry_of_run_id
    if parent_run_id:
        manifest["parent_run_id"] = parent_run_id
    if lineage_root_run_id:
        manifest["lineage_root_run_id"] = lineage_root_run_id
        manifest["lineage_key"] = stable_identity(
            "resident-session-lineage", lineage_root_run_id
        )
    if followup_id:
        manifest["followup_id"] = followup_id
        manifest["run_mode"] = "session_continuation"
    if continued_session_id:
        manifest["continued_session_id"] = continued_session_id
    if parent_manifest_path:
        manifest["parent_manifest_path"] = str(Path(parent_manifest_path).resolve())
        manifest["continuation_wait"] = {
            "status": "pending_parent_terminal",
            "parent_run_id": parent_run_id,
            "parent_manifest_path": str(Path(parent_manifest_path).resolve()),
            "committed_at": created_at,
        }
        if interrupt_parent:
            manifest["continuation_wait"]["interrupt_parent_on_session_ready"] = True
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
            "status": (
                "pending"
                if aggregation_role == "synthesis_delivery_owner"
                else "suppressed"
            ),
            "attempt_count": 0,
            "custody_id": manifest["custody_id"],
            "outbox_id": stable_identity("discord-outbox", run_id, origin["reply_to_message_id"]),
            "aggregation_key": aggregation_key,
            "aggregation_role": aggregation_role,
            "idempotency_key": f"resident-subagent-completion:{run_id}",
            "reply_target": {
                "conversation_key": origin["conversation_key"],
                "message_id": origin["reply_to_message_id"],
                "source_record_id": provenance["source_record_id"],
            },
            "state_history": [
                {
                    "status": (
                        "pending"
                        if aggregation_role == "synthesis_delivery_owner"
                        else "suppressed"
                    ),
                    "at": manifest["created_at"],
                    "evidence": (
                        "outbox_committed_before_launch"
                        if aggregation_role == "synthesis_delivery_owner"
                        else "internal_contributor_reports_to_synthesis_owner"
                    ),
                }
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
    if depends_on_run_id and predecessor_path is not None:
        predecessor = json.loads(predecessor_path.read_text(encoding="utf-8"))
        links = dict(predecessor.get("queue_links") or {})
        successor_ids = [
            str(value)
            for value in links.get("successor_run_ids", [])
            if str(value).strip() and str(value) != run_id
        ]
        successor_ids.append(run_id)
        links.update(
            {
                "schema_version": QUEUE_SCHEMA,
                "successor_run_ids": successor_ids[-20:],
                "successor_omitted_count": max(0, len(successor_ids) - 20),
                "updated_at": created_at,
            }
        )
        predecessor["queue_links"] = links
        _atomic_json(predecessor_path, predecessor)
        fcntl.flock(launch_handle.fileno(), fcntl.LOCK_UN)
        launch_handle.close()
        return SubagentResult(
            ok=True,
            final_text="",
            stderr="",
            returncode=0,
            run_id=run_id,
            status="queued",
            manifest_path=str(manifest_path),
            log_path=str(log_path),
            result_path=str(result_path),
            pid=None,
            description=agent_description,
        )
    # Once the manifest exists, concurrent/restarted callers can return its
    # durable identity without creating a second worker.  Process start is a
    # recoverable transition from this point onward.
    fcntl.flock(launch_handle.fileno(), fcntl.LOCK_UN)
    launch_handle.close()
    process, current = _spawn_managed_supervisor(manifest_path, manifest)
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
        description=agent_description,
    )


def _interrupt_parent_for_followup(
    *,
    parent_path: Path,
    continuation_manifest: Mapping[str, Any],
    session_id: str,
) -> str:
    """Request one exact resident supervisor to stop its active model turn.

    This is deliberately narrower than process-group or terminal cleanup: the
    PID must still execute the resident subagent supervisor with this exact
    manifest path.  Custody and delivery supersession are committed before the
    signal so a restart cannot publish a misleading terminal-failure reply for
    the interrupted turn.
    """

    with (parent_path.parent / ".followup-interrupt.lock").open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        parent = _read_managed_resident_manifest(parent_path)
        parent_run_id = str(parent.get("run_id") or parent_path.parent.name)
        expected_parent = str(continuation_manifest.get("parent_run_id") or "")
        if parent_run_id != expected_parent:
            raise SubagentFollowupError("continuation parent identity changed")
        expected_lineage = str(
            continuation_manifest.get("lineage_root_run_id") or ""
        )
        if _lineage_root_id(parent, parent_path) != expected_lineage:
            raise SubagentFollowupError("continuation parent lineage ownership changed")
        status = str(parent.get("status") or "unknown")
        if status in {"completed", "failed", "interrupted"}:
            return "parent_already_terminal"
        if status not in _ACTIVE_STATUSES:
            raise SubagentFollowupError(
                f"continuation parent entered unsafe status: {status}"
            )
        session_ids = _manifest_session_ids(parent_path, parent)
        if session_ids != {session_id}:
            raise SubagentFollowupError(
                "active parent session evidence changed before interruption"
            )
        pid = parent.get("pid")
        if not isinstance(pid, int) or not _pid_matches_manifest(pid, parent_path):
            raise SubagentFollowupError(
                "continuation parent lost its resident-managed supervisor"
            )
        requested_at = _utc_now()
        interrupt = {
            "schema_version": "arnold-resident-followup-interrupt-v1",
            "status": "requested",
            "requested_at": requested_at,
            "followup_id": continuation_manifest.get("followup_id"),
            "continuation_run_id": continuation_manifest.get("run_id")
            or continuation_manifest.get("continuation_run_id"),
            "session_id": session_id,
            "signal": "SIGINT",
            "evidence": "exact_manifest_supervisor_identity_verified",
        }
        parent["followup_interrupt"] = interrupt
        delivery = parent.get("completion_delivery")
        if isinstance(delivery, dict) and delivery.get("status") != "delivered":
            delivery.update(
                {
                    "status": "superseded",
                    "superseded_at": requested_at,
                    "superseded_by_run_id": interrupt["continuation_run_id"],
                    "superseded_reason": "active_turn_interrupted_for_same_session_followup",
                    "updated_at": requested_at,
                }
            )
            history = list(delivery.get("state_history") or [])
            history.append(
                {
                    "status": "superseded",
                    "at": requested_at,
                    "evidence": "same_session_followup_interrupt_committed",
                    "continuation_run_id": interrupt["continuation_run_id"],
                }
            )
            delivery["state_history"] = history[-20:]
            parent["completion_delivery"] = delivery
        _atomic_json(parent_path, parent)
        try:
            os.kill(pid, signal.SIGINT)
        except ProcessLookupError:
            latest = _read_managed_resident_manifest(parent_path)
            if str(latest.get("status") or "") not in {
                "completed",
                "failed",
                "interrupted",
            }:
                raise SubagentFollowupError(
                    "managed supervisor exited before interruption was accepted"
                )
            return "parent_became_terminal"
        return "interrupt_requested"


def _await_continuation_parent(
    manifest_path: Path, manifest: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    parent_path = Path(str(manifest.get("parent_manifest_path") or ""))
    parent_run_id = str(manifest.get("parent_run_id") or "")
    if not parent_path.is_absolute() or parent_path.name != "manifest.json":
        raise SubagentFollowupError("continuation parent manifest path is malformed")
    interrupt_requested = False
    while True:
        parent = _read_managed_resident_manifest(parent_path)
        if str(parent.get("run_id") or parent_path.parent.name) != parent_run_id:
            raise SubagentFollowupError("continuation parent identity changed")
        if _lineage_root_id(parent, parent_path) != str(manifest.get("lineage_root_run_id") or ""):
            raise SubagentFollowupError("continuation parent lineage ownership changed")
        status = str(parent.get("status") or "unknown")
        if status in {"completed", "failed", "interrupted"}:
            ids = _manifest_session_ids(parent_path, parent)
            expected = str(manifest.get("continued_session_id") or "").strip().lower()
            if expected:
                ids.add(expected)
            if len(ids) != 1:
                raise SubagentFollowupError(
                    "continuation parent has no unique persistent model session"
                )
            session_id = next(iter(ids))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["continued_session_id"] = session_id
            manifest["model_session"] = {
                "provider": "codex",
                "session_id": session_id,
                "lineage_root_run_id": manifest.get("lineage_root_run_id"),
                "evidence": "validated_from_terminal_parent",
                "source_run_id": parent_run_id,
                "recorded_at": _utc_now(),
            }
            continuation_wait = dict(manifest.get("continuation_wait") or {})
            continuation_wait.update(
                {
                    "status": "parent_terminal",
                    "parent_status": status,
                    "resolved_at": _utc_now(),
                }
            )
            manifest["continuation_wait"] = continuation_wait
            _atomic_json(manifest_path, manifest)
            return manifest, session_id
        if status in {"cancelled", "superseded"}:
            raise SubagentFollowupError(
                f"continuation parent entered intentionally terminal status: {status}"
            )
        if status not in _ACTIVE_STATUSES:
            raise SubagentFollowupError(
                f"continuation parent entered unsafe status: {status}"
            )
        parent_pid = parent.get("pid")
        if not isinstance(parent_pid, int) or not _pid_matches_manifest(parent_pid, parent_path):
            raise SubagentFollowupError(
                "continuation parent lost its resident-managed supervisor"
            )
        continuation_wait = dict(manifest.get("continuation_wait") or {})
        if (
            continuation_wait.get("interrupt_parent_on_session_ready")
            and not interrupt_requested
        ):
            expected = str(manifest.get("continued_session_id") or "").strip().lower()
            if not expected:
                raise SubagentFollowupError(
                    "active continuation has no committed session identity"
                )
            disposition = _interrupt_parent_for_followup(
                parent_path=parent_path,
                continuation_manifest=manifest,
                session_id=expected,
            )
            interrupt_requested = True
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            continuation_wait = dict(manifest.get("continuation_wait") or {})
            continuation_wait.update(
                {
                    "status": disposition,
                    "interrupt_requested_at": _utc_now(),
                    "session_id": expected,
                }
            )
            manifest["continuation_wait"] = continuation_wait
            _atomic_json(manifest_path, manifest)
        time.sleep(1)


def _run_codex_manifest(manifest_path: Path) -> int:
    execution_handle = (manifest_path.parent / ".execution.lock").open("a+b")
    try:
        fcntl.flock(execution_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        execution_handle.close()
        # Another manifest-bound supervisor owns the only execution lease.
        return 0
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if str(manifest.get("status") or "") in _TERMINAL_STATUSES:
        fcntl.flock(execution_handle.fileno(), fcntl.LOCK_UN)
        execution_handle.close()
        return int(manifest.get("returncode") or 0)
    prompt = Path(str(manifest["prompt_path"])).read_text(encoding="utf-8")
    result_path = Path(str(manifest["result_path"]))
    worker: subprocess.Popen[bytes] | None = None
    session_id: str | None = None
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
        if manifest.get("run_mode") == "session_continuation":
            manifest, session_id = _await_continuation_parent(manifest_path, manifest)
            argv = [
                "codex",
                "exec",
                "resume",
                "-m",
                str(manifest["model"]),
                "-c",
                f"model_reasoning_effort={manifest['reasoning_effort']}",
                "--output-last-message",
                str(result_path),
                session_id,
                prompt,
            ]
        else:
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
        worker_started_at = _utc_now()
        manifest.update({"worker_started_at": worker_started_at, "worker_pid": worker.pid})
        manifest["session_dispatch"] = {
            "status": "accepted",
            "mode": "resume" if session_id else "new",
            "session_id": session_id,
            "accepted_at": worker_started_at,
            "evidence": (
                "codex_resume_process_started"
                if session_id
                else "codex_session_process_started"
            ),
        }
        _atomic_json(manifest_path, manifest)
        returncode = worker.wait()
        # Codex writes the final response to result_path while its complete
        # stream is inherited by the supervisor and appended to run.log.
        result_path.touch(exist_ok=True)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        control_status = str(manifest.get("status") or "")
        if control_status in _CONTROL_TERMINAL_STATUSES:
            # The manifest-bound controller is the terminal-state authority.
            # A worker exit racing an explicit cancel/supersede must never
            # rewrite that durable intent as a generic failure/completion.
            return int(manifest.get("returncode") or returncode or 0)
        observed_session_ids = _manifest_session_ids(manifest_path, manifest)
        if session_id:
            observed_session_ids.add(session_id)
        if len(observed_session_ids) == 1:
            resolved_session_id = next(iter(observed_session_ids))
            manifest["model_session"] = {
                "provider": "codex",
                "session_id": resolved_session_id,
                "lineage_root_run_id": manifest.get("lineage_root_run_id")
                or manifest.get("run_id")
                or manifest_path.parent.name,
                "evidence": "managed_codex_worker_log_and_dispatch",
                "recorded_at": _utc_now(),
            }
        custody_error: str | None = None
        if returncode == 0 and manifest.get("work_intent") == "execution":
            custody = manifest.get("git_custody")
            if isinstance(custody, Mapping):
                project_snapshot = custody.get("launch_checkouts")
                project_snapshot = (
                    project_snapshot.get("project")
                    if isinstance(project_snapshot, Mapping)
                    else None
                )
                if isinstance(project_snapshot, Mapping) and project_snapshot.get("git"):
                    try:
                        manifest["git_custody_verification"] = validate_git_custody_evidence(
                            custody
                        )
                    except GitCustodyError as exc:
                        custody_error = str(exc)
                        returncode = 2
        manifest.update(
            {
                "status": "completed" if returncode == 0 else "failed",
                "returncode": returncode,
                "finished_at": _utc_now(),
                "terminal_outcome": "completed" if returncode == 0 else "failed",
            }
        )
        if custody_error is not None:
            manifest["error"] = "git custody verification failed"
            manifest["git_custody_error"] = custody_error
        manifest["updated_at"] = manifest["finished_at"]
        history = list(manifest.get("status_history") or [])
        history.append(
            {
                "status": manifest["status"],
                "at": manifest["finished_at"],
                "evidence": "managed_codex_worker_waited",
                "returncode": returncode,
                **({"git_custody_error": custody_error} if custody_error else {}),
            }
        )
        manifest["status_history"] = history[-100:]
        _atomic_json(manifest_path, manifest)
        try:
            reconcile_managed_subagent_queues(
                project_root=str(manifest.get("project_dir") or manifest_path.parents[4]),
                workspace_root=None,
            )
        except Exception:
            LOGGER.exception(
                "Resident successor reconciliation failed after terminalization run_id=%s",
                manifest.get("run_id") or manifest_path.parent.name,
            )
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
        control_status = str(manifest.get("status") or "")
        if control_status in _CONTROL_TERMINAL_STATUSES:
            history = list(manifest.get("status_history") or [])
            history.append(
                {
                    "status": control_status,
                    "at": _utc_now(),
                    "evidence": "managed_codex_supervisor_acknowledged_control_terminal",
                }
            )
            manifest["status_history"] = history[-100:]
            manifest["updated_at"] = history[-1]["at"]
            _atomic_json(manifest_path, manifest)
            return int(
                manifest.get("returncode")
                or (128 + interrupted_signal if interrupted_signal is not None else 1)
            )
        status = "interrupted" if interrupted_signal is not None else "failed"
        manifest.update(
            {
                "status": status,
                "error": "managed Codex worker failed",
                "error_class": exc.__class__.__name__,
                "finished_at": _utc_now(),
                "terminal_outcome": status,
            }
        )
        manifest["updated_at"] = manifest["finished_at"]
        dispatch = dict(manifest.get("session_dispatch") or {})
        if dispatch.get("status") != "accepted":
            dispatch.update(
                {
                    "status": "failed",
                    "failed_at": manifest["finished_at"],
                    "evidence": "codex_session_process_not_accepted",
                    "error_class": exc.__class__.__name__,
                }
            )
            manifest["session_dispatch"] = dispatch
        history = list(manifest.get("status_history") or [])
        history.append(
            {
                "status": status,
                "at": manifest["finished_at"],
                "evidence": "managed_codex_supervisor_exception",
            }
        )
        manifest["status_history"] = history[-100:]
        if interrupted_signal is not None:
            manifest["signal"] = interrupted_signal
            manifest["returncode"] = 128 + interrupted_signal
        _atomic_json(manifest_path, manifest)
        try:
            reconcile_managed_subagent_queues(
                project_root=str(manifest.get("project_dir") or manifest_path.parents[4]),
                workspace_root=None,
            )
        except Exception:
            LOGGER.exception(
                "Resident successor reconciliation failed after failed terminalization run_id=%s",
                manifest.get("run_id") or manifest_path.parent.name,
            )
        if interrupted_signal is not None:
            return 128 + interrupted_signal
        return 1
    finally:
        for signum, handler in prior_handlers.items():
            signal.signal(signum, handler)
        fcntl.flock(execution_handle.fileno(), fcntl.LOCK_UN)
        execution_handle.close()


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
    return managed_run_roots(project_root=project_root, workspace_root=workspace_root)


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
        is_managed_manifest(payload)
        and payload.get("run_kind") == MANAGED_RUN_KIND
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


@contextmanager
def _queue_lock(manifest_path: Path) -> Iterator[None]:
    """Serialize one successor transition across terminal observers and restarts."""

    lock_path = manifest_path.parent / ".queue-transition.lock"
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _queue_terminalize(
    manifest_path: Path,
    manifest: dict[str, Any],
    *,
    status: str,
    reason: str,
    predecessor_status: str,
    now: datetime,
) -> None:
    queue = dict(manifest.get("queue") or {})
    queue.update(
        {
            "state": "dependency_failed",
            "attention": reason,
            "predecessor_status": predecessor_status,
            "failed_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
    )
    manifest.update(
        {
            "status": status,
            "terminal_outcome": status,
            "finished_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "error": "queued successor dependency failed closed",
            "error_class": "ResidentSubagentDependencyFailure",
            "queue": queue,
        }
    )
    history = list(manifest.get("status_history") or [])
    history.append(
        {
            "status": status,
            "at": now.isoformat(),
            "evidence": reason,
            "predecessor_status": predecessor_status,
        }
    )
    manifest["status_history"] = history[-100:]
    _atomic_json(manifest_path, manifest)


def _is_cross_revision_contract_rejection(manifest: Mapping[str, Any]) -> bool:
    """Recognize the one terminal state an older worker can falsely produce.

    Detached workers retain the Python code loaded when they were launched.  A
    worker from before cross-request queues existed can therefore reject a
    newer, valid authorization contract when it reconciles queues on exit.
    Recovery remains fail closed: only the exact pre-launch rejection shape is
    eligible, and the current runtime must subsequently validate the complete
    authorization contract before this terminal state is removed.
    """

    queue = manifest.get("queue")
    delivery = manifest.get("completion_delivery")
    authorization = (
        queue.get("cross_request_authorization") if isinstance(queue, Mapping) else None
    )
    history = manifest.get("status_history")
    last_history = history[-1] if isinstance(history, list) and history else None
    return bool(
        manifest.get("status") == "failed"
        and manifest.get("terminal_outcome") == "failed"
        and manifest.get("error_class") == "ResidentSubagentDependencyFailure"
        and isinstance(queue, Mapping)
        and queue.get("schema_version") == QUEUE_SCHEMA
        and queue.get("state") == "dependency_failed"
        and queue.get("attention") == "invalid_dependency_contract"
        and queue.get("predecessor_status") == "unknown"
        and queue.get("attempt_count") in {None, 0, "0"}
        and isinstance(delivery, Mapping)
        and delivery.get("status") == "pending"
        and delivery.get("attempt_count") in {None, 0, "0"}
        and isinstance(authorization, Mapping)
        and authorization.get("schema_version")
        == QUEUE_CROSS_REQUEST_AUTHORIZATION_SCHEMA
        and isinstance(last_history, Mapping)
        and last_history.get("status") == "failed"
        and last_history.get("evidence") == "invalid_dependency_contract"
    )


def _restore_cross_revision_queue(
    manifest: dict[str, Any], *, predecessor_status: str, now: datetime
) -> None:
    """Restore a currently validated cross-request queue to pre-launch state."""

    queue = dict(manifest.get("queue") or {})
    queue.update(
        {
            "state": "waiting_predecessor",
            "attention": "dependency_contract_revalidated",
            "predecessor_status": predecessor_status,
            "revalidated_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
    )
    queue.pop("failed_at", None)
    manifest.update(
        {
            "status": "queued",
            "queue": queue,
            "updated_at": now.isoformat(),
        }
    )
    for field in ("terminal_outcome", "finished_at", "error", "error_class"):
        manifest.pop(field, None)
    history = list(manifest.get("status_history") or [])
    history.append(
        {
            "status": "queued",
            "at": now.isoformat(),
            "evidence": "valid_contract_recovered_after_stale_runtime_rejection",
            "predecessor_status": predecessor_status,
        }
    )
    manifest["status_history"] = history[-100:]


def _normalized_queue_predecessor_status(predecessor: Mapping[str, Any]) -> str:
    """Return a canonical managed status without inventing terminal success."""

    status = str(predecessor.get("status") or "").strip().casefold()
    if status in _ACTIVE_STATUSES or status in _TERMINAL_STATUSES or status == "queued":
        return status
    return "unknown"


def reconcile_managed_subagent_queues(
    *,
    project_root: str | Path = ".",
    workspace_root: str | Path | None = "/workspace",
    now: datetime | None = None,
) -> ManagedAgentQueueSweepResult:
    """Launch eligible successors once and fail closed on invalid dependencies.

    The queued manifest is the durable launch intent. A per-successor flock
    serializes observers, while the worker's execution lock prevents duplicate
    Codex execution if a supervisor launch is retried after an ambiguous crash.
    """

    observed_at = now or datetime.now(timezone.utc)
    scanned = waiting = launched = retry_pending = failed_closed = skipped = 0
    paths = _managed_manifest_paths(
        project_root=project_root, workspace_root=workspace_root
    )
    for manifest_path in paths:
        try:
            initial = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            continue
        if not isinstance(initial.get("queue"), Mapping):
            continue
        scanned += 1
        with _queue_lock(manifest_path):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, TypeError, ValueError):
                failed_closed += 1
                continue
            status = str(manifest.get("status") or "")
            recovering_cross_revision = _is_cross_revision_contract_rejection(
                manifest
            )
            if status in _TERMINAL_STATUSES and not recovering_cross_revision:
                skipped += 1
                continue
            if status in {"launching", "running"}:
                pid = manifest.get("pid")
                if isinstance(pid, int) and _pid_matches_manifest(pid, manifest_path):
                    skipped += 1
                    continue
                session_dispatch = manifest.get("session_dispatch")
                if (
                    isinstance(session_dispatch, Mapping)
                    and session_dispatch.get("status") == "accepted"
                ):
                    _queue_terminalize(
                        manifest_path,
                        manifest,
                        status="failed",
                        reason="successor_execution_lost_supervisor_without_terminal_evidence",
                        predecessor_status="completed",
                        now=observed_at,
                    )
                    failed_closed += 1
                    continue
            queue = manifest.get("queue")
            if not isinstance(queue, dict) or queue.get("schema_version") != QUEUE_SCHEMA:
                _queue_terminalize(
                    manifest_path,
                    manifest,
                    status="failed",
                    reason="invalid_queue_contract",
                    predecessor_status="unknown",
                    now=observed_at,
                )
                failed_closed += 1
                continue
            predecessor_run_id = str(queue.get("predecessor_run_id") or "")
            predecessor_path = manifest_path.parent.parent / predecessor_run_id / "manifest.json"
            predecessor_status = "unknown"
            try:
                predecessor = _read_managed_resident_manifest(predecessor_path)
                predecessor_status = _normalized_queue_predecessor_status(predecessor)
                ancestors = _queue_ancestor_ids(
                    manifest_path.parent.parent, predecessor_run_id
                )
                if str(manifest.get("run_id") or manifest_path.parent.name) in ancestors:
                    raise SubagentQueueError("queued dependency cycle reaches successor")
                if queue.get("ancestor_run_ids") != ancestors:
                    raise SubagentQueueError("queued dependency ancestry changed after commit")
                if queue.get("trigger_policy") != QUEUE_TRIGGER_POLICY:
                    raise SubagentQueueError("queued trigger policy is unsupported")
                refs = _queue_predecessor_references(predecessor_path, predecessor)
                if queue.get("predecessor_references") != refs:
                    raise SubagentQueueError("queued predecessor references changed after commit")
                _validate_queue_authorization(
                    predecessor, manifest, manifest_path=manifest_path
                )
            except (SubagentFollowupError, SubagentQueueError, OSError, ValueError) as exc:
                queue["last_validation_error"] = {
                    "error_class": exc.__class__.__name__,
                    "message": " ".join(redact_text(str(exc)).split())[:240],
                    "at": observed_at.isoformat(),
                }
                manifest["queue"] = queue
                if not recovering_cross_revision:
                    _queue_terminalize(
                        manifest_path,
                        manifest,
                        status="failed",
                        reason="invalid_dependency_contract",
                        predecessor_status=predecessor_status,
                        now=observed_at,
                    )
                failed_closed += 1
                continue
            if recovering_cross_revision:
                _restore_cross_revision_queue(
                    manifest,
                    predecessor_status=predecessor_status,
                    now=observed_at,
                )
                queue = dict(manifest["queue"])
            if predecessor_status == "unknown":
                _queue_terminalize(
                    manifest_path,
                    manifest,
                    status="failed",
                    reason="predecessor_status_unknown",
                    predecessor_status=predecessor_status,
                    now=observed_at,
                )
                failed_closed += 1
                continue
            if predecessor_status not in _TERMINAL_STATUSES:
                queue.update(
                    {
                        "state": "waiting_predecessor",
                        "attention": "waiting_for_predecessor",
                        "predecessor_status": predecessor_status,
                        "updated_at": observed_at.isoformat(),
                    }
                )
                manifest["status"] = "queued"
                manifest["queue"] = queue
                manifest["updated_at"] = observed_at.isoformat()
                _atomic_json(manifest_path, manifest)
                waiting += 1
                continue
            if predecessor_status in {"cancelled", "superseded"}:
                _queue_terminalize(
                    manifest_path,
                    manifest,
                    status=predecessor_status,
                    reason=f"predecessor_{predecessor_status}",
                    predecessor_status=predecessor_status,
                    now=observed_at,
                )
                failed_closed += 1
                continue
            if predecessor_status != "completed":
                _queue_terminalize(
                    manifest_path,
                    manifest,
                    status="failed",
                    reason="predecessor_terminal_failure",
                    predecessor_status=predecessor_status,
                    now=observed_at,
                )
                failed_closed += 1
                continue
            result_valid, result_error = _queue_result_is_valid(
                predecessor_path, predecessor
            )
            if not result_valid:
                _queue_terminalize(
                    manifest_path,
                    manifest,
                    status="failed",
                    reason=str(result_error or "predecessor_result_invalid"),
                    predecessor_status=predecessor_status,
                    now=observed_at,
                )
                failed_closed += 1
                continue
            next_attempt_at = _parse_timestamp(queue.get("next_attempt_at"))
            if next_attempt_at is not None and observed_at < next_attempt_at:
                retry_pending += 1
                continue
            attempt = int(queue.get("attempt_count") or 0) + 1
            max_attempts = int(
                queue.get("max_launch_attempts") or _QUEUE_MAX_LAUNCH_ATTEMPTS
            )
            queue.update(
                {
                    "state": "launching",
                    "attention": "none",
                    "attempt_count": attempt,
                    "predecessor_status": predecessor_status,
                    "launch_claimed_at": observed_at.isoformat(),
                    "updated_at": observed_at.isoformat(),
                }
            )
            queue.pop("next_attempt_at", None)
            manifest["status"] = "launching"
            manifest["queue"] = queue
            manifest["updated_at"] = observed_at.isoformat()
            history = list(manifest.get("status_history") or [])
            history.append(
                {
                    "status": "launching",
                    "at": observed_at.isoformat(),
                    "evidence": "predecessor_terminal_success_and_result_validated",
                    "attempt": attempt,
                }
            )
            manifest["status_history"] = history[-100:]
            _atomic_json(manifest_path, manifest)
            try:
                _spawn_managed_supervisor(manifest_path, manifest)
            except Exception as exc:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                queue = dict(manifest.get("queue") or {})
                if attempt >= max_attempts:
                    _queue_terminalize(
                        manifest_path,
                        manifest,
                        status="failed",
                        reason="successor_launch_retry_budget_exhausted",
                        predecessor_status=predecessor_status,
                        now=observed_at,
                    )
                    failed_closed += 1
                else:
                    delay = min(
                        _QUEUE_RETRY_MAX_S,
                        _QUEUE_RETRY_BASE_S * (2 ** max(0, attempt - 1)),
                    )
                    queue.update(
                        {
                            "state": "retry_pending",
                            "attention": "successor_launch_retry_pending",
                            "last_error_class": exc.__class__.__name__,
                            "next_attempt_at": (
                                observed_at + timedelta(seconds=delay)
                            ).isoformat(),
                            "updated_at": observed_at.isoformat(),
                        }
                    )
                    manifest["status"] = "queued"
                    manifest["queue"] = queue
                    manifest["updated_at"] = observed_at.isoformat()
                    _atomic_json(manifest_path, manifest)
                    retry_pending += 1
                continue
            launched += 1
    return ManagedAgentQueueSweepResult(
        scanned=scanned,
        waiting=waiting,
        launched=launched,
        retry_pending=retry_pending,
        failed_closed=failed_closed,
        skipped=skipped,
    )


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
    aggregation = manifest.get("aggregation")
    if isinstance(aggregation, Mapping) and aggregation.get("key"):
        return "aggregation_key", str(aggregation["key"])
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


def _completion_payload(
    manifest: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    rendered = str(payload.get("content") or "").strip()
    relationship = manifest.get("query_relationship")
    if (
        isinstance(relationship, Mapping)
        and relationship.get("classification") == "follow_up"
    ):
        root = _request_ref(relationship, "root_request") or {}
        current = _request_ref(relationship, "current_request") or {}
        reference_line = (
            "Related Discord messages: root request "
            f"{root.get('discord_message_id') or root.get('source_record_id') or 'unknown'}; "
            "current follow-up and delivery target "
            f"{current.get('discord_message_id') or current.get('source_record_id') or 'unknown'}."
        )
        rendered = f"{reference_line}\n\n{rendered}" if rendered else reference_line
    rendered = rendered[:_MAX_COMPLETION_DELIVERY_CHARS]
    return {
        **dict(payload),
        "content": rendered,
        "content_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
    }


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
            "suppressed",
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
            from .timezone import localize_text_timestamps

            launch_provenance = dict(manifest.get("launch_provenance") or {})
            content = localize_text_timestamps(
                content,
                str(launch_provenance.get("timezone_name") or "UTC"),
            )
            delivery["payload"] = _completion_payload(manifest, {
                "content": content,
                "result_kind": result_kind,
                "materialized_at": now.isoformat(),
            })

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
            "The verification outcome is unknown because the resident completion turn produced no "
            "user-facing verification summary; the delegated result is not being treated as proof."
        )
    with _delivery_lock(manifest_path):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload = _completion_payload(
            manifest,
            {
                "content": safe_text,
                "result_kind": "resident_verified_summary",
                "verification_outcome": result.verification_outcome,
                "resident_turn_id": result.turn_id,
                "materialized_at": now.isoformat(),
            },
        )
        safe_text = str(payload["content"])
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
        delivery["payload"] = payload
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
                "The resident could not establish an independent verification turn for delegated "
                f"run {run_id} after bounded retries. The verification outcome is unknown, and the "
                "delegated terminal result is not being treated as proof; operator inspection is required."
            )
            payload = _completion_payload(
                manifest,
                {
                    "content": content,
                    "result_kind": "resident_verification_unavailable",
                    "verification_outcome": "unknown",
                    "materialized_at": now.isoformat(),
                },
            )
            content = str(payload["content"])
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
            delivery["payload"] = payload
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
    delivery_evidence: Mapping[str, Any] | None = None,
) -> None:
    with _delivery_lock(manifest_path):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        delivery = dict(manifest.get("completion_delivery") or {})
        origin = dict(manifest.get("discord_origin") or {})
        expected_conversation_key = str(origin.get("conversation_key") or "")
        evidence = _normalized_discord_delivery_evidence(
            delivery_evidence,
            expected_conversation_key=expected_conversation_key,
            message_ids=message_ids,
        )
        history = list(delivery.get("state_history") or [])
        for rejection in evidence["provider_rejections"]:
            history.append(
                {
                    "status": "rejected",
                    "at": now.isoformat(),
                    "evidence": "provider_rejected_reply_or_thread_target",
                    "attempt_id": delivery.get("attempt_id"),
                    **rejection,
                }
            )
        history.append(
            {
                "status": "delivered",
                "at": now.isoformat(),
                "evidence": (
                    "provider_fallback_message_ids_persisted"
                    if evidence["delivery_mode"] == "fallback_plain"
                    else "provider_reply_message_ids_persisted"
                    if evidence["delivery_mode"] == "reply"
                    else "provider_plain_message_ids_persisted"
                ),
                "attempt_id": delivery.get("attempt_id"),
            }
        )
        delivery.update(
            {
                "status": "delivered",
                "delivered_at": now.isoformat(),
                "discord_message_ids": message_ids,
                "result_kind": result_kind,
                "delivery_evidence": evidence,
                "provider_outcome": "accepted",
                # Discord's returned message ids acknowledge provider
                # acceptance.  They are not evidence that a person saw a
                # notification or rendered message.
                "user_notification_visibility": "unknown",
                "updated_at": now.isoformat(),
                "state_history": history[-20:],
            }
        )
        delivery.pop("claim_state", None)
        manifest["completion_delivery"] = delivery
        _atomic_json(manifest_path, manifest)


def _normalized_discord_delivery_evidence(
    value: Mapping[str, Any] | None,
    *,
    expected_conversation_key: str,
    message_ids: list[str],
) -> dict[str, Any]:
    evidence = dict(value or {})
    recorded_conversation_key = str(
        evidence.get("authoritative_conversation_key") or expected_conversation_key
    )
    evidence_custody_valid = recorded_conversation_key == expected_conversation_key
    mode = str(evidence.get("delivery_mode") or "reply")
    if mode not in {"reply", "fallback_plain", "plain"}:
        mode = "reply"
    rejections: list[dict[str, object]] = []
    raw_rejections = evidence.get("provider_rejections")
    if isinstance(raw_rejections, (list, tuple)):
        for item in raw_rejections:
            if not isinstance(item, Mapping):
                continue
            rejections.append(
                {
                    "outcome": "rejected",
                    "scope": str(item.get("scope") or "unknown"),
                    "error_class": str(item.get("error_class") or "unknown"),
                    "http_status": item.get("http_status"),
                    "discord_error_code": item.get("discord_error_code"),
                }
            )
    return {
        "schema_version": "arnold-discord-delivery-evidence-v1",
        "authoritative_conversation_key": expected_conversation_key,
        "evidence_custody_valid": evidence_custody_valid,
        "delivery_mode": mode,
        "fallback_reason": (
            str(evidence.get("fallback_reason"))
            if evidence.get("fallback_reason")
            else None
        ),
        "provider_outcome": "accepted",
        "provider_message_ids": list(message_ids),
        "provider_rejections": rejections,
        "resolved_channel_id": (
            str(evidence.get("resolved_channel_id"))
            if evidence.get("resolved_channel_id") is not None
            else None
        ),
        "resolved_thread_id": (
            str(evidence.get("resolved_thread_id"))
            if evidence.get("resolved_thread_id") is not None
            else None
        ),
        "user_notification_visibility": "unknown",
    }


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
    if isinstance(exc, _ProviderAcceptanceEvidenceMissing):
        category = "provider_acceptance_unknown"
    elif "reply target" in detail or "snowflake" in detail:
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


def _retry_delivery(
    manifest_path: Path,
    *,
    now: datetime,
    exc: Exception,
    delivery_evidence: Mapping[str, Any] | None = None,
) -> str:
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
        ambiguous_outcome = category in {
            "provider_acceptance_unknown",
            "timeout",
            "network_error",
            "server_error",
        }
        provider_rejected = (
            category == "invalid_reply_target"
            or isinstance(evidence.get("last_http_status"), int)
            and 400 <= int(evidence["last_http_status"]) < 500
        )
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
        if isinstance(delivery_evidence, Mapping):
            raw_rejections = delivery_evidence.get("provider_rejections")
            if isinstance(raw_rejections, (list, tuple)):
                for rejection in raw_rejections:
                    if not isinstance(rejection, Mapping):
                        continue
                    state_history.append(
                        {
                            "status": "rejected",
                            "at": now.isoformat(),
                            "evidence": "provider_rejected_reply_or_thread_target",
                            "attempt_id": delivery.get("attempt_id"),
                            "scope": str(rejection.get("scope") or "unknown"),
                            "error_class": str(
                                rejection.get("error_class") or "unknown"
                            ),
                            "http_status": rejection.get("http_status"),
                            "discord_error_code": rejection.get(
                                "discord_error_code"
                            ),
                        }
                    )
        if ambiguous_outcome:
            state_history.append(
                {
                    "status": "unknown",
                    "at": now.isoformat(),
                    "evidence": "provider_acceptance_outcome_unknown",
                    "attempt_id": delivery.get("attempt_id"),
                }
            )
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
                "provider_outcome": (
                    "unknown"
                    if ambiguous_outcome
                    else "rejected"
                    if provider_rejected
                    else "not_accepted"
                ),
                "user_notification_visibility": "unknown",
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

    fixed_now = now
    reconcile_managed_subagent_queues(
        project_root=project_root,
        workspace_root=workspace_root,
        now=fixed_now,
    )
    paths = _managed_manifest_paths(project_root=project_root, workspace_root=workspace_root)
    delivered = retry_pending = skipped = failed = 0
    for manifest_path in paths:
        if completion_turn_handler is not None:
            completion_claim = _completion_turn_claim(
                manifest_path, now=_delivery_transition_now(fixed_now)
            )
            if completion_claim is not None:
                try:
                    completion_result = await completion_turn_handler(
                        manifest_path, completion_claim
                    )
                except Exception as exc:
                    verification_disposition = _retry_completion_turn(
                        manifest_path,
                        now=_delivery_transition_now(fixed_now),
                        exc=exc,
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
                    now=_delivery_transition_now(fixed_now),
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
        claim = _delivery_claim(
            manifest_path, now=_delivery_transition_now(fixed_now)
        )
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
                now=_delivery_transition_now(fixed_now),
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
            # The originating resident turn added this marker after durable
            # custody.  Terminal outbox delivery removes it before applying
            # the existing completion reaction, including after restart.
            "discord_processing_message_ids": [origin["reply_to_message_id"]],
            "discord_processing_turn_id": str(
                dict(manifest.get("launch_provenance") or {}).get("resident_turn_id") or ""
            ),
            "completion_delivery": True,
            "timezone_name": str(
                dict(manifest.get("launch_provenance") or {}).get("timezone_name") or "UTC"
            ),
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
                suppressed_at = _delivery_transition_now(fixed_now)
                delivery.update(
                    {
                        "status": "suppressed",
                        "claim_state": "suppressed",
                        "last_error": "",
                        "last_error_class": "",
                        "last_error_category": "test_execution_suppressed",
                        "suppression_reason": safety.reason,
                        "updated_at": suppressed_at.isoformat(),
                    }
                )
                history = list(delivery.get("state_history") or [])
                history.append(
                    {
                        "status": "suppressed",
                        "at": suppressed_at.isoformat(),
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
            disposition = _retry_delivery(
                manifest_path,
                now=_delivery_transition_now(fixed_now),
                exc=exc,
                delivery_evidence=(
                    metadata.get("discord_delivery_evidence")
                    if isinstance(
                        metadata.get("discord_delivery_evidence"), Mapping
                    )
                    else None
                ),
            )
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
        if not message_ids:
            # A normal return is not by itself provider-acceptance evidence.
            # Keep the stable nonce and redrive through the normal retry path;
            # Discord can deduplicate an attempt that was accepted but whose
            # response was lost, while the manifest remains truthful meanwhile.
            disposition = _retry_delivery(
                manifest_path,
                now=_delivery_transition_now(fixed_now),
                exc=_ProviderAcceptanceEvidenceMissing(
                    "Discord send returned without provider message ids"
                ),
                delivery_evidence=(
                    metadata.get("discord_delivery_evidence")
                    if isinstance(
                        metadata.get("discord_delivery_evidence"), Mapping
                    )
                    else None
                ),
            )
            retry_pending += int(disposition == "retry_pending")
            failed += int(disposition == "failed")
            continue
        _finish_delivery(
            manifest_path,
            now=_delivery_transition_now(fixed_now),
            message_ids=message_ids,
            result_kind=result_kind,
            delivery_evidence=(
                metadata.get("discord_delivery_evidence")
                if isinstance(metadata.get("discord_delivery_evidence"), Mapping)
                else None
            ),
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
    queue_limit: int = MAX_QUEUE_HOT_CONTEXT_ROWS,
) -> dict[str, Any]:
    """Build the unified managed-agent view used by resident hot context.

    Automatic repair appears here only when the real worker crossed the shared
    supervisor.  Legacy resident manifests remain visible; untracked legacy
    repairs are intentionally not manufactured into this view.
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
            very_legacy = schema == LEGACY_MANAGED_RUN_SCHEMA
            if not very_legacy and not is_managed_manifest(payload):
                continue
            persisted_status = str(payload.get("status") or "unknown")
            pid = payload.get("pid")
            run_kind = str(payload.get("run_kind") or MANAGED_RUN_KIND)
            evidence_class = "canonical"
            if schema == MANAGED_RUN_SCHEMA:
                observed_status, live = shared_observed_status(payload, manifest_path)
                if run_kind.startswith("automatic_"):
                    try:
                        validate_automatic_managed_manifest(
                            payload,
                            manifest_path=manifest_path,
                        )
                    except (TypeError, ValueError):
                        evidence_class = "legacy_noncanonical"
                        observed_status = "noncanonical_legacy"
                        live = False
            else:
                evidence_class = "legacy_compatibility"
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
                    "run_kind": run_kind,
                    "evidence_class": evidence_class,
                    "status": observed_status,
                    "persisted_status": persisted_status,
                    "live": live,
                    "pid": pid,
                    "backend": payload.get("backend"),
                    "model": payload.get("model"),
                    "reasoning_effort": payload.get("reasoning_effort"),
                    "task_kind": payload.get("task_kind"),
                    "description": payload.get("description"),
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
                    # A provider may persist this immutable measurement on the
                    # manifest.  Do not synthesize it from logs or limits.
                    "usage": payload.get("usage"),
                    "manifest_path": str(manifest_path.resolve()),
                    "full_log_path": artifact_path(
                        "full_log_path", str(payload.get("log_path") or "run.log")
                    ),
                    "result_path": artifact_path("result_path", "result.md"),
                    "discord_origin": payload.get("discord_origin"),
                    "launch_provenance": payload.get("launch_provenance"),
                    "completion_delivery": payload.get("completion_delivery"),
                    "status_history": payload.get("status_history"),
                    "terminal_outcome": payload.get("terminal_outcome"),
                    "worker_pid": payload.get("worker_pid"),
                    "retry_of_run_id": payload.get("retry_of_run_id"),
                    "parent_run_id": payload.get("parent_run_id"),
                    "lineage_key": payload.get("lineage_key"),
                    "links": payload.get("links"),
                    "query_relationship": payload.get("query_relationship"),
                    "aggregation": payload.get("aggregation"),
                    "queue": payload.get("queue"),
                    "queue_links": payload.get("queue_links"),
                }
            )
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    running = [row for row in rows if row["live"]]
    queued_all = [
        row
        for row in rows
        if isinstance(row.get("queue"), Mapping)
        and row["status"] not in _TERMINAL_STATUSES
        and not row["live"]
    ]
    queued = queued_all[: max(0, queue_limit)]
    terminal = [
        row
        for row in rows
        if not row["live"]
        and not (
            isinstance(row.get("queue"), Mapping)
            and row["status"] not in _TERMINAL_STATUSES
        )
    ]
    bounded_recent_limit = max(0, recent_limit)
    recent = terminal[:bounded_recent_limit]
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
        "scope": "unified resident and automatic-repair managed agents",
        "run_root": str((Path(project_root).resolve() / DEFAULT_MANAGED_RUN_ROOT)),
        "running": running,
        "queued": queued,
        "queued_count": len(queued_all),
        "queued_omitted_count": max(0, len(queued_all) - len(queued)),
        "queue_attention_count": sum(
            1
            for row in rows
            if isinstance(row.get("queue"), Mapping)
            and str(row["queue"].get("attention") or "none")
            not in {"none", "waiting_for_predecessor"}
        ),
        "recent": recent,
        "running_count": len(running),
        "recent_count": len(recent),
        "recent_total_count": len(terminal),
        "recent_omitted_count": max(0, len(terminal) - len(recent)),
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
    description: str | None = None,
    aggregation_role: str = "synthesis_delivery_owner",
    synthesis_group: str | None = None,
    toolsets: str | None = None,
    project_dir: str | None = None,
    backend: str = "codex",
    background: bool = True,
    model: str | None = None,
    reasoning_effort: str | None = None,
    task_kind: DelegatedTaskKind = DEFAULT_DELEGATED_TASK_KIND,
    work_intent: DelegatedWorkIntent = DEFAULT_DELEGATED_WORK_INTENT,
    difficulty: int = DEFAULT_DELEGATED_DIFFICULTY,
    request_id: str | None = None,
    launch_origin: Mapping[str, Any] | None = None,
    retry_of_run_id: str | None = None,
    query_relationship: Mapping[str, Any] | None = None,
    depends_on_run_id: str | None = None,
    queue_max_launch_attempts: int = _QUEUE_MAX_LAUNCH_ATTEMPTS,
) -> SubagentResult:
    """Dispatch ``task`` through the resident-owned delegated-agent seam.

    Managed Codex is the canonical resident path.  ``backend="hermes"`` is an
    explicit compatibility mode for old synchronous callers; its stdout carries
    the final response and it does not claim the managed lifecycle schema.
    """
    if len(task) > MAX_DELEGATED_TASK_CHARS:
        raise ValueError(
            f"delegated task exceeds {MAX_DELEGATED_TASK_CHARS} characters; "
            "store large evidence durably and pass paths/routes"
        )
    if depends_on_run_id and backend != "codex":
        raise ValueError("queued successors require the durable Codex managed lifecycle")
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
            description=description,
            aggregation_role=aggregation_role,
            synthesis_group=synthesis_group,
            project_dir=project_dir,
            model=model or route.model,
            reasoning_effort=selected_effort,
            task_kind=route.task_kind,
            work_intent=work_intent,
            difficulty=route.difficulty,
            route_class=(
                "explicit_override"
                if model is not None or reasoning_effort is not None
                else route.route_class
            ),
            request_id=request_id,
            launch_origin=launch_origin,
            retry_of_run_id=retry_of_run_id,
            query_relationship=query_relationship,
            depends_on_run_id=depends_on_run_id,
            queue_max_launch_attempts=queue_max_launch_attempts,
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
        handle.write(
            _delivery_prompt(
                task,
                str(compatibility_provenance.get("timezone_name") or "UTC"),
                task_kind=task_kind,
                work_intent=work_intent,
                context_directory=_delegated_context_directory(
                    project_root=Path(project_dir or Path.cwd()).resolve(),
                    provenance=compatibility_provenance,
                ),
            )
        )
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
    launch.add_argument(
        "--description",
        help="Concise one-line human-readable description of the delegated work",
    )
    launch.add_argument(
        "--aggregation-role",
        choices=sorted(AGGREGATION_ROLES),
        default="synthesis_delivery_owner",
    )
    launch.add_argument("--synthesis-group")
    launch.add_argument("--project-dir")
    launch.add_argument("--model")
    launch.add_argument(
        "--reasoning-effort", choices=sorted(_VALID_DELEGATED_EFFORTS)
    )
    launch.add_argument("--task-kind", choices=DELEGATED_TASK_KINDS, default=DEFAULT_DELEGATED_TASK_KIND)
    launch.add_argument(
        "--work-intent",
        choices=DELEGATED_WORK_INTENTS,
        default=DEFAULT_DELEGATED_WORK_INTENT,
    )
    launch.add_argument("--difficulty", type=int, default=DEFAULT_DELEGATED_DIFFICULTY)
    launch.add_argument("--request-id")
    launch.add_argument("--retry-of-run-id")
    followup = sub.add_parser(
        "follow-up",
        aliases=["followup"],
        help=(
            "Durably continue one resident-managed run lineage; active parents are "
            "safely interrupted and terminal parents resume their persistent Codex session"
        ),
    )
    followup.add_argument("--run-id", required=True)
    message_source = followup.add_mutually_exclusive_group(required=True)
    message_source.add_argument("--message")
    message_source.add_argument("--message-file")
    followup.add_argument("--project-dir")
    followup.add_argument(
        "--idempotency-key",
        help="Stable retry key; reuse is allowed only with identical message and custody",
    )
    followup.add_argument(
        "--aggregation-role",
        choices=sorted(AGGREGATION_ROLES),
        default="synthesis_delivery_owner",
    )
    followup.add_argument("--synthesis-group")
    return parser


def _local_launch_task(args: argparse.Namespace) -> str:
    if args.task_file:
        try:
            return Path(args.task_file).expanduser().read_text(encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"cannot read --task-file: {exc}") from exc
    return str(args.task or "")


def _local_followup_message(args: argparse.Namespace) -> str:
    if args.message_file:
        try:
            return Path(args.message_file).expanduser().read_text(encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"cannot read --message-file: {exc}") from exc
    return str(args.message or "")


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
                description=args.description,
                aggregation_role=args.aggregation_role,
                synthesis_group=args.synthesis_group,
                project_dir=args.project_dir,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                task_kind=args.task_kind,
                work_intent=args.work_intent,
                difficulty=args.difficulty,
                request_id=args.request_id,
                retry_of_run_id=args.retry_of_run_id,
            )
        )
        print(json.dumps(result.__dict__, sort_keys=True))
        return 0 if result.ok else 1
    if args.action in {"follow-up", "followup"}:
        message = _local_followup_message(args).strip()
        try:
            result = follow_up_managed_subagent(
                run_id=args.run_id,
                message=message,
                project_dir=args.project_dir,
                workspace_root=None,
                idempotency_key=args.idempotency_key,
                aggregation_role=args.aggregation_role,
                synthesis_group=args.synthesis_group,
            )
        except (SubagentFollowupError, DelegationProvenanceError, OSError) as exc:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "resident_followup_rejected",
                        "message": str(exc),
                    },
                    sort_keys=True,
                )
            )
            return 2
        print(json.dumps(result.__dict__, sort_keys=True))
        return 0
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
