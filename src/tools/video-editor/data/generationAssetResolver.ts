import { fetchGenerationRecordById } from '@/integrations/supabase/repositories/generationRepository';
import { getSupabaseClient } from '@/integrations/supabase/client';
import { asNullableNumber, asNullableString, asRecord } from '@/shared/lib/typeCoercion';
import type { AssetMissingReason } from '@/tools/video-editor/data/AssetResolver';
import type { AssetRegistryEntry } from '@/tools/video-editor/types';

const SIGNED_URL_TTL_SECONDS = 60 * 60;
const STORAGE_OBJECT_PATH_RE = /^\/storage\/v1\/object(?:\/(public|sign))?\/([^/]+)\/(.+)$/;

type SupabaseStorageAccess = 'public' | 'sign' | 'object';
type GenerationMediaType = 'image' | 'video' | 'audio';
type GenerationAssetDiagnosticCode =
  | 'generation-not-found'
  | 'missing-generation-location'
  | 'invalid-generation-url'
  | 'opaque-origin'
  | 'refresh-required'
  | 'refresh-failed';

interface RawGenerationRecord extends Record<string, unknown> {
  id: string;
  location: string | null;
  thumbnail_url?: string | null;
  type?: string | null;
  params?: Record<string, unknown> | null;
  primary_variant_id?: string | null;
}

export interface ParsedSupabaseStorageUrl {
  bucket: string;
  path: string;
  access: SupabaseStorageAccess;
  url: string;
}

export interface GenerationAssetDiagnostic {
  code: GenerationAssetDiagnosticCode;
  message: string;
  generationId: string;
  assetId?: string;
  url?: string;
  bucket?: string;
  path?: string;
}

export interface ResolvedGenerationAsset {
  entry: AssetRegistryEntry;
  generationId: string;
  url: string;
  thumbnailUrl?: string;
  mediaType: GenerationMediaType;
  mimeType?: string;
  refreshed: boolean;
  storage: ParsedSupabaseStorageUrl | null;
}

export interface ResolveGenerationAssetSuccess {
  ok: true;
  asset: ResolvedGenerationAsset;
}

export interface ResolveGenerationAssetFailure {
  ok: false;
  missingReason: AssetMissingReason;
  diagnostic: GenerationAssetDiagnostic;
}

export type ResolveGenerationAssetResult =
  | ResolveGenerationAssetSuccess
  | ResolveGenerationAssetFailure;

export interface ResolveGenerationAssetOptions {
  generationId: string;
  assetId?: string;
  entry?: AssetRegistryEntry | null;
  refresh?: 'if-stale' | 'force' | 'never';
}

