import { describe, expect, it } from 'vitest';
import { buildAssetDropEdit } from '@/tools/video-editor/hooks/useAssetManagement';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data';

const createTimelineData = (assetType: string, file: string): TimelineData => ({
  config: {
    output: { width: 1280, height: 720, fps: 30 },
    tracks: [{ id: 'V1', kind: 'visual' }],
    clips: [],
    registry: {
      assets: {
        asset1: { src: file, file, type: assetType, duration: 4 },
      },
    },
  },
  configVersion: 1,
  registry: {
    assets: {
      asset1: { src: file, file, type: assetType, duration: 4 },
    },
  },
  resolvedConfig: {
    output: { width: 1280, height: 720, fps: 30 },
    tracks: [{ id: 'V1', kind: 'visual' }],
    clips: [],
    registry: {
      asset1: { src: file, file, type: assetType, duration: 4 },
    },
  },
  rows: [{ id: 'V1', actions: [] }],
  meta: {},
  effects: {},
  assetMap: {},
  output: { width: 1280, height: 720, fps: 30 },
  tracks: [{ id: 'V1', kind: 'visual' }],
  clipOrder: { V1: [] },
  signature: 'sig',
  stableSignature: 'stable',
});

describe('buildAssetDropEdit media kind validation', () => {
  it('rejects text assets instead of adding them as visual video clips', () => {
    const edit = buildAssetDropEdit({
      current: createTimelineData('text/plain', 'https://example.com/script.txt'),
      assetKey: 'asset1',
      trackId: 'V1',
      time: 0,
    });

    expect(edit).toBeNull();
  });

  it('allows normal video assets on visual tracks', () => {
    const edit = buildAssetDropEdit({
      current: createTimelineData('video/mp4', 'https://example.com/clip.mp4'),
      assetKey: 'asset1',
      trackId: 'V1',
      time: 2,
    });

    expect(edit?.metaUpdates[edit.clipId]).toMatchObject({
      asset: 'asset1',
      track: 'V1',
      clipType: 'media',
      from: 0,
      to: 4,
    });
  });
});
