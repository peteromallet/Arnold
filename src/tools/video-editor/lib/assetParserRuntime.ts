import type {
  AssetMetadata,
  AssetMetadataEnrichment,
  AssetMetadataEnrichmentClaim,
  AssetRegistryEntry,
} from '../types/index.ts';
import type {
  ParserHandler,
  ParserInput,
  ParserResult,
  ParserDiagnostic,
} from '@reigh/editor-sdk';
import type { VideoEditorAssetParserDescriptor } from '../runtime/extensionSurface';
import { validateAssetMetadata } from './assetMetadata';

// ---------------------------------------------------------------------------
// Parser diagnostic codes
// ---------------------------------------------------------------------------

/** All parser diagnostic codes emitted by the host runtime. */
export const PARSER_DIAGNOSTIC_CODES = {
  /** The file's MIME type or extension does not match any parser's accept list. */
  UNSUPPORTED_TYPE: 'parser/unsupported-type' as const,
  /** The file exceeds the parser's maxBytes limit. */
  OVERSIZED_INPUT: 'parser/oversized-input' as const,
  /** The parser threw an exception during execution. */
  PARSER_EXCEPTION: 'parser/exception' as const,
  /** A required parser failed (exception or blocking diagnostic). */
  REQUIRED_PARSER_FAILURE: 'parser/required-parser-failure' as const,
  /** The parser returned unknown top-level registry fields that were rejected. */
  REJECTED_OUTPUT_FIELDS: 'parser/rejected-output-fields' as const,
} as const;

export type ParserDiagnosticCode =
  (typeof PARSER_DIAGNOSTIC_CODES)[keyof typeof PARSER_DIAGNOSTIC_CODES];

// ---------------------------------------------------------------------------
// Preflight types
// ---------------------------------------------------------------------------

/** Input for parser preflight — metadata about the file being ingested. */
export interface AssetParserPreflightInput {
  /** Detected MIME type. */
  mimeType: string;
  /** File extension without leading dot (lowercase). */
  extension: string;
  /** File size in bytes. */
  byteSize: number;
  /** Original filename (optional). */
  filename?: string;
}

// ---------------------------------------------------------------------------
// Registered parser (descriptor + handler wired during activate)
// ---------------------------------------------------------------------------

/** A parser that has a handler registered and is ready to execute. */
export interface RegisteredParser {
  /** Descriptor produced by runtime normalization. */
  descriptor: VideoEditorAssetParserDescriptor;
  /** The handler function registered by the extension during activate(). */
  handler: ParserHandler;
}

// ---------------------------------------------------------------------------
// Preflight: check if a file matches a parser's acceptance criteria
// ---------------------------------------------------------------------------

const normalizeExtension = (ext: string): string =>
  ext.toLowerCase().replace(/^\./, '');

const normalizeMimeType = (mime: string): string =>
  mime.toLowerCase().trim();

/**
 * Check whether `candidate` matches `accepted`.
 * Supports exact match and wildcard subtypes (`image/*`).
 */
const mimeTypeMatches = (candidate: string, accepted: string): boolean => {
  if (accepted === '*/*') return true;
  if (!accepted.includes('/')) return false;
  const [acceptedType, acceptedSubtype] = accepted.split('/');
  const [candidateType, candidateSubtype] = candidate.split('/');
  if (acceptedType !== candidateType) return false;
  if (acceptedSubtype === '*') return true;
  return acceptedSubtype === candidateSubtype;
};

/**
 * Run preflight for a single parser descriptor against the candidate file.
 *
 * Returns `null` if the parser accepts the file (passes preflight).
 * Returns a `ParserDiagnostic` if the file is rejected by this parser.
 *
 * Preflight is evaluated in this order:
 *   1. Size check against `maxBytes`.
 *   2. MIME type check against `acceptMimeTypes`.
 *   3. Extension check against `acceptExtensions`.
 *
 * A parser with no accept lists accepts ALL files (subject to size check).
 *
 * Each parser is independently preflighted — one parser's rejection
 * does not affect another parser's eligibility.
 */
