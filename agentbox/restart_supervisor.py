"""Detached supervisor for the canonical Discord resident restart transaction."""

from __future__ import annotations

import argparse
from pathlib import Path

from agentbox.services import execute_prepared_restart


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notification-id", required=True)
    parser.add_argument("--notification-root", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = execute_prepared_restart(
        args.notification_id,
        notification_root=args.notification_root,
    )
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
