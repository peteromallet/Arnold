import type { AssetMetadata, AssetRegistryEntry } from '../types/index.ts';
import type {
  VideoEditorMetadataFacetDescriptor,
  VideoEditorSearchProviderDescriptor,
  VideoEditorAssetDetailSectionDescriptor,
} from '../runtime/extensionSurface';
import type { MetadataFacetValueKind, ParserDiagnostic, SearchMatch, SearchProviderResult, SearchProviderHandler, SearchProviderContext } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Dot-path resolution
// ---------------------------------------------------------------------------

/**
 * Resolve a dot-separated path against an object tree.
 * Returns `undefined` when any segment is missing, not an object,
 * or out of bounds.
 *
 * Examples:
 *   resolveDotPath({ a: { b: 1 } }, 'a.b') → 1
 *   resolveDotPath({ a: { b: 1 } }, 'a.c') → undefined
 *   resolveDotPath({}, 'a.b') → undefined
 */
export function resolveDotPath(
  obj: Record<string, unknown> | undefined,
  path: string,
): unknown {
  if (!obj || typeof obj !== 'object') return undefined;

  const segments = path.split('.');
  let current: unknown = obj;

  for (let i = 0; i < segments.length; i++) {
    if (current === null || typeof current !== 'object') return undefined;
    current = (current as Record<string, unknown>)[segments[i]];
  }

  return current;
}

// ---------------------------------------------------------------------------
// Searchable metadata detection
// ---------------------------------------------------------------------------

/**
 * Host-owned metadata keys that are searchable.
 * Extension metadata under `extensions[extensionId]` is NOT included —
 * the host never searches extension-owned data directly.
 */
const SEARCHABLE_METADATA_KEYS = new Set([
  'integrity',
  'gps',
  'consent',
  'provenance',
  'enrichment',
]);

/**
 * Check whether an asset registry entry has any searchable host-owned metadata.
 *
 * Returns true when at least one of the host-owned metadata keys
 * (`integrity`, `gps`, `consent`, `provenance`, `enrichment`) is present
 * and non-empty in the entry's metadata.
 *
 * Extension-owned metadata under `extensions[extensionId]` is NOT considered
 * searchable by the host.
 */
export function hasSearchableMetadata(
  entry: AssetRegistryEntry | undefined,
): boolean {
  if (!entry?.metadata || typeof entry.metadata !== 'object') return false;

  const metadata = entry.metadata as Record<string, unknown>;

  for (const key of SEARCHABLE_METADATA_KEYS) {
    const value = metadata[key];
    if (value !== undefined && value !== null) {
      // For objects, check they are not empty
      if (typeof value === 'object') {
        if (Object.keys(value as Record<string, unknown>).length > 0) {
          return true;
        }
      } else {
        return true;
      }
    }
  }

  return false;
}

/**
 * Check whether any registry entry has searchable metadata.
 * Used to decide whether to show the metadata search input.
 */
export function anyAssetHasSearchableMetadata(
  registry: Record<string, AssetRegistryEntry> | undefined,
): boolean {
  if (!registry) return false;

  const keys = Object.keys(registry);
  for (let i = 0; i < keys.length; i++) {
    if (hasSearchableMetadata(registry[keys[i]])) {
      return true;
    }
  }

  return false;
}

/**
 * Check whether metadata search should be shown.
 * Returns true when any entry has searchable metadata OR when
 * search provider descriptors exist.
 */
export function shouldShowMetadataSearch(
  registry: Record<string, AssetRegistryEntry> | undefined,
  searchProviders: readonly VideoEditorSearchProviderDescriptor[] | undefined,
): boolean {
  if (searchProviders && searchProviders.length > 0) return true;
  return anyAssetHasSearchableMetadata(registry);
}

// ---------------------------------------------------------------------------
// Metadata text filtering
// ---------------------------------------------------------------------------

/**
 * Recursively collect all leaf string values from a host-owned metadata object.
 * Extension metadata under `extensions` is NOT traversed — the host
 * never searches extension-owned data directly.
 */