export function runParserPreflight(
  parser: VideoEditorAssetParserDescriptor,
  input: AssetParserPreflightInput,
): ParserDiagnostic | null {
  // -- Size check -----------------------------------------------------------
  if (
    parser.maxBytes !== undefined &&
    parser.maxBytes > 0 &&
    input.byteSize > parser.maxBytes
  ) {
    return {
      severity: 'error',
      code: PARSER_DIAGNOSTIC_CODES.OVERSIZED_INPUT,
      message:
        `File size (${input.byteSize} bytes) exceeds parser ` +
        `"${parser.label}" maximum (${parser.maxBytes} bytes).`,
      extensionId: parser.extensionId,
      contributionId: parser.id,
      detail: {
        byteSize: input.byteSize,
        maxBytes: parser.maxBytes,
        parserId: parser.id,
      },
    };
  }

  const hasMimeTypes =
    parser.acceptMimeTypes !== undefined &&
    parser.acceptMimeTypes.length > 0;
  const hasExtensions =
    parser.acceptExtensions !== undefined &&
    parser.acceptExtensions.length > 0;

  // If no accept filters are declared, accept everything.
  if (!hasMimeTypes && !hasExtensions) {
    return null;
  }

  const normalizedInputMime = normalizeMimeType(input.mimeType);
  const normalizedInputExt = normalizeExtension(input.extension);

  // -- MIME check -----------------------------------------------------------
  let mimePassed = !hasMimeTypes;
  if (hasMimeTypes) {
    for (const accepted of parser.acceptMimeTypes) {
      if (mimeTypeMatches(normalizedInputMime, normalizeMimeType(accepted))) {
        mimePassed = true;
        break;
      }
    }
  }

  // -- Extension check ------------------------------------------------------
  let extensionPassed = !hasExtensions;
  if (hasExtensions) {
    for (const accepted of parser.acceptExtensions) {
      if (normalizeExtension(accepted) === normalizedInputExt) {
        extensionPassed = true;
        break;
      }
    }
  }

  // If the parser declares both MIME types and extensions, the file must
  // match at least one of each declared filter group.
  if (!mimePassed || !extensionPassed) {
    const reasons: string[] = [];
    if (hasMimeTypes && !mimePassed) {
      reasons.push(
        `MIME type "${input.mimeType}" does not match [${parser.acceptMimeTypes!.join(', ')}]`,
      );
    }
    if (hasExtensions && !extensionPassed) {
      reasons.push(
        `extension ".${input.extension}" does not match [${parser.acceptExtensions!.join(', ')}]`,
      );
    }
    return {
      severity: 'info',
      code: PARSER_DIAGNOSTIC_CODES.UNSUPPORTED_TYPE,
      message: `Parser "${parser.label}" does not support this file type: ${reasons.join('; ')}.`,
      extensionId: parser.extensionId,
      contributionId: parser.id,
      detail: {
        mimeType: input.mimeType,
        extension: input.extension,
        acceptMimeTypes: parser.acceptMimeTypes,
        acceptExtensions: parser.acceptExtensions,
        parserId: parser.id,
      },
    };
  }

  return null; // Preflight passed
}

// ---------------------------------------------------------------------------
// Deterministic parser ordering
// ---------------------------------------------------------------------------

/**
 * Build a deterministically-ordered list of registered parsers.
 *
 * Orders parsers by the extension insertion order (primary), then
 * contribution order ascending, then parser ID alphabetically.
 *
 * Only parsers with a registered handler are included; descriptors
 * without a handler are silently skipped.
 */
export function orderParsers(
  parsers: readonly VideoEditorAssetParserDescriptor[],
  handlerMap: ReadonlyMap<string, ParserHandler>,
  extensionOrder: ReadonlyMap<string, number>,
): RegisteredParser[] {
  const registered: RegisteredParser[] = [];

  for (const descriptor of parsers) {
    const handler = handlerMap.get(descriptor.id);
    if (handler) {
      registered.push({ descriptor, handler });
    }
  }

  registered.sort((a, b) => {
    const extOrderA = extensionOrder.get(a.descriptor.extensionId) ?? Number.MAX_SAFE_INTEGER;
    const extOrderB = extensionOrder.get(b.descriptor.extensionId) ?? Number.MAX_SAFE_INTEGER;
    if (extOrderA !== extOrderB) return extOrderA - extOrderB;

    const orderA = a.descriptor.order ?? 0;
    const orderB = b.descriptor.order ?? 0;
    if (orderA !== orderB) return orderA - orderB;

    return a.descriptor.id.localeCompare(b.descriptor.id);
  });

  return registered;
}

