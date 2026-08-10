"""Megaplan process policy and compatibility exports.

Public surface
--------------
The runtime-neutral ``spawn``, ``spawn_async``, and ``kill_group`` callables
are imported unchanged from :mod:`arnold.runtime.process`.  This module owns
only Megaplan-specific engine-root, tmux, orphan, and custody policy.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

from arnold.runtime.process import kill_group, spawn, spawn_async

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def megaplan_engine_root() -> Path:
    """Return the import root for the currently running Megaplan package.

    Megaplan can drive a target checkout that also provides an ``arnold``
    package.  Deriving the engine root from that sibling package lets the
    target checkout replace the pinned Megaplan runtime in child processes.
    Anchor the root to this module instead so subprocesses inherit the same
    Megaplan implementation as their parent.
    """

    return Path(__file__).resolve().parents[3]


def megaplan_engine_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Return an env that resolves this engine's Python packages."""
    root = str(megaplan_engine_root())
    env = dict(os.environ if base_env is None else base_env)
    current = env.get("PYTHONPATH")
    parts = [part for part in (current or "").split(os.pathsep) if part]
    env["PYTHONPATH"] = os.pathsep.join([root, *[part for part in parts if part != root]])
    env["MEGAPLAN_ENGINE_ROOT"] = root
    return env


# ---------------------------------------------------------------------------
# Orphan detection and Tmux session management
# ---------------------------------------------------------------------------


class OrphanDetectedError(Exception):
    """Raised when a tmux session survives teardown and cannot be reaped."""

    def __init__(
        self,
        sessions: list[str],
        pids: list[str],
        remediation: str,
    ) -> None:
        super().__init__(
            f"Orphaned tmux session(s) detected: {sessions}. "
            f"Live PIDs: {pids}. {remediation}"
        )
        self.sessions = sessions
        self.pids = pids
        self.remediation = remediation


def tmux_socket_for(session_name: str) -> str:
    """Return the private tmux socket name for a Shannon session."""
    override = os.environ.get("SHANNON_TMUX_SOCKET")
    if override:
        return override
    return f"mp-{session_name}"


