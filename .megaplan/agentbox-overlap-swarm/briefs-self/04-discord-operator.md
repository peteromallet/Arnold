You are a DeepSeek subagent auditing overlap between the proposed AgentBox plan and existing Megaplan functionality. The brief embeds local file excerpts because you do not have filesystem tools. Return: existing functionality reusable directly, functionality needing extraction/generalization, missing pieces, risks/gotchas, and a recommended first implementation slice. Keep under 900 words and cite file names/sections.\nFocus only on Discord Operator overlap: message-triggered agent, tools, auth, confirmations, conversation state, and outbound notifications.


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

--- FILE: docs/agentbox-persistent-machine-plan.md (510,550p) ---
- `arnold_pipelines/megaplan/supervisor/*`
- Megaplan resident scheduler
- live supervisor pipeline patterns

### 9. Discord Operator

Purpose: primary human interface for the machine, and an on-demand agent that can operate on AgentBox state/tools when the user sends a Discord message.

Build commands:

- `status`
- `repos`
- `run <repo> <task>`
- `run chain <repo> <spec>`
- `logs <operation>`
- `attach <operation>` or instructions for SSH/tmux attach
- `approve <confirmation>`
- `stop <operation>`
- `restart <operation>`
- `cleanup <operation>`
- `creds test`
- `summarize`

Notification events:

- operation started;
- operation blocked;
- approval needed;
- operation completed;
- operation failed;
- disk/memory warning;
- dirty/unpushed branch warning.

Reuse:

- Megaplan resident Discord service;
- Megaplan resident runtime/auth/confirmation manager;
- OpenACP UX and streaming patterns;
- existing Hermes Discord send tools where useful.

### 10. Approval And Safety

