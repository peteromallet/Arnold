"""M4 T12 — Minimal git-bisect-shaped oracle consumer.

Wraps :func:`megaplan.orchestration.oracle.run` to classify a single
command invocation as ``good`` (exit==0) or ``bad`` (exit!=0) and emit a
red/blue branching log line.  The point of this tool is not to be a
production bisect harness; it exists so the oracle ships with a real
*consumer* rather than the oracle being dead code.

Usage::

    python tools/m4_oracle_bisect.py -- some-command --arg1 --arg2

The exit code mirrors the wrapped command (0 if good, non-zero if bad).
"""
from __future__ import annotations

import sys
from typing import Sequence

from megaplan.orchestration.oracle import OracleResult, run as oracle_run


GOOD = "\x1b[34mBLUE/good\x1b[0m"  # blue
BAD = "\x1b[31mRED/bad\x1b[0m"  # red


def classify(result: OracleResult) -> str:
    """Return ``"good"`` if exit == 0 else ``"bad"``."""
    return "good" if result.exit == 0 else "bad"


def bisect_step(cmd: Sequence[str]) -> tuple[str, OracleResult]:
    """Run ``cmd`` once via the oracle and emit a branching log line.

    Returns ``(verdict, OracleResult)`` so callers (and tests) can drive
    further bisect logic off the classification.
    """
    result = oracle_run(list(cmd))
    verdict = classify(result)
    label = GOOD if verdict == "good" else BAD
    print(f"oracle_bisect: {label} cmd={list(cmd)!r} exit={result.exit}")
    return verdict, result


def main(argv: Sequence[str]) -> int:
    if not argv:
        print("usage: m4_oracle_bisect.py -- <cmd> [args...]", file=sys.stderr)
        return 2
    # Strip a leading "--" separator if present (common bisect convention).
    cmd = list(argv)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print("usage: m4_oracle_bisect.py -- <cmd> [args...]", file=sys.stderr)
        return 2
    verdict, result = bisect_step(cmd)
    return 0 if verdict == "good" else result.exit


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
