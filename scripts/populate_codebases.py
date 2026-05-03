#!/usr/bin/env python
"""Populate verified codebases from public GitHub org repositories."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_kit.github_client import GitHubClient
from agent_kit.store.sqlite import SQLiteStore


JSONDict = dict[str, Any]
DEFAULT_GROUPS_PATH = Path(__file__).with_name("codebase_groups.yaml")


def populate_orgs(store, client, orgs: list[str]) -> JSONDict:
    verified: list[str] = []
    inaccessible: list[JSONDict] = []
    checked_at = _now()
    for org in orgs:
        listing = client.org_repos(org)
        if not listing.get("ok"):
            inaccessible.append({"org": org, "reason": listing.get("error")})
            continue
        for repo in listing["repos"]:
            owner = str(repo["owner"]).lower()
            name = str(repo["name"]).lower()
            metadata = client.repo_metadata(owner, name)
            if not metadata.get("ok"):
                inaccessible.append({"repo": f"{owner}/{name}", "reason": metadata.get("error")})
                continue
            repo_metadata = metadata["repo"]
            store.upsert_codebase(
                owner=repo_metadata["owner"],
                name=repo_metadata["name"],
                default_branch=repo_metadata["default_branch"],
                scope="global",
                added_via="populator",
                verified_accessible_at=checked_at,
            )
            verified.append(f"{repo_metadata['owner']}/{repo_metadata['name']}")
    return {"verified": verified, "inaccessible": inaccessible}


def apply_groups(store, groups_path: Path = DEFAULT_GROUPS_PATH) -> JSONDict:
    groups = _parse_groups(groups_path)
    updated: list[str] = []
    missing: list[str] = []
    for group_name, repos in groups.items():
        for repo in repos:
            owner, name = repo.lower().split("/", 1)
            row = store.find_codebase(owner, name)
            if row is None:
                missing.append(repo.lower())
                continue
            store.update_codebase(str(row["id"]), group_name=group_name)
            updated.append(repo.lower())
    return {"updated": updated, "missing": missing}


def main() -> int:
    parser = argparse.ArgumentParser(description="Populate Arnold codebases from GitHub org listings.")
    parser.add_argument("--orgs", default="", help="Comma-separated org/user names, e.g. peteromallet,banodoco.")
    parser.add_argument("--apply-groups", action="store_true", help="Apply group_name values from scripts/codebase_groups.yaml.")
    parser.add_argument("--groups-file", default=str(DEFAULT_GROUPS_PATH))
    parser.add_argument("--store", choices=("sqlite", "supabase"), default=os.environ.get("ARNOLD_STORE", "sqlite"))
    parser.add_argument("--db", default=os.environ.get("ARNOLD_DB", "arnold.db"))
    args = parser.parse_args()

    store = _build_store(args.store, args.db)
    try:
        client = GitHubClient(store=store)
        result: JSONDict = {"verified": [], "inaccessible": []}
        orgs = [item.strip() for item in args.orgs.split(",") if item.strip()]
        if orgs:
            result.update(populate_orgs(store, client, orgs))
        if args.apply_groups:
            result["groups"] = apply_groups(store, Path(args.groups_file))
    finally:
        close = getattr(store, "close", None)
        if close is not None:
            close()

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _build_store(kind: str, db_path: str):
    if kind == "sqlite":
        return SQLiteStore(Path(db_path))

    from agent_kit.store.supabase import SupabaseStore

    return SupabaseStore.from_env()


def _parse_groups(path: Path) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    current: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line == "groups:":
            continue
        if not line.startswith("-") and line.endswith(":"):
            current = line[:-1].strip()
            groups[current] = []
        elif line.startswith("-") and current:
            groups[current].append(line[1:].strip())
    return groups


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
