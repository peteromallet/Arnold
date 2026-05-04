import { describe, expect, it } from 'vitest';
import {
  createTimelineCommandRunner,
  type TimelineCommand,
  type TimelineCommandContext,
  type TimelineCommandDescriptor,
  type TimelineCommandValidationError,
} from '@/tools/video-editor/commands';
import { getConfigSignature, getStableConfigSignature } from '@/tools/video-editor/lib/config-utils';
import { migrateToFlatTracks, repairConfig } from '@/tools/video-editor/lib/migrate';
import {
  buildDataFromCurrentRegistry,
  buildDataFromSnapshot,
  shouldAcceptPolledData,
} from '@/tools/video-editor/lib/timeline-save-utils';
import { assembleTimelineData } from '@/tools/video-editor/lib/timeline-data';
import type {
  AssetRegistry,
  ResolvedAssetRegistryEntry,
  ResolvedTimelineConfig,
  TimelineConfig,
  TrackDefinition,
} from '@/tools/video-editor/types';

const makeTrack = (id: string, kind: TrackDefinition['kind'] = 'visual'): TrackDefinition => ({
  id,
  kind,
  label: id,
  scale: 1,
  fit: kind === 'audio' ? 'contain' : 'manual',
  opacity: 1,
  blendMode: 'normal',
});

const makePinnedGroup = (args: {
  shotId: string;
  trackId: string;
  clipIds: string[];
  mode?: 'images' | 'video';
}) => ({
  ...args,
  ...(args.mode ? { mode: args.mode } : {}),
});

const makeAssetMap = (registry: AssetRegistry): Record<string, string> => {
  return Object.fromEntries(
    Object.entries(registry.assets).map(([assetId, entry]) => [assetId, entry.file]),
  );
};

const buildResolvedRegistry = (registry: AssetRegistry): Record<string, ResolvedAssetRegistryEntry> => {
  return Object.fromEntries(
    Object.entries(registry.assets).map(([assetId, entry]) => [
      assetId,
      {
        ...entry,
        src: `https://example.com/${entry.file}`,
      },
    ]),
  );
};

const buildResolvedConfig = (
  config: TimelineConfig,
  resolvedRegistry: Record<string, ResolvedAssetRegistryEntry>,
): ResolvedTimelineConfig => ({
  output: { ...config.output },
  tracks: config.tracks ?? [],
  clips: config.clips.map((clip) => ({
    ...clip,
    assetEntry: clip.asset ? resolvedRegistry[clip.asset] : undefined,
  })),
  registry: resolvedRegistry,
  ...(config.theme !== undefined ? { theme: config.theme } : {}),
  ...(config.theme_overrides !== undefined ? { theme_overrides: config.theme_overrides } : {}),
  ...(config.generation_defaults !== undefined ? { generation_defaults: config.generation_defaults } : {}),
});

type MoveClipCommand = TimelineCommand<'move-clip', {
  clipId: string;
  at: number;
}>;

const getCommandAction = (
  context: TimelineCommandContext<MoveClipCommand>,
): { rowIndex: number; actionIndex: number } | null => {
  const clipId = context.command.payload?.clipId;
  if (typeof clipId !== 'string') {
    return null;
  }

  for (let rowIndex = 0; rowIndex < context.currentData.rows.length; rowIndex += 1) {
    const actionIndex = context.currentData.rows[rowIndex]?.actions.findIndex((action) => action.id === clipId) ?? -1;
    if (actionIndex >= 0) {
      return { rowIndex, actionIndex };
    }
  }

  return null;
};

const buildMoveClipEffect = (
  context: TimelineCommandContext<MoveClipCommand>,
) => {
  const location = getCommandAction(context);
  if (!location) {
    throw new Error('move-clip requires an existing clip.');
  }

  const nextAt = context.command.payload?.at;
  if (typeof nextAt !== 'number') {
    throw new Error('move-clip requires a numeric at value.');
  }

  const row = context.currentData.rows[location.rowIndex];
  const action = row.actions[location.actionIndex];
  const duration = action.end - action.start;
  const nextRows = context.currentData.rows.map((candidateRow, rowIndex) => (
    rowIndex === location.rowIndex
      ? {
          ...candidateRow,
          actions: candidateRow.actions.map((candidateAction, actionIndex) => (
            actionIndex === location.actionIndex
              ? { ...candidateAction, start: nextAt, end: nextAt + duration }
              : candidateAction
          )),
        }
      : candidateRow
  ));

  return {
    mutation: {
      type: 'rows' as const,
      rows: nextRows,
    },
    summary: `Move ${action.id} to ${nextAt}s`,
  };
};

