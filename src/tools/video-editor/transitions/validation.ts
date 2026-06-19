/**
 * Pure transition validation and repair utilities.
 *
 * These helpers validate timeline transition objects against the transition
 * registry snapshot (built-ins + contributed), detect malformed legacy data,
 * generate structured diagnostics, and produce explicit repair patches.
 *
 * All functions are pure — they do not mutate their inputs and have no
 * side effects.
 */

import type { ExtensionDiagnostic } from '@reigh/editor-sdk';
import type { ClipTransition } from '@/tools/video-editor/types/index.ts';
import type { TransitionRegistrySnapshot } from '@/tools/video-editor/transitions/registry/types.ts';
import {
  resolveTransition,
  isBuiltInTransition,
  normalizeClipTransition,
} from '@/tools/video-editor/transitions/catalog.ts';

// ---------------------------------------------------------------------------
// Diagnostic codes
// ---------------------------------------------------------------------------

export const TransitionDiagnosticCodes = {
  /** Transition object is null/undefined but expected. */
  MISSING_TRANSITION_OBJECT: 'transitions/validation/missing-transition-object',

  /** The `type` field is missing from the transition object. */
  MISSING_TYPE: 'transitions/validation/missing-type',

  /** The `type` field is present but is not a non-empty string. */
  INVALID_TYPE: 'transitions/validation/invalid-type',

  /** The transition type is not found in built-ins or the registry. */
  UNRESOLVED_TYPE: 'transitions/validation/unresolved-type',

  /** A contributed transition that was previously available has been removed. */
  REMOVED_CONTRIBUTED: 'transitions/validation/removed-contributed',

  /** The transition record exists but is in an inactive/error state. */
  INACTIVE_RECORD: 'transitions/validation/inactive-record',

  /** The transition has no params and the record defines a schema with defaults. */
  MISSING_PARAMS: 'transitions/validation/missing-params',

  /** The transition is valid. */
  VALID: 'transitions/validation/valid',
} as const;

export type TransitionDiagnosticCode =
  (typeof TransitionDiagnosticCodes)[keyof typeof TransitionDiagnosticCodes];

// ---------------------------------------------------------------------------
// Validation result
// ---------------------------------------------------------------------------

export interface TransitionValidationResult {
  /** Whether the transition is usable as-is. */
  readonly isValid: boolean;

  /** Structured diagnostics describing issues found. */
  readonly diagnostics: readonly TransitionValidationDiagnostic[];

  /**
   * The resolved transition type, if one could be determined.
   * - For valid transitions, this is the canonical transition ID.
   * - For transitions with a resolvable type, this is the ID even if
   *   other issues exist (e.g. missing params).
   * - Undefined when the type itself cannot be determined.
   */
  readonly resolvedType: string | undefined;

  /**
   * Whether the transition type resolves to a known record (built-in or
   * contributed). False when the type is unresolvable.
   */
  readonly isResolvable: boolean;
}

export interface TransitionValidationDiagnostic {
  readonly severity: 'error' | 'warning' | 'info';
  readonly code: TransitionDiagnosticCode;
  readonly message: string;
  readonly detail?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Repair patches
// ---------------------------------------------------------------------------

export type TransitionRepairAction = 'clear-transition' | 'set-transition' | 'no-op';

export interface TransitionRepairPatch {
  /** The action to take. */
  readonly action: TransitionRepairAction;

  /**
   * The repaired transition object.
   * - For 'clear-transition': `null` (explicitly remove the transition).
   * - For 'set-transition': the repaired ClipTransition with defaults materialized.
   * - For 'no-op': the original transition unchanged.
   */
  readonly transition: ClipTransition | null;

