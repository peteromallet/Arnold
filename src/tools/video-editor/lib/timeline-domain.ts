import type {
  AssetRegistry,
  AssetRegistryEntry,
  ClipContinuous,
  ClipEntrance,
  ClipExit,
  PinnedShotGroup,
  TimelineClip,
  TimelineConfig,
  TrackDefinition,
} from '../types/index.ts';
import { validateAssetMetadata } from './assetMetadata';

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
  | 'unexpected_track_key';

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
  const canonicalConfig = withCanonicalClips(
    migratedConfig,
    migratedConfig.clips.map((clip) => canonicalizeNonHoldTrim(clip, 'config-only', issues)),
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
  const canonicalConfig = withCanonicalClips(
    migratedConfig,
    migratedConfig.clips.map((clip) => canonicalizeNonHoldTrim(clip, 'pair-aware', issues, registry)),
  );

  return {
    level: 'pair-aware',
    config: canonicalConfig,
    registry: cloneAssetRegistry(registry),
    issues,
  };
};

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
