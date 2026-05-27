from __future__ import annotations

from typing import Sequence

from megaplan.schemas import SecondOpinion
from megaplan.schemas.base import utc_now

from .common import _new_id, _utc_key


class FileSecondOpinionMixin:
    def create_second_opinion(
        self,
        *,
        epic_id: str,
        requested_by: str,
        focus_areas: Sequence[str],
        raw_response: str,
        score: int,
        summary: str,
        verdict: str,
        model_used: str,
        resulting_checklist_item_ids: Sequence[str] | None = None,
        idempotency_key: str | None = None,
    ) -> SecondOpinion:
        opinion = SecondOpinion(
            id=_new_id("opinion"),
            epic_id=epic_id,
            requested_at=utc_now(),
            requested_by=requested_by,
            focus_areas=list(focus_areas),
            raw_response=raw_response,
            score=score,
            summary=summary,
            verdict=verdict,
            resulting_checklist_item_ids=list(resulting_checklist_item_ids or []),
            model_used=model_used,
        )
        self._save_model(self._second_opinion_path(opinion.id), opinion, journal_root=self.root)
        return opinion

    def list_second_opinions(self, epic_id: str, *, limit: int | None = None) -> list[SecondOpinion]:
        opinions = [row for row in self._second_opinions() if row.epic_id == epic_id]
        opinions.sort(key=lambda row: (_utc_key(row.requested_at), row.id), reverse=True)
        return opinions[:limit] if limit is not None else opinions

    def set_second_opinion_checklist_items(
        self,
        second_opinion_id: str,
        checklist_item_ids: Sequence[str],
        *,
        idempotency_key: str | None = None,
    ) -> SecondOpinion:
        return self._update_model(
            self._second_opinion_path(second_opinion_id),
            SecondOpinion,
            journal_root=self.root,
            resulting_checklist_item_ids=list(checklist_item_ids),
        )
