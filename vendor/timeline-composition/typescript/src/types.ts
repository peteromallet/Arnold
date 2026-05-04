// Sprint 5: package-internal type aliases.
//
// These mirror the structure of `tools/remotion/src/types.ts` (which re-exports
// from `types.generated.ts`), but to keep the package self-contained we declare
// the minimal interfaces here. The Banodoco shell at `tools/remotion/` keeps
// the real codegen-driven `types.generated.ts` for its own validation work
// (smoke fixture asserts allowed-arrays match); the package consumers only
// need the runtime shape used by the composition.

export type TimelineClip = {
  id: string;
  at: number;
  track: string;
  asset?: string;
  clipType?: string;
  clip_order?: number;
  continuous?: unknown;
  cropBottom?: number;
  cropLeft?: number;
  cropRight?: number;
  cropTop?: number;
  effects?: unknown;
  entrance?: unknown;
  exit?: unknown;
  from?: number;
  generation?: unknown;
  height?: number;
  hold?: number;
  opacity?: number;
  params?: Record<string, unknown>;
  pool_id?: string;
  source_uuid?: string;
  speed?: number;
  text?: unknown;
  to?: number;
  transition?: unknown;
  volume?: number;
  width?: number;
  x?: number;
  y?: number;
};

export type TrackDefinition = {
  blendMode?: 'darken' | 'hard-light' | 'lighten' | 'multiply' | 'normal' | 'overlay' | 'screen' | 'soft-light';
  fit?: 'contain' | 'cover' | 'manual';
  id: string;
  kind: 'audio' | 'visual';
  label: string;
  muted?: boolean;
  opacity?: number;
  scale?: number;
  volume?: number;
};

export type TimelineConfig = {
  theme: string;
  tracks?: TrackDefinition[];
  clips: TimelineClip[];
  output?: unknown;
  pinnedShotGroups?: unknown;
  theme_overrides?: unknown;
};

export type AssetRegistryEntry = {
  file?: string;
  type?: string;
  duration?: number;
  resolution?: string;
  fps?: number;
  url?: string;
  url_expires_at?: string;
  content_sha256?: string;
  etag?: string;
  thumbnailUrl?: string;
  generationId?: string;
  variantId?: string;
};

export type AssetRegistry = {
  assets: Record<string, AssetRegistryEntry>;
};

export type HypeCompositionProps = {
  timeline: TimelineConfig;
  assets: AssetRegistry;
  theme?: import('./ThemeContext').Theme;
};

// Sprint 5: TimelineCompositionProps is the canonical name going forward.
// HypeCompositionProps remains exported as a back-compat alias for the
// banodoco-side bundle smoke + tests until they migrate.
export type TimelineCompositionProps = HypeCompositionProps;
