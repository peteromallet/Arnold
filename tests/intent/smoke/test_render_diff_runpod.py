"""GPU smoke test for compare_rendered / run_and_collect.

This test is marked with the existing ``runpod`` marker so it is excluded from
CI (``pytest -m intent_ci tests/intent``).  It is exercised under a
runpod-marked test — rather than a local intent_ci test — for marker-deselection
consistency with the rest of the GPU test suite: the embedded runtime is run on
a provisioned RunPod GPU pod, ensuring the full execution path (CUDA, model
loading, ComfyUI queue) is exercised.

Nondeterminism note
-------------------
The following corpus workflows use ancestral or SDE samplers and remain
nondeterministic even when seeds are fixed:

- wan_* workflows (WanVideo): KSampler with euler_ancestral or
  dpm++_2m_sde variants — ancestral SDE schedules introduce per-step
  stochasticity beyond the initial seed.
- ltx_* workflows (LTX-2.3): SamplerCustomAdvanced with SamplerLCMCycle or
  similar schedules — internal stochastic steps are not fully seeded by
  the noise_seed alone.

Callers using compare_rendered against these families should widen the
threshold (e.g. threshold=32) or run multiple trials and take a median.
"""

import pytest

pytestmark = pytest.mark.runpod


@pytest.mark.runpod
def test_compare_rendered_detects_difference():
    """compare_rendered returns equal_within_tolerance=False for pre vs post edit.

    Uses the image/z_image template with a seed-change edit as a minimal
    structural change.  With seed fixed to 0, two runs of the same workflow
    should produce identical or very-close outputs (distance ≈ 0).  A
    structurally different post-workflow (different sampler seed) should
    yield a nonzero distance.
    """
    from vibecomfy import load_workflow_any
    from vibecomfy.intent.render_diff import compare_rendered, fix_seeds_in_ir

    pre_wf = load_workflow_any("image/z_image")
    # Post: change the seed so the rendered output differs visually.
    post_wf = fix_seeds_in_ir(pre_wf, seed=99999)

    report = compare_rendered(pre_wf, post_wf, seed=0)

    assert report.pre_outputs, "pre run must produce at least one output"
    assert report.post_outputs, "post run must produce at least one output"
    # Two different seeds should produce visually distinct images.
    assert not report.equal_within_tolerance, (
        f"expected pre != post for different seeds but distance={report.distance}"
    )


@pytest.mark.runpod
def test_compare_rendered_same_workflow_equal():
    """compare_rendered returns equal_within_tolerance=True for identical workflows.

    Two runs of the exact same workflow with the same fixed seed should produce
    perceptually identical outputs (distance ≤ default threshold of 8).
    Nondeterministic samplers (ancestral/SDE) are avoided here by using the
    z_image template whose default sampler is euler (deterministic).
    """
    import copy

    from vibecomfy import load_workflow_any
    from vibecomfy.intent.render_diff import compare_rendered

    wf = load_workflow_any("image/z_image")
    wf_copy = copy.deepcopy(wf)

    report = compare_rendered(wf, wf_copy, seed=42)

    assert report.equal_within_tolerance, (
        f"identical workflow + seed should produce equal outputs but distance={report.distance}"
    )
