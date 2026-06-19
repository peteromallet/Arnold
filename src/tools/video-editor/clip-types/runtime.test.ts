import { describe, expect, it } from 'vitest';
import {
  buildExtensionClipTypeDescriptorMap,
  createClipMetaFromDescriptor,
  createEditorClipTypeRegistry,
  defineClipTypeFromExtensionRecord,
  getClipTypeOverlayBehavior,
  getExtensionClipTypeDescriptor,
  getRegisteredClipTypeDescriptor,
  isClipTypeCommandAvailable,
} from '@/tools/video-editor/clip-types/runtime';

describe('clip-type runtime registry', () => {
  it('resolves builtin, available sequence, unavailable sequence, and unknown clip types distinctly', () => {
    const view = createEditorClipTypeRegistry({
      'resource-card': { component: () => null },
      'title-card': { component: () => null },
    });

    expect(view.resolveRegistration('media')).toMatchObject({
      status: 'available',
      registration: { id: 'media', source: 'builtin' },
    });
    expect(view.resolveRegistration('resource-card')).toMatchObject({
      status: 'available',
      registration: { id: 'resource-card', source: 'sequence' },
    });
    expect(view.resolveRegistration('title-card')).toMatchObject({
      status: 'available',
      registration: { id: 'title-card', source: 'sequence' },
    });
    expect(view.resolveRegistration('cta-card')).toMatchObject({
      status: 'unavailable',
      registration: { id: 'cta-card', source: 'sequence' },
    });
    expect(view.resolveRegistration('missing-type')).toEqual({
      status: 'unknown',
      clipType: 'missing-type',
    });
  });

  it('detects duplicates when extension records claim the same clipTypeId as trusted sequences', () => {
    const view = createEditorClipTypeRegistry(
      { 'cta-card': { component: () => null } },
      [{ clipTypeId: 'cta-card', ownerExtensionId: 'evil.ext' }],
    );

    const result = view.resolveRegistration('cta-card');
    expect(result.status).toBe('duplicate');
    if (result.status === 'duplicate') {
      expect(result.registration.id).toBe('cta-card');
      expect(result.duplicateExtensionIds).toEqual(['evil.ext']);
    }
  });

  it('returns unknown for extension-only clip types (no built-in or trusted descriptor)', () => {
    const view = createEditorClipTypeRegistry(
      {},
      [{ clipTypeId: 'ext-only-type', ownerExtensionId: 'my.ext' }],
    );

    // Extension-only types don't have ClipTypeDescriptors, so resolveRegistration
    // returns 'unknown' from this legacy path. Consumers should use
    // resolveDynamicClipType or ClipTypeRegistry directly.
    expect(view.resolveRegistration('ext-only-type')).toEqual({
      status: 'unknown',
      clipType: 'ext-only-type',
    });
  });

  it('handles empty extension records gracefully', () => {
    const view = createEditorClipTypeRegistry(
      { 'resource-card': { component: () => null } },
      [],
    );

    expect(view.resolveRegistration('resource-card').status).toBe('available');
    expect(view.resolveRegistration('cta-card').status).toBe('unavailable');
    expect(view.resolveRegistration('missing-type').status).toBe('unknown');
  });

  it('builds descriptor-backed clip meta without injecting extra persisted sequence params', () => {
    const clipMeta = createClipMetaFromDescriptor({
      clipType: 'title-card',
      trackId: 'V1',
      clipOverrides: {
        hold: 4,
      },
      params: {
        title: 'Registry title',
      },
    });

    expect(clipMeta).toEqual({
      track: 'V1',
      clipType: 'title-card',
      hold: 4,
      params: {
        title: 'Registry title',
      },
    });
  });

  it('evaluates command legality from instance facts instead of flat clip-type checks', () => {
    const mediaDescriptor = getRegisteredClipTypeDescriptor('media');
    const holdDescriptor = getRegisteredClipTypeDescriptor('hold');

    expect(isClipTypeCommandAvailable(mediaDescriptor, 'detach-audio', {
      clip: {
        id: 'clip-video',
        track: 'V1',
        at: 0,
        clipType: 'media',
        assetEntry: {
          file: 'clip.mp4',
          src: 'https://cdn.example.test/clip.mp4',
          type: 'video/mp4',
        },
      },
      track: { id: 'V1', kind: 'visual', label: 'V1' },
      selectedClipIds: ['clip-video'],
    })).toBe(true);

    expect(isClipTypeCommandAvailable(mediaDescriptor, 'detach-audio', {
      clip: {
        id: 'clip-image',
        track: 'V1',
        at: 0,
        clipType: 'hold',
        assetEntry: {
          file: 'still.png',
          src: 'https://cdn.example.test/still.png',
          type: 'image/png',
        },
      },
      track: { id: 'V1', kind: 'visual', label: 'V1' },
      selectedClipIds: ['clip-image'],
    })).toBe(false);

    expect(isClipTypeCommandAvailable(mediaDescriptor, 'toggle-mute', {
      clip: {
        id: 'clip-audio',
        track: 'A1',
        at: 0,
        clipType: 'media',
        assetEntry: {
          file: 'voice.wav',
          src: 'https://cdn.example.test/voice.wav',
          type: 'audio/wav',
        },
      },
      track: { id: 'A1', kind: 'audio', label: 'A1' },
      selectedClipIds: ['clip-audio'],
    })).toBe(true);

    expect(isClipTypeCommandAvailable(holdDescriptor, 'toggle-mute', {
      clip: {
        id: 'clip-hold',
        track: 'V1',
        at: 0,
        clipType: 'hold',
      },
      track: { id: 'V1', kind: 'visual', label: 'V1' },
      selectedClipIds: ['clip-hold'],
    })).toBe(false);
  });

  it('derives overlay, crop, inline-edit, and lightbox behavior from clip descriptors', () => {
    expect(getClipTypeOverlayBehavior(getRegisteredClipTypeDescriptor('media'))).toMatchObject({
      excluded: false,
      allowsBoundsEditing: true,
      allowsCrop: true,
      supportsInlineTextEdit: false,
      doubleClickAction: 'lightbox',
      lightboxEnabled: true,
      defaultBounds: null,
    });

    expect(getClipTypeOverlayBehavior(getRegisteredClipTypeDescriptor('text'))).toMatchObject({
      excluded: false,
      allowsBoundsEditing: true,
      allowsCrop: false,
      supportsInlineTextEdit: true,
      doubleClickAction: 'inline-text-edit',
      lightboxEnabled: false,
      defaultBounds: {
        x: 120,
        y: 120,
        width: 640,
        height: 180,
      },
    });

    expect(getClipTypeOverlayBehavior(getRegisteredClipTypeDescriptor('effect-layer'))).toMatchObject({
      excluded: true,
      allowsBoundsEditing: false,
      allowsCrop: false,
      supportsInlineTextEdit: false,
      doubleClickAction: 'none',
      lightboxEnabled: false,
    });
  });
});

