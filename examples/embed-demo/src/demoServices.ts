import {
  createLocalAssetResolver,
  createVideoEditorEffectCatalog,
  InMemoryDataProvider,
} from '@/tools/video-editor/browser-provider.ts';
import { EMBED_DEMO_TIMELINE_ID, createEmbedDemoSeed } from './demoTimeline';

export function createEmbedDemoServices() {
  const assetResolver = createLocalAssetResolver({ assetRoot: '/' });
  const effectCatalog = createVideoEditorEffectCatalog({ effects: [] });
  const dataProvider = new InMemoryDataProvider({
    timelines: {
      [EMBED_DEMO_TIMELINE_ID]: createEmbedDemoSeed(),
    },
    resolveAssetUrl: assetResolver.resolveAssetUrl,
  });

  return {
    assetResolver,
    effectCatalog,
    dataProvider,
  };
}
