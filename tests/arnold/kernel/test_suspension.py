from __future__ import annotations

from arnold.kernel import (
    CapabilityId,
    DispatchKey,
    ReentryId,
    SuspendCapabilityRoute,
    SuspensionRecord,
    SuspensionState,
)


def test_suspension_route_is_generic_and_reentry_addressable() -> None:
    route = SuspendCapabilityRoute(
        route_id="operator",
        dispatch_key=DispatchKey(CapabilityId("human", "review")),
        reentry_id=ReentryId("resume-1"),
        payload_schema_hash="sha256:" + "1" * 64,
    )
    record = SuspensionRecord(
        run_id="run-1",
        manifest_hash="sha256:" + "a" * 64,
        node_ref="node:review",
        route=route,
    )

    assert record.state is SuspensionState.PENDING
    assert record.route.reentry_id.value == "resume-1"