--- FILE: arnold_pipelines/megaplan/resident/discord.py (1,220p) ---
"""Discord adapter boundary for resident Megaplan conversations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import os
from typing import Any

from .auth import AuthorizationSubject
from .runtime import InboundEvent, OutboundMessage, OutboundSink, ResidentRuntime

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiscordDeliveryTarget:
    guild_id: str | None
    channel_id: str
    thread_id: str | None = None
    dm_user_id: str | None = None

    @property
    def conversation_key(self) -> str:
        if self.dm_user_id:
            return f"discord:dm:{self.dm_user_id}"
        thread_part = f":thread:{self.thread_id}" if self.thread_id else ""
        return f"discord:guild:{self.guild_id}:channel:{self.channel_id}{thread_part}"

    @classmethod
    def from_conversation_key(cls, conversation_key: str) -> "DiscordDeliveryTarget":
        parts = [part for part in conversation_key.split(":") if part]
        if parts[:2] == ["discord", "dm"] and len(parts) == 3:
            return cls(guild_id=None, channel_id=parts[2], dm_user_id=parts[2])
        if parts[:2] == ["discord", "guild"] and len(parts) >= 5 and parts[3] == "channel":
            thread_id = parts[6] if len(parts) >= 7 and parts[5] == "thread" else None
            return cls(guild_id=parts[2], channel_id=parts[4], thread_id=thread_id)
        raise ValueError(f"Unsupported Discord conversation key: {conversation_key}")


@dataclass(frozen=True)
class DiscordInboundMessage:
    message_id: str
    author_id: str
    target: DiscordDeliveryTarget
    content: str

    @classmethod
    def from_discord_message(cls, message: Any) -> "DiscordInboundMessage":
        channel = message.channel
        guild = getattr(message, "guild", None)
        author = getattr(message, "author", None)
        guild_id = _optional_snowflake(getattr(guild, "id", None))
        author_id = _optional_snowflake(getattr(author, "id", None))
        channel_id = _optional_snowflake(getattr(channel, "id", None))
        thread_id = None
        dm_user_id = None
        parent = getattr(channel, "parent", None)
        if parent is not None and _optional_snowflake(getattr(parent, "id", None)):
            thread_id = channel_id
            channel_id = _optional_snowflake(getattr(parent, "id", None))
        if guild_id is None:
            dm_user_id = author_id
        if not author_id:
            raise ValueError("Discord message author has no stable id")
        if not channel_id:
            raise ValueError("Discord message channel has no stable id")
        return cls(
            message_id=str(message.id),
            author_id=author_id,
            target=DiscordDeliveryTarget(
                guild_id=guild_id,
                channel_id=channel_id,
                thread_id=thread_id,
                dm_user_id=dm_user_id,
            ),
            content=str(getattr(message, "content", "")),
        )

    def to_inbound_event(self) -> InboundEvent:
        return InboundEvent(
            idempotency_key=f"discord:message:{self.message_id}",
            conversation_key=self.target.conversation_key,
            subject=AuthorizationSubject(
                user_id=self.author_id,
                guild_id=self.target.guild_id,
                channel_id=self.target.channel_id,
            ),
            content=self.content,
            raw={
                "discord_message_id": self.message_id,
                "thread_id": self.target.thread_id,
                "dm_user_id": self.target.dm_user_id,
            },
        )


class DiscordOutboundSink(OutboundSink):
    """Deliver resident outbound messages to Discord using durable targets."""

    def __init__(self, client: Any | None = None) -> None:
        self.client = client

    def bind_client(self, client: Any) -> None:
        self.client = client

    async def send(self, message: OutboundMessage) -> None:
        if self.client is None:
            raise RuntimeError("Discord client is not bound")
        target = DiscordDeliveryTarget.from_conversation_key(message.conversation_key)
        channel = await self._resolve_channel(target)
        sent = await channel.send(message.content)
        if isinstance(message.metadata, dict):
            message.metadata["discord_message_id"] = str(getattr(sent, "id", ""))

    async def _resolve_channel(self, target: DiscordDeliveryTarget) -> Any:
        if target.dm_user_id:
            user = self.client.get_user(int(target.dm_user_id)) or await self.client.fetch_user(int(target.dm_user_id))
            return user.dm_channel or await user.create_dm()
        channel_id = int(target.thread_id or target.channel_id)
        channel = self.client.get_channel(channel_id)
        if channel is None:
            channel = await self.client.fetch_channel(channel_id)
        return channel


class ResidentDiscordService:
    """Thin discord.py service that feeds Discord events into ResidentRuntime."""

    def __init__(self, *, runtime: ResidentRuntime, token: str) -> None:
        if not token:
            raise ValueError("Discord token is required")
        self.runtime = runtime
        self.token = token

    async def start(self) -> None:
        try:
            import discord
        except ImportError as exc:
            raise RuntimeError("discord.py is required for `megaplan resident discord`") from exc

        logging.basicConfig(level=os.environ.get("MEGAPLAN_LOG_LEVEL", "INFO").upper())
        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)

        @client.event
        async def on_ready() -> None:
            outbound = getattr(self.runtime, "outbound", None)
            if isinstance(outbound, DiscordOutboundSink):
                outbound.bind_client(client)
            recovered = await self.runtime.recover_abandoned_turns()
            user = getattr(client, "user", None)
            guilds = getattr(client, "guilds", ())
            LOGGER.info(
                "Resident Discord service ready user_id=%s guild_count=%s recovered_turns=%s",
                getattr(user, "id", None),
                len(guilds),
                recovered,
            )

        @client.event
        async def on_message(message: Any) -> None:
            if getattr(getattr(message, "author", None), "bot", False):
                return
            try:
                inbound = DiscordInboundMessage.from_discord_message(message)
                LOGGER.info(
                    "Resident Discord inbound message_id=%s author_id=%s conversation_key=%s content_length=%s",
                    inbound.message_id,
                    inbound.author_id,
                    inbound.target.conversation_key,
                    len(inbound.content),
                )
                await self.runtime.receive(inbound.to_inbound_event())
            except Exception:
                LOGGER.exception("Resident Discord message handling failed")

        @client.event
        async def on_error(event_method: str, *args: Any, **kwargs: Any) -> None:
            LOGGER.exception("Resident Discord client event failed: %s", event_method)

        await client.start(self.token)

    def run(self) -> None:
        asyncio.run(self.start())


def discord_token_from_env(env_name: str) -> str | None:
    token = os.environ.get(env_name)
    return token.strip() if token and token.strip() else None


def _optional_snowflake(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None

--- FILE: arnold_pipelines/megaplan/resident/cli.py (1,180p) ---
"""CLI entry points for resident Megaplan orchestration."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.store import DBStore, FileStore, Store
from arnold_pipelines.megaplan.types import CliError

