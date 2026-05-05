import { generateUUID } from '@/shared/lib/taskCreation/ids.ts';
import {
  findNearestFreeTrack,
  getCompatibleTrackId,
  trySnapToEdge,
  updateClipOrder,
} from '@/tools/video-editor/lib/coordinate-utils.ts';
import { getTrackIndex } from '@/tools/video-editor/lib/editor-utils.ts';
import { getNextClipId, type ClipMeta, type TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import {
  getDuplicateGenerationDurationContract,
  readPositiveDurationSeconds,
} from '@/tools/video-editor/lib/timeline-asset-durations.ts';
import type { AssetRegistryEntry, ClipType } from '@/tools/video-editor/types/index.ts';
import type { TimelineAction } from '@/tools/video-editor/types/timeline-canvas.ts';

export type PlannedGenerationAssetRegistration =
  | {
      ok: true;
      assetId: string;
      assetEntry: AssetRegistryEntry;
      sourceUrl: string;
    }
  | {
      ok: false;
      error: 'missing_media_url';
    };

export type PlannedAssetDropTarget =
  | {
      ok: true;
      current: TimelineData;
      preparedCurrent: TimelineData;
      trackId: string;
      snappedTime?: number;
    }
  | {
      ok: false;
      error: 'missing_timeline';
    };

export function getPlayableAssetKind(assetEntry: AssetRegistryEntry | undefined): 'image' | 'video' | 'audio' | null {
  const mimeType = assetEntry?.type?.toLowerCase() ?? '';
  const file = (assetEntry?.file ?? assetEntry?.src ?? '').toLowerCase();

  if (mimeType.startsWith('image/') || /\.(png|jpe?g|gif|webp|avif|svg)$/i.test(file)) {
    return 'image';
  }
  if (mimeType.startsWith('video/') || /\.(mp4|mov|webm|m4v)$/i.test(file)) {
    return 'video';
  }
  if (mimeType.startsWith('audio/') || /\.(mp3|wav|aac|m4a|ogg|flac)$/i.test(file)) {
    return 'audio';
  }

  return null;
}

export function estimateAssetDuration(
  assetEntry: AssetRegistryEntry | undefined,
  assetKind: 'audio' | 'visual',
): number {
  if (assetKind === 'audio') return assetEntry?.duration ?? 10;
  if (assetEntry?.type?.startsWith('image')) return 5;
  return assetEntry?.duration ?? 5;
}

export function planGenerationAssetRegistration({
  assetId,
  generationId,
  variantId,
  variantType,
  imageUrl,
  thumbUrl,
  metadata,
  assetDurationSeconds,
}: {
  assetId?: string;
  generationId: string;
  variantId?: string;
  variantType?: string;
  imageUrl: string;
  thumbUrl?: string | null;
  metadata?: Record<string, unknown> | null | undefined;
  assetDurationSeconds?: number | null;
}): PlannedGenerationAssetRegistration {
  if (!imageUrl) {
    return { ok: false, error: 'missing_media_url' };
  }

  const lowerImageUrl = imageUrl.toLowerCase();
  const metadataContentType = typeof metadata?.content_type === 'string'
    ? metadata.content_type.toLowerCase()
    : null;
  const mimeType = (() => {
    if (metadataContentType?.includes('/')) {
      return metadataContentType;
    }
    if (metadataContentType === 'video' || variantType === 'video' || /\.(mp4|mov|webm|m4v)$/i.test(lowerImageUrl)) {
      return 'video/mp4';
    }
    if (metadataContentType === 'audio' || /\.(mp3|wav|aac|m4a|ogg|flac)$/i.test(lowerImageUrl)) {
      return 'audio/mpeg';
    }
    if (/\.(txt|json|md|csv|vtt|srt|pdf)$/i.test(lowerImageUrl)) {
      return metadataContentType?.includes('/') ? metadataContentType : 'application/octet-stream';
    }
    return 'image/png';
  })();

  const normalizedDuration = readPositiveDurationSeconds(assetDurationSeconds);
  const resolvedThumbUrl = thumbUrl || imageUrl;
  return {
    ok: true,
    assetId: assetId ?? generateUUID(),
    sourceUrl: imageUrl,
    assetEntry: {
      file: imageUrl,
      type: mimeType,
      ...(normalizedDuration !== null ? { duration: normalizedDuration } : {}),
      generationId,
      ...(variantId ? { variantId } : {}),
      ...(resolvedThumbUrl !== imageUrl ? { thumbnailUrl: resolvedThumbUrl } : {}),
    },
  };
}

export function planDuplicateGenerationAssetRegistration({
  assetId,
  generationId,
  variantId,
  variantType,
  imageUrl,
  thumbUrl,
  sourceAssetEntry,
}: {
  assetId?: string;
  generationId: string;
  variantId?: string;
  variantType: 'image' | 'video';
  imageUrl: string;
  thumbUrl?: string | null;
  sourceAssetEntry: AssetRegistryEntry | undefined;
}): PlannedGenerationAssetRegistration {
  const durationContract = getDuplicateGenerationDurationContract(sourceAssetEntry);
  return planGenerationAssetRegistration({
    assetId,
    generationId,
    variantId,
    variantType,
    imageUrl,
    thumbUrl,
    assetDurationSeconds: durationContract.assetDurationSeconds,
    metadata: {
      content_type: sourceAssetEntry?.type ?? (variantType === 'video' ? 'video/mp4' : 'image/png'),
    },
  });
}

export function planFinalVideoGenerationAssetRegistration({
  assetId,
  generationId,
  imageUrl,
  thumbUrl,
  assetDurationSeconds,
}: {
  assetId?: string;
  generationId: string;
  imageUrl: string;
  thumbUrl?: string | null;
  assetDurationSeconds: number | null;
}): PlannedGenerationAssetRegistration {
  return planGenerationAssetRegistration({
    assetId,
    generationId,
    variantType: 'video',
    imageUrl,
    thumbUrl,
    assetDurationSeconds,
    metadata: {
      content_type: 'video/mp4',
    },
  });
}

export function executeGenerationAssetRegistrationPlan({
  plan,
  patchRegistry,
  registerAsset,
}: {
  plan: Extract<PlannedGenerationAssetRegistration, { ok: true }>;
  patchRegistry: (assetId: string, entry: AssetRegistryEntry, src?: string) => void;
  registerAsset: (assetId: string, entry: AssetRegistryEntry) => Promise<unknown>;
}): { assetKey: string; persistPromise: Promise<unknown> } {
  patchRegistry(plan.assetId, plan.assetEntry, plan.sourceUrl);
  return {
    assetKey: plan.assetId,
    persistPromise: registerAsset(plan.assetId, plan.assetEntry),
  };
}

export function planAssetDropTarget({
  current,
  assetKind,
  trackId,
  selectedTrackId,
  forceNewTrack = false,
  insertAtTop = false,
  time,
  duration,
}: {
  current: TimelineData | null;
  assetKind: 'audio' | 'visual';
  trackId: string | undefined;
  selectedTrackId: string | null;
  forceNewTrack?: boolean;
  insertAtTop?: boolean;
  time?: number;
  duration?: number;
}): PlannedAssetDropTarget {
  if (!current) {
    return { ok: false, error: 'missing_timeline' };
  }

  let resolvedTrackId = forceNewTrack
    ? null
    : getCompatibleTrackId(current.tracks, trackId, assetKind, selectedTrackId);

  if (resolvedTrackId && time != null && duration != null) {
    const snapResult = trySnapToEdge(current.rows, resolvedTrackId, time, duration);
    if (snapResult.snapped) {
      return { ok: true, current, preparedCurrent: current, trackId: resolvedTrackId, snappedTime: snapResult.time };
    }
    resolvedTrackId = findNearestFreeTrack(
      current.tracks,
      current.rows,
      resolvedTrackId,
      assetKind,
      time,
      duration,
    );
  }

  if (resolvedTrackId) {
    return { ok: true, current, preparedCurrent: current, trackId: resolvedTrackId };
  }

  const prefix = assetKind === 'audio' ? 'A' : 'V';
  const nextNumber = getTrackIndex(current.tracks, prefix) + 1;
  resolvedTrackId = `${prefix}${nextNumber}`;
  const newTrack = {
    id: resolvedTrackId,
    kind: assetKind,
    label: `${prefix}${nextNumber}`,
  };
  const nextRow = { id: resolvedTrackId, actions: [] };
  const preparedCurrent = {
    ...current,
    tracks: insertAtTop ? [newTrack, ...current.tracks] : [...current.tracks, newTrack],
    rows: insertAtTop ? [nextRow, ...current.rows] : [...current.rows, nextRow],
  };
  return {
    ok: true,
    current,
    preparedCurrent,
    trackId: resolvedTrackId,
  };
}

export interface BuildAssetDropEditResult {
  clipId: string;
  duration: number;
  rows: TimelineData['rows'];
  metaUpdates: Record<string, ClipMeta>;
  clipOrderOverride: TimelineData['clipOrder'];
}

export function buildAssetDropEdit({
  current,
  assetKey,
  assetEntry,
  trackId,
  time,
  clipSpanSeconds,
}: {
  current: TimelineData;
  assetKey: string;
  assetEntry?: AssetRegistryEntry;
  trackId: string;
  time: number;
  clipSpanSeconds?: number | null;
}): BuildAssetDropEditResult | null {
  const resolvedAssetEntry = assetEntry ?? current.registry.assets[assetKey];
  const playableKind = getPlayableAssetKind(resolvedAssetEntry);
  if (!resolvedAssetEntry || !playableKind) {
    return null;
  }
  const track = current.tracks.find((candidate) => candidate.id === trackId);
  if (!track) {
    return null;
  }
  if (track.kind === 'visual' && playableKind === 'audio') {
    return null;
  }
  if (track.kind === 'audio' && playableKind === 'image') {
    return null;
  }

  const resolvedClipSpanSeconds = readPositiveDurationSeconds(clipSpanSeconds);
  const clipId = getNextClipId(current.meta);
  const isImage = playableKind === 'image';
  const isVideo = playableKind === 'video';
  const isManual = track.fit === 'manual';
  const clipType: ClipType = isImage ? 'hold' : 'media';
  const defaultDuration = isVideo
    ? (resolvedAssetEntry.duration ?? 5)
    : isImage
      ? 5
      : Math.max(1, resolvedAssetEntry.duration ?? 5);

  let clipMeta: ClipMeta;
  let duration = resolvedClipSpanSeconds ?? defaultDuration;

  if (track.kind === 'audio') {
    duration = resolvedClipSpanSeconds ?? resolvedAssetEntry.duration ?? 10;
    clipMeta = {
      asset: assetKey,
      track: trackId,
      clipType: 'media',
      from: 0,
      to: duration,
      speed: 1,
      volume: 1,
    };
  } else if (isImage) {
    duration = 5;
    clipMeta = {
      asset: assetKey,
      track: trackId,
      clipType,
      hold: duration,
      opacity: 1,
      x: isManual ? 100 : undefined,
      y: isManual ? 100 : undefined,
      width: isManual ? 320 : undefined,
      height: isManual ? 240 : undefined,
    };
  } else {
    clipMeta = {
      asset: assetKey,
      track: trackId,
      clipType,
      from: 0,
      to: duration,
      speed: 1,
      volume: 1,
      opacity: 1,
      x: isManual ? 100 : undefined,
      y: isManual ? 100 : undefined,
      width: isManual ? 320 : undefined,
      height: isManual ? 240 : undefined,
    };
  }

  const action: TimelineAction = {
    id: clipId,
    start: time,
    end: time + duration,
    effectId: `effect-${clipId}`,
  };

  return {
    clipId,
    duration,
    rows: current.rows.map((row) => (row.id === trackId ? { ...row, actions: [...row.actions, action] } : row)),
    metaUpdates: { [clipId]: clipMeta },
    clipOrderOverride: updateClipOrder(current.clipOrder, trackId, (ids) => [...ids, clipId]),
  };
}
