"""Tests for control_after_generate retention through JSON→IR ingest (T3).

Proves:
1. 'randomize' and 'fixed' captured from the named-inputs dict (api-format path).
2. 'fixed' captured from _ui.widgets_values KSampler None-slot path.
3. Absent control_after_generate → metadata key unset (never guessed).
4. compile("api") guard: control_after_generate absent from compiled output
   even when captured in metadata (byte-identical compile path preserved).
"""
from __future__ import annotations

import json

from vibecomfy.ingest.normalize import convert_to_vibe_format


def _ksampler_api_node(*, control: str | None = None) -> dict:
    inputs: dict = {
        "seed": 42,
        "steps": 20,
        "cfg": 7.0,
        "sampler_name": "euler",
        "scheduler": "normal",
        "denoise": 1.0,
    }
    if control is not None:
        inputs["control_after_generate"] = control
    return {"class_type": "KSampler", "inputs": inputs}


def _ksampler_api_node_with_ui(*, control: str) -> dict:
    """KSampler node as produced by _normalize_ui_to_api with _ui.widgets_values.

    KSampler widget schema: ["seed", None, "steps", "cfg", "sampler_name", "scheduler", "denoise"]
    Slot index 1 is None (the control_after_generate UI slot).
    """
    return {
        "class_type": "KSampler",
        "inputs": {
            "seed": 42,
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
        },
        "_ui": {"widgets_values": [42, control, 20, 7.0, "euler", "normal", 1.0]},
    }


def _workflow_from_node(node: dict, node_id: str = "1"):  # type: ignore[return]
    return convert_to_vibe_format({node_id: node})


# ── Case 1a: 'randomize' captured from named inputs dict ─────────────────────


def test_control_after_generate_randomize_from_inputs() -> None:
    wf = _workflow_from_node(_ksampler_api_node(control="randomize"))
    assert wf.nodes["1"].metadata.get("control_after_generate") == "randomize"


# ── Case 1b: 'fixed' captured from named inputs dict ─────────────────────────


def test_control_after_generate_fixed_from_inputs() -> None:
    wf = _workflow_from_node(_ksampler_api_node(control="fixed"))
    assert wf.nodes["1"].metadata.get("control_after_generate") == "fixed"


# ── Case 2: 'fixed' captured from _ui.widgets_values None-slot ───────────────


def test_control_after_generate_fixed_from_ui_widgets() -> None:
    wf = _workflow_from_node(_ksampler_api_node_with_ui(control="fixed"))
    assert wf.nodes["1"].metadata.get("control_after_generate") == "fixed"


# ── Case 3: absent → metadata key unset (never guessed) ──────────────────────


def test_control_after_generate_absent_leaves_metadata_unset() -> None:
    wf = _workflow_from_node(_ksampler_api_node())
    assert "control_after_generate" not in wf.nodes["1"].metadata, (
        "control_after_generate must not be guessed when absent from source"
    )


# ── Case 4a: compile("api") excludes control_after_generate ──────────────────


def test_compile_api_excludes_control_after_generate() -> None:
    """compile('api') must not include control_after_generate even when metadata carries it."""
    wf = _workflow_from_node(_ksampler_api_node(control="randomize"))
    assert wf.nodes["1"].metadata.get("control_after_generate") == "randomize", "precondition: metadata captured"
    compiled = wf.compile("api")
    assert "control_after_generate" not in compiled.get("1", {}).get("inputs", {}), (
        "compile('api') must filter control_after_generate via _is_ui_only_prompt_input"
    )


# ── Case 4b: compile("api") byte-identical with and without the capture ───────


def test_compile_api_byte_identical_with_and_without_control_capture() -> None:
    """compile('api') output is identical regardless of control_after_generate presence.

    This is the guard asserting the T2 ingest change leaves the compiled API dict
    byte-for-byte unchanged: a node with control_after_generate captured in metadata
    compiles identically to the same node without it at all.
    """
    wf_without = _workflow_from_node(_ksampler_api_node())
    wf_with = _workflow_from_node(_ksampler_api_node(control="randomize"))

    compiled_without = wf_without.compile("api")
    compiled_with = wf_with.compile("api")

    assert json.dumps(compiled_without, sort_keys=True) == json.dumps(compiled_with, sort_keys=True), (
        "compile('api') output must be byte-for-byte identical with and without "
        "control_after_generate — the ingest metadata capture must not alter the compiled dict"
    )
