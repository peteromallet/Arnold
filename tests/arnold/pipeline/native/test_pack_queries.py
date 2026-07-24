"""Focused tests for PackReverseIndex reverse dependency queries.

Covers:
- Direct dependents lookup by stable ID
- Containment traversal (transitive dependents via BFS)
- Path-prefix lookup on call-site paths
- Parent/ancestor traversal up dependency chains
- Cross-program reverse dependency queries
- Registration semantics (additive call-site paths, lockfile merge)
- Empty and boundary cases
- Serialization round-trip
"""

from __future__ import annotations

import json

import pytest

from arnold.pipeline.native.pack_index import DependentRecord, PackReverseIndex
from arnold.pipeline.native.pack_metadata import LockfileEntry


# ── Helpers ────────────────────────────────────────────────────────────

def _lock(version: str = "1.0.0", interface_hash: str = "sha256:abcd") -> LockfileEntry:
    """Shortcut to create a LockfileEntry for test scenarios."""
    return LockfileEntry(
        stable_id="shared_step",
        version=version,
        interface_hash=interface_hash,
    )


def _rec(
    program_stable_id: str | None = None,
    program_name: str = "test_program",
    call_site_paths: tuple[str, ...] = (),
    lockfile_entry: LockfileEntry | None = None,
) -> DependentRecord:
    """Shortcut to create a DependentRecord."""
    return DependentRecord(
        program_stable_id=program_stable_id,
        program_name=program_name,
        call_site_paths=call_site_paths,
        lockfile_entry=lockfile_entry,
    )


# ── DependentRecord ────────────────────────────────────────────────────


class TestDependentRecord:
    """Serialization and construction for DependentRecord."""

    def test_minimal_construction(self) -> None:
        rec = DependentRecord(program_stable_id=None, program_name="prog")
        assert rec.program_stable_id is None
        assert rec.program_name == "prog"
        assert rec.call_site_paths == ()
        assert rec.lockfile_entry is None

    def test_full_construction(self) -> None:
        lock = _lock()
        rec = DependentRecord(
            program_stable_id="prog_1",
            program_name="My Program",
            call_site_paths=("root/a", "root/b"),
            lockfile_entry=lock,
        )
        assert rec.program_stable_id == "prog_1"
        assert rec.program_name == "My Program"
        assert rec.call_site_paths == ("root/a", "root/b")
        assert rec.lockfile_entry is lock

    def test_to_dict_minimal(self) -> None:
        rec = DependentRecord(program_stable_id=None, program_name="prog")
        d = rec.to_dict()
        assert d == {"program_name": "prog"}

    def test_to_dict_full(self) -> None:
        lock = _lock()
        rec = DependentRecord(
            program_stable_id="prog_1",
            program_name="My Program",
            call_site_paths=("root/a",),
            lockfile_entry=lock,
        )
        d = rec.to_dict()
        assert d["program_stable_id"] == "prog_1"
        assert d["program_name"] == "My Program"
        assert d["call_site_paths"] == ["root/a"]
        assert d["lockfile_entry"] == lock.to_dict()

    def test_to_dict_omits_none_stable_id(self) -> None:
        rec = DependentRecord(program_stable_id=None, program_name="prog")
        d = rec.to_dict()
        assert "program_stable_id" not in d

    def test_to_dict_omits_empty_call_site_paths(self) -> None:
        rec = DependentRecord(program_stable_id="prog_1", program_name="prog")
        d = rec.to_dict()
        assert "call_site_paths" not in d

    def test_to_dict_omits_none_lockfile(self) -> None:
        rec = DependentRecord(program_stable_id="prog_1", program_name="prog")
        d = rec.to_dict()
        assert "lockfile_entry" not in d

    def test_from_dict_minimal(self) -> None:
        rec = DependentRecord.from_dict({"program_name": "prog"})
        assert rec.program_stable_id is None
        assert rec.program_name == "prog"
        assert rec.call_site_paths == ()
        assert rec.lockfile_entry is None

    def test_from_dict_full_round_trip(self) -> None:
        lock = _lock()
        original = DependentRecord(
            program_stable_id="prog_1",
            program_name="My Program",
            call_site_paths=("root/a", "root/b"),
            lockfile_entry=lock,
        )
        rec = DependentRecord.from_dict(original.to_dict())
        assert rec.program_stable_id == original.program_stable_id
        assert rec.program_name == original.program_name
        assert rec.call_site_paths == original.call_site_paths
        assert rec.lockfile_entry == original.lockfile_entry

    def test_from_dict_missing_program_name_raises(self) -> None:
        with pytest.raises(KeyError):
            DependentRecord.from_dict({})

    def test_frozen(self) -> None:
        rec = DependentRecord(program_stable_id=None, program_name="prog")
        with pytest.raises(Exception):
            rec.program_name = "other"  # type: ignore[misc]

    def test_json_serializable(self) -> None:
        lock = _lock()
        rec = DependentRecord(
            program_stable_id="prog_1",
            program_name="My Program",
            call_site_paths=("root/a",),
            lockfile_entry=lock,
        )
        json_str = json.dumps(rec.to_dict(), sort_keys=True)
        parsed = json.loads(json_str)
        assert parsed["program_name"] == "My Program"