// ---------------------------------------------------------------------------
// M9 T7: Extension clip type descriptor synthesis
// ---------------------------------------------------------------------------

describe('defineClipTypeFromExtensionRecord', () => {
  it('synthesizes a ClipTypeDescriptor from extension schema with defaults', () => {
    const descriptor = defineClipTypeFromExtensionRecord('my-ext-clip', [
      {
        name: 'speed',
        label: 'Speed',
        description: 'Animation speed multiplier',
        type: 'number',
        default: 1.5,
        min: 0.1,
        max: 10,
        step: 0.1,
      },
      {
        name: 'style',
        label: 'Style',
        description: 'Visual style',
        type: 'select',
        default: 'modern',
        options: [
          { label: 'Modern', value: 'modern' },
          { label: 'Classic', value: 'classic' },
        ],
      },
    ]);

    expect(descriptor.id).toBe('my-ext-clip');
    expect(descriptor.label).toBe('my-ext-clip');
    expect(descriptor.hold).toMatchObject({
      kind: 'required',
      defaultSeconds: 4,
      minSeconds: 0.05,
      maxSeconds: 120,
    });
    expect(descriptor.paramsSchema.kind).toBe('sequence');
    expect(descriptor.paramsSchema.params).toHaveLength(2);
    expect(descriptor.paramsSchema.params[0]).toMatchObject({
      key: 'speed',
      label: 'Speed',
      kind: 'string',
      options: undefined,
    });
    expect(descriptor.paramsSchema.params[1]).toMatchObject({
      key: 'style',
      label: 'Style',
      kind: 'string',
      options: ['modern', 'classic'],
    });
    expect(descriptor.defaults.params).toMatchObject({
      speed: 1.5,
      style: 'modern',
    });
  });

  it('handles empty schema gracefully', () => {
    const descriptor = defineClipTypeFromExtensionRecord('bare-clip', undefined);
    expect(descriptor.id).toBe('bare-clip');
    expect(descriptor.paramsSchema.params).toHaveLength(0);
    expect(descriptor.defaults.params).toEqual({});
  });

  it('skips undefined defaults in schema', () => {
    const descriptor = defineClipTypeFromExtensionRecord('partial-clip', [
      {
        name: 'opacity',
        label: 'Opacity',
        description: 'Element opacity',
        type: 'number',
        // no default
      },
    ]);
    expect(descriptor.defaults.params).toEqual({});
    expect(descriptor.paramsSchema.params[0]).toMatchObject({ key: 'opacity' });
  });
});

