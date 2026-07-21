"""Tests for task_splitter — complexity >= 7 task splitting with contract preservation."""

from __future__ import annotations

from copy import deepcopy

import pytest

from arnold_pipelines.megaplan.orchestration.task_splitter import (
    SPLIT_AMBIGUOUS_OBJECTIVE,
    SPLIT_COMPLEXITY_TOO_LOW,
    SPLIT_INCOMPLETE_WRITE_SET,
    SPLIT_MUTATING_VALIDATION,
    SPLIT_PROOF_EXHAUSTED,
    SplitDiagnostic,
    split_high_complexity_tasks,
    split_task,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _task(
    task_id: str,
    *,
    complexity: int = 8,
    kind: str = "code",
    depends_on: list[str] | None = None,
    minutes: int = 12,
    paths: list[str] | None = None,
    objective: str | None = None,
    selectors: list[str] | None = None,
    max_seconds: int = 60,
    max_runs: int = 2,
    write_set_complete: bool = True,
    description: str | None = None,
) -> dict:
    """Build a minimal well-formed task dict for splitter tests.

    Use ``paths=_NO_PATHS`` sentinel to explicitly pass an empty list
    (plain ``[]`` is falsy and the helper would substitute the default).
    """
    deps = list(depends_on or [])
    _paths = [f"src/{task_id.lower()}.py"] if paths is None else list(paths)
    _selectors = [f"tests/test_{task_id.lower()}.py"] if selectors is None else list(selectors)
    return {
        "id": task_id,
        "objective": objective or f"Implement the {task_id} module with full type safety.",
        "description": description or f"Implement the {task_id} module and its narrow proof.",
        "kind": kind,
        "status": "pending",
        "complexity": complexity,
        "complexity_justification": "Complex multi-file change with contract implications.",
        "estimated_minutes": minutes,
        "depends_on": deps,
        "dependency_reasons": {
            dep: {
                "kind": "consumes_output",
                "reason": f"{task_id} imports the contract created by {dep}.",
                "required_output": f"src/{dep.lower()}.py:Contract",
            }
            for dep in deps
        },
        "routing_group": "",
        "write_set": {
            "paths": _paths,
            "complete": write_set_complete,
        },
        "narrow_tests": {
            "selectors": _selectors,
            "max_seconds": max_seconds,
            "max_runs": max_runs,
        },
        "checkpoint": {
            "required": complexity >= 7,
            "max_interval_seconds": 300,
            "records": (
                [
                    "completed_subobjectives",
                    "remaining_subobjectives",
                    "output_hashes",
                    "test_state",
                ]
                if complexity >= 7
                else []
            ),
        },
    }


def _payload(tasks: list[dict]) -> dict:
    return {"task_contract_version": 2, "tasks": tasks, "validation_jobs": []}


def _subtasks(result: object) -> list[dict]:
    """Assert result is a list of subtask dicts and return it."""
    assert isinstance(result, list), f"Expected list of subtasks, got {type(result).__name__}: {result}"
    assert len(result) == 2, f"Expected 2 subtasks, got {len(result)}"
    assert all(isinstance(t, dict) for t in result)
    return result  # type: ignore[return-value]


def _diagnostic(result: object) -> SplitDiagnostic:
    """Assert result is a SplitDiagnostic and return it."""
    assert isinstance(result, SplitDiagnostic), f"Expected SplitDiagnostic, got {type(result).__name__}: {result}"
    return result


# ---------------------------------------------------------------------------
# Successful splitting
# ---------------------------------------------------------------------------

class TestSuccessfulSplitting:
    """Happy-path: complexity >= 7 tasks are split into impl + proof."""

    def test_splits_code_task_into_impl_and_proof(self) -> None:
        task = _task("T1", complexity=8, kind="code")
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert impl["id"] == "T1_impl"
        assert proof["id"] == "T1_proof"

        # Implementation keeps the original kind
        assert impl["kind"] == "code"
        # Proof is a test-kind task
        assert proof["kind"] == "test"

    def test_splits_docs_task_into_impl_and_proof(self) -> None:
        task = _task("T1", complexity=7, kind="docs", objective="Write architecture decision record.")
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert impl["kind"] == "docs"
        assert proof["kind"] == "test"

    def test_proof_depends_on_implementation(self) -> None:
        task = _task("T1", complexity=8)
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert proof["depends_on"] == ["T1_impl"]
        assert "T1_impl" in proof["dependency_reasons"]
        reason = proof["dependency_reasons"]["T1_impl"]
        assert reason["kind"] == "consumes_output"
        assert "T1_impl" in reason["reason"]

    def test_implementation_preserves_original_dependencies(self) -> None:
        task = _task("T2", complexity=8, depends_on=["T1"])
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert impl["depends_on"] == ["T1"]
        assert "T1" in impl["dependency_reasons"]

    def test_preserves_write_set_on_implementation(self) -> None:
        paths = ["src/module.py", "src/types.py"]
        task = _task("T1", complexity=8, paths=paths)
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert impl["write_set"]["paths"] == paths
        assert impl["write_set"]["complete"] is True

    def test_proof_has_empty_write_set(self) -> None:
        task = _task("T1", complexity=8, paths=["src/module.py"])
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert proof["write_set"]["paths"] == []
        assert proof["write_set"]["complete"] is True

    def test_preserves_narrow_tests_on_proof(self) -> None:
        selectors = ["tests/test_module.py", "tests/test_types.py"]
        task = _task("T1", complexity=8, selectors=selectors, max_seconds=60, max_runs=2)
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert proof["narrow_tests"]["selectors"] == selectors
        assert proof["narrow_tests"]["max_seconds"] == 60
        assert proof["narrow_tests"]["max_runs"] == 2

    def test_implementation_has_reduced_test_budget(self) -> None:
        task = _task("T1", complexity=8, selectors=["tests/test_t1.py"], max_seconds=60, max_runs=2)
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        # Implementation gets half max_seconds, at most 1 run
        assert impl["narrow_tests"]["max_seconds"] == 30
        assert impl["narrow_tests"]["max_runs"] == 1
        # But same selectors
        assert impl["narrow_tests"]["selectors"] == ["tests/test_t1.py"]

    def test_preserves_checkpoint_on_implementation(self) -> None:
        task = _task("T1", complexity=8)
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert impl["checkpoint"]["required"] is True
        assert impl["checkpoint"]["max_interval_seconds"] == 300
        assert set(impl["checkpoint"]["records"]) == {
            "completed_subobjectives",
            "remaining_subobjectives",
            "output_hashes",
            "test_state",
        }

    def test_proof_checkpoint_is_disabled(self) -> None:
        task = _task("T1", complexity=8)
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert proof["checkpoint"]["required"] is False
        assert proof["checkpoint"]["max_interval_seconds"] == 0
        assert proof["checkpoint"]["records"] == []

    def test_impl_complexity_reduced_by_three(self) -> None:
        task = _task("T1", complexity=9)
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert impl["complexity"] == 6  # 9 - 3
        assert proof["complexity"] == 3

    def test_impl_complexity_never_below_one(self) -> None:
        task = _task("T1", complexity=7)
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert impl["complexity"] >= 1
        assert impl["complexity"] <= 6

    def test_time_budget_split_is_proportional(self) -> None:
        task = _task("T1", complexity=8, minutes=20)
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        # Implementation gets ~70%
        assert impl["estimated_minutes"] == 14  # 20 * 0.70
        # Proof gets the remainder
        assert proof["estimated_minutes"] == 6  # 20 - 14
        # Total preserved
        assert impl["estimated_minutes"] + proof["estimated_minutes"] == 20

    def test_minimum_one_minute_each(self) -> None:
        task = _task("T1", complexity=8, minutes=2)
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert impl["estimated_minutes"] >= 1
        assert proof["estimated_minutes"] >= 1

    def test_routing_group_preserved_on_both_subtasks(self) -> None:
        task = _task("T1", complexity=8)
        task["routing_group"] = "shared-contract"
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert impl["routing_group"] == "shared-contract"
        assert proof["routing_group"] == "shared-contract"

    def test_description_preserved_on_implementation(self) -> None:
        task = _task("T1", complexity=8, description="Build the parser and wire up the AST.")
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert impl["description"] == "Build the parser and wire up the AST."

    def test_proof_has_derived_description(self) -> None:
        task = _task("T1", complexity=8)
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert "T1_impl" in proof["description"]
        assert "narrow tests" in proof["description"].lower()

    def test_deterministic_splitting(self) -> None:
        task = _task("T1", complexity=8)
        result_a = split_task(deepcopy(task))
        result_b = split_task(deepcopy(task))

        assert isinstance(result_a, list)
        assert isinstance(result_b, list)
        assert result_a == result_b

    def test_objective_derived_for_implementation(self) -> None:
        task = _task("T1", complexity=8, objective="Build the authentication module.")
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert impl["objective"].startswith("Implement:")
        assert "authentication" in impl["objective"].lower()

    def test_objective_derived_for_proof(self) -> None:
        task = _task("T1", complexity=8, objective="Build the authentication module.")
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert proof["objective"].startswith("Prove correctness of T1_impl")


# ---------------------------------------------------------------------------
# Rejection cases
# ---------------------------------------------------------------------------

class TestRejectionAmbiguousObjective:
    """Tasks with ambiguous/multi-directive objectives are rejected."""

    def test_semicolon_separated_objective_rejected(self) -> None:
        task = _task("T1", complexity=8, objective="Implement parser; add error recovery.")
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_AMBIGUOUS_OBJECTIVE
        assert diag.task_id == "T1"
        assert diag.is_reject is True
        assert diag.is_blocker is False

    def test_multi_sentence_directive_objective_rejected(self) -> None:
        task = _task(
            "T1",
            complexity=8,
            objective="Implement the parser. Create the AST nodes. Build the type checker.",
        )
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_AMBIGUOUS_OBJECTIVE

    def test_and_joined_verbs_rejected(self) -> None:
        task = _task("T1", complexity=8, objective="Implement the cache and test the eviction policy.")
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_AMBIGUOUS_OBJECTIVE

    def test_newline_separated_directives_rejected(self) -> None:
        task = _task(
            "T1",
            complexity=8,
            objective="Implement the cache layer.\nTest the eviction policy.",
        )
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_AMBIGUOUS_OBJECTIVE

    def test_non_string_objective_rejected(self) -> None:
        task = _task("T1", complexity=8)
        task["objective"] = None  # type: ignore[assignment]
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_AMBIGUOUS_OBJECTIVE

    def test_empty_objective_rejected(self) -> None:
        task = _task("T1", complexity=8, objective="   ")
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_AMBIGUOUS_OBJECTIVE

    def test_single_clear_objective_accepted(self) -> None:
        task = _task("T1", complexity=8, objective="Implement the bounded LRU cache.")
        result = split_task(task)
        assert isinstance(result, list)  # accepted


class TestRejectionIncompleteWriteSet:
    """Tasks with missing or incomplete write sets are rejected."""

    def test_missing_write_set_rejected(self) -> None:
        task = _task("T1", complexity=8)
        del task["write_set"]
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_INCOMPLETE_WRITE_SET

    def test_write_set_not_complete_rejected(self) -> None:
        task = _task("T1", complexity=8, write_set_complete=False)
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_INCOMPLETE_WRITE_SET

    def test_empty_paths_rejected(self) -> None:
        task = _task("T1", complexity=8, paths=[])
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_INCOMPLETE_WRITE_SET

    def test_non_list_paths_rejected(self) -> None:
        task = _task("T1", complexity=8)
        task["write_set"]["paths"] = "src/file.py"  # type: ignore[assignment]
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_INCOMPLETE_WRITE_SET

    def test_paths_with_empty_strings_rejected(self) -> None:
        task = _task("T1", complexity=8, paths=["src/file.py", "   "])
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_INCOMPLETE_WRITE_SET

    def test_non_mapping_write_set_rejected(self) -> None:
        task = _task("T1", complexity=8)
        task["write_set"] = ["src/file.py"]  # type: ignore[assignment]
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_INCOMPLETE_WRITE_SET


class TestRejectionMutatingValidation:
    """Test-kind tasks with write paths are rejected as mutating validation."""

    def test_test_kind_with_write_paths_rejected(self) -> None:
        task = _task("T1", complexity=8, kind="test", paths=["src/test_helper.py"])
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_MUTATING_VALIDATION

    def test_test_kind_without_write_paths_is_not_mutating(self) -> None:
        # A test-kind task with empty paths is rejected, but NOT as mutating validation
        task = _task("T1", complexity=8, kind="test", paths=[])
        diag = _diagnostic(split_task(task))
        assert diag.code != SPLIT_MUTATING_VALIDATION
        # It is rejected for incomplete write set (empty paths checked before kind gate)
        assert diag.code == SPLIT_INCOMPLETE_WRITE_SET

    def test_code_kind_with_test_objective_not_rejected_as_mutating(self) -> None:
        # A code task saying "test" in objective is fine — it implements and tests
        task = _task("T1", complexity=8, kind="code", objective="Implement and test the cache.")
        # This is ambiguous_objective, not mutating_validation
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_AMBIGUOUS_OBJECTIVE


class TestRejectionComplexityTooLow:
    """Tasks below the split threshold are rejected."""

    def test_complexity_6_rejected(self) -> None:
        task = _task("T1", complexity=6)
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_COMPLEXITY_TOO_LOW

    def test_complexity_1_rejected(self) -> None:
        task = _task("T1", complexity=1)
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_COMPLEXITY_TOO_LOW

    def test_missing_complexity_rejected(self) -> None:
        task = _task("T1", complexity=8)
        del task["complexity"]
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_COMPLEXITY_TOO_LOW

    def test_non_int_complexity_rejected(self) -> None:
        task = _task("T1", complexity=8)
        task["complexity"] = "high"  # type: ignore[assignment]
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_COMPLEXITY_TOO_LOW

    def test_complexity_7_is_split(self) -> None:
        task = _task("T1", complexity=7)
        result = split_task(task)
        assert isinstance(result, list)


class TestBlockerProofExhausted:
    """Tasks with no valid proof path emit proof_exhausted blocker."""

    def test_no_narrow_tests_blocked(self) -> None:
        task = _task("T1", complexity=8)
        del task["narrow_tests"]
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_PROOF_EXHAUSTED
        assert diag.is_blocker is True
        assert diag.is_reject is False

    def test_empty_selectors_blocked(self) -> None:
        task = _task("T1", complexity=8, selectors=[])
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_PROOF_EXHAUSTED

    def test_selectors_with_empty_strings_blocked(self) -> None:
        task = _task("T1", complexity=8, selectors=["tests/test_t1.py", "  "])
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_PROOF_EXHAUSTED

    def test_non_list_selectors_blocked(self) -> None:
        task = _task("T1", complexity=8)
        task["narrow_tests"]["selectors"] = "tests/test_t1.py"  # type: ignore[assignment]
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_PROOF_EXHAUSTED

    def test_zero_max_seconds_blocked(self) -> None:
        task = _task("T1", complexity=8, max_seconds=0)
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_PROOF_EXHAUSTED

    def test_zero_max_runs_blocked(self) -> None:
        task = _task("T1", complexity=8, max_runs=0)
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_PROOF_EXHAUSTED

    def test_non_mapping_narrow_tests_blocked(self) -> None:
        task = _task("T1", complexity=8)
        task["narrow_tests"] = ["tests/test_t1.py"]  # type: ignore[assignment]
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_PROOF_EXHAUSTED


class TestNonSplittableKinds:
    """Tasks of non-splittable kinds are rejected."""

    def test_test_kind_rejected(self) -> None:
        task = _task("T1", complexity=8, kind="test", paths=[])
        diag = _diagnostic(split_task(task))
        # Rejected — could be incomplete_write_set (empty paths checked first)
        # or ambiguous_objective (unsplittable kind); either means rejected.
        assert diag.is_reject is True
        assert diag.code in {SPLIT_INCOMPLETE_WRITE_SET, SPLIT_AMBIGUOUS_OBJECTIVE}

    def test_review_kind_rejected(self) -> None:
        task = _task("T1", complexity=8, kind="review")
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_AMBIGUOUS_OBJECTIVE

    def test_unknown_kind_rejected(self) -> None:
        task = _task("T1", complexity=8, kind="deploy")
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_AMBIGUOUS_OBJECTIVE


# ---------------------------------------------------------------------------
# Diagnostic properties
# ---------------------------------------------------------------------------

class TestDiagnosticProperties:
    """SplitDiagnostic as_dict and typed properties."""

    def test_as_dict_includes_all_fields(self) -> None:
        diag = SplitDiagnostic(SPLIT_AMBIGUOUS_OBJECTIVE, "Test message.", "T1")
        d = diag.as_dict()
        assert d["code"] == SPLIT_AMBIGUOUS_OBJECTIVE
        assert d["message"] == "Test message."
        assert d["task_id"] == "T1"

    def test_as_dict_omits_none_task_id(self) -> None:
        diag = SplitDiagnostic(SPLIT_PROOF_EXHAUSTED, "No proof.")
        d = diag.as_dict()
        assert "task_id" not in d

    def test_reject_is_not_blocker(self) -> None:
        diag = SplitDiagnostic(SPLIT_AMBIGUOUS_OBJECTIVE, "msg")
        assert diag.is_reject is True
        assert diag.is_blocker is False

    def test_blocker_is_not_reject(self) -> None:
        diag = SplitDiagnostic(SPLIT_PROOF_EXHAUSTED, "msg")
        assert diag.is_blocker is True
        assert diag.is_reject is False


# ---------------------------------------------------------------------------
# Batch splitter
# ---------------------------------------------------------------------------

class TestBatchSplitter:
    """split_high_complexity_tasks processes entire payloads."""

    def test_splits_only_high_complexity_tasks(self) -> None:
        tasks = [
            _task("T1", complexity=4),   # stays
            _task("T2", complexity=8),   # split
            _task("T3", complexity=5),   # stays
            _task("T4", complexity=9),   # split
        ]
        result, diags = split_high_complexity_tasks(_payload(tasks))

        assert diags == []
        ids = [t["id"] for t in result]
        assert "T1" in ids
        assert "T3" in ids
        assert "T2_impl" in ids
        assert "T2_proof" in ids
        assert "T4_impl" in ids
        assert "T4_proof" in ids
        assert "T2" not in ids  # replaced
        assert "T4" not in ids  # replaced
        assert len(result) == 6  # 2 kept + 2*2 split

    def test_unsplittable_tasks_kept_and_diagnostic_emitted(self) -> None:
        tasks = [
            _task("T1", complexity=4),
            _task("T2", complexity=8, objective="X; Y"),  # ambiguous
        ]
        result, diags = split_high_complexity_tasks(_payload(tasks))

        assert len(diags) == 1
        assert diags[0].code == SPLIT_AMBIGUOUS_OBJECTIVE
        assert diags[0].task_id == "T2"

        ids = [t["id"] for t in result]
        assert "T1" in ids
        assert "T2" in ids  # kept as-is since unsplittable
        assert len(result) == 2

    def test_empty_tasks_list(self) -> None:
        result, diags = split_high_complexity_tasks({"tasks": []})
        assert result == []
        assert diags == []

    def test_non_list_tasks(self) -> None:
        result, diags = split_high_complexity_tasks({"tasks": "not a list"})
        assert result == []
        assert len(diags) == 1
        assert diags[0].code == SPLIT_AMBIGUOUS_OBJECTIVE

    def test_non_dict_entry_in_tasks(self) -> None:
        result, diags = split_high_complexity_tasks({"tasks": ["not a dict"]})
        assert result == []
        assert len(diags) == 1
        assert diags[0].code == SPLIT_AMBIGUOUS_OBJECTIVE

    def test_mixed_valid_and_invalid(self) -> None:
        tasks = [
            _task("T1", complexity=4),
            "not a dict",
            _task("T2", complexity=8, objective="X; Y"),
            _task("T3", complexity=8),
        ]
        result, diags = split_high_complexity_tasks(_payload(tasks))

        # Two diagnostics: non-dict entry + ambiguous T2
        assert len(diags) == 2
        codes = {d.code for d in diags}
        assert SPLIT_AMBIGUOUS_OBJECTIVE in codes

        ids = [t["id"] for t in result]
        assert "T1" in ids
        assert "T2" in ids  # kept (ambiguous)
        assert "T3_impl" in ids
        assert "T3_proof" in ids


# ---------------------------------------------------------------------------
# Contract preservation: write/test/checkpoint
# ---------------------------------------------------------------------------

class TestContractPreservation:
    """Subtask contracts must preserve write/test/checkpoint semantics."""

    def test_original_write_set_not_modified(self) -> None:
        original = _task("T1", complexity=8, paths=["src/original.py"])
        original_paths = list(original["write_set"]["paths"])
        split_task(original)
        # Original must be unchanged
        assert original["write_set"]["paths"] == original_paths
        assert original["write_set"]["paths"][0] == "src/original.py"

    def test_original_narrow_tests_not_modified(self) -> None:
        original = _task("T1", complexity=8, selectors=["tests/test_t1.py"])
        original_selectors = list(original["narrow_tests"]["selectors"])
        split_task(original)
        assert original["narrow_tests"]["selectors"] == original_selectors

    def test_original_checkpoint_not_modified(self) -> None:
        original = _task("T1", complexity=8)
        original_records = list(original["checkpoint"]["records"])
        split_task(original)
        assert original["checkpoint"]["records"] == original_records

    def test_proof_required_output_references_impl_paths(self) -> None:
        task = _task("T1", complexity=8, paths=["src/auth.py", "src/session.py"])
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        required = proof["dependency_reasons"]["T1_impl"]["required_output"]
        assert "src/auth.py" in required
        assert "src/session.py" in required

    def test_impl_dependency_reasons_drop_self_references(self) -> None:
        """dependency_reasons for the impl should not include the original task id."""
        task = _task("T2", complexity=8, depends_on=["T1"])
        # Artificially add a self-reference
        task["dependency_reasons"]["T2"] = {"kind": "consumes_output", "reason": "self", "required_output": "x"}
        subtasks = _subtasks(split_task(task))

        impl, proof = subtasks
        assert "T2" not in impl["dependency_reasons"]
        assert "T1" in impl["dependency_reasons"]

    def test_deterministic_across_copies(self) -> None:
        task = _task("T1", complexity=9, minutes=15, paths=["src/a.py", "src/b.py"])
        a = split_task(deepcopy(task))
        b = split_task(deepcopy(task))
        assert a == b


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Corner cases and boundary conditions."""

    def test_complexity_exactly_7(self) -> None:
        task = _task("T1", complexity=7)
        result = split_task(task)
        assert isinstance(result, list)

    def test_complexity_10(self) -> None:
        task = _task("T1", complexity=10)
        subtasks = _subtasks(split_task(task))
        impl, proof = subtasks
        # 10 - 3 = 7, but capped at 6
        assert impl["complexity"] == 6

    def test_missing_task_id(self) -> None:
        task = _task("T1", complexity=8)
        del task["id"]
        diag = _diagnostic(split_task(task))
        assert diag.code == SPLIT_AMBIGUOUS_OBJECTIVE

    def test_original_status_preserved(self) -> None:
        task = _task("T1", complexity=8)
        subtasks = _subtasks(split_task(task))
        for st in subtasks:
            assert st["status"] == "pending"

    def test_proof_is_standalone_test(self) -> None:
        """Proof subtask should be a well-formed test task with no write_set paths."""
        task = _task("T1", complexity=8)
        subtasks = _subtasks(split_task(task))
        impl, proof = subtasks
        assert proof["kind"] == "test"
        assert proof["write_set"]["paths"] == []
        assert proof["write_set"]["complete"] is True
        assert proof["complexity"] == 3
