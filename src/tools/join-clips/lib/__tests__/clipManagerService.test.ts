import {
  describe,
  it,
  expect,
  vi
} from 'vitest';
import {
  buildClipsToSave,
  buildPromptsToSave,
  getClipsNeedingDuration,
  normalizeClipSlots,
  reorderClipsAndPrompts,
  updateClipInArray,
  clearClipVideo,
} from '../clipManagerService';
import type { VideoClip, TransitionPrompt } from '../../clipTypes';

// Mock dependencies that aren't used by the pure functions we're testing
vi.mock('@/shared/lib/videoUploader', () => ({
  extractVideoMetadataFromUrl: vi.fn(),
  uploadVideoToStorage: vi.fn(),
}));

vi.mock('@/shared/lib/imageUploader', () => ({
  uploadBlobToStorage: vi.fn(),
}));

vi.mock('@/shared/lib/videoPosterExtractor', () => ({
  extractVideoPosterFrame: vi.fn(),
  extractVideoFinalFrame: vi.fn(),
}));

vi.mock('@/shared/lib/errorHandling/runtimeError', () => ({
  normalizeAndPresentError: vi.fn(),
}));

vi.mock('@dnd-kit/sortable', () => ({
  arrayMove: <T,>(arr: T[], from: number, to: number): T[] => {
    const result = [...arr];
    const [removed] = result.splice(from, 1);
    result.splice(to, 0, removed);
    return result;
  },
}));

vi.mock('../clipInitService', () => ({
  getCachedClipsCount: vi.fn(),
  setCachedClipsCount: vi.fn(),
  preloadPosterImages: vi.fn(),
  tryConsumePendingJoinClips: vi.fn(),
  applyPendingClipActions: vi.fn(),
  buildInitialClipsFromSettings: vi.fn(),
  padClipsWithEmptySlots: vi.fn(),
  createEmptyClip: () => ({
    id: `empty-${Math.random().toString(36).slice(2, 8)}`,
    url: '',
    loaded: false,
    playing: false,
  }),
}));

function makeClip(id: string, url: string, opts: Partial<VideoClip> = {}): VideoClip {
  return { id, url, loaded: false, playing: false, ...opts };
}

describe('buildClipsToSave', () => {
  it('filters out clips without URLs', () => {
    const clips = [
      makeClip('1', 'https://example.com/a.mp4'),
      makeClip('2', ''),
      makeClip('3', 'https://example.com/b.mp4'),
    ];

    const result = buildClipsToSave(clips);
    expect(result).toHaveLength(2);
    expect(result[0].url).toBe('https://example.com/a.mp4');
    expect(result[1].url).toBe('https://example.com/b.mp4');
  });

  it('includes posterUrl, finalFrameUrl, and durationSeconds', () => {
    const clips = [
      makeClip('1', 'https://example.com/a.mp4', {
        posterUrl: 'https://example.com/poster.jpg',
        finalFrameUrl: 'https://example.com/final.jpg',
        durationSeconds: 10.5,
      }),
    ];

    const result = buildClipsToSave(clips);
    expect(result[0].posterUrl).toBe('https://example.com/poster.jpg');
    expect(result[0].finalFrameUrl).toBe('https://example.com/final.jpg');
    expect(result[0].durationSeconds).toBe(10.5);
  });

  it('returns empty array for all-empty clips', () => {
    const clips = [makeClip('1', ''), makeClip('2', '')];
    expect(buildClipsToSave(clips)).toEqual([]);
  });
});

describe('buildPromptsToSave', () => {
  it('maps transition prompts to clip indices', () => {
    const clips = [
      makeClip('clip-1', 'a.mp4'),
      makeClip('clip-2', 'b.mp4'),
      makeClip('clip-3', 'c.mp4'),
    ];

    const transitionPrompts: TransitionPrompt[] = [
      { id: 'clip-2', prompt: 'transition 1-2' },
      { id: 'clip-3', prompt: 'transition 2-3' },
    ];

    const result = buildPromptsToSave(clips, transitionPrompts);
    expect(result).toEqual([
      { clipIndex: 1, prompt: 'transition 1-2' },
      { clipIndex: 2, prompt: 'transition 2-3' },
    ]);
  });

  it('filters out prompts at index 0 (no clip before first)', () => {
    const clips = [makeClip('clip-1', 'a.mp4')];
    const transitionPrompts: TransitionPrompt[] = [
      { id: 'clip-1', prompt: 'should be filtered' },
    ];

    const result = buildPromptsToSave(clips, transitionPrompts);
    expect(result).toEqual([]);
  });

  it('filters out empty prompts', () => {
    const clips = [makeClip('clip-1', 'a.mp4'), makeClip('clip-2', 'b.mp4')];
    const transitionPrompts: TransitionPrompt[] = [
      { id: 'clip-2', prompt: '' },
    ];

    const result = buildPromptsToSave(clips, transitionPrompts);
    expect(result).toEqual([]);
  });

  it('filters out prompts with unknown clip IDs', () => {
    const clips = [makeClip('clip-1', 'a.mp4')];
    const transitionPrompts: TransitionPrompt[] = [
      { id: 'unknown-id', prompt: 'orphaned' },
    ];

    const result = buildPromptsToSave(clips, transitionPrompts);
    expect(result).toEqual([]);
  });
});

