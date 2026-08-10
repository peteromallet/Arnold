from __future__ import annotations

from arnold.workflow.authoring import suspend, workflow


@workflow(id="invalid-intrinsic-missing-required-keyword", version="1.0")
def invalid_intrinsic_missing_required_keyword() -> None:
    suspend(capability_id="human.review")
