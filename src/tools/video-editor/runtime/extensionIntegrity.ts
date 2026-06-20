/**
 * Integrity utilities for extension bundle verification.
 *
 * Provides SHA-256 SRI (Subresource Integrity) generation and verification
 * for installed extension bundle content (`bundle.mjs` bytes/text).
 *
 * Mismatches produce blocking diagnostics that prevent installation and
 * activation. Missing, malformed, and algorithm-mismatched hashes are also
 * diagnosed with clear, actionable messages.
 */

import type { IntegrityHash, ExtensionDiagnostic } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** The only supported integrity algorithm for M14. */
export const SUPPORTED_ALGORITHM = 'sha256' as const;

// ---------------------------------------------------------------------------
// Core hashing
// ---------------------------------------------------------------------------

/**
 * Compute a SHA-256 hash of the given content.
 *
 * Handles both string (UTF-8 encoded) and raw byte input via the Web Crypto API.
 *
 * @returns Hex-encoded SHA-256 digest (lowercase, 64 hex chars).
 */
export async function computeSha256(content: string | Uint8Array): Promise<string> {
  const data = typeof content === 'string' ? new TextEncoder().encode(content) : content;
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Convert a hex-encoded SHA-256 digest to a Base64-encoded value.
 *
 * Base64 encoding is used for the SRI value per the IntegrityHash contract.
 */
export function hexToBase64(hex: string): string {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }
  // Use btoa-style encoding via Buffer
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Decode a Base64-encoded hash value to hex.
 *
 * @returns Hex string or null if the base64 value is malformed.
 */
export function base64ToHex(base64: string): string | null {
  if (!base64 || base64.length === 0) return null;
  try {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return Array.from(bytes)
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// IntegrityHash generation
// ---------------------------------------------------------------------------

/**
 * Generate an IntegrityHash for the given content using SHA-256.
 *
 * The hash value is Base64-encoded per the {@link IntegrityHash} contract.
 *
 * @param content Bundle content as a string (UTF-8) or raw bytes.
 * @returns An IntegrityHash with algorithm 'sha256' and the Base64-encoded digest.
 */
export async function generateIntegrityHash(
  content: string | Uint8Array,
): Promise<IntegrityHash> {
  const hex = await computeSha256(content);
  const value = hexToBase64(hex);
  return Object.freeze({
    algorithm: 'sha256' as const,
    value,
  });
}

// ---------------------------------------------------------------------------
// Verification result
// ---------------------------------------------------------------------------

/** The outcome of an integrity verification. */
export interface IntegrityVerificationResult {
  /** True when the computed hash matches the expected hash. */
  readonly valid: boolean;
  /** The hash computed from the actual content. */
  readonly computed: IntegrityHash;
  /** The expected hash against which content was verified. */
  readonly expected: IntegrityHash;
  /** Blocking diagnostics produced when verification fails. */
  readonly diagnostics: readonly ExtensionDiagnostic[];
}

// ---------------------------------------------------------------------------
// Verification
// ---------------------------------------------------------------------------

/**
 * Verify that bundle content matches an expected IntegrityHash.
 *
 * Content that fails verification produces a blocking diagnostic with code
 * `integrity/hash-mismatch` detailing the expected vs computed hash values.
 *
 * @param content   The bundle content to verify.
 * @param expected  The expected IntegrityHash to verify against.
 * @param extensionId Optional extension ID for diagnostic attribution.
 * @returns A verification result with diagnostics on failure.
 */
export async function verifyIntegrity(
  content: string | Uint8Array,
  expected: IntegrityHash,
  extensionId?: string,
): Promise<IntegrityVerificationResult> {
  const computed = await generateIntegrityHash(content);
  const valid = computed.value === expected.value && computed.algorithm === expected.algorithm;

  const diagnostics: ExtensionDiagnostic[] = [];

  if (!valid) {
    diagnostics.push(
      Object.freeze({
        severity: 'error' as const,
        code: 'integrity/hash-mismatch' as const,
        message:
          `Bundle integrity check failed. Expected ${expected.algorithm}:${expected.value} ` +
          `but computed ${computed.algorithm}:${computed.value}`,
        ...(extensionId ? { extensionId } : {}),
        detail: {
          expectedAlgorithm: expected.algorithm,
          expectedValue: expected.value,
          computedAlgorithm: computed.algorithm,
          computedValue: computed.value,
        },
      }),
    );
  }

  return Object.freeze({
    valid,
    computed,
    expected,
    diagnostics: Object.freeze(diagnostics),
  });
}

// ---------------------------------------------------------------------------
// SRI string parsing and formatting
// ---------------------------------------------------------------------------

/**
 * Parse an SRI-style string (e.g. "sha256-abc123...") into an IntegrityHash.
 *
 * Only "sha256" is supported as the algorithm prefix. Returns null for
 * malformed or unsupported SRI strings.
 */
export function parseSRI(sri: string): IntegrityHash | null {
  if (typeof sri !== 'string' || sri.length === 0) return null;

  // SRI format: algorithm-base64value
  const dashIndex = sri.indexOf('-');
  if (dashIndex <= 0 || dashIndex >= sri.length - 1) return null;

  const algorithm = sri.substring(0, dashIndex);
  const value = sri.substring(dashIndex + 1);

  if (algorithm !== SUPPORTED_ALGORITHM) return null;
  if (value.length === 0) return null;

  // Validate base64 characters
  if (!/^[A-Za-z0-9+/=]+$/.test(value)) return null;

  return Object.freeze({
    algorithm: algorithm as 'sha256',
    value,
  });
}

/**
 * Format an IntegrityHash as an SRI string (e.g. "sha256-abc123...").
 */
export function formatSRI(hash: IntegrityHash): string {
  return `${hash.algorithm}-${hash.value}`;
}

// ---------------------------------------------------------------------------
// Diagnostic builders
// ---------------------------------------------------------------------------

/**
 * Build a blocking diagnostic for a missing integrity hash requirement.
 *
 * Used when an installed bundle is missing its integrity metadata entirely.
 */
export function missingIntegrityDiagnostic(extensionId?: string): ExtensionDiagnostic {
  return Object.freeze({
    severity: 'error' as const,
    code: 'integrity/missing-hash' as const,
    message: 'Installed bundle is missing required integrity hash metadata',
    ...(extensionId ? { extensionId } : {}),
  });
}

/**
 * Build a blocking diagnostic for an unsupported integrity algorithm.
 *
 * M14 only supports SHA-256; any other algorithm is rejected.
 */
export function unsupportedAlgorithmDiagnostic(
  algorithm: string,
  extensionId?: string,
): ExtensionDiagnostic {
  return Object.freeze({
    severity: 'error' as const,
    code: 'integrity/unsupported-algorithm' as const,
    message:
      `Integrity algorithm "${algorithm}" is not supported. ` +
      `Only "${SUPPORTED_ALGORITHM}" is accepted.`,
    ...(extensionId ? { extensionId } : {}),
    detail: { algorithm, supported: [SUPPORTED_ALGORITHM] },
  });
}

/**
 * Build a blocking diagnostic for a malformed SRI hash value.
 *
 * Triggered when the hash value is not valid Base64 or is otherwise
 * structurally invalid.
 */
export function malformedIntegrityDiagnostic(
  reason: string,
  extensionId?: string,
): ExtensionDiagnostic {
  return Object.freeze({
    severity: 'error' as const,
    code: 'integrity/malformed-hash' as const,
    message: `Integrity hash is malformed: ${reason}`,
    ...(extensionId ? { extensionId } : {}),
    detail: { reason },
  });
}

/**
 * Validate an IntegrityHash object for structural correctness.
 *
 * Returns an array of diagnostic errors. An empty array means the hash is
 * structurally valid (though not yet verified against content).
 */
export function validateIntegrityHash(
  hash: unknown,
  extensionId?: string,
): ExtensionDiagnostic[] {
  const diagnostics: ExtensionDiagnostic[] = [];

  if (!hash || typeof hash !== 'object') {
    diagnostics.push(missingIntegrityDiagnostic(extensionId));
    return diagnostics;
  }

  const h = hash as Record<string, unknown>;

  // Validate algorithm
  if (!h.algorithm || h.algorithm !== SUPPORTED_ALGORITHM) {
    diagnostics.push(
      unsupportedAlgorithmDiagnostic(
        typeof h.algorithm === 'string' ? h.algorithm : 'undefined',
        extensionId,
      ),
    );
  }

  // Validate value
  if (!h.value || typeof h.value !== 'string' || (h.value as string).trim().length === 0) {
    diagnostics.push(
      malformedIntegrityDiagnostic('Hash value is missing or empty', extensionId),
    );
  } else if (!/^[A-Za-z0-9+/=]+$/.test(h.value as string)) {
    diagnostics.push(
      malformedIntegrityDiagnostic(
        'Hash value contains invalid Base64 characters',
        extensionId,
      ),
    );
  }

  return diagnostics;
}

// ---------------------------------------------------------------------------
// Re-exports for convenience
// ---------------------------------------------------------------------------

export type { IntegrityHash, ExtensionDiagnostic };