describe('getClipsNeedingDuration', () => {
  it('returns clips with URL but no duration', () => {
    const clips = [
      makeClip('1', 'https://example.com/a.mp4'),
      makeClip('2', 'https://example.com/b.mp4', { durationSeconds: 5 }),
      makeClip('3', ''),
    ];

    const result = getClipsNeedingDuration(clips);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('1');
  });

  it('excludes clips with metadataLoading flag', () => {
    const clips = [
      makeClip('1', 'https://example.com/a.mp4', { metadataLoading: true }),
    ];

    const result = getClipsNeedingDuration(clips);
    expect(result).toHaveLength(0);
  });

  it('returns empty when all clips have durations', () => {
    const clips = [
      makeClip('1', 'https://example.com/a.mp4', { durationSeconds: 5 }),
      makeClip('2', 'https://example.com/b.mp4', { durationSeconds: 10 }),
    ];

    const result = getClipsNeedingDuration(clips);
    expect(result).toHaveLength(0);
  });
});

describe('normalizeClipSlots', () => {
  it('returns null for empty array', () => {
    expect(normalizeClipSlots([])).toBe(null);
  });

  it('pads to minimum of 2 clips', () => {
    const clips = [makeClip('1', 'https://example.com/a.mp4')];
    const result = normalizeClipSlots(clips);
    expect(result).not.toBeNull();
    expect(result!.clips).toHaveLength(2);
    expect(result!.clips[0].url).toBe('https://example.com/a.mp4');
    expect(result!.clips[1].url).toBe('');
    expect(result!.removedClipIds).toEqual([]);
  });

  it('auto-adds empty slot when all clips are filled', () => {
    const clips = [
      makeClip('1', 'https://example.com/a.mp4'),
      makeClip('2', 'https://example.com/b.mp4'),
    ];

    const result = normalizeClipSlots(clips);
    expect(result).not.toBeNull();
    expect(result!.clips).toHaveLength(3);
    expect(result!.clips[2].url).toBe('');
  });

  it('trims extra trailing empties to keep exactly 1', () => {
    const clips = [
      makeClip('1', 'https://example.com/a.mp4'),
      makeClip('2', ''),
      makeClip('3', ''),
      makeClip('4', ''),
    ];

    const result = normalizeClipSlots(clips);
    expect(result).not.toBeNull();
    expect(result!.clips).toHaveLength(2); // 1 filled + 1 empty
    expect(result!.removedClipIds).toContain('3');
    expect(result!.removedClipIds).toContain('4');
  });

  it('returns null when no changes needed', () => {
    const clips = [
      makeClip('1', 'https://example.com/a.mp4'),
      makeClip('2', ''),
    ];

    const result = normalizeClipSlots(clips);
    expect(result).toBe(null);
  });

  it('keeps minimum of 2 clips even with trailing empties', () => {
    const clips = [
      makeClip('1', ''),
      makeClip('2', ''),
      makeClip('3', ''),
    ];

    const result = normalizeClipSlots(clips);
    // lastNonEmptyIndex = -1, targetLength = max(2, -1+2) = max(2,1) = 2
    expect(result).not.toBeNull();
    expect(result!.clips).toHaveLength(2);
  });
});

describe('reorderClipsAndPrompts', () => {
  it('reorders clips when moving forward', () => {
    const clips = [
      makeClip('a', 'a.mp4'),
      makeClip('b', 'b.mp4'),
      makeClip('c', 'c.mp4'),
    ];

    const result = reorderClipsAndPrompts(clips, [], 'a', 'c');
    expect(result.clips.map(c => c.id)).toEqual(['b', 'c', 'a']);
  });

  it('reorders clips when moving backward', () => {
    const clips = [
      makeClip('a', 'a.mp4'),
      makeClip('b', 'b.mp4'),
      makeClip('c', 'c.mp4'),
    ];

    const result = reorderClipsAndPrompts(clips, [], 'c', 'a');
    expect(result.clips.map(c => c.id)).toEqual(['c', 'a', 'b']);
  });

  it('returns unchanged when IDs not found', () => {
    const clips = [makeClip('a', 'a.mp4'), makeClip('b', 'b.mp4')];
    const result = reorderClipsAndPrompts(clips, [], 'unknown', 'b');
    expect(result.clips).toBe(clips);
  });
});

describe('updateClipInArray', () => {
  it('updates the matching clip', () => {
    const clips = [
      makeClip('1', 'a.mp4'),
      makeClip('2', 'b.mp4'),
    ];

    const result = updateClipInArray(clips, '2', { url: 'updated.mp4' });
    expect(result[0].url).toBe('a.mp4');
    expect(result[1].url).toBe('updated.mp4');
  });

  it('returns unchanged array when ID not found', () => {
    const clips = [makeClip('1', 'a.mp4')];
    const result = updateClipInArray(clips, 'unknown', { url: 'x.mp4' });
    expect(result[0].url).toBe('a.mp4');
  });
});

describe('clearClipVideo', () => {
  it('clears video content but keeps the ID', () => {
    const clip = makeClip('1', 'https://example.com/video.mp4', {
      posterUrl: 'poster.jpg',
      finalFrameUrl: 'final.jpg',
      loaded: true,
      playing: true,
    });

    const result = clearClipVideo(clip);
    expect(result.id).toBe('1');
    expect(result.url).toBe('');
    expect(result.posterUrl).toBeUndefined();
    expect(result.finalFrameUrl).toBeUndefined();
    expect(result.file).toBeUndefined();
    expect(result.loaded).toBe(false);
    expect(result.playing).toBe(false);
  });
});
