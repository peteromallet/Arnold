from __future__ import annotations

from arnold.workflow.authoring import halt, workflow


@workflow(id="invalid-intrinsic-wrong-keyword-set", version="1.0")
def invalid_intrinsic_wrong_keyword_set() -> None:
    halt(route_id="operator")