from .agent_loop import OpenAICompatibleAgentRunner
from .auth import StoreBackedConfirmationManager, ResidentAuthorizer
from .cloud import CloudCliBackend
from .config import ResidentConfig
from .discord import DiscordOutboundSink, ResidentDiscordService, discord_token_from_env
from .profile import MegaplanResidentProfile
from .runtime import ResidentRuntime
from .scheduler import make_store_scheduler


def _register_resident_subcommands(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="resident_action", required=True)
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--store-root", help="Use a local FileStore root for resident state")
    shared.add_argument("--mode", choices=["dev", "production"], help="Override MEGAPLAN_RESIDENT_MODE")

    discord_parser = sub.add_parser("discord", parents=[shared], help="Start the resident Discord service")
    discord_parser.add_argument("--dry-run", action="store_true", help="Validate configuration without connecting to Discord")

    scheduler_parser = sub.add_parser("scheduler-once", parents=[shared], help="Claim and process due resident jobs once")
    scheduler_parser.add_argument("--worker-id", default="resident-cli-scheduler")

    health_parser = sub.add_parser("health", parents=[shared], help="Report resident orchestration health")
    health_parser.add_argument("--limit", type=int, default=10)


def run_resident_cli(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    config = _resident_config(args)
    store = _resident_store(root, args)
    try:
        action = args.resident_action
        if action == "health":
            return _resident_health(store, config, limit=args.limit)
        if action == "scheduler-once":
            return asyncio.run(_resident_scheduler_once(store, config, worker_id=args.worker_id))
        if action == "discord":
            return _resident_discord(root, store, config, dry_run=args.dry_run)
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()
    raise CliError("invalid_args", f"Unknown resident action: {getattr(args, 'resident_action', None)!r}")


def _resident_config(args: argparse.Namespace) -> ResidentConfig:
    config = ResidentConfig.from_env()
    mode = getattr(args, "mode", None)
    return config.model_copy(update={"mode": mode}) if mode else config


def _resident_store(root: Path, args: argparse.Namespace) -> Store:
    if getattr(args, "store_root", None):
        return FileStore(Path(args.store_root).expanduser().resolve())
    config = _resident_config(args)
    if config.is_production:
        return DBStore(actor_id="resident")
    return FileStore(root / ".megaplan" / "resident")


def _resident_health(store: Store, config: ResidentConfig, *, limit: int) -> dict[str, Any]:
    pending_jobs = store.list_scheduled_jobs(status="pending", limit=limit)
    claimed_jobs = store.list_scheduled_jobs(status="claimed", limit=limit)
    recent_runs = store.list_cloud_runs(limit=limit)
    conversations = store.list_resident_conversations(transport="discord", limit=limit)
    stale_control = store.list_stale_control_messages(
        older_than_seconds=int(config.stale_control_claim_timeout_s),
        limit=limit,
    )
    pending_confirmations = StoreBackedConfirmationManager(config, store).pending()
    abandoned_turns = [
        turn
        for turn in store.list_recent_turns(n=limit * 2)
        if turn.status == "abandoned"
    ][:limit]
    return {
        "success": True,
        "step": "resident",
        "action": "health",
        "mode": config.mode,
        "store": type(store).__name__,
        "scheduled_backlog": {
            "pending": len(pending_jobs),
            "claimed": len(claimed_jobs),
            "pending_jobs": [_model(row) for row in pending_jobs],
            "claimed_jobs": [_model(row) for row in claimed_jobs],
        },
        "resident_conversations": [_model(row) for row in conversations],
        "abandoned_turns": [_model(row) for row in abandoned_turns],
        "recent_cloud_runs": [_model(row) for row in recent_runs],
        "pending_cloud_confirmations": [_confirmation_model(row) for row in pending_confirmations[:limit]],
        "stale_control_messages": {
            "count": len(stale_control),
            "messages": [_model(row) for row in stale_control],
        },
    }


async def _resident_scheduler_once(store: Store, config: ResidentConfig, *, worker_id: str) -> dict[str, Any]:
    worker = make_store_scheduler(
        store=store,
        config=config,
        cloud_backend=CloudCliBackend(),
        outbound=None,
        confirmation_manager=StoreBackedConfirmationManager(config, store),
        worker_id=worker_id,
    )
    result = await worker.run_due_once()
    return {
        "success": True,
        "step": "resident",
        "action": "scheduler-once",
        "result": result.__dict__,
    }


def _resident_discord(root: Path, store: Store, config: ResidentConfig, *, dry_run: bool) -> dict[str, Any]:
    token = discord_token_from_env(config.discord_bot_token_env)
    if dry_run:
        return {
            "success": True,
            "step": "resident",
            "action": "discord",
            "dry_run": True,
            "token_configured": bool(token),
            "conversation_count": len(store.list_resident_conversations(transport="discord", limit=100)),
        }
    if token is None:
        raise CliError("missing_discord_token", f"{config.discord_bot_token_env} is required")
    authorizer = ResidentAuthorizer(config)
    outbound = DiscordOutboundSink()
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=MegaplanResidentProfile(
            store=store,
            authorizer=authorizer,
            config=config,
            confirmation_manager=StoreBackedConfirmationManager(config, store),
            cloud_backend=CloudCliBackend(),
        ),
        runner=OpenAICompatibleAgentRunner(config),
        outbound=outbound,
    )
    service = ResidentDiscordService(runtime=runtime, token=token)
    service.run()
    return {"success": True, "step": "resident", "action": "discord", "stopped": True, "project_root": str(root)}