// ---------------------------------------------------------------------------
// Blessed registry fields (only these fields may be set by parser merge)
// ---------------------------------------------------------------------------

/**
 * Registry entry fields that are considered "blessed" — i.e. known to the
 * host schema and safe to preserve during parser merge.
 *
 * Parsers return metadata only (via `ParserResult.metadata`); they cannot
 * directly set registry entry fields like `file`, `url`, `type`, etc.
 * The merge helper enforces this by only copying through fields that
 * appear in this allowlist.
 */
const BLESSED_REGISTRY_ENTRY_FIELDS = new Set([
  'file',
  'url',
  'etag',
  'content_sha256',
  'url_expires_at',
  'type',
  'duration',
  'resolution',
  'fps',
  'origin',
  'derivedFrom',
  'generationId',
  'variantId',
  'thumbnailUrl',
  'metadata',
]);

/**
 * Check whether a key is an extension metadata namespace.
 *
 * Extension namespaces are keys under `metadata.extensions` that identify
 * an extension by its ID.  They are the only keys that extensions may
 * write to.
 */
const isExtensionNamespace = (key: string): boolean =>
  /^[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)*$/i.test(key) && key.length <= 128;

// ---------------------------------------------------------------------------
// Rejected output fields
// ---------------------------------------------------------------------------

/**
 * Known host-owned metadata keys that parsers are allowed to set.
 * Any top-level metadata key not in this set is treated as an unknown
 * output field and rejected with a diagnostic.
 */
const KNOWN_METADATA_KEYS = new Set([
  'integrity',
  'gps',
  'consent',
  'provenance',
  'enrichment',
  'extensions',
]);

/**
 * Check parser result metadata for rejected output fields.
 *
 * Extracts the top-level keys from `metadata` and reports any that are
 * not known host-owned metadata keys or the `extensions` namespace.
 * Extension-owned keys nested under `extensions[extensionId]` are always
 * allowed and are not subject to field-level rejection.
 *
 * Returns a diagnostic when unknown fields are present (the fields are
 * still stripped from the result — the diagnostic is informational).
 */
export function checkRejectedOutputFields(
  metadata: Record<string, unknown> | undefined,
  parserId: string,
  extensionId: string,
): ParserDiagnostic | null {
  if (!metadata || typeof metadata !== 'object') return null;

  const unknownFields: string[] = [];
  const keys = Object.keys(metadata);
  for (let i = 0; i < keys.length; i++) {
    const key = keys[i];
    if (!KNOWN_METADATA_KEYS.has(key)) {
      unknownFields.push(key);
    }
  }

  if (unknownFields.length === 0) return null;

  return {
    severity: 'warning',
    code: PARSER_DIAGNOSTIC_CODES.REJECTED_OUTPUT_FIELDS,
    message:
      `Parser "${parserId}" returned unknown metadata fields ` +
      `[${unknownFields.join(', ')}] — these will be stripped.`,
    extensionId,
    contributionId: parserId,
    detail: {
      rejectedFields: unknownFields,
      parserId,
    },
  };
}

// ---------------------------------------------------------------------------
// Metadata deep merge with namespace awareness
// ---------------------------------------------------------------------------

/**
 * Convert SDK-shaped enrichment records to host-shaped enrichment claims.
 * This handles the structural difference between DeferredEnrichmentRecord
 * (SDK) and AssetMetadataEnrichmentClaim (host).
 */
const enrichmentRecordToClaim = (
  record: Record<string, unknown>,
): AssetMetadataEnrichmentClaim | null => {
  const id = record.id;
  const extensionId = record.extensionId;
  const createdAt = record.createdAt;
  if (typeof id !== 'string' || !id) return null;
  if (typeof extensionId !== 'string' || !extensionId) return null;
  if (typeof createdAt !== 'string' || !createdAt) return null;
  return {
    claimId: id,
    parserId: extensionId,
    timestamp: createdAt,
    field: typeof record.kind === 'string' ? record.kind : undefined,
    summary: typeof record.diagnostic === 'string' ? record.diagnostic : undefined,
  };
};

/**
 * Normalize incoming metadata from a parser result into the host
 * `AssetMetadata` shape by converting known SDK-type fields to
 * the host-equivalent structure.
 *
 * This function is intentionally lenient: it accepts both SDK-shaped
 * and host-shaped inputs and produces the closest valid host shape.
 * Unknown keys are stripped.
 */
