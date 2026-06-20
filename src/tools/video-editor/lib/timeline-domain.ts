import type {
  AssetRegistry,
  AssetRegistryEntry,
  ClipContinuous,
  ClipEntrance,
  ClipExit,
  ClipTransition,
  PinnedShotGroup,
  TimelineClip,
  TimelineConfig,
  TimelineLiveBinding,
  TimelineLiveBindingResolutionStatus,
  TimelineLiveDeterministicRef,
  TimelineLiveSourceKind,
  TimelineLiveSourceStatus,
  TimelineLiveUniformBinding,
  TimelineLiveUniformBindingMappingKind,
  TrackDefinition,
} from '../types/index.ts';
import { validateAssetMetadata } from './assetMetadata';
import type { TransitionRegistrySnapshot } from '@/tools/video-editor/transitions/registry/types.ts';
import {
  validateClipTransition,
  repairClipTransition,
  TransitionDiagnosticCodes,
} from '@/tools/video-editor/transitions/validation.ts';

export type TimelineDomainContractLevel = 'config-only' | 'pair-aware';
export type TimelineDomainIssueSeverity = 'warning' | 'error';
export type TimelineDomainIssueCode =
  | 'duplicate_track_removed'
  | 'duplicate_clip_removed'
  | 'legacy_pinned_shot_group_repaired'
  | 'legacy_tracks_migrated'
  | 'legacy_background_clip_inserted'
  | 'shot_group_contiguity_repaired'
  | 'malformed_non_hold_trim_repaired'
  | 'malformed_non_hold_trim_zero_duration'
  | 'unexpected_top_level_key'
  | 'unexpected_clip_key'
  | 'unexpected_track_key'
  | 'legacy_transition_missing_type'
  | 'legacy_transition_unresolvable'
  | 'legacy_transition_removed_contributed'
  | 'legacy_transition_params_repaired'
  | 'legacy_transition_cleared'
  | 'live_binding_malformed_metadata'
  | 'live_binding_missing_binding_id'
  | 'live_binding_missing_source_id'
  | 'live_binding_missing_source_kind'
  | 'live_binding_unsupported_source_kind'
  | 'live_binding_sample_payload_rejected';

export interface TimelineDomainIssue {
  level: TimelineDomainContractLevel;
  severity: TimelineDomainIssueSeverity;
  code: TimelineDomainIssueCode;
  message: string;
  path?: string;
  clipId?: string;
  assetId?: string;
  trackId?: string;
  repairApplied?: boolean;
  details?: Record<string, unknown>;
}

export interface CanonicalTimelineConfigSnapshot {
  level: 'config-only';
  config: TimelineConfig;
  issues: TimelineDomainIssue[];
}

export interface CanonicalTimelinePair {
  level: 'pair-aware';
  config: TimelineConfig;
  registry: AssetRegistry;
  issues: TimelineDomainIssue[];
}

export interface TimelineDomainValidationResult {
  level: TimelineDomainContractLevel;
  ok: boolean;
  issues: TimelineDomainIssue[];
}

export class TimelineDomainError extends Error {
  readonly issues: TimelineDomainIssue[];
  readonly level: TimelineDomainContractLevel;

  constructor(level: TimelineDomainContractLevel, issues: TimelineDomainIssue[], message?: string) {
    super(message ?? (issues.map((issue) => issue.message).join('; ') || 'Invalid timeline payload'));
    this.name = 'TimelineDomainError';
    this.issues = issues;
    this.level = level;
  }
}

type TimelineExtras = Pick<TimelineConfig, 'theme' | 'theme_overrides' | 'generation_defaults' | 'app'>;
type LegacyPinnedGroupChild = { clipId: string; offset?: number; duration?: number };
type LegacyPinnedShotGroup = PinnedShotGroup & {
  start?: number;
  children?: LegacyPinnedGroupChild[];
};

const DEFAULT_VIDEO_SCALE = 0.95;
const LEGACY_TRACK_MAP: Record<string, string> = {
  video: 'V2',
  overlay: 'V3',
  audio: 'A1',
};
const LEGACY_ASSET_EFFECTS: Record<
  string,
  { entrance?: ClipEntrance; exit?: ClipExit; continuous?: ClipContinuous }
> = {
  'output-composition': {
    entrance: { type: 'slide-up', duration: 0.6 },
    exit: { type: 'flip', duration: 0.6 },
    continuous: { type: 'float', intensity: 0.45 },
  },
  'venn-diagram': {
    entrance: { type: 'zoom-spin', duration: 0.6 },
    exit: { type: 'zoom-out', duration: 0.5 },
    continuous: { type: 'ken-burns', intensity: 0.55 },
  },
  'demo-one': {
    entrance: { type: 'slide-right', duration: 0.6 },
    exit: { type: 'slide-down', duration: 0.5 },
    continuous: { type: 'glitch', intensity: 0.45 },
  },
  'demo-two': {
    entrance: { type: 'pulse', duration: 0.5 },
    exit: { type: 'flip', duration: 0.6 },
  },
};

const TIMELINE_TIME_PRECISION = 4;
const CONTIGUITY_EPSILON = 0.001;

export const TIMELINE_CLIP_FIELDS = [
  'id',
  'at',
  'track',
  'clipType',
  'asset',
  'from',
  'to',
  'speed',
  'hold',
  'volume',
  'x',
  'y',
  'width',
  'height',
  'cropTop',
  'cropBottom',
  'cropLeft',
  'cropRight',
  'opacity',
  'text',
  'entrance',
  'exit',
  'continuous',
  'transition',
  'effects',
  'params',
  'pool_id',
  'clip_order',
  'source_uuid',
  'generation',
  'app',
  // M9: Host-owned keyframes keyed by parameter name
  'keyframes',
] as const;

export type TimelineClipField = (typeof TIMELINE_CLIP_FIELDS)[number];

export const TRACK_DEFINITION_FIELDS = [
  'id',
  'kind',
  'label',
  'scale',
  'fit',
  'opacity',
  'volume',
  'muted',
  'blendMode',
  'app',
] as const;

export type TrackDefinitionField = (typeof TRACK_DEFINITION_FIELDS)[number];

const ALLOWED_TOP_LEVEL_KEYS = new Set([
  'output',
  'clips',
  'tracks',
  'pinnedShotGroups',
  'theme',
  'theme_overrides',
  'generation_defaults',
  'app',
]);

const ASSET_REGISTRY_ENTRY_FIELDS = [
  'file',
  'url',
  'etag',
  'content_sha256',
  'url_expires_at',
  'type',
  'duration',
  'resolution',
  'fps',
  'origin',
  'derivedFrom',
  'generationId',
  'variantId',
  'thumbnailUrl',
  'metadata',
] as const;

const roundTimelineValue = (value: number, digits = TIMELINE_TIME_PRECISION): number => {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
};

const cloneAppValue = (value: unknown): unknown => {
  if (Array.isArray(value)) {
    return value.map(cloneAppValue);
  }

  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, childValue]) => [key, cloneAppValue(childValue)]),
    );
  }

  return value;
};

export const cloneAppExtension = (app: Record<string, unknown>): Record<string, unknown> => {
  if (typeof structuredClone === 'function') {
    try {
      return structuredClone(app) as Record<string, unknown>;
    } catch {
      // Fall back to JSON-shaped structural passthrough for non-cloneable values.
    }
  }

  return cloneAppValue(app) as Record<string, unknown>;
};

const cloneTimelineExtras = (config: TimelineConfig): TimelineExtras => ({
  ...(config.theme !== undefined ? { theme: config.theme } : {}),
  ...(config.theme_overrides !== undefined ? { theme_overrides: config.theme_overrides } : {}),
  ...(config.generation_defaults !== undefined ? { generation_defaults: config.generation_defaults } : {}),
  ...(config.app !== undefined ? { app: cloneAppExtension(config.app) } : {}),
});

const clonePinnedShotImageSnapshots = (
  imageClipSnapshot: PinnedShotGroup['imageClipSnapshot'],
): PinnedShotGroup['imageClipSnapshot'] => imageClipSnapshot?.map((snapshot) => ({
  ...snapshot,
  meta: { ...snapshot.meta },
}));

export const clonePinnedShotGroups = (
  pinnedShotGroups: TimelineConfig['pinnedShotGroups'],
): TimelineConfig['pinnedShotGroups'] => pinnedShotGroups?.map((group) => ({
  shotId: group.shotId,
  trackId: group.trackId,
  clipIds: [...group.clipIds],
  mode: group.mode,
  videoAssetKey: group.videoAssetKey,
  imageClipSnapshot: clonePinnedShotImageSnapshots(group.imageClipSnapshot),
}));

