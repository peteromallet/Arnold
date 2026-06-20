/**
 * Provider compatibility test: InMemoryDataProvider (production/browser-runtime)
 *
 * Exercises the shared providerCompatibility suite against the production
 * InMemoryDataProvider from browser-runtime to prove the helper correctly
 * validates DataProvider contract behavior across both InMemory variants.
 */

import { describe } from 'vitest';
import {
  InMemoryDataProvider,
  createLocalAssetResolver,
} from '@/tools/video-editor/lib/browser-runtime';
import {
  runProviderCompatibilitySuite,
  type ProviderFactory,
} from '@/tools/video-editor/testing/providerCompatibility.shared';
import type { AssetRegistry, TimelineConfig } from '@/tools/video-editor/types/index';

const inMemoryFactory: ProviderFactory = (seed) => {
  const provider = new InMemoryDataProvider({
    timelines: seed?.timelineId
      ? {
          [seed.timelineId]: {
            config: seed.config ?? ({} as TimelineConfig),
            configVersion: seed.configVersion,
            registry: seed.registry,
          },
        }
      : {},
    resolveAssetUrl: createLocalAssetResolver({ assetRoot: 'https://cdn.example/assets/' }).resolveAssetUrl,
  });
  return provider;
};

describe('InMemoryDataProvider compatibility (browser-runtime)', () => {
  runProviderCompatibilitySuite(inMemoryFactory, {
    skipCheckpoints: false,
    versionConflictIsSoft: false,
    timelineId: 'compat-test-timeline',
    skipRegisterAsset: false,
  });
});
