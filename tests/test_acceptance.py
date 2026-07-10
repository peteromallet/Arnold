"""Acceptance smoke tests — end-to-end public knob exercises on ready templates."""
from __future__ import annotations

from vibecomfy import load_workflow_any


def test_acceptance_z_image_public_knobs_validate_compile():
    wf = load_workflow_any("image/z_image")

    wf.set_prompt("a glass teapot on basalt")
    wf.set_seed(42)
    wf.set_steps(20)

    report = wf.validate()
    assert report.ok, f"validate() failed: {[i.message for i in report.issues]}"

    compiled = wf.compile("api")
    assert compiled, "compile('api') returned empty dict"
    # z_image has ≥8 nodes (UNETLoader, CLIPLoader, VAELoader, CLIPTextEncode x2,
    # EmptySD3LatentImage, KSampler, VAEDecode, SaveImage — 9 total as of authoring)
    assert len(compiled) >= 5, f"compiled node count too low: {len(compiled)}"
