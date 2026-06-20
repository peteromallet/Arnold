/**
 * TimelinePatch pure validation, compilation, and preview.
 *
 * Validates, compiles, and previews TimelinePatch batches against the M3
 * public contract types defined in @reigh/editor-sdk.  This module is
 * intentionally pure — it does not import DataProvider, useTimelineCommit,
 * or any editor-internal mutation / store / provider machinery.
 *
 * Compilation materializes a validated patch through the existing
 * config/row serialization paths (rowsToConfig, configToRows,
 * buildDataFromCurrentRegistry) to produce nextData and a semantic diff
 * without committing.
 *
 * @publicContract
 */

import type {
  DiagnosticSeverity,
  TimelinePatch,
  TimelinePatchAnyOpFamily,
  TimelinePatchDiagnostic,
  TimelinePatchOperation,
  TimelinePatchValidationResult,
  TimelineDiff,
  TimelineDiffEntry,
  TimelineDiffGranularity,
  TimelineDiffKind,
  TimelinePreviewResult,
  ProjectDataLimitDetail,
} from '@/sdk/index';

import {
  validateExtensionId,
  EXTENSION_PROJECT_DATA_LIMITS,
} from '@/sdk/index';

import {
  configToRows,
  rowsToConfig,
  assembleTimelineData,
  type TimelineData,
  type ClipMeta,
  type ClipOrderMap,
} from '@/tools/video-editor/lib/timeline-data';

import type { TimelineEditMutation } from '@/tools/video-editor/hooks/useTimelineCommit';

import { buildDataFromCurrentRegistry } from '@/tools/video-editor/lib/timeline-save-utils';

import type {
  TimelineClip,
  TimelineClipShaderMetadata,
  TimelinePostprocessShaderMetadata,
  TrackDefinition,
} from '@/tools/video-editor/types/index';

import {
  TIMELINE_POSTPROCESS_SHADER_APP_KEY,
  assignTimelineClipShader,
  assignTimelinePostprocessShader,
} from '@/tools/video-editor/lib/timeline-domain';



// ---------------------------------------------------------------------------
// Reserved operation families
// ---------------------------------------------------------------------------

/** Operation families that are validated but deferred (not executed in M3). */
const RESERVED_OPS: ReadonlySet<TimelinePatchAnyOpFamily> = new Set([
  'clip.split',
  'clip.slice',
]);

/**
 * Active operation families that the validator must accept.
 * The full set is also defined in the SDK contract; this module mirrors it
 * so validation is self-contained.
 */
const ACTIVE_OPS: ReadonlySet<TimelinePatchAnyOpFamily> = new Set([
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
]);

const ALL_KNOWN_OPS: ReadonlySet<TimelinePatchAnyOpFamily> = new Set([
  ...Array.from(ACTIVE_OPS),
  ...Array.from(RESERVED_OPS),
]);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function diag(
  severity: DiagnosticSeverity,
  code: `timeline-patch/${string}`,
  message: string,
  overrides: Partial<TimelinePatchDiagnostic> = {},
): TimelinePatchDiagnostic {
  return { severity, code, message, ...overrides };
}

/** True when the extension ID syntax matches the SDK contract. */
function isValidExtensionId(id: string): boolean {
  return validateExtensionId(id).length === 0;
}

// ---------------------------------------------------------------------------
// Per-family payload validators
// ---------------------------------------------------------------------------

function validateClipAdd(
  op: TimelinePatchOperation,
  idx: number,
): TimelinePatchDiagnostic[] {
  const diags: TimelinePatchDiagnostic[] = [];
  const p = op.payload;
  if (p && p.track !== undefined && typeof p.track !== 'string') {
    diags.push(
      diag('error', 'timeline-patch/invalid-payload', 'clip.add: payload.track must be a string', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
        detail: { key: 'track', expected: 'string', actual: typeof p.track },
      }),
    );
  }
  if (p && p.at !== undefined && typeof p.at !== 'number') {
    diags.push(
      diag('error', 'timeline-patch/invalid-payload', 'clip.add: payload.at must be a number', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
        detail: { key: 'at', expected: 'number', actual: typeof p.at },
      }),
    );
  }
  if (p && p.clipType !== undefined && typeof p.clipType !== 'string') {
    diags.push(
      diag('error', 'timeline-patch/invalid-payload', 'clip.add: payload.clipType must be a string', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
        detail: { key: 'clipType', expected: 'string', actual: typeof p.clipType },
      }),
    );
  }
  return diags;
}

function validateClipUpdate(
  op: TimelinePatchOperation,
  idx: number,
): TimelinePatchDiagnostic[] {
  const diags: TimelinePatchDiagnostic[] = [];
  const p = op.payload;

  // Validate mode if present
  if (p && p.mode !== undefined) {
    if (p.mode !== 'merge' && p.mode !== 'replace') {
      diags.push(
        diag('error', 'timeline-patch/invalid-payload', 'clip.update: payload.mode must be "merge" or "replace"', {
          operationIndex: idx,
          op: op.op,
          target: op.target,
          detail: { key: 'mode', expected: '"merge" | "replace"', actual: p.mode },
        }),
      );
    }
  }

  // clip.update should have at least one updateable field (not just mode)
  const updateableKeys = p ? Object.keys(p).filter((k) => k !== 'mode') : [];
  if (!p || updateableKeys.length === 0) {
    diags.push(
      diag('warning', 'timeline-patch/empty-payload', 'clip.update: payload has no updateable fields', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
      }),
    );
  }
  return diags;
}

function validateClipMove(
  op: TimelinePatchOperation,
  idx: number,
): TimelinePatchDiagnostic[] {
  const diags: TimelinePatchDiagnostic[] = [];
  const p = op.payload;

  // At least one of track, at, before, after must be present
  if (!p || (p.track === undefined && p.at === undefined && p.before === undefined && p.after === undefined)) {
    diags.push(
      diag('error', 'timeline-patch/invalid-payload', 'clip.move: payload must contain track, at, before, and/or after', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
      }),
    );
  }
  if (p) {
    if (p.track !== undefined && typeof p.track !== 'string') {
      diags.push(
        diag('error', 'timeline-patch/invalid-payload', 'clip.move: payload.track must be a string', {
          operationIndex: idx,
          op: op.op,
          target: op.target,
          detail: { key: 'track', expected: 'string', actual: typeof p.track },
        }),
      );
    }
    if (p.at !== undefined && typeof p.at !== 'number') {
      diags.push(
        diag('error', 'timeline-patch/invalid-payload', 'clip.move: payload.at must be a number', {
          operationIndex: idx,
          op: op.op,
          target: op.target,
          detail: { key: 'at', expected: 'number', actual: typeof p.at },
        }),
      );
    }
    if (p.before !== undefined && typeof p.before !== 'string') {
      diags.push(
        diag('error', 'timeline-patch/invalid-payload', 'clip.move: payload.before must be a string (clip ID)', {
          operationIndex: idx,
          op: op.op,
          target: op.target,
          detail: { key: 'before', expected: 'string', actual: typeof p.before },
        }),
      );
    }
    if (p.after !== undefined && typeof p.after !== 'string') {
      diags.push(
        diag('error', 'timeline-patch/invalid-payload', 'clip.move: payload.after must be a string (clip ID)', {
          operationIndex: idx,
          op: op.op,
          target: op.target,
          detail: { key: 'after', expected: 'string', actual: typeof p.after },
        }),
      );
    }
    if (p.before !== undefined && p.after !== undefined && p.before === p.after) {
      diags.push(
        diag('warning', 'timeline-patch/invalid-payload', 'clip.move: payload.before and payload.after cannot be the same clip', {
          operationIndex: idx,
          op: op.op,
          target: op.target,
          detail: { key: 'before/after', conflict: p.before },
        }),
      );
    }
  }
  return diags;
}

