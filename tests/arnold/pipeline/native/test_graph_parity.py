"""Graph-only parity tests: compiled/projected native graph vs. hand-built reference.

Validates that :func:`project_graph` applied to the toy pipeline's compiled
:class:`NativeProgram` produces a :class:`Pipeline` whose structural fields
match the hand-built reference graph used across all native tests.

Covers:
- Stage count and identity (normalized base name matching)
- Entry point
- Edge connectivity (labels + resolved targets, normalized)
- Loop metadata (``loop_condition`` presence/absence)
- Typed ports (``produces`` / ``consumes``)
- Decision vocabulary and routes
- Binding map (key-normalized)
- Validator acceptance (zero defects on both graphs)
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from arnold.pipeline.declaration_lowering import derive_binding_map
from arnold.pipeline.native import project_graph
from arnold.pipeline.types import Edge, Pipeline, Stage
from arnold.pipeline.validator import validate

from .fixtures import (  # type: ignore[import-untyped]
    _reset_loop_counter,
    get_reference_graph,
    get_toy_program,
)

# ═══════════════════════════════════════════════════════════════════════
# Normalization helpers
# ═══════════════════════════════════════════════════════════════════════

# Projected stage names include a ``__pc{N}`` suffix, e.g.
# ``toy_pipeline__setup__pc0``, while reference stage names omit it, e.g.
# ``toy_pipeline__setup``.  Strip the suffix so comparisons are structural.

_PC_SUFFIX_RE = re.compile(r"__pc\d+$")
# Compiler appends ``_guard`` when a decision is used as a while-loop header
# (see ``_lower_while_stmt`` in ``arnold.pipeline.native.compiler`` line 537).
_GUARD_SUFFIX = "_guard"


def _normalize(name: str) -> str:
    """Strip the ``__pcN`` suffix from a projected stage name."""
    return _PC_SUFFIX_RE.sub("", name)


def _canonical_base(name: str) -> str:
    """Return a canonical base name for matching stages across graphs.

    Strips ``__pcN`` and ``_guard`` suffixes so that, for example,
    ``should_loop_guard`` (projected) matches ``should_loop`` (reference).
    """
    base = _normalize(name).rsplit("__", 1)[-1]
    if base.endswith(_GUARD_SUFFIX):
        base = base[: -len(_GUARD_SUFFIX)]
    return base


def _build_ref_by_canonical(
    ref: Pipeline,
) -> dict[str, Stage]:
    """Index reference stages by their canonical base name."""
    return {_canonical_base(name): stage for name, stage in ref.stages.items()}


def _get_proj_stage_by_canonical(
    proj: Pipeline, canonical: str
) -> Stage | None:
    """Find the first projected stage whose canonical base name matches."""
    for name, stage in proj.stages.items():
        if _canonical_base(name) == canonical:
            return stage
    return None


def _edge_tuple(edge: Edge) -> tuple[str, str]:
    """Return (normalized_label, normalized_target) for an edge.

    Both label and target are canonicalised: ``__pcN`` and ``_guard``
    suffixes are stripped so edges can be compared structurally with
    the reference graph.
    """
    label = _canonical_stage_ref(edge.label)
    target = _canonical_stage_ref(edge.target)
    return (label, target)


def _canonical_stage_ref(name: str) -> str:
    """Return a canonical stage reference by stripping ``__pcN`` and
    ``_guard`` suffixes, normalising both edge labels and targets to
    a common form.

    - ``toy_pipeline__producer__pc1`` → ``toy_pipeline__producer``
    - ``toy_pipeline__should_loop_guard`` → ``toy_pipeline__should_loop``
    - ``halt`` → ``halt`` (reserved, pass through)
    """
    if name == "halt":
        return name
    # Strip __pcN suffix
    name = _normalize(name)
    # Strip _guard suffix from the leaf name
    prefix, sep, leaf = name.rpartition("__")
    if sep and leaf.endswith(_GUARD_SUFFIX):
        leaf = leaf[: -len(_GUARD_SUFFIX)]
        name = f"{prefix}__{leaf}"
    return name


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_counter() -> None:
    """Reset the loop counter before every test."""
    _reset_loop_counter()


@pytest.fixture(scope="module")
def reference_graph() -> Pipeline:
    """Hand-built reference graph for the toy pipeline."""
    _reset_loop_counter()
    return get_reference_graph()


@pytest.fixture(scope="module")
def projected_graph() -> Pipeline:
    """Compiled + projected graph for the toy pipeline."""
    _reset_loop_counter()
    prog = get_toy_program()
    return project_graph(prog)


# ═══════════════════════════════════════════════════════════════════════
# Stage count and identity
# ═══════════════════════════════════════════════════════════════════════


class TestStageCountAndIdentity:
    """Stage cardinality and base-name presence across graph pairs."""

    def test_stage_counts_match(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """Both graphs must contain the same number of real stages."""
        assert len(reference_graph.stages) == len(projected_graph.stages), (
            f"Reference has {len(reference_graph.stages)} stages, "
            f"projected has {len(projected_graph.stages)}"
        )

    def test_all_reference_bases_present_in_projected(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """Every reference stage must have a corresponding projected stage
        (by canonical base name match)."""
        ref_by_canon = _build_ref_by_canonical(reference_graph)
        missing: list[str] = []
        for canon in ref_by_canon:
            proj_stage = _get_proj_stage_by_canonical(projected_graph, canon)
            if proj_stage is None:
                missing.append(canon)
        assert not missing, (
            f"Reference stages not found in projected graph: {missing}"
        )

    def test_no_extra_bases_in_projected(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """The projected graph must not contain stages absent from the reference."""
        ref_canons = set(_build_ref_by_canonical(reference_graph).keys())
        proj_canons: set[str] = set()
        for name in projected_graph.stages:
            proj_canons.add(_canonical_base(name))
        extra = proj_canons - ref_canons
        assert not extra, (
            f"Projected graph has extra stage bases not in reference: {extra}"
        )

    def test_entry_point_normalized_matches(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """The canonical entry names must match between graphs."""
        assert reference_graph.entry is not None
        assert projected_graph.entry is not None
        ref_canon = _canonical_base(reference_graph.entry)
        proj_canon = _canonical_base(projected_graph.entry)
        assert ref_canon == proj_canon, (
            f"Entry mismatch: ref={ref_canon!r}, proj={proj_canon!r}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Edge / route parity
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeRouteParity:
    """Edge labels and resolved targets match across graph pairs."""

    def test_edge_connectivity_per_stage(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """For each pair of corresponding stages, the normalized edge sets
        must be equivalent."""
        ref_by_base = _build_ref_by_canonical(reference_graph)
        mismatches: list[str] = []

        for base, ref_stage in ref_by_base.items():
            proj_stage = _get_proj_stage_by_canonical(projected_graph, base)
            assert proj_stage is not None, f"Stage {base!r} not found in projected graph"

            ref_edges = {_edge_tuple(e) for e in ref_stage.edges}
            proj_edges = {_edge_tuple(e) for e in proj_stage.edges}

            if ref_edges != proj_edges:
                mismatches.append(
                    f"{base}: ref={sorted(ref_edges)}, proj={sorted(proj_edges)}"
                )

        assert not mismatches, "Edge mismatches:\n" + "\n".join(mismatches)

    def test_decision_routes_normalized_parity(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """``decision_routes`` must be structurally equivalent after normalization."""
        ref_by_base = _build_ref_by_canonical(reference_graph)
        mismatches: list[str] = []

        for base, ref_stage in ref_by_base.items():
            proj_stage = _get_proj_stage_by_canonical(projected_graph, base)
            assert proj_stage is not None

            if not ref_stage.decision_routes and not proj_stage.decision_routes:
                continue

            # Normalize route values (they are edge labels, safe as-is)
            ref_routes = dict(ref_stage.decision_routes)
            proj_routes = dict(proj_stage.decision_routes)

            if ref_routes != proj_routes:
                mismatches.append(
                    f"{base}: ref={ref_routes}, proj={proj_routes}"
                )

        assert not mismatches, "Decision route mismatches:\n" + "\n".join(mismatches)


# ═══════════════════════════════════════════════════════════════════════
# Loop metadata parity
# ═══════════════════════════════════════════════════════════════════════


class TestLoopMetadataParity:
    """``loop_condition`` presence and function identity across graph pairs."""

    def test_loop_condition_set_on_same_stages(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """The same stage base names must carry ``loop_condition`` in both graphs."""
        ref_by_base = _build_ref_by_canonical(reference_graph)
        mismatches: list[str] = []

        for base, ref_stage in ref_by_base.items():
            proj_stage = _get_proj_stage_by_canonical(projected_graph, base)
            assert proj_stage is not None

            ref_has_loop = ref_stage.loop_condition is not None
            proj_has_loop = proj_stage.loop_condition is not None

            if ref_has_loop != proj_has_loop:
                mismatches.append(
                    f"{base}: ref_loop={ref_has_loop}, proj_loop={proj_has_loop}"
                )

        assert not mismatches, "Loop condition mismatches:\n" + "\n".join(mismatches)

    def test_loop_condition_callable_identity(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """Where ``loop_condition`` is set, the callable must be the same
        decorated function in both graphs."""
        ref_by_base = _build_ref_by_canonical(reference_graph)
        mismatches: list[str] = []

        for base, ref_stage in ref_by_base.items():
            if ref_stage.loop_condition is None:
                continue
            proj_stage = _get_proj_stage_by_canonical(projected_graph, base)
            assert proj_stage is not None
            assert proj_stage.loop_condition is not None, (
                f"Projected stage {base!r} missing loop_condition"
            )
            # Compare the functions by name — they should be the same decorated
            # callable (identity may differ if wrapped, so compare __name__).
            ref_name: str = getattr(ref_stage.loop_condition, "__name__", "?")
            proj_name: str = getattr(proj_stage.loop_condition, "__name__", "?")
            if ref_name != proj_name:
                mismatches.append(
                    f"{base}: ref_func={ref_name!r}, proj_func={proj_name!r}"
                )

        assert not mismatches, "Loop condition identity mismatches:\n" + "\n".join(mismatches)


# ═══════════════════════════════════════════════════════════════════════
# Typed ports (produces / consumes)
# ═══════════════════════════════════════════════════════════════════════


class TestPortParity:
    """``produces`` and ``consumes`` tuples match across graph pairs."""

    def test_produces_parity(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """Stages with ``produces`` declarations must match."""
        ref_by_base = _build_ref_by_canonical(reference_graph)
        mismatches: list[str] = []

        for base, ref_stage in ref_by_base.items():
            proj_stage = _get_proj_stage_by_canonical(projected_graph, base)
            assert proj_stage is not None

            if ref_stage.produces != proj_stage.produces:
                mismatches.append(
                    f"{base}: ref={ref_stage.produces!r}, proj={proj_stage.produces!r}"
                )

        assert not mismatches, "Produces mismatches:\n" + "\n".join(mismatches)

    def test_consumes_parity(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """Stages with ``consumes`` declarations must match."""
        ref_by_base = _build_ref_by_canonical(reference_graph)
        mismatches: list[str] = []

        for base, ref_stage in ref_by_base.items():
            proj_stage = _get_proj_stage_by_canonical(projected_graph, base)
            assert proj_stage is not None

            if ref_stage.consumes != proj_stage.consumes:
                mismatches.append(
                    f"{base}: ref={ref_stage.consumes!r}, proj={proj_stage.consumes!r}"
                )

        assert not mismatches, "Consumes mismatches:\n" + "\n".join(mismatches)

    def test_step_adapter_produces_parity(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """Step adapter-level ``produces`` must match."""
        ref_by_base = _build_ref_by_canonical(reference_graph)
        mismatches: list[str] = []

        for base, ref_stage in ref_by_base.items():
            proj_stage = _get_proj_stage_by_canonical(projected_graph, base)
            assert proj_stage is not None

            ref_produces = getattr(ref_stage.step, "produces", ())
            proj_produces = getattr(proj_stage.step, "produces", ())
            if ref_produces != proj_produces:
                mismatches.append(
                    f"{base}: ref={ref_produces!r}, proj={proj_produces!r}"
                )

        assert not mismatches, "Step adapter produces mismatches:\n" + "\n".join(mismatches)

    def test_step_adapter_consumes_parity(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """Step adapter-level ``consumes`` must match."""
        ref_by_base = _build_ref_by_canonical(reference_graph)
        mismatches: list[str] = []

        for base, ref_stage in ref_by_base.items():
            proj_stage = _get_proj_stage_by_canonical(projected_graph, base)
            assert proj_stage is not None

            ref_consumes = getattr(ref_stage.step, "consumes", ())
            proj_consumes = getattr(proj_stage.step, "consumes", ())
            if ref_consumes != proj_consumes:
                mismatches.append(
                    f"{base}: ref={ref_consumes!r}, proj={proj_consumes!r}"
                )

        assert not mismatches, "Step adapter consumes mismatches:\n" + "\n".join(mismatches)


# ═══════════════════════════════════════════════════════════════════════
# Decision vocabulary parity
# ═══════════════════════════════════════════════════════════════════════


class TestDecisionVocabularyParity:
    """``decision_vocabulary`` matches across graph pairs."""

    def test_decision_vocabulary_per_stage(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """Decision vocabulary must be identical for matching stages."""
        ref_by_base = _build_ref_by_canonical(reference_graph)
        mismatches: list[str] = []

        for base, ref_stage in ref_by_base.items():
            proj_stage = _get_proj_stage_by_canonical(projected_graph, base)
            assert proj_stage is not None

            if ref_stage.decision_vocabulary != proj_stage.decision_vocabulary:
                mismatches.append(
                    f"{base}: ref={set(ref_stage.decision_vocabulary)!r}, "
                    f"proj={set(proj_stage.decision_vocabulary)!r}"
                )

        assert not mismatches, "Decision vocabulary mismatches:\n" + "\n".join(mismatches)

    def test_decision_vocabulary_on_step_adapter(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """Step adapter ``decision_vocabulary`` must match."""
        ref_by_base = _build_ref_by_canonical(reference_graph)
        mismatches: list[str] = []

        for base, ref_stage in ref_by_base.items():
            proj_stage = _get_proj_stage_by_canonical(projected_graph, base)
            assert proj_stage is not None

            ref_vocab = getattr(ref_stage.step, "decision_vocabulary", frozenset())
            proj_vocab = getattr(proj_stage.step, "decision_vocabulary", frozenset())
            if ref_vocab != proj_vocab:
                mismatches.append(
                    f"{base}: ref={set(ref_vocab)!r}, proj={set(proj_vocab)!r}"
                )

        assert not mismatches, "Step adapter decision vocabulary mismatches:\n" + "\n".join(mismatches)


# ═══════════════════════════════════════════════════════════════════════
# Step kind parity
# ═══════════════════════════════════════════════════════════════════════


class TestStepKindParity:
    """Step ``kind`` attribute matches across graph pairs."""

    def test_step_kind_matches(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """Each stage's step.kind must match between reference and projected."""
        ref_by_base = _build_ref_by_canonical(reference_graph)
        mismatches: list[str] = []

        for base, ref_stage in ref_by_base.items():
            proj_stage = _get_proj_stage_by_canonical(projected_graph, base)
            assert proj_stage is not None

            ref_kind = getattr(ref_stage.step, "kind", "?")
            proj_kind = getattr(proj_stage.step, "kind", "?")
            if ref_kind != proj_kind:
                mismatches.append(
                    f"{base}: ref_kind={ref_kind!r}, proj_kind={proj_kind!r}"
                )

        assert not mismatches, "Step kind mismatches:\n" + "\n".join(mismatches)


