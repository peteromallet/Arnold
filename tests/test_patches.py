from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from vibecomfy.patches.registry import find_applicable, register, registered_patches
from vibecomfy.patches.ltx_lowvram import COMFY_CONFIGURATION, patch as ltx_lowvram
from vibecomfy.patches.requirements import ensure_custom_nodes
from vibecomfy.patches.types import Patch
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def test_patch_package_import_does_not_register_builtins() -> None:
    script = """
import vibecomfy.patches
from vibecomfy.patches.registry import _PATCHES, bootstrap_builtin_patches, registered_patches

print(",".join(sorted(_PATCHES)))
print(",".join(sorted(patch.name for patch in bootstrap_builtin_patches())))
print(",".join(sorted(_PATCHES)))
print(",".join(sorted(patch.name for patch in registered_patches())))
"""
    env = {**os.environ, "PYTHONPATH": str(Path.cwd())}
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
    )

    before_bootstrap, builtin_names, after_bootstrap, registered_names = result.stdout.splitlines()
    assert before_bootstrap == ""
    assert builtin_names == "controlnet,gguf_unet,ltx_lowvram"
    assert after_bootstrap == ""
    assert registered_names == builtin_names


def test_find_applicable_uses_builtin_tuple_and_external_registry() -> None:
    workflow = VibeWorkflow("patch-registry-test", WorkflowSource("patch-registry-test"))
    external = Patch("external", lambda candidate: candidate is workflow, lambda candidate: candidate, lambda _: "test")

    register(external)

    assert external in registered_patches(include_builtins=False)
    assert external in find_applicable(workflow)


def test_ensure_custom_nodes_appends_without_duplicates() -> None:
    workflow = VibeWorkflow("requirements-test", WorkflowSource("requirements-test"))
    workflow.requirements.custom_nodes.append("Existing")

    ensure_custom_nodes(workflow, ("Existing", "New"))
    ensure_custom_nodes(workflow, ("New",))

    assert workflow.requirements.custom_nodes == ["Existing", "New"]


def test_ltx_lowvram_applies_to_positive_negative_and_policy_diff() -> None:
    positive = VibeWorkflow("ltx", WorkflowSource("ltx"))
    positive.add_node("LTXVLoader")
    positive.nodes["4010"] = VibeNode(id="4010", class_type="AudioVAELoader", widgets={"widget_0": "old.safetensors"})
    positive.nodes["3940"] = VibeNode(id="3940", class_type="CheckpointLoader", widgets={"widget_0": "old.safetensors"})
    positive.metadata["ready_template"] = "video/ltx2_3_t2v"

    negative = VibeWorkflow("plain", WorkflowSource("plain"))
    negative.add_node("SaveImage", images="placeholder")

    assert ltx_lowvram.applies_to(positive)
    assert not ltx_lowvram.applies_to(negative)

    ltx_lowvram.apply(positive)

    assert positive.metadata["comfy_configuration"] == COMFY_CONFIGURATION
    assert positive.metadata["smoke_resolution"] == "384x256x9_frames"
    assert positive.metadata["external_python_marker"] == "external_python:video/ltx2_3_t2v"
    assert positive.nodes["4010"].class_type == "LowVRAMAudioVAELoader"
    assert positive.nodes["3940"].class_type == "LowVRAMCheckpointLoader"
    assert "ComfyUI-LTXVideo" in positive.requirements.custom_nodes
