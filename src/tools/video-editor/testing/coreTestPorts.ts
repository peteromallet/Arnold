import type { VideoEditorCorePorts } from '@/tools/video-editor/core/core-ports';
import type { AssetRegistry, TimelineConfig } from '@/tools/video-editor/types';
import { createDefaultTimelineConfig } from '@/tools/video-editor/lib/defaults';
import { InMemoryDataProvider } from '@/tools/video-editor/testing/InMemoryDataProvider';

export const CORE_TEST_TIMELINE_ID = 'timeline-headless-test';

export function createCoreTestTimelineConfig(): TimelineConfig {
  return {
    ...createDefaultTimelineConfig(),
    clips: [
      {
        id: 'clip-1',
        at: 0,
        track: 'V1',
        clipType: 'hold',
        hold: 2,
      },
    ],
  };
}

export function createCoreTestAssetRegistry(): AssetRegistry {
  return {
    assets: {
      'asset-1': {
        file: 'https://example.com/asset-1.png',
        type: 'image/png',
        generationId: 'generation-1',
        thumbnailUrl: 'https://example.com/asset-1-thumb.png',
      },
    },
  };
}

export function createCoreTestPorts(
  overrides: Partial<VideoEditorCorePorts> = {},
): { ports: VideoEditorCorePorts; dataProvider: InMemoryDataProvider } {
  const dataProvider = new InMemoryDataProvider({
    [CORE_TEST_TIMELINE_ID]: {
      config: createCoreTestTimelineConfig(),
      configVersion: 1,
      registry: createCoreTestAssetRegistry(),
    },
  });

  return {
    dataProvider,
    ports: {
      dataProvider,
      selectedProjectId: null,
      shots: [],
      finalVideoMap: new Map(),
      ...overrides,
    },
  };
}
