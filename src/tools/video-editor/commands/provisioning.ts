import type { AssetRegistryEntry } from '@/tools/video-editor/types';

export type TimelineProvisionedMediaType = 'image' | 'video' | 'audio';

export type TimelineProvisionedAsset = {
  assetKey: string;
  mediaType: TimelineProvisionedMediaType;
  durationSeconds: number | null;
  entry: AssetRegistryEntry;
  source: 'registered' | 'external-media';
};

export type RegisteredTimelineMediaSource = {
  kind: 'asset';
  assetKey: string;
  fallbackMediaType?: TimelineProvisionedMediaType;
};

export type ExternalTimelineMediaSource = {
  kind: 'external-media';
  url: string;
  mediaType: 'image' | 'video';
  generationId?: string;
  durationSeconds?: number | null;
  thumbnailUrl?: string;
  mimeType?: string;
};

export type TimelineMediaSource =
  | RegisteredTimelineMediaSource
  | ExternalTimelineMediaSource;

export type TimelineMediaProvisioningHost = {
  getAssetEntry: (assetKey: string) => AssetRegistryEntry | null | undefined;
  registerExternalAsset?: (
    source: ExternalTimelineMediaSource,
    entry: AssetRegistryEntry,
  ) => Promise<{ assetKey: string }>;
};

const inferMediaType = (
  entry: AssetRegistryEntry | null | undefined,
  assetKey: string,
  fallbackMediaType?: TimelineProvisionedMediaType,
): TimelineProvisionedMediaType | null => {
  const mimeType = entry?.type?.toLowerCase() ?? '';
  const file = (entry?.file ?? assetKey).toLowerCase();

  if (mimeType.startsWith('image/') || /\.(png|jpe?g|gif|webp|avif|svg)$/i.test(file)) {
    return 'image';
  }

  if (mimeType.startsWith('video/') || /\.(mp4|mov|webm|m4v)$/i.test(file)) {
    return 'video';
  }

  if (mimeType.startsWith('audio/') || /\.(mp3|wav|aac|m4a|ogg|flac)$/i.test(file)) {
    return 'audio';
  }

  return fallbackMediaType ?? null;
};

const getFallbackMimeType = (
  mediaType: TimelineProvisionedMediaType,
): string => {
  switch (mediaType) {
    case 'video':
      return 'video/mp4';
    case 'audio':
      return 'audio/mpeg';
    default:
      return 'image/png';
  }
};

export const estimateProvisionedAssetDuration = (
  asset: TimelineProvisionedAsset,
): number => {
  if (asset.mediaType === 'audio') {
    return asset.durationSeconds ?? 10;
  }

  if (asset.mediaType === 'image') {
    return 5;
  }

  return asset.durationSeconds ?? 5;
};

export const provisionRegisteredTimelineMedia = (
  assetKey: string,
  entry: AssetRegistryEntry | null | undefined,
  fallbackMediaType?: TimelineProvisionedMediaType,
): TimelineProvisionedAsset | null => {
  const mediaType = inferMediaType(entry, assetKey, fallbackMediaType);
  if (!mediaType) {
    return null;
  }

  const normalizedEntry: AssetRegistryEntry = entry
    ? { ...entry }
    : {
        file: assetKey,
        type: getFallbackMimeType(mediaType),
      };

  return {
    assetKey,
    mediaType,
    durationSeconds: typeof normalizedEntry.duration === 'number'
      ? normalizedEntry.duration
      : null,
    entry: normalizedEntry,
    source: 'registered',
  };
};

export const buildExternalTimelineAssetEntry = (
  source: ExternalTimelineMediaSource,
): AssetRegistryEntry => {
  const entry: AssetRegistryEntry = {
    file: source.url,
    type: source.mimeType ?? getFallbackMimeType(source.mediaType),
    ...(source.generationId ? { generationId: source.generationId } : {}),
    ...(typeof source.durationSeconds === 'number' ? { duration: source.durationSeconds } : {}),
    ...(source.thumbnailUrl ? { thumbnailUrl: source.thumbnailUrl } : {}),
  };

  return entry;
};

export const provisionTimelineMedia = async (
  source: TimelineMediaSource,
  host: TimelineMediaProvisioningHost,
): Promise<TimelineProvisionedAsset | null> => {
  if (source.kind === 'asset') {
    return provisionRegisteredTimelineMedia(
      source.assetKey,
      host.getAssetEntry(source.assetKey),
      source.fallbackMediaType,
    );
  }

  if (!host.registerExternalAsset) {
    return null;
  }

  const entry = buildExternalTimelineAssetEntry(source);
  const registration = await host.registerExternalAsset(source, entry);

  return {
    assetKey: registration.assetKey,
    mediaType: source.mediaType,
    durationSeconds: typeof entry.duration === 'number' ? entry.duration : null,
    entry,
    source: 'external-media',
  };
};
