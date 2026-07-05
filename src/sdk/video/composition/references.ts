/**
 * Composition reference contracts — data-only identifiers for contribution
 * identity, live-source references, and material references.
 *
 * These are plain-data types consumed by the public SDK surface and by
 * host composition infrastructure. None of these types import host
 * runtime or editor-internal modules.
 *
 * @module video/composition/references
 * @publicContract
 */

import type { RenderMaterialRef } from '../../video/rendering/artifacts';
import type { ProcessLiveSourceBinding } from '../families/processes';

// ---------------------------------------------------------------------------
// ContributionRef
// ---------------------------------------------------------------------------

/**
 * A stable, data-only reference to a contribution declared by an extension.
 *
 * The scoped key produced by {@link contributionRefKey} is the canonical
 * identity for composition indexing and duplicate detection. Version and
 * compatibility-range metadata are resolver-level inputs and are not part
 * of the default identity key.
 */
export interface ContributionRef {
  /** Contribution kind (e.g. `'slot'`, `'command'`, `'effect'`). */
  readonly kind: string;

  /** The extension that declared this contribution. */
  readonly extensionId: string;

  /** The contribution's declared ID within the owning extension. */
  readonly contributionId: string;
}

// ---------------------------------------------------------------------------
// LiveSourceRef
// ---------------------------------------------------------------------------

/**
 * A lightweight, data-only reference to a live data source.
 *
 * Live sources are ephemeral runtime objects scoped to a provider mount.
 * This reference carries the minimal identity needed for composition
 * infrastructure to track provenance without importing the full
 * {@link LiveSource} runtime contract.
 */
export interface LiveSourceRef {
  /** Unique source identifier (provider-scoped). */
  readonly sourceId: string;

  /** The kind of live data the source produces. */
  readonly sourceKind?: string;

  /** Optional process binding for process-backed live sources. */
  readonly processBinding?: ProcessLiveSourceBinding;
}

// ---------------------------------------------------------------------------
// MaterialRef
// ---------------------------------------------------------------------------

/**
 * A composition-facing alias for {@link RenderMaterialRef}.
 *
 * `MaterialRef` provides SDK ergonomics for composition scenarios without
 * introducing a parallel material model.  `RenderMaterialRef` remains the
 * canonical, fully-supported public type —`MaterialRef` is a transparent
 * alias, not a deprecation or migration target.
 */
export type MaterialRef = RenderMaterialRef;

// ---------------------------------------------------------------------------
// contributionRefKey
// ---------------------------------------------------------------------------

/**
 * Produce the canonical scoped identity key for a {@link ContributionRef}.
 *
 * Format: `kind:extensionId:contributionId`
 *
 * The key is deterministic and stable for index lookups. It does not
 * include version or compatibility-range fields — those are resolver-level
 * concerns and are not part of the default composition identity.
 *
 * This function also serves as the serialization identity for
 * {@link OutputFormatRef}, preserving graph identity consistency:
 * all contribution refs share the same node-key derivation.
 *
 * @returns The scoped key string `"kind:extensionId:contributionId"`.
 */
export function contributionRefKey(ref: ContributionRef): string {
  return `${ref.kind}:${ref.extensionId}:${ref.contributionId}`;
}

// ---------------------------------------------------------------------------
// OutputFormatRef (M7a)
// ---------------------------------------------------------------------------

/**
 * A constrained output-format contribution reference for M7a route planning.
 *
 * `OutputFormatRef` is a structural subtype of {@link ContributionRef} with
 * `kind` fixed to `'outputFormat'`. It is serialized through
 * {@link contributionRefKey} — no separate serialization system exists.
 * This preserves graph identity consistency: all contribution refs share
 * the same node-key derivation.
 *
 * Extension descriptors for output formats project into composition graph
 * `contribution` nodes keyed by `OutputFormatRef`, enabling `requires` edges
 * from output-format nodes to their declared capability, precondition, or
 * process requirement targets.
 */
export interface OutputFormatRef {
  /** Fixed contribution kind for output-format references. */
  readonly kind: 'outputFormat';
  /** The extension that declared this output format. */
  readonly extensionId: string;
  /** The output format's declared ID within the owning extension. */
  readonly contributionId: string;
}
