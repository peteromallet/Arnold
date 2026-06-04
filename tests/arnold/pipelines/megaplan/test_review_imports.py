"""Compatibility checks for canonical review modules and legacy facades."""

from __future__ import annotations

import importlib

import pytest


# ── module identity and symbol re-export ─────────────────────────────────

@pytest.mark.parametrize(
    ("legacy_module", "canonical_module", "symbol"),
    [
        (
            "megaplan.review.checks",
            "arnold.pipelines.megaplan.review.checks",
            "ReviewCheckSpec",
        ),
        (
            "megaplan.review.checks",
            "arnold.pipelines.megaplan.review.checks",
            "REVIEW_CHECKS",
        ),
        (
            "megaplan.review.checks",
            "arnold.pipelines.megaplan.review.checks",
            "get_check_by_id",
        ),
        (
            "megaplan.review.checks",
            "arnold.pipelines.megaplan.review.checks",
            "validate_review_checks",
        ),
        (
            "megaplan.review.mechanical",
            "arnold.pipelines.megaplan.review.mechanical",
            "run_pre_checks",
        ),
        (
            "megaplan.review.mechanical",
            "arnold.pipelines.megaplan.review.mechanical",
            "_is_diff_noise",
        ),
        (
            "megaplan.review.parallel",
            "arnold.pipelines.megaplan.review.parallel",
            "run_parallel_review",
        ),
    ],
)
def test_legacy_review_symbols_reexport_canonical_symbols(
    legacy_module: str,
    canonical_module: str,
    symbol: str,
) -> None:
    """Legacy megaplan.review.* module attributes resolve to canonical objects."""
    legacy = importlib.import_module(legacy_module)
    canonical = importlib.import_module(canonical_module)
    assert getattr(legacy, symbol) is getattr(canonical, symbol), (
        f"{legacy_module}.{symbol} is not {canonical_module}.{symbol}"
    )


# ── module identity: sys.modules facade IS the canonical module ─────────

def test_legacy_parallel_is_canonical() -> None:
    """The parallel facade uses sys.modules aliasing; legacy module IS canonical."""
    legacy = importlib.import_module("megaplan.review.parallel")
    canonical = importlib.import_module(
        "arnold.pipelines.megaplan.review.parallel"
    )
    assert legacy is canonical, (
        "megaplan.review.parallel must be sys.modules-alias to canonical"
    )


# ── explicitly imported private helpers ──────────────────────────────────

def test_legacy_mechanical_explicitly_reexports_is_diff_noise() -> None:
    """mechanical facade explicitly imports _is_diff_noise for io consumer."""
    legacy = importlib.import_module("megaplan.review.mechanical")
    canonical = importlib.import_module(
        "arnold.pipelines.megaplan.review.mechanical"
    )
    # Only _is_diff_noise is explicitly imported by the facade
    assert legacy._is_diff_noise is canonical._is_diff_noise


# ── monkeypatch compatibility (sys.modules aliasing) ─────────────────────

def test_legacy_parallel_monkeypatch_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Monkeypatching megaplan.review.parallel._resolve_model must reach canonical.

    The parallel facade uses sys.modules aliasing so that tests patching
    ``megaplan.review.parallel._resolve_model`` affect the canonical
    ``arnold.pipelines.megaplan.review.parallel`` module.
    """
    legacy = importlib.import_module("megaplan.review.parallel")
    canonical = importlib.import_module(
        "arnold.pipelines.megaplan.review.parallel"
    )

    sentinel = object()
    monkeypatch.setattr(legacy, "_resolve_model", sentinel)
    assert canonical._resolve_model is sentinel, (
        "Monkeypatch on megaplan.review.parallel did not reach canonical module"
    )


def test_legacy_parallel_monkeypatch_readable_from_legacy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Existing tests patch megaplan.review.parallel._resolve_model and it works."""
    legacy = importlib.import_module("megaplan.review.parallel")

    sentinel = object()
    monkeypatch.setattr(legacy, "_resolve_model", sentinel)

    # Re-import through the legacy path should see the patched value
    from megaplan.review.parallel import _resolve_model

    assert _resolve_model is sentinel, (
        "Monkeypatch on megaplan.review.parallel must be visible to importers"
    )
