/**
 * CompositionGraph — public SDK contracts for the M1b composition graph.
 *
 * These contracts define the graph shape, node kinds, edge kinds, resolver
 * states, and preview interface exposed through the public SDK barrel.
 * They are pure data contracts; host projection, resolution, and preview
 * logic live in runtime composition modules and are NOT re-exported here.
 *
 * M1b introduced shader/ref facts and `consumes` edges as the initial graph
 * authority surface. M2 expands the public edge vocabulary with `animates`
 * and `binds-live` while keeping node kinds and resolver states stable.
 *
 * @module video/composition/graph
 * @publicContract
 */

import type { ExtensionDiagnostic } from '../../diagnostics';
import type { ContributionRef } from './references';

// ---------------------------------------------------------------------------
// Node kinds
// ---------------------------------------------------------------------------

/**
 * M1b composition node kinds.
 *
 * - `clip`             — a timeline clip (shader-assignable scope).
 * - `timeline-postprocess` — the timeline-wide postprocess scope.
 * - `contribution`     — a contribution declared by an extension (shader,
 *                        effect, parser, etc.).
 *
 * These are the only node kinds for M1b graph authority.
 */
export type CompositionNodeKind = 'clip' | 'timeline-postprocess' | 'contribution';

/**
 * The canonical set of M1b node kinds.
 */
export const COMPOSITION_NODE_KINDS: readonly CompositionNodeKind[] = [
  'clip',
  'timeline-postprocess',
  'contribution',
] as const;

// ---------------------------------------------------------------------------
// Edge kinds
// ---------------------------------------------------------------------------

/**
 * M1b public edge kinds.
 *
 * - `consumes` — a source node (clip or timeline-postprocess) consumes a
 *                shader contribution from a target contribution node.
 * - `animates` — an automation clip drives a contribution target path.
 * - `binds-live` — a clip carries a resolved live binding for a target path.
 */
export type CompositionEdgeKind = 'consumes' | 'animates' | 'binds-live';

/**
 * The canonical set of M1b public edge kinds.
 */
export const COMPOSITION_EDGE_KINDS: readonly CompositionEdgeKind[] = [
  'consumes',
  'animates',
  'binds-live',
] as const;

// ---------------------------------------------------------------------------
// Resolver states — exactly 10
// ---------------------------------------------------------------------------

/**
 * Reference resolver state produced by the host resolver.
 *
 * Locked M1b states (v8 resolver precedence):
 *
 *  1. `resolved`            — a valid, active, package-healthy contribution ref.
 *  2. `missing`             — no scoped candidate exists in the index.
 *  3. `disabled`            — user-disabled package.
 *  4. `inactive-reserved`   — kind not yet bridged in this runtime.
 *  5. `invalid-package`     — package marked invalid by the loader.
 *  6. `duplicate`           — exact scoped-key duplicate (first-wins loser).
 *  7. `settings-error`      — package loaded but settings migration failed.
 *  8. `runtime-error`       — package loaded but runtime activation error.
 *  9. `version-incompatible` — package is incompatible with the current host version.
 * 10. `unknown`             — fallback for unrecognised states.
 *
 * `missing` is defined ONLY as zero scoped candidates — it is never used
 * when candidates exist but are in a non-resolved state.
 */
export type ReferenceState =
  | 'resolved'
  | 'missing'
  | 'disabled'
  | 'inactive-reserved'
  | 'invalid-package'
  | 'duplicate'
  | 'settings-error'
  | 'runtime-error'
  | 'version-incompatible'
  | 'unknown';

/**
 * The canonical ordered set of all 10 resolver states.
 */
export const REFERENCE_STATES: readonly ReferenceState[] = [
  'resolved',
  'missing',
  'disabled',
  'inactive-reserved',
  'invalid-package',
  'duplicate',
  'settings-error',
  'runtime-error',
  'version-incompatible',
  'unknown',
] as const;

// ---------------------------------------------------------------------------
// Graph nodes
// ---------------------------------------------------------------------------

/**
 * A single node in the composition graph.
 *
 * Every node carries a unique graph-level `id`, a `kind`, and an optional
 * `ref` that links it to a contribution identity when applicable.
 * Additional kind-specific metadata is carried in `detail`.
 */
