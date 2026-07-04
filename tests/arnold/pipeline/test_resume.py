from __future__ import annotations

import json
import ast
from pathlib import Path

from arnold.pipeline.resume import (
    COMPOSITE_RESUME_CURSOR_FILENAME,
    RESUME_CURSOR_FILENAME,
    extract_typed_resume_metadata,
    persist_composite_resume_cursor,
    persist_resume_cursor,
    read_awaiting_user_checkpoint,
    read_composite_resume_cursor,
    read_resume_cursor,
    read_state_resume_cursor,
    resolve_resume_surface,
)
from arnold.pipeline.types import StepContext, StepResult


class _FakeStep:
    """A step that does nothing — used only for structural tests."""

    def __init__(self, name: str = "fake", kind: str = "produce") -> None:
        self.name = name
        self.kind = kind

    def run(self, ctx: StepContext) -> StepResult:
        raise NotImplementedError("test-only stub")


def test_persist_and_read_resume_cursor(tmp_path: Path) -> None:
    path = persist_resume_cursor(
        tmp_path,
        stage="human_review",
        resume_cursor="cursor-1",
        reason="awaiting_human",
    )

    assert path == tmp_path / RESUME_CURSOR_FILENAME
    assert read_resume_cursor(tmp_path) == {
        "stage": "human_review",
        "resume_cursor": "cursor-1",
        "reason": "awaiting_human",
    }


def test_read_resume_cursor_absorbs_missing_and_malformed(tmp_path: Path) -> None:
    assert read_resume_cursor(tmp_path) is None
    (tmp_path / RESUME_CURSOR_FILENAME).write_text("[1, 2, 3]", encoding="utf-8")
    assert read_resume_cursor(tmp_path) is None
    (tmp_path / RESUME_CURSOR_FILENAME).write_text("{", encoding="utf-8")
    assert read_resume_cursor(tmp_path) is None


def test_persist_and_read_composite_resume_cursor(tmp_path: Path) -> None:
    path = persist_composite_resume_cursor(
        tmp_path,
        children={"left": {"cursor": "a"}, "right": {"cursor": "b"}},
        shared_awaitable="approval/1",
    )

    assert path == tmp_path / COMPOSITE_RESUME_CURSOR_FILENAME
    assert read_composite_resume_cursor(tmp_path) == {
        "kind": "composite_suspension",
        "version": 1,
        "children": {"left": {"cursor": "a"}, "right": {"cursor": "b"}},
        "shared_awaitable": "approval/1",
    }


def test_read_composite_resume_cursor_absorbs_missing_and_malformed(tmp_path: Path) -> None:
    assert read_composite_resume_cursor(tmp_path) is None
    (tmp_path / COMPOSITE_RESUME_CURSOR_FILENAME).write_text(
        json.dumps(["not", "a", "dict"]),
        encoding="utf-8",
    )
    assert read_composite_resume_cursor(tmp_path) is None


def test_read_state_resume_cursor_reads_state_json_payload(tmp_path: Path) -> None:
    (tmp_path / "state.json").write_text(
        json.dumps({"resume_cursor": {"phase": "review", "retry_strategy": "rerun"}}),
        encoding="utf-8",
    )

    assert read_state_resume_cursor(tmp_path) == {
        "phase": "review",
        "retry_strategy": "rerun",
    }


def test_read_awaiting_user_checkpoint_reads_valid_object(tmp_path: Path) -> None:
    (tmp_path / "awaiting_user.json").write_text(
        json.dumps({"stage": "human_decide", "choices": ["continue", "stop"]}),
        encoding="utf-8",
    )

    assert read_awaiting_user_checkpoint(tmp_path) == {
        "stage": "human_decide",
        "choices": ["continue", "stop"],
    }


