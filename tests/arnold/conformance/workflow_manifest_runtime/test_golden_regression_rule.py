from __future__ import annotations

from pathlib import Path

from arnold.conformance.workflow_manifest_runtime import GoldenRegressionRule


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
    import json

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
