import type {
  RouteFitMetadata,
  RenderRoute,
  RenderBlockerReason,
  CapabilityFinding,
} from '@reigh/editor-sdk';
import type {
  ContributionIndex,
  ContributionIndexEntry,
  VideoEditorPlannerBlockerDescriptor,
} from '@/tools/video-editor/runtime/extensionSurface.ts';

/**
 * Lightweight identity fragment used by the route-fit mapper.
 *
 * Callers supply whichever identity fields they have; the mapper resolves
 * a scoped key from the contribution index when possible.
 */
export interface RouteFitIdentityFragment {
  readonly kind?: string;
  readonly extensionId?: string;
  readonly contributionId?: string;
}

/**
 * Input parameters for the route-fit metadata mapper.
 *
 * The mapper joins the caller-supplied identity fragment against the
 * contribution index and returns merged route-fit metadata only when the
 * contribution identity is directly or uniquely resolvable.
 */
export interface RouteFitMapperParams {
  /** Host-owned contribution index used for scoped-key resolution. */
  readonly contributionIndex?: ContributionIndex;
  /** Identity fragment — any combination of kind, extensionId, contributionId. */
  readonly identity?: RouteFitIdentityFragment;
  /** Route the fit metadata applies to. */
  readonly route: RenderRoute;
  /** Caller-supplied fit, used when the index does not override it. */
  readonly fit?: RouteFitMetadata['fit'];
  /** Caller-supplied reason, used when the index does not override it. */
  readonly reason?: RenderBlockerReason;
  /** Caller-supplied message, used when the index does not override it. */
  readonly message?: string;
}

/**
 * Try to resolve a scoped key (`kind:extensionId:contributionId`) from the
 * contribution index using whichever identity fragments are available.
 *
 * Resolution succeeds when:
 * - `kind`, `extensionId`, and `contributionId` are all supplied → direct lookup.
 * - `extensionId` and `contributionId` are supplied and exactly one entry in the
 *   index shares those fields across all `kind` values → unique match.
 *
 * In all other cases the scoped key is considered ambiguous and `undefined` is
 * returned.
 */
export function resolveScopedKey(
  contributionIndex: ContributionIndex | undefined,
  identity: RouteFitIdentityFragment | undefined,
): string | undefined {
  if (!contributionIndex || !identity) return undefined;

  const { kind, extensionId, contributionId } = identity;
  if (!extensionId || !contributionId) return undefined;

  // Direct lookup when all three pieces are known.
  if (kind) {
    const scopedKey = `${kind}:${extensionId}:${contributionId}`;
    return scopedKey in contributionIndex ? scopedKey : undefined;
  }

  // Kind is missing — scan the index for a unique match.
  let matchedKey: string | undefined;
  for (const scopedKey of Object.keys(contributionIndex)) {
    const entries = contributionIndex[scopedKey];
    if (!entries || entries.length === 0) continue;
    const entry = entries[0];
    if (entry.extensionId === extensionId && entry.contributionId === contributionId) {
      if (matchedKey !== undefined) return undefined; // ambiguous
      matchedKey = scopedKey;
    }
  }

  return matchedKey;
}

/**
 * Narrow route-fit metadata mapper.
 *
 * Joins the caller-supplied identity fragment against the contribution index
 * and returns `RouteFitMetadata` only when `extensionId`, `kind`, and
 * `contributionId` are directly or uniquely resolvable from the index.
 *
 * When the index cannot attribute the identity to a single scoped
 * contribution key the mapper returns `undefined`, leaving the data
 * absent so downstream consumers treat it as unknown.
 *
 * Caller-supplied `fit`, `reason`, and `message` are preserved and passed
 * through; the mapper does not override them with index-derived values.
 */
export function resolveRouteFitMetadata(params: RouteFitMapperParams): RouteFitMetadata | undefined {
  const { contributionIndex, identity, route, fit, reason, message } = params;

  const scopedKey = resolveScopedKey(contributionIndex, identity);
  if (!scopedKey) return undefined;

  return {
    route,
    fit: fit ?? 'unknown',
    ...(reason !== undefined ? { reason } : {}),
    ...(message !== undefined ? { message } : {}),
  };
}

/**
 * Derive `RouteFitMetadata` from a planner blocker descriptor using the
 * contribution index for scoped-key resolution.
 *
 * The blocker already carries `extensionId` and `contributionId`; the
 * mapper resolves the missing `kind` from the index.  When the identity
 * cannot be uniquely attributed the function returns `undefined`.
 */
