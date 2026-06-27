from __future__ import annotations

from arnold.workflow.authoring import transition, workflow


@workflow(id="invalid-intrinsic-unknown-keyword", version="1.0")
def invalid_intrinsic_unknown_keyword() -> None:
    transition(id="operator-resume", type="override", unsupported="x")
