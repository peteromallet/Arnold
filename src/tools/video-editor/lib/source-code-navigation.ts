/**
 * source-code-navigation — Bidirectional source-map navigation helper.
 *
 * Provides utilities that wire the timeline canvas and source/code panel
 * views together using the existing SourceMapRuntime and window-level events.
 *
 * The module exposes two main utilities:
 * - `createTimelineSourceNavigator` — for the timeline side:
 *   looks up source-map entries for a clip/track and dispatches
 *   TIMELINE_NAVIGATE_TO_SOURCE_EVENT.
 * - `createSourceTimelineNavigator` — for the source/code panel side:
 *   looks up affected timeline objects for a source range and dispatches
 *   SOURCE_NAVIGATE_TO_TIMELINE_EVENT or TIMELINE_CENTER_CLIP_EVENT.
 *
 * @publicContract — implements bidirectional navigation as specified in M3.
 */

import type { SourceMapRuntime, SourceMapEntry } from '@/sdk/index';
import {
  requestNavigateTimelineToSource,
  requestNavigateSourceToTimeline,
  requestCenterTimelineClip,
  type TimelineNavigateToSourceDetail,
  type SourceNavigateToTimelineDetail,
} from '@/tools/video-editor/lib/timeline-viewport-events';

// ---------------------------------------------------------------------------
// Timeline → Source navigation
// ---------------------------------------------------------------------------

export interface TimelineSourceNavigatorOptions {
  /** Active SourceMapRuntime for looking up entries. */
  sourceMapRuntime: SourceMapRuntime;
}

export interface TimelineSourceNavigator {
  /**
   * Navigate from a timeline object (clip, track, etc.) to its source range.
   *
   * Looks up all source-map entries for the given target and dispatches
   * TIMELINE_NAVIGATE_TO_SOURCE_EVENT for each entry. If the target has
   * no source-map entries, returns false.
   *
   * @returns true if at least one navigation event was dispatched.
   */
  navigateToSource(
    extensionId: string,
    targetId: string,
  ): boolean;

  /**
   * Check whether a timeline target has any source-map entries (stale or not).
   */
  hasSourceMapEntries(extensionId: string, targetId: string): boolean;

  /**
   * Check whether a timeline target has any stale source-map entries.
   */
  hasStaleSourceMapEntries(extensionId: string, targetId: string): boolean;

  /**
   * Get all source-map entry IDs for a target to compute stale badges.
   */
  getStaleStatus(extensionId: string, targetId: string): {
    hasEntries: boolean;
    hasStale: boolean;
    staleEntries: SourceMapEntry[];
    nonStaleEntries: SourceMapEntry[];
  };
}

/**
 * Create a timeline-side source navigator.
 *
 * Usage from TimelineCanvas / ClipAction:
 * ```ts
 * const navigator = createTimelineSourceNavigator({ sourceMapRuntime });
 * const status = navigator.getStaleStatus('ext.dsl', clipId);
 * if (status.hasStale) { /* show stale badge *\/ }
 * navigator.navigateToSource('ext.dsl', clipId);
 * ```
 */
export function createTimelineSourceNavigator(
  options: TimelineSourceNavigatorOptions,
): TimelineSourceNavigator {
  const { sourceMapRuntime } = options;

  return {
    navigateToSource(extensionId: string, targetId: string): boolean {
      const entries = sourceMapRuntime.getForTarget(extensionId, targetId);
      if (entries.length === 0) return false;

      for (const entry of entries) {
        const detail: TimelineNavigateToSourceDetail = {
          extensionId: entry.source,
          sourceMapEntryId: entry.id,
          targetId: entry.targetId,
          sourceUri: entry.sourceUri,
          sourceStartLine: entry.sourceStartLine,
          sourceStartColumn: entry.sourceStartColumn,
          sourceEndLine: entry.sourceEndLine,
          sourceEndColumn: entry.sourceEndColumn,
          stale: entry.stale,
        };
        requestNavigateTimelineToSource(detail);
      }
      return true;
    },

    hasSourceMapEntries(extensionId: string, targetId: string): boolean {
      return sourceMapRuntime.getForTarget(extensionId, targetId).length > 0;
    },

    hasStaleSourceMapEntries(extensionId: string, targetId: string): boolean {
      return sourceMapRuntime
        .getForTarget(extensionId, targetId)
        .some((e) => e.stale);
    },

    getStaleStatus(extensionId: string, targetId: string) {
      const entries = sourceMapRuntime.getForTarget(extensionId, targetId);
      const staleEntries = entries.filter((e) => e.stale);
      const nonStaleEntries = entries.filter((e) => !e.stale);
      return {
        hasEntries: entries.length > 0,
        hasStale: staleEntries.length > 0,
        staleEntries,
        nonStaleEntries,
      };
    },
  };
}

