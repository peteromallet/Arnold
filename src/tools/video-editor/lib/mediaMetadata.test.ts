import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/shared/lib/media/videoMetadata', () => ({
  extractVideoMetadata: vi.fn(),
}));

import { extractVideoMetadata } from '@/shared/lib/media/videoMetadata';
import { extractAssetRegistryEntry } from '@/tools/video-editor/lib/mediaMetadata';

const mockedExtractVideoMetadata = vi.mocked(extractVideoMetadata);

class MockAudio {
  duration = 12;
  preload = '';
  onloadedmetadata: (() => void) | null = null;
  onerror: (() => void) | null = null;

  set src(_value: string) {
    queueMicrotask(() => {
      this.onloadedmetadata?.();
    });
  }
}

describe('extractAssetRegistryEntry', () => {
  beforeEach(() => {
    mockedExtractVideoMetadata.mockReset();
    vi.stubGlobal('Audio', MockAudio);
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      writable: true,
      value: vi.fn(() => 'blob:mock'),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      writable: true,
      value: vi.fn(),
    });
  });

  it('falls back to video metadata extraction for blank MIME types with known video extensions', async () => {
    const file = new File(['video'], 'test.mp4', { type: '' });
    mockedExtractVideoMetadata.mockResolvedValue({
      width: 1920,
      height: 1080,
      duration_seconds: 8,
      frame_rate: 30,
      total_frames: 240,
      file_size: file.size,
    });

    const result = await extractAssetRegistryEntry(file, 'uploads/test.mp4');

    expect(mockedExtractVideoMetadata).toHaveBeenCalledWith(file);
    expect(result).toEqual({
      file: 'uploads/test.mp4',
      type: 'video/mp4',
      duration: 8,
      resolution: '1920x1080',
      fps: 30,
      origin: 'immutable-public',
    });
  });

  it('falls back to audio metadata extraction for blank MIME types with known audio extensions', async () => {
    const file = new File(['audio'], 'test.mp3', { type: '' });

    const result = await extractAssetRegistryEntry(file, 'uploads/test.mp3');

    expect(result).toEqual({
      file: 'uploads/test.mp3',
      type: 'audio/mpeg',
      duration: 12,
      origin: 'immutable-public',
    });
  });
});