export const cloneAssetRegistry = (registry: AssetRegistry): AssetRegistry => ({
  assets: Object.fromEntries(
    Object.entries(registry.assets ?? {}).map(([assetId, entry]) => [assetId, sanitizeAssetRegistryEntry(entry)]),
  ),
});

const createIssue = (
  level: TimelineDomainContractLevel,
  severity: TimelineDomainIssueSeverity,
  code: TimelineDomainIssueCode,
  message: string,
  extra: Omit<TimelineDomainIssue, 'level' | 'severity' | 'code' | 'message'> = {},
): TimelineDomainIssue => ({
  level,
  severity,
  code,
  message,
  ...extra,
});

const isFiniteNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);

const isPositiveNumber = (value: unknown): value is number => isFiniteNumber(value) && value > 0;

const stripDupSuffix = (id: string): string => id.replace(/(-dup-\d+)+$/, '');

const isHoldLikeClip = (clip: TimelineClip): boolean => clip.clipType === 'hold' || typeof clip.hold === 'number';

const hasValidNonHoldTrim = (clip: Pick<TimelineClip, 'from' | 'to'>): boolean => {
  return isFiniteNumber(clip.from) && isFiniteNumber(clip.to) && clip.to > clip.from;
};

const getClipAssetDurationSeconds = (registry: AssetRegistry, assetId?: string): number | null => {
  if (!assetId) {
    return null;
  }

  const duration = registry.assets?.[assetId]?.duration;
  return isPositiveNumber(duration) ? duration : null;
};

const getDefaultTracks = (config: TimelineConfig): TrackDefinition[] => {
  const videoScale = config.output.background_scale ?? DEFAULT_VIDEO_SCALE;
  return [
    {
      id: 'V1',
      kind: 'visual',
      label: 'V1',
      scale: 1,
      fit: 'cover',
      opacity: 1,
      blendMode: 'normal',
    },
    {
      id: 'V2',
      kind: 'visual',
      label: 'V2',
      scale: videoScale,
      fit: 'contain',
      opacity: 1,
      blendMode: 'normal',
    },
    {
      id: 'V3',
      kind: 'visual',
      label: 'V3',
      scale: 1,
      fit: 'manual',
      opacity: 1,
      blendMode: 'normal',
    },
    {
      id: 'A1',
      kind: 'audio',
      label: 'A1',
      scale: 1,
      fit: 'contain',
      opacity: 1,
      blendMode: 'normal',
    },
  ];
};

const migrateLegacyEffects = (clip: TimelineClip): TimelineClip => {
  const nextClip: TimelineClip = { ...clip };
  const fadeIn = clip.effects && !Array.isArray(clip.effects) ? clip.effects.fade_in : undefined;
  const fadeOut = clip.effects && !Array.isArray(clip.effects) ? clip.effects.fade_out : undefined;
  const fallback = clip.asset ? LEGACY_ASSET_EFFECTS[clip.asset] : undefined;

  if (!nextClip.entrance && typeof fadeIn === 'number' && fadeIn > 0) {
    nextClip.entrance = { type: 'fade', duration: fadeIn };
  } else if (!nextClip.entrance && fallback?.entrance) {
    nextClip.entrance = fallback.entrance;
  }

  if (!nextClip.exit && typeof fadeOut === 'number' && fadeOut > 0) {
    nextClip.exit = { type: 'fade-out', duration: fadeOut };
  } else if (!nextClip.exit && fallback?.exit) {
    nextClip.exit = fallback.exit;
  }

  if (!nextClip.continuous && fallback?.continuous) {
    nextClip.continuous = fallback.continuous;
  }

  delete nextClip.effects;
  return nextClip;
};

const migrateLegacyClip = (clip: TimelineClip): TimelineClip => {
  const nextTrack = LEGACY_TRACK_MAP[clip.track] ?? clip.track;
  const clipType = clip.clipType
    ?? (clip.text ? 'text' : typeof clip.hold === 'number' ? 'hold' : 'media');

  return migrateLegacyEffects({
    ...clip,
    track: nextTrack,
    clipType,
  });
};

const ensureBackgroundClip = (
  config: TimelineConfig,
  level: TimelineDomainContractLevel,
  issues?: TimelineDomainIssue[],
): TimelineClip[] => {
  const backgroundAsset = config.output.background;
  if (!backgroundAsset) {
    return config.clips.map(migrateLegacyClip);
  }

  const migratedClips = config.clips.map(migrateLegacyClip);
  const alreadyPresent = migratedClips.some((clip) => clip.track === 'V1');
  if (alreadyPresent) {
    return migratedClips;
  }

  const timelineDuration = Math.max(0.1, roundTimelineValue(getConfigTimelineDuration(migratedClips)));
  issues?.push(createIssue(
    level,
    'warning',
    'legacy_background_clip_inserted',
    `Inserted missing V1 background clip for asset '${backgroundAsset}'.`,
    {
      assetId: backgroundAsset,
      path: 'clips',
      repairApplied: true,
      details: { duration: timelineDuration },
    },
  ));
  return [
    {
      id: 'clip-background',
      at: 0,
      track: 'V1',
      clipType: 'hold',
      asset: backgroundAsset,
      hold: timelineDuration,
      opacity: 1,
    },
    ...migratedClips,
  ];
};

export const getCanonicalClipPlaybackRate = (speed: TimelineClip['speed']): number => {
  return isPositiveNumber(speed) ? speed : 1;
};

export const getConfigTimelineClipSourceDuration = (clip: TimelineClip): number => {
  if (isHoldLikeClip(clip)) {
    return isFiniteNumber(clip.hold) ? Math.max(0, clip.hold) : 0;
  }

  if (hasValidNonHoldTrim(clip)) {
    return clip.to - clip.from;
  }

  return 0;
};

export const getPairTimelineClipSourceDuration = (
  clip: TimelineClip,
  registry: AssetRegistry,
): number => {
  if (isHoldLikeClip(clip)) {
    return getConfigTimelineClipSourceDuration(clip);
  }

  if (hasValidNonHoldTrim(clip)) {
    return clip.to - clip.from;
  }

  return getClipAssetDurationSeconds(registry, clip.asset) ?? 0;
};

export const getConfigTimelineClipDuration = (clip: TimelineClip): number => {
  return getConfigTimelineClipSourceDuration(clip) / getCanonicalClipPlaybackRate(clip.speed);
};

export const getPairTimelineClipDuration = (
  clip: TimelineClip,
  registry: AssetRegistry,
): number => {
  return getPairTimelineClipSourceDuration(clip, registry) / getCanonicalClipPlaybackRate(clip.speed);
};

export const getConfigTimelineDuration = (clips: TimelineClip[]): number => {
  return clips.reduce((maxDuration, clip) => Math.max(maxDuration, clip.at + getConfigTimelineClipDuration(clip)), 0);
};

export const getPairTimelineDuration = (clips: TimelineClip[], registry: AssetRegistry): number => {
  return clips.reduce((maxDuration, clip) => Math.max(maxDuration, clip.at + getPairTimelineClipDuration(clip, registry)), 0);
};

export const repairConfig = (
  config: TimelineConfig,
  issues?: TimelineDomainIssue[],
  level: TimelineDomainContractLevel = 'config-only',
): TimelineConfig => {
  let repaired = false;
  let duplicateTrackCount = 0;
  let duplicateClipCount = 0;
  let repairedLegacyGroupCount = 0;

  const seenTracks = new Set<string>();
  const tracks = (config.tracks ?? []).filter((track) => {
    if (seenTracks.has(track.id)) {
      duplicateTrackCount += 1;
      repaired = true;
      return false;
    }
    seenTracks.add(track.id);
    return true;
  });

  const seenClips = new Set<string>();
  const clips: TimelineClip[] = [];
  for (const clip of config.clips) {
    const baseId = stripDupSuffix(clip.id);
    if (seenClips.has(baseId)) {
      duplicateClipCount += 1;
      repaired = true;
      continue;
    }
    seenClips.add(baseId);
    clips.push(baseId !== clip.id ? { ...clip, id: baseId } : clip);
  }

  const pinnedShotGroups = config.pinnedShotGroups?.map((group) => {
    const legacy = group as LegacyPinnedShotGroup;
    const hasLegacyFields = typeof legacy.start === 'number' || Array.isArray(legacy.children);

    if (!hasLegacyFields) {
      return group;
    }

    repaired = true;
    repairedLegacyGroupCount += 1;
    const derivedClipIds = Array.isArray(legacy.children) && legacy.children.length > 0
      ? legacy.children.map((child) => child.clipId).filter((id): id is string => typeof id === 'string' && id.length > 0)
      : [...group.clipIds];

    return {
      shotId: group.shotId,
      trackId: group.trackId,
      clipIds: derivedClipIds,
      mode: group.mode,
      videoAssetKey: group.videoAssetKey,
      imageClipSnapshot: clonePinnedShotImageSnapshots(group.imageClipSnapshot),
    };
  });

  if (duplicateTrackCount > 0) {
    issues?.push(createIssue(
      level,
      'warning',
      'duplicate_track_removed',
      `Removed ${duplicateTrackCount} duplicate track definition(s).`,
      {
        path: 'tracks',
        repairApplied: true,
        details: { duplicateTrackCount },
      },
    ));
  }

  if (duplicateClipCount > 0) {
    issues?.push(createIssue(
      level,
      'warning',
      'duplicate_clip_removed',
      `Removed ${duplicateClipCount} duplicate clip(s) after stripping cascading -dup suffixes.`,
      {
        path: 'clips',
        repairApplied: true,
        details: { duplicateClipCount },
      },
    ));
  }

  if (repairedLegacyGroupCount > 0) {
    issues?.push(createIssue(
      level,
      'warning',
      'legacy_pinned_shot_group_repaired',
      `Repaired ${repairedLegacyGroupCount} legacy pinned shot group projection(s).`,
      {
        path: 'pinnedShotGroups',
        repairApplied: true,
        details: { repairedLegacyGroupCount },
      },
    ));
  }

  return repaired ? { ...config, tracks, clips, pinnedShotGroups } : config;
};

