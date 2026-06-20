import { describe, expect, it } from 'vitest';
import {
  computeSha256,
  hexToBase64,
  base64ToHex,
  generateIntegrityHash,
  verifyIntegrity,
  parseSRI,
  formatSRI,
  missingIntegrityDiagnostic,
  unsupportedAlgorithmDiagnostic,
  malformedIntegrityDiagnostic,
  validateIntegrityHash,
  SUPPORTED_ALGORITHM,
} from '@/tools/video-editor/runtime/extensionIntegrity';
import type {
  IntegrityVerificationResult,
  IntegrityHash,
  ExtensionDiagnostic,
} from '@/tools/video-editor/runtime/extensionIntegrity';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Known test content for deterministic hash testing. */
const HELLO_CONTENT = 'Hello, World!';
const HELLO_HEX =
  'dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f';
const HELLO_BASE64 = '3/1gIbsr1bCvZ2KQgJ7DpTGR3YHH9wpLKGiKNiGCmG8=';

const BUNDLE_CONTENT = 'export function activate() { return { dispose() {} }; }';
const BUNDLE_HEX =
  '2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae';

// ---------------------------------------------------------------------------
// computeSha256
// ---------------------------------------------------------------------------

describe('computeSha256', () => {
  it('computes correct SHA-256 hash for string content', async () => {
    const hash = await computeSha256(HELLO_CONTENT);
    expect(hash).toBe(HELLO_HEX);
  });

  it('computes correct SHA-256 hash for Uint8Array content', async () => {
    const bytes = new TextEncoder().encode(HELLO_CONTENT);
    const hash = await computeSha256(bytes);
    expect(hash).toBe(HELLO_HEX);
  });

  it('returns 64 hex characters', async () => {
    const hash = await computeSha256(HELLO_CONTENT);
    expect(hash).toHaveLength(64);
    expect(/^[0-9a-f]{64}$/.test(hash)).toBe(true);
  });

  it('produces deterministic output for same input', async () => {
    const a = await computeSha256(HELLO_CONTENT);
    const b = await computeSha256(HELLO_CONTENT);
    expect(a).toBe(b);
  });

  it('produces different hashes for different content', async () => {
    const a = await computeSha256(HELLO_CONTENT);
    const b = await computeSha256('Different content');
    expect(a).not.toBe(b);
  });

  it('handles empty string', async () => {
    const hash = await computeSha256('');
    expect(hash).toHaveLength(64);
    expect(hash).toBe('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855');
  });

  it('handles binary content with null bytes', async () => {
    const bytes = new Uint8Array([0x00, 0x01, 0x02, 0xff, 0xfe, 0xfd]);
    const hash = await computeSha256(bytes);
    expect(hash).toHaveLength(64);
  });
});

// ---------------------------------------------------------------------------
// hexToBase64 / base64ToHex
// ---------------------------------------------------------------------------

describe('hexToBase64', () => {
  it('converts known hex to base64', () => {
    const base64 = hexToBase64(HELLO_HEX);
    expect(base64).toBe(HELLO_BASE64);
  });

  it('output is valid base64', () => {
    const base64 = hexToBase64(HELLO_HEX);
    expect(/^[A-Za-z0-9+/]+=*$/.test(base64)).toBe(true);
  });

  it('round-trips through base64ToHex', () => {
    const original = HELLO_HEX;
    const base64 = hexToBase64(original);
    const back = base64ToHex(base64);
    expect(back).toBe(original);
  });
});

describe('base64ToHex', () => {
  it('converts known base64 to hex', () => {
    const hex = base64ToHex(HELLO_BASE64);
    expect(hex).toBe(HELLO_HEX);
  });

  it('returns null for malformed base64', () => {
    expect(base64ToHex('not-valid-base64!!!')).toBeNull();
  });

  it('returns null for empty string', () => {
    expect(base64ToHex('')).toBeNull();
  });

  it('handles base64 with padding', () => {
    const base64 = 'aGVsbG8='; // "hello"
    const hex = base64ToHex(base64);
    expect(hex).toBe('68656c6c6f');
  });
});

// ---------------------------------------------------------------------------
// generateIntegrityHash
// ---------------------------------------------------------------------------

