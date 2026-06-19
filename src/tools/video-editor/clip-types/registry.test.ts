import { describe, expect, it } from 'vitest';

import {
  TRUSTED_CLIP_TYPE_METADATA,
  TRUSTED_CLIP_TYPES,
  createAvailableClipTypeRegistry,
  filterTrustedClipTypeRegistrationsForRegistry,
  getTrustedSequenceParamDefinitions,
  resolveDynamicClipType,
  resolveDynamicClipTypeDescriptor,
  resolveTrustedClipTypeRegistration,
  type DynamicExtensionClipRecord,
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

// ---------------------------------------------------------------------------
// M9 T6: Dynamic-aware clip descriptor resolution
// ---------------------------------------------------------------------------

const BUILTIN_SET = new Set(['media', 'hold', 'text', 'effect-layer']);

function makeExtensionRecord(
  clipTypeId: string,
  ownerExtensionId?: string,
): DynamicExtensionClipRecord {
  return { clipTypeId, ownerExtensionId, renderer: {} };
}

describe('resolveDynamicClipType — merges builtins, trusted sequences, and extension records', () => {
  it('resolves built-in clip types with highest precedence', () => {
    const result = resolveDynamicClipType('media', BUILTIN_SET, undefined);
    expect(result).toEqual({ status: 'available', clipType: 'media', source: 'builtin' });

    const result2 = resolveDynamicClipType('hold', BUILTIN_SET, [makeExtensionRecord('hold', 'ext.a')]);
    // Built-in wins even when an extension also claims the ID
    expect(result2).toEqual({ status: 'available', clipType: 'hold', source: 'builtin' });
  });

  it('resolves trusted-sequence clip types when no extension conflicts', () => {
    const result = resolveDynamicClipType('resource-card', BUILTIN_SET, undefined);
    expect(result).toMatchObject({
      status: 'available',
      clipType: 'resource-card',
      source: 'trusted-sequence',
    });
    expect(result).toHaveProperty('descriptor');
    expect(result).toHaveProperty('metadata');
  });

  it('detects duplicates when an extension claims a trusted-sequence clipTypeId', () => {
    const result = resolveDynamicClipType('cta-card', BUILTIN_SET, [
      makeExtensionRecord('cta-card', 'evil.ext'),
    ]);
    expect(result).toMatchObject({
      status: 'duplicate',
      clipType: 'cta-card',
      source: 'trusted-sequence',
      duplicateExtensionIds: ['evil.ext'],
    });
  });

  it('lists multiple duplicate extension IDs when several extensions claim the same trusted type', () => {
    const result = resolveDynamicClipType('title-card', BUILTIN_SET, [
      makeExtensionRecord('title-card', 'ext.one'),
      makeExtensionRecord('title-card', 'ext.two'),
    ]);
    expect(result.status).toBe('duplicate');
    if (result.status === 'duplicate') {
      expect(result.duplicateExtensionIds).toEqual(['ext.one', 'ext.two']);
    }
  });

  it('resolves extension-only clip types as available', () => {
    const result = resolveDynamicClipType('my-custom-type', BUILTIN_SET, [
      makeExtensionRecord('my-custom-type', 'custom.ext'),
    ]);
    expect(result).toMatchObject({
      status: 'available',
      clipType: 'my-custom-type',
      source: 'extension',
    });
  });

  it('returns unknown for clip types not in any source', () => {
    expect(resolveDynamicClipType('nope', BUILTIN_SET, undefined)).toEqual({
      status: 'unknown',
      clipType: 'nope',
    });
    expect(resolveDynamicClipType('nope', BUILTIN_SET, [])).toEqual({
      status: 'unknown',
      clipType: 'nope',
    });
  });

  it('returns unknown for undefined clipType', () => {
    expect(resolveDynamicClipType(undefined, BUILTIN_SET, undefined)).toEqual({
      status: 'unknown',
      clipType: undefined,
    });
  });

  it('deterministic precedence: builtin > trusted > extension', () => {
    // 'text' is builtin and should win even if extension also claims it
    const result = resolveDynamicClipType('text', BUILTIN_SET, [
      makeExtensionRecord('text', 'bad.ext'),
    ]);
    expect(result.status).toBe('available');
    expect(result.source).toBe('builtin');

    // 'cta-card' is trusted with extension conflict → duplicate
    const result2 = resolveDynamicClipType('cta-card', BUILTIN_SET, [
      makeExtensionRecord('cta-card', 'bad.ext'),
    ]);
    expect(result2.status).toBe('duplicate');

    // 'image-jump' is trusted without extension conflict → available
    const result3 = resolveDynamicClipType('image-jump', BUILTIN_SET, undefined);
    expect(result3.status).toBe('available');
    expect(result3.source).toBe('trusted-sequence');
  });

  it('extension records matching a clip type return the first record', () => {
    const result = resolveDynamicClipType('ext-only', BUILTIN_SET, [
      makeExtensionRecord('ext-only', 'first.ext'),
      makeExtensionRecord('ext-only', 'second.ext'),
    ]);
    expect(result.status).toBe('available');
    if (result.status === 'available' && result.source === 'extension') {
      expect(result.extensionRecord?.ownerExtensionId).toBe('first.ext');
    }
  });
});

describe('resolveDynamicClipTypeDescriptor — descriptor lookup for dynamic resolution', () => {
  it('returns the trusted sequence descriptor for trusted clip types', () => {
    const descriptor = resolveDynamicClipTypeDescriptor('resource-card', BUILTIN_SET, undefined);
    expect(descriptor).toBeDefined();
    expect(descriptor?.id).toBe('resource-card');
  });

  it('returns undefined for built-ins (caller must use getBuiltinClipTypeDescriptor)', () => {
    const descriptor = resolveDynamicClipTypeDescriptor('media', BUILTIN_SET, undefined);
    expect(descriptor).toBeUndefined();
  });

  it('returns undefined for extension-only types', () => {
    const descriptor = resolveDynamicClipTypeDescriptor('my-custom-type', BUILTIN_SET, [
      makeExtensionRecord('my-custom-type', 'custom.ext'),
    ]);
    expect(descriptor).toBeUndefined();
  });

  it('returns undefined for unknown types', () => {
    expect(resolveDynamicClipTypeDescriptor('nope', BUILTIN_SET, undefined)).toBeUndefined();
    expect(resolveDynamicClipTypeDescriptor(undefined, BUILTIN_SET, undefined)).toBeUndefined();
  });
});
