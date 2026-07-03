/**
 * Timeline patch contracts — portable public contracts.
 *
 * Representative execution/process-like family boundary (M0 sanity check):
 * - Portable: operation-family vocabulary, patch/diff/preview shapes,
 *   diagnostics, and project-data limit contracts. These are data-only
 *   descriptions of intended timeline mutations; they do not execute.
 * - Host-only: the patch planner, runtime validation against actual timeline
 *   state, proposal execution, source-map resolution, React hooks/providers,
 *   and any behavior that needs DataProvider or browser APIs.
 *
 * @publicContract
 */

import type { DiagnosticSeverity } from '../../diagnostics';

/** Top-level operation families supported by TimelinePatch. */
export type TimelinePatchOpFamily =
  | 'clip.add'
  | 'clip.update'
  | 'clip.remove'
  | 'clip.move'
  | 'track.add'
  | 'track.update'
  | 'track.remove'
  | 'asset.update'
  | 'asset.remove'
  | 'app.update'
  | 'project-data.write'
  | 'project-data.delete'
  | 'extension.noop';

/** Reserved operation families that are validated but not executed in M3. */
export type TimelinePatchReservedOpFamily =
  | 'clip.split'
  | 'clip.slice'
  | 'graph.node.*'
  | 'graph.edge.*'
  | 'graph.group.*';

/** All known operation family strings (active + reserved). */
export type TimelinePatchAnyOpFamily =
  | TimelinePatchOpFamily
  | TimelinePatchReservedOpFamily;

/** Locked vocabulary for active TimelinePatch operation families. */
export const TIMELINE_PATCH_OP_FAMILIES = [
  'clip.add',
  'clip.update',
  'clip.remove',
  'clip.move',
  'track.add',
  'track.update',
  'track.remove',
  'asset.update',
  'asset.remove',
  'app.update',
  'project-data.write',
  'project-data.delete',
  'extension.noop',
] as const satisfies readonly TimelinePatchOpFamily[];
Object.freeze(TIMELINE_PATCH_OP_FAMILIES);

/** Locked vocabulary for reserved TimelinePatch operation families. */
export const TIMELINE_PATCH_RESERVED_OP_FAMILIES = [
  'clip.split',
  'clip.slice',
  'graph.node.*',
  'graph.edge.*',
  'graph.group.*',
] as const satisfies readonly TimelinePatchReservedOpFamily[];
Object.freeze(TIMELINE_PATCH_RESERVED_OP_FAMILIES);

/** Locked vocabulary for every known TimelinePatch operation family. */
export const TIMELINE_PATCH_ALL_OP_FAMILIES = [
  ...TIMELINE_PATCH_OP_FAMILIES,
  ...TIMELINE_PATCH_RESERVED_OP_FAMILIES,
] as const satisfies readonly TimelinePatchAnyOpFamily[];
Object.freeze(TIMELINE_PATCH_ALL_OP_FAMILIES);

/**
 * A single semantic operation in a TimelinePatch batch.
 *
 * Every operation carries an `op` family, a `target` object identifier
 * (clip ID, track ID, asset key, extension ID, etc.), and an optional
 * `payload` whose shape is family-dependent.
 */
export interface TimelinePatchOperation {
  /** Operation family, e.g. "clip.add", "track.update". */
  readonly op: TimelinePatchAnyOpFamily;
  /** Object identifier scoped to the operation family. */
  readonly target: string;
  /** Family-dependent payload. */
  readonly payload?: Record<string, unknown>;
  /**
   * Sortable anchor for ordering-dependent operations (clip.move, etc.).
   * Interpreted by the patch compiler; ignored for order-independent ops.
   */
  readonly order?: number;
}

/** A batch of TimelinePatch operations applied atomically. */
export interface TimelinePatch {
  /** Monotonically-increasing batch version assigned by the runtime. */
  readonly version: number;
  /** Ordered list of operations in this batch. */
  readonly operations: readonly TimelinePatchOperation[];
  /** Extension or source that produced this patch. */
  readonly source?: string;
  /** Opaque metadata attached by the producer. */
  readonly meta?: Record<string, unknown>;
}

/**
 * Structured diagnostic produced by TimelinePatch validation or compilation.
 *
 * Diagnostics are exportable to the host diagnostic panel and carry enough
 * context to navigate from the diagnostic to the offending operation/payload.
 */
export interface TimelinePatchDiagnostic {
  readonly severity: DiagnosticSeverity;
  /** Stable diagnostic code, e.g. "timeline-patch/unknown-op". */
  readonly code: `timeline-patch/${string}`;
  readonly message: string;
  /** Zero-based index into the patch operation list, when applicable. */
  readonly operationIndex?: number;
  /** The operation family that triggered the diagnostic. */
  readonly op?: TimelinePatchAnyOpFamily;
  /** The target identifier from the offending operation. */
  readonly target?: string;
  /** Structured detail (expected type, actual value, constraint, etc.). */
  readonly detail?: Record<string, unknown>;
}

