export const TIMELINE_CENTER_CLIP_EVENT = 'reigh:timeline-center-clip';

export type TimelineCenterClipEventDetail = {
  clipId: string;
};

export const requestCenterTimelineClip = (clipId: string): void => {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent<TimelineCenterClipEventDetail>(TIMELINE_CENTER_CLIP_EVENT, {
    detail: { clipId },
  }));
};

// ── M3: Source-map bidirectional navigation events ─────────────────────

/** Event: navigate from a timeline object to its source range. */
export const TIMELINE_NAVIGATE_TO_SOURCE_EVENT = 'reigh:timeline-navigate-to-source';

export interface TimelineNavigateToSourceDetail {
  /** Extension that owns the source map. */
  extensionId: string;
  /** The source-map entry ID to navigate to. */
  sourceMapEntryId: string;
  /** The timeline object ID (clip, track, etc.). */
  targetId: string;
  /** Source file URI. */
  sourceUri: string;
  /** 0-based start line. */
  sourceStartLine: number;
  /** 0-based start column. */
  sourceStartColumn: number;
  /** 0-based end line (exclusive). */
  sourceEndLine: number;
  /** 0-based end column (exclusive). */
  sourceEndColumn: number;
  /** Whether the mapping is stale. */
  stale: boolean;
}

/** Dispatch a request to navigate from a timeline object to its source range. */
export const requestNavigateTimelineToSource = (
  detail: TimelineNavigateToSourceDetail,
): void => {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent<TimelineNavigateToSourceDetail>(
      TIMELINE_NAVIGATE_TO_SOURCE_EVENT,
      { detail },
    ),
  );
};

/** Event: navigate from a source range to affected timeline objects. */
export const SOURCE_NAVIGATE_TO_TIMELINE_EVENT = 'reigh:source-navigate-to-timeline';

export interface SourceNavigateToTimelineDetail {
  /** Extension that owns the source map. */
  extensionId: string;
  /** Source file URI. */
  sourceUri: string;
  /** 0-based start line. */
  sourceStartLine: number;
  /** 0-based end line (exclusive). */
  sourceEndLine: number;
  /** Optional: specify a particular target to center on. */
  targetId?: string;
}

/** Dispatch a request to navigate from a source range to affected timeline objects. */
export const requestNavigateSourceToTimeline = (
  detail: SourceNavigateToTimelineDetail,
): void => {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent<SourceNavigateToTimelineDetail>(
      SOURCE_NAVIGATE_TO_TIMELINE_EVENT,
      { detail },
    ),
  );
};
