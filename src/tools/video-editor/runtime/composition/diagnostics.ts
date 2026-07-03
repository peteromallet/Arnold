/**
 * Canonical composition diagnostics — M1b composition/ diagnostic codes.
 *
 * These codes are produced by the host projector, resolver, and patch
 * preview modules and are surfaced through the graph's `diagnostics` field
 * and through the planner/export guard when graph-derived facts are consumed.
 *
 * All codes use the `composition/` prefix to namespace them away from
 * export-prefixed (`export/`) diagnostics and general extension diagnostics.
 *
 * Structured detail fields are standardised across all composition
 * diagnostics: `nodeId`, `refKey`, `refState`, `scope`, `extensionId`,
 * `contributionId`, and `shaderId`.
 *
 * @module composition/diagnostics
 * @hostOwned — NOT exported through public SDK contracts.
 */

import type { DiagnosticSeverity, ExtensionDiagnostic } from '@reigh/editor-sdk';
import type { ReferenceState } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Diagnostic codes
// ---------------------------------------------------------------------------

export const COMPOSITION_DIAGNOSTIC_CODE = {
  /** A graph edge references a contribution that has no scoped candidates (missing). */
  MISSING_REF: 'composition/missing-ref',

  /** A graph edge references a contribution from a user-disabled package. */
  DISABLED_REF: 'composition/disabled-ref',

  /** A graph edge references a contribution whose kind is not yet bridged. */
  INACTIVE_RESERVED_REF: 'composition/inactive-reserved-ref',

  /** A graph edge references a contribution from an invalid package. */
  INVALID_PACKAGE_REF: 'composition/invalid-package-ref',

  /** A graph edge references a contribution whose scoped key has an exact duplicate. */
  DUPLICATE_REF: 'composition/duplicate-ref',

  /** A graph edge references a contribution from a package that failed settings migration. */
  SETTINGS_ERROR_REF: 'composition/settings-error-ref',

  /** A graph edge references a contribution from a package that failed runtime activation. */
  RUNTIME_ERROR_REF: 'composition/runtime-error-ref',

  /** A graph edge references a contribution from a version-incompatible package. */
  VERSION_INCOMPATIBLE_REF: 'composition/version-incompatible-ref',

  /** A graph edge references a contribution in an unrecognised state. */
  UNKNOWN_REF: 'composition/unknown-ref',

  /** A clip or postprocess scope already has a shader assigned (single-occupancy violation). */
  SCOPE_OCCUPIED: 'composition/scope-occupied',

  /** A clip or postprocess scope has multiple shader assignments (duplicate scope). */
  DUPLICATE_SCOPE: 'composition/duplicate-scope',

  /** A canonical target path is malformed or cannot be normalized. */
  INVALID_TARGET_PATH: 'composition/invalid-target-path',

  /** A target uses a reserved host surface that is not bindable in the current runtime. */
  UNSUPPORTED_RESERVED_TARGET: 'composition/unsupported-reserved-target',

  /** A target references an unknown contribution or shader ref. */
  UNKNOWN_TARGET_REF: 'composition/unknown-target-ref',

  /** A shader-uniform target references an undeclared uniform. */
  UNKNOWN_UNIFORM: 'composition/unknown-uniform',

  /** A target resolves to a surface that cannot be animated or live-bound. */
  NON_BINDABLE_TARGET: 'composition/non-bindable-target',

  /** A target value does not satisfy the resolved capability value type. */
  TARGET_VALUE_TYPE_ERROR: 'composition/target-value-type-error',

  /** A target keyframe/live-binding interpolation policy cannot be satisfied. */
  TARGET_INTERPOLATION_GAP: 'composition/target-interpolation-gap',
} as const;

export type CompositionDiagnosticCode =
  (typeof COMPOSITION_DIAGNOSTIC_CODE)[keyof typeof COMPOSITION_DIAGNOSTIC_CODE];

// ---------------------------------------------------------------------------
// Structured detail contract
// ---------------------------------------------------------------------------

/**
 * Standardised structured detail fields for composition diagnostics.
 *
 * All `composition/` diagnostics populate these fields when the
 * corresponding information is available.  Consumers (planner, export
 * guard, UI) can rely on these field names for stable access without
 * importing host runtime internals.
 */
