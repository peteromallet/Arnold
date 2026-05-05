import type { QueryClient } from '@tanstack/react-query';
import { extractSettingsFromCache } from '@/shared/hooks/settings/useToolSettings.ts';
import { queryKeys } from '@/shared/lib/queryKeys/index.ts';
import { videoEditorSettings, type VideoEditorSettings } from '@/tools/video-editor/settings/videoEditorDefaults.ts';

export const VIDEO_EDITOR_PATH = '/tools/video-editor';

/**
 * Build the video-editor URL, appending `?timeline=<id>` when a last-opened
 * timeline is known. Accepts a known id directly, or pulls it from the React
 * Query cache when given a queryClient + projectId.
 */
export function videoEditorPathWithTimeline(timelineId: string | null | undefined): string {
  return timelineId
    ? `${VIDEO_EDITOR_PATH}?timeline=${encodeURIComponent(timelineId)}`
    : VIDEO_EDITOR_PATH;
}

export function resolveVideoEditorPath(
  queryClient: QueryClient,
  projectId: string | null | undefined,
): string {
  const cached = extractSettingsFromCache<VideoEditorSettings>(
    queryClient.getQueryData(
      queryKeys.settings.tool(videoEditorSettings.id, projectId ?? undefined, undefined),
    ),
  );
  return videoEditorPathWithTimeline(cached?.lastTimelineId);
}
