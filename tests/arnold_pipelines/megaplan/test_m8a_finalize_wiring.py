"""M8A handler wiring tests — splitter and validation compiler in finalize.

Verifies that ``_write_finalize_artifacts`` runs the task splitter and
validation compiler before each feasibility pass, augments ``graph_report``
with their diagnostics, and preserves the double-compile contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.handlers import finalize


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _low_complexity_task(task_id: str, **overrides: Any) -> dict[str, Any]:
    """Return a valid, low-complexity task that won't trigger the splitter."""
    task: dict[str, Any] = {
        "id": task_id,
        "objective": f"Implement bounded behavior {task_id}.",
        "description": f"Implement bounded behavior {task_id} and its narrow proof.",
        "kind": "code",
        "status": "pending",
        "complexity": 4,
        "complexity_justification": "Single module with clear contract.",
        "estimated_minutes": 5,
        "depends_on": [],
        "dependency_reasons": {},
        "routing_group": "",
        "write_set": {"paths": [f"src/{task_id.lower()}.py"], "complete": True},
        "narrow_tests": {
            "selectors": [f"tests/test_{task_id.lower()}.py"],
            "max_seconds": 120,
            "max_runs": 2,
        },
        "checkpoint": {"required": False, "max_interval_seconds": 300, "records": []},
        "executor_notes": "",
        "reviewer_verdict": "",
        "files_changed": [],
        "commands_run": [],
        "evidence_files": [],
    }
    task.update(overrides)
    return task


def _high_complexity_splittable_task(task_id: str) -> dict[str, Any]:
    """Return a valid complexity-7 task that SHOULD be split."""
    return {
        "id": task_id,
        "objective": "Refactor the auth middleware to support pluggable backends.",
        "description": "Extract the auth middleware into a pluggable backend system with "
        "a registry, default implementation, and migration guide.",
        "kind": "code",
        "status": "pending",
        "complexity": 7,
        "complexity_justification": "Touches the auth contract used by 4 call sites; "
        "non-trivial architecture change with significant regression risk.",
        "estimated_minutes": 14,
        "depends_on": [],
        "dependency_reasons": {},
        "routing_group": "",
        "write_set": {
            "paths": ["src/auth/middleware.py", "src/auth/backends.py"],
            "complete": True,
        },
        "narrow_tests": {
            "selectors": ["tests/test_auth_middleware.py"],
            "max_seconds": 120,
            "max_runs": 2,
        },
        "checkpoint": {
            "required": True,
            "max_interval_seconds": 300,
            "records": [
                "completed_subobjectives",
                "remaining_subobjectives",
                "output_hashes",
                "test_state",
            ],
        },
        "executor_notes": "",
        "reviewer_verdict": "",
        "files_changed": [],
        "commands_run": [],
        "evidence_files": [],
    }


def _payload(tasks: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "task_contract_version": 2,
        "validation_jobs": [],
        "tasks": tasks,
        "sense_checks": [],
        "watch_items": [],
        "user_actions": [],
        "provides": [],
        "assumes": [],
        "pre_existing": [],
        "meta_commentary": "",
        "critique_resolution_coverage": [],
    }
    base.update(extra)
    return base