def test_extract_typed_resume_metadata_reads_suspended_contract_result(
    tmp_path: Path,
) -> None:
    from arnold.pipeline.types import ContractResult, ContractStatus, HumanSuspension

    contract = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=HumanSuspension(
            kind="human",
            resume_cursor=json.dumps({"phase": "review"}),
            thread_ref="pipeline-123",
            awaitable="approval/123",
            resume_input_schema={
                "properties": {
                    "choice": {"type": "string", "enum": ["continue", "stop"]}
                }
            },
        ),
    )
    (tmp_path / "state.json").write_text(
        json.dumps({"contract_result": contract.to_json()}),
        encoding="utf-8",
    )

    metadata = extract_typed_resume_metadata(tmp_path)
    assert metadata is not None
    assert metadata.phase == "review"
    assert metadata.pipeline == "pipeline-123"
    assert metadata.awaitable == "approval/123"
    assert metadata.choices == ["continue", "stop"]


def test_resolve_resume_surface_respects_shared_precedence(tmp_path: Path) -> None:
    from arnold.pipeline.types import ContractResult, ContractStatus, HumanSuspension

    contract = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=HumanSuspension(
            kind="human",
            resume_cursor=json.dumps({"phase": "typed_review"}),
        ),
    )
    (tmp_path / "state.json").write_text(
        json.dumps(
            {
                "resume_cursor": {"phase": "state_review", "retry_strategy": "rerun"},
                "contract_result": contract.to_json(),
            }
        ),
        encoding="utf-8",
    )
    persist_composite_resume_cursor(tmp_path, children={"child": {"cursor": "c1"}})
    (tmp_path / "awaiting_user.json").write_text(
        json.dumps({"stage": "human_decide"}),
        encoding="utf-8",
    )
    persist_resume_cursor(tmp_path, stage="graph_review", resume_cursor="cursor-1")

    resolved = resolve_resume_surface(tmp_path)

    assert resolved.source == "state_resume_cursor"
    assert resolved.kind == "state_resume_cursor"
    assert resolved.blocked is False
    assert resolved.payload == {"phase": "state_review", "retry_strategy": "rerun"}
    assert [item.source for item in resolved.observations] == [
        "state_resume_cursor",
        "typed_contract",
        "composite_resume_cursor",
        "awaiting_user",
        "resume_cursor",
    ]


def test_resolve_resume_surface_fails_closed_for_corrupt_native_cursor(
    tmp_path: Path,
) -> None:
    (tmp_path / RESUME_CURSOR_FILENAME).write_text(
        json.dumps({"stage": "review", "resume_cursor": None, "native": "bad"}),
        encoding="utf-8",
    )

    resolved = resolve_resume_surface(tmp_path)

    assert resolved.source == "resume_cursor"
    assert resolved.kind == "corrupt_native"
    assert resolved.blocked is True
    assert resolved.diagnostic is not None
    assert "native payload is invalid" in resolved.diagnostic


def test_resume_module_has_no_megaplan_imports() -> None:
    resume_path = Path(__file__).resolve().parents[3] / "arnold/pipeline/resume.py"
    tree = ast.parse(resume_path.read_text(encoding="utf-8"))

    megaplan_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "megaplan" in alias.name:
                    megaplan_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if "megaplan" in module:
                megaplan_imports.append(module)

    assert not megaplan_imports


# ──────────────────────────────────────────────────────────────────────
# T1: Graph human-gate suspension contract — canonical shape freeze
# ──────────────────────────────────────────────────────────────────────


