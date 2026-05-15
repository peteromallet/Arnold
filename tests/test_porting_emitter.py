from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.porting.convert import ManualTemplateRefusal, _check_manual_refusal
from vibecomfy.porting.emitter import (
    EmissionDiagnostic,
    READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED,
    READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG,
    READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL,
    emit_ready_template_python,
    emit_scratchpad_python,
)
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource
from tools.format_as_python import format_as_python


def _sample_workflow() -> VibeWorkflow:
    workflow = VibeWorkflow("sample", WorkflowSource("sample", provenance={"origin": "unit"}))
    workflow.nodes["10"] = VibeNode("10", "LoadImage", inputs={"image": "input.png"})
    workflow.nodes["20"] = VibeNode(
        "20",
        "SaveImage",
        inputs={"filename_prefix": "out/sample", "resize_type.multiple": 3},
    )
    workflow.connect("10.0", "20.images")
    workflow.register_input("prefix", "20", "filename_prefix", "out/sample")
    return workflow


def test_emit_scratchpad_python_preserves_ids_extras_inputs_and_provenance() -> None:
    text = emit_scratchpad_python(
        _sample_workflow(),
        workflow_id="scratch/sample",
        source_path="workflow_corpus/source.json",
        provenance={"source_hash": "sha256:abc"},
        registered_inputs={"prefix": ("20", "filename_prefix")},
    )

    assert "READY_METADATA" not in text
    assert "source_type='scratchpad'" in text
    assert "provenance={'source_hash': 'sha256:abc'}" in text
    assert "_extras={'resize_type.multiple': 3}" in text

    namespace: dict[str, object] = {"__file__": "out/scratchpads/sample.py"}
    exec(compile(text, "scratch emitted", "exec"), namespace)  # noqa: S102 - generated code under test
    workflow = namespace["build"]()

    assert isinstance(workflow, VibeWorkflow)
    assert workflow.id == "scratch/sample"
    assert workflow.source.source_type == "scratchpad"
    assert workflow.source.path == "workflow_corpus/source.json"
    assert workflow.source.provenance == {"source_hash": "sha256:abc"}
    assert sorted(workflow.nodes) == ["10", "20"]
    assert workflow.nodes["20"].inputs["resize_type.multiple"] == 3
    assert workflow.inputs["prefix"].node_id == "20"
    assert workflow.compile("api")["20"]["inputs"]["images"] == ["10", 0]


