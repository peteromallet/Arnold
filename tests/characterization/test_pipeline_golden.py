"""Golden characterization for the canonical Megaplan pipeline surface.

The legacy golden used deleted ``arnold_pipelines.megaplan._pipeline`` modules.
This characterization is intentionally pinned to the native-backed public
``build_pipeline()`` surface while keeping graph compatibility visible.
"""

from __future__ import annotations

from pathlib import Path

from arnold.pipeline.native.ir import NativeProgram
from arnold.pipeline.native.routing import (
    has_native_dispatch_capability,
    select_runtime_for_dispatch,
)
from arnold.pipeline.resume import (
    classify_resume_cursor_payload,
    persist_resume_cursor,
)
from arnold.pipelines.megaplan.pipeline import build_pipeline


EXPECTED_STAGE_ORDER = (
    "prep",
    "plan",
    "critique",
    "gate",
    "revise",
    "tiebreaker",
    "finalize",
    "execute",
    "review",
)

EXPECTED_NATIVE_PHASE_TRACE = (
    "prep",
    "plan",
    "critique",
    "gate",
    "revise",
    "critique",
    "gate",
    "tiebreaker",
    "critique",
    "gate",
    "revise",
    "critique",
    "gate",
    "tiebreaker",
    "finalize",
    "execute",
    "review",
)

EXPECTED_NATIVE_INSTRUCTIONS = (
    ("phase", "prep", 1),
    ("phase", "plan", 2),
    ("phase", "critique", 3),
    ("phase", "gate", 4),
    ("decision", "gate_guard", None),
    ("phase", "revise", 6),
    ("phase", "critique", 7),
    ("phase", "gate", 8),
    ("jump", "gate_loop_back", 4),
    ("decision", "gate", None),
    ("halt", "", None),
    ("decision", "gate", None),
    ("phase", "tiebreaker", 13),
    ("decision", "tiebreaker", None),
    ("phase", "critique", 15),
    ("phase", "gate", 16),
    ("decision", "gate_guard", None),
    ("phase", "revise", 18),
    ("phase", "critique", 19),
    ("phase", "gate", 20),
    ("jump", "gate_loop_back", 16),
    ("decision", "gate", None),
    ("halt", "", None),
    ("decision", "gate", None),
    ("phase", "tiebreaker", 25),
    ("jump", "if_then_exit", 26),
    ("jump", "if_then_exit", 27),
    ("jump", "if_then_exit", 28),
    ("phase", "finalize", 29),
    ("phase", "execute", 30),
    ("phase", "review", 31),
    ("halt", "", None),
)


def _instruction_golden(program: NativeProgram) -> tuple[tuple[str, str, int | None], ...]:
    return tuple((inst.op, inst.name, inst.next_pc) for inst in program.instructions)


def _phase_port_golden(program: NativeProgram) -> dict[str, dict[str, tuple[str, ...]]]:
    return {
        phase.name: {
            "produces": tuple(port.name for port in phase.produces),
            "consumes": tuple(port.port_name for port in phase.consumes),
        }
        for phase in program.phases
    }


def test_build_pipeline_golden_shape_is_native_backed_compatibility_shell() -> None:
    pipeline = build_pipeline()

    assert pipeline.entry == "prep"
    assert tuple(pipeline.stages) == EXPECTED_STAGE_ORDER
    assert pipeline.resource_bundles == ()
    assert isinstance(pipeline.native_program, NativeProgram)
    assert pipeline.native_program.name == "megaplan"
    assert has_native_dispatch_capability(pipeline) is True


def test_native_program_golden_preserves_trace_and_port_shape() -> None:
    pipeline = build_pipeline()
    assert isinstance(pipeline.native_program, NativeProgram)

    program = pipeline.native_program
    assert tuple(phase.name for phase in program.phases) == EXPECTED_NATIVE_PHASE_TRACE
    assert tuple(decision.name for decision in program.decisions) == (
        "gate",
        "gate",
        "tiebreaker",
        "gate",
        "gate",
    )
    assert _instruction_golden(program) == EXPECTED_NATIVE_INSTRUCTIONS
    assert _phase_port_golden(program) == {
        "prep": {"produces": ("prep_payload",), "consumes": ()},
        "plan": {"produces": ("plan_payload",), "consumes": ("prep_payload",)},
        "critique": {
            "produces": ("critique_payload",),
            "consumes": ("plan_payload", "revise_payload", "tiebreaker_payload"),
        },
        "gate": {"produces": ("gate_payload",), "consumes": ("critique_payload",)},
        "revise": {"produces": ("revise_payload",), "consumes": ("gate_payload",)},
        "tiebreaker": {
            "produces": ("tiebreaker_payload",),
            "consumes": ("gate_payload",),
        },
        "finalize": {"produces": ("finalize_payload",), "consumes": ("gate_payload",)},
        "execute": {"produces": ("execute_payload",), "consumes": ("finalize_payload",)},
        "review": {"produces": ("review_payload",), "consumes": ("execute_payload",)},
    }


def test_serialized_runtime_ownership_golden_preserves_state_continuity(
    tmp_path: Path,
) -> None:
    pipeline = build_pipeline()

    fresh = select_runtime_for_dispatch(
        pipeline,
        state={},
        artifact_root=tmp_path,
    )
    assert (fresh.runtime, fresh.resume, fresh.reason) == (
        "native",
        False,
        "native_fresh",
    )

    persist_resume_cursor(
        tmp_path,
        stage="execute",
        resume_cursor="graph-era-cursor",
    )

    graph_resume = select_runtime_for_dispatch(
        pipeline,
        state={},
        artifact_root=tmp_path,
    )
    assert (graph_resume.runtime, graph_resume.resume, graph_resume.reason) == (
        "graph",
        True,
        "graph_cursor",
    )
    assert classify_resume_cursor_payload(
        {"stage": "execute", "resume_cursor": "graph-era-cursor"}
    ) == "graph"

    native_born_payload = {
        "stage": "execute",
        "resume_cursor": "native-cursor",
        "native": {"pc": 17, "version": 1},
    }
    assert classify_resume_cursor_payload(native_born_payload) == "native"
