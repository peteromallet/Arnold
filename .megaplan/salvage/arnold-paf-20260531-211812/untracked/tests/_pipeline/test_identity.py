"""Unit tests for megaplan._pipeline.identity (M5-eval T1 surface)."""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

from megaplan._pipeline.identity import (
    ARNOLD_API_VERSION,
    NODE_REGISTRY,
    NodeSpec,
    manifest_hash,
    register_node,
)
from megaplan._pipeline.types import Port


def _base_kwargs() -> dict:
    return dict(
        step_code_source="def run(): pass",
        resolved_rubric_body="rubric-A",
        model_identity="model-1",
        port_set=(Port(name="x", content_type="text/plain"),),
        abi_version=ARNOLD_API_VERSION,
    )


def test_distinct_rubric_bodies_yield_distinct_hashes() -> None:
    a = manifest_hash(**{**_base_kwargs(), "resolved_rubric_body": "rubric-A"})
    b = manifest_hash(**{**_base_kwargs(), "resolved_rubric_body": "rubric-B"})
    assert a != b


def test_manifest_hash_cross_process_determinism() -> None:
    src = textwrap.dedent(
        """
        from megaplan._pipeline.identity import manifest_hash, ARNOLD_API_VERSION
        from megaplan._pipeline.types import Port
        print(manifest_hash(
            step_code_source="src",
            resolved_rubric_body="rubric",
            model_identity="m",
            port_set=(Port(name="x", content_type="text/plain"),),
            abi_version=ARNOLD_API_VERSION,
        ))
        """
    )
    out1 = subprocess.check_output([sys.executable, "-c", src], text=True).strip()
    out2 = subprocess.check_output([sys.executable, "-c", src], text=True).strip()
    assert out1 == out2
    in_proc = manifest_hash(
        step_code_source="src",
        resolved_rubric_body="rubric",
        model_identity="m",
        port_set=(Port(name="x", content_type="text/plain"),),
        abi_version=ARNOLD_API_VERSION,
    )
    assert in_proc == out1


def test_model_swap_behind_stable_identity_changes_hash() -> None:
    a = manifest_hash(**{**_base_kwargs(), "model_identity": "model-1"})
    b = manifest_hash(**{**_base_kwargs(), "model_identity": "model-2"})
    assert a != b


def test_duplicate_register_node_rejected() -> None:
    spec = NodeSpec(
        consumes=(Port(name="p", content_type="text/plain"),),
        produces=(Port(name="q", content_type="text/plain"),),
        arnold_api_version=ARNOLD_API_VERSION,
        judge_version="abc",
    )
    register_node("test.dup.node", spec)
    try:
        with pytest.raises(ValueError):
            register_node("test.dup.node", spec)
    finally:
        NODE_REGISTRY.pop("test.dup.node", None)


def test_port_roundtrips_through_nodespec() -> None:
    p_in = Port(name="judged-artifact", content_type="text/markdown")
    p_out = Port(name="evaluand-record", content_type="application/x-evaluand+json")
    spec = NodeSpec(
        consumes=(p_in,),
        produces=(p_out,),
        arnold_api_version=ARNOLD_API_VERSION,
        judge_version="v",
    )
    assert spec.consumes[0] is p_in
    assert spec.produces[0].content_type == "application/x-evaluand+json"


def test_judge_default_registered_without_judge_piece_import() -> None:
    # Drop and re-import identity to assert clean import sequence.
    for mod in list(sys.modules):
        if mod.startswith("megaplan._pipeline.identity") or mod.endswith(".judge_piece"):
            sys.modules.pop(mod, None)
    import megaplan._pipeline.identity as identity_mod  # noqa: F401

    assert "judge.default" in identity_mod.NODE_REGISTRY
    assert "megaplan._pipeline.judge_piece" not in sys.modules


def test_registry_signature_hash_differs_from_runtime_hash() -> None:
    spec = NODE_REGISTRY["judge.default"]
    # Registry-baked judge_version uses empty rubric/model_identity.
    bare = manifest_hash(
        step_code_source="",
        resolved_rubric_body="",
        model_identity="",
        port_set=spec.consumes,
        abi_version=ARNOLD_API_VERSION,
    )
    assert spec.judge_version == bare

    runtime = manifest_hash(
        step_code_source="src",
        resolved_rubric_body="real-rubric",
        model_identity="real-model",
        port_set=spec.consumes,
        abi_version=ARNOLD_API_VERSION,
    )
    assert runtime != bare
