"""Focused tests for emit_ui_json slot/type resolution, provenance, and strict mode (T5)."""
from __future__ import annotations

import json
import warnings

import pytest

from vibecomfy.porting.ui_emitter import emit_ui_json
from vibecomfy.schema.provider import NodeSchema, OutputSpec
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wf(wf_id: str = "test") -> VibeWorkflow:
    return VibeWorkflow(wf_id, WorkflowSource(wf_id))


class _Provider:
    """Minimal schema provider backed by an explicit class→NodeSchema dict."""

    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def _schema(class_type: str, outputs: list[OutputSpec], *, confidence: float = 1.0, provider: str = "node_index") -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        pack=None,
        inputs={},
        outputs=outputs,
        source_provider=provider,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Numeric slot pass-through (from_output is a digit string)
# ---------------------------------------------------------------------------


def test_numeric_from_output_resolves_directly() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
    result = emit_ui_json(wf, schema_provider=provider)

    assert len(result["links"]) == 1
    link = result["links"][0]
    assert link[2] == 0  # from_slot
    assert link[5] == "IMAGE"  # socket type from OutputSpec


# ---------------------------------------------------------------------------
# NAME→slot resolution via OutputSpec list position
# ---------------------------------------------------------------------------


def test_name_from_output_resolves_to_slot_index() -> None:
    """from_output='clip' resolves to slot 1 for a [MODEL, CLIP] outputs list."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "CLIPLoader")
    wf.nodes["2"] = VibeNode("2", "Consumer")
    wf.edges.append(VibeEdge("1", "clip", "2", "clip_in"))

    provider = _Provider(
        {
            "CLIPLoader": _schema(
                "CLIPLoader",
                [OutputSpec("MODEL", "model"), OutputSpec("CLIP", "clip")],
            )
        }
    )
    result = emit_ui_json(wf, schema_provider=provider)

    assert len(result["links"]) == 1
    link = result["links"][0]
    assert link[2] == 1  # slot index = list position of 'clip'
    assert link[5] == "CLIP"  # socket type


# ---------------------------------------------------------------------------
# Node outputs list: slot_index, wired links, and links=null for unwired
# ---------------------------------------------------------------------------


def test_outputs_slot_index_and_links_null_for_unwired() -> None:
    """Schema has 2 outputs; only slot 0 is wired. Slot 1 must emit links=null."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    provider = _Provider(
        {
            "LoadImage": _schema(
                "LoadImage",
                [OutputSpec("IMAGE", "image"), OutputSpec("MASK", "mask")],
            )
        }
    )
    result = emit_ui_json(wf, schema_provider=provider)
    node1 = next(n for n in result["nodes"] if n["id"] == 1)
    outputs = node1["outputs"]

    assert len(outputs) == 2
    assert outputs[0]["slot_index"] == 0
    assert outputs[0]["links"] is not None  # wired
    assert outputs[1]["slot_index"] == 1
    assert outputs[1]["links"] is None  # unwired → null


# ---------------------------------------------------------------------------
# Recovery report — per-node provenance
# ---------------------------------------------------------------------------


def test_recovery_report_populated_for_all_nodes() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage", []),
        }
    )
    report: list[dict] = []
    emit_ui_json(wf, schema_provider=provider, recovery_report=report)

    node_ids = {e["node_id"] for e in report}
    assert "1" in node_ids
    assert "2" in node_ids
    for entry in report:
        assert "class_type" in entry
        assert "provider" in entry
        assert "confidence" in entry
        assert "schema_less" in entry


