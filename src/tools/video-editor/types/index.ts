// Sprint 2: re-export the canonical shared types so Reigh and Banodoco agree at
// the boundary. Reigh keeps richer locally-typed shapes for editor-internal use
// (ResolvedTimelineConfig, ClipMeta, etc.) — only the persisted on-disk shape
// must match the shared schema.
export type {
  TimelineConfigT as SharedTimelineConfig,
  TimelineClipT as SharedTimelineClip,
  ThemeOverridesT as SharedThemeOverrides,
  TimelineOutputT as SharedTimelineOutput,
  AssetEntryT as SharedAssetEntry,
  ThemeT as SharedTheme,
} from '@banodoco/timeline-schema';

export type TimelineEffect = {
  fade_in?: number;
  fade_out?: number;
};

export type ParameterType =
  | 'number'
  | 'select'
  | 'boolean'
  | 'color'
  | 'audio-binding';

export type AudioBindingValue = {
  source: 'bass' | 'mid' | 'treble' | 'amplitude';
  min: number;
  max: number;
};

export type ParameterOption = {
  label: string;
  value: string;
};

export type ParameterDefinition = {
  name: string;
  label: string;
  description: string;
  type: ParameterType;
  default?: number | string | boolean | AudioBindingValue;
  min?: number;
  max?: number;
  step?: number;
  options?: ParameterOption[];
};

export type ParameterSchema = ParameterDefinition[];

export type TrackKind = 'visual' | 'audio';
export type TrackFit = 'cover' | 'contain' | 'manual';
export type TrackBlendMode =
  | 'normal'
  | 'multiply'
  | 'screen'
  | 'overlay'
  | 'darken'
  | 'lighten'
  | 'soft-light'
  | 'hard-light';
// SD-024 (Sprint 2): clipType is widened to a string at the schema level.
// The closed union of built-in clip types is retained as BUILTIN_CLIP_TYPES for
// call sites that still narrow against the legacy four. Effect-id / theme-id
// validation against a registry is Sprint 5; the editor's placeholder fallback
// for unknown clipTypes is Sprint 3.
export const BUILTIN_CLIP_TYPES = ['media', 'hold', 'text', 'effect-layer'] as const;
export type BuiltinClipType = (typeof BUILTIN_CLIP_TYPES)[number];
export type ClipType = string;

export type TrackDefinition = {
  id: string;
  kind: TrackKind;
  label: string;
  scale?: number;
  fit?: TrackFit;
  opacity?: number;
  volume?: number;
  muted?: boolean;
  blendMode?: TrackBlendMode;
  app?: Record<string, unknown>;
};

export type ClipEntrance = {
  type: string;
  duration: number;
  intensity?: number;
  params?: Record<string, unknown>;
};

export type ClipExit = {
  type: string;
  duration: number;
  intensity?: number;
  params?: Record<string, unknown>;
};

export type ClipContinuous = {
  type: string;
  intensity?: number;
  params?: Record<string, unknown>;
};

export type ClipTransition = {
  type: string;
  duration: number;
};

export type TextAlignment = 'left' | 'center' | 'right';

export type TextClipData = {
  content: string;
  fontFamily?: string;
  fontSize?: number;
  color?: string;
  align?: TextAlignment;
  bold?: boolean;
  italic?: boolean;
};

export type TimelineClip = {
  id: string;
  at: number;
  track: string;
  clipType?: ClipType;
  asset?: string;
  from?: number;
  to?: number;
  speed?: number;
  hold?: number;
  volume?: number;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  cropTop?: number;
  cropBottom?: number;
  cropLeft?: number;
  cropRight?: number;
  opacity?: number;
  text?: TextClipData;
  entrance?: ClipEntrance;
  exit?: ClipExit;
  continuous?: ClipContinuous;
  transition?: ClipTransition;
  effects?: TimelineEffect[] | Record<string, number>;
  // Sprint 2: schema-lift fields. All optional; existing timelines without them
  // round-trip unchanged. `params` carries effect/theme parameter blobs;
  // `pool_id` / `clip_order` are Banodoco-arrangement provenance fields.
  params?: Record<string, unknown>;
  pool_id?: string;
  clip_order?: number;
  source_uuid?: string;
  generation?: Record<string, unknown>;
  app?: Record<string, unknown>;
};