// ---------------------------------------------------------------------------
// Source → Timeline navigation
// ---------------------------------------------------------------------------

export interface SourceTimelineNavigatorOptions {
  /** Active SourceMapRuntime for looking up entries. */
  sourceMapRuntime: SourceMapRuntime;
}

export interface SourceTimelineNavigator {
  /**
   * Navigate from a source range to affected timeline objects.
   *
   * Looks up all source-map entries whose sourceUri matches the given URI
   * and whose source range overlaps the given range, then dispatches
   * SOURCE_NAVIGATE_TO_TIMELINE_EVENT. If a specific targetId is provided,
   * additionally dispatches TIMELINE_CENTER_CLIP_EVENT for that target.
   *
   * @returns true if at least one matching entry was found.
   */
  navigateToTimeline(
    extensionId: string,
    sourceUri: string,
    sourceStartLine: number,
    sourceEndLine: number,
    targetId?: string,
  ): boolean;

  /**
   * Find all timeline targets affected by a source range.
   */
  findAffectedTargets(
    extensionId: string,
    sourceUri: string,
    sourceStartLine?: number,
    sourceEndLine?: number,
  ): SourceMapEntry[];

  /**
   * Check whether any source-map entries for a source URI are stale.
   */
  hasStaleEntriesForSource(extensionId: string, sourceUri: string): boolean;
}

/**
 * Check if two line ranges overlap.
 */
function rangesOverlap(
  aFrom: number, aTo: number,
  bFrom: number, bTo: number,
): boolean {
  return aFrom < bTo && bFrom < aTo;
}

/**
 * Create a source/code-panel-side timeline navigator.
 *
 * Usage from source/code panel:
 * ```ts
 * const navigator = createSourceTimelineNavigator({ sourceMapRuntime });
 * // On click of a source line:
 * navigator.navigateToTimeline('ext.dsl', sourceUri, lineStart, lineEnd);
 * ```
 */
export function createSourceTimelineNavigator(
  options: SourceTimelineNavigatorOptions,
): SourceTimelineNavigator {
  const { sourceMapRuntime } = options;

  return {
    navigateToTimeline(
      extensionId: string,
      sourceUri: string,
      sourceStartLine: number,
      sourceEndLine: number,
      targetId?: string,
    ): boolean {
      const allEntries = sourceMapRuntime.getForSource(extensionId, sourceUri);
      const matching = allEntries.filter((e) =>
        rangesOverlap(
          e.sourceStartLine,
          e.sourceEndLine,
          sourceStartLine,
          sourceEndLine,
        ),
      );

      if (matching.length === 0) {
        // No exact overlap — try wider match
        if (allEntries.length > 0) {
          const detail: SourceNavigateToTimelineDetail = {
            extensionId,
            sourceUri,
            sourceStartLine,
            sourceEndLine,
            targetId: allEntries[0].targetId,
          };
          requestNavigateSourceToTimeline(detail);
          return true;
        }
        return false;
      }

      // Dispatch navigate-to-timeline event
      const details: SourceNavigateToTimelineDetail = {
        extensionId,
        sourceUri,
        sourceStartLine,
        sourceEndLine,
        targetId: targetId ?? matching[0].targetId,
      };
      requestNavigateSourceToTimeline(details);

      // Also center on the first matching target
      if (matching[0]?.targetId) {
        requestCenterTimelineClip(matching[0].targetId);
      }

      return true;
    },

    findAffectedTargets(
      extensionId: string,
      sourceUri: string,
      sourceStartLine?: number,
      sourceEndLine?: number,
    ): SourceMapEntry[] {
      const allEntries = sourceMapRuntime.getForSource(extensionId, sourceUri);
      if (sourceStartLine === undefined || sourceEndLine === undefined) {
        return allEntries;
      }
      return allEntries.filter((e) =>
        rangesOverlap(
          e.sourceStartLine,
          e.sourceEndLine,
          sourceStartLine,
          sourceEndLine,
        ),
      );
    },

    hasStaleEntriesForSource(extensionId: string, sourceUri: string): boolean {
      return sourceMapRuntime
        .getForSource(extensionId, sourceUri)
        .some((e) => e.stale);
    },
  };
}
