# vibecomfy:generated
# pack: ComfyUI-KJNodes
# source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
# source_sha256: e6f4bcac4dc843f69d26c50900137a31b8fe540f43fe86c332d2b739efdad419
# generator_version: 1.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 230
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers ComfyUI-KJNodes

"""Auto-generated typed wrappers for the ComfyUI-KJNodes custom-node pack.

Each class in this module wraps one ComfyUI node class. The wrappers
are thin builders around ``VibeWorkflow.node()`` — calling
``ClassName.add(wf, ...)`` is equivalent to ``wf.node('ClassType', ...)``
but gives editors type-checked kwargs and a place to attach docstrings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from vibecomfy.handles import Handle  # noqa: F401
    from vibecomfy.workflow import VibeWorkflow, _NodeBuilder  # noqa: F401


class AddLabel:
    """Typed wrapper for the ComfyUI node class ``AddLabel``.

    Display name: Add Label

    Category: KJNodes/text

    Creates a new with the given text, and concatenates it to
    """

    CLASS_TYPE = 'AddLabel'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        direction: str = "up",
        font: str,
        font_color: str = "white",
        font_size: int = 32,
        height: int = 48,
        label_color: str = "black",
        text: str = "Text",
        text_x: int = 10,
        text_y: int = 2,
        caption: str = "",
    ) -> "_NodeBuilder":
        """Add a ``AddLabel`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'AddLabel',
            image=image,
            direction=direction,
            font=font,
            font_color=font_color,
            font_size=font_size,
            height=height,
            label_color=label_color,
            text=text,
            text_x=text_x,
            text_y=text_y,
            caption=caption,
        )

class AddNoiseToTrackPath:
    """Typed wrapper for the ComfyUI node class ``AddNoiseToTrackPath``.

    Category: conditioning/video_models
    """

    CLASS_TYPE = 'AddNoiseToTrackPath'
    OUTPUTS: tuple[str, ...] = ('TRACKS',)
    OUTPUT_TYPES: tuple[str, ...] = ('TRACKS',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        noise_temporal_ratio: float = 1.0,
        noise_x_ratio: float = 1.0,
        noise_y_ratio: float = 1.0,
        seed: int = 0,
        strength: float = 1.0,
        tracks: "Handle",
    ) -> "_NodeBuilder":
        """Add a ``AddNoiseToTrackPath`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'AddNoiseToTrackPath',
            noise_temporal_ratio=noise_temporal_ratio,
            noise_x_ratio=noise_x_ratio,
            noise_y_ratio=noise_y_ratio,
            seed=seed,
            strength=strength,
            tracks=tracks,
        )

class AppendInstanceDiffusionTracking:
    """Typed wrapper for the ComfyUI node class ``AppendInstanceDiffusionTracking``.

    Category: KJNodes/InstanceDiffusion

    Appends tracking data to be used with InstanceDiffusion:
    """

    CLASS_TYPE = 'AppendInstanceDiffusionTracking'
    OUTPUTS: tuple[str, ...] = ('tracking', 'prompt')
    OUTPUT_TYPES: tuple[str, ...] = ('TRACKING', 'STRING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        tracking_1: "Handle",
        tracking_2: "Handle",
        prompt_1: str = "",
        prompt_2: str = "",
    ) -> "_NodeBuilder":
        """Add a ``AppendInstanceDiffusionTracking`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'AppendInstanceDiffusionTracking',
            tracking_1=tracking_1,
            tracking_2=tracking_2,
            prompt_1=prompt_1,
            prompt_2=prompt_2,
        )

class AppendStringsToList:
    """Typed wrapper for the ComfyUI node class ``AppendStringsToList``.

    Display name: Append Strings To List

    Category: KJNodes/text
    """

    CLASS_TYPE = 'AppendStringsToList'
    OUTPUTS: tuple[str, ...] = ('STRING',)
    OUTPUT_TYPES: tuple[str, ...] = ('STRING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        string1: str = "",
        string2: str = "",
    ) -> "_NodeBuilder":
        """Add a ``AppendStringsToList`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'AppendStringsToList',
            string1=string1,
            string2=string2,
        )

class ApplyRifleXRoPE_HunuyanVideo:
    """Typed wrapper for the ComfyUI node class ``ApplyRifleXRoPE_HunuyanVideo``.

    Display name: Apply RifleXRoPE HunuyanVideo

    Category: KJNodes/hunyuanvideo

    Extends the potential frame count of HunyuanVideo using this method: https://github.com/thu-ml/RIFLEx
    """

    CLASS_TYPE = 'ApplyRifleXRoPE_HunuyanVideo'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latent: "Handle" = None,
        model: "Handle" = None,
        k: int = 4,
    ) -> "_NodeBuilder":
        """Add a ``ApplyRifleXRoPE_HunuyanVideo`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ApplyRifleXRoPE_HunuyanVideo',
            latent=latent,
            model=model,
            k=k,
        )

class ApplyRifleXRoPE_WanVideo:
    """Typed wrapper for the ComfyUI node class ``ApplyRifleXRoPE_WanVideo``.

    Display name: Apply RifleXRoPE WanVideo

    Category: KJNodes/wan

    Extends the potential frame count of HunyuanVideo using this method: https://github.com/thu-ml/RIFLEx
    """

    CLASS_TYPE = 'ApplyRifleXRoPE_WanVideo'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latent: "Handle" = None,
        model: "Handle" = None,
        k: int = 6,
    ) -> "_NodeBuilder":
        """Add a ``ApplyRifleXRoPE_WanVideo`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ApplyRifleXRoPE_WanVideo',
            latent=latent,
            model=model,
            k=k,
        )

class AudioConcatenate:
    """Typed wrapper for the ComfyUI node class ``AudioConcatenate``.

    Category: KJNodes/audio

    Concatenates the audio1 to audio2 in the specified direction.
    """

    CLASS_TYPE = 'AudioConcatenate'
    OUTPUTS: tuple[str, ...] = ('AUDIO',)
    OUTPUT_TYPES: tuple[str, ...] = ('AUDIO',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        audio1: "Handle" = None,
        audio2: "Handle" = None,
        direction: str = "right",
    ) -> "_NodeBuilder":
        """Add a ``AudioConcatenate`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'AudioConcatenate',
            audio1=audio1,
            audio2=audio2,
            direction=direction,
        )

class BOOLConstant:
    """Typed wrapper for the ComfyUI node class ``BOOLConstant``.

    Display name: BOOL Constant

    Category: KJNodes/constants
    """

    CLASS_TYPE = 'BOOLConstant'
    OUTPUTS: tuple[str, ...] = ('value',)
    OUTPUT_TYPES: tuple[str, ...] = ('BOOLEAN',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        value: bool = True,
    ) -> "_NodeBuilder":
        """Add a ``BOOLConstant`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'BOOLConstant',
            value=value,
        )

class BatchCLIPSeg:
    """Typed wrapper for the ComfyUI node class ``BatchCLIPSeg``.

    Display name: Batch CLIPSeg

    Category: KJNodes/masking

    Segments an image or batch of images using CLIPSeg.
    """

    CLASS_TYPE = 'BatchCLIPSeg'
    OUTPUTS: tuple[str, ...] = ('Mask', 'Image')
    OUTPUT_TYPES: tuple[str, ...] = ('MASK', 'IMAGE')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images: "Handle" = None,
        binary_mask: bool = True,
        combine_mask: bool = False,
        text: str,
        threshold: float = 0.5,
        use_cuda: bool = True,
        blur_sigma: float = 0.0,
        image_bg_level: float = 0.5,
        invert: bool = False,
        opt_model: "Handle" = None,
        prev_mask: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``BatchCLIPSeg`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'BatchCLIPSeg',
            images=images,
            binary_mask=binary_mask,
            combine_mask=combine_mask,
            text=text,
            threshold=threshold,
            use_cuda=use_cuda,
            blur_sigma=blur_sigma,
            image_bg_level=image_bg_level,
            invert=invert,
            opt_model=opt_model,
            prev_mask=prev_mask,
        )

class BatchCropFromMask:
    """Typed wrapper for the ComfyUI node class ``BatchCropFromMask``.

    Display name: Batch Crop From Mask

    Category: KJNodes/masking
    """

    CLASS_TYPE = 'BatchCropFromMask'
    OUTPUTS: tuple[str, ...] = ('original_images', 'cropped_images', 'bboxes', 'width', 'height')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'IMAGE', 'BBOX', 'INT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        masks: "Handle" = None,
        original_images: "Handle" = None,
        bbox_smooth_alpha: float = 0.5,
        crop_size_mult: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``BatchCropFromMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'BatchCropFromMask',
            masks=masks,
            original_images=original_images,
            bbox_smooth_alpha=bbox_smooth_alpha,
            crop_size_mult=crop_size_mult,
        )

class BatchCropFromMaskAdvanced:
    """Typed wrapper for the ComfyUI node class ``BatchCropFromMaskAdvanced``.

    Display name: Batch Crop From Mask Advanced

    Category: KJNodes/masking
    """

    CLASS_TYPE = 'BatchCropFromMaskAdvanced'
    OUTPUTS: tuple[str, ...] = ('original_images', 'cropped_images', 'cropped_masks', 'combined_crop_image', 'combined_crop_masks', 'bboxes', 'combined_bounding_box', 'bbox_width', 'bbox_height')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'IMAGE', 'MASK', 'IMAGE', 'MASK', 'BBOX', 'BBOX', 'INT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        masks: "Handle" = None,
        original_images: "Handle" = None,
        bbox_smooth_alpha: float = 0.5,
        crop_size_mult: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``BatchCropFromMaskAdvanced`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'BatchCropFromMaskAdvanced',
            masks=masks,
            original_images=original_images,
            bbox_smooth_alpha=bbox_smooth_alpha,
            crop_size_mult=crop_size_mult,
        )

class BatchUncrop:
    """Typed wrapper for the ComfyUI node class ``BatchUncrop``.

    Display name: Batch Uncrop

    Category: KJNodes/masking
    """

    CLASS_TYPE = 'BatchUncrop'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        cropped_images: "Handle" = None,
        original_images: "Handle" = None,
        bboxes: "Handle",
        border_blending: float = 0.25,
        border_bottom: bool = True,
        border_left: bool = True,
        border_right: bool = True,
        border_top: bool = True,
        crop_rescale: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``BatchUncrop`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'BatchUncrop',
            cropped_images=cropped_images,
            original_images=original_images,
            bboxes=bboxes,
            border_blending=border_blending,
            border_bottom=border_bottom,
            border_left=border_left,
            border_right=border_right,
            border_top=border_top,
            crop_rescale=crop_rescale,
        )

class BatchUncropAdvanced:
    """Typed wrapper for the ComfyUI node class ``BatchUncropAdvanced``.

    Display name: Batch Uncrop Advanced

    Category: KJNodes/masking
    """

    CLASS_TYPE = 'BatchUncropAdvanced'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        combined_crop_mask: "Handle" = None,
        cropped_images: "Handle" = None,
        cropped_masks: "Handle" = None,
        original_images: "Handle" = None,
        bboxes: "Handle",
        border_blending: float = 0.25,
        crop_rescale: float = 1.0,
        use_combined_mask: bool = False,
        use_square_mask: bool = True,
        combined_bounding_box: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``BatchUncropAdvanced`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'BatchUncropAdvanced',
            combined_crop_mask=combined_crop_mask,
            cropped_images=cropped_images,
            cropped_masks=cropped_masks,
            original_images=original_images,
            bboxes=bboxes,
            border_blending=border_blending,
            crop_rescale=crop_rescale,
            use_combined_mask=use_combined_mask,
            use_square_mask=use_square_mask,
            combined_bounding_box=combined_bounding_box,
        )

class BboxToInt:
    """Typed wrapper for the ComfyUI node class ``BboxToInt``.

    Display name: Bbox To Int

    Category: KJNodes/masking

    Returns selected index from bounding box list as integers.
    """

    CLASS_TYPE = 'BboxToInt'
    OUTPUTS: tuple[str, ...] = ('x_min', 'y_min', 'width', 'height', 'center_x', 'center_y')
    OUTPUT_TYPES: tuple[str, ...] = ('INT', 'INT', 'INT', 'INT', 'INT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        bboxes: "Handle",
        index: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``BboxToInt`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'BboxToInt',
            bboxes=bboxes,
            index=index,
        )

class BboxVisualize:
    """Typed wrapper for the ComfyUI node class ``BboxVisualize``.

    Display name: Bbox Visualize

    Category: KJNodes/masking

    Visualizes the specified bbox on the image.
    """

    CLASS_TYPE = 'BboxVisualize'
    OUTPUTS: tuple[str, ...] = ('images',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images: "Handle" = None,
        bbox_format: str = "xywh",
        bboxes: "Handle",
        line_width: int = 1,
    ) -> "_NodeBuilder":
        """Add a ``BboxVisualize`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'BboxVisualize',
            images=images,
            bbox_format=bbox_format,
            bboxes=bboxes,
            line_width=line_width,
        )

class BlockifyMask:
    """Typed wrapper for the ComfyUI node class ``BlockifyMask``.

    Display name: Blockify Mask

    Category: KJNodes/masking

    Creates a block mask by dividing the bounding box of each mask into blocks of the specified size and filling in blocks that contain any part of the original mask.
    """

    CLASS_TYPE = 'BlockifyMask'
    OUTPUTS: tuple[str, ...] = ('mask',)
    OUTPUT_TYPES: tuple[str, ...] = ('MASK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        masks: "Handle" = None,
        block_size: int = 32,
        device: str = "cpu",
    ) -> "_NodeBuilder":
        """Add a ``BlockifyMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'BlockifyMask',
            masks=masks,
            block_size=block_size,
            device=device,
        )

class CFGZeroStarAndInit:
    """Typed wrapper for the ComfyUI node class ``CFGZeroStarAndInit``.

    Display name: CFG Zero Star/Init

    Category: KJNodes/experimental

    https://github.com/WeichenFan/CFG-Zero-star
    """

    CLASS_TYPE = 'CFGZeroStarAndInit'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        use_zero_init: bool = True,
        zero_init_steps: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``CFGZeroStarAndInit`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CFGZeroStarAndInit',
            model=model,
            use_zero_init=use_zero_init,
            zero_init_steps=zero_init_steps,
        )

class CameraPoseVisualizer:
    """Typed wrapper for the ComfyUI node class ``CameraPoseVisualizer``.

    Display name: Camera Pose Visualizer

    Category: KJNodes/misc

    Visualizes the camera poses, from Animatediff-Evolved CameraCtrl Pose
    """

    CLASS_TYPE = 'CameraPoseVisualizer'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        base_xval: float = 0.2,
        pose_file_path: str = "",
        relative_c2w: bool = True,
        scale: float = 1.0,
        use_exact_fx: bool = False,
        use_viewer: bool = False,
        zval: float = 0.3,
        cameractrl_poses: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``CameraPoseVisualizer`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CameraPoseVisualizer',
            base_xval=base_xval,
            pose_file_path=pose_file_path,
            relative_c2w=relative_c2w,
            scale=scale,
            use_exact_fx=use_exact_fx,
            use_viewer=use_viewer,
            zval=zval,
            cameractrl_poses=cameractrl_poses,
        )

class CheckpointLoaderKJ:
    """Typed wrapper for the ComfyUI node class ``CheckpointLoaderKJ``.

    Category: KJNodes/model_loaders

    Experimental node for patching torch.nn.Linear with CublasLinear.
    """

    CLASS_TYPE = 'CheckpointLoaderKJ'
    OUTPUTS: tuple[str, ...] = ('MODEL', 'CLIP', 'VAE')
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL', 'CLIP', 'VAE')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        ckpt_name: str,
        compute_dtype: str = "default",
        enable_fp16_accumulation: bool = False,
        patch_cublaslinear: bool = False,
        sage_attention: str = False,
        weight_dtype: str,
    ) -> "_NodeBuilder":
        """Add a ``CheckpointLoaderKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CheckpointLoaderKJ',
            ckpt_name=ckpt_name,
            compute_dtype=compute_dtype,
            enable_fp16_accumulation=enable_fp16_accumulation,
            patch_cublaslinear=patch_cublaslinear,
            sage_attention=sage_attention,
            weight_dtype=weight_dtype,
        )

class CheckpointPerturbWeights:
    """Typed wrapper for the ComfyUI node class ``CheckpointPerturbWeights``.

    Category: KJNodes/experimental
    """

    CLASS_TYPE = 'CheckpointPerturbWeights'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        final_layer: float = 0.02,
        joint_blocks: float = 0.02,
        rest_of_the_blocks: float = 0.02,
        seed: int = 123,
    ) -> "_NodeBuilder":
        """Add a ``CheckpointPerturbWeights`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CheckpointPerturbWeights',
            model=model,
            final_layer=final_layer,
            joint_blocks=joint_blocks,
            rest_of_the_blocks=rest_of_the_blocks,
            seed=seed,
        )

class ColorMatch:
    """Typed wrapper for the ComfyUI node class ``ColorMatch``.

    Display name: Color Match

    Category: KJNodes/image

    color-matcher enables color transfer across images which comes in handy for automatic
    """

    CLASS_TYPE = 'ColorMatch'
    OUTPUTS: tuple[str, ...] = ('image',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image_ref: "Handle" = None,
        image_target: "Handle" = None,
        method: str = "mkl",
        multithread: bool = True,
        strength: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``ColorMatch`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ColorMatch',
            image_ref=image_ref,
            image_target=image_target,
            method=method,
            multithread=multithread,
            strength=strength,
        )

class ColorMatchV2:
    """Typed wrapper for the ComfyUI node class ``ColorMatchV2``.

    Category: KJNodes/image

    color-matcher enables color transfer across images which comes in handy for automatic
    """

    CLASS_TYPE = 'ColorMatchV2'
    OUTPUTS: tuple[str, ...] = ('image',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image_ref: "Handle" = None,
        image_target: "Handle" = None,
        method: str = "mkl",
        multithread: bool = True,
        strength: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``ColorMatchV2`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ColorMatchV2',
            image_ref=image_ref,
            image_target=image_target,
            method=method,
            multithread=multithread,
            strength=strength,
        )

class ColorToMask:
    """Typed wrapper for the ComfyUI node class ``ColorToMask``.

    Display name: Color To Mask

    Category: KJNodes/masking

    Converts chosen RGB value to a mask.
    """

    CLASS_TYPE = 'ColorToMask'
    OUTPUTS: tuple[str, ...] = ('MASK',)
    OUTPUT_TYPES: tuple[str, ...] = ('MASK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images: "Handle" = None,
        blue: int = 0,
        green: int = 0,
        invert: bool = False,
        per_batch: int = 16,
        red: int = 0,
        threshold: int = 10,
    ) -> "_NodeBuilder":
        """Add a ``ColorToMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ColorToMask',
            images=images,
            blue=blue,
            green=green,
            invert=invert,
            per_batch=per_batch,
            red=red,
            threshold=threshold,
        )

class CondPassThrough:
    """Typed wrapper for the ComfyUI node class ``CondPassThrough``.

    Category: KJNodes/misc

    Simply passes through the positive and negative conditioning,
    """

    CLASS_TYPE = 'CondPassThrough'
    OUTPUTS: tuple[str, ...] = ('positive', 'negative')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'CONDITIONING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        negative: "Handle" = None,
        positive: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``CondPassThrough`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CondPassThrough',
            negative=negative,
            positive=positive,
        )

class ConditioningMultiCombine:
    """Typed wrapper for the ComfyUI node class ``ConditioningMultiCombine``.

    Display name: Conditioning Multi Combine

    Category: KJNodes/masking/conditioning

    Combines multiple conditioning nodes into one
    """

    CLASS_TYPE = 'ConditioningMultiCombine'
    OUTPUTS: tuple[str, ...] = ('combined', 'inputcount')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        conditioning_1: "Handle" = None,
        conditioning_2: "Handle" = None,
        inputcount: int = 2,
        operation: str = "combine",
    ) -> "_NodeBuilder":
        """Add a ``ConditioningMultiCombine`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ConditioningMultiCombine',
            conditioning_1=conditioning_1,
            conditioning_2=conditioning_2,
            inputcount=inputcount,
            operation=operation,
        )

class ConditioningSetMaskAndCombine:
    """Typed wrapper for the ComfyUI node class ``ConditioningSetMaskAndCombine``.

    Category: KJNodes/masking/conditioning

    Bundles multiple conditioning mask and combine nodes into one,functionality is identical to ComfyUI native nodes
    """

    CLASS_TYPE = 'ConditioningSetMaskAndCombine'
    OUTPUTS: tuple[str, ...] = ('combined_positive', 'combined_negative')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'CONDITIONING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        mask_1: "Handle" = None,
        mask_2: "Handle" = None,
        negative_1: "Handle" = None,
        negative_2: "Handle" = None,
        positive_1: "Handle" = None,
        positive_2: "Handle" = None,
        mask_1_strength: float = 1.0,
        mask_2_strength: float = 1.0,
        set_cond_area: str,
    ) -> "_NodeBuilder":
        """Add a ``ConditioningSetMaskAndCombine`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ConditioningSetMaskAndCombine',
            mask_1=mask_1,
            mask_2=mask_2,
            negative_1=negative_1,
            negative_2=negative_2,
            positive_1=positive_1,
            positive_2=positive_2,
            mask_1_strength=mask_1_strength,
            mask_2_strength=mask_2_strength,
            set_cond_area=set_cond_area,
        )

class ConditioningSetMaskAndCombine3:
    """Typed wrapper for the ComfyUI node class ``ConditioningSetMaskAndCombine3``.

    Category: KJNodes/masking/conditioning

    Bundles multiple conditioning mask and combine nodes into one,functionality is identical to ComfyUI native nodes
    """

    CLASS_TYPE = 'ConditioningSetMaskAndCombine3'
    OUTPUTS: tuple[str, ...] = ('combined_positive', 'combined_negative')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'CONDITIONING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        mask_1: "Handle" = None,
        mask_2: "Handle" = None,
        mask_3: "Handle" = None,
        negative_1: "Handle" = None,
        negative_2: "Handle" = None,
        negative_3: "Handle" = None,
        positive_1: "Handle" = None,
        positive_2: "Handle" = None,
        positive_3: "Handle" = None,
        mask_1_strength: float = 1.0,
        mask_2_strength: float = 1.0,
        mask_3_strength: float = 1.0,
        set_cond_area: str,
    ) -> "_NodeBuilder":
        """Add a ``ConditioningSetMaskAndCombine3`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ConditioningSetMaskAndCombine3',
            mask_1=mask_1,
            mask_2=mask_2,
            mask_3=mask_3,
            negative_1=negative_1,
            negative_2=negative_2,
            negative_3=negative_3,
            positive_1=positive_1,
            positive_2=positive_2,
            positive_3=positive_3,
            mask_1_strength=mask_1_strength,
            mask_2_strength=mask_2_strength,
            mask_3_strength=mask_3_strength,
            set_cond_area=set_cond_area,
        )

class ConditioningSetMaskAndCombine4:
    """Typed wrapper for the ComfyUI node class ``ConditioningSetMaskAndCombine4``.

    Category: KJNodes/masking/conditioning

    Bundles multiple conditioning mask and combine nodes into one,functionality is identical to ComfyUI native nodes
    """

    CLASS_TYPE = 'ConditioningSetMaskAndCombine4'
    OUTPUTS: tuple[str, ...] = ('combined_positive', 'combined_negative')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'CONDITIONING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        mask_1: "Handle" = None,
        mask_2: "Handle" = None,
        mask_3: "Handle" = None,
        mask_4: "Handle" = None,
        negative_1: "Handle" = None,
        negative_2: "Handle" = None,
        negative_3: "Handle" = None,
        negative_4: "Handle" = None,
        positive_1: "Handle" = None,
        positive_2: "Handle" = None,
        positive_3: "Handle" = None,
        positive_4: "Handle" = None,
        mask_1_strength: float = 1.0,
        mask_2_strength: float = 1.0,
        mask_3_strength: float = 1.0,
        mask_4_strength: float = 1.0,
        set_cond_area: str,
    ) -> "_NodeBuilder":
        """Add a ``ConditioningSetMaskAndCombine4`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ConditioningSetMaskAndCombine4',
            mask_1=mask_1,
            mask_2=mask_2,
            mask_3=mask_3,
            mask_4=mask_4,
            negative_1=negative_1,
            negative_2=negative_2,
            negative_3=negative_3,
            negative_4=negative_4,
            positive_1=positive_1,
            positive_2=positive_2,
            positive_3=positive_3,
            positive_4=positive_4,
            mask_1_strength=mask_1_strength,
            mask_2_strength=mask_2_strength,
            mask_3_strength=mask_3_strength,
            mask_4_strength=mask_4_strength,
            set_cond_area=set_cond_area,
        )

