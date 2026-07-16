"""CLI entry points for resident Megaplan orchestration."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Mapping
import json
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
from .profile import _sanitize_stale_snapshot
from .provenance import provenance_from_environment
from .reply_chain import decode_reply_cursor, reply_chain_page
from .runtime import ResidentRuntime
from .scheduler import make_store_scheduler
from . import vp_todo
from .status_tree import DEFAULT_NODE_LIMIT, MAX_NODE_LIMIT, read_cloud_status_node
from .context_tree import read_context_node, search_context
from arnold_pipelines.megaplan.cloud import status_snapshot


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

    reply_parser = sub.add_parser(
        "read-reply-chain",
        parents=[shared],
        help="Read bounded store-backed Discord reply ancestry for the active conversation",
    )
    reply_parser.add_argument(
        "--source-message-id",
        help="Resident record id or Discord message id; defaults to the current source message",
    )
    reply_parser.add_argument("--cursor", help="Opaque next cursor from the prompt or prior page")
    reply_parser.add_argument("--limit", type=int, default=5)

    status_tree_parser = sub.add_parser(
        "status-tree",
        parents=[shared],
        help="Read one bounded branch of the canonical cloud status tree",
    )
    status_tree_parser.add_argument("--node", default="root", help="Node ID from the root or prior response")
    status_tree_parser.add_argument("--cursor", type=int, default=0)
    status_tree_parser.add_argument("--limit", type=int, default=DEFAULT_NODE_LIMIT)

    context_parser = sub.add_parser(
        "context", parents=[shared], help="Read one typed branch of the resident context tree"
    )
    context_parser.add_argument("--node", default="root")
    context_parser.add_argument("--conversation-id")
    context_parser.add_argument("--cursor", type=int, default=0)
    context_parser.add_argument("--limit", type=int, default=DEFAULT_NODE_LIMIT)

    search_parser = sub.add_parser(
        "context-search", parents=[shared], help="Search one resident context namespace"
    )
    search_parser.add_argument("--scope", required=True)
    search_parser.add_argument("--query", default="")
    search_parser.add_argument("--conversation-id")
    search_parser.add_argument("--cursor", type=int, default=0)
    search_parser.add_argument("--limit", type=int, default=DEFAULT_NODE_LIMIT)

    queue_parser = sub.add_parser(
        "queue-subagent-successor",
        parents=[shared],
        help="Durably queue a provenance-preserving successor after one or more managed runs",
    )
    dependency_source = queue_parser.add_mutually_exclusive_group(required=True)
    dependency_source.add_argument(
        "--after-run-id", help="Legacy singular predecessor run ID"
    )
    dependency_source.add_argument(
        "--after-run-ids",
        nargs="+",
        help="Distinct predecessor run IDs; every run must succeed before launch",
    )
    prompt_source = queue_parser.add_mutually_exclusive_group(required=True)
    prompt_source.add_argument("--prompt")
    prompt_source.add_argument("--prompt-file")
    queue_parser.add_argument("--description", required=True)
    queue_parser.add_argument("--project-dir")
    queue_parser.add_argument("--max-launch-attempts", type=int, default=3)

    inspect_queue_parser = sub.add_parser(
        "inspect-subagent-queue",
        parents=[shared],
        help="Inspect bounded resident successor dependency state",
    )
    inspect_queue_parser.add_argument("--run-id")
    inspect_queue_parser.add_argument("--project-dir")
    inspect_queue_parser.add_argument("--limit", type=int, default=8)

    supersede_todo_parser = sub.add_parser(
        "supersede-todo",
        parents=[shared],
        help=(
            "Supersede obsolete pending todo intent using canonical retirement or "
            "replacement evidence without asserting completion"
        ),
    )
    supersede_todo_parser.add_argument("--id", required=True)
    supersede_todo_parser.add_argument("--canonical-record-id", required=True)
    supersede_todo_parser.add_argument("--evidence", required=True)
    supersede_todo_parser.add_argument("--resolution", required=True)
    supersede_todo_parser.add_argument(
        "--todo-path",
        help="Explicit todo store path; defaults to the resident configuration",
    )

    schedule_parser = sub.add_parser(
        "schedule", parents=[shared], help="Manage durable resident-managed schedules"
    )
    schedule_sub = schedule_parser.add_subparsers(dest="schedule_action", required=True)
    create = schedule_sub.add_parser("create", help="Create a versioned schedule definition")
    create.add_argument("--file", required=True)
    create.add_argument("--idempotency-key", required=True)
    create.add_argument("--dry-run", action="store_true")
    preview = schedule_sub.add_parser("preview", help="Preview nominal instants without writing")
    preview.add_argument("--file", required=True)
    preview.add_argument("--count", type=int, default=10)
    get = schedule_sub.add_parser("get")
    get.add_argument("schedule_id")
    get.add_argument("--history", action="store_true")
    listing = schedule_sub.add_parser("list")
    listing.add_argument("--state")
    update = schedule_sub.add_parser("update")
    update.add_argument("schedule_id")
    update.add_argument("--file", required=True)
    update.add_argument("--if-revision", required=True, type=int)
    for action in ("activate", "pause", "resume", "cancel"):
        lifecycle = schedule_sub.add_parser(action)
        lifecycle.add_argument("schedule_id")
        lifecycle.add_argument("--if-revision", required=True, type=int)
        lifecycle.add_argument("--reason", required=True)
    occurrences = schedule_sub.add_parser("occurrences")
    occurrences.add_argument("schedule_id")
    occurrences.add_argument("--state")
    schedule_sub.add_parser("dead-letters").add_argument("--schedule")
    replay = schedule_sub.add_parser("replay", help="Replay a dead letter under a new grant")
    replay.add_argument("occurrence_id")
    replay.add_argument("--grant-file", required=True)
    event = schedule_sub.add_parser("event", help="Ingest one typed append-only event")
    event.add_argument("--file", required=True)
    run_once = schedule_sub.add_parser("run-once", help="Materialize and process due occurrences")
    run_once.add_argument("--worker-id", default="resident-schedule-cli")


def run_resident_cli(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    config = _resident_config(args)
    store = _resident_store(root, args)
    try:
        action = args.resident_action
        if action == "health":
            return _resident_health(store, config, limit=args.limit)
        if action == "scheduler-once":
            return asyncio.run(_resident_scheduler_once(store, config, worker_id=args.worker_id))
        if action == "queue-subagent-successor":
            return _resident_queue_subagent_successor(root, config, args)
        if action == "inspect-subagent-queue":
            return _resident_inspect_subagent_queue(root, args)
        if action == "supersede-todo":
            return _resident_supersede_todo(config, args)
        if action == "schedule":
            return _resident_schedule(root, store, args)
        if action == "read-reply-chain":
            return _resident_read_reply_chain(
                store,
                source_message_id=args.source_message_id,
                cursor=args.cursor,
                limit=args.limit,
            )
        if action == "status-tree":
            return _resident_status_tree(
                config,
                node_id=args.node,
                cursor=args.cursor,
                limit=args.limit,
            )
        if action in {"context", "context-search"}:
            return _resident_context_tree(
                store,
                config,
                action=action,
                conversation_id=args.conversation_id,
                node_id=getattr(args, "node", "root"),
                scope=getattr(args, "scope", None),
                query=getattr(args, "query", ""),
                cursor=args.cursor,
                limit=args.limit,
            )
        if action == "discord":
            return _resident_discord(root, store, config, dry_run=args.dry_run)
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()
    raise CliError("invalid_args", f"Unknown resident action: {getattr(args, 'resident_action', None)!r}")


def _resident_supersede_todo(
    config: ResidentConfig, args: argparse.Namespace
) -> dict[str, Any]:
    path = Path(
        args.todo_path or config.special_requests_todo_path
    ).expanduser().resolve()
    try:
        item = vp_todo.supersede_by_record(
            path,
            args.id,
            canonical_record_id=args.canonical_record_id,
            evidence=args.evidence,
            resolution=args.resolution,
        )
    except ValueError as exc:
        raise CliError("todo_reconciliation_rejected", str(exc)) from exc
    if item is None:
        raise CliError("todo_not_found", f"todo item not found: {args.id}")
    return {
        "success": True,
        "step": "resident",
        "action": "supersede-todo",
        "todo_path": str(path),
        "item": vp_todo.public_item(item),
    }


def _resident_schedule(root: Path, store: Store, args: argparse.Namespace) -> dict[str, Any]:
    from .schedules import (
        AuthorizationGrant, ScheduleService, definition_from_file, schedule_store_root,
    )

    store_root = schedule_store_root(store)
    if store_root is None:
        raise CliError(
            "unsupported_store",
            "resident schedule v1 is single-writer file mode; database multi-worker support is not enabled",
        )
    service = ScheduleService(store_root, project_root=root)
    action = args.schedule_action
    try:
        if action in {"create", "preview"}:
            definition = definition_from_file(Path(args.file).expanduser().resolve())
            preview = service.preview(definition, count=getattr(args, "count", 10))
            if action == "preview" or args.dry_run:
                return {
                    "success": True, "step": "resident", "action": f"schedule-{action}",
                    "dry_run": True, "definition": definition.model_dump(mode="json", by_alias=True),
                    "nominal_times": [item.isoformat() for item in preview],
                }
            created, changed = service.create(
                definition, idempotency_key=args.idempotency_key,
            )
            return {
                "success": True, "step": "resident", "action": "schedule-create",
                "created": changed, "definition": created.model_dump(mode="json", by_alias=True),
                "nominal_times": [item.isoformat() for item in preview],
            }
        if action == "get":
            definition = service.repo.read_definition(args.schedule_id)
            payload: dict[str, Any] = {
                "success": True, "step": "resident", "action": "schedule-get",
                "definition": definition.model_dump(mode="json", by_alias=True),
            }
            if args.history:
                payload["history"] = [
                    service.repo.read_definition(args.schedule_id, revision).model_dump(mode="json", by_alias=True)
                    for revision in range(1, definition.revision + 1)
                ]
            return payload
        if action == "list":
            rows = service.repo.definitions(state=args.state)
            return {
                "success": True, "step": "resident", "action": "schedule-list",
                "count": len(rows),
                "items": [row.model_dump(mode="json", by_alias=True) for row in rows],
            }
        if action == "update":
            replacement = definition_from_file(Path(args.file).expanduser().resolve())
            revised = service.revise(args.schedule_id, replacement, if_revision=args.if_revision)
            return {
                "success": True, "step": "resident", "action": "schedule-update",
                "definition": revised.model_dump(mode="json", by_alias=True),
            }
        if action in {"activate", "pause", "resume", "cancel"}:
            state = {"activate": "active", "resume": "active", "pause": "paused", "cancel": "cancelled"}[action]
            revised = service.set_state(
                args.schedule_id, state, if_revision=args.if_revision, audit_reason=args.reason,
            )
            return {
                "success": True, "step": "resident", "action": f"schedule-{action}",
                "definition": revised.model_dump(mode="json", by_alias=True),
            }
        if action in {"occurrences", "dead-letters"}:
            schedule_id = args.schedule_id if action == "occurrences" else args.schedule
            rows = service.repo.occurrences(schedule_id)
            wanted = getattr(args, "state", None) or ("dead_letter" if action == "dead-letters" else None)
            if wanted:
                rows = [row for row in rows if row.state == wanted]
            return {
                "success": True, "step": "resident", "action": f"schedule-{action}",
                "count": len(rows), "items": [row.model_dump(mode="json") for row in rows],
            }
        if action == "event":
            event = json.loads(Path(args.file).expanduser().resolve().read_text(encoding="utf-8"))
            created = service.ingest_event(event)
            return {
                "success": True, "step": "resident", "action": "schedule-event",
                "created_occurrence_ids": created,
            }
        if action == "replay":
            grant = AuthorizationGrant.model_validate_json(
                Path(args.grant_file).expanduser().resolve().read_text(encoding="utf-8")
            )
            created = service.replay(args.occurrence_id, grant=grant)
            return {
                "success": True, "step": "resident", "action": "schedule-replay",
                "occurrence_id": created, "replay_of_occurrence_id": args.occurrence_id,
            }
        if action == "run-once":
            receipt = asyncio.run(service.run_due_once(worker_id=args.worker_id))
            return {
                "success": True, "step": "resident", "action": "schedule-run-once",
                "receipt": receipt.model_dump(),
            }
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        raise CliError("schedule_rejected", str(exc)) from exc
    raise CliError("invalid_args", f"unknown schedule action: {action}")


def _resident_queue_subagent_successor(
    root: Path, config: ResidentConfig, args: argparse.Namespace
) -> dict[str, Any]:
    from .subagent import SubagentQueueError, launch_subagent_task

    if args.prompt_file:
        try:
            prompt = Path(args.prompt_file).expanduser().read_text(encoding="utf-8")
        except OSError as exc:
            raise CliError("invalid_args", f"cannot read --prompt-file: {exc}") from exc
    else:
        prompt = str(args.prompt or "")
    if not prompt.strip():
        raise CliError("invalid_args", "queued successor prompt must not be empty")
    project_dir = str(Path(args.project_dir).expanduser().resolve()) if args.project_dir else str(root)
    try:
        result = asyncio.run(
            launch_subagent_task(
                config,
                task=prompt.strip(),
                description=args.description,
                project_dir=project_dir,
                depends_on_run_id=getattr(args, "after_run_id", None),
                depends_on_run_ids=getattr(args, "after_run_ids", None),
                queue_max_launch_attempts=args.max_launch_attempts,
            )
        )
    except (SubagentQueueError, ValueError, OSError) as exc:
        raise CliError("queue_rejected", str(exc)) from exc
    try:
        manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise CliError(
            "queue_rejected", "queued successor manifest is unavailable after commit"
        ) from exc
    queue = manifest.get("queue") if isinstance(manifest, Mapping) else None
    predecessor_run_ids = (
        list(queue.get("predecessor_run_ids") or [])
        if isinstance(queue, Mapping)
        else []
    )
    return {
        "success": True,
        "step": "resident",
        "action": "queue-subagent-successor",
        "run_id": result.run_id,
        "status": result.status,
        "predecessor_run_id": (
            predecessor_run_ids[0] if len(predecessor_run_ids) == 1 else None
        ),
        "predecessor_run_ids": predecessor_run_ids,
        "authorization_mode": _queue_authorization_mode(queue),
        "manifest_path": result.manifest_path,
        "description": result.description,
    }


def _queue_authorization_mode(queue: object) -> str:
    if not isinstance(queue, Mapping):
        return "invalid_queue_contract"
    authorization = queue.get("cross_request_authorization")
    if isinstance(authorization, Mapping):
        return str(authorization.get("mode") or "invalid_cross_request_authorization")[:80]
    authorizations = queue.get("cross_request_authorizations")
    if not isinstance(authorizations, list):
        return "same_request_custody"
    modes = {
        str(item.get("mode") or "invalid_cross_request_authorization")[:80]
        for item in authorizations
        if isinstance(item, Mapping)
    }
    return next(iter(modes)) if len(modes) == 1 else "invalid_cross_request_authorization"


def _resident_inspect_subagent_queue(
    root: Path, args: argparse.Namespace
) -> dict[str, Any]:
    from .subagent import list_managed_resident_agents

    if args.limit < 1 or args.limit > 25:
        raise CliError("invalid_args", "inspect-subagent-queue --limit must be 1..25")
    project_dir = Path(args.project_dir).expanduser().resolve() if args.project_dir else root
    inventory = list_managed_resident_agents(
        project_root=project_dir,
        workspace_root=None,
        recent_limit=args.limit,
        queue_limit=args.limit,
    )
    rows = list(inventory.get("queued") or []) + [
        row
        for row in inventory.get("recent") or []
        if isinstance(row, dict) and isinstance(row.get("queue"), dict)
    ]
    if args.run_id:
        rows = [row for row in rows if row.get("run_id") == args.run_id]
        if not rows:
            raise CliError("not_found", f"queued resident run not found: {args.run_id}")
    bounded = []
    for row in rows[: args.limit]:
        queue = dict(row.get("queue") or {})
        authored = queue.get("authored_prompt")
        authored = authored if isinstance(authored, dict) else {}
        references = []
        for ref in list(queue.get("predecessor_references") or [])[:24]:
            if not isinstance(ref, dict):
                continue
            references.append(
                {
                    "schema_version": str(ref.get("schema_version") or "")[:80],
                    "run_id": str(ref.get("run_id") or "")[:96],
                    "artifact_type": str(ref.get("artifact_type") or "")[:32],
                    "path": str(ref.get("path") or "")[:4096],
                    "content_inlined": bool(ref.get("content_inlined")),
                }
            )
        predecessor_run_ids = [
            str(value)[:96]
            for value in list(queue.get("predecessor_run_ids") or [])[:8]
            if isinstance(value, str)
        ]
        if not predecessor_run_ids and queue.get("predecessor_run_id"):
            predecessor_run_ids = [str(queue.get("predecessor_run_id"))[:96]]
        predecessor_states = []
        for state in list(queue.get("predecessor_states") or [])[:8]:
            if not isinstance(state, Mapping):
                continue
            predecessor_states.append(
                {
                    "run_id": str(state.get("run_id") or "")[:96],
                    "status": str(state.get("status") or "")[:48],
                    "result_state": str(state.get("result_state") or "")[:48],
                    "attention": str(state.get("attention") or "")[:120],
                }
            )
        bounded.append(
            {
                "run_id": str(row.get("run_id") or "")[:96],
                "status": str(row.get("status") or "")[:48],
                "description": str(row.get("description") or "")[:180],
                "predecessor_run_id": str(queue.get("predecessor_run_id") or "")[:96],
                "predecessor_run_ids": predecessor_run_ids,
                "predecessor_states": predecessor_states,
                "failed_predecessor_run_id": str(
                    queue.get("failed_predecessor_run_id") or ""
                )[:96],
                "successor_run_id": str(queue.get("successor_run_id") or "")[:96],
                "dependency_state": str(queue.get("state") or "")[:48],
                "predecessor_status": str(queue.get("predecessor_status") or "")[:48],
                "attention": str(queue.get("attention") or "")[:120],
                "authorization_mode": _queue_authorization_mode(queue),
                "attempt_count": (
                    max(0, min(queue["attempt_count"], 10_000))
                    if isinstance(queue.get("attempt_count"), int)
                    and not isinstance(queue.get("attempt_count"), bool)
                    else None
                ),
                "max_launch_attempts": (
                    max(0, min(queue["max_launch_attempts"], 10_000))
                    if isinstance(queue.get("max_launch_attempts"), int)
                    and not isinstance(queue.get("max_launch_attempts"), bool)
                    else None
                ),
                "authored_prompt": {
                    "description": str(authored.get("description") or "")[:180],
                    "size_chars": (
                        max(0, min(authored["size_chars"], 40_000))
                        if isinstance(authored.get("size_chars"), int)
                        and not isinstance(authored.get("size_chars"), bool)
                        else None
                    ),
                },
                "predecessor_references": references,
            }
        )
    return {
        "success": True,
        "step": "resident",
        "action": "inspect-subagent-queue",
        "items": bounded,
        "count": len(bounded),
        "queued_total_count": inventory.get("queued_count", 0),
        "omitted_count": max(0, len(rows) - len(bounded)),
    }


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
    schedule_health: dict[str, Any] = {"supported": False, "reason": "database multi-worker schedule store not enabled"}
    from .schedules import ScheduleService, schedule_store_root, utc_now as schedule_utc_now
    if schedule_root := schedule_store_root(store):
        service = ScheduleService(schedule_root)
        definitions = service.repo.definitions()
        occurrences = service.repo.occurrences()
        schedule_health = {
            "supported": True,
            "definition_count": len(definitions),
            "state_counts": {
                state: sum(row.state == state for row in definitions)
                for state in ("draft", "active", "paused", "cancelled", "exhausted")
            },
            "occurrence_state_counts": {
                state: sum(row.state == state for row in occurrences)
                for state in ("scheduled", "claimed", "launch_committed", "launched", "terminal", "suppressed", "cancelled", "dead_letter")
            },
            "stale_claim_count": sum(
                row.state == "claimed" and row.claim_expires_at is not None
                and row.claim_expires_at <= schedule_utc_now()
                for row in occurrences
            ),
            "orphan_launch_commit_count": sum(
                row.state == "launch_committed" and not row.run_id for row in occurrences
            ),
            "next_nominal": {
                row.schedule_id: (
                    service.preview(row, count=1)[0].isoformat()
                    if row.state == "active" and service.preview(row, count=1)
                    else None
                )
                for row in definitions
            },
        }
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
        "resident_schedules": schedule_health,
    }


def _resident_read_reply_chain(
    store: Store,
    *,
    source_message_id: str | None,
    cursor: str | None,
    limit: int,
) -> dict[str, Any]:
    """Constrained CLI twin of the resident read_reply_chain function tool."""

    if limit < 1 or limit > 10:
        raise CliError("invalid_args", "read-reply-chain --limit must be between 1 and 10")
    provenance = provenance_from_environment(strict=True)
    if not provenance or provenance.get("applicability") != "applicable":
        raise CliError(
            "authorization_denied",
            "read-reply-chain requires one immutable Discord resident source envelope",
        )
    conversation_id = str(provenance.get("resident_conversation_id") or "").strip()
    if not conversation_id:
        raise CliError("authorization_denied", "resident conversation provenance is unavailable")

    cursor_source = None
    offset = 0
    if cursor:
        try:
            cursor_source, offset = decode_reply_cursor(cursor)
        except ValueError as exc:
            raise CliError("invalid_cursor", str(exc)) from exc
    requested = (source_message_id or "").strip() or cursor_source
    if not requested:
        requested = str(
            provenance.get("source_record_id") or provenance.get("discord_message_id") or ""
        ).strip()
    if not requested:
        raise CliError("invalid_args", "reply-chain source message is unavailable")

    message = store.load_message(requested)
    if message is not None and message.conversation_id != conversation_id:
        raise CliError(
            "authorization_denied", "reply-chain source is outside the active conversation"
        )
    if message is None:
        message = store.find_conversation_message_by_discord_id(conversation_id, requested)
    if message is None:
        raise CliError("not_found", "reply-chain source was not found in the active conversation")
    if cursor_source is not None and cursor_source != message.id:
        raise CliError("invalid_cursor", "cursor does not belong to the requested source message")
    return {
        "success": True,
        "step": "resident",
        "action": "read-reply-chain",
        **reply_chain_page(message, offset=offset, limit=limit),
    }


def _resident_status_tree(
    config: ResidentConfig,
    *,
    node_id: str,
    cursor: int,
    limit: int,
) -> dict[str, Any]:
    if cursor < 0:
        raise CliError("invalid_args", "status-tree --cursor must be non-negative")
    if limit < 1 or limit > MAX_NODE_LIMIT:
        raise CliError(
            "invalid_args", f"status-tree --limit must be between 1 and {MAX_NODE_LIMIT}"
        )
    snapshot, degraded_reason = status_snapshot.load_cloud_status_snapshot(
        config.status_snapshot_path,
        max_age_s=2 * 60 * 60,
    )
    if snapshot is None:
        raise CliError(
            "status_unavailable",
            degraded_reason or "canonical cloud status snapshot is unavailable",
        )
    if degraded_reason:
        snapshot = _sanitize_stale_snapshot(snapshot, degraded_reason)
    result = read_cloud_status_node(snapshot, node_id=node_id, cursor=cursor, limit=limit)
    if not result.get("success"):
        raise CliError("status_node_not_found", str(result.get("error") or "node read failed"))
    return {
        "success": True,
        "step": "resident",
        "action": "status-tree",
        "degraded_reason": degraded_reason,
        "node": result["node"],
    }


def _resident_context_tree(
    store: Store,
    config: ResidentConfig,
    *,
    action: str,
    conversation_id: str | None,
    node_id: str,
    scope: str | None,
    query: str,
    cursor: int,
    limit: int,
) -> dict[str, Any]:
    if cursor < 0 or limit < 1 or limit > MAX_NODE_LIMIT:
        raise CliError("invalid_args", f"cursor must be non-negative and limit 1..{MAX_NODE_LIMIT}")
    resolved_conversation = conversation_id
    if not resolved_conversation:
        provenance = provenance_from_environment(strict=False)
        if provenance:
            resolved_conversation = str(provenance.get("resident_conversation_id") or "") or None
    resolved_conversation = resolved_conversation or "cli-context"
    profile = MegaplanResidentProfile(store=store, config=config)
    asyncio.run(profile.load_hot_context(resolved_conversation))
    sources = profile._context_source_cache[resolved_conversation]
    result = (
        read_context_node(sources, node_id=node_id, cursor=cursor, limit=limit)
        if action == "context"
        else search_context(
            sources,
            scope=str(scope or ""),
            query=query,
            cursor=cursor,
            limit=limit,
        )
    )
    if not result.get("success"):
        raise CliError("context_node_error", str(result.get("error") or "context read failed"))
    return {"success": True, "step": "resident", "action": action, "node": result["node"]}


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
        reaction_effect_root=(
            Path(getattr(store, "root", None) or root / ".megaplan/resident")
            / "discord_reaction_effects"
        ),
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
