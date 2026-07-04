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

  // ---------------------------------------------------------------------------
  // Material (M3a) diagnostic codes
  // ---------------------------------------------------------------------------

  /** A material status/detail combination is structurally invalid. */
  MATERIAL_STATUS_INVALID: 'composition/material-status-invalid',

  /** A material is missing required provenance evidence. */
  MATERIAL_MISSING_PROVENANCE: 'composition/material-missing-provenance',

  /** A material exists only as live runtime data with no baked asset. */
  MATERIAL_LIVE_ONLY: 'composition/material-live-only',

  /** A previously baked material is now out of date. */
  MATERIAL_STALE: 'composition/material-stale',

  /** Materialization has definitively failed. */
  MATERIAL_FAILED: 'composition/material-failed',

  /** A resolved material carries weaker provenance than required. */
  MATERIAL_WEAKER_PROVENANCE: 'composition/material-weaker-provenance',

  /** A resolved material is incompatible with the selected render route. */
  MATERIAL_ROUTE_INCOMPATIBLE: 'composition/material-route-incompatible',

  // ---------------------------------------------------------------------------
  // Deterministic capture (M3b) conversion diagnostic codes
  // ---------------------------------------------------------------------------

  /** Conversion of a deterministic capture to graph operations has failed. */
  DETERMINISTIC_CAPTURE_CONVERSION_FAILED: 'composition/deterministic-capture-conversion-failed',

  /** A deterministic capture specifies a target path that cannot be resolved. */
  DETERMINISTIC_CAPTURE_TARGET_PATH_UNRESOLVABLE: 'composition/deterministic-capture-target-path-unresolvable',

  /** A deterministic capture event value could not be normalized to the target schema. */
  DETERMINISTIC_CAPTURE_VALUE_NORMALIZATION_FAILED: 'composition/deterministic-capture-value-normalization-failed',

  /** A deterministic capture event timing could not be resolved. */
  DETERMINISTIC_CAPTURE_TIMING_FAILED: 'composition/deterministic-capture-timing-failed',

  /** A deterministic capture provenance hash does not match the expected value. */
  DETERMINISTIC_CAPTURE_PROVENANCE_MISMATCH: 'composition/deterministic-capture-provenance-mismatch',
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
  /** Material ref ID when the diagnostic relates to a material. */
  materialRefId?: string;
  /** Render route scope when the diagnostic is route-sensitive. */
  routeScope?: string;
  /** Resolved material status state. */
  materialStatus?: string;
  /** Material status detail phase. */
  detailPhase?: string;
  /** Material status detail quality. */
  detailQuality?: string;
  /** Provenance evidence attached to the material ref. */
  provenance?: Record<string, unknown>;
  /** Structured description of the provenance gap when validation fails. */
  provenanceGap?: string;
  /** Planner next action associated with this diagnostic, when applicable. */
  nextAction?: Record<string, unknown>;
  /** Deterministic capture ref ID when the diagnostic relates to a capture conversion. */
  captureRef?: string;
  /** Provenance hash of the deterministic capture (SHA-256 hex, 64 chars). */
  provenanceHash?: string;
}

const BLOCKING_TARGET_COMPOSITION_DIAGNOSTIC_CODES = new Set<CompositionDiagnosticCode>([
  COMPOSITION_DIAGNOSTIC_CODE.INVALID_TARGET_PATH,
  COMPOSITION_DIAGNOSTIC_CODE.UNSUPPORTED_RESERVED_TARGET,
  COMPOSITION_DIAGNOSTIC_CODE.UNKNOWN_TARGET_REF,
  COMPOSITION_DIAGNOSTIC_CODE.UNKNOWN_UNIFORM,
  COMPOSITION_DIAGNOSTIC_CODE.NON_BINDABLE_TARGET,
  COMPOSITION_DIAGNOSTIC_CODE.TARGET_VALUE_TYPE_ERROR,
  COMPOSITION_DIAGNOSTIC_CODE.TARGET_INTERPOLATION_GAP,
  COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_CONVERSION_FAILED,
  COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_TARGET_PATH_UNRESOLVABLE,
  COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_VALUE_NORMALIZATION_FAILED,
  COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_TIMING_FAILED,
  COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_PROVENANCE_MISMATCH,
]);