class TestGraphHumanGateSuspensionContract:
    """Freeze the canonical graph human-gate suspension contract shapes.

    These tests document the EXISTING shapes for:

    * ``awaiting_user.json`` — produced by
      :func:`arnold.pipeline.steps.human_gate.write_human_gate_checkpoint`
    * ``HumanSuspension`` from checkpoint — produced by
      :func:`arnold.pipeline.steps.human_gate.make_human_suspension`
    * ``ContractResult(status=SUSPENDED)`` — the typed suspension envelope
    * ``resume_cursor.json`` for a single-choice graph gate — produced by
      :func:`arnold.pipeline.resume.persist_resume_cursor`

    Volatile fields (``artifact_path``, ``message``, ``prompt`` text,
    pipeline/version identity) are normalised to canonical test values;
    the tests are STRICT about key presence, key count, value types, and
    every field in the 11-field ``HumanSuspension`` envelope.
    """

    # ── awaiting_user.json canonical shape ───────────────────────────

    def test_canonical_awaiting_user_top_level_keys(self, tmp_path: Path) -> None:
        """awaiting_user.json contains exactly the expected top-level keys.

        The canonical set is: pipeline, version, artifact_stage, prompt,
        display_refs, stage, choices, message, artifact_path.
        resume_input_schema is absent when no re-verify declaration is
        configured (no-declaration parity).
        """
        from arnold.pipeline.steps.human_gate import write_human_gate_checkpoint

        checkpoint_path = tmp_path / "awaiting_user.json"
        checkpoint = write_human_gate_checkpoint(
            checkpoint_path,
            pipeline="writing-panel-strict",
            version=1,
            artifact_stage="revise",
            stage="human_decide",
            choices=["continue", "stop"],
            artifact_path="/tmp/plan_dir/revise/v1/output.json",
            message="Pipeline 'writing-panel-strict' paused at stage 'human_decide'.",
        )

        # Top-level key set is frozen (resume_input_schema absent by default).
        expected_keys = {
            "pipeline",
            "version",
            "artifact_stage",
            "prompt",
            "display_refs",
            "stage",
            "choices",
            "message",
            "artifact_path",
        }
        actual_keys = set(checkpoint.keys())
        assert actual_keys == expected_keys, (
            f"Unexpected awaiting_user.json keys: {actual_keys ^ expected_keys}"
        )

    def test_canonical_awaiting_user_value_types(self, tmp_path: Path) -> None:
        """awaiting_user.json value types are frozen.

        pipeline, artifact_stage, prompt, stage, message, artifact_path
        are str; version is int; choices and display_refs are list.
        """
        from arnold.pipeline.steps.human_gate import write_human_gate_checkpoint

        checkpoint_path = tmp_path / "awaiting_user.json"
        checkpoint = write_human_gate_checkpoint(
            checkpoint_path,
            pipeline="writing-panel-strict",
            version=1,
            artifact_stage="revise",
            stage="human_decide",
            choices=["continue", "stop"],
            artifact_path="/tmp/plan_dir/revise/v1/output.json",
            message="Paused.",
        )

        assert isinstance(checkpoint["pipeline"], str)
        assert isinstance(checkpoint["version"], int)
        assert isinstance(checkpoint["artifact_stage"], str)
        assert isinstance(checkpoint["prompt"], str)
        assert isinstance(checkpoint["display_refs"], list)
        assert isinstance(checkpoint["stage"], str)
        assert isinstance(checkpoint["choices"], list)
        assert isinstance(checkpoint["message"], str)
        assert isinstance(checkpoint["artifact_path"], str)

    def test_canonical_awaiting_user_read_round_trip(self, tmp_path: Path) -> None:
        """awaiting_user.json round-trips through write → read helpers."""
        from arnold.pipeline.steps.human_gate import (
            read_human_gate_checkpoint,
            write_human_gate_checkpoint,
        )

        checkpoint_path = tmp_path / "awaiting_user.json"
        written = write_human_gate_checkpoint(
            checkpoint_path,
            pipeline="writing-panel-strict",
            version=1,
            artifact_stage="revise",
            stage="human_decide",
            choices=["continue", "stop"],
            artifact_path="/tmp/plan_dir/revise/v1/output.json",
            message="Paused.",
        )

        read_back = read_human_gate_checkpoint(checkpoint_path)
        assert read_back == written

    def test_awaiting_user_with_resume_reverify_schema(self, tmp_path: Path) -> None:
        """When resume_input_schema is supplied, it appears as a top-level key.

        The schema key is only present when a re-verification declaration
        is configured (non-empty dict).
        """
        from arnold.pipeline.steps.human_gate import write_human_gate_checkpoint

        checkpoint_path = tmp_path / "awaiting_user.json"
        checkpoint = write_human_gate_checkpoint(
            checkpoint_path,
            pipeline="writing-panel-strict",
            version=1,
            artifact_stage="revise",
            resume_input_schema={"x-arnold-resume": {"port": "scan_output"}},
            stage="human_decide",
            choices=["continue", "stop"],
            artifact_path="/tmp/plan_dir/revise/v1/output.json",
            message="Paused.",
        )

        assert "resume_input_schema" in checkpoint
        assert checkpoint["resume_input_schema"] == {
            "x-arnold-resume": {"port": "scan_output"}
        }

    # ── HumanSuspension canonical shape ───────────────────────────────

    def test_canonical_human_suspension_from_checkpoint(self) -> None:
        """make_human_suspension produces a HumanSuspension with all 11 fields.

        The 11-field envelope (kind, awaitable, prompt, display_refs,
        resume_input_schema, resume_cursor, thread_ref, actor, deadline,
        on_timeout, default_action) is frozen by the type definition.
        kind is always "human" for graph human-gate suspensions.
        """
        from arnold.pipeline.steps.human_gate import make_human_suspension
        from arnold.pipeline.types import HumanSuspension

        checkpoint: dict = {
            "pipeline": "writing-panel-strict",
            "version": 1,
            "artifact_stage": "revise",
            "prompt": "Review the revised draft.",
            "display_refs": [],
            "stage": "human_decide",
            "choices": ["continue", "stop"],
            "message": "Paused at human_decide.",
            "artifact_path": "/tmp/plan_dir/revise/v1/output.json",
        }
        suspension = make_human_suspension(checkpoint, resume_cursor="cursor-1")

        assert isinstance(suspension, HumanSuspension)
        assert suspension.kind == "human"
        assert suspension.awaitable is None  # not populated by make_human_suspension
        assert suspension.prompt == "Review the revised draft."
        assert suspension.display_refs == ()
        assert suspension.resume_input_schema == {}
        assert suspension.resume_cursor == "cursor-1"
        assert suspension.thread_ref is None
        assert suspension.actor is None
        assert suspension.deadline is None
        assert suspension.on_timeout is None
        assert suspension.default_action is None

    def test_human_suspension_field_count_is_11(self) -> None:
        """HumanSuspension has exactly 11 fields (the frozen envelope)."""
        from dataclasses import fields as _fields
        from arnold.pipeline.types import HumanSuspension

        field_names = tuple(f.name for f in _fields(HumanSuspension))
        assert len(field_names) == 11, (
            f"Expected 11 fields, got {len(field_names)}: {field_names}"
        )

    def test_human_suspension_resume_input_schema_round_trip(self) -> None:
        """resume_input_schema survives HumanSuspension.to_json() → from_json().

        The schema is stored as a plain dict inside the frozen dataclass.
        """
        from arnold.pipeline.types import HumanSuspension

        schema = {"choice": {"type": "string", "enum": ["continue", "stop"]}}
        sus = HumanSuspension(
            kind="human",
            prompt="Continue?",
            resume_input_schema=schema,
            resume_cursor="cursor-1",
        )
        rt = HumanSuspension.from_json(sus.to_json())
        assert rt.resume_input_schema == schema

    def test_human_suspension_to_json_keys(self) -> None:
        """HumanSuspension.to_json() emits exactly the 11 frozen keys."""
        from arnold.pipeline.types import HumanSuspension

        sus = HumanSuspension(kind="human")
        json_dict = sus.to_json()
        expected_keys = {
            "kind",
            "awaitable",
            "prompt",
            "display_refs",
            "resume_input_schema",
            "resume_cursor",
            "thread_ref",
            "actor",
            "deadline",
            "on_timeout",
            "default_action",
        }
        assert set(json_dict.keys()) == expected_keys, (
            f"Unexpected to_json() keys: {set(json_dict.keys()) ^ expected_keys}"
        )

    # ── ContractResult(status=SUSPENDED) canonical shape ──────────────

    def test_canonical_contract_result_suspended_keys(self) -> None:
        """ContractResult(status=SUSPENDED) has the 8 frozen fields.

        The suspension field carries the HumanSuspension envelope.
        """
        from arnold.pipeline.types import (
            ContractResult,
            ContractStatus,
            HumanSuspension,
        )

        suspension = HumanSuspension(
            kind="human",
            prompt="Review the draft.",
            resume_cursor="cursor-1",
        )
        cr = ContractResult(
            status=ContractStatus.SUSPENDED,
            suspension=suspension,
        )

        json_dict = cr.to_json()
        expected_keys = {
            "schema_version",
            "status",
            "payload",
            "suspension",
            "evidence_refs",
            "authority_level",
            "provenance",
            "freshness",
        }
        assert set(json_dict.keys()) == expected_keys, (
            f"Unexpected ContractResult keys: {set(json_dict.keys()) ^ expected_keys}"
        )
        assert json_dict["status"] == "suspended"
        assert json_dict["suspension"] is not None
        assert json_dict["suspension"]["kind"] == "human"

    def test_contract_result_suspended_round_trip(self) -> None:
        """ContractResult(status=SUSPENDED) survives to_json → from_json."""
        from arnold.pipeline.types import (
            ContractResult,
            ContractStatus,
            HumanSuspension,
        )

        suspension = HumanSuspension(
            kind="human",
            prompt="Review the draft.",
            resume_cursor="cursor-1",
            resume_input_schema={"choice": {"type": "string"}},
        )
        original = ContractResult(
            status=ContractStatus.SUSPENDED,
            suspension=suspension,
            payload={"phase": "human_decide"},
        )
        restored = ContractResult.from_json(original.to_json())

        assert restored.status == ContractStatus.SUSPENDED
        assert restored.suspension is not None
        assert restored.suspension.kind == "human"
        assert restored.suspension.prompt == "Review the draft."
        assert restored.suspension.resume_cursor == "cursor-1"
        assert restored.suspension.resume_input_schema == {"choice": {"type": "string"}}
        assert restored.payload == {"phase": "human_decide"}

    def test_contract_result_suspended_requires_suspension(self) -> None:
        """A ContractResult with status=SUSPENDED conventionally carries a suspension.

        The type system does not ENFORCE this pairing (it is the caller's
        responsibility), but the canonical graph human-gate contract always
        pairs them.
        """
        from arnold.pipeline.types import (
            ContractResult,
            ContractStatus,
            HumanSuspension,
        )

        # Canonical: SUSPENDED always has a suspension.
        cr = ContractResult(
            status=ContractStatus.SUSPENDED,
            suspension=HumanSuspension(kind="human"),
        )
        assert cr.status == ContractStatus.SUSPENDED
        assert cr.suspension is not None
        assert cr.suspension.kind == "human"

    # ── resume_cursor.json canonical shape ────────────────────────────

    def test_canonical_resume_cursor_top_level_keys(self, tmp_path: Path) -> None:
        """resume_cursor.json for a graph gate has stage + resume_cursor.

        Additional keys passed via **extra are merged into the payload.
        """
        from arnold.pipeline.resume import RESUME_CURSOR_FILENAME

        persist_resume_cursor(
            tmp_path,
            stage="human_decide",
            resume_cursor="cursor-1",
            reason="awaiting_human",
        )

        cursor_path = tmp_path / RESUME_CURSOR_FILENAME
        assert cursor_path.exists()

        data = json.loads(cursor_path.read_text(encoding="utf-8"))
        assert "stage" in data
        assert "resume_cursor" in data
        assert data["stage"] == "human_decide"
        assert data["resume_cursor"] == "cursor-1"

    def test_resume_cursor_extra_keys_merge_additively(self, tmp_path: Path) -> None:
        """Extra kwargs in persist_resume_cursor merge into the payload.

        This is the additive compatibility strategy: graph readers only
        access the keys they know about; native readers access additional
        keys like 'native', 'stages', 'loops', 'frames'.
        """
        from arnold.pipeline.resume import RESUME_CURSOR_FILENAME

        persist_resume_cursor(
            tmp_path,
            stage="human_decide",
            resume_cursor="cursor-1",
            reason="awaiting_human",
            choices=["continue", "stop"],
        )

        data = json.loads(
            (tmp_path / RESUME_CURSOR_FILENAME).read_text(encoding="utf-8")
        )
        assert data["stage"] == "human_decide"
        assert data["resume_cursor"] == "cursor-1"
        assert data["reason"] == "awaiting_human"
        assert data["choices"] == ["continue", "stop"]

    def test_resume_cursor_for_writing_panel_strict_shape(self, tmp_path: Path) -> None:
        """resume_cursor.json shape that writing-panel-strict would produce.

        A single-choice graph gate with options ['continue', 'stop'] and
        edges {continue: panel_review, stop: halt} pauses at human_decide.
        The resume cursor records the stage and an opaque cursor string.
        """
        from arnold.pipeline.resume import RESUME_CURSOR_FILENAME

        # Simulate what the graph executor would persist for a
        # writing-panel-strict human gate at stage "human_decide".
        persist_resume_cursor(
            tmp_path,
            stage="human_decide",
            resume_cursor="cursor-wp-1",
            reason="awaiting_human",
            pipeline="writing-panel-strict",
            choices=["continue", "stop"],
            artifact_stage="revise",
        )

        data = json.loads(
            (tmp_path / RESUME_CURSOR_FILENAME).read_text(encoding="utf-8")
        )

        # Top-level contract fields
        assert data["stage"] == "human_decide"
        assert data["resume_cursor"] == "cursor-wp-1"

        # Volatile fields normalised for the canonical test shape
        assert data["reason"] == "awaiting_human"
        assert data["pipeline"] == "writing-panel-strict"
        assert data["choices"] == ["continue", "stop"]
        assert data["artifact_stage"] == "revise"

        # Verify that no native key leaked in (this is a graph-born cursor)
        assert "native" not in data, (
            "Graph-born cursor must not carry a 'native' key"
        )

    def test_resume_cursor_absent_native_key_is_graph_born(self, tmp_path: Path) -> None:
        """A resume_cursor.json without a 'native' key is graph-born.

        This is the contract that classify_resume_cursor relies on.
        """
        from arnold.pipeline.resume import RESUME_CURSOR_FILENAME

        persist_resume_cursor(
            tmp_path,
            stage="human_decide",
            resume_cursor="cursor-1",
            reason="awaiting_human",
        )

        data = json.loads(
            (tmp_path / RESUME_CURSOR_FILENAME).read_text(encoding="utf-8")
        )
        assert "native" not in data, (
            "persist_resume_cursor must not emit a 'native' key — "
            "native cursors are produced by persist_native_cursor only"
        )

    def test_read_resume_cursor_returns_full_payload(self, tmp_path: Path) -> None:
        """read_resume_cursor returns the complete dict including extra keys."""
        persist_resume_cursor(
            tmp_path,
            stage="human_decide",
            resume_cursor="cursor-1",
            reason="awaiting_human",
            choices=["continue", "stop"],
        )

        data = read_resume_cursor(tmp_path)
        assert data is not None
        assert data["stage"] == "human_decide"
        assert data["resume_cursor"] == "cursor-1"
        assert data["reason"] == "awaiting_human"
        assert data["choices"] == ["continue", "stop"]


