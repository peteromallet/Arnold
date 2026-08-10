from __future__ import annotations

from arnold.kernel import CapabilityCheck, CapabilityId, DispatchKey


def test_capability_identity_and_dispatch_key_are_policy_neutral() -> None:
    capability = CapabilityId("human", "review")
    dispatch = DispatchKey(capability, route="operator")
    check = CapabilityCheck(capability, allowed=False, reason="missing approval")

    assert capability.value == "human:review"
    assert dispatch.route == "operator"
    assert check.reason == "missing approval"
