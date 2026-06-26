/**
 * Asset search — runtime/read search contracts.
 *
 * Exports the runtime types that search provider handlers consume and return:
 * {@link SearchMatch}, {@link SearchProviderResult},
 * {@link SearchProviderHandler}, and {@link SearchProviderContext}.
 *
 * These are runtime handler contracts, not manifest contribution declarations.
 * Manifest declarations live in src/sdk/video/families/searchProviders.ts.
 *
 * @publicContract
 */

import type { ParserDiagnostic } from './parsers';

// ---------------------------------------------------------------------------
// M6: Search provider runtime types
// ---------------------------------------------------------------------------

/**
 * A single search result match from a search provider.
 */
export interface SearchMatch {
  /** Asset or material reference key. */
  ref: string;
  /** Kind of the referenced item. */
  kind: 'asset' | 'material';
  /**
   * Relevance score (0–1). Higher = more relevant.
   * Relative ordering is provider-owned; host may normalize.
   */
  score: number;
  /** Short excerpt or description for display in search results. */
  excerpt?: string;
  /** Opaque provider metadata (embedding distance, model version, etc.). */
  meta?: Record<string, unknown>;
}

/**
 * Result returned by a search provider for a host query.
 */
export interface SearchProviderResult {
  /** Ordered list of matches (highest score first). */
  matches: readonly SearchMatch[];
  /** Total number of results available beyond the returned matches. */
  totalCount?: number;
  /** Whether the provider has more results available. */
  hasMore?: boolean;
  /** Provider-owned diagnostics (indexing errors, etc.). */
  diagnostics?: readonly ParserDiagnostic[];
}

/**
 * A search provider handler registered by an extension.
 *
 * Receives a query string and returns scored asset/material refs.
 * Providers own indexing, model choice, and refresh; the host
 * owns query dispatch, result merge, and source labeling.
 */
export type SearchProviderHandler = (
  query: string,
  context: SearchProviderContext,
) => SearchProviderResult | Promise<SearchProviderResult>;

/**
 * Context passed to a search provider handler.
 */
export interface SearchProviderContext {
  /** The extension that registered the handler. */
  readonly extensionId: string;
  /** The search provider contribution ID. */
  readonly contributionId: string;
  /** Maximum number of results the host will display. */
  readonly maxResults: number;
  /** Optional filter scoping the search to asset/material kind. */
  readonly resultKind?: 'asset' | 'material';
}