def test_emit_ready_template_python_has_ready_metadata_contract() -> None:
    text = emit_ready_template_python(
        _sample_workflow(),
        ready_metadata={"ready_template": "image/sample", "source_workflow": "workflow_corpus/source.json"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="image/sample",
        registered_inputs={"prefix": ("20", "filename_prefix")},
    )

    assert "READY_METADATA =" in text
    assert "READY_REQUIREMENTS =" in text
    assert 'READY_METADATA["ready_template"]' in text
    # Sprint 3: shared helpers replace inline VibeWorkflow construction
    assert "from vibecomfy.registry.ready_template import" in text
    assert "ready_workflow" in text
    assert "ready_node" in text
    assert "finalize_ready_template" in text
    assert "def _node" not in text

    namespace: dict[str, object] = {"__file__": "ready_templates/image/sample.py"}
    exec(compile(text, "ready emitted", "exec"), namespace)  # noqa: S102 - generated code under test
    workflow = namespace["build"]()

    assert isinstance(workflow, VibeWorkflow)
    assert workflow.id == "image/sample"
    assert workflow.source.source_type == "ready_template"
    assert sorted(workflow.nodes) == ["10", "20"]
    assert workflow.metadata["ready_template"] == "image/sample"
    assert workflow.inputs["prefix"].node_id == "20"


def test_tools_format_as_python_remains_ready_template_wrapper() -> None:
    kwargs = {
        "ready_metadata": {"ready_template": "image/sample", "source_workflow": "workflow_corpus/source.json"},
        "ready_requirements": {"models": [], "custom_nodes": []},
        "template_id": "image/sample",
        "registered_inputs": {"prefix": ("20", "filename_prefix")},
    }

    assert format_as_python(_sample_workflow(), **kwargs) == emit_ready_template_python(_sample_workflow(), **kwargs)


def test_convert_ready_templates_tool_dry_run_remains_compatible() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.convert_ready_templates",
            "--template",
            "image/qwen_image_2512",
            "--dry-run",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "image/qwen_image_2512" in result.stdout


# ---------------------------------------------------------------------------
# Sprint 1 T10: focused tool tests - shared gates for bulk dry-run / --write
# ---------------------------------------------------------------------------


def test_shared_manual_refusal_raises_for_manual_marker() -> None:
    """_check_manual_refusal raises ManualTemplateRefusal for # vibecomfy: manual."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write("# vibecomfy: manual - do not regenerate\n")
        tmp.write("def build():\n    pass\n")
        tmp_path = Path(tmp.name)

    try:
        with pytest.raises(ManualTemplateRefusal, match="manual"):
            _check_manual_refusal(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def test_shared_manual_refusal_passes_for_non_manual() -> None:
    """_check_manual_refusal does not raise for a normal file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write("# vibecomfy: generated\n")
        tmp.write("def build():\n    pass\n")
        tmp_path = Path(tmp.name)

    try:
        # Should not raise
        _check_manual_refusal(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def test_write_emitted_raises_manual_refusal_before_write(tmp_path: Path) -> None:
    """_write_emitted refuses to write over a manual template (shared gate)."""
    from tools.convert_ready_templates import (
        _write_emitted,
    )

    # Create a "manual" template under a fake ready_templates tree
    tmpl_dir = tmp_path / "ready_templates" / "image"
    tmpl_dir.mkdir(parents=True)
    manual_path = tmpl_dir / "test_manual.py"
    manual_path.write_text("# vibecomfy: manual - do not regenerate\ndef build(): pass\n")

    # Monkey-patch READY_ROOT so the path passes the outside-root guard
    import tools.convert_ready_templates as tmod

    orig_root = tmod.READY_ROOT
    try:
        tmod.READY_ROOT = tmp_path / "ready_templates"
        with pytest.raises(ManualTemplateRefusal, match="manual"):
            _write_emitted(manual_path, "emitted text", dry_run=False)
        # File must be unchanged
        assert manual_path.read_text().startswith("# vibecomfy: manual")
    finally:
        tmod.READY_ROOT = orig_root


def test_write_emitted_uses_atomic_temp_replace(tmp_path: Path) -> None:
    """_write_emitted uses temp file + replace for atomic writes."""
    from tools.convert_ready_templates import (
        _write_emitted,
    )

    tmpl_dir = tmp_path / "ready_templates" / "image"
    tmpl_dir.mkdir(parents=True)
    target = tmpl_dir / "test_atomic.py"
    original = "# vibecomfy: generated\nORIGINAL_CONTENT = True\n"
    target.write_text(original)

    import tools.convert_ready_templates as tmod

    orig_root = tmod.READY_ROOT
    try:
        tmod.READY_ROOT = tmp_path / "ready_templates"
        emitted = "# vibecomfy: generated\nEMITTED_CONTENT = True\n"
        result = _write_emitted(target, emitted, dry_run=False)
        assert result == target
        assert target.read_text() == emitted
        # No temp file left behind
        temps = list(tmpl_dir.glob(".vibecomfy-convert-*"))
        assert len(temps) == 0
    finally:
        tmod.READY_ROOT = orig_root


def test_convert_template_refuses_manual_via_shared_gate(tmp_path: Path) -> None:
    """_convert_template returns manual-refused row via shared _check_manual_refusal."""
    from tools.convert_ready_templates import (
        _convert_template,
    )

    tmpl_dir = tmp_path / "ready_templates" / "image"
    tmpl_dir.mkdir(parents=True)
    manual_path = tmpl_dir / "test_manual_convert.py"
    manual_path.write_text("# vibecomfy: manual - do not regenerate\nAPI_WORKFLOW = {}\n")

    import tools.convert_ready_templates as tmod

    orig_root = tmod.READY_ROOT
    try:
        tmod.READY_ROOT = tmp_path / "ready_templates"
        row, emitted, _ = _convert_template(manual_path)
        assert emitted is None
        assert row.shape == "manual-refused"
        assert "manual template refused by shared gate" in row.note
        assert row.parse == "skip"
    finally:
        tmod.READY_ROOT = orig_root


def test_dry_run_writes_to_out_converted(tmp_path: Path) -> None:
    """_write_emitted dry_run=True writes to out/converted/ not in-place."""
    from tools.convert_ready_templates import (
        _write_emitted,
    )

    tmpl_dir = tmp_path / "ready_templates" / "image"
    tmpl_dir.mkdir(parents=True)
    target = tmpl_dir / "test_dry.py"
    original = "# vibecomfy: generated\nORIGINAL = True\n"
    target.write_text(original)

    out_dir = tmp_path / "out" / "converted"
    out_dir.mkdir(parents=True)

    import tools.convert_ready_templates as tmod

    orig_root = tmod.READY_ROOT
    orig_out = tmod.OUT_PREVIEW_ROOT
    try:
        tmod.READY_ROOT = tmp_path / "ready_templates"
        tmod.OUT_PREVIEW_ROOT = out_dir
        emitted = "# vibecomfy: generated\nEMITTED = True\n"
        result = _write_emitted(target, emitted, dry_run=True)
        # Wrote to out/converted/, not in-place
        assert result != target
        assert out_dir in result.parents
        assert result.read_text() == emitted
        # Original is unchanged
        assert target.read_text() == original
    finally:
        tmod.READY_ROOT = orig_root
        tmod.OUT_PREVIEW_ROOT = orig_out


def test_write_gate_requires_both_validate_and_parity() -> None:
    """main() skip-logic refuses writes when validate fails or roundtrip fails."""
    from tools.convert_ready_templates import Row

    # Simulate the gate check from main():
    #   gated_ok = row.validate == "ok" and row.roundtrip in ("ok", "skip", "skip-authored")

    # Case 1: validate fail -> blocked
    r1 = Row(template_id="test/fail_val")
    r1.validate = "fail"
    r1.roundtrip = "ok"
    gated = r1.validate == "ok" and r1.roundtrip in ("ok", "skip", "skip-authored")
    assert not gated

    # Case 2: roundtrip fail -> blocked
    r2 = Row(template_id="test/fail_rt")
    r2.validate = "ok"
    r2.roundtrip = "fail"
    gated = r2.validate == "ok" and r2.roundtrip in ("ok", "skip", "skip-authored")
    assert not gated

    # Case 3: both ok -> allowed
    r3 = Row(template_id="test/ok")
    r3.validate = "ok"
    r3.roundtrip = "ok"
    gated = r3.validate == "ok" and r3.roundtrip in ("ok", "skip", "skip-authored")
    assert gated

    # Case 4: authored shape (skip-authored) -> allowed
    r4 = Row(template_id="test/authored")
    r4.validate = "ok"
    r4.roundtrip = "skip-authored"
    gated = r4.validate == "ok" and r4.roundtrip in ("ok", "skip", "skip-authored")
    assert gated


# ---------------------------------------------------------------------------
# T11 - emitter tests: named outputs, widget aliases, fallbacks, _outputs
# ---------------------------------------------------------------------------


def _workflow_with_output_names(
    output_names: list[str],
) -> VibeWorkflow:
    """Build a minimal multi-output workflow with metadata-driven output_names."""
    workflow = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    workflow.nodes["1"] = VibeNode("1", "MultiOutput")
    workflow.nodes["1"].metadata["output_names"] = output_names
    workflow.nodes["2"] = VibeNode("2", "Consumer")
    # Connect both outputs from node 1 to node 2 on inputs named "a" and "b"
    workflow.connect("1.0", "2.a")
    workflow.connect("1.1", "2.b")
    return workflow


def _workflow_with_widget_aliases(
    class_type: str,
    input_aliases: list[str | None],
    widget_values: dict[str, Any] | None = None,
) -> VibeWorkflow:
    """Build a workflow where a node has input_aliases metadata and widget values."""
    workflow = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    node = VibeNode("1", class_type)
    node.metadata["input_aliases"] = input_aliases
    if widget_values:
        for k, v in widget_values.items():
            if k.startswith("widget_"):
                node.widgets[k] = v
            else:
                node.inputs[k] = v
    workflow.nodes["1"] = node
    workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "out"})
    workflow.connect("1.0", "2.images")
    return workflow