function collectMetadataStrings(
  obj: unknown,
  prefix: string,
  maxDepth: number,
): string[] {
  if (maxDepth <= 0) return [];
  if (typeof obj === 'string') return [obj];
  if (typeof obj === 'number') return [String(obj)];
  if (typeof obj === 'boolean') return [String(obj)];

  if (obj === null || typeof obj !== 'object') return [];

  const result: string[] = [];
  const record = obj as Record<string, unknown>;

  // Don't recurse into extensions — those are extension-owned
  const keys = Object.keys(record);
  for (let i = 0; i < keys.length; i++) {
    const key = keys[i];
    if (key === 'extensions') continue; // Skip extension-owned data
    const value = record[key];
    const childPath = prefix ? `${prefix}.${key}` : key;
    result.push(...collectMetadataStrings(value, childPath, maxDepth - 1));
  }

  return result;
}

/**
 * Test whether an asset's host-owned metadata matches a text filter.
 *
 * The search is case-insensitive and matches against all leaf string/number
 * values in host-owned metadata (`integrity`, `gps`, `consent`, `provenance`,
 * `enrichment`). Extension-owned metadata under `extensions[extensionId]`
 * is never searched.
 *
 * Returns the matching field paths (empty array = no match).
 */
export function matchMetadataText(
  entry: AssetRegistryEntry | undefined,
  searchText: string,
): string[] {
  if (!searchText || searchText.trim().length === 0) return [];
  if (!entry?.metadata || typeof entry.metadata !== 'object') return [];

  const hostMetadata: Record<string, unknown> = {};
  const rawMetadata = entry.metadata as Record<string, unknown>;

  for (const key of SEARCHABLE_METADATA_KEYS) {
    const value = rawMetadata[key];
    if (value !== undefined && value !== null) {
      hostMetadata[key] = value;
    }
  }

  if (Object.keys(hostMetadata).length === 0) return [];

  const lowerSearch = searchText.toLowerCase().trim();
  const strings = collectMetadataStrings(hostMetadata, '', 6);

  const matches: string[] = [];
  const seen = new Set<string>();

  for (let i = 0; i < strings.length; i++) {
    if (strings[i].toLowerCase().includes(lowerSearch)) {
      if (!seen.has(strings[i])) {
        seen.add(strings[i]);
        matches.push(strings[i]);
      }
    }
  }

  return matches;
}

/**
 * Filter registry entries by metadata text search.
 * Returns only entries whose host-owned metadata matches the search text.
 * When searchText is empty, returns all entries unchanged.
 */
export function filterByMetadataText(
  registry: Record<string, AssetRegistryEntry> | undefined,
  searchText: string,
): Record<string, AssetRegistryEntry> {
  if (!registry) return {};
  if (!searchText || searchText.trim().length === 0) return registry;

  const filtered: Record<string, AssetRegistryEntry> = {};
  const keys = Object.keys(registry);

  for (let i = 0; i < keys.length; i++) {
    const key = keys[i];
    const matches = matchMetadataText(registry[key], searchText);
    if (matches.length > 0) {
      filtered[key] = registry[key];
    }
  }

  return filtered;
}

// ---------------------------------------------------------------------------
// Metadata facets
// ---------------------------------------------------------------------------

/**
 * Resolve a metadata facet value from an asset registry entry.
 *
 * Uses the facet's `fieldPath` to look up the value in the entry's metadata.
 * Returns `undefined` when the path doesn't resolve or the value doesn't
 * match the expected value kind.
 */
export function resolveMetadataFacetValue(
  entry: AssetRegistryEntry | undefined,
  facet: VideoEditorMetadataFacetDescriptor,
): unknown {
  if (!entry?.metadata || typeof entry.metadata !== 'object') return undefined;

  const value = resolveDotPath(
    entry.metadata as Record<string, unknown>,
    facet.fieldPath,
  );

  if (value === undefined || value === null) return undefined;

  // Type-check against the declared value kind
  switch (facet.valueKind) {
    case 'string':
      return typeof value === 'string' ? value : undefined;
    case 'number':
      return typeof value === 'number' && Number.isFinite(value)
        ? value
        : undefined;
    case 'boolean':
      return typeof value === 'boolean' ? value : undefined;
    case 'enum':
      return typeof value === 'string' ? value : undefined;
    case 'timestamp':
      return typeof value === 'string' ? value : undefined;
    default:
      return value;
  }
}

