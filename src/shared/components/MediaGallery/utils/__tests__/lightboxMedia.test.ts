import { describe, expect, it } from 'vitest';
import { buildMediaGalleryLightboxMedia } from '../lightboxMedia';

describe('buildMediaGalleryLightboxMedia', () => {
  it('normalizes gallery media into the lightbox contract without cast fallbacks', () => {
    const result = buildMediaGalleryLightboxMedia({
      activeMedia: {
        id: 'shot-gen-1',
        generation_id: 'gen-1',
        url: 'https://cdn.example.com/active.png',
        thumbUrl: 'https://cdn.example.com/active-thumb.png',
        metadata: {
          __autoEnterEditMode: true,
          prompt: 'active prompt',
        },
        starred: false,
      },
      sourceMedia: {
        id: 'shot-gen-1',
        generation_id: 'gen-1',
        location: 'https://cdn.example.com/source.png',
        thumbUrl: 'https://cdn.example.com/source-thumb.png',
        metadata: {
          prompt: 'source prompt',
        },
        starred: true,
        timeline_frame: 24,
      },
    });

    expect(result).toEqual({
      id: 'shot-gen-1',
      generation_id: 'gen-1',
      location: 'https://cdn.example.com/source.png',
      imageUrl: 'https://cdn.example.com/source.png',
      thumbUrl: 'https://cdn.example.com/source-thumb.png',
      type: null,
      createdAt: undefined,
      metadata: {
        prompt: 'source prompt',
      },
      name: null,
      timeline_frame: 24,
      starred: true,
      based_on: null,
      parent_generation_id: null,
      is_child: undefined,
      child_order: null,
      contentType: undefined,
      storage_mode: null,
      local_handle_id: null,
      local_file_name: null,
      local_file_size: null,
      local_file_mime: null,
    });
  });

  it('falls back to the active media identity when gallery items only expose metadata generation ids', () => {
    const result = buildMediaGalleryLightboxMedia({
      activeMedia: {
        id: 'shot-gen-2',
        url: 'https://cdn.example.com/video.mp4',
        metadata: {
          generation_id: 'gen-2',
        },
      },
    });

    expect(result.generation_id).toBe('gen-2');
    expect(result.location).toBe('https://cdn.example.com/video.mp4');
    expect(result.thumbUrl).toBe('https://cdn.example.com/video.mp4');
    expect(result.starred).toBe(false);
  });

  it('preserves local-storage metadata for lightbox-only media resolution', () => {
    const result = buildMediaGalleryLightboxMedia({
      activeMedia: {
        id: 'gen-local',
        generation_id: 'gen-local',
        url: null,
        location: null,
        storage_mode: 'local',
        local_handle_id: 'handle-1',
        local_file_name: 'clip.mov',
        local_file_size: 123,
        local_file_mime: 'video/quicktime',
      },
    });

    expect(result.storage_mode).toBe('local');
    expect(result.local_handle_id).toBe('handle-1');
    expect(result.local_file_name).toBe('clip.mov');
    expect(result.local_file_size).toBe(123);
    expect(result.local_file_mime).toBe('video/quicktime');
  });
});