function validateTrackAdd(
  op: TimelinePatchOperation,
  idx: number,
): TimelinePatchDiagnostic[] {
  const diags: TimelinePatchDiagnostic[] = [];
  const p = op.payload;
  if (!p || !p.kind) {
    diags.push(
      diag('error', 'timeline-patch/missing-payload-key', 'track.add: payload.kind is required', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
        detail: { key: 'kind', required: true },
      }),
    );
  } else if (p.kind !== 'visual' && p.kind !== 'audio') {
    diags.push(
      diag('error', 'timeline-patch/invalid-payload', 'track.add: payload.kind must be "visual" or "audio"', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
        detail: { key: 'kind', expected: '"visual" | "audio"', actual: String(p.kind) },
      }),
    );
  }
  if (p && p.label !== undefined && typeof p.label !== 'string') {
    diags.push(
      diag('error', 'timeline-patch/invalid-payload', 'track.add: payload.label must be a string', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
        detail: { key: 'label', expected: 'string', actual: typeof p.label },
      }),
    );
  }
  return diags;
}

function validateTrackUpdate(
  op: TimelinePatchOperation,
  idx: number,
): TimelinePatchDiagnostic[] {
  const diags: TimelinePatchDiagnostic[] = [];
  const p = op.payload;

  // Validate mode if present
  if (p && p.mode !== undefined) {
    if (p.mode !== 'merge' && p.mode !== 'replace') {
      diags.push(
        diag('error', 'timeline-patch/invalid-payload', 'track.update: payload.mode must be "merge" or "replace"', {
          operationIndex: idx,
          op: op.op,
          target: op.target,
          detail: { key: 'mode', expected: '"merge" | "replace"', actual: p.mode },
        }),
      );
    }
  }

  const updateableKeys = p ? Object.keys(p).filter((k) => k !== 'mode') : [];
  if (!p || updateableKeys.length === 0) {
    diags.push(
      diag('warning', 'timeline-patch/empty-payload', 'track.update: payload has no updateable fields', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
      }),
    );
  }
  if (p) {
    if (p.kind !== undefined && p.kind !== 'visual' && p.kind !== 'audio') {
      diags.push(
        diag('error', 'timeline-patch/invalid-payload', 'track.update: payload.kind must be "visual" or "audio"', {
          operationIndex: idx,
          op: op.op,
          target: op.target,
          detail: { key: 'kind', expected: '"visual" | "audio"', actual: String(p.kind) },
        }),
      );
    }
    if (p.label !== undefined && typeof p.label !== 'string') {
      diags.push(
        diag('error', 'timeline-patch/invalid-payload', 'track.update: payload.label must be a string', {
          operationIndex: idx,
          op: op.op,
          target: op.target,
          detail: { key: 'label', expected: 'string', actual: typeof p.label },
        }),
      );
    }
    if (p.muted !== undefined && typeof p.muted !== 'boolean') {
      diags.push(
        diag('error', 'timeline-patch/invalid-payload', 'track.update: payload.muted must be a boolean', {
          operationIndex: idx,
          op: op.op,
          target: op.target,
          detail: { key: 'muted', expected: 'boolean', actual: typeof p.muted },
        }),
      );
    }
  }
  return diags;
}

function validateAppUpdate(
  op: TimelinePatchOperation,
  idx: number,
): TimelinePatchDiagnostic[] {
  const diags: TimelinePatchDiagnostic[] = [];
  if (!isValidExtensionId(op.target)) {
    diags.push(
      diag('error', 'timeline-patch/invalid-target', 'app.update: target must be a valid extension ID', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
      }),
    );
  }

  const p = op.payload;
  // Validate mode if present
  if (p && p.mode !== undefined && p.mode !== 'merge' && p.mode !== 'replace') {
    diags.push(
      diag('error', 'timeline-patch/invalid-payload', 'app.update: payload.mode must be "merge" or "replace"', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
        detail: { key: 'mode', expected: '"merge" | "replace"', actual: p.mode },
      }),
    );
  }

  const updateableKeys = p ? Object.keys(p).filter((k) => k !== 'mode') : [];
  if (!p || typeof p !== 'object' || updateableKeys.length === 0) {
    diags.push(
      diag('error', 'timeline-patch/missing-payload-key', 'app.update: payload with at least one key is required', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
      }),
    );
  }
  return diags;
}

function validateProjectDataWrite(
  op: TimelinePatchOperation,
  idx: number,
): TimelinePatchDiagnostic[] {
  const diags: TimelinePatchDiagnostic[] = [];
  if (!isValidExtensionId(op.target)) {
    diags.push(
      diag('error', 'timeline-patch/invalid-target', 'project-data.write: target must be a valid extension ID', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
      }),
    );
  }
  const p = op.payload;

  // Validate mode if present
  if (p && p.mode !== undefined && p.mode !== 'merge' && p.mode !== 'replace') {
    diags.push(
      diag('error', 'timeline-patch/invalid-payload', 'project-data.write: payload.mode must be "merge" or "replace"', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
        detail: { key: 'mode', expected: '"merge" | "replace"', actual: p.mode },
      }),
    );
  }

  if (!p || typeof p.key !== 'string' || p.key.length === 0) {
    diags.push(
      diag('error', 'timeline-patch/missing-payload-key', 'project-data.write: payload.key is required (non-empty string)', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
        detail: { key: 'key', required: true },
      }),
    );
  }
  if (p && p.value === undefined) {
    diags.push(
      diag('error', 'timeline-patch/missing-payload-key', 'project-data.write: payload.value is required', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
        detail: { key: 'value', required: true },
      }),
    );
  }
  // ── Entry-size overflow check ─────────────────────────────────────────
  if (p && p.value !== undefined) {
    try {
      const serialized = JSON.stringify(p.value);
      if (serialized.length > EXTENSION_PROJECT_DATA_LIMITS.MAX_ENTRY_BYTES) {
        diags.push(
          diag('error', 'timeline-patch/project-data-overflow', `project-data.write: value exceeds MAX_ENTRY_BYTES (${EXTENSION_PROJECT_DATA_LIMITS.MAX_ENTRY_BYTES})`, {
            operationIndex: idx,
            op: op.op,
            target: op.target,
            detail: {
              code: 'project-data/entry-size-exceeded' as const,
              extensionId: op.target,
              limit: EXTENSION_PROJECT_DATA_LIMITS.MAX_ENTRY_BYTES,
              actual: serialized.length,
              unit: 'bytes' as const,
            },
          }),
        );
      }
    } catch {
      // Non-serializable value — already caught by higher-level checks
    }
  }
  return diags;
}

function validateProjectDataDelete(
  op: TimelinePatchOperation,
  idx: number,
): TimelinePatchDiagnostic[] {
  const diags: TimelinePatchDiagnostic[] = [];
  if (!isValidExtensionId(op.target)) {
    diags.push(
      diag('error', 'timeline-patch/invalid-target', 'project-data.delete: target must be a valid extension ID', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
      }),
    );
  }
  const p = op.payload;
  if (!p || typeof p.key !== 'string' || p.key.length === 0) {
    diags.push(
      diag('error', 'timeline-patch/missing-payload-key', 'project-data.delete: payload.key is required (non-empty string)', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
        detail: { key: 'key', required: true },
      }),
    );
  }
  return diags;
}

