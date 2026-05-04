import { migrateToFlatTracks, repairConfig } from '@/tools/video-editor/lib/migrate';
import { assembleTimelineData, type TimelineData } from '@/tools/video-editor/lib/timeline-data';
import type {
  AssetRegistry,
  ResolvedAssetRegistryEntry,
  ResolvedTimelineConfig,
} from '@/tools/video-editor/types';

const buildResolvedRegistry = (registry: AssetRegistry): Record<string, ResolvedAssetRegistryEntry> => {
  return Object.fromEntries(
    Object.entries(registry.assets ?? {}).map(([assetKey, entry]) => [
      assetKey,
      {
        ...entry,
        src: entry.file,
      },
    ]),
  );
};

export const buildTimelineCommandData = (
  config: TimelineData['config'],
  registry: AssetRegistry,
): TimelineData => {
  const migratedConfig = migrateToFlatTracks(repairConfig(config));
  migratedConfig.tracks = migratedConfig.tracks ?? [];
  const resolvedRegistry = buildResolvedRegistry(registry);
  const resolvedConfig: ResolvedTimelineConfig = {
    output: { ...migratedConfig.output },
    tracks: migratedConfig.tracks,
    clips: migratedConfig.clips.map((clip) => ({
      ...clip,
      assetEntry: clip.asset ? resolvedRegistry[clip.asset] : undefined,
    })),
    registry: resolvedRegistry,
    ...(migratedConfig.theme !== undefined ? { theme: migratedConfig.theme } : {}),
    ...(migratedConfig.theme_overrides !== undefined ? { theme_overrides: migratedConfig.theme_overrides } : {}),
    ...(migratedConfig.generation_defaults !== undefined ? { generation_defaults: migratedConfig.generation_defaults } : {}),
  };

  return assembleTimelineData({
    config: migratedConfig,
    configVersion: 1,
    registry,
    resolvedConfig,
    output: { ...migratedConfig.output },
    assetMap: Object.fromEntries(
      Object.entries(registry.assets ?? {}).map(([assetKey, entry]) => [assetKey, entry.file]),
    ),
  });
};
