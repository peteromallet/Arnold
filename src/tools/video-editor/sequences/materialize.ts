import {
  getTrustedSequenceParamDefinitions,
} from '@/tools/video-editor/clip-types/registry.ts';
import type { ClipTypeSequenceParamDefinition as SequenceParamMetadata } from '@/tools/video-editor/clip-types/defineClipType.ts';
import type {
  ResolvedAssetRegistryEntry,
  ResolvedTimelineClip,
  ResolvedTimelineConfig,
} from '@/tools/video-editor/types/index.ts';

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

// Convention-based substitutions for code-path / DB-stored sequence
// components: if a custom component's params include `imageAssetKeys` or
// `videoAssetKeys` arrays of keys, the host populates the URL arrays
// `images` / `videos` so components can render via <Img src={params.images[0]} />
// without needing per-clip-type metadata. Mirrors the trusted built-in
// pattern (image-jump uses imageAssetKeys → images via componentParam) but
// applies to any clipType emitted by ai-generate-sequence-component.
const CONVENTION_ASSET_PARAMS: ReadonlyArray<{ keysParam: string; urlsParam: string }> = [
  { keysParam: 'imageAssetKeys', urlsParam: 'images' },
  { keysParam: 'videoAssetKeys', urlsParam: 'videos' },
];

export const materializeSequenceParams = (
  clipType: string | undefined,
  params: Record<string, unknown> | undefined,
  registry: SequenceAssetRegistry,
): Record<string, unknown> | undefined => {
  if (!params) return params;

  let changed = false;
  let nextParams: Record<string, unknown> = params;
  const ensureCopy = () => {
    if (nextParams === params) {
      nextParams = { ...params };
    }
  };

  // Trusted clip types: descriptor-driven substitution (e.g. image-jump
  // declares imageAssetKeys → images via componentParam).
  for (const param of assetListParamsForClipType(clipType)) {
    const componentParam = param.componentParam;
    if (!componentParam) continue;
    const materialized = materializeAssetListParam(params[param.key], registry);
    if (materialized === null) continue;
    ensureCopy();
    nextParams[componentParam] = materialized;
    changed = true;
  }

  // Custom-component / DB-stored components: convention-based substitution.
  // Only fill the URL slot if the model didn't already populate it.
  for (const { keysParam, urlsParam } of CONVENTION_ASSET_PARAMS) {
    if (Object.prototype.hasOwnProperty.call(nextParams, urlsParam)
      && Array.isArray(nextParams[urlsParam])
      && (nextParams[urlsParam] as unknown[]).length > 0) {
      continue;
    }
    const materialized = materializeAssetListParam(params[keysParam], registry);
    if (materialized === null || materialized.length === 0) continue;
    ensureCopy();
    nextParams[urlsParam] = materialized;
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