const moveClipCommandDescriptor: TimelineCommandDescriptor<MoveClipCommand> = {
  type: 'move-clip',
  validate: (context) => {
    const { clipId, at } = context.command.payload ?? {};
    const errors: TimelineCommandValidationError[] = [];

    if (typeof clipId !== 'string' || clipId.trim().length === 0) {
      errors.push({
        path: `$.commands[${context.commandIndex}].payload.clipId`,
        code: 'invalid_clip_id',
        message: 'clipId must be a non-empty string.',
      });
    } else if (!context.currentData.meta[clipId]) {
      errors.push({
        path: `$.commands[${context.commandIndex}].payload.clipId`,
        code: 'missing_clip',
        message: `Clip "${clipId}" was not found.`,
      });
    }

    if (typeof at !== 'number' || !Number.isFinite(at) || at < 0) {
      errors.push({
        path: `$.commands[${context.commandIndex}].payload.at`,
        code: 'invalid_at',
        message: 'at must be a finite non-negative number.',
      });
    }

    return errors;
  },
  dryRun: buildMoveClipEffect,
  apply: buildMoveClipEffect,
  invert: (context) => {
    const location = getCommandAction(context);
    if (!location) {
      return null;
    }

    const currentAction = context.currentData.rows[location.rowIndex]?.actions[location.actionIndex];
    if (!currentAction) {
      return null;
    }

    return {
      type: 'move-clip',
      payload: {
        clipId: currentAction.id,
        at: currentAction.start,
      },
    };
  },
};

const commandRunner = createTimelineCommandRunner([moveClipCommandDescriptor]);

const buildCommandTestData = () => {
  const config: TimelineConfig = {
    output: { resolution: '1920x1080', fps: 30, file: 'command-test.mp4' },
    tracks: [makeTrack('V1')],
    clips: [
      {
        id: 'clip-1',
        at: 0,
        track: 'V1',
        clipType: 'media',
        asset: 'asset-1',
        from: 0,
        to: 2,
      },
    ],
  };
  const assetRegistry: AssetRegistry = {
    assets: {
      'asset-1': { file: 'asset-1.mp4', type: 'video/mp4', duration: 2 },
    },
  };

  return assembleTimelineData({
    config,
    configVersion: 1,
    registry: assetRegistry,
    resolvedConfig: buildResolvedConfig(config, buildResolvedRegistry(assetRegistry)),
    output: { ...config.output },
    assetMap: makeAssetMap(assetRegistry),
  });
};

