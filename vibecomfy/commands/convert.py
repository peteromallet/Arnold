from __future__ import annotations

import argparse
import sys


def _cmd_convert(args: argparse.Namespace) -> int:
    """Legacy `vibecomfy convert` has been removed.

    Use the canonical `vibecomfy port` commands instead:
      vibecomfy port check <workflow>      # preflight a workflow
      vibecomfy port convert <workflow>    # emit an importable Python scratchpad
    """
    print(
        "vibecomfy convert has been removed.\n"
        "Use `vibecomfy port check <workflow>` to preflight a workflow.\n"
        "Use `vibecomfy port convert <workflow> --out <path>` to emit an importable scratchpad.\n"
        "See `vibecomfy port --help` for details.",
        file=sys.stderr,
    )
    return 2


def register(subparsers) -> None:
    convert = subparsers.add_parser("convert")
    convert.add_argument("workflow")
    convert.add_argument("--out", required=True)
    convert.set_defaults(func=_cmd_convert)
