import { createVideoEditorClipTypeCapabilityManifest } from '@/tools/video-editor/clip-types/manifest.ts';
import { SEQUENCE_COMPONENT_REGISTRY } from '@/tools/video-editor/sequences/registry.ts';

export const VIDEO_EDITOR_CLIP_TYPE_CAPABILITY_MANIFEST = createVideoEditorClipTypeCapabilityManifest(
  SEQUENCE_COMPONENT_REGISTRY,
);
