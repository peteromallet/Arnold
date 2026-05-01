import { describe, expect, it } from 'vitest';
import { serializeForDisk } from '@/tools/video-editor/lib/serialize';
import { materializeResolvedSequenceConfig } from '@/tools/video-editor/sequences/materialize';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types';

const buildConfig = (): ResolvedTimelineConfig => ({
  output: {
    resolution: '1920x1080',
    fps: 30,
    file: 'out.mp4',
  },
  tracks: [
    {
      id: 'V1',
      kind: 'visual',
      label: 'V1',
    },
  ],
  clips: [
    {
      id: 'clip-sequence',
      clipType: 'resource-card',
      track: 'V1',
      at: 0,
      hold: 3,
      params: {
        title: 'Leverage',
        previewAssetKeys: ['asset-a', 'asset-b'],
      },
    },
  ],
  registry: {
    'asset-a': {
      file: 'asset-a.png',
      src: 'https://cdn.example.com/asset-a.png',
      type: 'image',
    },
    'asset-b': {
      file: 'asset-b.png',
      src: 'https://cdn.example.com/asset-b.png',
      type: 'image',
    },
  },
});

describe('sequence asset materialization', () => {
  it('adds component-facing URL params from registry asset keys without mutating persisted params', () => {
    const config = buildConfig();
    const materialized = materializeResolvedSequenceConfig(config);

    expect(materialized).not.toBe(config);
    expect(materialized.clips[0]).not.toBe(config.clips[0]);
    expect(materialized.clips[0].params).toMatchObject({
      previewAssetKeys: ['asset-a', 'asset-b'],
      previews: [
        'https://cdn.example.com/asset-a.png',
        'https://cdn.example.com/asset-b.png',
      ],
    });
    expect(config.clips[0].params).toEqual({
      title: 'Leverage',
      previewAssetKeys: ['asset-a', 'asset-b'],
    });

    const persisted = serializeForDisk(config);
    expect(persisted.clips[0].params).toEqual({
      title: 'Leverage',
      previewAssetKeys: ['asset-a', 'asset-b'],
    });
  });

  it('leaves non-sequence or non-asset sequence params untouched by reference', () => {
    const config: ResolvedTimelineConfig = {
      ...buildConfig(),
      clips: [
        {
          id: 'clip-section',
          clipType: 'section-hook',
          track: 'V1',
          at: 0,
          hold: 3,
          params: { title: 'No assets here' },
        },
      ],
    };

    expect(materializeResolvedSequenceConfig(config)).toBe(config);
  });
});