function validateExtensionNoop(
  op: TimelinePatchOperation,
  idx: number,
): TimelinePatchDiagnostic[] {
  const diags: TimelinePatchDiagnostic[] = [];
  if (!isValidExtensionId(op.target)) {
    diags.push(
      diag('error', 'timeline-patch/invalid-target', 'extension.noop: target must be a valid extension ID', {
        operationIndex: idx,
        op: op.op,
        target: op.target,
      }),
    );
  }
  return diags;
}

// ---------------------------------------------------------------------------
// Main validator
// ---------------------------------------------------------------------------

/**
 * Validate a TimelinePatch batch.
 *
 * Returns a {@link TimelinePatchValidationResult} with `valid: true` and an
 * empty diagnostics array when every operation passes.  Otherwise `valid`
 * is `false` and `diagnostics` contains at least one error-level entry.
 *
 * Validation rules (per operation):
 *
 * - **op** must be a known active or reserved operation family.
 * - **target** must be a non-empty string.
 * - **payload** shape is validated per family (see per-family validators above).
 * - Reserved operations (`clip.split`, `clip.slice`) produce **warning**
 *   diagnostics (non-blocking) marking them as deferred/non-previewable.
 * - Unknown or malformed operations produce **error** diagnostics.
 *
 * Batch-level rules:
 * - `version` must be a positive integer.
 * - `operations` must be a non-empty array.
 *
 * All diagnostics carry `source: "timeline-patch"` semantics through the
 * `timeline-patch/` diagnostic code prefix.
 */
export function validateTimelinePatch(
  patch: TimelinePatch,
): TimelinePatchValidationResult {
  const diagnostics: TimelinePatchDiagnostic[] = [];

  // ── Batch-level checks ──────────────────────────────────────────────────

  if (typeof patch.version !== 'number' || !Number.isInteger(patch.version) || patch.version < 0) {
    diagnostics.push(
      diag('error', 'timeline-patch/invalid-version', `TimelinePatch.version must be a non-negative integer, got ${String(patch.version)}`),
    );
  }

  if (!Array.isArray(patch.operations)) {
    diagnostics.push(
      diag('error', 'timeline-patch/invalid-patch', 'TimelinePatch.operations must be an array'),
    );
    return { valid: false, diagnostics: Object.freeze(diagnostics) };
  }

  if (patch.operations.length === 0) {
    diagnostics.push(
      diag('error', 'timeline-patch/empty-operations', 'TimelinePatch.operations must contain at least one operation'),
    );
    return { valid: false, diagnostics: Object.freeze(diagnostics) };
  }

  // ── Per-operation checks ────────────────────────────────────────────────

  for (let i = 0; i < patch.operations.length; i++) {
    const op = patch.operations[i];
    const baseCtx = { operationIndex: i };

    // -- Structural checks -------------------------------------------------
    if (!op || typeof op !== 'object') {
      diagnostics.push(
        diag('error', 'timeline-patch/invalid-op', `operations[${i}] is not an object`, baseCtx),
      );
      continue;
    }

    // -- op family ---------------------------------------------------------
    if (typeof op.op !== 'string' || op.op.length === 0) {
      diagnostics.push(
        diag('error', 'timeline-patch/missing-op', `operations[${i}].op must be a non-empty string`, { ...baseCtx, target: op.target }),
      );
      continue;
    }

    if (!ALL_KNOWN_OPS.has(op.op as TimelinePatchAnyOpFamily)) {
      diagnostics.push(
        diag('error', 'timeline-patch/unknown-op', `Unknown operation family "${op.op}"`, {
          ...baseCtx,
          op: op.op as TimelinePatchAnyOpFamily,
          target: op.target,
        }),
      );
      continue;
    }

    // -- target ------------------------------------------------------------
    if (typeof op.target !== 'string' || op.target.length === 0) {
      diagnostics.push(
        diag('error', 'timeline-patch/missing-target', `operations[${i}] "${op.op}" requires a non-empty target`, {
          ...baseCtx,
          op: op.op as TimelinePatchAnyOpFamily,
        }),
      );
      continue;
    }

    // -- reserved ops ------------------------------------------------------
    if (RESERVED_OPS.has(op.op as TimelinePatchAnyOpFamily)) {
      diagnostics.push(
        diag(
          'warning',
          'timeline-patch/reserved-op',
          `"${op.op}" is a reserved operation family — validated but not executed in M3`,
          {
            ...baseCtx,
            op: op.op as TimelinePatchAnyOpFamily,
            target: op.target,
            detail: { reserved: true, deferred: true, nonPreviewable: true },
          },
        ),
      );
      // Reserved ops are valid (non-blocking warning) — continue to payload validation
    }

    // -- order field -------------------------------------------------------
    if (op.order !== undefined && (typeof op.order !== 'number' || !isFinite(op.order))) {
      diagnostics.push(
        diag('error', 'timeline-patch/invalid-order', `operations[${i}].order must be a finite number`, {
          ...baseCtx,
          op: op.op as TimelinePatchAnyOpFamily,
          target: op.target,
          detail: { actual: typeof op.order },
        }),
      );
    }

    // -- payload -----------------------------------------------------------
    if (op.payload !== undefined) {
      if (op.payload === null) {
        diagnostics.push(
          diag('error', 'timeline-patch/invalid-payload', `operations[${i}].payload must be an object or undefined, got null`, {
            ...baseCtx,
            op: op.op as TimelinePatchAnyOpFamily,
            target: op.target,
            detail: { actual: 'null' },
          }),
        );
        continue;
      }
      if (Array.isArray(op.payload)) {
        diagnostics.push(
          diag('error', 'timeline-patch/invalid-payload', `operations[${i}].payload must be a plain object, got array`, {
            ...baseCtx,
            op: op.op as TimelinePatchAnyOpFamily,
            target: op.target,
            detail: { actual: 'array' },
          }),
        );
        continue;
      }
      if (typeof op.payload !== 'object') {
        diagnostics.push(
          diag('error', 'timeline-patch/invalid-payload', `operations[${i}].payload must be an object or undefined`, {
            ...baseCtx,
            op: op.op as TimelinePatchAnyOpFamily,
            target: op.target,
            detail: { actual: typeof op.payload },
          }),
        );
        continue;
      }
    }

    // -- Per-family payload validation (only for active ops) -----------------
    if (!RESERVED_OPS.has(op.op as TimelinePatchAnyOpFamily)) {
      switch (op.op) {
        case 'clip.add':
          diagnostics.push(...validateClipAdd(op, i));
          break;
        case 'clip.update':
          diagnostics.push(...validateClipUpdate(op, i));
          break;
        case 'clip.remove':
          // No mandatory payload fields
          break;
        case 'clip.move':
          diagnostics.push(...validateClipMove(op, i));
          break;
        case 'track.add':
          diagnostics.push(...validateTrackAdd(op, i));
          break;
        case 'track.update':
          diagnostics.push(...validateTrackUpdate(op, i));
          break;
        case 'track.remove':
          // No mandatory payload fields
          break;
        case 'asset.update': {
          // target is asset key; no strict format constraint beyond non-empty
          if (op.payload && op.payload.mode !== undefined && op.payload.mode !== 'merge' && op.payload.mode !== 'replace') {
            diagnostics.push(
              diag('error', 'timeline-patch/invalid-payload', 'asset.update: payload.mode must be "merge" or "replace"', {
                operationIndex: i,
                op: op.op as TimelinePatchAnyOpFamily,
                target: op.target,
                detail: { key: 'mode', expected: '"merge" | "replace"', actual: op.payload.mode },
              }),
            );
          }
          const assetUpdateableKeys = op.payload ? Object.keys(op.payload).filter((k) => k !== 'mode') : [];
          if (!op.payload || typeof op.payload !== 'object' || assetUpdateableKeys.length === 0) {
            diagnostics.push(
              diag('error', 'timeline-patch/empty-payload', 'asset.update: payload must contain at least one updateable field', {
                operationIndex: i,
                op: op.op as TimelinePatchAnyOpFamily,
                target: op.target,
              }),
            );
          }
          break;
        }
        case 'asset.remove':
          // No mandatory payload fields
          break;
        case 'app.update':
          diagnostics.push(...validateAppUpdate(op, i));
          break;
        case 'project-data.write':
          diagnostics.push(...validateProjectDataWrite(op, i));
          break;
        case 'project-data.delete':
          diagnostics.push(...validateProjectDataDelete(op, i));
          break;
        case 'extension.noop':
          diagnostics.push(...validateExtensionNoop(op, i));
          break;
        default:
          // Should be unreachable — ALL_KNOWN_OPS already gates this
          diagnostics.push(
            diag('error', 'timeline-patch/unknown-op', `Unhandled operation family "${op.op}"`, {
              ...baseCtx,
              op: op.op as TimelinePatchAnyOpFamily,
              target: op.target,
            }),
          );
      }
    }
  }

  // ── Result ──────────────────────────────────────────────────────────────

  const hasErrors = diagnostics.some((d) => d.severity === 'error');

  return Object.freeze({
    valid: !hasErrors,
    diagnostics: Object.freeze(diagnostics),
  });
}