# ── PackReverseIndex — registration ────────────────────────────────────


class TestPackReverseIndexRegistration:
    """Registration semantics: adding dependents, merging paths, lockfile updates."""

    def test_register_single_dependent(self) -> None:
        index = PackReverseIndex()
        lock = _lock()
        index.register(
            dependency_stable_id="shared_step",
            program_stable_id="caller_1",
            program_name="Caller One",
            call_site_paths=("root/validate",),
            lockfile_entry=lock,
        )
        deps = index.dependents_of("shared_step")
        assert len(deps) == 1
        assert deps[0].program_stable_id == "caller_1"
        assert deps[0].program_name == "Caller One"
        assert deps[0].call_site_paths == ("root/validate",)
        assert deps[0].lockfile_entry is lock

    def test_register_multiple_dependents_same_dep(self) -> None:
        index = PackReverseIndex()
        index.register("shared_step", "caller_1", "Caller One")
        index.register("shared_step", "caller_2", "Caller Two")
        deps = index.dependents_of("shared_step")
        assert len(deps) == 2
        names = {d.program_name for d in deps}
        assert names == {"Caller One", "Caller Two"}

    def test_register_same_program_merges_call_site_paths(self) -> None:
        index = PackReverseIndex()
        index.register(
            "shared_step",
            "caller_1",
            "Caller One",
            call_site_paths=("root/a",),
        )
        index.register(
            "shared_step",
            "caller_1",
            "Caller One",
            call_site_paths=("root/b",),
        )
        deps = index.dependents_of("shared_step")
        assert len(deps) == 1
        assert set(deps[0].call_site_paths) == {"root/a", "root/b"}

    def test_register_same_program_deduplicates_paths(self) -> None:
        index = PackReverseIndex()
        index.register(
            "shared_step",
            "caller_1",
            "Caller One",
            call_site_paths=("root/a", "root/b"),
        )
        index.register(
            "shared_step",
            "caller_1",
            "Caller One",
            call_site_paths=("root/b", "root/c"),
        )
        deps = index.dependents_of("shared_step")
        assert len(deps) == 1
        # order-preserving, deduplicated
        assert deps[0].call_site_paths == ("root/a", "root/b", "root/c")

    def test_register_later_lockfile_wins(self) -> None:
        index = PackReverseIndex()
        lock1 = _lock(version="1.0.0", interface_hash="sha256:aaa")
        lock2 = _lock(version="2.0.0", interface_hash="sha256:bbb")
        index.register(
            "shared_step",
            "caller_1",
            "Caller One",
            call_site_paths=("root/a",),
            lockfile_entry=lock1,
        )
        index.register(
            "shared_step",
            "caller_1",
            "Caller One",
            call_site_paths=("root/b",),
            lockfile_entry=lock2,
        )
        deps = index.dependents_of("shared_step")
        assert deps[0].lockfile_entry is lock2

    def test_register_lockfile_not_overwritten_by_none(self) -> None:
        index = PackReverseIndex()
        lock1 = _lock()
        index.register(
            "shared_step",
            "caller_1",
            "Caller One",
            lockfile_entry=lock1,
        )
        index.register(
            "shared_step",
            "caller_1",
            "Caller One",
            lockfile_entry=None,
        )
        deps = index.dependents_of("shared_step")
        assert deps[0].lockfile_entry is lock1

    def test_register_empty_dependency_stable_id_raises(self) -> None:
        index = PackReverseIndex()
        with pytest.raises(ValueError, match="non-empty"):
            index.register("", "caller_1", "Caller One")

    def test_register_empty_program_name_raises(self) -> None:
        index = PackReverseIndex()
        with pytest.raises(ValueError, match="non-empty"):
            index.register("shared_step", "caller_1", "")

    def test_register_program_with_no_stable_id_uses_name_as_key(self) -> None:
        index = PackReverseIndex()
        index.register("shared_step", None, "Caller One")
        index.register("shared_step", None, "Caller One",
                       call_site_paths=("root/x",))
        deps = index.dependents_of("shared_step")
        assert len(deps) == 1
        assert deps[0].program_name == "Caller One"
        assert deps[0].call_site_paths == ("root/x",)

    def test_register_different_dependency_ids(self) -> None:
        index = PackReverseIndex()
        index.register("step_A", "prog_1", "Program 1")
        index.register("step_B", "prog_1", "Program 1")
        assert len(index.dependents_of("step_A")) == 1
        assert len(index.dependents_of("step_B")) == 1


