from __future__ import annotations

from typing import Any, Sequence

from arnold.pipelines.megaplan.schemas import Feedback
from arnold.pipelines.megaplan.schemas.base import utc_now

from .common import _OBSERVATION_KINDS, _new_id, _utc_key


class FileFeedbackMixin:
    def create_feedback(
        self,
        *,
        kind: str,
        content: str,
        source: str,
        source_message_id: str | None = None,
        epic_id: str | None = None,
        turn_id: str | None = None,
        context_snapshot: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Feedback:
        feedback = Feedback(
            id=_new_id("fb"),
            kind=kind,
            content=content,
            source=source,
            source_message_id=source_message_id,
            epic_id=epic_id,
            turn_id=turn_id,
            context_snapshot=context_snapshot,
            created_at=utc_now(),
        )
        self._save_model(self._feedback_path(feedback.id), feedback, journal_root=self.root)
        return feedback

    def load_feedback(self, feedback_id: str) -> Feedback | None:
        return self._load_model(self._feedback_path(feedback_id), Feedback)

    def update_feedback(self, feedback_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Feedback:
        return self._update_model(self._feedback_path(feedback_id), Feedback, journal_root=self.root, **changes)

    def list_feedback(
        self,
        *,
        epic_id: str | None = None,
        active: bool | None = None,
        kinds: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[Feedback]:
        feedback = self._feedback_records()
        if epic_id is not None:
            feedback = [row for row in feedback if row.epic_id == epic_id]
        if active is not None:
            feedback = [row for row in feedback if row.active == active]
        if kinds is not None:
            allowed = set(kinds)
            feedback = [row for row in feedback if row.kind in allowed]
        feedback.sort(key=lambda row: (_utc_key(row.created_at), row.id), reverse=True)
        return feedback[:limit] if limit is not None else feedback

    def list_observations(self, *, resolved: bool | None = None, limit: int | None = None) -> list[Feedback]:
        feedback = [row for row in self._feedback_records() if row.kind in _OBSERVATION_KINDS]
        if resolved is not None:
            feedback = [row for row in feedback if row.resolved == resolved]
        feedback.sort(key=lambda row: (_utc_key(row.created_at), row.id), reverse=True)
        return feedback[:limit] if limit is not None else feedback
