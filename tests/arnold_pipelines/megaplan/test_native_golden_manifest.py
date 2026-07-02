"""Native golden manifest integrity and comparison tests.

Validates the native golden manifest, canonical scenario imports/builders,
live native trace comparison, and record-mode explanation guarding.

These tests bridge the manifest metadata (T8), the comparison helpers (T6),
and the directory-level regression rule (T7) into a single verification
surface for M5 substrate proof.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.conformance.workflow_manifest_runtime import GoldenRegressionRule
from tests.arnold_pipelines.megaplan.fixtures.native_goldens import (
    TRACE_FILE_NAMES,
    _canonical_json,
    compare_native_golden_dir,
    record_native_golden_dir,
)

# ── manifest fixture ────────────────────────────────────────────────────────

MANIFEST_PATH = Path(__file__).resolve().parent / "fixtures" / "native_goldens" / "manifest.json"


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


# ── manifest structure / integrity ─────────────────────────────────────────


class TestManifestStructure:
    """Schema-level checks against the native golden manifest."""

    @pytest.fixture(autouse=True)
    def _manifest(self) -> dict:
        return _load_manifest()

    def test_manifest_has_correct_schema(self, _manifest: dict) -> None:
        assert _manifest["schema"] == "arnold.megaplan.native_goldens.manifest.v1"

    def test_manifest_has_description_and_timestamp(self, _manifest: dict) -> None:
        assert isinstance(_manifest["description"], str) and _manifest["description"]
        assert isinstance(_manifest["timestamp"], str) and _manifest["timestamp"]

    def test_manifest_scenarios_section_exists(self, _manifest: dict) -> None:
        scenarios = _manifest["scenarios"]
        assert isinstance(scenarios, dict)
        assert "committed" in scenarios
        assert "deferred" in scenarios

    def test_committed_scenarios_cover_D1_through_D8_and_D12(self, _manifest: dict) -> None:
        committed_ids = {s["scenario_id"] for s in _manifest["scenarios"]["committed"]}
        expected = {"D1-prep-plan", "D2-critique", "D3-gate-preflight",
                    "D4-gate-revise", "D5-tiebreaker", "D6-finalize",
                    "D7-execute-dag", "D8-execute-gates", "D12-runtime-trace"}
        assert committed_ids == expected

    def test_deferred_scenarios_cover_D9_through_D11_and_D13_through_D15(self, _manifest: dict) -> None:
        deferred_ids = {s["scenario_id"] for s in _manifest["scenarios"]["deferred"]}
        expected = {"D9-review-fanout", "D10-review-caps", "D11-human-control",
                    "D13-policy-platform", "D14-compiler-authoring", "D15-handler-extraction"}
        assert deferred_ids == expected

    def test_no_duplicate_scenario_ids(self, _manifest: dict) -> None:
        committed_ids = {s["scenario_id"] for s in _manifest["scenarios"]["committed"]}
        deferred_ids = {s["scenario_id"] for s in _manifest["scenarios"]["deferred"]}
        assert committed_ids.isdisjoint(deferred_ids), (
            f"Overlap: {committed_ids & deferred_ids}"
        )

    def test_every_committed_scenario_has_at_least_one_runner(self, _manifest: dict) -> None:
        for scenario in _manifest["scenarios"]["committed"]:
            runners = scenario.get("deterministic_runners", [])
            assert len(runners) >= 1, (
                f"{scenario['scenario_id']}: must have at least one deterministic runner"
            )

    def test_every_runner_has_required_fields(self, _manifest: dict) -> None:
        required = {"subpipeline", "canonical_import", "builder", "coverage", "test_function"}
        for scenario in _manifest["scenarios"]["committed"]:
            for runner in scenario["deterministic_runners"]:
                missing = required - set(runner.keys())
                assert not missing, (
                    f"{scenario['scenario_id']}/{runner['subpipeline']}: missing fields {missing}"
                )

    def test_every_deferred_scenario_has_reason_and_target(self, _manifest: dict) -> None:
        for scenario in _manifest["scenarios"]["deferred"]:
            assert isinstance(scenario.get("reason"), str) and scenario["reason"]
            assert isinstance(scenario.get("target_milestone"), str) and scenario["target_milestone"]

    def test_contract_section_complete(self, _manifest: dict) -> None:
        contract = _manifest["contract"]
        assert contract["golden_root"] == "tests/arnold_pipelines/megaplan/fixtures/native_goldens/"
        assert contract["fixture_format"] == "multi-file directory"
        assert set(contract["required_files"]) == set(TRACE_FILE_NAMES)
        assert contract["normalization"] is not None
        assert "GoldenRegressionRule" in contract["regression_guard"]
        assert contract["recording_flag"] == "--record-goldens"
        assert "compare_native_golden_dir" in contract["comparison_helper"]

    def test_committed_and_deferred_together_cover_D1_through_D15(self, _manifest: dict) -> None:
        all_ids = {s["scenario_id"] for s in _manifest["scenarios"]["committed"]} | \
                  {s["scenario_id"] for s in _manifest["scenarios"]["deferred"]}
        expected = {f"D{i}-{slug}" for i, slug in enumerate([
            "prep-plan", "critique", "gate-preflight", "gate-revise",
            "tiebreaker", "finalize", "execute-dag", "execute-gates",
            "review-fanout", "review-caps", "human-control",
            "runtime-trace", "policy-platform", "compiler-authoring",
            "handler-extraction",
        ], start=1)}
        assert all_ids == expected

    def test_committed_scenarios_have_alignment_rows(self, _manifest: dict) -> None:
        for scenario in _manifest["scenarios"]["committed"]:
            rows = scenario.get("alignment_rows", [])
            assert isinstance(rows, list) and len(rows) >= 1, (
                f"{scenario['scenario_id']}: must have at least one alignment_row"
            )


# ── canonical import / builder verification ────────────────────────────────


class TestCanonicalImportsAndBuilders:
    """Verify that every canonical_import and builder in the manifest resolves."""

    @staticmethod
    def _all_runners() -> list[dict]:
        manifest = _load_manifest()
        runners: list[dict] = []
        for scenario in manifest["scenarios"]["committed"]:
            for runner in scenario["deterministic_runners"]:
                runners.append({**runner, "_scenario_id": scenario["scenario_id"]})
        return runners

    @pytest.mark.parametrize("runner", _all_runners.__func__())  # type: ignore[attr-defined]
    def test_canonical_import_resolves(self, runner: dict) -> None:
        """Each runner's canonical_import statement resolves to a callable builder."""
        import_statement: str = runner["canonical_import"]
        # Parse "from X import Y as Z" or "from X import Y"
        statement = import_statement.strip()
        try:
            exec(statement, {})
        except Exception as exc:
            pytest.fail(
                f"{runner['_scenario_id']}/{runner['subpipeline']}: "
                f"import failed: {exc}"
            )

    @pytest.mark.parametrize("runner", _all_runners.__func__())  # type: ignore[attr-defined]
    def test_builder_produces_native_program(self, runner: dict) -> None:
        """Each builder function returns a pipeline with a non-null native_program.

        The D12 meta-runner (``run_native_pipeline``) is excluded — it is not a
        pipeline builder but a runtime entry point declared for trace contract
        documentation.
        """
        if runner["builder"] == "run_native_pipeline":
            pytest.skip("D12 meta-runner is a runtime entry point, not a pipeline builder")

        import_statement: str = runner["canonical_import"]
        builder_name: str = runner["builder"]

        # Execute the import to get the builder
        local_ns: dict = {}
        exec(import_statement, local_ns)

        # Extract the builder function
        # The import is "from X import Y" or "from X import Y as Z"
        # We need the actual name after any 'as' clause
        parts = import_statement.strip().split()
        # parts: ["from", "module", "import", "name", "as", "alias"] or ["from", "module", "import", "name"]
        if len(parts) >= 6 and parts[4] == "as":
            imported_name = parts[5]
        else:
            imported_name = parts[3]

        builder_fn = local_ns.get(imported_name) or local_ns.get(builder_name)
        assert builder_fn is not None, (
            f"{runner['_scenario_id']}/{runner['subpipeline']}: "
            f"could not find builder '{imported_name}' after import"
        )

        # Build the pipeline — some builders accept kwargs, some don't.
        # We try to call the builder with reasonable defaults.
        pipeline = _call_builder(builder_fn, runner["subpipeline"])
        native = getattr(pipeline, "native_program", None)
        assert native is not None, (
            f"{runner['_scenario_id']}/{runner['subpipeline']}: "
            f"native_program is None"
        )

    def test_runner_identifiers_are_well_formed(self) -> None:
        """Each runner entry has a non-empty subpipeline and test_function."""
        manifest = _load_manifest()
        for scenario in manifest["scenarios"]["committed"]:
            for runner in scenario["deterministic_runners"]:
                assert runner["subpipeline"], (
                    f"{scenario['scenario_id']}: subpipeline must be non-empty"
                )
                assert runner["test_function"], (
                    f"{scenario['scenario_id']}/{runner['subpipeline']}: "
                    f"test_function must be non-empty"
                )


