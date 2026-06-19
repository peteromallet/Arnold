import { describe, expect, it } from 'vitest';
import { validateAssetMetadata } from '@/tools/video-editor/lib/assetMetadata';
import { sanitizeAssetRegistryEntry } from '@/tools/video-editor/lib/timeline-domain';
import type { AssetRegistryEntry } from '@/tools/video-editor/types/index.ts';

// ---------------------------------------------------------------------------
// validateAssetMetadata
// ---------------------------------------------------------------------------

describe('validateAssetMetadata', () => {
  // -- GPS ----------------------------------------------------------------

  describe('gps', () => {
    it('accepts a complete GPS object with all fields', () => {
      const result = validateAssetMetadata({
        gps: {
          latitude: 37.7749,
          longitude: -122.4194,
          altitude: 10,
          horizontalAccuracy: 5,
          timestamp: '2025-06-15T10:30:00Z',
        },
      });
      expect(result).toBeDefined();
      expect(result!.gps).toEqual({
        latitude: 37.7749,
        longitude: -122.4194,
        altitude: 10,
        horizontalAccuracy: 5,
        timestamp: '2025-06-15T10:30:00Z',
      });
    });

    it('accepts GPS with only latitude and longitude', () => {
      const result = validateAssetMetadata({
        gps: { latitude: 0, longitude: 0 },
      });
      expect(result).toBeDefined();
      expect(result!.gps).toEqual({ latitude: 0, longitude: 0 });
    });

    it('rejects GPS when value is not a plain object', () => {
      const result = validateAssetMetadata({ gps: 'not-an-object' });
      expect(result).toBeUndefined();
    });

    it('rejects GPS with non-finite numbers (NaN, Infinity)', () => {
      const result = validateAssetMetadata({
        gps: { latitude: NaN, longitude: Infinity },
      });
      expect(result).toBeUndefined();
    });

    it('accepts GPS with valid latitude but invalid longitude and still keeps latitude', () => {
      const result = validateAssetMetadata({
        gps: { latitude: 45, longitude: 'bad' },
      });
      expect(result).toBeDefined();
      expect(result!.gps).toEqual({ latitude: 45 });
    });

    it('rejects GPS with only timestamp (no coordinate)', () => {
      const result = validateAssetMetadata({
        gps: { timestamp: '2025-06-15T10:30:00Z' },
      });
      expect(result).toBeDefined();
      expect(result!.gps).toEqual({ timestamp: '2025-06-15T10:30:00Z' });
    });

    it('rejects GPS when all fields are invalid types', () => {
      const result = validateAssetMetadata({
        gps: {
          latitude: 'string',
          longitude: null,
          altitude: true,
        },
      });
      expect(result).toBeUndefined();
    });
  });

  // -- Integrity ----------------------------------------------------------

  describe('integrity', () => {
    it('accepts a complete integrity object with sha256, md5, crc32', () => {
      const result = validateAssetMetadata({
        integrity: {
          sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
          md5: 'd41d8cd98f00b204e9800998ecf8427e',
          crc32: '00000000',
        },
      });
      expect(result).toBeDefined();
      expect(result!.integrity).toEqual({
        sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        md5: 'd41d8cd98f00b204e9800998ecf8427e',
        crc32: '00000000',
      });
    });

    it('accepts integrity with only sha256', () => {
      const result = validateAssetMetadata({
        integrity: {
          sha256: 'abc123',
        },
      });
      expect(result).toBeDefined();
      expect(result!.integrity).toEqual({ sha256: 'abc123' });
    });

    it('rejects integrity when value is not a plain object', () => {
      const result = validateAssetMetadata({ integrity: null });
      expect(result).toBeUndefined();
    });

    it('rejects integrity with empty strings as hash values', () => {
      const result = validateAssetMetadata({
        integrity: { sha256: '', md5: '' },
      });
      expect(result).toBeUndefined();
    });

    it('rejects integrity with non-string hash values', () => {
      const result = validateAssetMetadata({
        integrity: { sha256: 12345 },
      });
      expect(result).toBeUndefined();
    });
  });

  // -- Consent ------------------------------------------------------------

  describe('consent', () => {
    it('accepts a complete consent object', () => {
      const result = validateAssetMetadata({
        consent: {
          modelRelease: true,
          propertyRelease: false,
          rightsHolder: 'John Doe',
          license: 'CC-BY-4.0',
          usageTerms: 'editorial only',
        },
      });
      expect(result).toBeDefined();
      expect(result!.consent).toEqual({
        modelRelease: true,
        propertyRelease: false,
        rightsHolder: 'John Doe',
        license: 'CC-BY-4.0',
        usageTerms: 'editorial only',
      });
    });

    it('accepts consent with only booleans', () => {
      const result = validateAssetMetadata({
        consent: { modelRelease: false },
      });
      expect(result).toBeDefined();
      expect(result!.consent).toEqual({ modelRelease: false });
    });

    it('rejects consent when value is an array', () => {
      const result = validateAssetMetadata({ consent: [] });
      expect(result).toBeUndefined();
    });

    it('rejects consent when all fields are invalid', () => {
      const result = validateAssetMetadata({
        consent: { modelRelease: 'yes', propertyRelease: 1 },
      });
      expect(result).toBeUndefined();
    });

    it('accepts consent with only string fields', () => {
      const result = validateAssetMetadata({
        consent: { rightsHolder: 'ACME Corp', license: 'Proprietary' },
      });
      expect(result).toBeDefined();
      expect(result!.consent).toEqual({
        rightsHolder: 'ACME Corp',
        license: 'Proprietary',
      });
    });
  });

  // -- Provenance ---------------------------------------------------------

  describe('provenance', () => {
    it('accepts a complete provenance object', () => {
      const result = validateAssetMetadata({
        provenance: {
          importTimestamp: '2026-01-01T00:00:00Z',
          sourceUrl: 'https://example.com/asset.jpg',
          sourceProvider: 'unsplash',
          importedBy: 'user-42',
          originalFilename: 'DSC_0001.jpg',
        },
      });
      expect(result).toBeDefined();
      expect(result!.provenance).toEqual({
        importTimestamp: '2026-01-01T00:00:00Z',
        sourceUrl: 'https://example.com/asset.jpg',
        sourceProvider: 'unsplash',
        importedBy: 'user-42',
        originalFilename: 'DSC_0001.jpg',
      });
    });

    it('accepts provenance with only importTimestamp', () => {
      const result = validateAssetMetadata({
        provenance: { importTimestamp: '2026-01-01T00:00:00Z' },
      });
      expect(result).toBeDefined();
      expect(result!.provenance).toEqual({ importTimestamp: '2026-01-01T00:00:00Z' });
    });

    it('rejects provenance when value is not a plain object', () => {
      const result = validateAssetMetadata({ provenance: 'string' });
      expect(result).toBeUndefined();
    });

    it('rejects provenance with empty string values', () => {
      const result = validateAssetMetadata({
        provenance: { sourceUrl: '', sourceProvider: '' },
      });
      expect(result).toBeUndefined();
    });
  });

  // -- Enrichment (deferred records, claims, pending/failed counts) ------

  describe('enrichment', () => {
    it('accepts enrichment with pending and failed counts', () => {
      const result = validateAssetMetadata({
        enrichment: { pending: 3, failed: 1 },
      });
      expect(result).toBeDefined();
      expect(result!.enrichment).toEqual({ pending: 3, failed: 1 });
    });

    it('accepts enrichment with a single claim', () => {
      const result = validateAssetMetadata({
        enrichment: {
          claims: [
            {
              claimId: 'claim-001',
              parserId: 'exif-parser',
              timestamp: '2026-06-15T12:00:00Z',
              field: 'gps',
              summary: 'Extracted GPS from EXIF',
            },
          ],
        },
      });
      expect(result).toBeDefined();
      expect(result!.enrichment!.claims).toHaveLength(1);
      expect(result!.enrichment!.claims![0]).toEqual({
        claimId: 'claim-001',
        parserId: 'exif-parser',
        timestamp: '2026-06-15T12:00:00Z',
        field: 'gps',
        summary: 'Extracted GPS from EXIF',
      });
    });

    it('accepts enrichment with multiple claims', () => {
      const result = validateAssetMetadata({
        enrichment: {
          claims: [
            {
              claimId: 'claim-001',
              parserId: 'exif-parser',
              timestamp: '2026-06-15T12:00:00Z',
            },
            {
              claimId: 'claim-002',
              parserId: 'color-analyzer',
              timestamp: '2026-06-15T12:01:00Z',
              field: 'dominantColor',
              summary: 'rgb(120,80,200)',
            },
          ],
        },
      });
      expect(result).toBeDefined();
      expect(result!.enrichment!.claims).toHaveLength(2);
      expect(result!.enrichment!.claims![0].claimId).toBe('claim-001');
      expect(result!.enrichment!.claims![1].claimId).toBe('claim-002');
    });

    it('filters out invalid claims and keeps valid ones', () => {
      const result = validateAssetMetadata({
        enrichment: {
          claims: [
            { claimId: 'ok', parserId: 'p1', timestamp: 't1' },
            { parserId: 'p2', timestamp: 't2' }, // missing claimId
            { claimId: '', parserId: 'p3', timestamp: 't3' }, // empty claimId
            null,
            'not-an-object',
          ],
        },
      });
      expect(result).toBeDefined();
      expect(result!.enrichment!.claims).toHaveLength(1);
      expect(result!.enrichment!.claims![0].claimId).toBe('ok');
    });

    it('accepts enrichment with pending, failed, and claims combined', () => {
      const result = validateAssetMetadata({
        enrichment: {
          pending: 5,
          failed: 2,
          claims: [
            {
              claimId: 'claim-001',
              parserId: 'metadata-parser',
              timestamp: '2026-06-19T12:00:00Z',
              field: 'search/keywords',
              summary: 'sunset, mountains, lake',
            },
          ],
        },
      });
      expect(result).toBeDefined();
      expect(result!.enrichment).toEqual({
        pending: 5,
        failed: 2,
        claims: [
          {
            claimId: 'claim-001',
            parserId: 'metadata-parser',
            timestamp: '2026-06-19T12:00:00Z',
            field: 'search/keywords',
            summary: 'sunset, mountains, lake',
          },
        ],
      });
    });

    it('rejects enrichment with negative pending count', () => {
      const result = validateAssetMetadata({
        enrichment: { pending: -1 },
      });
      expect(result).toBeUndefined();
    });

    it('rejects enrichment with negative failed count', () => {
      const result = validateAssetMetadata({
        enrichment: { failed: -5 },
      });
      expect(result).toBeUndefined();
    });

    it('rejects enrichment when value is not a plain object', () => {
      const result = validateAssetMetadata({ enrichment: 42 });
      expect(result).toBeUndefined();
    });

    it('rejects enrichment when all claims are invalid', () => {
      const result = validateAssetMetadata({
        enrichment: {
          claims: [
            { claimId: '', parserId: '', timestamp: '' },
          ],
        },
      });
      expect(result).toBeUndefined();
    });
  });

  // -- Extensions namespace ------------------------------------------------

  describe('extensions', () => {
    it('accepts extension metadata under extensions[extensionId]', () => {
      const result = validateAssetMetadata({
        extensions: {
          'com.example.color-analyzer': {
            dominantColor: 'rgb(120,80,200)',
            palette: ['#ff0000', '#00ff00', '#0000ff'],
            score: 0.95,
          },
        },
      });
      expect(result).toBeDefined();
      expect(result!.extensions).toEqual({
        'com.example.color-analyzer': {
          dominantColor: 'rgb(120,80,200)',
          palette: ['#ff0000', '#00ff00', '#0000ff'],
          score: 0.95,
        },
      });
    });

    it('accepts multiple extension namespaces', () => {
      const result = validateAssetMetadata({
        extensions: {
          'ext-a': { value: 1 },
          'ext-b': { value: 2, nested: { deep: true } },
        },
      });
      expect(result).toBeDefined();
      expect(result!.extensions).toEqual({
        'ext-a': { value: 1 },
        'ext-b': { value: 2, nested: { deep: true } },
      });
    });

    it('strips extension entries with undefined values', () => {
      const result = validateAssetMetadata({
        extensions: {
          'ext-a': { value: 1 },
          'ext-b': undefined,
          'ext-c': { value: 3 },
        },
      });
      expect(result).toBeDefined();
      expect(result!.extensions).toEqual({
        'ext-a': { value: 1 },
        'ext-c': { value: 3 },
      });
    });

    it('strips extension entries with empty string keys', () => {
      const result = validateAssetMetadata({
        extensions: {
          '': { value: 'bad-key' },
          'valid': { value: 'ok' },
        },
      });
      expect(result).toBeDefined();
      expect(Object.keys(result!.extensions!)).not.toContain('');
      expect(result!.extensions).toEqual({ valid: { value: 'ok' } });
    });

    it('rejects extensions when value is an array', () => {
      const result = validateAssetMetadata({ extensions: [1, 2, 3] });
      expect(result).toBeUndefined();
    });

    it('returns undefined when extensions has only undefined values', () => {
      const result = validateAssetMetadata({
        extensions: {
          'ext-a': undefined,
        },
      });
      expect(result).toBeUndefined();
    });

    it('preserves complex nested structures in extension metadata', () => {
      const result = validateAssetMetadata({
        extensions: {
          'com.example.ai-tagger': {
            tags: ['portrait', 'outdoor', 'golden-hour'],
            confidence: { portrait: 0.92, outdoor: 0.87 },
            model: { name: 'tagger-v2', version: '1.0.0' },
            metadata: { processingTimeMs: 150 },
          },
        },
      });
      expect(result).toBeDefined();
      expect(result!.extensions!['com.example.ai-tagger']).toEqual({
        tags: ['portrait', 'outdoor', 'golden-hour'],
        confidence: { portrait: 0.92, outdoor: 0.87 },
        model: { name: 'tagger-v2', version: '1.0.0' },
        metadata: { processingTimeMs: 150 },
      });
    });
  });

  // -- Unknown top-level mutation rejection -------------------------------

  describe('unknown top-level key rejection', () => {
    it('silently strips unknown top-level keys', () => {
      const result = validateAssetMetadata({
        gps: { latitude: 10, longitude: 20 },
        unknownField: 'should be stripped',
        anotherUnknown: { nested: true },
      });
      expect(result).toBeDefined();
      expect(result!.gps).toEqual({ latitude: 10, longitude: 20 });
      expect(Object.keys(result!)).not.toContain('unknownField');
      expect(Object.keys(result!)).not.toContain('anotherUnknown');
      expect(Object.keys(result!).sort()).toEqual(['gps']);
    });

    it('rejects an object with only unknown keys', () => {
      const result = validateAssetMetadata({
        customField: 'value',
        anotherCustom: 42,
      });
      expect(result).toBeUndefined();
    });

    it('rejects unknown keys even when a known key is also present but empty', () => {
      const result = validateAssetMetadata({
        integrity: '', // invalid — not a plain object
        customField: 'value',
      });
      expect(result).toBeUndefined();
    });
  });

  // -- Combined shapes ----------------------------------------------------

  describe('combined metadata shapes', () => {
    it('accepts metadata with multiple known host fields', () => {
      const result = validateAssetMetadata({
        gps: { latitude: 48.8566, longitude: 2.3522 },
        integrity: { sha256: 'abc123' },
        consent: { modelRelease: true },
        provenance: { sourceProvider: 'pexels' },
        enrichment: { pending: 2 },
        extensions: { 'ext.test': { foo: 'bar' } },
      });
      expect(result).toBeDefined();
      expect(result!.gps).toBeDefined();
      expect(result!.integrity).toBeDefined();
      expect(result!.consent).toBeDefined();
      expect(result!.provenance).toBeDefined();
      expect(result!.enrichment).toBeDefined();
      expect(result!.extensions).toBeDefined();
      expect(Object.keys(result!).sort()).toEqual([
        'consent',
        'enrichment',
        'extensions',
        'gps',
        'integrity',
        'provenance',
      ]);
    });

    it('accepts metadata with only extensions and enrichment (search/related materials)', () => {
      const result = validateAssetMetadata({
        enrichment: {
          claims: [
            {
              claimId: 'search-001',
              parserId: 'keyword-extractor',
              timestamp: '2026-06-19T00:00:00Z',
              field: 'search/keywords',
              summary: 'landscape,nature,mountains',
            },
          ],
        },
        extensions: {
          'com.example.related': {
            relatedAssets: ['asset-1', 'asset-2'],
            similarityScores: { 'asset-1': 0.85, 'asset-2': 0.72 },
          },
        },
      });
      expect(result).toBeDefined();
      expect(result!.enrichment!.claims![0].field).toBe('search/keywords');
      expect(result!.extensions!['com.example.related'].relatedAssets).toEqual([
        'asset-1',
        'asset-2',
      ]);
    });
  });

  // -- Edge cases ---------------------------------------------------------

  describe('edge cases', () => {
    it('returns undefined for non-plain-object input (null)', () => {
      expect(validateAssetMetadata(null)).toBeUndefined();
    });

    it('returns undefined for non-plain-object input (array)', () => {
      expect(validateAssetMetadata([1, 2, 3])).toBeUndefined();
    });

    it('returns undefined for non-plain-object input (string)', () => {
      expect(validateAssetMetadata('hello')).toBeUndefined();
    });

    it('returns undefined for non-plain-object input (number)', () => {
      expect(validateAssetMetadata(42)).toBeUndefined();
    });

    it('returns undefined for non-plain-object input (undefined)', () => {
      expect(validateAssetMetadata(undefined)).toBeUndefined();
    });

    it('returns undefined for an empty object', () => {
      expect(validateAssetMetadata({})).toBeUndefined();
    });
  });
});

