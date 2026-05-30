"""T3b: every production Step exposes produces/consumes and satisfies the Step Protocol."""

from __future__ import annotations

import pytest

from megaplan._pipeline.types import Step


def _step_classes():
    from megaplan._pipeline.steps.agent import AgentStep
    from megaplan._pipeline.steps.panel import PanelReviewerStep
    from megaplan._pipeline.steps.human_gate import HumanDecisionStep
    from megaplan._pipeline.subloop import SubloopStep
    from megaplan._pipeline.pattern_dynamic import (
        _ConsensusStep,
        _PairedRoundStep,
        _PanelFromArtifactStep,
        _DynamicFanoutStep,
    )
    from megaplan._pipeline.stages.critique import CritiqueStep
    from megaplan._pipeline.stages.revise import ReviseStep
    from megaplan._pipeline.stages.gate import GateStep
    from megaplan._pipeline.stages.inprocess_step import InProcessHandlerStep
    from megaplan._pipeline.stages.tiebreaker import TiebreakerStep
    from megaplan._pipeline.stages.plan import PlanStep
    from megaplan._pipeline.stages.prep import PrepStep
    from megaplan._pipeline.stages.execute import ExecuteStep
    from megaplan._pipeline.stages.finalize import FinalizeStep
    from megaplan._pipeline.stages.review import ReviewStep
    from megaplan._pipeline.demo_judges import (
        JudgeClarity,
        JudgeConcreteness,
        JudgeBrevity,
        Synthesize,
    )
    from megaplan._pipeline.demos.doc_critique import DocCritic, DocReviser

    def _agent():
        return AgentStep(name="agent")

    def _panel():
        return PanelReviewerStep(name="panel")

    def _human():
        return HumanDecisionStep(name="human_gate")

    def _subloop():
        return SubloopStep()

    def _paired():
        return _PairedRoundStep()

    def _consensus():
        return _ConsensusStep(name="consensus", panel=None)

    def _panel_from_art():
        return _PanelFromArtifactStep(name="pfa")

    def _dynamic_fanout():
        return _DynamicFanoutStep(name="df")

    def _inproc():
        return InProcessHandlerStep(
            name="inproc", kind="produce", handler=lambda root, ns: {}
        )

    return [
        ("AgentStep", _agent),
        ("PanelReviewerStep", _panel),
        ("HumanDecisionStep", _human),
        ("SubloopStep", _subloop),
        ("_ConsensusStep", _consensus),
        ("_PairedRoundStep", _paired),
        ("_PanelFromArtifactStep", _panel_from_art),
        ("_DynamicFanoutStep", _dynamic_fanout),
        ("CritiqueStep", CritiqueStep),
        ("ReviseStep", ReviseStep),
        ("GateStep", GateStep),
        ("InProcessHandlerStep", _inproc),
        ("TiebreakerStep", TiebreakerStep),
        ("PlanStep", PlanStep),
        ("PrepStep", PrepStep),
        ("ExecuteStep", ExecuteStep),
        ("FinalizeStep", FinalizeStep),
        ("ReviewStep", ReviewStep),
        ("JudgeClarity", JudgeClarity),
        ("JudgeConcreteness", JudgeConcreteness),
        ("JudgeBrevity", JudgeBrevity),
        ("Synthesize", Synthesize),
        ("DocCritic", DocCritic),
        ("DocReviser", DocReviser),
    ]


@pytest.mark.parametrize("name,ctor", _step_classes())
def test_step_has_produces_consumes_and_isinstance(name, ctor):
    inst = ctor()
    assert hasattr(inst, "produces"), f"{name} missing produces"
    assert hasattr(inst, "consumes"), f"{name} missing consumes"
    assert isinstance(inst, Step), f"{name} does not satisfy Step Protocol"