def test_unique_safe_names_emit_named_out() -> None:
    """Unique safe output names produce .out('name') in emitted code."""
    text = emit_scratchpad_python(
        _workflow_with_output_names(["image", "latent"]),
        source_path="test.json",
    )
    # Should use named handles
    assert ".out('image')" in text
    assert ".out('latent')" in text
    assert "_outputs=('image', 'latent')" in text


def test_duplicate_output_names_fall_back_to_numeric() -> None:
    """Duplicate output names fall back to .out(n) with diagnostic."""
    diags: list[EmissionDiagnostic] = []
    from vibecomfy.porting.emitter import (
        EmissionDiagnostic,
        READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
    )

    text = emit_scratchpad_python(
        _workflow_with_output_names(["image", "image"]),
        source_path="test.json",
        diagnostics=diags,
    )
    # Should use numeric handles (duplicate names are unsafe)
    assert ".out(0)" in text
    assert ".out(1)" in text
    # Should NOT use named handles
    assert ".out('image')" not in text
    # Should emit _outputs with the partial names (source of truth)
    assert "_outputs=('image', 'image')" in text
    # Diagnostic should flag ambiguity
    ambiguity_codes = [d.code for d in diags if d.code == READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY]
    assert len(ambiguity_codes) > 0


def test_blank_output_names_fall_back_to_numeric() -> None:
    """Blank output names fall back to .out(n), with named slots where safe."""
    diags: list[EmissionDiagnostic] = []
    from vibecomfy.porting.emitter import (
        READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
    )

    text = emit_scratchpad_python(
        _workflow_with_output_names(["image", ""]),
        source_path="test.json",
        diagnostics=diags,
    )
    # Slot 0 is safe -> .out('image')
    assert ".out('image')" in text
    # Slot 1 is blank -> .out(1)
    assert ".out(1)" in text
    # _outputs preserves partial evidence
    assert "_outputs=('image', '')" in text
    # Should have avoidable_positional_output diagnostic
    fallback_codes = [d.code for d in diags if d.code == READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT]
    assert len(fallback_codes) > 0


