from __future__ import annotations

"""Semantic contract for the LTX 2.3 first/last parity workflow.

The contract validates the workflow through the VibeComfy lens instead of raw
Comfy API node-id assertions.  It intentionally tracks app-visible behavior:
dedicated distilled checkpoint, first/last image guide wiring, prompt and
negative paths, dimensions, frame count, FPS, strengths, and video output.
"""

from typing import Any

from vibecomfy.contracts.validation import ContractReport
from vibecomfy.lens.core import WorkflowLens
from vibecomfy.workflow import VibeWorkflow

_DISTILLED_CHECKPOINT = "ltx-2.3-22b-distilled-fp8.safetensors"
_SIGMAS = "1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"

_EXPECTED_INPUTS = frozenset(
    {
        "prompt",
        "negative_prompt",
        "seed",
        "seed_first",
        "seed_last",
        "width",
        "height",
        "frames",
        "fps",
        "fps_int",
        "first_strength",
        "last_strength",
        "first_image",
        "last_image",
        "model",
    }
)

_EXPECTED_INPUT_TARGETS = {
    "prompt": ("130", "text"),
    "negative_prompt": ("127", "text"),
    "seed": ("99", "noise_seed"),
    "seed_first": ("99", "noise_seed"),
    "seed_last": ("99", "noise_seed"),
    "width": ("113", "value"),
    "height": ("98", "value"),
    "frames": ("102", "value"),
    "fps": ("123", "value"),
    "fps_int": ("114", "value"),
    "first_strength": ("136", "strength"),
    "last_strength": ("137", "strength"),
    "first_image": ("1", "image"),
    "last_image": ("2", "image"),
    "model": ("125", "ckpt_name"),
}

_CHECKPOINT_NODES = ("103", "125")
_GUIDE_NODES = {"first_strength": "136", "last_strength": "137"}
_DISALLOWED_RAW_JSON_DRIFT_NODES = frozenset(
    {
        "LTXICLoRALoaderModelOnly",
        "LTXAddVideoICLoRAGuide",
        "LTX2MemoryEfficientSageAttentionPatch",
        "LTX2SamplingPreviewOverride",
        "PathchSageAttentionKJ",
    }
)
_DISALLOWED_CUSTOM_NODE_PACKS = frozenset({"rgthree-comfy"})