def _call_builder(builder_fn, subpipeline: str):
    """Call a builder with appropriate args for the subpipeline type."""
    simple_builders = {
        "deliberation", "creative", "doc", "jokes",
        "select_tournament", "writing_panel_strict", "live_supervisor",
        "folder_audit",
    }
    if subpipeline in simple_builders:
        try:
            # Try no-arg first
            return builder_fn()
        except TypeError:
            pass
        # Try with common kwargs
        if subpipeline == "creative":
            return builder_fn(form="joke")
        elif subpipeline == "jokes":
            return builder_fn(topic="test")
        elif subpipeline == "select_tournament":
            return builder_fn(candidates=("a", "b", "c"))
        elif subpipeline == "folder_audit":
            return builder_fn(worker=lambda **kw: "{}")
    # Fallback: try no-arg
    return builder_fn()


# ── live native trace comparison ───────────────────────────────────────────


class TestNativeGoldenComparison:
    """Exercise compare_native_golden_dir with synthetic trace directories."""

    @staticmethod
    def _make_trace_dir(base: Path, *, mutate: dict | None = None) -> Path:
        """Create a minimal native trace directory with all five canonical files."""
        trace = base / "trace"
        trace.mkdir(parents=True, exist_ok=True)
        payloads: dict = {
            "events.ndjson": [
                {"kind": "pipeline.init", "step": ""},
                {"kind": "phase.start", "step": "prep"},
                {"kind": "phase.end", "step": "prep"},
                {"kind": "stage.complete", "step": "prep"},
                {"kind": "checkpoint", "step": ""},
            ],
            "state.json": {"status": "ok", "stage": "prep"},
            "stages.json": ["prep"],
            "artifacts.json": {"prep/v1.md": "sha256:abcdef"},
            "checkpoint.json": {"status": "done"},
        }
        if mutate:
            for filename, value in mutate.items():
                payloads[filename] = value

        for filename in TRACE_FILE_NAMES:
            value = payloads[filename]
            if filename == "events.ndjson":
                content = "\n".join(
                    json.dumps(item, sort_keys=True) for item in value
                ) + "\n"
            else:
                content = _canonical_json(value)
            (trace / filename).write_text(content, encoding="utf-8")
        return trace

    def test_identical_dirs_match(self, tmp_path: Path) -> None:
        golden = self._make_trace_dir(tmp_path / "golden")
        actual = self._make_trace_dir(tmp_path / "actual")
        ok, msg = compare_native_golden_dir(golden, actual)
        assert ok, f"Identical dirs should match: {msg}"

    def test_missing_golden_dir_reports_failure(self, tmp_path: Path) -> None:
        ok, msg = compare_native_golden_dir(
            tmp_path / "nonexistent-golden",
            tmp_path / "actual",
        )
        assert not ok
        assert "does not exist" in msg

    def test_missing_actual_dir_reports_failure(self, tmp_path: Path) -> None:
        golden = self._make_trace_dir(tmp_path / "golden")
        ok, msg = compare_native_golden_dir(
            golden,
            tmp_path / "nonexistent-actual",
        )
        assert not ok
        assert "does not exist" in msg

    def test_missing_file_in_golden_reports_failure(self, tmp_path: Path) -> None:
        golden = self._make_trace_dir(tmp_path / "golden")
        actual = self._make_trace_dir(tmp_path / "actual")
        (golden / "artifacts.json").unlink()
        ok, msg = compare_native_golden_dir(golden, actual)
        assert not ok
        assert "Missing golden file: artifacts.json" in msg

    def test_missing_file_in_actual_reports_failure(self, tmp_path: Path) -> None:
        golden = self._make_trace_dir(tmp_path / "golden")
        actual = self._make_trace_dir(tmp_path / "actual")
        (actual / "checkpoint.json").unlink()
        ok, msg = compare_native_golden_dir(golden, actual)
        assert not ok
        assert "Missing actual file: checkpoint.json" in msg

    def test_state_difference_reported(self, tmp_path: Path) -> None:
        golden = self._make_trace_dir(tmp_path / "golden")
        actual = self._make_trace_dir(
            tmp_path / "actual",
            mutate={"state.json": {"status": "changed"}},
        )
        ok, msg = compare_native_golden_dir(golden, actual)
        assert not ok
        assert "state.json differs" in msg

    def test_events_ndjson_difference_reported(self, tmp_path: Path) -> None:
        golden = self._make_trace_dir(tmp_path / "golden")
        actual = self._make_trace_dir(
            tmp_path / "actual",
            mutate={"events.ndjson": [
                {"kind": "pipeline.init"},
                {"kind": "phase.start", "step": "different"},
            ]},
        )
        ok, msg = compare_native_golden_dir(golden, actual)
        assert not ok
        assert "events.ndjson differs" in msg

    def test_events_ndjson_normalization_ignores_nondeterministic_fields(self, tmp_path: Path) -> None:
        """seq, ts_utc, ts_rel_init_s are stripped before comparison."""
        golden = self._make_trace_dir(tmp_path / "golden")
        actual = self._make_trace_dir(
            tmp_path / "actual",
            mutate={"events.ndjson": [
                {"kind": "pipeline.init", "step": "", "seq": 1, "ts_utc": "2025-01-01T00:00:00Z", "ts_rel_init_s": 0.001},
                {"kind": "phase.start", "step": "prep", "seq": 2, "ts_utc": "2025-01-01T00:00:01Z", "ts_rel_init_s": 0.002},
                {"kind": "phase.end", "step": "prep", "seq": 3},
                {"kind": "stage.complete", "step": "prep", "seq": 4},
                {"kind": "checkpoint", "step": "", "seq": 5, "ts_utc": "2025-01-01T00:00:02Z", "ts_rel_init_s": 0.003},
            ]},
        )
        ok, msg = compare_native_golden_dir(golden, actual)
        assert ok, f"Normalized events should match: {msg}"

    def test_record_native_golden_dir_copies_all_files(self, tmp_path: Path) -> None:
        source = self._make_trace_dir(tmp_path / "source")
        target = tmp_path / "recorded"
        record_native_golden_dir(source, target)
        for filename in TRACE_FILE_NAMES:
            assert (target / filename).is_file(), f"Missing {filename}"

    def test_record_native_golden_dir_refuses_overwrite_without_flag(self, tmp_path: Path) -> None:
        source = self._make_trace_dir(tmp_path / "source")
        target = tmp_path / "recorded"
        target.mkdir()
        (target / "events.ndjson").write_text("{}", encoding="utf-8")
        with pytest.raises(FileExistsError):
            record_native_golden_dir(source, target)

    def test_record_native_golden_dir_overwrites_with_flag(self, tmp_path: Path) -> None:
        source = self._make_trace_dir(tmp_path / "source")
        target = tmp_path / "recorded"
        target.mkdir()
        (target / "events.ndjson").write_text("old", encoding="utf-8")
        record_native_golden_dir(source, target, overwrite=True)
        # Should now have the source content
        assert (target / "events.ndjson").is_file()
        content = (target / "events.ndjson").read_text(encoding="utf-8")
        assert "pipeline.init" in content

    def test_compare_normalizes_json_key_ordering(self, tmp_path: Path) -> None:
        """state.json with different key ordering should still match."""
        golden_dir = tmp_path / "golden"
        actual_dir = tmp_path / "actual"
        golden_dir.mkdir()
        actual_dir.mkdir()

        # Write events that match
        events = '{"kind":"start","step":"prep"}\n'
        for d in (golden_dir, actual_dir):
            (d / "events.ndjson").write_text(events, encoding="utf-8")

        # Write state.json with different key ordering
        (golden_dir / "state.json").write_text(
            '{"status":"ok","stage":"prep"}', encoding="utf-8"
        )
        (actual_dir / "state.json").write_text(
            '{"stage":"prep","status":"ok"}', encoding="utf-8"
        )

        # Write remaining files identically
        for filename in ("stages.json", "artifacts.json", "checkpoint.json"):
            for d in (golden_dir, actual_dir):
                (d / filename).write_text('{"dummy":true}', encoding="utf-8")

        ok, msg = compare_native_golden_dir(golden_dir, actual_dir)
        assert ok, f"JSON key reordering should not cause mismatch: {msg}"