describe('timeline save utils regression coverage', () => {
  it('assembleTimelineData produces consistent output with the resolved-config signature', () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [makeTrack('V1'), makeTrack('A1', 'audio')],
      clips: [
        { id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 3 },
        { id: 'clip-2', at: 1, track: 'A1', clipType: 'hold', asset: 'asset-2', hold: 2 },
      ],
    };
    const registry: AssetRegistry = {
      assets: {
        'asset-1': { file: 'video.mp4', duration: 3 },
        'asset-2': { file: 'audio.mp3', duration: 2 },
      },
    };
    const resolvedConfig = buildResolvedConfig(config, buildResolvedRegistry(registry));

    const data = assembleTimelineData({
      config,
      configVersion: 7,
      registry,
      resolvedConfig,
      output: { ...config.output },
      assetMap: makeAssetMap(registry),
    });

    expect(data.config).toBe(config);
    expect(data.registry).toBe(registry);
    expect(data.resolvedConfig).toBe(resolvedConfig);
    expect(data.configVersion).toBe(7);
    expect(data.output).toEqual(config.output);
    expect(data.assetMap).toEqual({
      'asset-1': 'video.mp4',
      'asset-2': 'audio.mp3',
    });
    expect(data.tracks.map((track) => track.id)).toEqual(['V1', 'A1']);
    expect(data.clipOrder).toEqual({
      V1: ['clip-1'],
      A1: ['clip-2'],
    });
    expect(data.rows).toEqual([
      {
        id: 'V1',
        actions: [{ id: 'clip-1', start: 0, end: 3, effectId: 'effect-clip-1' }],
      },
      {
        id: 'A1',
        actions: [{ id: 'clip-2', start: 1, end: 3, effectId: 'effect-clip-2' }],
      },
    ]);
    expect(Object.keys(data.meta)).toEqual(['clip-1', 'clip-2']);
    expect(Object.keys(data.effects)).toEqual(['effect-clip-1', 'effect-clip-2']);
    expect(data.signature).toBe(getConfigSignature(resolvedConfig));
    expect(data.stableSignature).toBe(getStableConfigSignature(config, registry));
  });

  it('deduplicates duplicate track ids through repair then assemble', () => {
    const migratedConfig = migrateToFlatTracks(repairConfig({
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [makeTrack('V1'), makeTrack('V3'), makeTrack('V3')],
      clips: [{ id: 'clip-1', at: 0, track: 'V3', clipType: 'hold', asset: 'asset-1', hold: 2 }],
    }));
    const registry: AssetRegistry = {
      assets: {
        'asset-1': { file: 'overlay.png' },
      },
    };
    const resolvedConfig = buildResolvedConfig(migratedConfig, buildResolvedRegistry(registry));

    const data = assembleTimelineData({
      config: migratedConfig,
      configVersion: 1,
      registry,
      resolvedConfig,
      output: { ...migratedConfig.output },
      assetMap: makeAssetMap(registry),
    });

    expect(migratedConfig.tracks?.map((track) => track.id)).toEqual(['V1', 'V3']);
    expect(data.tracks.map((track) => track.id)).toEqual(['V1', 'V3']);
    expect(data.rows.map((row) => row.id)).toEqual(['V1', 'V3']);
    expect(Object.keys(data.clipOrder)).toEqual(['V1', 'V3']);
    expect(data.clipOrder.V3).toEqual(['clip-1']);
  });

  it('cleans cascading duplicate clip ids through repair then assemble', () => {
    const migratedConfig = migrateToFlatTracks(repairConfig({
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [makeTrack('V1')],
      clips: [
        { id: 'clip-7-dup-2-dup-1', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 2 },
        { id: 'clip-7', at: 2, track: 'V1', clipType: 'hold', asset: 'asset-2', hold: 1 },
      ],
    }));
    const registry: AssetRegistry = {
      assets: {
        'asset-1': { file: 'base.png' },
        'asset-2': { file: 'alt.png' },
      },
    };
    const resolvedConfig = buildResolvedConfig(migratedConfig, buildResolvedRegistry(registry));

    const data = assembleTimelineData({
      config: migratedConfig,
      configVersion: 1,
      registry,
      resolvedConfig,
      output: { ...migratedConfig.output },
      assetMap: makeAssetMap(registry),
    });

    // repairConfig strips -dup- suffix and drops duplicates of the same base id
    expect(migratedConfig.clips.map((clip) => clip.id)).toEqual(['clip-7']);
    expect(data.clipOrder.V1).toEqual(['clip-7']);
    expect(Object.keys(data.meta)).toEqual(['clip-7']);
    expect(Object.keys(data.effects)).toEqual(['effect-clip-7']);
    expect(Object.keys(data.meta).some((clipId) => /-dup-\d+/.test(clipId))).toBe(false);
  });

  it('buildDataFromCurrentRegistry preserves registry objects from current data', () => {
    const currentConfig: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'current.mp4' },
      tracks: [makeTrack('V1')],
      clips: [{ id: 'clip-current', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 2 }],
    };
    const currentRegistry: AssetRegistry = {
      assets: {
        'asset-1': { file: 'current.png' },
        'asset-2': { file: 'next.png' },
      },
    };
    const currentResolvedRegistry = buildResolvedRegistry(currentRegistry);
    const current = assembleTimelineData({
      config: currentConfig,
      configVersion: 3,
      registry: currentRegistry,
      resolvedConfig: buildResolvedConfig(currentConfig, currentResolvedRegistry),
      output: { ...currentConfig.output },
      assetMap: makeAssetMap(currentRegistry),
    });
    const nextConfig: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'next.mp4' },
      tracks: [makeTrack('V1')],
      clips: [{ id: 'clip-next', at: 1, track: 'V1', clipType: 'hold', asset: 'asset-2', hold: 4 }],
    };

    const data = buildDataFromCurrentRegistry(nextConfig, current);

    expect(data.registry).toBe(current.registry);
    expect(data.resolvedConfig.registry).toBe(current.resolvedConfig.registry);
    expect(data.assetMap).toEqual(makeAssetMap(current.registry));
    expect(data.resolvedConfig.clips[0]?.assetEntry).toBe(current.resolvedConfig.registry['asset-2']);
  });

  it('buildDataFromCurrentRegistry repairs malformed non-hold trims using the joined registry', () => {
    const currentConfig: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'current.mp4' },
      tracks: [makeTrack('V1')],
      clips: [{ id: 'clip-current', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 2 }],
    };
    const currentRegistry: AssetRegistry = {
      assets: {
        'asset-1': { file: 'current.png' },
        'asset-video': { file: 'video.mp4', duration: 9 },
      },
    };
    const current = assembleTimelineData({
      config: currentConfig,
      configVersion: 3,
      registry: currentRegistry,
      resolvedConfig: buildResolvedConfig(currentConfig, buildResolvedRegistry(currentRegistry)),
      output: { ...currentConfig.output },
      assetMap: makeAssetMap(currentRegistry),
    });

    const data = buildDataFromCurrentRegistry({
      output: { resolution: '1920x1080', fps: 30, file: 'next.mp4' },
      tracks: [makeTrack('V1')],
      clips: [{
        id: 'clip-video',
        at: 1,
        track: 'V1',
        clipType: 'media',
        asset: 'asset-video',
      }],
    }, current);

    expect(data.config.clips[0]).toMatchObject({
      id: 'clip-video',
      from: 0,
      to: 9,
    });
    expect(data.rows[0]?.actions[0]).toMatchObject({
      id: 'clip-video',
      start: 1,
      end: 10,
    });
  });

  it('buildDataFromSnapshot repairs malformed non-hold trims using the snapshot registry', () => {
    const currentConfig: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'current.mp4' },
      tracks: [makeTrack('V1')],
      clips: [{ id: 'clip-current', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 2 }],
    };
    const currentRegistry: AssetRegistry = {
      assets: {
        'asset-1': { file: 'current.png' },
      },
    };
    const current = assembleTimelineData({
      config: currentConfig,
      configVersion: 3,
      registry: currentRegistry,
      resolvedConfig: buildResolvedConfig(currentConfig, buildResolvedRegistry(currentRegistry)),
      output: { ...currentConfig.output },
      assetMap: makeAssetMap(currentRegistry),
    });
    const snapshotRegistry: AssetRegistry = {
      assets: {
        'asset-video': { file: 'snapshot.mp4', duration: 6 },
      },
    };

    const data = buildDataFromSnapshot({
      output: { resolution: '1920x1080', fps: 30, file: 'snapshot.mp4' },
      tracks: [makeTrack('V1')],
      clips: [{
        id: 'clip-video',
        at: 2,
        track: 'V1',
        clipType: 'media',
        asset: 'asset-video',
      }],
    }, snapshotRegistry, current);

    expect(data.registry).toEqual(snapshotRegistry);
    expect(data.config.clips[0]).toMatchObject({
      id: 'clip-video',
      from: 0,
      to: 6,
    });
    expect(data.rows[0]?.actions[0]).toMatchObject({
      id: 'clip-video',
      start: 2,
      end: 8,
    });
  });

  it('buildDataFromCurrentRegistry carries theme extras through registry-backed reconstruction', () => {
    const currentConfig: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'current.mp4' },
      tracks: [makeTrack('V1')],
      clips: [{ id: 'clip-current', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 2 }],
      theme: '2rp',
      theme_overrides: { visual: { canvas: { fps: 24 } } },
      generation_defaults: { model: 'sequence-v1' },
    };
    const currentRegistry: AssetRegistry = {
      assets: {
        'asset-1': { file: 'current.png' },
        'asset-2': { file: 'next.png' },
      },
    };
    const currentResolvedRegistry = buildResolvedRegistry(currentRegistry);
    const current = assembleTimelineData({
      config: currentConfig,
      configVersion: 3,
      registry: currentRegistry,
      resolvedConfig: buildResolvedConfig(currentConfig, currentResolvedRegistry),
      output: { ...currentConfig.output },
      assetMap: makeAssetMap(currentRegistry),
    });
    const nextConfig: TimelineConfig = {
      ...currentConfig,
      output: { resolution: '1920x1080', fps: 30, file: 'next.mp4' },
      clips: [{ id: 'clip-next', at: 1, track: 'V1', clipType: 'hold', asset: 'asset-2', hold: 4 }],
    };

    const data = buildDataFromCurrentRegistry(nextConfig, current);

    expect(data.config).toMatchObject({
      theme: '2rp',
      theme_overrides: { visual: { canvas: { fps: 24 } } },
      generation_defaults: { model: 'sequence-v1' },
    });
    expect(data.resolvedConfig).toMatchObject({
      theme: '2rp',
      theme_overrides: { visual: { canvas: { fps: 24 } } },
      generation_defaults: { model: 'sequence-v1' },
    });
  });

  it('buildDataFromCurrentRegistry migrates configs with duplicate tracks before assembly', () => {
    const currentConfig: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'current.mp4' },
      tracks: [makeTrack('V1')],
      clips: [{ id: 'clip-current', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 2 }],
    };
    const currentRegistry: AssetRegistry = {
      assets: {
        'asset-1': { file: 'current.png' },
        'asset-2': { file: 'overlay.png' },
      },
    };
    const current = assembleTimelineData({
      config: currentConfig,
      configVersion: 4,
      registry: currentRegistry,
      resolvedConfig: buildResolvedConfig(currentConfig, buildResolvedRegistry(currentRegistry)),
      output: { ...currentConfig.output },
      assetMap: makeAssetMap(currentRegistry),
    });
    const data = buildDataFromCurrentRegistry({
      output: { resolution: '1920x1080', fps: 30, file: 'next.mp4' },
      tracks: [makeTrack('V1'), makeTrack('V3'), makeTrack('V3')],
      clips: [{ id: 'clip-overlay', at: 0, track: 'V3', clipType: 'hold', asset: 'asset-2', hold: 2 }],
    }, current);

    expect(data.config.tracks?.map((track) => track.id)).toEqual(['V1', 'V3']);
    expect(data.tracks.map((track) => track.id)).toEqual(['V1', 'V3']);
    expect(data.rows.map((row) => row.id)).toEqual(['V1', 'V3']);
    expect(Object.keys(data.clipOrder)).toEqual(['V1', 'V3']);
  });

  it('preserves soft-tag pinned shot groups while repairing their contiguity', () => {
    const currentConfig: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'current.mp4' },
      tracks: [makeTrack('V1'), makeTrack('V2')],
      clips: [{ id: 'clip-current', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 2 }],
    };
    const currentRegistry: AssetRegistry = {
      assets: {
        'asset-1': { file: 'current.png' },
      },
    };
    const current = assembleTimelineData({
      config: currentConfig,
      configVersion: 5,
      registry: currentRegistry,
      resolvedConfig: buildResolvedConfig(currentConfig, buildResolvedRegistry(currentRegistry)),
      output: { ...currentConfig.output },
      assetMap: makeAssetMap(currentRegistry),
    });
    const pinnedGroup = makePinnedGroup({
      shotId: 'shot-1',
      trackId: 'V2',
      clipIds: ['clip-1', 'clip-2'],
      mode: 'images',
    });

    const nextConfig: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'next.mp4' },
      tracks: [makeTrack('V1'), makeTrack('V2')],
      clips: [
        { id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', hold: 99 },
        { id: 'clip-2', at: 0, track: 'V1', clipType: 'hold', hold: 99 },
      ],
      pinnedShotGroups: [pinnedGroup],
    };

    const data = buildDataFromCurrentRegistry(nextConfig, current);

    expect(data.config.pinnedShotGroups).toEqual([pinnedGroup]);
    expect(data.resolvedConfig.clips).toEqual(expect.arrayContaining([
      expect.objectContaining({ id: 'clip-1', at: 0, track: 'V1', hold: 99 }),
      expect.objectContaining({ id: 'clip-2', at: 99, track: 'V1', hold: 99 }),
    ]));
    expect(data.signature).toBe(getConfigSignature(data.resolvedConfig));
    expect(data.signature).not.toBe(getConfigSignature(buildResolvedConfig(nextConfig, current.resolvedConfig.registry)));
  });

  it('buildDataFromCurrentRegistry materializes rows from clip geometry while keeping soft-tag groups unchanged', () => {
    const currentConfig: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'current.mp4' },
      tracks: [makeTrack('V1')],
      clips: [{ id: 'clip-current', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 2 }],
    };
    const currentRegistry: AssetRegistry = {
      assets: {
        'asset-1': { file: 'current.png' },
        'asset-2': { file: 'next.png' },
      },
    };
    const current = assembleTimelineData({
      config: currentConfig,
      configVersion: 5,
      registry: currentRegistry,
      resolvedConfig: buildResolvedConfig(currentConfig, buildResolvedRegistry(currentRegistry)),
      output: { ...currentConfig.output },
      assetMap: makeAssetMap(currentRegistry),
    });

    const nextConfig: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'next.mp4' },
      tracks: [makeTrack('V1')],
      clips: [
        { id: 'clip-1', at: 7, track: 'V1', clipType: 'hold', asset: 'asset-2', hold: 2 },
        { id: 'clip-2', at: 9, track: 'V1', clipType: 'hold', asset: 'asset-2', hold: 3 },
      ],
      pinnedShotGroups: [makePinnedGroup({
        shotId: 'shot-1',
        trackId: 'V1',
        clipIds: ['clip-1', 'clip-2'],
        mode: 'images',
      })],
    };

    const data = buildDataFromCurrentRegistry(nextConfig, current);
    const unprojectedResolvedConfig = buildResolvedConfig(nextConfig, buildResolvedRegistry(currentRegistry));

    expect(data.config.pinnedShotGroups).toEqual(nextConfig.pinnedShotGroups);
    expect(data.config.clips).toEqual(nextConfig.clips);
    expect(data.rows).toEqual([
      {
        id: 'V1',
        actions: [
          { id: 'clip-1', start: 7, end: 9, effectId: 'effect-clip-1' },
          { id: 'clip-2', start: 9, end: 12, effectId: 'effect-clip-2' },
        ],
      },
    ]);
    expect(data.signature).toBe(getConfigSignature(data.resolvedConfig));
    expect(data.signature).toBe(getConfigSignature(unprojectedResolvedConfig));
  });

  it('repairs legacy pinned groups to soft-tag `clipIds` without re-projecting clip geometry', () => {
    const currentConfig: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'current.mp4' },
      tracks: [makeTrack('V1')],
      clips: [{ id: 'clip-current', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 2 }],
    };
    const currentRegistry: AssetRegistry = {
      assets: {
        'asset-1': { file: 'current.png' },
        'asset-2': { file: 'next.png' },
      },
    };
    const current = assembleTimelineData({
      config: currentConfig,
      configVersion: 7,
      registry: currentRegistry,
      resolvedConfig: buildResolvedConfig(currentConfig, buildResolvedRegistry(currentRegistry)),
      output: { ...currentConfig.output },
      assetMap: makeAssetMap(currentRegistry),
    });

    const data = buildDataFromCurrentRegistry({
      output: { resolution: '1920x1080', fps: 30, file: 'next.mp4' },
      tracks: [makeTrack('V1')],
      clips: [
        { id: 'clip-1', at: 9, track: 'V1', clipType: 'hold', asset: 'asset-2', hold: 2 },
        { id: 'clip-2', at: 4, track: 'V1', clipType: 'hold', asset: 'asset-2', hold: 3 },
      ],
      pinnedShotGroups: [{
        shotId: 'shot-1',
        trackId: 'V1',
        clipIds: ['clip-1', 'clip-2'],
        start: 4,
        children: [
          { clipId: 'clip-2', offset: 0, duration: 3 },
          { clipId: 'clip-1', offset: 3, duration: 2 },
        ],
        mode: 'images',
      }] as unknown as TimelineConfig['pinnedShotGroups'],
    }, current);

    expect(data.config.pinnedShotGroups?.[0]).toEqual(expect.objectContaining({
      clipIds: ['clip-2', 'clip-1'],
    }));
    expect(data.resolvedConfig.clips).toEqual(expect.arrayContaining([
      expect.objectContaining({ id: 'clip-2', at: 4, hold: 3 }),
      expect.objectContaining({ id: 'clip-1', at: 7, hold: 2 }),
    ]));
    expect(data.signature).toBe(getConfigSignature(data.resolvedConfig));
  });

  it('keeps the stable signature unchanged when only resolved asset URLs change', () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [makeTrack('V1')],
      clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 2 }],
    };
    const registry: AssetRegistry = {
      assets: {
        'asset-1': { file: 'video.mp4', duration: 2 },
      },
    };

    const first = assembleTimelineData({
      config,
      configVersion: 1,
      registry,
      resolvedConfig: buildResolvedConfig(config, {
        'asset-1': { ...registry.assets['asset-1'], src: 'https://signed.example.com/video?token=one' },
      }),
      output: { ...config.output },
      assetMap: makeAssetMap(registry),
    });
    const second = assembleTimelineData({
      config,
      configVersion: 1,
      registry,
      resolvedConfig: buildResolvedConfig(config, {
        'asset-1': { ...registry.assets['asset-1'], src: 'https://signed.example.com/video?token=two' },
      }),
      output: { ...config.output },
      assetMap: makeAssetMap(registry),
    });

    expect(first.signature).not.toBe(second.signature);
    expect(first.stableSignature).toBe(second.stableSignature);
    expect(shouldAcceptPolledData(2, 2, 0, second.stableSignature, first.stableSignature)).toBe(false);
  });

  it('produces the same stable signature across repeated canonical serializations', () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [makeTrack('V1')],
      clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 2 }],
    };
    const registryA: AssetRegistry = {
      assets: {
        'asset-2': { duration: 4, file: 'b.mp4', fps: 24 },
        'asset-1': { file: 'a.mp4', duration: 2 },
      },
    };
    const registryB: AssetRegistry = {
      assets: {
        'asset-1': { duration: 2, file: 'a.mp4' },
        'asset-2': { fps: 24, file: 'b.mp4', duration: 4 },
      },
    };

    const first = getStableConfigSignature(config, registryA);
    const second = getStableConfigSignature(JSON.parse(JSON.stringify(config)) as TimelineConfig, registryB);

    expect(first).toBe(second);
  });

  it('rejects polled data while asset operations are pending', () => {
    expect(shouldAcceptPolledData(4, 4, 1, 'polled', 'saved')).toBe(false);
    expect(shouldAcceptPolledData(4, 4, 0, 'polled', 'saved')).toBe(true);
  });

  it('rejects polled data while drag is in progress (pendingOps incremented by drag)', () => {
    expect(shouldAcceptPolledData(5, 5, 1, 'polled-sig', 'saved-sig')).toBe(false);
  });
});

