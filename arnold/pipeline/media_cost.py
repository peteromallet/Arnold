"""Neutral media usage record + per-media-unit pricing core.

This module defines the media cost accounting types and the
:func:`compute_media_cost` function.  It lives in generic ``arnold.pipeline``
so non-megaplan consumers can emit and price media usage without importing
any megaplan-coupled module.

Key types
---------
* ``MediaUsage``        — frozen record of one media usage event.
* ``MediaPricingEntry`` — one pricing row keyed by ``(provider, model, unit)``.
* ``compute_media_cost`` — prices a sequence of ``MediaUsage`` items into
  ``CostResult`` lines; missing pricing rows return ``status='unknown'``
  (never a silent zero).

Design invariants
-----------------
* **Zero megaplan imports.**  No import statement in this module references
  ``megaplan``.
* **Sibling surface.**  Token pricing lives in ``token_cost.py`` and shares
  neutral cost result types with media cost.
* **Reference-by-unit, not by content.**  Media usage is counted in semantic
  units (e.g. ``image``, ``video_second``, ``audio_second``, ``song``) and
  dimensions; it never reads a produced blob to compute cost.
* **Graceful unknown.**  Missing pricing rows yield ``CostStatus='unknown'``
  with ``amount_usd is None``.  The run is never blocked on missing media
  pricing.

Semantic cost units vs. content types
---------------------------------------
The cost units used here (``image``, ``video_second``, ``audio_second``,
``song``) are **open semantic strings** for pricing — they are *not* MIME
content types.  Content-type validation lives in
:mod:`arnold.pipeline.media_content` and uses strings like ``video/mp4``,
``audio/wav``, etc.

For orientation only, a rough mapping:

* ``image``         →  ``image/*``
* ``video_second``  →  ``video/*``
* ``audio_second``  →  ``audio/*``
* ``song``          →  ``audio/*``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping, Optional

from arnold.pipeline.cost_types import CostResult, CostSource, CostStatus


# ── MediaUsage ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MediaUsage:
    """A single media usage event.

    Attributes
    ----------
    unit:
        Semantic unit string, e.g. ``"image"``, ``"video_second"``,
        ``"audio_second"``, ``"song"``.  Open vocabulary.
    count:
        Number of units consumed.  ``int``, ``float``, or ``Decimal``.
        Normalized to ``Decimal`` before pricing arithmetic.
    dimensions:
        Optional key/value metadata (resolution, fps, duration, …).
    raw_usage:
        Optional raw provider response blob — retained for debugging but
        never inspected by pricing logic.
    """

    unit: str
    count: int | float | Decimal
    dimensions: Mapping[str, Any] = field(default_factory=dict)
    raw_usage: Any | None = None


# ── Decimal normalizer ──────────────────────────────────────────────────────

def _decimal_count(count: int | float | Decimal) -> Decimal:
    """Normalize *count* to ``Decimal`` via string conversion.

    This ensures predictable precision: ``Decimal(str(0.015))`` yields
    ``Decimal('0.015')`` rather than the binary-float approximation.
    """
    return Decimal(str(count))


# ── MediaPricingEntry ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class MediaPricingEntry:
    """A single per-media-unit pricing row.

    Keyed by ``(provider, model, unit)``.  Mirrors the provenance fields
    of the token ``PricingEntry`` from ``usage_pricing.py``.
    """

    provider: str
    model: str
    unit: str
    cost_per_unit: Optional[Decimal] = None
    source: CostSource = "estimated"
    source_url: Optional[str] = None
    pricing_version: Optional[str] = None
    fetched_at: Optional[datetime] = None
    status: CostStatus = "estimated"


# ── Default pricing rows ────────────────────────────────────────────────────

# Representative fixture rows.  These are *snapshots* captured from published
# provider documentation and are not guaranteed to be current live rates.
# The ``pricing_version`` string marks them as AR3-era snapshots.
# Consumers should always allow override via ``pricing_rows=``.
DEFAULT_MEDIA_PRICING: tuple[MediaPricingEntry, ...] = (
    MediaPricingEntry(
        provider="openai",
        model="dall-e-3",
        unit="image",
        cost_per_unit=Decimal("0.040"),
        source="official_docs_snapshot",
        source_url="https://openai.com/api/pricing/",
        pricing_version="ar3-media-snapshot-2026-06",
        status="estimated",
    ),
    MediaPricingEntry(
        provider="openai",
        model="dall-e-3",
        unit="image_hd",
        cost_per_unit=Decimal("0.080"),
        source="official_docs_snapshot",
        source_url="https://openai.com/api/pricing/",
        pricing_version="ar3-media-snapshot-2026-06",
        status="estimated",
    ),
    MediaPricingEntry(
        provider="openai",
        model="tts-1",
        unit="song",
        cost_per_unit=Decimal("0.015"),
        source="official_docs_snapshot",
        source_url="https://openai.com/api/pricing/",
        pricing_version="ar3-media-snapshot-2026-06",
        status="estimated",
    ),
)


# ── Lookup helper ───────────────────────────────────────────────────────────

def _lookup_media_pricing(
    provider: str,
    model: str,
    unit: str,
    pricing_rows: tuple[MediaPricingEntry, ...],
) -> Optional[MediaPricingEntry]:
    """Return the first matching ``MediaPricingEntry`` or ``None``.

    Matching is case-insensitive on *provider* and *model*; *unit* is
    matched exactly (lowercased).
    """
    key = (provider.strip().lower(), model.strip().lower(), unit.strip().lower())
    for entry in pricing_rows:
        if (entry.provider.strip().lower() == key[0]
                and entry.model.strip().lower() == key[1]
                and entry.unit.strip().lower() == key[2]):
            return entry
    return None


# ── UsageExtraction ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class UsageExtraction:
    """Structured return from a ``_usage_extractor`` callable.

    This is the **structured** extraction path (AR3+).  Legacy extractors
    that return a plain ``dict`` continue to work — their output is treated
    as ``state_patch`` only and is never routed into ``hook_metadata``.

    Attributes
    ----------
    state_patch:
        Key/value pairs to merge into the step's ``state_patch``.
        Identical to what a plain-dict legacy extractor would return.
    media_usage:
        Zero or more :class:`MediaUsage` records that should be attached
        to ``StepResult.hook_metadata['media_usage']``.  Defaults to an
        empty tuple (no media usage reported).
    """

    state_patch: dict[str, Any] = field(default_factory=dict)
    media_usage: tuple[MediaUsage, ...] = ()


def normalize_usage_extraction(
    extracted: Any,
) -> tuple[dict[str, Any], tuple[MediaUsage, ...]]:
    """Normalize ``_usage_extractor`` output to ``(state_patch, media_usage)``.

    Parameters
    ----------
    extracted:
        The return value of a ``_usage_extractor`` callable.

    Returns
    -------
    tuple[dict[str, Any], tuple[MediaUsage, ...]]
        * If *extracted* is a :class:`UsageExtraction`: returns
          ``(dict(extracted.state_patch), extracted.media_usage)``.
        * If *extracted* is a plain ``dict``: returns
          ``(dict(extracted), ())`` — legacy behavior, no media usage
          is routed into hook metadata.
        * Otherwise: returns ``({}, ())`` — graceful degradation for
          unrecognised return shapes (the caller's try/except already
          guards this path).

    Notes
    -----
    Callers that do **not** use a ``_usage_extractor`` are unaffected —
    ``media_usage`` can still arrive via the adapter envelope
    (:class:`~arnold.pipeline.step_invocation.StepInvocationResult`).
    This normalizer is only relevant when a ``_usage_extractor`` **is**
    configured.
    """
    if isinstance(extracted, UsageExtraction):
        return dict(extracted.state_patch), extracted.media_usage
    if isinstance(extracted, dict):
        return dict(extracted), ()
    return {}, ()


# ── Hook metadata normalization ──────────────────────────────────────────────

def media_usage_from_hook_metadata(
    media_usage_value: MediaUsage | list[MediaUsage] | tuple[MediaUsage, ...] | None,
) -> tuple[MediaUsage, ...]:
    """Normalize a ``hook_metadata['media_usage']`` value to a tuple of ``MediaUsage``.

    This is the single entry point for reading media usage from hook metadata.
    It accepts the shapes that callers can realistically produce:

    * ``None`` / absent key → empty tuple ``()``
    * A single ``MediaUsage`` → one-element tuple ``(usage,)``
    * A ``list`` or ``tuple`` of ``MediaUsage`` → tuple copy

    Raises
    ------
    TypeError
        If *media_usage_value* is not ``None``, a ``MediaUsage``, or a
        list/tuple of ``MediaUsage`` items.

    Notes
    -----
    Direct callers (unit tests) get a hard ``TypeError`` on malformed input.
    Runtime hooks should wrap the call in a try/except and record a nonfatal
    warning or unknown cost line rather than fail a pipeline run.
    """
    if media_usage_value is None:
        return ()

    if isinstance(media_usage_value, MediaUsage):
        return (media_usage_value,)

    if isinstance(media_usage_value, (list, tuple)):
        result = tuple(media_usage_value)
        for i, item in enumerate(result):
            if not isinstance(item, MediaUsage):
                raise TypeError(
                    f"Item {i} in media_usage is {type(item).__name__!r}, "
                    f"expected MediaUsage"
                )
        return result

    raise TypeError(
        f"Expected MediaUsage, list[MediaUsage], tuple[MediaUsage, ...], or None; "
        f"got {type(media_usage_value).__name__!r}"
    )


# ── Cost computation ────────────────────────────────────────────────────────

def compute_media_cost(
    provider: str,
    model: str,
    media_usage: tuple[MediaUsage, ...],
    *,
    pricing_rows: tuple[MediaPricingEntry, ...] = DEFAULT_MEDIA_PRICING,
) -> tuple[CostResult, ...]:
    """Price a sequence of media usage items into ``CostResult`` lines.

    Parameters
    ----------
    provider:
        Provider name (e.g. ``"openai"``, ``"anthropic"``).
    model:
        Model name (e.g. ``"dall-e-3"``, ``"tts-1"``).
    media_usage:
        One or more ``MediaUsage`` records.
    pricing_rows:
        Tuple of ``MediaPricingEntry`` rows to search.

    Returns
    -------
    tuple of ``CostResult``
        One result per *media_usage* item, in the same order.  Items whose
        ``(provider, model, unit)`` has no matching pricing row are returned
        with ``status='unknown'`` and ``amount_usd=None`` — never a silent
        zero and never an exception.
    """
    results: list[CostResult] = []

    for mu in media_usage:
        # --- find the matching pricing row --------------------------------
        entry = _lookup_media_pricing(provider, model, mu.unit, pricing_rows)

        if entry is None:
            # No pricing row → unknown.
            results.append(
                CostResult(
                    amount_usd=None,
                    status="unknown",
                    source="none",
                    label="n/a",
                    notes=(
                        f"No media pricing row for provider={provider!r}"
                        f" model={model!r} unit={mu.unit!r}",
                    ),
                )
            )
            continue

        # --- compute cost -------------------------------------------------
        normalized = _decimal_count(mu.count)
        cost_per_unit = entry.cost_per_unit
        if cost_per_unit is None:
            amount = None
        else:
            amount = normalized * cost_per_unit

        results.append(
            CostResult(
                amount_usd=amount,
                status=entry.status,
                source=entry.source,
                label=f"{mu.unit} ({normalized})",
                fetched_at=entry.fetched_at,
                pricing_version=entry.pricing_version,
            )
        )

    return tuple(results)
