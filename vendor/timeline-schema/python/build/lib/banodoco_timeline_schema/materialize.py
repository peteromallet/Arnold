from __future__ import annotations

from typing import Any, Mapping

OUTPUT_FILE_DEFAULT = "output.mp4"


def materialize_output(
    timeline: Mapping[str, Any],
    theme: Mapping[str, Any],
    *,
    file: str = OUTPUT_FILE_DEFAULT,
) -> dict[str, Any]:
    """Build a Reigh-compatible `output` block from a Banodoco timeline + theme.

    SD-009: `output.fps` sources from `theme.visual.canvas.fps`, NOT
    `theme.pacing.fps`. The 2rp theme's pacing block has no fps field; the
    canvas block is the authoritative render-rate source.
    """
    visual = _as_dict(theme.get("visual"))
    canvas = _as_dict(visual.get("canvas"))
    width = canvas.get("width")
    height = canvas.get("height")
    fps = canvas.get("fps")
    if not _is_positive_number(width):
        raise ValueError("theme.visual.canvas.width must be a positive number")
    if not _is_positive_number(height):
        raise ValueError("theme.visual.canvas.height must be a positive number")
    if not _is_positive_number(fps):
        raise ValueError("theme.visual.canvas.fps must be a positive number")

    output: dict[str, Any] = {
        "resolution": f"{int(width)}x{int(height)}",
        "fps": float(fps) if isinstance(fps, float) else int(fps),
        "file": file,
    }
    timeline_output = _as_dict(timeline.get("output"))
    background = timeline_output.get("background")
    if isinstance(background, str) and background:
        output["background"] = background
    background_scale = timeline_output.get("background_scale")
    if isinstance(background_scale, (int, float)):
        output["background_scale"] = background_scale
    return output


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _is_positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) > 0
