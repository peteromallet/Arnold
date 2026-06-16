import { describe, expect, it } from 'vitest';

import { buildExternalTimelineAssetEntry } from '@/tools/video-editor/commands/provisioning.ts';
import { sanitizeAssetRegistryEntry } from '@/tools/video-editor/lib/timeline-domain.ts';

describe('asset registry contract helpers', () => {
  // ---------------------------------------------------------------------------
  // Sanitization — field preservation
  // ---------------------------------------------------------------------------

  it('preserves extended fields during sanitization', () => {
    const sanitized = sanitizeAssetRegistryEntry({
      file: 'sources/main.mp4',
      url: 'https://cdn.example.com/main.mp4',
      etag: '"main-etag"',
      content_sha256: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
      url_expires_at: '2026-12-31T23:59:59Z',
      type: 'video/mp4',
      duration: 12,
      resolution: '1920x1080',
      fps: 24,
      origin: 'refreshable-from-generation',
      derivedFrom: {
        assetId: 'asset-parent',
        content_sha256: 'fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210',
        role: 'proxy',
      },
      generationId: 'gen-1',
      variantId: 'variant-1',
      thumbnailUrl: 'https://cdn.example.com/main.jpg',
      // @ts-expect-error verifying unknown fields are stripped.
      ignored: true,
    });

    expect(sanitized).toEqual({
      file: 'sources/main.mp4',
      url: 'https://cdn.example.com/main.mp4',
      etag: '"main-etag"',
      content_sha256: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
      url_expires_at: '2026-12-31T23:59:59Z',
      type: 'video/mp4',
      duration: 12,
      resolution: '1920x1080',
      fps: 24,
      origin: 'refreshable-from-generation',
      derivedFrom: {
        assetId: 'asset-parent',
        content_sha256: 'fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210',
        role: 'proxy',
      },
      generationId: 'gen-1',
      variantId: 'variant-1',
      thumbnailUrl: 'https://cdn.example.com/main.jpg',
    });
  });

  it('preserves url through sanitization', () => {
    const sanitized = sanitizeAssetRegistryEntry({
      file: 'a.mp4',
      url: 'https://cdn.example.com/assets/a.mp4',
    });

    expect(sanitized.url).toBe('https://cdn.example.com/assets/a.mp4');
  });

  it('preserves etag through sanitization', () => {
    const sanitized = sanitizeAssetRegistryEntry({
      file: 'a.mp4',
      etag: '"abc123"',
    });

    expect(sanitized.etag).toBe('"abc123"');
  });

  it('preserves content_sha256 through sanitization', () => {
    const sanitized = sanitizeAssetRegistryEntry({
      file: 'a.mp4',
      content_sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    });

    expect(sanitized.content_sha256).toBe(
      'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    );
  });

  it('preserves url_expires_at through sanitization', () => {
    const sanitized = sanitizeAssetRegistryEntry({
      file: 'a.mp4',
      url_expires_at: '2026-12-31T23:59:59Z',
    });

    expect(sanitized.url_expires_at).toBe('2026-12-31T23:59:59Z');
  });

  it('preserves origin through sanitization', () => {
    for (const origin of ['immutable-public', 'refreshable-from-generation', 'opaque-foreign'] as const) {
      const sanitized = sanitizeAssetRegistryEntry({
        file: 'a.mp4',
        origin,
      });

      expect(sanitized.origin).toBe(origin);
    }
  });

  it('preserves thumbnailUrl through sanitization', () => {
    const sanitized = sanitizeAssetRegistryEntry({
      file: 'a.mp4',
      thumbnailUrl: 'https://cdn.example.com/a.jpg',
    });

    expect(sanitized.thumbnailUrl).toBe('https://cdn.example.com/a.jpg');
  });

  it('preserves derivedFrom through sanitization', () => {
    const sanitized = sanitizeAssetRegistryEntry({
      file: 'a.mp4',
      derivedFrom: {
        assetId: 'parent-a',
        content_sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        role: 'proxy' as const,
      },
    });

    expect(sanitized.derivedFrom).toEqual({
      assetId: 'parent-a',
      content_sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      role: 'proxy',
    });
  });

  it('preserves generationId through sanitization', () => {
    const sanitized = sanitizeAssetRegistryEntry({
      file: 'a.mp4',
      generationId: 'gen-abc-123',
    });

    expect(sanitized.generationId).toBe('gen-abc-123');
  });

  it('preserves variantId through sanitization', () => {
    const sanitized = sanitizeAssetRegistryEntry({
      file: 'a.mp4',
      variantId: 'variant-xyz',
    });

    expect(sanitized.variantId).toBe('variant-xyz');
  });

  it('strips unknown fields during sanitization', () => {
    const sanitized = sanitizeAssetRegistryEntry({
      file: 'a.mp4',
      // @ts-expect-error verifying unknown fields are stripped.
      extraField: 'should-be-removed',
      // @ts-expect-error verifying unknown fields are stripped.
      anotherUnknown: 42,
    });

    expect(sanitized).not.toHaveProperty('extraField');
    expect(sanitized).not.toHaveProperty('anotherUnknown');
  });

  it('handles minimal asset entry with only file', () => {
    const sanitized = sanitizeAssetRegistryEntry({
      file: 'minimal.mp4',
    });

    expect(sanitized).toEqual({
      file: 'minimal.mp4',
    });
  });

  // ---------------------------------------------------------------------------
  // External asset entry construction — origin defaults
  // ---------------------------------------------------------------------------

  it('assigns conservative external origin defaults', () => {
    expect(buildExternalTimelineAssetEntry({
      kind: 'external-media',
      url: 'https://cdn.example.com/image.png',
      mediaType: 'image',
    })).toEqual({
      file: 'https://cdn.example.com/image.png',
      url: 'https://cdn.example.com/image.png',
      type: 'image/png',
      origin: 'opaque-foreign',
    });

    expect(buildExternalTimelineAssetEntry({
      kind: 'external-media',
      url: 'https://cdn.example.com/video.mp4',
      mediaType: 'video',
      generationId: 'gen-2',
      thumbnailUrl: 'https://cdn.example.com/video.jpg',
    })).toEqual({
      file: 'https://cdn.example.com/video.mp4',
      url: 'https://cdn.example.com/video.mp4',
      type: 'video/mp4',
      origin: 'refreshable-from-generation',
      generationId: 'gen-2',
      thumbnailUrl: 'https://cdn.example.com/video.jpg',
    });
  });

  it('preserves url in external asset entry', () => {
    const entry = buildExternalTimelineAssetEntry({
      kind: 'external-media',
      url: 'https://cdn.example.com/video.mp4',
      mediaType: 'video',
    });

    expect(entry.url).toBe('https://cdn.example.com/video.mp4');
  });

  it('preserves durationSeconds in external asset entry', () => {
    const entry = buildExternalTimelineAssetEntry({
      kind: 'external-media',
      url: 'https://cdn.example.com/video.mp4',
      mediaType: 'video',
      durationSeconds: 30,
    });

    expect(entry.duration).toBe(30);
  });
});