// ---------------------------------------------------------------------------
// Merge / Replace semantics
// ---------------------------------------------------------------------------

/**
 * Patch merge mode controlling how payload fields are combined with
 * existing state.
 *
 * - `'merge'` (default): Shallow-merge payload keys into the existing
 *   object.  Keys present in the existing object but absent from the
 *   payload are preserved.
 * - `'replace'`: Replace the entire mutable configuration with the
 *   payload.  Structural fields (id, track, at for clips; id for
 *   tracks) are preserved.  All other fields are set from payload and
 *   any existing field not mentioned in the payload is removed.
 */
export type PatchMergeMode = 'merge' | 'replace';

/**
 * Deep-merge `source` into `target` (mutates target).
 * Only called for `'merge'` mode when the existing value is a plain object.
 */
function deepMergeObject(
  target: Record<string, unknown>,
  source: Record<string, unknown>,
): Record<string, unknown> {
  for (const key of Object.keys(source)) {
    const srcVal = source[key];
    const tgtVal = target[key];
    if (
      srcVal !== null &&
      typeof srcVal === 'object' &&
      !Array.isArray(srcVal) &&
      tgtVal !== null &&
      typeof tgtVal === 'object' &&
      !Array.isArray(tgtVal)
    ) {
      target[key] = deepMergeObject(
        tgtVal as Record<string, unknown>,
        srcVal as Record<string, unknown>,
      );
    } else {
      target[key] = srcVal;
    }
  }
  return target;
}

/** Mutable clip fields (excludes structural id/track/at). */
const CLIP_MUTABLE_FIELDS: ReadonlySet<string> = new Set([
  'clipType', 'asset', 'from', 'to', 'speed', 'hold',
  'volume', 'x', 'y', 'width', 'height',
  'cropTop', 'cropBottom', 'cropLeft', 'cropRight',
  'opacity', 'text', 'entrance', 'exit', 'continuous', 'transition',
  'effects', 'params', 'pool_id', 'clip_order', 'source_uuid',
  'generation', 'app',
]);

const getIncomingClipShader = (payload: Record<string, unknown>): TimelineClipShaderMetadata | undefined => {
  const app = payload.app;
  if (!app || typeof app !== 'object' || Array.isArray(app)) {
    return undefined;
  }
  const shader = (app as { shader?: unknown }).shader;
  return shader && typeof shader === 'object' && !Array.isArray(shader)
    ? shader as TimelineClipShaderMetadata
    : undefined;
};

const getIncomingPostprocessShader = (
  target: string,
  payload: Record<string, unknown>,
): TimelinePostprocessShaderMetadata | undefined => {
  if (target !== TIMELINE_POSTPROCESS_SHADER_APP_KEY) {
    return undefined;
  }
  return payload && typeof payload === 'object' && !Array.isArray(payload)
    ? payload as TimelinePostprocessShaderMetadata
    : undefined;
};

/** Mutable track fields (excludes structural id). */
const TRACK_MUTABLE_FIELDS: ReadonlySet<string> = new Set([
  'kind', 'label', 'scale', 'fit', 'opacity', 'volume',
  'muted', 'blendMode', 'app',
]);

// ---------------------------------------------------------------------------
// Compile / Preview
// ---------------------------------------------------------------------------

/** Result shape returned by {@link compileTimelinePatch}. */
export interface TimelinePatchCompileResult {
  /** True when the patch was compiled successfully. */
  valid: boolean;
  /** The fully-materialized nextData after applying the patch. */
  nextData: TimelineData | null;
  /**
   * Internal mutation description suitable for {@link TimelineEditMutation}
   * consumers (e.g. `applyEdit`).  Null when no row-level changes were
   * produced or the patch was invalid.
   */
  mutation: TimelineEditMutation | null;
  /** Semantic diff describing what the patch changed. */
  diff: TimelineDiff;
  /** Diagnostics (validation errors, compilation warnings, etc.). */
  diagnostics: readonly TimelinePatchDiagnostic[];
}

/**
 * Compile a validated TimelinePatch batch against current TimelineData.
 *
 * This is a pure function — it clones the data, applies every operation,
 * materializes through the existing config/row serialization paths, and
 * returns the projected nextData, an internal mutation description,
 * a semantic TimelineDiff, and the set of affected object IDs.
 *
 * **It does not commit** — the caller is responsible for feeding the
 * returned `mutation` into `applyEdit` or `nextData` into `commitData`.
 *
 * Reserved operations (`clip.split`, `clip.slice`) are skipped during
 * compilation (they produce warning diagnostics but no diff entries).
 *
 * @param patch  The patch to compile (must pass validation).
 * @param data   Current canonical TimelineData snapshot.
 * @returns A {@link TimelinePatchCompileResult}.
 */
