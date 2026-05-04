/**
 * @publicContract
 * Browser-only runtime provider and hooks for supported custom shells.
 *
 * Import `./browser.ts` when you want the stock editor shell.
 */
export {
  BrowserVideoEditorProvider,
} from './browser/BrowserVideoEditorProvider.tsx';
export {
  useVideoEditorCommands,
  useVideoEditorHost,
  useVideoEditorTimeline,
} from './browser/hooks.tsx';
export {
  createVideoEditorEffectCatalog,
} from './lib/effect-catalog.ts';
export {
  createLocalAssetResolver,
  InMemoryDataProvider,
} from './lib/browser-runtime.ts';

export type {
  BrowserVideoEditorProviderProps,
} from './browser/BrowserVideoEditorProvider.tsx';
export type {
  VideoEditorCommands,
  VideoEditorHost,
  VideoEditorRenderStatus,
  VideoEditorReplaceTimelineConfigOptions,
  VideoEditorSaveStatus,
  VideoEditorTimelineState,
} from './browser/hooks.tsx';
export type {
  CreateVideoEditorEffectInput,
  DeleteVideoEditorEffectInput,
  EffectCategory,
  EffectResource,
  EffectResourcesByCategory,
  UpdateVideoEditorEffectInput,
  VideoEditorEffectCatalog,
  VideoEditorEffectCatalogOptions,
} from './lib/effect-catalog.ts';
export type {
  InMemoryDataProviderOptions,
  InMemoryTimelineSeed,
  VideoEditorAssetResolver,
  VideoEditorExporter,
  VideoEditorExportJob,
  VideoEditorExportProgress,
  VideoEditorExportRequest,
  VideoEditorHostContext,
} from './lib/browser-runtime.ts';
