"""Asset and ticket mixins for DBStore."""

from __future__ import annotations

import uuid
from typing import Any, Sequence

from arnold_pipelines.megaplan.schemas import CodeArtifact, Codebase, Feedback, Ticket, TicketEpicLink

from .common import _OBSERVATION_KINDS, _jb

class DBAssetMixin:
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
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO codebases
                (id, owner, name, repo_url, repo_workspace, default_branch, scope, group_name,
                 associated_epic_id, root_commit_sha, added_via, verified_accessible_at, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                codebase_id or str(uuid.uuid4()),
                owner.lower(), name.lower(), repo_url, repo_workspace, default_branch, scope, group_name,
                associated_epic_id, root_commit_sha, added_via, verified_accessible_at, notes,
            ],
        ).fetchone()
        return Codebase(**row)

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
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO codebases
                (id, owner, name, repo_url, repo_workspace, default_branch, scope, group_name,
                 associated_epic_id, root_commit_sha, added_via, verified_accessible_at, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (lower(owner), lower(name)) DO UPDATE SET
                repo_url             = EXCLUDED.repo_url,
                repo_workspace       = EXCLUDED.repo_workspace,
                default_branch       = EXCLUDED.default_branch,
                scope                = EXCLUDED.scope,
                group_name           = EXCLUDED.group_name,
                associated_epic_id   = EXCLUDED.associated_epic_id,
                root_commit_sha      = EXCLUDED.root_commit_sha,
                added_via            = EXCLUDED.added_via,
                verified_accessible_at = EXCLUDED.verified_accessible_at,
                notes                = EXCLUDED.notes
            RETURNING *
            """,
            [
                str(uuid.uuid4()),
                owner.lower(), name.lower(), repo_url, repo_workspace, default_branch, scope, group_name,
                associated_epic_id, root_commit_sha, added_via, verified_accessible_at, notes,
            ],
        ).fetchone()
        return Codebase(**row)

    def load_codebase(self, codebase_id: str) -> Codebase | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM codebases WHERE id = %s", [codebase_id]
        ).fetchone()
        return Codebase(**row) if row else None

    def find_codebase(self, owner: str, name: str) -> Codebase | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM codebases WHERE lower(owner) = lower(%s) AND lower(name) = lower(%s)",
            [owner, name],
        ).fetchone()
        return Codebase(**row) if row else None

    def list_codebases(
        self,
        *,
        scope: str | None = None,
        group_name: str | None = None,
        epic_id: str | None = None,
        include_global: bool = True,
    ) -> list[Codebase]:
        conn = self._get_conn()
        conditions: list[str] = []
        values: list[Any] = []
        if scope is not None:
            conditions.append("scope = %s")
            values.append(scope)
        if group_name is not None:
            conditions.append("group_name = %s")
            values.append(group_name)
        if epic_id is not None:
            if include_global:
                conditions.append("(associated_epic_id = %s OR scope = 'global')")
                values.append(epic_id)
            else:
                conditions.append("associated_epic_id = %s")
                values.append(epic_id)
        elif not include_global:
            conditions.append("scope != 'global'")
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            f"SELECT * FROM codebases{where} ORDER BY owner, name",
            values,
        ).fetchall()
        return [Codebase(**row) for row in rows]

    def update_codebase(self, codebase_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Codebase:
        conn = self._get_conn()
        set_parts = [f"{k} = %s" for k in changes]
        values = list(changes.values()) + [codebase_id]
        row = conn.execute(
            f"UPDATE codebases SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        return Codebase(**row)

    def remove_codebase(self, codebase_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM codebases WHERE id = %s", [codebase_id])

    def touch_codebase_accessed(
        self, codebase_id: str, *, accessed_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> Codebase:
        conn = self._get_conn()
        if accessed_at is not None:
            row = conn.execute(
                "UPDATE codebases SET last_accessed_at = %s WHERE id = %s RETURNING *",
                [accessed_at, codebase_id],
            ).fetchone()
        else:
            row = conn.execute(
                "UPDATE codebases SET last_accessed_at = now() WHERE id = %s RETURNING *",
                [codebase_id],
            ).fetchone()
        return Codebase(**row)

    def mark_codebase_verified(
        self,
        codebase_id: str,
        *,
        verified_at: str | None = None,
        default_branch: str | None = None,
        idempotency_key: str | None = None,
    ) -> Codebase:
        conn = self._get_conn()
        set_parts = ["verified_accessible_at = " + ("%s" if verified_at else "now()")]
        values: list[Any] = [verified_at] if verified_at else []
        if default_branch is not None:
            set_parts.append("default_branch = %s")
            values.append(default_branch)
        values.append(codebase_id)
        row = conn.execute(
            f"UPDATE codebases SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        return Codebase(**row)

    def load_codebase_by_associated_epic(self, epic_id: str) -> Codebase | None:
        """Return the codebase whose associated_epic_id matches, or None."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM codebases WHERE associated_epic_id = %s",
            [epic_id],
        ).fetchone()
        return Codebase(**row) if row else None

    def resolve_codebase_by_root_sha(self, root_commit_sha: str) -> Codebase | None:
        """Find a codebase by its root_commit_sha."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM codebases WHERE root_commit_sha = %s",
            [root_commit_sha],
        ).fetchone()
        return Codebase(**row) if row else None

    def create_ticket(
        self,
        *,
        codebase_id: str,
        title: str,
        body: str = "",
        source: str = "human",
        tags: list[str] | None = None,
        filed_by_actor_id: str | None = None,
        filed_in_turn_id: str | None = None,
        slug: str,
        ticket_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Ticket:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO tickets
                (id, codebase_id, title, body, status, source, tags,
                 filed_by_actor_id, filed_in_turn_id, slug)
            VALUES (%s, %s, %s, %s, 'open', %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                ticket_id or str(uuid.uuid4()),
                codebase_id, title, body, source,
                tags or [], filed_by_actor_id, filed_in_turn_id, slug,
            ],
        ).fetchone()
        return Ticket(**row)

    def load_ticket(self, ticket_id: str) -> Ticket | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM tickets WHERE id = %s", [ticket_id]
        ).fetchone()
        return Ticket(**row) if row else None

    def list_tickets(
        self,
        *,
        codebase_id: str | None = None,
        codebase_ids: Sequence[str] | None = None,
        status: str | None = None,
        tags: Sequence[str] | None = None,
        keywords: Sequence[str] | None = None,
        keywords_all: bool = False,
        sort: str = "created",
        order: str = "desc",
        limit: int | None = None,
    ) -> list[Ticket]:
        """List tickets with optional keyword / multi-project / sort filters.

        Parameters
        ----------
        codebase_id:
            Single-codebase filter (legacy).  Ignored if *codebase_ids* given.
        codebase_ids:
            Restrict to these codebases (cross-project search).
        keywords:
            Case-insensitive substring matches across title, body, tags,
            and resolution_note.  Default semantics: OR (any keyword
            matches).  Pass *keywords_all=True* for AND semantics.
        sort:
            One of ``created``, ``edited``, ``length``, ``title``.
        order:
            ``asc`` or ``desc``.
        """
        conn = self._get_conn()
        conditions: list[str] = []
        values: list[Any] = []
        if codebase_ids is not None:
            conditions.append("codebase_id = ANY(%s)")
            values.append(list(codebase_ids))
        elif codebase_id is not None:
            conditions.append("codebase_id = %s")
            values.append(codebase_id)
        if status is not None:
            conditions.append("status = %s")
            values.append(status)
        if tags is not None:
            conditions.append("tags && %s")
            values.append(list(tags))
        if keywords:
            kw_clauses: list[str] = []
            for kw in keywords:
                pat = f"%{kw}%"
                # tags: array_to_string lets us substring-match tag values
                kw_clauses.append(
                    "(title ILIKE %s OR body ILIKE %s "
                    "OR COALESCE(resolution_note, '') ILIKE %s "
                    "OR array_to_string(COALESCE(tags, ARRAY[]::text[]), ' ') ILIKE %s)"
                )
                values.extend([pat, pat, pat, pat])
            joiner = " AND " if keywords_all else " OR "
            conditions.append("(" + joiner.join(kw_clauses) + ")")
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        sort_col = {
            "created": "created_at",
            "edited": "last_edited_at",
            "length": "LENGTH(COALESCE(body, ''))",
            "title": "title",
        }.get(sort, "created_at")
        order_kw = "ASC" if order.lower() == "asc" else "DESC"

        sql = f"SELECT * FROM tickets{where} ORDER BY {sort_col} {order_kw}"
        if limit is not None:
            sql += " LIMIT %s"
            values.append(limit)
        rows = conn.execute(sql, values).fetchall()
        return [Ticket(**row) for row in rows]

    def update_ticket(self, ticket_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Ticket:
        conn = self._get_conn()
        set_parts = [f"{k} = %s" for k in changes]
        values: list[Any] = list(changes.values())
        # Always bump last_edited_at (LWW)
        set_parts.append("last_edited_at = now()")
        values.append(ticket_id)
        row = conn.execute(
            f"UPDATE tickets SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        return Ticket(**row)

    def link_ticket_to_epic(
        self,
        *,
        ticket_id: str,
        epic_id: str,
        resolves_on_complete: bool = False,
        kind: str = "associated",
        provenance: str | None = None,
        idempotency_key: str | None = None,
    ) -> TicketEpicLink:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO ticket_epics
                (ticket_id, epic_id, resolves_on_complete, kind, provenance)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (ticket_id, epic_id) DO UPDATE SET
                resolves_on_complete = EXCLUDED.resolves_on_complete,
                kind = EXCLUDED.kind,
                provenance = EXCLUDED.provenance
            RETURNING *
            """,
            [ticket_id, epic_id, resolves_on_complete, kind, provenance],
        ).fetchone()
        return TicketEpicLink(**row)

    def unlink_ticket_from_epic(
        self,
        *,
        ticket_id: str,
        epic_id: str,
        idempotency_key: str | None = None,
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM ticket_epics WHERE ticket_id = %s AND epic_id = %s",
            [ticket_id, epic_id],
        )

    def list_ticket_epic_links(
        self,
        *,
        ticket_id: str | None = None,
        epic_id: str | None = None,
    ) -> list[TicketEpicLink]:
        conn = self._get_conn()
        conditions: list[str] = []
        values: list[Any] = []
        if ticket_id is not None:
            conditions.append("ticket_id = %s")
            values.append(ticket_id)
        if epic_id is not None:
            conditions.append("epic_id = %s")
            values.append(epic_id)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            f"SELECT * FROM ticket_epics{where} ORDER BY linked_at DESC",
            values,
        ).fetchall()
        return [TicketEpicLink(**row) for row in rows]

    def address_tickets_resolved_by_epic(self, epic_id: str) -> list[str]:
        """Flip open tickets linked to *epic_id* with resolves_on_complete=true to 'addressed'.

        Returns the list of ticket ids that were updated (empty if none).
        Idempotent: already-addressed tickets are skipped by the status='open' filter.
        """
        conn = self._get_conn()
        rows = conn.execute(
            """
            UPDATE tickets
            SET status = 'addressed',
                resolution_note = %s,
                addressed_at = now()
            FROM ticket_epics
            WHERE ticket_epics.epic_id = %s
              AND ticket_epics.resolves_on_complete = true
              AND tickets.status = 'open'
              AND tickets.id = ticket_epics.ticket_id
            RETURNING tickets.id
            """,
            [f"Resolved by epic {epic_id} completing.", epic_id],
        ).fetchall()
        return [row["id"] for row in rows]

    def create_code_artifact(
        self,
        *,
        kind: str,
        source: str,
        content: str,
        codebase_id: str | None = None,
        epic_id: str | None = None,
        file_path: str | None = None,
        line_range: Any = None,
        scope: str | None = None,
        content_summary: str | None = None,
        metadata: dict | None = None,
        expires_at: str | None = None,
        artifact_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CodeArtifact:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO code_artifacts
                (id, codebase_id, epic_id, kind, source, file_path, line_range,
                 scope, content, content_summary, metadata, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                artifact_id or str(uuid.uuid4()),
                codebase_id, epic_id, kind, source, file_path,
                _jb(line_range), scope, content, content_summary,
                _jb(metadata or {}), expires_at,
            ],
        ).fetchone()
        return CodeArtifact(**row)

    def load_code_artifact(self, artifact_id: str) -> CodeArtifact | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM code_artifacts WHERE id = %s", [artifact_id]
        ).fetchone()
        return CodeArtifact(**row) if row else None

    def list_code_artifacts(
        self,
        *,
        codebase_id: str | None = None,
        epic_id: str | None = None,
        kind: str | None = None,
        source: str | None = None,
        file_path: str | None = None,
        scope: str | None = None,
        include_expired: bool = True,
        limit: int | None = 50,
    ) -> list[CodeArtifact]:
        conn = self._get_conn()
        conditions: list[str] = []
        values: list[Any] = []
        if codebase_id is not None:
            conditions.append("codebase_id = %s")
            values.append(codebase_id)
        if epic_id is not None:
            conditions.append("epic_id = %s")
            values.append(epic_id)
        if kind is not None:
            conditions.append("kind = %s")
            values.append(kind)
        if source is not None:
            conditions.append("source = %s")
            values.append(source)
        if file_path is not None:
            conditions.append("file_path = %s")
            values.append(file_path)
        if scope is not None:
            conditions.append("scope = %s")
            values.append(scope)
        if not include_expired:
            conditions.append("(expires_at IS NULL OR expires_at > now())")
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"SELECT * FROM code_artifacts{where} ORDER BY created_at DESC"
        if limit is not None:
            sql += " LIMIT %s"
            values.append(limit)
        rows = conn.execute(sql, values).fetchall()
        return [CodeArtifact(**row) for row in rows]

    def update_code_artifact(self, artifact_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> CodeArtifact:
        conn = self._get_conn()
        set_parts = [f"{k} = %s" for k in changes]
        values = list(changes.values()) + [artifact_id]
        row = conn.execute(
            f"UPDATE code_artifacts SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        return CodeArtifact(**row)

    def delete_code_artifact(self, artifact_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM code_artifacts WHERE id = %s", [artifact_id])

    def touch_code_artifact_used(
        self, artifact_id: str, *, used_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> CodeArtifact:
        conn = self._get_conn()
        if used_at is not None:
            row = conn.execute(
                "UPDATE code_artifacts SET last_used_at = %s WHERE id = %s RETURNING *",
                [used_at, artifact_id],
            ).fetchone()
        else:
            row = conn.execute(
                "UPDATE code_artifacts SET last_used_at = now() WHERE id = %s RETURNING *",
                [artifact_id],
            ).fetchone()
        return CodeArtifact(**row)

    def get_api_cache(
        self,
        cache_key: str,
        *,
        now: str | None = None,
        touch: bool = True,
    ) -> CodeArtifact | None:
        conn = self._get_conn()
        now_expr = "%s" if now else "now()"
        now_values: list[Any] = [now] if now else []
        row = conn.execute(
            f"""
            SELECT * FROM code_artifacts
            WHERE kind = 'api_cache'
              AND metadata->>'cache_key' = %s
              AND (expires_at IS NULL OR expires_at > {now_expr})
            LIMIT 1
            """,
            [cache_key] + now_values,
        ).fetchone()
        if row is None:
            return None
        if touch:
            row = conn.execute(
                "UPDATE code_artifacts SET last_used_at = now() WHERE id = %s RETURNING *",
                [row["id"]],
            ).fetchone()
        return CodeArtifact(**row)

    def upsert_api_cache(
        self,
        *,
        cache_key: str,
        content: str,
        content_summary: str | None = None,
        metadata: dict | None = None,
        codebase_id: str | None = None,
        epic_id: str | None = None,
        file_path: str | None = None,
        scope: str | None = None,
        expires_at: str | None = None,
        ttl_seconds: int = 3600,
        idempotency_key: str | None = None,
    ) -> CodeArtifact:
        conn = self._get_conn()
        full_meta = dict(metadata or {})
        full_meta["cache_key"] = cache_key
        expires_expr = "%s" if expires_at else "now() + interval '1 second' * %s"
        expires_val: Any = expires_at if expires_at else ttl_seconds
        existing = conn.execute(
            "SELECT id FROM code_artifacts WHERE kind = 'api_cache' AND metadata->>'cache_key' = %s LIMIT 1",
            [cache_key],
        ).fetchone()
        if existing:
            row = conn.execute(
                f"""
                UPDATE code_artifacts
                SET content = %s, content_summary = %s, metadata = %s,
                    codebase_id = %s, epic_id = %s, file_path = %s,
                    scope = %s, expires_at = {expires_expr}, last_used_at = now()
                WHERE id = %s
                RETURNING *
                """,
                [
                    content, content_summary, _jb(full_meta),
                    codebase_id, epic_id, file_path, scope,
                    expires_val, existing["id"],
                ],
            ).fetchone()
        else:
            row = conn.execute(
                f"""
                INSERT INTO code_artifacts
                    (id, kind, source, content, content_summary, metadata,
                     codebase_id, epic_id, file_path, scope, expires_at)
                VALUES (%s, 'api_cache', 'conversation', %s, %s, %s, %s, %s, %s, %s, {expires_expr})
                RETURNING *
                """,
                [
                    str(uuid.uuid4()), content, content_summary, _jb(full_meta),
                    codebase_id, epic_id, file_path, scope, expires_val,
                ],
            ).fetchone()
        return CodeArtifact(**row)

    def cleanup_expired_api_cache(self, *, now: str | None = None,
        idempotency_key: str | None = None,
    ) -> int:
        conn = self._get_conn()
        now_expr = "%s" if now else "now()"
        values: list[Any] = [now] if now else []
        cur = conn.execute(
            f"""
            DELETE FROM code_artifacts
            WHERE kind = 'api_cache'
              AND expires_at IS NOT NULL
              AND expires_at < {now_expr}
            """,
            values,
        )
        return cur.rowcount

    def create_feedback(
        self,
        *,
        kind: str,
        content: str,
        source: str,
        source_message_id: str | None = None,
        epic_id: str | None = None,
        turn_id: str | None = None,
        context_snapshot: dict | None = None,
        idempotency_key: str | None = None,
    ) -> Feedback:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO feedback
                (id, kind, content, source, source_message_id, epic_id,
                 turn_id, context_snapshot)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                str(uuid.uuid4()), kind, content, source, source_message_id,
                epic_id, turn_id, _jb(context_snapshot),
            ],
        ).fetchone()
        return Feedback(**row)

    def load_feedback(self, feedback_id: str) -> Feedback | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM feedback WHERE id = %s", [feedback_id]
        ).fetchone()
        return Feedback(**row) if row else None

    def update_feedback(self, feedback_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Feedback:
        conn = self._get_conn()
        set_parts = [f"{k} = %s" for k in changes]
        values = list(changes.values())
        if changes.get("resolved") is True and "resolved_at" not in changes:
            set_parts.append("resolved_at = now()")
        values.append(feedback_id)
        row = conn.execute(
            f"UPDATE feedback SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        return Feedback(**row)

    def list_feedback(
        self,
        *,
        epic_id: str | None = None,
        active: bool | None = None,
        kinds: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[Feedback]:
        conn = self._get_conn()
        conditions: list[str] = []
        values: list[Any] = []
        if epic_id is not None:
            conditions.append("epic_id = %s")
            values.append(epic_id)
        if active is not None:
            conditions.append("active = %s")
            values.append(active)
        if kinds is not None:
            conditions.append("kind = ANY(%s)")
            values.append(list(kinds))
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"SELECT * FROM feedback{where} ORDER BY created_at DESC"
        if limit is not None:
            sql += " LIMIT %s"
            values.append(limit)
        rows = conn.execute(sql, values).fetchall()
        return [Feedback(**row) for row in rows]

    def list_observations(
        self,
        *,
        resolved: bool | None = None,
        limit: int | None = None,
    ) -> list[Feedback]:
        conn = self._get_conn()
        obs_kinds = ["friction", "ambiguity", "tool_failure", "confusion", "pattern_noticed"]
        conditions = ["kind = ANY(%s)"]
        values: list[Any] = [obs_kinds]
        if resolved is not None:
            conditions.append("resolved = %s")
            values.append(resolved)
        sql = f"SELECT * FROM feedback WHERE {' AND '.join(conditions)} ORDER BY created_at DESC"
        if limit is not None:
            sql += " LIMIT %s"
            values.append(limit)
        rows = conn.execute(sql, values).fetchall()
        return [Feedback(**row) for row in rows]

__all__ = ["DBAssetMixin"]
