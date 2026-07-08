"""Canonical coordinate snapping for layout positions and sizes.

Uses round-half-even (banker's rounding) for idempotence and bit-stability
through json.dumps/json.loads cycles.  Python's built-in round() implements
banker's rounding per IEEE 754, so snap_coord is a one-liner.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def snap_coord(value: float | int) -> int:
    """Snap a single coordinate to a whole-pixel integer using round-half-even.

    Idempotent: snap_coord(snap_coord(x)) == snap_coord(x) for all finite x.
    Bit-stable: json.loads(json.dumps(snap_coord(x))) == snap_coord(x).
    """
    return round(value)


def _coord_values(seq: Sequence[float | int] | Mapping[Any, float | int]) -> list[float | int]:
    """Return coordinate values from ComfyUI geometry arrays or indexed objects."""
    if isinstance(seq, Mapping):
        indexed: list[tuple[int, float | int]] = []
        for key, value in seq.items():
            if isinstance(key, int):
                index = key
            elif isinstance(key, str) and key.isdecimal():
                index = int(key)
            else:
                raise TypeError(f"coordinate mapping key must be an integer index, got {key!r}")
            indexed.append((index, value))
        return [value for _, value in sorted(indexed)]
    if isinstance(seq, (str, bytes)):
        raise TypeError("coordinate sequence must not be a string")
    return list(seq)


def snap_pos(seq: Sequence[float | int] | Mapping[Any, float | int]) -> list[int]:
    """Snap a position sequence (x, y) to whole pixels."""
    return [snap_coord(v) for v in _coord_values(seq)]


def snap_size(seq: Sequence[float | int] | Mapping[Any, float | int]) -> list[int]:
    """Snap a size sequence (width, height) to whole pixels."""
    return [snap_coord(v) for v in _coord_values(seq)]
