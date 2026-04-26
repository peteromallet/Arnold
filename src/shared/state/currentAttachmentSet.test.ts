import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  __getSelectionStateForTests,
  __resetSelectionStoreForTests,
  composerRemoveAttachment,
  editorReplaceTimelineSelection,
  setTimelineClipData,
  userSelectGalleryItem,
} from './selectionStore';
import {
  makePlaceholderClip,
  mergeSelectedClips,
  type SelectedMediaClip,
  useCurrentAttachmentSet,
} from './currentAttachmentSet';

const timelineClip = (
  clipId: string,
  overrides: Partial<SelectedMediaClip> = {},
): SelectedMediaClip => ({
  clipId,
  assetKey: `asset-${clipId}`,
  url: `https://example.test/${clipId}.png`,
  mediaType: 'image',
  isTimelineBacked: true,
  ...overrides,
});

const galleryItem = (
  id: string,
  overrides: {
    url?: string;
    mediaType?: string;
    generationId?: string;
    variantId?: string;
  } = {},
) => ({
  id,
  url: overrides.url ?? `https://example.test/${id}.png`,
  mediaType: overrides.mediaType ?? 'image/png',
  generationId: overrides.generationId ?? `generation-${id}`,
  variantId: overrides.variantId,
});

const selectedGalleryIds = () => [...__getSelectionStateForTests().gallery.selectedGalleryIds];
const selectedTimelineIds = () => [...__getSelectionStateForTests().timeline.selectedClipIds];

describe('current attachment set', () => {
  beforeEach(() => {
    __resetSelectionStoreForTests();
    vi.restoreAllMocks();
  });

  it('composerRemoveAttachment removes a generation-scoped matching gallery item', () => {
    userSelectGalleryItem(galleryItem('gallery-a', {
      url: 'https://example.test/shared.png',
      generationId: 'generation-a',
    }), { additive: false });

    composerRemoveAttachment({
      url: 'https://example.test/shared.png',
      mediaType: 'image',
      generationId: 'generation-a',
    });

    expect(selectedGalleryIds()).toEqual([]);
  });

  it('composerRemoveAttachment removes a generation-scoped matching timeline clip', () => {
    editorReplaceTimelineSelection(['clip-a']);
    setTimelineClipData([timelineClip('clip-a', {
      url: 'https://example.test/shared.png',
      generationId: 'generation-a',
    })]);

    composerRemoveAttachment({
      url: 'https://example.test/shared.png',
      mediaType: 'image',
      generationId: 'generation-a',
    });

    expect(selectedTimelineIds()).toEqual([]);
  });

  it('composerRemoveAttachment preserves sibling variants with the same generation and different URL', () => {
    userSelectGalleryItem(galleryItem('gallery-a', {
      url: 'https://example.test/variant-a.png',
      generationId: 'generation-a',
    }), { additive: false });
    userSelectGalleryItem(galleryItem('gallery-b', {
      url: 'https://example.test/variant-b.png',
      generationId: 'generation-a',
    }), { additive: true });

    composerRemoveAttachment({
      url: 'https://example.test/variant-a.png',
      mediaType: 'image',
      generationId: 'generation-a',
    });

    expect(selectedGalleryIds()).toEqual(['gallery-b']);
  });

  it('composerRemoveAttachment falls back to URL and media type for gallery when generationId is absent', () => {
    userSelectGalleryItem(galleryItem('gallery-a', {
      url: 'https://example.test/shared.png',
      generationId: 'generation-a',
    }), { additive: false });

    composerRemoveAttachment({
      url: 'https://example.test/shared.png',
      mediaType: 'image',
    });

    expect(selectedGalleryIds()).toEqual([]);
  });

  it('composerRemoveAttachment falls back to URL and media type for timeline when generationId is absent', () => {
    editorReplaceTimelineSelection(['clip-a']);
    setTimelineClipData([timelineClip('clip-a', {
      url: 'https://example.test/shared.png',
      generationId: 'generation-a',
    })]);

    composerRemoveAttachment({
      url: 'https://example.test/shared.png',
      mediaType: 'image',
    });

    expect(selectedTimelineIds()).toEqual([]);
  });

  it('composerRemoveAttachment uses clipId to disambiguate timeline clips with the same URL', () => {
    editorReplaceTimelineSelection(['clip-a', 'clip-b']);
    setTimelineClipData([
      timelineClip('clip-a', { url: 'https://example.test/shared.png' }),
      timelineClip('clip-b', { url: 'https://example.test/shared.png' }),
    ]);

    composerRemoveAttachment({
      url: 'https://example.test/shared.png',
      mediaType: 'image',
      clipId: 'clip-b',
    });

    expect(selectedTimelineIds()).toEqual(['clip-a']);
  });

  it('returns a placeholder for a selected timeline clip before clip data resolves', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    editorReplaceTimelineSelection(['clip-a']);

    const { result } = renderHook(() => useCurrentAttachmentSet());

    expect(result.current.clips).toEqual([makePlaceholderClip('clip-a')]);
    expect(warn).toHaveBeenCalledWith('[currentAttachmentSet] 1 placeholder(s) rendered');
  });

  it('keeps two unknown selected clip ids as two distinct placeholders', () => {
    editorReplaceTimelineSelection(['clip-a', 'clip-b']);

    const { result } = renderHook(() => useCurrentAttachmentSet());

    expect(result.current.clips).toEqual([
      makePlaceholderClip('clip-a'),
      makePlaceholderClip('clip-b'),
    ]);
  });

  it('preserves chip count while timeline clip data partially resolves', () => {
    editorReplaceTimelineSelection(['clip-a', 'clip-b']);
    const { result } = renderHook(() => useCurrentAttachmentSet());

    expect(result.current.clips).toHaveLength(2);

    act(() => {
      setTimelineClipData([timelineClip('clip-a')]);
    });

    expect(result.current.clips).toHaveLength(2);
    expect(result.current.clips).toEqual([
      timelineClip('clip-a'),
      makePlaceholderClip('clip-b'),
    ]);
  });

  it('dedupes real gallery and timeline clips by URL even when the gallery clip has a clipId', () => {
    const url = 'https://example.test/shared.png';
    editorReplaceTimelineSelection(['clip-a']);
    setTimelineClipData([timelineClip('clip-a', { url, generationId: undefined })]);
    userSelectGalleryItem(galleryItem('gallery-a', { url, generationId: 'generation-a' }), { additive: true });

    const { result } = renderHook(() => useCurrentAttachmentSet());

    expect(result.current.clips).toHaveLength(1);
    expect(result.current.clips[0]).toMatchObject({
      url,
      generationId: 'generation-a',
      isTimelineBacked: true,
    });
  });

  it('mergeSelectedClips falls back to URL for constructed clips without clipId', () => {
    const url = 'https://example.test/shared.png';
    const timeline = timelineClip('clip-a', { url, generationId: undefined });
    const gallery = {
      ...timelineClip('', {
        url,
        isTimelineBacked: false,
        generationId: 'generation-a',
      }),
      clipId: undefined,
    } as unknown as SelectedMediaClip;

    expect(mergeSelectedClips([timeline], [gallery])).toHaveLength(1);
    expect(mergeSelectedClips([timeline], [gallery])[0].generationId).toBe('generation-a');
  });
});
