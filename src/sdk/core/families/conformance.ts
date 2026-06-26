/**
 * Family conformance reporting — report types, gap analysis, and
 * cross-axis coherence validation.
 *
 * These types and helpers are data/type-only. They do NOT import host
 * runtime code (editor internals, DataProvider, timeline ops, etc.).
 *
 * @module families/conformance
 * @publicContract
 */

import type {
  DeclarationMaturity,
  ExecutionMaturity,
  FamilyDefinition,
  FamilyRequirementChecklist,
} from './maturity';
import {
  declarationMaturityAtLeast,
} from './maturity';

// ---------------------------------------------------------------------------
// Conformance report
// ---------------------------------------------------------------------------

/**
 * A conformance report for a single family, built from its
 * `FamilyDefinition`.  Reports the current declaration/execution
 * coordinates, requirement coverage, any detected gaps, and
 * cross-axis coherence status.
 */
export interface FamilyConformanceReport<Kind extends string = string> {
  /** The contribution kind this report covers. */
  readonly kind: Kind;

  /** The family definition this report was derived from. */
  readonly definition: FamilyDefinition<Kind>;

  /** Current declaration maturity coordinate. */
  readonly declarationMaturity: DeclarationMaturity;

  /** Current execution maturity coordinate. */
  readonly executionMaturity: ExecutionMaturity;

  /** Requirement checklist from the definition. */
  readonly requirements: FamilyRequirementChecklist;

  /** Requirements that are explicitly unmet. */
  readonly unmetRequirements: (keyof FamilyRequirementChecklist)[];

  /** Requirements that are explicitly met. */
  readonly metRequirements: (keyof FamilyRequirementChecklist)[];

  /** Requirements whose status has not yet been assessed. */
  readonly unassessedRequirements: (keyof FamilyRequirementChecklist)[];

  /** Detected gaps (requirement, coherence, or schema coverage). */
  readonly gaps: readonly ConformanceGap[];

  /** Whether the family passes all coherence checks. */
  readonly coherent: boolean;

  /** Whether the family has all required schema coverage. */
  readonly schemaCovered: boolean;
}

// ---------------------------------------------------------------------------
// Gap types
// ---------------------------------------------------------------------------

/**
 * A detected gap in a family's maturity posture.
 */
export interface ConformanceGap {
  /** The gap category. */
  readonly category: ConformanceGapCategory;

  /** Human-readable description of the gap. */
  readonly message: string;

  /** The requirement keys involved, if applicable. */
  readonly requirementKeys?: readonly (keyof FamilyRequirementChecklist)[];

  /**
   * Optional free-form metadata for extensibility.
   *
   * Consumers (adapter registry, gap reporters, tooling) may attach
   * structured metadata here (e.g. adapter provenance, maturity
   * projection details, schema references) without adding new fields
   * to the core ConformanceGap interface.
   */
  readonly metadata?: Record<string, unknown>;
}

/**
 * Categories of conformance gaps.
 *
 * - `unmet-requirement`        — A requirement is explicitly flagged as unmet.
 * - `coherence-violation`      — Cross-axis maturity combination is incoherent.
 * - `schema-coverage-missing`  — Declaration maturity expects schema coverage
 *                                but none is confirmed.
 * - `host-adapter-missing`     — Execution maturity expects a host adapter but
 *                                none is defined.
 * - `unassessed-requirement`   — A requirement's status has not been assessed.
 */
export type ConformanceGapCategory =
  | 'unmet-requirement'
  | 'coherence-violation'
  | 'schema-coverage-missing'
  | 'host-adapter-missing'
  | 'unassessed-requirement';

// ---------------------------------------------------------------------------
// Cross-axis coherence
// ---------------------------------------------------------------------------

/**
 * Result of a cross-axis coherence check.
 */
export interface CrossAxisCoherenceResult {
  /** Whether the combination is coherent. */
  readonly coherent: boolean;

