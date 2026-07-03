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
  /** Minimum string length (StandardSchema `minLength`). */
  minLength?: number;
  /** Maximum string length (StandardSchema `maxLength`). */
  maxLength?: number;
  /** Regex pattern constraint (StandardSchema `pattern`). */
  pattern?: string;
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
export { BUILTIN_CLIP_TYPES, type BuiltinClipType } from '@/sdk/video/timeline/clipTypes.ts';
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
  params?: Record<string, unknown>;
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

// M9: Keyframe interpolation mode — mirrors the SDK KeyframeInterpolation type.
export type KeyframeInterpolation = 'linear' | 'hold';

// M9: A single keyframe stored as JSON-serializable timeline data on a clip.
export type ClipKeyframe = {
  /** Time in seconds. */
  time: number;
  /** JSON-serializable value (number | string | boolean). */
  value: number | string | boolean;
  /** Interpolation mode from this keyframe to the next. */
  interpolation: KeyframeInterpolation;
};

// M11: Timeline-resident live binding metadata. Runtime samples remain
// provider-scoped and must never be persisted in these shapes.
export type TimelineLiveSourceKind =
  | 'webcam'
  | 'microphone'
  | 'midi'
  | 'serial'
  | 'bluetooth'
  | 'generated'
  | 'screen-capture'
  | 'audio-device'
  | 'osc'
  | 'custom';

export type TimelineLiveSourceStatus =
  | 'inactive'
  | 'activating'
  | 'active'
  | 'error'
  | 'disposed'
  | 'orphaned';

export type TimelineLiveBindingResolutionStatus =
  | 'active'
  | 'inactive'
  | 'missing'
  | 'disposed'
  | 'orphaned'
  | 'partiallyBaked'
  | 'resolved'
  | 'malformed';

export type TimelineLiveSamplingMode = 'latest' | 'time' | 'frame' | 'sequence';

export type TimelineLiveBakeRange = {
  start?: number;
  end?: number;
  startFrame?: number;
  endFrame?: number;
  startSample?: number;
  endSample?: number;
  takeId?: string;
};

export type TimelineLiveDeterministicRefKind =
  | 'asset'
  | 'keyframe'
  | 'automation'
  | 'clip'
  | 'sidecar'
  | 'render-material';

export type TimelineLiveDeterministicRef = {
  kind: TimelineLiveDeterministicRefKind;
  ref: string;
  range?: TimelineLiveBakeRange;
  metadata?: Record<string, unknown>;
};

export type TimelineLiveBakeMetadata = {
  status?: 'unbaked' | 'partial' | 'complete';
  bakedRanges?: TimelineLiveBakeRange[];
  unresolvedRanges?: TimelineLiveBakeRange[];
  deterministicRefs?: TimelineLiveDeterministicRef[];
};

export type TimelineLiveBinding = {
  bindingId: string;
  sourceId: string;
  sourceKind: TimelineLiveSourceKind;
  channelId?: string;
  targetParamName?: string;
  targetEffectId?: string;
  targetPath?: string;
  ownerExtensionId?: string;
  sampling?: {
    mode: TimelineLiveSamplingMode;
    frameOffset?: number;
    timeOffsetMs?: number;
  };
  sourceStatus?: TimelineLiveSourceStatus;
  resolutionStatus?: TimelineLiveBindingResolutionStatus;
  bake?: TimelineLiveBakeMetadata;
  deterministicRefs?: TimelineLiveDeterministicRef[];
  placeholder?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
};

export type TimelineLiveClipMetadata = {
  bindings?: TimelineLiveBinding[];
};

export type TimelineLiveUniformBindingMappingKind =
  | 'scalar'
  | 'vector'
  | 'fft-bin'
  | 'rms-amplitude'
  | 'onset-event'
  | 'frame-ref'
  | 'material-ref';

export type TimelineLiveUniformVectorComponent = 'x' | 'y' | 'z' | 'w';

