import { getClipTimelineDuration } from './config-utils';
import type {
  ClipContinuous,
  ClipEntrance,
  ClipExit,
  PinnedShotGroup,
  TimelineClip,
  TimelineConfig,
  TrackDefinition,
} from '@/tools/video-editor/types';

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

const roundTimelineValue = (value: number, digits = 4): number => {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
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

const getTimelineEndSeconds = (config: TimelineConfig): number => {
  return Math.max(
    0,
    ...config.clips.map((clip) => clip.at + getClipTimelineDuration(clip)),
  );
};

const ensureBackgroundClip = (config: TimelineConfig): TimelineClip[] => {
  const backgroundAsset = config.output.background;
  if (!backgroundAsset) {
    return config.clips.map(migrateLegacyClip);
  }

  const migratedClips = config.clips.map(migrateLegacyClip);
  const alreadyPresent = migratedClips.some((clip) => clip.track === 'V1');
  if (alreadyPresent) {
    return migratedClips;
  }

  const timelineDuration = Math.max(0.1, roundTimelineValue(getTimelineEndSeconds(config)));
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

const clonePinnedShotImageSnapshots = (
  imageClipSnapshot: PinnedShotGroup['imageClipSnapshot'],
): PinnedShotGroup['imageClipSnapshot'] => imageClipSnapshot?.map((snapshot) => ({
  ...snapshot,
  meta: { ...snapshot.meta },
}));

const clonePinnedShotGroups = (
  pinnedShotGroups: TimelineConfig['pinnedShotGroups'],
): TimelineConfig['pinnedShotGroups'] => pinnedShotGroups?.map((group) => ({
  shotId: group.shotId,
  trackId: group.trackId,
  clipIds: [...group.clipIds],
  mode: group.mode,
  videoAssetKey: group.videoAssetKey,
  imageClipSnapshot: clonePinnedShotImageSnapshots(group.imageClipSnapshot),
}));

const cloneTimelineExtras = (
  config: TimelineConfig,
): Pick<TimelineConfig, 'theme' | 'theme_overrides' | 'generation_defaults'> => ({
  ...(config.theme !== undefined ? { theme: config.theme } : {}),
  ...(config.theme_overrides !== undefined ? { theme_overrides: config.theme_overrides } : {}),
  ...(config.generation_defaults !== undefined ? { generation_defaults: config.generation_defaults } : {}),
});

/**
 * Cheap structural migration — runs on every edit.
 * Ensures tracks exist, clips have clipType. No dedup, no repair.
 */
export const migrateToFlatTracks = (config: TimelineConfig): TimelineConfig => {
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

  return {
    output: { ...config.output },
    tracks: getDefaultTracks(config),
    clips: ensureBackgroundClip(config),
    pinnedShotGroups: clonePinnedShotGroups(config.pinnedShotGroups),
    ...cloneTimelineExtras(config),
  };
};

const CONTIGUITY_EPSILON = 0.001;

/**
 * Repair non-contiguous clips within pinned shot groups.
 * Runs once on load (not on every edit). For each shot group, orders its clips
 * by timeline position and snaps each subsequent clip's `at` so it starts
 * exactly where the previous clip ends — preserving each clip's duration.
 * Returns the original config unchanged when no repairs are needed.
 */
export const repairShotGroupContiguity = (config: TimelineConfig): TimelineConfig => {
  if (!config.pinnedShotGroups?.length) return config;

  const clipById = new Map<string, TimelineClip>();
  for (const clip of config.clips) {
    clipById.set(clip.id, clip);
  }

  let totalFixed = 0;
  // Track which clip ids need their `at` updated, and to what value
  const clipAtOverrides = new Map<string, number>();

  for (const group of config.pinnedShotGroups) {
    if (group.clipIds.length < 2) continue;

    // Resolve clips in the group's declared order
    const groupClips: TimelineClip[] = [];
    for (const clipId of group.clipIds) {
      const clip = clipById.get(clipId);
      if (clip) groupClips.push(clip);
    }
    if (groupClips.length < 2) continue;

    // Sort by current timeline position to handle any ordering quirks
    groupClips.sort((a, b) => a.at - b.at);

    let fixedInGroup = 0;
    let cursor = groupClips[0].at + getClipTimelineDuration(groupClips[0]);

    for (let i = 1; i < groupClips.length; i++) {
      const clip = groupClips[i];
      const gap = Math.abs(clip.at - cursor);

      if (gap > CONTIGUITY_EPSILON) {
        clipAtOverrides.set(clip.id, roundTimelineValue(cursor));
        fixedInGroup++;
      }

      // Advance cursor by this clip's duration regardless
      const duration = getClipTimelineDuration(clip);
      cursor = (clipAtOverrides.get(clip.id) ?? clip.at) + duration;
    }

    if (fixedInGroup > 0) {
      console.warn(
        `[timeline-repair] Fixed ${fixedInGroup} non-contiguous clips in shot group ${group.shotId}`,
      );
      totalFixed += fixedInGroup;
    }
  }

  if (totalFixed === 0) return config;

  // Apply overrides immutably
  const nextClips = config.clips.map((clip) => {
    const override = clipAtOverrides.get(clip.id);
    return override !== undefined ? { ...clip, at: override } : clip;
  });

  return { ...config, clips: nextClips, pinnedShotGroups: config.pinnedShotGroups };
};

/** Strip cascading `-dup-N` suffixes from a clip id back to its base. */
const stripDupSuffix = (id: string): string => id.replace(/(-dup-\d+)+$/, '');

/**
 * Repair corrupted server configs — runs once on load, NOT on every edit.
 * Deduplicates tracks by id, deduplicates clips by base id (stripping
 * cascading -dup- suffixes), and logs what it fixed.
 */
export const repairConfig = (config: TimelineConfig): TimelineConfig => {
  let repaired = false;

  // Deduplicate tracks by id
  const seenTracks = new Set<string>();
  const tracks = (config.tracks ?? []).filter((track) => {
    if (seenTracks.has(track.id)) {
      repaired = true;
      return false;
    }
    seenTracks.add(track.id);
    return true;
  });

  // Deduplicate clips: strip -dup- suffixes, keep first occurrence of each base id
  const seenClips = new Set<string>();
  const clips: TimelineClip[] = [];
  for (const clip of config.clips) {
    const baseId = stripDupSuffix(clip.id);
    if (seenClips.has(baseId)) {
      repaired = true;
      continue;
    }
    seenClips.add(baseId);
    clips.push(baseId !== clip.id ? { ...clip, id: baseId } : clip);
  }

  const pinnedShotGroups = config.pinnedShotGroups?.map((group) => {
    const legacy = group as LegacyPinnedShotGroup;
    const hasLegacyFields
      = typeof legacy.start === 'number'
      || Array.isArray(legacy.children);

    if (!hasLegacyFields) {
      return group;
    }

    repaired = true;
    // Derive soft-tag clipIds from legacy children when present; otherwise preserve
    // the existing clipIds array. Clip positions are already correct in `clips[]`
    // because the prior projection model wrote them back on every commit.
    const derivedClipIds = Array.isArray(legacy.children) && legacy.children.length > 0
      ? legacy.children.map((child) => child.clipId).filter((id): id is string => typeof id === 'string' && id.length > 0)
      : [...group.clipIds];

    const softTagGroup: PinnedShotGroup = {
      shotId: group.shotId,
      trackId: group.trackId,
      clipIds: derivedClipIds,
      mode: group.mode,
      videoAssetKey: group.videoAssetKey,
      imageClipSnapshot: clonePinnedShotImageSnapshots(group.imageClipSnapshot),
    };
    return softTagGroup;
  });

  if (repaired) {
    console.warn(
      '[timeline] repairConfig: fixed corrupted data —',
      'tracks:', config.tracks?.length, '→', tracks.length,
      'clips:', config.clips.length, '→', clips.length,
    );
  }

  return repaired
    ? { ...config, tracks, clips, pinnedShotGroups }
    : config;
};
