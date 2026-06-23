You are a DeepSeek subagent auditing overlap between the proposed AgentBox plan and existing Megaplan functionality. The brief embeds local file excerpts because you do not have filesystem tools. Return: existing functionality reusable directly, functionality needing extraction/generalization, missing pieces, risks/gotchas, and a recommended first implementation slice. Keep under 900 words and cite file names/sections.\nFocus only on the Guardian daemon: periodic checks, safe actions, unblocking, operation classification, notifications, and approval boundaries.


--- FILE: docs/agentbox-persistent-machine-plan.md (1,120p) ---
# AgentBox Persistent Machine Plan

## Goal

Build a persistent remote agent machine that can host many repositories, receive selected credentials from the user's laptop, launch and supervise many concurrent coding operations, and expose the whole system through a resident Discord control plane.

This is broader than the current Megaplan Cloud worker. Megaplan Cloud is a remote runner for plans/chains. AgentBox is a remote development and agent operations machine.

The short version:

- the user can spin up Megaplan plans or chains on the machine;
- each run gets an isolated worktree, branch, tmux session, logs, and operation record;
- a **Guardian** checks all active operations every `X` minutes and safely keeps them moving;
- a **Discord Operator** starts on user messages, has access to AgentBox state/tools, and can launch or inspect work on demand;
- both actors use the same operation registry and safety/approval system.

The core constraint is:

- one persistent machine;
- many repos on that machine;
- one canonical repo checkout or bare repo per source repo;
- one git worktree per operation per repo;
- one tmux/session/process group per operation;
- one Guardian daemon supervising all known operations;
- one Discord-triggered Operator agent for interactive control;
- Discord as the primary human control surface.

## Resident Actors

AgentBox has two primary resident actors. They share the same state, tools, and safety policy, but they wake up for different reasons.

### Guardian

The Guardian is a long-running supervisor daemon. It wakes on a fixed cadence, for example every 5, 10, or 15 minutes, and checks every active operation.

Responsibilities:

- scan the operation registry;
- inspect tmux/process liveness;
- inspect Megaplan plan or chain status;
- read recent logs and structured state;
- classify operations as running, stale, blocked, failed, completed, or awaiting approval;
- restart a missing runner when the operation type has a known-safe restart path;
- advance a chain when the next step is unambiguous;
- file or update pending approvals for risky actions;
- notify Discord when a run blocks, fails, completes, or needs human input;
- update operation state and health summaries.

The Guardian should not silently make product decisions, resolve merge conflicts, delete worktrees, merge PRs, or accept quality debt. Those become explicit pending approvals.

### Discord Operator

The Discord Operator is an on-demand agent launched by Discord messages. It is the interactive control plane.

Responsibilities:

- answer "what is running?";
- launch a Megaplan plan or chain in a fresh worktree;
- launch Codex, Claude, subagent, shell, or test operations;
- inspect logs and summarize failures;
- ask the Guardian what is stuck;
- approve or reject pending actions;
- stop, restart, or clean up operations when authorized;
- inspect repo/worktree/branch state;
- push branches or open PRs when authorized.

The Operator should have access to all AgentBox data and tools, but it should still go through the same safety policy as the Guardian. Discord messages are the trigger, not a bypass.

### Shared State

Both actors depend on the same durable records:

```text
operation id
operation kind
repo(s)
worktree(s)
branch(es)
tmux session
command
log path
current status
last check timestamp
pending approvals
Discord conversation/thread/message ids
PR/CI metadata
```

This operation registry is the center of the system. The Guardian is scheduled/autonomous; the Discord Operator is user-triggered/interactive.

## Recommendation

Use a Hetzner VM or dedicated server as the primary target. Keep Railway support for simpler one-off hosted runners, but do not force the full resident-machine model into Railway's persistent-container model.

Start with a Hetzner `CX53`-class box for the prototype:

- 16 vCPU
- 32 GB RAM
- 320 GB disk
- enough to validate several concurrent agents, tests, and repos

If the workload saturates shared CPU or disk, move the same bootstrap to a dedicated or auction server. The design should make host migration boring.

## Target Layout