describe('generateIntegrityHash', () => {
  it('generates an IntegrityHash with algorithm sha256', async () => {
    const hash = await generateIntegrityHash(HELLO_CONTENT);
    expect(hash.algorithm).toBe('sha256');
  });

  it('generates correct base64 value for known content', async () => {
    const hash = await generateIntegrityHash(HELLO_CONTENT);
    expect(hash.value).toBe(HELLO_BASE64);
  });

  it('returns a frozen object', async () => {
    const hash = await generateIntegrityHash(HELLO_CONTENT);
    expect(Object.isFrozen(hash)).toBe(true);
  });

  it('produces consistent results', async () => {
    const a = await generateIntegrityHash(BUNDLE_CONTENT);
    const b = await generateIntegrityHash(BUNDLE_CONTENT);
    expect(a.value).toBe(b.value);
  });

  it('produces different values for different content', async () => {
    const a = await generateIntegrityHash('Content A');
    const b = await generateIntegrityHash('Content B');
    expect(a.value).not.toBe(b.value);
  });
});

// ---------------------------------------------------------------------------
// verifyIntegrity
// ---------------------------------------------------------------------------

describe('verifyIntegrity', () => {
  it('returns valid=true when content matches expected hash', async () => {
    const expected = await generateIntegrityHash(HELLO_CONTENT);
    const result = await verifyIntegrity(HELLO_CONTENT, expected);
    expect(result.valid).toBe(true);
    expect(result.diagnostics).toHaveLength(0);
  });

  it('returns valid=false when content does not match', async () => {
    const expected = await generateIntegrityHash(HELLO_CONTENT);
    const result = await verifyIntegrity('Tampered content!', expected);
    expect(result.valid).toBe(false);
    expect(result.diagnostics).toHaveLength(1);
  });

  it('produces hash-mismatch diagnostic on failure', async () => {
    const expected = await generateIntegrityHash(HELLO_CONTENT);
    const result = await verifyIntegrity('Tampered content!', expected);
    expect(result.diagnostics[0].code).toBe('integrity/hash-mismatch');
    expect(result.diagnostics[0].severity).toBe('error');
  });

  it('includes expected and computed hashes in diagnostic detail', async () => {
    const expected = await generateIntegrityHash(HELLO_CONTENT);
    const result = await verifyIntegrity('Tampered content!', expected);
    const detail = result.diagnostics[0].detail;
    expect(detail).toBeDefined();
    expect(detail!.expectedAlgorithm).toBe('sha256');
    expect(detail!.expectedValue).toBe(expected.value);
    expect(detail!.computedAlgorithm).toBe('sha256');
    expect(detail!.computedValue).not.toBe(expected.value);
  });

  it('attaches extensionId to diagnostic when provided', async () => {
    const expected = await generateIntegrityHash(HELLO_CONTENT);
    const result = await verifyIntegrity('Tampered content!', expected, 'com.test.ext');
    expect(result.diagnostics[0].extensionId).toBe('com.test.ext');
  });

  it('does not attach extensionId when not provided', async () => {
    const expected = await generateIntegrityHash(HELLO_CONTENT);
    const result = await verifyIntegrity('Tampered content!', expected);
    expect(result.diagnostics[0].extensionId).toBeUndefined();
  });

  it('verifies Uint8Array content correctly', async () => {
    const bytes = new TextEncoder().encode(HELLO_CONTENT);
    const expected = await generateIntegrityHash(bytes);
    const result = await verifyIntegrity(bytes, expected);
    expect(result.valid).toBe(true);
  });

  it('verification result is frozen', async () => {
    const expected = await generateIntegrityHash(HELLO_CONTENT);
    const result = await verifyIntegrity(HELLO_CONTENT, expected);
    expect(Object.isFrozen(result)).toBe(true);
    expect(Object.isFrozen(result.diagnostics)).toBe(true);
  });

  it('valid verification has empty diagnostics array', async () => {
    const expected = await generateIntegrityHash(HELLO_CONTENT);
    const result = await verifyIntegrity(HELLO_CONTENT, expected);
    expect(result.valid).toBe(true);
    expect(result.diagnostics).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// parseSRI
// ---------------------------------------------------------------------------

describe('parseSRI', () => {
  it('parses a valid sha256 SRI string', () => {
    const sri = `sha256-${HELLO_BASE64}`;
    const parsed = parseSRI(sri);
    expect(parsed).not.toBeNull();
    expect(parsed!.algorithm).toBe('sha256');
    expect(parsed!.value).toBe(HELLO_BASE64);
  });

  it('returns null for non-string input', () => {
    expect(parseSRI(undefined as any)).toBeNull();
    expect(parseSRI(null as any)).toBeNull();
    expect(parseSRI(123 as any)).toBeNull();
  });

  it('returns null for empty string', () => {
    expect(parseSRI('')).toBeNull();
  });

  it('returns null for missing algorithm prefix', () => {
    expect(parseSRI('-abc123')).toBeNull();
  });

  it('returns null for missing dash separator', () => {
    expect(parseSRI('sha256abc123')).toBeNull();
  });

  it('returns null for missing value after dash', () => {
    expect(parseSRI('sha256-')).toBeNull();
  });

  it('returns null for unsupported algorithm', () => {
    expect(parseSRI('md5-abc123')).toBeNull();
    expect(parseSRI('sha384-abc123')).toBeNull();
    expect(parseSRI('sha512-abc123')).toBeNull();
  });

  it('returns null for invalid base64 in value', () => {
    expect(parseSRI('sha256-!!!invalid!!!')).toBeNull();
  });

  it('returns frozen object', () => {
    const parsed = parseSRI(`sha256-${HELLO_BASE64}`);
    expect(Object.isFrozen(parsed!)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// formatSRI
// ---------------------------------------------------------------------------

describe('formatSRI', () => {
  it('formats an IntegrityHash as SRI string', () => {
    const hash: IntegrityHash = { algorithm: 'sha256', value: HELLO_BASE64 };
    expect(formatSRI(hash)).toBe(`sha256-${HELLO_BASE64}`);
  });

  it('round-trips with parseSRI', () => {
    const original = `sha256-${HELLO_BASE64}`;
    const parsed = parseSRI(original)!;
    expect(formatSRI(parsed)).toBe(original);
  });
});

// ---------------------------------------------------------------------------
// Diagnostic builders
// ---------------------------------------------------------------------------

describe('missingIntegrityDiagnostic', () => {
  it('produces an error diagnostic', () => {
    const diag = missingIntegrityDiagnostic();
    expect(diag.severity).toBe('error');
    expect(diag.code).toBe('integrity/missing-hash');
  });

  it('includes extensionId when provided', () => {
    const diag = missingIntegrityDiagnostic('com.test.ext');
    expect(diag.extensionId).toBe('com.test.ext');
  });

  it('does not include extensionId when omitted', () => {
    const diag = missingIntegrityDiagnostic();
    expect(diag.extensionId).toBeUndefined();
  });

  it('is frozen', () => {
    expect(Object.isFrozen(missingIntegrityDiagnostic())).toBe(true);
  });
});

describe('unsupportedAlgorithmDiagnostic', () => {
  it('produces an error diagnostic with algorithm in message', () => {
    const diag = unsupportedAlgorithmDiagnostic('md5');
    expect(diag.severity).toBe('error');
    expect(diag.code).toBe('integrity/unsupported-algorithm');
    expect(diag.message).toContain('md5');
    expect(diag.message).toContain('sha256');
  });

  it('includes detail with algorithm and supported list', () => {
    const diag = unsupportedAlgorithmDiagnostic('sha512');
    expect(diag.detail).toEqual({
      algorithm: 'sha512',
      supported: ['sha256'],
    });
  });
});

describe('malformedIntegrityDiagnostic', () => {
  it('produces an error diagnostic with reason', () => {
    const diag = malformedIntegrityDiagnostic('invalid base64');
    expect(diag.severity).toBe('error');
    expect(diag.code).toBe('integrity/malformed-hash');
    expect(diag.message).toContain('invalid base64');
    expect(diag.detail).toEqual({ reason: 'invalid base64' });
  });
});

// ---------------------------------------------------------------------------
// validateIntegrityHash
// ---------------------------------------------------------------------------

describe('validateIntegrityHash', () => {
  it('returns empty array for valid IntegrityHash', () => {
    const hash: IntegrityHash = { algorithm: 'sha256', value: HELLO_BASE64 };
    const diags = validateIntegrityHash(hash);
    expect(diags).toHaveLength(0);
  });

  it('returns diagnostic for null/undefined hash', () => {
    const diags = validateIntegrityHash(null);
    expect(diags).toHaveLength(1);
    expect(diags[0].code).toBe('integrity/missing-hash');
  });

  it('returns diagnostic for non-object hash', () => {
    const diags = validateIntegrityHash('not-an-object');
    expect(diags).toHaveLength(1);
    expect(diags[0].code).toBe('integrity/missing-hash');
  });

  it('returns diagnostic for unsupported algorithm', () => {
    const hash = { algorithm: 'md5', value: 'abc123' };
    const diags = validateIntegrityHash(hash);
    expect(diags.some((d) => d.code === 'integrity/unsupported-algorithm')).toBe(true);
  });

  it('returns diagnostic for missing value', () => {
    const hash = { algorithm: 'sha256' };
    const diags = validateIntegrityHash(hash);
    expect(diags.some((d) => d.code === 'integrity/malformed-hash')).toBe(true);
  });

  it('returns diagnostic for empty value', () => {
    const hash = { algorithm: 'sha256', value: '' };
    const diags = validateIntegrityHash(hash);
    expect(diags.some((d) => d.code === 'integrity/malformed-hash')).toBe(true);
  });

  it('returns diagnostic for whitespace-only value', () => {
    const hash = { algorithm: 'sha256', value: '   ' };
    const diags = validateIntegrityHash(hash);
    expect(diags.some((d) => d.code === 'integrity/malformed-hash')).toBe(true);
  });

  it('returns diagnostic for invalid base64 characters', () => {
    const hash = { algorithm: 'sha256', value: '!!!invalid!!!' };
    const diags = validateIntegrityHash(hash);
    expect(diags.some((d) => d.code === 'integrity/malformed-hash')).toBe(true);
  });

  it('attaches extensionId to diagnostics when provided', () => {
    const diags = validateIntegrityHash(null, 'com.test.ext');
    expect(diags[0].extensionId).toBe('com.test.ext');
  });

  it('returns multiple diagnostics for multiple problems', () => {
    const hash = { algorithm: 'invalid', value: '' };
    const diags = validateIntegrityHash(hash);
    expect(diags.length).toBeGreaterThanOrEqual(2);
  });
});

// ---------------------------------------------------------------------------
// Integration: full generate → verify round-trip
// ---------------------------------------------------------------------------

describe('integrity round-trip', () => {
  it('generated hash can verify the same content', async () => {
    const content = 'console.log("hello from bundle.mjs");';
    const hash = await generateIntegrityHash(content);
    const result = await verifyIntegrity(content, hash);
    expect(result.valid).toBe(true);
  });

  it('tampered content fails verification', async () => {
    const original = 'const x = 1;';
    const tampered = 'const x = 2;';
    const hash = await generateIntegrityHash(original);
    const result = await verifyIntegrity(tampered, hash);
    expect(result.valid).toBe(false);
  });

  it('single-byte change produces different hash', async () => {
    const a = await generateIntegrityHash('AAAA');
    const b = await generateIntegrityHash('AAAB');
    expect(a.value).not.toBe(b.value);
  });

  it('parse → format round-trip preserves value', async () => {
    const hash = await generateIntegrityHash(BUNDLE_CONTENT);
    const sri = formatSRI(hash);
    const parsed = parseSRI(sri);
    expect(parsed).not.toBeNull();
    expect(parsed!.algorithm).toBe(hash.algorithm);
    expect(parsed!.value).toBe(hash.value);
  });

  it('validateIntegrityHash accepts generated hash', async () => {
    const hash = await generateIntegrityHash(BUNDLE_CONTENT);
    const diags = validateIntegrityHash(hash);
    expect(diags).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

describe('edge cases', () => {
  it('handles very large content without error', async () => {
    const large = 'x'.repeat(1_000_000);
    const hash = await generateIntegrityHash(large);
    expect(hash.value).toBeTruthy();
    expect(hash.algorithm).toBe('sha256');
  });

  it('handles unicode content', async () => {
    const unicode = 'Hello 🌍! こんにちは';
    const hash = await generateIntegrityHash(unicode);
    expect(hash.algorithm).toBe('sha256');
    const result = await verifyIntegrity(unicode, hash);
    expect(result.valid).toBe(true);
  });

  it('handles newlines and control characters', async () => {
    const content = 'line1\nline2\r\nline3\tindented';
    const hash = await generateIntegrityHash(content);
    const result = await verifyIntegrity(content, hash);
    expect(result.valid).toBe(true);
  });

  it('base64ToHex handles empty string gracefully', () => {
    // base64ToHex returns null for empty input
    expect(base64ToHex('')).toBeNull();
  });

  it('SUPPORTED_ALGORITHM is sha256', () => {
    expect(SUPPORTED_ALGORITHM).toBe('sha256');
  });
});