def test_recovery_report_schema_less_entry_has_diagnostic() -> None:
    """Schema-less nodes get a diagnostic string in the recovery report."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "UnknownNode")

    report: list[dict] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        emit_ui_json(wf, schema_provider=None, recovery_report=report)

    assert len(report) == 1
    assert report[0]["schema_less"] is True
    assert report[0]["provider"] is None
    assert "diagnostic" in report[0]


def test_recovery_report_widget_schema_fallback_has_diagnostic() -> None:
    """widget_schema_fallback (confidence=0.3) recorded with diagnostic."""
    provider = _Provider(
        {"SomeNode": _schema("SomeNode", [OutputSpec("X", "x")], confidence=0.3, provider="widget_schema")}
    )
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "SomeNode")

    report: list[dict] = []
    emit_ui_json(wf, schema_provider=provider, recovery_report=report)

    assert report[0]["confidence"] == 0.3
    assert "diagnostic" in report[0]
    assert "low-confidence" in report[0]["diagnostic"]


# ---------------------------------------------------------------------------
# Strict mode
# ---------------------------------------------------------------------------


def test_strict_raises_for_schema_less_node() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "Unknown")

    with pytest.raises(ValueError, match="strict=True"):
        emit_ui_json(wf, schema_provider=None, strict=True)


def test_strict_raises_for_widget_schema_fallback_confidence() -> None:
    provider = _Provider(
        {"SomeNode": _schema("SomeNode", [], confidence=0.3, provider="widget_schema")}
    )
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "SomeNode")

    with pytest.raises(ValueError, match="strict=True"):
        emit_ui_json(wf, schema_provider=provider, strict=True)


def test_strict_passes_for_high_confidence_schema() -> None:
    provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    # Should not raise
    emit_ui_json(wf, schema_provider=provider, strict=True)


# ---------------------------------------------------------------------------
# Schema-less best-effort warning (non-strict)
# ---------------------------------------------------------------------------


def test_schema_less_emits_warning_in_non_strict_mode() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "MysteryNode")
    wf.nodes["2"] = VibeNode("2", "Consumer")
    wf.connect("1.0", "2.a")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        emit_ui_json(wf, schema_provider=None)

    assert any("schema-less" in str(w.message) for w in caught)


# ---------------------------------------------------------------------------
# UUID class types pass through as-is
# ---------------------------------------------------------------------------


def test_uuid_class_type_emits_as_is() -> None:
    """Subgraph UUID class types are valid type strings and must pass through unchanged."""
    import uuid as _uuid

    ct = str(_uuid.UUID("7b34ab90-36f9-45ba-a665-71d418f0df18"))
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", ct)
    wf.nodes["2"] = VibeNode("2", "Consumer")
    wf.connect("1.0", "2.a")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, schema_provider=None)

    node1 = next(n for n in result["nodes"] if n["id"] == 1)
    assert node1["type"] == ct
    # Link emitted with best-effort slot
    assert len(result["links"]) == 1


# ---------------------------------------------------------------------------
# Byte-determinism preserved with schema provider
# ---------------------------------------------------------------------------


def test_byte_determinism_with_schema_provider() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image"), OutputSpec("MASK", "mask")]),
            "SaveImage": _schema("SaveImage", []),
        }
    )
    r1 = emit_ui_json(wf, schema_provider=provider)
    r2 = emit_ui_json(wf, schema_provider=provider)

    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


# ---------------------------------------------------------------------------
# T6 — widgets_values, control_after_generate, input-slot widget objects
# ---------------------------------------------------------------------------


def _ksampler(node_id: str = "1") -> VibeNode:
    return VibeNode(
        node_id,
        "KSampler",
        inputs={
            "seed": 5,
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
        },
    )


def test_widgets_values_use_compacted_schema_ordering() -> None:
    """widgets_values lays values against _schema_input_names (None slots stripped),
    so control_after_generate is NOT a positional element (parity-safe)."""
    wf = _wf()
    wf.nodes["1"] = _ksampler()
    node = next(n for n in emit_ui_json(wf)["nodes"] if n["id"] == 1)
    # compacted KSampler names: seed, steps, cfg, sampler_name, scheduler, denoise
    assert node["widgets_values"] == [5, 20, 7.0, "euler", "normal", 1.0]


def test_control_after_generate_retained_from_metadata() -> None:
    wf = _wf()
    node = _ksampler()
    node.metadata["control_after_generate"] = "randomize"
    wf.nodes["1"] = node
    report: list[dict] = []
    emit_ui_json(wf, recovery_report=report)
    entry = report[0]
    assert entry["control_after_generate"] == "randomize"
    assert entry["control_after_generate_defaulted"] is False


def test_control_after_generate_defaults_to_fixed_and_flags() -> None:
    wf = _wf()
    wf.nodes["1"] = _ksampler()  # no metadata control
    report: list[dict] = []
    emit_ui_json(wf, recovery_report=report)
    entry = report[0]
    assert entry["control_after_generate"] == "fixed"
    assert entry["control_after_generate_defaulted"] is True


def test_linked_widget_input_carries_widget_object() -> None:
    """A widget-type input converted to a LINK gets widget:{name:...} and leaves
    widgets_values; pure socket inputs get no widget key."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "PrimitiveString")
    wf.nodes["2"] = VibeNode("2", "CLIPTextEncode")
    wf.edges.append(VibeEdge("1", "0", "2", "text"))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        node = next(n for n in emit_ui_json(wf)["nodes"] if n["id"] == 2)
    slot = node["inputs"][0]
    assert slot["name"] == "text"
    assert slot["widget"] == {"name": "text"}
    assert node["widgets_values"] == []  # linked widget removed from array


