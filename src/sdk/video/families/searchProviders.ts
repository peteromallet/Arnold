/**
 * Search provider family contracts — manifest contribution declarations.
 *
 * Exports the {@link SearchProviderContribution} interface that extensions
 * declare in their manifest to supply asset/material search results to the
 * host search surface.
 *
 * Runtime search types (SearchMatch, SearchProviderResult,
 * SearchProviderHandler, SearchProviderContext) live in
 * src/sdk/video/assets/search.ts.
 *
 * @publicContract
 */

import type { ContributionId } from '../../ids';

/**
 * M6: A search provider contribution declared in an extension manifest.
 *
 * Search providers supply asset/material search results to the host search
 * surface.  The provider owns indexing, model choice, and refresh; the host
 * owns query dispatch, result merge, and source labeling.
 *
 * Search providers are bounded to host query/result integration — no local
 * model loading, inference, vector database, or ranking ownership is added
 * in M6.
 */
export interface SearchProviderContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'searchProvider';
  /** Human-readable label shown in the search surface. */
  label: string;
  /**
   * Optional description of the search provider capabilities
   * (e.g. 'semantic search over image embeddings').
   */
  description?: string;
  /**
   * Kinds of results this provider can surface.
   * Defaults to ['asset'] when omitted.
   */
  resultKinds?: readonly ('asset' | 'material')[];
  /** Lower values sort first. Default 0. */
  order?: number;
}