function trimToUndefined(value: unknown): string | undefined {
  if (typeof value !== 'string') {
    return undefined;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function normalizeGenerationRecord(value: Record<string, unknown> | null): RawGenerationRecord | null {
  if (!value || typeof value.id !== 'string') {
    return null;
  }

  const params = asRecord(value.params);

  return {
    id: value.id,
    location: asNullableString(value.location) ?? null,
    ...(asNullableString(value.thumbnail_url) !== undefined ? { thumbnail_url: asNullableString(value.thumbnail_url) } : {}),
    ...(asNullableString(value.type) !== undefined ? { type: asNullableString(value.type) } : {}),
    ...(params ? { params } : {}),
    ...(asNullableString(value.primary_variant_id) !== undefined ? { primary_variant_id: asNullableString(value.primary_variant_id) } : {}),
  };
}

function inferMediaType(
  generation: RawGenerationRecord,
  entry: AssetRegistryEntry | null | undefined,
  location: string,
): GenerationMediaType {
  const entryMimeType = trimToUndefined(entry?.type)?.toLowerCase();
  if (entryMimeType?.startsWith('image/')) return 'image';
  if (entryMimeType?.startsWith('video/')) return 'video';
  if (entryMimeType?.startsWith('audio/')) return 'audio';

  const params = generation.params ?? {};
  const storedContentType = trimToUndefined(params.content_type)?.toLowerCase();
  if (storedContentType === 'image' || storedContentType === 'video' || storedContentType === 'audio') {
    return storedContentType;
  }

  const generationType = trimToUndefined(generation.type)?.toLowerCase();
  if (generationType?.includes('video')) return 'video';
  if (generationType?.includes('audio')) return 'audio';
  if (generationType?.includes('image')) return 'image';

  const loweredLocation = location.toLowerCase();
  if (/\.(mp4|mov|webm|m4v)(?:[?#].*)?$/.test(loweredLocation)) return 'video';
  if (/\.(mp3|wav|aac|m4a|ogg|flac)(?:[?#].*)?$/.test(loweredLocation)) return 'audio';

  return 'image';
}

function inferMimeType(
  mediaType: GenerationMediaType,
  entry: AssetRegistryEntry | null | undefined,
  location: string,
): string {
  const explicitMimeType = trimToUndefined(entry?.type);
  if (explicitMimeType?.includes('/')) {
    return explicitMimeType;
  }

  const loweredLocation = location.toLowerCase();
  if (/\.(png)(?:[?#].*)?$/.test(loweredLocation)) return 'image/png';
  if (/\.(jpe?g)(?:[?#].*)?$/.test(loweredLocation)) return 'image/jpeg';
  if (/\.(gif)(?:[?#].*)?$/.test(loweredLocation)) return 'image/gif';
  if (/\.(webp)(?:[?#].*)?$/.test(loweredLocation)) return 'image/webp';
  if (/\.(avif)(?:[?#].*)?$/.test(loweredLocation)) return 'image/avif';
  if (/\.(svg)(?:[?#].*)?$/.test(loweredLocation)) return 'image/svg+xml';
  if (/\.(mp4|m4v)(?:[?#].*)?$/.test(loweredLocation)) return 'video/mp4';
  if (/\.(mov)(?:[?#].*)?$/.test(loweredLocation)) return 'video/quicktime';
  if (/\.(webm)(?:[?#].*)?$/.test(loweredLocation)) return 'video/webm';
  if (/\.(mp3)(?:[?#].*)?$/.test(loweredLocation)) return 'audio/mpeg';
  if (/\.(wav)(?:[?#].*)?$/.test(loweredLocation)) return 'audio/wav';
  if (/\.(aac)(?:[?#].*)?$/.test(loweredLocation)) return 'audio/aac';
  if (/\.(m4a)(?:[?#].*)?$/.test(loweredLocation)) return 'audio/mp4';
  if (/\.(ogg)(?:[?#].*)?$/.test(loweredLocation)) return 'audio/ogg';
  if (/\.(flac)(?:[?#].*)?$/.test(loweredLocation)) return 'audio/flac';

  switch (mediaType) {
    case 'video':
      return 'video/mp4';
    case 'audio':
      return 'audio/mpeg';
    default:
      return 'image/png';
  }
}

function parseResolution(params: Record<string, unknown>, entry: AssetRegistryEntry | null | undefined): string | undefined {
  if (trimToUndefined(entry?.resolution)) {
    return trimToUndefined(entry?.resolution);
  }

  const directResolution = trimToUndefined(params.resolution);
  if (directResolution) {
    return directResolution;
  }

  const width = asNullableNumber(params.width);
  const height = asNullableNumber(params.height);
  if (typeof width === 'number' && typeof height === 'number') {
    return `${width}x${height}`;
  }

  return trimToUndefined(asRecord(params.orchestrator_details)?.parsed_resolution_wh);
}

function firstFiniteNumber(...values: unknown[]): number | undefined {
  for (const value of values) {
    const numeric = asNullableNumber(value);
    if (typeof numeric === 'number') {
      return numeric;
    }
  }

  return undefined;
}

function isExpired(expiresAt: string | undefined, now: number): boolean {
  if (!expiresAt) {
    return false;
  }

  const parsed = Date.parse(expiresAt);
  return Number.isFinite(parsed) ? parsed <= now : false;
}

export function parseSupabaseStorageUrl(url: string): ParsedSupabaseStorageUrl | null {
  const normalizedUrl = trimToUndefined(url);
  if (!normalizedUrl) {
    return null;
  }

  let parsedUrl: URL;
  try {
    parsedUrl = new URL(normalizedUrl);
  } catch {
    return null;
  }

  const match = STORAGE_OBJECT_PATH_RE.exec(parsedUrl.pathname);
  if (!match?.[2] || !match[3]) {
    return null;
  }

  const access = (match[1] ?? 'object') as SupabaseStorageAccess;
  const bucket = decodeURIComponent(match[2]);
  const path = match[3]
    .split('/')
    .map((segment) => decodeURIComponent(segment))
    .join('/');

  if (!bucket || !path) {
    return null;
  }

  return {
    bucket,
    path,
    access,
    url: parsedUrl.toString(),
  };
}

function buildFailure(
  missingReason: AssetMissingReason,
  diagnostic: GenerationAssetDiagnostic,
): ResolveGenerationAssetFailure {
  return { ok: false, missingReason, diagnostic };
}

async function mintStorageUrl(
  storageRef: ParsedSupabaseStorageUrl,
  now: number,
): Promise<{ url: string; expiresAt?: string }> {
  const client = getSupabaseClient();

  if (storageRef.access === 'public') {
    const { data } = client.storage.from(storageRef.bucket).getPublicUrl(storageRef.path);
    return { url: data.publicUrl };
  }

  const { data, error } = await client.storage
    .from(storageRef.bucket)
    .createSignedUrl(storageRef.path, SIGNED_URL_TTL_SECONDS);

  if (error || !data?.signedUrl) {
    throw error ?? new Error('Failed to mint a signed storage URL');
  }

  return {
    url: data.signedUrl,
    expiresAt: new Date(now + SIGNED_URL_TTL_SECONDS * 1000).toISOString(),
  };
}

export async function resolveGenerationAsset(
  options: ResolveGenerationAssetOptions,
): Promise<ResolveGenerationAssetResult> {
  const refreshMode = options.refresh ?? 'if-stale';
  const now = Date.now();
  const currentEntry = options.entry ?? null;
  const rawGeneration = normalizeGenerationRecord(
    await fetchGenerationRecordById(options.generationId) as Record<string, unknown> | null,
  );

  if (!rawGeneration) {
    return buildFailure('missing_asset', {
      code: 'generation-not-found',
      message: `Generation ${options.generationId} was not found.`,
      generationId: options.generationId,
      ...(options.assetId ? { assetId: options.assetId } : {}),
    });
  }

  const location = trimToUndefined(rawGeneration.location);
  if (!location) {
    return buildFailure('missing_asset', {
      code: 'missing-generation-location',
      message: `Generation ${options.generationId} does not have a media location.`,
      generationId: options.generationId,
      ...(options.assetId ? { assetId: options.assetId } : {}),
    });
  }

  let normalizedLocation: URL;
  try {
    normalizedLocation = new URL(location);
  } catch {
    return buildFailure('invalid_asset_url', {
      code: 'invalid-generation-url',
      message: `Generation ${options.generationId} has an invalid media URL.`,
      generationId: options.generationId,
      ...(options.assetId ? { assetId: options.assetId } : {}),
      url: location,
    });
  }

  const storageRef = parseSupabaseStorageUrl(normalizedLocation.toString());
  const needsRefresh = refreshMode === 'force'
    || (refreshMode === 'if-stale' && isExpired(trimToUndefined(currentEntry?.url_expires_at), now));

  if (needsRefresh && currentEntry?.origin === 'opaque-foreign') {
    return buildFailure('unresolvable_asset', {
      code: 'opaque-origin',
      message: `Asset ${options.assetId ?? '(unknown)'} is marked opaque-foreign and cannot be refreshed from generation metadata.`,
      generationId: options.generationId,
      ...(options.assetId ? { assetId: options.assetId } : {}),
      url: normalizedLocation.toString(),
    });
  }

  let resolvedUrl = normalizedLocation.toString();
  let refreshed = false;
  let urlExpiresAt = trimToUndefined(currentEntry?.url_expires_at);

  if (needsRefresh) {
    if (!storageRef) {
      return buildFailure('invalid_asset_url', {
        code: 'refresh-required',
        message: `Generation ${options.generationId} needs a refreshed URL, but its bucket/path cannot be derived from ${normalizedLocation.toString()}.`,
        generationId: options.generationId,
        ...(options.assetId ? { assetId: options.assetId } : {}),
        url: normalizedLocation.toString(),
      });
    }

    try {
      const minted = await mintStorageUrl(storageRef, now);
      resolvedUrl = minted.url;
      urlExpiresAt = minted.expiresAt;
      refreshed = true;
    } catch (error) {
      return buildFailure('unresolvable_asset', {
        code: 'refresh-failed',
        message: error instanceof Error
          ? error.message
          : `Failed to refresh the URL for generation ${options.generationId}.`,
        generationId: options.generationId,
        ...(options.assetId ? { assetId: options.assetId } : {}),
        url: normalizedLocation.toString(),
        bucket: storageRef.bucket,
        path: storageRef.path,
      });
    }
  }

  const thumbnailUrl = trimToUndefined(rawGeneration.thumbnail_url)
    ?? trimToUndefined(currentEntry?.thumbnailUrl)
    ?? normalizedLocation.toString();
  const mediaType = inferMediaType(rawGeneration, currentEntry, normalizedLocation.toString());
  const mimeType = inferMimeType(mediaType, currentEntry, normalizedLocation.toString());
  const params = rawGeneration.params ?? {};
  const duration = firstFiniteNumber(
    currentEntry?.duration,
    params.duration,
    params.original_duration,
    params.source_video_duration,
  );
  const fps = firstFiniteNumber(
    currentEntry?.fps,
    params.fps,
    params.source_video_fps,
  );
  const resolution = parseResolution(params, currentEntry);
  const file = trimToUndefined(currentEntry?.file) ?? normalizedLocation.toString();

  const entry: AssetRegistryEntry = {
    ...(currentEntry ? { ...currentEntry } : {}),
    file,
    url: resolvedUrl,
    type: mimeType,
    origin: 'refreshable-from-generation',
    generationId: options.generationId,
    ...(rawGeneration.primary_variant_id ? { variantId: rawGeneration.primary_variant_id } : {}),
    ...(thumbnailUrl ? { thumbnailUrl } : {}),
    ...(typeof duration === 'number' ? { duration } : {}),
    ...(resolution ? { resolution } : {}),
    ...(typeof fps === 'number' ? { fps } : {}),
    ...(urlExpiresAt ? { url_expires_at: urlExpiresAt } : {}),
  };

  return {
    ok: true,
    asset: {
      entry,
      generationId: options.generationId,
      url: resolvedUrl,
      ...(thumbnailUrl ? { thumbnailUrl } : {}),
      mediaType,
      mimeType,
      refreshed,
      storage: storageRef,
    },
  };
}
