import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { computeSHA256, fillMissingContentSHA256 } from '@/tools/video-editor/lib/sha256';
import { buildTimelineCommandData } from '@/tools/video-editor/commands/timelineData';
import { applyTimelineCommandEffect } from '@/tools/video-editor/commands/runner';
import {
  buildDataFromCurrentRegistry,
  buildDataFromSnapshot,
} from '@/tools/video-editor/lib/timeline-save-utils';
import { assembleTimelineData } from '@/tools/video-editor/lib/timeline-data';
import type {
  AssetRegistry,
  TimelineClip,
  TimelineConfig,
  TrackDefinition,
} from '@/tools/video-editor/types/index';

// ---------------------------------------------------------------------------
// Known-answer test vectors
// ---------------------------------------------------------------------------

const EMPTY_SHA256 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';

// Pre-computed: echo -n "hello world" | sha256sum
const HELLO_WORLD_BYTES = new TextEncoder().encode('hello world');
const HELLO_WORLD_SHA256 =
  'b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9';

describe('computeSHA256', () => {
  it('computes the SHA-256 of an empty blob', async () => {
    const blob = new Blob([], { type: 'application/octet-stream' });
    const hash = await computeSHA256(blob);
    expect(hash).toBe(EMPTY_SHA256);
  });

  it('computes the SHA-256 of a small blob (hello world)', async () => {
    const blob = new Blob([HELLO_WORLD_BYTES]);
    const hash = await computeSHA256(blob);
    expect(hash).toBe(HELLO_WORLD_SHA256);
  });

  it('computes the SHA-256 of a File object', async () => {
    const file = new File([HELLO_WORLD_BYTES], 'hello.txt', { type: 'text/plain' });
    const hash = await computeSHA256(file);
    expect(hash).toBe(HELLO_WORLD_SHA256);
  });

  it('returns a 64-character lowercase hex string', async () => {
    const blob = new Blob(['test']);
    const hash = await computeSHA256(blob);
    expect(hash).toHaveLength(64);
    expect(hash).toMatch(/^[0-9a-f]{64}$/);
  });

  it('handles a blob larger than one chunk (2.5 MiB)', async () => {
    // Create a 2.5 MiB blob — larger than the internal 1 MiB chunk size.
    const size = Math.ceil(2.5 * 1024 * 1024);
    const data = new Uint8Array(size);
    // Fill with a repeating pattern so the output is deterministic.
    for (let i = 0; i < size; i++) {
      data[i] = i % 251;
    }
    const blob = new Blob([data]);
    const hash = await computeSHA256(blob);
    expect(hash).toHaveLength(64);
    expect(hash).toMatch(/^[0-9a-f]{64}$/);

    // Verify determinism: two runs on the same data produce the same hash.
    const second = await computeSHA256(new Blob([data]));
    expect(hash).toBe(second);
  });

  it('produces different hashes for different content', async () => {
    const a = await computeSHA256(new Blob(['alpha']));
    const b = await computeSHA256(new Blob(['beta']));
    expect(a).not.toBe(b);
  });

  it('produces the same hash for the same content', async () => {
    const data = 'deterministic-content-' + Date.now();
    const a = await computeSHA256(new Blob([data]));
    const b = await computeSHA256(new Blob([data]));
    expect(a).toBe(b);
  });
});

// ---------------------------------------------------------------------------
// fillMissingContentSHA256
// ---------------------------------------------------------------------------

