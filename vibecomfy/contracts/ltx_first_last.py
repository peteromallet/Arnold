from __future__ import annotations

"""Semantic contract for LTX 2.3 two-stage first/last workflows.

Validates that a ``VibeWorkflow`` follows the Lightricks two-stage first/last
spine: named inputs, first/last conditioning nodes, prompt/negative paths,
seed configuration, dimensions/frames/FPS, stage-2 sigmas, strength defaults,
declared custom nodes, absence of Runexx-only packs, and video output
materialization.
"""

from typing import Any

from vibecomfy.contracts.validation import ContractReport
from vibecomfy.lens.core import WorkflowLens
from vibecomfy.workflow import VibeWorkflow

# ── expected named inputs ─────────────────────────────────────────────
_EXPECTED_INPUTS = frozenset(
    {
        "prompt",
        "negative_prompt",
        "seed_first",
        "seed_last",
        "width",
        "height",
        "frames",
        "fps",
        "first_image",
        "last_image",
        "model",
    }
)
_EXPECTED_INPUT_TARGETS = {
    "prompt": ("2483", "text"),
    "negative_prompt": ("2612", "text"),
    "seed_first": ("4832", "noise_seed"),
    "seed_last": ("4967", "noise_seed"),
    "width": ("3059", "width"),
    "height": ("3059", "height"),
    "frames": ("4988", "value"),
    "fps": ("4989", "value"),
    "first_image": ("2004", "image"),
    "last_image": ("2005", "image"),
    "model": ("3940", "ckpt_name"),
}

# ── stage node ids ────────────────────────────────────────────────────
_FIRST_STAGE_ID = "3159"
_LAST_STAGE_ID = "4970"

# ── prompt / negative path node ids ───────────────────────────────────
_PROMPT_ENCODE_ID = "2483"
_NEGATIVE_ENCODE_ID = "2612"
_TEXT_ENCODER_LOADER_ID = "4982"

# ── seed node ids ─────────────────────────────────────────────────────
_SEED_FIRST_ID = "4832"
_SEED_LAST_ID = "4967"

# ── dimension / frame / fps node ids ──────────────────────────────────
_LATENT_VIDEO_ID = "3059"
_FRAMES_ID = "4988"
_FPS_ID = "4989"

# ── stage-2 sigmas ────────────────────────────────────────────────────
_STAGE2_SIGMAS_ID = "4985"
_STAGE2_SIGMAS_VALUE = "0.909375, 0.725, 0.421875, 0.0"

# ── expected custom node packs ────────────────────────────────────────
_EXPECTED_CUSTOM_NODES = frozenset({"ComfyUI-LTXVideo", "ComfyUI-KJNodes"})

# ── Runexx-only / incompatible packs ──────────────────────────────────
_RUNEXX_ONLY_PACKS = frozenset(
    {
        "LTXVAddGuide",
        "LTXICLoRALoaderModelOnly",
        "LTXAddVideoICLoRAGuide",
        "LTX2MemoryEfficientSageAttentionPatch",
        "LTX2SamplingPreviewOverride",
    }
)
_RUNEXX_ONLY_CUSTOM_NODES = frozenset({"rgthree-comfy"})