def test_schema_less_node_skips_length_check() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "TotallyUnknownNode", widgets={"widget_0": 5})
    report: list[dict] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        emit_ui_json(wf, recovery_report=report)
    assert "skipped" in report[0]["widget_length_check"]


def test_corpus_roundtrip_parity_with_compile_api() -> None:
    """The parity oracle: _normalize_ui_to_api(emit_ui_json(wf)) is compile_equivalent
    to wf.compile('api') for every UI-shaped official corpus workflow."""
    import glob

    from vibecomfy.ingest.normalize import _normalize_ui_to_api, convert_to_vibe_format
    from vibecomfy.porting.parity import compile_equivalent

    paths = sorted(glob.glob("workflow_corpus/official/**/*.json", recursive=True))
    checked = 0
    for path in paths:
        with open(path) as handle:
            raw = json.load(handle)
        if not isinstance(raw.get("nodes"), list):
            continue
        wf = convert_to_vibe_format(raw)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ui = emit_ui_json(wf)
        api = wf.compile("api")
        equal, diffs = compile_equivalent(_normalize_ui_to_api(ui), api)
        assert equal, f"{path}: {diffs[:5]}"
        checked += 1
    assert checked > 0


# ---------------------------------------------------------------------------
# T7 — id remap, broadcast fan-out, primitive feeders, multi-output, subgraphs
# ---------------------------------------------------------------------------


def test_node_ids_remapped_to_litegraph_ints() -> None:
    """Digit ids preserve their numeric value; node id field and link node slots are ints."""
    wf = _wf()
    wf.nodes["9"] = VibeNode("9", "LoadImage")
    wf.nodes["78"] = VibeNode("78", "SaveImage")
    wf.connect("9.0", "78.images")
    provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
    result = emit_ui_json(wf, schema_provider=provider)

    ids = {n["id"] for n in result["nodes"]}
    assert ids == {9, 78}
    assert all(isinstance(i, int) for i in ids)
    assert result["last_node_id"] == 78
    link = result["links"][0]
    assert link[1] == 9 and link[3] == 78  # int node refs in the 6-element array
    # ir_node_id preserves the original string id
    node9 = next(n for n in result["nodes"] if n["id"] == 9)
    assert node9["properties"]["ir_node_id"] == "9"


def test_non_digit_node_ids_assigned_fresh_ints_above_max() -> None:
    wf = _wf()
    wf.nodes["5"] = VibeNode("5", "LoadImage")
    wf.nodes["node_alpha"] = VibeNode("node_alpha", "SaveImage")
    wf.connect("5.0", "node_alpha.images")
    provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
    result = emit_ui_json(wf, schema_provider=provider)

    by_ir = {n["properties"]["ir_node_id"]: n["id"] for n in result["nodes"]}
    assert by_ir["5"] == 5
    assert by_ir["node_alpha"] > 5  # assigned above the highest digit id
    assert result["last_node_id"] == by_ir["node_alpha"]


