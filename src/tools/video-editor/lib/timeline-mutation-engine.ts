import { buildTrackClipOrder } from '@/tools/video-editor/lib/coordinate-utils';
import { serializeForDisk } from '@/tools/video-editor/lib/serialize';
import { buildDataFromCurrentRegistry } from '@/tools/video-editor/lib/timeline-save-utils';
import {
  assembleTimelineData,
  preserveUploadingClips,
  rowsToConfig,
  type ClipMeta,
  type ClipOrderMap,
  type TimelineData,
} from '@/tools/video-editor/lib/timeline-data';
import type { TimelineDomainContractLevel, TimelineDomainIssue } from '@/tools/video-editor/lib/timeline-domain';
import type { TimelineRow } from '@/tools/video-editor/types/timeline-canvas';

export type TimelineEditMutation =
  | {
      type: 'rows';
      rows: TimelineRow[];
      metaUpdates?: Record<string, Partial<ClipMeta>>;
      metaDeletes?: string[];
      clipOrderOverride?: ClipOrderMap;
      pinnedShotGroupsOverride?: TimelineData['config']['pinnedShotGroups'];
    }
  | {
      type: 'config';
      resolvedConfig: TimelineData['resolvedConfig'];
      pinnedShotGroupsOverride?: TimelineData['config']['pinnedShotGroups'];
    }
  | {
      type: 'pinnedShotGroups';
      pinnedShotGroups: NonNullable<TimelineData['config']['pinnedShotGroups']>;
    };

export interface TimelineMutationSuccess {
  ok: true;
  nextData: TimelineData;
  nextRows: TimelineData['rows'];
  nextMeta: Record<string, ClipMeta>;
  nextClipOrder: ClipOrderMap;
}

export interface TimelineMutationFailure {
  ok: false;
  error: {
    message: string;
    level?: TimelineDomainContractLevel;
    issues?: TimelineDomainIssue[];
    cause: unknown;
  };
}

export type TimelineMutationResult = TimelineMutationSuccess | TimelineMutationFailure;

const withPinnedShotGroups = (
  config: TimelineData['config'],
  pinnedShotGroups: TimelineData['config']['pinnedShotGroups'],
): TimelineData['config'] => ({
  ...config,
  pinnedShotGroups: pinnedShotGroups && pinnedShotGroups.length > 0
    ? pinnedShotGroups
    : undefined,
});

const normalizeMutationError = (error: unknown): TimelineMutationFailure['error'] => {
  if (error instanceof Error) {
    const errorWithIssues = error as Error & {
      level?: TimelineDomainContractLevel;
      issues?: TimelineDomainIssue[];
    };

    return {
      message: error.message,
      ...(errorWithIssues.level ? { level: errorWithIssues.level } : {}),
      ...(errorWithIssues.issues ? { issues: errorWithIssues.issues } : {}),
      cause: error,
    };
  }

  return {
    message: String(error),
    cause: error,
  };
};

export const materializeTimelineRows = (
  current: TimelineData,
  rows: TimelineRow[],
  meta: Record<string, ClipMeta>,
  clipOrder: ClipOrderMap,
): TimelineData => {
  const config = rowsToConfig(
    rows,
    meta,
    current.output,
    clipOrder,
    current.tracks,
    current.config.pinnedShotGroups,
    current.config,
  );

  return preserveUploadingClips(
    { ...current, rows, meta } as TimelineData,
    buildDataFromCurrentRegistry(config, current),
  );
};

const buildDataFromSerializedConfig = (
  current: TimelineData,
  config: TimelineData['config'],
): TimelineData => {
  const resolvedConfig = {
    output: { ...config.output },
    tracks: config.tracks ?? [],
    clips: config.clips.map((clip) => ({
      ...clip,
      assetEntry: clip.asset ? current.resolvedConfig.registry[clip.asset] : undefined,
    })),
    registry: current.resolvedConfig.registry,
    ...(config.theme !== undefined ? { theme: config.theme } : {}),
    ...(config.theme_overrides !== undefined ? { theme_overrides: config.theme_overrides } : {}),
    ...(config.generation_defaults !== undefined ? { generation_defaults: config.generation_defaults } : {}),
  };

  return preserveUploadingClips(
    current,
    assembleTimelineData({
      config,
      configVersion: current.configVersion,
      registry: current.registry,
      resolvedConfig,
      assetMap: Object.fromEntries(
        Object.entries(current.registry.assets ?? {}).map(([assetId, entry]) => [assetId, entry.file]),
      ),
      output: { ...config.output },
    }),
  );
};

export const previewTimelineMutation = (
  current: TimelineData,
  mutation: TimelineEditMutation,
): TimelineMutationResult => {
  try {
    if (mutation.type === 'pinnedShotGroups') {
      const nextData = preserveUploadingClips(
        current,
        buildDataFromCurrentRegistry(
          withPinnedShotGroups(current.config, mutation.pinnedShotGroups),
          current,
        ),
      );

      return {
        ok: true,
        nextData,
        nextRows: nextData.rows,
        nextMeta: nextData.meta,
        nextClipOrder: nextData.clipOrder,
      };
    }

    if (mutation.type === 'rows') {
      const nextMeta: Record<string, ClipMeta> = { ...current.meta };

      if (mutation.metaUpdates) {
        for (const [clipId, patch] of Object.entries(mutation.metaUpdates)) {
          nextMeta[clipId] = nextMeta[clipId]
            ? { ...nextMeta[clipId], ...patch }
            : (patch as ClipMeta);
        }
      }

      if (mutation.metaDeletes) {
        for (const clipId of mutation.metaDeletes) {
          delete nextMeta[clipId];
        }
      }

      const nextClipOrder = mutation.clipOrderOverride
        ?? buildTrackClipOrder(current.tracks, current.clipOrder, mutation.metaDeletes);
      const baseNextData = materializeTimelineRows(
        current,
        mutation.rows,
        nextMeta,
        nextClipOrder,
      );
      const nextData = mutation.pinnedShotGroupsOverride === undefined
        ? baseNextData
        : preserveUploadingClips(
            { ...current, rows: mutation.rows, meta: nextMeta } as TimelineData,
            buildDataFromCurrentRegistry(
              withPinnedShotGroups(baseNextData.config, mutation.pinnedShotGroupsOverride),
              current,
            ),
          );

      return {
        ok: true,
        nextData,
        nextRows: nextData.rows,
        nextMeta: nextData.meta,
        nextClipOrder: nextData.clipOrder,
      };
    }

    const nextData = buildDataFromSerializedConfig(
      current,
      serializeForDisk(
        mutation.resolvedConfig,
        mutation.pinnedShotGroupsOverride ?? current.config.pinnedShotGroups,
      ),
    );

    return {
      ok: true,
      nextData,
      nextRows: nextData.rows,
      nextMeta: nextData.meta,
      nextClipOrder: nextData.clipOrder,
    };
  } catch (error) {
    return {
      ok: false,
      error: normalizeMutationError(error),
    };
  }
};

export const applyTimelineMutation = (
  current: TimelineData,
  mutation: TimelineEditMutation,
): TimelineMutationResult => {
  return previewTimelineMutation(current, mutation);
};

export const rethrowTimelineMutationFailure = (
  failure: TimelineMutationFailure['error'],
): never => {
  if (failure.cause instanceof Error) {
    throw failure.cause;
  }

  throw new Error(failure.message);
};
