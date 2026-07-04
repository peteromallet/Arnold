/**
 * Host-side ProcessRoundtripResult payload-limit normalization.
 *
 * Rejects oversized inline material / artifact / sidecar blobs unless a
 * backing artifact locator is present.  Does NOT truncate, silently
 * accept, or fallback-encode any data — oversized inline without a
 * locator is a hard protocol-level rejection.
 *
 * The limit is an explicit configurable constant so callers (and tests)
 * can assert behaviour independently of the default.
 */

import { JsonRpcTransportError } from './jsonRpcStdioTransport';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/** Default maximum bytes for an inline blob without an artifact locator. */
export const DEFAULT_MAX_INLINE_BLOB_BYTES = 64 * 1024; // 64 KiB

export interface PayloadLimitsConfig {
  /** Override the per-blob byte limit (defaults to {@link DEFAULT_MAX_INLINE_BLOB_BYTES}). */
  readonly maxInlineBlobBytes?: number;
}

// ---------------------------------------------------------------------------
// Diagnostics
// ---------------------------------------------------------------------------

/** Diagnostic produced for a single oversized inline blob lacking a locator. */
export interface InlineBlobDiagnostic {
  /** Which top-level result array the entry belongs to. */
  readonly field: 'returnedMaterials' | 'artifacts' | 'sidecars';
  /** Zero-based index within that array. */
  readonly index: number;
  /** Measured byte size of the inline blob. */
  readonly actualBytes: number;
  /** The limit that was exceeded. */
  readonly limitBytes: number;
  /** Whether a non-inline locator was present on the entry. */
  readonly locatorPresent: boolean;
  /** Human-readable summary. */
  readonly message: string;
}

// ---------------------------------------------------------------------------
// Size estimation
// ---------------------------------------------------------------------------

function estimateBlobBytes(value: unknown): number {
  if (value instanceof Uint8Array) {
    return value.byteLength;
  }
  if (typeof value === 'string') {
    return Buffer.byteLength(value, 'utf-8');
  }
  // For structured objects (shouldn't normally be a blob, but be safe).
  if (typeof value === 'object' && value !== null) {
    return Buffer.byteLength(JSON.stringify(value), 'utf-8');
  }
  return 0;
}

// ---------------------------------------------------------------------------
// Locator helpers
// ---------------------------------------------------------------------------

interface LocatorLike {
  readonly kind?: unknown;
  readonly uri?: unknown;
}

function asLocator(value: unknown): LocatorLike | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as LocatorLike;
}

function isInlineKind(kind: unknown): boolean {
  return kind === 'inline';
}

function isNonInlineLocatorKind(kind: unknown): boolean {
  return typeof kind === 'string'
    && kind.length > 0
    && kind !== 'inline';
}

// ---------------------------------------------------------------------------
// Core check
// ---------------------------------------------------------------------------

/**
 * Inspect a raw execute-response payload for oversized inline blobs that
 * lack a backing artifact locator.
 *
 * Returns zero or more diagnostics.  An empty array means the payload
 * passes the size limits for every entry.
 *
 * This function is deliberately pure and does not mutate or re-encode
 * the payload — it only measures and reports.
 */
export function checkPayloadLimits(
  payload: Record<string, unknown>,
  config: PayloadLimitsConfig = {},
): InlineBlobDiagnostic[] {
  const maxBytes = config.maxInlineBlobBytes ?? DEFAULT_MAX_INLINE_BLOB_BYTES;
  const diagnostics: InlineBlobDiagnostic[] = [];

  const pushDiagnostic = (
    field: InlineBlobDiagnostic['field'],
    index: number,
    actualBytes: number,
    locatorPresent: boolean,
  ): void => {
    diagnostics.push({
      field,
      index,
      actualBytes,
      limitBytes: maxBytes,
      locatorPresent,
      message: `${field}[${index}] has an inline blob of ${actualBytes} bytes (limit: ${maxBytes}) and no artifact locator.`,
    });
  };

  // ── returnedMaterials / artifacts (same shape: { locator, … }) ─────
  const checkMaterialLike = (
    entries: unknown[],
    field: 'returnedMaterials' | 'artifacts',
  ): void => {
    for (let i = 0; i < entries.length; i++) {
      const entry = entries[i];
      const locator = asLocator(
        (entry as Record<string, unknown> | undefined)?.locator,
      );
      if (!locator || !isInlineKind(locator.kind)) continue;

      // The locator itself is inline — estimate payload size from its URI.
      const blobBytes = estimateBlobBytes(locator.uri);
      const locatorPresent = isNonInlineLocatorKind(locator.kind); // always false here

      if (blobBytes > maxBytes) {
        pushDiagnostic(field, i, blobBytes, locatorPresent);
      }
    }
  };

  // ── sidecars ({ data?, locator?, … }) ──────────────────────────────
  const checkSidecars = (entries: unknown[]): void => {
    for (let i = 0; i < entries.length; i++) {
      const entry = entries[i] as Record<string, unknown> | undefined;
      if (!entry) continue;

      const data = entry.data;
      if (data === undefined) continue;

      const blobBytes = estimateBlobBytes(data);
      if (blobBytes <= maxBytes) continue;

      const locator = asLocator(entry.locator);
      const locatorPresent = locator !== null && isNonInlineLocatorKind(locator.kind);

      if (!locatorPresent) {
        pushDiagnostic('sidecars', i, blobBytes, false);
      }
    }
  };

  // ── Apply checks ───────────────────────────────────────────────────
  if (Array.isArray(payload.returnedMaterials)) {
    checkMaterialLike(payload.returnedMaterials as unknown[], 'returnedMaterials');
  }
  if (Array.isArray(payload.artifacts)) {
    checkMaterialLike(payload.artifacts as unknown[], 'artifacts');
  }
  if (Array.isArray(payload.sidecars)) {
    checkSidecars(payload.sidecars as unknown[]);
  }

  return diagnostics;
}

// ---------------------------------------------------------------------------
// Assertion wrapper (convenience for ProcessManager)
// ---------------------------------------------------------------------------

/**
 * Throw if any oversized inline blob lacks an artifact locator.
 *
 * The thrown error is a {@link JsonRpcTransportError} with class
 * `'protocol-error'` so it fits neatly into the existing ProcessManager
 * error-handling pipeline.
 */
export function assertPayloadLimits(
  payload: Record<string, unknown>,
  config?: PayloadLimitsConfig,
): void {
  const diagnostics = checkPayloadLimits(payload, config);
  if (diagnostics.length === 0) return;

  throw new JsonRpcTransportError(
    `Payload contains ${diagnostics.length} oversized inline blob(s) without artifact locators.`,
    {
      code: -32600,
      errorClass: 'protocol-error',
      processId: typeof payload.processId === 'string' ? payload.processId : undefined,
      operationId: typeof payload.operationId === 'string' ? payload.operationId : undefined,
      taskId:
        typeof payload.requestId === 'string'
          ? payload.requestId
          : typeof payload.taskId === 'string'
            ? payload.taskId
            : undefined,
      rawMessage: { diagnostics },
    },
  );
}
