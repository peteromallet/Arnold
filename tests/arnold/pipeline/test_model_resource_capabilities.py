from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arnold.pipeline import (
    MODEL_RESOURCE_CAPABILITIES,
    Pipeline,
    Stage,
    StepInvocation,
    prove_invocation_capabilities,
    prove_stage_required_capabilities,
)
from arnold.pipeline.resources import PipelineResourceBundle


@dataclass(frozen=True)
class _StubStep:
    name: str = "stub"
    kind: str = "agent"

    def run(self, ctx: Any) -> Any:
        raise RuntimeError("static capability proof tests must not run steps")


def test_closed_vocabulary_is_limited_to_m7_model_resource_capabilities() -> None:
    assert MODEL_RESOURCE_CAPABILITIES == frozenset(
        {"model:text", "model:vision", "decoder:image"}
    )


def test_invocation_proves_text_and_vision_from_model_adapter_payload() -> None:
    invocation = StepInvocation.model(
        adapter_config={
            "prompt": "describe the diagram",
            "media": [{"mime_type": "image/png", "descriptor": "diagram"}],
        }
    )

    evidence = prove_invocation_capabilities(invocation)

    assert {item.capability for item in evidence} == {"model:text", "model:vision"}
    assert {item.source for item in evidence} == {
        "invocation.model_payload",
        "invocation.media_payload",
    }


def test_invocation_proves_decoder_from_explicit_adapter_capabilities() -> None:
    invocation = StepInvocation.model(
        adapter_config={"capabilities": ["decoder:image", "decoder:audio"]}
    )

    evidence = prove_invocation_capabilities(invocation)

    assert [item.capability for item in evidence] == ["decoder:image"]
    assert evidence[0].source == "invocation.adapter_config"


def test_stage_proof_combines_stage_pipeline_and_resource_bundle_metadata() -> None:
    stage = Stage(
        name="draft",
        step=_StubStep(),
        invocation=StepInvocation.model(metadata={"message": "write a draft"}),
        required_capabilities=("model:text", "decoder:image"),
    )
    pipeline = Pipeline(stages={"draft": stage}, entry="draft")
    object.__setattr__(pipeline, "metadata", {"supported_capabilities": ["decoder:image"]})
    bundle = PipelineResourceBundle(
        base_dir=Path("/tmp/base"),
        prompt_dir=Path("/tmp/base/prompts"),
        resources={"capabilities": ["decoder:image", "decoder:audio"]},
    )
    object.__setattr__(pipeline, "resource_bundles", (bundle,))

    proof = prove_stage_required_capabilities(stage, pipeline)

    assert proof.ok
    assert proof.proven_capabilities == ("model:text", "decoder:image")
    assert proof.unsatisfied_capabilities == ()
    assert proof.unknown_required_capabilities == ()
    assert proof.unknown_provided_capabilities == ("decoder:audio",)
    assert {item.source for item in proof.evidence} == {
        "invocation.model_payload",
        "pipeline.metadata",
        "resource_bundle[0].resources",
    }


def test_stage_proof_fails_closed_for_unknown_and_unproven_capabilities() -> None:
    stage = Stage(
        name="review",
        step=_StubStep(),
        invocation=StepInvocation(kind="tool", metadata={"action": "approve"}),
        required_capabilities=("model:vision", "model:audio"),
    )

    proof = prove_stage_required_capabilities(stage)

    assert not proof.ok
    assert proof.proven_capabilities == ()
    assert proof.unsatisfied_capabilities == ("model:vision",)
    assert proof.unknown_required_capabilities == ("model:audio",)
    assert proof.unknown_provided_capabilities == ()


def test_stage_attr_metadata_proves_capabilities_without_invocation_guessing() -> None:
    class _StageWithMetadata:
        name = "image-review"
        invocation = StepInvocation(kind="tool", metadata={})
        required_capabilities = ("model:vision",)
        capability_metadata = {"modalities": ["vision"], "capabilities": ["unknown:cap"]}

    proof = prove_stage_required_capabilities(_StageWithMetadata())

    assert proof.ok
    assert proof.proven_capabilities == ("model:vision",)
    assert proof.unknown_provided_capabilities == ("unknown:cap",)
