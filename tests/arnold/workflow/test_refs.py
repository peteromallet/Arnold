from __future__ import annotations

import pytest

from arnold.workflow import (
    EdgeRef,
    ExpressionRef,
    HookRef,
    ImportRef,
    NodeRef,
    RefDiagnosticError,
    SourceRef,
    SourceSpan,
    ValueRef,
    as_hook_ref,
    as_import_ref,
    as_optional_hook_ref,
    expression_ref,
    manifest_coordinate,
)

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


def module_level_hook() -> str:
    return "ok"


class HookFixtures:
    def method_hook(self) -> str:
        return "method"

    @staticmethod
    def static_hook() -> str:
        return "static"

    @classmethod
    def class_hook(cls) -> str:
        return "class"


class CallableHook:
    def __call__(self) -> str:
        return "callable"


def test_node_and_edge_refs_have_stable_canonical_keys() -> None:
    start = NodeRef("plan")
    review = NodeRef("review")
    edge = EdgeRef(source=start, target=review, label="approved")

    assert str(start) == "node:plan"
    assert start.key == "node:plan"
    assert str(edge) == "edge:plan->review:approved"
    assert edge == EdgeRef(NodeRef("plan"), NodeRef("review"), "approved")


def test_source_refs_preserve_authored_span_identity() -> None:
    span = SourceSpan(
        path="pipelines/example.py",
        start_line=12,
        start_column=5,
        end_line=14,
        end_column=9,
    )
    ref = SourceRef("build_pipeline", span=span)

    assert span.key == "source:pipelines/example.py:12:5-14:9"
    assert ref.key == "source-ref:build_pipeline@source:pipelines/example.py:12:5-14:9"


def test_value_refs_are_node_scoped_and_schema_hash_normalized() -> None:
    ref = ValueRef(NodeRef("reduce"), "verdict", schema_hash="SHA256:" + "C" * 64)

    assert ref.schema_hash == "sha256:" + "c" * 64
    assert ref.key == f"value:reduce.verdict@{ref.schema_hash}"
    assert ValueRef(NodeRef("reduce"), "verdict") != ref


def test_runtime_coordinate_derives_from_human_alias_and_manifest_hash() -> None:
    first = manifest_coordinate("planning", HASH_A)
    same = manifest_coordinate("planning", HASH_A.upper())
    different_alias = manifest_coordinate("review", HASH_A)
    different_hash = manifest_coordinate("planning", HASH_B)

    assert first == same
    assert first.key == f"workflow:planning@{HASH_A}"
    assert first != different_alias
    assert first != different_hash


def test_manifest_cursor_composes_coordinate_with_refs() -> None:
    coordinate = manifest_coordinate("planning", HASH_A)
    node = NodeRef("human_gate")
    cursor = coordinate.cursor(
        node=node,
        edge=EdgeRef(node, NodeRef("finalize"), "approved"),
        value=ValueRef(node, "answer"),
        reentry_id="resume-1",
    )

    assert cursor.key == (
        f"workflow:planning@{HASH_A}"
        "#node:human_gate"
        "#edge:human_gate->finalize:approved"
        "#value:human_gate.answer"
        "#reentry:resume-1"
    )


def test_import_and_hook_refs_accept_stable_module_and_class_functions() -> None:
    module_ref = ImportRef.from_callable(module_level_hook, node_id="decide", field="condition_ref")
    static_ref = HookRef.from_callable(HookFixtures.static_hook, node_id="reduce", field="reducer_ref")
    method_ref = HookRef.from_callable(HookFixtures.method_hook, node_id="inspect", field="prompt_ref")

    assert module_ref.spec == f"{__name__}:module_level_hook"
    assert module_ref.key == f"import:{__name__}:module_level_hook"
    assert module_ref.resolve() is module_level_hook
    assert static_ref.spec == f"{__name__}:HookFixtures.static_hook"
    assert static_ref.key == f"hook:{__name__}:HookFixtures.static_hook"
    assert static_ref.resolve() is HookFixtures.static_hook
    assert method_ref.resolve() is HookFixtures.method_hook
    assert HookRef.parse(module_ref.spec).resolve() is module_level_hook