export function compileTimelinePatch(
  patch: TimelinePatch,
  data: TimelineData,
): TimelinePatchCompileResult {
  const validation = validateTimelinePatch(patch);

  // If validation produced errors, refuse to compile.
  if (!validation.valid) {
    return {
      valid: false,
      nextData: null,
      mutation: null,
      diff: {
        version: patch.version,
        entries: [],
        affectedObjectIds: [],
      },
      diagnostics: validation.diagnostics,
    };
  }

  // ── Clone mutable working copies ──────────────────────────────────────
  const clips: TimelineClip[] = data.config.clips.map((c) => ({ ...c, app: c.app ? { ...c.app } : undefined }));
  let tracks: TrackDefinition[] = (data.config.tracks ?? data.tracks).map((t) => ({ ...t, app: t.app ? { ...t.app } : undefined }));
  const meta: Record<string, ClipMeta> = {};
  for (const [id, m] of Object.entries(data.meta)) {
    meta[id] = { ...m };
  }
  const clipOrder: ClipOrderMap = {};
  for (const [trackId, ids] of Object.entries(data.clipOrder)) {
    clipOrder[trackId] = [...ids];
  }

  // Working config.app clone (extension project-data lives here per SD2).
  const configApp: Record<string, unknown> = data.config.app
    ? { ...data.config.app }
    : {};

  // Track-level app data clone
  const trackAppSnapshots = new Map<string, Record<string, unknown> | undefined>();
  for (const t of tracks) {
    trackAppSnapshots.set(t.id, t.app ? { ...t.app } : undefined);
  }

  const diffEntries: TimelineDiffEntry[] = [];
  const affectedIds = new Set<string>();
  const compileDiags: TimelinePatchDiagnostic[] = [...validation.diagnostics];

  const hasReservedOps = patch.operations.some(
    (op) => RESERVED_OPS.has(op.op as TimelinePatchAnyOpFamily),
  );

  // ── Sort operations by order field (stable) ───────────────────────────
  //   - Operations with explicit `order` are applied before those without.
  //   - Ties on `order` are broken by original array position (stable sort).
  //   - Operations without `order` are applied last in original order.
  //   - Negative orders are allowed and sorted naturally.
  const indexedOps = patch.operations.map((op, originalIndex) => ({
    op,
    originalIndex,
    hasOrder: op.order !== undefined,
  }));

  // Stable sort: operations with order first (ascending), then without order
  const sortedOps = [...indexedOps].sort((a, b) => {
    if (a.hasOrder && !b.hasOrder) return -1;
    if (!a.hasOrder && b.hasOrder) return 1;
    if (a.hasOrder && b.hasOrder) {
      const diff = (a.op.order as number) - (b.op.order as number);
      if (diff !== 0) return diff;
    }
    // Same order or both without order — preserve original position
    return a.originalIndex - b.originalIndex;
  });

  // ── Apply each operation to the working copies ─────────────────────────
  for (let i = 0; i < sortedOps.length; i++) {
    const { op, originalIndex } = sortedOps[i];
    const family = op.op as TimelinePatchAnyOpFamily;

    // Reserved ops — skip execution, they only produce warnings.
    if (RESERVED_OPS.has(family)) {
      continue;
    }

    switch (family) {
      // ── clip.add ──────────────────────────────────────────────────────
      case 'clip.add': {
        const track = (op.payload?.track as string) ?? tracks[0]?.id ?? 'V1';
        const at = (op.payload?.at as number) ?? 0;
        const clipType = op.payload?.clipType as string | undefined;

        const newClip: TimelineClip = {
          id: op.target,
          at,
          track,
        };
        if (clipType !== undefined) newClip.clipType = clipType;

        // Ensure track exists
        if (!tracks.some((t) => t.id === track)) {
          compileDiags.push(
            diag('warning', 'timeline-patch/target-not-found', `clip.add: track "${track}" not found — auto-creating visual track`, {
              operationIndex: originalIndex,
              op: family,
              target: op.target,
              detail: { missingTrack: track, autoCreated: true },
            }),
          );
          const newTrack: TrackDefinition = { id: track, kind: 'visual', label: track };
          tracks = [...tracks, newTrack];
          clipOrder[track] = [];
          trackAppSnapshots.set(track, undefined);
        }

        // Ensure clipOrder entry exists for track
        if (!clipOrder[track]) {
          clipOrder[track] = [];
        }

        // Append to clips and clipOrder
        clips.push(newClip);
        clipOrder[track] = [...clipOrder[track], op.target];

        // Minimal meta
        meta[op.target] = {
          track,
          clipType: clipType as TimelineClip['clipType'],
        };

        affectedIds.add(op.target);
        affectedIds.add(track);
        diffEntries.push({
          granularity: 'clip',
          kind: 'added',
          target: op.target,
          op: family,
          after: { id: op.target, track, at, clipType },
        });
        break;
      }

      // ── clip.remove ───────────────────────────────────────────────────
      case 'clip.remove': {
        const idx = clips.findIndex((c) => c.id === op.target);
        if (idx === -1) {
          compileDiags.push(
            diag('warning', 'timeline-patch/target-not-found', `clip.remove: clip "${op.target}" not found`, {
              operationIndex: originalIndex,
              op: family,
              target: op.target,
            }),
          );
          break;
        }

        const removed = clips[idx];
        const beforeSummary: Record<string, unknown> = {
          id: removed.id,
          track: removed.track,
          at: removed.at,
        };
        if (removed.clipType) beforeSummary.clipType = removed.clipType;

        clips.splice(idx, 1);
        delete meta[op.target];

        // Remove from clipOrder
        for (const tid of Object.keys(clipOrder)) {
          clipOrder[tid] = clipOrder[tid].filter((cid) => cid !== op.target);
        }

        affectedIds.add(op.target);
        affectedIds.add(removed.track);
        diffEntries.push({
          granularity: 'clip',
          kind: 'removed',
          target: op.target,
          op: family,
          before: beforeSummary,
        });
        break;
      }

      // ── clip.update ───────────────────────────────────────────────────
      case 'clip.update': {
        const existingClip = clips.find((c) => c.id === op.target);
        if (!existingClip) {
          compileDiags.push(
            diag('warning', 'timeline-patch/target-not-found', `clip.update: clip "${op.target}" not found`, {
              operationIndex: originalIndex,
              op: family,
              target: op.target,
            }),
          );
          break;
        }

        const beforeSummary: Record<string, unknown> = {
          id: existingClip.id,
          track: existingClip.track,
          at: existingClip.at,
        };
        if (existingClip.clipType) beforeSummary.clipType = existingClip.clipType;

        const payload = op.payload ?? {};
        const mode = (payload.mode as PatchMergeMode | undefined) ?? 'merge';
        const incomingShader = getIncomingClipShader(payload);
        if (incomingShader) {
          const assignment = assignTimelineClipShader(existingClip, incomingShader);
          if (!assignment.ok) {
            compileDiags.push(
              diag('error', 'timeline-patch/shader-scope-occupied', assignment.message, {
                operationIndex: originalIndex,
                op: family,
                target: op.target,
                detail: {
                  scope: assignment.scope,
                  existingShaderId: assignment.existing.shaderId,
                  incomingShaderId: assignment.incoming.shaderId,
                },
              }),
            );
            break;
          }
        }

        if (mode === 'replace') {
          // Replace mode: preserve structural fields, clear mutable fields, then apply payload
          for (const key of Array.from(CLIP_MUTABLE_FIELDS)) {
            if (Object.prototype.hasOwnProperty.call(existingClip, key)) {
              delete (existingClip as Record<string, unknown>)[key];
            }
          }
          for (const [key, value] of Object.entries(payload)) {
            if (key === 'id' || key === 'track' || key === 'at' || key === 'mode') continue;
            (existingClip as Record<string, unknown>)[key] = value;
          }
        } else {
          // Merge mode (default): shallow-merge payload into existing clip
          for (const [key, value] of Object.entries(payload)) {
            if (key === 'id' || key === 'track' || key === 'at' || key === 'mode') continue;
            (existingClip as Record<string, unknown>)[key] = value;
          }
        }

        // Sync to meta for downstream serialization
        const existingMeta = meta[op.target];
        if (existingMeta) {
          if (mode === 'replace') {
            // In replace mode, wipe meta and rebuild from current clip state
            for (const k of Object.keys(existingMeta)) {
              delete existingMeta[k];
            }
          }
          for (const [key, value] of Object.entries(payload)) {
            if (key === 'mode') continue;
            if (
              key in existingMeta || key === 'volume' || key === 'opacity' || key === 'x' || key === 'y'
              || key === 'width' || key === 'height' || key === 'speed' || key === 'hold'
              || key === 'from' || key === 'to' || key === 'clipType' || key === 'text'
              || key === 'entrance' || key === 'exit' || key === 'continuous' || key === 'transition'
              || key === 'effects' || key === 'params' || key === 'pool_id' || key === 'clip_order'
              || key === 'source_uuid' || key === 'generation' || key === 'cropTop' || key === 'cropBottom'
              || key === 'cropLeft' || key === 'cropRight' || key === 'asset' || key === 'app'
            ) {
               
              (existingMeta as unknown as Record<string, unknown>)[key] = value;
            }
          }
        }

        affectedIds.add(op.target);
        diffEntries.push({
          granularity: 'clip',
          kind: 'modified',
          target: op.target,
          op: family,
          before: beforeSummary,
          after: { id: existingClip.id, track: existingClip.track, at: existingClip.at, clipType: existingClip.clipType, mode },
        });
        break;
      }

      // ── clip.move ─────────────────────────────────────────────────────
      case 'clip.move': {
        const existingClip = clips.find((c) => c.id === op.target);
        if (!existingClip) {
          compileDiags.push(
            diag('warning', 'timeline-patch/target-not-found', `clip.move: clip "${op.target}" not found`, {
              operationIndex: originalIndex,
              op: family,
              target: op.target,
            }),
          );
          break;
        }

        const oldTrack = existingClip.track;
        const oldAt = existingClip.at;
        const beforeSummary: Record<string, unknown> = { id: op.target, track: oldTrack, at: oldAt };
        if (existingClip.clipType) beforeSummary.clipType = existingClip.clipType;

        const newTrack = (op.payload?.track as string | undefined) ?? oldTrack;
        const newAt = (op.payload?.at as number | undefined) ?? oldAt;

        // before / after fractional anchors
        const beforeAnchor = op.payload?.before as string | undefined;
        const afterAnchor = op.payload?.after as string | undefined;

        // Remove from old track in clipOrder
        if (clipOrder[oldTrack]) {
          clipOrder[oldTrack] = clipOrder[oldTrack].filter((cid) => cid !== op.target);
        }

        // Ensure new track exists
        if (!tracks.some((t) => t.id === newTrack)) {
          compileDiags.push(
            diag('warning', 'timeline-patch/target-not-found', `clip.move: track "${newTrack}" not found — auto-creating visual track`, {
              operationIndex: originalIndex,
              op: family,
              target: op.target,
              detail: { missingTrack: newTrack, autoCreated: true },
            }),
          );
          const newTrackDef: TrackDefinition = { id: newTrack, kind: 'visual', label: newTrack };
          tracks = [...tracks, newTrackDef];
          clipOrder[newTrack] = [];
          trackAppSnapshots.set(newTrack, undefined);
        }

        // Update clip position
        existingClip.track = newTrack;
        existingClip.at = newAt;

        // Update meta
        if (meta[op.target]) {
          meta[op.target].track = newTrack;
        }

        // Add to new track in clipOrder with before/after anchor positioning
        if (!clipOrder[newTrack]) {
          clipOrder[newTrack] = [];
        }

        const targetOrder = clipOrder[newTrack];
        const anchorIdx = (() => {
          // 'before' takes precedence over 'after'
          if (beforeAnchor !== undefined) {
            const idx = targetOrder.indexOf(beforeAnchor);
            return idx >= 0 ? idx : -1; // insert at this position, pushing anchor right
          }
          if (afterAnchor !== undefined) {
            const idx = targetOrder.indexOf(afterAnchor);
            return idx >= 0 ? idx + 1 : -1; // insert after anchor
          }
          return -1;
        })();

        if (anchorIdx >= 0) {
          targetOrder.splice(anchorIdx, 0, op.target);
        } else {
          // No anchor or anchor not found — use `order` for fractional positioning
          const opOrder = op.order;
          if (opOrder !== undefined) {
            // Insert maintaining ascending order among ordered clips
            let insertIdx = targetOrder.length;
            for (let idx = 0; idx < targetOrder.length; idx++) {
              const otherId = targetOrder[idx];
              const otherClip = clips.find((c) => c.id === otherId);
              // Use clip's `clip_order` or `at` as tiebreaker
              const otherOrder = otherClip?.clip_order ?? otherClip?.at ?? 0;
              if (opOrder < otherOrder) {
                insertIdx = idx;
                break;
              }
            }
            targetOrder.splice(insertIdx, 0, op.target);
          } else {
            targetOrder.push(op.target);
          }
        }

        affectedIds.add(op.target);
        affectedIds.add(oldTrack);
        if (newTrack !== oldTrack) affectedIds.add(newTrack);
        if (beforeAnchor) affectedIds.add(beforeAnchor);
        if (afterAnchor) affectedIds.add(afterAnchor);

        diffEntries.push({
          granularity: 'clip',
          kind: oldTrack !== newTrack ? 'modified' : 'reordered',
          target: op.target,
          op: family,
          before: beforeSummary,
          after: {
            id: op.target,
            track: newTrack,
            at: newAt,
            clipType: existingClip.clipType,
            ...(beforeAnchor ? { before: beforeAnchor } : {}),
            ...(afterAnchor ? { after: afterAnchor } : {}),
          },
        });
        break;
      }

      // ── track.add ─────────────────────────────────────────────────────
      case 'track.add': {
        const kind = op.payload?.kind as 'visual' | 'audio';
        const label = (op.payload?.label as string) ?? op.target;

        if (tracks.some((t) => t.id === op.target)) {
          compileDiags.push(
            diag('warning', 'timeline-patch/duplicate-target', `track.add: track "${op.target}" already exists`, {
              operationIndex: originalIndex,
              op: family,
              target: op.target,
            }),
          );
          break;
        }

        const newTrack: TrackDefinition = { id: op.target, kind, label };
        tracks = [...tracks, newTrack];
        clipOrder[op.target] = [];
        trackAppSnapshots.set(op.target, undefined);

        affectedIds.add(op.target);
        diffEntries.push({
          granularity: 'track',
          kind: 'added',
          target: op.target,
          op: family,
          after: { id: op.target, kind, label },
        });
        break;
      }

      // ── track.update ──────────────────────────────────────────────────
      case 'track.update': {
        const trackIdx = tracks.findIndex((t) => t.id === op.target);
        if (trackIdx === -1) {
          compileDiags.push(
            diag('warning', 'timeline-patch/target-not-found', `track.update: track "${op.target}" not found`, {
              operationIndex: originalIndex,
              op: family,
              target: op.target,
            }),
          );
          break;
        }

        const before = tracks[trackIdx];
        const beforeSummary: Record<string, unknown> = { id: before.id, kind: before.kind, label: before.label };
        if (before.muted !== undefined) beforeSummary.muted = before.muted;
        if (before.app) beforeSummary.app = before.app;

        const payload = op.payload ?? {};
        const mode = (payload.mode as PatchMergeMode | undefined) ?? 'merge';

        let updatedTrack: TrackDefinition;

        if (mode === 'replace') {
          // Replace mode: preserve id, clear mutable fields, apply payload
          updatedTrack = { id: before.id, kind: before.kind, label: before.label };
          for (const key of Array.from(TRACK_MUTABLE_FIELDS)) {
            if (Object.prototype.hasOwnProperty.call(payload, key)) {
              (updatedTrack as Record<string, unknown>)[key] = payload[key];
            }
          }
          // Preserve app if provided in payload, otherwise reset
          if (payload.app !== undefined && typeof payload.app === 'object' && payload.app !== null) {
            updatedTrack.app = { ...(payload.app as Record<string, unknown>) };
          } else if (payload.app === null) {
            updatedTrack.app = undefined;
          } else {
            // Reset app in replace mode when not explicitly provided
            updatedTrack.app = undefined;
          }
        } else {
          // Merge mode (default): shallow-merge payload into existing track
          updatedTrack = {
            ...before,
            app: before.app ? { ...before.app } : undefined,
          };

          if (payload.label !== undefined && typeof payload.label === 'string') {
            updatedTrack.label = payload.label;
          }
          if (payload.kind !== undefined && (payload.kind === 'visual' || payload.kind === 'audio')) {
            updatedTrack.kind = payload.kind;
          }
          if (payload.muted !== undefined && typeof payload.muted === 'boolean') {
            updatedTrack.muted = payload.muted;
          }
          // Preserve any app-level updates (deep merge)
          if (payload.app !== undefined && typeof payload.app === 'object' && payload.app !== null) {
            updatedTrack.app = { ...updatedTrack.app, ...(payload.app as Record<string, unknown>) };
          }
        }

        tracks[trackIdx] = updatedTrack;
        trackAppSnapshots.set(op.target, updatedTrack.app ? { ...updatedTrack.app } : undefined);

        affectedIds.add(op.target);
        diffEntries.push({
          granularity: 'track',
          kind: 'modified',
          target: op.target,
          op: family,
          before: beforeSummary,
          after: {
            id: updatedTrack.id,
            kind: updatedTrack.kind,
            label: updatedTrack.label,
            muted: updatedTrack.muted,
            mode,
          },
        });
        break;
      }

      // ── track.remove ──────────────────────────────────────────────────
      case 'track.remove': {
        const trackIdx = tracks.findIndex((t) => t.id === op.target);
        if (trackIdx === -1) {
          compileDiags.push(
            diag('warning', 'timeline-patch/target-not-found', `track.remove: track "${op.target}" not found`, {
              operationIndex: originalIndex,
              op: family,
              target: op.target,
            }),
          );
          break;
        }

        const removedTrack = tracks[trackIdx];
        const removedClipIds = clipOrder[op.target] ?? [];

        // Remove track
        tracks.splice(trackIdx, 1);
        trackAppSnapshots.delete(op.target);

        // Remove all clips on this track
        for (const cid of removedClipIds) {
          const ci = clips.findIndex((c) => c.id === cid);
          if (ci !== -1) clips.splice(ci, 1);
          delete meta[cid];
          affectedIds.add(cid);
        }

        // Remove from clipOrder
        delete clipOrder[op.target];

        affectedIds.add(op.target);
        diffEntries.push({
          granularity: 'track',
          kind: 'removed',
          target: op.target,
          op: family,
          before: { id: removedTrack.id, kind: removedTrack.kind, label: removedTrack.label },
        });

        // Add diff entries for removed clips
        for (const cid of removedClipIds) {
          diffEntries.push({
            granularity: 'clip',
            kind: 'removed',
            target: cid,
            op: 'clip.remove',
          });
        }
        break;
      }

      // ── asset.update ──────────────────────────────────────────────────
      case 'asset.update': {
        const payload = op.payload ?? {};
        const mode = (payload.mode as PatchMergeMode | undefined) ?? 'merge';
        const registryAssets = data.registry.assets ?? {};
        const existing = registryAssets[op.target];

        const beforeSummary: Record<string, unknown> | undefined = existing
          ? { key: op.target, file: existing.file }
          : undefined;

        // Asset mutations produce a diff entry but the registry clone is
        // handled at materialization time via buildDataFromCurrentRegistry.
        // We record the intent via a synthetic registry patch with mode.
        affectedIds.add(op.target);
        diffEntries.push({
          granularity: 'asset',
          kind: existing ? 'modified' : 'added',
          target: op.target,
          op: family,
          before: beforeSummary,
          after: { key: op.target, ...payload, mode },
        });

        compileDiags.push(
          diag('warning', 'timeline-patch/asset-not-implemented', `asset.update: registry mutation is recorded in diff but not applied to TimelineData — asset ops require host-level registry mutation`, {
            operationIndex: originalIndex,
            op: family,
            target: op.target,
            detail: { note: 'asset ops are recorded in the diff for host consumption; apply via patchRegistry/unpatchRegistry', mode },
          }),
        );
        break;
      }

      // ── asset.remove ──────────────────────────────────────────────────
      case 'asset.remove': {
        const registryAssets = data.registry.assets ?? {};
        const existing = registryAssets[op.target];

        affectedIds.add(op.target);
        diffEntries.push({
          granularity: 'asset',
          kind: 'removed',
          target: op.target,
          op: family,
          before: existing ? { key: op.target, file: existing.file } : undefined,
        });

        compileDiags.push(
          diag('warning', 'timeline-patch/asset-not-implemented', `asset.remove: registry mutation is recorded in diff but not applied to TimelineData — asset ops require host-level registry mutation`, {
            operationIndex: originalIndex,
            op: family,
            target: op.target,
            detail: { note: 'asset ops are recorded in the diff for host consumption; apply via patchRegistry/unpatchRegistry' },
          }),
        );
        break;
      }

      // ── app.update ────────────────────────────────────────────────────
      case 'app.update': {
        const extId = op.target;
        const payload = op.payload ?? {};
        const mode = (payload.mode as PatchMergeMode | undefined) ?? 'merge';
        const beforeApp = configApp[extId];
        const beforeSummary: Record<string, unknown> | undefined = beforeApp !== undefined
          ? { extensionId: extId, config: beforeApp }
          : undefined;

        // Build the update payload excluding meta keys
        const updateData: Record<string, unknown> = {};
        for (const [k, v] of Object.entries(payload)) {
          if (k !== 'mode') updateData[k] = v;
        }

        const incomingPostprocessShader = getIncomingPostprocessShader(extId, updateData);
        if (incomingPostprocessShader) {
          const assignment = assignTimelinePostprocessShader(
            { ...data.config, app: configApp },
            incomingPostprocessShader,
          );
          if (!assignment.ok) {
            compileDiags.push(
              diag('error', 'timeline-patch/shader-scope-occupied', assignment.message, {
                operationIndex: originalIndex,
                op: family,
                target: op.target,
                detail: {
                  scope: assignment.scope,
                  existingShaderId: assignment.existing.shaderId,
                  incomingShaderId: assignment.incoming.shaderId,
                },
              }),
            );
            break;
          }
        }

        if (mode === 'replace') {
          // Replace mode: overwrite entire extension namespace
          configApp[extId] = { ...updateData };
        } else {
          // Merge mode (default): shallow-merge into existing app namespace
          const existingApp = (configApp[extId] as Record<string, unknown> | undefined) ?? {};
          configApp[extId] = { ...existingApp, ...updateData };
        }

        affectedIds.add(extId);
        diffEntries.push({
          granularity: 'app',
          kind: beforeApp !== undefined ? 'modified' : 'added',
          target: extId,
          op: family,
          before: beforeSummary,
          after: { extensionId: extId, config: configApp[extId], mode },
        });
        break;
      }

      // ── project-data.write ──────────────────────────────────────────────────────
      case 'project-data.write': {
        const extId = op.target;
        const key = op.payload?.key as string;
        const value = op.payload?.value;
        const mode = (op.payload?.mode as PatchMergeMode | undefined) ?? 'replace';

        const existingApp = (configApp[extId] as Record<string, unknown> | undefined) ?? {};
        const beforeValue = existingApp[key];
        const beforeSummary: Record<string, unknown> = {
          extensionId: extId,
          key,
          hadValue: beforeValue !== undefined,
        };

        // ── Compute projected state for limit checks ──────────────────
        const projectedApp = { ...existingApp };

        if (mode === 'merge' && beforeValue !== null && typeof beforeValue === 'object' && !Array.isArray(beforeValue)
            && value !== null && typeof value === 'object' && !Array.isArray(value)) {
          projectedApp[key] = deepMergeObject(
            { ...(beforeValue as Record<string, unknown>) },
            value as Record<string, unknown>,
          );
        } else {
          projectedApp[key] = value;
        }

        // ── Extension total bytes check (V1: 1 MB per extension) ─────
        let projectedTotalBytes = 0;
        for (const [, entryValue] of Object.entries(projectedApp)) {
          if (entryValue !== undefined) {
            try {
              projectedTotalBytes += JSON.stringify(entryValue).length;
            } catch {
              // Non-serializable value ─ skip
            }
          }
        }

        if (projectedTotalBytes > EXTENSION_PROJECT_DATA_LIMITS.MAX_EXTENSION_TOTAL_BYTES) {
          compileDiags.push(
            diag('error', 'timeline-patch/project-data-overflow',
              `project-data.write: extension "${extId}" total bytes would exceed MAX_EXTENSION_TOTAL_BYTES (${EXTENSION_PROJECT_DATA_LIMITS.MAX_EXTENSION_TOTAL_BYTES})`, {
              operationIndex: originalIndex,
              op: family,
              target: extId,
              detail: {
                code: 'project-data/extension-total-exceeded',
                extensionId: extId,
                limit: EXTENSION_PROJECT_DATA_LIMITS.MAX_EXTENSION_TOTAL_BYTES,
                actual: projectedTotalBytes,
                unit: 'bytes',
              } satisfies ProjectDataLimitDetail,
            }),
          );
        }

        // ── Entry count check (V1: 128 entries per extension) ────────
        const projectedEntryCount = Object.keys(projectedApp).length;
        const isNewKey = !(key in existingApp);

        if (isNewKey && projectedEntryCount > EXTENSION_PROJECT_DATA_LIMITS.MAX_ENTRIES_PER_EXTENSION) {
          compileDiags.push(
            diag('error', 'timeline-patch/project-data-overflow',
              `project-data.write: extension "${extId}" entry count would exceed MAX_ENTRIES_PER_EXTENSION (${EXTENSION_PROJECT_DATA_LIMITS.MAX_ENTRIES_PER_EXTENSION})`, {
              operationIndex: originalIndex,
              op: family,
              target: extId,
              detail: {
                code: 'project-data/entry-count-exceeded',
                extensionId: extId,
                limit: EXTENSION_PROJECT_DATA_LIMITS.MAX_ENTRIES_PER_EXTENSION,
                actual: projectedEntryCount,
                unit: 'entries',
              } satisfies ProjectDataLimitDetail,
            }),
          );
        }

        // ── Apply to working state ─────────────────────────────────────
        configApp[extId] = projectedApp;

        affectedIds.add(extId);
        diffEntries.push({
          granularity: 'project-data',
          kind: beforeValue !== undefined ? 'modified' : 'added',
          target: extId,
          op: family,
          before: beforeSummary,
          after: { extensionId: extId, key, value: projectedApp[key], mode },
        });
        break;
      }

      // ── project-data.delete ───────────────────────────────────────────
      case 'project-data.delete': {
        const extId = op.target;
        const key = op.payload?.key as string;

        const existingApp = (configApp[extId] as Record<string, unknown> | undefined) ?? {};
        const hadKey = key in existingApp;
        const beforeValue = existingApp[key];

        delete existingApp[key];
        if (Object.keys(existingApp).length === 0) {
          delete configApp[extId];
        } else {
          configApp[extId] = existingApp;
        }

        if (hadKey) {
          affectedIds.add(extId);
          diffEntries.push({
            granularity: 'project-data',
            kind: 'removed',
            target: extId,
            op: family,
            before: { extensionId: extId, key, value: beforeValue },
          });
        }
        break;
      }

      // ── extension.noop ────────────────────────────────────────────────
      case 'extension.noop': {
        // No-op: validated and serialized as a diff entry for traceability.
        // Produces no state mutations but records the operation in the diff.
        affectedIds.add(op.target);
        diffEntries.push({
          granularity: 'app',
          kind: 'modified',
          target: op.target,
          op: family,
          after: {
            extensionId: op.target,
            noop: true,
            ...(op.payload ? { payload: op.payload } : {}),
          },
        });
        break;
      }

      default:
        // Should be unreachable due to validation gating
        break;
    }
  }

  // ── Materialize nextData through existing serialization paths ──────────

  // Rebuild rows from the mutated clips/tracks
  const rowData = configToRows({
    output: data.config.output,
    clips,
    tracks,
    pinnedShotGroups: data.config.pinnedShotGroups,
    theme: data.config.theme,
    theme_overrides: data.config.theme_overrides,
    generation_defaults: data.config.generation_defaults,
    app: Object.keys(configApp).length > 0 ? configApp : undefined,
  });

  // Build the next config using rowsToConfig (this also serializes clips properly)
  // Merge rowData.meta (built by configToRows from working clips) with
  // the compiler's working meta (which carries track updates, etc.).
  const mergedMeta = { ...data.meta, ...rowData.meta, ...meta };
  const nextConfig = rowsToConfig(
    rowData.rows,
    mergedMeta,
    data.output,
    clipOrder,
    tracks,
    data.config.pinnedShotGroups,
    { theme: data.config.theme, theme_overrides: data.config.theme_overrides, generation_defaults: data.config.generation_defaults },
  );

  // Attach config.app
  if (Object.keys(configApp).length > 0) {
    nextConfig.app = configApp;
  }

  // Attach track-level app data
  const nextTracksWithApp = tracks.map((t) => {
    const app = trackAppSnapshots.get(t.id);
    if (app !== undefined && Object.keys(app).length > 0) {
      return { ...t, app };
    }
    return t;
  });
  nextConfig.tracks = nextTracksWithApp;

  // Build full TimelineData through assembleTimelineData (via buildDataFromCurrentRegistry)
  const nextData = buildDataFromCurrentRegistry(nextConfig, data);

  // ── Build internal mutation description ───────────────────────────────
  const mutation: TimelineEditMutation = {
    type: 'rows',
    rows: rowData.rows,
    metaUpdates: mergedMeta,
    clipOrderOverride: clipOrder,
  };

  // ── Assemble TimelineDiff ─────────────────────────────────────────────
  const diff: TimelineDiff = {
    version: patch.version,
    entries: diffEntries,
    affectedObjectIds: Array.from(affectedIds),
  };

  return {
    valid: true,
    nextData,
    mutation,
    diff,
    diagnostics: compileDiags,
  };
}