  /** If not coherent, a list of violation descriptions. */
  readonly violations: readonly string[];
}

/**
 * Check whether a declaration/execution maturity pair is coherent.
 *
 * Rules:
 * - Execution maturity `runtime-bridged` or higher requires declaration
 *   maturity at least `schema-backed`.
 * - Execution maturity `host-integrated` or higher requires declaration
 *   maturity at least `documented`.
 * - Execution maturity cannot be `public-supported` unless declaration
 *   maturity is `documented`.
 */
export function checkCrossAxisCoherence(
  declarationMaturity: DeclarationMaturity,
  executionMaturity: ExecutionMaturity,
): CrossAxisCoherenceResult {
  const violations: string[] = [];

  // Rule 1: runtime-bridged+ → declaration at least schema-backed
  if (
    executionMaturity === 'runtime-bridged' ||
    executionMaturity === 'host-integrated' ||
    executionMaturity === 'public-supported'
  ) {
    if (!declarationMaturityAtLeast(declarationMaturity, 'schema-backed')) {
      violations.push(
        `Execution maturity "${executionMaturity}" requires declaration ` +
          `maturity at least "schema-backed", but got "${declarationMaturity}".`,
      );
    }
  }

  // Rule 2: host-integrated+ → declaration at least documented
  if (
    executionMaturity === 'host-integrated' ||
    executionMaturity === 'public-supported'
  ) {
    if (!declarationMaturityAtLeast(declarationMaturity, 'documented')) {
      violations.push(
        `Execution maturity "${executionMaturity}" requires declaration ` +
          `maturity at least "documented", but got "${declarationMaturity}".`,
      );
    }
  }

  // Rule 3: public-supported → dedication documented
  if (executionMaturity === 'public-supported') {
    if (declarationMaturity !== 'documented') {
      // Already caught by rule 2, but keep as explicit check for clarity.
      violations.push(
        `Execution maturity "public-supported" requires declaration ` +
          `maturity "documented", but got "${declarationMaturity}".`,
      );
    }
  }

  // Deduplicate violations
  const uniqueViolations = [...new Set(violations)];

  return {
    coherent: uniqueViolations.length === 0,
    violations: uniqueViolations,
  };
}

/**
 * Check cross-axis coherence for a `FamilyDefinition` by reading its
 * maturity fields.
 */
export function checkFamilyCoherence<Kind extends string>(
  definition: FamilyDefinition<Kind>,
): CrossAxisCoherenceResult {
  return checkCrossAxisCoherence(
    definition.declarationMaturity,
    definition.executionMaturity,
  );
}

// ---------------------------------------------------------------------------
// Conformance report builder
// ---------------------------------------------------------------------------

/**
 * Build a full `FamilyConformanceReport` from a `FamilyDefinition`.
 * This is a pure function with no side effects.
 */
