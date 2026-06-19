import { describe, expect, it } from 'vitest';
import {
  runParserPreflight,
  orderParsers,
  mergeParserMetadata,
  runAllParsers,
  findMatchingParser,
  preflightAllParsers,
  checkRejectedOutputFields,
  PARSER_DIAGNOSTIC_CODES,
} from './assetParserRuntime';
import type { VideoEditorAssetParserDescriptor } from '../runtime/extensionSurface';
import type {
  ParserHandler,
  ParserInput,
  ParserResult,
  ParserDiagnostic,
} from '@reigh/editor-sdk';
import type {
  AssetRegistryEntry,
} from '../types/index.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const makeParser = (
  overrides: Partial<VideoEditorAssetParserDescriptor> = {},
): VideoEditorAssetParserDescriptor => ({
  id: 'test.parser',
  extensionId: 'test.ext',
  order: 0,
  label: 'Test Parser',
  ...overrides,
});

const makePreflightInput = (
  overrides: Partial<{
    mimeType: string;
    extension: string;
    byteSize: number;
    filename: string;
  }> = {},
) => ({
  mimeType: 'image/jpeg',
  extension: 'jpg',
  byteSize: 1024,
  ...overrides,
});

const makeRegistryEntry = (
  overrides: Partial<AssetRegistryEntry> = {},
): AssetRegistryEntry => ({
  file: 'test.jpg',
  ...overrides,
});

const noopHandler: ParserHandler = (_input: ParserInput): ParserResult => ({});

// ---------------------------------------------------------------------------
// runParserPreflight
// ---------------------------------------------------------------------------