# ── PackReverseIndex — direct dependents ────────────────────────────────


class TestDependentsOf:
    """Querying direct dependents by stable ID."""

    def test_dependents_of_known_id(self) -> None:
        index = PackReverseIndex()
        index.register("shared_step", "caller_1", "Caller One")
        index.register("shared_step", "caller_2", "Caller Two")
        deps = index.dependents_of("shared_step")
        assert len(deps) == 2

    def test_dependents_of_unknown_id_returns_empty(self) -> None:
        index = PackReverseIndex()
        deps = index.dependents_of("nonexistent")
        assert deps == ()

    def test_dependents_of_empty_string_returns_empty(self) -> None:
        index = PackReverseIndex()
        index.register("shared_step", "caller_1", "Caller One")
        deps = index.dependents_of("")
        assert deps == ()

    def test_dependents_of_returns_tuple_of_dependent_records(self) -> None:
        index = PackReverseIndex()
        lock = _lock()
        index.register(
            "shared_step", "caller_1", "Caller One",
            call_site_paths=("root/a",), lockfile_entry=lock,
        )
        deps = index.dependents_of("shared_step")
        assert isinstance(deps, tuple)
        assert isinstance(deps[0], DependentRecord)


# ── PackReverseIndex — containment / transitive traversal ───────────────


class TestTransitiveDependentsOf:
    """Containment traversal: transitive dependents via BFS over reverse index."""

    def test_direct_only_no_transitive(self) -> None:
        """When no dependents themselves have dependents, only direct ones appear."""
        index = PackReverseIndex()
        index.register("shared_step", "caller_1", "Caller One")
        index.register("shared_step", "caller_2", "Caller Two")
        # caller_1 and caller_2 have no dependents registered
        trans = index.transitive_dependents_of("shared_step")
        assert len(trans) == 2

    def test_chain_of_three(self) -> None:
        """A → B → C: transitive dependents of C include B and A."""
        index = PackReverseIndex()
        # C depends on nothing (leaf)
        # B depends on C
        index.register("C", "B", "Program B")
        # A depends on B
        index.register("B", "A", "Program A")

        trans = index.transitive_dependents_of("C")
        # BFS: first B (direct dependent of C), then A (dependent of B)
        assert len(trans) == 2
        names = [r.program_name for r in trans]
        assert names == ["Program B", "Program A"]

    def test_diamond_dependency(self) -> None:
        """A → B, A → C, B → D, C → D: D has A as transitive dependent once."""
        index = PackReverseIndex()
        index.register("D", "B", "Program B")
        index.register("D", "C", "Program C")
        index.register("B", "A", "Program A")
        index.register("C", "A", "Program A")

        trans = index.transitive_dependents_of("D")
        names = [r.program_name for r in trans]
        # B and C first (direct), then A (once, deduplicated)
        assert names.count("Program A") == 1
        assert set(names) == {"Program B", "Program C", "Program A"}

    def test_transitive_empty_for_leaf(self) -> None:
        """A depends on B with no dependents of its own → B has only A as transitive."""
        index = PackReverseIndex()
        index.register("B", "A", "Program A")
        trans = index.transitive_dependents_of("B")
        assert len(trans) == 1
        assert trans[0].program_name == "Program A"

    def test_cycle_detection(self) -> None:
        """A depends on B, B depends on A: transitive traversal terminates."""
        index = PackReverseIndex()
        index.register("B", "A", "Program A")
        index.register("A", "B", "Program B")
        trans = index.transitive_dependents_of("B")
        # BFS: A then B — but B is already visited
        assert len(trans) == 2

    def test_transitive_with_empty_stable_id(self) -> None:
        index = PackReverseIndex()
        trans = index.transitive_dependents_of("")
        assert trans == ()