// ---------------------------------------------------------------------------
// sanitizeAssetRegistryEntry (registry sanitization)
// ---------------------------------------------------------------------------

describe('sanitizeAssetRegistryEntry', () => {
  const baseEntry: AssetRegistryEntry = {
    file: 'assets/photo.jpg',
    type: 'image/jpeg',
    duration: 5,
    resolution: '1920x1080',
    fps: 30,
    origin: 'immutable-public',
  };

  it('preserves known registry fields unchanged', () => {
    const result = sanitizeAssetRegistryEntry(baseEntry);
    expect(result.file).toBe('assets/photo.jpg');
    expect(result.type).toBe('image/jpeg');
    expect(result.duration).toBe(5);
    expect(result.resolution).toBe('1920x1080');
    expect(result.fps).toBe(30);
    expect(result.origin).toBe('immutable-public');
  });

  it('sanitizes metadata through validateAssetMetadata', () => {
    const entry: AssetRegistryEntry = {
      ...baseEntry,
      metadata: {
        gps: { latitude: 40.7128, longitude: -74.006 },
        integrity: { sha256: 'def456' },
        unknownTopLevel: 'should-be-stripped',
      },
    };
    const result = sanitizeAssetRegistryEntry(entry);
    expect(result.metadata).toBeDefined();
    expect(result.metadata!.gps).toEqual({ latitude: 40.7128, longitude: -74.006 });
    expect(result.metadata!.integrity).toEqual({ sha256: 'def456' });
    expect(Object.keys(result.metadata!)).not.toContain('unknownTopLevel');
  });

  it('strips metadata when it fails validation entirely', () => {
    const entry: AssetRegistryEntry = {
      ...baseEntry,
      metadata: { unknownField: 'value' } as any,
    };
    const result = sanitizeAssetRegistryEntry(entry);
    expect(result.metadata).toBeUndefined();
  });

  it('strips undefined metadata', () => {
    const entry: AssetRegistryEntry = {
      ...baseEntry,
      metadata: undefined,
    };
    const result = sanitizeAssetRegistryEntry(entry);
    expect(result.metadata).toBeUndefined();
  });

  it('preserves extension metadata under extensions namespace through sanitization', () => {
    const entry: AssetRegistryEntry = {
      ...baseEntry,
      metadata: {
        extensions: {
          'com.example.analyzer': {
            score: 0.88,
            tags: ['outdoor', 'sunny'],
          },
        },
      },
    };
    const result = sanitizeAssetRegistryEntry(entry);
    expect(result.metadata).toBeDefined();
    expect(result.metadata!.extensions).toEqual({
      'com.example.analyzer': {
        score: 0.88,
        tags: ['outdoor', 'sunny'],
      },
    });
  });

  it('preserves enrichment claims through sanitization (deferred enrichment records)', () => {
    const entry: AssetRegistryEntry = {
      ...baseEntry,
      metadata: {
        enrichment: {
          pending: 1,
          claims: [
            {
              claimId: 'deferred-001',
              parserId: 'slow-parser',
              timestamp: '2026-06-19T12:00:00Z',
            },
          ],
        },
      },
    };
    const result = sanitizeAssetRegistryEntry(entry);
    expect(result.metadata).toBeDefined();
    expect(result.metadata!.enrichment).toEqual({
      pending: 1,
      claims: [
        {
          claimId: 'deferred-001',
          parserId: 'slow-parser',
          timestamp: '2026-06-19T12:00:00Z',
        },
      ],
    });
  });

  it('preserves all host-owned metadata facets through sanitization', () => {
    const entry: AssetRegistryEntry = {
      ...baseEntry,
      metadata: {
        gps: { latitude: 51.5074, longitude: -0.1278 },
        integrity: { sha256: 'aaa', md5: 'bbb' },
        consent: { modelRelease: true, rightsHolder: 'Alice' },
        provenance: { sourceProvider: 'custom', originalFilename: 'img.png' },
        enrichment: {
          claims: [
            {
              claimId: 'c1',
              parserId: 'p1',
              timestamp: 't1',
              field: 'search/keywords',
              summary: 'london, bridge',
            },
          ],
        },
        extensions: {
          'ext.related': { materials: ['doc-1.pdf', 'doc-2.pdf'] },
        },
      },
    };
    const result = sanitizeAssetRegistryEntry(entry);
    expect(result.metadata).toBeDefined();
    expect(result.metadata!.gps).toBeDefined();
    expect(result.metadata!.integrity).toBeDefined();
    expect(result.metadata!.consent).toBeDefined();
    expect(result.metadata!.provenance).toBeDefined();
    expect(result.metadata!.enrichment).toBeDefined();
    expect(result.metadata!.extensions).toBeDefined();
    // Six known keys, nothing else
    expect(Object.keys(result.metadata!).sort()).toEqual([
      'consent',
      'enrichment',
      'extensions',
      'gps',
      'integrity',
      'provenance',
    ]);
  });

  it('strips fields not in ASSET_REGISTRY_ENTRY_FIELDS', () => {
    const entry = {
      ...baseEntry,
      extraField: 'should-be-stripped',
      anotherExtra: 123,
    } as any;
    const result = sanitizeAssetRegistryEntry(entry);
    expect((result as any).extraField).toBeUndefined();
    expect((result as any).anotherExtra).toBeUndefined();
    // Known fields preserved
    expect(result.file).toBe('assets/photo.jpg');
    expect(result.type).toBe('image/jpeg');
  });

  it('handles empty entry gracefully', () => {
    const result = sanitizeAssetRegistryEntry({ file: 'x' });
    expect(result.file).toBe('x');
  });
});
