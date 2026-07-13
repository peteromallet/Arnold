"""CLI entry points for resident Megaplan orchestration."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.store import DBStore, FileStore, Store
from arnold_pipelines.megaplan.types import CliError

from .agent_loop import CodexCliAgentRunner, OpenAICompatibleAgentRunner
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
    discord_parser.add_argument(
        "--profile",
        choices=["megaplan", "agentbox_operator"],
        help="Resident profile to run for Discord.",
    )

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
    profile = getattr(args, "profile", None)
    updates = {}
    if mode:
        updates["mode"] = mode
    if profile:
        updates["profile"] = profile
    return config.model_copy(update=updates) if updates else config


def _resident_store(root: Path, args: argparse.Namespace) -> Store:
    store_root = getattr(args, "store_root", None) or os.environ.get(
        "MEGAPLAN_RESIDENT_STORE_ROOT"
    )
    if store_root:
        return FileStore(Path(store_root).expanduser().resolve())
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
            "profile": config.profile,
            "conversation_count": len(store.list_resident_conversations(transport="discord", limit=100)),
        }
    if token is None:
        raise CliError("missing_discord_token", f"{config.discord_bot_token_env} is required")
    authorizer = ResidentAuthorizer(config)
    # Dev/test residents may handle interactive test traffic, but durable
    # operational outboxes belong exclusively to the production bot boundary.
    outbound = DiscordOutboundSink(
        delivery_environment=config.mode,
        bot_role=config.discord_bot_role,
    )
    confirmation_manager = StoreBackedConfirmationManager(config, store)
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=_resident_profile(
            store=store,
            authorizer=authorizer,
            config=config,
            confirmation_manager=confirmation_manager,
        ),
        runner=_resident_runner(config, root),
        outbound=outbound,
    )
    scheduler = make_store_scheduler(
        store=store,
        config=config,
        cloud_backend=CloudCliBackend(),
        outbound=outbound,
        confirmation_manager=confirmation_manager,
        runtime=runtime,
        worker_id="resident-discord-scheduler",
    )
    service = ResidentDiscordService(
        runtime=runtime,
        token=token,
        scheduler=scheduler,
        scheduler_interval_s=config.scheduler_poll_interval_s,
    )
    service.run()
    return {"success": True, "step": "resident", "action": "discord", "stopped": True, "project_root": str(root)}


def _resident_runner(config: ResidentConfig, root: Path):
    if config.model_provider == "codex":
        return CodexCliAgentRunner(config, cwd=root)
    return OpenAICompatibleAgentRunner(config)


def _resident_profile(
    *,
    store: Store,
    authorizer: ResidentAuthorizer,
    config: ResidentConfig,
    confirmation_manager: StoreBackedConfirmationManager | None = None,
):
    confirmation_manager = confirmation_manager or StoreBackedConfirmationManager(config, store)
    if config.profile == "agentbox_operator":
        from agentbox.resident_profile import AgentBoxOperatorProfile

        return AgentBoxOperatorProfile(
            store=store,
            authorizer=authorizer,
            config=config,
            confirmation_manager=confirmation_manager,
        )
    return MegaplanResidentProfile(
        store=store,
        authorizer=authorizer,
        config=config,
        confirmation_manager=confirmation_manager,
        cloud_backend=CloudCliBackend(),
    )


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