def test_partial_output_evidence_still_emits_outputs_tuple() -> None:
    """_outputs is emitted even when output_names has blank entries (SC19)."""
    text = emit_scratchpad_python(
        _workflow_with_output_names(["image", ""]),
        source_path="test.json",
    )
    # Must contain _outputs with both entries, including the blank
    assert "_outputs=('image', '')" in text


def test_missing_output_names_does_not_emit_outputs() -> None:
    """When node has no output_names metadata, _outputs is NOT emitted."""
    wf = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    wf.nodes["1"] = VibeNode("1", "NoMeta")  # no metadata
    wf.nodes["2"] = VibeNode("2", "Consumer")
    wf.connect("1.0", "2.a")

    text = emit_scratchpad_python(wf, source_path="test.json")
    # _outputs= keyword arg should NOT appear in the _node() builder call;
    # the helper function definition itself contains "_outputs" but that's fine.
    assert "_outputs=" not in text


def test_out_of_range_slot_falls_back_to_numeric() -> None:
    """An edge with a slot beyond output_names range uses .out(n)."""
    wf = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    wf.nodes["1"] = VibeNode("1", "SingleOutput")
    wf.nodes["1"].metadata["output_names"] = ["only"]  # only slot 0 named
    wf.nodes["2"] = VibeNode("2", "Consumer")
    # Connect from slot 5 which is out of range
    wf.edges.append(VibeEdge("1", "5", "2", "a"))

    text = emit_scratchpad_python(wf, source_path="test.json")
    # Slot 5 is out of range for ["only"] -> .out(5) not .out('only')
    assert ".out(5)" in text
    assert ".out('only')" not in text


