import { TOOL_IDS } from '@/shared/lib/tooling/toolIds.ts';

export interface VideoEditorSettings {
  lastTimelineId?: string;
}

export const videoEditorSettings = {
  id: TOOL_IDS.VIDEO_EDITOR,
  scope: ['project'] as const,
  defaults: {
    lastTimelineId: undefined,
  } satisfies VideoEditorSettings,
};
