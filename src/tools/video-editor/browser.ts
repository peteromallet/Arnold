/**
 * @publicContract
 * Browser-only host helpers for mounting or linking into the video editor.
 */
export {
  VIDEO_EDITOR_PATH,
  videoEditorPathWithTimeline,
  resolveVideoEditorPath,
} from './lib/video-editor-path.ts';

export {
  videoEditorSettings,
} from './settings/videoEditorDefaults.ts';

export type {
  VideoEditorSettings,
} from './settings/videoEditorDefaults.ts';

export {
  createVideoEditorEffectCatalog,
} from './lib/effect-catalog.ts';
export {
  AVAILABLE_SEQUENCE_CLIP_TYPES,
  AVAILABLE_SEQUENCE_METADATA,
  getAvailableSequenceMetadata,
  isAvailableSequenceClipType,
} from './sequences/registry.ts';
export {
  BrowserVideoEditor,
} from './browser/BrowserVideoEditor.tsx';
export {
  useVideoEditorCommands,
  useVideoEditorHost,
  useVideoEditorTimeline,
} from './browser/hooks.tsx';
export {
  mountVideoEditor,
} from './browser/mountVideoEditor.tsx';
export {
  createLocalAssetResolver,
  InMemoryDataProvider,
} from './lib/browser-runtime.ts';

export type {
  AvailableSequenceMetadata,
} from './sequences/registry.ts';
export type {
  BrowserVideoEditorLayoutRenderer,
  BrowserVideoEditorProps,
} from './browser/BrowserVideoEditor.tsx';
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
