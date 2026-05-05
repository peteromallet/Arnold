import type { GenerationDropData } from '@/shared/lib/dnd/dragDrop.ts';
import type { AssetRegistryEntry } from '@/tools/video-editor/types/index.ts';

export type VideoDurationContract = {
  assetDurationSeconds: number | null;
  clipSpanSeconds: number | null;
};

export const DEFAULT_VISIBLE_CLIP_SPAN_SECONDS = 5;
export const EXTERNAL_DROP_VISIBLE_VIDEO_FALLBACK_SECONDS = DEFAULT_VISIBLE_CLIP_SPAN_SECONDS;

/**
 * Sprint 2 keeps registry asset duration separate from visible clip span:
 * duplicate-generation style callers preserve the source asset duration on the
 * new registry entry, while external-drop retains its existing five-second
 * visible fallback when media length stays unresolved.
 */

export function readPositiveDurationSeconds(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : null;
}

export function getRegistryAssetDurationSeconds(assetEntry: AssetRegistryEntry | undefined): number | null {
  return readPositiveDurationSeconds(assetEntry?.duration);
}

export function getDuplicateGenerationDurationContract(
  assetEntry: AssetRegistryEntry | undefined,
): VideoDurationContract {
  return {
    assetDurationSeconds: getRegistryAssetDurationSeconds(assetEntry),
    clipSpanSeconds: null,
  };
}

export function isVideoGenerationDrop(data: GenerationDropData): boolean {
  const contentType = typeof data.metadata?.content_type === 'string'
    ? data.metadata.content_type
    : null;

  return contentType?.startsWith('video/')
    || data.variantType === 'video'
    || /\.(mp4|mov|webm|m4v)$/i.test(data.imageUrl);
}

export function getDroppedGenerationAssetDurationSeconds(data: GenerationDropData): number | null {
  if (!isVideoGenerationDrop(data)) {
    return null;
  }

  return readPositiveDurationSeconds(data.metadata?.duration)
    ?? readPositiveDurationSeconds(data.metadata?.duration_seconds)
    ?? readPositiveDurationSeconds(data.metadata?.original_duration);
}

export function getDroppedGenerationDurationContract(data: GenerationDropData): VideoDurationContract {
  const assetDurationSeconds = getDroppedGenerationAssetDurationSeconds(data);

  if (!isVideoGenerationDrop(data)) {
    return {
      assetDurationSeconds: null,
      clipSpanSeconds: DEFAULT_VISIBLE_CLIP_SPAN_SECONDS,
    };
  }

  return {
    assetDurationSeconds,
    clipSpanSeconds: assetDurationSeconds ?? EXTERNAL_DROP_VISIBLE_VIDEO_FALLBACK_SECONDS,
  };
}

export function getDroppedGenerationClipSpanSeconds(data: GenerationDropData): number {
  return getDroppedGenerationDurationContract(data).clipSpanSeconds ?? EXTERNAL_DROP_VISIBLE_VIDEO_FALLBACK_SECONDS;
}

export function getFinalVideoDropDurationContract(
  assetDurationSeconds: number | null,
): VideoDurationContract {
  return {
    assetDurationSeconds,
    clipSpanSeconds: assetDurationSeconds ?? EXTERNAL_DROP_VISIBLE_VIDEO_FALLBACK_SECONDS,
  };
}

export function getFinalVideoReplacementDurationContract(
  assetDurationSeconds: number | null,
): VideoDurationContract {
  return {
    assetDurationSeconds,
    clipSpanSeconds: assetDurationSeconds,
  };
}
