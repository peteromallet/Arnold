import { beforeEach, describe, expect, it } from 'vitest';
import {
  __getSelectionStateForTests,
  __resetSelectionStoreForTests,
  composerClearAttachments,
  editorClearTimelineSelection,
  editorReplaceTimelineSelection,
  editorSelectTimelineClip,
  editorSetSelectedTrackId,
  systemClearGallerySelection,
  systemPruneTimelineSelection,
  systemResetSelectionForProjectChange,
  systemResetTimelineSelection,
  systemSetCurrentShotId,
  systemSetLastAffectedShotId,
  systemSyncGallerySelection,
  userClearAllSelection,
  userSelectGalleryItem,
  userSelectGalleryItems,
  userSelectTimelineClip,
  userSelectTimelineClips,
} from './selectionStore';

const galleryItem = (id: string, url = `https://example.test/${id}.png`) => ({
  id,
  url,
  mediaType: 'image/png',
  generationId: `generation-${id}`,
});

const selectedTimelineIds = () => [...__getSelectionStateForTests().timeline.selectedClipIds];
const selectedGalleryIds = () => [...__getSelectionStateForTests().gallery.selectedGalleryIds];

describe('selection intent actions', () => {
  beforeEach(() => {
    __resetSelectionStoreForTests();
  });

  it('user single-click gallery selection replaces gallery AND clears timeline; additive preserves timeline', () => {
    // Single-click gallery (additive: false) clears timeline — symmetric with
    // single-click timeline clearing gallery. Additive gallery (Cmd+click) is
    // a multi-select extension within the gallery surface and preserves timeline.
    editorReplaceTimelineSelection(['clip-a']);

    userSelectGalleryItem(galleryItem('gallery-a'), { additive: false });
    expect(selectedGalleryIds()).toEqual(['gallery-a']);
    expect(selectedTimelineIds()).toEqual([]);

    // Re-set timeline to test the additive preserve case.
    editorReplaceTimelineSelection(['clip-a']);

    userSelectGalleryItem(galleryItem('gallery-b'), { additive: true });
    expect(selectedGalleryIds()).toEqual(['gallery-a', 'gallery-b']);
    expect(selectedTimelineIds()).toEqual(['clip-a']);

    userSelectGalleryItem(galleryItem('gallery-b'), { additive: true });
    expect(selectedGalleryIds()).toEqual(['gallery-a']);
    expect(selectedTimelineIds()).toEqual(['clip-a']);
  });

  it('user gallery marquee replaces gallery AND clears timeline; additive marquee preserves timeline', () => {
    editorReplaceTimelineSelection(['clip-a']);
    userSelectGalleryItems([galleryItem('gallery-a')], { additive: false });
    // Replace-marquee cleared timeline.
    expect(selectedTimelineIds()).toEqual([]);

    editorReplaceTimelineSelection(['clip-a']);

    userSelectGalleryItems([galleryItem('gallery-b')], { additive: true });
    expect(selectedGalleryIds()).toEqual(['gallery-a', 'gallery-b']);
    expect(selectedTimelineIds()).toEqual(['clip-a']);

    userSelectGalleryItems([galleryItem('gallery-c')], { additive: false });
    expect(selectedGalleryIds()).toEqual(['gallery-c']);
    expect(selectedTimelineIds()).toEqual([]);
  });

  it('user single timeline additive selection toggles and clears gallery', () => {
    userSelectGalleryItem(galleryItem('gallery-a'), { additive: false });

    userSelectTimelineClip('clip-a', { additive: true });
    expect(selectedTimelineIds()).toEqual(['clip-a']);
    expect(selectedGalleryIds()).toEqual([]);

    // Verify toggle-off behavior on a clip already selected in timeline.
    userSelectTimelineClip('clip-a', { additive: true });
    expect(selectedTimelineIds()).toEqual([]);
  });

  it('user marquee timeline additive selection appends without toggling and clears gallery', () => {
    editorReplaceTimelineSelection(['clip-a']);
    userSelectGalleryItem(galleryItem('gallery-a'), { additive: false });

    userSelectTimelineClips(['clip-a', 'clip-b'], { additive: true });
    expect(selectedTimelineIds()).toEqual(['clip-a', 'clip-b']);
    expect(selectedGalleryIds()).toEqual([]);

    userSelectTimelineClips(['clip-a'], { additive: true });
    expect(selectedTimelineIds()).toEqual(['clip-a', 'clip-b']);
  });

  it('user timeline preserveIfSelected is a no-op when already selected', () => {
    // Use additive gallery select so we don't clear the timeline pre-condition.
    userSelectGalleryItem(galleryItem('gallery-seed'), { additive: false });
    editorReplaceTimelineSelection(['clip-a', 'clip-b']);
    userSelectGalleryItem(galleryItem('gallery-a'), { additive: true });

    userSelectTimelineClip('clip-a', { additive: false, preserveIfSelected: true });
    expect(selectedTimelineIds()).toEqual(['clip-a', 'clip-b']);
    expect(selectedGalleryIds()).toEqual(['gallery-seed', 'gallery-a']);
  });

  it('editor timeline commands preserve gallery selection', () => {
    userSelectGalleryItem(galleryItem('gallery-a'), { additive: false });

    editorReplaceTimelineSelection(['clip-a', 'clip-b']);
    expect(selectedTimelineIds()).toEqual(['clip-a', 'clip-b']);
    expect(selectedGalleryIds()).toEqual(['gallery-a']);

    editorSelectTimelineClip('clip-c');
    expect(selectedTimelineIds()).toEqual(['clip-c']);
    expect(selectedGalleryIds()).toEqual(['gallery-a']);

    editorSetSelectedTrackId('track-a');
    expect(__getSelectionStateForTests().timeline.selectedTrackId).toBe('track-a');
    expect(selectedGalleryIds()).toEqual(['gallery-a']);

    editorClearTimelineSelection();
    expect(selectedTimelineIds()).toEqual([]);
    expect(selectedGalleryIds()).toEqual(['gallery-a']);
  });

  it('system timeline commands reset and prune per system contracts', () => {
    userSelectGalleryItem(galleryItem('gallery-a'), { additive: false });
    editorReplaceTimelineSelection(['clip-a', 'clip-b']);

    systemPruneTimelineSelection(new Set(['clip-b']));
    expect(selectedTimelineIds()).toEqual(['clip-b']);
    expect(selectedGalleryIds()).toEqual(['gallery-a']);

    editorSetSelectedTrackId('track-a');
    systemResetTimelineSelection();
    expect(selectedTimelineIds()).toEqual([]);
    expect(__getSelectionStateForTests().timeline.selectedTrackId).toBeNull();
    expect(selectedGalleryIds()).toEqual(['gallery-a']);
  });

  it('system gallery commands sync and clear gallery without touching timeline', () => {
    editorReplaceTimelineSelection(['clip-a']);

    systemSyncGallerySelection([galleryItem('gallery-a'), galleryItem('gallery-b')]);
    expect(selectedGalleryIds()).toEqual(['gallery-a', 'gallery-b']);
    expect(selectedTimelineIds()).toEqual(['clip-a']);

    systemClearGallerySelection();
    expect(selectedGalleryIds()).toEqual([]);
    expect(selectedTimelineIds()).toEqual(['clip-a']);
  });

  it('explicit clear commands clear both attachment surfaces', () => {
    userSelectGalleryItem(galleryItem('gallery-a'), { additive: false });
    editorReplaceTimelineSelection(['clip-a']);

    userClearAllSelection();
    expect(selectedGalleryIds()).toEqual([]);
    expect(selectedTimelineIds()).toEqual([]);

    userSelectGalleryItem(galleryItem('gallery-b'), { additive: false });
    editorReplaceTimelineSelection(['clip-b']);
    composerClearAttachments();
    expect(selectedGalleryIds()).toEqual([]);
    expect(selectedTimelineIds()).toEqual([]);
  });

  it('system project and shot commands reset/hydrate state', () => {
    userSelectGalleryItem(galleryItem('gallery-a'), { additive: false });
    editorReplaceTimelineSelection(['clip-a']);
    systemSetCurrentShotId('shot-a');
    systemSetLastAffectedShotId('shot-b');

    expect(__getSelectionStateForTests().shot.currentShotId).toBe('shot-a');
    expect(__getSelectionStateForTests().shot.lastAffectedShotId).toBe('shot-b');

    systemResetSelectionForProjectChange();
    expect(selectedGalleryIds()).toEqual([]);
    expect(selectedTimelineIds()).toEqual([]);
    expect(__getSelectionStateForTests().shot.currentShotId).toBeNull();
    expect(__getSelectionStateForTests().shot.lastAffectedShotId).toBeNull();
  });
});