class LTXFirstLastTwoStageContract:
    """Contract for the app's LTX 2.3 first/last parity route.

    The historical name is kept for CLI compatibility.  The active parity route
    uses the official distilled fp8 first/last workflow rather than the older
    dev-checkpoint two-stage template because that better matches the Wan2GP
    distilled model path on 24GB GPUs.
    """

    def __init__(self, workflow: VibeWorkflow) -> None:
        self._workflow = workflow
        self._lens = WorkflowLens(workflow)

    def validate(self) -> ContractReport:
        report = ContractReport(contract_name="ltx-first-last-two-stage", passed=True)
        self._check_named_inputs(report)
        self._check_distilled_checkpoint(report)
        self._check_first_last_guides(report)
        self._check_prompt_negative_paths(report)
        self._check_dimensions_frames_fps(report)
        self._check_sampler(report)
        self._check_video_output(report)
        self._check_no_incompatible_nodes(report)
        return report

    def _check_named_inputs(self, report: ContractReport) -> None:
        actual = set(self._workflow.inputs.keys())
        missing = _EXPECTED_INPUTS - actual
        if missing:
            report.add(
                "missing_named_inputs",
                f"Missing named inputs: {sorted(missing)}",
                detail={"expected": sorted(_EXPECTED_INPUTS), "actual": sorted(actual), "missing": sorted(missing)},
            )
        for name, (expected_node_id, expected_field) in _EXPECTED_INPUT_TARGETS.items():
            target = self._lens.registered_input_target(name)
            if target is None:
                continue
            if target.node_id != expected_node_id or target.field != expected_field:
                report.add(
                    "wrong_named_input_target",
                    f"Named input {name!r} targets {target.node_id}.{target.field}, "
                    f"expected {expected_node_id}.{expected_field}",
                    detail={
                        "input": name,
                        "actual_node_id": target.node_id,
                        "actual_field": target.field,
                        "expected_node_id": expected_node_id,
                        "expected_field": expected_field,
                    },
                )

    def _check_distilled_checkpoint(self, report: ContractReport) -> None:
        for node_id in _CHECKPOINT_NODES:
            node = self._lens.node(node_id)
            if node is None:
                report.add("missing_distilled_loader", f"Missing distilled loader node {node_id}.")
                continue
            ckpt_name = self._lens.node_value(node_id, "ckpt_name")
            if ckpt_name != _DISTILLED_CHECKPOINT:
                report.add(
                    "wrong_distilled_checkpoint",
                    f"Node {node_id} uses {ckpt_name!r}, expected {_DISTILLED_CHECKPOINT!r}.",
                    detail={"node_id": node_id, "actual": ckpt_name, "expected": _DISTILLED_CHECKPOINT},
                )

    def _check_first_last_guides(self, report: ContractReport) -> None:
        for label, node_id in _GUIDE_NODES.items():
            node = self._lens.node(node_id)
            if node is None:
                report.add(f"missing_{label}_guide", f"Missing LTXVAddGuide node {node_id}.")
                continue
            if node.class_type != "LTXVAddGuide":
                report.add(
                    f"wrong_{label}_guide_class_type",
                    f"Node {node_id} has class_type {node.class_type!r}, expected LTXVAddGuide.",
                    detail={"node_id": node_id, "actual_class_type": node.class_type},
                )
            strength = self._lens.node_value(node_id, "strength")
            if strength is not None and not (0 <= float(strength) <= 1):
                report.add(
                    f"{label}_out_of_range",
                    f"Node {node_id} guide strength is {strength!r}; expected Wan2GP range [0, 1].",
                    detail={"node_id": node_id, "actual": strength},
                )

        first_latent = self._lens.edge_source("136", "latent")
        if first_latent is None or first_latent.node_id != "135":
            report.add(
                "wrong_first_guide_latent_source",
                "First LTXVAddGuide.latent must consume EmptyLTXVLatentVideo.",
                detail={"expected_source_node_id": "135", "actual_source_node_id": getattr(first_latent, "node_id", None)},
            )
        last_latent = self._lens.edge_source("137", "latent")
        if last_latent is None or last_latent.node_id != "136":
            report.add(
                "wrong_last_guide_latent_source",
                "Last LTXVAddGuide.latent must consume the first guide output.",
                detail={"expected_source_node_id": "136", "actual_source_node_id": getattr(last_latent, "node_id", None)},
            )

        guider_model = self._lens.edge_source("138", "model")
        if guider_model is None or guider_model.node_id != "125":
            report.add(
                "wrong_guider_model_source",
                "CFGGuider.model must consume the distilled checkpoint directly in the portable parity profile.",
                detail={"expected_source_node_id": "125", "actual_source_node_id": getattr(guider_model, "node_id", None)},
            )

        for node_id, field in (("138", "positive"), ("138", "negative")):
            source = self._lens.edge_source(node_id, field)
            if source is None or source.node_id != "137":
                report.add(
                    "wrong_last_guide_conditioning_consumer",
                    f"{node_id}.{field} must consume conditioning from last guide node 137.",
                    detail={"node_id": node_id, "field": field, "actual_source_node_id": getattr(source, "node_id", None)},
                )

    def _check_prompt_negative_paths(self, report: ContractReport) -> None:
        for node_id, label in [("130", "prompt"), ("127", "negative")]:
            node = self._lens.node(node_id)
            if node is None:
                report.add(f"missing_{label}_encode", f"Missing {label} CLIPTextEncode node {node_id}.")
                continue
            if node.class_type != "CLIPTextEncode":
                report.add(
                    f"wrong_{label}_encode_class_type",
                    f"Node {node_id} has class_type {node.class_type!r}, expected CLIPTextEncode.",
                    detail={"node_id": node_id, "actual_class_type": node.class_type},
                )
            clip_src = self._lens.edge_source(node_id, "clip")
            if clip_src is None or clip_src.node_id != "103":
                report.add(
                    f"wrong_{label}_clip_source",
                    f"Node {node_id} clip input must be fed by LTXAVTextEncoderLoader.",
                    detail={"node_id": node_id, "actual_source_node_id": getattr(clip_src, "node_id", None)},
                )

    def _check_dimensions_frames_fps(self, report: ContractReport) -> None:
        for node_id, class_type, label in [
            ("113", "PrimitiveInt", "width"),
            ("98", "PrimitiveInt", "height"),
            ("102", "PrimitiveInt", "frames"),
            ("114", "PrimitiveInt", "fps_int"),
            ("123", "PrimitiveFloat", "fps"),
            ("135", "EmptyLTXVLatentVideo", "latent_video"),
        ]:
            node = self._lens.node(node_id)
            if node is None:
                report.add(f"missing_{label}_node", f"Missing {class_type} node {node_id}.")
            elif node.class_type != class_type:
                report.add(
                    f"wrong_{label}_class_type",
                    f"Node {node_id} has class_type {node.class_type!r}, expected {class_type}.",
                    detail={"node_id": node_id, "actual_class_type": node.class_type},
                )

        for resize_id in ("128", "129"):
            node = self._lens.node(resize_id)
            if node is None:
                report.add("missing_resize_node", f"Missing ResizeImageMaskNode {resize_id}.")
            elif node.class_type != "ResizeImageMaskNode":
                report.add(
                    "wrong_resize_class_type",
                    f"Node {resize_id} has class_type {node.class_type!r}, expected ResizeImageMaskNode.",
                    detail={"node_id": resize_id, "actual_class_type": node.class_type},
                )

    def _check_sampler(self, report: ContractReport) -> None:
        sampler = self._lens.node("140")
        if sampler is None:
            report.add("missing_sampler", "Missing SamplerCustomAdvanced node 140.")
        elif sampler.class_type != "SamplerCustomAdvanced":
            report.add("wrong_sampler_class_type", f"Node 140 has class_type {sampler.class_type!r}.")

        sigmas = self._lens.node("116")
        if sigmas is None:
            report.add("missing_sigmas", "Missing ManualSigmas node 116.")
            return
        value = self._lens.node_value("116", "sigmas") or self._lens.node_value("116", "widget_0")
        if value is not None and str(value).replace(" ", "") != _SIGMAS.replace(" ", ""):
            report.add(
                "wrong_sigmas_value",
                f"ManualSigmas value is {value!r}, expected {_SIGMAS!r}.",
                severity="warning",
                detail={"actual": str(value), "expected": _SIGMAS},
            )

        crop = self._lens.node("142")
        if crop is None:
            report.add("missing_ltx_crop_guides", "Missing LTXVCropGuides node 142 between sampled latent and video decode.")
        elif crop.class_type != "LTXVCropGuides":
            report.add("wrong_ltx_crop_guides_class_type", f"Node 142 has class_type {crop.class_type!r}.")

        decode_samples = self._lens.edge_source("144", "samples")
        if decode_samples is None or decode_samples.node_id != "142" or decode_samples.output_slot != 2:
            report.add(
                "wrong_decode_samples_source",
                "VAEDecodeTiled.samples must consume LTXVCropGuides latent output 2.",
                detail={
                    "expected_source_node_id": "142",
                    "expected_output_slot": 2,
                    "actual_source_node_id": getattr(decode_samples, "node_id", None),
                    "actual_output_slot": getattr(decode_samples, "output_slot", None),
                },
            )

    def _check_video_output(self, report: ContractReport) -> None:
        video_outputs = [o for o in self._workflow.outputs if o.output_type == "SaveVideo"]
        if not video_outputs:
            report.add(
                "missing_savevideo_output",
                "No SaveVideo output detected; workflow must materialize a video output.",
                detail={"outputs": [(o.node_id, o.output_type) for o in self._workflow.outputs]},
            )

    def _check_no_incompatible_nodes(self, report: ContractReport) -> None:
        found: list[str] = []
        for node_id, node in self._workflow.nodes.items():
            if node.class_type in _DISALLOWED_RAW_JSON_DRIFT_NODES:
                found.append(f"{node.class_type}:{node_id}")
        if found:
            report.add(
                "incompatible_nodes_present",
                f"Incompatible nodes present: {sorted(found)}",
                detail={"found": sorted(found), "disallowed": sorted(_DISALLOWED_RAW_JSON_DRIFT_NODES)},
            )

        actual_cn = set(self._workflow.requirements.custom_nodes)
        bad_cn = actual_cn & _DISALLOWED_CUSTOM_NODE_PACKS
        if bad_cn:
            report.add(
                "incompatible_custom_nodes_declared",
                f"Incompatible custom node packs declared: {sorted(bad_cn)}",
                detail={"found": sorted(bad_cn)},
            )