class ConditioningSetMaskAndCombine5:
    """Typed wrapper for the ComfyUI node class ``ConditioningSetMaskAndCombine5``.

    Category: KJNodes/masking/conditioning

    Bundles multiple conditioning mask and combine nodes into one,functionality is identical to ComfyUI native nodes
    """

    CLASS_TYPE = 'ConditioningSetMaskAndCombine5'
    OUTPUTS: tuple[str, ...] = ('combined_positive', 'combined_negative')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'CONDITIONING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        mask_1: "Handle" = None,
        mask_2: "Handle" = None,
        mask_3: "Handle" = None,
        mask_4: "Handle" = None,
        mask_5: "Handle" = None,
        negative_1: "Handle" = None,
        negative_2: "Handle" = None,
        negative_3: "Handle" = None,
        negative_4: "Handle" = None,
        negative_5: "Handle" = None,
        positive_1: "Handle" = None,
        positive_2: "Handle" = None,
        positive_3: "Handle" = None,
        positive_4: "Handle" = None,
        positive_5: "Handle" = None,
        mask_1_strength: float = 1.0,
        mask_2_strength: float = 1.0,
        mask_3_strength: float = 1.0,
        mask_4_strength: float = 1.0,
        mask_5_strength: float = 1.0,
        set_cond_area: str,
    ) -> "_NodeBuilder":
        """Add a ``ConditioningSetMaskAndCombine5`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ConditioningSetMaskAndCombine5',
            mask_1=mask_1,
            mask_2=mask_2,
            mask_3=mask_3,
            mask_4=mask_4,
            mask_5=mask_5,
            negative_1=negative_1,
            negative_2=negative_2,
            negative_3=negative_3,
            negative_4=negative_4,
            negative_5=negative_5,
            positive_1=positive_1,
            positive_2=positive_2,
            positive_3=positive_3,
            positive_4=positive_4,
            positive_5=positive_5,
            mask_1_strength=mask_1_strength,
            mask_2_strength=mask_2_strength,
            mask_3_strength=mask_3_strength,
            mask_4_strength=mask_4_strength,
            mask_5_strength=mask_5_strength,
            set_cond_area=set_cond_area,
        )

class ConsolidateMasksKJ:
    """Typed wrapper for the ComfyUI node class ``ConsolidateMasksKJ``.

    Display name: Consolidate Masks

    Category: KJNodes/masking

    Consolidates a batch of separate masks by finding the largest group of masks that fit inside a tile of the given width and height (including the padding), and repeating until no more masks can be combined.
    """

    CLASS_TYPE = 'ConsolidateMasksKJ'
    OUTPUTS: tuple[str, ...] = ('MASK',)
    OUTPUT_TYPES: tuple[str, ...] = ('MASK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        masks: "Handle" = None,
        height: int = 512,
        padding: int = 0,
        width: int = 512,
    ) -> "_NodeBuilder":
        """Add a ``ConsolidateMasksKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ConsolidateMasksKJ',
            masks=masks,
            height=height,
            padding=padding,
            width=width,
        )

class CreateAudioMask:
    """Typed wrapper for the ComfyUI node class ``CreateAudioMask``.

    Display name: Create Audio Mask

    Category: KJNodes/deprecated
    """

    CLASS_TYPE = 'CreateAudioMask'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        audio_path: str = "audio.wav",
        frames: int = 16,
        height: int = 256,
        invert: bool = False,
        scale: float = 0.5,
        width: int = 256,
    ) -> "_NodeBuilder":
        """Add a ``CreateAudioMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CreateAudioMask',
            audio_path=audio_path,
            frames=frames,
            height=height,
            invert=invert,
            scale=scale,
            width=width,
        )

class CreateFadeMask:
    """Typed wrapper for the ComfyUI node class ``CreateFadeMask``.

    Display name: Create Fade Mask

    Category: KJNodes/deprecated
    """

    CLASS_TYPE = 'CreateFadeMask'
    OUTPUTS: tuple[str, ...] = ('MASK',)
    OUTPUT_TYPES: tuple[str, ...] = ('MASK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        end_level: float = 0.0,
        frames: int = 2,
        height: int = 256,
        interpolation: str,
        invert: bool = False,
        midpoint_frame: int = 0,
        midpoint_level: float = 0.5,
        start_level: float = 1.0,
        width: int = 256,
    ) -> "_NodeBuilder":
        """Add a ``CreateFadeMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CreateFadeMask',
            end_level=end_level,
            frames=frames,
            height=height,
            interpolation=interpolation,
            invert=invert,
            midpoint_frame=midpoint_frame,
            midpoint_level=midpoint_level,
            start_level=start_level,
            width=width,
        )

class CreateFadeMaskAdvanced:
    """Typed wrapper for the ComfyUI node class ``CreateFadeMaskAdvanced``.

    Display name: Create Fade Mask Advanced

    Category: KJNodes/masking/generate

    Create a batch of masks interpolated between given frames and values.
    """

    CLASS_TYPE = 'CreateFadeMaskAdvanced'
    OUTPUTS: tuple[str, ...] = ('MASK',)
    OUTPUT_TYPES: tuple[str, ...] = ('MASK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        frames: int = 16,
        height: int = 512,
        interpolation: str,
        invert: bool = False,
        points_string: str = "0:(0.0),\n7:(1.0),\n15:(0.0)\n",
        width: int = 512,
    ) -> "_NodeBuilder":
        """Add a ``CreateFadeMaskAdvanced`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CreateFadeMaskAdvanced',
            frames=frames,
            height=height,
            interpolation=interpolation,
            invert=invert,
            points_string=points_string,
            width=width,
        )

class CreateFluidMask:
    """Typed wrapper for the ComfyUI node class ``CreateFluidMask``.

    Display name: Create Fluid Mask

    Category: KJNodes/masking/generate
    """

    CLASS_TYPE = 'CreateFluidMask'
    OUTPUTS: tuple[str, ...] = ('IMAGE', 'MASK')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        frames: int = 1,
        height: int = 256,
        inflow_count: int = 3,
        inflow_duration: int = 60,
        inflow_padding: int = 50,
        inflow_radius: int = 8,
        inflow_velocity: int = 1,
        invert: bool = False,
        width: int = 256,
    ) -> "_NodeBuilder":
        """Add a ``CreateFluidMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CreateFluidMask',
            frames=frames,
            height=height,
            inflow_count=inflow_count,
            inflow_duration=inflow_duration,
            inflow_padding=inflow_padding,
            inflow_radius=inflow_radius,
            inflow_velocity=inflow_velocity,
            invert=invert,
            width=width,
        )

class CreateGradientFromCoords:
    """Typed wrapper for the ComfyUI node class ``CreateGradientFromCoords``.

    Display name: Create Gradient From Coords

    Category: KJNodes/image

    Creates a gradient image from coordinates.
    """

    CLASS_TYPE = 'CreateGradientFromCoords'
    OUTPUTS: tuple[str, ...] = ('image',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        coordinates: str,
        end_color: str = "black",
        frame_height: int = 512,
        frame_width: int = 512,
        multiplier: float = 1.0,
        start_color: str = "white",
    ) -> "_NodeBuilder":
        """Add a ``CreateGradientFromCoords`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CreateGradientFromCoords',
            coordinates=coordinates,
            end_color=end_color,
            frame_height=frame_height,
            frame_width=frame_width,
            multiplier=multiplier,
            start_color=start_color,
        )

class CreateGradientMask:
    """Typed wrapper for the ComfyUI node class ``CreateGradientMask``.

    Display name: Create Gradient Mask

    Category: KJNodes/masking/generate
    """

    CLASS_TYPE = 'CreateGradientMask'
    OUTPUTS: tuple[str, ...] = ('MASK',)
    OUTPUT_TYPES: tuple[str, ...] = ('MASK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        frames: int = 0,
        height: int = 256,
        invert: bool = False,
        width: int = 256,
    ) -> "_NodeBuilder":
        """Add a ``CreateGradientMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CreateGradientMask',
            frames=frames,
            height=height,
            invert=invert,
            width=width,
        )

class CreateInstanceDiffusionTracking:
    """Typed wrapper for the ComfyUI node class ``CreateInstanceDiffusionTracking``.

    Category: KJNodes/InstanceDiffusion

    Creates tracking data to be used with InstanceDiffusion:
    """

    CLASS_TYPE = 'CreateInstanceDiffusionTracking'
    OUTPUTS: tuple[str, ...] = ('tracking', 'prompt', 'width', 'height', 'bbox_width', 'bbox_height')
    OUTPUT_TYPES: tuple[str, ...] = ('TRACKING', 'STRING', 'INT', 'INT', 'INT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        bbox_height: int = 512,
        bbox_width: int = 512,
        class_id: int = 0,
        class_name: str = "class_name",
        coordinates: str,
        height: int = 512,
        prompt: str = "prompt",
        width: int = 512,
        fit_in_frame: bool = True,
        size_multiplier: float = [1.0],
    ) -> "_NodeBuilder":
        """Add a ``CreateInstanceDiffusionTracking`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CreateInstanceDiffusionTracking',
            bbox_height=bbox_height,
            bbox_width=bbox_width,
            class_id=class_id,
            class_name=class_name,
            coordinates=coordinates,
            height=height,
            prompt=prompt,
            width=width,
            fit_in_frame=fit_in_frame,
            size_multiplier=size_multiplier,
        )

class CreateMagicMask:
    """Typed wrapper for the ComfyUI node class ``CreateMagicMask``.

    Display name: Create Magic Mask

    Category: KJNodes/masking/generate
    """

    CLASS_TYPE = 'CreateMagicMask'
    OUTPUTS: tuple[str, ...] = ('mask', 'mask_inverted')
    OUTPUT_TYPES: tuple[str, ...] = ('MASK', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        depth: int = 12,
        distortion: float = 1.5,
        frame_height: int = 512,
        frame_width: int = 512,
        frames: int = 16,
        seed: int = 123,
        transitions: int = 1,
    ) -> "_NodeBuilder":
        """Add a ``CreateMagicMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CreateMagicMask',
            depth=depth,
            distortion=distortion,
            frame_height=frame_height,
            frame_width=frame_width,
            frames=frames,
            seed=seed,
            transitions=transitions,
        )

class CreateShapeImageOnPath:
    """Typed wrapper for the ComfyUI node class ``CreateShapeImageOnPath``.

    Display name: Create Shape Image On Path

    Category: KJNodes/image

    Creates an image or batch of images with the specified shape.
    """

    CLASS_TYPE = 'CreateShapeImageOnPath'
    OUTPUTS: tuple[str, ...] = ('image', 'mask')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        bg_color: str = "black",
        blur_radius: float = 0.0,
        coordinates: str,
        frame_height: int = 512,
        frame_width: int = 512,
        intensity: float = 1.0,
        shape: str = "circle",
        shape_color: str = "white",
        shape_height: int = 128,
        shape_width: int = 128,
        border_color: str = "black",
        border_width: int = 0,
        size_multiplier: float = [1.0],
        trailing: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``CreateShapeImageOnPath`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CreateShapeImageOnPath',
            bg_color=bg_color,
            blur_radius=blur_radius,
            coordinates=coordinates,
            frame_height=frame_height,
            frame_width=frame_width,
            intensity=intensity,
            shape=shape,
            shape_color=shape_color,
            shape_height=shape_height,
            shape_width=shape_width,
            border_color=border_color,
            border_width=border_width,
            size_multiplier=size_multiplier,
            trailing=trailing,
        )

class CreateShapeMask:
    """Typed wrapper for the ComfyUI node class ``CreateShapeMask``.

    Display name: Create Shape Mask

    Category: KJNodes/masking/generate

    Creates a mask or batch of masks with the specified shape.
    """

    CLASS_TYPE = 'CreateShapeMask'
    OUTPUTS: tuple[str, ...] = ('mask', 'mask_inverted')
    OUTPUT_TYPES: tuple[str, ...] = ('MASK', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        frame_height: int = 512,
        frame_width: int = 512,
        frames: int = 1,
        grow: int = 0,
        location_x: int = 256,
        location_y: int = 256,
        shape: str = "circle",
        shape_height: int = 128,
        shape_width: int = 128,
    ) -> "_NodeBuilder":
        """Add a ``CreateShapeMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CreateShapeMask',
            frame_height=frame_height,
            frame_width=frame_width,
            frames=frames,
            grow=grow,
            location_x=location_x,
            location_y=location_y,
            shape=shape,
            shape_height=shape_height,
            shape_width=shape_width,
        )

class CreateShapeMaskOnPath:
    """Typed wrapper for the ComfyUI node class ``CreateShapeMaskOnPath``.

    Display name: Create Shape Mask On Path

    Category: KJNodes/masking/generate

    Creates a mask or batch of masks with the specified shape.
    """

    CLASS_TYPE = 'CreateShapeMaskOnPath'
    OUTPUTS: tuple[str, ...] = ('mask', 'mask_inverted')
    OUTPUT_TYPES: tuple[str, ...] = ('MASK', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        coordinates: str,
        frame_height: int = 512,
        frame_width: int = 512,
        shape: str = "circle",
        shape_height: int = 128,
        shape_width: int = 128,
        size_multiplier: float = [1.0],
    ) -> "_NodeBuilder":
        """Add a ``CreateShapeMaskOnPath`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CreateShapeMaskOnPath',
            coordinates=coordinates,
            frame_height=frame_height,
            frame_width=frame_width,
            shape=shape,
            shape_height=shape_height,
            shape_width=shape_width,
            size_multiplier=size_multiplier,
        )

class CreateTextMask:
    """Typed wrapper for the ComfyUI node class ``CreateTextMask``.

    Display name: Create Text Mask

    Category: KJNodes/text

    Creates a text image and mask.
    """

    CLASS_TYPE = 'CreateTextMask'
    OUTPUTS: tuple[str, ...] = ('IMAGE', 'MASK')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        end_rotation: int = 0,
        font: str,
        font_color: str = "white",
        font_size: int = 32,
        frames: int = 1,
        height: int = 512,
        invert: bool = False,
        start_rotation: int = 0,
        text: str = "HELLO!",
        text_x: int = 0,
        text_y: int = 0,
        width: int = 512,
    ) -> "_NodeBuilder":
        """Add a ``CreateTextMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CreateTextMask',
            end_rotation=end_rotation,
            font=font,
            font_color=font_color,
            font_size=font_size,
            frames=frames,
            height=height,
            invert=invert,
            start_rotation=start_rotation,
            text=text,
            text_x=text_x,
            text_y=text_y,
            width=width,
        )

class CreateTextOnPath:
    """Typed wrapper for the ComfyUI node class ``CreateTextOnPath``.

    Display name: Create Text On Path

    Category: KJNodes/masking/generate

    Creates a mask or batch of masks with the specified text.
    """

    CLASS_TYPE = 'CreateTextOnPath'
    OUTPUTS: tuple[str, ...] = ('image', 'mask', 'mask_inverted')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'MASK', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        alignment: str = "center",
        coordinates: str,
        font: str,
        font_size: int = 42,
        frame_height: int = 512,
        frame_width: int = 512,
        text: str = "text",
        text_color: str = "white",
        size_multiplier: float = [1.0],
    ) -> "_NodeBuilder":
        """Add a ``CreateTextOnPath`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CreateTextOnPath',
            alignment=alignment,
            coordinates=coordinates,
            font=font,
            font_size=font_size,
            frame_height=frame_height,
            frame_width=frame_width,
            text=text,
            text_color=text_color,
            size_multiplier=size_multiplier,
        )

class CreateVoronoiMask:
    """Typed wrapper for the ComfyUI node class ``CreateVoronoiMask``.

    Display name: Create Voronoi Mask

    Category: KJNodes/masking/generate
    """

    CLASS_TYPE = 'CreateVoronoiMask'
    OUTPUTS: tuple[str, ...] = ('mask', 'mask_inverted')
    OUTPUT_TYPES: tuple[str, ...] = ('MASK', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        frame_height: int = 512,
        frame_width: int = 512,
        frames: int = 16,
        line_width: int = 4,
        num_points: int = 15,
        speed: float = 0.5,
    ) -> "_NodeBuilder":
        """Add a ``CreateVoronoiMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CreateVoronoiMask',
            frame_height=frame_height,
            frame_width=frame_width,
            frames=frames,
            line_width=line_width,
            num_points=num_points,
            speed=speed,
        )

class CrossFadeImages:
    """Typed wrapper for the ComfyUI node class ``CrossFadeImages``.

    Display name: Cross Fade Images

    Category: KJNodes/image
    """

    CLASS_TYPE = 'CrossFadeImages'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images_1: "Handle" = None,
        images_2: "Handle" = None,
        end_level: float = 1.0,
        interpolation: str,
        start_level: float = 0.0,
        transition_start_index: int = 1,
        transitioning_frames: int = 1,
    ) -> "_NodeBuilder":
        """Add a ``CrossFadeImages`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CrossFadeImages',
            images_1=images_1,
            images_2=images_2,
            end_level=end_level,
            interpolation=interpolation,
            start_level=start_level,
            transition_start_index=transition_start_index,
            transitioning_frames=transitioning_frames,
        )

class CrossFadeImagesMulti:
    """Typed wrapper for the ComfyUI node class ``CrossFadeImagesMulti``.

    Display name: Cross Fade Images Multi

    Category: KJNodes/image
    """

    CLASS_TYPE = 'CrossFadeImagesMulti'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image_1: "Handle" = None,
        inputcount: int = 2,
        interpolation: str,
        transitioning_frames: int = 1,
        image_2: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``CrossFadeImagesMulti`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CrossFadeImagesMulti',
            image_1=image_1,
            inputcount=inputcount,
            interpolation=interpolation,
            transitioning_frames=transitioning_frames,
            image_2=image_2,
        )

class CustomControlNetWeightsFluxFromList:
    """Typed wrapper for the ComfyUI node class ``CustomControlNetWeightsFluxFromList``.

    Display name: Custom ControlNet Weights Flux From List

    Category: KJNodes/controlnet

    Creates controlnet weights from a list of floats for Advanced-ControlNet
    """

    CLASS_TYPE = 'CustomControlNetWeightsFluxFromList'
    OUTPUTS: tuple[str, ...] = ('CN_WEIGHTS', 'TK_SHORTCUT')
    OUTPUT_TYPES: tuple[str, ...] = ('CONTROL_NET_WEIGHTS', 'TIMESTEP_KEYFRAME')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        list_of_floats: float,
        autosize: "Handle" = None,
        cn_extras: "Handle" = None,
        uncond_multiplier: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``CustomControlNetWeightsFluxFromList`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CustomControlNetWeightsFluxFromList',
            list_of_floats=list_of_floats,
            autosize=autosize,
            cn_extras=cn_extras,
            uncond_multiplier=uncond_multiplier,
        )

class CustomSigmas:
    """Typed wrapper for the ComfyUI node class ``CustomSigmas``.

    Display name: Custom Sigmas

    Category: KJNodes/noise

    Creates a sigmas tensor from a string of comma separated values.
    """

    CLASS_TYPE = 'CustomSigmas'
    OUTPUTS: tuple[str, ...] = ('SIGMAS',)
    OUTPUT_TYPES: tuple[str, ...] = ('SIGMAS',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        interpolate_to_steps: int = 10,
        sigmas_string: str = "14.615, 6.475, 3.861, 2.697, 1.886, 1.396, 0.963, 0.652, 0.399, 0.152, 0.029",
    ) -> "_NodeBuilder":
        """Add a ``CustomSigmas`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CustomSigmas',
            interpolate_to_steps=interpolate_to_steps,
            sigmas_string=sigmas_string,
        )

class CutAndDragOnPath:
    """Typed wrapper for the ComfyUI node class ``CutAndDragOnPath``.

    Display name: Cut And Drag On Path

    Category: KJNodes/image

    Cuts the masked area from the image, and drags it along the path. If inpaint is enabled, and no bg_image is provided, the cut area is filled using cv2 TELEA algorithm.
    """

    CLASS_TYPE = 'CutAndDragOnPath'
    OUTPUTS: tuple[str, ...] = ('image', 'mask')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        mask: "Handle" = None,
        coordinates: str,
        frame_height: int = 512,
        frame_width: int = 512,
        inpaint: bool = True,
        bg_image: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``CutAndDragOnPath`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'CutAndDragOnPath',
            image=image,
            mask=mask,
            coordinates=coordinates,
            frame_height=frame_height,
            frame_width=frame_width,
            inpaint=inpaint,
            bg_image=bg_image,
        )

class DecodeAndSaveVideo:
    """Typed wrapper for the ComfyUI node class ``DecodeAndSaveVideo``.

    Display name: Decode and Save Video

    Category: KJNodes/image

    Decodes video frames and audio from latent representations, combines them, and saves as a video file, without keeping intermediate images in memory.
    """

    CLASS_TYPE = 'DecodeAndSaveVideo'
    OUTPUTS: tuple[str, ...] = ()
    OUTPUT_TYPES: tuple[str, ...] = ()

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        tiling: "Handle" = None,
        video_latent: "Handle" = None,
        video_vae: "Handle" = None,
        codec: str = "auto",
        filename_prefix: str = "video/ComfyUI",
        format: str = "auto",
        fps: float = 25.0,
        audio_latent: "Handle" = None,
        audio_vae: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``DecodeAndSaveVideo`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'DecodeAndSaveVideo',
            tiling=tiling,
            video_latent=video_latent,
            video_vae=video_vae,
            codec=codec,
            filename_prefix=filename_prefix,
            format=format,
            fps=fps,
            audio_latent=audio_latent,
            audio_vae=audio_vae,
        )

class DiTBlockLoraLoader:
    """Typed wrapper for the ComfyUI node class ``DiTBlockLoraLoader``.

    Display name: DiT Block Lora Loader

    Category: KJNodes/lora
    """

    CLASS_TYPE = 'DiTBlockLoraLoader'
    OUTPUTS: tuple[str, ...] = ('model', 'rank')
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL', 'STRING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        strength_model: float = 1.0,
        blocks: "Handle" = None,
        lora_name: str = "",
        opt_lora_path: str = "",
    ) -> "_NodeBuilder":
        """Add a ``DiTBlockLoraLoader`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'DiTBlockLoraLoader',
            model=model,
            strength_model=strength_model,
            blocks=blocks,
            lora_name=lora_name,
            opt_lora_path=opt_lora_path,
        )

class DifferentialDiffusionAdvanced:
    """Typed wrapper for the ComfyUI node class ``DifferentialDiffusionAdvanced``.

    Display name: Differential Diffusion Advanced

    Category: _for_testing
    """

    CLASS_TYPE = 'DifferentialDiffusionAdvanced'
    OUTPUTS: tuple[str, ...] = ('MODEL', 'LATENT')
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL', 'LATENT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        mask: "Handle" = None,
        model: "Handle" = None,
        samples: "Handle" = None,
        multiplier: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``DifferentialDiffusionAdvanced`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'DifferentialDiffusionAdvanced',
            mask=mask,
            model=model,
            samples=samples,
            multiplier=multiplier,
        )

class DiffusionModelLoaderKJ:
    """Typed wrapper for the ComfyUI node class ``DiffusionModelLoaderKJ``.

    Display name: Diffusion Model Loader KJ

    Category: KJNodes/model_loaders

    Node for patching torch.nn.Linear with CublasLinear.
    """

    CLASS_TYPE = 'DiffusionModelLoaderKJ'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        compute_dtype: str = "default",
        enable_fp16_accumulation: bool = False,
        model_name: str,
        patch_cublaslinear: bool = False,
        sage_attention: str = False,
        weight_dtype: str,
        extra_state_dict: str = "",
    ) -> "_NodeBuilder":
        """Add a ``DiffusionModelLoaderKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'DiffusionModelLoaderKJ',
            compute_dtype=compute_dtype,
            enable_fp16_accumulation=enable_fp16_accumulation,
            model_name=model_name,
            patch_cublaslinear=patch_cublaslinear,
            sage_attention=sage_attention,
            weight_dtype=weight_dtype,
            extra_state_dict=extra_state_dict,
        )

class DiffusionModelSelector:
    """Typed wrapper for the ComfyUI node class ``DiffusionModelSelector``.

    Display name: Diffusion Model Selector

    Category: KJNodes/model_loaders

    Returns the path to the model as a string.
    """

    CLASS_TYPE = 'DiffusionModelSelector'
    OUTPUTS: tuple[str, ...] = ('model_path',)
    OUTPUT_TYPES: tuple[str, ...] = ('STRING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model_name: str,
    ) -> "_NodeBuilder":
        """Add a ``DiffusionModelSelector`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'DiffusionModelSelector',
            model_name=model_name,
        )

class DownloadAndLoadCLIPSeg:
    """Typed wrapper for the ComfyUI node class ``DownloadAndLoadCLIPSeg``.

    Display name: (Down)load CLIPSeg

    Category: KJNodes/masking

    Downloads and loads CLIPSeg model with huggingface_hub,
    """

    CLASS_TYPE = 'DownloadAndLoadCLIPSeg'
    OUTPUTS: tuple[str, ...] = ('clipseg_model',)
    OUTPUT_TYPES: tuple[str, ...] = ('CLIPSEGMODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: str,
    ) -> "_NodeBuilder":
        """Add a ``DownloadAndLoadCLIPSeg`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'DownloadAndLoadCLIPSeg',
            model=model,
        )

