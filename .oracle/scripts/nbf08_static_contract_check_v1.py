#!/usr/bin/env python3
"""Static NBF08 lock-order / direct-save checker."""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

FORBIDDEN_REVERSE = ("fcntl.flock",)


def _check_lock_order(root: Path) -> list[str]:
    errors: list[str] = []
    path = root / "arnold_pipelines/megaplan/incident/chain_control.py"
    source = path.read_text(encoding="utf-8")
    if "sorted({str(item) for item in chain_ids" not in source and "tuple(sorted(" not in source:
        errors.append("LockedChainControlTransaction must sort chain ids before locking")
    if "sequence" not in source.lower() or "LOCK_EX" not in source:
        errors.append("sequence lock acquisition missing")
    return errors


def _check_direct_save(root: Path) -> list[str]:
    errors: list[str] = []
    spec = (root / "arnold_pipelines/megaplan/chain/spec.py").read_text(encoding="utf-8")
    epic = (root / "arnold_pipelines/megaplan/chain/epic_chain.py").read_text(encoding="utf-8")
    if "_direct" not in spec or "UnattributedStateChange" not in spec:
        errors.append("save_chain_state missing context-free bound rejection")
    if "_direct" not in epic or "UnattributedStateChange" not in epic:
        errors.append("save_epic_chain_state missing context-free bound rejection")
    return errors


def _check_sequence_migration(root: Path) -> list[str]:
    errors: list[str] = []
    ledger = (root / "arnold_pipelines/megaplan/incident/ledger.py").read_text(encoding="utf-8")
    facade = (root / "arnold_pipelines/megaplan/incident/chain_control.py").read_text(encoding="utf-8")
    if "migrate_integer_sidecar" not in ledger and "migrate_integer_sidecar" not in facade:
        errors.append("legacy .events.seq migration helper missing")
    if "nbf08-sequence-reservation-v1" not in facade:
        errors.append("structured reservation schema missing")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--check-lock-order", action="store_true")
    parser.add_argument("--check-sequence-migration", action="store_true")
    parser.add_argument("--reject-direct-save", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    errors: list[str] = []
    if args.check_lock_order:
        errors.extend(_check_lock_order(root))
    if args.check_sequence_migration:
        errors.extend(_check_sequence_migration(root))
    if args.reject_direct_save:
        errors.extend(_check_direct_save(root))
    if errors:
        for item in errors:
            print(item)
        return 1
    print("nbf08 static contract check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
