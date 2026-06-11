import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock('@/integrations/supabase/repositories/generationRepository.ts', () => ({
  fetchGenerationRecordById: vi.fn(),
}));

vi.mock('@/integrations/supabase/client.ts', () => ({
  getSupabaseClient: vi.fn(),
}));

import { fetchGenerationRecordById } from '@/integrations/supabase/repositories/generationRepository';
import { getSupabaseClient } from '@/integrations/supabase/client';

import {
  parseSupabaseStorageUrl,
  resolveGenerationAsset,
  type ResolveGenerationAssetResult,
  type ResolveGenerationAssetSuccess,
  type ResolveGenerationAssetFailure,
} from '@/tools/video-editor/data/generationAssetResolver';

// ── Helpers ──────────────────────────────────────────────────────────────────

type SupabaseStorageMock = {
  from: ReturnType<typeof vi.fn>;
};

type SupabaseClientMock = {
  storage: SupabaseStorageMock;
};

function makeSupabaseClientMock(overrides: Partial<SupabaseClientMock> = {}): SupabaseClientMock {
  const from = vi.fn();
  return {
    storage: { from, ...overrides.storage },
    ...overrides,
  };
}

function makePublicUrlResponse(publicUrl: string) {
  return { data: { publicUrl } };
}

function makeSignedUrlResponse(signedUrl: string) {
  return { data: { signedUrl }, error: null };
}

function makeSignedUrlFailure(message: string) {
  return { data: null, error: new Error(message) };
}

function makeGenerationRecord(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 'gen-00000000-0000-4000-a000-000000000001',
    location: 'https://example.supabase.co/storage/v1/object/public/generated-media/gen-1/video.mp4',
    thumbnail_url: 'https://example.supabase.co/storage/v1/object/public/generated-media/gen-1/thumb.png',
    type: 'video',
    params: {
      width: 1920,
      height: 1080,
      fps: 30,
      duration: 12.5,
      resolution: '1920x1080',
      content_type: 'video',
    },
    primary_variant_id: 'variant-01',
    ...overrides,
  };
}

function expectSuccess(result: ResolveGenerationAssetResult): asserts result is ResolveGenerationAssetSuccess {
  if (!result.ok) {
    const diag = (result as ResolveGenerationAssetFailure).diagnostic;
    throw new Error(`Expected success but got failure: ${diag.code} — ${diag.message}`);
  }
}

function expectFailure(result: ResolveGenerationAssetResult): asserts result is ResolveGenerationAssetFailure {
  if (result.ok) {
    throw new Error(`Expected failure but got success with url=${result.asset.url}`);
  }
}

// ── parseSupabaseStorageUrl ─────────────────────────────────────────────────

describe('parseSupabaseStorageUrl', () => {
  it('parses a public storage URL into bucket, path, and access', () => {
    const parsed = parseSupabaseStorageUrl(
      'https://example.supabase.co/storage/v1/object/public/my-bucket/images/photo.png',
    );
    expect(parsed).not.toBeNull();
    expect(parsed!.bucket).toBe('my-bucket');
    expect(parsed!.path).toBe('images/photo.png');
    expect(parsed!.access).toBe('public');
  });

  it('parses a signed storage URL', () => {
    const parsed = parseSupabaseStorageUrl(
      'https://example.supabase.co/storage/v1/object/sign/generated-media/gen-1/clip.mp4?token=abc123',
    );
    expect(parsed).not.toBeNull();
    expect(parsed!.bucket).toBe('generated-media');
    expect(parsed!.path).toBe('gen-1/clip.mp4');
    expect(parsed!.access).toBe('sign');
    expect(parsed!.url).toContain('token=abc123');
  });

  it('parses an object-level URL without access discriminator', () => {
    const parsed = parseSupabaseStorageUrl(
      'https://example.supabase.co/storage/v1/object/timeline-assets/user-1/render.mp4',
    );
    expect(parsed).not.toBeNull();
    expect(parsed!.bucket).toBe('timeline-assets');
    expect(parsed!.path).toBe('user-1/render.mp4');
    expect(parsed!.access).toBe('object');
  });

  it('returns null for an empty string', () => {
    expect(parseSupabaseStorageUrl('')).toBeNull();
  });

  it('returns null for a non-URL string', () => {
    expect(parseSupabaseStorageUrl('not-a-url')).toBeNull();
  });

  it('returns null for a non-Supabase storage URL', () => {
    expect(parseSupabaseStorageUrl('https://cdn.example.com/media/video.mp4')).toBeNull();
  });

  it('returns null for a URL with missing bucket/path segments', () => {
    expect(parseSupabaseStorageUrl('https://example.supabase.co/storage/v1/object/')).toBeNull();
  });

  it('decodes URI-encoded bucket and path segments', () => {
    const parsed = parseSupabaseStorageUrl(
      'https://example.supabase.co/storage/v1/object/public/my%20bucket/nested%2Ffile%20name.mp4',
    );
    expect(parsed).not.toBeNull();
    expect(parsed!.bucket).toBe('my bucket');
    expect(parsed!.path).toBe('nested/file name.mp4');
  });
});

