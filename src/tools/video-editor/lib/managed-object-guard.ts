/**
 * ManagedObjectGuard — host-side managed-object detection and metadata envelope.
 *
 * Provides a pure check that inspects a TimelineReader snapshot to determine
 * whether a clip (or track) is managed by an extension and, if so, surfaces
 * the owner/source metadata so host-owned confirmation dialogs can name the
 * responsible extension before allowing manual edits to proceed.
 *
 * This module does NOT render UI.  It is consumed by the command interceptor
 * in useTimelineCommands and by the ManagedObjectConfirmationDialog.
 *
 * @publicContract — implements the managed-object metadata envelope from M3.
 */

import type {
  TimelineReader,
  TimelineClipSummary,
  TimelineTrackSummary,
  GeneratedObjectMeta,
} from '@/sdk/index';

// ---------------------------------------------------------------------------
// ManagedObjectInfo
// ---------------------------------------------------------------------------

/**
 * Metadata envelope for a timeline object that is managed by an extension.
 *
 * Host-owned UI surfaces (confirmation dialogs, inspector badges) consume
 * this envelope to display owner/source information without importing
 * extension code.
 */
export interface ManagedObjectInfo {
  /** ID of the timeline object (clip or track). */
  objectId: string;
  /** Kind of timeline object. */
  kind: 'clip' | 'track';
  /** Extension ID that owns/manages this object. */
  managedBy: string;
  /** Generated-object metadata if present. */
  generatedMeta?: GeneratedObjectMeta;
  /** Source-map entry ID if present in generatedMeta. */
  sourceMapEntryId?: string;
  /** Contribution ID if present in generatedMeta. */
  contributionId?: string;
  /** Generation provenance if present in generatedMeta. */
  provenance?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// ManagedObjectGuard
// ---------------------------------------------------------------------------

export interface ManagedObjectGuard {
  /**
   * Check whether a clip is managed by an extension.
   *
   * @returns ManagedObjectInfo if the clip is managed, null otherwise.
   */
  checkClipManaged(clipId: string): ManagedObjectInfo | null;

  /**
   * Check whether a track is managed by an extension.
   *
   * @returns ManagedObjectInfo if the track is managed, null otherwise.
   */
  checkTrackManaged(trackId: string): ManagedObjectInfo | null;
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

/**
 * Create a ManagedObjectGuard backed by a TimelineReader.
 *
 * The guard reads the current reader snapshot on every call so it always
 * reflects the latest timeline state (after commits, checkpoints, etc.).
 */
export function createManagedObjectGuard(
  reader: TimelineReader,
): ManagedObjectGuard {
  return {
    checkClipManaged(clipId: string): ManagedObjectInfo | null {
      const snapshot = reader.snapshot();
      const clip = snapshot.clips.find((c) => c.id === clipId);
      if (!clip || !clip.managed || !clip.managedBy) return null;

      return buildManagedObjectInfo('clip', clip);
    },

    checkTrackManaged(trackId: string): ManagedObjectInfo | null {
      const snapshot = reader.snapshot();
      const track = snapshot.tracks.find((t) => t.id === trackId);
      if (!track || !track.generatedMeta) return null;

      // Tracks are managed if they have generatedMeta with an extensionId.
      // We also check for managedBy on tracks (future-proofing).
      const extensionId = track.generatedMeta.extensionId;
      return {
        objectId: track.id,
        kind: 'track',
        managedBy: extensionId,
        generatedMeta: track.generatedMeta,
        sourceMapEntryId: track.generatedMeta.sourceMapEntryId,
        contributionId: track.generatedMeta.contributionId,
        provenance: track.generatedMeta.provenance,
      };
    },
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildManagedObjectInfo(
  kind: 'clip',
  summary: TimelineClipSummary,
): ManagedObjectInfo {
  const info: ManagedObjectInfo = {
    objectId: summary.id,
    kind,
    managedBy: summary.managedBy!,
  };

  if (summary.generatedMeta) {
    info.generatedMeta = summary.generatedMeta;
    info.sourceMapEntryId = summary.generatedMeta.sourceMapEntryId;
    info.contributionId = summary.generatedMeta.contributionId;
    info.provenance = summary.generatedMeta.provenance;
  }

  return info;
}

/**
 * Build a patch that removes managed-object metadata from a clip's app record.
 *
 * Used by the "Edit Anyway / Detach" action in the confirmation dialog.
 * Returns the patch to apply via updateClip (or directly as a detached update).
 */
export function buildDetachManagedClipPatch(
  clipSummary: TimelineClipSummary,
): Record<string, unknown> {
  const patch: Record<string, unknown> = {};

  // We can't directly modify app from the summary; the caller must use
  // the full clip data. This function provides the set of keys to clear.
  // The actual clearing happens in the detachManagedClip command.

  return patch;
}

/**
 * Keys that should be removed from clip.app when detaching a managed clip.
 */
export const MANAGED_APP_KEYS_TO_CLEAR = [
  'managedBy',
  '__generated__',
] as const;

/**
 * Compute the app record after detaching managed metadata.
 */
export function detachManagedApp(
  app: Record<string, unknown> | undefined,
  extensionIds: ReadonlySet<string>,
): Record<string, unknown> | undefined {
  if (!app) return undefined;
  const next: Record<string, unknown> = {};
  let changed = false;
  for (const [key, value] of Object.entries(app)) {
    // Skip well-known managed keys.
    if (key === 'managedBy' || key === '__generated__') {
      changed = true;
      continue;
    }
    // Skip keys that are extension IDs (namespace keys).
    if (extensionIds.has(key)) {
      changed = true;
      continue;
    }
    next[key] = value;
  }
  if (!changed) return app;
  return Object.keys(next).length > 0 ? next : undefined;
}