# ──────────────────────────────────────────────────────────────────────
# T17: Native-backed resume re-entry path — with_entry preserves fields
# ──────────────────────────────────────────────────────────────────────


class TestNativeBackedResumeReEntry:
    """``with_entry()`` must preserve ``native_program`` and other dataclass
    fields during resume re-entry.

    The T6 fix closed a drop-site where ``with_entry()`` could lose
    ``native_program`` during resume by constructing a fresh Pipeline
    instead of using ``dataclasses.replace``.  These tests lock that
    behaviour: a native-backed pipeline that suspends and resumes must
    keep its ``native_program`` intact after re-entry.
    """

    def test_with_entry_preserves_native_program(self) -> None:
        """``with_entry`` on a pipeline with native_program keeps it."""
        from arnold.pipeline.native.ir import NativeProgram
        from arnold.pipeline.types import Pipeline, Stage
        from arnold_pipelines.megaplan.runtime.resume import with_entry

        program = NativeProgram(name="test-program")
        s1 = Stage(name="phase_a", step=_FakeStep("phase_a"), edges=())
        s2 = Stage(name="phase_b", step=_FakeStep("phase_b"), edges=())
        pipeline = Pipeline(
            stages={"phase_a": s1, "phase_b": s2},
            entry="phase_a",
            native_program=program,
        )

        re_entered = with_entry(pipeline, "phase_b")
        assert re_entered.entry == "phase_b"
        assert re_entered.native_program is program, (
            "native_program must survive with_entry() re-entry"
        )

    def test_with_entry_preserves_native_program_when_none(self) -> None:
        """``with_entry`` on a pipeline without native_program keeps None."""
        from arnold.pipeline.types import Pipeline, Stage
        from arnold_pipelines.megaplan.runtime.resume import with_entry

        s1 = Stage(name="phase_a", step=_FakeStep("phase_a"), edges=())
        s2 = Stage(name="phase_b", step=_FakeStep("phase_b"), edges=())
        pipeline = Pipeline(
            stages={"phase_a": s1, "phase_b": s2},
            entry="phase_a",
            native_program=None,
        )

        re_entered = with_entry(pipeline, "phase_b")
        assert re_entered.entry == "phase_b"
        assert re_entered.native_program is None, (
            "absent native_program must stay None after re-entry"
        )

    def test_with_entry_preserves_resource_bundles(self) -> None:
        """``with_entry`` preserves resource_bundles during re-entry."""
        from arnold.pipeline.types import Pipeline, Stage
        from arnold_pipelines.megaplan.runtime.resume import with_entry

        class _FakeBundle:
            pass

        bundle = _FakeBundle()
        s1 = Stage(name="phase_a", step=_FakeStep("phase_a"), edges=())
        s2 = Stage(name="phase_b", step=_FakeStep("phase_b"), edges=())
        pipeline = Pipeline(
            stages={"phase_a": s1, "phase_b": s2},
            entry="phase_a",
            resource_bundles=(bundle,),
        )

        re_entered = with_entry(pipeline, "phase_b")
        assert re_entered.entry == "phase_b"
        assert re_entered.resource_bundles == (bundle,), (
            "resource_bundles must survive with_entry() re-entry"
        )

    def test_with_entry_preserves_binding_map(self) -> None:
        """``with_entry`` preserves binding_map during re-entry."""
        from arnold.pipeline.types import Pipeline, Stage
        from arnold_pipelines.megaplan.runtime.resume import with_entry

        bm = {"phase_a": {"out": "phase_b.in"}}
        s1 = Stage(name="phase_a", step=_FakeStep("phase_a"), edges=())
        s2 = Stage(name="phase_b", step=_FakeStep("phase_b"), edges=())
        pipeline = Pipeline(
            stages={"phase_a": s1, "phase_b": s2},
            entry="phase_a",
            binding_map=bm,
        )

        re_entered = with_entry(pipeline, "phase_b")
        assert re_entered.entry == "phase_b"
        assert re_entered.binding_map == bm, (
            "binding_map must survive with_entry() re-entry"
        )

    def test_with_entry_rejects_unknown_stage(self) -> None:
        """``with_entry`` raises KeyError for a stage not in the pipeline."""
        from arnold.pipeline.types import Pipeline, Stage
        from arnold_pipelines.megaplan.runtime.resume import with_entry

        s1 = Stage(name="phase_a", step=_FakeStep("phase_a"), edges=())
        pipeline = Pipeline(stages={"phase_a": s1}, entry="phase_a")

        import pytest as _pytest
        with _pytest.raises(KeyError, match="phase_b"):
            with_entry(pipeline, "phase_b")
