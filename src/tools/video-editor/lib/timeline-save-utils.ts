import { assembleTimelineData, type TimelineData } from '@/tools/video-editor/lib/timeline-data';
import { migrateToFlatTracks, repairConfig } from '@/tools/video-editor/lib/migrate';
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
  // Repair before migration so saved/snapshotted configs keep the canonical shape.
  const migratedConfig = migrateToFlatTracks(repairConfig(config));
  migratedConfig.tracks = migratedConfig.tracks ?? [];

  const resolvedConfig = {
    output: { ...migratedConfig.output },
    tracks: migratedConfig.tracks,
    clips: migratedConfig.clips.map((clip) => ({
      ...clip,
      assetEntry: clip.asset ? current.resolvedConfig.registry[clip.asset] : undefined,
    })),
    registry: current.resolvedConfig.registry,
    ...(migratedConfig.theme !== undefined ? { theme: migratedConfig.theme } : {}),
    ...(migratedConfig.theme_overrides !== undefined ? { theme_overrides: migratedConfig.theme_overrides } : {}),
    ...(migratedConfig.generation_defaults !== undefined ? { generation_defaults: migratedConfig.generation_defaults } : {}),
  };

  return assembleTimelineData({
    config: migratedConfig,
    configVersion: current.configVersion,
    registry: current.registry,
    resolvedConfig,
    assetMap: Object.fromEntries(
      Object.entries(current.registry.assets ?? {}).map(([assetId, entry]) => [assetId, entry.file]),
    ),
    output: { ...migratedConfig.output },
  });
}

export function buildDataFromSnapshot(
  config: TimelineConfig,
  registry: AssetRegistry,
  current: TimelineData,
): TimelineData {
  const migratedConfig = migrateToFlatTracks(repairConfig(config));
  migratedConfig.tracks = migratedConfig.tracks ?? [];

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
    output: { ...migratedConfig.output },
    tracks: migratedConfig.tracks,
    clips: migratedConfig.clips.map((clip) => ({
      ...clip,
      assetEntry: clip.asset ? mergedResolvedRegistry[clip.asset] : undefined,
    })),
    registry: mergedResolvedRegistry,
    ...(migratedConfig.theme !== undefined ? { theme: migratedConfig.theme } : {}),
    ...(migratedConfig.theme_overrides !== undefined ? { theme_overrides: migratedConfig.theme_overrides } : {}),
    ...(migratedConfig.generation_defaults !== undefined ? { generation_defaults: migratedConfig.generation_defaults } : {}),
  };

  return assembleTimelineData({
    config: migratedConfig,
    configVersion: current.configVersion,
    registry,
    resolvedConfig,
    assetMap: Object.fromEntries(
      Object.entries(registry.assets ?? {}).map(([assetId, entry]) => [assetId, entry.file]),
    ),
    output: { ...migratedConfig.output },
  });
}