class DrawInstanceDiffusionTracking:
    """Typed wrapper for the ComfyUI node class ``DrawInstanceDiffusionTracking``.

    Category: KJNodes/InstanceDiffusion

    Draws the tracking data from
    """

    CLASS_TYPE = 'DrawInstanceDiffusionTracking'
    OUTPUTS: tuple[str, ...] = ('image',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        box_line_width: int = 2,
        draw_text: bool = True,
        font: str,
        font_size: int = 20,
        tracking: "Handle",
    ) -> "_NodeBuilder":
        """Add a ``DrawInstanceDiffusionTracking`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'DrawInstanceDiffusionTracking',
            image=image,
            box_line_width=box_line_width,
            draw_text=draw_text,
            font=font,
            font_size=font_size,
            tracking=tracking,
        )

class DrawMaskOnImage:
    """Typed wrapper for the ComfyUI node class ``DrawMaskOnImage``.

    Display name: Draw Mask On Image

    Category: KJNodes/masking

    Applies the provided masks to the input images with Alpha Blending support.
    """

    CLASS_TYPE = 'DrawMaskOnImage'
    OUTPUTS: tuple[str, ...] = ('images',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        mask: "Handle" = None,
        color: str = "0, 0, 0",
        device: str = "cpu",
    ) -> "_NodeBuilder":
        """Add a ``DrawMaskOnImage`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'DrawMaskOnImage',
            image=image,
            mask=mask,
            color=color,
            device=device,
        )

class DummyOut:
    """Typed wrapper for the ComfyUI node class ``DummyOut``.

    Display name: Dummy Out

    Category: KJNodes/misc

    Does nothing, used to trigger generic workflow output.
    """

    CLASS_TYPE = 'DummyOut'
    OUTPUTS: tuple[str, ...] = ('*',)
    OUTPUT_TYPES: tuple[str, ...] = ('*',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        any_input: "Handle",
    ) -> "_NodeBuilder":
        """Add a ``DummyOut`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'DummyOut',
            any_input=any_input,
        )

class EmptyLatentImageCustomPresets:
    """Typed wrapper for the ComfyUI node class ``EmptyLatentImageCustomPresets``.

    Display name: Empty Latent Image Custom Presets

    Category: KJNodes/latents

    Generates an empty latent image with the specified dimensions.
    """

    CLASS_TYPE = 'EmptyLatentImageCustomPresets'
    OUTPUTS: tuple[str, ...] = ('Latent', 'Width', 'Height')
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT', 'INT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        batch_size: int = 1,
        dimensions: str,
        invert: bool = False,
    ) -> "_NodeBuilder":
        """Add a ``EmptyLatentImageCustomPresets`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'EmptyLatentImageCustomPresets',
            batch_size=batch_size,
            dimensions=dimensions,
            invert=invert,
        )

class EmptyLatentImagePresets:
    """Typed wrapper for the ComfyUI node class ``EmptyLatentImagePresets``.

    Display name: Empty Latent Image Presets

    Category: KJNodes/latents
    """

    CLASS_TYPE = 'EmptyLatentImagePresets'
    OUTPUTS: tuple[str, ...] = ('Latent', 'Width', 'Height')
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT', 'INT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        batch_size: int = 1,
        dimensions: str = "512 x 512 (1:1)",
        invert: bool = False,
    ) -> "_NodeBuilder":
        """Add a ``EmptyLatentImagePresets`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'EmptyLatentImagePresets',
            batch_size=batch_size,
            dimensions=dimensions,
            invert=invert,
        )

class EncodeVideoComponents:
    """Typed wrapper for the ComfyUI node class ``EncodeVideoComponents``.

    Display name: Encode Video Components

    Category: KJNodes/image

    Extracts video frames, resizes them, and encodes with a VAE directly, avoiding storing the full image tensor.
    """

    CLASS_TYPE = 'EncodeVideoComponents'
    OUTPUTS: tuple[str, ...] = ('latent', 'audio', 'fps', 'frame_count')
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT', 'AUDIO', 'FLOAT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        keep_proportion: "Handle" = None,
        vae: "Handle" = None,
        video: "Handle" = None,
        height: int = 512,
        max_frames: int = 0,
        upscale_method: str = "lanczos",
        width: int = 768,
    ) -> "_NodeBuilder":
        """Add a ``EncodeVideoComponents`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'EncodeVideoComponents',
            keep_proportion=keep_proportion,
            vae=vae,
            video=video,
            height=height,
            max_frames=max_frames,
            upscale_method=upscale_method,
            width=width,
        )

class EndRecordCUDAMemoryHistory:
    """Typed wrapper for the ComfyUI node class ``EndRecordCUDAMemoryHistory``.

    Display name: End Recording CUDAMemory History

    Category: KJNodes/memory

    Records CUDA memory allocation history between start and end, saves to a file that can be analyzed here: https://docs.pytorch.org/memory_viz or with VisualizeCUDAMemoryHistory node
    """

    CLASS_TYPE = 'EndRecordCUDAMemoryHistory'
    OUTPUTS: tuple[str, ...] = ('input', 'output_path')
    OUTPUT_TYPES: tuple[str, ...] = ('*', 'STRING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        input: "Handle",
        output_path: str = "comfy_cuda_memory_history",
    ) -> "_NodeBuilder":
        """Add a ``EndRecordCUDAMemoryHistory`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'EndRecordCUDAMemoryHistory',
            input=input,
            output_path=output_path,
        )

class FastPreview:
    """Typed wrapper for the ComfyUI node class ``FastPreview``.

    Display name: Fast Preview

    Category: KJNodes/experimental

    Fast image preview using binary websocket, bypassing base64/JSON overhead.
    """

    CLASS_TYPE = 'FastPreview'
    OUTPUTS: tuple[str, ...] = ()
    OUTPUT_TYPES: tuple[str, ...] = ()

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        format: str = "JPEG",
        max_size: int = 768,
    ) -> "_NodeBuilder":
        """Add a ``FastPreview`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'FastPreview',
            image=image,
            format=format,
            max_size=max_size,
        )

class FilterZeroMasksAndCorrespondingImages:
    """Typed wrapper for the ComfyUI node class ``FilterZeroMasksAndCorrespondingImages``.

    Category: KJNodes/masking

    Filter out all the empty (i.e. all zero) mask in masks
    """

    CLASS_TYPE = 'FilterZeroMasksAndCorrespondingImages'
    OUTPUTS: tuple[str, ...] = ('non_zero_masks_out', 'non_zero_mask_images_out', 'zero_mask_images_out', 'zero_mask_images_out_indexes')
    OUTPUT_TYPES: tuple[str, ...] = ('MASK', 'IMAGE', 'IMAGE', 'INDEXES')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        masks: "Handle" = None,
        original_images: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``FilterZeroMasksAndCorrespondingImages`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'FilterZeroMasksAndCorrespondingImages',
            masks=masks,
            original_images=original_images,
        )

class FlipSigmasAdjusted:
    """Typed wrapper for the ComfyUI node class ``FlipSigmasAdjusted``.

    Display name: Flip Sigmas Adjusted

    Category: KJNodes/noise
    """

    CLASS_TYPE = 'FlipSigmasAdjusted'
    OUTPUTS: tuple[str, ...] = ('SIGMAS', 'sigmas_string')
    OUTPUT_TYPES: tuple[str, ...] = ('SIGMAS', 'STRING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        sigmas: "Handle" = None,
        divide_by: float = 1,
        divide_by_last_sigma: bool = False,
        offset_by: int = 1,
    ) -> "_NodeBuilder":
        """Add a ``FlipSigmasAdjusted`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'FlipSigmasAdjusted',
            sigmas=sigmas,
            divide_by=divide_by,
            divide_by_last_sigma=divide_by_last_sigma,
            offset_by=offset_by,
        )

class FloatConstant:
    """Typed wrapper for the ComfyUI node class ``FloatConstant``.

    Display name: Float Constant

    Category: KJNodes/constants
    """

    CLASS_TYPE = 'FloatConstant'
    OUTPUTS: tuple[str, ...] = ('value',)
    OUTPUT_TYPES: tuple[str, ...] = ('FLOAT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        value: float = 0.0,
    ) -> "_NodeBuilder":
        """Add a ``FloatConstant`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'FloatConstant',
            value=value,
        )

class FloatToMask:
    """Typed wrapper for the ComfyUI node class ``FloatToMask``.

    Display name: Float To Mask

    Category: KJNodes/masking/generate

    Generates a batch of masks based on the input float values.
    """

    CLASS_TYPE = 'FloatToMask'
    OUTPUTS: tuple[str, ...] = ('MASK',)
    OUTPUT_TYPES: tuple[str, ...] = ('MASK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        height: int = 100,
        input_values: float = 0,
        width: int = 100,
    ) -> "_NodeBuilder":
        """Add a ``FloatToMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'FloatToMask',
            height=height,
            input_values=input_values,
            width=width,
        )

class FloatToSigmas:
    """Typed wrapper for the ComfyUI node class ``FloatToSigmas``.

    Display name: Float To Sigmas

    Category: KJNodes/noise

    Creates a sigmas tensor from list of float values.
    """

    CLASS_TYPE = 'FloatToSigmas'
    OUTPUTS: tuple[str, ...] = ('SIGMAS',)
    OUTPUT_TYPES: tuple[str, ...] = ('SIGMAS',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        float_list: float = 0.0,
    ) -> "_NodeBuilder":
        """Add a ``FloatToSigmas`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'FloatToSigmas',
            float_list=float_list,
        )

class FluxBlockLoraSelect:
    """Typed wrapper for the ComfyUI node class ``FluxBlockLoraSelect``.

    Display name: Flux Block Lora Select

    Category: KJNodes/experimental

    Select individual block alpha values, value of 0 removes the block altogether
    """

    CLASS_TYPE = 'FluxBlockLoraSelect'
    OUTPUTS: tuple[str, ...] = ('blocks',)
    OUTPUT_TYPES: tuple[str, ...] = ('SELECTEDDITBLOCKS',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        double_blocks_0: float = 0.0,
        double_blocks_1: float = 0.0,
        double_blocks_10: float = 0.0,
        double_blocks_11: float = 0.0,
        double_blocks_12: float = 0.0,
        double_blocks_13: float = 0.0,
        double_blocks_14: float = 0.0,
        double_blocks_15: float = 0.0,
        double_blocks_16: float = 0.0,
        double_blocks_17: float = 0.0,
        double_blocks_18: float = 0.0,
        double_blocks_2: float = 0.0,
        double_blocks_3: float = 0.0,
        double_blocks_4: float = 0.0,
        double_blocks_5: float = 0.0,
        double_blocks_6: float = 0.0,
        double_blocks_7: float = 0.0,
        double_blocks_8: float = 0.0,
        double_blocks_9: float = 0.0,
        single_blocks_0: float = 0.0,
        single_blocks_1: float = 0.0,
        single_blocks_10: float = 0.0,
        single_blocks_11: float = 0.0,
        single_blocks_12: float = 0.0,
        single_blocks_13: float = 0.0,
        single_blocks_14: float = 0.0,
        single_blocks_15: float = 0.0,
        single_blocks_16: float = 0.0,
        single_blocks_17: float = 0.0,
        single_blocks_18: float = 0.0,
        single_blocks_19: float = 0.0,
        single_blocks_2: float = 0.0,
        single_blocks_20: float = 0.0,
        single_blocks_21: float = 0.0,
        single_blocks_22: float = 0.0,
        single_blocks_23: float = 0.0,
        single_blocks_24: float = 0.0,
        single_blocks_25: float = 0.0,
        single_blocks_26: float = 0.0,
        single_blocks_27: float = 0.0,
        single_blocks_28: float = 0.0,
        single_blocks_29: float = 0.0,
        single_blocks_3: float = 0.0,
        single_blocks_30: float = 0.0,
        single_blocks_31: float = 0.0,
        single_blocks_32: float = 0.0,
        single_blocks_33: float = 0.0,
        single_blocks_34: float = 0.0,
        single_blocks_35: float = 0.0,
        single_blocks_36: float = 0.0,
        single_blocks_37: float = 0.0,
        single_blocks_4: float = 0.0,
        single_blocks_5: float = 0.0,
        single_blocks_6: float = 0.0,
        single_blocks_7: float = 0.0,
        single_blocks_8: float = 0.0,
        single_blocks_9: float = 0.0,
    ) -> "_NodeBuilder":
        """Add a ``FluxBlockLoraSelect`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'FluxBlockLoraSelect',
            **{
                'double_blocks.0.': double_blocks_0,
                'double_blocks.1.': double_blocks_1,
                'double_blocks.10.': double_blocks_10,
                'double_blocks.11.': double_blocks_11,
                'double_blocks.12.': double_blocks_12,
                'double_blocks.13.': double_blocks_13,
                'double_blocks.14.': double_blocks_14,
                'double_blocks.15.': double_blocks_15,
                'double_blocks.16.': double_blocks_16,
                'double_blocks.17.': double_blocks_17,
                'double_blocks.18.': double_blocks_18,
                'double_blocks.2.': double_blocks_2,
                'double_blocks.3.': double_blocks_3,
                'double_blocks.4.': double_blocks_4,
                'double_blocks.5.': double_blocks_5,
                'double_blocks.6.': double_blocks_6,
                'double_blocks.7.': double_blocks_7,
                'double_blocks.8.': double_blocks_8,
                'double_blocks.9.': double_blocks_9,
                'single_blocks.0.': single_blocks_0,
                'single_blocks.1.': single_blocks_1,
                'single_blocks.10.': single_blocks_10,
                'single_blocks.11.': single_blocks_11,
                'single_blocks.12.': single_blocks_12,
                'single_blocks.13.': single_blocks_13,
                'single_blocks.14.': single_blocks_14,
                'single_blocks.15.': single_blocks_15,
                'single_blocks.16.': single_blocks_16,
                'single_blocks.17.': single_blocks_17,
                'single_blocks.18.': single_blocks_18,
                'single_blocks.19.': single_blocks_19,
                'single_blocks.2.': single_blocks_2,
                'single_blocks.20.': single_blocks_20,
                'single_blocks.21.': single_blocks_21,
                'single_blocks.22.': single_blocks_22,
                'single_blocks.23.': single_blocks_23,
                'single_blocks.24.': single_blocks_24,
                'single_blocks.25.': single_blocks_25,
                'single_blocks.26.': single_blocks_26,
                'single_blocks.27.': single_blocks_27,
                'single_blocks.28.': single_blocks_28,
                'single_blocks.29.': single_blocks_29,
                'single_blocks.3.': single_blocks_3,
                'single_blocks.30.': single_blocks_30,
                'single_blocks.31.': single_blocks_31,
                'single_blocks.32.': single_blocks_32,
                'single_blocks.33.': single_blocks_33,
                'single_blocks.34.': single_blocks_34,
                'single_blocks.35.': single_blocks_35,
                'single_blocks.36.': single_blocks_36,
                'single_blocks.37.': single_blocks_37,
                'single_blocks.4.': single_blocks_4,
                'single_blocks.5.': single_blocks_5,
                'single_blocks.6.': single_blocks_6,
                'single_blocks.7.': single_blocks_7,
                'single_blocks.8.': single_blocks_8,
                'single_blocks.9.': single_blocks_9,
            },
        )

class GGUFLoaderKJ:
    """Typed wrapper for the ComfyUI node class ``GGUFLoaderKJ``.

    Category: KJNodes/model_loaders

    Loads a GGUF model with advanced options, requires [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) to be installed.
    """

    CLASS_TYPE = 'GGUFLoaderKJ'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        attention_override: str = "none",
        dequant_dtype: str = "default",
        enable_fp16_accumulation: bool = False,
        extra_model_name: str = "none",
        model_name: str,
        patch_dtype: str = "default",
        patch_on_device: bool = False,
    ) -> "_NodeBuilder":
        """Add a ``GGUFLoaderKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'GGUFLoaderKJ',
            attention_override=attention_override,
            dequant_dtype=dequant_dtype,
            enable_fp16_accumulation=enable_fp16_accumulation,
            extra_model_name=extra_model_name,
            model_name=model_name,
            patch_dtype=patch_dtype,
            patch_on_device=patch_on_device,
        )

class GLIGENTextBoxApplyBatchCoords:
    """Typed wrapper for the ComfyUI node class ``GLIGENTextBoxApplyBatchCoords``.

    Category: KJNodes/experimental

    This node allows scheduling GLIGEN text box positions in a batch,
    """

    CLASS_TYPE = 'GLIGENTextBoxApplyBatchCoords'
    OUTPUTS: tuple[str, ...] = ('conditioning', 'coord_preview')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'IMAGE')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        clip: "Handle" = None,
        conditioning_to: "Handle" = None,
        gligen_textbox_model: "Handle" = None,
        latents: "Handle" = None,
        coordinates: str,
        height: int = 128,
        text: str,
        width: int = 128,
        size_multiplier: float = [1.0],
    ) -> "_NodeBuilder":
        """Add a ``GLIGENTextBoxApplyBatchCoords`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'GLIGENTextBoxApplyBatchCoords',
            clip=clip,
            conditioning_to=conditioning_to,
            gligen_textbox_model=gligen_textbox_model,
            latents=latents,
            coordinates=coordinates,
            height=height,
            text=text,
            width=width,
            size_multiplier=size_multiplier,
        )

class GenerateNoise:
    """Typed wrapper for the ComfyUI node class ``GenerateNoise``.

    Display name: Generate Noise

    Category: KJNodes/noise

    Generates noise for injection or to be used as empty latents on samplers with add_noise off.
    """

    CLASS_TYPE = 'GenerateNoise'
    OUTPUTS: tuple[str, ...] = ('LATENT',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        batch_size: int = 1,
        constant_batch_noise: bool = False,
        height: int = 512,
        multiplier: float = 1.0,
        normalize: bool = False,
        seed: int = 123,
        width: int = 512,
        latent_channels: str = "",
        model: "Handle" = None,
        shape: str = "",
        sigmas: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``GenerateNoise`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'GenerateNoise',
            batch_size=batch_size,
            constant_batch_noise=constant_batch_noise,
            height=height,
            multiplier=multiplier,
            normalize=normalize,
            seed=seed,
            width=width,
            latent_channels=latent_channels,
            model=model,
            shape=shape,
            sigmas=sigmas,
        )

class GetImageSizeAndCount:
    """Typed wrapper for the ComfyUI node class ``GetImageSizeAndCount``.

    Display name: Get Image Size & Count

    Category: KJNodes/image

    Returns width, height and batch size of the image,
    """

    CLASS_TYPE = 'GetImageSizeAndCount'
    OUTPUTS: tuple[str, ...] = ('image', 'width', 'height', 'count')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'INT', 'INT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``GetImageSizeAndCount`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'GetImageSizeAndCount',
            image=image,
        )

class GetImagesFromBatchIndexed:
    """Typed wrapper for the ComfyUI node class ``GetImagesFromBatchIndexed``.

    Display name: Get Images From Batch Indexed

    Category: KJNodes/image

    Selects and returns the images at the specified indices as an image batch.
    """

    CLASS_TYPE = 'GetImagesFromBatchIndexed'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images: "Handle" = None,
        indexes: str = "0, 1, 2",
    ) -> "_NodeBuilder":
        """Add a ``GetImagesFromBatchIndexed`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'GetImagesFromBatchIndexed',
            images=images,
            indexes=indexes,
        )

class GetLatentRangeFromBatch:
    """Typed wrapper for the ComfyUI node class ``GetLatentRangeFromBatch``.

    Display name: Get Latent Range From Batch

    Category: KJNodes/latents

    Returns a range of latents from a batch.
    """

    CLASS_TYPE = 'GetLatentRangeFromBatch'
    OUTPUTS: tuple[str, ...] = ('LATENT',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latents: "Handle" = None,
        num_frames: int = 1,
        start_index: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``GetLatentRangeFromBatch`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'GetLatentRangeFromBatch',
            latents=latents,
            num_frames=num_frames,
            start_index=start_index,
        )

class GetLatentSizeAndCount:
    """Typed wrapper for the ComfyUI node class ``GetLatentSizeAndCount``.

    Display name: Get Latent Size & Count

    Category: KJNodes/image

    Returns latent tensor dimensions,
    """

    CLASS_TYPE = 'GetLatentSizeAndCount'
    OUTPUTS: tuple[str, ...] = ('latent', 'batch_size', 'channels', 'frames', 'height', 'width')
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT', 'INT', 'INT', 'INT', 'INT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latent: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``GetLatentSizeAndCount`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'GetLatentSizeAndCount',
            latent=latent,
        )

class GetLatentsFromBatchIndexed:
    """Typed wrapper for the ComfyUI node class ``GetLatentsFromBatchIndexed``.

    Display name: Get Latents From Batch Indexed

    Category: KJNodes/latents

    Selects and returns the latents at the specified indices as an latent batch.
    """

    CLASS_TYPE = 'GetLatentsFromBatchIndexed'
    OUTPUTS: tuple[str, ...] = ('LATENT',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latents: "Handle" = None,
        indexes: str = "0, 1, 2",
        latent_format: str = "BCHW",
    ) -> "_NodeBuilder":
        """Add a ``GetLatentsFromBatchIndexed`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'GetLatentsFromBatchIndexed',
            latents=latents,
            indexes=indexes,
            latent_format=latent_format,
        )

class GetMaskSizeAndCount:
    """Typed wrapper for the ComfyUI node class ``GetMaskSizeAndCount``.

    Display name: Get Mask Size & Count

    Category: KJNodes/masking

    Returns the width, height and batch size of the mask,
    """

    CLASS_TYPE = 'GetMaskSizeAndCount'
    OUTPUTS: tuple[str, ...] = ('mask', 'width', 'height', 'count')
    OUTPUT_TYPES: tuple[str, ...] = ('MASK', 'INT', 'INT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        mask: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``GetMaskSizeAndCount`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'GetMaskSizeAndCount',
            mask=mask,
        )

class GetTrackRange:
    """Typed wrapper for the ComfyUI node class ``GetTrackRange``.

    Category: conditioning/video_models
    """

    CLASS_TYPE = 'GetTrackRange'
    OUTPUTS: tuple[str, ...] = ('TRACKS',)
    OUTPUT_TYPES: tuple[str, ...] = ('TRACKS',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        num_frames: int = 10,
        start_index: int = 24,
        tracks: "Handle",
    ) -> "_NodeBuilder":
        """Add a ``GetTrackRange`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'GetTrackRange',
            num_frames=num_frames,
            start_index=start_index,
            tracks=tracks,
        )

class GradientToFloat:
    """Typed wrapper for the ComfyUI node class ``GradientToFloat``.

    Display name: Gradient To Float

    Category: KJNodes/image

    Calculates list of floats from image.
    """

    CLASS_TYPE = 'GradientToFloat'
    OUTPUTS: tuple[str, ...] = ('float_x', 'float_y')
    OUTPUT_TYPES: tuple[str, ...] = ('FLOAT', 'FLOAT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        steps: int = 10,
    ) -> "_NodeBuilder":
        """Add a ``GradientToFloat`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'GradientToFloat',
            image=image,
            steps=steps,
        )

class GrowMaskWithBlur:
    """Typed wrapper for the ComfyUI node class ``GrowMaskWithBlur``.

    Display name: Grow Mask With Blur

    Category: KJNodes/masking

    # GrowMaskWithBlur
    """

    CLASS_TYPE = 'GrowMaskWithBlur'
    OUTPUTS: tuple[str, ...] = ('mask', 'mask_inverted')
    OUTPUT_TYPES: tuple[str, ...] = ('MASK', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        mask: "Handle" = None,
        blur_radius: float = 0.0,
        decay_factor: float = 1.0,
        expand: int = 0,
        flip_input: bool = False,
        incremental_expandrate: float = 0.0,
        lerp_alpha: float = 1.0,
        tapered_corners: bool = True,
        fill_holes: bool = False,
    ) -> "_NodeBuilder":
        """Add a ``GrowMaskWithBlur`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'GrowMaskWithBlur',
            mask=mask,
            blur_radius=blur_radius,
            decay_factor=decay_factor,
            expand=expand,
            flip_input=flip_input,
            incremental_expandrate=incremental_expandrate,
            lerp_alpha=lerp_alpha,
            tapered_corners=tapered_corners,
            fill_holes=fill_holes,
        )

