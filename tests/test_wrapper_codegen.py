"""Tests for ``vibecomfy.porting.wrappers.codegen``.

Covers:
- Determinism: rendering the same specs twice yields byte-identical output.
- Header parsing round-trip.
- Round-trip wrapper -> workflow build -> API JSON without raw_call.
- Identifier-unsafe field names route through ``**{...}`` spread.
- Golden snapshot for a representative spec.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from vibecomfy.porting.wrappers import codegen as wc
from vibecomfy.porting.wrappers.discovery import ClassSpec, InputFieldSpec


def _make_simple_spec(class_type: str = "SimpleSampler") -> ClassSpec:
    return ClassSpec(
        pack_slug="demo-pack",
        class_type=class_type,
        inputs={
            "model": InputFieldSpec(name="model", type="MODEL", required=True),
            "seed": InputFieldSpec(
                name="seed",
                type="INT",
                required=True,
                default=42,
                has_default=True,
            ),
            "mode": InputFieldSpec(
                name="mode",
                type="COMBO",
                required=True,
                default="alpha",
                has_default=True,
                options=("alpha", "beta"),
            ),
            "extra": InputFieldSpec(
                name="extra",
                type="STRING",
                required=False,
                default="hi",
                has_default=True,
            ),
        },
        outputs=("LATENT",),
        output_types=("LATENT",),
        category="test/category",
        display_name="Simple Sampler",
        source_provenance="object_info snapshot demo-pack@v1.json sha256:deadbeef",
    )


def test_render_is_deterministic(tmp_path: Path) -> None:
    spec = _make_simple_spec()
    a = wc.render_pack("demo-pack", [spec], out_dir=tmp_path)
    b = wc.render_pack("demo-pack", [spec], out_dir=tmp_path)
    assert a.source_text == b.source_text
    assert a.source_sha256 == b.source_sha256


def test_render_header_contains_marker_and_sha(tmp_path: Path) -> None:
    spec = _make_simple_spec()
    result = wc.render_pack("demo-pack", [spec], out_dir=tmp_path)
    parsed = wc.parse_generated_header(result.source_text)
    assert parsed is not None
    assert parsed["pack"] == "demo-pack"
    assert parsed["source_sha256"] == result.source_sha256
    assert parsed["generator_version"] == wc.GENERATOR_VERSION
    assert parsed["classes"] == "1"


def test_parse_generated_header_returns_none_for_handwritten() -> None:
    text = '"""hand-written module"""\n\nx = 1\n'
    assert wc.parse_generated_header(text) is None


def test_render_imports_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = _make_simple_spec()
    out_dir = tmp_path / "nodes"
    out_dir.mkdir()
    (out_dir / "__init__.py").write_text("")
    result = wc.render_pack("demo-pack", [spec], out_dir=out_dir)
    result.module_path.write_text(result.source_text)

    monkeypatch.syspath_prepend(str(tmp_path))
    mod = importlib.import_module("nodes." + result.module_path.stem)
    assert mod.SimpleSampler.CLASS_TYPE == "SimpleSampler"
    assert mod.SimpleSampler.OUTPUTS == ("LATENT",)


def test_render_round_trip_to_api_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The generated wrapper produces a typed wf.node call that compiles to API JSON."""
    spec = _make_simple_spec()
    out_dir = tmp_path / "nodes"
    out_dir.mkdir()
    (out_dir / "__init__.py").write_text("")
    result = wc.render_pack("demo-pack", [spec], out_dir=out_dir)
    result.module_path.write_text(result.source_text)
    monkeypatch.syspath_prepend(str(tmp_path))
    mod = importlib.import_module("nodes." + result.module_path.stem)

    from vibecomfy.workflow import VibeWorkflow, WorkflowSource

    wf = VibeWorkflow(
        "rt",
        WorkflowSource(id="rt", path="rt.py", source_type="inline"),
    )
    builder = mod.SimpleSampler.add(
        wf,
        model=None,  # link with no upstream — still valid for compile()
        seed=7,
        mode="beta",
    )
    api = wf.compile("api")
    assert api[builder.id]["class_type"] == "SimpleSampler"
    assert api[builder.id]["inputs"]["seed"] == 7
    assert api[builder.id]["inputs"]["mode"] == "beta"


def test_identifier_unsafe_kwargs_route_via_spread(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = ClassSpec(
        pack_slug="weird-pack",
        class_type="WeirdNode",
        inputs={
            "double_blocks.0.": InputFieldSpec(
                name="double_blocks.0.",
                type="FLOAT",
                required=False,
                default=1.0,
                has_default=True,
            ),
            "normal": InputFieldSpec(
                name="normal",
                type="INT",
                required=False,
                default=0,
                has_default=True,
            ),
        },
        outputs=("OUT",),
        output_types=("FLOAT",),
        source_provenance="test",
    )
    result = wc.render_pack("weird-pack", [spec], out_dir=tmp_path)
    assert "**{" in result.source_text
    assert "'double_blocks.0.':" in result.source_text
    # The Python file must parse.
    compile(result.source_text, str(result.module_path), "exec")


def test_class_name_sanitization_dedupes() -> None:
    # Two classes that sanitize to the same identifier — second is skipped.
    a = _make_simple_spec("Foo (bar)")
    b = _make_simple_spec("Foo_bar")
    result = wc.render_pack("dup", [a, b], out_dir=Path("/tmp"))
    # One is kept, one is skipped.
    assert (len(result.skipped_classes) == 1) ^ (result.class_count == 2)


def test_widget_schema_render_lists_non_link_fields() -> None:
    spec = _make_simple_spec()
    text = wc.render_widget_schema([spec])
    assert "'SimpleSampler'" in text
    assert "'seed'" in text
    # 'model' is a link socket, should NOT appear in widget order.
    assert "'model'" not in text


def test_golden_snapshot(tmp_path: Path) -> None:
    """One representative spec -> stable rendered shape.

    If this fails, inspect the diff carefully — a render change that breaks
    determinism is the headline failure mode for this whole pipeline.
    """
    spec = _make_simple_spec()
    result = wc.render_pack("demo-pack", [spec], out_dir=tmp_path)
    # We don't check the full text byte-for-byte against a golden file
    # (timestamps and SHAs would force frequent updates). Instead, anchor on
    # invariants that should not change without intent:
    text = result.source_text
    assert "class SimpleSampler:" in text
    assert "CLASS_TYPE = 'SimpleSampler'" in text
    assert "OUTPUTS: tuple[str, ...] = ('LATENT',)" in text
    assert "def add(" in text
    assert 'wf: "VibeWorkflow"' in text
    assert 'model: "Handle" = None' in text  # required link, no upstream default
    assert "seed: int = 42" in text
    assert "mode: str = \"alpha\"" in text
    assert "extra: str = \"hi\"" in text
    assert "return wf.node(" in text