def _model(row: Any) -> dict[str, Any]:
    return row.model_dump(mode="json")


def _confirmation_model(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "action": row.action,
        "target_summary": row.target_summary,
        "expires_at": row.expires_at.isoformat().replace("+00:00", "Z"),
        "created_at": row.created_at.isoformat().replace("+00:00", "Z"),
        "subject": {
            "user_id": row.subject.user_id,
            "guild_id": row.subject.guild_id,
            "channel_id": row.subject.channel_id,
        },
        "metadata": row.metadata,
    }

--- FILE: arnold_pipelines/megaplan/resident/cloud.py (1,240p) ---
"""Constrained Megaplan cloud operation wrappers for resident tools."""

from __future__ import annotations

import argparse
import contextlib
from dataclasses import dataclass, field
from io import StringIO
import json
from pathlib import Path
from typing import Literal, Protocol

from arnold_pipelines.megaplan.cloud.cli import build_cloud_parser, run_cloud_cli

CloudClassification = Literal["running", "blocked", "failed", "gate-needed", "completed", "unknown"]
CloudOperation = Literal[
    "cloud_status",
    "cloud_status_chain",
    "cloud_start_chain",
    "cloud_bootstrap",
    "cloud_resume",
    "cloud_logs",
]


@dataclass(frozen=True)
class CloudToolRequest:
    operation: CloudOperation
    target_id: str | None = None
    arguments: dict[str, str] = field(default_factory=dict)
    confirmed: bool = False


@dataclass(frozen=True)
class CloudToolResult:
    classification: CloudClassification
    summary: str
    details: dict[str, object] = field(default_factory=dict)