/**
 * Extract all facet values for a registry entry.
 * Returns a map of facet descriptor ID → resolved value.
 */
export function getMetadataFacetValues(
  entry: AssetRegistryEntry | undefined,
  facets: readonly VideoEditorMetadataFacetDescriptor[] | undefined,
): ReadonlyMap<string, unknown> {
  const result = new Map<string, unknown>();

  if (!facets || facets.length === 0 || !entry) return result;

  for (let i = 0; i < facets.length; i++) {
    const facet = facets[i];
    const value = resolveMetadataFacetValue(entry, facet);
    if (value !== undefined) {
      result.set(facet.id, value);
    }
  }

  return result;
}

/**
 * Check whether any metadata facet has a value for this entry.
 */
export function hasMetadataFacetValues(
  entry: AssetRegistryEntry | undefined,
  facets: readonly VideoEditorMetadataFacetDescriptor[] | undefined,
): boolean {
  if (!facets || facets.length === 0 || !entry) return false;

  for (let i = 0; i < facets.length; i++) {
    const value = resolveMetadataFacetValue(entry, facets[i]);
    if (value !== undefined) return true;
  }

  return false;
}

// ---------------------------------------------------------------------------
// Source / provider badges
// ---------------------------------------------------------------------------

export interface SourceBadge {
  /** Machine-readable provider key (e.g. 'generation', 'upload', 'unknown'). */
  kind: 'generation' | 'upload' | 'external-url' | 'unknown';
  /** Human-readable label for the badge. */
  label: string;
  /** Optional detail text (e.g. generation ID or source URL hostname). */
  detail?: string;
}

/**
 * Derive a source/provider badge from an asset registry entry.
 *
 * Rules (in priority order):
 *   1. `origin === 'refreshable-from-generation'` → generation badge
 *   2. `generationId` is present → generation badge
 *   3. `origin === 'opaque-foreign'` or `origin === 'immutable-public'`
 *      with a `sourceUrl` → external-url badge
 *   4. `provenance.sourceProvider` is present → upload badge
 *   5. Otherwise → unknown badge
 */
export function getSourceBadge(
  entry: AssetRegistryEntry | undefined,
): SourceBadge {
  if (!entry) {
    return { kind: 'unknown', label: 'Unknown' };
  }

  // Generation origin
  if (
    entry.origin === 'refreshable-from-generation' ||
    entry.generationId
  ) {
    return {
      kind: 'generation',
      label: 'Generated',
      detail: entry.generationId ?? undefined,
    };
  }

  // External URL
  if (
    (entry.origin === 'opaque-foreign' || entry.origin === 'immutable-public') &&
    entry.metadata?.provenance?.sourceUrl
  ) {
    try {
      const hostname = new URL(entry.metadata.provenance.sourceUrl).hostname;
      return {
        kind: 'external-url',
        label: 'External',
        detail: hostname,
      };
    } catch {
      return {
        kind: 'external-url',
        label: 'External',
        detail: entry.metadata.provenance.sourceUrl,
      };
    }
  }

  // Upload with provenance provider
  if (entry.metadata?.provenance?.sourceProvider) {
    return {
      kind: 'upload',
      label: entry.metadata.provenance.sourceProvider,
    };
  }

  // Regular upload
  if (entry.origin === 'immutable-public') {
    return { kind: 'upload', label: 'Upload' };
  }

  return { kind: 'unknown', label: 'Unknown' };
}

// ---------------------------------------------------------------------------
// Enrichment status
// ---------------------------------------------------------------------------

export interface EnrichmentStatus {
  /** Number of pending enrichment tasks. */
  pending: number;
  /** Number of failed enrichment tasks. */
  failed: number;
  /** Total number of enrichment claims. */
  totalClaims: number;
  /** Whether any enrichment data exists. */
  hasEnrichment: boolean;
}

/**
 * Extract enrichment status from an asset registry entry.
 * Returns zeroed status when no enrichment metadata exists.
 */
export function getEnrichmentStatus(
  entry: AssetRegistryEntry | undefined,
): EnrichmentStatus {
  const enrichment = entry?.metadata?.enrichment;

  if (!enrichment) {
    return {
      pending: 0,
      failed: 0,
      totalClaims: 0,
      hasEnrichment: false,
    };
  }

  return {
    pending: enrichment.pending ?? 0,
    failed: enrichment.failed ?? 0,
    totalClaims: enrichment.claims?.length ?? 0,
    hasEnrichment: true,
  };
}