// ── resolveGenerationAsset success paths ────────────────────────────────────

describe('resolveGenerationAsset success paths', () => {
  const originalNow = Date.now;
  const frozenNow = 1718100000000;

  beforeEach(() => {
    Date.now = vi.fn(() => frozenNow);
    vi.resetAllMocks();
  });

  afterEach(() => {
    Date.now = originalNow;
    vi.restoreAllMocks();
  });

  it('returns a resolved asset for an immutable public URL with no refresh needed', async () => {
    const generation = makeGenerationRecord();
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const existingEntry = {
      file: '',
      url: generation.location as string,
      origin: 'immutable-public' as const,
      generationId: generation.id as string,
    };

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      assetId: 'asset-1',
      entry: existingEntry,
      refresh: 'never',
    });

    expectSuccess(result);
    expect(result.asset.url).toBe(generation.location);
    expect(result.asset.entry.origin).toBe('refreshable-from-generation');
    expect(result.asset.generationId).toBe(generation.id);
    expect(result.asset.refreshed).toBe(false);
    expect(result.asset.mediaType).toBe('video');
    expect(result.asset.mimeType).toBe('video/mp4');
    expect(result.asset.storage?.bucket).toBe('generated-media');
    expect(result.asset.entry.generationId).toBe(generation.id);
    expect(result.asset.entry.variantId).toBe('variant-01');
    expect(result.asset.entry.resolution).toBe('1920x1080');
    expect(result.asset.entry.fps).toBe(30);
    expect(result.asset.entry.duration).toBe(12.5);
    expect(result.asset.thumbnailUrl).toBe(generation.thumbnail_url);
  });

  it('remints an expired refreshable URL when bucket/path is derivable', async () => {
    const pastExpiry = '2020-01-01T00:00:00.000Z';
    const storageUrl = 'https://example.supabase.co/storage/v1/object/sign/generated-media/gen-1/clip.mp4';
    const newSignedUrl = 'https://example.supabase.co/storage/v1/object/sign/generated-media/gen-1/clip.mp4?token=new';

    const generation = makeGenerationRecord({ location: storageUrl });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const mockFrom = vi.fn().mockReturnValue({
      createSignedUrl: vi.fn().mockResolvedValue(makeSignedUrlResponse(newSignedUrl)),
    });

    vi.mocked(getSupabaseClient).mockReturnValue({
      storage: { from: mockFrom },
    } as unknown as ReturnType<typeof getSupabaseClient>);

    const existingEntry = {
      file: 'clips/old.mp4',
      url: storageUrl,
      url_expires_at: pastExpiry,
      origin: 'refreshable-from-generation' as const,
      generationId: generation.id as string,
    };

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      assetId: 'asset-1',
      entry: existingEntry,
      refresh: 'if-stale',
    });

    expectSuccess(result);
    expect(result.asset.refreshed).toBe(true);
    expect(result.asset.url).toBe(newSignedUrl);
    expect(result.asset.entry.url).toBe(newSignedUrl);
    expect(result.asset.entry.url_expires_at).toBeDefined();
  });

  it('returns unchanged when refresh=never even if expired', async () => {
    const pastExpiry = '2020-01-01T00:00:00.000Z';
    const generation = makeGenerationRecord();
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const originalUrl = generation.location as string;
    const existingEntry = {
      file: 'clips/old.mp4',
      url: originalUrl,
      url_expires_at: pastExpiry,
      origin: 'refreshable-from-generation' as const,
      generationId: generation.id as string,
    };

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      entry: existingEntry,
      refresh: 'never',
    });

    expectSuccess(result);
    expect(result.asset.refreshed).toBe(false);
    expect(result.asset.url).toBe(originalUrl);
  });

  it('preserves existing entry metadata when reminting', async () => {
    const pastExpiry = '2020-01-01T00:00:00.000Z';
    const storageUrl = 'https://example.supabase.co/storage/v1/object/sign/generated-media/gen-1/clip.mp4';
    const newSignedUrl = 'https://example.supabase.co/storage/v1/object/sign/generated-media/gen-1/clip.mp4?token=new';

    const generation = makeGenerationRecord({
      location: storageUrl,
      thumbnail_url: null,
      primary_variant_id: null,
    });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const mockFrom = vi.fn().mockReturnValue({
      createSignedUrl: vi.fn().mockResolvedValue(makeSignedUrlResponse(newSignedUrl)),
    });
    vi.mocked(getSupabaseClient).mockReturnValue({
      storage: { from: mockFrom },
    } as unknown as ReturnType<typeof getSupabaseClient>);

    const existingEntry = {
      file: 'custom/name.mp4',
      url: storageUrl,
      url_expires_at: pastExpiry,
      origin: 'refreshable-from-generation' as const,
      generationId: generation.id as string,
      duration: 42,
      fps: 60,
      resolution: '3840x2160',
      type: 'video/mp4',
      thumbnailUrl: 'https://example.com/custom-thumb.png',
    };

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      entry: existingEntry,
      refresh: 'if-stale',
    });

    expectSuccess(result);
    expect(result.asset.refreshed).toBe(true);
    // Preserved from existing entry
    expect(result.asset.entry.duration).toBe(42);
    expect(result.asset.entry.fps).toBe(60);
    expect(result.asset.entry.resolution).toBe('3840x2160');
    expect(result.asset.entry.thumbnailUrl).toBe('https://example.com/custom-thumb.png');
    expect(result.asset.thumbnailUrl).toBe('https://example.com/custom-thumb.png');
  });

  it('handles timeline-assets URLs without explicit access discriminator', async () => {
    const timelineAssetsUrl = 'https://example.supabase.co/storage/v1/object/timeline-assets/user/render.mp4';
    const generation = makeGenerationRecord({ location: timelineAssetsUrl });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      refresh: 'if-stale',
    });

    expectSuccess(result);
    expect(result.asset.storage?.bucket).toBe('timeline-assets');
    expect(result.asset.storage?.path).toBe('user/render.mp4');
    expect(result.asset.storage?.access).toBe('object');
  });

  it('infers image media type from entry type', async () => {
    const generation = makeGenerationRecord({
      type: null,
      params: { content_type: null },
      location: 'https://example.supabase.co/storage/v1/object/public/generated-media/gen-1/output.png',
    });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      entry: {
        file: '',
        type: 'image/png',
        origin: 'refreshable-from-generation' as const,
        generationId: generation.id as string,
      },
      refresh: 'if-stale',
    });

    expectSuccess(result);
    expect(result.asset.mediaType).toBe('image');
    expect(result.asset.mimeType).toBe('image/png');
  });

  it('infers audio media type from generation params.content_type', async () => {
    const generation = makeGenerationRecord({
      type: null,
      location: 'https://example.supabase.co/storage/v1/object/public/generated-media/gen-1/audio.mp3',
      params: { content_type: 'audio' },
    });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      refresh: 'if-stale',
    });

    expectSuccess(result);
    expect(result.asset.mediaType).toBe('audio');
    expect(result.asset.mimeType).toBe('audio/mpeg');
  });

  it('falls back to generation.thumbnail_url when no existing thumbnailUrl', async () => {
    const generation = makeGenerationRecord();
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      refresh: 'if-stale',
    });

    expectSuccess(result);
    expect(result.asset.thumbnailUrl).toBe(generation.thumbnail_url);
  });

  it('uses location as thumbnailUrl when neither source is available', async () => {
    const generation = makeGenerationRecord({ thumbnail_url: null });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      refresh: 'if-stale',
    });

    expectSuccess(result);
    expect(result.asset.thumbnailUrl).toBe(generation.location);
  });

  it('resolves resolution from generation params orchestrator_details', async () => {
    const generation = makeGenerationRecord({
      params: {
        content_type: 'video',
        orchestrator_details: { parsed_resolution_wh: '2560x1440' },
      },
    });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      refresh: 'if-stale',
    });

    expectSuccess(result);
    expect(result.asset.entry.resolution).toBe('2560x1440');
  });

  it('resolves fps and duration from generation params fallback keys', async () => {
    const generation = makeGenerationRecord({
      params: {
        content_type: 'video',
        source_video_fps: 24,
        source_video_duration: 60,
      },
    });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      refresh: 'if-stale',
    });

    expectSuccess(result);
    expect(result.asset.entry.fps).toBe(24);
    expect(result.asset.entry.duration).toBe(60);
  });
});