describe('timeline command runner core', () => {
  it('returns structured validation failures without mutating timeline data', () => {
    const data = buildCommandTestData();

    const result = commandRunner.validate(data, {
      transactionId: 'tx-invalid',
      commands: [
        {
          type: 'move-clip',
          payload: {
            clipId: 'missing-clip',
            at: 3,
          },
        },
      ],
    });

    expect(result.status).toBe('rejected');
    expect(result.errors).toHaveLength(1);
    expect(result.errors[0]).toMatchObject({
      code: 'validation_failed',
      transactionId: 'tx-invalid',
      commandType: 'move-clip',
    });
    expect(result.errors[0]?.validationErrors?.[0]).toMatchObject({
      code: 'missing_clip',
      path: '$.commands[0].payload.clipId',
    });
    expect(result.nextData.stableSignature).toBe(data.stableSignature);
    expect(data.config.clips[0]?.at).toBe(0);
  });

  it('supports dry-run with inverse transaction metadata', () => {
    const data = buildCommandTestData();

    const result = commandRunner.dryRun(data, {
      transactionId: 'tx-dry-run',
      commands: [
        {
          type: 'move-clip',
          payload: {
            clipId: 'clip-1',
            at: 5,
          },
        },
      ],
    });

    expect(result.status).toBe('ok');
    expect(result.nextData.config.clips[0]?.at).toBe(5);
    expect(data.config.clips[0]?.at).toBe(0);
    expect(result.history.strategy).toBe('inverse_transaction');
    expect(result.history.inverseTransaction).toEqual({
      transactionId: 'tx-dry-run:undo',
      commands: [
        {
          type: 'move-clip',
          payload: {
            clipId: 'clip-1',
            at: 0,
          },
        },
      ],
    });
  });

  it('applies commands and uses inverse transactions to undo them', () => {
    const data = buildCommandTestData();
    const applied = commandRunner.apply(data, {
      transactionId: 'tx-apply',
      commands: [
        {
          type: 'move-clip',
          payload: {
            clipId: 'clip-1',
            at: 4,
          },
        },
      ],
    });
    const inverseTransaction = applied.history.inverseTransaction;

    expect(applied.status).toBe('ok');
    expect(applied.nextData.config.clips[0]?.at).toBe(4);
    expect(inverseTransaction).not.toBeNull();

    if (!inverseTransaction) {
      throw new Error('Expected inverse transaction metadata.');
    }

    const undone = commandRunner.apply(applied.nextData, inverseTransaction);

    expect(undone.status).toBe('ok');
    expect(undone.nextData.config.clips[0]?.at).toBe(0);
    expect(undone.nextData.stableSignature).toBe(data.stableSignature);
  });

  it('keeps atomic batches all-or-nothing when any command fails', () => {
    const data = buildCommandTestData();

    const result = commandRunner.apply(data, {
      transactionId: 'tx-atomic',
      commands: [
        {
          type: 'move-clip',
          payload: {
            clipId: 'clip-1',
            at: 2,
          },
        },
        {
          type: 'move-clip',
          payload: {
            clipId: 'missing-clip',
            at: 6,
          },
        },
      ],
    });

    expect(result.status).toBe('rejected');
    expect(result.errors).toHaveLength(1);
    expect(result.history.appliedCount).toBe(0);
    expect(result.nextData.stableSignature).toBe(data.stableSignature);
    expect(result.nextData.config.clips[0]?.at).toBe(0);
  });

  it('supports compat_partial batch execution without embedding adapter policy in the core runner', () => {
    const data = buildCommandTestData();

    const result = commandRunner.apply(data, {
      transactionId: 'tx-partial',
      commands: [
        {
          type: 'move-clip',
          payload: {
            clipId: 'clip-1',
            at: 2,
          },
        },
        {
          type: 'move-clip',
          payload: {
            clipId: 'missing-clip',
            at: 6,
          },
        },
        {
          type: 'move-clip',
          payload: {
            clipId: 'clip-1',
            at: 4,
          },
        },
      ],
    }, {
      executionMode: 'compat_partial',
    });

    expect(result.status).toBe('partial');
    expect(result.errors).toHaveLength(1);
    expect(result.history.partial).toBe(true);
    expect(result.history.appliedCount).toBe(2);
    expect(result.nextData.config.clips[0]?.at).toBe(4);
    expect(result.history.inverseTransaction?.commands).toHaveLength(2);
  });
});
