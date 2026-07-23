from __future__ import annotations

from arnold_pipelines.megaplan.workers.hermes import _toolsets_for_phase


def test_finalize_uses_explicit_empty_tool_filter() -> None:
    # None means "load all tools" to AIAgent; finalize must request no tools.
    assert _toolsets_for_phase("finalize") == []