export function buildConformanceReport<Kind extends string>(
  definition: FamilyDefinition<Kind>,
): FamilyConformanceReport<Kind> {
  const unmetReqs: (keyof FamilyRequirementChecklist)[] = [];
  const metReqs: (keyof FamilyRequirementChecklist)[] = [];
  const unassessedReqs: (keyof FamilyRequirementChecklist)[] = [];

  for (const key of Object.keys(definition.requirements) as (keyof FamilyRequirementChecklist)[]) {
    const value = definition.requirements[key];
    if (value === false) {
      unmetReqs.push(key);
    } else if (value === true) {
      metReqs.push(key);
    } else {
      unassessedReqs.push(key);
    }
  }

  const gaps: ConformanceGap[] = [];

  // Unmet requirements
  for (const key of unmetReqs) {
    gaps.push({
      category: 'unmet-requirement',
      message: `Requirement "${key}" is explicitly unmet.`,
      requirementKeys: [key],
    });
  }

  // Unassessed requirements
  for (const key of unassessedReqs) {
    gaps.push({
      category: 'unassessed-requirement',
      message: `Requirement "${key}" has not been assessed.`,
      requirementKeys: [key],
    });
  }

  // Cross-axis coherence
  const coherence = checkCrossAxisCoherence(
    definition.declarationMaturity,
    definition.executionMaturity,
  );
  for (const violation of coherence.violations) {
    gaps.push({
      category: 'coherence-violation',
      message: violation,
    });
  }

  // Schema coverage: schema-backed+ must have manifest schema requirement met
  const schemaCovered =
    declarationMaturityAtLeast(definition.declarationMaturity, 'schema-backed') &&
    definition.requirements.manifestSchema === true;

  if (
    declarationMaturityAtLeast(definition.declarationMaturity, 'schema-backed') &&
    definition.requirements.manifestSchema !== true
  ) {
    gaps.push({
      category: 'schema-coverage-missing',
      message:
        `Declaration maturity "${definition.declarationMaturity}" expects ` +
        `manifest schema coverage, but requirement "manifestSchema" is not met.`,
      requirementKeys: ['manifestSchema'],
    });
  }

  // Host adapter check for execution maturity that implies host runtime
  if (
    definition.executionMaturity !== 'absent' &&
    definition.executionMaturity !== 'delegated' &&
    definition.hostAdapter === null
  ) {
    gaps.push({
      category: 'host-adapter-missing',
      message:
        `Execution maturity "${definition.executionMaturity}" expects a host ` +
        `adapter path, but none is defined.`,
    });
  }

  return {
    kind: definition.kind,
    definition,
    declarationMaturity: definition.declarationMaturity,
    executionMaturity: definition.executionMaturity,
    requirements: definition.requirements,
    unmetRequirements: unmetReqs,
    metRequirements: metReqs,
    unassessedRequirements: unassessedReqs,
    gaps,
    coherent: coherence.coherent,
    schemaCovered,
  };
}

/**
 * Compute just the gaps for a family definition without building a full
 * conformance report.  Lightweight helper for quick gap scanning.
 */
export function computeGaps<Kind extends string>(
  definition: FamilyDefinition<Kind>,
): readonly ConformanceGap[] {
  return buildConformanceReport(definition).gaps;
}

/**
 * Returns `true` when a family definition has no gaps and is fully coherent.
 */
export function isFullyConformant<Kind extends string>(
  definition: FamilyDefinition<Kind>,
): boolean {
  const report = buildConformanceReport(definition);
  return report.gaps.length === 0 && report.coherent && report.schemaCovered;
}

// ---------------------------------------------------------------------------
// Compatibility metadata
// ---------------------------------------------------------------------------

/**
 * Legacy milestone compatibility entry derived from a family definition.
 * Used to populate `CONTRIBUTION_KIND_MILESTONE` in a registry-derived way.
 */
export interface LegacyMilestoneEntry {
  /** The contribution kind. */
  readonly kind: string;
  /** The milestone string (e.g. 'M1', 'M6', 'M13'), or `undefined`. */
  readonly milestone: string | undefined;
}

/**
 * Extract a legacy milestone entry from a family definition.
 * Returns `kind` and `legacyMilestone` (or `undefined` if not set).
 */
export function toLegacyMilestoneEntry<Kind extends string>(
  definition: FamilyDefinition<Kind>,
): LegacyMilestoneEntry {
  return {
    kind: definition.kind,
    milestone: definition.legacyMilestone,
  };
}

/**
 * Build a `Record<Kind, string | undefined>` compatible with the legacy
 * `CONTRIBUTION_KIND_MILESTONE` shape from an array of family definitions.
 */
export function buildLegacyMilestoneMap<Kind extends string>(
  definitions: readonly FamilyDefinition<Kind>[],
): Record<string, string | undefined> {
  const map: Record<string, string | undefined> = {};
  for (const def of definitions) {
    map[def.kind] = def.legacyMilestone;
  }
  return map;
}