const normalizeParserMetadata = (
  incoming: Record<string, unknown>,
): Record<string, unknown> => {
  const normalized: Record<string, unknown> = {};

  // Copy known host-owned keys as-is (they pass through validateAssetMetadata)
  for (const key of KNOWN_METADATA_KEYS) {
    const value = incoming[key];
    if (value !== undefined) {
      normalized[key] = value;
    }
  }

  // Convert SDK-style enrichment (array of DeferredEnrichmentRecord)
  // into host-style enrichment ({pending, failed, claims}).
  // If the incoming enrichment is an array, convert each record to a claim.
  if (Array.isArray(incoming.enrichment)) {
    const records = incoming.enrichment as Record<string, unknown>[];
    const claims: AssetMetadataEnrichmentClaim[] = [];
    for (const record of records) {
      if (record && typeof record === 'object') {
        const claim = enrichmentRecordToClaim(record);
        if (claim) claims.push(claim);
      }
    }
    if (claims.length > 0) {
      normalized.enrichment = {
        pending: claims.length,
        failed: 0,
        claims,
      } satisfies AssetMetadataEnrichment;
    }
  }

  // Clean up extensions namespace — ensure only valid namespace keys
  if (normalized.extensions && typeof normalized.extensions === 'object') {
    const extObj = normalized.extensions as Record<string, unknown>;
    const cleaned: Record<string, unknown> = {};
    const extKeys = Object.keys(extObj);
    for (let i = 0; i < extKeys.length; i++) {
      const ns = extKeys[i];
      if (isExtensionNamespace(ns) && extObj[ns] !== undefined) {
        cleaned[ns] = extObj[ns];
      }
    }
    if (Object.keys(cleaned).length > 0) {
      normalized.extensions = cleaned;
    } else {
      delete normalized.extensions;
    }
  }

  return normalized;
};

/**
 * Deep-merge parser-produced metadata into an existing registry entry.
 *
 * Rules:
 *   1. Only the `metadata` field of the registry entry is mutated — all
 *      other blessed fields are preserved as-is.
 *   2. Host-owned metadata keys (`integrity`, `gps`, `consent`, `provenance`,
 *      `enrichment`) are shallow-merged (later values overwrite earlier for
 *      the same key).
 *   3. Extension-owned metadata under `extensions[extensionId]` is
 *      namespace-aware deep-merged: each extension ID is its own namespace
 *      and values from different extensions are never cross-merged.
 *   4. Unknown top-level metadata keys are silently stripped.
 *   5. The merged metadata is validated through `validateAssetMetadata`
 *      to ensure only valid shapes survive.
 *
 * Returns the merged registry entry and any parser diagnostics produced.
 */
