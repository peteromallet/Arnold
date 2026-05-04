import { describe, expect, it } from 'vitest';
import type { AssetRegistry, TimelineConfig } from '@/tools/video-editor/index.ts';
import { createDefaultTimelineConfig } from '@/tools/video-editor/testing.ts';
import {
  applySequenceDraftToTimeline,
  materializeSequenceConfig,
  TRUSTED_SEQUENCE_CLIP_TYPES,
  validateSequenceDraft,
} from '@/tools/video-editor/sequence.ts';

const registry: AssetRegistry = {
  assets: {
    'asset-a': {
      file: 'asset-a.png',
      src: 'https://cdn.example.test/asset-a.png',
      type: 'image/png',
    },
    'asset-b': {
      file: 'asset-b.png',
      src: 'https://cdn.example.test/asset-b.png',
      type: 'image/png',
    },
  },
};

describe('public sequence SDK', () => {
  it('exports the trusted clip allowlist and validates trusted drafts', () => {
    expect([...TRUSTED_SEQUENCE_CLIP_TYPES].sort()).toEqual([
      'art-card',
      'cta-card',
      'image-jump',
      'resource-card',
      'section-hook',
      'title-card',
    ]);

    const result = validateSequenceDraft({
      clipType: 'image-jump',
      hold: 4,
      params: {
        imageAssetKeys: ['asset-a', 'asset-b'],
        mode: 'jump',
      },
    }, { allowedAssetKeys: ['asset-a', 'asset-b'] });

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.draft.clipType).toBe('image-jump');
  });

  it('materializes asset-backed params without mutating persisted asset-key params', () => {
    const config: TimelineConfig = {
      ...createDefaultTimelineConfig(),
      clips: [
        {
          id: 'clip-sequence',
          track: 'V1',
          at: 0,
          clipType: 'resource-card',
          hold: 3,
          params: {
            title: 'Resources',
            previewAssetKeys: ['asset-a'],
          },
        },
      ],
      theme: '2rp',
    };

    const materialized = materializeSequenceConfig({
      ...config,
      registry: registry.assets,
    });

    expect(materialized.clips[0].params).toMatchObject({
      title: 'Resources',
      previewAssetKeys: ['asset-a'],
      previews: ['https://cdn.example.test/asset-a.png'],
    });
    expect(config.clips[0].params).toEqual({
      title: 'Resources',
      previewAssetKeys: ['asset-a'],
    });
  });

  it('applies a validated sequence draft onto a plain timeline config without internal helpers', async () => {
    const validation = validateSequenceDraft({
      clipType: 'section-hook',
      hold: 3,
      params: {
        title: 'A new renaissance',
      },
    });
    expect(validation.ok).toBe(true);
    if (!validation.ok) return;

    const config: TimelineConfig = {
      ...createDefaultTimelineConfig(),
      theme: '2rp',
      theme_overrides: {
        visual: {
          color: {
            accent: '#00ff88',
          },
        },
      },
    };

    const result = await applySequenceDraftToTimeline(
      config,
      { assets: {} },
      validation.draft,
      {
        at: 2,
        selectedTrackId: 'V1',
      },
    );

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.selectedTrackId).toBe('V1');
    expect(result.config.theme).toBe('2rp');
    expect(result.config.theme_overrides).toEqual(config.theme_overrides);
    expect(result.config.clips).toHaveLength(1);
    expect(result.config.clips[0]).toMatchObject({
      id: result.clipId,
      track: 'V1',
      at: 2,
      clipType: 'section-hook',
      hold: 3,
      params: {
        title: 'A new renaissance',
      },
    });
  });

  it('replaces selected visual clips through the public config-level helper', async () => {
    const validation = validateSequenceDraft({
      clipType: 'resource-card',
      hold: 3,
      params: {
        title: 'Creator leverage',
        previewAssetKeys: ['asset-a'],
      },
    }, { allowedAssetKeys: ['asset-a'] });
    expect(validation.ok).toBe(true);
    if (!validation.ok) return;

    const config: TimelineConfig = {
      ...createDefaultTimelineConfig(),
      clips: [
        {
          id: 'clip-1',
          track: 'V1',
          at: 1,
          clipType: 'media',
          hold: 2,
          asset: 'asset-a',
        },
        {
          id: 'clip-2',
          track: 'V1',
          at: 4,
          clipType: 'media',
          hold: 2,
          asset: 'asset-b',
        },
      ],
      theme: '2rp',
    };

    const result = await applySequenceDraftToTimeline(
      config,
      registry,
      validation.draft,
      {
        mode: 'replace',
        selectedClipId: 'clip-2',
        selectedClipIds: ['clip-1', 'clip-2'],
      },
    );

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.config.clips).toHaveLength(1);
    expect(result.config.clips[0]).toMatchObject({
      id: result.clipId,
      track: 'V1',
      at: 1,
      clipType: 'resource-card',
      hold: 3,
      params: {
        title: 'Creator leverage',
        previewAssetKeys: ['asset-a'],
      },
    });
  });
});
