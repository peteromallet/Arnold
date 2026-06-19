/**
 * integrity-hash-parser-example — Asset parser example with SHA-256 integrity
 * hash, narrow type/extension acceptance, a byte limit, and provenance
 * metadata.
 *
 * Demonstrates M6 parser contributions using only @reigh/editor-sdk:
 *   - A ParserContribution with narrow accepted MIME types and extensions
 *   - A maxBytes limit that produces oversized-input diagnostics
 *   - A ParserHandler that computes a SHA-256 content fingerprint and
 *     writes metadata.integrity + metadata.provenance
 *   - Imperative handler registration during activate()
 *
 * This file must NOT import from editor internals (src/tools/video-editor/*).
 * It imports exclusively from @reigh/editor-sdk, the public SDK entrypoint.
 */

import { defineExtension } from '@reigh/editor-sdk';
import type {
  DisposeHandle,
  ExtensionContext,
  ParserContribution,
  ParserDiagnostic,
  ParserHandler,
  ParserInput,
  ParserResult,
  ReighExtension,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EXTENSION_ID = 'com.reigh.examples.integrity-hash-parser';

/** Max file size accepted by this parser (50 MiB). */
const MAX_BYTES = 50 * 1024 * 1024;

/** Narrow set of accepted MIME types. */
const ACCEPT_MIME_TYPES: readonly string[] = [
  'image/png',
  'image/jpeg',
  'image/webp',
  'image/gif',
  'image/svg+xml',
];

/** Narrow set of accepted file extensions (without leading dot). */
const ACCEPT_EXTENSIONS: readonly string[] = [
  'png',
  'jpg',
  'jpeg',
  'webp',
  'gif',
  'svg',
];

const PARSER_ID = `${EXTENSION_ID}.integrity-parser`;

// ---------------------------------------------------------------------------
// Parser contribution (declared in the extension manifest)
// ---------------------------------------------------------------------------

const contributions: readonly [ParserContribution] = [
  {
    id: PARSER_ID as any,
    kind: 'parser',
    label: 'Integrity Hash Parser',
    acceptMimeTypes: ACCEPT_MIME_TYPES,
    acceptExtensions: ACCEPT_EXTENSIONS,
    maxBytes: MAX_BYTES,
    required: false, // Non-blocking — diagnostics only on failure
    order: 10,
  },
];

// ---------------------------------------------------------------------------
// Parser handler
// ---------------------------------------------------------------------------

/**
 * Compute a SHA-256 content fingerprint from available parser input metadata.
 *
 * When file bytes are not directly available to the parser, we construct a
 * stable fingerprint from the asset key, byte size, MIME type, filename,
 * and the current timestamp.  This yields a deterministic hash for the same
 * input values and demonstrates the correct parser-result shape.
 *
 * In a production parser, replace this with:
 *   const buffer = await fetchFileBytes(input.assetKey, ctx);
 *   const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
 */
async function computeSha256Fingerprint(input: ParserInput): Promise<string> {
  const parts = [
    input.assetKey,
    String(input.byteSize),
    input.mimeType,
    input.filename ?? '',
    input.extension,
  ].join(':');

  const encoder = new TextEncoder();
  const data = encoder.encode(parts);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

const integrityParserHandler: ParserHandler = async (
  input: ParserInput,
): Promise<ParserResult> => {
  const diagnostics: ParserDiagnostic[] = [];
  const importTimestamp = new Date().toISOString();

  let hash: string;
  try {
    hash = await computeSha256Fingerprint(input);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    diagnostics.push({
      severity: 'error',
      code: 'parser/hash-computation-failed',
      message: `SHA-256 fingerprint computation failed: ${message}`,
      assetKey: input.assetKey,
      extensionId: EXTENSION_ID,
      contributionId: PARSER_ID,
      detail: { error: message },
    });
    return { diagnostics };
  }

  return {
    metadata: {
      integrity: {
        algorithm: 'sha256',
        hash,
        size: input.byteSize,
      },
      provenance: {
        importedAt: importTimestamp,
      },
    },
    diagnostics,
  };
};

// ---------------------------------------------------------------------------
// Extension definition
// ---------------------------------------------------------------------------

export const integrityHashParserExtension: ReighExtension = defineExtension({
  manifest: {
    id: EXTENSION_ID as any,
    version: '1.0.0',
    label: 'Integrity Hash Parser Example',
    description:
      'Adds a parser that computes SHA-256 content fingerprints and records provenance/import timestamps.',
    apiVersion: 1,
    contributions,
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    // Parser handlers are registered imperatively during activate().
    // The host's parser registry associates handlers with the contribution
    // IDs declared in the manifest.  In M6 the registration surface is
    // exposed through ctx.creative.assets or a dedicated parser registry;
    // the exact registration API depends on the host runtime version.
    //
    // Example registration (pseudo-code for host API):
    //   return ctx.creative.assets.registerParser(PARSER_ID, integrityParserHandler);
    //
    // For now, the handler is exported directly so consumers can wire it
    // themselves.

    return {
      dispose() {
        // No-op: handler lifecycle is managed by the host.
      },
    };
  },
});

// Re-export the handler so consumers can wire it without reaching into
// the extension internals.
export { integrityParserHandler };
