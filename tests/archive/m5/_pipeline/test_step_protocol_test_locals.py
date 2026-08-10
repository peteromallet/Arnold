"""T3c — verify test-local Step subclasses satisfy Step Protocol."""
from __future__ import annotations

import pytest

pytest.skip("archived legacy step protocol surface", allow_module_level=True)

from arnold.pipelines.megaplan._pipeline.types import Step


def test_prep_finalize_satisfy_step():
    from tests.test_pipeline_compose import PrepStep, FinalizeStep
    for cls in (PrepStep, FinalizeStep):
        inst = cls()
        assert hasattr(inst, "produces")
        assert hasattr(inst, "consumes")
        assert isinstance(inst, Step)


def test_sleepy_satisfies_step():
    # SleepyStep is defined inside a test function; re-define equivalently.
    from dataclasses import dataclass
    from typing import ClassVar

    @dataclass
    class SleepyStep:
        name: str = "x"
        kind: str = "produce"
        prompt_key: str | None = None
        slot: str | None = None
        sleep_s: float = 0.0
        output_label: str = "out"
        produces: ClassVar[tuple] = ()
        consumes: ClassVar[tuple] = ()

        def run(self, ctx):  # pragma: no cover
            raise NotImplementedError

    inst = SleepyStep()
    assert hasattr(inst, "produces") and hasattr(inst, "consumes")
    assert isinstance(inst, Step)


def test_noop_satisfies_step():
    from tests.test_pipelines_check_validator import _NoopStep
    inst = _NoopStep()
    assert hasattr(inst, "produces") and hasattr(inst, "consumes")
    assert isinstance(inst, Step)


def test_label_step_satisfies_step():
    from tests.test_pipeline_typed_edges import _LabelStep
    inst = _LabelStep()
    assert hasattr(inst, "produces") and hasattr(inst, "consumes")
    assert isinstance(inst, Step)
