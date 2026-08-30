from __future__ import annotations

import argparse
from pathlib import Path

from arnold_pipelines.megaplan.workers import _impl
from arnold_pipelines.megaplan.workers._impl import AgentMode


def test_native_public_door_delegates_to_canonical_production_dispatch(tmp_path: Path, monkeypatch) -> None:
    calls: list[object] = []
    expected = (object(), "codex", "fresh", True)
    monkeypatch.setattr(_impl, "_production_worker_dispatch", lambda *args, **kwargs: calls.append(kwargs) or expected)
    result = _impl.run_step_with_worker(
        "plan", {"meta": {}}, tmp_path, argparse.Namespace(), root=tmp_path,
        resolved=AgentMode("codex", "fresh", True, "gpt-5.5", None, "gpt-5.5"),
        worker_options={"production_intent": True},
    )
    assert result == expected
    assert len(calls) == 1


def test_door_source_has_one_shared_dispatch_loop() -> None:
    source = Path(_impl.__file__).read_text(encoding="utf-8")
    assert source.count("def dispatch_with_admission") == 0
    assert source.count("dispatch_with_admission(") == 1
