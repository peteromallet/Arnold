"""First-class ``live_supervisor`` pipeline.

Explicit-node workflow for the Megaplan Live Watchdog Supervisor:

    classify -> diagnose -> repair_decision -> recheck_emit

The old step shells in :mod:`arnold_pipelines.megaplan.pipelines.live_supervisor.steps`
remain available for M4 parity callers; the canonical ``build_pipeline()``
entrypoint now returns an :class:`arnold.workflow.dsl.Pipeline`.
"""

from __future__ import annotations

from arnold.workflow.dsl import Capability, Input, Output, Pipeline, Route, Step


name: str = "live-supervisor"
description: str = (
    "Megaplan Live Watchdog Supervisor: classify, diagnose, and decide "
    "safe repair actions for likely-live Megaplan/Arnold runs."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ()
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("graph", "dispatch+emit")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("supervisor", "repair")


def build_pipeline() -> Pipeline:
    """Build the classify→diagnose→repair_decision→recheck_emit pipeline."""

    classify = Step(
        id="classify",
        kind="agent",
        label="Classify snapshot",
        inputs=(Input(name="snapshot"),),
        outputs=(Output(name="classification"),),
        capabilities=(Capability(id="supervisor", route="classify"),),
        metadata={"stage": "classify"},
    )
    diagnose = Step(
        id="diagnose",
        kind="agent",
        label="Diagnose root cause",
        inputs=(Input(name="classification", value_ref="classify.classification"),),
        outputs=(Output(name="diagnosis"),),
        capabilities=(Capability(id="supervisor", route="diagnose"),),
        metadata={"stage": "diagnose"},
    )
    repair_decision = Step(
        id="repair_decision",
        kind="agent",
        label="Select safe repair",
        inputs=(Input(name="diagnosis", value_ref="diagnose.diagnosis"),),
        outputs=(Output(name="repair_plan"),),
        capabilities=(Capability(id="supervisor", route="repair"),),
        metadata={"stage": "repair_decision"},
    )
    recheck_emit = Step(
        id="recheck_emit",
        kind="emit",
        label="Recheck and emit report",
        inputs=(
            Input(name="repair_plan", value_ref="repair_decision.repair_plan"),
        ),
        outputs=(Output(name="report"),),
        capabilities=(Capability(id="supervisor", route="report"),),
        metadata={"stage": "recheck_emit", "terminal": True},
    )

    return Pipeline(
        id="live-supervisor",
        version="m5-phase3",
        steps=(classify, diagnose, repair_decision, recheck_emit),
        routes=(
            Route(id="classify:diagnose", source="classify", target="diagnose", label="diagnose"),
            Route(id="diagnose:repair_decision", source="diagnose", target="repair_decision", label="repair_decision"),
            Route(id="repair_decision:recheck_emit", source="repair_decision", target="recheck_emit", label="recheck_emit"),
        ),
        capabilities=(Capability(id="supervisor", route="default"),),
        metadata={
            "name": name,
            "description": description,
            "driver": driver,
            "entrypoint": entrypoint,
            "arnold_api_version": arnold_api_version,
            "capabilities": capabilities,
            "default_profile": default_profile,
            "supported_modes": supported_modes,
            "recommended_profiles": recommended_profiles,
        },
    )


__all__ = [
    "build_pipeline",
    "name",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
]
