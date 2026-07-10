from __future__ import annotations

import argparse


def _cmd_agentic(args: argparse.Namespace) -> int:
    print("agentic affordances live under `port` and `nodes` commands")
    return 0


def register(subparsers) -> None:
    parser = subparsers.add_parser("agentic", help="Show agent-oriented CLI affordance pointers.")
    parser.set_defaults(func=_cmd_agentic)