/** Result of validating a TimelinePatch batch. */
export interface TimelinePatchValidationResult {
  /** True when every operation in the batch passes validation. */
  readonly valid: boolean;
  /** Diagnostics produced during validation (empty when valid). */
  readonly diagnostics: readonly TimelinePatchDiagnostic[];
}

/** Granularity of a diff entry. */
export type TimelineDiffGranularity =
  | 'clip'
  | 'track'
  | 'asset'
  | 'app'
  | 'project-data'
  | 'graph'
  | 'node'
  | 'edge';

/** Locked vocabulary for diff entry granularity. */
export const TIMELINE_DIFF_GRANULARITIES = [
  'clip',
  'track',
  'asset',
  'app',
  'project-data',
  'graph',
  'node',
  'edge',
] as const satisfies readonly TimelineDiffGranularity[];
Object.freeze(TIMELINE_DIFF_GRANULARITIES);

/** The kind of change represented by a diff entry. */
export type TimelineDiffKind = 'added' | 'removed' | 'modified' | 'reordered';

/** Locked vocabulary for semantic diff entry kinds. */
export const TIMELINE_DIFF_KINDS = [
  'added',
  'removed',
  'modified',
  'reordered',
] as const satisfies readonly TimelineDiffKind[];
Object.freeze(TIMELINE_DIFF_KINDS);

/** A single entry in a TimelineDiff describing what changed. */
export interface TimelineDiffEntry {
  readonly granularity: TimelineDiffGranularity;
  readonly kind: TimelineDiffKind;
  /** Object identifier (clip ID, track ID, asset key, extension ID, etc.). */
  readonly target: string;
  /** The operation family that produced this change. */
  readonly op: TimelinePatchAnyOpFamily;
  /**
   * Pre-mutation value snapshot (summary). Omitted for 'added' entries.
   * Never exposes raw internal row/meta shapes.
   */
  readonly before?: Record<string, unknown>;
  /**
   * Post-mutation value snapshot (summary). Omitted for 'removed' entries.
   * Never exposes raw internal row/meta shapes.
   */
  readonly after?: Record<string, unknown>;
}

/**
 * Semantic diff describing what a patch batch changed.
 *
 * This is the public change description. It never exposes raw internal
 * timeline row data, provider metadata, or mutation engine internals.
 */
export interface TimelineDiff {
  /** The patch version this diff corresponds to. */
  readonly version: number;
  /** Ordered list of changes produced by the patch. */
  readonly entries: readonly TimelineDiffEntry[];
  /** Set of all object IDs affected by this patch. */
  readonly affectedObjectIds: readonly string[];
}

/** Result of previewing a patch batch against current timeline state. */
export interface TimelinePreviewResult {
  /** The projected diff if the patch were applied. */
  readonly diff: TimelineDiff;
  /**
   * Whether every operation in the patch is previewable.
   * Non-previewable operations still produce diagnostics but the diff may be incomplete.
   */
  readonly fullyPreviewable: boolean;
  /** Diagnostics for non-previewable or problematic operations. */
  readonly diagnostics: readonly TimelinePatchDiagnostic[];
}

/** Diagnostic codes produced when project-data limits are exceeded. */
export type ProjectDataLimitCode =
  | 'project-data/entry-size-exceeded'
  | 'project-data/extension-total-exceeded'
  | 'project-data/entry-count-exceeded';

/**
 * Hard limits on extension-owned project data stored in TimelineConfig.app.
 *
 * These limits are enforced by the patch compiler and the project-data
 * validation path. Exceeding any limit produces a diagnostic.
 */
export const EXTENSION_PROJECT_DATA_LIMITS = {
  /** Maximum size in bytes for a single project-data entry (JSON-serialized). */
  MAX_ENTRY_BYTES: 64 * 1024,
  /** Maximum total size in bytes for all entries owned by one extension. */
  MAX_EXTENSION_TOTAL_BYTES: 1 * 1024 * 1024,
  /** Maximum number of entries one extension may store. */
  MAX_ENTRIES_PER_EXTENSION: 128,
} as const;

/**
 * Structured detail carried in TimelinePatchDiagnostic.detail when a
 * project-data limit is exceeded.
 */
export interface ProjectDataLimitDetail {
  readonly extensionId: string;
  readonly limit: number;
  readonly actual: number;
  readonly unit: 'bytes' | 'entries';
  readonly code: ProjectDataLimitCode;
}
