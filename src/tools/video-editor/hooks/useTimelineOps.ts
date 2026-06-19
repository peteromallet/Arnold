/**
 * useTimelineOps — host adapter that produces a stable TimelineOps instance
 * wired to the existing commitData/history path.
 *
 * Extensions and proposal machinery receive this adapter through
 * CreativeContext.timeline.  It wraps the pure compiler functions
 * (validateTimelinePatch / compileTimelinePatch / previewTimelinePatch)
 * and delegates checkpoint/rollback to the host history module.
 *
 * @publicContract — only exposes the TimelineOps surface; never leaks
 *   raw TimelineData, applyEdit, provider handles, or store internals.
 */

import { useCallback, useMemo, useRef } from 'react';
import type {
  TimelineOps,
  TimelinePatch,
  TimelinePatchValidationResult,
  TimelinePreviewResult,
  TimelineDiff,
} from '@/sdk/index';
import {
  validateTimelinePatch,
  compileTimelinePatch,
  previewTimelinePatch,
} from '@/tools/video-editor/lib/timeline-patch';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data';
import type { CommitDataOptions } from '@/tools/video-editor/hooks/useTimelineCommit';
import type { Checkpoint } from '@/tools/video-editor/types/history';
import { TimelineVersionConflictError } from '@/tools/video-editor/data/DataProvider';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Generate a compact unique ID for checkpoint tracking. */
function uid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `ckpt-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
}

// ---------------------------------------------------------------------------
// Argument types
// ---------------------------------------------------------------------------

export interface UseTimelineOpsArgs {
  /** Stable commitData from useTimelineCommit / useTimelineSave. */
  commitData: (nextData: TimelineData, options?: CommitDataOptions) => void;

  /** Mutable ref holding the current canonical TimelineData. */
  dataRef: { current: TimelineData | null };

  /** Host checkpoint creation (async fire-and-forget). */
  createManualCheckpoint: (label?: string) => Promise<void>;

  /** Host checkpoint restoration. */
  jumpToCheckpoint: (checkpointId: string) => void;

  /** Current checkpoint list (for existence checks). */
  checkpoints: Checkpoint[];
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Create a stable {@link TimelineOps} adapter wired to the host commit and
 * history pipeline.
 *
 * Every method that reads timeline state accesses `dataRef.current` at call
 * time so the adapter always operates on the latest canonical data without
 * re-creating the object on every render.
 *
 * ## Base-version semantics
 *
 * Every `apply()` call compares the patch's `version` field (the base version
 * the patch was built against) with the current `dataRef.current.configVersion`.
 * If they differ the patch is stale and a {@link TimelineVersionConflictError}
 * is thrown before any mutation occurs.
 *
 * This is the **local monotonic invalidation** layer: it catches stale patches
 * before they reach the provider, which is essential when the provider does
 * not enforce strict compare-and-swap on save (e.g. AstridBridge).  When the
 * provider *does* enforce CAS the provider layer adds a second line of defence.
 *
 * Version 0 is treated as "no base-version expectation" (initial patches,
 * extensions that intentionally bypass version gating).
 */
export function useTimelineOps({
  commitData,
  dataRef,
  createManualCheckpoint,
  jumpToCheckpoint,
  checkpoints,
}: UseTimelineOpsArgs): TimelineOps {
  // Keep checkpoints in a ref so synchronous rollback lookups are always
  // against the latest list without re-creating the adapter on every change.
  const checkpointsRef = useRef(checkpoints);
  checkpointsRef.current = checkpoints;

  // Map client-generated checkpoint IDs to labels so rollback can resolve
  // them against the backend-populated checkpoints list.
  const pendingLabels = useRef<Map<string, string>>(new Map());

  // ---- validate -----------------------------------------------------------

  const validate = useCallback(
    (patch: TimelinePatch): TimelinePatchValidationResult => {
      return validateTimelinePatch(patch);
    },
    [],
  );

  // ---- preview ------------------------------------------------------------

  const preview = useCallback(
    (patch: TimelinePatch): TimelinePreviewResult => {
      const current = dataRef.current;
      if (!current) {
        return {
          diff: { version: patch.version, entries: [], affectedObjectIds: [] },
          fullyPreviewable: false,
          diagnostics: [
            {
              severity: 'error',
              code: 'timeline-patch/no-data',
              message: 'Timeline data is not yet loaded.',
            },
          ],
        };
      }

      const result = previewTimelinePatch(patch, current);

      // Attach a stale-base-version warning when the patch was built against
      // a different version than the current canonical state.  Preview is
      // read-only, so we warn rather than block.
      if (
        patch.version !== 0 &&
        patch.version !== current.configVersion &&
        result.fullyPreviewable
      ) {
        result.diagnostics = [
          ...result.diagnostics,
          {
            severity: 'warning' as const,
            code: 'timeline-patch/stale-base-version' as const,
            message:
              `Preview: patch baseVersion (${patch.version}) does not match ` +
              `current timeline version (${current.configVersion}). ` +
              `The preview may not reflect the current state. Re-snapshot ` +
              `to get an accurate preview.`,
          },
        ];
      }

      return result;
    },
    [dataRef],
  );

  // ---- apply --------------------------------------------------------------

  const apply = useCallback(
    (patch: TimelinePatch): TimelineDiff => {
      // 0. Guard against no data
      const current = dataRef.current;
      if (!current) {
        throw new Error('TimelineOps.apply: timeline data is not yet loaded.');
      }

      // 0a. Base-version staleness check (local monotonic invalidation).
      //
      //     The patch.version is the base version the caller observed when
      //     building the patch.  If it doesn't match the current canonical
      //     configVersion the timeline has been modified since the patch was
      //     created — the patch is stale and must be rejected.
      //
      //     Version 0 is treated as "no base-version expectation" (e.g.
      //     initial patches before the first provider load or patches from
      //     extensions that intentionally bypass version gating).
      if (patch.version !== 0 && patch.version !== current.configVersion) {
        throw new TimelineVersionConflictError(
          `TimelineOps.apply: stale baseVersion — ` +
          `patch created at version ${patch.version} but timeline is at ` +
          `version ${current.configVersion}. ` +
          `Re-read the current snapshot and rebuild the patch.`,
        );
      }

      // 1. Validate the full batch
      const validation = validateTimelinePatch(patch);
      if (!validation.valid) {
        const messages = validation.diagnostics
          .filter((d) => d.severity === 'error')
          .map((d) => d.message)
          .join('; ');
        throw new Error(
          `TimelineOps.apply: patch validation failed. ${messages}`,
        );
      }

      // 2. Compile against current canonical data
      const compiled = compileTimelinePatch(patch, current);
      if (!compiled.valid || !compiled.nextData) {
        const messages = compiled.diagnostics
          .filter((d) => d.severity === 'error')
          .map((d) => d.message)
          .join('; ');
        throw new Error(
          `TimelineOps.apply: patch compilation failed. ${messages}`,
        );
      }

      // 3. Commit once through commitData with semantic transaction metadata.
      //    History recording is enabled by default (skipHistory defaults to false).
      commitData(compiled.nextData, {
        save: true,
        semantic: true,
      });

      // 4. Return the semantic diff
      return compiled.diff;
    },
    [commitData, dataRef],
  );

  // ---- checkpoint ---------------------------------------------------------

  const checkpoint = useCallback(
    (label?: string): string => {
      const id = uid();
      const effectiveLabel = label ?? `Patch checkpoint ${id.slice(0, 8)}`;
      pendingLabels.current.set(id, effectiveLabel);
      // Fire-and-forget: the host persists the checkpoint asynchronously.
      // The backend-generated ID will appear in the checkpoints list with
      // the same label, allowing rollback to resolve the client ID.
      void createManualCheckpoint(effectiveLabel);
      return id;
    },
    [createManualCheckpoint],
  );

  // ---- rollback -----------------------------------------------------------

  const rollback = useCallback(
    (checkpointId: string): TimelineDiff | null => {
      const currentCheckpoints = checkpointsRef.current;

      // Resolve the checkpoint: first try an exact ID match, then fall back
      // to label-based lookup for client-generated IDs.
      let resolvedId: string | null = null;

      const exactMatch = currentCheckpoints.find((c) => c.id === checkpointId);
      if (exactMatch) {
        resolvedId = exactMatch.id;
      } else {
        // Try label-based resolution for client-generated IDs.
        const label = pendingLabels.current.get(checkpointId);
        if (label) {
          const labelMatch = currentCheckpoints.find((c) => c.label === label);
          if (labelMatch) {
            resolvedId = labelMatch.id;
            pendingLabels.current.delete(checkpointId);
          }
        }
      }

      if (!resolvedId) {
        return null;
      }

      // Capture a snapshot of the pre-rollback state for the diff
      const beforeData = dataRef.current;

      jumpToCheckpoint(resolvedId);

      // Build a minimal rollback diff
      const afterData = dataRef.current;
      const affectedIds: string[] = [];
      if (beforeData) {
        for (const track of beforeData.tracks) {
          affectedIds.push(track.id);
        }
      }
      if (afterData) {
        for (const track of afterData.tracks) {
          if (!affectedIds.includes(track.id)) {
            affectedIds.push(track.id);
          }
        }
      }

      return {
        version: afterData?.configVersion ?? 0,
        entries: [
          {
            granularity: 'track',
            kind: 'modified',
            target: 'timeline',
            op: 'track.update',
            before: beforeData
              ? { configVersion: beforeData.configVersion }
              : undefined,
            after: afterData
              ? { configVersion: afterData.configVersion }
              : undefined,
          },
        ],
        affectedObjectIds: affectedIds,
      };
    },
    [dataRef, jumpToCheckpoint],
  );

  // ---- setAllTracksMuted --------------------------------------------------

  const setAllTracksMuted = useCallback(
    (muted: boolean): TimelineDiff => {
      const current = dataRef.current;
      if (!current) {
        throw new Error(
          'TimelineOps.setAllTracksMuted: timeline data is not yet loaded.',
        );
      }

      // Find all audio tracks
      const audioTracks = current.tracks.filter((t) => t.kind === 'audio');

      if (audioTracks.length === 0) {
        return {
          version: current.configVersion,
          entries: [],
          affectedObjectIds: [],
        };
      }

      // Build a patch with track.update for each audio track.
      // The version is set to current.configVersion so the base-version
      // check in apply() will pass.
      const patch: TimelinePatch = {
        version: current.configVersion,
        operations: audioTracks.map((track) => ({
          op: 'track.update' as const,
          target: track.id,
          payload: { muted },
          mergeMode: 'merge' as const,
        })),
      };

      // Re-use apply which validates, compiles, and commits
      return apply(patch);
    },
    [apply, dataRef],
  );

  // ---- assemble stable adapter --------------------------------------------

  return useMemo<TimelineOps>(
    () => ({
      validate,
      preview,
      apply,
      checkpoint,
      rollback,
      setAllTracksMuted,
    }),
    [validate, preview, apply, checkpoint, rollback, setAllTracksMuted],
  );
}
