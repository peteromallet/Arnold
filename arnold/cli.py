"""Command-line interface for Arnold invocation mode."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
from pathlib import Path
from threading import Event as ThreadingEvent
from typing import Sequence
from uuid import uuid4

from agent_kit.envelope import Envelope, EnvelopeError, StateDelta, event_to_json
from agent_kit.blob import LocalBlobStore, SupabaseStorageBlob
from agent_kit.loop import run_turn
from agent_kit.model import AnthropicModel, FakeModel
from agent_kit.store.sqlite import SQLiteStore


EXIT_CODES = {
    "completed": 0,
    "errored": 1,
    "blocked_on_caller": 2,
    "aborted": 3,
}


def main(argv: Sequence[str] | None = None) -> int:
    _load_dotenv()
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "turn":
        return _turn(args)
    if args.command == "resident":
        return _resident(args)
    parser.print_help(sys.stderr)
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arnold")
    subparsers = parser.add_subparsers(dest="command")

    turn = subparsers.add_parser(
        "turn",
        description="Run one Arnold turn. Omit --epic to start a new epic via natural language; the bot must call create_epic first.",
    )
    turn.add_argument(
        "--epic",
        default=None,
        help="Existing epic id. Omit to start a new epic via natural language; the bot must call create_epic first.",
    )
    input_group = turn.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input")
    input_group.add_argument("--from-stdin", action="store_true")
    turn.add_argument("--stream-events", action="store_true")
    turn.add_argument(
        "--attach",
        action="append",
        default=[],
        metavar="PATH",
        help="Attach an image file to this invocation. May be repeated; requires --epic.",
    )
    turn.add_argument("--store", choices=["sqlite", "supabase"], default="sqlite")
    turn.add_argument("--db", default="arnold.sqlite3")
    turn.add_argument(
        "--model-id",
        default=os.environ.get("ARNOLD_MODEL_ID", "claude-opus-4-7"),
    )

    resident = subparsers.add_parser("resident")
    resident.add_argument(
        "--model-id",
        default=os.environ.get("ARNOLD_MODEL_ID", "claude-opus-4-7"),
    )
    resident.add_argument(
        "--status-debounce-seconds",
        type=float,
        default=1.0,
    )
    return parser


def _turn(args: argparse.Namespace) -> int:
    cancel_event = ThreadingEvent()
    previous_sigint = signal.getsignal(signal.SIGINT)

    def _handle_sigint(signum, frame):  # noqa: ARG001
        cancel_event.set()

    signal.signal(signal.SIGINT, _handle_sigint)
    try:
        input_text = sys.stdin.read() if args.from_stdin else args.input
        attachments = _normalize_cli_attachment_paths(args.attach)
        store = _build_store(args)
        blob = _build_blob(args, attachments_present=bool(attachments))
        model = _build_model(args.model_id)

        def on_event(event):
            if args.stream_events:
                sys.stderr.write(event_to_json(event) + "\n")
                sys.stderr.flush()

        try:
            envelope = run_turn(
                epic_id=args.epic,
                input=input_text,
                store=store,
                model=model,
                model_id=args.model_id,
                blob=blob,
                attachments=attachments,
                on_event=on_event,
                cancel_event=cancel_event,
            )
        except Exception as exc:
            envelope = Envelope(
                turn_id=f"turn_cli_{uuid4().hex}",
                epic_id=args.epic,
                epic_state_before="unknown",
                epic_state_after="unknown",
                reply="",
                state_delta=StateDelta(),
                outcome="errored",
                error=EnvelopeError(
                    code="cli_error",
                    message=str(exc),
                    retryable=False,
                ),
            )
        finally:
            store.close()

        sys.stdout.write(envelope.to_json() + "\n")
        return EXIT_CODES[envelope.outcome]
    finally:
        signal.signal(signal.SIGINT, previous_sigint)


def _resident(args: argparse.Namespace) -> int:
    try:
        asyncio.run(_run_resident(args))
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        sys.stderr.write(f"resident failed: {exc}\n")
        return 1
    return 0


async def _run_resident(args: argparse.Namespace) -> None:
    from agent_kit.ledger import Ledger, Reconciler
    from agent_kit.resident import ResidentRunner
    from agent_kit.transport.discord import DiscordTransport

    missing = _missing_resident_env()
    if missing:
        raise RuntimeError(
            "missing required resident env vars: " + ", ".join(missing)
        )

    try:
        from groq import Groq
    except ImportError as exc:
        raise RuntimeError("groq SDK is required for arnold resident") from exc

    store = _build_supabase_store()
    blob = SupabaseStorageBlob.from_env()
    ledger = Ledger(store)
    groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    transport = DiscordTransport(
        store=store,
        blob=blob,
        ledger=ledger,
        groq_client=groq_client,
    )
    model = _build_model(args.model_id)
    reconciler = Reconciler(
        store,
        model=model,
        transport=transport,
        blob=blob,
        groq_client=groq_client,
    )
    runner = ResidentRunner(
        store=store,
        model=model,
        model_id=args.model_id,
        transport=transport,
        blob=blob,
        ledger=ledger,
        reconciler=reconciler,
        status_debounce_seconds=args.status_debounce_seconds,
    )
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass
    try:
        runner.start()
        await stop_event.wait()
    finally:
        runner.stop()
        store.close()


def _build_model(model_id: str):
    script = os.environ.get("ARNOLD_FAKE_MODEL_SCRIPT")
    if script is not None:
        return FakeModel(
            seed=os.environ.get("ARNOLD_FAKE_MODEL_SEED", "0"),
            script=json.loads(script),
        )
    return AnthropicModel(model_id=model_id)


def _build_store(args: argparse.Namespace):
    if args.store == "sqlite":
        return SQLiteStore(args.db)
    return _build_supabase_store()


def _build_blob(args: argparse.Namespace, *, attachments_present: bool = False):
    if args.store == "sqlite":
        return LocalBlobStore.for_sqlite_db(args.db)
    if attachments_present:
        return SupabaseStorageBlob.from_env()
    return None


def _normalize_cli_attachment_paths(paths: Sequence[str]) -> list[Path]:
    return [Path(path).expanduser().resolve() for path in paths]


def _build_supabase_store():
    from agent_kit.store.supabase import SupabaseStore

    return SupabaseStore.from_env()


def _load_dotenv(path: Path | None = None) -> None:
    env_path = path or Path.cwd() / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def _missing_resident_env() -> list[str]:
    from resident_chat_runtime.env import EnvSetting, read_env_settings

    specs = [
        EnvSetting("SUPABASE_DB_URL", required=True),
        EnvSetting("SUPABASE_URL", required=True),
        EnvSetting("DISCORD_BOT_TOKEN", required=True, secret=True),
        EnvSetting("DISCORD_USER_WHITELIST", required=True),
        EnvSetting("ANTHROPIC_API_KEY", required=True, secret=True),
        EnvSetting("OPENAI_API_KEY", required=True, secret=True),
        EnvSetting("GROQ_API_KEY", required=True, secret=True),
    ]
    _values, statuses = read_env_settings(specs)
    missing = [status.name for status in statuses if status.error == "missing"]
    if not (
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    ):
        missing.append("SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_ROLE_KEY")
    return missing


if __name__ == "__main__":
    raise SystemExit(main())