export interface CompositionGraphNode {
  /** Unique node identifier within the graph (scoped to the projection). */
  readonly id: string;
  /** Node kind. */
  readonly kind: CompositionNodeKind;
  /** Contribution identity reference, when this node represents a contribution. */
  readonly ref?: ContributionRef;
  /** Kind-specific structured detail. */
  readonly detail?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Graph edges
// ---------------------------------------------------------------------------

/**
 * A single directed edge in the composition graph.
 *
 * Edge detail is kind-specific: shader assignment metadata for `consumes`,
 * canonical target-path metadata for `animates` / `binds-live`, and
 * future per-kind fields as the graph surface evolves.
 */
export interface CompositionGraphEdge {
  /** Unique edge identifier within the graph (scoped to the projection). */
  readonly id: string;
  /** Edge kind. */
  readonly kind: CompositionEdgeKind;
  /** ID of the source node (clip or timeline-postprocess). */
  readonly sourceNodeId: string;
  /** ID of the target node (contribution node). */
  readonly targetNodeId: string;
  /** Optional kind-specific structured detail (e.g. shaderId). */
  readonly detail?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Reference state entries
// ---------------------------------------------------------------------------

/**
 * A single reference-state entry produced by the resolver.
 *
 * Each entry maps a contribution ref key to its resolved state and links
 * back to the graph node(s) that reference it.
 */
export interface CompositionReferenceStateEntry {
  /** The scoped contribution ref key (`kind:extensionId:contributionId`). */
  readonly refKey: string;
  /** The resolved reference state. */
  readonly state: ReferenceState;
  /** IDs of graph nodes that reference this contribution. */
  readonly nodeIds: readonly string[];
}

// ---------------------------------------------------------------------------
// Graph preview
// ---------------------------------------------------------------------------

/**
 * Lightweight public shape for graph preview results.
 *
 * Returned by `CompositionGraph.preview` after applying internal patch
 * operations (`shader.assign` / `shader.remove`).  The preview result
 * carries the projected nodes, edges, updated reference states, and
 * diagnostics that would result from the preview operations.
 */
export interface CompositionGraphPreviewResult {
  /** Projected graph nodes after preview operations. */
  readonly nodes: readonly CompositionGraphNode[];
  /** Projected graph edges after preview operations. */
  readonly edges: readonly CompositionGraphEdge[];
  /** Updated reference states after preview operations. */
  readonly referenceStates: readonly CompositionReferenceStateEntry[];
  /** Diagnostics produced during preview resolution. */
  readonly diagnostics: readonly ExtensionDiagnostic[];
}

// ---------------------------------------------------------------------------
// CompositionGraph — the top-level contract
// ---------------------------------------------------------------------------

/**
 * The composition graph projection for an editor render surface.
 *
 * Constructed eagerly during extension runtime assembly and attached to
 * `ExtensionRuntime`.  When present, the graph becomes the authoritative
 * source for M1b shader/ref facts and contribution-index lookups consumed
 * by the planner, export guard, and shader validation.
 *
 * Fields:
 * - `nodes`           — all projected graph nodes.
 * - `edges`           — all projected graph edges.
 * - `referenceStates` — resolved reference states for every contribution ref
 *                       referenced by graph nodes/edges.
 * - `diagnostics`     — projection-level diagnostics (duplicate scope, etc.).
 * - `preview`         — produce a preview result from internal patch operations
 *                       (`shader.assign` / `shader.remove`) without mutating
 *                       the original graph.
 */
export interface CompositionGraph {
  /** Projected graph nodes (read-only). */
  readonly nodes: readonly CompositionGraphNode[];
  /** Projected graph edges (read-only). */
  readonly edges: readonly CompositionGraphEdge[];
  /** Resolved reference states for every scoped contribution ref. */
  readonly referenceStates: readonly CompositionReferenceStateEntry[];
  /** Projection-level diagnostics. */
  readonly diagnostics: readonly ExtensionDiagnostic[];
  /**
   * Produce a lightweight preview of the graph after applying internal
   * patch operations (shader assign/remove).
   *
   * Returns `undefined` when no preview operations are pending.
   */
  readonly preview?: () => CompositionGraphPreviewResult | undefined;
}