// ── resolveGenerationAsset failure paths ────────────────────────────────────

describe('resolveGenerationAsset failure paths', () => {
  const originalNow = Date.now;
  const frozenNow = 1718100000000;

  beforeEach(() => {
    Date.now = vi.fn(() => frozenNow);
    vi.resetAllMocks();
  });

  afterEach(() => {
    Date.now = originalNow;
    vi.restoreAllMocks();
  });

  it('returns generation-not-found when generation record is null', async () => {
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(null);

    const result = await resolveGenerationAsset({ generationId: 'gen-nonexistent' });

    expectFailure(result);
    expect(result.missingReason).toBe('missing_asset');
    expect(result.diagnostic.code).toBe('generation-not-found');
    expect(result.diagnostic.generationId).toBe('gen-nonexistent');
  });

  it('returns missing-generation-location when location is null', async () => {
    const generation = makeGenerationRecord({ location: null });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const result = await resolveGenerationAsset({ generationId: generation.id as string });

    expectFailure(result);
    expect(result.missingReason).toBe('missing_asset');
    expect(result.diagnostic.code).toBe('missing-generation-location');
  });

  it('returns missing-generation-location when location is empty string', async () => {
    const generation = makeGenerationRecord({ location: '   ' });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const result = await resolveGenerationAsset({ generationId: generation.id as string });

    expectFailure(result);
    expect(result.missingReason).toBe('missing_asset');
    expect(result.diagnostic.code).toBe('missing-generation-location');
  });

  it('returns invalid-generation-url for a malformed location', async () => {
    const generation = makeGenerationRecord({ location: 'not-a-valid-url-at-all' });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const result = await resolveGenerationAsset({ generationId: generation.id as string });

    expectFailure(result);
    expect(result.missingReason).toBe('invalid_asset_url');
    expect(result.diagnostic.code).toBe('invalid-generation-url');
    expect(result.diagnostic.url).toBe('not-a-valid-url-at-all');
  });

  it('returns refresh-required when URL needs refresh but bucket/path cannot be derived', async () => {
    const pastExpiry = '2020-01-01T00:00:00.000Z';
    const foreignUrl = 'https://cdn.other-service.com/media/video.mp4';
    const generation = makeGenerationRecord({ location: foreignUrl });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const existingEntry = {
      file: 'external/video.mp4',
      url: foreignUrl,
      url_expires_at: pastExpiry,
      origin: 'refreshable-from-generation' as const,
      generationId: generation.id as string,
    };

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      assetId: 'asset-unsupported',
      entry: existingEntry,
      refresh: 'if-stale',
    });

    expectFailure(result);
    expect(result.missingReason).toBe('invalid_asset_url');
    expect(result.diagnostic.code).toBe('refresh-required');
    expect(result.diagnostic.url).toBe(foreignUrl);
  });

  it('returns opaque-origin when refresh is attempted on opaque-foreign entry', async () => {
    const pastExpiry = '2020-01-01T00:00:00.000Z';
    const storageUrl = 'https://example.supabase.co/storage/v1/object/public/gen-media/clip.mp4';
    const generation = makeGenerationRecord({ location: storageUrl });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const existingEntry = {
      file: 'foreign/video.mp4',
      url: storageUrl,
      url_expires_at: pastExpiry,
      origin: 'opaque-foreign' as const,
      generationId: generation.id as string,
    };

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      assetId: 'asset-opaque',
      entry: existingEntry,
      refresh: 'if-stale',
    });

    expectFailure(result);
    expect(result.missingReason).toBe('unresolvable_asset');
    expect(result.diagnostic.code).toBe('opaque-origin');
    expect(result.diagnostic.assetId).toBe('asset-opaque');
  });

  it('returns opaque-origin even with force refresh on opaque-foreign', async () => {
    const storageUrl = 'https://example.supabase.co/storage/v1/object/public/gen-media/clip.mp4';
    const generation = makeGenerationRecord({ location: storageUrl });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const existingEntry = {
      file: 'foreign/video.mp4',
      url: storageUrl,
      origin: 'opaque-foreign' as const,
      generationId: generation.id as string,
    };

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      assetId: 'asset-opaque-2',
      entry: existingEntry,
      refresh: 'force',
    });

    expectFailure(result);
    expect(result.missingReason).toBe('unresolvable_asset');
    expect(result.diagnostic.code).toBe('opaque-origin');
  });

  it('returns refresh-failed when reminting throws', async () => {
    const pastExpiry = '2020-01-01T00:00:00.000Z';
    const storageUrl = 'https://example.supabase.co/storage/v1/object/sign/generated-media/gen-1/clip.mp4';

    const generation = makeGenerationRecord({ location: storageUrl });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const mockFrom = vi.fn().mockReturnValue({
      createSignedUrl: vi.fn().mockResolvedValue(makeSignedUrlFailure('Storage unavailable')),
    });
    vi.mocked(getSupabaseClient).mockReturnValue({
      storage: { from: mockFrom },
    } as unknown as ReturnType<typeof getSupabaseClient>);

    const existingEntry = {
      file: 'clips/clip.mp4',
      url: storageUrl,
      url_expires_at: pastExpiry,
      origin: 'refreshable-from-generation' as const,
      generationId: generation.id as string,
    };

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      assetId: 'asset-refresh-fail',
      entry: existingEntry,
      refresh: 'if-stale',
    });

    expectFailure(result);
    expect(result.missingReason).toBe('unresolvable_asset');
    expect(result.diagnostic.code).toBe('refresh-failed');
    expect(result.diagnostic.message).toBe('Storage unavailable');
    expect(result.diagnostic.bucket).toBe('generated-media');
    expect(result.diagnostic.path).toBe('gen-1/clip.mp4');
  });

  it('includes assetId in failure diagnostic when provided', async () => {
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(null);

    const result = await resolveGenerationAsset({
      generationId: 'gen-missing',
      assetId: 'asset-with-id',
    });

    expectFailure(result);
    expect(result.diagnostic.assetId).toBe('asset-with-id');
    expect(result.diagnostic.generationId).toBe('gen-missing');
  });
});