export const migrateToFlatTracks = (
  config: TimelineConfig,
  issues?: TimelineDomainIssue[],
  level: TimelineDomainContractLevel = 'config-only',
): TimelineConfig => {
  if (config.tracks?.length) {
    return {
      output: { ...config.output },
      tracks: config.tracks.map((track) => ({ ...track })),
      clips: config.clips.map((clip) => ({
        ...clip,
        clipType: clip.clipType
          ?? (clip.text ? 'text' : typeof clip.hold === 'number' ? 'hold' : 'media'),
      })),
      pinnedShotGroups: clonePinnedShotGroups(config.pinnedShotGroups),
      ...cloneTimelineExtras(config),
    };
  }

  issues?.push(createIssue(
    level,
    'warning',
    'legacy_tracks_migrated',
    'Migrated legacy timeline config into the flat-track shape.',
    {
      path: 'tracks',
      repairApplied: true,
    },
  ));

  return {
    output: { ...config.output },
    tracks: getDefaultTracks(config),
    clips: ensureBackgroundClip(config, level, issues),
    pinnedShotGroups: clonePinnedShotGroups(config.pinnedShotGroups),
    ...cloneTimelineExtras(config),
  };
};

export const repairShotGroupContiguity = (
  config: TimelineConfig,
  issues?: TimelineDomainIssue[],
  level: TimelineDomainContractLevel = 'config-only',
): TimelineConfig => {
  if (!config.pinnedShotGroups?.length) {
    return config;
  }

  const clipById = new Map<string, TimelineClip>();
  for (const clip of config.clips) {
    clipById.set(clip.id, clip);
  }

  let totalFixed = 0;
  const clipAtOverrides = new Map<string, number>();

  for (const group of config.pinnedShotGroups) {
    if (group.clipIds.length < 2) {
      continue;
    }

    const groupClips: TimelineClip[] = [];
    for (const clipId of group.clipIds) {
      const clip = clipById.get(clipId);
      if (clip) {
        groupClips.push(clip);
      }
    }
    if (groupClips.length < 2) {
      continue;
    }

    groupClips.sort((left, right) => left.at - right.at);
    let fixedInGroup = 0;
    let cursor = groupClips[0].at + getConfigTimelineClipDuration(groupClips[0]);

    for (let index = 1; index < groupClips.length; index += 1) {
      const clip = groupClips[index];
      const gap = Math.abs(clip.at - cursor);

      if (gap > CONTIGUITY_EPSILON) {
        clipAtOverrides.set(clip.id, roundTimelineValue(cursor));
        fixedInGroup += 1;
      }

      const duration = getConfigTimelineClipDuration(clip);
      cursor = (clipAtOverrides.get(clip.id) ?? clip.at) + duration;
    }

    if (fixedInGroup > 0) {
      totalFixed += fixedInGroup;
      issues?.push(createIssue(
        level,
        'warning',
        'shot_group_contiguity_repaired',
        `Snapped ${fixedInGroup} non-contiguous clip(s) back into pinned shot group '${group.shotId}'.`,
        {
          path: 'clips',
          trackId: group.trackId,
          repairApplied: true,
          details: { fixedInGroup, shotId: group.shotId, clipIds: [...group.clipIds] },
        },
      ));
    }
  }

  if (totalFixed === 0) {
    return config;
  }

  return {
    ...config,
    clips: config.clips.map((clip) => {
      const override = clipAtOverrides.get(clip.id);
      return override !== undefined ? { ...clip, at: override } : clip;
    }),
    pinnedShotGroups: clonePinnedShotGroups(config.pinnedShotGroups),
  };
};

const canonicalizeNonHoldTrim = (
  clip: TimelineClip,
  level: TimelineDomainContractLevel,
  issues: TimelineDomainIssue[],
  registry?: AssetRegistry,
): TimelineClip => {
  if (isHoldLikeClip(clip) || hasValidNonHoldTrim(clip)) {
    return clip;
  }

  const assetDuration = registry ? getClipAssetDurationSeconds(registry, clip.asset) : null;
  if (assetDuration !== null) {
    issues.push(createIssue(
      level,
      'warning',
      'malformed_non_hold_trim_repaired',
      `Repaired malformed trim for clip '${clip.id}' using registry duration ${assetDuration}s.`,
      {
        clipId: clip.id,
        assetId: clip.asset,
        path: `clips.${clip.id}`,
        repairApplied: true,
        details: { from: 0, to: assetDuration },
      },
    ));
    return {
      ...clip,
      from: 0,
      to: roundTimelineValue(assetDuration),
    };
  }

  issues.push(createIssue(
    level,
    'warning',
    'malformed_non_hold_trim_zero_duration',
    `Clip '${clip.id}' has malformed non-hold trim and no registry duration; canonical duration remains 0s.`,
    {
      clipId: clip.id,
      assetId: clip.asset,
      path: `clips.${clip.id}`,
      repairApplied: false,
      details: {
        from: clip.from,
        to: clip.to,
      },
    },
  ));
  return clip;
};

const withCanonicalClips = (
  config: TimelineConfig,
  clips: TimelineClip[],
): TimelineConfig => ({
  output: { ...config.output },
  tracks: (config.tracks ?? []).map((track) => ({ ...track })),
  clips,
  pinnedShotGroups: clonePinnedShotGroups(config.pinnedShotGroups),
  ...cloneTimelineExtras(config),
});

export const canonicalizeTimelineConfigSnapshot = (
  config: TimelineConfig,
): CanonicalTimelineConfigSnapshot => {
  const issues: TimelineDomainIssue[] = [];
  const repairedConfig = repairConfig(config, issues, 'config-only');
  const contiguousConfig = repairShotGroupContiguity(repairedConfig, issues, 'config-only');
  const migratedConfig = migrateToFlatTracks(contiguousConfig, issues, 'config-only');
  // Repair clip transitions against built-in catalog (no registry snapshot in config-only)
  const transitionRepairedConfig = repairTimelineClipTransitions(
    migratedConfig,
    undefined,
    issues,
    'config-only',
  );
  const canonicalConfig = withCanonicalClips(
    transitionRepairedConfig,
    transitionRepairedConfig.clips.map((clip) => canonicalizeNonHoldTrim(clip, 'config-only', issues)),
  );

  return {
    level: 'config-only',
    config: canonicalConfig,
    issues,
  };
};

export const canonicalizeTimelinePair = (
  config: TimelineConfig,
  registry: AssetRegistry,
): CanonicalTimelinePair => {
  const issues: TimelineDomainIssue[] = [];
  const repairedConfig = repairConfig(config, issues, 'pair-aware');
  const contiguousConfig = repairShotGroupContiguity(repairedConfig, issues, 'pair-aware');
  const migratedConfig = migrateToFlatTracks(contiguousConfig, issues, 'pair-aware');
  // Repair clip transitions against built-in catalog (no registry snapshot in pair-aware)
  const transitionRepairedConfig = repairTimelineClipTransitions(
    migratedConfig,
    undefined,
    issues,
    'pair-aware',
  );
  const canonicalConfig = withCanonicalClips(
    transitionRepairedConfig,
    transitionRepairedConfig.clips.map((clip) => canonicalizeNonHoldTrim(clip, 'pair-aware', issues, registry)),
  );

  return {
    level: 'pair-aware',
    config: canonicalConfig,
    registry: cloneAssetRegistry(registry),
    issues,
  };
};

