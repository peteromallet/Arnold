import {
  buildInsertSequenceDraftEdit,
  buildReplaceSequenceDraftEdit,
  type BuildInsertSequenceDraftOptions,
  type BuildReplaceSequenceDraftOptions,
  type SequenceDraftEditError,
} from '@/tools/video-editor/lib/sequence-drafts';
import {
  buildTimelineData,
  rowsToConfig,
  type ClipMeta,
  type ClipOrderMap,
} from '@/tools/video-editor/lib/timeline-data';
import type { UrlResolver } from '@/tools/video-editor/lib/config-utils';
import type { ValidatedSequenceDraft } from '@/tools/video-editor/sequences/validation';
import type { AssetRegistry, TimelineConfig } from '@/tools/video-editor/types';

export type InsertSequenceDraftIntoTimelineOptions = BuildInsertSequenceDraftOptions & {
  mode?: 'insert';
};

export type ReplaceSequenceDraftInTimelineOptions = BuildReplaceSequenceDraftOptions & {
  mode: 'replace';
};

export type ApplySequenceDraftToTimelineOptions = (
  | InsertSequenceDraftIntoTimelineOptions
  | ReplaceSequenceDraftInTimelineOptions
) & {
  urlResolver?: UrlResolver;
};

export type ApplySequenceDraftToTimelineResult =
  | {
      ok: true;
      clipId: string;
      config: TimelineConfig;
      selectedClipId: string;
      selectedTrackId: string;
    }
  | {
      ok: false;
      error: SequenceDraftEditError;
    };

const applyRowsMutationToConfig = async (
  config: TimelineConfig,
  registry: AssetRegistry,
  draft: ValidatedSequenceDraft,
  options: ApplySequenceDraftToTimelineOptions,
): Promise<ApplySequenceDraftToTimelineResult> => {
  const timeline = await buildTimelineData(config, registry, options.urlResolver);
  const result = options.mode === 'replace'
    ? buildReplaceSequenceDraftEdit(timeline, draft, options)
    : buildInsertSequenceDraftEdit(timeline, draft, options);

  if (!result.ok) {
    return result;
  }

  const meta: Record<string, ClipMeta> = {
    ...timeline.meta,
    ...(result.mutation.metaUpdates ?? {}),
  };
  for (const clipId of result.mutation.metaDeletes ?? []) {
    delete meta[clipId];
  }

  const clipOrder: ClipOrderMap = result.mutation.clipOrderOverride ?? timeline.clipOrder;
  const nextConfig = rowsToConfig(
    result.mutation.rows,
    meta,
    timeline.output,
    clipOrder,
    timeline.tracks,
    timeline.config.pinnedShotGroups,
    timeline.config,
  );

  return {
    ok: true,
    clipId: result.clipId,
    config: nextConfig,
    selectedClipId: result.selectedClipId,
    selectedTrackId: result.selectedTrackId,
  };
};

export const applySequenceDraftToTimeline = async (
  config: TimelineConfig,
  registry: AssetRegistry,
  draft: ValidatedSequenceDraft,
  options: ApplySequenceDraftToTimelineOptions = {},
): Promise<ApplySequenceDraftToTimelineResult> => applyRowsMutationToConfig(
  config,
  registry,
  draft,
  options,
);
