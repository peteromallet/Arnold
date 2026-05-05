import { getClipTimelineDuration } from './config-utils.ts';
import type {
  ResolvedTimelineClip,
  ResolvedTimelineConfig,
  TrackDefinition,
  TrackKind,
} from '@/tools/video-editor/types/index.ts';

const SPLIT_EPSILON = 0.0001;

export const roundTimelineValue = (value: number, digits = 4): number => {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
};

export const clampValue = (value: number, min: number, max: number): number => {
  return Math.min(Math.max(value, min), max);
};

export const getTrackIndex = (tracks: TrackDefinition[], prefix: 'V' | 'A'): number => {
  return tracks.reduce((maxIndex, track) => {
    const match = track.id.match(new RegExp(`^${prefix}(\\d+)$`));
    return match ? Math.max(maxIndex, Number(match[1])) : maxIndex;
  }, 0);
};

export const getVisualTracks = (config: Pick<ResolvedTimelineConfig, 'tracks'>): TrackDefinition[] => {
  return config.tracks.filter((track) => track.kind === 'visual');
};

export const getAudioTracks = (config: Pick<ResolvedTimelineConfig, 'tracks'>): TrackDefinition[] => {
  return config.tracks.filter((track) => track.kind === 'audio');
};

export const getTrackById = (
  config: Pick<ResolvedTimelineConfig, 'tracks'>,
  trackId: string,
): TrackDefinition | null => {
  return config.tracks.find((track) => track.id === trackId) ?? null;
};

export const isTrackMuted = (track: TrackDefinition): boolean => {
  return track.muted === true || (track.volume ?? 1) <= 0;
};

export const toggleTrackMute = (
  config: ResolvedTimelineConfig,
  trackId: string,
): ResolvedTimelineConfig => {
  return {
    ...config,
    tracks: config.tracks.map((track) =>
      track.id === trackId ? { ...track, muted: !isTrackMuted(track) } : track
    ),
  };
};

export const setTrackVolume = (
  config: ResolvedTimelineConfig,
  trackId: string,
  volume: number,
): ResolvedTimelineConfig => {
  return {
    ...config,
    tracks: config.tracks.map((track) =>
      track.id === trackId ? { ...track, volume } : track
    ),
  };
};

export const addTrack = (
  config: ResolvedTimelineConfig,
  kind: TrackKind,
  index?: number,
): ResolvedTimelineConfig => {
  const prefix = kind === 'visual' ? 'V' : 'A';
  const nextNumber = getTrackIndex(config.tracks, prefix) + 1;
  const nextTrack: TrackDefinition = {
    id: `${prefix}${nextNumber}`,
    kind,
    label: `${prefix}${nextNumber}`,
    scale: 1,
    fit: kind === 'visual' ? 'manual' : 'contain',
    opacity: 1,
    blendMode: 'normal',
  };

  const nextTracks = [...config.tracks];
  if (index === undefined || index < 0 || index > nextTracks.length) {
    nextTracks.push(nextTrack);
  } else {
    nextTracks.splice(index, 0, nextTrack);
  }

  return {
    ...config,
    tracks: nextTracks,
  };
};

export const removeTrack = (
  config: ResolvedTimelineConfig,
  trackId: string,
): ResolvedTimelineConfig => {
  const clips = config.clips.filter((clip) => clip.track !== trackId);
  return {
    ...config,
    tracks: config.tracks.filter((track) => track.id !== trackId),
    clips,
  };
};

export const reorderTracks = (
  config: ResolvedTimelineConfig,
  fromIndex: number,
  toIndex: number,
): ResolvedTimelineConfig => {
  if (
    fromIndex < 0
    || fromIndex >= config.tracks.length
    || toIndex < 0
    || toIndex >= config.tracks.length
    || fromIndex === toIndex
  ) {
    return config;
  }

  const nextTracks = [...config.tracks];
  const [track] = nextTracks.splice(fromIndex, 1);
  nextTracks.splice(toIndex, 0, track);
  return {
    ...config,
    tracks: nextTracks,
  };
};

export const isHoldClip = (clip: ResolvedTimelineClip): boolean => {
  return typeof clip.hold === 'number';
};

export const getClipEndSeconds = (clip: ResolvedTimelineClip): number => {
  return clip.at + getClipTimelineDuration(clip);
};

export const findClipById = (
  config: ResolvedTimelineConfig,
  clipId: string,
): ResolvedTimelineClip | null => {
  return config.clips.find((clip) => clip.id === clipId) ?? null;
};

export const updateClipInConfig = (
  config: ResolvedTimelineConfig,
  clipId: string,
  updater: (clip: ResolvedTimelineClip) => ResolvedTimelineClip,
): ResolvedTimelineConfig => {
  let didUpdate = false;
  const clips = config.clips.map((clip) => {
    if (clip.id !== clipId) {
      return clip;
    }

    didUpdate = true;
    return updater(clip);
  });

  return didUpdate ? { ...config, clips } : config;
};

export const getClipVolume = (clip: ResolvedTimelineClip): number => {
  return clip.volume ?? 1;
};

export const isClipMuted = (clip: ResolvedTimelineClip): boolean => {
  return getClipVolume(clip) <= 0;
};

