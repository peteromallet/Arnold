/**
 * Asset parser — runtime/read parser contracts.
 *
 * Exports the runtime types that parser handlers consume and return:
 * {@link ParserInput}, {@link ParserResult},
 * {@link ParserDiagnostic}, and {@link ParserHandler}.
 *
 * These are runtime handler contracts, not manifest contribution declarations.
 * Manifest declarations live in src/sdk/video/families/parsers.ts.
 *
 * @publicContract
 */

import type { DiagnosticSeverity } from '../../diagnostics';
import type { AssetMetadata, DeferredEnrichmentRecord } from './metadata';

// ---------------------------------------------------------------------------
// M6: Parser runtime types
// ---------------------------------------------------------------------------

/**
 * Input passed to a parser handler during asset ingestion.
 *
 * Parsers receive metadata about the ingested file but not the raw
 * file bytes — the host validates size/type before invoking the parser
 * and the parser receives only the fields it declares interest in.
 */
export interface ParserInput {
  /** Asset key in the registry. */
  assetKey: string;
  /** Detected MIME type of the uploaded file. */
  mimeType: string;
  /** File extension (without leading dot). */
  extension: string;
  /** File size in bytes. */
  byteSize: number;
  /** Original filename from the upload. */
  filename?: string;
  /**
   * Any metadata already collected for this asset before this parser runs.
   * Parsers may read existing metadata to avoid recomputing values.
   */
  existingMetadata?: Readonly<AssetMetadata>;
}

/**
 * Result returned by a parser handler.
 *
 * Parsers return only the metadata they wish to contribute.
 * The host shallow-merges blessed registry fields and deep-merges
 * metadata by namespace.  Unknown top-level fields are rejected with
 * a diagnostic.
 */
export interface ParserResult {
  /**
   * Metadata to merge into the asset's metadata.
   * Extension-owned fields should be placed under `extensions[extensionId]`.
   */
  metadata?: Partial<AssetMetadata>;
  /** Diagnostics produced by the parser. */
  diagnostics?: readonly ParserDiagnostic[];
  /**
   * Deferred enrichment records the parser wishes to enqueue.
   * These are persisted alongside the asset and surface in the asset
   * detail panel; execution is deferred to M10/M12.
   */
  enrichment?: readonly DeferredEnrichmentRecord[];
}

/**
 * A diagnostic produced by a parser during asset ingestion.
 *
 * Parser diagnostics use `parser/`-prefixed codes and carry
 * enough context to identify the asset and the parser that produced
 * the diagnostic.
 */
export interface ParserDiagnostic {
  severity: DiagnosticSeverity;
  /** Stable diagnostic code, e.g. 'parser/unsupported-mime-type'. */
  code: `parser/${string}`;
  message: string;
  /** The asset key that triggered the diagnostic. */
  assetKey?: string;
  /** The extension that owns the parser. */
  extensionId?: string;
  /** The parser contribution ID. */
  contributionId?: string;
  /** Structured detail (expected MIME, actual MIME, size limit, etc.). */
  detail?: Record<string, unknown>;
}

/**
 * A parser handler function registered by an extension.
 *
 * Receives a {@link ParserInput} and returns a {@link ParserResult}
 * or a Promise of one.  Thrown errors are caught by the host and
 * published as parser diagnostics.
 */
export type ParserHandler = (
  input: ParserInput,
) => ParserResult | Promise<ParserResult>;