class TmuxSession:
    """Handle for a single tmux session, keyed by name."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.socket = tmux_socket_for(name)

    def teardown(self) -> None:
        """Kill the tmux session and its private server. Idempotent."""
        try:
            result = subprocess.run(
                ["tmux", "-L", self.socket, "kill-session", "-t", self.name],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            logger.debug(
                "TmuxSession.teardown(%r): tmux not found on PATH",
                self.name,
            )
            return

        if result.returncode == 0:
            logger.debug("TmuxSession.teardown(%r): session killed", self.name)
        else:
            logger.debug(
                "TmuxSession.teardown(%r): tmux returned %d (already gone?)",
                self.name,
                result.returncode,
            )
        try:
            subprocess.run(
                ["tmux", "-L", self.socket, "kill-server"],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            pass

        # Reap the private server so no idle daemon lingers (exit-empty off).
        try:
            subprocess.run(
                ["tmux", "-L", self.socket, "kill-server"],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            pass

    def exists(self) -> bool:
        """Return True iff the tmux session is currently live."""
        try:
            result = subprocess.run(
                ["tmux", "-L", self.socket, "has-session", "-t", self.name],
                check=False,
                capture_output=True,
            )
        except FileNotFoundError:
            return False
        return result.returncode == 0


def detect_orphans(session_pattern: str) -> list[str]:
    """Return tmux session names matching *session_pattern* via fnmatch."""
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return []

    if result.returncode != 0:
        return []

    sessions: list[str] = []
    for line in result.stdout.strip().splitlines():
        name = line.strip()
        if name and fnmatch.fnmatch(name, session_pattern):
            sessions.append(name)
    return sessions


def pane_pids(session_name: str) -> list[str]:
    """Return the PIDs of every pane in *session_name*."""
    try:
        result = subprocess.run(
            [
                "tmux",
                "-L",
                tmux_socket_for(session_name),
                "list-panes",
                "-t",
                session_name,
                "-F",
                "#{pane_pid}",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return []

    if result.returncode != 0:
        return []

    return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Validation process custody receipts (Steps 16 and 17)
# ---------------------------------------------------------------------------

#: Schema/version stamp carried by every custody receipt.
PROCESS_CUSTODY_RECEIPT_SCHEMA = "megaplan.process_custody_receipt"
PROCESS_CUSTODY_RECEIPT_VERSION = 1

#: Adoption/termination policies recorded on a receipt.
CUSTODY_ADOPTION_POLICY_ADOPT = "adopt"
CUSTODY_ADOPTION_POLICY_TERMINATE = "terminate"
CUSTODY_ADOPTION_POLICIES: frozenset[str] = frozenset(
    {CUSTODY_ADOPTION_POLICY_ADOPT, CUSTODY_ADOPTION_POLICY_TERMINATE}
)

#: Lifecycle cutover triggers that must resolve to an adopt-or-terminate decision.
CUSTODY_CUTOVER_TRIGGERS: tuple[str, ...] = (
    "exit",
    "restart",
    "timeout",
    "signal",
    "parent_death",
    "cutover",
)

CutoverAction = Literal["adopt", "terminate"]
CutoverTrigger = Literal["exit", "restart", "timeout", "signal", "parent_death", "cutover"]


class DuplicateLaunchError(Exception):
    """Raised when a duplicate launch targets the same custody slot.

    A custody slot is keyed by ``(command_hash, receipt_path)``.  A second
    launch that collides with a slot still held by a live receipt is rejected
    so an uncontrolled twin validation process cannot displace or shadow the
    original job while preserving a misleading validation outcome.
    """


def command_hash(argv: Sequence[str]) -> str:
    """Return a deterministic SHA-256 over an argv list (``sha256:`` prefix).

    Mirrors the managed-agent command hash so custody receipts are stable
    across the launcher and the custody registry, independent of working
    directory, labels, or liveness.
    """
    if not isinstance(argv, (list, tuple)):
        argv = list(argv)
    digest = hashlib.sha256(
        json.dumps(list(argv), separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def coordinator_birth_identity() -> dict[str, str]:
    """Return the current coordinator process-birth identity.

    Best-effort snapshot of hostname, PID, and boot id.  This identity is
    *provenance* for custody — it records who launched the job — and is never
    authority: authority flows from the custody lease / Run Authority grant
    (Step 10), not from birth identity, labels, liveness, or WBC receipts.
    """
    identity: dict[str, str] = {"host": "", "pid": str(os.getpid()), "boot_id": ""}
    try:
        import socket

        identity["host"] = socket.gethostname()
    except Exception:  # pragma: no cover - best effort
        pass
    try:
        identity["boot_id"] = (
            Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
        )
    except Exception:  # pragma: no cover - best effort
        pass
    return identity


@dataclass(frozen=True)
class ProcessCustodyReceipt:
    """Immutable record binding a validation process under custody to its launcher.

    Records the durable launch provenance — coordinator PID and birth identity,
    process group, command hash, receipt path, adoption/termination policy, and
    a deterministic log path — so lifecycle cutovers can adopt or terminate the
    EXACT job this run launched.  The birth identity and command hash are
    provenance for custody, never authority (see coordinator_birth_identity).
    """

    receipt_id: str
    coordinator_pid: int
    coordinator_host: str
    coordinator_boot_id: str
    process_group_id: int | None
    command: tuple[str, ...]
    command_hash: str
    receipt_path: str
    adoption_policy: str
    deterministic_log_path: str
    validation_outcome: str
    launched_at: str
    schema: str = PROCESS_CUSTODY_RECEIPT_SCHEMA
    schema_version: int = PROCESS_CUSTODY_RECEIPT_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.receipt_id, str) or not self.receipt_id.strip():
            raise ValueError("receipt_id must be a non-empty string")
        if not isinstance(self.coordinator_pid, int) or isinstance(self.coordinator_pid, bool):
            raise ValueError("coordinator_pid must be an int")
        if not isinstance(self.coordinator_host, str):
            raise ValueError("coordinator_host must be a string")
        if not isinstance(self.coordinator_boot_id, str):
            raise ValueError("coordinator_boot_id must be a string")
        if not isinstance(self.command, tuple):
            raise ValueError("command must be a tuple")
        if not isinstance(self.command_hash, str) or not self.command_hash.strip():
            raise ValueError("command_hash must be a non-empty string")
        if not isinstance(self.receipt_path, str) or not self.receipt_path.strip():
            raise ValueError("receipt_path must be a non-empty string")
        if self.adoption_policy not in CUSTODY_ADOPTION_POLICIES:
            raise ValueError(
                f"adoption_policy must be one of {sorted(CUSTODY_ADOPTION_POLICIES)}"
            )
        if not isinstance(self.deterministic_log_path, str) or not self.deterministic_log_path.strip():
            raise ValueError("deterministic_log_path must be a non-empty string")
        if not isinstance(self.validation_outcome, str):
            raise ValueError("validation_outcome must be a string")
        if not isinstance(self.launched_at, str) or not self.launched_at.strip():
            raise ValueError("launched_at must be a non-empty string")

    @property
    def custody_key(self) -> tuple[str, str]:
        """Return the ``(command_hash, receipt_path)`` slot key."""
        return (self.command_hash, self.receipt_path)

    @property
    def birth_identity(self) -> dict[str, str]:
        """Return the coordinator birth-identity dict."""
        return {
            "host": self.coordinator_host,
            "pid": str(self.coordinator_pid),
            "boot_id": self.coordinator_boot_id,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "coordinator_pid": self.coordinator_pid,
            "coordinator_host": self.coordinator_host,
            "coordinator_boot_id": self.coordinator_boot_id,
            "process_group_id": self.process_group_id,
            "command": list(self.command),
            "command_hash": self.command_hash,
            "receipt_path": self.receipt_path,
            "adoption_policy": self.adoption_policy,
            "deterministic_log_path": self.deterministic_log_path,
            "validation_outcome": self.validation_outcome,
            "launched_at": self.launched_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ProcessCustodyReceipt:
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict")
        return cls(
            receipt_id=payload.get("receipt_id", ""),
            coordinator_pid=int(payload.get("coordinator_pid", 0)),
            coordinator_host=payload.get("coordinator_host", ""),
            coordinator_boot_id=payload.get("coordinator_boot_id", ""),
            process_group_id=(
                int(payload["process_group_id"])
                if payload.get("process_group_id") is not None
                else None
            ),
            command=tuple(payload.get("command") or ()),
            command_hash=payload.get("command_hash", ""),
            receipt_path=payload.get("receipt_path", ""),
            adoption_policy=payload.get("adoption_policy", ""),
            deterministic_log_path=payload.get("deterministic_log_path", ""),
            validation_outcome=payload.get("validation_outcome", ""),
            launched_at=payload.get("launched_at", ""),
        )


class ProcessCustodyRegistry:
    """In-memory registry of validation processes under custody.

    Enforces duplicate-launch rejection: a second launch whose
    ``(command_hash, receipt_path)`` collides with a slot still held by a live
    receipt raises :class:`DuplicateLaunchError`.  ``release`` clears a slot
    when its job exits cleanly so a legitimate same-key relaunch is permitted.
    """

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], ProcessCustodyReceipt] = {}

    @property
    def live_keys(self) -> tuple[tuple[str, str], ...]:
        return tuple(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def register(self, receipt: ProcessCustodyReceipt) -> ProcessCustodyReceipt:
        key = receipt.custody_key
        existing = self._entries.get(key)
        if existing is not None:
            raise DuplicateLaunchError(
                "duplicate launch rejected: command_hash="
                f"{receipt.command_hash} receipt_path={receipt.receipt_path!r} "
                f"is already held by receipt_id={existing.receipt_id!r}"
            )
        self._entries[key] = receipt
        logger.debug(
            "process_custody: registered receipt_id=%s command_hash=%s pgid=%s",
            receipt.receipt_id,
            receipt.command_hash,
            receipt.process_group_id,
        )
        return receipt

    def find(self, command_hash: str, receipt_path: str) -> ProcessCustodyReceipt | None:
        return self._entries.get((command_hash, receipt_path))

    def release(self, receipt: ProcessCustodyReceipt) -> None:
        self._entries.pop(receipt.custody_key, None)


@dataclass(frozen=True)
class CutoverDecision:
    """Resolved adopt-or-terminate decision for a lifecycle cutover."""

    action: CutoverAction
    trigger: CutoverTrigger
    receipt: ProcessCustodyReceipt
    preserved_outcome: str
    reason: str


def resolve_cutover(
    receipt: ProcessCustodyReceipt,
    *,
    trigger: str,
    live_command_hash: str | None = None,
    live_process_group_id: int | None = None,
) -> CutoverDecision:
    """Decide whether to adopt or terminate the recorded job on a cutover.

    On a clean ``exit`` the job is already gone, so there is nothing to reap:
    the recorded validation outcome is preserved as-is (an adopt with no live
    process to take over).

    For every other cutover (restart, timeout, signal, parent death, runtime
    cutover) the decision adopts the job ONLY when the live process is the
    EXACT recorded job (same command_hash AND same process_group_id) and the
    receipt's adoption policy permits adoption.  Otherwise the recorded
    process group is terminated to prevent an orphaned validation job, while
    the original recorded validation outcome is preserved verbatim.

    The ``live_*`` parameters are observations of the currently-running
    process; they are never authority.  Authority to act comes from the
    receipt's durable launch provenance (this run launched that process group).
    """
    if trigger not in CUSTODY_CUTOVER_TRIGGERS:
        raise ValueError(f"unknown cutover trigger {trigger!r}")
    if trigger == "exit":
        return CutoverDecision(
            action="adopt",
            trigger=trigger,  # type: ignore[arg-type]
            receipt=receipt,
            preserved_outcome=receipt.validation_outcome,
            reason="clean exit: job already gone, recorded outcome preserved",
        )
    exact = (
        live_command_hash is not None
        and live_command_hash == receipt.command_hash
        and live_process_group_id is not None
        and live_process_group_id == receipt.process_group_id
        and receipt.adoption_policy == CUSTODY_ADOPTION_POLICY_ADOPT
    )
    if exact:
        return CutoverDecision(
            action="adopt",
            trigger=trigger,  # type: ignore[arg-type]
            receipt=receipt,
            preserved_outcome=receipt.validation_outcome,
            reason=(
                "exact job provenance match (command_hash + process_group_id) "
                "with adopt policy: retain ownership and preserve outcome"
            ),
        )
    return CutoverDecision(
        action="terminate",
        trigger=trigger,  # type: ignore[arg-type]
        receipt=receipt,
        preserved_outcome=receipt.validation_outcome,
        reason=(
            f"live process is not the exact recorded job (trigger={trigger}): "
            "terminate the recorded process group and preserve the original outcome"
        ),
    )


def apply_cutover_decision(
    decision: CutoverDecision,
    *,
    process: Any | None = None,
) -> CutoverDecision:
    """Execute a cutover decision.

    ``adopt``: no destructive action — ownership of the exact job is retained.

    ``terminate``: reap the recorded process group via :func:`kill_group`, but
    ONLY when an explicit process handle is supplied.  Per the fail-closed
    custody invariant, a missing or ambiguous process handle never authorizes
    a signal: the decision is returned unchanged so the caller can supply exact
    provenance.  The original recorded validation outcome is always preserved.
    """
    if decision.action == "terminate" and process is not None:
        kill_group(
            process,
            label=(
                f"custody-cutover:{decision.receipt.receipt_id}:{decision.trigger}"
            ),
        )
    return decision


__all__ = [
    "spawn",
    "spawn_async",
    "kill_group",
    "OrphanDetectedError",
    "TmuxSession",
    "detect_orphans",
    "pane_pids",
    "tmux_socket_for",
    # Process custody (Steps 16 and 17)
    "PROCESS_CUSTODY_RECEIPT_SCHEMA",
    "PROCESS_CUSTODY_RECEIPT_VERSION",
    "CUSTODY_ADOPTION_POLICY_ADOPT",
    "CUSTODY_ADOPTION_POLICY_TERMINATE",
    "CUSTODY_ADOPTION_POLICIES",
    "CUSTODY_CUTOVER_TRIGGERS",
    "DuplicateLaunchError",
    "command_hash",
    "coordinator_birth_identity",
    "ProcessCustodyReceipt",
    "ProcessCustodyRegistry",
    "CutoverDecision",
    "resolve_cutover",
    "apply_cutover_decision",
]
