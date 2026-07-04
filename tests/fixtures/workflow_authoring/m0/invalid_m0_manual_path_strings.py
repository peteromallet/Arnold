from __future__ import annotations

from arnold.pipeline import step, workflow


@step(id="critique", inputs={"draft"}, outputs={"findings"})
def critique(draft: str) -> str:
    ...


@workflow(id="manual_path_workflow", inputs={"draft"}, outputs={"findings"})
def manual_path_workflow(draft: str) -> str:
    # REJECTED — manual path string
    path = f"review/{draft[:8]}/critique"
    findings = critique(draft)
    return findings