# ── PackReverseIndex — path-prefix lookup ───────────────────────────────


class TestLookupByPathPrefix:
    """Querying dependents by call-site path prefix."""

    def test_exact_prefix_match(self) -> None:
        index = PackReverseIndex()
        index.register(
            "shared_step", "caller_1", "Caller One",
            call_site_paths=("root/validate", "root/build"),
        )
        results = index.lookup_by_path_prefix("root/validate")
        assert len(results) == 1
        dep_id, rec = results[0]
        assert dep_id == "shared_step"
        assert rec.program_name == "Caller One"

    def test_broader_prefix_match(self) -> None:
        index = PackReverseIndex()
        index.register(
            "shared_step", "caller_1", "Caller One",
            call_site_paths=("root/validate/check_x",),
        )
        index.register(
            "shared_step", "caller_2", "Caller Two",
            call_site_paths=("root/build",),
        )
        results = index.lookup_by_path_prefix("root/validate")
        assert len(results) == 1
        assert results[0][1].program_name == "Caller One"

    def test_root_prefix_matches_all(self) -> None:
        index = PackReverseIndex()
        index.register(
            "step_A", "prog_1", "Program 1",
            call_site_paths=("root/alpha",),
        )
        index.register(
            "step_B", "prog_2", "Program 2",
            call_site_paths=("root/beta/gamma",),
        )
        results = index.lookup_by_path_prefix("root")
        assert len(results) == 2

    def test_no_match_returns_empty(self) -> None:
        index = PackReverseIndex()
        index.register(
            "shared_step", "caller_1", "Caller One",
            call_site_paths=("root/validate",),
        )
        results = index.lookup_by_path_prefix("other/prefix")
        assert results == ()

    def test_empty_prefix_returns_empty(self) -> None:
        index = PackReverseIndex()
        index.register(
            "shared_step", "caller_1", "Caller One",
            call_site_paths=("root/validate",),
        )
        results = index.lookup_by_path_prefix("")
        assert results == ()

    def test_multiple_records_matching_same_prefix(self) -> None:
        index = PackReverseIndex()
        index.register(
            "step_A", "prog_1", "Program 1",
            call_site_paths=("root/alpha",),
        )
        index.register(
            "step_B", "prog_2", "Program 2",
            call_site_paths=("root/alpha/sub",),
        )
        index.register(
            "step_C", "prog_3", "Program 3",
            call_site_paths=("root/beta",),
        )
        results = index.lookup_by_path_prefix("root/alpha")
        assert len(results) == 2
        dep_ids = {r[0] for r in results}
        assert dep_ids == {"step_A", "step_B"}

    def test_one_record_multiple_paths_one_match(self) -> None:
        index = PackReverseIndex()
        index.register(
            "shared_step", "caller_1", "Caller One",
            call_site_paths=("root/validate", "root/build"),
        )
        results = index.lookup_by_path_prefix("root/build")
        assert len(results) == 1
        assert results[0][1].program_name == "Caller One"


# ── PackReverseIndex — ancestors of ─────────────────────────────────────


