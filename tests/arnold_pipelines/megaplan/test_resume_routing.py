"""Resume-routing contract tests for generic native routing.

Resurrected from the archived ``tests/archive/m6_deleted_legacy_runtime/
arnold/pipeline/native/test_resume_routing.py`` during M3.5 (T2).

Key changes from the archived version:
- Uses live imports: ``arnold.pipeline.native.checkpoint`` and
  ``arnold.pipeline.native.routing`` instead of the deleted
  ``arnold_pipelines.megaplan._pipeline._bridge``.
- No Megaplan stage-order assumptions — all stage references are
  generic and not coupled to the canonical ``prep→plan→critique→...``
  topology.
- Dispatch assertions use the public ``select_runtime_for_dispatch``
  and ``has_native_dispatch_capability`` surface rather than the
  deleted private bridge.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from arnold.pipeline.resume import persist_composite_resume_cursor
from arnold.pipeline.types import ContractResult, ContractStatus, HumanSuspension
from arnold.pipeline.native.checkpoint import (
    NATIVE_CURSOR_VERSION,
    NativeCursorCorruptError,
    classify_resume_cursor,
    persist_native_cursor,
    read_native_cursor,
)
from arnold.pipeline.native.ir import NativeProgram
from arnold.pipeline.resume import (
    RESUME_CURSOR_FILENAME,
    persist_resume_cursor,
)
from arnold_pipelines.megaplan._core.workflow import _resolve_resume_cursor, resume_plan
from arnold_pipelines.megaplan.types import CliError


# ═══════════════════════════════════════════════════════════════════════════
# Unit tests: classify_resume_cursor
# ═══════════════════════════════════════════════════════════════════════════


class TestClassifyResumeCursor:
    """Unit tests for classify_resume_cursor — generic native cursor routing."""

    # ── "none" cases ────────────────────────────────────────────────────

    def test_no_cursor_file_returns_none(self, tmp_path: Path) -> None:
        """No resume_cursor.json → 'none'."""
        assert classify_resume_cursor(tmp_path) == "none"

    def test_unreadable_json_raises_corrupt_error(self, tmp_path: Path) -> None:
        """Malformed JSON fails closed."""
        (tmp_path / RESUME_CURSOR_FILENAME).write_text("{", encoding="utf-8")
        with pytest.raises(NativeCursorCorruptError, match="could not be decoded"):
            classify_resume_cursor(tmp_path)

    def test_non_dict_json_raises_corrupt_error(self, tmp_path: Path) -> None:
        """JSON that isn't a dict fails closed."""
        (tmp_path / RESUME_CURSOR_FILENAME).write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(NativeCursorCorruptError, match="expected JSON object"):
            classify_resume_cursor(tmp_path)

    # ── "graph" cases ───────────────────────────────────────────────────

    def test_cursor_without_native_key_returns_graph(self, tmp_path: Path) -> None:
        """Cursor with no 'native' key → graph-born."""
        persist_resume_cursor(
            tmp_path,
            stage="some_stage",
            resume_cursor="cursor-1",
            reason="awaiting_human",
        )
        assert classify_resume_cursor(tmp_path) == "graph"

    def test_cursor_with_null_native_returns_graph(self, tmp_path: Path) -> None:
        """Cursor with 'native': null → graph."""
        payload = {
            "stage": "some_stage",
            "resume_cursor": None,
            "native": None,
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        assert classify_resume_cursor(tmp_path) == "graph"

    def test_graph_cursor_with_extra_fields_returns_graph(self, tmp_path: Path) -> None:
        """Graph cursor with extra fields but no native key → graph."""
        payload = {
            "stage": "review",
            "resume_cursor": "c-123",
            "stages": ["phase_a", "phase_b"],
            "loops": {},
            "frames": {},
            "extra_field": "some_value",
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        assert classify_resume_cursor(tmp_path) == "graph"

    # ── "native" cases ──────────────────────────────────────────────────

    def test_valid_native_cursor_returns_native(self, tmp_path: Path) -> None:
        """Valid native cursor → native-born."""
        persist_native_cursor(
            tmp_path,
            stage="pipeline__phase_a__pc0",
            pc=0,
        )
        assert classify_resume_cursor(tmp_path) == "native"

    def test_valid_native_cursor_with_all_fields_returns_native(
        self, tmp_path: Path
    ) -> None:
        """Full native cursor → native-born."""
        persist_native_cursor(
            tmp_path,
            stage="pipeline__phase_b__pc1",
            pc=1,
            stages=["pipeline__phase_a__pc0"],
            loops={"my_loop": 2},
            frames={"my_loop": {"iteration_data": {}}},
            resume_cursor="opaque-cursor",
            cursor_id="abc123def456",
            stage_reentry_points={"phase_a": "pipeline__phase_a__pc0"},
        )
        assert classify_resume_cursor(tmp_path) == "native"

    def test_native_cursor_minimal_valid_returns_native(self, tmp_path: Path) -> None:
        """Minimal valid native cursor (just pc + version) → native."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"pc": 0, "version": 1},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        assert classify_resume_cursor(tmp_path) == "native"

    # ── NativeCursorCorruptError cases ──────────────────────────────────

    def test_native_not_dict_raises_corrupt_error(self, tmp_path: Path) -> None:
        """native key is a string → NativeCursorCorruptError."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": "not-a-dict",
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError) as exc_info:
            classify_resume_cursor(tmp_path)
        assert "not a JSON object" in str(exc_info.value)
        assert exc_info.value.cursor_path is not None

    def test_native_is_list_raises_corrupt_error(self, tmp_path: Path) -> None:
        """native key is a list → NativeCursorCorruptError."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": [1, 2, 3],
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError) as exc_info:
            classify_resume_cursor(tmp_path)
        assert "not a JSON object" in str(exc_info.value)

    def test_native_missing_pc_raises_corrupt_error(self, tmp_path: Path) -> None:
        """native dict missing 'pc' → NativeCursorCorruptError."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"version": 1},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError) as exc_info:
            classify_resume_cursor(tmp_path)
        assert "missing the required 'pc'" in str(exc_info.value)

    def test_native_missing_version_raises_corrupt_error(self, tmp_path: Path) -> None:
        """native dict missing 'version' → NativeCursorCorruptError."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"pc": 0},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError) as exc_info:
            classify_resume_cursor(tmp_path)
        assert "missing the required 'version'" in str(exc_info.value)

    def test_native_pc_not_int_raises_corrupt_error(self, tmp_path: Path) -> None:
        """native.pc is a string → NativeCursorCorruptError."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"pc": "zero", "version": 1},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError) as exc_info:
            classify_resume_cursor(tmp_path)
        error_msg = str(exc_info.value).lower()
        assert "unreadable" in error_msg or "expected int" in error_msg

    def test_native_version_not_int_raises_corrupt_error(self, tmp_path: Path) -> None:
        """native.version is a string → NativeCursorCorruptError."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"pc": 0, "version": "one"},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError) as exc_info:
            classify_resume_cursor(tmp_path)
        error_msg = str(exc_info.value).lower()
        assert "unreadable" in error_msg or "expected int" in error_msg

    def test_native_pc_is_float_raises_corrupt_error(self, tmp_path: Path) -> None:
        """native.pc is a float → NativeCursorCorruptError."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {"pc": 1.5, "version": 1},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError):
            classify_resume_cursor(tmp_path)

    def test_corrupt_error_includes_cursor_path(self, tmp_path: Path) -> None:
        """NativeCursorCorruptError carries the cursor path."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": "bad",
        }
        cursor_path = tmp_path / RESUME_CURSOR_FILENAME
        cursor_path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(NativeCursorCorruptError) as exc_info:
            classify_resume_cursor(tmp_path)
        assert exc_info.value.cursor_path == str(cursor_path)


# ═══════════════════════════════════════════════════════════════════════════
# Edge case tests
# ═══════════════════════════════════════════════════════════════════════════


class TestResumeRoutingEdgeCases:
    """Edge cases for resume routing — no Megaplan stage-order assumptions."""

    def test_empty_dict_native_raises_corrupt_error(self, tmp_path: Path) -> None:
        """native key is empty dict → missing pc/version → corrupt."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {},
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with pytest.raises(NativeCursorCorruptError) as exc_info:
            classify_resume_cursor(tmp_path)
        assert "missing the required 'pc'" in str(exc_info.value)

    def test_native_with_extra_keys_is_valid(self, tmp_path: Path) -> None:
        """native dict with extra keys beyond pc/version is still valid."""
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": {
                "pc": 5,
                "version": 2,
                "extra_field": "ignored",
                "nested": {"a": 1},
            },
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )
        assert classify_resume_cursor(tmp_path) == "native"

    def test_classify_then_read_consistency(self, tmp_path: Path) -> None:
        """classify_resume_cursor('native') ⇒ read_native_cursor succeeds."""
        persist_native_cursor(
            tmp_path,
            stage="pipeline__phase_c__pc3",
            pc=3,
            stages=[
                "pipeline__phase_a__pc0",
                "pipeline__phase_b__pc1",
                "pipeline__phase_c__pc2",
            ],
        )
        assert classify_resume_cursor(tmp_path) == "native"
        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["native"]["pc"] == 3
        assert cursor["native"]["version"] == NATIVE_CURSOR_VERSION

    def test_classify_graph_then_read_returns_none(self, tmp_path: Path) -> None:
        """classify_resume_cursor('graph') ⇒ read_native_cursor returns None."""
        persist_resume_cursor(
            tmp_path,
            stage="human_review",
            resume_cursor="c-1",
            reason="awaiting_human",
        )
        assert classify_resume_cursor(tmp_path) == "graph"
        assert read_native_cursor(tmp_path) is None

    def test_native_cursor_version_constant_used(self, tmp_path: Path) -> None:
        """NATIVE_CURSOR_VERSION constant is respected."""
        assert NATIVE_CURSOR_VERSION == 1
        persist_native_cursor(
            tmp_path, stage="s", pc=0, version=NATIVE_CURSOR_VERSION
        )
        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["native"]["version"] == NATIVE_CURSOR_VERSION

    def test_nested_directory_artifact_root(self, tmp_path: Path) -> None:
        """classify_resume_cursor works with nested artifact_root paths."""
        nested = tmp_path / "deep" / "path"
        nested.mkdir(parents=True)
        assert classify_resume_cursor(nested) == "none"

        persist_native_cursor(nested, stage="s", pc=0)
        assert classify_resume_cursor(nested) == "native"

    def test_string_artifact_root_accepted(self, tmp_path: Path) -> None:
        """classify_resume_cursor accepts string paths."""
        persist_native_cursor(tmp_path, stage="s", pc=0)
        assert classify_resume_cursor(str(tmp_path)) == "native"


