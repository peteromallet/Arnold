import { describe, it, expect, vi } from 'vitest';

// Mock Supabase client to avoid real DB calls
vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: () => ({
    from: vi.fn(() => ({
      select: vi.fn(() => ({
        in: vi.fn(() => Promise.resolve({ data: [], error: null })),
      })),
    })),
  }),
}));

import {
  LOCAL_GENERATION_MEDIA_SENTINEL_URL,
  transformGeneration,
  transformForTimeline,
  transformVariant,
  type RawGeneration,
  type RawVariant,
  type RawShotGeneration,
} from '../generationTransformers';

describe('transformGeneration', () => {
  const makeRaw = (overrides: Partial<RawGeneration> = {}): RawGeneration => ({
    id: 'gen-1',
    location: 'https://example.com/image.png',
    created_at: '2024-01-01T00:00:00Z',
    ...overrides,
  });

  it('transforms a basic generation', () => {
    const result = transformGeneration(makeRaw());
    expect(result.id).toBe('gen-1');
    expect(result.url).toBe('https://example.com/image.png');
    expect(result.createdAt).toBe('2024-01-01T00:00:00Z');
    expect(result.starred).toBe(false);
    expect(result.isVideo).toBe(false);
  });

  it('detects video by type field', () => {
    const result = transformGeneration(makeRaw({ type: 'video' }));
    expect(result.isVideo).toBe(true);
    // contentType is derived from params.content_type, not the type field
  });

  it('sets contentType from params.content_type', () => {
    expect(transformGeneration(makeRaw({
      params: { content_type: 'video' },
    })).contentType).toBe('video/mp4');
    expect(transformGeneration(makeRaw({
      params: { content_type: 'image' },
    })).contentType).toBe('image/png');
  });

  it('detects video from content_type param', () => {
    const result = transformGeneration(makeRaw({
      params: { content_type: 'video' },
    }));
    expect(result.isVideo).toBe(true);
  });

  it('uses thumbnail_url when available', () => {
    const result = transformGeneration(makeRaw({
      thumbnail_url: 'https://example.com/thumb.jpg',
    }));
    expect(result.thumbUrl).toBe('https://example.com/thumb.jpg');
  });

  it('falls back to main URL when no thumbnail', () => {
    const result = transformGeneration(makeRaw());
    expect(result.thumbUrl).toBe('https://example.com/image.png');
  });

  it('extracts prompt from params', () => {
    const result = transformGeneration(makeRaw({
      params: { prompt: 'a beautiful sunset' },
    }));
    expect(result.prompt).toBe('a beautiful sunset');
  });

  it('extracts prompt from nested originalParams', () => {
    const result = transformGeneration(makeRaw({
      params: {
        originalParams: {
          orchestrator_details: { prompt: 'nested prompt' },
        },
      },
    }));
    expect(result.prompt).toBe('nested prompt');
  });

  it('defaults prompt to "No prompt"', () => {
    const result = transformGeneration(makeRaw());
    expect(result.prompt).toBe('No prompt');
  });

  it('passes through starred flag', () => {
    const result = transformGeneration(makeRaw({ starred: true }));
    expect(result.starred).toBe(true);
  });

  it('passes through based_on', () => {
    const result = transformGeneration(makeRaw({ based_on: 'parent-gen' }));
    expect(result.based_on).toBe('parent-gen');
  });

  it('passes through parent/child fields', () => {
    const result = transformGeneration(makeRaw({
      is_child: true,
      parent_generation_id: 'parent-1',
      child_order: 2,
    }));
    expect(result.is_child).toBe(true);
    expect(result.parent_generation_id).toBe('parent-1');
    expect(result.child_order).toBe(2);
  });

  it('applies shot context from options', () => {
    const result = transformGeneration(makeRaw(), {
      shotImageEntryId: 'entry-1',
      timeline_frame: 100,
    });
    expect(result.shotImageEntryId).toBe('entry-1');
    expect(result.timeline_frame).toBe(100);
    expect(result.position).toBe(2); // 100 / 50 = 2
  });

  it('processes JSONB shot_data', () => {
    const result = transformGeneration(makeRaw({
      shot_data: { 'shot-1': [50, 100] },
    }));
    expect(result.shot_id).toBe('shot-1');
    expect(result.timeline_frame).toBe(50);
    expect(result.position).toBe(1); // 50 / 50
  });

  it('processes shot_data with multiple shots and shotId filter', () => {
    const result = transformGeneration(makeRaw({
      shot_data: { 'shot-1': [50], 'shot-2': [100] },
    }), { shotId: 'shot-2' });
    expect(result.shot_id).toBe('shot-2');
    expect(result.timeline_frame).toBe(100);
  });

  it('returns no shot association when shot_data is absent', () => {
    const result = transformGeneration(makeRaw());
    expect(result.shot_id).toBeUndefined();
    expect(result.timeline_frame).toBeNull();
  });

  it('strips query parameters for URL identity', () => {
    const result = transformGeneration(makeRaw({
      location: 'https://example.com/image.png?token=abc',
    }));
    expect(result.urlIdentity).toBe('https://example.com/image.png');
  });

  it('includes derivedCount and unviewed variant info', () => {
    const result = transformGeneration(makeRaw({
      derivedCount: 3,
      hasUnviewedVariants: true,
      unviewedVariantCount: 2,
    }));
    expect(result.derivedCount).toBe(3);
    expect(result.hasUnviewedVariants).toBe(true);
    expect(result.unviewedVariantCount).toBe(2);
  });

  it('merges additional metadata from options', () => {
    const result = transformGeneration(makeRaw(), {
      metadata: { custom: 'value' },
    });
    expect(result.metadata?.custom).toBe('value');
  });

  it('preserves local-generation metadata while nulling resolved media location', () => {
    const result = transformGeneration(makeRaw({
      location: null,
      thumbnail_url: 'https://example.com/thumb.png',
      storage_mode: 'local',
      local_handle_id: 'handle-1',
      local_file_name: 'clip.mov',
      local_file_size: 123456789,
      local_file_mime: 'video/quicktime',
      type: 'video',
    }));

    expect(result.url).toBe(LOCAL_GENERATION_MEDIA_SENTINEL_URL);
    expect(result.location).toBeNull();
    expect(result.thumbUrl).toBe('https://example.com/thumb.png');
    expect(result.storage_mode).toBe('local');
    expect(result.local_handle_id).toBe('handle-1');
    expect(result.local_file_name).toBe('clip.mov');
    expect(result.local_file_size).toBe(123456789);
    expect(result.local_file_mime).toBe('video/quicktime');
  });
});

