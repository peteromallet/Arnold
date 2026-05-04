import { createVideoEditorClipTypeCapabilityManifest } from '@/tools/video-editor/clip-types/manifest';
import { SEQUENCE_COMPONENT_REGISTRY } from '@/tools/video-editor/sequences/registry';

export const VIDEO_EDITOR_CLIP_TYPE_CAPABILITY_MANIFEST = createVideoEditorClipTypeCapabilityManifest(
  SEQUENCE_COMPONENT_REGISTRY,
);
