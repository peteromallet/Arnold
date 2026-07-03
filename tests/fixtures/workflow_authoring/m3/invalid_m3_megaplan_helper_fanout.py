from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import plan


@workflow(id="invalid-m3-megaplan-helper-fanout")
def flow(brief):
    async def hidden_worker(item):
        return item

    plan(id="plan", brief=brief)