describe('transformForTimeline', () => {
  it('transforms a shot_generation with nested generation data', () => {
    const sg: RawShotGeneration = {
      id: 'sg-1',
      shot_id: 'shot-1',
      generation_id: 'gen-1',
      timeline_frame: 50,
      generation: {
        id: 'gen-1',
        location: 'https://example.com/img.png',
        created_at: '2024-01-01',
        type: 'image',
        starred: true,
      },
    };
    const result = transformForTimeline(sg);
    expect(result.id).toBe('sg-1');
    expect(result.generation_id).toBe('gen-1');
    expect(result.imageUrl).toBe('https://example.com/img.png');
    expect(result.timeline_frame).toBe(50);
    expect(result.starred).toBe(true);
  });

  it('handles missing generation data gracefully', () => {
    const sg: RawShotGeneration = {
      id: 'sg-2',
      shot_id: 'shot-1',
      generation_id: 'gen-2',
      timeline_frame: null,
      generation: null,
    };
    const result = transformForTimeline(sg);
    expect(result.id).toBe('sg-2');
    expect(result.generation_id).toBe('gen-2');
    expect(result.imageUrl).toBeUndefined();
  });

  it('uses generations (plural) when generation is absent', () => {
    const sg: RawShotGeneration = {
      id: 'sg-3',
      shot_id: 'shot-1',
      generation_id: 'gen-3',
      timeline_frame: 100,
      generations: {
        id: 'gen-3',
        location: 'https://example.com/vid.mp4',
        created_at: '2024-01-01',
        type: 'video',
      },
    };
    const result = transformForTimeline(sg);
    expect(result.location).toBe('https://example.com/vid.mp4');
    expect(result.type).toBe('video');
  });
});

describe('transformVariant', () => {
  const makeVariant = (overrides: Partial<RawVariant> = {}): RawVariant => ({
    id: 'var-1',
    generation_id: 'gen-1',
    location: 'https://example.com/variant.png',
    created_at: '2024-01-01T00:00:00Z',
    ...overrides,
  });

  it('transforms a basic image variant', () => {
    const result = transformVariant(makeVariant());
    expect(result.id).toBe('var-1');
    expect(result.url).toBe('https://example.com/variant.png');
    expect(result.isVideo).toBe(false);
    expect(result.contentType).toBe('image/png');
    expect(result.starred).toBe(false);
  });

  it('detects video variants by extension', () => {
    const result = transformVariant(makeVariant({
      location: 'https://example.com/variant.mp4',
    }));
    expect(result.isVideo).toBe(true);
    expect(result.contentType).toBe('video/mp4');
  });

  it('includes variant metadata', () => {
    const result = transformVariant(makeVariant({
      variant_type: 'upscaled',
      name: 'My Upscale',
      params: { prompt: 'a cat', tool_type: 'image-upscale' },
    }));
    expect(result.metadata?.variant_type).toBe('upscaled');
    expect(result.metadata?.name).toBe('My Upscale');
    expect(result.metadata?.prompt).toBe('a cat');
    expect(result.metadata?.tool_type).toBe('image-upscale');
  });

  it('uses thumbnail_url when available', () => {
    const result = transformVariant(makeVariant({
      thumbnail_url: 'https://example.com/thumb.jpg',
    }));
    expect(result.thumbUrl).toBe('https://example.com/thumb.jpg');
  });

  it('falls back to location for thumbnail', () => {
    const result = transformVariant(makeVariant());
    expect(result.thumbUrl).toBe('https://example.com/variant.png');
  });

  it('uses toolType from options as fallback', () => {
    const result = transformVariant(makeVariant(), { toolType: 'travel-between-images' });
    expect(result.metadata?.tool_type).toBe('travel-between-images');
  });
});
