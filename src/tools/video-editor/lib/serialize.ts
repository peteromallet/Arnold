import type {
  ResolvedTimelineConfig,
  TimelineClip,
  TimelineConfig,
  TrackDefinition,
} from '@/tools/video-editor/types';

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
  // Sprint 2 schema-lift additions (all optional). Listed here so the
  // serializer survives them on round-trip and the closed-allowlist validator
  // doesn't strip them silently.
  'params',
  'pool_id',
  'clip_order',
  'source_uuid',
  'generation',
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
] as const;

export type TrackDefinitionField = (typeof TRACK_DEFINITION_FIELDS)[number];

export const serializeClipForDisk = (clip: ResolvedTimelineConfig['clips'][number]): TimelineClip => {
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
      serializedClip[field] = value;
    }
  }

  return serializedClip as TimelineClip;
};

export const serializeTrackForDisk = (track: TrackDefinition): TrackDefinition => {
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
      serializedTrack[field] = value;
    }
  }

  return serializedTrack as TrackDefinition;
};

// Sprint 2 schema-lift: tolerate the new optional top-level fields. The
// validator does NOT enforce a clipType registry yet (SD-015 — strict
// validation lands Sprint 5).
const ALLOWED_TOP_LEVEL_KEYS = new Set([
  'output',
  'clips',
  'tracks',
  'pinnedShotGroups',
  'theme',
  'theme_overrides',
  'generation_defaults',
]);

export const validateSerializedConfig = (config: TimelineConfig): void => {
  const topLevelKeys = Object.keys(config);
  const unexpectedKeys = topLevelKeys.filter((key) => !ALLOWED_TOP_LEVEL_KEYS.has(key));
  if (unexpectedKeys.length > 0) {
    throw new Error(`Serialized timeline has unexpected top-level keys: ${unexpectedKeys.join(', ')}`);
  }

  const allowedClipKeys = new Set<string>(TIMELINE_CLIP_FIELDS);
  for (const clip of config.clips) {
    const invalidClipKeys = Object.keys(clip).filter((key) => !allowedClipKeys.has(key));
    if (invalidClipKeys.length > 0) {
      throw new Error(`Serialized clip '${clip.id}' has unexpected keys: ${invalidClipKeys.join(', ')}`);
    }
  }

  const allowedTrackKeys = new Set<string>(TRACK_DEFINITION_FIELDS);
  for (const track of config.tracks ?? []) {
    const invalidTrackKeys = Object.keys(track).filter((key) => !allowedTrackKeys.has(key));
    if (invalidTrackKeys.length > 0) {
      throw new Error(`Serialized track '${track.id}' has unexpected keys: ${invalidTrackKeys.join(', ')}`);
    }
  }
};

export const serializeForDisk = (
  resolved: ResolvedTimelineConfig,
  pinnedShotGroups?: TimelineConfig['pinnedShotGroups'],
  // Sprint 2: optional carry-through of schema-lift top-level fields. Callers
  // that don't pass these keep the prior behavior; existing timelines without
  // them stay unchanged.
  extras?: Pick<TimelineConfig, 'theme' | 'theme_overrides' | 'generation_defaults'>,
): TimelineConfig => {
  const serialized: TimelineConfig = {
    output: { ...resolved.output },
    tracks: resolved.tracks.map(serializeTrackForDisk),
    clips: resolved.clips.map(serializeClipForDisk),
  };

  if (pinnedShotGroups && pinnedShotGroups.length > 0) {
    serialized.pinnedShotGroups = pinnedShotGroups;
  }

  if (extras?.theme !== undefined) {
    serialized.theme = extras.theme;
  }
  if (extras?.theme_overrides !== undefined) {
    serialized.theme_overrides = extras.theme_overrides;
  }
  if (extras?.generation_defaults !== undefined) {
    serialized.generation_defaults = extras.generation_defaults;
  }

  validateSerializedConfig(serialized);
  return serialized;
};