// ---------------------------------------------------------------------------
// M11 live binding metadata scan / resolution
// ---------------------------------------------------------------------------

export type TimelineLiveBindingDiagnosticSeverity = 'info' | 'warning' | 'error';
export type TimelineLiveBindingDiagnosticCode =
  | 'live-binding/malformed-metadata'
  | 'live-binding/missing-binding-id'
  | 'live-binding/missing-source-id'
  | 'live-binding/missing-source-kind'
  | 'live-binding/unsupported-source-kind'
  | 'live-binding/sample-payload-rejected'
  | 'live-binding/missing-source'
  | 'live-binding/inactive-source'
  | 'live-binding/disposed-source'
  | 'live-binding/orphaned-source'
  | 'live-binding/partially-baked'
  | 'live-binding/resolved';

export interface TimelineLiveBindingDiagnostic {
  severity: TimelineLiveBindingDiagnosticSeverity;
  code: TimelineLiveBindingDiagnosticCode;
  message: string;
  path: string;
  clipId?: string;
  bindingId?: string;
  sourceId?: string;
  details?: Record<string, unknown>;
}

export interface TimelineLiveSourceSnapshot {
  sourceId: string;
  kind: TimelineLiveSourceKind;
  status: TimelineLiveSourceStatus;
  ownerExtensionId?: string;
}

export interface TimelineLiveBindingScanOptions {
  sources?: readonly TimelineLiveSourceSnapshot[];
}

export interface TimelineLiveBindingRecord {
  binding: TimelineLiveBinding;
  clipId: string;
  path: string;
  status: TimelineLiveBindingResolutionStatus;
  diagnostics: readonly TimelineLiveBindingDiagnostic[];
  blocksExport: boolean;
}

export interface TimelineLiveBindingScanResult {
  bindings: readonly TimelineLiveBindingRecord[];
  diagnostics: readonly TimelineLiveBindingDiagnostic[];
  counts: Record<TimelineLiveBindingResolutionStatus, number>;
  hasBlockingLiveBindings: boolean;
}

export type TimelineLiveUniformBindingDiagnosticCode =
  | 'live-uniform-binding/malformed-metadata'
  | 'live-uniform-binding/missing-binding-id'
  | 'live-uniform-binding/missing-source-id'
  | 'live-uniform-binding/missing-source-kind'
  | 'live-uniform-binding/unsupported-source-kind'
  | 'live-uniform-binding/sample-payload-rejected'
  | 'live-uniform-binding/missing-mapping'
  | 'live-uniform-binding/unsupported-mapping-kind'
  | 'live-uniform-binding/missing-uniform'
  | 'live-uniform-binding/invalid-vector-components'
  | 'live-uniform-binding/invalid-fft-bin'
  | 'live-uniform-binding/invalid-deterministic-ref';

export interface TimelineLiveUniformBindingDiagnostic {
  severity: TimelineLiveBindingDiagnosticSeverity;
  code: TimelineLiveUniformBindingDiagnosticCode;
  message: string;
  path: string;
  clipId?: string;
  bindingId?: string;
  sourceId?: string;
  details?: Record<string, unknown>;
}

export interface TimelineLiveUniformBindingRecord {
  binding: TimelineLiveUniformBinding;
  clipId: string;
  path: string;
  diagnostics: readonly TimelineLiveUniformBindingDiagnostic[];
}

export interface TimelineLiveUniformBindingScanResult {
  bindings: readonly TimelineLiveUniformBindingRecord[];
  diagnostics: readonly TimelineLiveUniformBindingDiagnostic[];
}

const SUPPORTED_LIVE_SOURCE_KINDS = new Set<string>([
  'webcam',
  'microphone',
  'midi',
  'serial',
  'bluetooth',
  'generated',
  'screen-capture',
  'audio-device',
  'osc',
  'custom',
]);

const LIVE_SAMPLE_PAYLOAD_KEYS = new Set<string>([
  'sample',
  'samples',
  'samplePayload',
  'sample_payload',
  'frame',
  'frames',
  'payload',
  'ringBuffer',
  'ring_buffer',
  'buffer',
]);

const LIVE_UNIFORM_MAPPING_KINDS = new Set<TimelineLiveUniformBindingMappingKind>([
  'scalar',
  'vector',
  'fft-bin',
  'rms-amplitude',
  'onset-event',
  'frame-ref',
  'material-ref',
]);

const LIVE_UNIFORM_VECTOR_COMPONENTS = new Set(['x', 'y', 'z', 'w']);

const LIVE_BINDING_BLOCKING_STATUSES = new Set<TimelineLiveBindingResolutionStatus>([
  'active',
  'inactive',
  'missing',
  'disposed',
  'orphaned',
  'partiallyBaked',
  'malformed',
]);

const emptyLiveBindingCounts = (): Record<TimelineLiveBindingResolutionStatus, number> => ({
  active: 0,
  inactive: 0,
  missing: 0,
  disposed: 0,
  orphaned: 0,
  partiallyBaked: 0,
  resolved: 0,
  malformed: 0,
});

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
};

const createLiveBindingDiagnostic = (
  severity: TimelineLiveBindingDiagnosticSeverity,
  code: TimelineLiveBindingDiagnosticCode,
  message: string,
  path: string,
  extra: Omit<TimelineLiveBindingDiagnostic, 'severity' | 'code' | 'message' | 'path'> = {},
): TimelineLiveBindingDiagnostic => ({
  severity,
  code,
  message,
  path,
  ...extra,
});

const isTimelineLiveSourceKind = (value: unknown): value is TimelineLiveSourceKind => {
  return typeof value === 'string' && SUPPORTED_LIVE_SOURCE_KINDS.has(value);
};

const isTimelineLiveBindingResolutionStatus = (
  value: unknown,
): value is TimelineLiveBindingResolutionStatus => {
  return (
    value === 'active'
    || value === 'inactive'
    || value === 'missing'
    || value === 'disposed'
    || value === 'orphaned'
    || value === 'partiallyBaked'
    || value === 'resolved'
    || value === 'malformed'
  );
};

const hasForbiddenSamplePayload = (value: unknown): boolean => {
  if (Array.isArray(value)) {
    return value.some(hasForbiddenSamplePayload);
  }

  if (!isRecord(value)) {
    return false;
  }

  for (const [key, child] of Object.entries(value)) {
    if (LIVE_SAMPLE_PAYLOAD_KEYS.has(key)) {
      return true;
    }
    if (hasForbiddenSamplePayload(child)) {
      return true;
    }
  }

  return false;
};

const getBindingArrayCandidates = (
  value: unknown,
): readonly { value: unknown; pathSuffix: string }[] => {
  if (Array.isArray(value)) {
    return [{ value, pathSuffix: '' }];
  }

  if (!isRecord(value)) {
    return [];
  }

  if (Array.isArray(value.bindings)) {
    return [{ value: value.bindings, pathSuffix: '.bindings' }];
  }

  if (Array.isArray(value.liveBindings)) {
    return [{ value: value.liveBindings, pathSuffix: '.liveBindings' }];
  }

  if (typeof value.bindingId === 'string' || typeof value.sourceId === 'string') {
    return [{ value: [value], pathSuffix: '' }];
  }

  return [];
};

const extractLiveBindingCandidates = (
  clip: TimelineClip,
): readonly { value: unknown; path: string }[] => {
  const candidates: { value: unknown; path: string }[] = [];

  const appLive = clip.app?.live;
  if (appLive !== undefined) {
    for (const candidate of getBindingArrayCandidates(appLive)) {
      candidates.push({
        value: candidate.value,
        path: `clips.${clip.id}.app.live${candidate.pathSuffix}`,
      });
    }
    if (candidates.length === 0) {
      candidates.push({ value: appLive, path: `clips.${clip.id}.app.live` });
    }
  }

  const paramsLiveBindings = clip.params?.liveBindings;
  if (paramsLiveBindings !== undefined) {
    candidates.push({ value: paramsLiveBindings, path: `clips.${clip.id}.params.liveBindings` });
  }

  return candidates;
};