class CloudToolBackend(Protocol):
    async def run(self, request: CloudToolRequest) -> CloudToolResult:
        """Execute one constrained cloud operation."""


class CloudCliBackend:
    """Default resident backend that dispatches through existing cloud CLI code."""

    async def run(self, request: CloudToolRequest) -> CloudToolResult:
        argv = _argv_for_request(request)
        root = Path(request.arguments.get("project_root") or ".").expanduser().resolve()
        parser = argparse.ArgumentParser()
        build_cloud_parser(parser.add_subparsers(dest="command", required=True))
        args = parser.parse_args(["cloud", *argv])
        stdout = StringIO()
        stderr = StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = run_cloud_cli(root, args)
        output = stdout.getvalue().strip()
        error_output = stderr.getvalue().strip()
        payload = _json_payload(output)
        classification = classify_cloud_payload(payload or {"returncode": code, "stderr": error_output})
        ok = code == 0
        summary = _summary_for_payload(request.operation, classification, payload, ok=ok)
        return CloudToolResult(
            classification=classification if ok else "failed",
            summary=summary,
            details={
                "returncode": code,
                "stdout": output,
                "stderr": error_output,
                "payload": payload,
                "argv": argv,
            },
        )


def classify_cloud_payload(payload: object) -> CloudClassification:
    """Classify status/chain payloads without depending on provider-specific text."""
    flat = " ".join(str(value).lower() for value in _walk_values(payload))
    if not flat.strip():
        return "unknown"
    if any(token in flat for token in ("gate-needed", "gate_needed", "gate pending", "gate_pending", "state_gated")):
        return "gate-needed"
    if any(token in flat for token in ("failed", "failure", "error", "state_failed", "traceback")):
        return "failed"
    if any(token in flat for token in ("blocked", "execution_blocked", "state_blocked")):
        return "blocked"
    if any(token in flat for token in ("completed", "complete", "done", "success", "state_done", "plan_done")):
        return "completed"
    if any(token in flat for token in ("running", "starting", "queued", "in_progress", "state_executing", "state_planning")):
        return "running"
    if isinstance(payload, dict) and payload.get("next_step"):
        return "running"
    return "unknown"


def progress_kind_for_classification(classification: CloudClassification) -> str:
    if classification == "completed":
        return "plan_done"
    if classification == "failed":
        return "plan_failed"
    if classification == "gate-needed":
        return "gate_pending"
    if classification == "blocked":
        return "execution_blocked"
    if classification == "running":
        return "phase_start"
    return "phase_end"


def cloud_run_status_for_classification(classification: CloudClassification) -> str:
    """Map resident cloud classifications onto CloudRun.status values."""
    if classification == "completed":
        return "completed"
    if classification == "failed":
        return "failed"
    if classification == "blocked":
        return "blocked"
    if classification == "gate-needed":
        return "gate-needed"
    if classification == "running":
        return "running"
    return "unknown"


def _argv_for_request(request: CloudToolRequest) -> list[str]:
    args = request.arguments
    cloud_yaml = args.get("cloud_yaml")
    argv: list[str] = []
    if request.operation == "cloud_status":
        argv = ["status"]
        if plan := args.get("plan"):
            argv.extend(["--plan", plan])
    elif request.operation == "cloud_status_chain":
        argv = ["status", "--chain"]
        if remote_spec := args.get("remote_spec"):
            argv.extend(["--remote-spec", remote_spec])
    elif request.operation == "cloud_start_chain":
        spec = args.get("spec")
        if not spec:
            raise ValueError("cloud_start_chain requires spec")
        argv = ["chain", spec]
        if idea_dir := args.get("idea_dir"):
            argv.extend(["--idea-dir", idea_dir])
        _append_repo_args(argv, args)
    elif request.operation == "cloud_bootstrap":
        idea_file = args.get("idea_file")
        if not idea_file:
            raise ValueError("cloud_bootstrap requires idea_file")
        argv = ["bootstrap", idea_file]
        if plan_name := args.get("plan_name"):
            argv.extend(["--plan-name", plan_name])
        if robustness := args.get("robustness"):
            argv.extend(["--robustness", robustness])
        _append_repo_args(argv, args)
    elif request.operation == "cloud_resume":
        argv = ["resume"]
        if plan := args.get("plan"):
            argv.extend(["--plan", plan])
    elif request.operation == "cloud_logs":
        argv = ["logs"]
        if args.get("no_follow") == "true":
            argv.append("--no-follow")
    else:
        raise ValueError(f"unsupported cloud operation: {request.operation}")
    if cloud_yaml:
        argv.extend(["--cloud-yaml", cloud_yaml])
    return argv


