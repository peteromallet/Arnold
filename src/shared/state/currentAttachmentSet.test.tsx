import { act, render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  __getSelectionStateForTests,
  __resetSelectionStoreForTests,
  setTimelineClipData,
  userSelectGalleryItem,
  userSelectTimelineClip,
  userSelectTimelineClips,
} from './selectionStore';
import {
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

const galleryItem = (id: string) => ({
  id,
  url: `https://example.test/${id}.png`,
  mediaType: 'image/png',
  generationId: `generation-${id}`,
});

type AttachmentSnapshot = SelectedMediaClip[];

function AttachmentRecorder({ snapshots }: { snapshots: AttachmentSnapshot[] }) {
  const { clips } = useCurrentAttachmentSet();
  snapshots.push(clips.map((clip) => ({ ...clip })));
  return <div data-testid="attachment-count">{clips.length}</div>;
}

function renderAttachmentRecorder() {
  const snapshots: AttachmentSnapshot[] = [];
  const view = render(<AttachmentRecorder snapshots={snapshots} />);
  return { ...view, snapshots };
}

function expectAllRendersNonEmpty(snapshots: AttachmentSnapshot[]) {
  expect(snapshots.length).toBeGreaterThan(0);
  for (const snapshot of snapshots) {
    expect(snapshot.length).toBeGreaterThanOrEqual(1);
  }
}

function latestSnapshot(snapshots: AttachmentSnapshot[]) {
  const snapshot = snapshots.at(-1);
  expect(snapshot).toBeDefined();
  return snapshot ?? [];
}

describe('current attachment set render flow', () => {
  beforeEach(() => {
    __resetSelectionStoreForTests();
    vi.restoreAllMocks();
  });

  it('keeps clips non-empty when timeline data is ready before selecting a timeline clip', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});

    setTimelineClipData([timelineClip('A')]);
    userSelectGalleryItem(galleryItem('G'), { additive: false });
    const { snapshots } = renderAttachmentRecorder();

    act(() => {
      userSelectTimelineClip('A', { additive: false });
    });

    expectAllRendersNonEmpty(snapshots);
    expect(latestSnapshot(snapshots)).toEqual([timelineClip('A')]);
    expect(warn).not.toHaveBeenCalled();
  });

  it('clears gallery and renders additive marquee timeline clips with real data in the same render', () => {
    setTimelineClipData([timelineClip('A'), timelineClip('B')]);
    userSelectGalleryItem(galleryItem('G'), { additive: false });
    const { snapshots } = renderAttachmentRecorder();

    act(() => {
      userSelectTimelineClips(['A', 'B'], { additive: true });
    });

    expect([...__getSelectionStateForTests().gallery.selectedGalleryIds]).toEqual([]);
    expect(latestSnapshot(snapshots)).toEqual([timelineClip('A'), timelineClip('B')]);
  });

  it('fills the single-clip gap with a placeholder until timeline clip data resolves', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});

    userSelectGalleryItem(galleryItem('G'), { additive: false });
    const { snapshots } = renderAttachmentRecorder();

    act(() => {
      userSelectTimelineClip('clipA', { additive: false });
    });

    expectAllRendersNonEmpty(snapshots);
    expect(snapshots).toContainEqual([
      expect.objectContaining({
        clipId: 'clipA',
        isPlaceholder: true,
      }),
    ]);
    expect(warn).toHaveBeenCalledWith('[currentAttachmentSet] 1 placeholder(s) rendered');

    warn.mockClear();

    act(() => {
      setTimelineClipData([timelineClip('clipA')]);
    });

    expect(latestSnapshot(snapshots)).toEqual([timelineClip('clipA')]);
    expect(warn).not.toHaveBeenCalled();
  });

  it('toggles a single additive timeline selection on and off', () => {
    setTimelineClipData([timelineClip('A')]);
    const { snapshots } = renderAttachmentRecorder();

    act(() => {
      userSelectTimelineClip('A', { additive: true });
    });

    expect(latestSnapshot(snapshots)).toEqual([timelineClip('A')]);

    act(() => {
      userSelectTimelineClip('A', { additive: true });
    });

    expect(latestSnapshot(snapshots)).toEqual([]);
    expect([...__getSelectionStateForTests().timeline.selectedClipIds]).toEqual([]);
  });

  /*
   * Test 5 specifically locks the mergeSelectedClips merge-key contract: dedupe
   * is by clipId || url. Without the fix, multiple placeholders (all url:'')
   * would collapse and the visible chip count would jump when real data arrives.
   */
  it('keeps multiple placeholders distinct through partial and full timeline data resolution', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { snapshots } = renderAttachmentRecorder();

    act(() => {
      userSelectTimelineClip('clipA', { additive: false });
    });

    act(() => {
      userSelectTimelineClip('clipB', { additive: true });
    });

    const selectedUnknownSnapshots = snapshots.filter((snapshot) => (
      snapshot.some((clip) => clip.clipId === 'clipA')
      && snapshot.some((clip) => clip.clipId === 'clipB')
    ));

    expect(selectedUnknownSnapshots).not.toEqual([]);
    for (const snapshot of selectedUnknownSnapshots) {
      expect(snapshot).toHaveLength(2);
    }

    expect(latestSnapshot(snapshots)).toEqual([
      expect.objectContaining({ clipId: 'clipA', isPlaceholder: true }),
      expect.objectContaining({ clipId: 'clipB', isPlaceholder: true }),
    ]);
    expect(warn).toHaveBeenCalled();

    act(() => {
      setTimelineClipData([timelineClip('clipA')]);
    });

    expect(latestSnapshot(snapshots)).toEqual([
      timelineClip('clipA'),
      expect.objectContaining({ clipId: 'clipB', isPlaceholder: true }),
    ]);
    expect(latestSnapshot(snapshots)).toHaveLength(2);

    act(() => {
      setTimelineClipData([timelineClip('clipA'), timelineClip('clipB')]);
    });

    expect(latestSnapshot(snapshots)).toEqual([
      timelineClip('clipA'),
      timelineClip('clipB'),
    ]);
    expect(latestSnapshot(snapshots)).toHaveLength(2);
  });
});
