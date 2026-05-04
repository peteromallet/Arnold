import { describe, expect, it } from 'vitest';
import {
  InMemoryDataProvider,
  createLocalAssetResolver,
} from '@/tools/video-editor/lib/browser-runtime';
import {
  TimelineNotFoundError,
  TimelineVersionConflictError,
  type TimelineConfig,
} from '@/tools/video-editor';

function buildConfig(): TimelineConfig {
  return {
    output: {
      resolution: '1920x1080',
      fps: 30,
      file: 'timeline.mp4',
    },
    tracks: [
      { id: 'V1', kind: 'visual', label: 'V1' },
    ],
    clips: [],
  };
}

describe('InMemoryDataProvider', () => {
  it('loads, saves, checkpoints, and registers assets with optimistic versioning', async () => {
    const provider = new InMemoryDataProvider({
      timelines: {
        'timeline-1': {
          config: buildConfig(),
          registry: { assets: {} },
        },
      },
    });

    const initial = await provider.loadTimeline('timeline-1');
    expect(initial.configVersion).toBe(1);

    const nextVersion = await provider.saveTimeline('timeline-1', {
      ...initial.config,
      clips: [{
        id: 'clip-1',
        clipType: 'media',
        track: 'V1',
        at: 0,
        hold: 5,
      }],
    }, initial.configVersion, { assets: {} });
    expect(nextVersion).toBe(2);

    const checkpointId = await provider.saveCheckpoint?.('timeline-1', {
      timelineId: 'timeline-1',
      config: initial.config,
      createdAt: new Date('2026-05-04T00:00:00.000Z').toISOString(),
      triggerType: 'manual',
      label: 'Manual checkpoint',
      editsSinceLastCheckpoint: 1,
    });
    expect(checkpointId).toBeTruthy();
    expect(await provider.loadCheckpoints?.('timeline-1')).toHaveLength(1);

    await provider.registerAsset?.('timeline-1', 'asset-1', {
      file: 'clips/demo.mp4',
      type: 'video/mp4',
      duration: 4,
    });

    const registry = await provider.loadAssetRegistry('timeline-1');
    expect(registry.assets['asset-1']).toEqual(expect.objectContaining({
      file: 'clips/demo.mp4',
      type: 'video/mp4',
      duration: 4,
    }));
  });

  it('throws the public not-found and conflict errors', async () => {
    const provider = new InMemoryDataProvider({
      timelines: {
        'timeline-1': {
          config: buildConfig(),
        },
      },
    });

    await expect(provider.loadTimeline('missing')).rejects.toBeInstanceOf(TimelineNotFoundError);
    await expect(provider.saveTimeline('timeline-1', buildConfig(), 999)).rejects.toBeInstanceOf(TimelineVersionConflictError);
  });

  it('supports local/file asset resolution through the public resolver seam', async () => {
    const resolver = createLocalAssetResolver({ assetRoot: 'https://cdn.example/assets/' });
    const provider = new InMemoryDataProvider({
      timelines: {
        'timeline-1': {
          config: buildConfig(),
        },
      },
      resolveAssetUrl: resolver.resolveAssetUrl,
    });

    await expect(provider.resolveAssetUrl('video/demo.mp4')).resolves.toBe('https://cdn.example/assets/video/demo.mp4');
    await expect(provider.resolveAssetUrl('https://example.com/absolute.mp4')).resolves.toBe('https://example.com/absolute.mp4');
  });
});
