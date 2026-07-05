/**
 * Family maturity model — declaration and execution axes, requirement
 * checklists, and the generic `FamilyDefinition` contract.
 *
 * These types and helpers are data/type-only. They do NOT import host
 * runtime code (editor internals, DataProvider, timeline ops, etc.).
 *
 * @module families/maturity
 * @publicContract
 */

// ---------------------------------------------------------------------------
// Declaration maturity axis
// ---------------------------------------------------------------------------

/**
 * How well the extension-author contract (types, schema, docs) is defined.
 *
 * - `typed`            — TypeScript types exist.
 * - `schema-backed`    — Manifest schema and descriptor shape are stable.
 * - `documented`       — Author docs and examples exist.
 */
export type DeclarationMaturity = 'typed' | 'schema-backed' | 'documented';

/** Ordered declaration maturity levels (least → most mature). */
export const DECLARATION_MATURITY_LEVELS: readonly DeclarationMaturity[] = [
  'typed',
  'schema-backed',
  'documented',
] as const;

// ---------------------------------------------------------------------------
// Execution maturity axis
// ---------------------------------------------------------------------------

/**
 * How much real host runtime behavior exists for a family.
 *
 * - `absent`           — No host runtime behavior.
 * - `delegated`        — Runtime behavior exists but delegates through an
 *                        extracted host projector with a placeholder adapter
 *                        that reports a conformance gap.
 * - `runtime-bridged`  — A real, independent host adapter owns normalization,
 *                        lifecycle, and diagnostics.
 * - `host-integrated`  — Export/render planner or host-phase participation is
 *                        real and tested.
 * - `public-supported` — Lifecycle, UI, diagnostics, persistence, examples,
 *                        and conformance tests are complete.
 */
export type ExecutionMaturity =
  | 'absent'
  | 'delegated'
  | 'runtime-bridged'
  | 'host-integrated'
  | 'public-supported';

/** Ordered execution maturity levels (least → most mature). */
export const EXECUTION_MATURITY_LEVELS: readonly ExecutionMaturity[] = [
  'absent',
  'delegated',
  'runtime-bridged',
  'host-integrated',
  'public-supported',
] as const;

// ---------------------------------------------------------------------------
// Requirement checklist
// ---------------------------------------------------------------------------

/**
 * Compact coverage flags for each requirement area in the family maturity
 * checklist.  Each flag is `true` when the requirement is demonstrably met,
 * `false` when it is known to be missing, and `undefined` when its status
 * has not yet been assessed.
 */
export interface FamilyRequirementChecklist {
  /** Manifest schema definition exists in the canonical schema file. */
  manifestSchema: boolean | undefined;
  /** A normalized descriptor shape is exposed. */
  normalizedDescriptor: boolean | undefined;
  /** A registration API is available to extensions. */
  registrationApi: boolean | undefined;
  /** Lifecycle cleanup (dispose, teardown) is implemented. */
  lifecycleCleanup: boolean | undefined;
  /** Diagnostics are produced for author-visible problems. */
  diagnostics: boolean | undefined;
  /**
   * Host capability projection (e.g. video render planner projection) is
   * wired and tested.
   */
  hostCapabilityProjection: boolean | undefined;
  /** UI integration exists for the contribution kind. */
  uiIntegration: boolean | undefined;
  /** Persistence posture is defined (saved/restored state). */
  persistencePosture: boolean | undefined;
  /** Author-facing examples exist. */
  examples: boolean | undefined;
  /** Conformance tests exist. */
  tests: boolean | undefined;
  /** Sidecar export capability is tracked (M7b). */
  sidecarExport?: boolean | undefined;
  /** Artifact route completion evidence exists (M7b). */
  artifactRouteCompletion?: boolean | undefined;
}

// ---------------------------------------------------------------------------
// Family definition
// ---------------------------------------------------------------------------

/**
 * Canonical definition of a contribution family with two-axis maturity,
 * requirement coverage, schema binding, and SDK/host module paths.
 *
 * @typeParam Kind — The string-literal kind this family represents
 *                   (defaults to `string` for generic use).
 */
export interface FamilyDefinition<Kind extends string = string> {
  /** The contribution kind this family describes. */
  readonly kind: Kind;

  /** How well the author-facing contract is defined. */
  readonly declarationMaturity: DeclarationMaturity;

  /** How much real host runtime behavior exists. */
  readonly executionMaturity: ExecutionMaturity;

  /**
   * Optional human-readable notes about host integration status,
   * bridging posture, or known gaps.
   */
  readonly hostIntegrationNotes?: string;

  /** Whether this family requires trusted-code execution. */
  readonly requiresTrustedCode: boolean;

  /**
   * The manifest schema definition name (in `config/contracts/reigh-extension.schema.json`)
   * that corresponds to this family's contribution shape.
   */
  readonly manifestSchemaDefinition: string;

  /** SDK module path(s) where this family's types/helpers live. */
  readonly sdkModules: readonly string[];

  /**
   * Host adapter module path, or `null` when no host adapter exists
   * (e.g. execution maturity is `absent` or `delegated` with a placeholder).
   */
  readonly hostAdapter: string | null;

  /** Coverage flags for each requirement area. */
  readonly requirements: FamilyRequirementChecklist;

  /**
   * Optional compatibility metadata for legacy milestone bridging.
   * Populated only for families that previously relied on
   * `CONTRIBUTION_KIND_MILESTONE`.
   */
  readonly legacyMilestone?: string;