/**
 * Get enrichment claim details for display.
 * Each claim includes the parser ID, timestamp, and optional summary.
 */
export function getEnrichmentClaimDetails(
  entry: AssetRegistryEntry | undefined,
): readonly import('../types/index.ts').AssetMetadataEnrichmentClaim[] {
  return entry?.metadata?.enrichment?.claims ?? [];
}

// ---------------------------------------------------------------------------
// Provenance chain details
// ---------------------------------------------------------------------------

export interface ProvenanceChainDetail {
  /** Import timestamp (ISO string). */
  importTimestamp?: string;
  /** Source URL. */
  sourceUrl?: string;
  /** Source provider name. */
  sourceProvider?: string;
  /** User who imported the asset. */
  importedBy?: string;
  /** Original filename at import time. */
  originalFilename?: string;
  /** Integrity hash algorithm. */
  integrityAlgorithm?: string;
  /** Integrity hash value. */
  integrityHash?: string;
}

/**
 * Extract provenance-chain details for display.
 * Combines provenance metadata with integrity data.
 */
export function getProvenanceChainDetails(
  entry: AssetRegistryEntry | undefined,
): ProvenanceChainDetail | undefined {
  if (!entry?.metadata) return undefined;

  const provenance = entry.metadata.provenance;
  const integrity = entry.metadata.integrity;

  if (!provenance && !integrity) return undefined;

  const detail: ProvenanceChainDetail = {};

  if (provenance) {
    if (provenance.importTimestamp) detail.importTimestamp = provenance.importTimestamp;
    if (provenance.sourceUrl) detail.sourceUrl = provenance.sourceUrl;
    if (provenance.sourceProvider) detail.sourceProvider = provenance.sourceProvider;
    if (provenance.importedBy) detail.importedBy = provenance.importedBy;
    if (provenance.originalFilename) detail.originalFilename = provenance.originalFilename;
  }

  if (integrity) {
    if (integrity.sha256) {
      detail.integrityAlgorithm = 'sha256';
      detail.integrityHash = integrity.sha256;
    } else if (integrity.md5) {
      detail.integrityAlgorithm = 'md5';
      detail.integrityHash = integrity.md5;
    } else if (integrity.crc32) {
      detail.integrityAlgorithm = 'crc32';
      detail.integrityHash = integrity.crc32;
    }
  }

  // Return undefined if no fields were populated
  if (Object.keys(detail).length === 0) return undefined;

  return detail;
}

// ---------------------------------------------------------------------------
// Related materials
// ---------------------------------------------------------------------------

/**
 * Get material IDs related to this asset.
 *
 * Currently surfaces the `derivedFrom.assetId` relationship when present.
 * Future: may also surface material references from parser enrichment.
 */
export function getRelatedMaterialIds(
  entry: AssetRegistryEntry | undefined,
): string[] {
  if (!entry) return [];

  const ids: string[] = [];

  if (entry.derivedFrom?.assetId) {
    ids.push(entry.derivedFrom.assetId);
  }

  return ids;
}

/**
 * Check whether the asset has any related materials.
 */
export function hasRelatedMaterials(
  entry: AssetRegistryEntry | undefined,
): boolean {
  return getRelatedMaterialIds(entry).length > 0;
}

// ---------------------------------------------------------------------------
// Extension-declared asset detail sections
// ---------------------------------------------------------------------------

export interface ResolvedAssetDetailSection {
  id: string;
  extensionId: string;
  title: string;
  placement: 'before-default' | 'after-default';
  order?: number;
  /** Whether this section has data to display for the given entry. */
  hasData: boolean;
}

/**
 * Resolve extension-declared asset detail sections for a given entry.
 *
 * Sections are filtered by:
 *   1. Visibility predicate (`when`) — sections without matching data are hidden
 *   2. Field paths — sections that declare `fieldPaths` are only shown when
 *      at least one field resolves to a value
 *
 * Extension-declared sections are returned in deterministic order, separated
 * into before-default and after-default groups. The host owns section placement,
 * empty/error states, and bounding — extensions provide only descriptors.
 */
