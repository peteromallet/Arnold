from __future__ import annotations

import argparse

from vibecomfy.commands import register_commands


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vibecomfy")
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    register_commands(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
