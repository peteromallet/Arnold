import type {
  ResolvedTimelineConfig,
  TimelineClip,
  TimelineConfig,
  TrackDefinition,
} from '@/tools/video-editor/types/index.ts';
import {
  assertValidTimelineConfigSnapshot,
  cloneAppExtension,
  sanitizeTimelineClipSnapshot,
  sanitizeTrackDefinitionSnapshot,
} from './timeline-domain.ts';

export {
  TIMELINE_CLIP_FIELDS,
  TRACK_DEFINITION_FIELDS,
  type TimelineClipField,
  type TrackDefinitionField,
} from './timeline-domain.ts';

export const serializeClipForDisk = (clip: ResolvedTimelineConfig['clips'][number]): TimelineClip => {
  return sanitizeTimelineClipSnapshot(clip);
};

export const serializeTrackForDisk = (track: TrackDefinition): TrackDefinition => {
  return sanitizeTrackDefinitionSnapshot(track);
};

export const validateSerializedConfig = (config: TimelineConfig): void => {
  assertValidTimelineConfigSnapshot(config);
};

export const serializeForDisk = (
  resolved: ResolvedTimelineConfig,
  pinnedShotGroups?: TimelineConfig['pinnedShotGroups'],
  // Sprint 2: optional carry-through of schema-lift top-level fields. Callers
  // that don't pass these keep the prior behavior; existing timelines without
  // them stay unchanged.
  extras?: Pick<TimelineConfig, 'theme' | 'theme_overrides' | 'generation_defaults' | 'app'>,
): TimelineConfig => {
  const resolvedExtras = extras ?? resolved;
  const serialized: TimelineConfig = {
    output: { ...resolved.output },
    tracks: resolved.tracks.map(serializeTrackForDisk),
    clips: resolved.clips.map(serializeClipForDisk),
  };

  if (pinnedShotGroups && pinnedShotGroups.length > 0) {
    serialized.pinnedShotGroups = pinnedShotGroups;
  }

  if (resolvedExtras.theme !== undefined) {
    serialized.theme = resolvedExtras.theme;
  }
  if (resolvedExtras.theme_overrides !== undefined) {
    serialized.theme_overrides = resolvedExtras.theme_overrides;
  }
  if (resolvedExtras.generation_defaults !== undefined) {
    serialized.generation_defaults = resolvedExtras.generation_defaults;
  }
  if (resolvedExtras.app !== undefined) {
    serialized.app = cloneAppExtension(resolvedExtras.app);
  }

  validateSerializedConfig(serialized);
  return serialized;
};
