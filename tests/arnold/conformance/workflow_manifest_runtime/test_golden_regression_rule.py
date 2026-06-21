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