# ═══════════════════════════════════════════════════════════════════════════
# Generic native dispatch routing tests (no Megaplan stage-order assumptions)
# ═══════════════════════════════════════════════════════════════════════════


class TestGenericNativeDispatchRouting:
    """Generic native dispatch routing — no hard-coded Megaplan topology."""

    def test_has_native_dispatch_capability_with_program(self) -> None:
        """Pipeline with native_program is native-capable."""
        from arnold.pipeline.native.routing import has_native_dispatch_capability

        program = NativeProgram(name="test-pipeline")
        pipeline = SimpleNamespace(
            native_program=program,
            resource_bundles=(),
        )
        assert has_native_dispatch_capability(pipeline) is True

    def test_has_native_dispatch_capability_without_program(self) -> None:
        """Pipeline without native_program is not native-capable."""
        from arnold.pipeline.native.routing import has_native_dispatch_capability

        pipeline = SimpleNamespace(
            native_program=None,
            resource_bundles=(),
        )
        assert has_native_dispatch_capability(pipeline) is False

    def test_has_native_dispatch_capability_with_bundle(self) -> None:
        """Pipeline with NativeProgram in resource_bundles is native-capable."""
        from arnold.pipeline.native.routing import has_native_dispatch_capability

        program = NativeProgram(name="test-pipeline")
        pipeline = SimpleNamespace(
            native_program=None,
            resource_bundles=(program,),
        )
        assert has_native_dispatch_capability(pipeline) is True

    def test_has_native_dispatch_capability_with_runner_adapter(self) -> None:
        """Pipeline with run_native_pipeline adapter is native-capable."""
        from arnold.pipeline.native.routing import has_native_dispatch_capability

        class RunnerAdapter:
            def run_native_pipeline(self, *args, **kwargs):
                pass

        pipeline = SimpleNamespace(
            native_program=None,
            resource_bundles=(RunnerAdapter(),),
        )
        assert has_native_dispatch_capability(pipeline) is True

    def test_select_fresh_runtime_prefers_native_when_capable(self) -> None:
        """Fresh dispatch routes to native when pipeline has native_program."""
        from arnold.pipeline.native.routing import (
            RUNTIME_NATIVE,
            select_fresh_runtime_owner,
        )

        program = NativeProgram(name="test-pipeline")
        pipeline = SimpleNamespace(
            native_program=program,
            resource_bundles=(),
        )
        result = select_fresh_runtime_owner(pipeline)
        assert result == RUNTIME_NATIVE, (
            f"Fresh dispatch should prefer native when capable, got {result}"
        )

    def test_select_fresh_runtime_falls_back_to_graph(self) -> None:
        """Fresh dispatch routes to graph when pipeline lacks native_program."""
        from arnold.pipeline.native.routing import (
            RUNTIME_GRAPH,
            select_fresh_runtime_owner,
        )

        pipeline = SimpleNamespace(
            native_program=None,
            resource_bundles=(),
        )
        result = select_fresh_runtime_owner(pipeline)
        assert result == RUNTIME_GRAPH, (
            f"Fresh dispatch should fall back to graph when no native_program, "
            f"got {result}"
        )

    def test_select_fresh_runtime_respects_explicit_state_override(
        self, tmp_path: Path
    ) -> None:
        """Explicit runtime marker in state overrides capability detection."""
        from arnold.pipeline.native.routing import (
            RUNTIME_GRAPH,
            select_fresh_runtime_owner,
        )

        program = NativeProgram(name="test-pipeline")
        pipeline = SimpleNamespace(
            native_program=program,
            resource_bundles=(),
        )
        # Even though pipeline is native-capable, explicit graph marker wins
        result = select_fresh_runtime_owner(
            pipeline,
            state={"runtime_envelope": {"runtime": "graph"}},
        )
        assert result == RUNTIME_GRAPH, (
            "Explicit runtime marker must override capability detection"
        )

    def test_select_fresh_runtime_respects_persisted_state(
        self, tmp_path: Path
    ) -> None:
        """Persisted state.json runtime markers participate in routing."""
        from arnold.pipeline.native.routing import (
            RUNTIME_GRAPH,
            select_fresh_runtime_owner,
        )

        (tmp_path / "state.json").write_text(
            json.dumps({"runtime_envelope": {"runtime": "graph"}}),
            encoding="utf-8",
        )

        program = NativeProgram(name="test-pipeline")
        pipeline = SimpleNamespace(
            native_program=program,
            resource_bundles=(),
        )
        result = select_fresh_runtime_owner(
            pipeline,
            artifact_root=tmp_path,
        )
        assert result == RUNTIME_GRAPH, (
            "Persisted state.json marker must override capability detection"
        )

    def test_select_runtime_for_dispatch_native_cursor_resumes_native(
        self, tmp_path: Path
    ) -> None:
        """Native-born cursor must resume through native runtime."""
        from arnold.pipeline.native.routing import (
            RUNTIME_NATIVE,
            select_runtime_for_dispatch,
        )

        persist_native_cursor(
            tmp_path,
            stage="pipeline__phase_a__pc0",
            pc=0,
        )

        program = NativeProgram(name="test-pipeline")
        pipeline = SimpleNamespace(
            native_program=program,
            resource_bundles=(),
        )
        decision = select_runtime_for_dispatch(
            pipeline,
            state={},
            artifact_root=tmp_path,
        )
        assert decision.runtime == RUNTIME_NATIVE
        assert decision.resume is True
        assert decision.reason == "native_cursor"

    def test_select_runtime_for_dispatch_graph_cursor_resumes_graph(
        self, tmp_path: Path
    ) -> None:
        """Graph-born cursor must resume through graph runtime."""
        from arnold.pipeline.native.routing import (
            RUNTIME_GRAPH,
            select_runtime_for_dispatch,
        )

        persist_resume_cursor(
            tmp_path,
            stage="some_stage",
            resume_cursor="cursor-1",
            reason="awaiting_human",
        )

        program = NativeProgram(name="test-pipeline")
        pipeline = SimpleNamespace(
            native_program=program,
            resource_bundles=(),
        )
        decision = select_runtime_for_dispatch(
            pipeline,
            state={},
            artifact_root=tmp_path,
        )
        assert decision.runtime == RUNTIME_GRAPH
        assert decision.resume is True
        assert decision.reason == "graph_cursor"

    def test_select_runtime_for_dispatch_no_cursor_native_capable(
        self, tmp_path: Path
    ) -> None:
        """No cursor + native-capable → fresh native dispatch."""
        from arnold.pipeline.native.routing import (
            RUNTIME_NATIVE,
            select_runtime_for_dispatch,
        )

        program = NativeProgram(name="test-pipeline")
        pipeline = SimpleNamespace(
            native_program=program,
            resource_bundles=(),
        )
        decision = select_runtime_for_dispatch(
            pipeline,
            state={},
            artifact_root=tmp_path,
        )
        assert decision.runtime == RUNTIME_NATIVE
        assert decision.resume is False
        assert decision.reason == "native_fresh"

    def test_select_runtime_for_dispatch_no_cursor_no_native(
        self, tmp_path: Path
    ) -> None:
        """No cursor + not native-capable → graph dispatch."""
        from arnold.pipeline.native.routing import (
            RUNTIME_GRAPH,
            select_runtime_for_dispatch,
        )

        pipeline = SimpleNamespace(
            native_program=None,
            resource_bundles=(),
        )
        decision = select_runtime_for_dispatch(
            pipeline,
            state={},
            artifact_root=tmp_path,
        )
        assert decision.runtime == RUNTIME_GRAPH
        assert decision.resume is False
        assert decision.reason == "graph_fresh"

    def test_corrupt_native_cursor_in_select_runtime_fails_closed(
        self, tmp_path: Path
    ) -> None:
        """select_runtime_for_dispatch must fail closed on corrupt native cursors."""
        from arnold.pipeline.native.routing import select_runtime_for_dispatch

        # Write a corrupt native cursor
        payload = {
            "stage": "s",
            "resume_cursor": None,
            "native": "corrupt",
        }
        (tmp_path / RESUME_CURSOR_FILENAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )

        program = NativeProgram(name="test-pipeline")
        pipeline = SimpleNamespace(
            native_program=program,
            resource_bundles=(),
        )

        with pytest.raises(NativeCursorCorruptError) as exc_info:
            select_runtime_for_dispatch(
                pipeline,
                state={},
                artifact_root=tmp_path,
            )
        assert "not a JSON object" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════════