const normalizeLiveBinding = (
  rawBinding: unknown,
  clip: TimelineClip,
  path: string,
): { binding?: TimelineLiveBinding; diagnostics: TimelineLiveBindingDiagnostic[] } => {
  const diagnostics: TimelineLiveBindingDiagnostic[] = [];

  if (!isRecord(rawBinding)) {
    diagnostics.push(createLiveBindingDiagnostic(
      'error',
      'live-binding/malformed-metadata',
      `Live binding metadata on clip '${clip.id}' must be an object.`,
      path,
      { clipId: clip.id },
    ));
    return { diagnostics };
  }

  if (hasForbiddenSamplePayload(rawBinding)) {
    diagnostics.push(createLiveBindingDiagnostic(
      'error',
      'live-binding/sample-payload-rejected',
      `Live binding '${String(rawBinding.bindingId ?? path)}' on clip '${clip.id}' contains sample payload data.`,
      path,
      { clipId: clip.id, bindingId: typeof rawBinding.bindingId === 'string' ? rawBinding.bindingId : undefined },
    ));
  }

  const bindingId = rawBinding.bindingId;
  if (typeof bindingId !== 'string' || bindingId.length === 0) {
    diagnostics.push(createLiveBindingDiagnostic(
      'error',
      'live-binding/missing-binding-id',
      `Live binding metadata on clip '${clip.id}' is missing bindingId.`,
      path,
      { clipId: clip.id },
    ));
  }

  const sourceId = rawBinding.sourceId;
  if (typeof sourceId !== 'string' || sourceId.length === 0) {
    diagnostics.push(createLiveBindingDiagnostic(
      'error',
      'live-binding/missing-source-id',
      `Live binding '${typeof bindingId === 'string' ? bindingId : path}' on clip '${clip.id}' is missing sourceId.`,
      path,
      { clipId: clip.id, bindingId: typeof bindingId === 'string' ? bindingId : undefined },
    ));
  }

  const sourceKind = rawBinding.sourceKind ?? rawBinding.kind;
  if (typeof sourceKind !== 'string' || sourceKind.length === 0) {
    diagnostics.push(createLiveBindingDiagnostic(
      'error',
      'live-binding/missing-source-kind',
      `Live binding '${typeof bindingId === 'string' ? bindingId : path}' on clip '${clip.id}' is missing sourceKind.`,
      path,
      {
        clipId: clip.id,
        bindingId: typeof bindingId === 'string' ? bindingId : undefined,
        sourceId: typeof sourceId === 'string' ? sourceId : undefined,
      },
    ));
  } else if (!isTimelineLiveSourceKind(sourceKind)) {
    diagnostics.push(createLiveBindingDiagnostic(
      'error',
      'live-binding/unsupported-source-kind',
      `Live binding '${typeof bindingId === 'string' ? bindingId : path}' references unsupported source kind '${sourceKind}'.`,
      path,
      {
        clipId: clip.id,
        bindingId: typeof bindingId === 'string' ? bindingId : undefined,
        sourceId: typeof sourceId === 'string' ? sourceId : undefined,
        details: { sourceKind },
      },
    ));
  }

  if (
    typeof bindingId !== 'string'
    || bindingId.length === 0
    || typeof sourceId !== 'string'
    || sourceId.length === 0
    || !isTimelineLiveSourceKind(sourceKind)
  ) {
    return { diagnostics };
  }

  const binding: TimelineLiveBinding = {
    ...(rawBinding as Omit<TimelineLiveBinding, 'bindingId' | 'sourceId' | 'sourceKind'>),
    bindingId,
    sourceId,
    sourceKind,
  };

  return { binding, diagnostics };
};

const liveBindingDeterministicRefs = (
  binding: TimelineLiveBinding,
): readonly TimelineLiveDeterministicRef[] => [
  ...(Array.isArray(binding.deterministicRefs) ? binding.deterministicRefs : []),
  ...(Array.isArray(binding.bake?.deterministicRefs) ? binding.bake.deterministicRefs : []),
];

const liveBindingHasUnresolvedRanges = (binding: TimelineLiveBinding): boolean => (
  Array.isArray(binding.bake?.unresolvedRanges) && binding.bake.unresolvedRanges.length > 0
);

const liveBindingHasRangedDeterministicRefs = (binding: TimelineLiveBinding): boolean => (
  liveBindingDeterministicRefs(binding).some((ref) => ref.range !== undefined)
);

const liveBindingHasPartialBake = (binding: TimelineLiveBinding): boolean => {
  return (
    binding.resolutionStatus === 'partiallyBaked'
    || binding.bake?.status === 'partial'
    || liveBindingHasUnresolvedRanges(binding)
    || (liveBindingHasRangedDeterministicRefs(binding) && binding.bake?.status !== 'complete')
  );
};

const liveBindingHasCompleteBake = (binding: TimelineLiveBinding): boolean => {
  return (
    !liveBindingHasPartialBake(binding)
    && (
      binding.resolutionStatus === 'resolved'
      || binding.bake?.status === 'complete'
      || liveBindingDeterministicRefs(binding).length > 0
    )
  );
};

export const resolveTimelineLiveBinding = (
  binding: TimelineLiveBinding,
  sources: readonly TimelineLiveSourceSnapshot[] = [],
): { status: TimelineLiveBindingResolutionStatus; diagnostics: TimelineLiveBindingDiagnostic[] } => {
  const diagnostics: TimelineLiveBindingDiagnostic[] = [];

  if (liveBindingHasPartialBake(binding)) {
    diagnostics.push(createLiveBindingDiagnostic(
      'warning',
      'live-binding/partially-baked',
      `Live binding '${binding.bindingId}' is only partially baked and remains export-blocking.`,
      '',
      {
        bindingId: binding.bindingId,
        sourceId: binding.sourceId,
        details: {
          bakedRanges: binding.bake?.bakedRanges?.length ?? 0,
          unresolvedRanges: binding.bake?.unresolvedRanges?.length ?? 0,
        },
      },
    ));
    return { status: 'partiallyBaked', diagnostics };
  }

  if (liveBindingHasCompleteBake(binding)) {
    diagnostics.push(createLiveBindingDiagnostic(
      'info',
      'live-binding/resolved',
      `Live binding '${binding.bindingId}' has deterministic replacement metadata.`,
      '',
      { bindingId: binding.bindingId, sourceId: binding.sourceId },
    ));
    return { status: 'resolved', diagnostics };
  }

  if (isTimelineLiveBindingResolutionStatus(binding.resolutionStatus)) {
    return { status: binding.resolutionStatus, diagnostics };
  }

  if (binding.sourceStatus === 'disposed' || binding.sourceStatus === 'orphaned') {
    return { status: binding.sourceStatus, diagnostics };
  }

  const source = sources.find((candidate) => candidate.sourceId === binding.sourceId);
  const sourceStatus = source?.status ?? binding.sourceStatus;

  if (!sourceStatus) {
    diagnostics.push(createLiveBindingDiagnostic(
      'warning',
      'live-binding/missing-source',
      `Live binding '${binding.bindingId}' references missing source '${binding.sourceId}'.`,
      '',
      { bindingId: binding.bindingId, sourceId: binding.sourceId },
    ));
    return { status: 'missing', diagnostics };
  }

  if (sourceStatus === 'disposed' || sourceStatus === 'orphaned') {
    diagnostics.push(createLiveBindingDiagnostic(
      'warning',
      sourceStatus === 'disposed' ? 'live-binding/disposed-source' : 'live-binding/orphaned-source',
      `Live binding '${binding.bindingId}' references ${sourceStatus} source '${binding.sourceId}'.`,
      '',
      { bindingId: binding.bindingId, sourceId: binding.sourceId },
    ));
    return { status: sourceStatus, diagnostics };
  }

  if (sourceStatus === 'active') {
    return { status: 'active', diagnostics };
  }

  diagnostics.push(createLiveBindingDiagnostic(
    'warning',
    'live-binding/inactive-source',
    `Live binding '${binding.bindingId}' references inactive source '${binding.sourceId}'.`,
    '',
    { bindingId: binding.bindingId, sourceId: binding.sourceId, details: { sourceStatus } },
  ));
  return { status: 'inactive', diagnostics };
};