class LTXFirstLastTwoStageContract:
    """Semantic contract for LTX 2.3 two-stage first/last parity templates.

    Validates structural intent through the lens — no compiled Comfy API JSON
    assertions.
    """

    def __init__(self, workflow: VibeWorkflow) -> None:
        self._workflow = workflow
        self._lens = WorkflowLens(workflow)

    def validate(self) -> ContractReport:
        report = ContractReport(contract_name="ltx-first-last-two-stage", passed=True)
        self._check_named_inputs(report)
        self._check_first_last_conditioning(report)
        self._check_prompt_negative_paths(report)
        self._check_seeds(report)
        self._check_dimensions_frames_fps(report)
        self._check_stage2_sigmas(report)
        self._check_strength_defaults(report)
        self._check_custom_nodes(report)
        self._check_no_runexx_only_packs(report)
        self._check_video_output(report)
        return report

    # ── checks ─────────────────────────────────────────────────────────

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

    def _check_first_last_conditioning(self, report: ContractReport) -> None:
        for stage_id, label in [(_FIRST_STAGE_ID, "first"), (_LAST_STAGE_ID, "last")]:
            node = self._lens.node(stage_id)
            if node is None:
                report.add(
                    f"missing_{label}_stage_node",
                    f"Missing {label}-stage node {stage_id} (expected LTXVImgToVideoConditionOnly)",
                    detail={"expected_node_id": stage_id},
                )
                continue
            if node.class_type != "LTXVImgToVideoConditionOnly":
                report.add(
                    f"wrong_{label}_stage_class_type",
                    f"Node {stage_id} has class_type {node.class_type!r}, expected LTXVImgToVideoConditionOnly",
                    detail={"node_id": stage_id, "actual_class_type": node.class_type},
                )
            # The image input should come from an LTXVPreprocess or ResizeImageMaskNode
            image_src = self._lens.edge_source(stage_id, "image")
            if image_src is not None and image_src.node_id is not None:
                src_node = self._lens.node(image_src.node_id)
                if src_node is not None and src_node.class_type not in {"LTXVPreprocess", "ResizeImageMaskNode"}:
                    report.add(
                        f"unexpected_{label}_image_source",
                        f"Node {stage_id} image input fed by {src_node.class_type} ({image_src.node_id}), "
                        "expected LTXVPreprocess or ResizeImageMaskNode",
                        severity="warning",
                        detail={"node_id": stage_id, "source_class_type": src_node.class_type},
                    )

    def _check_prompt_negative_paths(self, report: ContractReport) -> None:
        for node_id, label in [(_PROMPT_ENCODE_ID, "prompt"), (_NEGATIVE_ENCODE_ID, "negative")]:
            node = self._lens.node(node_id)
            if node is None:
                report.add(
                    f"missing_{label}_encode",
                    f"Missing {label} CLIPTextEncode node {node_id}",
                    detail={"expected_node_id": node_id},
                )
                continue
            if node.class_type != "CLIPTextEncode":
                report.add(
                    f"wrong_{label}_encode_class_type",
                    f"Node {node_id} has class_type {node.class_type!r}, expected CLIPTextEncode",
                    detail={"node_id": node_id, "actual_class_type": node.class_type},
                )
            clip_src = self._lens.edge_source(node_id, "clip")
            if clip_src.node_id is not None:
                clip_node = self._lens.node(clip_src.node_id)
                if clip_node is None or clip_node.class_type != "LTXAVTextEncoderLoader":
                    report.add(
                        f"unexpected_{label}_clip_source",
                        f"Node {node_id} clip input fed by {getattr(clip_node, 'class_type', 'unknown')} "
                        f"({clip_src.node_id}), expected LTXAVTextEncoderLoader",
                        detail={"node_id": node_id, "source_node_id": clip_src.node_id},
                    )

    def _check_seeds(self, report: ContractReport) -> None:
        for node_id, label in [(_SEED_FIRST_ID, "seed_first"), (_SEED_LAST_ID, "seed_last")]:
            node = self._lens.node(node_id)
            if node is None:
                report.add(
                    f"missing_{label}_noise",
                    f"Missing {label} RandomNoise node {node_id}",
                    detail={"expected_node_id": node_id},
                )
                continue
            if node.class_type != "RandomNoise":
                report.add(
                    f"wrong_{label}_noise_class_type",
                    f"Node {node_id} has class_type {node.class_type!r}, expected RandomNoise",
                    detail={"node_id": node_id, "actual_class_type": node.class_type},
                )
            ca = self._lens.node_value(node_id, "control_after_generate")
            if ca != "fixed":
                report.add(
                    f"{label}_noise_not_fixed",
                    f"Node {node_id} RandomNoise control_after_generate is {ca!r}, expected 'fixed'",
                    severity="warning",
                    detail={"node_id": node_id, "actual": ca},
                )

    def _check_dimensions_frames_fps(self, report: ContractReport) -> None:
        latent = self._lens.node(_LATENT_VIDEO_ID)
        if latent is None:
            report.add(
                "missing_latent_video",
                f"Missing EmptyLTXVLatentVideo node {_LATENT_VIDEO_ID}",
                detail={"expected_node_id": _LATENT_VIDEO_ID},
            )
        elif latent.class_type != "EmptyLTXVLatentVideo":
            report.add(
                "wrong_latent_video_class_type",
                f"Node {_LATENT_VIDEO_ID} has class_type {latent.class_type!r}, expected EmptyLTXVLatentVideo",
                detail={"node_id": _LATENT_VIDEO_ID, "actual_class_type": latent.class_type},
            )

        frames_node = self._lens.node(_FRAMES_ID)
        if frames_node is None:
            report.add("missing_frames_node", f"Missing PrimitiveInt node {_FRAMES_ID} for frame count")
        elif frames_node.class_type != "PrimitiveInt":
            report.add(
                "wrong_frames_class_type",
                f"Node {_FRAMES_ID} has class_type {frames_node.class_type!r}, expected PrimitiveInt",
            )

        fps_node = self._lens.node(_FPS_ID)
        if fps_node is None:
            report.add("missing_fps_node", f"Missing PrimitiveFloat node {_FPS_ID} for FPS")
        elif fps_node.class_type != "PrimitiveFloat":
            report.add(
                "wrong_fps_class_type",
                f"Node {_FPS_ID} has class_type {fps_node.class_type!r}, expected PrimitiveFloat",
            )

    def _check_stage2_sigmas(self, report: ContractReport) -> None:
        node = self._lens.node(_STAGE2_SIGMAS_ID)
        if node is None:
            report.add(
                "missing_stage2_sigmas",
                f"Missing ManualSigmas node {_STAGE2_SIGMAS_ID}",
                detail={"expected_node_id": _STAGE2_SIGMAS_ID},
            )
            return
        if node.class_type != "ManualSigmas":
            report.add(
                "wrong_stage2_sigmas_class_type",
                f"Node {_STAGE2_SIGMAS_ID} has class_type {node.class_type!r}, expected ManualSigmas",
            )
            return
        value = self._lens.node_value(_STAGE2_SIGMAS_ID, "widget_0") or self._lens.node_value(
            _STAGE2_SIGMAS_ID, "sigmas"
        )
        if value is not None:
            actual = str(value).replace(" ", "")
            expected = _STAGE2_SIGMAS_VALUE.replace(" ", "")
            if actual != expected:
                report.add(
                    "wrong_stage2_sigmas_value",
                    f"Node {_STAGE2_SIGMAS_ID} ManualSigmas value is {value!r}, "
                    f"expected {_STAGE2_SIGMAS_VALUE!r}",
                    severity="warning",
                    detail={"expected": _STAGE2_SIGMAS_VALUE, "actual": str(value)},
                )

    def _check_strength_defaults(self, report: ContractReport) -> None:
        for stage_id in (_FIRST_STAGE_ID, _LAST_STAGE_ID):
            node = self._lens.node(stage_id)
            if node is None:
                continue
            strength = self._lens.node_value(stage_id, "widget_0")
            if strength is not None and strength != 1.0:
                report.add(
                    f"non_default_strength_{stage_id}",
                    f"Node {stage_id} widget_0 (strength) is {strength!r}, expected 1.0",
                    severity="warning",
                    detail={"node_id": stage_id, "actual": strength},
                )

    def _check_custom_nodes(self, report: ContractReport) -> None:
        actual = set(self._workflow.requirements.custom_nodes)
        missing = _EXPECTED_CUSTOM_NODES - actual
        if missing:
            report.add(
                "missing_custom_nodes",
                f"Missing declared custom node packs: {sorted(missing)}",
                detail={"expected": sorted(_EXPECTED_CUSTOM_NODES), "actual": sorted(actual), "missing": sorted(missing)},
            )

    def _check_no_runexx_only_packs(self, report: ContractReport) -> None:
        api_nodes: dict[str, Any] = {}
        try:
            api_nodes = self._workflow.compile("api")
        except Exception:
            pass

        found_runexx: list[str] = []
        for node in api_nodes.values():
            ct = node.get("class_type", "") if isinstance(node, dict) else ""
            if ct in _RUNEXX_ONLY_PACKS:
                found_runexx.append(ct)
        for node_id, node in self._workflow.nodes.items():
            if node.class_type in _RUNEXX_ONLY_PACKS:
                found_runexx.append(f"{node.class_type}:{node_id}")

        if found_runexx:
            report.add(
                "runexx_only_nodes_present",
                f"Incompatible Runexx-only nodes present: {sorted(set(found_runexx))}",
                detail={"found": sorted(set(found_runexx)), "disallowed": sorted(_RUNEXX_ONLY_PACKS)},
            )

        actual_cn = set(self._workflow.requirements.custom_nodes)
        bad_cn = actual_cn & _RUNEXX_ONLY_CUSTOM_NODES
        if bad_cn:
            report.add(
                "runexx_only_custom_nodes_declared",
                f"Incompatible Runexx-only custom node packs declared: {sorted(bad_cn)}",
                detail={"found": sorted(bad_cn)},
            )

    def _check_video_output(self, report: ContractReport) -> None:
        video_outputs = [o for o in self._workflow.outputs if o.output_type == "SaveVideo"]
        if not video_outputs:
            report.add(
                "missing_savevideo_output",
                "No SaveVideo output detected; workflow must materialize a video output.",
                detail={"outputs": [(o.node_id, o.output_type) for o in self._workflow.outputs]},
            )
            return

        for vo in video_outputs:
            upstream = self._lens.upstream_nodes(vo.node_id)
            if not upstream:
                report.add(
                    "savevideo_no_upstream",
                    f"SaveVideo output node {vo.node_id} has no upstream connections.",
                    detail={"node_id": vo.node_id},
                )
