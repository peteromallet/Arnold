"""Unit tests for materialize_output and the 2rp theme path.

Run from packages/timeline-schema/:
    python -m pytest tests/

Or:
    python tests/test_materialize_output.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
THEMES_ROOT = REPO_ROOT / "themes"
HYPE_TIMELINE = (
    REPO_ROOT
    / "tools"
    / "runs"
    / "2rp-templated"
    / "briefs"
    / "2rp-templated"
    / "hype.timeline.json"
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

from banodoco_timeline_schema import (  # noqa: E402
    OUTPUT_FILE_DEFAULT,
    materialize_output,
    resolve_theme,
    validate_timeline,
)


class MaterializeOutputTests(unittest.TestCase):
    def test_materialize_output_from_2rp_theme(self) -> None:
        theme = json.loads((THEMES_ROOT / "2rp" / "theme.json").read_text(encoding="utf-8"))
        timeline = {"theme": "2rp", "clips": []}
        out = materialize_output(timeline, theme)
        self.assertEqual(out["resolution"], "1920x1080")
        self.assertEqual(out["fps"], 30)
        self.assertEqual(out["file"], OUTPUT_FILE_DEFAULT)
        self.assertNotIn("background", out)

    def test_materialize_output_carries_background(self) -> None:
        theme = {"visual": {"canvas": {"width": 1280, "height": 720, "fps": 24}}}
        timeline = {
            "theme": "x",
            "clips": [],
            "output": {"background": "#000000", "background_scale": 1.5},
        }
        out = materialize_output(timeline, theme)
        self.assertEqual(out["resolution"], "1280x720")
        self.assertEqual(out["fps"], 24)
        self.assertEqual(out["background"], "#000000")
        self.assertEqual(out["background_scale"], 1.5)

    def test_materialize_output_rejects_missing_canvas(self) -> None:
        with self.assertRaises(ValueError):
            materialize_output({"theme": "x", "clips": []}, {"visual": {}})

    def test_materialize_output_rejects_pacing_only_fps(self) -> None:
        # Defensive: ensure fps does NOT fall back to theme.pacing.fps (SD-009).
        theme = {"visual": {"canvas": {"width": 1, "height": 1}}, "pacing": {"fps": 30}}
        with self.assertRaises(ValueError):
            materialize_output({"theme": "x", "clips": []}, theme)


class ResolveThemeTests(unittest.TestCase):
    def test_resolve_theme_2rp(self) -> None:
        out = resolve_theme({"theme": "2rp"}, THEMES_ROOT)
        self.assertEqual(out["visual"]["canvas"]["fps"], 30)

    def test_resolve_theme_with_overrides(self) -> None:
        out = resolve_theme(
            {"theme": "2rp", "theme_overrides": {"visual": {"canvas": {"fps": 60}}}},
            THEMES_ROOT,
        )
        self.assertEqual(out["visual"]["canvas"]["fps"], 60)
        self.assertEqual(out["visual"]["canvas"]["width"], 1920)

    def test_resolve_theme_rejects_missing_theme(self) -> None:
        with self.assertRaisesRegex(ValueError, "Timeline.theme must be a non-empty slug"):
            resolve_theme({}, THEMES_ROOT)

    def test_resolve_theme_rejects_empty_theme(self) -> None:
        with self.assertRaisesRegex(ValueError, "Timeline.theme must be a non-empty slug"):
            resolve_theme({"theme": ""}, THEMES_ROOT)


class ValidateTimelineTests(unittest.TestCase):
    def test_validate_timeline_accepts_no_theme_persisted_shape(self) -> None:
        validate_timeline({"clips": []}, strict=False)

    def test_validate_timeline_accepts_open_generation_defaults(self) -> None:
        payload = {
            "theme": "2rp",
            "clips": [],
            "generation_defaults": {
                "model": "sequence-v1",
                "image": {"quality": "high", "provider": "reigh"},
                "provider_settings": {"seed": 1234, "flags": ["keep", "open"]},
            },
        }
        validate_timeline(payload, strict=False)

    def test_validate_timeline_rejects_non_object_generation_defaults(self) -> None:
        with self.assertRaises(Exception):
            validate_timeline({"clips": [], "generation_defaults": []}, strict=False)

    @unittest.skipUnless(
        HYPE_TIMELINE.is_file(),
        f"fixture missing: {HYPE_TIMELINE}",
    )
    def test_2rp_templated_hype_timeline_validates(self) -> None:
        payload = json.loads(HYPE_TIMELINE.read_text(encoding="utf-8"))
        validate_timeline(payload, strict=False)


if __name__ == "__main__":
    unittest.main()