  /**
   * Optional human-readable label for diagnostics / UI.
   * Defaults to `kind` when absent.
   */
  readonly label?: string;

  /**
   * Optional longer description of the family's purpose and scope.
   */
  readonly description?: string;
}

// ---------------------------------------------------------------------------
// Maturity ordering helpers
// ---------------------------------------------------------------------------

/** Set of declaration maturity levels for fast lookups. */
const DECLARATION_MATURITY_SET: ReadonlySet<string> = new Set(DECLARATION_MATURITY_LEVELS);

/** Set of execution maturity levels for fast lookups. */
const EXECUTION_MATURITY_SET: ReadonlySet<string> = new Set(EXECUTION_MATURITY_LEVELS);

/**
 * Returns `true` when `a` is at least as mature as `b` on the
 * declaration axis.
 */
export function declarationMaturityAtLeast(
  a: DeclarationMaturity,
  b: DeclarationMaturity,
): boolean {
  const indexA = DECLARATION_MATURITY_LEVELS.indexOf(a);
  const indexB = DECLARATION_MATURITY_LEVELS.indexOf(b);
  return indexA >= indexB;
}

/**
 * Returns `true` when `a` is at least as mature as `b` on the
 * execution axis.
 */
export function executionMaturityAtLeast(
  a: ExecutionMaturity,
  b: ExecutionMaturity,
): boolean {
  const indexA = EXECUTION_MATURITY_LEVELS.indexOf(a);
  const indexB = EXECUTION_MATURITY_LEVELS.indexOf(b);
  return indexA >= indexB;
}

/**
 * Compare two declaration maturity levels.
 * Returns a negative number when `a` is less mature than `b`,
 * zero when equal, and positive when `a` is more mature.
 */
export function compareDeclarationMaturity(
  a: DeclarationMaturity,
  b: DeclarationMaturity,
): number {
  return DECLARATION_MATURITY_LEVELS.indexOf(a) - DECLARATION_MATURITY_LEVELS.indexOf(b);
}

/**
 * Compare two execution maturity levels.
 * Returns a negative number when `a` is less mature than `b`,
 * zero when equal, and positive when `a` is more mature.
 */
export function compareExecutionMaturity(
  a: ExecutionMaturity,
  b: ExecutionMaturity,
): number {
  return EXECUTION_MATURITY_LEVELS.indexOf(a) - EXECUTION_MATURITY_LEVELS.indexOf(b);
}

/** Type guard for `DeclarationMaturity`. */
export function isDeclarationMaturity(value: string): value is DeclarationMaturity {
  return DECLARATION_MATURITY_SET.has(value);
}

/** Type guard for `ExecutionMaturity`. */
export function isExecutionMaturity(value: string): value is ExecutionMaturity {
  return EXECUTION_MATURITY_SET.has(value);
}

/**
 * Validate that a `DeclarationMaturity` string is a known level.
 * Returns an array of error messages (empty = valid).
 */
export function validateDeclarationMaturity(value: string): string[] {
  const errors: string[] = [];
  if (!DECLARATION_MATURITY_SET.has(value)) {
    errors.push(
      `Unknown declaration maturity "${value}". ` +
        `Expected one of: ${DECLARATION_MATURITY_LEVELS.join(', ')}`,
    );
  }
  return errors;
}

/**
 * Validate that an `ExecutionMaturity` string is a known level.
 * Returns an array of error messages (empty = valid).
 */
export function validateExecutionMaturity(value: string): string[] {
  const errors: string[] = [];
  if (!EXECUTION_MATURITY_SET.has(value)) {
    errors.push(
      `Unknown execution maturity "${value}". ` +
        `Expected one of: ${EXECUTION_MATURITY_LEVELS.join(', ')}`,
    );
  }
  return errors;
}

/**
 * Return all requirement keys that are explicitly unmet (`false`) in a
 * checklist.  Keys whose status is `undefined` (not yet assessed) are
 * not included.
 */
export function unmetRequirements(
  checklist: FamilyRequirementChecklist,
): (keyof FamilyRequirementChecklist)[] {
  const unmet: (keyof FamilyRequirementChecklist)[] = [];
  for (const key of Object.keys(checklist) as (keyof FamilyRequirementChecklist)[]) {
    if (checklist[key] === false) {
      unmet.push(key);
    }
  }
  return unmet;
}

/**
 * Return all requirement keys that are explicitly met (`true`) in a
 * checklist.
 */
export function metRequirements(
  checklist: FamilyRequirementChecklist,
): (keyof FamilyRequirementChecklist)[] {
  const met: (keyof FamilyRequirementChecklist)[] = [];
  for (const key of Object.keys(checklist) as (keyof FamilyRequirementChecklist)[]) {
    if (checklist[key] === true) {
      met.push(key);
    }
  }
  return met;
}

/**
 * Return all requirement keys whose status has not yet been assessed
 * (`undefined`).
 */
export function unassessedRequirements(
  checklist: FamilyRequirementChecklist,
): (keyof FamilyRequirementChecklist)[] {
  const unassessed: (keyof FamilyRequirementChecklist)[] = [];
  for (const key of Object.keys(checklist) as (keyof FamilyRequirementChecklist)[]) {
    if (checklist[key] === undefined) {
      unassessed.push(key);
    }
  }
  return unassessed;
}