/** Material diagnostic codes that carry warning severity. */
const MATERIAL_WARNING_DIAGNOSTIC_CODES = new Set<CompositionDiagnosticCode>([
  COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_MISSING_PROVENANCE,
  COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_LIVE_ONLY,
  COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_STALE,
  COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_WEAKER_PROVENANCE,
]);

/** Material diagnostic codes that carry error severity. */
const MATERIAL_ERROR_DIAGNOSTIC_CODES = new Set<CompositionDiagnosticCode>([
  COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_STATUS_INVALID,
  COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_FAILED,
  COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_ROUTE_INCOMPATIBLE,
]);

/** All material diagnostic codes (M3a). */
const MATERIAL_DIAGNOSTIC_CODES: ReadonlySet<CompositionDiagnosticCode> = new Set([
  COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_MISSING_PROVENANCE,
  COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_LIVE_ONLY,
  COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_STALE,
  COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_WEAKER_PROVENANCE,
  COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_STATUS_INVALID,
  COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_FAILED,
  COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_ROUTE_INCOMPATIBLE,
]);

/** All deterministic capture conversion diagnostic codes (M3b). */
const DETERMINISTIC_CAPTURE_CONVERSION_DIAGNOSTIC_CODES: ReadonlySet<CompositionDiagnosticCode> = new Set([
  COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_CONVERSION_FAILED,
  COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_TARGET_PATH_UNRESOLVABLE,
  COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_VALUE_NORMALIZATION_FAILED,
  COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_TIMING_FAILED,
  COMPOSITION_DIAGNOSTIC_CODE.DETERMINISTIC_CAPTURE_PROVENANCE_MISMATCH,
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
 * Type guard: returns `true` when `code` is a material (M3a) diagnostic code.
 */
export function isMaterialDiagnosticCode(code: string): code is CompositionDiagnosticCode {
  return MATERIAL_DIAGNOSTIC_CODES.has(code as CompositionDiagnosticCode);
}

/**
 * Type guard: returns `true` when `code` is a deterministic capture
 * conversion (M3b) diagnostic code.
 *
 * These codes remain separate from material live-only diagnostics so that
 * consumers (export guard, planner) can distinguish material issues from
 * deterministic capture conversion issues.
 */
export function isDeterministicCaptureConversionDiagnosticCode(code: string): code is CompositionDiagnosticCode {
  return DETERMINISTIC_CAPTURE_CONVERSION_DIAGNOSTIC_CODES.has(code as CompositionDiagnosticCode);
}

/**
 * Severity for material (M3a) diagnostic codes.
 *
 * Invalid status, failed materialization, and route-incompatible materials
 * produce errors; missing provenance, live-only, stale, and weaker-provenance
 * produce warnings.
 */
export function materialDiagnosticSeverity(code: CompositionDiagnosticCode): DiagnosticSeverity {
  if (MATERIAL_ERROR_DIAGNOSTIC_CODES.has(code)) {
    return 'error';
  }
  if (MATERIAL_WARNING_DIAGNOSTIC_CODES.has(code)) {
    return 'warning';
  }
  return 'error';
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
  let severity: DiagnosticSeverity;
  if (isMaterialDiagnosticCode(code)) {
    severity = materialDiagnosticSeverity(code);
  } else if (isDeterministicCaptureConversionDiagnosticCode(code)) {
    // Deterministic capture conversion issues are always blocking errors.
    severity = 'error';
  } else if (
    code === COMPOSITION_DIAGNOSTIC_CODE.MISSING_REF
    || code === COMPOSITION_DIAGNOSTIC_CODE.INACTIVE_RESERVED_REF
  ) {
    severity = 'warning';
  } else {
    severity = 'error';
  }

  return {
    severity,
    code,
    message,
    detail: detail as Record<string, unknown>,
  };
}