export const scanTimelineLiveBindings = (
  config: TimelineConfig,
  options: TimelineLiveBindingScanOptions = {},
): TimelineLiveBindingScanResult => {
  const records: TimelineLiveBindingRecord[] = [];
  const diagnostics: TimelineLiveBindingDiagnostic[] = [];
  const counts = emptyLiveBindingCounts();

  for (const clip of config.clips) {
    for (const candidate of extractLiveBindingCandidates(clip)) {
      if (!Array.isArray(candidate.value)) {
        const diagnostic = createLiveBindingDiagnostic(
          'error',
          'live-binding/malformed-metadata',
          `Live binding metadata on clip '${clip.id}' must be an array or binding object.`,
          candidate.path,
          { clipId: clip.id },
        );
        diagnostics.push(diagnostic);
        counts.malformed += 1;
        records.push({
          binding: {
            bindingId: `${clip.id}:malformed:${records.length}`,
            sourceId: '',
            sourceKind: 'custom',
            resolutionStatus: 'malformed',
          },
          clipId: clip.id,
          path: candidate.path,
          status: 'malformed',
          diagnostics: Object.freeze([diagnostic]),
          blocksExport: true,
        });
        continue;
      }

      candidate.value.forEach((rawBinding, index) => {
        const path = `${candidate.path}.${index}`;
        const normalized = normalizeLiveBinding(rawBinding, clip, path);

        if (!normalized.binding) {
          diagnostics.push(...normalized.diagnostics);
          counts.malformed += 1;
          records.push({
            binding: {
              bindingId: isRecord(rawBinding) && typeof rawBinding.bindingId === 'string'
                ? rawBinding.bindingId
                : `${clip.id}:malformed:${index}`,
              sourceId: isRecord(rawBinding) && typeof rawBinding.sourceId === 'string' ? rawBinding.sourceId : '',
              sourceKind: 'custom',
              resolutionStatus: 'malformed',
            },
            clipId: clip.id,
            path,
            status: 'malformed',
            diagnostics: Object.freeze(normalized.diagnostics),
            blocksExport: true,
          });
          return;
        }

        const resolution = resolveTimelineLiveBinding(normalized.binding, options.sources);
        const recordDiagnostics = [
          ...normalized.diagnostics,
          ...resolution.diagnostics.map((diagnostic) => ({
            ...diagnostic,
            path,
            clipId: clip.id,
          })),
        ];
        diagnostics.push(...recordDiagnostics);
        counts[resolution.status] += 1;
        records.push({
          binding: normalized.binding,
          clipId: clip.id,
          path,
          status: resolution.status,
          diagnostics: Object.freeze(recordDiagnostics),
          blocksExport: LIVE_BINDING_BLOCKING_STATUSES.has(resolution.status),
        });
      });
    }
  }

  return {
    bindings: Object.freeze(records),
    diagnostics: Object.freeze(diagnostics),
    counts,
    hasBlockingLiveBindings: records.some((record) => record.blocksExport),
  };
};

const createLiveUniformBindingDiagnostic = (
  severity: TimelineLiveBindingDiagnosticSeverity,
  code: TimelineLiveUniformBindingDiagnosticCode,
  message: string,
  path: string,
  extra: Omit<TimelineLiveUniformBindingDiagnostic, 'severity' | 'code' | 'message' | 'path'> = {},
): TimelineLiveUniformBindingDiagnostic => ({
  severity,
  code,
  message,
  path,
  ...extra,
});

const getLiveUniformBindingArrayCandidates = (
  value: unknown,
): readonly { value: unknown; pathSuffix: string }[] => {
  if (Array.isArray(value)) return [{ value, pathSuffix: '' }];
  if (!isRecord(value)) return [];
  if (Array.isArray(value.liveUniformBindings)) {
    return [{ value: value.liveUniformBindings, pathSuffix: '.liveUniformBindings' }];
  }
  if (Array.isArray(value.uniformBindings)) {
    return [{ value: value.uniformBindings, pathSuffix: '.uniformBindings' }];
  }
  return [];
};

const extractLiveUniformBindingCandidates = (
  clip: TimelineClip,
): readonly { value: unknown; path: string }[] => {
  const candidates: { value: unknown; path: string }[] = [];

  if (clip.app?.liveUniformBindings !== undefined) {
    candidates.push({ value: clip.app.liveUniformBindings, path: `clips.${clip.id}.app.liveUniformBindings` });
  }

  if (clip.app?.live !== undefined) {
    for (const candidate of getLiveUniformBindingArrayCandidates(clip.app.live)) {
      candidates.push({
        value: candidate.value,
        path: `clips.${clip.id}.app.live${candidate.pathSuffix}`,
      });
    }
  }

  if (clip.params?.liveUniformBindings !== undefined) {
    candidates.push({ value: clip.params.liveUniformBindings, path: `clips.${clip.id}.params.liveUniformBindings` });
  }

  return candidates;
};

const normalizeLiveUniformBinding = (
  rawBinding: unknown,
  clip: TimelineClip,
  path: string,
): { binding?: TimelineLiveUniformBinding; diagnostics: TimelineLiveUniformBindingDiagnostic[] } => {
  const diagnostics: TimelineLiveUniformBindingDiagnostic[] = [];

  if (!isRecord(rawBinding)) {
    diagnostics.push(createLiveUniformBindingDiagnostic(
      'error',
      'live-uniform-binding/malformed-metadata',
      `Live uniform binding metadata on clip '${clip.id}' must be an object.`,
      path,
      { clipId: clip.id },
    ));
    return { diagnostics };
  }

  if (hasForbiddenSamplePayload(rawBinding)) {
    diagnostics.push(createLiveUniformBindingDiagnostic(
      'error',
      'live-uniform-binding/sample-payload-rejected',
      `Live uniform binding '${String(rawBinding.bindingId ?? path)}' on clip '${clip.id}' contains sample payload data.`,
      path,
      { clipId: clip.id, bindingId: typeof rawBinding.bindingId === 'string' ? rawBinding.bindingId : undefined },
    ));
  }

  const bindingId = rawBinding.bindingId;
  if (typeof bindingId !== 'string' || bindingId.length === 0) {
    diagnostics.push(createLiveUniformBindingDiagnostic(
      'error',
      'live-uniform-binding/missing-binding-id',
      `Live uniform binding metadata on clip '${clip.id}' is missing bindingId.`,
      path,
      { clipId: clip.id },
    ));
  }

  const sourceId = rawBinding.sourceId;
  if (typeof sourceId !== 'string' || sourceId.length === 0) {
    diagnostics.push(createLiveUniformBindingDiagnostic(
      'error',
      'live-uniform-binding/missing-source-id',
      `Live uniform binding '${typeof bindingId === 'string' ? bindingId : path}' on clip '${clip.id}' is missing sourceId.`,
      path,
      { clipId: clip.id, bindingId: typeof bindingId === 'string' ? bindingId : undefined },
    ));
  }

  const sourceKind = rawBinding.sourceKind ?? rawBinding.kind;
  if (typeof sourceKind !== 'string' || sourceKind.length === 0) {
    diagnostics.push(createLiveUniformBindingDiagnostic(
      'error',
      'live-uniform-binding/missing-source-kind',
      `Live uniform binding '${typeof bindingId === 'string' ? bindingId : path}' on clip '${clip.id}' is missing sourceKind.`,
      path,
      {
        clipId: clip.id,
        bindingId: typeof bindingId === 'string' ? bindingId : undefined,
        sourceId: typeof sourceId === 'string' ? sourceId : undefined,
      },
    ));
  } else if (!isTimelineLiveSourceKind(sourceKind)) {
    diagnostics.push(createLiveUniformBindingDiagnostic(
      'error',
      'live-uniform-binding/unsupported-source-kind',
      `Live uniform binding '${typeof bindingId === 'string' ? bindingId : path}' references unsupported source kind '${sourceKind}'.`,
      path,
      {
        clipId: clip.id,
        bindingId: typeof bindingId === 'string' ? bindingId : undefined,
        sourceId: typeof sourceId === 'string' ? sourceId : undefined,
        details: { sourceKind },
      },
    ));
  }

  const mapping = rawBinding.mapping;
  if (!isRecord(mapping)) {
    diagnostics.push(createLiveUniformBindingDiagnostic(
      'error',
      'live-uniform-binding/missing-mapping',
      `Live uniform binding '${typeof bindingId === 'string' ? bindingId : path}' is missing mapping metadata.`,
      `${path}.mapping`,
      {
        clipId: clip.id,
        bindingId: typeof bindingId === 'string' ? bindingId : undefined,
        sourceId: typeof sourceId === 'string' ? sourceId : undefined,
      },
    ));
  } else {
    const kind = mapping.kind;
    if (typeof kind !== 'string' || !LIVE_UNIFORM_MAPPING_KINDS.has(kind as TimelineLiveUniformBindingMappingKind)) {
      diagnostics.push(createLiveUniformBindingDiagnostic(
        'error',
        'live-uniform-binding/unsupported-mapping-kind',
        `Live uniform binding '${typeof bindingId === 'string' ? bindingId : path}' has unsupported mapping kind '${String(kind)}'.`,
        `${path}.mapping.kind`,
        {
          clipId: clip.id,
          bindingId: typeof bindingId === 'string' ? bindingId : undefined,
          sourceId: typeof sourceId === 'string' ? sourceId : undefined,
          details: { kind },
        },
      ));
    }

    if (typeof mapping.uniform !== 'string' || mapping.uniform.length === 0) {
      diagnostics.push(createLiveUniformBindingDiagnostic(
        'error',
        'live-uniform-binding/missing-uniform',
        `Live uniform binding '${typeof bindingId === 'string' ? bindingId : path}' mapping is missing uniform.`,
        `${path}.mapping.uniform`,
        {
          clipId: clip.id,
          bindingId: typeof bindingId === 'string' ? bindingId : undefined,
          sourceId: typeof sourceId === 'string' ? sourceId : undefined,
        },
      ));
    }

    if (mapping.kind === 'vector') {
      const components = mapping.components;
      const validComponents = Array.isArray(components)
        && components.length > 0
        && components.length <= 4
        && components.every((component) => (
          typeof component === 'string' && LIVE_UNIFORM_VECTOR_COMPONENTS.has(component)
        ));
      if (!validComponents) {
        diagnostics.push(createLiveUniformBindingDiagnostic(
          'error',
          'live-uniform-binding/invalid-vector-components',
          `Live uniform binding '${typeof bindingId === 'string' ? bindingId : path}' vector mapping has invalid components.`,
          `${path}.mapping.components`,
          {
            clipId: clip.id,
            bindingId: typeof bindingId === 'string' ? bindingId : undefined,
            sourceId: typeof sourceId === 'string' ? sourceId : undefined,
          },
        ));
      }
    }

    if (mapping.kind === 'fft-bin' && (!Number.isInteger(mapping.bin) || Number(mapping.bin) < 0)) {
      diagnostics.push(createLiveUniformBindingDiagnostic(
        'error',
        'live-uniform-binding/invalid-fft-bin',
        `Live uniform binding '${typeof bindingId === 'string' ? bindingId : path}' fft-bin mapping must have a non-negative integer bin.`,
        `${path}.mapping.bin`,
        {
          clipId: clip.id,
          bindingId: typeof bindingId === 'string' ? bindingId : undefined,
          sourceId: typeof sourceId === 'string' ? sourceId : undefined,
        },
      ));
    }

    if (
      (mapping.kind === 'frame-ref' || mapping.kind === 'material-ref')
      && (!isRecord(mapping.ref) || typeof mapping.ref.ref !== 'string' || mapping.ref.ref.length === 0)
    ) {
      diagnostics.push(createLiveUniformBindingDiagnostic(
        'error',
        'live-uniform-binding/invalid-deterministic-ref',
        `Live uniform binding '${typeof bindingId === 'string' ? bindingId : path}' ${mapping.kind} mapping must include a deterministic ref.`,
        `${path}.mapping.ref`,
        {
          clipId: clip.id,
          bindingId: typeof bindingId === 'string' ? bindingId : undefined,
          sourceId: typeof sourceId === 'string' ? sourceId : undefined,
        },
      ));
    }
  }

  if (
    diagnostics.some((diagnostic) => diagnostic.severity === 'error')
    || typeof bindingId !== 'string'
    || bindingId.length === 0
    || typeof sourceId !== 'string'
    || sourceId.length === 0
    || !isTimelineLiveSourceKind(sourceKind)
    || !isRecord(mapping)
    || typeof mapping.kind !== 'string'
    || !LIVE_UNIFORM_MAPPING_KINDS.has(mapping.kind as TimelineLiveUniformBindingMappingKind)
    || typeof mapping.uniform !== 'string'
    || mapping.uniform.length === 0
  ) {
    return { diagnostics };
  }

  return {
    binding: {
      ...(rawBinding as Omit<TimelineLiveUniformBinding, 'bindingId' | 'sourceId' | 'sourceKind'>),
      bindingId,
      sourceId,
      sourceKind,
    },
    diagnostics,
  };
};