export function mergeParserMetadata(
  existingEntry: AssetRegistryEntry,
  parserResults: ReadonlyArray<{
    result: ParserResult;
    parserId: string;
    extensionId: string;
  }>,
): { entry: AssetRegistryEntry; diagnostics: ParserDiagnostic[] } {
  const diagnostics: ParserDiagnostic[] = [];

  // Start with a shallow copy of the existing entry, keeping only blessed fields.
  const mergedEntry: Record<string, unknown> = {};
  const blessedKeys = Array.from(BLESSED_REGISTRY_ENTRY_FIELDS);
  for (let i = 0; i < blessedKeys.length; i++) {
    const field = blessedKeys[i];
    if (field in existingEntry) {
      mergedEntry[field] = (existingEntry as Record<string, unknown>)[field];
    }
  }

  // Collect the existing metadata (already validated through sanitization)
  const existingMetadata: Record<string, unknown> =
    existingEntry.metadata && typeof existingEntry.metadata === 'object'
      ? { ...(existingEntry.metadata as Record<string, unknown>) }
      : {};

  // Process each parser result in order
  for (let ri = 0; ri < parserResults.length; ri++) {
    const { result, parserId, extensionId } = parserResults[ri];

    if (!result.metadata || typeof result.metadata !== 'object') {
      continue;
    }

    const rawMetadata = result.metadata as Record<string, unknown>;

    // Reject unknown output fields
    const rejectedFieldsDiag = checkRejectedOutputFields(
      rawMetadata,
      parserId,
      extensionId,
    );
    if (rejectedFieldsDiag) {
      diagnostics.push(rejectedFieldsDiag);
    }

    // Normalize incoming metadata to host shape
    const incoming = normalizeParserMetadata(rawMetadata);

    // Shallow-merge host-owned metadata keys
    const hostKeys = ['integrity', 'gps', 'consent', 'provenance'];
    for (let hk = 0; hk < hostKeys.length; hk++) {
      const hostKey = hostKeys[hk];
      if (incoming[hostKey] !== undefined && typeof incoming[hostKey] === 'object') {
        const existing = existingMetadata[hostKey];
        const incObj = incoming[hostKey] as Record<string, unknown>;
        if (existing && typeof existing === 'object') {
          existingMetadata[hostKey] = {
            ...(existing as Record<string, unknown>),
            ...incObj,
          };
        } else {
          existingMetadata[hostKey] = { ...incObj };
        }
      }
    }

    // Enrichment: shallow-merge object fields (pending, failed, claims)
    if (incoming.enrichment !== undefined && typeof incoming.enrichment === 'object') {
      const incEnrichment = incoming.enrichment as Record<string, unknown>;
      const existingEnrichment =
        existingMetadata.enrichment &&
        typeof existingMetadata.enrichment === 'object'
          ? (existingMetadata.enrichment as Record<string, unknown>)
          : {};
      // Build the merged enrichment: copy incEnrichment fields (pending, failed, etc.),
      // then handle claims concatenation separately.
      const mergedEnrichment: Record<string, unknown> = {
        ...existingEnrichment,
        ...incEnrichment,
      };
      // If incEnrichment has claims, concatenate with existing claims
      if (incEnrichment.claims !== undefined && Array.isArray(incEnrichment.claims)) {
        const existingClaims = Array.isArray(existingEnrichment.claims)
          ? (existingEnrichment.claims as unknown[])
          : [];
        mergedEnrichment.claims = [
          ...existingClaims,
          ...incEnrichment.claims,
        ];
      }
      existingMetadata.enrichment = mergedEnrichment;
    }

    // Namespace-aware deep merge for extensions
    if (incoming.extensions !== undefined && typeof incoming.extensions === 'object') {
      if (!existingMetadata.extensions || typeof existingMetadata.extensions !== 'object') {
        existingMetadata.extensions = {};
      }
      const existingExts = existingMetadata.extensions as Record<string, unknown>;
      const incomingExts = incoming.extensions as Record<string, unknown>;
      const extKeys = Object.keys(incomingExts);
      for (let ek = 0; ek < extKeys.length; ek++) {
        const nsKey = extKeys[ek];
        if (!isExtensionNamespace(nsKey)) continue;
        const nsValue = incomingExts[nsKey];
        if (nsValue === undefined) continue;
        if (
          typeof nsValue === 'object' &&
          nsValue !== null &&
          !Array.isArray(nsValue)
        ) {
          const existingNs =
            existingExts[nsKey] &&
            typeof existingExts[nsKey] === 'object' &&
            !Array.isArray(existingExts[nsKey])
              ? (existingExts[nsKey] as Record<string, unknown>)
              : {};
          existingExts[nsKey] = {
            ...existingNs,
            ...(nsValue as Record<string, unknown>),
          };
        }
      }
    }
  }

  // Validate the final metadata through the host validator
  const validatedMetadata = validateAssetMetadata(existingMetadata);
  if (validatedMetadata) {
    mergedEntry.metadata = validatedMetadata;
  }

  return {
    entry: mergedEntry as unknown as AssetRegistryEntry,
    diagnostics,
  };
}

// ---------------------------------------------------------------------------
// Run all parsers
// ---------------------------------------------------------------------------

/**
 * Result of running all parsers against an asset during ingestion.
 */
export interface AssetParserRunResult {
  /** The resulting registry entry with merged parser metadata. */
  entry: AssetRegistryEntry;
  /** All diagnostics produced during preflight, parsing, and merge. */
  diagnostics: ParserDiagnostic[];
  /** Whether ingestion is blocked by a required parser failure. */
  blocked: boolean;
}