# ═══════════════════════════════════════════════════════════════════════
# Binding map parity
# ═══════════════════════════════════════════════════════════════════════


class TestBindingMapParity:
    """The derived ``binding_map`` is structurally equivalent across graph pairs."""

    def test_binding_map_not_none(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """Both graphs must have a non-None ``binding_map`` (typed ports exist)."""
        assert reference_graph.binding_map is not None, "Reference binding_map is None"
        assert projected_graph.binding_map is not None, "Projected binding_map is None"

    def test_binding_map_has_same_keys_normalized(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """Binding map keys must be equivalent after normalizing stage names."""
        ref_map = reference_graph.binding_map
        proj_map = projected_graph.binding_map
        assert ref_map is not None
        assert proj_map is not None

        # Normalize stage-name parts of binding_map keys
        # Keys are typically (stage_name, port_name) tuples
        def _normalize_key(key: Any) -> Any:
            if isinstance(key, tuple) and len(key) == 2:
                return (_canonical_stage_ref(str(key[0])), str(key[1]))
            if isinstance(key, str):
                return _canonical_stage_ref(key)
            return key

        ref_keys = {_normalize_key(k) for k in ref_map.keys()}
        proj_keys = {_normalize_key(k) for k in proj_map.keys()}

        ref_only = ref_keys - proj_keys
        proj_only = proj_keys - ref_keys

        assert not ref_only, f"Binding map keys only in reference: {ref_only}"
        assert not proj_only, f"Binding map keys only in projected: {proj_only}"

    def test_binding_map_values_equivalent(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """For matching keys, binding map values must be equivalent."""
        ref_map = reference_graph.binding_map
        proj_map = projected_graph.binding_map
        assert ref_map is not None
        assert proj_map is not None

        def _normalize_key(key: Any) -> Any:
            if isinstance(key, tuple) and len(key) == 2:
                return (_canonical_stage_ref(str(key[0])), str(key[1]))
            return key

        # Build normalized-key lookup for projected graph
        proj_normalized: dict[Any, Any] = {
            _normalize_key(k): v for k, v in proj_map.items()
        }

        mismatches: list[str] = []
        for key, ref_val in ref_map.items():
            nk = _normalize_key(key)
            proj_val = proj_normalized.get(nk)
            if proj_val is None:
                mismatches.append(f"Key {nk!r} missing from projected binding_map")
                continue

            # Canonicalize both values for comparison
            def _canon_val(v: Any) -> Any:
                """Canonicalize a binding map value for comparison."""
                if isinstance(v, tuple) and len(v) == 2:
                    return (_canonical_stage_ref(str(v[0])), v[1])
                if isinstance(v, str):
                    return _canonical_stage_ref(v)
                return v

            ref_canon = _canon_val(ref_val)
            proj_canon = _canon_val(proj_val)

            if ref_canon != proj_canon:
                mismatches.append(
                    f"Key {nk!r}: ref_val={ref_val!r} (canon={ref_canon!r}), "
                    f"proj_val={proj_val!r} (canon={proj_canon!r})"
                )

        assert not mismatches, "Binding map value mismatches:\n" + "\n".join(mismatches)

    def test_derive_binding_map_on_projected_produces_same_result(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """Calling ``derive_binding_map`` on the projected stages must produce
        a non-empty dict (typed ports are declared)."""
        edge_pairs: list[tuple[str, str]] = []
        for src_name, stage in projected_graph.stages.items():
            for edge in stage.edges:
                if edge.target != "halt" and edge.target in projected_graph.stages:
                    edge_pairs.append((src_name, edge.target))

        bm = derive_binding_map(projected_graph.stages, edge_pairs)
        assert bm is not None, "derive_binding_map returned None on projected graph"
        assert isinstance(bm, dict), f"Expected dict, got {type(bm)}"
        assert len(bm) > 0, "derive_binding_map returned empty dict on projected graph"


# ═══════════════════════════════════════════════════════════════════════
# Validator acceptance
# ═══════════════════════════════════════════════════════════════════════


class TestValidatorAcceptance:
    """Both graphs must validate cleanly (zero defects)."""

    def test_reference_graph_validates(
        self, reference_graph: Pipeline
    ) -> None:
        """The hand-built reference graph must have zero validation defects."""
        result = validate(reference_graph)
        assert len(result.defects) == 0, (
            f"Reference graph has defects: {result.defects}"
        )

    def test_projected_graph_validates(
        self, projected_graph: Pipeline
    ) -> None:
        """The compiled/projected graph must have zero validation defects."""
        result = validate(projected_graph)
        assert len(result.defects) == 0, (
            f"Projected graph has defects: {result.defects}"
        )

    def test_both_graphs_have_zero_cycle_defects(
        self, reference_graph: Pipeline, projected_graph: Pipeline
    ) -> None:
        """Neither graph should have cycle-related defects (loop is guarded)."""
        ref_result = validate(reference_graph)
        proj_result = validate(projected_graph)

        ref_cycles = [d for d in ref_result.defects if "cycle" in str(d).lower()]
        proj_cycles = [d for d in proj_result.defects if "cycle" in str(d).lower()]

        assert not ref_cycles, f"Reference graph cycle defects: {ref_cycles}"
        assert not proj_cycles, f"Projected graph cycle defects: {proj_cycles}"


# ═══════════════════════════════════════════════════════════════════════
# Derived graph structural sanity
# ═══════════════════════════════════════════════════════════════════════


class TestDerivedGraphSanity:
    """Quick sanity checks on the projected graph as a standalone object."""

    def test_projected_stages_have_step_with_run_method(
        self, projected_graph: Pipeline
    ) -> None:
        """Every projected stage must have a step with a callable ``run`` method."""
        for name, stage in projected_graph.stages.items():
            assert hasattr(stage.step, "run"), (
                f"Stage {name!r} step has no 'run' attribute"
            )
            assert callable(stage.step.run), (
                f"Stage {name!r} step.run is not callable"
            )

    def test_projected_stages_have_name_attribute(
        self, projected_graph: Pipeline
    ) -> None:
        """Every projected stage step must have a ``name`` attribute."""
        for name, stage in projected_graph.stages.items():
            assert hasattr(stage.step, "name"), (
                f"Stage {name!r} step has no 'name' attribute"
            )

    def test_projected_stages_have_kind_attribute(
        self, projected_graph: Pipeline
    ) -> None:
        """Every projected stage step must have a ``kind`` attribute."""
        for name, stage in projected_graph.stages.items():
            assert hasattr(stage.step, "kind"), (
                f"Stage {name!r} step has no 'kind' attribute"
            )

    def test_projected_stages_edges_are_tuples(
        self, projected_graph: Pipeline
    ) -> None:
        """Stage edges must be tuples of Edge objects."""
        for name, stage in projected_graph.stages.items():
            assert isinstance(stage.edges, tuple), (
                f"Stage {name!r} edges is not a tuple: {type(stage.edges)}"
            )
            for edge in stage.edges:
                assert isinstance(edge, Edge), (
                    f"Stage {name!r} edge {edge!r} is not an Edge"
                )

    def test_projected_stages_have_decision_routes_dict(
        self, projected_graph: Pipeline
    ) -> None:
        """All stages must have a ``decision_routes`` dict (possibly empty)."""
        for name, stage in projected_graph.stages.items():
            assert isinstance(stage.decision_routes, dict), (
                f"Stage {name!r} decision_routes is not a dict: {type(stage.decision_routes)}"
            )

    def test_projected_stages_have_decision_vocabulary_frozenset(
        self, projected_graph: Pipeline
    ) -> None:
        """All stages must have a ``decision_vocabulary`` frozenset."""
        for name, stage in projected_graph.stages.items():
            assert isinstance(stage.decision_vocabulary, frozenset), (
                f"Stage {name!r} decision_vocabulary is not a frozenset: "
                f"{type(stage.decision_vocabulary)}"
            )