def _append_repo_args(argv: list[str], args: dict[str, str]) -> None:
    if repo_url := args.get("repo_url"):
        argv.extend(["--repo-url", repo_url])
    if repo_branch := args.get("repo_branch"):
        argv.extend(["--repo-branch", repo_branch])
    if repo_workspace := args.get("repo_workspace"):
        argv.extend(["--repo-workspace", repo_workspace])


def _summary_for_payload(
    operation: CloudOperation,
    classification: CloudClassification,
    payload: object,
    *,
    ok: bool,
) -> str:
    if not ok:
        return f"{operation} failed"
    if isinstance(payload, dict):
        next_step = payload.get("next_step")
        if isinstance(next_step, str) and next_step:
            return f"{operation}: next step {next_step}"
        summary = payload.get("summary")
        if isinstance(summary, dict):
            current = summary.get("current")
            if current:
                return f"{operation}: {current}"
    return f"{operation}: {classification}"


def _json_payload(text: str) -> object | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _walk_values(value: object) -> list[object]:
    if isinstance(value, dict):
        values: list[object] = []
        for key, item in value.items():
            values.append(key)
            values.extend(_walk_values(item))
        return values
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(_walk_values(item))
        return values
    return [value]

--- FILE: arnold_pipelines/megaplan/resident/config.py (1,120p) ---
"""Configuration boundary for resident orchestration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ResidentMode = Literal["dev", "production"]


def _split_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


class ResidentConfig(BaseModel):
    """Runtime configuration shared by Discord, scheduling, and tools."""

    mode: ResidentMode = "dev"
    discord_bot_token_env: str = "DISCORD_BOT_TOKEN"
    allowed_guild_ids: tuple[str, ...] = Field(default_factory=tuple)
    allowed_channel_ids: tuple[str, ...] = Field(default_factory=tuple)
    allowed_user_ids: tuple[str, ...] = Field(default_factory=tuple)
    admin_user_ids: tuple[str, ...] = Field(default_factory=tuple)
    model_provider: str = "openai"
    model_name: str = "gpt-5.4"
    model_api_key_env: str | None = None
    model_base_url: str | None = None
    model_timeout_s: float = Field(default=120.0, gt=0)
    max_tool_calls_per_turn: int = Field(default=8, gt=0)
    scheduler_poll_interval_s: float = Field(default=10.0, gt=0)
    scheduler_batch_size: int = Field(default=10, gt=0)
    stale_claim_timeout_s: float = Field(default=600.0, gt=0)
    stale_turn_timeout_s: float = Field(default=1800.0, gt=0)
    stale_control_claim_timeout_s: float = Field(default=600.0, gt=0)
    burst_idle_delay_s: float = Field(default=1.5, ge=0)
    burst_max_delay_s: float = Field(default=10.0, gt=0)
    confirmation_expiry_s: float = Field(default=900.0, gt=0)
    require_cloud_start_confirmation: bool = True
    cloud_yaml_path: Path = Path("cloud.yaml")
    resident_export_root: Path = Path(".megaplan/resident_exports")

    @field_validator(
        "allowed_guild_ids",
        "allowed_channel_ids",
        "allowed_user_ids",
        "admin_user_ids",
        mode="before",
    )
    @classmethod
    def _coerce_id_tuple(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            return _split_csv(value)
        if isinstance(value, (list, tuple, set)):
            return tuple(str(part).strip() for part in value if str(part).strip())
        raise TypeError("allowlist values must be strings or sequences")

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "ResidentConfig":
        env = environ or os.environ
        arnold_user_whitelist = env.get("DISCORD_USER_WHITELIST")
        return cls(
            mode=env.get("MEGAPLAN_RESIDENT_MODE", "dev"),
            allowed_guild_ids=_split_csv(env.get("MEGAPLAN_RESIDENT_ALLOWED_GUILDS")),
            allowed_channel_ids=_split_csv(env.get("MEGAPLAN_RESIDENT_ALLOWED_CHANNELS")),
            allowed_user_ids=_split_csv(env.get("MEGAPLAN_RESIDENT_ALLOWED_USERS") or arnold_user_whitelist),
            admin_user_ids=_split_csv(env.get("MEGAPLAN_RESIDENT_ADMIN_USERS") or arnold_user_whitelist),
            model_provider=env.get("MEGAPLAN_RESIDENT_MODEL_PROVIDER", "openai"),
            model_name=env.get("MEGAPLAN_RESIDENT_MODEL", "gpt-5.4"),
            model_api_key_env=env.get("MEGAPLAN_RESIDENT_MODEL_API_KEY_ENV"),
            model_base_url=env.get("MEGAPLAN_RESIDENT_MODEL_BASE_URL") or env.get("OPENAI_BASE_URL"),
            model_timeout_s=_env_float(env, "MEGAPLAN_RESIDENT_MODEL_TIMEOUT_S", 120.0),
            max_tool_calls_per_turn=_env_int(env, "MEGAPLAN_RESIDENT_MAX_TOOL_CALLS", 8),
            scheduler_poll_interval_s=_env_float(env, "MEGAPLAN_RESIDENT_SCHEDULER_POLL_S", 10.0),
            scheduler_batch_size=_env_int(env, "MEGAPLAN_RESIDENT_SCHEDULER_BATCH_SIZE", 10),
            stale_claim_timeout_s=_env_float(env, "MEGAPLAN_RESIDENT_STALE_CLAIM_TIMEOUT_S", 600.0),
            stale_turn_timeout_s=_env_float(env, "MEGAPLAN_RESIDENT_STALE_TURN_TIMEOUT_S", 1800.0),
            stale_control_claim_timeout_s=_env_float(env, "MEGAPLAN_RESIDENT_STALE_CONTROL_CLAIM_TIMEOUT_S", 600.0),
            burst_idle_delay_s=_env_float(env, "MEGAPLAN_RESIDENT_BURST_IDLE_S", 1.5),
            burst_max_delay_s=_env_float(env, "MEGAPLAN_RESIDENT_BURST_MAX_S", 10.0),
            confirmation_expiry_s=_env_float(env, "MEGAPLAN_RESIDENT_CONFIRMATION_EXPIRY_S", 900.0),
            require_cloud_start_confirmation=_env_bool(
                env,
                "MEGAPLAN_RESIDENT_REQUIRE_CLOUD_CONFIRMATION",
                True,
            ),
            cloud_yaml_path=Path(env.get("MEGAPLAN_RESIDENT_CLOUD_YAML", "cloud.yaml")),
            resident_export_root=Path(env.get("MEGAPLAN_RESIDENT_EXPORT_ROOT", ".megaplan/resident_exports")),
        )

    @property
    def is_production(self) -> bool:
        return self.mode == "production"


def _env_int(env: dict[str, str], key: str, default: int) -> int:
    value = env.get(key)
    return default if value is None or value == "" else int(value)


def _env_float(env: dict[str, str], key: str, default: float) -> float:
    value = env.get(key)
    return default if value is None or value == "" else float(value)


def _env_bool(env: dict[str, str], key: str, default: bool) -> bool:
    value = env.get(key)
    if value is None or value == "":
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