export const scanTimelineLiveUniformBindings = (
  config: TimelineConfig,
): TimelineLiveUniformBindingScanResult => {
  const records: TimelineLiveUniformBindingRecord[] = [];
  const diagnostics: TimelineLiveUniformBindingDiagnostic[] = [];

  for (const clip of config.clips) {
    for (const candidate of extractLiveUniformBindingCandidates(clip)) {
      if (!Array.isArray(candidate.value)) {
        const diagnostic = createLiveUniformBindingDiagnostic(
          'error',
          'live-uniform-binding/malformed-metadata',
          `Live uniform binding metadata on clip '${clip.id}' must be an array.`,
          candidate.path,
          { clipId: clip.id },
        );
        diagnostics.push(diagnostic);
        continue;
      }

      candidate.value.forEach((rawBinding, index) => {
        const path = `${candidate.path}.${index}`;
        const normalized = normalizeLiveUniformBinding(rawBinding, clip, path);
        diagnostics.push(...normalized.diagnostics);
        if (!normalized.binding) return;
        records.push({
          binding: normalized.binding,
          clipId: clip.id,
          path,
          diagnostics: Object.freeze(normalized.diagnostics),
        });
      });
    }
  }

  return {
    bindings: Object.freeze(records),
    diagnostics: Object.freeze(diagnostics),
  };
};

// ---------------------------------------------------------------------------
// Transition validation / repair (T14: timeline-domain integration)
// ---------------------------------------------------------------------------

const TRANSITION_CODE_TO_ISSUE_CODE: Partial<Record<string, TimelineDomainIssueCode>> = {
  [TransitionDiagnosticCodes.MISSING_TRANSITION_OBJECT]: 'legacy_transition_cleared',
  [TransitionDiagnosticCodes.MISSING_TYPE]: 'legacy_transition_missing_type',
  [TransitionDiagnosticCodes.INVALID_TYPE]: 'legacy_transition_missing_type',
  [TransitionDiagnosticCodes.UNRESOLVED_TYPE]: 'legacy_transition_unresolvable',
  [TransitionDiagnosticCodes.REMOVED_CONTRIBUTED]: 'legacy_transition_removed_contributed',
  [TransitionDiagnosticCodes.MISSING_PARAMS]: 'legacy_transition_params_repaired',
  [TransitionDiagnosticCodes.INACTIVE_RECORD]: 'legacy_transition_unresolvable',
};

/**
 * Validate and repair clip transitions across a timeline config.
 *
 * Uses the pure validation/repair helpers from
 * `@/tools/video-editor/transitions/validation.ts` to detect malformed legacy
 * transitions, removed contributed transitions, and missing params. Each issue
 * is surfaced as a `TimelineDomainIssue` so consumers can report or repair.
 *
 * **Repair strategy:**
 * - Malformed / missing type / unresolvable → transition is cleared (removed).
 * - Missing params → schema defaults are materialized via `set-transition`.
 * - Valid transitions → left unchanged.
 *
 * Unresolvable transition IDs are **never** silently replaced with a built-in
 * fallback; they are explicitly cleared and the diagnostic is recorded.
 *
 * @param config - The timeline config whose clips may have transitions.
 * @param registrySnapshot - Optional provider-scoped transition registry snapshot
 *   for resolution against contributed transitions.
 * @param issues - Optional mutable array to append TimelineDomainIssue entries.
 * @param level - The contract level for generated issues.
 * @returns A new config with repaired transitions. Returns the original config
 *   unchanged if no transitions needed repair.
 */
export function repairTimelineClipTransitions(
  config: TimelineConfig,
  registrySnapshot?: TransitionRegistrySnapshot,
  issues?: TimelineDomainIssue[],
  level: TimelineDomainContractLevel = 'config-only',
): TimelineConfig {
  let repaired = false;
  let clearedCount = 0;
  let repairedParamsCount = 0;

  const clips: TimelineClip[] = config.clips.map((clip) => {
    const transition = clip.transition as ClipTransition | undefined;

    // Skip clips without a transition
    if (!transition) return clip;

    const validation = validateClipTransition(transition, registrySnapshot);

    // If valid with no issues, skip this clip
    if (validation.isValid && validation.diagnostics.every(
      (d) => d.severity !== 'error' && d.code !== TransitionDiagnosticCodes.MISSING_PARAMS,
    )) {
      return clip;
    }

    const repair = repairClipTransition(transition, registrySnapshot);

    if (repair.action === 'no-op') return clip;

    // Generate timeline-domain issues for each validation diagnostic
    for (const diag of repair.diagnostics) {
      const issueCode: TimelineDomainIssueCode =
        TRANSITION_CODE_TO_ISSUE_CODE[diag.code] ?? 'legacy_transition_unresolvable';

      issues?.push({
        level,
        severity: diag.severity === 'error' ? 'error' : 'warning',
        code: issueCode,
        message: `Clip "${clip.id}": ${diag.message}`,
        clipId: clip.id,
        path: `clips.${clip.id}.transition`,
        repairApplied: repair.action !== 'no-op',
        details: {
          transitionType: transition.type,
          repairAction: repair.action,
          diagnosticCode: diag.code,
          ...(diag.detail ?? {}),
        },
      });
    }

    repaired = true;

    if (repair.action === 'clear-transition') {
      clearedCount += 1;
      // Return clip without the transition
      const { transition: _removed, ...clipWithoutTransition } = clip;
      return clipWithoutTransition as TimelineClip;
    }

    if (repair.action === 'set-transition') {
      repairedParamsCount += 1;
      return {
        ...clip,
        transition: repair.transition as ClipTransition,
      };
    }

    return clip;
  });

  if (clearedCount > 0) {
    issues?.push(createIssue(
      level,
      'warning',
      'legacy_transition_cleared',
      `Cleared ${clearedCount} unresolvable or malformed clip transition(s).`,
      {
        path: 'clips',
        repairApplied: true,
        details: { clearedCount, repairedParamsCount },
      },
    ));
  }

  if (repairedParamsCount > 0 && clearedCount === 0) {
    issues?.push(createIssue(
      level,
      'warning',
      'legacy_transition_params_repaired',
      `Repaired ${repairedParamsCount} clip transition(s) with materialized schema defaults.`,
      {
        path: 'clips',
        repairApplied: true,
        details: { repairedParamsCount },
      },
    ));
  }

  return repaired ? { ...config, clips } : config;
}

