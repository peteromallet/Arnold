import { extractVideoMetadataFromUrl } from '@/shared/lib/media/videoMetadata.ts';
import { asRecord } from '@/shared/lib/jsonNarrowing.ts';
import type { AssetRegistryEntry } from '@/tools/video-editor/types/index.ts';

export interface FinalVideoAssetSource {
  id: string;
  location: string;
  thumbnailUrl: string | null;
  durationSeconds?: number | null;
}

function readPositiveNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value) && value > 0) {
    return value;
  }

  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
  }

  return null;
}

function readPositiveNumberFromFirstArrayItem(value: unknown): number | null {
  if (!Array.isArray(value) || value.length === 0) {
    return null;
  }

  return readPositiveNumber(value[0]);
}

function readDurationFromRecord(record: Record<string, unknown> | null | undefined): number | null {
  if (!record) {
    return null;
  }

  const directDuration = readPositiveNumber(record.duration_seconds)
    ?? readPositiveNumber(record.trimmed_duration)
    ?? readPositiveNumber(record.duration)
    ?? readPositiveNumber(record.video_duration)
    ?? readPositiveNumber(record.original_duration);
  if (directDuration !== null) {
    return directDuration;
  }

  const totalFrames = readPositiveNumber(record.total_frames)
    ?? readPositiveNumber(record.num_frames)
    ?? readPositiveNumber(record.segment_frames_target)
    ?? readPositiveNumberFromFirstArrayItem(record.segment_frames_expanded);
  const frameRate = readPositiveNumber(record.frame_rate)
    ?? readPositiveNumber(record.fps)
    ?? readPositiveNumber(record.fps_helpers);
  if (totalFrames !== null && frameRate !== null) {
    return totalFrames / frameRate;
  }

  return null;
}

export function getDurationSecondsFromFinalVideoParams(params: unknown): number | null {
  const root = asRecord(params);
  if (!root) {
    return null;
  }

  const recordsToCheck = [
    root,
    asRecord(root.metadata),
    asRecord(root.orchestrator_details),
    asRecord(asRecord(root.orchestrator_details)?.metadata),
    asRecord(root.full_orchestrator_payload),
    asRecord(asRecord(root.full_orchestrator_payload)?.metadata),
    asRecord(root.originalParams),
    asRecord(asRecord(root.originalParams)?.metadata),
    asRecord(asRecord(root.originalParams)?.orchestrator_details),
    asRecord(asRecord(asRecord(root.originalParams)?.orchestrator_details)?.metadata),
  ];

  for (const record of recordsToCheck) {
    const durationSeconds = readDurationFromRecord(record);
    if (durationSeconds !== null) {
      return durationSeconds;
    }
  }

  return null;
}

export function getKnownFinalVideoDurationSeconds(
  finalVideo: Pick<FinalVideoAssetSource, 'id' | 'location' | 'durationSeconds'>,
  assets?: Record<string, AssetRegistryEntry>,
): number | null {
  const explicitDuration = readPositiveNumber(finalVideo.durationSeconds);
  if (explicitDuration !== null) {
    return explicitDuration;
  }

  if (!assets) {
    return null;
  }

  for (const assetEntry of Object.values(assets)) {
    if (assetEntry.generationId !== finalVideo.id && assetEntry.file !== finalVideo.location) {
      continue;
    }

    const assetDuration = readPositiveNumber(assetEntry.duration);
    if (assetDuration !== null) {
      return assetDuration;
    }
  }

  return null;
}

export async function resolveFinalVideoDurationSeconds(
  finalVideo: Pick<FinalVideoAssetSource, 'id' | 'location' | 'durationSeconds'>,
  assets?: Record<string, AssetRegistryEntry>,
): Promise<number | null> {
  const knownDuration = getKnownFinalVideoDurationSeconds(finalVideo, assets);
  if (knownDuration !== null) {
    return knownDuration;
  }

  try {
    const metadata = await extractVideoMetadataFromUrl(finalVideo.location);
    return readPositiveNumber(metadata.duration_seconds);
  } catch {
    return null;
  }
}

export function buildFinalVideoAssetEntry(
  finalVideo: Pick<FinalVideoAssetSource, 'id' | 'location' | 'thumbnailUrl'>,
  durationSeconds?: number | null,
): AssetRegistryEntry {
  const positiveDuration = readPositiveNumber(durationSeconds);

  return {
    file: finalVideo.location,
    type: 'video/mp4',
    ...(positiveDuration !== null ? { duration: positiveDuration } : {}),
    generationId: finalVideo.id,
    ...(finalVideo.thumbnailUrl ? { thumbnailUrl: finalVideo.thumbnailUrl } : {}),
  };
}