export function getVisibleExtensionDetailSections(
  entry: AssetRegistryEntry | undefined,
  sections: readonly VideoEditorAssetDetailSectionDescriptor[] | undefined,
): readonly ResolvedAssetDetailSection[] {
  if (!sections || sections.length === 0) return [];

  const resolved: ResolvedAssetDetailSection[] = [];

  for (let i = 0; i < sections.length; i++) {
    const section = sections[i];

    // Check field paths — if declared, at least one must resolve
    let hasData = true;
    if (section.fieldPaths && section.fieldPaths.length > 0) {
      hasData = false;
      if (entry?.metadata && typeof entry.metadata === 'object') {
        const metadata = entry.metadata as Record<string, unknown>;
        for (let j = 0; j < section.fieldPaths.length; j++) {
          const value = resolveDotPath(metadata, section.fieldPaths[j]);
          if (value !== undefined && value !== null) {
            hasData = true;
            break;
          }
        }
      }
    }

    resolved.push({
      id: section.id,
      extensionId: section.extensionId,
      title: section.title,
      placement: section.placement,
      order: section.order,
      hasData,
    });
  }

  // Sort: placement first (before-default before after-default),
  // then order ascending, then ID alphabetical
  return resolved.sort((a, b) => {
    if (a.placement !== b.placement) {
      return a.placement === 'before-default' ? -1 : 1;
    }
    const orderA = a.order ?? 0;
    const orderB = b.order ?? 0;
    if (orderA !== orderB) return orderA - orderB;
    return a.id.localeCompare(b.id);
  });
}

// ---------------------------------------------------------------------------
// Metadata field presence check
// ---------------------------------------------------------------------------

/**
 * Check whether a specific metadata field path exists in an entry.
 * Useful for conditional rendering decisions.
 */
export function isMetadataFieldPresent(
  entry: AssetRegistryEntry | undefined,
  fieldPath: string,
): boolean {
  if (!entry?.metadata || typeof entry.metadata !== 'object') return false;

  const value = resolveDotPath(
    entry.metadata as Record<string, unknown>,
    fieldPath,
  );

  return value !== undefined && value !== null;
}

// ---------------------------------------------------------------------------
// M6: Search provider result integration
// ---------------------------------------------------------------------------

// Re-export SDK types used by consumers
export type { SearchMatch, SearchProviderResult };

// ---------------------------------------------------------------------------
// Search provider result envelope
// ---------------------------------------------------------------------------

/**
 * A search provider result paired with its source metadata.
 * The host collects these from all registered providers before merging.
 */
export interface SearchProviderResultEnvelope {
  /** The search provider contribution ID. */
  providerId: string;
  /** Human-readable label for the search provider. */
  providerLabel: string;
  /** Sort order (lower = higher priority for tiebreaking). */
  providerOrder: number;
  /** The raw result from the provider handler. */
  result: SearchProviderResult;
}

// ---------------------------------------------------------------------------
// Merged search result types
// ---------------------------------------------------------------------------

/**
 * A single merged search result combining built-in metadata filtering
 * with search provider results.
 */
export interface MergedSearchResult {
  /** Asset or material reference key. */
  ref: string;
  /** Kind of the referenced item. */
  kind: 'asset' | 'material';
  /**
   * Relevance score (0–1). Higher = more relevant.
   * Metadata-text-filtered results are assigned score 1.0.
   */
  score: number;
  /** Short excerpt or description for display. */
  excerpt?: string;
  /** ID of the source (provider contribution ID, or '__host__' for built-in). */
  sourceProviderId: string;
  /** Human-readable label for the source. */
  sourceProviderLabel: string;
  /** Whether this match came from built-in filtering or a search provider. */
  matchSource: 'metadata-filter' | 'search-provider';
}

/**
 * The result of merging search provider results with built-in
 * metadata text filtering.
 */