export const toggleClipMute = (
  config: ResolvedTimelineConfig,
  clipId: string,
): ResolvedTimelineConfig => {
  return updateClipInConfig(config, clipId, (clip) => ({
    ...clip,
    volume: isClipMuted(clip) ? 1 : 0,
  }));
};

export const detachAudioFromVideo = (
  config: ResolvedTimelineConfig,
  clipId: string,
): ResolvedTimelineConfig => {
  const clip = findClipById(config, clipId);
  if (!clip || isClipMuted(clip) || !clip.asset || !clip.assetEntry?.src) {
    return config;
  }

  const sourceTrack = getTrackById(config, clip.track);
  if (!sourceTrack || sourceTrack.kind !== 'visual' || !clip.assetEntry.type?.startsWith('video/')) {
    return config;
  }

  const originalVolume = getClipVolume(clip);
  const mutedConfig = updateClipInConfig(config, clipId, (currentClip) => ({
    ...currentClip,
    volume: 0,
  }));

  const existingAudioTrack = mutedConfig.tracks.find((track) => track.kind === 'audio' && /^A\d+$/.test(track.id))
    ?? mutedConfig.tracks.find((track) => track.kind === 'audio')
    ?? null;

  let nextConfig = mutedConfig;
  let destinationTrack = existingAudioTrack;

  if (!destinationTrack) {
    const previousTrackIds = new Set(mutedConfig.tracks.map((track) => track.id));
    nextConfig = addTrack(mutedConfig, 'audio');
    destinationTrack = nextConfig.tracks.find((track) => !previousTrackIds.has(track.id)) ?? null;
  }

  if (!destinationTrack) {
    return config;
  }

  const detachedClip: ResolvedTimelineClip = {
    id: createSplitClipId(
      nextConfig.clips.map((entry) => entry.id),
      clip.id,
    ),
    at: clip.at,
    track: destinationTrack.id,
    clipType: clip.clipType,
    asset: clip.asset,
    assetEntry: clip.assetEntry,
    from: clip.from,
    to: clip.to,
    speed: clip.speed,
    volume: originalVolume,
  };

  return {
    ...nextConfig,
    clips: [...nextConfig.clips, detachedClip],
  };
};

/** Whether a URL or MIME type represents a media asset openable in the lightbox. */
export function isOpenableAssetType(type: string | undefined, url: string | undefined): boolean {
  if (typeof type === 'string' && (type.startsWith('video/') || type.startsWith('image/'))) {
    return true;
  }

  if (!url) {
    return false;
  }

  return /\.(mp4|mov|webm|m4v|png|jpe?g|webp|gif|avif)(\?.*)?$/i.test(url);
}

export const canSplitClipAtTime = (clip: ResolvedTimelineClip, playheadSeconds: number): boolean => {
  return playheadSeconds > clip.at + SPLIT_EPSILON && playheadSeconds < getClipEndSeconds(clip) - SPLIT_EPSILON;
};

export const createSplitClipId = (
  existingIds: string[],
  originalId: string,
  timestamp = Date.now(),
): string => {
  const used = new Set(existingIds);
  let suffix = 0;

  while (true) {
    const candidate = suffix === 0 ? `${originalId}-${timestamp}` : `${originalId}-${timestamp}-${suffix}`;
    if (!used.has(candidate)) {
      return candidate;
    }

    suffix += 1;
  }
};

export const splitClipAtPlayhead = (
  config: ResolvedTimelineConfig,
  clipId: string,
  playheadSeconds: number,
): { config: ResolvedTimelineConfig; nextSelectedClipId: string | null } => {
  const clipIndex = config.clips.findIndex((clip) => clip.id === clipId);
  if (clipIndex < 0) {
    return { config, nextSelectedClipId: null };
  }

  const clip = config.clips[clipIndex];
  if (!canSplitClipAtTime(clip, playheadSeconds)) {
    return { config, nextSelectedClipId: null };
  }

  const nextSelectedClipId = createSplitClipId(
    config.clips.map((entry) => entry.id),
    clip.id,
  );

  let leftClip: ResolvedTimelineClip;
  let rightClip: ResolvedTimelineClip;

  if (isHoldClip(clip)) {
    const elapsed = roundTimelineValue(playheadSeconds - clip.at);
    const remaining = roundTimelineValue((clip.hold ?? 0) - elapsed);

    leftClip = {
      ...clip,
      hold: elapsed,
    };
    rightClip = {
      ...clip,
      id: nextSelectedClipId,
      at: roundTimelineValue(playheadSeconds),
      hold: remaining,
    };
  } else {
    const speed = clip.speed ?? 1;
    const clipFrom = clip.from ?? 0;
    const splitSource = roundTimelineValue(clipFrom + (playheadSeconds - clip.at) * speed);

    leftClip = {
      ...clip,
      to: splitSource,
    };
    rightClip = {
      ...clip,
      id: nextSelectedClipId,
      at: roundTimelineValue(playheadSeconds),
      from: splitSource,
    };
  }

  const clips = [...config.clips];
  clips.splice(clipIndex, 1, leftClip, rightClip);
  return {
    config: {
      ...config,
      clips,
    },
    nextSelectedClipId,
  };
};