describe('fillMissingContentSHA256', () => {
  const mockFetch = vi.fn<(_url: string) => Promise<Response>>();

  beforeEach(() => {
    mockFetch.mockReset();
    vi.stubGlobal('fetch', mockFetch);
  });

  function mockBlobResponse(data: Uint8Array): Response {
    return {
      ok: true,
      blob: async () => new Blob([data]),
    } as unknown as Response;
  }

  function emptyRegistry(): AssetRegistry {
    return { assets: {} };
  }

  it('returns an empty registry unchanged', async () => {
    const result = await fillMissingContentSHA256(emptyRegistry());
    expect(result).toEqual({ assets: {} });
  });

  it('does not overwrite an existing content_sha256', async () => {
    const preExistingHash = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'; // 64 hex chars
    const registry: AssetRegistry = {
      assets: {
        'asset-a': {
          file: 'a.jpg',
          url: 'https://cdn.example.com/a.jpg',
          content_sha256: preExistingHash,
        },
      },
    };

    mockFetch.mockResolvedValue(mockBlobResponse(new Uint8Array([1, 2, 3])));
    const result = await fillMissingContentSHA256(registry);

    expect(result.assets['asset-a'].content_sha256).toBe(preExistingHash);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('fills a missing content_sha256 using entry.url', async () => {
    const registry: AssetRegistry = {
      assets: {
        'asset-b': {
          file: 'b.png',
          url: 'https://cdn.example.com/b.png',
        },
      },
    };

    mockFetch.mockResolvedValue(mockBlobResponse(HELLO_WORLD_BYTES));
    const result = await fillMissingContentSHA256(registry);

    expect(result.assets['asset-b'].content_sha256).toBe(HELLO_WORLD_SHA256);
    expect(mockFetch).toHaveBeenCalledWith('https://cdn.example.com/b.png');
  });

  it('fills a missing content_sha256 using entry.file when url is absent', async () => {
    const registry: AssetRegistry = {
      assets: {
        'asset-c': {
          file: 'c.mp3',
        },
      },
    };

    mockFetch.mockResolvedValue(mockBlobResponse(new TextEncoder().encode('audio-data')));
    const result = await fillMissingContentSHA256(registry);

    expect(result.assets['asset-c'].content_sha256).toHaveLength(64);
    expect(mockFetch).toHaveBeenCalledWith('c.mp3');
  });

  it('skips entries with no url and no file', async () => {
    const registry: AssetRegistry = {
      assets: {
        'orphan': {
          file: '',
        } as any,
      },
    };

    const result = await fillMissingContentSHA256(registry);
    expect(result.assets['orphan'].content_sha256).toBeUndefined();
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('handles multiple entries in a single pass', async () => {
    const registry: AssetRegistry = {
      assets: {
        'keep': {
          file: 'keep.png',
          url: 'https://cdn.example.com/keep.png',
          content_sha256: HELLO_WORLD_SHA256,
        },
        'fill': {
          file: 'fill.png',
          url: 'https://cdn.example.com/fill.png',
        },
        'also-fill': {
          file: 'also.mp4',
          url: 'https://cdn.example.com/also.mp4',
        },
      },
    };

    mockFetch.mockResolvedValue(mockBlobResponse(new Uint8Array([42])));

    const result = await fillMissingContentSHA256(registry);

    // Unchanged
    expect(result.assets['keep'].content_sha256).toBe(HELLO_WORLD_SHA256);

    // Filled
    expect(result.assets['fill'].content_sha256).toHaveLength(64);
    expect(result.assets['also-fill'].content_sha256).toHaveLength(64);

    // Both filled entries should have the same hash (same fetched content).
    expect(result.assets['fill'].content_sha256).toBe(
      result.assets['also-fill'].content_sha256,
    );

    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('preserves other entry fields after filling the hash', async () => {
    const registry: AssetRegistry = {
      assets: {
        'full': {
          file: 'full.mov',
          url: 'https://cdn.example.com/full.mov',
          type: 'video/quicktime',
          duration: 42,
          origin: 'immutable-public',
          generationId: 'gen-99',
        },
      },
    };

    mockFetch.mockResolvedValue(mockBlobResponse(HELLO_WORLD_BYTES));
    const result = await fillMissingContentSHA256(registry);

    const entry = result.assets['full'];
    expect(entry.file).toBe('full.mov');
    expect(entry.url).toBe('https://cdn.example.com/full.mov');
    expect(entry.type).toBe('video/quicktime');
    expect(entry.duration).toBe(42);
    expect(entry.origin).toBe('immutable-public');
    expect(entry.generationId).toBe('gen-99');
    expect(entry.content_sha256).toBe(HELLO_WORLD_SHA256);
  });

  it('does not mutate the original registry', async () => {
    const registry: AssetRegistry = {
      assets: {
        'immutable': {
          file: 'immutable.mp4',
          url: 'https://cdn.example.com/immutable.mp4',
        },
      },
    };

    mockFetch.mockResolvedValue(mockBlobResponse(new Uint8Array([7])));
    const result = await fillMissingContentSHA256(registry);

    // Original entry should NOT have content_sha256.
    expect(registry.assets['immutable'].content_sha256).toBeUndefined();

    // Result entry should.
    expect(result.assets['immutable'].content_sha256).toHaveLength(64);

    // Original and result should be different objects.
    expect(result).not.toBe(registry);
    expect(result.assets).not.toBe(registry.assets);
    expect(result.assets['immutable']).not.toBe(registry.assets['immutable']);
  });

  it('swallows fetch failures and leaves the entry unchanged', async () => {
    const registry: AssetRegistry = {
      assets: {
        'failing': {
          file: 'gone.jpg',
          url: 'https://cdn.example.com/gone.jpg',
        },
      },
    };

    mockFetch.mockRejectedValue(new Error('Network error'));
    const result = await fillMissingContentSHA256(registry);

    expect(result.assets['failing'].content_sha256).toBeUndefined();
  });

  it('swallows non-ok fetch responses', async () => {
    const registry: AssetRegistry = {
      assets: {
        'not-found': {
          file: 'missing.png',
          url: 'https://cdn.example.com/missing.png',
        },
      },
    };

    mockFetch.mockResolvedValue({
      ok: false,
      status: 404,
    } as Response);

    const result = await fillMissingContentSHA256(registry);
    expect(result.assets['not-found'].content_sha256).toBeUndefined();
  });

  it('uses a custom fetchBlob when provided', async () => {
    const registry: AssetRegistry = {
      assets: {
        'local': {
          file: 'local.bin',
        },
      },
    };

    const customBlob = new Blob([new Uint8Array([1, 2, 3, 4])]);
    const customFetch = vi.fn<(_url: string) => Promise<Blob | null>>().mockResolvedValue(customBlob);

    const result = await fillMissingContentSHA256(registry, { fetchBlob: customFetch });

    expect(customFetch).toHaveBeenCalledWith('local.bin');
    expect(result.assets['local'].content_sha256).toHaveLength(64);

    // Verify the hash matches what we'd expect for [1, 2, 3, 4].
    const expectedHash = await computeSHA256(customBlob);
    expect(result.assets['local'].content_sha256).toBe(expectedHash);
  });
});

// ---------------------------------------------------------------------------
// T9: Chunk-boundary correctness
// ---------------------------------------------------------------------------

describe('computeSHA256 chunk-boundary correctness', () => {
  function makePatternBlob(size: number, byteFn: (i: number) => number): Blob {
    const data = new Uint8Array(size);
    for (let i = 0; i < size; i++) {
      data[i] = byteFn(i);
    }
    return new Blob([data]);
  }

  // Compute a reference SHA-256 by reading the blob in chunks (same strategy
  // as computeSHA256) and then digesting the merged buffer.  This avoids
  // relying on blob.arrayBuffer() which can return a non-ArrayBuffer type in
  // some test environments.
  async function referenceSHA256(blob: Blob): Promise<string> {
    const CHUNK = 1024 * 1024;
    let offset = 0;
    const parts: Uint8Array[] = [];
    let total = 0;
    while (offset < blob.size) {
      const slice = blob.slice(offset, offset + CHUNK);
      const ab = await slice.arrayBuffer();
      const view = new Uint8Array(ab);
      parts.push(view);
      total += view.byteLength;
      offset += CHUNK;
    }
    const merged = new Uint8Array(total);
    let pos = 0;
    for (const p of parts) {
      merged.set(p, pos);
      pos += p.byteLength;
    }
    const hash = await crypto.subtle.digest('SHA-256', merged);
    return Array.from(new Uint8Array(hash))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
  }

  it('produces the same hash as a single-pass reference for a blob exactly at the chunk boundary (1 MiB)', async () => {
    const size = 1024 * 1024; // exactly 1 MiB
    const blob = makePatternBlob(size, (i) => i % 251);
    const chunkedHash = await computeSHA256(blob);
    const referenceHash = await referenceSHA256(blob);
    expect(chunkedHash).toBe(referenceHash);
  });

  it('produces the same hash as a single-pass reference for a blob just past the chunk boundary (1 MiB + 1 byte)', async () => {
    const size = 1024 * 1024 + 1; // one byte past 1 MiB
    const blob = makePatternBlob(size, (i) => (i * 7 + 13) % 251);
    const chunkedHash = await computeSHA256(blob);
    const referenceHash = await referenceSHA256(blob);
    expect(chunkedHash).toBe(referenceHash);
  });

  it('produces the same hash as a single-pass reference for multiple chunks (2 MiB + 500 bytes)', async () => {
    const size = 2 * 1024 * 1024 + 500;
    const blob = makePatternBlob(size, (i) => (i * 31 + 17) % 256);
    const chunkedHash = await computeSHA256(blob);
    const referenceHash = await referenceSHA256(blob);
    expect(chunkedHash).toBe(referenceHash);
  });

  it('produces the same hash as a single-pass reference for a blob smaller than one chunk (512 KiB)', async () => {
    const size = 512 * 1024;
    const blob = makePatternBlob(size, (i) => i % 256);
    const chunkedHash = await computeSHA256(blob);
    const referenceHash = await referenceSHA256(blob);
    expect(chunkedHash).toBe(referenceHash);
  });

  it('produces deterministic hashes across repeated chunked computations on the same data', async () => {
    const size = 1024 * 1024 + 777;
    const data = new Uint8Array(size);
    for (let i = 0; i < size; i++) {
      data[i] = (i * 5 + 3) % 256;
    }

    const hashes: string[] = [];
    for (let run = 0; run < 5; run++) {
      const blob = new Blob([data]);
      hashes.push(await computeSHA256(blob));
    }

    const first = hashes[0];
    for (const hash of hashes) {
      expect(hash).toBe(first);
    }
  });
});

// ---------------------------------------------------------------------------
// T9: Preparation workflow — filling missing hashes
// ---------------------------------------------------------------------------

describe('fillMissingContentSHA256 preparation workflow', () => {
  const mockFetch = vi.fn<(_url: string) => Promise<Response>>();

  beforeEach(() => {
    mockFetch.mockReset();
    vi.stubGlobal('fetch', mockFetch);
  });

  function mockBlobResponse(data: Uint8Array): Response {
    return {
      ok: true,
      blob: async () => new Blob([data]),
    } as unknown as Response;
  }

  it('fills hashes in a simulated publish-preparation pipeline (mix of filled and missing)', async () => {
    const preExistingHash = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
    const registry: AssetRegistry = {
      assets: {
        'fresh-1': {
          file: 'fresh-1.mp4',
          url: 'https://cdn.example.com/fresh-1.mp4',
          type: 'video/mp4',
          duration: 10,
        },
        'fresh-2': {
          file: 'fresh-2.jpg',
          url: 'https://cdn.example.com/fresh-2.jpg',
          type: 'image/jpeg',
        },
        'cached': {
          file: 'cached.mp4',
          url: 'https://cdn.example.com/cached.mp4',
          content_sha256: preExistingHash,
          type: 'video/mp4',
        },
        'orphan-no-url': {
          file: '',
        } as any,
      },
    };

    const responseData = new TextEncoder().encode('preparation-test-data');
    mockFetch.mockResolvedValue(mockBlobResponse(responseData));

    const result = await fillMissingContentSHA256(registry);

    // fresh-1 and fresh-2 should have hashes filled
    expect(result.assets['fresh-1'].content_sha256).toHaveLength(64);
    expect(result.assets['fresh-2'].content_sha256).toHaveLength(64);

    // cached should retain its pre-existing hash
    expect(result.assets['cached'].content_sha256).toBe(preExistingHash);

    // orphan should remain unchanged
    expect(result.assets['orphan-no-url'].content_sha256).toBeUndefined();

    // fresh-1 and fresh-2 should have the same hash (same fetched content)
    expect(result.assets['fresh-1'].content_sha256).toBe(
      result.assets['fresh-2'].content_sha256,
    );

    // Only 2 fetches should have been made (fresh-1, fresh-2)
    expect(mockFetch).toHaveBeenCalledTimes(2);

    // Original registry should not be mutated
    expect(registry.assets['fresh-1'].content_sha256).toBeUndefined();
    expect(registry.assets['fresh-2'].content_sha256).toBeUndefined();
  });

  it('can be called sequentially (fill-then-verify pattern)', async () => {
    const data1 = new TextEncoder().encode('first-pass');
    const data2 = new TextEncoder().encode('second-pass');

    const registry: AssetRegistry = {
      assets: {
        'a': { file: 'a.bin', url: 'https://cdn.example.com/a.bin' },
        'b': { file: 'b.bin', url: 'https://cdn.example.com/b.bin' },
      },
    };

    // First pass: resolve as data1
    mockFetch.mockResolvedValue(mockBlobResponse(data1));
    const firstPass = await fillMissingContentSHA256(registry);

    expect(firstPass.assets['a'].content_sha256).toHaveLength(64);
    expect(firstPass.assets['b'].content_sha256).toHaveLength(64);

    // Second pass: should not re-fetch since hashes are already filled
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(mockBlobResponse(data2));
    const secondPass = await fillMissingContentSHA256(firstPass);

    // Should not have called fetch again
    expect(mockFetch).not.toHaveBeenCalled();

    // Hashes should be identical to first pass
    expect(secondPass.assets['a'].content_sha256).toBe(firstPass.assets['a'].content_sha256);
    expect(secondPass.assets['b'].content_sha256).toBe(firstPass.assets['b'].content_sha256);
  });
});

// ---------------------------------------------------------------------------
// T9: Sync boundary — import/materialization/load must not hash synchronously
// ---------------------------------------------------------------------------

describe('sync boundary — no synchronous hashing in import/materialization/load', () => {
  let digestSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    digestSpy = vi.spyOn(crypto.subtle, 'digest');
  });

  afterEach(() => {
    digestSpy.mockRestore();
  });

  // -----------------------------------------------------------------------
  // Helpers to construct minimal TimelineData fixtures
  // -----------------------------------------------------------------------

  function makeTrack(id: string, kind: TrackDefinition['kind'] = 'visual'): TrackDefinition {
    return { id, kind, label: id, scale: 1, fit: 'manual', opacity: 1, blendMode: 'normal' };
  }

  function makeSnapshotTimelineData() {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [makeTrack('V1')],
      clips: [
        { id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 2 },
      ],
    };
    const registry: AssetRegistry = {
      assets: { 'asset-1': { file: 'img.png' } },
    };
    const resolvedRegistry = Object.fromEntries(
      Object.entries(registry.assets).map(([k, e]) => [k, { ...e, src: e.file }]),
    );
    const resolvedConfig = {
      output: { ...config.output },
      tracks: config.tracks ?? [],
      clips: config.clips.map((c) => ({
        ...c,
        assetEntry: c.asset ? resolvedRegistry[c.asset] : undefined,
      })),
      registry: resolvedRegistry,
    };
    return assembleTimelineData({
      config,
      configVersion: 1,
      registry,
      resolvedConfig: resolvedConfig as any,
      output: { ...config.output },
      assetMap: Object.fromEntries(
        Object.entries(registry.assets).map(([k, e]) => [k, e.file]),
      ),
    });
  }

  // -----------------------------------------------------------------------
  // Verify the hash helpers themselves are async-only
  // -----------------------------------------------------------------------

  it('computeSHA256 returns a Promise (never synchronously resolved)', () => {
    const blob = new Blob(['test']);
    const result = computeSHA256(blob);
    // Must be a genuine Promise
    expect(result).toBeInstanceOf(Promise);
    // crypto.subtle.digest must not have been called synchronously
    expect(digestSpy).not.toHaveBeenCalled();
  });

  it('fillMissingContentSHA256 returns a Promise', () => {
    const registry: AssetRegistry = {
      assets: { 'a': { file: 'a.bin', url: 'https://cdn.example.com/a.bin' } },
    };
    const result = fillMissingContentSHA256(registry);
    expect(result).toBeInstanceOf(Promise);
    // No synchronous digest call
    expect(digestSpy).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // buildTimelineCommandData (timeline load / import path)
  // -----------------------------------------------------------------------

  it('buildTimelineCommandData does not call crypto.subtle.digest synchronously', () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [makeTrack('V1')],
      clips: [
        { id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 2 },
      ],
    };
    const registry: AssetRegistry = {
      assets: {
        'asset-1': {
          file: 'img.png',
          url: 'https://cdn.example.com/img.png',
          content_sha256: undefined,
        },
      },
    };

    buildTimelineCommandData(config, registry);

    // Even though content_sha256 is undefined, the data-building path
    // must not eagerly compute hashes.
    expect(digestSpy).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // buildDataFromSnapshot (timeline load path)
  // -----------------------------------------------------------------------

  it('buildDataFromSnapshot does not call crypto.subtle.digest synchronously', () => {
    const current = makeSnapshotTimelineData();
    const snapshotRegistry: AssetRegistry = {
      assets: {
        'asset-2': {
          file: 'snapshot.mp4',
          url: 'https://cdn.example.com/snapshot.mp4',
          content_sha256: undefined,
          duration: 6,
        },
      },
    };
    const snapshotConfig: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'snap.mp4' },
      tracks: [makeTrack('V1')],
      clips: [
        { id: 'clip-2', at: 2, track: 'V1', clipType: 'media', asset: 'asset-2' },
      ],
    };

    buildDataFromSnapshot(snapshotConfig, snapshotRegistry, current);

    expect(digestSpy).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // buildDataFromCurrentRegistry (timeline load path)
  // -----------------------------------------------------------------------

  it('buildDataFromCurrentRegistry does not call crypto.subtle.digest synchronously', () => {
    const current = makeSnapshotTimelineData();
    const nextConfig: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'next.mp4' },
      tracks: [makeTrack('V1')],
      clips: [
        { id: 'clip-next', at: 1, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 4 },
      ],
    };

    buildDataFromCurrentRegistry(nextConfig, current);

    expect(digestSpy).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // applyTimelineCommandEffect (materialization path)
  // -----------------------------------------------------------------------

  it('applyTimelineCommandEffect does not call crypto.subtle.digest synchronously', () => {
    const current = makeSnapshotTimelineData();
    const clip: TimelineClip = {
      id: 'clip-1',
      at: 0,
      track: 'V1',
      clipType: 'hold',
      asset: 'asset-1',
      hold: 2,
    };

    const effect = {
      mutation: {
        type: 'rows' as const,
        rows: current.rows,
        metaUpdates: {
          'clip-1': { ...clip },
        },
      },
      summary: 'no-op test',
    };

    applyTimelineCommandEffect(current, effect);

    expect(digestSpy).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // assembleTimelineData (core data assembly path)
  // -----------------------------------------------------------------------

  it('assembleTimelineData does not call crypto.subtle.digest synchronously', () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [makeTrack('V1')],
      clips: [
        { id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', asset: 'asset-1', hold: 2 },
      ],
    };
    const registry: AssetRegistry = {
      assets: {
        'asset-1': {
          file: 'img.png',
          url: 'https://cdn.example.com/img.png',
          content_sha256: undefined,
        },
      },
    };
    const resolvedRegistry = Object.fromEntries(
      Object.entries(registry.assets).map(([k, e]) => [k, { ...e, src: e.file }]),
    );

    assembleTimelineData({
      config,
      configVersion: 1,
      registry,
      resolvedConfig: {
        output: { ...config.output },
        tracks: config.tracks ?? [],
        clips: config.clips.map((c) => ({
          ...c,
          assetEntry: c.asset ? resolvedRegistry[c.asset] : undefined,
        })),
        registry: resolvedRegistry,
      },
      output: { ...config.output },
      assetMap: Object.fromEntries(
        Object.entries(registry.assets).map(([k, e]) => [k, e.file]),
      ),
    });

    expect(digestSpy).not.toHaveBeenCalled();
  });
});