export interface MergedSearchResults {
  /** Stable-ordered merged matches (bounded to maxResults). */
  readonly matches: readonly MergedSearchResult[];
  /** Diagnostics collected from all providers. */
  readonly diagnostics: readonly ParserDiagnostic[];
  /** Total number of raw matches across all providers (before merge). */
  readonly totalProviderResults: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Default maximum results returned by merge. */
const DEFAULT_MAX_SEARCH_RESULTS = 50;

/** Source ID for built-in metadata text filter matches. */
const METADATA_FILTER_SOURCE_ID = '__host__';

/** Source label for built-in metadata text filter matches. */
const METADATA_FILTER_SOURCE_LABEL = 'Metadata';

// ---------------------------------------------------------------------------
// Merge logic
// ---------------------------------------------------------------------------

/**
 * Merge search provider results with built-in metadata text filtering.
 *
 * Merging rules:
 *   1. Built-in metadata text matches are scored at 1.0 (highest) and
 *      assigned source `__host__` / "Metadata".
 *   2. Provider matches are deduplicated by (kind, ref) — the highest
 *      score wins; ties go to the provider with lower `providerOrder`.
 *   3. Provider matches for asset refs not present in `registry` are
 *      dropped (host validates asset existence).
 *   4. Results are sorted by score descending, then matchSource
 *      (metadata-filter before search-provider), then ref alphabetically
 *      for deterministic stability.
 *   5. Results are bounded to `maxResults` (default 50).
 *   6. Provider diagnostics are collected and returned alongside matches.
 *
 * No embeddings, inference, or vector database are added — the host
 * only merges and orders opaque provider results.
 */
export function mergeSearchProviderResults(
  registry: Record<string, AssetRegistryEntry> | undefined,
  searchText: string,
  providerResults: readonly SearchProviderResultEnvelope[],
  options?: {
    /** Maximum number of merged results (default 50). */
    maxResults?: number;
    /** Minimum score threshold (default 0, i.e. no filtering). */
    minScore?: number;
  },
): MergedSearchResults {
  const maxResults = options?.maxResults ?? DEFAULT_MAX_SEARCH_RESULTS;
  const minScore = options?.minScore ?? 0;
  const diagnostics: ParserDiagnostic[] = [];
  const matchMap = new Map<string, MergedSearchResult>();
  let totalProviderResults = 0;

  // ---- 1. Built-in metadata text matches (score 1.0) -----------------------
  if (registry && searchText && searchText.trim().length > 0) {
    const filtered = filterByMetadataText(registry, searchText);
    const keys = Object.keys(filtered);
    for (let i = 0; i < keys.length; i++) {
      const key = keys[i];
      const matchKey = `asset:${key}`;
      matchMap.set(matchKey, {
        ref: key,
        kind: 'asset',
        score: 1.0,
        sourceProviderId: METADATA_FILTER_SOURCE_ID,
        sourceProviderLabel: METADATA_FILTER_SOURCE_LABEL,
        matchSource: 'metadata-filter',
      });
    }
  }

  // ---- 2. Search provider results ------------------------------------------
  // Sort providers by providerOrder for deterministic tiebreaking
  const sortedProviders = [...providerResults].sort(
    (a, b) => (a.providerOrder ?? 0) - (b.providerOrder ?? 0),
  );

  for (let pi = 0; pi < sortedProviders.length; pi++) {
    const envelope = sortedProviders[pi];
    const { providerId, providerLabel, result } = envelope;
    totalProviderResults += result.matches.length;

    // Collect diagnostics
    if (result.diagnostics) {
      for (let di = 0; di < result.diagnostics.length; di++) {
        diagnostics.push(result.diagnostics[di]);
      }
    }

    // Process matches
    for (let mi = 0; mi < result.matches.length; mi++) {
      const match = result.matches[mi];

      // Score threshold
      if (match.score < minScore) continue;

      // Validate: asset refs must exist in registry (if registry provided)
      if (match.kind === 'asset' && registry && !(match.ref in registry)) {
        continue;
      }

      const matchKey = `${match.kind}:${match.ref}`;
      const existing = matchMap.get(matchKey);

      // Keep the match with higher score; ties keep the earlier provider
      // (already handled by sorted provider order — first-wins)
      if (!existing || match.score > existing.score) {
        matchMap.set(matchKey, {
          ref: match.ref,
          kind: match.kind,
          score: match.score,
          excerpt: match.excerpt,
          sourceProviderId: providerId,
          sourceProviderLabel: providerLabel,
          matchSource: 'search-provider',
        });
      }
    }
  }

  // ---- 3. Stable sort ------------------------------------------------------
  // Score descending, then matchSource (metadata-filter first), then ref
  const sorted = Array.from(matchMap.values()).sort((a, b) => {
    // Score descending
    if (a.score !== b.score) return b.score - a.score;
    // metadata-filter before search-provider
    if (a.matchSource !== b.matchSource) {
      return a.matchSource === 'metadata-filter' ? -1 : 1;
    }
    // Alphabetical by ref for deterministic stability
    return a.ref.localeCompare(b.ref);
  });

  // ---- 4. Bound ------------------------------------------------------------
  const bounded = sorted.slice(0, maxResults);

  return {
    matches: bounded,
    diagnostics,
    totalProviderResults,
  };
}

/**
 * Execute multiple search provider handlers concurrently and merge
 * their results with built-in metadata text filtering.
 *
 * Each handler is called with the query and a {@link SearchProviderContext}.
 * Handler errors are caught and surfaced as diagnostics — a failing
 * provider never blocks other providers or the host.
 *
 * This is a convenience wrapper around {@link mergeSearchProviderResults}
 * for callers that have direct access to handler functions.
 */
export async function executeSearchProviders(
  registry: Record<string, AssetRegistryEntry> | undefined,
  searchText: string,
  providers: ReadonlyArray<{
    descriptor: VideoEditorSearchProviderDescriptor;
    handler: SearchProviderHandler;
  }>,
  options?: {
    maxResults?: number;
    minScore?: number;
  },
): Promise<MergedSearchResults> {
  if (!searchText || searchText.trim().length === 0) {
    return {
      matches: [],
      diagnostics: [],
      totalProviderResults: 0,
    };
  }

  const maxResults = options?.maxResults ?? DEFAULT_MAX_SEARCH_RESULTS;

  // Execute all handlers concurrently
  const promises = providers.map(
    async ({
      descriptor,
      handler,
    }): Promise<SearchProviderResultEnvelope> => {
      try {
        const result = await handler(searchText, {
          extensionId: descriptor.extensionId,
          contributionId: descriptor.id,
          maxResults,
        });
        return {
          providerId: descriptor.id,
          providerLabel: descriptor.label,
          providerOrder: descriptor.order ?? 0,
          result,
        };
      } catch (error: unknown) {
        // Surface handler errors as diagnostics
        const message =
          error instanceof Error ? error.message : String(error);
        return {
          providerId: descriptor.id,
          providerLabel: descriptor.label,
          providerOrder: descriptor.order ?? 0,
          result: {
            matches: [],
            diagnostics: [
              {
                severity: 'error',
                code: 'search-provider/exception' as `parser/${string}`,
                message: `Search provider "${descriptor.label}" failed: ${message}`,
              },
            ],
          },
        };
      }
    },
  );

  const providerResults = await Promise.all(promises);
  return mergeSearchProviderResults(registry, searchText, providerResults, {
    maxResults,
    minScore: options?.minScore,
  });
}

/**
 * Extract asset keys from merged search results.
 *
 * Returns a Set of asset refs that matched either built-in metadata
 * filtering or any search provider. Material results are excluded —
 * these are surfaced separately.
 *
 * Useful for determining which assets should be visible in the
 * asset panel when search is active.
 */
export function getSearchProviderMatchedAssetKeys(
  merged: MergedSearchResults,
): Set<string> {
  const keys = new Set<string>();
  const matches = merged.matches;
  for (let i = 0; i < matches.length; i++) {
    const match = matches[i];
    if (match.kind === 'asset') {
      keys.add(match.ref);
    }
  }
  return keys;
}

/**
 * Collect all unique source provider labels from merged search results,
 * excluding the built-in metadata filter source.
 *
 * Useful for displaying "Results from: Provider A, Provider B" in the UI.
 */
export function getSearchProviderSourceLabels(
  merged: MergedSearchResults,
): readonly string[] {
  const labels = new Set<string>();
  const matches = merged.matches;
  for (let i = 0; i < matches.length; i++) {
    const match = matches[i];
    if (match.matchSource === 'search-provider' && match.sourceProviderLabel) {
      labels.add(match.sourceProviderLabel);
    }
  }
  return Array.from(labels).sort();
}