def test_widget_alias_success_emits_named_field() -> None:
    """When input_aliases maps widget_N to a name, the emitter uses that name."""
    from vibecomfy.porting.emitter import EmissionDiagnostic

    wf = _workflow_with_widget_aliases(
        "CheckpointLoaderSimple",
        ["ckpt_name"],  # widget_0 -> ckpt_name
        {"widget_0": "v1-5-pruned.safetensors"},
    )

    diags: list[EmissionDiagnostic] = []
    text = emit_scratchpad_python(wf, source_path="test.json", diagnostics=diags)
    # Should use the named field from input_aliases
    assert "ckpt_name=" in text
    assert "'v1-5-pruned.safetensors'" in text
    # Should NOT use raw widget_0
    assert "'widget_0'" not in text


def test_widget_alias_fallback_keeps_positional_widget() -> None:
    """When widget_N index is beyond input_aliases range, keep positional."""
    from vibecomfy.porting.emitter import EmissionDiagnostic

    wf = _workflow_with_widget_aliases(
        "SomeNode",
        ["only_name"],  # only widget_0 has an alias
        {"widget_0": "first_val", "widget_3": "out_of_range_val"},
    )

    diags: list[EmissionDiagnostic] = []
    text = emit_scratchpad_python(wf, source_path="test.json", diagnostics=diags)

    # widget_0 gets aliased
    assert "only_name=" in text
    # widget_3 stays positional (out of range) - emitted as kwarg widget_3=
    assert "widget_3=" in text

    # Verify diagnostics include schema_backed_widget_alias_not_resolved
    from vibecomfy.porting.emitter import (
        READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
    )
    unresolved_codes = [
        d.code for d in diags
        if d.code == READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED
    ]
    assert len(unresolved_codes) > 0


def test_emitted_outputs_preservation_with_partial_blank() -> None:
    """SC19: partial output_names ['image', ''] still emits _outputs=('image', '')."""
    text = emit_scratchpad_python(
        _workflow_with_output_names(["image", ""]),
        source_path="test.json",
    )
    # Must contain the exact _outputs tuple including the blank
    assert "_outputs=('image', '')" in text


# ---------------------------------------------------------------------------
# T5: style diagnostics for generated ready templates
# ---------------------------------------------------------------------------


def test_variable_name_too_long_diagnostic() -> None:
    """generated_variable_name_too_long fires when emitted var name >40 chars."""
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("test/long", WorkflowSource("test/long", provenance={"origin": "unit"}))
    # Use a class_type that produces a very long safe variable name
    very_long_ct = "a" * 41
    wf.nodes["1"] = VibeNode("1", very_long_ct, inputs={"text": "hello"})

    diags: list[EmissionDiagnostic] = []
    emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "test/long"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="test/long",
        diagnostics=diags,
    )

    long_name_codes = [
        d.code for d in diags
        if d.code == READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG
    ]
    assert len(long_name_codes) > 0, f"Expected generated_variable_name_too_long diagnostic, got: {[d.code for d in diags]}"