class HDRPreviewKJ:
    """Typed wrapper for the ComfyUI node class ``HDRPreviewKJ``.

    Display name: HDR Preview KJ

    Category: KJNodes/image

    Realtime-exposure preview for HDR-compressed images.
    """

    CLASS_TYPE = 'HDRPreviewKJ'
    OUTPUTS: tuple[str, ...] = ('image',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        exposure: float = 0.0,
        saturation: float = 1.0,
        fps: float = 24.0,
        input_space: str = "logc3",
    ) -> "_NodeBuilder":
        """Add a ``HDRPreviewKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'HDRPreviewKJ',
            image=image,
            exposure=exposure,
            saturation=saturation,
            fps=fps,
            input_space=input_space,
        )

class HunyuanVideoBlockLoraSelect:
    """Typed wrapper for the ComfyUI node class ``HunyuanVideoBlockLoraSelect``.

    Display name: Hunyuan Video Block Lora Select

    Category: KJNodes/hunyuanvideo

    Select individual block alpha values, value of 0 removes the block altogether
    """

    CLASS_TYPE = 'HunyuanVideoBlockLoraSelect'
    OUTPUTS: tuple[str, ...] = ('blocks',)
    OUTPUT_TYPES: tuple[str, ...] = ('SELECTEDDITBLOCKS',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        double_blocks_0: float = 0.0,
        double_blocks_1: float = 0.0,
        double_blocks_10: float = 0.0,
        double_blocks_11: float = 0.0,
        double_blocks_12: float = 0.0,
        double_blocks_13: float = 0.0,
        double_blocks_14: float = 0.0,
        double_blocks_15: float = 0.0,
        double_blocks_16: float = 0.0,
        double_blocks_17: float = 0.0,
        double_blocks_18: float = 0.0,
        double_blocks_19: float = 0.0,
        double_blocks_2: float = 0.0,
        double_blocks_3: float = 0.0,
        double_blocks_4: float = 0.0,
        double_blocks_5: float = 0.0,
        double_blocks_6: float = 0.0,
        double_blocks_7: float = 0.0,
        double_blocks_8: float = 0.0,
        double_blocks_9: float = 0.0,
        single_blocks_0: float = 0.0,
        single_blocks_1: float = 0.0,
        single_blocks_10: float = 0.0,
        single_blocks_11: float = 0.0,
        single_blocks_12: float = 0.0,
        single_blocks_13: float = 0.0,
        single_blocks_14: float = 0.0,
        single_blocks_15: float = 0.0,
        single_blocks_16: float = 0.0,
        single_blocks_17: float = 0.0,
        single_blocks_18: float = 0.0,
        single_blocks_19: float = 0.0,
        single_blocks_2: float = 0.0,
        single_blocks_20: float = 0.0,
        single_blocks_21: float = 0.0,
        single_blocks_22: float = 0.0,
        single_blocks_23: float = 0.0,
        single_blocks_24: float = 0.0,
        single_blocks_25: float = 0.0,
        single_blocks_26: float = 0.0,
        single_blocks_27: float = 0.0,
        single_blocks_28: float = 0.0,
        single_blocks_29: float = 0.0,
        single_blocks_3: float = 0.0,
        single_blocks_30: float = 0.0,
        single_blocks_31: float = 0.0,
        single_blocks_32: float = 0.0,
        single_blocks_33: float = 0.0,
        single_blocks_34: float = 0.0,
        single_blocks_35: float = 0.0,
        single_blocks_36: float = 0.0,
        single_blocks_37: float = 0.0,
        single_blocks_38: float = 0.0,
        single_blocks_39: float = 0.0,
        single_blocks_4: float = 0.0,
        single_blocks_5: float = 0.0,
        single_blocks_6: float = 0.0,
        single_blocks_7: float = 0.0,
        single_blocks_8: float = 0.0,
        single_blocks_9: float = 0.0,
    ) -> "_NodeBuilder":
        """Add a ``HunyuanVideoBlockLoraSelect`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'HunyuanVideoBlockLoraSelect',
            **{
                'double_blocks.0.': double_blocks_0,
                'double_blocks.1.': double_blocks_1,
                'double_blocks.10.': double_blocks_10,
                'double_blocks.11.': double_blocks_11,
                'double_blocks.12.': double_blocks_12,
                'double_blocks.13.': double_blocks_13,
                'double_blocks.14.': double_blocks_14,
                'double_blocks.15.': double_blocks_15,
                'double_blocks.16.': double_blocks_16,
                'double_blocks.17.': double_blocks_17,
                'double_blocks.18.': double_blocks_18,
                'double_blocks.19.': double_blocks_19,
                'double_blocks.2.': double_blocks_2,
                'double_blocks.3.': double_blocks_3,
                'double_blocks.4.': double_blocks_4,
                'double_blocks.5.': double_blocks_5,
                'double_blocks.6.': double_blocks_6,
                'double_blocks.7.': double_blocks_7,
                'double_blocks.8.': double_blocks_8,
                'double_blocks.9.': double_blocks_9,
                'single_blocks.0.': single_blocks_0,
                'single_blocks.1.': single_blocks_1,
                'single_blocks.10.': single_blocks_10,
                'single_blocks.11.': single_blocks_11,
                'single_blocks.12.': single_blocks_12,
                'single_blocks.13.': single_blocks_13,
                'single_blocks.14.': single_blocks_14,
                'single_blocks.15.': single_blocks_15,
                'single_blocks.16.': single_blocks_16,
                'single_blocks.17.': single_blocks_17,
                'single_blocks.18.': single_blocks_18,
                'single_blocks.19.': single_blocks_19,
                'single_blocks.2.': single_blocks_2,
                'single_blocks.20.': single_blocks_20,
                'single_blocks.21.': single_blocks_21,
                'single_blocks.22.': single_blocks_22,
                'single_blocks.23.': single_blocks_23,
                'single_blocks.24.': single_blocks_24,
                'single_blocks.25.': single_blocks_25,
                'single_blocks.26.': single_blocks_26,
                'single_blocks.27.': single_blocks_27,
                'single_blocks.28.': single_blocks_28,
                'single_blocks.29.': single_blocks_29,
                'single_blocks.3.': single_blocks_3,
                'single_blocks.30.': single_blocks_30,
                'single_blocks.31.': single_blocks_31,
                'single_blocks.32.': single_blocks_32,
                'single_blocks.33.': single_blocks_33,
                'single_blocks.34.': single_blocks_34,
                'single_blocks.35.': single_blocks_35,
                'single_blocks.36.': single_blocks_36,
                'single_blocks.37.': single_blocks_37,
                'single_blocks.38.': single_blocks_38,
                'single_blocks.39.': single_blocks_39,
                'single_blocks.4.': single_blocks_4,
                'single_blocks.5.': single_blocks_5,
                'single_blocks.6.': single_blocks_6,
                'single_blocks.7.': single_blocks_7,
                'single_blocks.8.': single_blocks_8,
                'single_blocks.9.': single_blocks_9,
            },
        )

class HunyuanVideoEncodeKeyframesToCond:
    """Typed wrapper for the ComfyUI node class ``HunyuanVideoEncodeKeyframesToCond``.

    Display name: HunyuanVideo Encode Keyframes To Cond

    Category: KJNodes/hunyuanvideo
    """

    CLASS_TYPE = 'HunyuanVideoEncodeKeyframesToCond'
    OUTPUTS: tuple[str, ...] = ('model', 'positive', 'negative', 'latent')
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL', 'CONDITIONING', 'CONDITIONING', 'LATENT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        end_frame: "Handle" = None,
        model: "Handle" = None,
        positive: "Handle" = None,
        start_frame: "Handle" = None,
        vae: "Handle" = None,
        num_frames: int = 33,
        overlap: int = 64,
        temporal_overlap: int = 8,
        temporal_size: int = 64,
        tile_size: int = 512,
        negative: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``HunyuanVideoEncodeKeyframesToCond`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'HunyuanVideoEncodeKeyframesToCond',
            end_frame=end_frame,
            model=model,
            positive=positive,
            start_frame=start_frame,
            vae=vae,
            num_frames=num_frames,
            overlap=overlap,
            temporal_overlap=temporal_overlap,
            temporal_size=temporal_size,
            tile_size=tile_size,
            negative=negative,
        )

class INTConstant:
    """Typed wrapper for the ComfyUI node class ``INTConstant``.

    Display name: INT Constant

    Category: KJNodes/constants
    """

    CLASS_TYPE = 'INTConstant'
    OUTPUTS: tuple[str, ...] = ('value',)
    OUTPUT_TYPES: tuple[str, ...] = ('INT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        value: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``INTConstant`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'INTConstant',
            value=value,
        )

class ImageAddMulti:
    """Typed wrapper for the ComfyUI node class ``ImageAddMulti``.

    Display name: Image Add Multi

    Category: KJNodes/image

    Add blends multiple images together.
    """

    CLASS_TYPE = 'ImageAddMulti'
    OUTPUTS: tuple[str, ...] = ('images',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image_1: "Handle" = None,
        image_2: "Handle" = None,
        blend_amount: float = 0.5,
        blending: str = "add",
        inputcount: int = 2,
    ) -> "_NodeBuilder":
        """Add a ``ImageAddMulti`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageAddMulti',
            image_1=image_1,
            image_2=image_2,
            blend_amount=blend_amount,
            blending=blending,
            inputcount=inputcount,
        )

class ImageAndMaskPreview:
    """Typed wrapper for the ComfyUI node class ``ImageAndMaskPreview``.

    Category: KJNodes/masking

    Preview an image or a mask, when both inputs are used
    """

    CLASS_TYPE = 'ImageAndMaskPreview'
    OUTPUTS: tuple[str, ...] = ('composite',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        mask_color: str = "255, 255, 255",
        mask_opacity: float = 1.0,
        pass_through: bool = False,
        image: "Handle" = None,
        mask: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImageAndMaskPreview`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageAndMaskPreview',
            mask_color=mask_color,
            mask_opacity=mask_opacity,
            pass_through=pass_through,
            image=image,
            mask=mask,
        )

class ImageBatchExtendWithOverlap:
    """Typed wrapper for the ComfyUI node class ``ImageBatchExtendWithOverlap``.

    Display name: Image Batch Extend With Overlap

    Category: KJNodes/image

    Helper node for video generation extension
    """

    CLASS_TYPE = 'ImageBatchExtendWithOverlap'
    OUTPUTS: tuple[str, ...] = ('source_images', 'start_images', 'extended_images')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'IMAGE', 'IMAGE')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        source_images: "Handle" = None,
        overlap: int = 13,
        overlap_mode: str = "linear_blend",
        overlap_side: str = "source",
        new_images: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImageBatchExtendWithOverlap`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageBatchExtendWithOverlap',
            source_images=source_images,
            overlap=overlap,
            overlap_mode=overlap_mode,
            overlap_side=overlap_side,
            new_images=new_images,
        )

class ImageBatchFilter:
    """Typed wrapper for the ComfyUI node class ``ImageBatchFilter``.

    Display name: Image Batch Filter

    Category: KJNodes/image

    Removes empty images from a batch
    """

    CLASS_TYPE = 'ImageBatchFilter'
    OUTPUTS: tuple[str, ...] = ('images', 'removed_indices')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'STRING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images: "Handle" = None,
        empty_color: str = "0, 0, 0",
        empty_threshold: float = 0.01,
        replacement_image: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImageBatchFilter`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageBatchFilter',
            images=images,
            empty_color=empty_color,
            empty_threshold=empty_threshold,
            replacement_image=replacement_image,
        )

class ImageBatchJoinWithTransition:
    """Typed wrapper for the ComfyUI node class ``ImageBatchJoinWithTransition``.

    Display name: Image Batch Join With Transition

    Category: KJNodes/image

    Transitions between two batches of images, starting at a specified index in the first batch.
    """

    CLASS_TYPE = 'ImageBatchJoinWithTransition'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images_1: "Handle" = None,
        images_2: "Handle" = None,
        blur_radius: float = 0.0,
        device: str = "CPU",
        interpolation: str,
        reverse: bool = False,
        start_index: int = 0,
        transition_type: str,
        transitioning_frames: int = 1,
    ) -> "_NodeBuilder":
        """Add a ``ImageBatchJoinWithTransition`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageBatchJoinWithTransition',
            images_1=images_1,
            images_2=images_2,
            blur_radius=blur_radius,
            device=device,
            interpolation=interpolation,
            reverse=reverse,
            start_index=start_index,
            transition_type=transition_type,
            transitioning_frames=transitioning_frames,
        )

class ImageBatchMulti:
    """Typed wrapper for the ComfyUI node class ``ImageBatchMulti``.

    Display name: Image Batch Multi

    Category: KJNodes/image

    Creates an image batch from multiple images.
    """

    CLASS_TYPE = 'ImageBatchMulti'
    OUTPUTS: tuple[str, ...] = ('images',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image_1: "Handle" = None,
        inputcount: int = 2,
        image_2: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImageBatchMulti`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageBatchMulti',
            image_1=image_1,
            inputcount=inputcount,
            image_2=image_2,
        )

class ImageBatchRepeatInterleaving:
    """Typed wrapper for the ComfyUI node class ``ImageBatchRepeatInterleaving``.

    Category: KJNodes/image

    Repeats each image in a batch by the specified number of times.
    """

    CLASS_TYPE = 'ImageBatchRepeatInterleaving'
    OUTPUTS: tuple[str, ...] = ('IMAGE', 'MASK')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images: "Handle" = None,
        repeats: int = 1,
        mask: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImageBatchRepeatInterleaving`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageBatchRepeatInterleaving',
            images=images,
            repeats=repeats,
            mask=mask,
        )

class ImageBatchTestPattern:
    """Typed wrapper for the ComfyUI node class ``ImageBatchTestPattern``.

    Display name: Image Batch Test Pattern

    Category: KJNodes/text
    """

    CLASS_TYPE = 'ImageBatchTestPattern'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        batch_size: int = 1,
        font: str,
        font_size: int = 255,
        height: int = 512,
        start_from: int = 0,
        text_x: int = 256,
        text_y: int = 256,
        width: int = 512,
    ) -> "_NodeBuilder":
        """Add a ``ImageBatchTestPattern`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageBatchTestPattern',
            batch_size=batch_size,
            font=font,
            font_size=font_size,
            height=height,
            start_from=start_from,
            text_x=text_x,
            text_y=text_y,
            width=width,
        )

class ImageConcanate:
    """Typed wrapper for the ComfyUI node class ``ImageConcanate``.

    Display name: Image Concatenate

    Category: KJNodes/image

    Concatenates the image2 to image1 in the specified direction.
    """

    CLASS_TYPE = 'ImageConcanate'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image1: "Handle" = None,
        image2: "Handle" = None,
        direction: str = "right",
        match_image_size: bool = True,
    ) -> "_NodeBuilder":
        """Add a ``ImageConcanate`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageConcanate',
            image1=image1,
            image2=image2,
            direction=direction,
            match_image_size=match_image_size,
        )

class ImageConcatFromBatch:
    """Typed wrapper for the ComfyUI node class ``ImageConcatFromBatch``.

    Display name: Image Concatenate From Batch

    Category: KJNodes/image

    Concatenates images from a batch into a grid with a specified number of columns.
    """

    CLASS_TYPE = 'ImageConcatFromBatch'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images: "Handle" = None,
        match_image_size: bool = False,
        max_resolution: int = 4096,
        num_columns: int = 3,
    ) -> "_NodeBuilder":
        """Add a ``ImageConcatFromBatch`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageConcatFromBatch',
            images=images,
            match_image_size=match_image_size,
            max_resolution=max_resolution,
            num_columns=num_columns,
        )

class ImageConcatMulti:
    """Typed wrapper for the ComfyUI node class ``ImageConcatMulti``.

    Display name: Image Concatenate Multi

    Category: KJNodes/image

    Creates an image from multiple images.
    """

    CLASS_TYPE = 'ImageConcatMulti'
    OUTPUTS: tuple[str, ...] = ('images',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image_1: "Handle" = None,
        direction: str = "right",
        inputcount: int = 2,
        match_image_size: bool = False,
        image_2: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImageConcatMulti`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageConcatMulti',
            image_1=image_1,
            direction=direction,
            inputcount=inputcount,
            match_image_size=match_image_size,
            image_2=image_2,
        )

class ImageCropByMask:
    """Typed wrapper for the ComfyUI node class ``ImageCropByMask``.

    Display name: Image Crop By Mask

    Category: KJNodes/image

    Crops the input images based on the provided mask.
    """

    CLASS_TYPE = 'ImageCropByMask'
    OUTPUTS: tuple[str, ...] = ('image',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        mask: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImageCropByMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageCropByMask',
            image=image,
            mask=mask,
        )

class ImageCropByMaskAndResize:
    """Typed wrapper for the ComfyUI node class ``ImageCropByMaskAndResize``.

    Display name: Image Crop By Mask And Resize

    Category: KJNodes/image
    """

    CLASS_TYPE = 'ImageCropByMaskAndResize'
    OUTPUTS: tuple[str, ...] = ('images', 'masks', 'bbox')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'MASK', 'BBOX')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        mask: "Handle" = None,
        base_resolution: int = 512,
        max_crop_resolution: int = 512,
        min_crop_resolution: int = 128,
        padding: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``ImageCropByMaskAndResize`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageCropByMaskAndResize',
            image=image,
            mask=mask,
            base_resolution=base_resolution,
            max_crop_resolution=max_crop_resolution,
            min_crop_resolution=min_crop_resolution,
            padding=padding,
        )

class ImageCropByMaskBatch:
    """Typed wrapper for the ComfyUI node class ``ImageCropByMaskBatch``.

    Display name: Image Crop By Mask Batch

    Category: KJNodes/image

    Crops the input images based on the provided masks.
    """

    CLASS_TYPE = 'ImageCropByMaskBatch'
    OUTPUTS: tuple[str, ...] = ('images', 'masks')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        masks: "Handle" = None,
        bg_color: str = "0, 0, 0",
        height: int = 512,
        padding: int = 0,
        preserve_size: bool = False,
        width: int = 512,
    ) -> "_NodeBuilder":
        """Add a ``ImageCropByMaskBatch`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageCropByMaskBatch',
            image=image,
            masks=masks,
            bg_color=bg_color,
            height=height,
            padding=padding,
            preserve_size=preserve_size,
            width=width,
        )

class ImageGrabPIL:
    """Typed wrapper for the ComfyUI node class ``ImageGrabPIL``.

    Display name: Image Grab PIL

    Category: KJNodes/image

    Captures an area specified by screen coordinates.
    """

    CLASS_TYPE = 'ImageGrabPIL'
    OUTPUTS: tuple[str, ...] = ('image',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        delay: float = 0.1,
        height: int = 512,
        num_frames: int = 1,
        width: int = 512,
        x: int = 0,
        y: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``ImageGrabPIL`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageGrabPIL',
            delay=delay,
            height=height,
            num_frames=num_frames,
            width=width,
            x=x,
            y=y,
        )

class ImageGridComposite2x2:
    """Typed wrapper for the ComfyUI node class ``ImageGridComposite2x2``.

    Display name: Image Grid Composite 2x2

    Category: KJNodes/image

    Concatenates the 4 input images into a 2x2 grid.
    """

    CLASS_TYPE = 'ImageGridComposite2x2'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image1: "Handle" = None,
        image2: "Handle" = None,
        image3: "Handle" = None,
        image4: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImageGridComposite2x2`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageGridComposite2x2',
            image1=image1,
            image2=image2,
            image3=image3,
            image4=image4,
        )

class ImageGridComposite3x3:
    """Typed wrapper for the ComfyUI node class ``ImageGridComposite3x3``.

    Display name: Image Grid Composite 3x3

    Category: KJNodes/image

    Concatenates the 9 input images into a 3x3 grid.
    """

    CLASS_TYPE = 'ImageGridComposite3x3'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image1: "Handle" = None,
        image2: "Handle" = None,
        image3: "Handle" = None,
        image4: "Handle" = None,
        image5: "Handle" = None,
        image6: "Handle" = None,
        image7: "Handle" = None,
        image8: "Handle" = None,
        image9: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImageGridComposite3x3`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageGridComposite3x3',
            image1=image1,
            image2=image2,
            image3=image3,
            image4=image4,
            image5=image5,
            image6=image6,
            image7=image7,
            image8=image8,
            image9=image9,
        )

class ImageGridtoBatch:
    """Typed wrapper for the ComfyUI node class ``ImageGridtoBatch``.

    Display name: Image Grid To Batch

    Category: KJNodes/image

    Converts a grid of images to a batch of images.
    """

    CLASS_TYPE = 'ImageGridtoBatch'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        columns: int = 3,
        rows: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``ImageGridtoBatch`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageGridtoBatch',
            image=image,
            columns=columns,
            rows=rows,
        )

class ImageNoiseAugmentation:
    """Typed wrapper for the ComfyUI node class ``ImageNoiseAugmentation``.

    Display name: Image Noise Augmentation

    Category: KJNodes/image

    Add noise to an image.
    """

    CLASS_TYPE = 'ImageNoiseAugmentation'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        noise_aug_strength: float = None,
        seed: int = 123,
    ) -> "_NodeBuilder":
        """Add a ``ImageNoiseAugmentation`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageNoiseAugmentation',
            image=image,
            noise_aug_strength=noise_aug_strength,
            seed=seed,
        )

class ImageNormalize_Neg1_To_1:
    """Typed wrapper for the ComfyUI node class ``ImageNormalize_Neg1_To_1``.

    Display name: Image Normalize -1 to 1

    Category: KJNodes/image

    Normalize the images to be in the range [-1, 1]
    """

    CLASS_TYPE = 'ImageNormalize_Neg1_To_1'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImageNormalize_Neg1_To_1`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageNormalize_Neg1_To_1',
            images=images,
        )

class ImagePadForOutpaintMasked:
    """Typed wrapper for the ComfyUI node class ``ImagePadForOutpaintMasked``.

    Display name: Image Pad For Outpaint Masked

    Category: image
    """

    CLASS_TYPE = 'ImagePadForOutpaintMasked'
    OUTPUTS: tuple[str, ...] = ('IMAGE', 'MASK')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        bottom: int = 0,
        feathering: int = 0,
        left: int = 0,
        right: int = 0,
        top: int = 0,
        mask: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImagePadForOutpaintMasked`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImagePadForOutpaintMasked',
            image=image,
            bottom=bottom,
            feathering=feathering,
            left=left,
            right=right,
            top=top,
            mask=mask,
        )

class ImagePadForOutpaintTargetSize:
    """Typed wrapper for the ComfyUI node class ``ImagePadForOutpaintTargetSize``.

    Display name: Image Pad For Outpaint Target Size

    Category: image
    """

    CLASS_TYPE = 'ImagePadForOutpaintTargetSize'
    OUTPUTS: tuple[str, ...] = ('IMAGE', 'MASK')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        feathering: int = 0,
        target_height: int = 0,
        target_width: int = 0,
        upscale_method: str,
        mask: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImagePadForOutpaintTargetSize`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImagePadForOutpaintTargetSize',
            image=image,
            feathering=feathering,
            target_height=target_height,
            target_width=target_width,
            upscale_method=upscale_method,
            mask=mask,
        )

class ImagePadKJ:
    """Typed wrapper for the ComfyUI node class ``ImagePadKJ``.

    Display name: ImagePad KJ

    Category: KJNodes/image

    Pad the input image and optionally mask with the specified padding.
    """

    CLASS_TYPE = 'ImagePadKJ'
    OUTPUTS: tuple[str, ...] = ('images', 'masks')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        bottom: int = 0,
        color: str = "0, 0, 0",
        extra_padding: int = 0,
        left: int = 0,
        pad_mode: str,
        right: int = 0,
        top: int = 0,
        mask: "Handle" = None,
        target_height: int = 512,
        target_width: int = 512,
    ) -> "_NodeBuilder":
        """Add a ``ImagePadKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImagePadKJ',
            image=image,
            bottom=bottom,
            color=color,
            extra_padding=extra_padding,
            left=left,
            pad_mode=pad_mode,
            right=right,
            top=top,
            mask=mask,
            target_height=target_height,
            target_width=target_width,
        )

