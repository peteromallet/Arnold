from __future__ import annotations

from vibecomfy import VibeWorkflow, WorkflowSource


def build() -> VibeWorkflow:
    workflow = VibeWorkflow("audio/ace_step_1_5_t2a_song", WorkflowSource("typed-fixture"))
    clip = workflow.node(
        "DualCLIPLoader",
        clip_name1="qwen_0.6b_ace15.safetensors",
        clip_name2="qwen_4b_ace15.safetensors",
        type="ace",
        device="default",
    ).out(0)
    vae = workflow.node("VAELoader", vae_name="ace_1.5_vae.safetensors").out(0)
    latent = workflow.node("EmptyAceStep1.5LatentAudio", seconds=2, batch_size=1).out(0)
    negative_builder = workflow.node("ConditioningZeroOut")
    negative = negative_builder.out(0)
    sampler_builder = workflow.node(
        "KSampler",
        seed=561594583201063,
        steps=1,
        cfg=1,
        sampler_name="euler",
        scheduler="simple",
        denoise=1,
    )
    samples = sampler_builder.out(0)
    model_sampling_builder = workflow.node("ModelSamplingAuraFlow", shift=3)
    shifted_model = model_sampling_builder.out(0)
    decode_builder = workflow.node("VAEDecodeAudio")
    audio = decode_builder.out(0)
    conditioning = workflow.node(
        "TextEncodeAceStepAudio1.5",
        seed=561594583201063,
        duration=2,
        tags="synthwave, short instrumental",
        lyrics="Verse\nTiny signal in the night.",
        bpm=120,
        timesignature="4",
        language="en",
        keyscale="E minor",
        generate_audio_codes=True,
        cfg_scale=1.5,
        top_p=0.85,
        min_p=0.9,
        top_k=0,
        temperature=0,
        clip=clip,
    ).out(0)
    model = workflow.node("UNETLoader", unet_name="acestep_v1.5_turbo.safetensors", weight_dtype="default").out(0)
    workflow.connect(conditioning, f"{negative_builder.id}.conditioning")
    workflow.connect(shifted_model, f"{sampler_builder.id}.model")
    workflow.connect(conditioning, f"{sampler_builder.id}.positive")
    workflow.connect(negative, f"{sampler_builder.id}.negative")
    workflow.connect(latent, f"{sampler_builder.id}.latent_image")
    workflow.connect(model, f"{model_sampling_builder.id}.model")
    workflow.connect(samples, f"{decode_builder.id}.samples")
    workflow.connect(vae, f"{decode_builder.id}.vae")
    workflow.node("SaveAudioMP3", filename_prefix="audio/vibecomfy_ace_step_smoke", quality="V0", audio=audio)
    return workflow
