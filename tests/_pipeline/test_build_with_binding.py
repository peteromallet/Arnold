"""T5 — build_with_binding flag-ON / flag-OFF behavior."""
from __future__ import annotations

import pytest

from arnold.pipelines.megaplan._core.workflow import BuildBindingError, build_with_binding
from arnold.pipelines.megaplan._pipeline.types import Edge, Pipeline, Port, PortRef, Stage


class _ProdStep:
    name = "p"
    kind = "produce"
    prompt_key = None
    slot = None
    produces = (Port(name="alpha", content_type="text/markdown"),)
    consumes = ()

    def run(self, ctx):  # pragma: no cover
        raise NotImplementedError


class _ConsStep:
    name = "c"
    kind = "produce"
    prompt_key = None
    slot = None
    produces = ()
    consumes = (PortRef(port_name="alpha", content_type="text/markdown"),)

    def run(self, ctx):  # pragma: no cover
        raise NotImplementedError


def _two_stage_pipeline() -> Pipeline:
    return Pipeline(
        stages={
            "p": Stage(name="p", step=_ProdStep(), edges=(Edge("done", "c"),)),
            "c": Stage(name="c", step=_ConsStep(), edges=(Edge("done", "halt"),)),
        },
        entry="p",
    )


@pytest.mark.parametrize("robustness", ["light", "thorough", "extreme"])
def test_build_with_binding_flag_on(monkeypatch, robustness):
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
    pipeline = _two_stage_pipeline()
    out = build_with_binding(pipeline, robustness=robustness)
    assert isinstance(out, Pipeline)
    assert out.binding_map is not None
    assert ("c", "alpha") in out.binding_map


def test_build_with_binding_unbindable_raises(monkeypatch):
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")

    class _BadCons:
        name = "c"
        kind = "produce"
        prompt_key = None
        slot = None
        produces = ()
        consumes = (PortRef(port_name="missing_port", content_type="text/markdown"),)

        def run(self, ctx):  # pragma: no cover
            raise NotImplementedError

    pipeline = Pipeline(
        stages={
            "p": Stage(name="p", step=_ProdStep(), edges=(Edge("done", "c"),)),
            "c": Stage(name="c", step=_BadCons(), edges=(Edge("done", "halt"),)),
        },
        entry="p",
    )
    with pytest.raises(BuildBindingError) as ei:
        build_with_binding(pipeline)
    assert ei.value.gradient is not None


def test_build_with_binding_flag_off_returns_unchanged(monkeypatch):
    monkeypatch.delenv("MEGAPLAN_TYPED_PORTS", raising=False)
    pipeline = _two_stage_pipeline()
    out = build_with_binding(pipeline)
    assert out is pipeline
    assert out.binding_map is None