# Substrate-proof: no Megaplan stage-order assumptions in routing
# ═══════════════════════════════════════════════════════════════════════════


class TestNoMegaplanStageOrderInRouting:
    """Generic native routing must not assume Megaplan stage order."""

    def test_classify_resume_cursor_is_generic(self) -> None:
        """classify_resume_cursor does not reference Megaplan stage names."""
        import inspect

        source = inspect.getsource(classify_resume_cursor)
        megaplan_stages = {
            "prep", "plan", "critique", "gate", "revise",
            "tiebreaker", "finalize", "execute", "review",
            "override", "halt",
        }
        source_lower = source.lower()
        found = [s for s in megaplan_stages if s in source_lower]
        assert not found, (
            f"classify_resume_cursor must not reference Megaplan stages: {found}"
        )

    def test_native_routing_select_functions_are_generic(self) -> None:
        """The select_* functions in native/routing.py are stage-order agnostic.

        Only flag stage names that appear as *string literals* (quoted values)
        within the function bodies, not as generic English words in docstrings
        or comments.
        """
        import ast
        import inspect
        import textwrap

        from arnold.pipeline.native import routing as native_routing

        functions_to_check = [
            native_routing.select_fresh_runtime_owner,
            native_routing.select_runtime_for_dispatch,
            native_routing.has_native_dispatch_capability,
        ]

        megaplan_stages = {
            "prep", "plan", "critique", "gate", "revise",
            "tiebreaker", "finalize", "execute", "review",
        }

        for func in functions_to_check:
            source = textwrap.dedent(inspect.getsource(func))
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            # Find string literals that match Megaplan stage names
            found: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    lowered = node.value.lower()
                    if lowered in megaplan_stages:
                        found.append(node.value)

            assert not found, (
                f"{func.__name__} must not reference Megaplan stage names "
                f"as string literals: {found}"
            )


