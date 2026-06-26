/**
 * Parser family contracts — manifest contribution declarations.
 *
 * Exports the {@link ParserContribution} interface that extensions
 * declare in their manifest to supply asset metadata parsers for
 * the ingestion pipeline.
 *
 * Runtime parser types (ParserInput, ParserResult, ParserDiagnostic,
 * ParserHandler) live in src/sdk/video/assets/parsers.ts.
 *
 * @publicContract
 */

import type { ContributionId } from '../../ids';

/**
 * M6: A parser contribution declared in an extension manifest.
 *
 * Parsers enrich asset metadata during ingestion.  The contribution declares
 * accepted MIME types, file extensions, max size, and whether the parser is
 * required (blocking) or optional.
 *
 * Actual parser behaviour is registered imperatively during activate() via
 * the host's parser registry (ctx.creative.assets if active, or a
 * dedicated parser registration surface).
 */
export interface ParserContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'parser';
  /** Human-readable label for diagnostics / UI. */
  label: string;
  /**
   * Accepted MIME types.  At least one of `acceptMimeTypes` or
   * `acceptExtensions` must be non-empty.
   */
  acceptMimeTypes?: readonly string[];
  /**
   * Accepted file extensions (without leading dot).  E.g. `['jpg','jpeg']`.
   */
  acceptExtensions?: readonly string[];
  /**
   * Maximum file size in bytes this parser will accept.
   * Files exceeding this size produce a diagnostic and are not passed
   * to the parser handler.
   */
  maxBytes?: number;
  /**
   * When true, parser failure blocks asset ingestion with a clear
   * diagnostic.  When false (default), the failure is diagnostic-only
   * and the asset is still ingested with whatever metadata was already
   * available.
   */
  required?: boolean;
  /** Lower values sort first. Default 0. */
  order?: number;
}
