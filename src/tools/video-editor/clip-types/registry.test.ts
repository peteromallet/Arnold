import { describe, expect, it } from 'vitest';

import {
  TRUSTED_CLIP_TYPE_METADATA,
  TRUSTED_CLIP_TYPES,
  createAvailableClipTypeRegistry,
  filterTrustedClipTypeRegistrationsForRegistry,
  getTrustedSequenceParamDefinitions,
  resolveTrustedClipTypeRegistration,
} from '@/tools/video-editor/clip-types/registry';

describe('clip-type registry', () => {
  it('exposes explicit trusted and available clip-type views', () => {
    const availableView = createAvailableClipTypeRegistry({
      'section-hook': { component: () => null },
      'resource-card': { component: () => null },
      'image-jump': { component: () => null },
      'title-card': { component: () => null },
    });

    expect([...TRUSTED_CLIP_TYPES].sort()).toEqual([
      'art-card',
      'cta-card',
      'image-jump',
      'resource-card',
      'section-hook',
      'title-card',
    ]);
    expect([...availableView.clipTypes].sort()).toEqual([
      'image-jump',
      'resource-card',
      'section-hook',
      'title-card',
    ]);
    expect(TRUSTED_CLIP_TYPE_METADATA).toHaveLength(6);
    expect(availableView.metadata).toHaveLength(4);
  });

  it('filters trusted clip types against a provided available registry shape', () => {
    const filtered = filterTrustedClipTypeRegistrationsForRegistry({
      'section-hook': { component: () => null },
      'resource-card': { component: () => null },
    });

    expect(filtered.map((registration) => registration.id).sort()).toEqual([
      'resource-card',
      'section-hook',
    ]);
  });

  it('surfaces available, unavailable, and unknown clip-type resolutions loudly', () => {
    const availableView = createAvailableClipTypeRegistry({
      'resource-card': { component: () => null },
      'image-jump': { component: () => null },
      'title-card': { component: () => null },
    });

    expect(resolveTrustedClipTypeRegistration('cta-card')).toMatchObject({
      status: 'trusted',
      registration: { id: 'cta-card' },
    });
    expect(resolveTrustedClipTypeRegistration('missing-type')).toEqual({
      status: 'unknown',
      clipType: 'missing-type',
    });

    expect(availableView.resolveAvailableClipTypeRegistration('resource-card')).toMatchObject({
      status: 'available',
      registration: { id: 'resource-card' },
    });
    expect(availableView.resolveAvailableClipTypeRegistration('title-card')).toMatchObject({
      status: 'available',
      registration: { id: 'title-card' },
    });
    expect(availableView.resolveAvailableClipTypeRegistration('cta-card')).toMatchObject({
      status: 'unavailable',
      registration: { id: 'cta-card' },
    });
    expect(availableView.resolveAvailableClipTypeRegistration('missing-type')).toEqual({
      status: 'unknown',
      clipType: 'missing-type',
    });
  });

  it('serves trusted param selectors through the registry without bypassing metadata tables', () => {
    expect(getTrustedSequenceParamDefinitions('resource-card')).toContainEqual(
      expect.objectContaining({
        key: 'previewAssetKeys',
        kind: 'asset-list',
        componentParam: 'previews',
      }),
    );
    expect(getTrustedSequenceParamDefinitions('missing-type')).toEqual([]);
  });
});