  /** Diagnostics explaining why this repair was chosen. */
  readonly diagnostics: readonly TransitionValidationDiagnostic[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function diagnostic(
  severity: TransitionValidationDiagnostic['severity'],
  code: TransitionDiagnosticCode,
  message: string,
  detail?: Record<string, unknown>,
): TransitionValidationDiagnostic {
  return Object.freeze({ severity, code, message, detail: detail ? Object.freeze(detail) : undefined });
}

/**
 * Check whether the transition type looks like it came from a contributed
 * extension (and therefore should surface a "removed contributed" diagnostic
 * when not found, rather than a generic "unresolved" one).
 *
 * Extension-contributed transitions commonly use namespaced IDs containing
 * `:`, `@`, or `/` (e.g. `my-ext:custom-wipe`, `@scope/transition`).
 * Simple non-built-in IDs like `nonexistent-transition` are treated as
 * just unresolvable.
 */
function isContributedTransition(transitionType: string): boolean {
  if (isBuiltInTransition(transitionType)) return false;
  // Namespaced patterns suggest extension origin
  return transitionType.includes(':')
    || transitionType.includes('@')
    || transitionType.includes('/');
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

/**
 * Validate a raw transition value from timeline data.
 *
 * Handles legacy malformed data:
 * - `null` / `undefined` transition (but the key exists)
 * - Objects missing the `type` field
 * - `type` that is not a non-empty string
 *
 * @param raw - The raw transition value (may be null, undefined, or malformed).
 * @returns Validation result with diagnostics.
 */
export function validateTransitionObject(
  raw: unknown,
): TransitionValidationResult {
  // Null/undefined transition
  if (raw === null || raw === undefined) {
    return Object.freeze({
      isValid: false,
      diagnostics: Object.freeze([
        diagnostic(
          'warning',
          TransitionDiagnosticCodes.MISSING_TRANSITION_OBJECT,
          'Transition is null or undefined — no transition will be applied.',
          { raw: String(raw) },
        ),
      ]),
      resolvedType: undefined,
      isResolvable: false,
    });
  }

  // Not an object
  if (typeof raw !== 'object' || Array.isArray(raw)) {
    return Object.freeze({
      isValid: false,
      diagnostics: Object.freeze([
        diagnostic(
          'error',
          TransitionDiagnosticCodes.INVALID_TYPE,
          `Transition must be an object, got ${typeof raw}.`,
          { rawType: typeof raw },
        ),
      ]),
      resolvedType: undefined,
      isResolvable: false,
    });
  }

  const obj = raw as Record<string, unknown>;

  // Missing type field
  if (!('type' in obj) || obj.type === undefined) {
    return Object.freeze({
      isValid: false,
      diagnostics: Object.freeze([
        diagnostic(
          'error',
          TransitionDiagnosticCodes.MISSING_TYPE,
          'Transition object is missing the required "type" field.',
          { keys: Object.keys(obj) },
        ),
      ]),
      resolvedType: undefined,
      isResolvable: false,
    });
  }

  const typeValue = obj.type;

  // Type is null
  if (typeValue === null) {
    return Object.freeze({
      isValid: false,
      diagnostics: Object.freeze([
        diagnostic(
          'error',
          TransitionDiagnosticCodes.INVALID_TYPE,
          'Transition "type" field is null — must be a non-empty string.',
          { type: null },
        ),
      ]),
      resolvedType: undefined,
      isResolvable: false,
    });
  }

  // Type is not a string
  if (typeof typeValue !== 'string') {
    return Object.freeze({
      isValid: false,
      diagnostics: Object.freeze([
        diagnostic(
          'error',
          TransitionDiagnosticCodes.INVALID_TYPE,
          `Transition "type" must be a string, got ${typeof typeValue}.`,
          { type: typeValue, typeOf: typeof typeValue },
        ),
      ]),
      resolvedType: undefined,
      isResolvable: false,
    });
  }

  // Type is empty string
  if (typeValue.trim() === '') {
    return Object.freeze({
      isValid: false,
      diagnostics: Object.freeze([
        diagnostic(
          'error',
          TransitionDiagnosticCodes.INVALID_TYPE,
          'Transition "type" is an empty string — must be a non-empty transition ID.',
          { type: '' },
        ),
      ]),
      resolvedType: undefined,
      isResolvable: false,
    });
  }

  // Object is structurally valid (has a non-empty type string).
  // Further validation (registry resolution) happens in validateClipTransition.
  return Object.freeze({
    isValid: true,
    diagnostics: Object.freeze([
      diagnostic(
        'info',
        TransitionDiagnosticCodes.VALID,
        `Transition object is structurally valid (type: "${typeValue}").`,
        { type: typeValue },
      ),
    ]),
    resolvedType: typeValue,
    isResolvable: true,
  });
}

/**
 * Validate a clip transition against the transition registry snapshot.
 *
 * Checks:
 * - Structural validity (via validateTransitionObject)
 * - Whether the type resolves to a known record
 * - Whether the record is in a usable state
 * - Whether params are missing where the schema expects them
 * - Whether a contributed transition has been removed
 *
 * @param transition - The clip transition to validate.
 * @param registrySnapshot - Optional registry snapshot for resolution.
 * @returns Full validation result.
 */
export function validateClipTransition(
  transition: ClipTransition | undefined | null,
  registrySnapshot?: TransitionRegistrySnapshot,
): TransitionValidationResult {
  // First, validate the raw object
  const structuralResult = validateTransitionObject(transition);

  if (!structuralResult.isValid) {
    return structuralResult;
  }

  // At this point, transition is a valid ClipTransition with a non-empty type
  const clipTransition = transition as ClipTransition;
  const transitionType = clipTransition.type;

  // Resolve against registry
  const record = resolveTransition(transitionType, registrySnapshot);
  const diagnostics: TransitionValidationDiagnostic[] = [];

  if (!record) {
    // Unresolvable type
    const isContributed = isContributedTransition(transitionType);

    diagnostics.push(
      diagnostic(
        'error',
        isContributed
          ? TransitionDiagnosticCodes.REMOVED_CONTRIBUTED
          : TransitionDiagnosticCodes.UNRESOLVED_TYPE,
        isContributed
          ? `Contributed transition "${transitionType}" is no longer available. ` +
            `The extension that provided it may have been removed or disabled.`
          : `Transition type "${transitionType}" is not a recognized built-in or contributed transition.`,
        { transitionType, isContributed },
      ),
    );

    return {
      isValid: false,
      diagnostics: Object.freeze(diagnostics),
      resolvedType: transitionType,
      isResolvable: false,
    };
  }

  // Record exists — check its status
  if (record.status !== 'active') {
    diagnostics.push(
      diagnostic(
        'warning',
        TransitionDiagnosticCodes.INACTIVE_RECORD,
        `Transition "${transitionType}" is registered but has status "${record.status}". ` +
          `It may not render correctly.`,
        { transitionType, recordStatus: record.status },
      ),
    );
  }

  // Check for missing params
  const hasSchema = record.schema && Array.isArray(record.schema) && record.schema.length > 0;
  const hasParams = clipTransition.params && Object.keys(clipTransition.params).length > 0;

  if (hasSchema && !hasParams) {
    diagnostics.push(
      diagnostic(
        'warning',
        TransitionDiagnosticCodes.MISSING_PARAMS,
        `Transition "${transitionType}" has a parameter schema but no params are stored. ` +
          `Schema defaults will be used at render time.`,
        { transitionType, parameterCount: record.schema!.length },
      ),
    );
  }

  const isValid = !diagnostics.some((d) => d.severity === 'error');

  return {
    isValid,
    diagnostics: Object.freeze(diagnostics),
    resolvedType: transitionType,
    isResolvable: true,
  };
}

// ---------------------------------------------------------------------------
// Repair
// ---------------------------------------------------------------------------

/**
 * Generate a repair patch for a clip transition.
 *
 * The repair strategy:
 * - **Malformed / missing type / unresolvable → `clear-transition`**:
 *   The transition is removed entirely, and the clip renders without
 *   transition styling.
 * - **Missing params (schema exists) → `set-transition`**:
 *   Materialize schema defaults and return a repaired transition.
 * - **Valid → `no-op`**: No changes needed.
 *
 * @param transition - The clip transition to repair.
 * @param registrySnapshot - Optional registry snapshot for resolution.
 * @returns A repair patch with the recommended action and repaired transition.
 */
export function repairClipTransition(
  transition: ClipTransition | undefined | null,
  registrySnapshot?: TransitionRegistrySnapshot,
): TransitionRepairPatch {
  const validation = validateClipTransition(transition, registrySnapshot);

  // Case 1: Not resolvable or structurally invalid → clear transition
  if (!validation.isResolvable || !validation.isValid) {
    return {
      action: 'clear-transition',
      transition: null,
      diagnostics: validation.diagnostics,
    };
  }

  // Case 2: Resolvable but has missing-params warning → materialize defaults
  const hasMissingParams = validation.diagnostics.some(
    (d) => d.code === TransitionDiagnosticCodes.MISSING_PARAMS,
  );

  if (hasMissingParams) {
    const clipTransition = transition as ClipTransition;
    const record = resolveTransition(clipTransition.type, registrySnapshot);
    const repaired = normalizeClipTransition(clipTransition, record);

    return {
      action: 'set-transition',
      transition: repaired ?? clipTransition,
      diagnostics: validation.diagnostics,
    };
  }

  // Case 3: Valid — no repair needed
  return {
    action: 'no-op',
    transition: (transition as ClipTransition | null) ?? null,
    diagnostics: validation.diagnostics,
  };
}

/**
 * Generate diagnostics for a clip transition without performing a full
 * validation (lighter-weight than validateClipTransition).
 *
 * Produces the same diagnostics array that validateClipTransition would,
 * but skips the structural validation step.
 */
export function generateTransitionDiagnostics(
  transition: ClipTransition | undefined | null,
  registrySnapshot?: TransitionRegistrySnapshot,
): readonly TransitionValidationDiagnostic[] {
  return validateClipTransition(transition, registrySnapshot).diagnostics;
}
