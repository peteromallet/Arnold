from __future__ import annotations

import json
from pathlib import Path

from arnold.conformance.workflow_manifest_runtime import GoldenRegressionRule
from tests.arnold_pipelines.megaplan.fixtures.native_goldens import TRACE_FILE_NAMES


def test_golden_regression_rule_accepts_unchanged_fixture(tmp_path: Path) -> None:
    rule = GoldenRegressionRule(tmp_path / "fresh.json", tmp_path / "fresh.explanation.md")

    assert rule.is_explained(old_text="{}", new_text="{}") is True


def test_golden_regression_rule_rejects_unexplained_fixture_change(tmp_path: Path) -> None:
    rule = GoldenRegressionRule(tmp_path / "fresh.json", tmp_path / "fresh.explanation.md")

    assert rule.is_explained(old_text="{}", new_text='{"changed": true}') is False


def test_golden_regression_rule_accepts_explained_fixture_change(tmp_path: Path) -> None:
    explanation = tmp_path / "fresh.explanation.md"
    explanation.write_text("Behavior changed because the product route changed.\n", encoding="utf-8")
    rule = GoldenRegressionRule(tmp_path / "fresh.json", explanation)

    assert rule.is_explained(old_text="{}", new_text='{"changed": true}') is True


def test_tiebreaker_fixture_is_guarded_by_regression_rule() -> None:
    fixture_path = Path("tests/fixtures/golden/workflow_manifest_runtime/tiebreaker.json")
    explanation_path = fixture_path.with_suffix(fixture_path.suffix + ".explanation.md")
    rule = GoldenRegressionRule(fixture_path, explanation_path)

    current = fixture_path.read_text(encoding="utf-8")
    assert rule.is_explained(old_text=current, new_text=current) is True
    assert rule.is_explained(old_text=current, new_text='{"changed": true}') is False


def test_canonical_megaplan_fixture_is_guarded_by_regression_rule() -> None:
    fixture_path = Path("tests/fixtures/golden/workflow_manifest_runtime/canonical_megaplan.json")
    explanation_path = fixture_path.with_suffix(fixture_path.suffix + ".explanation.md")
    rule = GoldenRegressionRule(fixture_path, explanation_path)

    current = fixture_path.read_text(encoding="utf-8")
    assert rule.is_explained(old_text=current, new_text=current) is True
    assert rule.is_explained(old_text=current, new_text='{"changed": true}') is False


def test_canonical_megaplan_fixture_matches_compiled_manifest() -> None:
    from arnold.workflow import compile_pipeline

    from tests.arnold.workflow.test_canonical_megaplan_conformance import (
        _build_pattern_blocks,
        _build_pipeline,
    )

    fixture_path = Path("tests/fixtures/golden/workflow_manifest_runtime/canonical_megaplan.json")
    expected = json.loads(fixture_path.read_text(encoding="utf-8"))

    manifest = compile_pipeline(_build_pipeline(), patterns=_build_pattern_blocks())
    payload = manifest.to_dict(include_hashes=False)

    def strip_source_spans(value):
        if isinstance(value, dict):
            return {
                key: strip_source_spans(subvalue)
                for key, subvalue in value.items()
                if key != "source_span"
            }
        if isinstance(value, list):
            return [strip_source_spans(item) for item in value]
        return value

    payload = strip_source_spans(payload)
    payload["topology_hash"] = manifest.topology_hash
    payload["manifest_hash"] = manifest.manifest_hash

    assert payload == expected


def test_golden_regression_rule_accepts_unchanged_directory_fixture(tmp_path: Path) -> None:
    fixture_path = tmp_path / "native"
    explanation_path = tmp_path / "native.explanation.md"
    rule = GoldenRegressionRule(fixture_path, explanation_path)
    old_directory = _make_native_trace_dir(tmp_path / "old")
    new_directory = _make_native_trace_dir(tmp_path / "new")

    assert rule.directory_digest(old_directory) == rule.directory_digest(new_directory)
    assert rule.directory_is_explained(
        old_directory=old_directory,
        new_directory=new_directory,
    ) is True


def test_golden_regression_rule_rejects_unexplained_directory_fixture_change(tmp_path: Path) -> None:
    fixture_path = tmp_path / "native"
    explanation_path = tmp_path / "native.explanation.md"
    rule = GoldenRegressionRule(fixture_path, explanation_path)
    old_directory = _make_native_trace_dir(tmp_path / "old")
    new_directory = _make_native_trace_dir(
        tmp_path / "new",
        mutate={"state.json": {"status": "changed"}},
    )

    assert rule.directory_is_explained(
        old_directory=old_directory,
        new_directory=new_directory,
    ) is False


def test_golden_regression_rule_accepts_explained_directory_fixture_change(tmp_path: Path) -> None:
    fixture_path = tmp_path / "native"
    explanation_path = tmp_path / "native.explanation.md"
    explanation_path.write_text("Native trace fixture intentionally changed.\n", encoding="utf-8")
    rule = GoldenRegressionRule(fixture_path, explanation_path)
    old_directory = _make_native_trace_dir(tmp_path / "old")
    new_directory = _make_native_trace_dir(
        tmp_path / "new",
        mutate={"checkpoint.json": {"status": "revised"}},
    )

    assert rule.directory_is_explained(
        old_directory=old_directory,
        new_directory=new_directory,
    ) is True


def test_native_trace_rebaseline_requires_explanation_sidecar(tmp_path: Path) -> None:
    fixture_path = tmp_path / "native"
    explanation_path = tmp_path / "native.explanation.md"
    fixture_path.mkdir()
    rule = GoldenRegressionRule(fixture_path, explanation_path)
    committed = _make_native_trace_dir(tmp_path / "committed")
    regenerated = _make_native_trace_dir(
        tmp_path / "regenerated",
        mutate={"artifacts.json": {"artifact.txt": "sha256:changed"}},
    )

    assert rule.directory_is_explained(
        old_directory=committed,
        new_directory=regenerated,
    ) is False

    explanation_path.write_text("Approved native rebaseline.\n", encoding="utf-8")

    assert rule.directory_is_explained(
        old_directory=committed,
        new_directory=regenerated,
    ) is True


def _make_native_trace_dir(
    path: Path,
    *,
    mutate: dict[str, object] | None = None,
) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    payloads: dict[str, object] = {
        "events.ndjson": [
            {"kind": "start", "step": "prep"},
            {"kind": "finish", "step": "prep"},
        ],
        "state.json": {"status": "ok"},
        "stages.json": [{"name": "prep"}],
        "artifacts.json": {"artifact.txt": "sha256:abc"},
        "checkpoint.json": {"status": "done"},
    }
    for filename, value in (mutate or {}).items():
        payloads[filename] = value

    for filename in TRACE_FILE_NAMES:
        target = path / filename
        value = payloads[filename]
        if filename == "events.ndjson":
            lines = [json.dumps(item, sort_keys=True) for item in value]
            target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            target.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return path
