/**
 * Output format runtime contracts — portable public contracts.
 *
 * Contains compile-only output format handler, context, result, and
 * ExportService contracts consumed by extension code at runtime.
 * These were extracted from src/sdk/video/assets/metadata.ts in M2b
 * to separate the export-service runtime surface from asset metadata
 * descriptor/value contracts.
 *
 * All contracts are data-only types and read-only surfaces; no
 * registry, provider, resolver, upload, or storage behaviour lives here.
 *
 * @publicContract
 */

import type { TimelineSnapshot } from '../timeline/reader';
import type { DisposeHandle } from '../../dispose';
import type { ParserDiagnostic } from '../assets/parsers';
import type { AssetMetadata } from '../assets/metadata';

// ---------------------------------------------------------------------------
// Compile-only output format result and handler
// ---------------------------------------------------------------------------

/**
 * The result of executing a compile-only output format.
 *
 * Compile-only formats (requiresRender: false) produce an artifact
 * without entering the render pipeline.  The output is a byte buffer
 * plus metadata describing the artifact.
 */
export interface CompileOnlyOutputResult {
  /** The output artifact bytes. */
  data: Uint8Array;
  /** MIME type of the output artifact. */
  mimeType: string;
  /** Suggested filename for the output artifact. */
  filename: string;
  /**
   * Diagnostics produced during compilation.
   * Non-error diagnostics do not prevent artifact production.
   */
  diagnostics?: readonly ParserDiagnostic[];
  /** Whether the compilation produced blocking errors. */
  hasBlockingErrors: boolean;
}

/**
 * A compile-only output format handler registered by an extension.
 *
 * Receives read-only access to timeline and asset data and produces
 * a deterministic artifact.  Must not mutate timeline state.
 */
export type OutputFormatHandler = (
  context: OutputFormatContext,
) => CompileOnlyOutputResult | Promise<CompileOnlyOutputResult>;

/**
 * Context passed to an output format handler.
 *
 * Provides read-only access to timeline snapshot and asset metadata
 * without exposing mutation surfaces.
 */
export interface OutputFormatContext {
  /** Read-only snapshot of the current timeline state. */
  readonly timeline: TimelineSnapshot;
  /** Read-only map of asset key to asset metadata. */
  readonly assets: ReadonlyMap<string, Readonly<AssetMetadata>>;
  /** The extension that registered the handler. */
  readonly extensionId: string;
  /** The output format contribution ID. */
  readonly contributionId: string;
}

// ---------------------------------------------------------------------------
// Export service
// ---------------------------------------------------------------------------

/**
 * Export service available to extensions for registering output format
 * handlers imperatively during activate().
 *
 * Output formats must have a matching `OutputFormatContribution` in the
 * extension manifest.  Handlers are registered via `registerOutputFormat()`
 * and the returned DisposeHandle unregisters them on dispose.
 */
export interface ExportService {
  /**
   * Register a compile-only output format handler.
   *
   * The `formatId` must match the `id` of an `OutputFormatContribution`
   * declared by this extension in its manifest with `requiresRender: false`.
   *
   * Returns a DisposeHandle that unregisters the handler when dispose()
   * is called (safe to call multiple times; idempotent).
   */
  registerOutputFormat(
    formatId: string,
    handler: OutputFormatHandler,
    options?: OutputFormatRegistrationOptions,
  ): DisposeHandle;
}

/** Options for imperative output format registration. */
export interface OutputFormatRegistrationOptions {
  /** Override label for the export UI. */
  label?: string;
  /** Override description for the export UI. */
  description?: string;
}
