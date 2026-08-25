"""Stdlib-only launch guards for first-run onboarding.

This module is intentionally dependency-free so the primary `arnold` entry
point can evaluate the guard WITHOUT paying the onboarding import cost —
the full flow chain loads only when the offer is actually accepted.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence


def should_offer(
    *,
    stdin_tty: bool,
    stderr_tty: bool,
    message: bool,
    flags: Sequence[str],
    environ: Mapping[str, str] = os.environ,
) -> bool:
    """Pure guard — ALL conditions must hold to offer the flow.

    - stdin AND stderr are TTYs (strictly an interactive-terminal offer)
    - not ``--message`` one-shot mode
    - no ``-c`` / ``--resume`` / ``--session-dir`` flag (those runs have
      their own contract and must fail closed byte-for-byte as today)
    - ``CI`` unset (empty value counts as unset), ``ARNOLD_STOCK_OMP != 1``,
      ``MEGAPLAN_RESIDENT_MODE`` unset (empty counts as unset).
    """
    if not (stdin_tty and stderr_tty):
        return False
    if message:
        return False
    for flag in flags:
        if flag in ("-c", "--resume", "--session-dir") or flag.startswith(
            ("--resume=", "--session-dir=")
        ):
            return False
    if environ.get("CI"):
        return False
    if environ.get("ARNOLD_STOCK_OMP") == "1":
        return False
    if environ.get("MEGAPLAN_RESIDENT_MODE"):
        return False
    return True