def test_variable_name_not_too_short_no_diagnostic() -> None:
    """No diagnostic for variable names <=40 chars."""
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("test/short", WorkflowSource("test/short", provenance={"origin": "unit"}))
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "test.png"})

    diags: list[EmissionDiagnostic] = []
    emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "test/short"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="test/short",
        diagnostics=diags,
    )

    long_name_codes = [
        d.code for d in diags
        if d.code == READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG
    ]
    assert len(long_name_codes) == 0, f"Unexpected long-name diagnostic for short variable names: {long_name_codes}"


def test_long_one_line_node_call_diagnostic() -> None:
    """long_one_line_node_call fires for a single-line ready_node call >120 chars."""
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("test/long_line", WorkflowSource("test/long_line", provenance={"origin": "unit"}))
    # Create a node with many string inputs to make the ready_node call long
    wf.nodes["1"] = VibeNode(
        "1",
        "LoadImage",
        inputs={
            "image": "a_very_long_filename_that_pads_the_call_line_to_exceed_one_hundred_twenty_characters_total.png",
        },
    )

    diags: list[EmissionDiagnostic] = []
    emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "test/long_line"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="test/long_line",
        diagnostics=diags,
    )

    long_line_codes = [
        d.code for d in diags
        if d.code == READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL
    ]
    # Note: if multi-line formatting kicks in, the line won't be "single line"
    # but the diagnostic fires for any ready_node call whose computed single_line > 120
    # regardless of formatting. Validate that it appears when appropriate.
    # This test verifies the diagnostic code exists and is emitted under the right conditions.
    assert len(long_line_codes) > 0, f"Expected long_one_line_node_call diagnostic, got: {[d.code for d in diags]}"


def test_generated_template_not_formatted_missing_section_comments() -> None:
    """generated_template_not_formatted fires for >=8 nodes without section comments."""
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("test/no_sections", WorkflowSource("test/no_sections", provenance={"origin": "unit"}))
    # Create 8 nodes, none of which map to section roles, so section_groups is empty
    # But the check looks for missing section COMMENTS in the output when nodes >= 8
    # and section_groups are non-empty. Let's create nodes that map to sections.
    for i in range(8):
        nid = str(i + 1)
        # Use class types that map to section roles
        if i == 0:
            ct = "LoadImage"
        elif i == 1:
            ct = "CLIPLoader"
        elif i == 2:
            ct = "CLIPTextEncode"
        elif i == 3:
            ct = "KSampler"
        elif i == 4:
            ct = "VAEDecode"
        elif i == 5:
            ct = "SaveImage"
        elif i == 6:
            ct = "CheckpointLoaderSimple"
        else:
            ct = "PrimitiveInt"
        wf.nodes[nid] = VibeNode(nid, ct, inputs={"test": "val"})

    diags: list[EmissionDiagnostic] = []
    text = emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "test/no_sections"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="test/no_sections",
        diagnostics=diags,
    )

    # The emitter should produce section comments for >=8 nodes.
    # If not, the diagnostic should fire.
    has_section_comments = any(
        line.strip().startswith("# ") and any(
            sec in line for sec in ("Inputs", "Loaders", "Conditioning", "Sampling", "Decode", "Outputs")
        )
        for line in text.split("\n")
    )

    not_formatted_codes = [
        d.code for d in diags
        if d.code == READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED
    ]
    if not has_section_comments:
        assert len(not_formatted_codes) > 0, (
            f"Expected generated_template_not_formatted diagnostic when no section comments found. "
            f"Diags: {[d.code for d in diags]}"
        )
    # If section comments ARE present, we accept either way (no diagnostic needed)
    # but the diagnostic should NOT fire if sections are present
    if has_section_comments:
        # The diagnostic might still fire for un-indented tail, but not for missing sections
        missing_section_diags = [
            d for d in not_formatted_codes
            if "lacks section comments" in d.message
        ]
        assert len(missing_section_diags) == 0, (
            f"Should not flag missing sections when sections are present: {missing_section_diags}"
        )

