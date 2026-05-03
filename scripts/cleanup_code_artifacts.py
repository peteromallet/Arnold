#!/usr/bin/env python
"""Delete expired code artifact API cache rows."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_kit.store.sqlite import SQLiteStore


def cleanup_expired_api_cache(store, *, now: str | None = None) -> int:
    return store.cleanup_expired_api_cache(now=now)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete expired kind='api_cache' code_artifacts rows."
    )
    parser.add_argument(
        "--store",
        choices=("sqlite", "supabase"),
        default=os.environ.get("ARNOLD_STORE", "sqlite"),
    )
    parser.add_argument(
        "--db",
        default=os.environ.get("ARNOLD_DB", "arnold.db"),
        help="SQLite database path when --store=sqlite.",
    )
    parser.add_argument(
        "--now",
        default=None,
        help="Optional ISO timestamp override, mainly for local smoke checks.",
    )
    args = parser.parse_args()

    store = _build_store(args.store, args.db)
    try:
        checked_at = args.now or datetime.now(UTC).isoformat().replace("+00:00", "Z")
        deleted = cleanup_expired_api_cache(store, now=checked_at)
    finally:
        close = getattr(store, "close", None)
        if close is not None:
            close()

    print(json.dumps({"deleted": deleted, "checked_at": checked_at}, sort_keys=True))
    return 0


def _build_store(kind: str, db_path: str):
    if kind == "sqlite":
        return SQLiteStore(Path(db_path))

    from agent_kit.store.supabase import SupabaseStore

    return SupabaseStore.from_env()


if __name__ == "__main__":
    raise SystemExit(main())