class ImagePass:
    """Typed wrapper for the ComfyUI node class ``ImagePass``.

    Category: KJNodes/image

    Passes the image through without modifying it.
    """

    CLASS_TYPE = 'ImagePass'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImagePass`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImagePass',
            image=image,
        )

class ImagePrepForICLora:
    """Typed wrapper for the ComfyUI node class ``ImagePrepForICLora``.

    Display name: Image Prep For ICLora

    Category: image
    """

    CLASS_TYPE = 'ImagePrepForICLora'
    OUTPUTS: tuple[str, ...] = ('IMAGE', 'MASK')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        reference_image: "Handle" = None,
        border_width: int = 0,
        output_height: int = 1024,
        output_width: int = 1024,
        latent_image: "Handle" = None,
        latent_mask: "Handle" = None,
        reference_mask: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImagePrepForICLora`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImagePrepForICLora',
            reference_image=reference_image,
            border_width=border_width,
            output_height=output_height,
            output_width=output_width,
            latent_image=latent_image,
            latent_mask=latent_mask,
            reference_mask=reference_mask,
        )

class ImageResizeKJ:
    """Typed wrapper for the ComfyUI node class ``ImageResizeKJ``.

    Display name: Resize Image (deprecated)

    Category: KJNodes/image

    DEPRECATED!
    """

    CLASS_TYPE = 'ImageResizeKJ'
    OUTPUTS: tuple[str, ...] = ('IMAGE', 'width', 'height')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'INT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        divisible_by: int = 2,
        height: int = 512,
        keep_proportion: bool = False,
        upscale_method: str,
        width: int = 512,
        crop: str = "",
        get_image_size: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImageResizeKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageResizeKJ',
            image=image,
            divisible_by=divisible_by,
            height=height,
            keep_proportion=keep_proportion,
            upscale_method=upscale_method,
            width=width,
            crop=crop,
            get_image_size=get_image_size,
        )

class ImageResizeKJv2:
    """Typed wrapper for the ComfyUI node class ``ImageResizeKJv2``.

    Display name: Resize Image v2

    Category: KJNodes/image

    Resizes the image to the specified width and height.
    """

    CLASS_TYPE = 'ImageResizeKJv2'
    OUTPUTS: tuple[str, ...] = ('IMAGE', 'width', 'height', 'mask')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'INT', 'INT', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        crop_position: str = "center",
        divisible_by: int = 2,
        height: int = 512,
        keep_proportion: str = False,
        pad_color: str = "0, 0, 0",
        upscale_method: str,
        width: int = 512,
        device: str = "",
        mask: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImageResizeKJv2`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageResizeKJv2',
            image=image,
            crop_position=crop_position,
            divisible_by=divisible_by,
            height=height,
            keep_proportion=keep_proportion,
            pad_color=pad_color,
            upscale_method=upscale_method,
            width=width,
            device=device,
            mask=mask,
        )

class ImageSharpenKJ:
    """Typed wrapper for the ComfyUI node class ``ImageSharpenKJ``.

    Display name: Image Sharpen KJ

    Category: KJNodes/image

    GPU-accelerated image sharpening with multiple methods.
    """

    CLASS_TYPE = 'ImageSharpenKJ'
    OUTPUTS: tuple[str, ...] = ('output',)
    OUTPUT_TYPES: tuple[str, ...] = ('COMFY_MATCHTYPE_V3',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        method: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImageSharpenKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageSharpenKJ',
            image=image,
            method=method,
        )

class ImageTensorList:
    """Typed wrapper for the ComfyUI node class ``ImageTensorList``.

    Display name: Image Tensor List

    Category: KJNodes/image

    Creates an image list from the input images.
    """

    CLASS_TYPE = 'ImageTensorList'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image1: "Handle" = None,
        image2: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImageTensorList`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageTensorList',
            image1=image1,
            image2=image2,
        )

class ImageTransformByNormalizedAmplitude:
    """Typed wrapper for the ComfyUI node class ``ImageTransformByNormalizedAmplitude``.

    Category: KJNodes/audio

    Works as a bridge to the AudioScheduler -nodes:
    """

    CLASS_TYPE = 'ImageTransformByNormalizedAmplitude'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        normalized_amp: "Handle" = None,
        cumulative: bool = False,
        x_offset: int = 0,
        y_offset: int = 0,
        zoom_scale: float = 0.0,
    ) -> "_NodeBuilder":
        """Add a ``ImageTransformByNormalizedAmplitude`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageTransformByNormalizedAmplitude',
            image=image,
            normalized_amp=normalized_amp,
            cumulative=cumulative,
            x_offset=x_offset,
            y_offset=y_offset,
            zoom_scale=zoom_scale,
        )

class ImageTransformKJ:
    """Typed wrapper for the ComfyUI node class ``ImageTransformKJ``.

    Display name: Image Transform KJ

    Category: KJNodes/image

    Interactive image transform node: crop, resize, pad, and rotate.
    """

    CLASS_TYPE = 'ImageTransformKJ'
    OUTPUTS: tuple[str, ...] = ('output', 'output_mask', 'bbox', 'bbox_mask', 'width', 'height')
    OUTPUT_TYPES: tuple[str, ...] = ('COMFY_MATCHTYPE_V3', 'MASK', 'BBOX', 'MASK', 'INT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        extra_padding: "Handle" = None,
        image: "Handle" = None,
        invert_crop: "Handle" = None,
        keep_proportion: "Handle" = None,
        bboxes: str = "",
        divisible_by: int = 2,
        target_height: int = 0,
        target_width: int = 0,
        upscale_method: str = "lanczos",
        mask: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImageTransformKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageTransformKJ',
            extra_padding=extra_padding,
            image=image,
            invert_crop=invert_crop,
            keep_proportion=keep_proportion,
            bboxes=bboxes,
            divisible_by=divisible_by,
            target_height=target_height,
            target_width=target_width,
            upscale_method=upscale_method,
            mask=mask,
        )

class ImageUncropByMask:
    """Typed wrapper for the ComfyUI node class ``ImageUncropByMask``.

    Display name: Image Uncrop By Mask

    Category: KJNodes/image
    """

    CLASS_TYPE = 'ImageUncropByMask'
    OUTPUTS: tuple[str, ...] = ('image',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        destination: "Handle" = None,
        mask: "Handle" = None,
        source: "Handle" = None,
        bbox: "Handle",
    ) -> "_NodeBuilder":
        """Add a ``ImageUncropByMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageUncropByMask',
            destination=destination,
            mask=mask,
            source=source,
            bbox=bbox,
        )

class ImageUpscaleWithModelBatched:
    """Typed wrapper for the ComfyUI node class ``ImageUpscaleWithModelBatched``.

    Display name: Image Upscale With Model Batched

    Category: KJNodes/image

    Same as ComfyUI native model upscaling node,
    """

    CLASS_TYPE = 'ImageUpscaleWithModelBatched'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images: "Handle" = None,
        upscale_model: "Handle" = None,
        per_batch: int = 16,
        downscale_method: str = "lanczos",
        downscale_ratio: float = 1.0,
        precision: str = "float32",
    ) -> "_NodeBuilder":
        """Add a ``ImageUpscaleWithModelBatched`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ImageUpscaleWithModelBatched',
            images=images,
            upscale_model=upscale_model,
            per_batch=per_batch,
            downscale_method=downscale_method,
            downscale_ratio=downscale_ratio,
            precision=precision,
        )

class InjectNoiseToLatent:
    """Typed wrapper for the ComfyUI node class ``InjectNoiseToLatent``.

    Display name: Inject Noise To Latent

    Category: KJNodes/noise
    """

    CLASS_TYPE = 'InjectNoiseToLatent'
    OUTPUTS: tuple[str, ...] = ('LATENT',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latents: "Handle" = None,
        noise: "Handle" = None,
        average: bool = False,
        normalize: bool = False,
        strength: float = 0.1,
        mask: "Handle" = None,
        mix_randn_amount: float = 0.0,
        seed: int = 123,
    ) -> "_NodeBuilder":
        """Add a ``InjectNoiseToLatent`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'InjectNoiseToLatent',
            latents=latents,
            noise=noise,
            average=average,
            normalize=normalize,
            strength=strength,
            mask=mask,
            mix_randn_amount=mix_randn_amount,
            seed=seed,
        )

class InsertImageBatchByIndexes:
    """Typed wrapper for the ComfyUI node class ``InsertImageBatchByIndexes``.

    Display name: Insert Image Batch By Indexes

    Category: KJNodes/image

    This node is designed to be use with node FilterZeroMasksAndCorrespondingImages
    """

    CLASS_TYPE = 'InsertImageBatchByIndexes'
    OUTPUTS: tuple[str, ...] = ('images_after_insert',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images: "Handle" = None,
        images_to_insert: "Handle" = None,
        insert_indexes: "Handle",
    ) -> "_NodeBuilder":
        """Add a ``InsertImageBatchByIndexes`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'InsertImageBatchByIndexes',
            images=images,
            images_to_insert=images_to_insert,
            insert_indexes=insert_indexes,
        )

class InsertImagesToBatchIndexed:
    """Typed wrapper for the ComfyUI node class ``InsertImagesToBatchIndexed``.

    Display name: Insert Images To Batch Indexed

    Category: KJNodes/image

    Inserts images at the specified indices into the original image batch.
    """

    CLASS_TYPE = 'InsertImagesToBatchIndexed'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images_to_insert: "Handle" = None,
        original_images: "Handle" = None,
        indexes: str = "0, 1, 2",
        mode: str = "",
    ) -> "_NodeBuilder":
        """Add a ``InsertImagesToBatchIndexed`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'InsertImagesToBatchIndexed',
            images_to_insert=images_to_insert,
            original_images=original_images,
            indexes=indexes,
            mode=mode,
        )

class InsertLatentToIndexed:
    """Typed wrapper for the ComfyUI node class ``InsertLatentToIndexed``.

    Display name: Insert Latent To Index

    Category: KJNodes/latents

    Inserts a latent at the specified index into the original latent batch.
    """

    CLASS_TYPE = 'InsertLatentToIndexed'
    OUTPUTS: tuple[str, ...] = ('LATENT',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        destination: "Handle" = None,
        source: "Handle" = None,
        index: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``InsertLatentToIndexed`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'InsertLatentToIndexed',
            destination=destination,
            source=source,
            index=index,
        )

class InterpolateCoords:
    """Typed wrapper for the ComfyUI node class ``InterpolateCoords``.

    Display name: Interpolate Coords

    Category: KJNodes/experimental

    Interpolates coordinates based on a curve.
    """

    CLASS_TYPE = 'InterpolateCoords'
    OUTPUTS: tuple[str, ...] = ('coordinates',)
    OUTPUT_TYPES: tuple[str, ...] = ('STRING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        coordinates: str,
        interpolation_curve: float,
    ) -> "_NodeBuilder":
        """Add a ``InterpolateCoords`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'InterpolateCoords',
            coordinates=coordinates,
            interpolation_curve=interpolation_curve,
        )

class Intrinsic_lora_sampling:
    """Typed wrapper for the ComfyUI node class ``Intrinsic_lora_sampling``.

    Display name: Intrinsic Lora Sampling

    Category: KJNodes/misc

    Sampler to use the intrinsic loras:
    """

    CLASS_TYPE = 'Intrinsic_lora_sampling'
    OUTPUTS: tuple[str, ...] = ('IMAGE', 'LATENT')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'LATENT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        clip: "Handle" = None,
        model: "Handle" = None,
        vae: "Handle" = None,
        lora_name: str,
        per_batch: int = 16,
        task: str = "depth map",
        text: str = "",
        image: "Handle" = None,
        optional_latent: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``Intrinsic_lora_sampling`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'Intrinsic_lora_sampling',
            clip=clip,
            model=model,
            vae=vae,
            lora_name=lora_name,
            per_batch=per_batch,
            task=task,
            text=text,
            image=image,
            optional_latent=optional_latent,
        )

class JoinStringMulti:
    """Typed wrapper for the ComfyUI node class ``JoinStringMulti``.

    Display name: Join String Multi

    Category: KJNodes/text

    Creates single string, or a list of strings, from
    """

    CLASS_TYPE = 'JoinStringMulti'
    OUTPUTS: tuple[str, ...] = ('string',)
    OUTPUT_TYPES: tuple[str, ...] = ('STRING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        delimiter: str = " ",
        inputcount: int = 2,
        return_list: bool = False,
        string_1: str = "",
        string_2: str = "",
    ) -> "_NodeBuilder":
        """Add a ``JoinStringMulti`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'JoinStringMulti',
            delimiter=delimiter,
            inputcount=inputcount,
            return_list=return_list,
            string_1=string_1,
            string_2=string_2,
        )

class JoinStrings:
    """Typed wrapper for the ComfyUI node class ``JoinStrings``.

    Display name: Join Strings

    Category: KJNodes/text
    """

    CLASS_TYPE = 'JoinStrings'
    OUTPUTS: tuple[str, ...] = ('STRING',)
    OUTPUT_TYPES: tuple[str, ...] = ('STRING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        delimiter: str = " ",
        string1: str = "",
        string2: str = "",
    ) -> "_NodeBuilder":
        """Add a ``JoinStrings`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'JoinStrings',
            delimiter=delimiter,
            string1=string1,
            string2=string2,
        )

class LTX2AttentionTunerPatch:
    """Typed wrapper for the ComfyUI node class ``LTX2AttentionTunerPatch``.

    Display name: LTX2 Attention Tuner Patch

    Category: KJNodes/ltxv

    EXPERIMENTAL! Custom LTX2 forward pass with attention scaling factors per modality, also reduces peak VRAM usage.
    """

    CLASS_TYPE = 'LTX2AttentionTunerPatch'
    OUTPUTS: tuple[str, ...] = ('model',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        audio_scale: float = 1.0,
        audio_to_video_scale: float = 1.0,
        blocks: str = "",
        triton_kernels: bool = True,
        video_scale: float = 1.0,
        video_to_audio_scale: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``LTX2AttentionTunerPatch`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LTX2AttentionTunerPatch',
            model=model,
            audio_scale=audio_scale,
            audio_to_video_scale=audio_to_video_scale,
            blocks=blocks,
            triton_kernels=triton_kernels,
            video_scale=video_scale,
            video_to_audio_scale=video_to_audio_scale,
        )

class LTX2AudioLatentNormalizingSampling:
    """Typed wrapper for the ComfyUI node class ``LTX2AudioLatentNormalizingSampling``.

    Display name: LTX2 Audio Latent Normalizing Sampling

    Category: KJNodes/ltxv

    Improves LTX2 generated audio quality by normalizing audio latents at specified sampling steps.
    """

    CLASS_TYPE = 'LTX2AudioLatentNormalizingSampling'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        audio_normalization_factors: str = "1,1,0.25,1,1,0.25,1,1",
    ) -> "_NodeBuilder":
        """Add a ``LTX2AudioLatentNormalizingSampling`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LTX2AudioLatentNormalizingSampling',
            model=model,
            audio_normalization_factors=audio_normalization_factors,
        )

class LTX2BlockLoraSelect:
    """Typed wrapper for the ComfyUI node class ``LTX2BlockLoraSelect``.

    Display name: LTX2 Block Lora Select

    Category: KJNodes/ltxv

    Select individual block alpha values, value of 0 removes the block altogether
    """

    CLASS_TYPE = 'LTX2BlockLoraSelect'
    OUTPUTS: tuple[str, ...] = ('blocks',)
    OUTPUT_TYPES: tuple[str, ...] = ('SELECTEDDITBLOCKS',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        blocks_0: float = 0.0,
        blocks_1: float = 0.0,
        blocks_10: float = 0.0,
        blocks_11: float = 0.0,
        blocks_12: float = 0.0,
        blocks_13: float = 0.0,
        blocks_14: float = 0.0,
        blocks_15: float = 0.0,
        blocks_16: float = 0.0,
        blocks_17: float = 0.0,
        blocks_18: float = 0.0,
        blocks_19: float = 0.0,
        blocks_2: float = 0.0,
        blocks_20: float = 0.0,
        blocks_21: float = 0.0,
        blocks_22: float = 0.0,
        blocks_23: float = 0.0,
        blocks_24: float = 0.0,
        blocks_25: float = 0.0,
        blocks_26: float = 0.0,
        blocks_27: float = 0.0,
        blocks_28: float = 0.0,
        blocks_29: float = 0.0,
        blocks_3: float = 0.0,
        blocks_30: float = 0.0,
        blocks_31: float = 0.0,
        blocks_32: float = 0.0,
        blocks_33: float = 0.0,
        blocks_34: float = 0.0,
        blocks_35: float = 0.0,
        blocks_36: float = 0.0,
        blocks_37: float = 0.0,
        blocks_38: float = 0.0,
        blocks_39: float = 0.0,
        blocks_4: float = 0.0,
        blocks_40: float = 0.0,
        blocks_41: float = 0.0,
        blocks_42: float = 0.0,
        blocks_43: float = 0.0,
        blocks_44: float = 0.0,
        blocks_45: float = 0.0,
        blocks_46: float = 0.0,
        blocks_47: float = 0.0,
        blocks_5: float = 0.0,
        blocks_6: float = 0.0,
        blocks_7: float = 0.0,
        blocks_8: float = 0.0,
        blocks_9: float = 0.0,
    ) -> "_NodeBuilder":
        """Add a ``LTX2BlockLoraSelect`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LTX2BlockLoraSelect',
            **{
                'blocks.0.': blocks_0,
                'blocks.1.': blocks_1,
                'blocks.10.': blocks_10,
                'blocks.11.': blocks_11,
                'blocks.12.': blocks_12,
                'blocks.13.': blocks_13,
                'blocks.14.': blocks_14,
                'blocks.15.': blocks_15,
                'blocks.16.': blocks_16,
                'blocks.17.': blocks_17,
                'blocks.18.': blocks_18,
                'blocks.19.': blocks_19,
                'blocks.2.': blocks_2,
                'blocks.20.': blocks_20,
                'blocks.21.': blocks_21,
                'blocks.22.': blocks_22,
                'blocks.23.': blocks_23,
                'blocks.24.': blocks_24,
                'blocks.25.': blocks_25,
                'blocks.26.': blocks_26,
                'blocks.27.': blocks_27,
                'blocks.28.': blocks_28,
                'blocks.29.': blocks_29,
                'blocks.3.': blocks_3,
                'blocks.30.': blocks_30,
                'blocks.31.': blocks_31,
                'blocks.32.': blocks_32,
                'blocks.33.': blocks_33,
                'blocks.34.': blocks_34,
                'blocks.35.': blocks_35,
                'blocks.36.': blocks_36,
                'blocks.37.': blocks_37,
                'blocks.38.': blocks_38,
                'blocks.39.': blocks_39,
                'blocks.4.': blocks_4,
                'blocks.40.': blocks_40,
                'blocks.41.': blocks_41,
                'blocks.42.': blocks_42,
                'blocks.43.': blocks_43,
                'blocks.44.': blocks_44,
                'blocks.45.': blocks_45,
                'blocks.46.': blocks_46,
                'blocks.47.': blocks_47,
                'blocks.5.': blocks_5,
                'blocks.6.': blocks_6,
                'blocks.7.': blocks_7,
                'blocks.8.': blocks_8,
                'blocks.9.': blocks_9,
            },
        )

class LTX2LoraLoaderAdvanced:
    """Typed wrapper for the ComfyUI node class ``LTX2LoraLoaderAdvanced``.

    Display name: LTX2 LoRA Loader Advanced

    Category: KJNodes/ltxv

    Advanced LoRA loader with per-block strength control for LTX2 models
    """

    CLASS_TYPE = 'LTX2LoraLoaderAdvanced'
    OUTPUTS: tuple[str, ...] = ('model', 'rank', 'loaded_keys_info')
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL', 'STRING', 'STRING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        audio: float = 1.0,
        audio_to_video: float = 1.0,
        lora_name: str,
        other: float = 1.0,
        strength_model: float = 1.0,
        video: float = 1.0,
        video_to_audio: float = 1.0,
        blocks: "Handle" = None,
        opt_lora_path: str = "",
    ) -> "_NodeBuilder":
        """Add a ``LTX2LoraLoaderAdvanced`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LTX2LoraLoaderAdvanced',
            model=model,
            audio=audio,
            audio_to_video=audio_to_video,
            lora_name=lora_name,
            other=other,
            strength_model=strength_model,
            video=video,
            video_to_audio=video_to_audio,
            blocks=blocks,
            opt_lora_path=opt_lora_path,
        )

class LTX2MemoryEfficientSageAttentionPatch:
    """Typed wrapper for the ComfyUI node class ``LTX2MemoryEfficientSageAttentionPatch``.

    Display name: LTX2 Mem Eff Sage Attention Patch

    Category: KJNodes/ltxv

    EXPERIMENTAL! Activates custom sageattention to reduce peak VRAM usage, overrides the attention mode. Requires latest sageattention version.
    """

    CLASS_TYPE = 'LTX2MemoryEfficientSageAttentionPatch'
    OUTPUTS: tuple[str, ...] = ('model',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        triton_kernels: bool = True,
    ) -> "_NodeBuilder":
        """Add a ``LTX2MemoryEfficientSageAttentionPatch`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LTX2MemoryEfficientSageAttentionPatch',
            model=model,
            triton_kernels=triton_kernels,
        )

class LTX2SamplingPreviewOverride:
    """Typed wrapper for the ComfyUI node class ``LTX2SamplingPreviewOverride``.

    Display name: LTX2 Sampling Preview Override

    Category: KJNodes/ltxv

    Overrides the LTX2 preview sampling preview function, temporary measure until previews are in comfy core
    """

    CLASS_TYPE = 'LTX2SamplingPreviewOverride'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        preview_rate: int = 8,
        latent_upscale_model: "Handle" = None,
        vae: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTX2SamplingPreviewOverride`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LTX2SamplingPreviewOverride',
            model=model,
            preview_rate=preview_rate,
            latent_upscale_model=latent_upscale_model,
            vae=vae,
        )

class LTX2_NAG:
    """Typed wrapper for the ComfyUI node class ``LTX2_NAG``.

    Display name: LTX2 NAG

    Category: KJNodes/ltxv

    https://github.com/ChenDarYen/Normalized-Attention-Guidance
    """

    CLASS_TYPE = 'LTX2_NAG'
    OUTPUTS: tuple[str, ...] = ('model',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        nag_alpha: float = 0.25,
        nag_scale: float = 11.0,
        nag_tau: float = 2.5,
        inplace: bool = True,
        nag_cond_audio: "Handle" = None,
        nag_cond_video: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTX2_NAG`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LTX2_NAG',
            model=model,
            nag_alpha=nag_alpha,
            nag_scale=nag_scale,
            nag_tau=nag_tau,
            inplace=inplace,
            nag_cond_audio=nag_cond_audio,
            nag_cond_video=nag_cond_video,
        )

class LTXVAudioVideoMask:
    """Typed wrapper for the ComfyUI node class ``LTXVAudioVideoMask``.

    Category: KJNodes/ltxv

    Creates noise masks for video and audio latents based on specified time ranges. New content is generated within these masked regions
    """

    CLASS_TYPE = 'LTXVAudioVideoMask'
    OUTPUTS: tuple[str, ...] = ('video_latent', 'audio_latent')
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT', 'LATENT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        audio_end_time: float = 5.0,
        audio_start_time: float = 0.0,
        max_length: str = "truncate",
        video_end_time: float = 5.0,
        video_fps: float = 25,
        video_start_time: float = 0.0,
        audio_latent: "Handle" = None,
        existing_mask_mode: str = "add",
        video_latent: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXVAudioVideoMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LTXVAudioVideoMask',
            audio_end_time=audio_end_time,
            audio_start_time=audio_start_time,
            max_length=max_length,
            video_end_time=video_end_time,
            video_fps=video_fps,
            video_start_time=video_start_time,
            audio_latent=audio_latent,
            existing_mask_mode=existing_mask_mode,
            video_latent=video_latent,
        )

class LTXVChunkFeedForward:
    """Typed wrapper for the ComfyUI node class ``LTXVChunkFeedForward``.

    Display name: LTXV Chunk FeedForward

    Category: KJNodes/ltxv

    EXPERIMENTAL AND MAY CHANGE THE MODEL OUTPUT!! Chunks feedforward activations to reduce peak VRAM usage.
    """

    CLASS_TYPE = 'LTXVChunkFeedForward'
    OUTPUTS: tuple[str, ...] = ('model',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        chunks: int = 2,
        dim_threshold: int = 4096,
    ) -> "_NodeBuilder":
        """Add a ``LTXVChunkFeedForward`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LTXVChunkFeedForward',
            model=model,
            chunks=chunks,
            dim_threshold=dim_threshold,
        )

class LTXVEnhanceAVideoKJ:
    """Typed wrapper for the ComfyUI node class ``LTXVEnhanceAVideoKJ``.

    Display name: LTXV Enhance A Video KJ

    Category: KJNodes/ltxv

    https://github.com/NUS-HPC-AI-Lab/Enhance-A-Video
    """

    CLASS_TYPE = 'LTXVEnhanceAVideoKJ'
    OUTPUTS: tuple[str, ...] = ('model',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latent: "Handle" = None,
        model: "Handle" = None,
        weight: float = 4.0,
    ) -> "_NodeBuilder":
        """Add a ``LTXVEnhanceAVideoKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LTXVEnhanceAVideoKJ',
            latent=latent,
            model=model,
            weight=weight,
        )

class LTXVImgToVideoInplaceKJ:
    """Typed wrapper for the ComfyUI node class ``LTXVImgToVideoInplaceKJ``.

    Category: KJNodes/ltxv

    Replaces video latent frames with the encoded input images, uses DynamicCombo which requires ComfyUI 0.8.1 and frontend 1.33.4 or later.
    """

    CLASS_TYPE = 'LTXVImgToVideoInplaceKJ'
    OUTPUTS: tuple[str, ...] = ('latent',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latent: "Handle" = None,
        num_images: "Handle" = None,
        vae: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXVImgToVideoInplaceKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LTXVImgToVideoInplaceKJ',
            latent=latent,
            num_images=num_images,
            vae=vae,
        )

class LatentInpaintTTM:
    """Typed wrapper for the ComfyUI node class ``LatentInpaintTTM``.

    Display name: Latent Inpaint TTM

    Category: KJNodes/experimental

    https://github.com/time-to-move/TTM
    """

    CLASS_TYPE = 'LatentInpaintTTM'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        steps: int = 7,
        mask: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LatentInpaintTTM`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LatentInpaintTTM',
            model=model,
            steps=steps,
            mask=mask,
        )