class TestMegaplanResumeSurfaceRouting:
    def _previous_state(self) -> dict[str, object]:
        return {
            "current_state": "blocked",
            "history": [],
            "config": {},
            "sessions": {},
            "plan_versions": [],
            "meta": {},
            "last_gate": {},
        }

    def test_resolve_resume_cursor_prefers_state_over_typed_contract(
        self, tmp_path: Path
    ) -> None:
        previous_state = self._previous_state()
        previous_state["resume_cursor"] = {"phase": "review", "retry_strategy": "state-first"}
        (tmp_path / "state.json").write_text(
            json.dumps(
                {
                    "resume_cursor": {"phase": "review", "retry_strategy": "state-first"},
                    "contract_result": ContractResult(
                        status=ContractStatus.SUSPENDED,
                        suspension=HumanSuspension(
                            kind="human",
                            resume_cursor=json.dumps({"phase": "execute"}),
                        ),
                    ).to_json(),
                }
            ),
            encoding="utf-8",
        )

        cursor, source, extra = _resolve_resume_cursor(
            plan_dir=tmp_path,
            previous_state=previous_state,
        )

        assert cursor == {"phase": "review", "retry_strategy": "state-first"}
        assert source == "state"
        assert extra is None

    def test_resolve_resume_cursor_prefers_typed_contract_over_awaiting_user(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "state.json").write_text(
            json.dumps(
                {
                    "contract_result": ContractResult(
                        status=ContractStatus.SUSPENDED,
                        suspension=HumanSuspension(
                            kind="human",
                            resume_cursor=json.dumps({"retry_strategy": "typed"}),
                            resume_input_schema={
                                "type": "object",
                                "properties": {
                                    "choice": {
                                        "type": "string",
                                        "enum": ["continue", "stop"],
                                    }
                                },
                            },
                        ),
                    ).to_json(),
                    "_pipeline_paused_stage": "review",
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / "awaiting_user.json").write_text(
            json.dumps({"stage": "gate", "choices": ["legacy"]}),
            encoding="utf-8",
        )

        cursor, source, extra = _resolve_resume_cursor(
            plan_dir=tmp_path,
            previous_state=self._previous_state(),
        )

        assert cursor == {
            "retry_strategy": "typed",
            "choices": ["continue", "stop"],
        }
        assert source == "typed_contract"
        assert extra is None

    def test_resolve_resume_cursor_prefers_composite_cursor_over_awaiting_user(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "state.json").write_text(json.dumps({}), encoding="utf-8")
        persist_composite_resume_cursor(
            tmp_path,
            children={"child": {"cursor": "token"}},
            phase="execute",
        )
        (tmp_path / "awaiting_user.json").write_text(
            json.dumps({"stage": "gate", "choices": ["legacy"]}),
            encoding="utf-8",
        )

        cursor, source, extra = _resolve_resume_cursor(
            plan_dir=tmp_path,
            previous_state=self._previous_state(),
        )

        assert cursor["kind"] == "composite_suspension"
        assert cursor["phase"] == "execute"
        assert source == "composite"
        assert extra is None

    def test_resolve_resume_cursor_fails_closed_on_corrupt_native_surface(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "state.json").write_text(json.dumps({}), encoding="utf-8")
        (tmp_path / "resume_cursor.json").write_text(
            json.dumps({"stage": "native", "resume_cursor": None, "native": "bad"}),
            encoding="utf-8",
        )

        with pytest.raises(CliError) as exc_info:
            _resolve_resume_cursor(
                plan_dir=tmp_path,
                previous_state=self._previous_state(),
            )

        assert getattr(exc_info.value, "code", None) == "invalid_resume_cursor"
        assert exc_info.value.extra["resume_surface"] == "resume_cursor"

    def test_resume_plan_rejects_later_phase_without_execute_authority(
        self, tmp_path: Path
    ) -> None:
        plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    **self._previous_state(),
                    "name": "demo",
                    "config": {"project_dir": str(tmp_path)},
                    "meta": {"current_invocation_id": "inv-test"},
                    "resume_cursor": {
                        "phase": "review",
                        "retry_strategy": "manual_review",
                    },
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "finalize.json").write_text(
            json.dumps({"tasks": [{"id": "T1", "status": "done"}]}),
            encoding="utf-8",
        )

        with pytest.raises(CliError) as exc_info:
            resume_plan(tmp_path, "demo")

        assert getattr(exc_info.value, "code", None) == "resume_execute_authority_blocked"
        assert exc_info.value.extra["guard"] == "before_later_phase_dispatch"
        assert exc_info.value.extra["reason"] == "execute_authority_diverged"
        assert exc_info.value.extra["missing_task_ids"] == ["T1"]

    def test_native_routing_module_has_no_megaplan_imports(self) -> None:
        """The native routing module must not import from megaplan paths."""
        import ast
        from pathlib import Path

        routing_path = (
            Path(__file__).resolve().parents[3]
            / "arnold/pipeline/native/routing.py"
        )
        tree = ast.parse(routing_path.read_text(encoding="utf-8"))

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

        assert not megaplan_imports, (
            f"arnold/pipeline/native/routing.py must not import megaplan: "
            f"{megaplan_imports}"
        )

    def test_native_routing_has_no_route_label_special_cases(self) -> None:
        """No Megaplan-specific route labels (e.g. 'megaplan::prep') in routing.py."""
        import ast
        from pathlib import Path

        routing_path = (
            Path(__file__).resolve().parents[3]
            / "arnold/pipeline/native/routing.py"
        )
        source = routing_path.read_text(encoding="utf-8")

        # Route-label patterns that would suggest Megaplan-specific logic
        route_label_patterns = [
            "megaplan::",
            "megaplan_route",
            "route_label",
            "canonical_route",
            "stage_label",
        ]
        source_lower = source.lower()
        found = [p for p in route_label_patterns if p in source_lower]
        assert not found, (
            f"routing.py must not contain route-label special cases: {found}"
        )

    def test_native_routing_has_no_topology_hash_special_cases(self) -> None:
        """No topology-hash special cases in routing.py."""
        import ast
        from pathlib import Path

        routing_path = (
            Path(__file__).resolve().parents[3]
            / "arnold/pipeline/native/routing.py"
        )
        source = routing_path.read_text(encoding="utf-8").lower()

        topology_hash_patterns = [
            "topology_hash",
            "topology-hash",
            "stage_hash",
            "pipeline_hash",
            "canonical_hash",
        ]
        found = [p for p in topology_hash_patterns if p in source]
        assert not found, (
            f"routing.py must not contain topology-hash special cases: {found}"
        )

    def test_native_routing_all_public_functions_are_generic(self) -> None:
        """Every public function in routing.py is stage-order agnostic."""
        import ast
        import inspect
        import textwrap

        from arnold.pipeline.native import routing as native_routing

        all_public = [
            native_routing.normalize_runtime_owner,
            native_routing.runtime_owner_from_state,
            native_routing.persisted_runtime_owner,
            native_routing.explicit_runtime_owner,
            native_routing.has_native_dispatch_capability,
            native_routing.select_fresh_runtime_owner,
            native_routing.select_runtime_for_dispatch,
        ]

        megaplan_stages = {
            "prep", "plan", "critique", "gate", "revise",
            "tiebreaker", "finalize", "execute", "review",
        }

        for func in all_public:
            source = textwrap.dedent(inspect.getsource(func))
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            found: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    lowered = node.value.lower()
                    if lowered in megaplan_stages:
                        found.append(node.value)

            assert not found, (
                f"{func.__name__} must not reference Megaplan stage names "
                f"as string literals: {found}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Substrate-proof: executor.py has no Megaplan-specific special cases
# ═══════════════════════════════════════════════════════════════════════════


class TestNoMegaplanSpecialCasesInExecutor:
    """Executor must have no Megaplan route-label, topology-hash, or stage-order special cases."""

    def test_executor_module_has_no_megaplan_imports(self) -> None:
        """arnold/pipeline/executor.py must not import from megaplan paths."""
        import ast
        from pathlib import Path

        executor_path = (
            Path(__file__).resolve().parents[3]
            / "arnold/pipeline/executor.py"
        )
        tree = ast.parse(executor_path.read_text(encoding="utf-8"))

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

        assert not megaplan_imports, (
            f"arnold/pipeline/executor.py must not import megaplan: "
            f"{megaplan_imports}"
        )

    def test_executor_has_no_megaplan_stage_name_references(self) -> None:
        """Executor must not reference Megaplan stage names as string literals."""
        import ast
        from pathlib import Path

        executor_path = (
            Path(__file__).resolve().parents[3]
            / "arnold/pipeline/executor.py"
        )
        tree = ast.parse(executor_path.read_text(encoding="utf-8"))

        megaplan_stages = {
            "prep", "plan", "critique", "gate", "revise",
            "tiebreaker", "finalize", "execute", "review",
        }

        found: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                lowered = node.value.lower()
                if lowered in megaplan_stages:
                    found.append((node.lineno, node.value))

        # Allow: 'plan' in compound words like 'plan-dir' is a false positive;
        # only flag standalone stage-name matches.
        actual: list[tuple[int, str]] = []
        for lineno, val in found:
            val_lower = val.lower().strip()
            # 'plan' is too common as a substring; only flag when it's the
            # exact word or part of a Megaplan-stage compound like 'prep_phase'
            if val_lower in megaplan_stages or any(
                val_lower.startswith(s + "_") or val_lower.endswith("_" + s)
                or val_lower == s
                for s in megaplan_stages
            ):
                actual.append((lineno, val))

        assert not actual, (
            f"executor.py must not reference Megaplan stage names as "
            f"string literals: {actual}"
        )

    def test_executor_has_no_route_label_special_cases(self) -> None:
        """Executor must not contain Megaplan-specific route-label logic."""
        from pathlib import Path

        executor_path = (
            Path(__file__).resolve().parents[3]
            / "arnold/pipeline/executor.py"
        )
        source = executor_path.read_text(encoding="utf-8").lower()

        route_label_patterns = [
            "megaplan::",
            "megaplan_route",
            "route_label",
            "canonical_route",
            "stage_label",
        ]
        found = [p for p in route_label_patterns if p in source]
        assert not found, (
            f"executor.py must not contain route-label special cases: {found}"
        )

    def test_executor_has_no_topology_hash_special_cases(self) -> None:
        """Executor must not contain topology-hash or stage-hash logic."""
        from pathlib import Path

        executor_path = (
            Path(__file__).resolve().parents[3]
            / "arnold/pipeline/executor.py"
        )
        source = executor_path.read_text(encoding="utf-8").lower()

        topology_hash_patterns = [
            "topology_hash",
            "topology-hash",
            "stage_hash",
            "pipeline_hash",
            "canonical_hash",
        ]
        found = [p for p in topology_hash_patterns if p in source]
        assert not found, (
            f"executor.py must not contain topology-hash special cases: {found}"
        )

    def test_executor_has_no_legacy_stage_order_special_cases(self) -> None:
        """Executor must not contain legacy stage-order assumptions."""
        from pathlib import Path

        executor_path = (
            Path(__file__).resolve().parents[3]
            / "arnold/pipeline/executor.py"
        )
        source = executor_path.read_text(encoding="utf-8").lower()

        stage_order_patterns = [
            "stage_order",
            "stage-order",
            "canonical_order",
            "megaplan_order",
            "ordered_stages",
            "prep_phase",
            "plan_phase",
            "critique_phase",
            "prep→plan",
            "prep->plan",
        ]
        found = [p for p in stage_order_patterns if p in source]
        assert not found, (
            f"executor.py must not contain legacy stage-order special cases: {found}"
        )

    def test_executor_discipline_boundary_is_intact(self) -> None:
        """Executor's boundary discipline comment is present and accurate.

        The file header explicitly states: 'No product-specific pipeline
        imports. No forbidden vocabulary literals.' This test verifies
        that declaration is still present.
        """
        from pathlib import Path

        executor_path = (
            Path(__file__).resolve().parents[3]
            / "arnold/pipeline/executor.py"
        )
        source = executor_path.read_text(encoding="utf-8")

        assert "No product-specific pipeline imports" in source, (
            "executor.py must retain its boundary discipline declaration"
        )
        assert "No forbidden vocabulary literals" in source, (
            "executor.py must retain its forbidden-vocabulary declaration"
        )

    def test_executor_native_dispatch_is_generic(self) -> None:
        """Native dispatch functions in executor.py are stage-order agnostic."""
        import ast
        import inspect
        import textwrap

        from arnold.pipeline import executor as ex

        dispatch_funcs = [
            ex._should_dispatch_native,
            ex._run_native_dispatched,
            ex._resolve_executor_marker,
            ex._resolve_resume_marker,
            ex._modern_runtime_owner_from_state,
            ex._legacy_runtime_owner_from_state,
            ex._find_native_bundle,
            ex._find_native_program,
        ]

        megaplan_stages = {
            "prep", "plan", "critique", "gate", "revise",
            "tiebreaker", "finalize", "execute", "review",
        }

        for func in dispatch_funcs:
            source = textwrap.dedent(inspect.getsource(func))
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            found: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    lowered = node.value.lower()
                    if lowered in megaplan_stages:
                        found.append(node.value)

            assert not found, (
                f"{func.__name__} must not reference Megaplan stage names "
                f"as string literals: {found}"
            )
