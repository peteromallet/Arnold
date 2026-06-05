"""Canonical review module import checks."""

from __future__ import annotations

import importlib

import pytest


# ── canonical symbol exports ─────────────────────────────────────────────

@pytest.mark.parametrize(
    ("canonical_module", "symbol"),
    [
        (
            "arnold.pipelines.megaplan.review.checks",
            "ReviewCheckSpec",
        ),
        (
            "arnold.pipelines.megaplan.review.checks",
            "REVIEW_CHECKS",
        ),
        (
            "arnold.pipelines.megaplan.review.checks",
            "get_check_by_id",
        ),
        (
            "arnold.pipelines.megaplan.review.checks",
            "validate_review_checks",
        ),
        (
            "arnold.pipelines.megaplan.review.mechanical",
            "run_pre_checks",
        ),
        (
            "arnold.pipelines.megaplan.review.mechanical",
            "_is_diff_noise",
        ),
        (
            "arnold.pipelines.megaplan.review.parallel",
            "run_parallel_review",
        ),
    ],
)
def test_canonical_review_symbols_exist(
    canonical_module: str,
    symbol: str,
) -> None:
    """Canonical arnold.pipelines.megaplan.review.* module attributes resolve."""
    canonical = importlib.import_module(canonical_module)
    assert hasattr(canonical, symbol)


# ── module identity ─────────────────────────────────────────────────────

def test_canonical_parallel_importable() -> None:
    canonical = importlib.import_module(
        "arnold.pipelines.megaplan.review.parallel"
    )
    assert canonical.__name__ == "arnold.pipelines.megaplan.review.parallel"


# ── explicitly imported private helpers ──────────────────────────────────

def test_canonical_mechanical_exports_is_diff_noise() -> None:
    canonical = importlib.import_module(
        "arnold.pipelines.megaplan.review.mechanical"
    )
    assert callable(canonical._is_diff_noise)


# ── monkeypatch surface ──────────────────────────────────────────────────

def test_canonical_parallel_monkeypatch_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical = importlib.import_module(
        "arnold.pipelines.megaplan.review.parallel"
    )

    sentinel = object()
    monkeypatch.setattr(canonical, "_resolve_model", sentinel)
    assert canonical._resolve_model is sentinel, (
        "Monkeypatch on canonical review.parallel did not stick"
    )


def test_canonical_parallel_monkeypatch_readable_from_canonical_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical = importlib.import_module(
        "arnold.pipelines.megaplan.review.parallel"
    )

    sentinel = object()
    monkeypatch.setattr(canonical, "_resolve_model", sentinel)

    from arnold.pipelines.megaplan.review.parallel import _resolve_model

    assert _resolve_model is sentinel, (
        "Monkeypatch on canonical review.parallel must be visible to importers"
    )