class TestAncestorsOf:
    """Parent/ancestor traversal up dependency chains."""

    def test_direct_ancestors(self) -> None:
        """Program depends on A and B: ancestors are A, B."""
        index = PackReverseIndex()
        index.register("A", "prog", "Program")
        index.register("B", "prog", "Program")
        ancestors = index.ancestors_of("prog")
        assert set(ancestors) == {"A", "B"}

    def test_transitive_ancestors(self) -> None:
        """prog → A → B → C: ancestors_of('prog') returns A, B, C."""
        index = PackReverseIndex()
        index.register("A", "prog", "Program")
        index.register("B", "A", "Dep A")
        index.register("C", "B", "Dep B")
        ancestors = index.ancestors_of("prog")
        # BFS order: A, then B, then C
        assert len(ancestors) == 3
        assert ancestors[0] == "A"
        assert "B" in ancestors
        assert "C" in ancestors

    def test_ancestors_none_stable_id_returns_empty(self) -> None:
        index = PackReverseIndex()
        ancestors = index.ancestors_of(None)
        assert ancestors == ()

    def test_ancestors_empty_string_returns_empty(self) -> None:
        index = PackReverseIndex()
        ancestors = index.ancestors_of("")
        assert ancestors == ()

    def test_ancestors_unknown_program_returns_empty(self) -> None:
        index = PackReverseIndex()
        ancestors = index.ancestors_of("unknown")
        assert ancestors == ()

    def test_ancestors_with_cycle(self) -> None:
        """A → B, B → A: cycle detected, no infinite loop."""
        index = PackReverseIndex()
        index.register("B", "A", "Program A")
        index.register("A", "B", "Program B")
        ancestors = index.ancestors_of("A")
        # BFS: B, then (A which is visited)
        assert len(ancestors) == 1
        assert ancestors[0] == "B"


# ── PackReverseIndex — cross-program dependents ─────────────────────────


class TestCrossProgramDependents:
    """Cross-program reverse dependency queries."""

    def test_program_with_dependents(self) -> None:
        index = PackReverseIndex()
        index.register("prog", "caller_1", "Caller One")
        index.register("prog", "caller_2", "Caller Two")
        deps = index.cross_program_dependents("prog")
        assert len(deps) == 2

    def test_program_with_no_dependents(self) -> None:
        index = PackReverseIndex()
        index.register("other", "caller_1", "Caller One")
        deps = index.cross_program_dependents("unrelated")
        assert deps == ()

    def test_cross_program_same_as_dependents_of(self) -> None:
        index = PackReverseIndex()
        lock = _lock()
        index.register(
            "shared_step", "caller_1", "Caller One",
            call_site_paths=("root/a",), lockfile_entry=lock,
        )
        assert (
            index.cross_program_dependents("shared_step")
            == index.dependents_of("shared_step")
        )


# ── PackReverseIndex — serialization round-trip ─────────────────────────


class TestPackReverseIndexSerialization:
    """to_dict / from_dict round-trip for PackReverseIndex."""

    def test_empty_index_round_trip(self) -> None:
        index = PackReverseIndex()
        data = index.to_dict()
        restored = PackReverseIndex.from_dict(data)
        assert restored.dependents_of("anything") == ()

    def test_populated_index_round_trip(self) -> None:
        index = PackReverseIndex()
        lock = _lock()
        index.register(
            "shared_step", "caller_1", "Caller One",
            call_site_paths=("root/a",), lockfile_entry=lock,
        )
        index.register("shared_step", "caller_2", "Caller Two")
        index.register("other_step", "caller_1", "Caller One")

        data = index.to_dict()
        restored = PackReverseIndex.from_dict(data)

        assert len(restored.dependents_of("shared_step")) == 2
        assert len(restored.dependents_of("other_step")) == 1
        restored_dep = restored.dependents_of("shared_step")[0]
        if restored_dep.program_stable_id == "caller_1":
            assert restored_dep.lockfile_entry == lock

    def test_json_serializable(self) -> None:
        index = PackReverseIndex()
        index.register("shared_step", "caller_1", "Caller One")
        json_str = json.dumps(index.to_dict(), sort_keys=True)
        parsed = json.loads(json_str)
        assert "dependents" in parsed
        assert "forward" in parsed

    def test_round_trip_preserves_ancestors(self) -> None:
        index = PackReverseIndex()
        index.register("B", "A", "Program A")
        index.register("C", "B", "Program B")
        data = index.to_dict()
        restored = PackReverseIndex.from_dict(data)
        assert set(restored.ancestors_of("A")) == {"B", "C"}

    def test_round_trip_preserves_transitive_dependents(self) -> None:
        index = PackReverseIndex()
        index.register("B", "A", "Program A")
        index.register("C", "B", "Program B")
        data = index.to_dict()
        restored = PackReverseIndex.from_dict(data)
        trans = restored.transitive_dependents_of("C")
        assert len(trans) == 2