class LazySwitchKJ:
    """Typed wrapper for the ComfyUI node class ``LazySwitchKJ``.

    Display name: Lazy Switch KJ

    Category: KJNodes/misc

    Controls flow of execution based on a boolean switch.
    """

    CLASS_TYPE = 'LazySwitchKJ'
    OUTPUTS: tuple[str, ...] = ('*',)
    OUTPUT_TYPES: tuple[str, ...] = ('*',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        on_false: "Handle",
        on_true: "Handle",
        switch: bool,
    ) -> "_NodeBuilder":
        """Add a ``LazySwitchKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LazySwitchKJ',
            on_false=on_false,
            on_true=on_true,
            switch=switch,
        )

class LeapfusionHunyuanI2VPatcher:
    """Typed wrapper for the ComfyUI node class ``LeapfusionHunyuanI2VPatcher``.

    Display name: Leapfusion Hunyuan I2V Patcher

    Category: KJNodes/hunyuanvideo
    """

    CLASS_TYPE = 'LeapfusionHunyuanI2VPatcher'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latent: "Handle" = None,
        model: "Handle" = None,
        end_percent: float = 1.0,
        index: int = 0,
        start_percent: float = 0.0,
        strength: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``LeapfusionHunyuanI2VPatcher`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LeapfusionHunyuanI2VPatcher',
            latent=latent,
            model=model,
            end_percent=end_percent,
            index=index,
            start_percent=start_percent,
            strength=strength,
        )

class LoadAndResizeImage:
    """Typed wrapper for the ComfyUI node class ``LoadAndResizeImage``.

    Display name: Load & Resize Image

    Category: KJNodes/image
    """

    CLASS_TYPE = 'LoadAndResizeImage'
    OUTPUTS: tuple[str, ...] = ('image', 'mask', 'width', 'height', 'image_path')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'MASK', 'INT', 'INT', 'STRING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        background_color: str = "",
        divisible_by: int = 2,
        height: int = 512,
        image: str,
        keep_proportion: bool = False,
        mask_channel: str,
        repeat: int = 1,
        resize: bool = False,
        width: int = 512,
    ) -> "_NodeBuilder":
        """Add a ``LoadAndResizeImage`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LoadAndResizeImage',
            background_color=background_color,
            divisible_by=divisible_by,
            height=height,
            image=image,
            keep_proportion=keep_proportion,
            mask_channel=mask_channel,
            repeat=repeat,
            resize=resize,
            width=width,
        )

class LoadImagesFromFolderKJ:
    """Typed wrapper for the ComfyUI node class ``LoadImagesFromFolderKJ``.

    Display name: Load Images From Folder (KJ)

    Category: KJNodes/image

    Loads images from a folder into a batch, images are resized and loaded into a batch.
    """

    CLASS_TYPE = 'LoadImagesFromFolderKJ'
    OUTPUTS: tuple[str, ...] = ('image', 'mask', 'count', 'image_path')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'MASK', 'INT', 'STRING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        folder: str = "",
        height: int = 1024,
        keep_aspect_ratio: str,
        width: int = 1024,
        image_load_cap: int = 0,
        include_subfolders: bool = False,
        start_index: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``LoadImagesFromFolderKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LoadImagesFromFolderKJ',
            folder=folder,
            height=height,
            keep_aspect_ratio=keep_aspect_ratio,
            width=width,
            image_load_cap=image_load_cap,
            include_subfolders=include_subfolders,
            start_index=start_index,
        )

class LoadResAdapterNormalization:
    """Typed wrapper for the ComfyUI node class ``LoadResAdapterNormalization``.

    Category: KJNodes/experimental
    """

    CLASS_TYPE = 'LoadResAdapterNormalization'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        resadapter_path: str,
    ) -> "_NodeBuilder":
        """Add a ``LoadResAdapterNormalization`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LoadResAdapterNormalization',
            model=model,
            resadapter_path=resadapter_path,
        )

class LoadVideosFromFolder:
    """Typed wrapper for the ComfyUI node class ``LoadVideosFromFolder``.

    Display name: Load Videos From Folder

    Category: KJNodes/misc
    """

    CLASS_TYPE = 'LoadVideosFromFolder'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        add_label: bool = False,
        custom_height: int = 0,
        custom_width: int = 0,
        force_rate: float = 0,
        frame_load_cap: int = 0,
        grid_max_columns: int = 4,
        output_type: str = "batch",
        select_every_nth: int = 1,
        skip_first_frames: int = 0,
        video: str = "X://insert/path/",
    ) -> "_NodeBuilder":
        """Add a ``LoadVideosFromFolder`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LoadVideosFromFolder',
            add_label=add_label,
            custom_height=custom_height,
            custom_width=custom_width,
            force_rate=force_rate,
            frame_load_cap=frame_load_cap,
            grid_max_columns=grid_max_columns,
            output_type=output_type,
            select_every_nth=select_every_nth,
            skip_first_frames=skip_first_frames,
            video=video,
        )

class LoraExtractKJ:
    """Typed wrapper for the ComfyUI node class ``LoraExtractKJ``.

    Category: KJNodes/lora
    """

    CLASS_TYPE = 'LoraExtractKJ'
    OUTPUTS: tuple[str, ...] = ()
    OUTPUT_TYPES: tuple[str, ...] = ()

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        adaptive_param: float = 0.15,
        algorithm: str = "svd_lowrank",
        bias_diff: bool = True,
        clamp_quantile: bool = False,
        filename_prefix: str = "loras/ComfyUI_extracted_lora",
        finetuned: "Handle",
        lora_type: str,
        lowrank_iters: int = 7,
        original: "Handle",
        output_dtype: str = "fp16",
        rank: int = 64,
    ) -> "_NodeBuilder":
        """Add a ``LoraExtractKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LoraExtractKJ',
            adaptive_param=adaptive_param,
            algorithm=algorithm,
            bias_diff=bias_diff,
            clamp_quantile=clamp_quantile,
            filename_prefix=filename_prefix,
            finetuned=finetuned,
            lora_type=lora_type,
            lowrank_iters=lowrank_iters,
            original=original,
            output_dtype=output_dtype,
            rank=rank,
        )

class LoraReduceRankKJ:
    """Typed wrapper for the ComfyUI node class ``LoraReduceRankKJ``.

    Display name: LoraReduceRank

    Category: KJNodes/lora

    Resize a LoRA model by reducing its rank. Based on kohya's sd-scripts: https://github.com/kohya-ss/sd-scripts/blob/main/networks/resize_lora.py
    """

    CLASS_TYPE = 'LoraReduceRankKJ'
    OUTPUTS: tuple[str, ...] = ()
    OUTPUT_TYPES: tuple[str, ...] = ()

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        dynamic_method: str = "disabled",
        dynamic_param: float = 0.2,
        lora_name: str,
        new_rank: int = 8,
        output_dtype: str = "match_original",
        verbose: bool = True,
    ) -> "_NodeBuilder":
        """Add a ``LoraReduceRankKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'LoraReduceRankKJ',
            dynamic_method=dynamic_method,
            dynamic_param=dynamic_param,
            lora_name=lora_name,
            new_rank=new_rank,
            output_dtype=output_dtype,
            verbose=verbose,
        )

class MaskBatchMulti:
    """Typed wrapper for the ComfyUI node class ``MaskBatchMulti``.

    Display name: Mask Batch Multi

    Category: KJNodes/masking

    Creates an image batch from multiple masks.
    """

    CLASS_TYPE = 'MaskBatchMulti'
    OUTPUTS: tuple[str, ...] = ('masks',)
    OUTPUT_TYPES: tuple[str, ...] = ('MASK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        mask_1: "Handle" = None,
        mask_2: "Handle" = None,
        inputcount: int = 2,
    ) -> "_NodeBuilder":
        """Add a ``MaskBatchMulti`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'MaskBatchMulti',
            mask_1=mask_1,
            mask_2=mask_2,
            inputcount=inputcount,
        )

class MaskOrImageToWeight:
    """Typed wrapper for the ComfyUI node class ``MaskOrImageToWeight``.

    Display name: Mask Or Image To Weight

    Category: KJNodes/weights

    Gets the mean values from mask or image batch
    """

    CLASS_TYPE = 'MaskOrImageToWeight'
    OUTPUTS: tuple[str, ...] = ('FLOAT', 'STRING')
    OUTPUT_TYPES: tuple[str, ...] = ('FLOAT', 'STRING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        output_type: str = "list",
        images: "Handle" = None,
        masks: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``MaskOrImageToWeight`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'MaskOrImageToWeight',
            output_type=output_type,
            images=images,
            masks=masks,
        )

class MergeImageChannels:
    """Typed wrapper for the ComfyUI node class ``MergeImageChannels``.

    Display name: Merge Image Channels

    Category: KJNodes/image

    Merges channel data into an image.
    """

    CLASS_TYPE = 'MergeImageChannels'
    OUTPUTS: tuple[str, ...] = ('image',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        blue: "Handle" = None,
        green: "Handle" = None,
        red: "Handle" = None,
        alpha: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``MergeImageChannels`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'MergeImageChannels',
            blue=blue,
            green=green,
            red=red,
            alpha=alpha,
        )

class ModelMemoryUsageFactorOverride:
    """Typed wrapper for the ComfyUI node class ``ModelMemoryUsageFactorOverride``.

    Display name: Model Memory Usage Factor Override

    Category: KJNodes/memory

    Overrides the memory usage factor of the model during sampling.
    """

    CLASS_TYPE = 'ModelMemoryUsageFactorOverride'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        memory_usage_factor: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``ModelMemoryUsageFactorOverride`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ModelMemoryUsageFactorOverride',
            model=model,
            memory_usage_factor=memory_usage_factor,
        )

class ModelMemoryUseReportPatch:
    """Typed wrapper for the ComfyUI node class ``ModelMemoryUseReportPatch``.

    Display name: Model Memory Use Report Patch

    Category: KJNodes/memory

    Adds callbacks to model to report memory usage during after sampling
    """

    CLASS_TYPE = 'ModelMemoryUseReportPatch'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ModelMemoryUseReportPatch`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ModelMemoryUseReportPatch',
            model=model,
        )

class ModelPassThrough:
    """Typed wrapper for the ComfyUI node class ``ModelPassThrough``.

    Display name: ModelPass

    Category: KJNodes/misc

    Simply passes through the model,
    """

    CLASS_TYPE = 'ModelPassThrough'
    OUTPUTS: tuple[str, ...] = ('model',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ModelPassThrough`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ModelPassThrough',
            model=model,
        )

class ModelPatchTorchSettings:
    """Typed wrapper for the ComfyUI node class ``ModelPatchTorchSettings``.

    Display name: Model Patch Torch Settings

    Category: KJNodes/experimental

    Adds callbacks to model to set torch settings before and after running the model.
    """

    CLASS_TYPE = 'ModelPatchTorchSettings'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        enable_fp16_accumulation: bool = False,
    ) -> "_NodeBuilder":
        """Add a ``ModelPatchTorchSettings`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ModelPatchTorchSettings',
            model=model,
            enable_fp16_accumulation=enable_fp16_accumulation,
        )

class ModelSaveKJ:
    """Typed wrapper for the ComfyUI node class ``ModelSaveKJ``.

    Display name: Model Save KJ

    Category: advanced/model_merging
    """

    CLASS_TYPE = 'ModelSaveKJ'
    OUTPUTS: tuple[str, ...] = ()
    OUTPUT_TYPES: tuple[str, ...] = ()

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        filename_prefix: str = "diffusion_models/ComfyUI",
        model_key_prefix: str = "model.diffusion_model.",
    ) -> "_NodeBuilder":
        """Add a ``ModelSaveKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ModelSaveKJ',
            model=model,
            filename_prefix=filename_prefix,
            model_key_prefix=model_key_prefix,
        )

class NABLA_AttentionKJ:
    """Typed wrapper for the ComfyUI node class ``NABLA_AttentionKJ``.

    Display name: NABLA Attention KJ

    Category: KJNodes/experimental

    Experimental node for patching attention mode to use NABLA sparse attention for video models, currently only works with Kadinsky5
    """

    CLASS_TYPE = 'NABLA_AttentionKJ'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latent: "Handle" = None,
        model: "Handle" = None,
        sparsity: float = 0.9,
        torch_compile: bool = True,
        window_height: int = 3,
        window_time: int = 11,
        window_width: int = 3,
    ) -> "_NodeBuilder":
        """Add a ``NABLA_AttentionKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'NABLA_AttentionKJ',
            latent=latent,
            model=model,
            sparsity=sparsity,
            torch_compile=torch_compile,
            window_height=window_height,
            window_time=window_time,
            window_width=window_width,
        )

class NormalizedAmplitudeToFloatList:
    """Typed wrapper for the ComfyUI node class ``NormalizedAmplitudeToFloatList``.

    Category: KJNodes/audio

    Works as a bridge to the AudioScheduler -nodes:
    """

    CLASS_TYPE = 'NormalizedAmplitudeToFloatList'
    OUTPUTS: tuple[str, ...] = ('FLOAT',)
    OUTPUT_TYPES: tuple[str, ...] = ('FLOAT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        normalized_amp: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``NormalizedAmplitudeToFloatList`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'NormalizedAmplitudeToFloatList',
            normalized_amp=normalized_amp,
        )

class NormalizedAmplitudeToMask:
    """Typed wrapper for the ComfyUI node class ``NormalizedAmplitudeToMask``.

    Category: KJNodes/audio

    Works as a bridge to the AudioScheduler -nodes:
    """

    CLASS_TYPE = 'NormalizedAmplitudeToMask'
    OUTPUTS: tuple[str, ...] = ('MASK',)
    OUTPUT_TYPES: tuple[str, ...] = ('MASK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        normalized_amp: "Handle" = None,
        color: str = "amplitude",
        frame_offset: int = 0,
        height: int = 512,
        location_x: int = 256,
        location_y: int = 256,
        shape: str = "none",
        size: int = 128,
        width: int = 512,
    ) -> "_NodeBuilder":
        """Add a ``NormalizedAmplitudeToMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'NormalizedAmplitudeToMask',
            normalized_amp=normalized_amp,
            color=color,
            frame_offset=frame_offset,
            height=height,
            location_x=location_x,
            location_y=location_y,
            shape=shape,
            size=size,
            width=width,
        )

class OffsetMask:
    """Typed wrapper for the ComfyUI node class ``OffsetMask``.

    Display name: Offset Mask

    Category: KJNodes/masking

    Offsets the mask by the specified amount.
    """

    CLASS_TYPE = 'OffsetMask'
    OUTPUTS: tuple[str, ...] = ('mask',)
    OUTPUT_TYPES: tuple[str, ...] = ('MASK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        mask: "Handle" = None,
        angle: int = 0,
        duplication_factor: int = 1,
        incremental: bool = False,
        padding_mode: str = "empty",
        roll: bool = False,
        x: int = 0,
        y: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``OffsetMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'OffsetMask',
            mask=mask,
            angle=angle,
            duplication_factor=duplication_factor,
            incremental=incremental,
            padding_mode=padding_mode,
            roll=roll,
            x=x,
            y=y,
        )

class OffsetMaskByNormalizedAmplitude:
    """Typed wrapper for the ComfyUI node class ``OffsetMaskByNormalizedAmplitude``.

    Category: KJNodes/audio

    Works as a bridge to the AudioScheduler -nodes:
    """

    CLASS_TYPE = 'OffsetMaskByNormalizedAmplitude'
    OUTPUTS: tuple[str, ...] = ('mask',)
    OUTPUT_TYPES: tuple[str, ...] = ('MASK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        mask: "Handle" = None,
        normalized_amp: "Handle" = None,
        angle_multiplier: float = 0.0,
        rotate: bool = False,
        x: int = 0,
        y: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``OffsetMaskByNormalizedAmplitude`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'OffsetMaskByNormalizedAmplitude',
            mask=mask,
            normalized_amp=normalized_amp,
            angle_multiplier=angle_multiplier,
            rotate=rotate,
            x=x,
            y=y,
        )

class PadImageBatchInterleaved:
    """Typed wrapper for the ComfyUI node class ``PadImageBatchInterleaved``.

    Display name: Pad Image Batch Interleaved

    Category: KJNodes/image

    Inserts empty frames between the images in a batch.
    """

    CLASS_TYPE = 'PadImageBatchInterleaved'
    OUTPUTS: tuple[str, ...] = ('images', 'masks')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images: "Handle" = None,
        add_after_last: bool = False,
        empty_frames_per_image: int = 1,
        pad_frame_value: float = 0.0,
    ) -> "_NodeBuilder":
        """Add a ``PadImageBatchInterleaved`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'PadImageBatchInterleaved',
            images=images,
            add_after_last=add_after_last,
            empty_frames_per_image=empty_frames_per_image,
            pad_frame_value=pad_frame_value,
        )

class PatchModelPatcherOrder:
    """Typed wrapper for the ComfyUI node class ``PatchModelPatcherOrder``.

    Display name: Patch Model Patcher Order

    Category: KJNodes/deprecated

    NO LONGER NECESSARY OR FUNCTIONAL, keeping node for backwards compatibility. Use the TorchCompileModelAdvanced to use LoRA with torch.compile.
    """

    CLASS_TYPE = 'PatchModelPatcherOrder'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        full_load: str = "auto",
        patch_order: str = "weight_patch_first",
    ) -> "_NodeBuilder":
        """Add a ``PatchModelPatcherOrder`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'PatchModelPatcherOrder',
            model=model,
            full_load=full_load,
            patch_order=patch_order,
        )

class PathchSageAttentionKJ:
    """Typed wrapper for the ComfyUI node class ``PathchSageAttentionKJ``.

    Display name: Patch Sage Attention KJ

    Category: KJNodes/experimental

    Experimental node for patching attention mode. This doesn't use the model patching system and thus can't be disabled without running the node again with 'disabled' option.
    """

    CLASS_TYPE = 'PathchSageAttentionKJ'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        sage_attention: str = False,
        allow_compile: bool = False,
    ) -> "_NodeBuilder":
        """Add a ``PathchSageAttentionKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'PathchSageAttentionKJ',
            model=model,
            sage_attention=sage_attention,
            allow_compile=allow_compile,
        )

class PlaySoundKJ:
    """Typed wrapper for the ComfyUI node class ``PlaySoundKJ``.

    Category: KJNodes/audio

    Plays the input audio in the browser. Modes: 'always' plays on every execution, 'on_empty_queue' plays only when the queue finishes, 'on_change' plays only when the audio content changes. Duration limits playback length (0 = full audio).
    """

    CLASS_TYPE = 'PlaySoundKJ'
    OUTPUTS: tuple[str, ...] = ('any_output',)
    OUTPUT_TYPES: tuple[str, ...] = ('*',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        audio_path: str = "",
        duration: float = 5.0,
        mode: str = "always",
        volume: float = 0.5,
        any_input: "Handle" = None,
        audio: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``PlaySoundKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'PlaySoundKJ',
            audio_path=audio_path,
            duration=duration,
            mode=mode,
            volume=volume,
            any_input=any_input,
            audio=audio,
        )

class PlotCoordinates:
    """Typed wrapper for the ComfyUI node class ``PlotCoordinates``.

    Display name: Plot Coordinates

    Category: KJNodes/experimental

    Plots coordinates to sequence of images using Matplotlib.
    """

    CLASS_TYPE = 'PlotCoordinates'
    OUTPUTS: tuple[str, ...] = ('images', 'width', 'height', 'bbox_width', 'bbox_height')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'INT', 'INT', 'INT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        bbox_height: int = 128,
        bbox_width: int = 128,
        coordinates: str,
        height: int = 512,
        text: str = "title",
        width: int = 512,
        size_multiplier: float = [1.0],
    ) -> "_NodeBuilder":
        """Add a ``PlotCoordinates`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'PlotCoordinates',
            bbox_height=bbox_height,
            bbox_width=bbox_width,
            coordinates=coordinates,
            height=height,
            text=text,
            width=width,
            size_multiplier=size_multiplier,
        )

class PointsEditor:
    """Typed wrapper for the ComfyUI node class ``PointsEditor``.

    Display name: Points Editor

    Category: KJNodes/experimental

    # WORK IN PROGRESS
    """

    CLASS_TYPE = 'PointsEditor'
    OUTPUTS: tuple[str, ...] = ('positive_coords', 'negative_coords', 'bbox', 'bbox_mask', 'cropped_image')
    OUTPUT_TYPES: tuple[str, ...] = ('STRING', 'STRING', 'BBOX', 'MASK', 'IMAGE')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        bbox_format: str,
        bbox_store: str,
        bboxes: str,
        coordinates: str,
        height: int = 512,
        neg_coordinates: str,
        normalize: bool = False,
        points_store: str,
        width: int = 512,
        bg_image: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``PointsEditor`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'PointsEditor',
            bbox_format=bbox_format,
            bbox_store=bbox_store,
            bboxes=bboxes,
            coordinates=coordinates,
            height=height,
            neg_coordinates=neg_coordinates,
            normalize=normalize,
            points_store=points_store,
            width=width,
            bg_image=bg_image,
        )

class PreviewAnimation:
    """Typed wrapper for the ComfyUI node class ``PreviewAnimation``.

    Display name: Preview Animation

    Category: KJNodes/image
    """

    CLASS_TYPE = 'PreviewAnimation'
    OUTPUTS: tuple[str, ...] = ()
    OUTPUT_TYPES: tuple[str, ...] = ()

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        fps: float = 8.0,
        images: "Handle" = None,
        masks: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``PreviewAnimation`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'PreviewAnimation',
            fps=fps,
            images=images,
            masks=masks,
        )

class PreviewImageOrMask:
    """Typed wrapper for the ComfyUI node class ``PreviewImageOrMask``.

    Display name: Preview Image Or Mask

    Category: KJNodes/misc

    Previews the input images or masks.
    """

    CLASS_TYPE = 'PreviewImageOrMask'
    OUTPUTS: tuple[str, ...] = ()
    OUTPUT_TYPES: tuple[str, ...] = ()

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        input: "Handle",
    ) -> "_NodeBuilder":
        """Add a ``PreviewImageOrMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'PreviewImageOrMask',
            input=input,
        )

class PreviewLatentNoiseMask:
    """Typed wrapper for the ComfyUI node class ``PreviewLatentNoiseMask``.

    Category: KJNodes/latents

    Previews the latent noise mask
    """

    CLASS_TYPE = 'PreviewLatentNoiseMask'
    OUTPUTS: tuple[str, ...] = ('mask',)
    OUTPUT_TYPES: tuple[str, ...] = ('MASK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latent: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``PreviewLatentNoiseMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'PreviewLatentNoiseMask',
            latent=latent,
        )

