import { assembleTimelineData, type TimelineData } from '@/tools/video-editor/lib/timeline-data';
import { canonicalizeTimelinePair } from '@/tools/video-editor/lib/timeline-domain';
import type {
  AssetRegistry,
  ResolvedAssetRegistryEntry,
  TimelineConfig,
} from '@/tools/video-editor/types';

export function shouldAcceptPolledData(
  editSeq: number,
  savedSeq: number,
  pendingOps: number,
  polledStableSig: string,
  lastSavedStableSig: string,
): boolean {
  if (savedSeq < editSeq) {
    return false;
  }

  if (pendingOps > 0) {
    return false;
  }

  return polledStableSig !== lastSavedStableSig;
}

export function buildDataFromCurrentRegistry(
  config: TimelineConfig,
  current: TimelineData,
): TimelineData {
  const canonical = canonicalizeTimelinePair(config, current.registry);
  const canonicalConfig = canonical.config;

  const resolvedConfig = {
    output: { ...canonicalConfig.output },
    tracks: canonicalConfig.tracks ?? [],
    clips: canonicalConfig.clips.map((clip) => ({
      ...clip,
      assetEntry: clip.asset ? current.resolvedConfig.registry[clip.asset] : undefined,
    })),
    registry: current.resolvedConfig.registry,
    ...(canonicalConfig.theme !== undefined ? { theme: canonicalConfig.theme } : {}),
    ...(canonicalConfig.theme_overrides !== undefined ? { theme_overrides: canonicalConfig.theme_overrides } : {}),
    ...(canonicalConfig.generation_defaults !== undefined ? { generation_defaults: canonicalConfig.generation_defaults } : {}),
  };

  return assembleTimelineData({
    config: canonicalConfig,
    configVersion: current.configVersion,
    registry: current.registry,
    resolvedConfig,
    assetMap: Object.fromEntries(
      Object.entries(current.registry.assets ?? {}).map(([assetId, entry]) => [assetId, entry.file]),
    ),
    output: { ...canonicalConfig.output },
  });
}

export function buildDataFromSnapshot(
  config: TimelineConfig,
  registry: AssetRegistry,
  current: TimelineData,
): TimelineData {
  const canonical = canonicalizeTimelinePair(config, registry);
  const canonicalConfig = canonical.config;

  const snapshotResolvedRegistry: Record<string, ResolvedAssetRegistryEntry> = Object.fromEntries(
    Object.entries(registry.assets ?? {}).map(([assetId, entry]) => [
      assetId,
      {
        ...entry,
        src: entry.file,
      },
    ]),
  );
  const mergedResolvedRegistry = {
    ...snapshotResolvedRegistry,
    ...current.resolvedConfig.registry,
  };
  const resolvedConfig = {
    output: { ...canonicalConfig.output },
    tracks: canonicalConfig.tracks ?? [],
    clips: canonicalConfig.clips.map((clip) => ({
      ...clip,
      assetEntry: clip.asset ? mergedResolvedRegistry[clip.asset] : undefined,
    })),
    registry: mergedResolvedRegistry,
    ...(canonicalConfig.theme !== undefined ? { theme: canonicalConfig.theme } : {}),
    ...(canonicalConfig.theme_overrides !== undefined ? { theme_overrides: canonicalConfig.theme_overrides } : {}),
    ...(canonicalConfig.generation_defaults !== undefined ? { generation_defaults: canonicalConfig.generation_defaults } : {}),
  };

  return assembleTimelineData({
    config: canonicalConfig,
    configVersion: current.configVersion,
    registry,
    resolvedConfig,
    assetMap: Object.fromEntries(
      Object.entries(registry.assets ?? {}).map(([assetId, entry]) => [assetId, entry.file]),
    ),
    output: { ...canonicalConfig.output },
  });
}