export function blockerToRouteFitMetadata(
  blocker: VideoEditorPlannerBlockerDescriptor,
  contributionIndex: ContributionIndex | undefined,
): RouteFitMetadata | undefined {
  return resolveRouteFitMetadata({
    contributionIndex,
    identity: {
      extensionId: blocker.extensionId,
      contributionId: blocker.contributionId,
    },
    route: blocker.route ?? 'sidecar-export',
    fit: 'blocked',
    reason: blocker.reason,
    message: blocker.message,
  });
}

/**
 * Derive `RouteFitMetadata` from a planner finding using the contribution
 * index for scoped-key resolution.
 *
 * Findings carry optional `extensionId` and `contributionId`; the mapper
 * resolves the missing `kind` from the index when possible.  Findings that
 * cannot be uniquely attributed yield `undefined`.
 */
export function findingToRouteFitMetadata(
  finding: CapabilityFinding,
  contributionIndex: ContributionIndex | undefined,
  fallbackRoute?: RenderRoute,
): RouteFitMetadata | undefined {
  return resolveRouteFitMetadata({
    contributionIndex,
    identity: {
      extensionId: finding.extensionId,
      contributionId: finding.contributionId,
    },
    route: finding.route ?? fallbackRoute ?? 'sidecar-export',
    fit: finding.severity === 'error' ? 'blocked' : 'degraded',
    reason: finding.reason,
    message: finding.message,
  });
}

// ---------------------------------------------------------------------------
// Contribution-index route-fit normalization
// ---------------------------------------------------------------------------

/**
 * Normalize route-fit metadata into the contribution index from descriptor
 * blockers.
 *
 * For each blocker whose identity (`extensionId`, `contributionId`) can be
 * directly or uniquely resolved to a scoped key in the index, the blocker's
 * route-fit metadata is attached to the first matching entry.  Blockers whose
 * identity is ambiguous (multiple entries share the same `extensionId` /
 * `contributionId` across different `kind` values) are silently skipped,
 * leaving the route-fit field absent.
 *
 * The returned index is deeply frozen.  Entries that already carry
 * `routeFit` metadata are left unchanged.
 *
 * @param contributionIndex - Host-owned contribution index (may be mutated
 *   by the caller before freezing).
 * @param descriptorBlockers - Flat list of blocker descriptors harvested
 *   from output-format and process descriptors.
 * @returns A new, frozen contribution index enriched with resolved
 *   route-fit metadata.
 */
export function normalizeContributionIndexRouteFit(
  contributionIndex: ContributionIndex,
  descriptorBlockers?: readonly VideoEditorPlannerBlockerDescriptor[],
): ContributionIndex {
  if (!descriptorBlockers || descriptorBlockers.length === 0) {
    return contributionIndex;
  }

  // Resolve scopedKey → RouteFitMetadata for each uniquely-attributable blocker.
  // First-wins policy when multiple blockers target the same scoped key.
  const routeFitByScopedKey = new Map<string, RouteFitMetadata>();
  for (const blocker of descriptorBlockers) {
    const scopedKey = resolveScopedKey(contributionIndex, {
      extensionId: blocker.extensionId,
      contributionId: blocker.contributionId,
    });
    if (!scopedKey || routeFitByScopedKey.has(scopedKey)) continue;

    const metadata = blockerToRouteFitMetadata(blocker, contributionIndex);
    if (metadata) {
      routeFitByScopedKey.set(scopedKey, metadata);
    }
  }

  if (routeFitByScopedKey.size === 0) {
    return contributionIndex;
  }

  // Enrich entries with resolved route-fit metadata.
  const enriched: Record<string, readonly ContributionIndexEntry[]> = {};
  for (const scopedKey of Object.keys(contributionIndex)) {
    const entries = contributionIndex[scopedKey];
    if (!entries || entries.length === 0) {
      enriched[scopedKey] = Object.freeze([]);
      continue;
    }

    const routeFit = routeFitByScopedKey.get(scopedKey);
    if (!routeFit) {
      enriched[scopedKey] = entries; // already frozen
      continue;
    }

    enriched[scopedKey] = Object.freeze(
      entries.map((entry) =>
        entry.routeFit
          ? entry // preserve existing routeFit
          : Object.freeze({ ...entry, routeFit }),
      ),
    );
  }

  return Object.freeze(enriched);
}