// ── resolveGenerationAsset edge cases ───────────────────────────────────────

describe('resolveGenerationAsset edge cases', () => {
  const originalNow = Date.now;
  const frozenNow = 1718100000000;

  beforeEach(() => {
    Date.now = vi.fn(() => frozenNow);
    vi.resetAllMocks();
  });

  afterEach(() => {
    Date.now = originalNow;
    vi.restoreAllMocks();
  });

  it('refreshes with force even when not stale', async () => {
    const storageUrl = 'https://example.supabase.co/storage/v1/object/sign/generated-media/gen-1/clip.mp4';
    const newSignedUrl = 'https://example.supabase.co/storage/v1/object/sign/generated-media/gen-1/clip.mp4?token=forced';

    const generation = makeGenerationRecord({ location: storageUrl });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const mockFrom = vi.fn().mockReturnValue({
      createSignedUrl: vi.fn().mockResolvedValue(makeSignedUrlResponse(newSignedUrl)),
    });
    vi.mocked(getSupabaseClient).mockReturnValue({
      storage: { from: mockFrom },
    } as unknown as ReturnType<typeof getSupabaseClient>);

    const existingEntry = {
      file: '',
      url: storageUrl,
      url_expires_at: '2099-01-01T00:00:00.000Z', // far future, not stale
      origin: 'refreshable-from-generation' as const,
      generationId: generation.id as string,
    };

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      entry: existingEntry,
      refresh: 'force',
    });

    expectSuccess(result);
    expect(result.asset.refreshed).toBe(true);
    expect(result.asset.url).toBe(newSignedUrl);
  });

  it('handles public URL refresh by returning public URL', async () => {
    const publicUrl = 'https://example.supabase.co/storage/v1/object/public/generated-media/gen-1/clip.mp4';

    const generation = makeGenerationRecord({ location: publicUrl });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const mockFrom = vi.fn().mockReturnValue({
      getPublicUrl: vi.fn().mockReturnValue(makePublicUrlResponse(publicUrl)),
    });
    vi.mocked(getSupabaseClient).mockReturnValue({
      storage: { from: mockFrom },
    } as unknown as ReturnType<typeof getSupabaseClient>);

    const existingEntry = {
      file: '',
      url: publicUrl,
      origin: 'refreshable-from-generation' as const,
      generationId: generation.id as string,
    };

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      entry: existingEntry,
      refresh: 'force',
    });

    expectSuccess(result);
    expect(result.asset.refreshed).toBe(true);
    expect(result.asset.url).toBe(publicUrl);
    expect(result.asset.storage?.access).toBe('public');
  });

  it('returns valid result without an existing entry', async () => {
    const generation = makeGenerationRecord();
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      refresh: 'if-stale',
    });

    expectSuccess(result);
    expect(result.asset.generationId).toBe(generation.id);
    expect(result.asset.url).toBe(generation.location);
    expect(result.asset.entry.origin).toBe('refreshable-from-generation');
  });

  it('handles generation record with minimal fields', async () => {
    const generation = makeGenerationRecord({
      thumbnail_url: null,
      type: null,
      params: null,
      primary_variant_id: null,
    });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      refresh: 'if-stale',
    });

    expectSuccess(result);
    expect(result.asset.mediaType).toBe('video');
    expect(result.asset.entry.variantId).toBeUndefined();
    expect(result.asset.entry.resolution).toBeUndefined();
    expect(result.asset.entry.fps).toBeUndefined();
    expect(result.asset.entry.duration).toBeUndefined();
  });

  it('handles null params gracefully', async () => {
    const generation = makeGenerationRecord({ params: null });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      refresh: 'if-stale',
    });

    expectSuccess(result);
    expect(result.asset.mediaType).toBe('video');
  });

  it('handles params as non-object by falling back to undefined fields', async () => {
    const generation = makeGenerationRecord({ params: ['not-an-object'] });
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      refresh: 'if-stale',
    });

    expectSuccess(result);
    expect(result.asset.entry.resolution).toBeUndefined();
    expect(result.asset.entry.fps).toBeUndefined();
    expect(result.asset.entry.duration).toBeUndefined();
  });

  it('sets file from existing entry when available', async () => {
    const generation = makeGenerationRecord();
    vi.mocked(fetchGenerationRecordById).mockResolvedValue(generation);

    const result = await resolveGenerationAsset({
      generationId: generation.id as string,
      entry: {
        file: 'my-special/path.mp4',
        url: generation.location as string,
        origin: 'refreshable-from-generation' as const,
        generationId: generation.id as string,
      },
      refresh: 'never',
    });

    expectSuccess(result);
    expect(result.asset.entry.file).toBe('my-special/path.mp4');
  });
});