def _code_state(plan_dir: Path, repo: Path) -> dict[str, Any]:
    return {
        "name": "p",
        "iteration": 1,
        "current_state": "gated",
        "config": {"mode": "code", "project_dir": str(repo), "robustness": "extreme"},
        "meta": {},
        "history": [],
        "plan_versions": [
            {
                "version": 1,
                "file": "plan_v1.md",
                "hash": "sha256:old",
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "last_gate": {"recommendation": "PROCEED", "passed": True},
        "sessions": {},
    }


def _minimal_setup(tmp_path: Path) -> tuple[Path, Path]:
    """Create repo + plan_dir scaffolding and return (plan_dir, repo)."""
    repo = tmp_path / "repo"
    plan_dir = repo / ".megaplan" / "plans" / "p"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan_v1.md").write_text("## Step 1: Do the thing\n", encoding="utf-8")
    (plan_dir / "plan_v1.meta.json").write_text("{}", encoding="utf-8")
    (plan_dir / "gate.json").write_text(
        json.dumps({"recommendation": "PROCEED", "passed": True}), encoding="utf-8"
    )
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "t1.py").write_text("# placeholder\n", encoding="utf-8")
    return plan_dir, repo


# ---------------------------------------------------------------------------
# Tests: splitter wiring
# ---------------------------------------------------------------------------


class TestM8AFinalizeSplitterWiring:
    def test_high_complexity_task_is_split_before_feasibility(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A complexity-7 task is replaced by impl+proof subtasks."""
        plan_dir, repo = _minimal_setup(tmp_path)
        state = _code_state(plan_dir, repo)
        payload = _payload([_high_complexity_splittable_task("T1")])

        # suppress baseline capture
        monkeypatch.setattr(
            finalize,
            "_capture_test_baseline_for_plan",
            lambda *a, **kw: {
                "baseline_test_failures": [],
                "baseline_test_command": "pytest",
            },
        )

        finalize._write_finalize_artifacts(plan_dir, payload, state)

        task_ids = [t["id"] for t in payload["tasks"]]
        assert "T1_impl" in task_ids, f"Expected T1_impl in {task_ids}"
        assert "T1_proof" in task_ids, f"Expected T1_proof in {task_ids}"
        assert "T1" not in task_ids, "Original T1 should be replaced by subtasks"

    def test_low_complexity_task_is_not_split(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A complexity-4 task passes through the splitter unchanged."""
        plan_dir, repo = _minimal_setup(tmp_path)
        state = _code_state(plan_dir, repo)
        payload = _payload([_low_complexity_task("T1")])

        monkeypatch.setattr(
            finalize,
            "_capture_test_baseline_for_plan",
            lambda *a, **kw: {
                "baseline_test_failures": [],
                "baseline_test_command": "pytest",
            },
        )

        finalize._write_finalize_artifacts(plan_dir, payload, state)

        task_ids = [t["id"] for t in payload["tasks"]]
        assert "T1" in task_ids, f"Low-complexity T1 should remain: {task_ids}"
        assert "T1_impl" not in task_ids
        assert "T1_proof" not in task_ids

    def test_proof_subtask_depends_on_impl(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The proof subtask has depends_on=[impl_id] with consumes_output reason."""
        plan_dir, repo = _minimal_setup(tmp_path)
        state = _code_state(plan_dir, repo)
        payload = _payload([_high_complexity_splittable_task("T1")])

        monkeypatch.setattr(
            finalize,
            "_capture_test_baseline_for_plan",
            lambda *a, **kw: {
                "baseline_test_failures": [],
                "baseline_test_command": "pytest",
            },
        )

        finalize._write_finalize_artifacts(plan_dir, payload, state)

        by_id = {t["id"]: t for t in payload["tasks"]}
        proof = by_id["T1_proof"]
        assert proof["depends_on"] == ["T1_impl"]
        assert "T1_impl" in proof["dependency_reasons"]
        assert proof["dependency_reasons"]["T1_impl"]["kind"] == "consumes_output"
        # Proof subtasks are reclassified as "audit" (read-only verification)
        # so they pass feasibility without declaring write_set paths.
        assert proof["kind"] == "audit", (
            f"Proof subtask kind should be 'audit' (reclassified by finalize), "
            f"got {proof['kind']!r}"
        )

    def test_graph_report_includes_splitter_diagnostics(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """graph_report carries splitter_diagnostics after finalize."""
        plan_dir, repo = _minimal_setup(tmp_path)
        state = _code_state(plan_dir, repo)
        payload = _payload([_high_complexity_splittable_task("T1")])

        monkeypatch.setattr(
            finalize,
            "_capture_test_baseline_for_plan",
            lambda *a, **kw: {
                "baseline_test_failures": [],
                "baseline_test_command": "pytest",
            },
        )

        finalize._write_finalize_artifacts(plan_dir, payload, state)

        graph_report = payload.get("graph_report")
        assert isinstance(graph_report, dict), "graph_report must be a dict"
        assert "splitter_diagnostics" in graph_report
        # With a valid high-complexity task, splitter_diagnostics should be empty
        assert graph_report["splitter_diagnostics"] == []


# ---------------------------------------------------------------------------
# Tests: validation compiler wiring
# ---------------------------------------------------------------------------


class TestM8AFinalizeValidationCompilerWiring:
    def test_graph_report_includes_validation_compilation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """graph_report carries validation_compilation after finalize."""
        plan_dir, repo = _minimal_setup(tmp_path)
        state = _code_state(plan_dir, repo)
        payload = _payload([_low_complexity_task("T1")])

        monkeypatch.setattr(
            finalize,
            "_capture_test_baseline_for_plan",
            lambda *a, **kw: {
                "baseline_test_failures": [],
                "baseline_test_command": "pytest",
            },
        )

        finalize._write_finalize_artifacts(plan_dir, payload, state)

        graph_report = payload.get("graph_report")
        assert isinstance(graph_report, dict)
        assert "validation_compilation" in graph_report
        vc = graph_report["validation_compilation"]
        assert isinstance(vc, dict)
        assert "validation_jobs" in vc
        assert "diagnostics" in vc
        assert "admitted" in vc
        # validation_jobs was set to [] in the payload, so admitted should be False
        # (empty array is not a validation error, but the compiler needs at least
        # one valid job for admit=True, or the array is just empty with no diags)
        assert isinstance(vc["admitted"], bool)

    def test_validation_jobs_empty_array_passes_through(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty validation_jobs array produces empty compiled jobs and no diagnostics."""
        plan_dir, repo = _minimal_setup(tmp_path)
        state = _code_state(plan_dir, repo)
        payload = _payload([_low_complexity_task("T1")], validation_jobs=[])

        monkeypatch.setattr(
            finalize,
            "_capture_test_baseline_for_plan",
            lambda *a, **kw: {
                "baseline_test_failures": [],
                "baseline_test_command": "pytest",
            },
        )

        finalize._write_finalize_artifacts(plan_dir, payload, state)

        vc = payload["graph_report"]["validation_compilation"]
        # Empty validation_jobs: no jobs to compile, no diagnostics, admitted=True
        assert vc["diagnostics"] == []
        assert vc["admitted"] is True, (
            f"Empty validation_jobs should yield admitted=True (no blocking "
            f"diagnostics), got {vc['admitted']!r}"
        )
        assert vc["validation_jobs"] == []


# ---------------------------------------------------------------------------
# Tests: double-compile contract
# ---------------------------------------------------------------------------


class TestM8AFinalizeDoubleCompile:
    def test_feasibility_admitted_hash_in_graph_report(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The graph_report still carries the feasibility fields including task_contract_hash."""
        plan_dir, repo = _minimal_setup(tmp_path)
        state = _code_state(plan_dir, repo)
        payload = _payload([_low_complexity_task("T1")])

        monkeypatch.setattr(
            finalize,
            "_capture_test_baseline_for_plan",
            lambda *a, **kw: {
                "baseline_test_failures": [],
                "baseline_test_command": "pytest",
            },
        )

        finalize._write_finalize_artifacts(plan_dir, payload, state)

        graph_report = payload["graph_report"]
        # All original feasibility fields are preserved
        assert "task_contract_hash" in graph_report
        assert "task_count" in graph_report
        assert "edge_count" in graph_report
        assert "max_width" in graph_report
        assert "batches" in graph_report
        assert "critical_path_task_ids" in graph_report
        assert "seriality" in graph_report
        assert "admitted" in graph_report
        assert graph_report["admitted"] is True

    def test_task_feasibility_json_is_written(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """task_feasibility.json is still written to the plan directory."""
        plan_dir, repo = _minimal_setup(tmp_path)
        state = _code_state(plan_dir, repo)
        payload = _payload([_low_complexity_task("T1")])

        monkeypatch.setattr(
            finalize,
            "_capture_test_baseline_for_plan",
            lambda *a, **kw: {
                "baseline_test_failures": [],
                "baseline_test_command": "pytest",
            },
        )

        finalize._write_finalize_artifacts(plan_dir, payload, state)

        feasibility_path = plan_dir / "task_feasibility.json"
        assert feasibility_path.exists()
        written = json.loads(feasibility_path.read_text(encoding="utf-8"))
        assert written["admitted"] is True
        assert written["task_count"] >= 1

    def test_unsplittable_task_with_diagnostics(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A high-complexity task with ambiguous objective produces splitter diagnostics.

        The unsplittable task remains in place (not replaced) and the splitter
        diagnostic is recorded in graph_report.  Because the objective is
        ambiguous but still within the 240-char feasibility limit, the
        unsplit original task passes feasibility on its own.
        """
        plan_dir, repo = _minimal_setup(tmp_path)
        state = _code_state(plan_dir, repo)

        # Ambiguous objective: uses "and" to join two independent directives
        # ("implement" + "test" = 2 verbs), triggering split_ambiguous_objective
        # without violating feasibility (no semicolons or newlines).
        bad_task = _high_complexity_splittable_task("T1")
        bad_task["objective"] = "Implement auth middleware and test all consumers."
        payload = _payload([bad_task])

        monkeypatch.setattr(
            finalize,
            "_capture_test_baseline_for_plan",
            lambda *a, **kw: {
                "baseline_test_failures": [],
                "baseline_test_command": "pytest",
            },
        )

        finalize._write_finalize_artifacts(plan_dir, payload, state)

        graph_report = payload["graph_report"]
        diagnostics = graph_report["splitter_diagnostics"]
        assert len(diagnostics) >= 1, (
            f"Expected at least one splitter diagnostic, got {diagnostics}"
        )
        assert any(
            d["code"] == "split_ambiguous_objective" for d in diagnostics
        ), f"No split_ambiguous_objective in {diagnostics}"
        # The original task remains in place (unsplit)
        task_ids = [t["id"] for t in payload["tasks"]]
        assert "T1" in task_ids, f"Unsplit task T1 should remain in {task_ids}"


# ---------------------------------------------------------------------------
# Tests: existing-plan immutability (report-only replay)
# ---------------------------------------------------------------------------


class TestM8AFinalizeExistingPlanImmutability:
    def test_graph_report_not_overwritten_by_replay(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When a plan is finalized, graph_report is set to the augmented feasibility dict.

        This test verifies that the augmentation (splitter_diagnostics +
        validation_compilation) is produced correctly. Replay tests (T1)
        separately verify byte-identical double-compile.
        """
        plan_dir, repo = _minimal_setup(tmp_path)
        state = _code_state(plan_dir, repo)
        payload = _payload([_low_complexity_task("T1")])

        monkeypatch.setattr(
            finalize,
            "_capture_test_baseline_for_plan",
            lambda *a, **kw: {
                "baseline_test_failures": [],
                "baseline_test_command": "pytest",
            },
        )

        finalize._write_finalize_artifacts(plan_dir, payload, state)

        # Verify the graph_report is a dict with all expected keys
        gr = payload["graph_report"]
        expected_keys = {
            "task_contract_hash",
            "task_count",
            "edge_count",
            "max_width",
            "batches",
            "critical_path_task_ids",
            "seriality",
            "admitted",
            "splitter_diagnostics",
            "validation_compilation",
        }
        for key in expected_keys:
            assert key in gr, f"graph_report missing key: {key}"