describe('getExtensionClipTypeDescriptor', () => {
  const records = [
    { clipTypeId: 'ext-a', schema: [{ name: 'x', label: 'X', description: '', type: 'number' as const }] },
    { clipTypeId: 'ext-b', schema: [{ name: 'y', label: 'Y', description: '', type: 'boolean' as const, default: true }] },
  ];

  it('resolves a matching extension record', () => {
    const descriptor = getExtensionClipTypeDescriptor('ext-a', records);
    expect(descriptor).toBeDefined();
    expect(descriptor?.id).toBe('ext-a');
  });

  it('returns undefined for non-matching clipType', () => {
    expect(getExtensionClipTypeDescriptor('missing', records)).toBeUndefined();
  });
});

describe('buildExtensionClipTypeDescriptorMap', () => {
  it('builds a map from clipTypeId to descriptor', () => {
    const records = [
      { clipTypeId: 'ext-1', schema: [{ name: 'a', label: 'A', description: '', type: 'number' as const }] },
      { clipTypeId: 'ext-2', schema: [{ name: 'b', label: 'B', description: '', type: 'boolean' as const }] },
    ];
    const map = buildExtensionClipTypeDescriptorMap(records);
    expect(map.size).toBe(2);
    expect(map.get('ext-1')?.id).toBe('ext-1');
    expect(map.get('ext-2')?.id).toBe('ext-2');
  });

  it('deduplicates by clipTypeId', () => {
    const records = [
      { clipTypeId: 'dup', schema: [{ name: 'first', label: 'First', description: '', type: 'number' as const }] },
      { clipTypeId: 'dup', schema: [{ name: 'second', label: 'Second', description: '', type: 'boolean' as const }] },
    ];
    const map = buildExtensionClipTypeDescriptorMap(records);
    expect(map.size).toBe(1);
    // First wins
    expect(map.get('dup')?.paramsSchema.params[0]?.key).toBe('first');
  });

  it('returns empty map for empty records', () => {
    expect(buildExtensionClipTypeDescriptorMap([]).size).toBe(0);
  });
});

describe('getRegisteredClipTypeDescriptor with extension records', () => {
  const extRecords = [
    { clipTypeId: 'my-extension', schema: [{ name: 'param1', label: 'P1', description: '', type: 'number' as const, default: 42 }] },
  ];

  it('falls back to extension descriptor when built-in and trusted both miss', () => {
    const descriptor = getRegisteredClipTypeDescriptor('my-extension', extRecords);
    expect(descriptor).toBeDefined();
    expect(descriptor?.id).toBe('my-extension');
  });

  it('prefers built-in over extension', () => {
    const descriptor = getRegisteredClipTypeDescriptor('media', extRecords);
    expect(descriptor?.id).toBe('media');
  });

  it('prefers trusted sequence over extension', () => {
    // 'resource-card' is a trusted sequence type
    const descriptor = getRegisteredClipTypeDescriptor('resource-card', [
      { clipTypeId: 'resource-card', schema: [] },
    ]);
    expect(descriptor?.id).toBe('resource-card');
  });

  it('returns undefined for unknown clipType without records', () => {
    expect(getRegisteredClipTypeDescriptor('nope')).toBeUndefined();
  });
});

describe('createClipMetaFromDescriptor with extension records', () => {
  const extRecords = [
    {
      clipTypeId: 'pulse-clip',
      schema: [
        { name: 'intensity', label: 'Intensity', description: '', type: 'number' as const, default: 0.8 },
      ],
    },
  ];

  it('creates meta for extension clip types using their schema defaults', () => {
    const meta = createClipMetaFromDescriptor({
      clipType: 'pulse-clip',
      trackId: 'V1',
      extensionRecords: extRecords,
      useDescriptorParamDefaults: true,
    });
    expect(meta).not.toBeNull();
    expect(meta?.clipType).toBe('pulse-clip');
    expect(meta?.track).toBe('V1');
    expect((meta as Record<string, unknown>)?.params).toMatchObject({ intensity: 0.8 });
  });

  it('returns null for unknown clip type even with extension records', () => {
    expect(createClipMetaFromDescriptor({
      clipType: 'nope',
      trackId: 'V1',
      extensionRecords: extRecords,
    })).toBeNull();
  });

  it('overrides extension defaults with explicit params', () => {
    const meta = createClipMetaFromDescriptor({
      clipType: 'pulse-clip',
      trackId: 'V2',
      params: { intensity: 2.0, extra: 'custom' },
      extensionRecords: extRecords,
    });
    expect(meta).not.toBeNull();
    expect((meta as Record<string, unknown>)?.params).toMatchObject({
      intensity: 2.0,
      extra: 'custom',
    });
  });
});