def test_import_ref_rejects_unstable_callable_identities_with_diagnostics() -> None:
    captured = "state"

    def closure() -> str:
        return captured

    def local_function() -> str:
        return "local"

    cases = [
        (lambda: "lambda", "lambdas"),
        (closure, "closures"),
        (local_function, "ambiguous local functions"),
        (HookFixtures().method_hook, "bound methods"),
        (HookFixtures.class_hook, "bound methods"),
        (CallableHook(), "callable instances"),
        (object(), "live objects"),
    ]

    for target, reason in cases:
        with pytest.raises(RefDiagnosticError) as exc_info:
            HookRef.from_callable(target, node_id="review", field="condition_ref")

        message = str(exc_info.value)
        assert "node 'review' field 'condition_ref'" in message
        assert reason in message
        assert "module-level function or class/static function" in message


def test_hook_ref_parse_rejects_string_refs_to_unstable_callables() -> None:
    with pytest.raises(RefDiagnosticError, match="bound methods"):
        HookRef.parse(f"{__name__}:HookFixtures.class_hook")


def test_expression_refs_are_inert_and_dependency_only() -> None:
    hook = HookRef.from_callable(module_level_hook)
    ref = expression_ref("ready", dependencies=["plan.draft", "review:score"], hook=hook)

    assert ref == ExpressionRef("ready", dependencies=("plan.draft", "review:score"), hook=hook)
    assert ref.key == f"expr:ready@hook:{__name__}:module_level_hook"
    assert ref.dependencies == ("plan.draft", "review:score")
    with pytest.raises(TypeError, match="inert reference"):
        bool(ref)
    with pytest.raises(TypeError, match="inert reference"):
        bool(hook)


def test_as_hook_ref_accepts_strings_import_refs_and_callables() -> None:
    string_ref = as_hook_ref(
        f"{__name__}:module_level_hook",
        node_id="plan",
        field="prompt_ref",
    )
    import_ref = as_import_ref(module_level_hook)
    callable_ref = as_hook_ref(module_level_hook, node_id="plan", field="prompt_ref")

    assert string_ref.spec == f"{__name__}:module_level_hook"
    assert callable_ref.spec == string_ref.spec
    assert HookRef(import_ref).spec == string_ref.spec


def test_as_hook_ref_rejects_unstable_callables_with_node_field_context() -> None:
    captured = "state"

    def closure() -> str:
        return captured

    cases = [
        (lambda: "lambda", "lambdas"),
        (closure, "closures"),
        (HookFixtures().method_hook, "bound methods"),
        (CallableHook(), "callable instances"),
        (object(), "live objects"),
        ("not_a_module:func", "invalid hook ref"),
    ]

    for target, reason in cases:
        with pytest.raises(RefDiagnosticError) as exc_info:
            as_hook_ref(target, node_id="review", field="condition_ref")

        message = str(exc_info.value)
        assert "node 'review' field 'condition_ref'" in message
        assert reason in message
        assert "module-level function or class/static function" in message


def test_as_optional_hook_ref_preserves_none_and_valid_refs() -> None:
    assert as_optional_hook_ref(None, node_id="plan", field="reducer_ref") is None
    ref = as_optional_hook_ref(
        f"{__name__}:module_level_hook",
        node_id="plan",
        field="reducer_ref",
    )
    assert isinstance(ref, HookRef)


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: NodeRef("bad/id"), "ref alphabet"),
        (lambda: EdgeRef(NodeRef("a"), NodeRef("b"), ""), "edge label"),
        (lambda: SourceSpan("", 1), "source path"),
        (lambda: SourceSpan("x.py", 0), "start_line"),
        (lambda: ValueRef(NodeRef("a"), "payload", schema_hash="sha256:not-a-hash"), "manifest_hash"),
        (lambda: manifest_coordinate("1-invalid", HASH_A), "workflow alias"),
        (lambda: ImportRef.parse("missing-colon"), "module:qualname"),
        (lambda: expression_ref("bad/id"), "ref alphabet"),
    ],
)
def test_refs_fail_closed_on_ambiguous_identity(factory, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        factory()