/**
 * Run all registered parsers against an asset being ingested.
 *
 * Each parser is independently preflighted:
 *   - Parsers that don't match the file type produce informational
 *     `parser/unsupported-type` diagnostics and are skipped.
 *   - Parsers whose size limit is exceeded produce error
 *     `parser/oversized-input` diagnostics and are skipped.
 *
 * Eligible parsers are invoked in deterministic order. Each parser
 * receives the current accumulated metadata (so later parsers can
 * read earlier parsers' outputs).
 *
 * Parser results are merged into the registry entry, and validated
 * through `validateAssetMetadata`.
 *
 * When a required parser fails (throws or returns a blocking diagnostic),
 * the failure is recorded as a `parser/required-parser-failure` diagnostic
 * and `blocked` is set to `true` in the return value.
 *
 * @returns The merged registry entry, all diagnostics, and whether
 *          ingestion is blocked by a required parser failure.
 */
export async function runAllParsers(
  parsers: readonly RegisteredParser[],
  preflightInput: AssetParserPreflightInput,
  existingEntry: AssetRegistryEntry,
  assetKey: string,
): Promise<AssetParserRunResult> {
  const diagnostics: ParserDiagnostic[] = [];
  let blocked = false;
  let accumulatedMetadata: Record<string, unknown> | undefined =
    existingEntry.metadata && typeof existingEntry.metadata === 'object'
      ? { ...(existingEntry.metadata as Record<string, unknown>) }
      : undefined;

  const resultsToMerge: Array<{
    result: ParserResult;
    parserId: string;
    extensionId: string;
  }> = [];

  for (let pi = 0; pi < parsers.length; pi++) {
    const { descriptor, handler } = parsers[pi];

    // -- Preflight -----------------------------------------------------------
    const preflightDiag = runParserPreflight(descriptor, preflightInput);

    if (preflightDiag) {
      diagnostics.push(preflightDiag);

      // Oversized input is an error even for non-required parsers
      if (preflightDiag.code === PARSER_DIAGNOSTIC_CODES.OVERSIZED_INPUT) {
        if (descriptor.required) {
          blocked = true;
          diagnostics.push({
            severity: 'error',
            code: PARSER_DIAGNOSTIC_CODES.REQUIRED_PARSER_FAILURE,
            message:
              `Required parser "${descriptor.label}" (${descriptor.id}) ` +
              `cannot process this file — oversized input.`,
            assetKey,
            extensionId: descriptor.extensionId,
            contributionId: descriptor.id,
            detail: {
              reason: 'oversized-input',
              byteSize: preflightInput.byteSize,
              maxBytes: descriptor.maxBytes,
            },
          });
        }
      }
      // Unsupported type is informational for non-required parsers
      // but for required parsers it blocks ingestion
      if (
        preflightDiag.code === PARSER_DIAGNOSTIC_CODES.UNSUPPORTED_TYPE &&
        descriptor.required
      ) {
        blocked = true;
        diagnostics.push({
          severity: 'error',
          code: PARSER_DIAGNOSTIC_CODES.REQUIRED_PARSER_FAILURE,
          message:
            `Required parser "${descriptor.label}" (${descriptor.id}) ` +
            `cannot process this file — unsupported type.`,
          assetKey,
          extensionId: descriptor.extensionId,
          contributionId: descriptor.id,
          detail: {
            reason: 'unsupported-type',
            mimeType: preflightInput.mimeType,
            extension: preflightInput.extension,
          },
        });
      }
      continue;
    }

    // -- Build parser input with accumulated metadata ------------------------
    const parserInput: ParserInput = {
      assetKey,
      mimeType: preflightInput.mimeType,
      extension: preflightInput.extension,
      byteSize: preflightInput.byteSize,
      filename: preflightInput.filename,
      existingMetadata: accumulatedMetadata
        ? (Object.freeze({ ...accumulatedMetadata }) as unknown as import('@reigh/editor-sdk').AssetMetadata)
        : undefined,
    };

    // -- Invoke parser -------------------------------------------------------
    try {
      const result = await handler(parserInput);

      if (!result || typeof result !== 'object') {
        // Parser returned nothing — non-blocking, just skip
        continue;
      }

      // Collect parser's own diagnostics
      if (result.diagnostics && result.diagnostics.length > 0) {
        for (let di = 0; di < result.diagnostics.length; di++) {
          const d = result.diagnostics[di];
          diagnostics.push({
            ...d,
            assetKey: d.assetKey ?? assetKey,
            extensionId: d.extensionId ?? descriptor.extensionId,
            contributionId: d.contributionId ?? descriptor.id,
          });
        }
      }

      // Check for blocking errors from the parser itself
      const hasBlockingError =
        result.diagnostics &&
        result.diagnostics.some((d) => d.severity === 'error');
      if (hasBlockingError && descriptor.required) {
        blocked = true;
        diagnostics.push({
          severity: 'error',
          code: PARSER_DIAGNOSTIC_CODES.REQUIRED_PARSER_FAILURE,
          message:
            `Required parser "${descriptor.label}" (${descriptor.id}) ` +
            `reported blocking errors.`,
          assetKey,
          extensionId: descriptor.extensionId,
          contributionId: descriptor.id,
          detail: {
            reason: 'blocking-diagnostic',
            errorCount: result.diagnostics.filter((d) => d.severity === 'error').length,
          },
        });
      }

      // Collect result for merge
      resultsToMerge.push({
        result,
        parserId: descriptor.id,
        extensionId: descriptor.extensionId,
      });

      // Update accumulated metadata so later parsers can see previous results
      if (result.metadata) {
        if (!accumulatedMetadata) {
          accumulatedMetadata = {};
        }
        const rawMeta = result.metadata as Record<string, unknown>;
        const rawKeys = Object.keys(rawMeta);
        for (let rk = 0; rk < rawKeys.length; rk++) {
          accumulatedMetadata[rawKeys[rk]] = rawMeta[rawKeys[rk]];
        }
      }
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      const exceptionDiag: ParserDiagnostic = {
        severity: 'error',
        code: PARSER_DIAGNOSTIC_CODES.PARSER_EXCEPTION,
        message:
          `Parser "${descriptor.label}" (${descriptor.id}) threw an exception: ${errorMessage}`,
        assetKey,
        extensionId: descriptor.extensionId,
        contributionId: descriptor.id,
        detail: {
          error: errorMessage,
          parserId: descriptor.id,
        },
      };
      diagnostics.push(exceptionDiag);

      if (descriptor.required) {
        blocked = true;
        diagnostics.push({
          severity: 'error',
          code: PARSER_DIAGNOSTIC_CODES.REQUIRED_PARSER_FAILURE,
          message:
            `Required parser "${descriptor.label}" (${descriptor.id}) ` +
            `failed with an exception.`,
          assetKey,
          extensionId: descriptor.extensionId,
          contributionId: descriptor.id,
          detail: {
            reason: 'exception',
            error: errorMessage,
          },
        });
      }
    }
  }

  // Merge all parser results into the registry entry
  const merged = mergeParserMetadata(existingEntry, resultsToMerge);
  const entry = merged.entry;
  for (let di = 0; di < merged.diagnostics.length; di++) {
    diagnostics.push(merged.diagnostics[di]);
  }

  return { entry, diagnostics, blocked };
}

