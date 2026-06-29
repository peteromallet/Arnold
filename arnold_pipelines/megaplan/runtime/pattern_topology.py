"""Small product-local topology helpers for migrated Megaplan mirrors."""

from __future__ import annotations

from typing import Any

from arnold.pipeline.types import Edge, ParallelStage, Step, StepResult


def panel_parallel(
    name: str,
    reviewers: tuple[tuple[str, Step], ...],
    *,
    edges: tuple[Edge, ...] = (),
    merge_strategy: str = "none",
    max_workers: int | None = None,
    next_label: str = "next",
    **_kwargs: Any,
) -> ParallelStage:
    del merge_strategy

    def join(results: dict[str, StepResult]) -> StepResult:
        outputs = {
            f"{reviewer_id}.{label}": path
            for reviewer_id, result in results.items()
            for label, path in result.outputs.items()
        }
        return StepResult(outputs=outputs, next=next_label)

    return ParallelStage(
        name=name,
        steps=reviewers,
        join=join,
        edges=edges,
        max_workers=max_workers,
    )


__all__ = ["panel_parallel"]
