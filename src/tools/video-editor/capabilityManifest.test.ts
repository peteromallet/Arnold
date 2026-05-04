import { describe, expect, it } from 'vitest';
import { VIDEO_EDITOR_CLIP_TYPE_CAPABILITY_MANIFEST } from './capabilityManifest';

describe('video editor capability manifest export', () => {
  it('exports a stable manifest constant for agent inspection', () => {
    expect(VIDEO_EDITOR_CLIP_TYPE_CAPABILITY_MANIFEST.version).toBe(1);
    expect(
      VIDEO_EDITOR_CLIP_TYPE_CAPABILITY_MANIFEST.clipTypes.some((entry) => entry.id === 'media'),
    ).toBe(true);
    expect(
      VIDEO_EDITOR_CLIP_TYPE_CAPABILITY_MANIFEST.clipTypes.some((entry) => entry.id === 'image-jump'),
    ).toBe(true);
    expect(
      VIDEO_EDITOR_CLIP_TYPE_CAPABILITY_MANIFEST.clipTypes.some((entry) => entry.id === 'title-card'),
    ).toBe(true);
  });
});