// ---------------------------------------------------------------------------
// Convenience: check if any parser matches a given file
// ---------------------------------------------------------------------------

/**
 * Check whether any parser in the list would accept the given file.
 *
 * Returns the first matching parser descriptor, or `undefined` if
 * no parser would handle this file.
 */
export function findMatchingParser(
  parsers: readonly VideoEditorAssetParserDescriptor[],
  input: AssetParserPreflightInput,
): VideoEditorAssetParserDescriptor | undefined {
  for (let i = 0; i < parsers.length; i++) {
    const diag = runParserPreflight(parsers[i], input);
    if (diag === null) {
      return parsers[i];
    }
  }
  return undefined;
}

/**
 * Collect preflight diagnostics for all parsers against a candidate file.
 *
 * Returns both the list of matching parsers and the full set of preflight
 * diagnostics (unsupported-type and oversized-input).
 */
export function preflightAllParsers(
  parsers: readonly VideoEditorAssetParserDescriptor[],
  input: AssetParserPreflightInput,
): {
  matchingParsers: VideoEditorAssetParserDescriptor[];
  diagnostics: ParserDiagnostic[];
} {
  const matchingParsers: VideoEditorAssetParserDescriptor[] = [];
  const diagnostics: ParserDiagnostic[] = [];

  for (let i = 0; i < parsers.length; i++) {
    const diag = runParserPreflight(parsers[i], input);
    if (diag === null) {
      matchingParsers.push(parsers[i]);
    } else {
      diagnostics.push(diag);
    }
  }

  return { matchingParsers, diagnostics };
}