export const sanitizeTimelineClipSnapshot = (clip: TimelineClip): TimelineClip => {
  const serializedClip: Partial<Record<TimelineClipField, TimelineClip[TimelineClipField]>> = {
    id: clip.id,
    at: clip.at,
    track: clip.track,
  };

  if (clip.asset !== undefined) {
    serializedClip.asset = clip.asset;
  }

  for (const field of TIMELINE_CLIP_FIELDS) {
    if (field in serializedClip) {
      continue;
    }

    const value = clip[field];
    if (value !== undefined) {
      serializedClip[field] = field === 'app' ? cloneAppExtension(value) : value;
    }
  }

  return serializedClip as TimelineClip;
};

export const sanitizeTrackDefinitionSnapshot = (track: TrackDefinition): TrackDefinition => {
  const serializedTrack: Partial<Record<TrackDefinitionField, TrackDefinition[TrackDefinitionField]>> = {
    id: track.id,
    kind: track.kind,
    label: track.label,
  };

  for (const field of TRACK_DEFINITION_FIELDS) {
    if (field in serializedTrack) {
      continue;
    }

    const value = track[field];
    if (value !== undefined) {
      serializedTrack[field] = field === 'app' ? cloneAppExtension(value) : value;
    }
  }

  return serializedTrack as TrackDefinition;
};

export const sanitizeAssetRegistryEntry = (entry: AssetRegistryEntry): AssetRegistryEntry => {
  const sanitized: Partial<AssetRegistryEntry> = {};
  for (const field of ASSET_REGISTRY_ENTRY_FIELDS) {
    const value = entry[field];
    if (value === undefined) {
      continue;
    }
    if (field === 'metadata') {
      const validated = validateAssetMetadata(value);
      if (validated) {
        sanitized.metadata = validated;
      }
    } else {
      sanitized[field] = value;
    }
  }
  return sanitized as AssetRegistryEntry;
};

const validateSerializedConfig = (
  config: TimelineConfig,
  level: TimelineDomainContractLevel,
): TimelineDomainValidationResult => {
  const issues: TimelineDomainIssue[] = [];

  const topLevelKeys = Object.keys(config);
  for (const key of topLevelKeys) {
    if (!ALLOWED_TOP_LEVEL_KEYS.has(key)) {
      issues.push(createIssue(
        level,
        'error',
        'unexpected_top_level_key',
        `Serialized timeline has unexpected top-level key '${key}'.`,
        { path: key },
      ));
    }
  }

  const allowedClipKeys = new Set<string>(TIMELINE_CLIP_FIELDS);
  for (const clip of config.clips) {
    for (const key of Object.keys(clip)) {
      if (!allowedClipKeys.has(key)) {
        issues.push(createIssue(
          level,
          'error',
          'unexpected_clip_key',
          `Serialized clip '${clip.id}' has unexpected key '${key}'.`,
          {
            clipId: clip.id,
            path: `clips.${clip.id}.${key}`,
          },
        ));
      }
    }
  }

  const allowedTrackKeys = new Set<string>(TRACK_DEFINITION_FIELDS);
  for (const track of config.tracks ?? []) {
    for (const key of Object.keys(track)) {
      if (!allowedTrackKeys.has(key)) {
        issues.push(createIssue(
          level,
          'error',
          'unexpected_track_key',
          `Serialized track '${track.id}' has unexpected key '${key}'.`,
          {
            trackId: track.id,
            path: `tracks.${track.id}.${key}`,
          },
        ));
      }
    }
  }

  const liveBindingValidation = scanTimelineLiveBindings(config);
  for (const diagnostic of liveBindingValidation.diagnostics) {
    if (diagnostic.severity !== 'error') {
      continue;
    }
    const code: TimelineDomainIssueCode =
      diagnostic.code === 'live-binding/missing-binding-id'
        ? 'live_binding_missing_binding_id'
        : diagnostic.code === 'live-binding/missing-source-id'
          ? 'live_binding_missing_source_id'
          : diagnostic.code === 'live-binding/missing-source-kind'
            ? 'live_binding_missing_source_kind'
            : diagnostic.code === 'live-binding/unsupported-source-kind'
              ? 'live_binding_unsupported_source_kind'
              : diagnostic.code === 'live-binding/sample-payload-rejected'
                ? 'live_binding_sample_payload_rejected'
                : 'live_binding_malformed_metadata';
    issues.push(createIssue(
      level,
      'error',
      code,
      diagnostic.message,
      {
        clipId: diagnostic.clipId,
        path: diagnostic.path,
        repairApplied: false,
        details: {
          bindingId: diagnostic.bindingId,
          sourceId: diagnostic.sourceId,
          diagnosticCode: diagnostic.code,
          ...(diagnostic.details ?? {}),
        },
      },
    ));
  }

  return {
    level,
    ok: issues.length === 0,
    issues,
  };
};

export const validateTimelineConfigSnapshot = (config: TimelineConfig): TimelineDomainValidationResult => {
  return validateSerializedConfig(config, 'config-only');
};

export const validateTimelinePair = (
  config: TimelineConfig,
  _registry: AssetRegistry,
): TimelineDomainValidationResult => {
  return validateSerializedConfig(config, 'pair-aware');
};

export const assertValidTimelineConfigSnapshot = (config: TimelineConfig): void => {
  const validation = validateTimelineConfigSnapshot(config);
  if (!validation.ok) {
    throw new TimelineDomainError(validation.level, validation.issues);
  }
};

export const assertValidTimelinePair = (config: TimelineConfig, registry: AssetRegistry): void => {
  const validation = validateTimelinePair(config, registry);
  if (!validation.ok) {
    throw new TimelineDomainError(validation.level, validation.issues);
  }
};

export const serializeTimelineConfigSnapshot = (
  config: TimelineConfig,
): CanonicalTimelineConfigSnapshot => {
  const canonical = canonicalizeTimelineConfigSnapshot(config);
  const validation = validateTimelineConfigSnapshot(canonical.config);
  if (!validation.ok) {
    throw new TimelineDomainError(validation.level, validation.issues);
  }

  return {
    level: 'config-only',
    config: {
      output: { ...canonical.config.output },
      tracks: (canonical.config.tracks ?? []).map(sanitizeTrackDefinitionSnapshot),
      clips: canonical.config.clips.map(sanitizeTimelineClipSnapshot),
      ...(canonical.config.pinnedShotGroups && canonical.config.pinnedShotGroups.length > 0
        ? { pinnedShotGroups: clonePinnedShotGroups(canonical.config.pinnedShotGroups) }
        : {}),
      ...cloneTimelineExtras(canonical.config),
    },
    issues: canonical.issues,
  };
};

export const serializeTimelinePair = (
  config: TimelineConfig,
  registry: AssetRegistry,
): CanonicalTimelinePair => {
  const canonical = canonicalizeTimelinePair(config, registry);
  const validation = validateTimelinePair(canonical.config, canonical.registry);
  if (!validation.ok) {
    throw new TimelineDomainError(validation.level, validation.issues);
  }

  return {
    level: 'pair-aware',
    config: {
      output: { ...canonical.config.output },
      tracks: (canonical.config.tracks ?? []).map(sanitizeTrackDefinitionSnapshot),
      clips: canonical.config.clips.map(sanitizeTimelineClipSnapshot),
      ...(canonical.config.pinnedShotGroups && canonical.config.pinnedShotGroups.length > 0
        ? { pinnedShotGroups: clonePinnedShotGroups(canonical.config.pinnedShotGroups) }
        : {}),
      ...cloneTimelineExtras(canonical.config),
    },
    registry: cloneAssetRegistry(canonical.registry),
    issues: canonical.issues,
  };
};
