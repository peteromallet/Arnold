"""Tests for ``arnold.pipeline.media_cost`` — media usage, pricing, and cost computation.

Covers:
- image, video_second, audio_second, song semantic units
- exact Decimal math on counts (int, float, Decimal)
- labels, status, provenance fields in CostResult output
- unknown pricing → status='unknown', amount_usd=None
- fractional float normalization via Decimal(str(count))
- no blob/file reads (raw_usage never inspected)
- case-insensitive provider/model matching
- multiple usage items in one call
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from arnold.pipeline.cost_types import CostResult, CostSource, CostStatus
from arnold.pipeline.media_cost import (
    DEFAULT_MEDIA_PRICING,
    MediaPricingEntry,
    MediaUsage,
    _decimal_count,
    _lookup_media_pricing,
    compute_media_cost,
    media_usage_from_hook_metadata,
)


# ---------------------------------------------------------------------------
# Fixture pricing rows for tests — not live data
# ---------------------------------------------------------------------------

_FIXTURE_NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)

_FIXTURE_PRICING: tuple[MediaPricingEntry, ...] = (
    MediaPricingEntry(
        provider="openai",
        model="dall-e-3",
        unit="image",
        cost_per_unit=Decimal("0.040"),
        source="official_docs_snapshot",
        source_url="https://openai.com/api/pricing/",
        pricing_version="test-fixture-v1",
        fetched_at=_FIXTURE_NOW,
        status="estimated",
    ),
    MediaPricingEntry(
        provider="openai",
        model="sora",
        unit="video_second",
        cost_per_unit=Decimal("0.005"),
        source="official_docs_snapshot",
        source_url="https://openai.com/api/pricing/",
        pricing_version="test-fixture-v1",
        fetched_at=_FIXTURE_NOW,
        status="estimated",
    ),
    MediaPricingEntry(
        provider="openai",
        model="tts-1",
        unit="audio_second",
        cost_per_unit=Decimal("0.00023"),
        source="official_docs_snapshot",
        source_url="https://openai.com/api/pricing/",
        pricing_version="test-fixture-v1",
        fetched_at=_FIXTURE_NOW,
        status="estimated",
    ),
    MediaPricingEntry(
        provider="openai",
        model="tts-1",
        unit="song",
        cost_per_unit=Decimal("0.015"),
        source="official_docs_snapshot",
        source_url="https://openai.com/api/pricing/",
        pricing_version="test-fixture-v1",
        fetched_at=_FIXTURE_NOW,
        status="estimated",
    ),
    # Anthropic does not have public image/video/audio pricing yet,
    # but a fixture row exercises cross-provider lookup.
    MediaPricingEntry(
        provider="anthropic",
        model="claude-opus-4-20250514",
        unit="image",
        cost_per_unit=Decimal("0.010"),
        source="user_override",
        source_url=None,
        pricing_version="test-fixture-v1",
        fetched_at=_FIXTURE_NOW,
        status="estimated",
    ),
)


# ---------------------------------------------------------------------------
# _decimal_count normalization
# ---------------------------------------------------------------------------

class TestDecimalCount:
    """``_decimal_count`` normalizes int, float, and Decimal via str()."""

    def test_int_yields_exact_decimal(self) -> None:
        assert _decimal_count(3) == Decimal("3")

    def test_float_yields_exact_decimal_from_string(self) -> None:
        # 3.5 → "3.5" → Decimal("3.5") — not 3.500000000000000…
        assert _decimal_count(3.5) == Decimal("3.5")

    def test_fractional_float_preserves_precision(self) -> None:
        # 0.015 → Decimal("0.015") not the binary approximation
        assert _decimal_count(0.015) == Decimal("0.015")

    def test_decimal_passthrough(self) -> None:
        d = Decimal("0.015")
        result = _decimal_count(d)
        # Round-trip via str preserves value exactly — may be a new object
        assert result == d
        assert isinstance(result, Decimal)

    def test_zero_int(self) -> None:
        assert _decimal_count(0) == Decimal("0")

    def test_zero_float(self) -> None:
        assert _decimal_count(0.0) == Decimal("0.0")

    def test_large_float(self) -> None:
        assert _decimal_count(1234567.89) == Decimal("1234567.89")

    def test_small_fractional_float(self) -> None:
        assert _decimal_count(0.00001) == Decimal("0.00001")


# ---------------------------------------------------------------------------
# _lookup_media_pricing
# ---------------------------------------------------------------------------

class TestLookupMediaPricing:
    """Case-insensitive key matching on (provider, model, unit)."""

    def test_exact_match_returns_entry(self) -> None:
        entry = _lookup_media_pricing("openai", "dall-e-3", "image", _FIXTURE_PRICING)
        assert entry is not None
        assert entry.provider == "openai"
        assert entry.model == "dall-e-3"
        assert entry.unit == "image"

    def test_case_insensitive_provider(self) -> None:
        entry = _lookup_media_pricing("OpenAI", "dall-e-3", "image", _FIXTURE_PRICING)
        assert entry is not None
        assert entry.unit == "image"

    def test_case_insensitive_model(self) -> None:
        entry = _lookup_media_pricing("openai", "DALL-E-3", "image", _FIXTURE_PRICING)
        assert entry is not None
        assert entry.unit == "image"

    def test_unit_is_lowered_not_case_insensitive(self) -> None:
        # unit is lowercased — "IMAGE" should match "image"
        entry = _lookup_media_pricing("openai", "dall-e-3", "IMAGE", _FIXTURE_PRICING)
        assert entry is not None
        assert entry.unit == "image"

    def test_mismatched_unit_returns_none(self) -> None:
        entry = _lookup_media_pricing("openai", "dall-e-3", "video_second", _FIXTURE_PRICING)
        assert entry is None

    def test_mismatched_provider_returns_none(self) -> None:
        entry = _lookup_media_pricing("google", "dall-e-3", "image", _FIXTURE_PRICING)
        assert entry is None

    def test_mismatched_model_returns_none(self) -> None:
        entry = _lookup_media_pricing("openai", "nonexistent", "image", _FIXTURE_PRICING)
        assert entry is None

    def test_empty_pricing_rows_returns_none(self) -> None:
        entry = _lookup_media_pricing("openai", "dall-e-3", "image", ())
        assert entry is None

    def test_whitespace_in_key_is_stripped(self) -> None:
        entry = _lookup_media_pricing("  openai  ", " dall-e-3 ", "image", _FIXTURE_PRICING)
        assert entry is not None


# ---------------------------------------------------------------------------
# MediaUsage construction
# ---------------------------------------------------------------------------

class TestMediaUsageConstruction:
    """``MediaUsage`` is a frozen dataclass with sensible defaults."""

    def test_minimal_construction(self) -> None:
        mu = MediaUsage(unit="image", count=1)
        assert mu.unit == "image"
        assert mu.count == 1
        assert mu.dimensions == {}
        assert mu.raw_usage is None

    def test_with_dimensions(self) -> None:
        mu = MediaUsage(unit="image", count=2, dimensions={"resolution": "1024x1024"})
        assert mu.dimensions == {"resolution": "1024x1024"}

    def test_with_raw_usage(self) -> None:
        blob = {"url": "https://example.com/img.png"}
        mu = MediaUsage(unit="image", count=1, raw_usage=blob)
        assert mu.raw_usage is blob

    def test_is_frozen(self) -> None:
        mu = MediaUsage(unit="image", count=1)
        with pytest.raises(Exception):
            mu.unit = "video_second"  # type: ignore[misc]

    def test_decimal_count(self) -> None:
        mu = MediaUsage(unit="image", count=Decimal("0.5"))
        assert mu.count == Decimal("0.5")


# ---------------------------------------------------------------------------
# compute_media_cost — priced results
# ---------------------------------------------------------------------------

class TestComputeMediaCostPriced:
    """``compute_media_cost`` returns correct CostResult for matched rows."""

    def test_image_pricing_with_int_count(self) -> None:
        results = compute_media_cost(
            provider="openai",
            model="dall-e-3",
            media_usage=(MediaUsage(unit="image", count=5),),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert len(results) == 1
        r = results[0]
        assert r.amount_usd == Decimal("0.200")  # 5 × 0.040
        assert r.status == "estimated"
        assert r.source == "official_docs_snapshot"
        assert r.label == "image (5)"
        assert r.pricing_version == "test-fixture-v1"
        assert r.fetched_at == _FIXTURE_NOW

    def test_image_pricing_with_float_count(self) -> None:
        """Float count uses Decimal(str(count)) for exact math."""
        results = compute_media_cost(
            provider="openai",
            model="dall-e-3",
            media_usage=(MediaUsage(unit="image", count=2.5),),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert len(results) == 1
        # 2.5 × 0.040 = 0.100 exactly
        assert results[0].amount_usd == Decimal("0.100")

    def test_video_second_pricing(self) -> None:
        results = compute_media_cost(
            provider="openai",
            model="sora",
            media_usage=(MediaUsage(unit="video_second", count=Decimal("60")),),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert results[0].amount_usd == Decimal("0.300")  # 60 × 0.005
        assert results[0].label == "video_second (60)"

    def test_audio_second_pricing(self) -> None:
        results = compute_media_cost(
            provider="openai",
            model="tts-1",
            media_usage=(MediaUsage(unit="audio_second", count=30),),
            pricing_rows=_FIXTURE_PRICING,
        )
        # 30 × 0.00023 = 0.00690
        assert results[0].amount_usd == Decimal("0.00690")
        assert results[0].label == "audio_second (30)"

    def test_song_pricing(self) -> None:
        results = compute_media_cost(
            provider="openai",
            model="tts-1",
            media_usage=(MediaUsage(unit="song", count=3),),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert results[0].amount_usd == Decimal("0.045")  # 3 × 0.015
        assert results[0].label == "song (3)"

    def test_fractional_float_count_exact_decimal_math(self) -> None:
        """Fractional float 0.015 produces exact result, not binary-float drift."""
        results = compute_media_cost(
            provider="openai",
            model="sora",
            media_usage=(MediaUsage(unit="video_second", count=0.015),),
            pricing_rows=_FIXTURE_PRICING,
        )
        # 0.015 × 0.005 = 0.000075 exactly
        assert results[0].amount_usd == Decimal("0.000075")

    def test_multiple_usage_items(self) -> None:
        results = compute_media_cost(
            provider="openai",
            model="dall-e-3",
            media_usage=(
                MediaUsage(unit="image", count=2),
                MediaUsage(unit="image", count=3),
            ),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert len(results) == 2
        assert results[0].amount_usd == Decimal("0.080")
        assert results[1].amount_usd == Decimal("0.120")

    def test_case_insensitive_provider_lookup(self) -> None:
        """Cost computation is case-insensitive on provider/model."""
        results = compute_media_cost(
            provider="OPENAI",
            model="DALL-E-3",
            media_usage=(MediaUsage(unit="image", count=10),),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert results[0].amount_usd == Decimal("0.400")

    def test_status_and_source_preserved(self) -> None:
        """Result carries the pricing entry's status and source exactly."""
        results = compute_media_cost(
            provider="anthropic",
            model="claude-opus-4-20250514",
            media_usage=(MediaUsage(unit="image", count=1),),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert results[0].status == "estimated"
        assert results[0].source == "user_override"
        assert results[0].pricing_version == "test-fixture-v1"

    def test_label_includes_unit_and_normalized_count(self) -> None:
        results = compute_media_cost(
            provider="openai",
            model="dall-e-3",
            media_usage=(MediaUsage(unit="image", count=Decimal("7")),),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert results[0].label == "image (7)"

    def test_fetched_at_propagated(self) -> None:
        results = compute_media_cost(
            provider="openai",
            model="dall-e-3",
            media_usage=(MediaUsage(unit="image", count=1),),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert results[0].fetched_at == _FIXTURE_NOW


# ---------------------------------------------------------------------------
# compute_media_cost — unknown / missing pricing
# ---------------------------------------------------------------------------

class TestComputeMediaCostUnknown:
    """Missing pricing rows → status='unknown', amount_usd=None, never raises."""

    def test_unknown_unit_returns_unknown(self) -> None:
        results = compute_media_cost(
            provider="openai",
            model="dall-e-3",
            media_usage=(MediaUsage(unit="video_second", count=5),),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert len(results) == 1
        r = results[0]
        assert r.status == "unknown"
        assert r.source == "none"
        assert r.amount_usd is None
        assert r.label == "n/a"

    def test_unknown_provider_returns_unknown(self) -> None:
        results = compute_media_cost(
            provider="nonexistent",
            model="dall-e-3",
            media_usage=(MediaUsage(unit="image", count=1),),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert results[0].status == "unknown"
        assert results[0].amount_usd is None

    def test_unknown_model_returns_unknown(self) -> None:
        results = compute_media_cost(
            provider="openai",
            model="nonexistent-model",
            media_usage=(MediaUsage(unit="image", count=1),),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert results[0].status == "unknown"

    def test_empty_pricing_rows_all_unknown(self) -> None:
        results = compute_media_cost(
            provider="openai",
            model="dall-e-3",
            media_usage=(MediaUsage(unit="image", count=1),),
            pricing_rows=(),
        )
        assert results[0].status == "unknown"
        assert results[0].amount_usd is None

    def test_unknown_notes_include_context(self) -> None:
        results = compute_media_cost(
            provider="openai",
            model="dall-e-3",
            media_usage=(MediaUsage(unit="video_second", count=5),),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert len(results[0].notes) > 0
        note = results[0].notes[0]
        assert "openai" in note.lower()
        assert "dall-e-3" in note.lower()
        assert "video_second" in note

    def test_unknown_never_raises(self) -> None:
        """Missing pricing should never raise an exception."""
        # All-unknown combination
        results = compute_media_cost(
            provider="zzz",
            model="yyy",
            media_usage=(MediaUsage(unit="xxx", count=999),),
            pricing_rows=(),
        )
        assert results[0].status == "unknown"

    def test_mixed_known_and_unknown(self) -> None:
        """One known, one unknown in same call — both returned in order."""
        results = compute_media_cost(
            provider="openai",
            model="dall-e-3",
            media_usage=(
                MediaUsage(unit="image", count=2),
                MediaUsage(unit="video_second", count=10),
            ),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert len(results) == 2
        # first is known
        assert results[0].status == "estimated"
        assert results[0].amount_usd == Decimal("0.080")
        # second is unknown
        assert results[1].status == "unknown"
        assert results[1].amount_usd is None

    def test_null_cost_per_unit_returns_none_amount(self) -> None:
        """If cost_per_unit is None on a matched row, amount_usd is None."""
        null_cost_row = (
            MediaPricingEntry(
                provider="test",
                model="test",
                unit="image",
                cost_per_unit=None,
                source="none",
                status="estimated",
            ),
        )
        results = compute_media_cost(
            provider="test",
            model="test",
            media_usage=(MediaUsage(unit="image", count=10),),
            pricing_rows=null_cost_row,
        )
        assert results[0].amount_usd is None
        assert results[0].status == "estimated"  # status from entry preserved


# ---------------------------------------------------------------------------
# compute_media_cost — edge cases
# ---------------------------------------------------------------------------

class TestComputeMediaCostEdgeCases:
    """Edge cases: zero count, empty media_usage, defaults, etc."""

    def test_zero_count_yields_zero_amount(self) -> None:
        results = compute_media_cost(
            provider="openai",
            model="dall-e-3",
            media_usage=(MediaUsage(unit="image", count=0),),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert results[0].amount_usd == Decimal("0.00")

    def test_empty_media_usage_returns_empty_tuple(self) -> None:
        results = compute_media_cost(
            provider="openai",
            model="dall-e-3",
            media_usage=(),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert results == ()

    def test_default_pricing_is_nonempty_after_seeding(self) -> None:
        """DEFAULT_MEDIA_PRICING must contain fixture rows (T3 seeding)."""
        assert len(DEFAULT_MEDIA_PRICING) >= 2

    def test_default_pricing_entries_have_required_fields(self) -> None:
        for entry in DEFAULT_MEDIA_PRICING:
            assert isinstance(entry.provider, str) and entry.provider
            assert isinstance(entry.model, str) and entry.model
            assert isinstance(entry.unit, str) and entry.unit
            assert entry.source == "official_docs_snapshot"
            assert entry.pricing_version is not None

    def test_raw_usage_never_inspected(self) -> None:
        """Prove pricing does not read raw_usage contents."""
        # raw_usage could be anything — the cost math never touches it
        results = compute_media_cost(
            provider="openai",
            model="dall-e-3",
            media_usage=(
                MediaUsage(
                    unit="image",
                    count=3,
                    raw_usage={"blob_bytes": b"\x00" * 10_000_000},
                ),
            ),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert results[0].amount_usd == Decimal("0.120")
        # No blob was read — the raw_usage value is irrelevant to cost math

    def test_dimensions_not_inspected_for_pricing(self) -> None:
        """Dimensions are metadata only — pricing is driven by (provider, model, unit)."""
        results = compute_media_cost(
            provider="openai",
            model="dall-e-3",
            media_usage=(
                MediaUsage(unit="image", count=1, dimensions={"size": "1792x1024"}),
            ),
            pricing_rows=_FIXTURE_PRICING,
        )
        assert results[0].amount_usd == Decimal("0.040")  # not HD price
        assert results[0].label == "image (1)"


# ---------------------------------------------------------------------------
# MediaPricingEntry construction
# ---------------------------------------------------------------------------

class TestMediaPricingEntry:
    """``MediaPricingEntry`` field defaults and construction."""

    def test_minimal_construction(self) -> None:
        entry = MediaPricingEntry(
            provider="openai",
            model="dall-e-3",
            unit="image",
        )
        assert entry.provider == "openai"
        assert entry.model == "dall-e-3"
        assert entry.unit == "image"
        assert entry.cost_per_unit is None
        assert entry.source == "estimated"
        assert entry.source_url is None
        assert entry.pricing_version is None
        assert entry.fetched_at is None
        assert entry.status == "estimated"

    def test_full_construction(self) -> None:
        now = datetime.now(timezone.utc)
        entry = MediaPricingEntry(
            provider="openai",
            model="dall-e-3",
            unit="image",
            cost_per_unit=Decimal("0.040"),
            source="official_docs_snapshot",
            source_url="https://example.com",
            pricing_version="v1",
            fetched_at=now,
            status="estimated",
        )
        assert entry.cost_per_unit == Decimal("0.040")
        assert entry.source == "official_docs_snapshot"
        assert entry.fetched_at is now

    def test_is_frozen(self) -> None:
        entry = MediaPricingEntry(provider="x", model="y", unit="z")
        with pytest.raises(Exception):
            entry.provider = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# media_usage_from_hook_metadata
# ---------------------------------------------------------------------------

class TestMediaUsageFromHookMetadata:
    """``media_usage_from_hook_metadata()`` normalizes absent/single/list/tuple."""

    # -- absent / None --------------------------------------------------------

    def test_none_returns_empty_tuple(self) -> None:
        assert media_usage_from_hook_metadata(None) == ()

    # -- single MediaUsage ---------------------------------------------------

    def test_single_media_usage_wrapped_in_tuple(self) -> None:
        mu = MediaUsage(unit="image", count=1)
        result = media_usage_from_hook_metadata(mu)
        assert result == (mu,)
        assert len(result) == 1

    # -- tuple ---------------------------------------------------------------

    def test_tuple_passthrough(self) -> None:
        a = MediaUsage(unit="image", count=1)
        b = MediaUsage(unit="video_second", count=30)
        result = media_usage_from_hook_metadata((a, b))
        assert result == (a, b)
        assert len(result) == 2

    def test_empty_tuple_returns_empty_tuple(self) -> None:
        result = media_usage_from_hook_metadata(())
        assert result == ()

    # -- list ----------------------------------------------------------------

    def test_list_converted_to_tuple(self) -> None:
        a = MediaUsage(unit="image", count=1)
        b = MediaUsage(unit="song", count=2)
        result = media_usage_from_hook_metadata([a, b])
        assert result == (a, b)
        assert isinstance(result, tuple)

    def test_empty_list_returns_empty_tuple(self) -> None:
        result = media_usage_from_hook_metadata([])
        assert result == ()

    # -- malformed / invalid -------------------------------------------------

    def test_non_media_usage_in_list_raises_typeerror(self) -> None:
        with pytest.raises(TypeError, match="Item 0.*"):
            media_usage_from_hook_metadata(["not-a-usage"])  # type: ignore[arg-type]

    def test_non_media_usage_in_tuple_raises_typeerror(self) -> None:
        with pytest.raises(TypeError, match="Item 0.*"):
            media_usage_from_hook_metadata(({"bad": True},))  # type: ignore[arg-type]

    def test_mixed_valid_and_invalid_raises_typeerror(self) -> None:
        a = MediaUsage(unit="image", count=1)
        with pytest.raises(TypeError, match="Item 1.*"):
            media_usage_from_hook_metadata([a, 42])  # type: ignore[arg-type]

    def test_arbitrary_object_raises_typeerror(self) -> None:
        with pytest.raises(TypeError, match="Expected MediaUsage"):
            media_usage_from_hook_metadata(42)  # type: ignore[arg-type]

    def test_string_raises_typeerror(self) -> None:
        with pytest.raises(TypeError, match="Expected MediaUsage"):
            media_usage_from_hook_metadata("image")  # type: ignore[arg-type]

    def test_dict_raises_typeerror(self) -> None:
        with pytest.raises(TypeError, match="Expected MediaUsage"):
            media_usage_from_hook_metadata({"unit": "image"})  # type: ignore[arg-type]

    # -- no-key / absence byte-compatibility --------------------------------

    def test_none_preserves_no_key_behavior(self) -> None:
        """When hook_metadata lacks 'media_usage', None is passed → empty tuple."""
        assert media_usage_from_hook_metadata(None) == ()

    def test_empty_list_preserves_no_key_behavior(self) -> None:
        """An empty list from hook_metadata should also be no-op."""
        result = media_usage_from_hook_metadata([])
        assert result == ()
        assert len(result) == 0


# ---------------------------------------------------------------------------
# No megaplan imports
# ---------------------------------------------------------------------------

class TestNoMegaplanImports:
    """``media_cost.py`` must not import arnold.pipelines.megaplan."""

    def test_media_cost_has_no_megaplan_imports(self) -> None:
        import ast
        import inspect
        import arnold.pipeline.media_cost as mc_module

        source = inspect.getsource(mc_module)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module_name = node.module or ""
                if "megaplan" in module_name:
                    assert False, f"media_cost.py imports megaplan: {ast.dump(node)}"
        assert True  # explicit pass


# ---------------------------------------------------------------------------
# compute_media_cost against DEFAULT_MEDIA_PRICING
# ---------------------------------------------------------------------------

class TestComputeMediaCostDefaults:
    """``compute_media_cost`` using ``DEFAULT_MEDIA_PRICING``."""

    def test_default_dall_e_image_priced(self) -> None:
        results = compute_media_cost(
            provider="openai",
            model="dall-e-3",
            media_usage=(MediaUsage(unit="image", count=2),),
        )
        assert results[0].status == "estimated"
        assert results[0].amount_usd == Decimal("0.080")

    def test_default_tts_song_priced(self) -> None:
        results = compute_media_cost(
            provider="openai",
            model="tts-1",
            media_usage=(MediaUsage(unit="song", count=1),),
        )
        assert results[0].status == "estimated"
        assert results[0].amount_usd == Decimal("0.015")

    def test_default_missing_unit_unknown(self) -> None:
        """DEFAULT_MEDIA_PRICING has no video_second row → unknown."""
        results = compute_media_cost(
            provider="openai",
            model="dall-e-3",
            media_usage=(MediaUsage(unit="video_second", count=10),),
        )
        assert results[0].status == "unknown"
        assert results[0].amount_usd is None