# ── PackReverseIndex — frozen DependentRecord ───────────────────────────


class TestDependentRecordFrozen:
    """Confirm DependentRecord is frozen."""

    def test_dependent_record_is_frozen(self) -> None:
        rec = DependentRecord(program_stable_id=None, program_name="prog")
        with pytest.raises(Exception):
            rec.program_name = "other"  # type: ignore[misc]

    def test_dependent_record_hashable(self) -> None:
        rec1 = DependentRecord(program_stable_id="a", program_name="A")
        rec2 = DependentRecord(program_stable_id="a", program_name="A")
        assert hash(rec1) == hash(rec2)

    def test_different_records_have_different_hashes(self) -> None:
        rec1 = DependentRecord(program_stable_id="a", program_name="A")
        rec2 = DependentRecord(program_stable_id="b", program_name="B")
        assert hash(rec1) != hash(rec2)


# ── Integration scenarios ───────────────────────────────────────────────


class TestIntegrationScenarios:
    """End-to-end scenarios that exercise multiple query types together."""

    def test_multi_program_chain_full_queries(self) -> None:
        """A → B → C → D: test all query types on the chain."""
        index = PackReverseIndex()
        lock_c = _lock(version="1.0.0", interface_hash="sha256:ccc")
        lock_b = _lock(version="1.0.0", interface_hash="sha256:bbb")

        index.register("D", "C", "Program C",
                       call_site_paths=("root/leaf",), lockfile_entry=lock_c)
        index.register("C", "B", "Program B",
                       call_site_paths=("root/mid",), lockfile_entry=lock_b)
        index.register("B", "A", "Program A",
                       call_site_paths=("root/top",))

        # Direct dependents
        assert len(index.dependents_of("D")) == 1
        assert index.dependents_of("D")[0].program_name == "Program C"
        assert index.dependents_of("C")[0].program_name == "Program B"
        assert index.dependents_of("B")[0].program_name == "Program A"

        # Transitive (containment)
        trans = index.transitive_dependents_of("D")
        names = [r.program_name for r in trans]
        assert names == ["Program C", "Program B", "Program A"]

        # Path-prefix
        leaf_results = index.lookup_by_path_prefix("root/leaf")
        assert len(leaf_results) == 1
        assert leaf_results[0][1].program_name == "Program C"

        mid_results = index.lookup_by_path_prefix("root/mid")
        assert len(mid_results) == 1
        assert mid_results[0][1].program_name == "Program B"

        # Ancestors (upward chain from A)
        ancestors = index.ancestors_of("A")
        # A depends on B, B depends on C, C depends on D
        assert ancestors[0] == "B"
        assert "C" in ancestors
        assert "D" in ancestors
        assert len(ancestors) == 3

        # Cross-program
        cross = index.cross_program_dependents("D")
        assert len(cross) == 1
        assert cross[0].lockfile_entry == lock_c

    def test_shared_dependency_across_programs(self) -> None:
        """Two programs depend on the same shared step at different paths."""
        index = PackReverseIndex()
        lock = _lock()
        index.register(
            "shared_step", "prog_A", "Program A",
            call_site_paths=("root/validate", "root/build"),
            lockfile_entry=lock,
        )
        index.register(
            "shared_step", "prog_B", "Program B",
            call_site_paths=("root/validate", "root/test"),
        )

        deps = index.dependents_of("shared_step")
        assert len(deps) == 2

        # Path-prefix finds both at root/validate
        validate_results = index.lookup_by_path_prefix("root/validate")
        assert len(validate_results) == 2

        # Only Program A at root/build
        build_results = index.lookup_by_path_prefix("root/build")
        assert len(build_results) == 1
        assert build_results[0][1].program_name == "Program A"

    def test_register_via_program_name_without_stable_id(self) -> None:
        """Programs identified by name (no stable_id) work across all queries."""
        index = PackReverseIndex()
        index.register("shared_step", None, "Program One",
                       call_site_paths=("root/a",))
        index.register("shared_step", None, "Program Two",
                       call_site_paths=("root/b",))

        deps = index.dependents_of("shared_step")
        assert len(deps) == 2

        # Ancestors via name
        index.register("other_step", "shared_step", "shared_step")
        ancestors = index.ancestors_of("shared_step")
        assert "other_step" in ancestors
