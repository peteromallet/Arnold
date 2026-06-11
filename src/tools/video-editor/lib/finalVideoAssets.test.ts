import { describe, expect, it, vi } from 'vitest';
import { getDurationSecondsFromFinalVideoParams } from '@/tools/video-editor/lib/finalVideoAssets';
import {
  buildDerivedFromLink,
  buildDerivedAssetEntry,
  buildDerivedThumbnailAssetEntry,
  buildDerivedProxyAssetEntry,
  buildRenderOutputAssetEntry,
  upsertDerivedAsset,
} from '@/tools/video-editor/lib/derivedAssetRegistry';
import { fillMissingContentSHA256 } from '@/tools/video-editor/lib/sha256';

describe('getDurationSecondsFromFinalVideoParams', () => {
  it('reads direct duration_seconds from root params', () => {
    expect(getDurationSecondsFromFinalVideoParams({
      duration_seconds: 4.25,
    })).toBe(4.25);
  });

  it('prefers trimmed duration over original duration style fields', () => {
    expect(getDurationSecondsFromFinalVideoParams({
      original_duration: 9,
      trimmed_duration: 3.5,
    })).toBe(3.5);
  });

  it('reads nested metadata from orchestrator details', () => {
    expect(getDurationSecondsFromFinalVideoParams({
      orchestrator_details: {
        metadata: {
          duration_seconds: 6,
        },
      },
    })).toBe(6);
  });

  it('derives seconds from total_frames and frame_rate when needed', () => {
    expect(getDurationSecondsFromFinalVideoParams({
      full_orchestrator_payload: {
        total_frames: 96,
        frame_rate: 24,
      },
    })).toBe(4);
  });

  it('derives seconds from num_frames and fps_helpers for single-segment travel videos', () => {
    expect(getDurationSecondsFromFinalVideoParams({
      num_frames: 49,
      fps_helpers: 16,
    })).toBe(49 / 16);
  });

  it('derives seconds from segment_frames_expanded and fps_helpers when frame count is stored in arrays', () => {
    expect(getDurationSecondsFromFinalVideoParams({
      segment_frames_expanded: [50],
      fps_helpers: 20,
    })).toBe(2.5);
  });

  it('supports numeric strings from persisted JSON', () => {
    expect(getDurationSecondsFromFinalVideoParams({
      metadata: {
        duration_seconds: '5.75',
      },
    })).toBe(5.75);
  });

  it('returns null when params do not contain a usable duration', () => {
    expect(getDurationSecondsFromFinalVideoParams({
      prompt: 'no duration here',
    })).toBeNull();
  });
});