export type TimelineLiveUniformBindingMapping =
  | {
      kind: 'scalar';
      uniform: string;
      sourcePath?: string;
      scale?: number;
      offset?: number;
    }
  | {
      kind: 'vector';
      uniform: string;
      components: TimelineLiveUniformVectorComponent[];
      sourcePaths?: string[];
    }
  | {
      kind: 'fft-bin';
      uniform: string;
      bin: number;
      fftSize?: number;
      smoothing?: number;
    }
  | {
      kind: 'rms-amplitude';
      uniform: string;
      windowMs?: number;
      scale?: number;
    }
  | {
      kind: 'onset-event';
      uniform: string;
      threshold?: number;
      decayMs?: number;
    }
  | {
      kind: 'frame-ref';
      uniform: string;
      ref: TimelineLiveDeterministicRef;
    }
  | {
      kind: 'material-ref';
      uniform: string;
      ref: TimelineLiveDeterministicRef;
    };

export type TimelineLiveUniformBinding = {
  bindingId: string;
  sourceId: string;
  sourceKind: TimelineLiveSourceKind;
  channelId?: string;
  targetMaterialId?: string;
  targetParamName?: string;
  targetPath?: string;
  mapping: TimelineLiveUniformBindingMapping;
  metadata?: Record<string, unknown>;
};

// M13: Host-owned shader metadata persisted on the timeline. V1 stores one
// clip-local shader in clip.app.shader and one postprocess shader in
// config.app.shaderPostprocess.
export type TimelineShaderScope = 'clip' | 'postprocess';

export type TimelineShaderUniformValues = Record<string, unknown>;

export type TimelineShaderTextureRef = {
  kind: 'clip-frame' | 'static-image-asset' | 'live-generated-frame';
  ref?: string;
};

export type TimelineShaderTextureValues = Record<string, TimelineShaderTextureRef>;

export type TimelineShaderBaseMetadata = {
  extensionId: string;
  contributionId: string;
  shaderId: string;
  label?: string;
  uniforms?: TimelineShaderUniformValues;
  textures?: TimelineShaderTextureValues;
  enabled?: boolean;
  sourceHash?: string;
  metadata?: Record<string, unknown>;
};

export type TimelineClipShaderMetadata = TimelineShaderBaseMetadata & {
  scope: 'clip';
};

export type TimelinePostprocessShaderMetadata = TimelineShaderBaseMetadata & {
  scope: 'postprocess';
};

export type TimelineClipAppMetadata = Record<string, unknown> & {
  shader?: TimelineClipShaderMetadata;
};

export type TimelineConfigAppMetadata = Record<string, unknown> & {
  shaderPostprocess?: TimelinePostprocessShaderMetadata;
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
  app?: TimelineClipAppMetadata;
  // M9: Host-owned keyframes keyed by parameter name.
  // Each parameter maps to an ordered array of keyframes.
  keyframes?: Record<string, ClipKeyframe[]>;
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
    keyframes?: Record<string, ClipKeyframe[]>;
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
  app?: TimelineConfigAppMetadata;
};

// ---------------------------------------------------------------------------
// Asset metadata — host-owned shapes + extension namespace
// ---------------------------------------------------------------------------

export type AssetMetadataIntegrity = {
  sha256?: string;
  md5?: string;
  crc32?: string;
};

export type AssetMetadataGPS = {
  latitude?: number;
  longitude?: number;
  altitude?: number;
  horizontalAccuracy?: number;
  timestamp?: string;
};

export type AssetMetadataConsent = {
  modelRelease?: boolean;
  propertyRelease?: boolean;
  rightsHolder?: string;
  license?: string;
  usageTerms?: string;
};

export type AssetMetadataProvenance = {
  importTimestamp?: string;
  sourceUrl?: string;
  sourceProvider?: string;
  importedBy?: string;
  originalFilename?: string;
};

export type AssetMetadataEnrichmentClaim = {
  claimId: string;
  parserId: string;
  timestamp: string;
  field?: string;
  summary?: string;
};

export type AssetMetadataEnrichment = {
  pending?: number;
  failed?: number;
  claims?: AssetMetadataEnrichmentClaim[];
};

export type AssetMetadata = {
  integrity?: AssetMetadataIntegrity;
  gps?: AssetMetadataGPS;
  consent?: AssetMetadataConsent;
  provenance?: AssetMetadataProvenance;
  enrichment?: AssetMetadataEnrichment;
  extensions?: Record<string, unknown>;
};

// ---------------------------------------------------------------------------
// Registry entries
// ---------------------------------------------------------------------------

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
  metadata?: AssetMetadata;
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
  app?: TimelineConfigAppMetadata;
};

export type TimelineCompositionProps = {
  config?: ResolvedTimelineConfig;
  preview?: boolean;
};
