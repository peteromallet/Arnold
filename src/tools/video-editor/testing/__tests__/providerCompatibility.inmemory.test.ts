/**
 * Provider compatibility test: InMemoryDataProvider (testing utility)
 *
 * Exercises the shared providerCompatibility suite against the testing
 * InMemoryDataProvider to prove the helper correctly validates DataProvider
 * contract behavior.
 */

import { describe } from 'vitest';
import { InMemoryDataProvider } from '@/tools/video-editor/testing/InMemoryDataProvider';
import {
  runProviderCompatibilitySuite,
  type ProviderFactory,
} from '@/tools/video-editor/testing/providerCompatibility.shared';
import type { AssetRegistry, TimelineConfig } from '@/tools/video-editor/types/index';

const inMemoryFactory: ProviderFactory = (seed) => {
  const provider = new InMemoryDataProvider();
  if (seed?.timelineId) {
    provider.seedTimeline(seed.timelineId, {
      config: seed.config,
      configVersion: seed.configVersion,
      registry: seed.registry,
    });
  }
  return provider;
};

describe('InMemoryDataProvider compatibility (testing version)', () => {
  runProviderCompatibilitySuite(inMemoryFactory, {
    skipCheckpoints: false,
    versionConflictIsSoft: false,
    timelineId: 'compat-test-timeline',
    skipRegisterAsset: false,
  });
});