describe('derived asset registry helpers', () => {
  it('creates a thumbnail-derived entry and updates thumbnailUrl without changing the source identity', () => {
    const registry = {
      assets: {
        source: {
          file: 'clips/source.mp4',
          type: 'video/mp4',
          generationId: 'gen-source',
          content_sha256: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
        },
      },
    };

    const nextRegistry = upsertDerivedAsset(registry, {
      derivedAssetId: 'source-thumb',
      sourceAssetId: 'source',
      role: 'thumbnail',
      displayUrl: 'https://cdn.example.com/source-thumb.jpg',
      entry: {
        file: 'derived/source-thumb.jpg',
        url: 'https://cdn.example.com/source-thumb.jpg',
        type: 'image/jpeg',
        origin: 'opaque-foreign',
      },
    });

    expect(nextRegistry.assets.source).toEqual({
      file: 'clips/source.mp4',
      type: 'video/mp4',
      generationId: 'gen-source',
      content_sha256: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
      thumbnailUrl: 'https://cdn.example.com/source-thumb.jpg',
    });
    expect(nextRegistry.assets['source-thumb']).toEqual({
      file: 'derived/source-thumb.jpg',
      url: 'https://cdn.example.com/source-thumb.jpg',
      type: 'image/jpeg',
      origin: 'opaque-foreign',
      derivedFrom: {
        assetId: 'source',
        content_sha256: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
        role: 'thumbnail',
      },
    });
  });

  it('uses an explicitly prepared parent hash for render-output linkage when the source entry has not been filled yet', () => {
    const entry = buildRenderOutputAssetEntry({
      sourceAssetId: 'source',
      sourceEntry: {
        file: 'clips/source.mp4',
        type: 'video/mp4',
      },
      parentContentSha256: 'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789',
      entry: {
        file: 'output/hype.mp4',
        type: 'video/mp4',
        origin: 'opaque-foreign',
      },
    });

    expect(entry).toEqual({
      file: 'output/hype.mp4',
      type: 'video/mp4',
      origin: 'opaque-foreign',
      derivedFrom: {
        assetId: 'source',
        content_sha256: 'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789',
        role: 'render-output',
      },
    });
  });

  it('fills a missing parent hash during preparation before creating a render-output link', async () => {
    const registry = {
      assets: {
        source: {
          file: 'clips/source.mp4',
          url: 'https://cdn.example.com/source.mp4',
          type: 'video/mp4',
        },
      },
    };
    const fetchBlob = vi.fn(async () => new Blob(['source-video-bytes'], { type: 'video/mp4' }));

    const preparedRegistry = await fillMissingContentSHA256(registry, { fetchBlob });
    const entry = buildRenderOutputAssetEntry({
      sourceAssetId: 'source',
      sourceEntry: preparedRegistry.assets.source,
      entry: {
        file: 'output/hype.mp4',
        type: 'video/mp4',
        origin: 'opaque-foreign',
      },
    });

    expect(fetchBlob).toHaveBeenCalledWith('https://cdn.example.com/source.mp4');
    expect(preparedRegistry.assets.source.content_sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(entry.derivedFrom).toEqual({
      assetId: 'source',
      content_sha256: preparedRegistry.assets.source.content_sha256,
      role: 'render-output',
    });
  });

  it('builds thumbnail-derived metadata without requiring a registry clone when only the entry payload is needed', () => {
    expect(buildDerivedThumbnailAssetEntry({
      sourceAssetId: 'source',
      sourceEntry: {
        file: 'clips/source.mp4',
        type: 'video/mp4',
        content_sha256: 'fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210',
      },
      entry: {
        file: 'derived/source-thumb.jpg',
        type: 'image/jpeg',
      },
    })).toEqual({
      file: 'derived/source-thumb.jpg',
      type: 'image/jpeg',
      derivedFrom: {
        assetId: 'source',
        content_sha256: 'fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210',
        role: 'thumbnail',
      },
    });
  });

  // ---------------------------------------------------------------------------
  // Non-thumbnail roles do NOT write thumbnailUrl onto the source entry
  // ---------------------------------------------------------------------------

  it('upsert with proxy role does not set thumbnailUrl on source', () => {
    const registry = {
      assets: {
        source: {
          file: 'clips/source.mp4',
          type: 'video/mp4',
          content_sha256: 'aaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccdddd',
        },
      },
    };

    const nextRegistry = upsertDerivedAsset(registry, {
      derivedAssetId: 'source-proxy',
      sourceAssetId: 'source',
      role: 'proxy',
      entry: {
        file: 'derived/source-proxy-480p.mp4',
        url: 'https://cdn.example.com/source-proxy-480p.mp4',
        type: 'video/mp4',
        origin: 'opaque-foreign',
      },
    });

    // Source identity is preserved, no thumbnailUrl is set
    expect(nextRegistry.assets.source).toEqual({
      file: 'clips/source.mp4',
      type: 'video/mp4',
      content_sha256: 'aaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccdddd',
    });
    // Derived entry has correct linkage
    expect(nextRegistry.assets['source-proxy']).toEqual({
      file: 'derived/source-proxy-480p.mp4',
      url: 'https://cdn.example.com/source-proxy-480p.mp4',
      type: 'video/mp4',
      origin: 'opaque-foreign',
      derivedFrom: {
        assetId: 'source',
        content_sha256: 'aaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccdddd',
        role: 'proxy',
      },
    });
  });

  it('upsert with render-output role does not set thumbnailUrl on source', () => {
    const registry = {
      assets: {
        source: {
          file: 'clips/source.mp4',
          type: 'video/mp4',
        },
      },
    };

    const nextRegistry = upsertDerivedAsset(registry, {
      derivedAssetId: 'final-render',
      sourceAssetId: 'source',
      parentContentSha256: 'deadbeef0123456789deadbeef0123456789deadbeef0123456789deadbeef0123456789',
      role: 'render-output',
      entry: {
        file: 'output/hype.mp4',
        type: 'video/mp4',
        origin: 'opaque-foreign',
      },
    });

    // Source identity preserved, no thumbnailUrl
    expect(nextRegistry.assets.source).toEqual({
      file: 'clips/source.mp4',
      type: 'video/mp4',
    });
    expect(nextRegistry.assets['final-render']).toEqual({
      file: 'output/hype.mp4',
      type: 'video/mp4',
      origin: 'opaque-foreign',
      derivedFrom: {
        assetId: 'source',
        content_sha256: 'deadbeef0123456789deadbeef0123456789deadbeef0123456789deadbeef0123456789',
        role: 'render-output',
      },
    });
  });

  // ---------------------------------------------------------------------------
  // Source-not-found guard
  // ---------------------------------------------------------------------------

  it('throws when the source asset does not exist in the registry', () => {
    const registry = {
      assets: {
        other: {
          file: 'clips/other.mp4',
          type: 'video/mp4',
        },
      },
    };

    expect(() => upsertDerivedAsset(registry, {
      derivedAssetId: 'ghost-thumb',
      sourceAssetId: 'ghost',
      role: 'thumbnail',
      entry: {
        file: 'derived/ghost-thumb.jpg',
        type: 'image/jpeg',
      },
    })).toThrow(/Cannot register derived asset 'ghost-thumb' without source asset 'ghost'/);
  });

  // ---------------------------------------------------------------------------
  // Parent-hash resolution: source hash, explicit override, neither present
  // ---------------------------------------------------------------------------

  it('resolves parent content_sha256 from source entry when no explicit hash is given', () => {
    const entry = buildDerivedProxyAssetEntry({
      sourceAssetId: 'source',
      sourceEntry: {
        file: 'clips/source.mp4',
        type: 'video/mp4',
        content_sha256: '1111222233334444111122223333444411112222333344441111222233334444',
      },
      entry: {
        file: 'derived/source-proxy.mp4',
        type: 'video/mp4',
      },
    });

    expect(entry.derivedFrom).toEqual({
      assetId: 'source',
      content_sha256: '1111222233334444111122223333444411112222333344441111222233334444',
      role: 'proxy',
    });
  });

  it('omits content_sha256 from derivedFrom when neither source hash nor explicit hash is available', () => {
    const entry = buildDerivedProxyAssetEntry({
      sourceAssetId: 'source',
      sourceEntry: {
        file: 'clips/source.mp4',
        type: 'video/mp4',
        // no content_sha256
      },
      entry: {
        file: 'derived/source-proxy.mp4',
        type: 'video/mp4',
      },
    });

    expect(entry.derivedFrom).toEqual({
      assetId: 'source',
      role: 'proxy',
    });
    expect(entry.derivedFrom).not.toHaveProperty('content_sha256');
  });

  it('explicit parentContentSha256 takes precedence over source entry hash', () => {
    const entry = buildRenderOutputAssetEntry({
      sourceAssetId: 'source',
      sourceEntry: {
        file: 'clips/source.mp4',
        type: 'video/mp4',
        content_sha256: '9999888877776666999988887777666699998888777766669999888877776666',
      },
      parentContentSha256: 'aaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccdddd',
      entry: {
        file: 'output/hype.mp4',
        type: 'video/mp4',
      },
    });

    expect(entry.derivedFrom).toEqual({
      assetId: 'source',
      content_sha256: 'aaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccdddd',
      role: 'render-output',
    });
  });

  it('buildDerivedFromLink omits content_sha256 when sourceEntry has no hash and no explicit hash', () => {
    const link = buildDerivedFromLink({
      sourceAssetId: 'source',
      sourceEntry: {
        file: 'clips/source.mp4',
        type: 'video/mp4',
      },
      role: 'proxy',
    });

    expect(link).toEqual({
      assetId: 'source',
      role: 'proxy',
    });
    expect(link).not.toHaveProperty('content_sha256');
  });

  it('buildDerivedFromLink with explicit null parentContentSha256 and no source hash omits content_sha256', () => {
    const link = buildDerivedFromLink({
      sourceAssetId: 'source',
      sourceEntry: {
        file: 'clips/source.mp4',
        type: 'video/mp4',
      },
      parentContentSha256: null,
      role: 'thumbnail',
    });

    expect(link).toEqual({
      assetId: 'source',
      role: 'thumbnail',
    });
    expect(link).not.toHaveProperty('content_sha256');
  });

  // ---------------------------------------------------------------------------
  // Multiple derived entries from the same source
  // ---------------------------------------------------------------------------

  it('allows multiple derived entries from the same source (proxy + render-output)', () => {
    let registry = {
      assets: {
        source: {
          file: 'clips/source.mp4',
          type: 'video/mp4',
          content_sha256: 'aaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccdddd',
        },
      },
    };

    registry = upsertDerivedAsset(registry, {
      derivedAssetId: 'source-proxy',
      sourceAssetId: 'source',
      role: 'proxy',
      entry: {
        file: 'derived/source-proxy.mp4',
        type: 'video/mp4',
        origin: 'opaque-foreign',
      },
    });

    registry = upsertDerivedAsset(registry, {
      derivedAssetId: 'source-thumb',
      sourceAssetId: 'source',
      role: 'thumbnail',
      displayUrl: 'https://cdn.example.com/source-thumb.jpg',
      entry: {
        file: 'derived/source-thumb.jpg',
        url: 'https://cdn.example.com/source-thumb.jpg',
        type: 'image/jpeg',
        origin: 'opaque-foreign',
      },
    });

    // Source still has identity fields plus thumbnailUrl from the thumbnail upsert
    expect(registry.assets.source).toEqual({
      file: 'clips/source.mp4',
      type: 'video/mp4',
      content_sha256: 'aaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccdddd',
      thumbnailUrl: 'https://cdn.example.com/source-thumb.jpg',
    });
    expect(registry.assets['source-proxy'].derivedFrom).toEqual({
      assetId: 'source',
      content_sha256: 'aaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccdddd',
      role: 'proxy',
    });
    expect(registry.assets['source-thumb'].derivedFrom).toEqual({
      assetId: 'source',
      content_sha256: 'aaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccdddd',
      role: 'thumbnail',
    });
  });

  // ---------------------------------------------------------------------------
  // Thumbnail displayUrl fallback behavior
  // ---------------------------------------------------------------------------

  it('upsert thumbnail falls back to entry.url when displayUrl is not provided', () => {
    const registry = {
      assets: {
        source: {
          file: 'clips/source.mp4',
          type: 'video/mp4',
        },
      },
    };

    const nextRegistry = upsertDerivedAsset(registry, {
      derivedAssetId: 'source-thumb',
      sourceAssetId: 'source',
      role: 'thumbnail',
      entry: {
        file: 'derived/source-thumb.jpg',
        url: 'https://cdn.example.com/source-thumb.jpg',
        type: 'image/jpeg',
        origin: 'opaque-foreign',
      },
    });

    expect(nextRegistry.assets.source.thumbnailUrl).toBe('https://cdn.example.com/source-thumb.jpg');
  });

  it('upsert thumbnail with neither displayUrl nor entry.url does not set thumbnailUrl on source', () => {
    const registry = {
      assets: {
        source: {
          file: 'clips/source.mp4',
          type: 'video/mp4',
        },
      },
    };

    const nextRegistry = upsertDerivedAsset(registry, {
      derivedAssetId: 'source-thumb',
      sourceAssetId: 'source',
      role: 'thumbnail',
      entry: {
        file: 'derived/source-thumb.jpg',
        type: 'image/jpeg',
        origin: 'opaque-foreign',
      },
    });

    expect(nextRegistry.assets.source).toEqual({
      file: 'clips/source.mp4',
      type: 'video/mp4',
    });
  });
});