```text
/workspace
  /repos
    /megaplan.git
    /reigh-app.git
    /reigh-worker.git

  /worktrees
    /op-20260623-foo
      /megaplan
      /reigh-app
    /op-20260623-bar
      /megaplan

  /runs

--- FILE: docs/agentbox-persistent-machine-plan.md (470,510p) ---
- existing subagent/Hermes conventions;
- Rover supported-agent wrappers;
- OpenACP protocol ideas.

### 8. Guardian Daemon

Purpose: continuously supervise operations and the machine.

Build:

- periodic status loop;
- classify operations as running, waiting, blocked, failed, completed, stale;
- detect dead tmux sessions;
- detect stuck logs/no heartbeat;
- detect dirty/unpushed repos;
- disk/RAM/process pressure checks;
- safe restart/continue policy;
- pending approval queue;
- Discord notifications.

Safe actions:

- summarize;
- collect logs;
- restart a known-safe missing runner;
- continue a Megaplan chain if the next step is unambiguous;
- notify Discord.

Unsafe actions requiring confirmation:

- delete worktrees;
- reset branches;
- resolve merge conflicts;
- merge PRs;
- kill unknown processes;
- push or publish sensitive branches when policy requires approval.

Reuse:

- `arnold_pipelines/megaplan/cloud/supervise.py`
- `arnold_pipelines/megaplan/supervisor/*`

--- FILE: arnold_pipelines/megaplan/cloud/supervise.py (1,260p) ---
"""Cloud chain supervisor — one-shot tick logic.

The supervisor observes a chain and makes safe progress decisions without
human approval.  It may restart missing runners and surface recoverable
blockers but must not invent approvals or force destructive git operations.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path, PurePosixPath
from typing import Any


# ---------------------------------------------------------------------------
# Shared command helpers (imported from cli to keep session/log/env/quotes
# consistent across all entry points).
# ---------------------------------------------------------------------------

def _chain_tick_command(remote_spec_path: str, *, one_shot: bool = False) -> str:
    """Canonical ``megaplan chain start`` command string.

    session name, log path, trusted env, and quoting are shared with
    ``_run_chain_wrapper()`` via the same helper in ``megaplan.cloud.cli``.

    **M5d boundary note:** This function lives in the cloud tier, which is a
    long-lived host *above* the supervisor tier.  Cloud wraps the supervisor
    as a tick host and is explicitly anti-scope for M5d — it continues to
    construct and execute ``megaplan chain start`` commands regardless of
    whether the chain runner routes through the old engine or the new
    ``MEGAPLAN_SUPERVISOR_TIER=1`` path.  Cloud is not ported in M5d.
    """
    from arnold_pipelines.megaplan.cloud.cli import _chain_start_command as _cmd

    return _cmd(remote_spec_path, one_shot=one_shot)


def _remote_sync_refresh_command(
    workspace: str,
    remote_spec: str,
    *,
    branch: str | None = None,
    pr_number: int | None = None,
    extra_repos: list[str] | None = None,
    resolved_workspace: str | None = None,
    chain_session: str | None = None,
) -> str:
    """Construct a remote Python one-liner that calls ``_capture_sync_state``
    on the cloud runner.

    Every value interpolated into the Python snippet is a Python literal
    (via :func:`json.dumps` or :func:`repr`) — **not** :func:`shlex.quote`,
    which would produce bare identifiers instead of string literals.
    ``shlex.quote`` is used only for shell boundaries (``cd <workspace>``,
    ``python3 -c <snippet>``).
    """
    snippet = (
        "from arnold_pipelines.megaplan.chain import _capture_sync_state, ChainState, save_chain_state, load_chain_state; "
        "from pathlib import Path; "
        "_capture_sync_state("
        f"Path({json.dumps(workspace)}), Path({json.dumps(remote_spec)}), "
        f"branch={json.dumps(branch) if branch is not None else 'None'}, "
        f"pr_number={repr(pr_number)}, "
        f"extra_repos={json.dumps(extra_repos) if extra_repos is not None else 'None'}); "
    )
    # Persist resolved workspace and session into remote chain state so
    # subsequent status reads pick them up even without marker/chain_state
    # pre-population.
    if resolved_workspace or chain_session:
        snippet += (
            "s = load_chain_state(Path({})); ".format(json.dumps(remote_spec))
        )
        if resolved_workspace:
            snippet += (
                "s.resolved_workspace = {}; ".format(json.dumps(resolved_workspace))
            )
        if chain_session:
            snippet += (
                "s.chain_session = {}; ".format(json.dumps(chain_session))
            )
        snippet += (
            "save_chain_state(Path({}), s)".format(json.dumps(remote_spec))
        )
    return f"cd {shlex.quote(workspace)} && python3 -c {shlex.quote(snippet)}"


def _remote_pr_state_command(workspace: str, pr_number: int) -> str:
    """Return a shell command that probes the remote PR merge state."""
    return (
        f"cd {shlex.quote(workspace)} && "
        f"gh pr view {pr_number} --json state --jq .state 2>/dev/null "
        f"|| echo unknown"
    )


# ---------------------------------------------------------------------------
# Tick report builder
# ---------------------------------------------------------------------------

def _tick_report(
    *,
    success: bool,
    event: str,
    spec: str,
    effective_status: str,
    next_action: str,
    acted: bool,
    refused_reason: str | None,
    runner: dict[str, Any],
    sync: dict[str, Any],
    pr: dict[str, Any],
    logs: dict[str, Any],
    sync_refresh: dict[str, Any] | None = None,
    provider_consistency: dict[str, Any] | None = None,
    extra_repo_sync: list[dict[str, Any]] | None = None,
    human_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical supervisor tick report dict."""
    report: dict[str, Any] = {
        "success": success,
        "event": event,
        "spec": spec,
        "effective_status": effective_status,
        "next_action": next_action,
        "acted": acted,
        "refused_reason": refused_reason,
        "runner": runner,
        "sync": sync,
        "pr": pr,
        "logs": logs,
    }
    if sync_refresh is not None:
        report["sync_refresh"] = sync_refresh
    if provider_consistency is not None:
        report["provider_consistency"] = provider_consistency
    if extra_repo_sync is not None:
        report["extra_repo_sync"] = extra_repo_sync
    if human_verification is not None:
        report["human_verification"] = human_verification
    return report


# ---------------------------------------------------------------------------
# Safe action policy
# ---------------------------------------------------------------------------

# Statuses the supervisor will **never** mutate.
READ_ONLY_STATUSES = frozenset({
    "running",
    "complete",
    "human_prerequisite",
    "quality_gate",
})

# Statuses that trigger a read-only refusal (no mutation).
BLOCKED_REFUSAL_REASONS: dict[str, str] = {
    "human_prerequisite": "human prerequisite policy is 'required' and unmet; "
    "a human operator must resolve it via `megaplan user-action resolve` "
    "or `megaplan chain override`",
    "quality_gate": "validation policy is 'required' and quality gate is failing; "
    "a human operator must resolve the blocker or accept with debt",
}


# ---------------------------------------------------------------------------
# Main tick logic
# ---------------------------------------------------------------------------

def cloud_supervise_tick(
    root: Path,
    args: argparse.Namespace,
    spec: Any,
    provider: Any,
) -> dict[str, Any]:
    """Run a single supervisor tick and return a structured report.

    (a) Read chain status via ``cloud_chain_status_payload()``.
    (b) Refresh branch/PR/extra-repo sync (before any decisions).
    (c) Re-read ``cloud_chain_status_payload()``.
    (d) Block if provider consistency is mismatched.
    (e) Map refreshed ``effective_status`` to safe actions.
    (f) Execute only safe mutations.
    (g) Produce tick report with sync_refresh, provider_consistency,
        and extra_repo_sync always included.
    """
    # ── deferred imports to keep the module's top-level light ──────────
    from arnold_pipelines.megaplan.cloud.cli import (
        _resolve_remote_chain_spec,
        _tmux_chain_restart_command,
        cloud_chain_status_payload,
    )

    # ------------------------------------------------------------------
    # (a) Read initial chain status
    # ------------------------------------------------------------------
    try:
        payload = cloud_chain_status_payload(root, args, spec, provider)
    except Exception as exc:
        return _tick_report(
            success=False,
            event="supervisor_error",
            spec="",
            effective_status="unknown",
            next_action="none",
            acted=False,
            refused_reason=f"chain status read failed: {exc}",
            runner={},
            sync={},
            pr={},
            logs={},
        )

    remote_spec = _resolve_remote_chain_spec(root, args, spec)
    # Use resolved workspace/session from the payload for all downstream work.
    resolved_workspace: str = payload.get("resolved_workspace", spec.repo.workspace)
    resolved_session: str = payload.get("resolved_session", "megaplan-chain")
    extra_repos: list[str] = (
        payload.get("resolved_context", {}).get("extra_repos", [])
    )
    status = payload.get("effective_status", "unknown")
    runner = payload.get("runner", {})
    sync_info = payload.get("sync", {})
    pr_info = payload.get("pr", {})
    logs_info = payload.get("logs", {})
    provider_consistency = payload.get("provider_consistency", {})
    extra_repo_sync_info = payload.get("chain_state", {}).get("extra_repo_sync", [])
    # Human-verification status from the cloud status payload (T11).
    # When the payload already probed the remote chain, use its data.
    # Section (c2) refreshes this for human-verification-relevant statuses.
    human_verification: dict[str, Any] = payload.get(
        "human_verification",
        {"status": "unavailable", "reason": "not probed"},
    )

    # ------------------------------------------------------------------
    # (b) Refresh branch/PR sync — BEFORE any restart/advance/wake decisions
    # ------------------------------------------------------------------
    ssh_meth = getattr(provider, "ssh_exec", None)
    sync_refresh: dict[str, Any] = {"status": "skipped", "reason": "no ssh_exec"}
    sync_refreshed = False
    if ssh_meth is not None:
        try:
            chain_state_raw = payload.get("chain_state", {})
            pr_number_raw = (
                chain_state_raw.get("pr_number")
                if isinstance(chain_state_raw, dict)
                else None
            )
            pr_number: int | None = (
                int(pr_number_raw) if pr_number_raw is not None else None
            )
            sync_cmd = _remote_sync_refresh_command(
                resolved_workspace,
                remote_spec,
                branch=None,
                pr_number=pr_number,
                extra_repos=extra_repos if extra_repos else None,

--- FILE: arnold_pipelines/megaplan/cloud/supervise.py (260,560p) ---
                extra_repos=extra_repos if extra_repos else None,
                resolved_workspace=resolved_workspace,
                chain_session=resolved_session,
            )
            ssh_meth(sync_cmd)
            sync_refreshed = True
            sync_refresh = {"status": "ok"}
        except Exception as exc:
            # Sync refresh failure is now visible in the tick report.
            sync_refresh = {"status": "failed", "reason": str(exc)}

    # ------------------------------------------------------------------
    # (c) Re-read chain status after sync refresh
    # ------------------------------------------------------------------
    if sync_refreshed:
        try:
            payload = cloud_chain_status_payload(root, args, spec, provider)
            status = payload.get("effective_status", status)
            runner = payload.get("runner", runner)
            sync_info = payload.get("sync", sync_info)
            pr_info = payload.get("pr", pr_info)
            logs_info = payload.get("logs", logs_info)
            provider_consistency = payload.get("provider_consistency", provider_consistency)
            extra_repo_sync_info = (
                payload.get("chain_state", {}).get("extra_repo_sync", extra_repo_sync_info)
            )
            human_verification = payload.get(
                "human_verification", human_verification
            )
        except Exception:
            # Re-read failed; keep the pre-refresh values.
            sync_refresh["re_read"] = "failed"

    # ------------------------------------------------------------------
    # (c2) Probe remote human-verification status (T11)
    #
    # Only probe when the effective status is human-verification-related
    # (``awaiting_human_verify``, ``human_prerequisite``) so that mock-based
    # tests with ordered ``ssh_exec`` results are not disrupted when the
    # supervisor tick handles a non-human-verification status.
    # ------------------------------------------------------------------
    from arnold_pipelines.megaplan.cloud.cli import _remote_human_verification_status_command

    current_plan_name = (
        payload.get("chain_state", {}).get("current_plan_name")
        if isinstance(payload.get("chain_state"), dict)
        else None
    )
    _hv_relevant_statuses = {"awaiting_human_verify", "human_prerequisite"}
    if (
        ssh_meth is not None
        and current_plan_name
        and status in _hv_relevant_statuses
    ):
        try:
            cmd = _remote_human_verification_status_command(
                resolved_workspace, current_plan_name
            )
            result = ssh_meth(cmd)
            stdout = (result.stdout or "").strip()
            if not stdout:
                human_verification = {
                    "status": "unavailable", "reason": "empty stdout"
                }
            else:
                hv_payload = json.loads(stdout)
                semantics = hv_payload.get("semantics")
                if semantics != "latest_verdict":
                    human_verification = {
                        "status": "unavailable",
                        "reason": (
                            f"remote payload semantics {semantics!r} != "
                            "'latest_verdict'; facts may be stale"
                        ),
                        "raw_semantics": semantics,
                    }
                else:
                    human_verification = {
                        "status": "available",
                        "pending": hv_payload.get("pending", 0),
                        "verified": hv_payload.get("verified", 0),
                        "all_deferred_must_verified": hv_payload.get(
                            "all_deferred_must_verified", False
                        ),
                        "rows": hv_payload.get("rows", []),
                        "semantics": semantics,
                    }
        except json.JSONDecodeError as exc:
            human_verification = {
                "status": "unavailable", "reason": f"invalid JSON: {exc}"
            }
        except Exception as exc:
            human_verification = {"status": "unavailable", "reason": str(exc)}

    # ------------------------------------------------------------------
    # (d) Block mutations on provider consistency mismatch
    # ------------------------------------------------------------------
    if provider_consistency.get("status") == "mismatch":
        return _tick_report(
            success=True,
            event="supervisor_blocked",
            spec=remote_spec,
            effective_status=status,
            next_action="blocked",
            acted=False,
            refused_reason=(
                f"provider consistency mismatch: "
                f"{provider_consistency.get('reason', 'unknown')}"
            ),
            runner=runner,
            sync=sync_info,
            pr=pr_info,
            logs=logs_info,
            sync_refresh=sync_refresh,
            provider_consistency=provider_consistency,
            extra_repo_sync=extra_repo_sync_info,
            human_verification=human_verification,
        )

    # ------------------------------------------------------------------
    # (e) Map effective_status to safe actions
    # ------------------------------------------------------------------

    # --- running → noop ---
    if status == "running":
        return _tick_report(
            success=True,
            event="supervisor_tick",
            spec=remote_spec,
            effective_status=status,
            next_action="noop",
            acted=False,
            refused_reason=None,
            runner=runner,
            sync=sync_info,
            pr=pr_info,
            logs=logs_info,
            sync_refresh=sync_refresh,
            provider_consistency=provider_consistency,
            extra_repo_sync=extra_repo_sync_info,
            human_verification=human_verification,
        )

    # --- complete / done → done ---
    if status == "complete":
        return _tick_report(
            success=True,
            event="supervisor_tick",
            spec=remote_spec,
            effective_status=status,
            next_action="done",
            acted=False,
            refused_reason=None,
            runner=runner,
            sync=sync_info,
            pr=pr_info,
            logs=logs_info,
            sync_refresh=sync_refresh,
            provider_consistency=provider_consistency,
            extra_repo_sync=extra_repo_sync_info,
            human_verification=human_verification,
        )

    # --- human_prerequisite → blocked ---
    if status == "human_prerequisite":
        return _tick_report(
            success=True,
            event="supervisor_blocked",
            spec=remote_spec,
            effective_status=status,
            next_action="blocked",
            acted=False,
            refused_reason=BLOCKED_REFUSAL_REASONS["human_prerequisite"],
            runner=runner,
            sync=sync_info,
            pr=pr_info,
            logs=logs_info,
            sync_refresh=sync_refresh,
            provider_consistency=provider_consistency,
            extra_repo_sync=extra_repo_sync_info,
            human_verification=human_verification,
        )

    # --- quality_gate → blocked ---
    if status == "quality_gate":
        return _tick_report(
            success=True,
            event="supervisor_blocked",
            spec=remote_spec,
            effective_status=status,
            next_action="blocked",
            acted=False,
            refused_reason=BLOCKED_REFUSAL_REASONS["quality_gate"],
            runner=runner,
            sync=sync_info,
            pr=pr_info,
            logs=logs_info,
            sync_refresh=sync_refresh,
            provider_consistency=provider_consistency,
            extra_repo_sync=extra_repo_sync_info,
            human_verification=human_verification,
        )

    # --- awaiting_pr_merge → probe PR ---
    if status == "awaiting_pr_merge":
        pr_number_val = pr_info.get("pr_number") if isinstance(pr_info, dict) else None
        if pr_number_val is not None and ssh_meth is not None:
            try:
                pr_state_cmd = _remote_pr_state_command(resolved_workspace, int(pr_number_val))
                result = ssh_meth(pr_state_cmd)
                pr_state_output = (result.stdout or "").strip().lower()
            except Exception:
                pr_state_output = "unknown"
        else:
            pr_state_output = "unknown"

        if pr_state_output == "merged":
            # PR merged — advance with one-shot tick
            try:
                restart_cmd = _tmux_chain_restart_command(
                    resolved_workspace, remote_spec, session_name=resolved_session
                )
                ssh_meth(restart_cmd)
                return _tick_report(
                    success=True,
                    event="supervisor_advanced",
                    spec=remote_spec,
                    effective_status=status,
                    next_action="advance",
                    acted=True,
                    refused_reason=None,
                    runner=runner,
                    sync=sync_info,
                    pr=pr_info,
                    logs=logs_info,
                    sync_refresh=sync_refresh,
                    provider_consistency=provider_consistency,
                    extra_repo_sync=extra_repo_sync_info,
                    human_verification=human_verification,
                )
            except Exception as exc:
                return _tick_report(
                    success=False,
                    event="supervisor_error",
                    spec=remote_spec,
                    effective_status=status,
                    next_action="blocked",
                    acted=False,
                    refused_reason=f"PR merged but restart failed: {exc}",
                    runner=runner,
                    sync=sync_info,
                    pr=pr_info,
                    logs=logs_info,
                    sync_refresh=sync_refresh,
                    provider_consistency=provider_consistency,
                    extra_repo_sync=extra_repo_sync_info,
                    human_verification=human_verification,
                )
        else:
            # PR not merged — blocked
            return _tick_report(
                success=True,
                event="supervisor_blocked",
                spec=remote_spec,
                effective_status=status,
                next_action="blocked",
                acted=False,
                refused_reason=(
                    f"awaiting PR merge (PR #{pr_number_val} state={pr_state_output}); "
                    "supervisor will not advance until PR is merged"
                ),
                runner=runner,
                sync=sync_info,
                pr=pr_info,
                logs=logs_info,
                sync_refresh=sync_refresh,
                provider_consistency=provider_consistency,
                extra_repo_sync=extra_repo_sync_info,
                human_verification=human_verification,
            )

    # --- stale_bookkeeping with dead/missing runner → restart ---
    if status == "stale_bookkeeping":
        runner_status = runner.get("status", "unavailable") if isinstance(runner, dict) else "unavailable"
        if runner_status in ("dead", "unavailable") and ssh_meth is not None:
            try:
                restart_cmd = _tmux_chain_restart_command(
                    resolved_workspace, remote_spec, session_name=resolved_session
                )
                ssh_meth(restart_cmd)
                return _tick_report(
                    success=True,
                    event="supervisor_restarted",
                    spec=remote_spec,
                    effective_status=status,
                    next_action="restart",
                    acted=True,
                    refused_reason=None,
                    runner=runner,
                    sync=sync_info,
                    pr=pr_info,

--- FILE: arnold_pipelines/megaplan/resident/scheduler.py (1,260p) ---
"""Durable scheduled-job worker and resident job handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import uuid4

from arnold_pipelines.megaplan.schemas import CloudRun, ResidentConversation, ScheduledJob
from arnold_pipelines.megaplan.store import ProgressEventInput, ScheduledJobInput, Store, deterministic_idempotency_key

from .auth import ConfirmationManager
from .cloud import (
    CloudClassification,
    CloudToolBackend,
    CloudToolRequest,
    CloudToolResult,
    cloud_run_status_for_classification,
    progress_kind_for_classification,
)
from .config import ResidentConfig
from .runtime import EmitProtocol, OutboundMessage, OutboundSink

JobHandler = Callable[[dict[str, Any]], Awaitable[None]]
TERMINAL_OR_INPUT_NEEDED: frozenset[CloudClassification] = frozenset(
    {"blocked", "failed", "gate-needed", "completed"}
)


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class SchedulerRunResult:
    claimed: int = 0
    fired: int = 0
    retried: int = 0
    cancelled: int = 0


class ScheduledJobBackend(Protocol):
    async def claim_due_jobs(self, *, worker_id: str, now: datetime) -> list[dict[str, Any]]:
        """Atomically claim due jobs and return job payloads."""

    async def mark_fired(self, job_id: str, *, now: datetime) -> None:
        """Mark a claimed job as fired."""

    async def mark_failed(self, job_id: str, error: str, *, now: datetime) -> bool:
        """Record failure and return whether the job will be retried."""


class StoreScheduledJobBackend:
    """Store-backed scheduled-job claiming and retry/cancel policy."""

    def __init__(
        self,
        store: Store,
        *,
        stale_after_seconds: int,
        batch_size: int,
        retry_delay_seconds: int | None = None,
    ) -> None:
        self.store = store
        self.stale_after_seconds = stale_after_seconds
        self.batch_size = batch_size
        self.retry_delay_seconds = retry_delay_seconds or 30

    async def claim_due_jobs(self, *, worker_id: str, now: datetime) -> list[dict[str, Any]]:
        jobs = self.store.claim_due_scheduled_jobs(
            worker_id=worker_id,
            now=now,
            stale_after_seconds=self.stale_after_seconds,
            max=self.batch_size,
            idempotency_key=deterministic_idempotency_key("resident-scheduler-claim", worker_id, now.isoformat()),
        )
        return [job.model_dump(mode="json") for job in jobs]

    async def mark_fired(self, job_id: str, *, now: datetime) -> None:
        self.store.update_scheduled_job(
            job_id,
            status="fired",
            fired_at=now,
            claimed_by=None,
            claimed_at=None,
            idempotency_key=deterministic_idempotency_key("resident-scheduler-fired", job_id),
        )

    async def mark_failed(self, job_id: str, error: str, *, now: datetime) -> bool:
        job = self.store.load_scheduled_job(job_id)
        if job is None:
            return False
        retrying = job.attempt_count < job.max_attempts
        if retrying:
            self.store.update_scheduled_job(
                job.id,
                status="pending",
                scheduled_for=now + timedelta(seconds=self.retry_delay_seconds),
                claimed_by=None,
                claimed_at=None,
                last_error=error,
                idempotency_key=deterministic_idempotency_key("resident-scheduler-retry", job.id, job.attempt_count, error),
            )
        else:
            self.store.update_scheduled_job(
                job.id,
                status="cancelled",
                cancelled_at=now,
                claimed_by=None,
                claimed_at=None,
                last_error=error,
                idempotency_key=deterministic_idempotency_key("resident-scheduler-cancel", job.id, job.attempt_count, error),
            )
        return retrying


class ScheduledJobWorker:
    """Runtime scheduler shell; storage-specific claiming arrives in store code."""

    def __init__(
        self,
        backend: ScheduledJobBackend,
        *,
        handlers: dict[str, JobHandler] | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.backend = backend
        self.worker_id = worker_id or f"resident-scheduler-{uuid4()}"
        self.handlers = handlers or {}

    async def run_due_once(self, *, now: datetime | None = None) -> SchedulerRunResult:
        now = now or utc_now()
        jobs = await self.backend.claim_due_jobs(worker_id=self.worker_id, now=now)
        fired = retried = cancelled = 0
        for job in jobs:
            job_type = str(job.get("job_type") or job.get("type") or "")
            handler = self.handlers.get(job_type)
            if handler is None:
                retrying = await self.backend.mark_failed(str(job["id"]), f"no handler for {job_type}", now=now)
                retried += int(retrying)
                cancelled += int(not retrying)
                continue
            try:
                await handler(job)
            except Exception as exc:
                retrying = await self.backend.mark_failed(str(job["id"]), str(exc), now=now)
                retried += int(retrying)
                cancelled += int(not retrying)
            else:
                await self.backend.mark_fired(str(job["id"]), now=now)
                fired += 1
        return SchedulerRunResult(claimed=len(jobs), fired=fired, retried=retried, cancelled=cancelled)


@dataclass
class ResidentJobHandlers:
    """Handlers for resident durable scheduled jobs."""

    store: Store
    config: ResidentConfig
    cloud_backend: CloudToolBackend
    outbound: OutboundSink | None = None
    confirmation_manager: ConfirmationManager | None = None
    runtime_flush: Callable[[], Awaitable[None]] | None = None
    worker_id: str = "resident-scheduler"
    reschedule_interval_s: int | None = None

    def handlers(self) -> dict[str, JobHandler]:
        return {
            "cloud_check": self.handle_cloud_check,
            "deferred_turn": self.handle_deferred_turn,
            "heartbeat": self.handle_heartbeat,
            "confirmation_expiry": self.handle_confirmation_expiry,
        }

    async def handle_cloud_check(self, job_payload: dict[str, Any]) -> None:
        job = _job_from_payload(job_payload)
        if not job.cloud_run_id:
            raise ValueError("cloud_check job requires cloud_run_id")
        if not job.conversation_id:
            raise ValueError("cloud_check job requires conversation_id")
        run = self.store.load_cloud_run(job.cloud_run_id)
        if run is None:
            raise ValueError(f"cloud run {job.cloud_run_id!r} was not found")
        conversation = self.store.load_resident_conversation(job.conversation_id)
        if conversation is None:
            raise ValueError(f"resident conversation {job.conversation_id!r} was not found")

        result = await self.cloud_backend.run(_cloud_request_for_job(job, run))
        previous_status = run.status
        updated = self._persist_cloud_result(run, result)
        classification = result.classification
        if classification == "running":
            self._reschedule_cloud_check(job, updated)
        elif classification in TERMINAL_OR_INPUT_NEEDED:
            await self._notify_cloud_transition(
                conversation=conversation,
                run=updated,
                classification=classification,
                summary=result.summary,
            )
        self._log_cloud_check(job, updated, result, previous_status=previous_status)

    async def handle_deferred_turn(self, job_payload: dict[str, Any]) -> None:
        job = _job_from_payload(job_payload)
        if self.runtime_flush is not None:
            await self.runtime_flush()
        self._emit_sink().log_system_event(
            level="info",
            category="system",
            event_type="resident_deferred_turn",
            message="Resident deferred turn job processed",
            details={"job_id": job.id, "conversation_id": job.conversation_id},
            idempotency_key=deterministic_idempotency_key("resident-deferred-turn", job.id, job.attempt_count),
        )

    async def handle_heartbeat(self, job_payload: dict[str, Any]) -> None:
        job = _job_from_payload(job_payload)
        self._emit_sink().log_system_event(
            level="info",
            category="system",
            event_type="resident_scheduler_heartbeat",
            message="Resident scheduler heartbeat",
            details={"job_id": job.id, "worker_id": self.worker_id},
            idempotency_key=deterministic_idempotency_key("resident-heartbeat", job.id, job.attempt_count),
        )

    async def handle_confirmation_expiry(self, job_payload: dict[str, Any]) -> None:
        job = _job_from_payload(job_payload)
        expired = self.confirmation_manager.expire_due() if self.confirmation_manager is not None else []
        self._emit_sink().log_system_event(
            level="info",
            category="system",
            event_type="resident_confirmation_expiry",
            message="Expired resident confirmation requests",
            details={"job_id": job.id, "expired_request_ids": [request.id for request in expired]},
            idempotency_key=deterministic_idempotency_key("resident-confirmation-expiry", job.id, job.attempt_count),
        )

    def _persist_cloud_result(
        self,
        run: CloudRun,
        result: CloudToolResult,
    ) -> CloudRun:
        now = utc_now()
        status = cloud_run_status_for_classification(result.classification)
        last_status = {
            "cloud_status": result.classification,
            "summary": result.summary,
            "details": result.details,
            "checked_at": now.isoformat().replace("+00:00", "Z"),
        }
        changes: dict[str, Any] = {
            "status": status,
            "progress_summary": result.summary,
            "last_status": last_status,
            "last_checked_at": now,
        }