def test_multi_output_node_links_grouped_by_slot() -> None:
    """A node with two output slots both wired emits links on the correct slots."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "CheckpointLoader")
    wf.nodes["2"] = VibeNode("2", "ConsumerA")
    wf.nodes["3"] = VibeNode("3", "ConsumerB")
    wf.edges.append(VibeEdge("1", "model", "2", "model"))
    wf.edges.append(VibeEdge("1", "clip", "3", "clip"))
    provider = _Provider(
        {"CheckpointLoader": _schema("CheckpointLoader", [OutputSpec("MODEL", "model"), OutputSpec("CLIP", "clip")])}
    )
    result = emit_ui_json(wf, schema_provider=provider)
    node1 = next(n for n in result["nodes"] if n["id"] == 1)
    assert node1["outputs"][0]["links"] is not None  # slot 0 (model)
    assert node1["outputs"][1]["links"] is not None  # slot 1 (clip)
    assert len(result["links"]) == 2


def test_primitive_feeder_no_inputs_one_output() -> None:
    """A feeder node (no inputs, one output) feeding many consumers emits one link each."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "PrimitiveInt")
    wf.nodes["2"] = VibeNode("2", "ConsumerA")
    wf.nodes["3"] = VibeNode("3", "ConsumerB")
    wf.edges.append(VibeEdge("1", "0", "2", "value"))
    wf.edges.append(VibeEdge("1", "0", "3", "value"))
    provider = _Provider({"PrimitiveInt": _schema("PrimitiveInt", [OutputSpec("INT", "int")])})
    result = emit_ui_json(wf, schema_provider=provider)
    node1 = next(n for n in result["nodes"] if n["id"] == 1)
    assert not node1["inputs"]  # feeder has no input slots
    assert sorted(node1["outputs"][0]["links"]) and len(node1["outputs"][0]["links"]) == 2
    assert len(result["links"]) == 2


def test_broadcast_fanout_resolved_via_collect_broadcast_sources() -> None:
    """SetNode/GetNode broadcast: helpers are dropped and a GetNode fan-out becomes
    direct links from the captured real source (one source → many links)."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "CheckpointLoader")
    wf.nodes["10"] = VibeNode("10", "SetNode", widgets={"widget_0": "MODEL_BUS"})
    wf.nodes["11"] = VibeNode("11", "GetNode", widgets={"widget_0": "MODEL_BUS"})
    wf.nodes["2"] = VibeNode("2", "ConsumerA")
    wf.nodes["3"] = VibeNode("3", "ConsumerB")
    wf.edges.append(VibeEdge("1", "0", "10", "value"))   # source → SetNode
    wf.edges.append(VibeEdge("11", "0", "2", "model"))    # GetNode → consumers
    wf.edges.append(VibeEdge("11", "0", "3", "model"))
    provider = _Provider({"CheckpointLoader": _schema("CheckpointLoader", [OutputSpec("MODEL", "model")])})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, schema_provider=provider)

    emitted_types = {n["type"] for n in result["nodes"]}
    assert "SetNode" not in emitted_types and "GetNode" not in emitted_types
    # Two direct links, both originating from the real source node id (1)
    assert len(result["links"]) == 2
    assert all(link[1] == 1 for link in result["links"])
    targets = sorted(link[3] for link in result["links"])
    assert targets == [2, 3]


def test_definitions_emit_object_links_and_last_reroute_id() -> None:
    """When the IR carries subgraph definitions, links use OBJECT shape and
    state.lastRerouteId is emitted at both subgraph and top level."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    wf.metadata["definitions"] = {
        "subgraphs": [
            {
                "id": "sg-uuid",
                "name": "Sub",
                "nodes": [],
                "links": [[137, 68, 0, 62, 0, "INT"]],  # array-style → must convert
            }
        ]
    }
    provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
    result = emit_ui_json(wf, schema_provider=provider)

    assert "definitions" in result
    sg = result["definitions"]["subgraphs"][0]
    assert sg["links"][0] == {
        "id": 137,
        "origin_id": 68,
        "origin_slot": 0,
        "target_id": 62,
        "target_slot": 0,
        "type": "INT",
    }
    assert sg["state"]["lastRerouteId"] == 0
    assert result["state"]["lastRerouteId"] == 0


