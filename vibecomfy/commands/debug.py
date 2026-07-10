from __future__ import annotations

import argparse

from vibecomfy.commands._agent_edit_debug import add_debug_subcommands, dispatch


def _cmd_debug(args: argparse.Namespace) -> int:
    args.cmd = getattr(args, "debug_cmd", None)
    return dispatch(args)


def register(subparsers) -> None:
    debug = subparsers.add_parser("debug")
    nested = debug.add_subparsers(dest="debug_cmd")
    add_debug_subcommands(nested, per_subcommand_json=True)
    debug.set_defaults(func=_cmd_debug)
