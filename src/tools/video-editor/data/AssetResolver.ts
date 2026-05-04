import type {
  AssetRegistry,
  AssetRegistryEntry,
  TimelineClip,
  TimelineConfig,
} from '@/tools/video-editor/types';

export interface SilenceRegion {
  start: number;
  end: number;
}

export interface AssetProfile {
  transcript?: { segments?: Array<{ start: number; end: number; text: string }> };
  [key: string]: unknown;
}

export interface UploadAssetOptions {
  timelineId: string;
  userId: string;
  filename?: string;
}

export interface UploadedAssetResult {
  assetId: string;
  entry: AssetRegistryEntry;
}

export interface AssetResolveRequest {
  file: string;
  assetId?: string;
  entry?: AssetRegistryEntry;
  clipId?: string;
  timelineId?: string;
}

export type AssetMissingReason =
  | 'missing_asset'
  | 'unresolvable_asset'
  | 'invalid_asset_url';

export interface AssetMissingRequest {
  assetId: string;
  reason: AssetMissingReason;
  clipId?: string;
  timelineId?: string;
  file?: string;
  entry?: AssetRegistryEntry;
  clip?: TimelineClip;
  config?: TimelineConfig;
  registry?: AssetRegistry;
}

export interface AssetProfileLoadRequest {
  assetId: string;
  timelineId?: string;
}

export interface AssetUploadRequest {
  file: File;
  options: UploadAssetOptions;
}

export interface AssetTranscodeRequest {
  file: File;
  timelineId: string;
  userId: string;
  intent: 'asset-upload' | 'image-generation' | 'video-generation';
}

export interface AssetResolver {
  onResolve?(request: AssetResolveRequest): Promise<string>;
  onUpload?(request: AssetUploadRequest): Promise<UploadedAssetResult>;
  onTranscode?(request: AssetTranscodeRequest): Promise<File | null | undefined>;
  onMissing?(request: AssetMissingRequest): Promise<void>;
  onProfileLoad?(request: AssetProfileLoadRequest): Promise<AssetProfile | null>;
  resolveAssetUrl(file: string): Promise<string>;
  registerAsset?(timelineId: string, assetId: string, entry: AssetRegistryEntry): Promise<void>;
  uploadAsset?(
    file: File,
    options: UploadAssetOptions,
  ): Promise<UploadedAssetResult>;
  loadWaveform?(assetId: string): Promise<SilenceRegion[] | null>;
  loadAssetProfile?(assetId: string): Promise<AssetProfile | null>;
}

export async function resolveAssetUrlWithResolver(
  resolver: AssetResolver,
  request: AssetResolveRequest,
): Promise<string> {
  if (resolver.onResolve) {
    return resolver.onResolve(request);
  }

  return resolver.resolveAssetUrl(request.file);
}

export async function uploadAssetWithResolver(
  resolver: AssetResolver,
  request: AssetUploadRequest,
): Promise<UploadedAssetResult> {
  if (resolver.onUpload) {
    return resolver.onUpload(request);
  }

  if (!resolver.uploadAsset) {
    throw new Error('This editor backend does not support asset uploads');
  }

  return resolver.uploadAsset(request.file, request.options);
}

export async function transcodeAssetWithResolver(
  resolver: AssetResolver,
  request: AssetTranscodeRequest,
): Promise<File> {
  if (!resolver.onTranscode) {
    return request.file;
  }

  return (await resolver.onTranscode(request)) ?? request.file;
}

export async function notifyMissingAsset(
  resolver: AssetResolver,
  request: AssetMissingRequest,
): Promise<void> {
  await resolver.onMissing?.(request);
}

export async function loadAssetProfileWithResolver(
  resolver: AssetResolver,
  request: AssetProfileLoadRequest,
): Promise<AssetProfile | null> {
  if (resolver.onProfileLoad) {
    return resolver.onProfileLoad(request);
  }

  return resolver.loadAssetProfile?.(request.assetId) ?? null;
}