def test_no_definitions_omits_definitions_and_state() -> None:
    """Common post-ingest case: no definitions → envelope omits definitions/state."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
    result = emit_ui_json(wf, schema_provider=provider)
    assert "definitions" not in result
    assert "state" not in result


# ---------------------------------------------------------------------------
# T8 — offline parity gate + structural validation
# ---------------------------------------------------------------------------

_STARTER_SET = [
    "workflow_corpus/official/image/z_image.json",
    "workflow_corpus/official/image/flux2_klein_4b_t2i.json",
    "workflow_corpus/official/video/wan_t2v.json",
    "workflow_corpus/official/video/wan_i2v.json",
    "workflow_corpus/official/edit/qwen_image_edit.json",
    "workflow_corpus/official/edit/flux2_klein_4b_image_edit_base.json",
]


def _local_provider():
    from vibecomfy.schema import get_schema_provider

    return get_schema_provider("local")


@pytest.mark.parametrize("path", _STARTER_SET)
def test_offline_parity_gate_green_on_starter_set(path: str) -> None:
    """compile_equivalent(_normalize_ui_to_api(emit_ui_json(wf)), compile('api')) — never
    imports ComfyUI — is green for a >=5 starter set spanning image/video/edit."""
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.ui_emitter import offline_parity_check

    with open(path) as handle:
        raw = json.load(handle)
    wf = convert_to_vibe_format(raw)
    ok, diffs = offline_parity_check(wf, schema_provider=_local_provider())
    assert ok, f"{path}: {diffs[:5]}"


def test_offline_parity_never_imports_comfy() -> None:
    """The offline gate must not import ComfyUI. Build the IR first (ingest itself may
    probe comfy with an ImportError fallback), then poison ``comfy`` imports *only*
    around offline_parity_check and assert it still runs green."""
    import builtins

    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.ui_emitter import offline_parity_check

    with open("workflow_corpus/official/video/wan_t2v.json") as handle:
        raw = json.load(handle)
    wf = convert_to_vibe_format(raw)
    provider = _local_provider()

    real_import = builtins.__import__

    def _poisoned(name, *args, **kwargs):
        if name == "comfy" or name.startswith("comfy."):
            raise AssertionError(f"offline parity gate imported ComfyUI module {name!r}")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = _poisoned
    try:
        ok, diffs = offline_parity_check(wf, schema_provider=provider)
    finally:
        builtins.__import__ = real_import
    assert ok, diffs[:5]


def test_ksampler_none_widget_alignment_roundtrips() -> None:
    """The KSampler None-named slot (control_after_generate) must NOT misalign the
    widget positions after it on round-trip. Exercises the _schema_input_names None-strip
    coupling end-to-end: seed/steps/cfg/sampler_name/scheduler/denoise stay positionally
    correct and parity holds even with a retained control value."""
    from vibecomfy.porting.ui_emitter import offline_parity_check

    wf = _wf()
    node = _ksampler()
    node.metadata["control_after_generate"] = "randomize"
    wf.nodes["1"] = node
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    ui = emit_ui_json(wf)
    ksamp = next(n for n in ui["nodes"] if n["type"] == "KSampler")
    # Values stay aligned to the compacted (None-stripped) schema ordering.
    assert ksamp["widgets_values"] == [5, 20, 7.0, "euler", "normal", 1.0]

    ok, diffs = offline_parity_check(wf)
    assert ok, diffs[:5]


def test_structural_validate_detects_dangling_link() -> None:
    from vibecomfy.porting.ui_emitter import structural_validate

    envelope = {
        "nodes": [{"id": 1, "type": "LoadImage", "inputs": [], "outputs": [{"slot_index": 0}], "widgets_values": []}],
        "links": [[1, 1, 0, 99, 0, "IMAGE"]],  # to_node 99 does not exist
    }
    report = structural_validate(envelope)
    assert report["ok"] is False
    assert any("99" in e for e in report["errors"])


def test_structural_validate_detects_slot_out_of_range() -> None:
    from vibecomfy.porting.ui_emitter import structural_validate

    envelope = {
        "nodes": [
            {"id": 1, "type": "LoadImage", "inputs": [], "outputs": [{"slot_index": 0}], "widgets_values": []},
            {"id": 2, "type": "SaveImage", "inputs": [{"name": "images"}], "outputs": [], "widgets_values": []},
        ],
        "links": [[1, 1, 5, 2, 0, "IMAGE"]],  # from_slot 5 out of range (node 1 has 1 output)
    }
    report = structural_validate(envelope)
    assert report["ok"] is False
    assert any("from_slot 5" in e for e in report["errors"])


def test_structural_validate_skips_schema_less_and_records() -> None:
    """Schema-less nodes skip slot/widget-length assertions and the skip is recorded."""
    from vibecomfy.porting.ui_emitter import structural_validate

    envelope = {
        "nodes": [
            {"id": 1, "type": "TotallyUnknownNode", "inputs": [], "outputs": [], "widgets_values": [1, 2, 3]},
        ],
        "links": [],
    }
    report = structural_validate(envelope, schema_provider=None)
    assert report["ok"] is True
    assert any(s["class_type"] == "TotallyUnknownNode" for s in report["skipped"])


@pytest.mark.parametrize("path", _STARTER_SET)
def test_structural_validate_green_on_starter_set(path: str) -> None:
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.ui_emitter import structural_validate

    with open(path) as handle:
        raw = json.load(handle)
    wf = convert_to_vibe_format(raw)
    provider = _local_provider()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(wf, schema_provider=provider)
    report = structural_validate(ui, schema_provider=provider)
    assert report["ok"], f"{path}: {report['errors'][:5]}"


@pytest.mark.comfy
def test_comfy_release_smoke_convert_ui_to_api() -> None:
    """Release gate (env VIBECOMFY_COMFY_SMOKE=1, real ComfyUI): emit_ui_json output is
    accepted by comfy's convert_ui_to_api. Conflating this with the offline gate is
    forbidden — this is the only path that actually imports ComfyUI."""
    import os

    if os.environ.get("VIBECOMFY_COMFY_SMOKE") != "1":
        pytest.skip("comfy release smoke gate is opt-in (set VIBECOMFY_COMFY_SMOKE=1)")
    comfy_convert = pytest.importorskip(
        "comfy.component_model.workflow_convert"
    ).convert_ui_to_api

    from vibecomfy.ingest.normalize import convert_to_vibe_format

    with open("workflow_corpus/official/video/wan_t2v.json") as handle:
        raw = json.load(handle)
    wf = convert_to_vibe_format(raw)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(wf, schema_provider=_local_provider())
    converted = comfy_convert(ui)
    assert isinstance(converted, dict) and converted


# ---------------------------------------------------------------------------
# T9 — output path derivation + breadcrumb stamping
# ---------------------------------------------------------------------------


def test_default_output_path_from_source_name() -> None:
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.ui_emitter import default_output_path

    with open("workflow_corpus/official/video/wan_t2v.json") as handle:
        raw = json.load(handle)
    wf = convert_to_vibe_format(raw, source_path="workflow_corpus/official/video/wan_t2v.json")
    assert default_output_path(wf).as_posix() == "out/ui_export/wan_t2v.json"


def test_output_path_hash_fallback_for_unnamed_source() -> None:
    """Programmatic IR with no source name → deterministic hash path; never empty/raising."""
    from vibecomfy.porting.ui_emitter import default_output_path

    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    p1 = default_output_path(wf)
    p2 = default_output_path(wf)
    assert p1 == p2  # deterministic
    assert p1.as_posix().startswith("out/ui_export/")
    assert p1.suffix == ".json"
    assert p1.stem  # non-empty


def test_output_path_out_override_wins() -> None:
    from vibecomfy.porting.ui_emitter import default_output_path

    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    assert default_output_path(wf, out="some/dir/custom.json").as_posix() == "some/dir/custom.json"


def test_breadcrumb_stamped_at_top_level_extra() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
    ui = emit_ui_json(wf, schema_provider=provider, source_template="image/z_image", prior_path="orig/path.json")
    crumb = ui["extra"]["vibecomfy"]
    assert crumb == {
        "layout_version": "m1",
        "source_template": "image/z_image",
        "prior_path": "orig/path.json",
    }


def test_breadcrumb_stamped_on_each_subgraph_definition() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    wf.metadata["definitions"] = {
        "subgraphs": [{"id": "sg-uuid", "name": "Sub", "nodes": [], "links": []}]
    }
    provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
    ui = emit_ui_json(wf, schema_provider=provider, source_template="t", prior_path="p.json")
    sg = ui["definitions"]["subgraphs"][0]
    assert sg["extra"]["vibecomfy"] == {
        "layout_version": "m1",
        "source_template": "t",
        "prior_path": "p.json",
    }
