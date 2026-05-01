import { describe, expect, it } from 'vitest';
import {
  TRUSTED_SEQUENCE_CLIP_TYPES,
  TRUSTED_SEQUENCE_METADATA,
  getTrustedSequenceMetadata,
} from '@/tools/video-editor/sequences/metadata';
import {
  AVAILABLE_SEQUENCE_CLIP_TYPES,
  AVAILABLE_SEQUENCE_METADATA,
  filterTrustedSequenceMetadataForRegistry,
  isAvailableSequenceClipType,
} from '@/tools/video-editor/sequences/registry';

describe('trusted sequence metadata', () => {
  it('defines the trusted 2rp v1 clip set only', () => {
    expect([...TRUSTED_SEQUENCE_CLIP_TYPES].sort()).toEqual([
      'art-card',
      'cta-card',
      'resource-card',
      'section-hook',
    ]);
    expect(TRUSTED_SEQUENCE_METADATA.every((metadata) => metadata.themeId === '2rp')).toBe(true);
  });

  it('keeps timing as top-level hold metadata instead of an editable param', () => {
    for (const metadata of TRUSTED_SEQUENCE_METADATA) {
      expect(metadata.hold.defaultSeconds).toBeGreaterThan(0);
      expect(metadata.hold.minSeconds).toBeGreaterThan(0);
      expect(metadata.hold.maxSeconds).toBeGreaterThanOrEqual(metadata.hold.defaultSeconds);
      expect(metadata.params.map((param) => param.key)).not.toContain('hold');
    }
  });

  it('does not expose entrance or exit animation refs as editable params', () => {
    for (const metadata of TRUSTED_SEQUENCE_METADATA) {
      const paramKeys = metadata.params.map((param) => param.key);
      expect(paramKeys).not.toContain('entrance');
      expect(paramKeys).not.toContain('exit');
    }
  });

  it('uses previewAssetKeys as the resource-card asset-list field', () => {
    const resourceCard = getTrustedSequenceMetadata('resource-card');
    expect(resourceCard).toBeDefined();
    const previewField = resourceCard!.params.find((param) => param.key === 'previewAssetKeys');
    expect(previewField).toMatchObject({
      kind: 'asset-list',
      maxItems: 3,
      componentParam: 'previews',
    });
  });
});

describe('available sequence metadata', () => {
  it('exposes only trusted sequences that exist in the generated theme package registry', () => {
    expect([...AVAILABLE_SEQUENCE_CLIP_TYPES].sort()).toEqual([
      'art-card',
      'cta-card',
      'resource-card',
      'section-hook',
    ]);
    expect(AVAILABLE_SEQUENCE_METADATA).toHaveLength(4);
    expect(isAvailableSequenceClipType('section-hook')).toBe(true);
    expect(isAvailableSequenceClipType('theme-package-not-yet-trusted')).toBe(false);
  });

  it('filters trusted metadata against a provided frontend registry shape', () => {
    const filtered = filterTrustedSequenceMetadataForRegistry({
      'section-hook': {},
      'resource-card': {},
    });

    expect(filtered.map((metadata) => metadata.clipType).sort()).toEqual([
      'resource-card',
      'section-hook',
    ]);
  });
});
