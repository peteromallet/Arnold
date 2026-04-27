from __future__ import annotations

from vibecomfy.registry.ready_template import build_authored_ready_workflow

NODES = (('9', 'SaveImage', {'images': ['75', 0], 'widget_0': 'Flux2-Klein'}),
 ('78', 'SaveImage', {'images': ['77', 0], 'widget_0': 'Flux2-Klein'}),
 ('76',
  'PrimitiveStringMultiline',
  {'widget_0': 'A hedgehog wearing a tiny party hat surrounded by confetti, early digital camera style, slight noise, '
               'flash photography, candid moment, 2000s digicam aesthetic, festive birthday celebration atmosphere\n'}),
 ('75',
  '7b34ab90-36f9-45ba-a665-71d418f0df18',
  {'text': ['76', 0],
   'widget_0': '',
   'widget_1': 1024,
   'widget_2': 1024,
   'widget_3': 'flux-2-klein-base-4b.safetensors',
   'widget_4': 'qwen_3_4b.safetensors',
   'widget_5': 'flux2-vae.safetensors'}),
 ('77',
  'a67caa28-5f85-4917-8396-36004960dd30',
  {'text': ['76', 0],
   'widget_0': '',
   'widget_1': 1024,
   'widget_2': 1024,
   'widget_3': 'flux-2-klein-4b.safetensors',
   'widget_4': 'qwen_3_4b.safetensors',
   'widget_5': 'flux2-vae.safetensors'}))

READY_METADATA = {'model_assets': [{'name': 'flux-2-klein-base-4b.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-base-4b.safetensors',
                   'subdir': 'diffusion_models'},
                  {'name': 'qwen_3_4b.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors',
                   'subdir': 'text_encoders'},
                  {'name': 'flux2-vae.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors',
                   'subdir': 'vae'},
                  {'name': 'flux-2-klein-4b.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-4b.safetensors',
                   'subdir': 'diffusion_models'}],
 'unbound_inputs': {'seed': 2734},
 'ready_template': 'image/flux2_klein_4b_t2i',
 'workflow_template': 'flux2_klein_4b_t2i',
 'capability': 'text_to_image',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/official/image/flux2_klein_4b_t2i.json',
 'coverage_tier': 'required',
 'approach': None,
 'runtime_note': None,
 'discord_signal': None}

READY_REQUIREMENTS = {'models': [{'name': 'flux-2-klein-base-4b.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-base-4b.safetensors',
             'subdir': 'diffusion_models'},
            {'name': 'qwen_3_4b.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors',
             'subdir': 'text_encoders'},
            {'name': 'flux2-vae.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors',
             'subdir': 'vae'},
            {'name': 'flux-2-klein-4b.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-4b.safetensors',
             'subdir': 'diffusion_models'}],
 'custom_nodes': []}


def build():
    workflow = build_authored_ready_workflow(
        NODES,
        READY_METADATA,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template"),
        requirements=READY_REQUIREMENTS,
        registered_inputs={'prompt': ('76', 'widget_0')},
    )
    return workflow