export type TimelineOutput = {
  resolution: string;
  fps: number;
  file: string;
  background?: string | null;
  background_scale?: number | null;
};

export type CustomEffectEntry = {
  code: string;
  category?: 'entrance' | 'exit' | 'continuous';
};

export type PinnedShotImageClipSnapshot = {
  clipId: string;
  assetKey?: string;
  start?: number;
  end?: number;
  meta: {
    clipType?: ClipType;
    from?: number;
    to?: number;
    speed?: number;
    hold?: number;
    volume?: number;
    x?: number;
    y?: number;
    width?: number;
    height?: number;
    cropTop?: number;
    cropBottom?: number;
    cropLeft?: number;
    cropRight?: number;
    opacity?: number;
    text?: TextClipData;
    entrance?: ClipEntrance;
    exit?: ClipExit;
    continuous?: ClipContinuous;
    transition?: ClipTransition;
    effects?: TimelineEffect[] | Record<string, number>;
    params?: Record<string, unknown>;
    pool_id?: string;
    clip_order?: number;
    source_uuid?: string;
    generation?: Record<string, unknown>;
  };
};

// `clipIds` is ordered left-to-right by each clip's live `at` and must be rebuilt whenever group membership or ordering changes.
export type PinnedShotGroup = {
  shotId: string;
  trackId: string;
  clipIds: string[];
  mode?: 'images' | 'video';
  videoAssetKey?: string;
  imageClipSnapshot?: PinnedShotImageClipSnapshot[];
};

// Sprint 2: theme overrides and generation defaults blocks. Open-shaped on
// purpose — concrete schemas land with theme registry packages (Sprint 5+).
export type ThemeOverrides = {
  visual?: Record<string, unknown>;
  generation?: Record<string, unknown>;
  voice?: Record<string, unknown>;
  audio?: Record<string, unknown>;
  pacing?: Record<string, unknown>;
};

export type GenerationDefaults = Record<string, unknown>;

export type TimelineConfig = {
  output: TimelineOutput;
  clips: TimelineClip[];
  tracks?: TrackDefinition[];
  pinnedShotGroups?: PinnedShotGroup[];
  // Sprint 2: schema-lift fields. All optional. `theme` is a slug that
  // resolves against the theme registry at render time; `theme_overrides`
  // deep-merges onto the resolved theme; `generation_defaults` carries
  // pipeline-wide generation knobs.
  theme?: string;
  theme_overrides?: ThemeOverrides;
  generation_defaults?: GenerationDefaults;
  app?: Record<string, unknown>;
};

export type AssetRegistryEntry = {
  file: string;
  url?: string;
  etag?: string;
  content_sha256?: string;
  url_expires_at?: string;
  type?: string;
  duration?: number;
  resolution?: string;
  fps?: number;
  origin?: 'immutable-public' | 'refreshable-from-generation' | 'opaque-foreign';
  derivedFrom?: {
    assetId?: string;
    content_sha256?: string;
    role: 'thumbnail' | 'proxy' | 'render-output';
  };
  generationId?: string;
  variantId?: string;
  thumbnailUrl?: string;
};

export type AssetRegistry = {
  assets: Record<string, AssetRegistryEntry>;
};

export type ResolvedAssetRegistryEntry = AssetRegistryEntry & {
  src: string;
};

export type ResolvedTimelineClip = TimelineClip & {
  assetEntry?: ResolvedAssetRegistryEntry;
};

export type ResolvedTimelineConfig = {
  output: TimelineOutput;
  tracks: TrackDefinition[];
  clips: ResolvedTimelineClip[];
  registry: Record<string, ResolvedAssetRegistryEntry>;
  theme?: string;
  theme_overrides?: ThemeOverrides;
  generation_defaults?: GenerationDefaults;
  app?: Record<string, unknown>;
};

export type TimelineCompositionProps = {
  config?: ResolvedTimelineConfig;
  preview?: boolean;
};