/**
 * Preview a TimelinePatch batch against a snapshot of current timeline state.
 *
 * Validates the patch, compiles it against the provided TimelineData snapshot,
 * and returns a {@link TimelinePreviewResult} with the projected diff,
 * diagnostics, and whether every operation in the patch is fully previewable.
 *
 * This is a pure function — it never commits or mutates canonical state.
 *
 * @param patch  The patch to preview.
 * @param data   A snapshot of the current timeline state.
 * @returns A {@link TimelinePreviewResult}.
 */
export function previewTimelinePatch(
  patch: TimelinePatch,
  data: TimelineData,
): TimelinePreviewResult {
  const validation = validateTimelinePatch(patch);

  // Check for reserved ops that make preview non-fully-previewable
  const hasReserved = patch.operations.some(
    (op) => RESERVED_OPS.has(op.op as TimelinePatchAnyOpFamily),
  );

  if (!validation.valid) {
    return {
      diff: {
        version: patch.version,
        entries: [],
        affectedObjectIds: [],
      },
      fullyPreviewable: false,
      diagnostics: validation.diagnostics,
    };
  }

  const compiled = compileTimelinePatch(patch, data);

  // Merge validation diagnostics with compile diagnostics
  const allDiags = compiled.diagnostics;

  return {
    diff: compiled.diff,
    fullyPreviewable: !hasReserved && compiled.valid,
    diagnostics: allDiags,
  };
}
