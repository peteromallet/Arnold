from __future__ import annotations

from typing import Any

from megaplan.schemas import Codebase
from megaplan.schemas.base import utc_now

from .common import _new_id, _parse_datetime


class FileCodebaseMixin:
    def create_codebase(
        self,
        *,
        owner: str,
        name: str,
        default_branch: str,
        repo_url: str | None = None,
        repo_workspace: str | None = None,
        scope: str = "global",
        group_name: str | None = None,
        associated_epic_id: str | None = None,
        root_commit_sha: str | None = None,
        added_via: str = "manual",
        verified_accessible_at: str | None = None,
        notes: str | None = None,
        codebase_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Codebase:
        codebase = Codebase(
            id=codebase_id or _new_id("codebase"),
            owner=owner.lower(),
            name=name.lower(),
            repo_url=repo_url,
            repo_workspace=repo_workspace,
            default_branch=default_branch,
            scope=scope,
            group_name=group_name,
            associated_epic_id=associated_epic_id,
            root_commit_sha=root_commit_sha,
            added_at=utc_now(),
            added_via=added_via,
            verified_accessible_at=_parse_datetime(verified_accessible_at),
            notes=notes,
        )
        self._save_model(self._codebase_path(codebase.id), codebase, journal_root=self.root)
        return codebase

    def upsert_codebase(
        self,
        *,
        owner: str,
        name: str,
        default_branch: str,
        repo_url: str | None = None,
        repo_workspace: str | None = None,
        scope: str = "global",
        group_name: str | None = None,
        associated_epic_id: str | None = None,
        root_commit_sha: str | None = None,
        added_via: str = "manual",
        verified_accessible_at: str | None = None,
        notes: str | None = None,
        idempotency_key: str | None = None,
    ) -> Codebase:
        fields: dict[str, Any] = {
            "owner": owner,
            "name": name,
            "default_branch": default_branch,
            "repo_url": repo_url,
            "repo_workspace": repo_workspace,
            "scope": scope,
            "group_name": group_name,
            "associated_epic_id": associated_epic_id,
            "root_commit_sha": root_commit_sha,
            "added_via": added_via,
            "verified_accessible_at": verified_accessible_at,
            "notes": notes,
            "idempotency_key": idempotency_key,
        }
        existing = self.find_codebase(owner, name)
        if existing is None:
            return self.create_codebase(**fields)
        return self.update_codebase(existing.id, **fields)

    def load_codebase(self, codebase_id: str) -> Codebase | None:
        return self._load_model(self._codebase_path(codebase_id), Codebase)

    def find_codebase(self, owner: str, name: str) -> Codebase | None:
        owner_l = owner.lower()
        name_l = name.lower()
        for codebase in self._codebases():
            if codebase.owner == owner_l and codebase.name == name_l:
                return codebase
        return None

    def load_codebase_by_associated_epic(self, epic_id: str) -> Codebase | None:
        for codebase in self._codebases():
            if codebase.associated_epic_id == epic_id:
                return codebase
        return None

    def resolve_codebase_by_root_sha(self, root_commit_sha: str) -> Codebase | None:
        for codebase in self._codebases():
            if codebase.root_commit_sha == root_commit_sha:
                return codebase
        return None

    def list_codebases(
        self,
        *,
        scope: str | None = None,
        group_name: str | None = None,
        epic_id: str | None = None,
        include_global: bool = True,
    ) -> list[Codebase]:
        codebases = self._codebases()
        if scope is not None:
            codebases = [row for row in codebases if row.scope == scope]
        if group_name is not None:
            codebases = [row for row in codebases if row.group_name == group_name]
        if epic_id is not None:
            codebases = [
                row
                for row in codebases
                if row.associated_epic_id == epic_id or (include_global and row.scope == "global")
            ]
        elif not include_global:
            codebases = [row for row in codebases if row.scope != "global"]
        codebases.sort(key=lambda row: (row.owner, row.name, row.id))
        return codebases

    def update_codebase(self, codebase_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Codebase:
        if "owner" in changes:
            changes["owner"] = changes["owner"].lower()
        if "name" in changes:
            changes["name"] = changes["name"].lower()
        return self._update_model(self._codebase_path(codebase_id), Codebase, journal_root=self.root, **changes)

    def remove_codebase(self, codebase_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        self._delete_file(self._codebase_path(codebase_id))

    def touch_codebase_accessed(self, codebase_id: str, *, accessed_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> Codebase:
        return self.update_codebase(codebase_id, last_accessed_at=_parse_datetime(accessed_at) or utc_now())

    def mark_codebase_verified(
        self,
        codebase_id: str,
        *,
        verified_at: str | None = None,
        default_branch: str | None = None,
        idempotency_key: str | None = None,
    ) -> Codebase:
        changes: dict[str, Any] = {"verified_accessible_at": _parse_datetime(verified_at) or utc_now()}
        if default_branch is not None:
            changes["default_branch"] = default_branch
        return self.update_codebase(codebase_id, **changes)
