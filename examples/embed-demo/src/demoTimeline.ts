import {
  EMBED_DEMO_ASSET_KEYS,
  EMBED_DEMO_TIMELINE_ID,
  EMBED_DEMO_TIMELINE_NAME,
  createEmbedDemoTimelineFixture,
} from '@/tools/video-editor/testing.ts';

export {
  EMBED_DEMO_ASSET_KEYS,
  EMBED_DEMO_TIMELINE_ID,
  EMBED_DEMO_TIMELINE_NAME,
};

export function createEmbedDemoSeed() {
  const fixture = createEmbedDemoTimelineFixture();

  return {
    configVersion: fixture.configVersion,
    registry: fixture.registry,
    config: fixture.config,
  };
}