# ── record-mode explanation guarding ───────────────────────────────────────


class TestRecordModeExplanationGuarding:
    """Verify directory_is_explained enforces .explanation.md sidecar for changes."""

    @staticmethod
    def _make_trace_dir(base: Path, **file_contents: str) -> Path:
        base.mkdir(parents=True, exist_ok=True)
        for filename in TRACE_FILE_NAMES:
            content = file_contents.get(filename, "{}")
            (base / filename).write_text(content, encoding="utf-8")
        return base

    def test_unchanged_directory_is_explained_without_sidecar(self, tmp_path: Path) -> None:
        old = self._make_trace_dir(tmp_path / "old")
        new = self._make_trace_dir(tmp_path / "new")
        rule = GoldenRegressionRule(
            tmp_path / "native",
            tmp_path / "native.explanation.md",
        )
        assert rule.directory_is_explained(old_directory=old, new_directory=new) is True

    def test_changed_directory_is_not_explained_without_sidecar(self, tmp_path: Path) -> None:
        old = self._make_trace_dir(tmp_path / "old", **{"state.json": '{"status":"ok"}'})
        new = self._make_trace_dir(tmp_path / "new", **{"state.json": '{"status":"changed"}'})
        rule = GoldenRegressionRule(
            tmp_path / "native",
            tmp_path / "native.explanation.md",
        )
        assert rule.directory_is_explained(old_directory=old, new_directory=new) is False

    def test_changed_directory_is_explained_with_nonempty_sidecar(self, tmp_path: Path) -> None:
        explanation = tmp_path / "native.explanation.md"
        explanation.write_text("Rebaseline approved: state shape changed.\n", encoding="utf-8")
        old = self._make_trace_dir(tmp_path / "old", **{"state.json": '{"status":"ok"}'})
        new = self._make_trace_dir(tmp_path / "new", **{"state.json": '{"status":"changed"}'})
        rule = GoldenRegressionRule(tmp_path / "native", explanation)
        assert rule.directory_is_explained(old_directory=old, new_directory=new) is True

    def test_changed_directory_is_not_explained_with_empty_sidecar(self, tmp_path: Path) -> None:
        explanation = tmp_path / "native.explanation.md"
        explanation.write_text("", encoding="utf-8")
        old = self._make_trace_dir(tmp_path / "old", **{"state.json": '{"status":"ok"}'})
        new = self._make_trace_dir(tmp_path / "new", **{"state.json": '{"status":"changed"}'})
        rule = GoldenRegressionRule(tmp_path / "native", explanation)
        assert rule.directory_is_explained(old_directory=old, new_directory=new) is False

    def test_directory_digest_is_stable_and_deterministic(self, tmp_path: Path) -> None:
        a = self._make_trace_dir(tmp_path / "a")
        b = self._make_trace_dir(tmp_path / "b")
        rule = GoldenRegressionRule(
            tmp_path / "native",
            tmp_path / "native.explanation.md",
        )
        digest_a = rule.directory_digest(a)
        digest_b = rule.directory_digest(b)
        assert digest_a == digest_b, "Identical dirs should produce same digest"
        assert len(digest_a) == 64, "SHA-256 produces 64 hex chars"

    def test_directory_digest_differs_when_file_contents_change(self, tmp_path: Path) -> None:
        a = self._make_trace_dir(tmp_path / "a", **{"state.json": '{"status":"ok"}'})
        b = self._make_trace_dir(tmp_path / "b", **{"state.json": '{"status":"changed"}'})
        rule = GoldenRegressionRule(
            tmp_path / "native",
            tmp_path / "native.explanation.md",
        )
        assert rule.directory_digest(a) != rule.directory_digest(b)

    def test_directory_digest_differs_when_files_are_added(self, tmp_path: Path) -> None:
        a = self._make_trace_dir(tmp_path / "a")
        b = self._make_trace_dir(tmp_path / "b")
        (b / "extra.txt").write_text("bonus", encoding="utf-8")
        rule = GoldenRegressionRule(
            tmp_path / "native",
            tmp_path / "native.explanation.md",
        )
        assert rule.directory_digest(a) != rule.directory_digest(b)
