import { describe, expect, it } from 'vitest';
import {
  checkPayloadLimits,
  assertPayloadLimits,
  DEFAULT_MAX_INLINE_BLOB_BYTES,
  type PayloadLimitsConfig,
} from './payloadLimits';
import { JsonRpcTransportError } from './jsonRpcStdioTransport';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function largeString(bytes: number): string {
  return 'x'.repeat(bytes);
}

function oversizedBuffer(bytes: number): Uint8Array {
  return new Uint8Array(bytes).fill(0x41);
}

// ---------------------------------------------------------------------------
// checkPayloadLimits
// ---------------------------------------------------------------------------

describe('checkPayloadLimits', () => {
  // ── Empty / missing payloads ───────────────────────────────────────

  it('returns no diagnostics for an empty payload', () => {
    expect(checkPayloadLimits({})).toEqual([]);
  });

  it('returns no diagnostics when arrays are empty', () => {
    expect(checkPayloadLimits({
      returnedMaterials: [],
      artifacts: [],
      sidecars: [],
    })).toEqual([]);
  });

  it('returns no diagnostics when arrays are missing', () => {
    expect(checkPayloadLimits({
      processId: 'proc.alpha',
      status: 'completed',
    })).toEqual([]);
  });

  // ── returnedMaterials — inline under / over limit ───────────────────

  it('accepts inline returnedMaterials with URI under the limit', () => {
    const underLimit = largeString(DEFAULT_MAX_INLINE_BLOB_BYTES - 100);
    const result = checkPayloadLimits({
      returnedMaterials: [
        {
          locator: { kind: 'inline', uri: underLimit },
        },
      ],
    });
    expect(result).toEqual([]);
  });

  it('rejects oversized inline returnedMaterials without artifact locator', () => {
    const overLimit = largeString(DEFAULT_MAX_INLINE_BLOB_BYTES + 1);
    const result = checkPayloadLimits({
      returnedMaterials: [
        {
          locator: { kind: 'inline', uri: overLimit },
        },
      ],
    });
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      field: 'returnedMaterials',
      index: 0,
      actualBytes: overLimit.length,
      limitBytes: DEFAULT_MAX_INLINE_BLOB_BYTES,
      locatorPresent: false,
    });
  });

  it('uses an explicit configurable limit for returnedMaterials', () => {
    const smallLimit: PayloadLimitsConfig = { maxInlineBlobBytes: 10 };
    const payload = {
      returnedMaterials: [
        { locator: { kind: 'inline', uri: 'x'.repeat(11) } },
      ],
    };
    expect(checkPayloadLimits(payload, smallLimit)).toHaveLength(1);
    expect(checkPayloadLimits(payload, { maxInlineBlobBytes: 128 })).toEqual([]);
  });

  // ── artifacts — inline under / over limit ───────────────────────────

  it('accepts inline artifacts with URI under the limit', () => {
    const underLimit = largeString(DEFAULT_MAX_INLINE_BLOB_BYTES - 50);
    expect(checkPayloadLimits({
      artifacts: [
        { locator: { kind: 'inline', uri: underLimit } },
      ],
    })).toEqual([]);
  });

  it('rejects oversized inline artifacts without artifact locator', () => {
    const overLimit = largeString(DEFAULT_MAX_INLINE_BLOB_BYTES + 500);
    const result = checkPayloadLimits({
      artifacts: [
        { locator: { kind: 'inline', uri: overLimit } },
      ],
    });
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      field: 'artifacts',
      index: 0,
      actualBytes: overLimit.length,
      locatorPresent: false,
    });
  });

  // ── sidecars — inline data under / over limit ───────────────────────

  it('accepts sidecar inline data under the limit without locator', () => {
    const underLimit = oversizedBuffer(DEFAULT_MAX_INLINE_BLOB_BYTES - 200);
    expect(checkPayloadLimits({
      sidecars: [
        { data: underLimit },
      ],
    })).toEqual([]);
  });

  it('rejects oversized sidecar data without a locator', () => {
    const overLimit = oversizedBuffer(DEFAULT_MAX_INLINE_BLOB_BYTES + 1);
    const result = checkPayloadLimits({
      sidecars: [
        { data: overLimit },
      ],
    });
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      field: 'sidecars',
      index: 0,
      actualBytes: overLimit.byteLength,
      limitBytes: DEFAULT_MAX_INLINE_BLOB_BYTES,
      locatorPresent: false,
    });
  });

  it('accepts oversized sidecar data when a non-inline locator is present', () => {
    const overLimit = oversizedBuffer(DEFAULT_MAX_INLINE_BLOB_BYTES * 2);
    expect(checkPayloadLimits({
      sidecars: [
        {
          data: overLimit,
          locator: { kind: 'artifact-store', uri: 'artifact://store/abc' },
        },
      ],
    })).toEqual([]);
  });

  it('rejects oversized sidecar data when locator is inline', () => {
    const overLimit = oversizedBuffer(DEFAULT_MAX_INLINE_BLOB_BYTES + 10);
    const result = checkPayloadLimits({
      sidecars: [
        {
          data: overLimit,
          locator: { kind: 'inline', uri: 'data:...' },
        },
      ],
    });
    expect(result).toHaveLength(1);
    expect(result[0].locatorPresent).toBe(false);
  });

  it('accepts oversized sidecar data with a url locator', () => {
    const overLimit = oversizedBuffer(DEFAULT_MAX_INLINE_BLOB_BYTES + 100);
    expect(checkPayloadLimits({
      sidecars: [
        {
          data: overLimit,
          locator: { kind: 'url', uri: 'https://example.com/file.bin' },
        },
      ],
    })).toEqual([]);
  });

  it('accepts oversized sidecar data with a local-file locator', () => {
    const overLimit = oversizedBuffer(DEFAULT_MAX_INLINE_BLOB_BYTES + 100);
    expect(checkPayloadLimits({
      sidecars: [
        {
          data: overLimit,
          locator: { kind: 'local-file', uri: '/tmp/out.bin' },
        },
      ],
    })).toEqual([]);
  });

  // ── Multiple entries ────────────────────────────────────────────────

  it('reports diagnostics for multiple oversized entries across fields', () => {
    const overLimit = largeString(DEFAULT_MAX_INLINE_BLOB_BYTES + 10);
    const overSidecar = oversizedBuffer(DEFAULT_MAX_INLINE_BLOB_BYTES + 5);
    const result = checkPayloadLimits({
      returnedMaterials: [
        { locator: { kind: 'inline', uri: overLimit } },
      ],
      artifacts: [
        { locator: { kind: 'inline', uri: overLimit } },
      ],
      sidecars: [
        { data: overSidecar },
      ],
    });
    expect(result).toHaveLength(3);
    expect(result.map((d) => d.field).sort()).toEqual([
      'artifacts',
      'returnedMaterials',
      'sidecars',
    ]);
  });

  // ── Mixed (some ok, some bad) ───────────────────────────────────────

  it('only reports oversized entries, not valid ones', () => {
    const ok = largeString(DEFAULT_MAX_INLINE_BLOB_BYTES - 1);
    const bad = largeString(DEFAULT_MAX_INLINE_BLOB_BYTES + 1);
    const result = checkPayloadLimits({
      returnedMaterials: [
        { locator: { kind: 'inline', uri: ok } },
        { locator: { kind: 'inline', uri: bad } },
        { locator: { kind: 'inline', uri: ok } },
      ],
    });
    expect(result).toHaveLength(1);
    expect(result[0].index).toBe(1);
  });

  // ── No truncation / fallback encoding ───────────────────────────────

  it('does not mutate or truncate the input payload', () => {
    const overLimit = largeString(DEFAULT_MAX_INLINE_BLOB_BYTES + 5);
    const payload = {
      returnedMaterials: [
        { locator: { kind: 'inline' as const, uri: overLimit } },
      ],
    };
    const snapshot = JSON.stringify(payload);
    checkPayloadLimits(payload);
    expect(JSON.stringify(payload)).toBe(snapshot);
  });

  it('treats string blobs by UTF-8 byte length, not character length', () => {
    // Multi-byte characters should count as multiple bytes.
    const emoji = '🎬'.repeat(DEFAULT_MAX_INLINE_BLOB_BYTES);
    const result = checkPayloadLimits({
      returnedMaterials: [
        { locator: { kind: 'inline', uri: emoji } },
      ],
    });
    // Each 🎬 is 4 bytes in UTF-8.
    expect(result.length).toBeGreaterThanOrEqual(1);
    expect(result[0].actualBytes).toBeGreaterThan(emoji.length);
  });
});

