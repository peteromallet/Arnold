import { describe, expect, it } from 'vitest';
import {
  createClipMetaFromDescriptor,
  createEditorClipTypeRegistry,
  getClipTypeOverlayBehavior,
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