class RemapImageRange:
    """Typed wrapper for the ComfyUI node class ``RemapImageRange``.

    Display name: Remap Image Range

    Category: KJNodes/image

    Remaps the image values to the specified range.
    """

    CLASS_TYPE = 'RemapImageRange'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        clamp: bool = True,
        max: float = 1.0,
        min: float = 0.0,
    ) -> "_NodeBuilder":
        """Add a ``RemapImageRange`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'RemapImageRange',
            image=image,
            clamp=clamp,
            max=max,
            min=min,
        )

class RemapMaskRange:
    """Typed wrapper for the ComfyUI node class ``RemapMaskRange``.

    Display name: Remap Mask Range

    Category: KJNodes/masking

    Sets new min and max values for the mask.
    """

    CLASS_TYPE = 'RemapMaskRange'
    OUTPUTS: tuple[str, ...] = ('mask',)
    OUTPUT_TYPES: tuple[str, ...] = ('MASK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        mask: "Handle" = None,
        max: float = 1.0,
        min: float = 0.0,
    ) -> "_NodeBuilder":
        """Add a ``RemapMaskRange`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'RemapMaskRange',
            mask=mask,
            max=max,
            min=min,
        )

class ReplaceImagesInBatch:
    """Typed wrapper for the ComfyUI node class ``ReplaceImagesInBatch``.

    Display name: Replace Images In Batch

    Category: KJNodes/image

    Replaces the images in a batch, starting from the specified start index,
    """

    CLASS_TYPE = 'ReplaceImagesInBatch'
    OUTPUTS: tuple[str, ...] = ('IMAGE', 'MASK')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        start_index: int = 1,
        original_images: "Handle" = None,
        original_masks: "Handle" = None,
        replacement_images: "Handle" = None,
        replacement_masks: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ReplaceImagesInBatch`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ReplaceImagesInBatch',
            start_index=start_index,
            original_images=original_images,
            original_masks=original_masks,
            replacement_images=replacement_images,
            replacement_masks=replacement_masks,
        )

class ResizeMask:
    """Typed wrapper for the ComfyUI node class ``ResizeMask``.

    Display name: Resize Mask

    Category: KJNodes/masking

    Resizes the mask or batch of masks to the specified width and height.
    """

    CLASS_TYPE = 'ResizeMask'
    OUTPUTS: tuple[str, ...] = ('mask', 'width', 'height')
    OUTPUT_TYPES: tuple[str, ...] = ('MASK', 'INT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        mask: "Handle" = None,
        crop: str,
        height: int = 512,
        keep_proportions: bool = False,
        upscale_method: str,
        width: int = 512,
    ) -> "_NodeBuilder":
        """Add a ``ResizeMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ResizeMask',
            mask=mask,
            crop=crop,
            height=height,
            keep_proportions=keep_proportions,
            upscale_method=upscale_method,
            width=width,
        )

class ReverseImageBatch:
    """Typed wrapper for the ComfyUI node class ``ReverseImageBatch``.

    Display name: Reverse Image Batch

    Category: KJNodes/image

    Reverses the order of the images in a batch.
    """

    CLASS_TYPE = 'ReverseImageBatch'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ReverseImageBatch`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ReverseImageBatch',
            images=images,
        )

class RoundMask:
    """Typed wrapper for the ComfyUI node class ``RoundMask``.

    Display name: Round Mask

    Category: KJNodes/masking

    Rounds the mask or batch of masks to a binary mask.
    """

    CLASS_TYPE = 'RoundMask'
    OUTPUTS: tuple[str, ...] = ('MASK',)
    OUTPUT_TYPES: tuple[str, ...] = ('MASK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        mask: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``RoundMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'RoundMask',
            mask=mask,
        )

class SV3D_BatchSchedule:
    """Typed wrapper for the ComfyUI node class ``SV3D_BatchSchedule``.

    Display name: SV3D Batch Schedule

    Category: KJNodes/experimental

    Allow scheduling of the azimuth and elevation conditions for SV3D.
    """

    CLASS_TYPE = 'SV3D_BatchSchedule'
    OUTPUTS: tuple[str, ...] = ('positive', 'negative', 'latent')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'CONDITIONING', 'LATENT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        clip_vision: "Handle" = None,
        init_image: "Handle" = None,
        vae: "Handle" = None,
        azimuth_points_string: str = "0:(0.0),\n9:(180.0),\n20:(360.0)\n",
        batch_size: int = 21,
        elevation_points_string: str = "0:(0.0),\n9:(0.0),\n20:(0.0)\n",
        height: int = 576,
        interpolation: str,
        width: int = 576,
    ) -> "_NodeBuilder":
        """Add a ``SV3D_BatchSchedule`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'SV3D_BatchSchedule',
            clip_vision=clip_vision,
            init_image=init_image,
            vae=vae,
            azimuth_points_string=azimuth_points_string,
            batch_size=batch_size,
            elevation_points_string=elevation_points_string,
            height=height,
            interpolation=interpolation,
            width=width,
        )

class SamplerSelfRefineVideo:
    """Typed wrapper for the ComfyUI node class ``SamplerSelfRefineVideo``.

    Category: KJNodes/samplers

    Attempt to implement https://github.com/agwmon/self-refine-video, for testing only, MAY NOT WORK AS INTENDED.
    """

    CLASS_TYPE = 'SamplerSelfRefineVideo'
    OUTPUTS: tuple[str, ...] = ('SAMPLER',)
    OUTPUT_TYPES: tuple[str, ...] = ('SAMPLER',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        input_mode: "Handle" = None,
        certain_percentage: float = 0.999,
        seed: int = 0,
        uncertainty_threshold: float = 0.2,
        verbose: bool = False,
        latent: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``SamplerSelfRefineVideo`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'SamplerSelfRefineVideo',
            input_mode=input_mode,
            certain_percentage=certain_percentage,
            seed=seed,
            uncertainty_threshold=uncertainty_threshold,
            verbose=verbose,
            latent=latent,
        )

class SaveImageKJ:
    """Typed wrapper for the ComfyUI node class ``SaveImageKJ``.

    Display name: Save Image KJ

    Category: KJNodes/image

    Saves the input images to your ComfyUI output directory.
    """

    CLASS_TYPE = 'SaveImageKJ'
    OUTPUTS: tuple[str, ...] = ('filename',)
    OUTPUT_TYPES: tuple[str, ...] = ('STRING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images: "Handle" = None,
        filename_prefix: str = "ComfyUI",
        output_folder: str = "output",
        caption: str = "",
        caption_file_extension: str = ".txt",
    ) -> "_NodeBuilder":
        """Add a ``SaveImageKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'SaveImageKJ',
            images=images,
            filename_prefix=filename_prefix,
            output_folder=output_folder,
            caption=caption,
            caption_file_extension=caption_file_extension,
        )

class SaveImageWithAlpha:
    """Typed wrapper for the ComfyUI node class ``SaveImageWithAlpha``.

    Display name: Save Image With Alpha

    Category: KJNodes/image

    Saves an image and mask as .PNG with the mask as the alpha channel.
    """

    CLASS_TYPE = 'SaveImageWithAlpha'
    OUTPUTS: tuple[str, ...] = ()
    OUTPUT_TYPES: tuple[str, ...] = ()

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images: "Handle" = None,
        mask: "Handle" = None,
        filename_prefix: str = "ComfyUI",
    ) -> "_NodeBuilder":
        """Add a ``SaveImageWithAlpha`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'SaveImageWithAlpha',
            images=images,
            mask=mask,
            filename_prefix=filename_prefix,
        )

class SaveStringKJ:
    """Typed wrapper for the ComfyUI node class ``SaveStringKJ``.

    Display name: Save String KJ

    Category: KJNodes/misc

    Saves the input string to your ComfyUI output directory.
    """

    CLASS_TYPE = 'SaveStringKJ'
    OUTPUTS: tuple[str, ...] = ('filename',)
    OUTPUT_TYPES: tuple[str, ...] = ('STRING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        filename_prefix: str = "text",
        output_folder: str = "output",
        string: str,
        file_extension: str = ".txt",
    ) -> "_NodeBuilder":
        """Add a ``SaveStringKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'SaveStringKJ',
            filename_prefix=filename_prefix,
            output_folder=output_folder,
            string=string,
            file_extension=file_extension,
        )

class ScaleBatchPromptSchedule:
    """Typed wrapper for the ComfyUI node class ``ScaleBatchPromptSchedule``.

    Display name: Scale Batch Prompt Schedule

    Category: KJNodes/misc

    Scales a batch schedule from Fizz' nodes BatchPromptSchedule
    """

    CLASS_TYPE = 'ScaleBatchPromptSchedule'
    OUTPUTS: tuple[str, ...] = ('STRING',)
    OUTPUT_TYPES: tuple[str, ...] = ('STRING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        input_str: str = "0:(0.0),\n7:(1.0),\n15:(0.0)\n",
        new_frame_count: int = 1,
        old_frame_count: int = 1,
    ) -> "_NodeBuilder":
        """Add a ``ScaleBatchPromptSchedule`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ScaleBatchPromptSchedule',
            input_str=input_str,
            new_frame_count=new_frame_count,
            old_frame_count=old_frame_count,
        )

class ScheduledCFGGuidance:
    """Typed wrapper for the ComfyUI node class ``ScheduledCFGGuidance``.

    Display name: Scheduled CFG Guidance

    Category: KJNodes/experimental
    """

    CLASS_TYPE = 'ScheduledCFGGuidance'
    OUTPUTS: tuple[str, ...] = ('GUIDER',)
    OUTPUT_TYPES: tuple[str, ...] = ('GUIDER',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        negative: "Handle" = None,
        positive: "Handle" = None,
        cfg: float = 6.0,
        end_percent: float = 1.0,
        start_percent: float = 0.0,
    ) -> "_NodeBuilder":
        """Add a ``ScheduledCFGGuidance`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ScheduledCFGGuidance',
            model=model,
            negative=negative,
            positive=positive,
            cfg=cfg,
            end_percent=end_percent,
            start_percent=start_percent,
        )

class ScreencapStream:
    """Typed wrapper for the ComfyUI node class ``ScreencapStream``.

    Display name: Screencap Stream

    Category: KJNodes/image

    Captures a frame from a browser screen/window share stream.
    """

    CLASS_TYPE = 'ScreencapStream'
    OUTPUTS: tuple[str, ...] = ('image',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        crop_height: int = 1,
        crop_width: int = 1,
        frame_data: str = "",
    ) -> "_NodeBuilder":
        """Add a ``ScreencapStream`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ScreencapStream',
            crop_height=crop_height,
            crop_width=crop_width,
            frame_data=frame_data,
        )

class Screencap_mss:
    """Typed wrapper for the ComfyUI node class ``Screencap_mss``.

    Display name: Screencap mss

    Category: KJNodes/image

    Captures an area specified by screen coordinates.
    """

    CLASS_TYPE = 'Screencap_mss'
    OUTPUTS: tuple[str, ...] = ('image',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        delay: float = 0.1,
        height: int = 512,
        num_frames: int = 1,
        width: int = 512,
        x: int = 0,
        y: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``Screencap_mss`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'Screencap_mss',
            delay=delay,
            height=height,
            num_frames=num_frames,
            width=width,
            x=x,
            y=y,
        )

class SeparateMasks:
    """Typed wrapper for the ComfyUI node class ``SeparateMasks``.

    Display name: Separate Masks

    Category: KJNodes/masking

    Separates a mask into multiple masks based on the size of the connected components.
    """

    CLASS_TYPE = 'SeparateMasks'
    OUTPUTS: tuple[str, ...] = ('mask',)
    OUTPUT_TYPES: tuple[str, ...] = ('MASK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        mask: "Handle" = None,
        max_poly_points: int = 8,
        mode: str,
        size_threshold_height: int = 256,
        size_threshold_width: int = 256,
    ) -> "_NodeBuilder":
        """Add a ``SeparateMasks`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'SeparateMasks',
            mask=mask,
            max_poly_points=max_poly_points,
            mode=mode,
            size_threshold_height=size_threshold_height,
            size_threshold_width=size_threshold_width,
        )

class SetShakkerLabsUnionControlNetType:
    """Typed wrapper for the ComfyUI node class ``SetShakkerLabsUnionControlNetType``.

    Display name: Set Shakker Labs Union ControlNet Type

    Category: conditioning/controlnet
    """

    CLASS_TYPE = 'SetShakkerLabsUnionControlNetType'
    OUTPUTS: tuple[str, ...] = ('CONTROL_NET',)
    OUTPUT_TYPES: tuple[str, ...] = ('CONTROL_NET',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        control_net: "Handle" = None,
        type: str,
    ) -> "_NodeBuilder":
        """Add a ``SetShakkerLabsUnionControlNetType`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'SetShakkerLabsUnionControlNetType',
            control_net=control_net,
            type=type,
        )

class ShuffleImageBatch:
    """Typed wrapper for the ComfyUI node class ``ShuffleImageBatch``.

    Display name: Shuffle Image Batch

    Category: KJNodes/image
    """

    CLASS_TYPE = 'ShuffleImageBatch'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images: "Handle" = None,
        seed: int = 123,
    ) -> "_NodeBuilder":
        """Add a ``ShuffleImageBatch`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'ShuffleImageBatch',
            images=images,
            seed=seed,
        )

class SigmasToFloat:
    """Typed wrapper for the ComfyUI node class ``SigmasToFloat``.

    Display name: Sigmas To Float

    Category: KJNodes/noise

    Creates a float list from sigmas tensors.
    """

    CLASS_TYPE = 'SigmasToFloat'
    OUTPUTS: tuple[str, ...] = ('float',)
    OUTPUT_TYPES: tuple[str, ...] = ('FLOAT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        sigmas: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``SigmasToFloat`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'SigmasToFloat',
            sigmas=sigmas,
        )

class SimpleCalculatorKJ:
    """Typed wrapper for the ComfyUI node class ``SimpleCalculatorKJ``.

    Category: KJNodes/misc

    Calculator node that evaluates a mathematical expression using inputs a and b.
    """

    CLASS_TYPE = 'SimpleCalculatorKJ'
    OUTPUTS: tuple[str, ...] = ('FLOAT', 'INT', 'BOOLEAN')
    OUTPUT_TYPES: tuple[str, ...] = ('FLOAT', 'INT', 'BOOLEAN')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        variables: "Handle" = None,
        expression: str = "a + b",
    ) -> "_NodeBuilder":
        """Add a ``SimpleCalculatorKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'SimpleCalculatorKJ',
            variables=variables,
            expression=expression,
        )

class SkipLayerGuidanceWanVideo:
    """Typed wrapper for the ComfyUI node class ``SkipLayerGuidanceWanVideo``.

    Display name: Skip Layer Guidance WanVideo

    Category: advanced/guidance

    Simplified skip layer guidance that only skips the uncond on selected blocks
    """

    CLASS_TYPE = 'SkipLayerGuidanceWanVideo'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        blocks: str = "10",
        end_percent: float = 1.0,
        start_percent: float = 0.2,
    ) -> "_NodeBuilder":
        """Add a ``SkipLayerGuidanceWanVideo`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'SkipLayerGuidanceWanVideo',
            model=model,
            blocks=blocks,
            end_percent=end_percent,
            start_percent=start_percent,
        )

class Sleep:
    """Typed wrapper for the ComfyUI node class ``Sleep``.

    Category: KJNodes/misc

    Delays the execution for the input amount of time.
    """

    CLASS_TYPE = 'Sleep'
    OUTPUTS: tuple[str, ...] = ('*',)
    OUTPUT_TYPES: tuple[str, ...] = ('*',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        input: "Handle",
        minutes: int = 0,
        seconds: float = 0.0,
    ) -> "_NodeBuilder":
        """Add a ``Sleep`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'Sleep',
            input=input,
            minutes=minutes,
            seconds=seconds,
        )

class SoundReactive:
    """Typed wrapper for the ComfyUI node class ``SoundReactive``.

    Display name: Sound Reactive

    Category: KJNodes/audio

    Reacts to the sound level of the input.
    """

    CLASS_TYPE = 'SoundReactive'
    OUTPUTS: tuple[str, ...] = ('sound_level', 'sound_level_int')
    OUTPUT_TYPES: tuple[str, ...] = ('FLOAT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        end_range_hz: int = 2000,
        multiplier: float = 1.0,
        normalize: bool = False,
        smoothing_factor: float = 0.5,
        sound_level: float = 1.0,
        start_range_hz: int = 150,
    ) -> "_NodeBuilder":
        """Add a ``SoundReactive`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'SoundReactive',
            end_range_hz=end_range_hz,
            multiplier=multiplier,
            normalize=normalize,
            smoothing_factor=smoothing_factor,
            sound_level=sound_level,
            start_range_hz=start_range_hz,
        )

class SplineEditor:
    """Typed wrapper for the ComfyUI node class ``SplineEditor``.

    Display name: Spline Editor

    Category: KJNodes/weights

    # WORK IN PROGRESS
    """

    CLASS_TYPE = 'SplineEditor'
    OUTPUTS: tuple[str, ...] = ('mask', 'coord_str', 'float', 'count', 'normalized_str')
    OUTPUT_TYPES: tuple[str, ...] = ('MASK', 'STRING', 'FLOAT', 'INT', 'STRING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        coordinates: str,
        float_output_type: str = "list",
        interpolation: str = "cardinal",
        mask_height: int = 512,
        mask_width: int = 512,
        points_store: str,
        points_to_sample: int = 16,
        repeat_output: int = 1,
        sampling_method: str = "time",
        tension: float = 0.5,
        bg_image: "Handle" = None,
        max_value: float = 1.0,
        min_value: float = 0.0,
    ) -> "_NodeBuilder":
        """Add a ``SplineEditor`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'SplineEditor',
            coordinates=coordinates,
            float_output_type=float_output_type,
            interpolation=interpolation,
            mask_height=mask_height,
            mask_width=mask_width,
            points_store=points_store,
            points_to_sample=points_to_sample,
            repeat_output=repeat_output,
            sampling_method=sampling_method,
            tension=tension,
            bg_image=bg_image,
            max_value=max_value,
            min_value=min_value,
        )

class SplitBboxes:
    """Typed wrapper for the ComfyUI node class ``SplitBboxes``.

    Display name: Split Bboxes

    Category: KJNodes/masking

    Splits the specified bbox list at the given index into two lists.
    """

    CLASS_TYPE = 'SplitBboxes'
    OUTPUTS: tuple[str, ...] = ('bboxes_a', 'bboxes_b')
    OUTPUT_TYPES: tuple[str, ...] = ('BBOX', 'BBOX')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        bboxes: "Handle",
        index: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``SplitBboxes`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'SplitBboxes',
            bboxes=bboxes,
            index=index,
        )

class SplitImageChannels:
    """Typed wrapper for the ComfyUI node class ``SplitImageChannels``.

    Display name: Split Image Channels

    Category: KJNodes/image

    Splits image channels into images where the selected channel
    """

    CLASS_TYPE = 'SplitImageChannels'
    OUTPUTS: tuple[str, ...] = ('red', 'green', 'blue', 'mask')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'IMAGE', 'IMAGE', 'MASK')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``SplitImageChannels`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'SplitImageChannels',
            image=image,
        )

class StableZero123_BatchSchedule:
    """Typed wrapper for the ComfyUI node class ``StableZero123_BatchSchedule``.

    Display name: Stable Zero123 Batch Schedule

    Category: KJNodes/experimental
    """

    CLASS_TYPE = 'StableZero123_BatchSchedule'
    OUTPUTS: tuple[str, ...] = ('positive', 'negative', 'latent')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'CONDITIONING', 'LATENT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        clip_vision: "Handle" = None,
        init_image: "Handle" = None,
        vae: "Handle" = None,
        azimuth_points_string: str = "0:(0.0),\n7:(1.0),\n15:(0.0)\n",
        batch_size: int = 1,
        elevation_points_string: str = "0:(0.0),\n7:(0.0),\n15:(0.0)\n",
        height: int = 256,
        interpolation: str,
        width: int = 256,
    ) -> "_NodeBuilder":
        """Add a ``StableZero123_BatchSchedule`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'StableZero123_BatchSchedule',
            clip_vision=clip_vision,
            init_image=init_image,
            vae=vae,
            azimuth_points_string=azimuth_points_string,
            batch_size=batch_size,
            elevation_points_string=elevation_points_string,
            height=height,
            interpolation=interpolation,
            width=width,
        )

class StartRecordCUDAMemoryHistory:
    """Typed wrapper for the ComfyUI node class ``StartRecordCUDAMemoryHistory``.

    Display name: Start Recording CUDAMemory History

    Category: KJNodes/memory

    THIS NODE ALWAYS RUNS. Starts recording CUDA memory allocation history, can be ended and saved with EndRecordCUDAMemoryHistory.
    """

    CLASS_TYPE = 'StartRecordCUDAMemoryHistory'
    OUTPUTS: tuple[str, ...] = ('input',)
    OUTPUT_TYPES: tuple[str, ...] = ('*',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        context: str = "all",
        enabled: str = "all",
        input: "Handle",
        max_entries: int = 100000,
        stacks: str = "all",
    ) -> "_NodeBuilder":
        """Add a ``StartRecordCUDAMemoryHistory`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'StartRecordCUDAMemoryHistory',
            context=context,
            enabled=enabled,
            input=input,
            max_entries=max_entries,
            stacks=stacks,
        )

class StringConstant:
    """Typed wrapper for the ComfyUI node class ``StringConstant``.

    Display name: String Constant

    Category: KJNodes/constants
    """

    CLASS_TYPE = 'StringConstant'
    OUTPUTS: tuple[str, ...] = ('STRING',)
    OUTPUT_TYPES: tuple[str, ...] = ('STRING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        string: str = "",
    ) -> "_NodeBuilder":
        """Add a ``StringConstant`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'StringConstant',
            string=string,
        )

class StringConstantMultiline:
    """Typed wrapper for the ComfyUI node class ``StringConstantMultiline``.

    Display name: String Constant Multiline

    Category: KJNodes/constants
    """

    CLASS_TYPE = 'StringConstantMultiline'
    OUTPUTS: tuple[str, ...] = ('STRING',)
    OUTPUT_TYPES: tuple[str, ...] = ('STRING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        string: str = "",
        strip_newlines: bool = True,
    ) -> "_NodeBuilder":
        """Add a ``StringConstantMultiline`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'StringConstantMultiline',
            string=string,
            strip_newlines=strip_newlines,
        )

class StringToFloatList:
    """Typed wrapper for the ComfyUI node class ``StringToFloatList``.

    Display name: String to Float List

    Category: KJNodes/misc
    """

    CLASS_TYPE = 'StringToFloatList'
    OUTPUTS: tuple[str, ...] = ('FLOAT',)
    OUTPUT_TYPES: tuple[str, ...] = ('FLOAT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        string: str = "1, 2, 3",
    ) -> "_NodeBuilder":
        """Add a ``StringToFloatList`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'StringToFloatList',
            string=string,
        )

class StyleModelApplyAdvanced:
    """Typed wrapper for the ComfyUI node class ``StyleModelApplyAdvanced``.

    Display name: Style Model Apply Advanced

    Category: KJNodes/experimental

    StyleModelApply but with strength parameter
    """

    CLASS_TYPE = 'StyleModelApplyAdvanced'
    OUTPUTS: tuple[str, ...] = ('CONDITIONING',)
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        clip_vision_output: "Handle" = None,
        conditioning: "Handle" = None,
        style_model: "Handle" = None,
        strength: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``StyleModelApplyAdvanced`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'StyleModelApplyAdvanced',
            clip_vision_output=clip_vision_output,
            conditioning=conditioning,
            style_model=style_model,
            strength=strength,
        )

class Superprompt:
    """Typed wrapper for the ComfyUI node class ``Superprompt``.

    Category: KJNodes/text

    # SuperPrompt
    """

    CLASS_TYPE = 'Superprompt'
    OUTPUTS: tuple[str, ...] = ('STRING',)
    OUTPUT_TYPES: tuple[str, ...] = ('STRING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        instruction_prompt: str = "Expand the following prompt to add more detail",
        max_new_tokens: int = 128,
        prompt: str = "",
    ) -> "_NodeBuilder":
        """Add a ``Superprompt`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'Superprompt',
            instruction_prompt=instruction_prompt,
            max_new_tokens=max_new_tokens,
            prompt=prompt,
        )

class TimerNodeKJ:
    """Typed wrapper for the ComfyUI node class ``TimerNodeKJ``.

    Display name: Timer Node KJ

    Category: KJNodes/misc
    """

    CLASS_TYPE = 'TimerNodeKJ'
    OUTPUTS: tuple[str, ...] = ('any_output', 'timer', 'time')
    OUTPUT_TYPES: tuple[str, ...] = ('*', 'TIMER', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        any_input: "Handle",
        mode: str,
        name: str = "Timer",
        timer: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``TimerNodeKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'TimerNodeKJ',
            any_input=any_input,
            mode=mode,
            name=name,
            timer=timer,
        )

class TorchCompileControlNet:
    """Typed wrapper for the ComfyUI node class ``TorchCompileControlNet``.

    Category: KJNodes/torchcompile
    """

    CLASS_TYPE = 'TorchCompileControlNet'
    OUTPUTS: tuple[str, ...] = ('CONTROL_NET',)
    OUTPUT_TYPES: tuple[str, ...] = ('CONTROL_NET',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        controlnet: "Handle" = None,
        backend: str,
        fullgraph: bool = False,
        mode: str = "default",
    ) -> "_NodeBuilder":
        """Add a ``TorchCompileControlNet`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'TorchCompileControlNet',
            controlnet=controlnet,
            backend=backend,
            fullgraph=fullgraph,
            mode=mode,
        )