export interface CompositionDiagnosticDetail {
  /** ID of the graph node associated with this diagnostic. */
  nodeId?: string;
  /** Clip ID when the diagnostic is scoped to a specific timeline clip. */
  clipId?: string;
  /** Live binding ID when the diagnostic relates to a binding. */
  bindingId?: string;
  /** Scoped contribution ref key (`kind:extensionId:contributionId`). */
  refKey?: string;
  /** Resolved reference state for the contribution ref. */
  refState?: ReferenceState;
  /** Shader scope (`clip` or `postprocess`) when applicable. */
  scope?: 'clip' | 'postprocess';
  /** Canonical target kind when the diagnostic relates to a target path. */
  targetKind?: string;
  /** Canonical target path when the diagnostic relates to a target path. */
  targetPath?: string;
  /** Uniform name when the diagnostic relates to a shader uniform. */
  uniformName?: string;
  /** Extension ID of the owning extension. */
  extensionId?: string;
  /** Contribution ID within the owning extension. */
  contributionId?: string;
  /** Shader ID when the diagnostic relates to a shader assignment. */
  shaderId?: string;
  /** Expected value type for target capability validation. */
  expectedValueType?: string;
  /** Actual value type that failed validation. */
  actualValueType?: string;
  /** Interpolation mode or policy involved in a target diagnostic. */
  interpolation?: string;
}

const BLOCKING_TARGET_COMPOSITION_DIAGNOSTIC_CODES = new Set<CompositionDiagnosticCode>([
  COMPOSITION_DIAGNOSTIC_CODE.INVALID_TARGET_PATH,
  COMPOSITION_DIAGNOSTIC_CODE.UNSUPPORTED_RESERVED_TARGET,
  COMPOSITION_DIAGNOSTIC_CODE.UNKNOWN_TARGET_REF,
  COMPOSITION_DIAGNOSTIC_CODE.UNKNOWN_UNIFORM,
  COMPOSITION_DIAGNOSTIC_CODE.NON_BINDABLE_TARGET,
  COMPOSITION_DIAGNOSTIC_CODE.TARGET_VALUE_TYPE_ERROR,
  COMPOSITION_DIAGNOSTIC_CODE.TARGET_INTERPOLATION_GAP,
]);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Map a {@link ReferenceState} to its canonical `composition/` diagnostic code.
 *
 * Returns `undefined` for `resolved` (no diagnostic emitted) and for states
 * that are not yet reachable through the current resolver pipeline.
 */
export function referenceStateDiagnosticCode(state: ReferenceState): CompositionDiagnosticCode | undefined {
  switch (state) {
    case 'resolved':
      return undefined;
    case 'missing':
      return COMPOSITION_DIAGNOSTIC_CODE.MISSING_REF;
    case 'disabled':
      return COMPOSITION_DIAGNOSTIC_CODE.DISABLED_REF;
    case 'inactive-reserved':
      return COMPOSITION_DIAGNOSTIC_CODE.INACTIVE_RESERVED_REF;
    case 'invalid-package':
      return COMPOSITION_DIAGNOSTIC_CODE.INVALID_PACKAGE_REF;
    case 'duplicate':
      return COMPOSITION_DIAGNOSTIC_CODE.DUPLICATE_REF;
    case 'settings-error':
      return COMPOSITION_DIAGNOSTIC_CODE.SETTINGS_ERROR_REF;
    case 'runtime-error':
      return COMPOSITION_DIAGNOSTIC_CODE.RUNTIME_ERROR_REF;
    case 'version-incompatible':
      return COMPOSITION_DIAGNOSTIC_CODE.VERSION_INCOMPATIBLE_REF;
    case 'unknown':
      return COMPOSITION_DIAGNOSTIC_CODE.UNKNOWN_REF;
    default: {
      const _exhaustive: never = state;
      return _exhaustive;
    }
  }
}

/**
 * Severity for non-resolved reference states.
 *
 * `missing` and `inactive-reserved` produce warnings; all other non-resolved
 * states produce errors.
 */
export function referenceStateSeverity(state: ReferenceState): DiagnosticSeverity {
  switch (state) {
    case 'resolved':
      return 'info';
    case 'missing':
    case 'inactive-reserved':
      return 'warning';
    default:
      return 'error';
  }
}

export function isBlockingTargetCompositionDiagnosticCode(code: string): code is CompositionDiagnosticCode {
  return BLOCKING_TARGET_COMPOSITION_DIAGNOSTIC_CODES.has(code as CompositionDiagnosticCode);
}

/**
 * Build a canonical composition diagnostic payload.
 *
 * The returned object conforms to {@link ExtensionDiagnostic} and can be
 * published directly into a diagnostic collection or returned as part of
 * graph `diagnostics`.
 */
export function buildCompositionDiagnostic(
  code: CompositionDiagnosticCode,
  message: string,
  detail: CompositionDiagnosticDetail,
): ExtensionDiagnostic {
  return {
    severity: code === COMPOSITION_DIAGNOSTIC_CODE.MISSING_REF
      || code === COMPOSITION_DIAGNOSTIC_CODE.INACTIVE_RESERVED_REF
      ? 'warning'
      : 'error',
    code,
    message,
    detail: detail as Record<string, unknown>,
  };
}
