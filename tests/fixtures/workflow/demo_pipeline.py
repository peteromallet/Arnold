from __future__ import annotations

import arnold.workflow as workflow


def build_pipeline() -> workflow.Pipeline:
    return workflow.Pipeline(
        id="demo",
        version="1.0.0",
        steps=(
            workflow.Step(id="start", kind="noop"),
            workflow.Step(id="process", kind="task"),
            workflow.Step(id="end", kind="noop"),
        ),
        routes=(
            workflow.Route(id="r1", source="start", target="process"),
            workflow.Route(id="r2", source="process", target="end"),
        ),
    )
