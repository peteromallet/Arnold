from __future__ import annotations

import argparse
import json
import sys

from vibecomfy.runtime.run import smoke_runtime_sync


def _cmd_runtime_doctor(args: argparse.Namespace) -> int:
    print("runtime modes: embedded, managed, external")
    print("default `vibecomfy run` mode: auto")
    print("use `vibecomfy session start` to create a reusable managed HTTP server")
    print("use `vibecomfy run --runtime server` for one-shot managed HTTP server mode")
    print("use `vibecomfy run --runtime server --server-url URL` for external HTTP server mode")
    return 0


def _cmd_runtime_smoke(args: argparse.Namespace) -> int:
    if args.mode not in {"managed", "external"}:
        print(f"unknown smoke mode: {args.mode}", file=sys.stderr)
        return 2
    server_url = args.server_url if args.mode == "external" else None
    result = smoke_runtime_sync(server_url=server_url)
    print(json.dumps(result, indent=2))
    return 0


def register(subparsers) -> None:
    runtime = subparsers.add_parser("runtime")
    runtime_sub = runtime.add_subparsers(dest="subcmd", required=True)
    runtime_doctor = runtime_sub.add_parser("doctor")
    runtime_doctor.set_defaults(func=_cmd_runtime_doctor)
    runtime_smoke = runtime_sub.add_parser("smoke")
    runtime_smoke.add_argument("--mode", default="managed")
    runtime_smoke.add_argument("--server-url")
    runtime_smoke.set_defaults(func=_cmd_runtime_smoke)
