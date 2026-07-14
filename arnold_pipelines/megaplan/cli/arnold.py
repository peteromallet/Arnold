"""Compatibility module for ``python -m arnold_pipelines.megaplan.cli.arnold``."""

from . import _normalize_execute_compat_argv, build_parser, main

__all__ = ["_normalize_execute_compat_argv", "build_parser", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
