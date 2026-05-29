from __future__ import annotations

def test_workflow_uses_ir_neutral_helper_module() -> None:
    import vibecomfy.workflow as workflow

    assert workflow.workflow_helpers.__name__ == "vibecomfy._workflow_helpers"
    assert workflow.helper_resolve.__name__ == "vibecomfy._helper_resolve"


def test_porting_helpers_remains_compatibility_wrapper() -> None:
    from vibecomfy import _workflow_helpers
    from vibecomfy.porting import helpers

    assert helpers.HelperDiagnostic is _workflow_helpers.HelperDiagnostic
    assert helpers.collect_broadcast_sources is _workflow_helpers.collect_broadcast_sources
    assert helpers._node_sort_key is _workflow_helpers._node_sort_key
    assert helpers.is_api_link(["1", 0])
