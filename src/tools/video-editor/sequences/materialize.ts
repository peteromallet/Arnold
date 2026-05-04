import {
  getTrustedSequenceParamDefinitions,
} from '@/tools/video-editor/clip-types/registry';
import type { ClipTypeSequenceParamDefinition as SequenceParamMetadata } from '@/tools/video-editor/clip-types/defineClipType';
import type {
  ResolvedAssetRegistryEntry,
  ResolvedTimelineClip,
  ResolvedTimelineConfig,
} from '@/tools/video-editor/types';

export type SequenceAssetRegistry = Record<string, Partial<ResolvedAssetRegistryEntry> | undefined>;

const resolveAssetUrl = (
  assetKey: string,
  registry: SequenceAssetRegistry,
): string | null => {
  const entry = registry[assetKey];
  if (!entry) return null;
  if (typeof entry.src === 'string' && entry.src.trim()) return entry.src;
  if (typeof entry.file === 'string' && entry.file.trim()) return entry.file;
  return null;
};

const materializeAssetListParam = (
  value: unknown,
  registry: SequenceAssetRegistry,
): string[] | null => {
  if (!Array.isArray(value)) return null;
  const urls = value
    .filter((assetKey): assetKey is string => typeof assetKey === 'string')
    .map((assetKey) => resolveAssetUrl(assetKey, registry))
    .filter((url): url is string => typeof url === 'string' && url.length > 0);
  return urls.length > 0 ? urls : [];
};

const assetListParamsForClipType = (
  clipType: string | undefined,
): readonly SequenceParamMetadata[] => {
  return getTrustedSequenceParamDefinitions(clipType).filter((param) => (
    param.kind === 'asset-list' && typeof param.componentParam === 'string'
  ));
};

export const materializeSequenceParams = (
  clipType: string | undefined,
  params: Record<string, unknown> | undefined,
  registry: SequenceAssetRegistry,
): Record<string, unknown> | undefined => {
  const assetParams = assetListParamsForClipType(clipType);
  if (assetParams.length === 0 || !params) {
    return params;
  }

  let changed = false;
  const nextParams: Record<string, unknown> = { ...params };
  for (const param of assetParams) {
    const componentParam = param.componentParam;
    if (!componentParam) continue;
    const materialized = materializeAssetListParam(params[param.key], registry);
    if (materialized === null) continue;
    nextParams[componentParam] = materialized;
    changed = true;
  }

  return changed ? nextParams : params;
};

export const materializeSequenceClip = (
  clip: ResolvedTimelineClip,
  registry: SequenceAssetRegistry,
): ResolvedTimelineClip => {
  const nextParams = materializeSequenceParams(clip.clipType, clip.params, registry);
  if (nextParams === clip.params) {
    return clip;
  }
  return {
    ...clip,
    params: nextParams,
  };
};

export const materializeSequenceConfig = <
  TConfig extends { clips?: ReadonlyArray<ResolvedTimelineClip>; registry?: SequenceAssetRegistry },
>(
  config: TConfig,
): TConfig => {
  const clips = config.clips;
  if (!Array.isArray(clips) || clips.length === 0) {
    return config;
  }

  const registry = config.registry ?? {};
  let changed = false;
  const nextClips = clips.map((clip) => {
    const nextClip = materializeSequenceClip(clip, registry);
    if (nextClip !== clip) {
      changed = true;
    }
    return nextClip;
  });

  if (!changed) {
    return config;
  }

  return {
    ...config,
    clips: nextClips,
  };
};

export const materializeResolvedSequenceConfig = (
  config: ResolvedTimelineConfig,
): ResolvedTimelineConfig => materializeSequenceConfig(config);