class TorchCompileCosmosModel:
    """Typed wrapper for the ComfyUI node class ``TorchCompileCosmosModel``.

    Category: KJNodes/deprecated

    This node has been replaced with TorchCompileModelAdvanced node, please use that instead.
    """

    CLASS_TYPE = 'TorchCompileCosmosModel'
    OUTPUTS: tuple[str, ...] = ('*',)
    OUTPUT_TYPES: tuple[str, ...] = ('*',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle",
    ) -> "_NodeBuilder":
        """Add a ``TorchCompileCosmosModel`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'TorchCompileCosmosModel',
            model=model,
        )

class TorchCompileLTXModel:
    """Typed wrapper for the ComfyUI node class ``TorchCompileLTXModel``.

    Category: KJNodes/deprecated

    This node has been replaced with TorchCompileModelAdvanced node, please use that instead.
    """

    CLASS_TYPE = 'TorchCompileLTXModel'
    OUTPUTS: tuple[str, ...] = ('*',)
    OUTPUT_TYPES: tuple[str, ...] = ('*',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle",
    ) -> "_NodeBuilder":
        """Add a ``TorchCompileLTXModel`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'TorchCompileLTXModel',
            model=model,
        )

class TorchCompileModelAdvanced:
    """Typed wrapper for the ComfyUI node class ``TorchCompileModelAdvanced``.

    Category: KJNodes/torchcompile

    Advanced torch.compile patching for diffusion models.
    """

    CLASS_TYPE = 'TorchCompileModelAdvanced'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        backend: str = "inductor",
        compile_transformer_blocks_only: bool = True,
        debug_compile_keys: bool = False,
        dynamic: str = "auto",
        dynamo_cache_size_limit: int = 64,
        fullgraph: bool = False,
        mode: str = "default",
        disable_dynamic_vram: bool = False,
    ) -> "_NodeBuilder":
        """Add a ``TorchCompileModelAdvanced`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'TorchCompileModelAdvanced',
            model=model,
            backend=backend,
            compile_transformer_blocks_only=compile_transformer_blocks_only,
            debug_compile_keys=debug_compile_keys,
            dynamic=dynamic,
            dynamo_cache_size_limit=dynamo_cache_size_limit,
            fullgraph=fullgraph,
            mode=mode,
            disable_dynamic_vram=disable_dynamic_vram,
        )

class TorchCompileModelFluxAdvanced:
    """Typed wrapper for the ComfyUI node class ``TorchCompileModelFluxAdvanced``.

    Category: KJNodes/deprecated

    This node has been replaced with TorchCompileModelAdvanced node, please use that instead.
    """

    CLASS_TYPE = 'TorchCompileModelFluxAdvanced'
    OUTPUTS: tuple[str, ...] = ('*',)
    OUTPUT_TYPES: tuple[str, ...] = ('*',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle",
    ) -> "_NodeBuilder":
        """Add a ``TorchCompileModelFluxAdvanced`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'TorchCompileModelFluxAdvanced',
            model=model,
        )

class TorchCompileModelFluxAdvancedV2:
    """Typed wrapper for the ComfyUI node class ``TorchCompileModelFluxAdvancedV2``.

    Category: KJNodes/torchcompile

    Deprecated, use TorchCompileModelAdvanced instead.
    """

    CLASS_TYPE = 'TorchCompileModelFluxAdvancedV2'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        backend: str,
        double_blocks: bool = True,
        dynamic: bool = False,
        fullgraph: bool = False,
        mode: str = "default",
        single_blocks: bool = True,
        dynamo_cache_size_limit: int = 64,
        force_parameter_static_shapes: bool = True,
    ) -> "_NodeBuilder":
        """Add a ``TorchCompileModelFluxAdvancedV2`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'TorchCompileModelFluxAdvancedV2',
            model=model,
            backend=backend,
            double_blocks=double_blocks,
            dynamic=dynamic,
            fullgraph=fullgraph,
            mode=mode,
            single_blocks=single_blocks,
            dynamo_cache_size_limit=dynamo_cache_size_limit,
            force_parameter_static_shapes=force_parameter_static_shapes,
        )

class TorchCompileModelHyVideo:
    """Typed wrapper for the ComfyUI node class ``TorchCompileModelHyVideo``.

    Category: KJNodes/deprecated

    This node has been replaced with TorchCompileModelAdvanced node, please use that instead.
    """

    CLASS_TYPE = 'TorchCompileModelHyVideo'
    OUTPUTS: tuple[str, ...] = ('*',)
    OUTPUT_TYPES: tuple[str, ...] = ('*',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle",
    ) -> "_NodeBuilder":
        """Add a ``TorchCompileModelHyVideo`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'TorchCompileModelHyVideo',
            model=model,
        )

class TorchCompileModelQwenImage:
    """Typed wrapper for the ComfyUI node class ``TorchCompileModelQwenImage``.

    Category: KJNodes/deprecated

    This node has been replaced with TorchCompileModelAdvanced node, please use that instead.
    """

    CLASS_TYPE = 'TorchCompileModelQwenImage'
    OUTPUTS: tuple[str, ...] = ('*',)
    OUTPUT_TYPES: tuple[str, ...] = ('*',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle",
    ) -> "_NodeBuilder":
        """Add a ``TorchCompileModelQwenImage`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'TorchCompileModelQwenImage',
            model=model,
        )

class TorchCompileModelWanVideo:
    """Typed wrapper for the ComfyUI node class ``TorchCompileModelWanVideo``.

    Category: KJNodes/deprecated

    This node has been replaced with TorchCompileModelAdvanced node, please use that instead.
    """

    CLASS_TYPE = 'TorchCompileModelWanVideo'
    OUTPUTS: tuple[str, ...] = ('*',)
    OUTPUT_TYPES: tuple[str, ...] = ('*',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle",
    ) -> "_NodeBuilder":
        """Add a ``TorchCompileModelWanVideo`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'TorchCompileModelWanVideo',
            model=model,
        )

class TorchCompileModelWanVideoV2:
    """Typed wrapper for the ComfyUI node class ``TorchCompileModelWanVideoV2``.

    Category: KJNodes/torchcompile

    Deprecated, use TorchCompileModelAdvanced instead.
    """

    CLASS_TYPE = 'TorchCompileModelWanVideoV2'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        backend: str = "inductor",
        compile_transformer_blocks_only: bool = True,
        dynamic: bool = False,
        dynamo_cache_size_limit: int = 64,
        fullgraph: bool = False,
        mode: str = "default",
        force_parameter_static_shapes: bool = True,
    ) -> "_NodeBuilder":
        """Add a ``TorchCompileModelWanVideoV2`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'TorchCompileModelWanVideoV2',
            model=model,
            backend=backend,
            compile_transformer_blocks_only=compile_transformer_blocks_only,
            dynamic=dynamic,
            dynamo_cache_size_limit=dynamo_cache_size_limit,
            fullgraph=fullgraph,
            mode=mode,
            force_parameter_static_shapes=force_parameter_static_shapes,
        )

class TorchCompileVAE:
    """Typed wrapper for the ComfyUI node class ``TorchCompileVAE``.

    Category: KJNodes/torchcompile
    """

    CLASS_TYPE = 'TorchCompileVAE'
    OUTPUTS: tuple[str, ...] = ('VAE',)
    OUTPUT_TYPES: tuple[str, ...] = ('VAE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        vae: "Handle" = None,
        backend: str,
        compile_decoder: bool = True,
        compile_encoder: bool = True,
        fullgraph: bool = False,
        mode: str = "default",
    ) -> "_NodeBuilder":
        """Add a ``TorchCompileVAE`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'TorchCompileVAE',
            vae=vae,
            backend=backend,
            compile_decoder=compile_decoder,
            compile_encoder=compile_encoder,
            fullgraph=fullgraph,
            mode=mode,
        )

class TransitionImagesInBatch:
    """Typed wrapper for the ComfyUI node class ``TransitionImagesInBatch``.

    Display name: Transition Images In Batch

    Category: KJNodes/image

    Creates transitions between images in a batch.
    """

    CLASS_TYPE = 'TransitionImagesInBatch'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images: "Handle" = None,
        blur_radius: float = 0.0,
        device: str = "CPU",
        interpolation: str,
        reverse: bool = False,
        transition_type: str,
        transitioning_frames: int = 1,
    ) -> "_NodeBuilder":
        """Add a ``TransitionImagesInBatch`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'TransitionImagesInBatch',
            images=images,
            blur_radius=blur_radius,
            device=device,
            interpolation=interpolation,
            reverse=reverse,
            transition_type=transition_type,
            transitioning_frames=transitioning_frames,
        )

class TransitionImagesMulti:
    """Typed wrapper for the ComfyUI node class ``TransitionImagesMulti``.

    Display name: Transition Images Multi

    Category: KJNodes/image

    Creates transitions between images.
    """

    CLASS_TYPE = 'TransitionImagesMulti'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image_1: "Handle" = None,
        blur_radius: float = 0.0,
        device: str = "CPU",
        inputcount: int = 2,
        interpolation: str,
        reverse: bool = False,
        transition_type: str,
        transitioning_frames: int = 2,
        image_2: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``TransitionImagesMulti`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'TransitionImagesMulti',
            image_1=image_1,
            blur_radius=blur_radius,
            device=device,
            inputcount=inputcount,
            interpolation=interpolation,
            reverse=reverse,
            transition_type=transition_type,
            transitioning_frames=transitioning_frames,
            image_2=image_2,
        )

class VAEDecodeLoopKJ:
    """Typed wrapper for the ComfyUI node class ``VAEDecodeLoopKJ``.

    Display name: VAE Decode Loop KJ

    Category: KJNodes/vae

    Video latent VAE decoding to fix artifacts on loop seams.
    """

    CLASS_TYPE = 'VAEDecodeLoopKJ'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        samples: "Handle" = None,
        vae: "Handle" = None,
        overlap_latent_frames: int = 2,
    ) -> "_NodeBuilder":
        """Add a ``VAEDecodeLoopKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'VAEDecodeLoopKJ',
            samples=samples,
            vae=vae,
            overlap_latent_frames=overlap_latent_frames,
        )

class VAELoaderKJ:
    """Typed wrapper for the ComfyUI node class ``VAELoaderKJ``.

    Display name: VAELoader KJ

    Category: KJNodes/vae
    """

    CLASS_TYPE = 'VAELoaderKJ'
    OUTPUTS: tuple[str, ...] = ('VAE',)
    OUTPUT_TYPES: tuple[str, ...] = ('VAE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        device: str,
        vae_name: str,
        weight_dtype: str,
    ) -> "_NodeBuilder":
        """Add a ``VAELoaderKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'VAELoaderKJ',
            device=device,
            vae_name=vae_name,
            weight_dtype=weight_dtype,
        )

class VRAM_Debug:
    """Typed wrapper for the ComfyUI node class ``VRAM_Debug``.

    Display name: VRAM Debug

    Category: KJNodes/memory

    Returns the inputs unchanged, they are only used as triggers,
    """

    CLASS_TYPE = 'VRAM_Debug'
    OUTPUTS: tuple[str, ...] = ('any_output', 'image_pass', 'model_pass', 'freemem_before', 'freemem_after')
    OUTPUT_TYPES: tuple[str, ...] = ('*', 'IMAGE', 'MODEL', 'INT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        empty_cache: bool = True,
        gc_collect: bool = True,
        unload_all_models: bool = False,
        any_input: "Handle" = None,
        image_pass: "Handle" = None,
        model_pass: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``VRAM_Debug`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'VRAM_Debug',
            empty_cache=empty_cache,
            gc_collect=gc_collect,
            unload_all_models=unload_all_models,
            any_input=any_input,
            image_pass=image_pass,
            model_pass=model_pass,
        )

class VisualizeCUDAMemoryHistory:
    """Typed wrapper for the ComfyUI node class ``VisualizeCUDAMemoryHistory``.

    Display name: Visualize CUDAMemory History

    Category: KJNodes/memory

    Visualizes a CUDA memory allocation history file, opens in browser
    """

    CLASS_TYPE = 'VisualizeCUDAMemoryHistory'
    OUTPUTS: tuple[str, ...] = ('output_path',)
    OUTPUT_TYPES: tuple[str, ...] = ('STRING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        snapshot_path: str,
    ) -> "_NodeBuilder":
        """Add a ``VisualizeCUDAMemoryHistory`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'VisualizeCUDAMemoryHistory',
            snapshot_path=snapshot_path,
        )

class VisualizeSigmasKJ:
    """Typed wrapper for the ComfyUI node class ``VisualizeSigmasKJ``.

    Category: KJNodes/misc
    """

    CLASS_TYPE = 'VisualizeSigmasKJ'
    OUTPUTS: tuple[str, ...] = ('sigmas_out', 'image')
    OUTPUT_TYPES: tuple[str, ...] = ('SIGMAS', 'IMAGE')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        sigmas: "Handle" = None,
        end_step: int = -1,
        start_step: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``VisualizeSigmasKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'VisualizeSigmasKJ',
            sigmas=sigmas,
            end_step=end_step,
            start_step=start_step,
        )

class Wan21BlockLoraSelect:
    """Typed wrapper for the ComfyUI node class ``Wan21BlockLoraSelect``.

    Display name: Wan21 Block Lora Select

    Category: KJNodes/wan

    Select individual block alpha values, value of 0 removes the block altogether
    """

    CLASS_TYPE = 'Wan21BlockLoraSelect'
    OUTPUTS: tuple[str, ...] = ('blocks',)
    OUTPUT_TYPES: tuple[str, ...] = ('SELECTEDDITBLOCKS',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        blocks_0: float = 0.0,
        blocks_1: float = 0.0,
        blocks_10: float = 0.0,
        blocks_11: float = 0.0,
        blocks_12: float = 0.0,
        blocks_13: float = 0.0,
        blocks_14: float = 0.0,
        blocks_15: float = 0.0,
        blocks_16: float = 0.0,
        blocks_17: float = 0.0,
        blocks_18: float = 0.0,
        blocks_19: float = 0.0,
        blocks_2: float = 0.0,
        blocks_20: float = 0.0,
        blocks_21: float = 0.0,
        blocks_22: float = 0.0,
        blocks_23: float = 0.0,
        blocks_24: float = 0.0,
        blocks_25: float = 0.0,
        blocks_26: float = 0.0,
        blocks_27: float = 0.0,
        blocks_28: float = 0.0,
        blocks_29: float = 0.0,
        blocks_3: float = 0.0,
        blocks_30: float = 0.0,
        blocks_31: float = 0.0,
        blocks_32: float = 0.0,
        blocks_33: float = 0.0,
        blocks_34: float = 0.0,
        blocks_35: float = 0.0,
        blocks_36: float = 0.0,
        blocks_37: float = 0.0,
        blocks_38: float = 0.0,
        blocks_39: float = 0.0,
        blocks_4: float = 0.0,
        blocks_5: float = 0.0,
        blocks_6: float = 0.0,
        blocks_7: float = 0.0,
        blocks_8: float = 0.0,
        blocks_9: float = 0.0,
    ) -> "_NodeBuilder":
        """Add a ``Wan21BlockLoraSelect`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'Wan21BlockLoraSelect',
            **{
                'blocks.0.': blocks_0,
                'blocks.1.': blocks_1,
                'blocks.10.': blocks_10,
                'blocks.11.': blocks_11,
                'blocks.12.': blocks_12,
                'blocks.13.': blocks_13,
                'blocks.14.': blocks_14,
                'blocks.15.': blocks_15,
                'blocks.16.': blocks_16,
                'blocks.17.': blocks_17,
                'blocks.18.': blocks_18,
                'blocks.19.': blocks_19,
                'blocks.2.': blocks_2,
                'blocks.20.': blocks_20,
                'blocks.21.': blocks_21,
                'blocks.22.': blocks_22,
                'blocks.23.': blocks_23,
                'blocks.24.': blocks_24,
                'blocks.25.': blocks_25,
                'blocks.26.': blocks_26,
                'blocks.27.': blocks_27,
                'blocks.28.': blocks_28,
                'blocks.29.': blocks_29,
                'blocks.3.': blocks_3,
                'blocks.30.': blocks_30,
                'blocks.31.': blocks_31,
                'blocks.32.': blocks_32,
                'blocks.33.': blocks_33,
                'blocks.34.': blocks_34,
                'blocks.35.': blocks_35,
                'blocks.36.': blocks_36,
                'blocks.37.': blocks_37,
                'blocks.38.': blocks_38,
                'blocks.39.': blocks_39,
                'blocks.4.': blocks_4,
                'blocks.5.': blocks_5,
                'blocks.6.': blocks_6,
                'blocks.7.': blocks_7,
                'blocks.8.': blocks_8,
                'blocks.9.': blocks_9,
            },
        )

class WanChunkFeedForward:
    """Typed wrapper for the ComfyUI node class ``WanChunkFeedForward``.

    Display name: Wan Chunk FeedForward

    Category: KJNodes/wan

    EXPERIMENTAL AND MAY CHANGE THE MODEL OUTPUT!! Chunks feedforward activations to reduce peak VRAM usage.
    """

    CLASS_TYPE = 'WanChunkFeedForward'
    OUTPUTS: tuple[str, ...] = ('model',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        chunks: int = 2,
        dim_threshold: int = 4096,
    ) -> "_NodeBuilder":
        """Add a ``WanChunkFeedForward`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'WanChunkFeedForward',
            model=model,
            chunks=chunks,
            dim_threshold=dim_threshold,
        )

class WanImageToVideoSVIPro:
    """Typed wrapper for the ComfyUI node class ``WanImageToVideoSVIPro``.

    Category: conditioning/video_models
    """

    CLASS_TYPE = 'WanImageToVideoSVIPro'
    OUTPUTS: tuple[str, ...] = ('positive', 'negative', 'latent')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'CONDITIONING', 'LATENT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        anchor_samples: "Handle" = None,
        negative: "Handle" = None,
        positive: "Handle" = None,
        length: int = 81,
        motion_latent_count: int = 1,
        prev_samples: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``WanImageToVideoSVIPro`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'WanImageToVideoSVIPro',
            anchor_samples=anchor_samples,
            negative=negative,
            positive=positive,
            length=length,
            motion_latent_count=motion_latent_count,
            prev_samples=prev_samples,
        )

class WanVideoEnhanceAVideoKJ:
    """Typed wrapper for the ComfyUI node class ``WanVideoEnhanceAVideoKJ``.

    Display name: WanVideo Enhance A Video (native)

    Category: KJNodes/wan

    https://github.com/NUS-HPC-AI-Lab/Enhance-A-Video
    """

    CLASS_TYPE = 'WanVideoEnhanceAVideoKJ'
    OUTPUTS: tuple[str, ...] = ('model',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latent: "Handle" = None,
        model: "Handle" = None,
        weight: float = 2.0,
    ) -> "_NodeBuilder":
        """Add a ``WanVideoEnhanceAVideoKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'WanVideoEnhanceAVideoKJ',
            latent=latent,
            model=model,
            weight=weight,
        )

class WanVideoNAG:
    """Typed wrapper for the ComfyUI node class ``WanVideoNAG``.

    Category: KJNodes/wan

    https://github.com/ChenDarYen/Normalized-Attention-Guidance
    """

    CLASS_TYPE = 'WanVideoNAG'
    OUTPUTS: tuple[str, ...] = ('model',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        conditioning: "Handle" = None,
        model: "Handle" = None,
        nag_alpha: float = 0.25,
        nag_scale: float = 11.0,
        nag_tau: float = 2.5,
        input_type: str = "",
    ) -> "_NodeBuilder":
        """Add a ``WanVideoNAG`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'WanVideoNAG',
            conditioning=conditioning,
            model=model,
            nag_alpha=nag_alpha,
            nag_scale=nag_scale,
            nag_tau=nag_tau,
            input_type=input_type,
        )

class WanVideoTeaCacheKJ:
    """Typed wrapper for the ComfyUI node class ``WanVideoTeaCacheKJ``.

    Display name: WanVideo Tea Cache (native)

    Category: KJNodes/deprecated

    Patch WanVideo model to use TeaCache. Speeds up inference by caching the output and
    """

    CLASS_TYPE = 'WanVideoTeaCacheKJ'
    OUTPUTS: tuple[str, ...] = ('model',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        cache_device: str = "offload_device",
        coefficients: str = "i2v_480",
        end_percent: float = 1.0,
        rel_l1_thresh: float = 0.275,
        start_percent: float = 0.1,
    ) -> "_NodeBuilder":
        """Add a ``WanVideoTeaCacheKJ`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'WanVideoTeaCacheKJ',
            model=model,
            cache_device=cache_device,
            coefficients=coefficients,
            end_percent=end_percent,
            rel_l1_thresh=rel_l1_thresh,
            start_percent=start_percent,
        )

class WebcamCaptureCV2:
    """Typed wrapper for the ComfyUI node class ``WebcamCaptureCV2``.

    Display name: Webcam Capture CV2

    Category: KJNodes/experimental

    Captures a frame from a webcam using CV2.
    """

    CLASS_TYPE = 'WebcamCaptureCV2'
    OUTPUTS: tuple[str, ...] = ('image',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        cam_index: int = 0,
        height: int = 512,
        release: bool = False,
        width: int = 512,
        x: int = 0,
        y: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``WebcamCaptureCV2`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'WebcamCaptureCV2',
            cam_index=cam_index,
            height=height,
            release=release,
            width=width,
            x=x,
            y=y,
        )

class WeightScheduleConvert:
    """Typed wrapper for the ComfyUI node class ``WeightScheduleConvert``.

    Display name: Weight Schedule Convert

    Category: KJNodes/weights

    Converts different value lists/series to another type.
    """

    CLASS_TYPE = 'WeightScheduleConvert'
    OUTPUTS: tuple[str, ...] = ('FLOAT', 'STRING', 'INT')
    OUTPUT_TYPES: tuple[str, ...] = ('FLOAT', 'STRING', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        input_values: float = 0.0,
        invert: bool = False,
        output_type: str = "list",
        repeat: int = 1,
        interpolation_curve: float = 0.0,
        remap_max: float = 1.0,
        remap_min: float = 0.0,
        remap_to_frames: int = 0,
        remap_values: bool = False,
    ) -> "_NodeBuilder":
        """Add a ``WeightScheduleConvert`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'WeightScheduleConvert',
            input_values=input_values,
            invert=invert,
            output_type=output_type,
            repeat=repeat,
            interpolation_curve=interpolation_curve,
            remap_max=remap_max,
            remap_min=remap_min,
            remap_to_frames=remap_to_frames,
            remap_values=remap_values,
        )

class WeightScheduleExtend:
    """Typed wrapper for the ComfyUI node class ``WeightScheduleExtend``.

    Display name: Weight Schedule Extend

    Category: KJNodes/weights

    Extends, and converts if needed, different value lists/series
    """

    CLASS_TYPE = 'WeightScheduleExtend'
    OUTPUTS: tuple[str, ...] = ('FLOAT',)
    OUTPUT_TYPES: tuple[str, ...] = ('FLOAT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        input_values_1: float = 0.0,
        input_values_2: float = 0.0,
        output_type: str = "match_input",
    ) -> "_NodeBuilder":
        """Add a ``WeightScheduleExtend`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'WeightScheduleExtend',
            input_values_1=input_values_1,
            input_values_2=input_values_2,
            output_type=output_type,
        )

class WidgetToString:
    """Typed wrapper for the ComfyUI node class ``WidgetToString``.

    Display name: Widget To String

    Category: KJNodes/text

    Selects a node and it's specified widget and outputs the value as a string.
    """

    CLASS_TYPE = 'WidgetToString'
    OUTPUTS: tuple[str, ...] = ('STRING',)
    OUTPUT_TYPES: tuple[str, ...] = ('STRING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        id: int = 0,
        return_all: bool = False,
        widget_name: str,
        allowed_float_decimals: int = 2,
        any_input: "Handle" = None,
        node_title: str = "",
    ) -> "_NodeBuilder":
        """Add a ``WidgetToString`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-KJNodes@runpod-snapshot.json sha256:b8303c2a325a
        """
        return wf.node(
            'WidgetToString',
            id=id,
            return_all=return_all,
            widget_name=widget_name,
            allowed_float_decimals=allowed_float_decimals,
            any_input=any_input,
            node_title=node_title,
        )
