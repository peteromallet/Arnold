from __future__ import annotations

from arnold_pipelines.megaplan.handlers.shared import _normalize_plan_text


def test_normalize_plan_text_decodes_escaped_newlines_and_unicode_without_codec_roundtrip() -> None:
    plan = "# Price \\u00a3\\n\\n## Step 1: Ship\\n- Preserve Unicode"

    assert _normalize_plan_text(plan) == "# Price £\n\n## Step 1: Ship\n- Preserve Unicode"


def test_normalize_plan_text_preserves_unrelated_escapes() -> None:
    plan = "# Plan\\n\\n## Step 1: Example\\n- `path\\\\to\\\\thing`\\n- `\\t` stays literal"

    assert _normalize_plan_text(plan) == "# Plan\n\n## Step 1: Example\n- `path\\\\to\\\\thing`\n- `\\t` stays literal"