describe('runParserPreflight', () => {
  describe('size check', () => {
    it('returns oversized diagnostic when byteSize exceeds maxBytes', () => {
      const parser = makeParser({ maxBytes: 100 });
      const input = makePreflightInput({ byteSize: 200 });

      const diag = runParserPreflight(parser, input);

      expect(diag).not.toBeNull();
      expect(diag!.code).toBe(PARSER_DIAGNOSTIC_CODES.OVERSIZED_INPUT);
      expect(diag!.severity).toBe('error');
      expect(diag!.detail).toEqual({
        byteSize: 200,
        maxBytes: 100,
        parserId: 'test.parser',
      });
    });

    it('returns null when byteSize is within maxBytes', () => {
      const parser = makeParser({ maxBytes: 1000 });
      const input = makePreflightInput({ byteSize: 500 });

      const diag = runParserPreflight(parser, input);

      expect(diag).toBeNull();
    });

    it('returns null when maxBytes is undefined (no limit)', () => {
      const parser = makeParser({ maxBytes: undefined });
      const input = makePreflightInput({ byteSize: 10_000_000 });

      const diag = runParserPreflight(parser, input);

      expect(diag).toBeNull();
    });

    it('returns null when maxBytes is 0 (treats as no limit)', () => {
      const parser = makeParser({ maxBytes: 0 });
      const input = makePreflightInput({ byteSize: 10_000_000 });

      const diag = runParserPreflight(parser, input);

      expect(diag).toBeNull();
    });
  });

  describe('MIME type check', () => {
    it('accepts exact MIME match', () => {
      const parser = makeParser({ acceptMimeTypes: ['image/jpeg'] });
      const input = makePreflightInput({ mimeType: 'image/jpeg' });

      expect(runParserPreflight(parser, input)).toBeNull();
    });

    it('accepts wildcard subtype match', () => {
      const parser = makeParser({ acceptMimeTypes: ['image/*'] });
      const input = makePreflightInput({ mimeType: 'image/png' });

      expect(runParserPreflight(parser, input)).toBeNull();
    });

    it('accepts wildcard full match', () => {
      const parser = makeParser({ acceptMimeTypes: ['*/*'] });
      const input = makePreflightInput({ mimeType: 'application/octet-stream' });

      expect(runParserPreflight(parser, input)).toBeNull();
    });

    it('rejects non-matching MIME type', () => {
      const parser = makeParser({ acceptMimeTypes: ['image/jpeg', 'image/png'] });
      const input = makePreflightInput({ mimeType: 'video/mp4' });

      const diag = runParserPreflight(parser, input);
      expect(diag).not.toBeNull();
      expect(diag!.code).toBe(PARSER_DIAGNOSTIC_CODES.UNSUPPORTED_TYPE);
      expect(diag!.severity).toBe('info');
      expect(diag!.message).toContain('MIME type');
    });

    it('is case-insensitive for MIME types', () => {
      const parser = makeParser({ acceptMimeTypes: ['Image/JPEG'] });
      const input = makePreflightInput({ mimeType: 'image/jpeg' });

      expect(runParserPreflight(parser, input)).toBeNull();
    });
  });

  describe('extension check', () => {
    it('accepts matching extension', () => {
      const parser = makeParser({ acceptExtensions: ['jpg', 'jpeg'] });
      const input = makePreflightInput({ extension: 'jpg' });

      expect(runParserPreflight(parser, input)).toBeNull();
    });

    it('rejects non-matching extension', () => {
      const parser = makeParser({ acceptExtensions: ['jpg', 'jpeg'] });
      const input = makePreflightInput({ extension: 'png' });

      const diag = runParserPreflight(parser, input);
      expect(diag).not.toBeNull();
      expect(diag!.code).toBe(PARSER_DIAGNOSTIC_CODES.UNSUPPORTED_TYPE);
      expect(diag!.message).toContain('extension');
    });

    it('is case-insensitive for extensions', () => {
      const parser = makeParser({ acceptExtensions: ['JPG'] });
      const input = makePreflightInput({ extension: 'jpg' });

      expect(runParserPreflight(parser, input)).toBeNull();
    });

    it('strips leading dot from accepted and input extensions', () => {
      const parser = makeParser({ acceptExtensions: ['.jpg'] });
      const input = makePreflightInput({ extension: '.jpg' });

      expect(runParserPreflight(parser, input)).toBeNull();
    });
  });

  describe('combined MIME + extension check', () => {
    it('requires both MIME and extension to match when both are declared', () => {
      const parser = makeParser({
        acceptMimeTypes: ['image/jpeg'],
        acceptExtensions: ['jpg'],
      });

      // Both match
      expect(runParserPreflight(parser, makePreflightInput({
        mimeType: 'image/jpeg',
        extension: 'jpg',
      }))).toBeNull();

      // Only MIME matches
      const mimeOnly = runParserPreflight(parser, makePreflightInput({
        mimeType: 'image/jpeg',
        extension: 'png',
      }));
      expect(mimeOnly).not.toBeNull();
      expect(mimeOnly!.code).toBe(PARSER_DIAGNOSTIC_CODES.UNSUPPORTED_TYPE);

      // Only extension matches
      const extOnly = runParserPreflight(parser, makePreflightInput({
        mimeType: 'video/mp4',
        extension: 'jpg',
      }));
      expect(extOnly).not.toBeNull();
      expect(extOnly!.code).toBe(PARSER_DIAGNOSTIC_CODES.UNSUPPORTED_TYPE);
    });
  });

  describe('no accept filters', () => {
    it('accepts any file when no accept lists are declared', () => {
      const parser = makeParser({});
      const input = makePreflightInput({ mimeType: 'application/zip', extension: 'zip', byteSize: 10_000 });

      expect(runParserPreflight(parser, input)).toBeNull();
    });

    it('still checks size even when no accept filters', () => {
      const parser = makeParser({ maxBytes: 100 });
      const input = makePreflightInput({ byteSize: 200 });

      const diag = runParserPreflight(parser, input);
      expect(diag).not.toBeNull();
      expect(diag!.code).toBe(PARSER_DIAGNOSTIC_CODES.OVERSIZED_INPUT);
    });
  });
});

// ---------------------------------------------------------------------------
// checkRejectedOutputFields
// ---------------------------------------------------------------------------