// ---------------------------------------------------------------------------
// assertPayloadLimits
// ---------------------------------------------------------------------------

describe('assertPayloadLimits', () => {
  it('does not throw for clean payloads', () => {
    expect(() => assertPayloadLimits({
      returnedMaterials: [],
      sidecars: [],
    })).not.toThrow();
  });

  it('does not throw for locator-backed oversized sidecar', () => {
    const overLimit = oversizedBuffer(DEFAULT_MAX_INLINE_BLOB_BYTES * 2);
    expect(() => assertPayloadLimits({
      sidecars: [
        {
          data: overLimit,
          locator: { kind: 'artifact-store', uri: 'artifact://abc' },
        },
      ],
    })).not.toThrow();
  });

  it('throws JsonRpcTransportError for oversized inline without locator', () => {
    const overLimit = oversizedBuffer(DEFAULT_MAX_INLINE_BLOB_BYTES + 1);
    expect(() => assertPayloadLimits({
      processId: 'proc.alpha',
      operationId: 'render',
      requestId: 'task-1',
      sidecars: [{ data: overLimit }],
    })).toThrow(JsonRpcTransportError);

    try {
      assertPayloadLimits({
        processId: 'proc.alpha',
        operationId: 'render',
        requestId: 'task-1',
        sidecars: [{ data: overLimit }],
      });
    } catch (error) {
      expect(error).toBeInstanceOf(JsonRpcTransportError);
      const transportError = error as JsonRpcTransportError;
      expect(transportError.errorClass).toBe('protocol-error');
      expect(transportError.code).toBe(-32600);
      expect(transportError.processId).toBe('proc.alpha');
      expect(transportError.operationId).toBe('render');
      expect(transportError.taskId).toBe('task-1');
    }
  });

  it('throws with taskId from requestId field', () => {
    const overLimit = oversizedBuffer(DEFAULT_MAX_INLINE_BLOB_BYTES + 1);
    expect(() => assertPayloadLimits({
      processId: 'p',
      requestId: 'r1',
      sidecars: [{ data: overLimit }],
    })).toThrow(JsonRpcTransportError);

    try {
      assertPayloadLimits({
        processId: 'p',
        requestId: 'r1',
        sidecars: [{ data: overLimit }],
      });
    } catch (error) {
      expect((error as JsonRpcTransportError).taskId).toBe('r1');
    }
  });

  it('throws with taskId from taskId field when requestId absent', () => {
    const overLimit = oversizedBuffer(DEFAULT_MAX_INLINE_BLOB_BYTES + 1);
    try {
      assertPayloadLimits({
        processId: 'p',
        taskId: 't2',
        sidecars: [{ data: overLimit }],
      });
    } catch (error) {
      expect((error as JsonRpcTransportError).taskId).toBe('t2');
    }
  });

  it('includes diagnostic details in the error rawMessage', () => {
    const overLimit = oversizedBuffer(DEFAULT_MAX_INLINE_BLOB_BYTES + 1);
    try {
      assertPayloadLimits({
        sidecars: [{ data: overLimit }],
      });
    } catch (error) {
      const transportError = error as JsonRpcTransportError;
      const raw = transportError.rawMessage as { diagnostics: unknown[] } | undefined;
      expect(raw?.diagnostics).toBeDefined();
      expect(Array.isArray(raw?.diagnostics)).toBe(true);
    }
  });
});
