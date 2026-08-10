from __future__ import annotations

from arnold.workflow.authoring import Pipeline

# REJECTED — manual graph nodes
pipeline = Pipeline()
pipeline.add(Stage(name="plan", handler=plan_handler))
pipeline.add(Stage(name="execute", handler=execute_handler))
pipeline.add(Edge("plan", "execute"))
pipeline.add(Stage(name="review", handler=review_handler))
pipeline.add(Edge("execute", "review"))