describe('checkRejectedOutputFields', () => {
  it('returns null when metadata has only known keys', () => {
    const result = checkRejectedOutputFields(
      { integrity: { sha256: 'abc' } },
      'test.parser',
      'test.ext',
    );
    expect(result).toBeNull();
  });

  it('returns diagnostic when metadata has unknown keys', () => {
    const result = checkRejectedOutputFields(
      { unknownField: 'value', integrity: { sha256: 'abc' } },
      'test.parser',
      'test.ext',
    );
    expect(result).not.toBeNull();
    expect(result!.code).toBe(PARSER_DIAGNOSTIC_CODES.REJECTED_OUTPUT_FIELDS);
    expect(result!.severity).toBe('warning');
    expect(result!.detail?.rejectedFields).toContain('unknownField');
  });

  it('returns null for undefined metadata', () => {
    expect(checkRejectedOutputFields(undefined, 'test.parser', 'test.ext')).toBeNull();
  });

  it('returns null for empty metadata', () => {
    expect(checkRejectedOutputFields({}, 'test.parser', 'test.ext')).toBeNull();
  });

  it('recognizes all known keys: integrity, gps, consent, provenance, enrichment, extensions', () => {
    const result = checkRejectedOutputFields(
      {
        integrity: {},
        gps: {},
        consent: {},
        provenance: {},
        enrichment: {},
        extensions: {},
      },
      'test.parser',
      'test.ext',
    );
    expect(result).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// orderParsers
// ---------------------------------------------------------------------------

describe('orderParsers', () => {
  it('returns empty array when no handlers are registered', () => {
    const parsers: VideoEditorAssetParserDescriptor[] = [
      makeParser({ id: 'p1', extensionId: 'ext1' }),
    ];
    const handlerMap = new Map<string, ParserHandler>();
    const extensionOrder = new Map([['ext1', 0]]);

    expect(orderParsers(parsers, handlerMap, extensionOrder)).toEqual([]);
  });

  it('returns only parsers with registered handlers', () => {
    const p1 = makeParser({ id: 'p1', extensionId: 'ext1' });
    const p2 = makeParser({ id: 'p2', extensionId: 'ext2' });
    const parsers = [p1, p2];
    const handlerMap = new Map<string, ParserHandler>([
      ['p1', noopHandler],
    ]);
    const extensionOrder = new Map([['ext1', 0], ['ext2', 1]]);

    const ordered = orderParsers(parsers, handlerMap, extensionOrder);
    expect(ordered).toHaveLength(1);
    expect(ordered[0].descriptor.id).toBe('p1');
  });

  it('orders by extension order first, then contribution order, then ID', () => {
    const p1 = makeParser({ id: 'p1', extensionId: 'ext2', order: 0 });
    const p2 = makeParser({ id: 'p2', extensionId: 'ext1', order: 100 });
    const p3 = makeParser({ id: 'p3', extensionId: 'ext1', order: 0 });
    const parsers = [p1, p2, p3];
    const handlerMap = new Map<string, ParserHandler>([
      ['p1', noopHandler],
      ['p2', noopHandler],
      ['p3', noopHandler],
    ]);
    const extensionOrder = new Map([['ext1', 0], ['ext2', 1]]);

    const ordered = orderParsers(parsers, handlerMap, extensionOrder);
    // ext1 (order 0): p3 (order 0) then p2 (order 100)
    // ext2 (order 1): p1 (order 0)
    expect(ordered.map((p) => p.descriptor.id)).toEqual(['p3', 'p2', 'p1']);
  });

  it('uses ID as tiebreaker', () => {
    const p1 = makeParser({ id: 'b-parser', extensionId: 'ext1', order: 0 });
    const p2 = makeParser({ id: 'a-parser', extensionId: 'ext1', order: 0 });
    const parsers = [p1, p2];
    const handlerMap = new Map<string, ParserHandler>([
      ['b-parser', noopHandler],
      ['a-parser', noopHandler],
    ]);
    const extensionOrder = new Map([['ext1', 0]]);

    const ordered = orderParsers(parsers, handlerMap, extensionOrder);
    expect(ordered.map((p) => p.descriptor.id)).toEqual(['a-parser', 'b-parser']);
  });

  it('handles extension not in extensionOrder (sorts last)', () => {
    const p1 = makeParser({ id: 'p1', extensionId: 'ext1' });
    const p2 = makeParser({ id: 'p2', extensionId: 'ext-unknown' });
    const parsers = [p1, p2];
    const handlerMap = new Map<string, ParserHandler>([
      ['p1', noopHandler],
      ['p2', noopHandler],
    ]);
    const extensionOrder = new Map([['ext1', 0]]);

    const ordered = orderParsers(parsers, handlerMap, extensionOrder);
    expect(ordered.map((p) => p.descriptor.id)).toEqual(['p1', 'p2']);
  });
});

// ---------------------------------------------------------------------------
// mergeParserMetadata
// ---------------------------------------------------------------------------

describe('mergeParserMetadata', () => {
  it('preserves blessed registry fields from existing entry', () => {
    const entry = makeRegistryEntry({
      file: 'test.jpg',
      url: 'https://example.com/test.jpg',
      type: 'image/jpeg',
      duration: 10,
    });

    const merged = mergeParserMetadata(entry, []);

    expect(merged.entry.file).toBe('test.jpg');
    expect(merged.entry.url).toBe('https://example.com/test.jpg');
    expect(merged.entry.type).toBe('image/jpeg');
    expect(merged.entry.duration).toBe(10);
    expect(merged.diagnostics).toEqual([]);
  });

  it('strips unknown registry entry fields not in the blessed allowlist', () => {
    const entry = {
      file: 'test.jpg',
      unknownField: 'should-be-stripped',
    } as unknown as AssetRegistryEntry;

    const merged = mergeParserMetadata(entry, []);

    expect(merged.entry.file).toBe('test.jpg');
    // @ts-expect-error verify unknown field is stripped
    expect(merged.entry.unknownField).toBeUndefined();
  });

  it('merges host-owned metadata fields shallowly (later overwrites earlier)', () => {
    const entry = makeRegistryEntry({
      metadata: {
        gps: { latitude: 10, longitude: 20 },
        integrity: { sha256: 'aaa' },
      },
    });

    const results = [
      {
        result: { metadata: { gps: { altitude: 100 } } },
        parserId: 'p1',
        extensionId: 'ext1',
      },
      {
        result: { metadata: { gps: { latitude: 50 } } },
        parserId: 'p2',
        extensionId: 'ext2',
      },
    ];

    const merged = mergeParserMetadata(entry, results);

    // Later parser (p2) overwrites latitude but altitude from p1 is preserved
    expect(merged.entry.metadata?.gps).toEqual({
      latitude: 50,
      longitude: 20,
      altitude: 100,
    });
    // integrity from original entry is preserved
    expect(merged.entry.metadata?.integrity).toEqual({ sha256: 'aaa' });
  });

  it('namespace-aware merges extension metadata', () => {
    const entry = makeRegistryEntry({
      metadata: {
        extensions: {
          'ext1': { tags: ['old'], score: 0.5 },
        },
      },
    });

    const results = [
      {
        result: {
          metadata: {
            extensions: {
              'ext1': { tags: ['new'], verified: true },
              'ext2': { data: 'ext2-data' },
            },
          },
        },
        parserId: 'p1',
        extensionId: 'ext1',
      },
    ];

    const merged = mergeParserMetadata(entry, results);

    // ext1 is shallow-merged: new tags overwrite old tags, new verified field added, score preserved
    expect(merged.entry.metadata?.extensions).toEqual({
      'ext1': { tags: ['new'], score: 0.5, verified: true },
      'ext2': { data: 'ext2-data' },
    });
  });

  it('produces rejected output fields diagnostic for unknown metadata keys', () => {
    const entry = makeRegistryEntry();

    const results = [
      {
        result: {
          metadata: {
            bogusField: 'should-not-be-here',
            integrity: { sha256: 'abc' },
          },
        },
        parserId: 'p1',
        extensionId: 'ext1',
      },
    ];

    const merged = mergeParserMetadata(entry, results);

    expect(merged.diagnostics).toHaveLength(1);
    expect(merged.diagnostics[0].code).toBe(PARSER_DIAGNOSTIC_CODES.REJECTED_OUTPUT_FIELDS);
    expect(merged.diagnostics[0].detail?.rejectedFields).toContain('bogusField');

    // integrity is still merged
    expect(merged.entry.metadata?.integrity).toEqual({ sha256: 'abc' });
  });

  it('validates final metadata through validateAssetMetadata', () => {
    const entry = makeRegistryEntry();

    const results = [
      {
        result: {
          metadata: {
            gps: { latitude: 'not-a-number', longitude: Infinity },
          },
        },
        parserId: 'p1',
        extensionId: 'ext1',
      },
    ];

    const merged = mergeParserMetadata(entry, results);

    // Invalid GPS fields are stripped by validateAssetMetadata
    expect(merged.entry.metadata?.gps).toBeUndefined();
  });

  it('handles empty parser results gracefully', () => {
    const entry = makeRegistryEntry({ file: 'test.jpg' });

    const merged = mergeParserMetadata(entry, []);

    expect(merged.entry.file).toBe('test.jpg');
    expect(merged.entry.metadata).toBeUndefined();
    expect(merged.diagnostics).toEqual([]);
  });

  it('handles parser results with no metadata', () => {
    const entry = makeRegistryEntry({
      metadata: { gps: { latitude: 1 } },
    });

    const results = [
      {
        result: {},
        parserId: 'p1',
        extensionId: 'ext1',
      },
    ];

    const merged = mergeParserMetadata(entry, results);

    expect(merged.entry.metadata?.gps).toEqual({ latitude: 1 });
    expect(merged.diagnostics).toEqual([]);
  });

  it('converts SDK-style enrichment array to host shape', () => {
    const entry = makeRegistryEntry();

    const results = [
      {
        result: {
          metadata: {
            enrichment: [
              { id: 'r1', extensionId: 'ext1', kind: 'caption', createdAt: '2025-01-01T00:00:00Z' },
              { id: 'r2', extensionId: 'ext1', kind: 'embedding', createdAt: '2025-01-02T00:00:00Z' },
            ],
          } as unknown as ParserResult['metadata'],
        },
        parserId: 'p1',
        extensionId: 'ext1',
      },
    ];

    const merged = mergeParserMetadata(entry, results);

    expect(merged.entry.metadata?.enrichment).toBeDefined();
    if (merged.entry.metadata?.enrichment) {
      expect(merged.entry.metadata.enrichment.claims).toHaveLength(2);
      expect(merged.entry.metadata.enrichment.claims?.[0].claimId).toBe('r1');
      expect(merged.entry.metadata.enrichment.claims?.[1].claimId).toBe('r2');
      expect(merged.entry.metadata.enrichment.pending).toBe(2);
      expect(merged.entry.metadata.enrichment.failed).toBe(0);
    }
  });

  it('filters invalid extension namespace keys', () => {
    const entry = makeRegistryEntry();

    const results = [
      {
        result: {
          metadata: {
            extensions: {
              '': 'empty-key',
              'InvalidWithCapital': 'capital',
              'valid.ext': { data: true },
            },
          },
        },
        parserId: 'p1',
        extensionId: 'ext1',
      },
    ];

    const merged = mergeParserMetadata(entry, results);

    // Only 'valid.ext' should survive (matches extension ID pattern)
    expect(merged.entry.metadata?.extensions).toBeDefined();
    const exts = merged.entry.metadata?.extensions ?? {};
    expect(Object.keys(exts)).toContain('valid.ext');
    expect(Object.keys(exts)).not.toContain('');
    expect(Object.keys(exts)).not.toContain('InvalidWithCapital');
  });
});

// ---------------------------------------------------------------------------
// runAllParsers
// ---------------------------------------------------------------------------

describe('runAllParsers', () => {
  it('returns the existing entry unchanged when no parsers', async () => {
    const entry = makeRegistryEntry({ file: 'test.jpg' });

    const result = await runAllParsers(
      [],
      makePreflightInput(),
      entry,
      'asset-1',
    );

    expect(result.entry.file).toBe('test.jpg');
    expect(result.diagnostics).toEqual([]);
    expect(result.blocked).toBe(false);
  });

  it('invokes matching parsers and merges their results', async () => {
    const handler: ParserHandler = (_input: ParserInput): ParserResult => ({
      metadata: { gps: { latitude: 42 } },
    });

    const parsers = [
      {
        descriptor: makeParser({ id: 'p1', extensionId: 'ext1', acceptMimeTypes: ['image/jpeg'] }),
        handler,
      },
    ];

    const result = await runAllParsers(
      parsers,
      makePreflightInput({ mimeType: 'image/jpeg' }),
      makeRegistryEntry({ file: 'test.jpg' }),
      'asset-1',
    );

    expect(result.entry.metadata?.gps).toEqual({ latitude: 42 });
    expect(result.blocked).toBe(false);
  });

  it('skips parsers that do not match preflight', async () => {
    let invoked = false;
    const handler: ParserHandler = (_input: ParserInput): ParserResult => {
      invoked = true;
      return {};
    };

    const parsers = [
      {
        descriptor: makeParser({ id: 'p1', extensionId: 'ext1', acceptMimeTypes: ['image/png'] }),
        handler,
      },
    ];

    const result = await runAllParsers(
      parsers,
      makePreflightInput({ mimeType: 'image/jpeg', extension: 'jpg' }),
      makeRegistryEntry(),
      'asset-1',
    );

    expect(invoked).toBe(false);
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].code).toBe(PARSER_DIAGNOSTIC_CODES.UNSUPPORTED_TYPE);
  });

  it('catches parser exceptions and emits parser/exception diagnostic', async () => {
    const handler: ParserHandler = (_input: ParserInput): ParserResult => {
      throw new Error('Parser crash');
    };

    const parsers = [
      {
        descriptor: makeParser({ id: 'p1', extensionId: 'ext1' }),
        handler,
      },
    ];

    const result = await runAllParsers(
      parsers,
      makePreflightInput(),
      makeRegistryEntry(),
      'asset-1',
    );

    const exceptionDiag = result.diagnostics.find(
      (d) => d.code === PARSER_DIAGNOSTIC_CODES.PARSER_EXCEPTION,
    );
    expect(exceptionDiag).toBeDefined();
    expect(exceptionDiag!.severity).toBe('error');
    expect(exceptionDiag!.message).toContain('Parser crash');
    expect(result.blocked).toBe(false); // not required, so not blocked
  });

  it('blocks ingestion when a required parser throws', async () => {
    const handler: ParserHandler = (_input: ParserInput): ParserResult => {
      throw new Error('Required crash');
    };

    const parsers = [
      {
        descriptor: makeParser({ id: 'p1', extensionId: 'ext1', required: true }),
        handler,
      },
    ];

    const result = await runAllParsers(
      parsers,
      makePreflightInput(),
      makeRegistryEntry(),
      'asset-1',
    );

    expect(result.blocked).toBe(true);
    const blockingDiag = result.diagnostics.find(
      (d) => d.code === PARSER_DIAGNOSTIC_CODES.REQUIRED_PARSER_FAILURE,
    );
    expect(blockingDiag).toBeDefined();
  });

  it('blocks ingestion when a required parser returns blocking errors', async () => {
    const handler: ParserHandler = (_input: ParserInput): ParserResult => ({
      diagnostics: [{ severity: 'error', code: 'parser/custom-error', message: 'Bad data' }],
    });

    const parsers = [
      {
        descriptor: makeParser({ id: 'p1', extensionId: 'ext1', required: true }),
        handler,
      },
    ];

    const result = await runAllParsers(
      parsers,
      makePreflightInput(),
      makeRegistryEntry(),
      'asset-1',
    );

    expect(result.blocked).toBe(true);
  });

  it('does NOT block when a non-required parser throws', async () => {
    const handler: ParserHandler = (_input: ParserInput): ParserResult => {
      throw new Error('Non-required crash');
    };

    const parsers = [
      {
        descriptor: makeParser({ id: 'p1', extensionId: 'ext1', required: false }),
        handler,
      },
    ];

    const result = await runAllParsers(
      parsers,
      makePreflightInput(),
      makeRegistryEntry(),
      'asset-1',
    );

    expect(result.blocked).toBe(false);
  });

  it('passes accumulated metadata to later parsers', async () => {
    const handler1: ParserHandler = (_input: ParserInput): ParserResult => ({
      metadata: { gps: { latitude: 10 } },
    });

    let receivedGps: unknown;
    const handler2: ParserHandler = (input: ParserInput): ParserResult => {
      receivedGps = (input.existingMetadata as Record<string, unknown>)?.gps;
      return { metadata: { gps: { longitude: 20 } } };
    };

    const parsers = [
      { descriptor: makeParser({ id: 'p1', extensionId: 'ext1', order: 0 }), handler: handler1 },
      { descriptor: makeParser({ id: 'p2', extensionId: 'ext1', order: 1 }), handler: handler2 },
    ];

    await runAllParsers(
      parsers,
      makePreflightInput(),
      makeRegistryEntry(),
      'asset-1',
    );

    expect(receivedGps).toBeDefined();
    expect((receivedGps as Record<string, unknown>)?.latitude).toBe(10);
  });

  it('blocks when required parser fails preflight with unsupported type', async () => {
    const handler: ParserHandler = () => ({});

    const parsers = [
      {
        descriptor: makeParser({
          id: 'p1',
          extensionId: 'ext1',
          required: true,
          acceptMimeTypes: ['image/png'],
        }),
        handler,
      },
    ];

    const result = await runAllParsers(
      parsers,
      makePreflightInput({ mimeType: 'image/jpeg' }),
      makeRegistryEntry(),
      'asset-1',
    );

    expect(result.blocked).toBe(true);
    expect(
      result.diagnostics.some((d) => d.code === PARSER_DIAGNOSTIC_CODES.REQUIRED_PARSER_FAILURE),
    ).toBe(true);
  });

  it('blocks when required parser fails preflight with oversized input', async () => {
    const handler: ParserHandler = () => ({});

    const parsers = [
      {
        descriptor: makeParser({ id: 'p1', extensionId: 'ext1', required: true, maxBytes: 100 }),
        handler,
      },
    ];

    const result = await runAllParsers(
      parsers,
      makePreflightInput({ byteSize: 200 }),
      makeRegistryEntry(),
      'asset-1',
    );

    expect(result.blocked).toBe(true);
  });

  it('supports async parser handlers', async () => {
    const handler: ParserHandler = async (_input: ParserInput): Promise<ParserResult> => {
      return { metadata: { gps: { latitude: 99 } } };
    };

    const parsers = [
      {
        descriptor: makeParser({ id: 'p1', extensionId: 'ext1' }),
        handler,
      },
    ];

    const result = await runAllParsers(
      parsers,
      makePreflightInput(),
      makeRegistryEntry(),
      'asset-1',
    );

    expect(result.entry.metadata?.gps?.latitude).toBe(99);
  });

  it('emits rejected output fields diagnostic via merge', async () => {
    const handler: ParserHandler = (_input: ParserInput): ParserResult => ({
      metadata: {
        bogus: 'nope',
        integrity: { sha256: 'abc' },
      } as unknown as ParserResult['metadata'],
    });

    const parsers = [
      {
        descriptor: makeParser({ id: 'p1', extensionId: 'ext1' }),
        handler,
      },
    ];

    const result = await runAllParsers(
      parsers,
      makePreflightInput(),
      makeRegistryEntry(),
      'asset-1',
    );

    const rejectedDiag = result.diagnostics.find(
      (d) => d.code === PARSER_DIAGNOSTIC_CODES.REJECTED_OUTPUT_FIELDS,
    );
    expect(rejectedDiag).toBeDefined();
    // bogus is stripped, integrity is merged
    expect(result.entry.metadata?.integrity?.sha256).toBe('abc');
  });
});

// ---------------------------------------------------------------------------
// findMatchingParser
// ---------------------------------------------------------------------------

describe('findMatchingParser', () => {
  it('returns undefined when no parser matches', () => {
    const parsers = [
      makeParser({ id: 'p1', acceptMimeTypes: ['image/png'] }),
    ];

    expect(findMatchingParser(parsers, makePreflightInput({ mimeType: 'image/jpeg' }))).toBeUndefined();
  });

  it('returns the first matching parser', () => {
    const parsers = [
      makeParser({ id: 'p1', acceptMimeTypes: ['image/png'] }),
      makeParser({ id: 'p2', acceptMimeTypes: ['image/*'] }),
    ];

    const found = findMatchingParser(parsers, makePreflightInput({ mimeType: 'image/jpeg' }));
    expect(found).toBeDefined();
    expect(found!.id).toBe('p2');
  });
});

// ---------------------------------------------------------------------------
// preflightAllParsers
// ---------------------------------------------------------------------------

describe('preflightAllParsers', () => {
  it('separates matching parsers from diagnostics', () => {
    const parsers = [
      makeParser({ id: 'p1', acceptMimeTypes: ['image/png'] }),
      makeParser({ id: 'p2', acceptMimeTypes: ['image/*'] }),
    ];

    const result = preflightAllParsers(parsers, makePreflightInput({ mimeType: 'image/jpeg' }));

    expect(result.matchingParsers).toHaveLength(1);
    expect(result.matchingParsers[0].id).toBe('p2');
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].code).toBe(PARSER_DIAGNOSTIC_CODES.UNSUPPORTED_TYPE);
    expect(result.diagnostics[0].contributionId).toBe('p1');
  });
});

// ---------------------------------------------------------------------------
// Parser diagnostic codes
// ---------------------------------------------------------------------------

describe('PARSER_DIAGNOSTIC_CODES', () => {
  it('all codes use the parser/ prefix', () => {
    for (const code of Object.values(PARSER_DIAGNOSTIC_CODES)) {
      expect(code).toMatch(/^parser\//);
    }
  });

  it('covers all required diagnostic types', () => {
    const codes = Object.values(PARSER_DIAGNOSTIC_CODES);
    expect(codes).toContain('parser/unsupported-type');
    expect(codes).toContain('parser/oversized-input');
    expect(codes).toContain('parser/exception');
    expect(codes).toContain('parser/required-parser-failure');
    expect(codes).toContain('parser/rejected-output-fields');
  });
});
