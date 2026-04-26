import {
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  type SetStateAction,
} from 'react';
import { shallow } from 'zustand/shallow';
import { useStoreWithEqualityFn } from 'zustand/traditional';
import { createStore } from 'zustand/vanilla';
import {
  buildSummary,
  type SelectedMediaClip,
} from '@/tools/video-editor/hooks/useSelectedMediaClips';

type GallerySelectionMediaType = 'image' | 'video';

type GallerySelectionEntry = {
  url: string;
  mediaType: GallerySelectionMediaType;
  generationId: string;
  variantId?: string;
};

export type GallerySelectionMeta = {
  url: string;
  type?: string | null;
  mediaType?: string | null;
  generationId?: string | null;
  variantId?: string | null;
};

export type GallerySelectionItem = GallerySelectionMeta & {
  id: string;
};

export interface SelectClipOptions {
  toggle?: boolean;
  preserveSelection?: boolean;
}

interface GallerySliceState {
  gallerySelectionMap: ReadonlyMap<string, GallerySelectionEntry>;
  selectedGalleryIds: ReadonlySet<string>;
  selectedGalleryClips: SelectedMediaClip[];
  gallerySummary: string;
}

interface TimelineSliceState {
  selectedClipId: string | null;
  selectedTrackId: string | null;
  selectedClipIds: ReadonlySet<string>;
  primaryClipId: string | null;
  additiveSelection: boolean;
}

interface ShotSliceState {
  currentShotId: string | null;
  lastAffectedShotId: string | null;
  shotAdditionSelectedShotId: string | null;
}

interface SelectionStoreState {
  gallery: GallerySliceState;
  timeline: TimelineSliceState;
  shot: ShotSliceState;
  clipDataById: ReadonlyMap<string, SelectedMediaClip>;
  clearGallerySelection: () => void;
  selectGalleryItem: (
    id: string,
    meta: GallerySelectionMeta,
    options?: { toggle?: boolean },
  ) => void;
  selectGalleryItems: (
    items: GallerySelectionItem[],
    options?: { append?: boolean },
  ) => void;
  deselectGalleryItems: (ids: Iterable<string>) => void;
  /**
   * Clears timeline clip selection and preserves the selected track.
   *
   * Note: opposite gallery default from `selectTimelineClip` and
   * `selectTimelineClips`. Gallery selection is preserved by default; pass
   * `{ clearGallery: true }` only when the caller intentionally wants to clear
   * gallery selection too.
   */
  clearTimelineSelection: (options?: { clearGallery?: boolean }) => void;
  /**
   * Selects one timeline clip.
   *
   * Without `options.toggle`, this replaces the timeline clip set with the
   * single clip and makes it primary. With `options.toggle`, the clip is added
   * or removed from the existing timeline selection and the primary clip is
   * recomputed. Gallery selection clears by default; pass
   * `{ clearGallery: false }` for editor-internal timeline mutations that must
   * preserve gallery selection.
   */
  selectTimelineClip: (
    clipId: string,
    options?: SelectClipOptions,
    syncOptions?: { clearGallery?: boolean },
  ) => void;
  /**
   * Replaces the entire timeline clip selection with `clipIds`.
   *
   * The primary clip is derived from the replacement set and additive selection
   * is enabled when more than one clip remains selected. Gallery selection
   * clears by default; pass `{ clearGallery: false }` for editor-internal
   * timeline mutations that must preserve gallery selection.
   */
  selectTimelineClips: (
    clipIds: Iterable<string>,
    syncOptions?: { clearGallery?: boolean },
  ) => void;
  /**
   * Adds clips to the existing timeline selection without clearing existing
   * selected clips or gallery selection.
   *
   * The primary clip is preserved when possible and recomputed only if needed.
   */
  addTimelineClips: (clipIds: Iterable<string>) => void;
  /**
   * Removes selected timeline clips that are not present in `validIds`.
   *
   * Preserves the selected track and gallery selection, and recomputes the
   * primary clip from the remaining valid selection.
   */
  pruneTimelineSelection: (validIds: Set<string>) => void;
  setTimelineSelectedTrackId: (trackId: string | null) => void;
  resetTimelineSelection: () => void;
  setCurrentShotId: (shotId: string | null) => void;
  setLastAffectedShotId: (shotIdOrUpdater: SetStateAction<string | null>) => void;
  hydrateLastAffectedShotId: (shotId: string | null) => void;
  selectShotForAddition: (shotId: string) => void;
  clearSelectedShotForAddition: () => void;
  resetForProjectChange: () => void;
}

const initialGalleryState = (): GallerySliceState => ({
  gallerySelectionMap: new Map(),
  selectedGalleryIds: new Set(),
  selectedGalleryClips: [],
  gallerySummary: '',
});

const initialTimelineState = (): TimelineSliceState => ({
  selectedClipId: null,
  selectedTrackId: null,
  selectedClipIds: new Set(),
  primaryClipId: null,
  additiveSelection: false,
});

const initialShotState = (): ShotSliceState => ({
  currentShotId: null,
  lastAffectedShotId: null,
  shotAdditionSelectedShotId: null,
});

const initialClipDataById = (): ReadonlyMap<string, SelectedMediaClip> => new Map();

function resolveMediaType(value: string | null | undefined): GallerySelectionMediaType | null {
  if (!value) {
    return null;
  }

  if (value.includes('image')) {
    return 'image';
  }

  if (value.includes('video')) {
    return 'video';
  }

  return null;
}

function normalizeSelectionItem(item: GallerySelectionItem): (GallerySelectionEntry & { id: string }) | null {
  const id = item.id.trim();
  const url = item.url.trim();
  const mediaType = resolveMediaType(item.mediaType ?? item.type);
  const generationId = (item.generationId ?? item.id).trim();

  if (!id || !url || !mediaType || !generationId) {
    return null;
  }

  return {
    id,
    url,
    mediaType,
    generationId,
    ...(item.variantId?.trim() ? { variantId: item.variantId.trim() } : {}),
  };
}

function hasSameSelection(
  selectionMap: ReadonlyMap<string, GallerySelectionEntry>,
  items: readonly (GallerySelectionEntry & { id: string })[],
): boolean {
  if (selectionMap.size !== items.length) {
    return false;
  }

  return items.every((item) => {
    const existing = selectionMap.get(item.id);
    return existing?.url === item.url
      && existing.mediaType === item.mediaType
      && existing.generationId === item.generationId
      && existing.variantId === item.variantId;
  });
}

function getFirstSelectedClipId(clipIds: ReadonlySet<string>): string | null {
  for (const clipId of clipIds) {
    return clipId;
  }

  return null;
}

function getPrimaryClipId(
  clipIds: ReadonlySet<string>,
  preferredClipId: string | null,
): string | null {
  if (preferredClipId && clipIds.has(preferredClipId)) {
    return preferredClipId;
  }

  return getFirstSelectedClipId(clipIds);
}

function areSetsEqual(left: ReadonlySet<string>, right: ReadonlySet<string>): boolean {
  if (left.size !== right.size) {
    return false;
  }

  for (const value of left) {
    if (!right.has(value)) {
      return false;
    }
  }

  return true;
}

function buildGalleryState(
  selectionMap: ReadonlyMap<string, GallerySelectionEntry>,
): GallerySliceState {
  const selectedGalleryIds = new Set(selectionMap.keys());
  const selectedGalleryClips: SelectedMediaClip[] = Array.from(selectionMap.entries()).map(([id, item]) => ({
    clipId: id,
    assetKey: item.generationId,
    url: item.url,
    mediaType: item.mediaType,
    isTimelineBacked: false,
    generationId: item.generationId,
    variantId: item.variantId,
  }));

  return {
    gallerySelectionMap: selectionMap,
    selectedGalleryIds,
    selectedGalleryClips,
    gallerySummary: buildSummary(selectedGalleryClips),
  };
}

function buildTimelineState(
  selectedClipIds: ReadonlySet<string>,
  preferredPrimaryClipId: string | null,
  selectedTrackId: string | null,
  additiveSelection: boolean,
): TimelineSliceState {
  const primaryClipId = getPrimaryClipId(selectedClipIds, preferredPrimaryClipId);
  return {
    selectedClipId: primaryClipId,
    selectedTrackId,
    selectedClipIds,
    primaryClipId,
    additiveSelection: additiveSelection && selectedClipIds.size > 1,
  };
}

function clearTimelineClipSelection(
  timeline: TimelineSliceState,
): TimelineSliceState {
  if (
    timeline.selectedClipIds.size === 0
    && timeline.selectedClipId === null
    && timeline.primaryClipId === null
    && !timeline.additiveSelection
  ) {
    return timeline;
  }

  return {
    ...timeline,
    selectedClipId: null,
    selectedClipIds: new Set(),
    primaryClipId: null,
    additiveSelection: false,
  };
}

function computeTimelineReplacement(
  timeline: TimelineSliceState,
  clipIds: Iterable<string>,
): TimelineSliceState {
  const nextSelection = new Set(clipIds);
  return buildTimelineState(
    nextSelection,
    null,
    timeline.selectedTrackId,
    nextSelection.size > 1,
  );
}

function computeTimelineSingleSelection(
  timeline: TimelineSliceState,
  clipId: string,
  options?: SelectClipOptions,
): TimelineSliceState {
  const currentSelection = timeline.selectedClipIds;
  const currentPrimary = timeline.primaryClipId;

  let nextSelection: ReadonlySet<string>;
  let nextPrimary = clipId;

  if (!options?.toggle) {
    nextSelection = new Set([clipId]);
  } else {
    const mutableSelection = new Set(currentSelection);
    if (mutableSelection.has(clipId)) {
      mutableSelection.delete(clipId);
      nextPrimary = getPrimaryClipId(
        mutableSelection,
        currentPrimary === clipId ? null : currentPrimary,
      ) ?? null;
    } else {
      mutableSelection.add(clipId);
    }
    nextSelection = mutableSelection;
  }

  return buildTimelineState(
    nextSelection,
    nextPrimary,
    timeline.selectedTrackId,
    nextSelection.size > 1,
  );
}

function computeTimelineAppend(
  timeline: TimelineSliceState,
  clipIds: Iterable<string>,
): TimelineSliceState {
  const mergedSelection = new Set(timeline.selectedClipIds);
  for (const clipId of clipIds) {
    mergedSelection.add(clipId);
  }

  return buildTimelineState(
    mergedSelection,
    getPrimaryClipId(mergedSelection, timeline.primaryClipId),
    timeline.selectedTrackId,
    mergedSelection.size > 1,
  );
}

function computeTimelinePrune(
  timeline: TimelineSliceState,
  validIds: ReadonlySet<string>,
): TimelineSliceState {
  const nextSelection = new Set<string>();
  for (const clipId of timeline.selectedClipIds) {
    if (validIds.has(clipId)) {
      nextSelection.add(clipId);
    }
  }

  return buildTimelineState(
    nextSelection,
    getPrimaryClipId(nextSelection, timeline.primaryClipId),
    timeline.selectedTrackId,
    timeline.additiveSelection,
  );
}

function hasSameTimelineState(left: TimelineSliceState, right: TimelineSliceState): boolean {
  return areSetsEqual(left.selectedClipIds, right.selectedClipIds)
    && left.primaryClipId === right.primaryClipId
    && left.selectedClipId === right.selectedClipId
    && left.selectedTrackId === right.selectedTrackId
    && left.additiveSelection === right.additiveSelection;
}

type AttachmentMatch = {
  url: string;
  mediaType: 'image' | 'video';
  generationId?: string | null;
  clipId?: string | null;
};

function matchesAttachment(
  clip: Pick<SelectedMediaClip, 'url' | 'mediaType' | 'generationId' | 'clipId'>,
  match: AttachmentMatch,
  options?: { matchClipId?: boolean },
): boolean {
  if (clip.url !== match.url || clip.mediaType !== match.mediaType) {
    return false;
  }

  if (match.generationId && clip.generationId !== match.generationId) {
    return false;
  }

  if (options?.matchClipId && match.clipId && clip.clipId !== match.clipId) {
    return false;
  }

  return true;
}

const selectionStore = createStore<SelectionStoreState>((set) => ({
  gallery: initialGalleryState(),
  timeline: initialTimelineState(),
  shot: initialShotState(),
  clipDataById: initialClipDataById(),

  clearGallerySelection: () => {
    set((state) => (
      state.gallery.gallerySelectionMap.size === 0
        ? state
        : { gallery: initialGalleryState() }
    ));
  },

  selectGalleryItem: (id, meta, options) => {
    const normalized = normalizeSelectionItem({ id, ...meta });
    if (!normalized) {
      return;
    }

    set((state) => {
      const previous = state.gallery.gallerySelectionMap;
      if (!options?.toggle) {
        if (hasSameSelection(previous, [normalized])) {
          return state;
        }

        return {
          gallery: buildGalleryState(new Map([
            [
              normalized.id,
              {
                url: normalized.url,
                mediaType: normalized.mediaType,
                generationId: normalized.generationId,
                variantId: normalized.variantId,
              },
            ],
          ])),
          timeline: clearTimelineClipSelection(state.timeline),
        };
      }

      const next = new Map(previous);
      if (next.has(normalized.id)) {
        next.delete(normalized.id);
      } else {
        next.set(normalized.id, {
          url: normalized.url,
          mediaType: normalized.mediaType,
          generationId: normalized.generationId,
          variantId: normalized.variantId,
        });
      }

      return { gallery: buildGalleryState(next) };
    });
  },

  selectGalleryItems: (items, options) => {
    const normalizedItems = items
      .map(normalizeSelectionItem)
      .filter((item): item is GallerySelectionEntry & { id: string } => item !== null);

    set((state) => {
      const previous = state.gallery.gallerySelectionMap;
      if (normalizedItems.length === 0) {
        if (options?.append || previous.size === 0) {
          return state;
        }

        return {
          gallery: initialGalleryState(),
          timeline: clearTimelineClipSelection(state.timeline),
        };
      }

      const next = options?.append ? new Map(previous) : new Map<string, GallerySelectionEntry>();
      let changed = !options?.append && !hasSameSelection(previous, normalizedItems);

      for (const item of normalizedItems) {
        const nextEntry = {
          url: item.url,
          mediaType: item.mediaType,
          generationId: item.generationId,
          variantId: item.variantId,
        };
        const previousEntry = previous.get(item.id);
        if (
          !previousEntry
          || previousEntry.url !== nextEntry.url
          || previousEntry.mediaType !== nextEntry.mediaType
          || previousEntry.generationId !== nextEntry.generationId
          || previousEntry.variantId !== nextEntry.variantId
        ) {
          changed = true;
        }
        next.set(item.id, nextEntry);
      }

      if (!changed && next.size === previous.size) {
        return state;
      }

      return options?.append
        ? { gallery: buildGalleryState(next) }
        : {
            gallery: buildGalleryState(next),
            timeline: clearTimelineClipSelection(state.timeline),
          };
    });
  },

  deselectGalleryItems: (ids) => {
    const idsToRemove = new Set(ids);
    if (idsToRemove.size === 0) {
      return;
    }

    set((state) => {
      let changed = false;
      const next = new Map(state.gallery.gallerySelectionMap);

      idsToRemove.forEach((id) => {
        if (next.delete(id)) {
          changed = true;
        }
      });

      return changed ? { gallery: buildGalleryState(next) } : state;
    });
  },

  clearTimelineSelection: (options) => {
    set((state) => {
      const nextTimeline = clearTimelineClipSelection(state.timeline);
      const nextGallery = options?.clearGallery ? initialGalleryState() : state.gallery;
      if (nextTimeline === state.timeline && nextGallery === state.gallery) {
        return state;
      }
      return {
        timeline: nextTimeline,
        gallery: nextGallery,
      };
    });
  },

  selectTimelineClip: (clipId, options, syncOptions) => {
    set((state) => {
      if (options?.preserveSelection && state.timeline.selectedClipIds.has(clipId)) {
        return state;
      }

      const nextTimeline = computeTimelineSingleSelection(state.timeline, clipId, options);

      if (hasSameTimelineState(state.timeline, nextTimeline)) {
        return state;
      }

      return {
        timeline: nextTimeline,
        gallery: syncOptions?.clearGallery === false ? state.gallery : initialGalleryState(),
      };
    });
  },

  selectTimelineClips: (clipIds, syncOptions) => {
    const nextSelection = new Set(clipIds);

    set((state) => {
      const nextTimeline = computeTimelineReplacement(state.timeline, nextSelection);

      if (hasSameTimelineState(state.timeline, nextTimeline)) {
        return state;
      }

      return {
        timeline: nextTimeline,
        gallery: syncOptions?.clearGallery === false ? state.gallery : initialGalleryState(),
      };
    });
  },

  addTimelineClips: (clipIds) => {
    const nextClipIds = new Set(clipIds);

    set((state) => {
      const nextTimeline = computeTimelineAppend(state.timeline, nextClipIds);

      if (hasSameTimelineState(state.timeline, nextTimeline)) {
        return state;
      }

      return {
        timeline: nextTimeline,
      };
    });
  },

  pruneTimelineSelection: (validIds) => {
    set((state) => {
      const nextTimeline = computeTimelinePrune(state.timeline, validIds);
      if (hasSameTimelineState(state.timeline, nextTimeline)) {
        return state;
      }

      return {
        timeline: nextTimeline,
      };
    });
  },

  setTimelineSelectedTrackId: (trackId) => {
    set((state) => (
      state.timeline.selectedTrackId === trackId
        ? state
        : {
            timeline: {
              ...state.timeline,
              selectedTrackId: trackId,
            },
          }
    ));
  },

  resetTimelineSelection: () => {
    set((state) => ({
      timeline: {
        ...initialTimelineState(),
        selectedTrackId: state.timeline.selectedTrackId,
      },
    }));
  },

  setCurrentShotId: (shotId) => {
    set((state) => (
      state.shot.currentShotId === shotId
        ? state
        : {
            shot: {
              ...state.shot,
              currentShotId: shotId,
            },
          }
    ));
  },

  setLastAffectedShotId: (shotIdOrUpdater) => {
    set((state) => {
      const nextValue = typeof shotIdOrUpdater === 'function'
        ? shotIdOrUpdater(state.shot.lastAffectedShotId)
        : shotIdOrUpdater;

      return state.shot.lastAffectedShotId === nextValue
        ? state
        : {
            shot: {
              ...state.shot,
              lastAffectedShotId: nextValue,
            },
          };
    });
  },

  hydrateLastAffectedShotId: (shotId) => {
    set((state) => (
      state.shot.lastAffectedShotId === shotId
        ? state
        : {
            shot: {
              ...state.shot,
              lastAffectedShotId: shotId,
            },
          }
    ));
  },

  selectShotForAddition: (shotId) => {
    set((state) => (
      state.shot.shotAdditionSelectedShotId === shotId
        ? state
        : {
            shot: {
              ...state.shot,
              shotAdditionSelectedShotId: shotId,
            },
          }
    ));
  },

  clearSelectedShotForAddition: () => {
    set((state) => (
      state.shot.shotAdditionSelectedShotId === null
        ? state
        : {
            shot: {
              ...state.shot,
              shotAdditionSelectedShotId: null,
            },
          }
    ));
  },

  resetForProjectChange: () => {
    set({
      gallery: initialGalleryState(),
      timeline: initialTimelineState(),
      shot: {
        ...initialShotState(),
        currentShotId: null,
        lastAffectedShotId: null,
      },
      clipDataById: initialClipDataById(),
    });
  },
}));

export function useSelectionStore<T>(
  selector: (state: SelectionStoreState) => T,
  equalityFn?: (left: T, right: T) => boolean,
): T {
  return useStoreWithEqualityFn(selectionStore, selector, equalityFn);
}

export function userSelectGalleryItem(
  item: GallerySelectionItem,
  opts: { additive: boolean },
): void {
  const normalized = normalizeSelectionItem(item);
  if (!normalized) {
    return;
  }

  selectionStore.setState((state) => {
    const previous = state.gallery.gallerySelectionMap;
    // Single-click gallery intent (additive=false) is a context shift to the
    // gallery surface — clear timeline selection so the agent-chat attachment
    // set reflects ONLY what the user just clicked. Additive (Cmd+click) is a
    // multi-select extension of the current surface and does NOT clear timeline.
    const shouldClearTimeline = !opts.additive;
    const nextTimeline = shouldClearTimeline ? clearTimelineClipSelection(state.timeline) : state.timeline;
    const timelinePatch = hasSameTimelineState(state.timeline, nextTimeline)
      ? null
      : { timeline: nextTimeline };

    if (!opts.additive) {
      if (hasSameSelection(previous, [normalized])) {
        return timelinePatch ?? state;
      }

      return {
        ...(timelinePatch ?? {}),
        gallery: buildGalleryState(new Map([
          [
            normalized.id,
            {
              url: normalized.url,
              mediaType: normalized.mediaType,
              generationId: normalized.generationId,
              variantId: normalized.variantId,
            },
          ],
        ])),
      };
    }

    const next = new Map(previous);
    if (next.has(normalized.id)) {
      next.delete(normalized.id);
    } else {
      next.set(normalized.id, {
        url: normalized.url,
        mediaType: normalized.mediaType,
        generationId: normalized.generationId,
        variantId: normalized.variantId,
      });
    }

    return { gallery: buildGalleryState(next) };
  });
}

export function userSelectGalleryItems(
  items: GallerySelectionItem[],
  opts: { additive: boolean },
): void {
  const normalizedItems = items
    .map(normalizeSelectionItem)
    .filter((item): item is GallerySelectionEntry & { id: string } => item !== null);

  selectionStore.setState((state) => {
    const previous = state.gallery.gallerySelectionMap;
    // Same rule as userSelectGalleryItem: replace-marquee (additive=false) clears
    // timeline; append-marquee (additive=true) preserves it.
    const shouldClearTimeline = !opts.additive;
    const nextTimeline = shouldClearTimeline ? clearTimelineClipSelection(state.timeline) : state.timeline;
    const timelinePatch = hasSameTimelineState(state.timeline, nextTimeline)
      ? null
      : { timeline: nextTimeline };

    if (normalizedItems.length === 0) {
      if (opts.additive || previous.size === 0) {
        return timelinePatch ?? state;
      }
      return { ...(timelinePatch ?? {}), gallery: initialGalleryState() };
    }

    const next = opts.additive ? new Map(previous) : new Map<string, GallerySelectionEntry>();
    let changed = !opts.additive && !hasSameSelection(previous, normalizedItems);

    for (const item of normalizedItems) {
      const nextEntry = {
        url: item.url,
        mediaType: item.mediaType,
        generationId: item.generationId,
        variantId: item.variantId,
      };
      const previousEntry = previous.get(item.id);
      if (
        !previousEntry
        || previousEntry.url !== nextEntry.url
        || previousEntry.mediaType !== nextEntry.mediaType
        || previousEntry.generationId !== nextEntry.generationId
        || previousEntry.variantId !== nextEntry.variantId
      ) {
        changed = true;
      }
      next.set(item.id, nextEntry);
    }

    if (changed || next.size !== previous.size) {
      return { ...(timelinePatch ?? {}), gallery: buildGalleryState(next) };
    }
    return timelinePatch ?? state;
  });
}

/**
 * User single-click timeline intent.
 *
 * `additive: true` means TOGGLE for one clip: Cmd/Ctrl/Shift-clicking an
 * already-selected clip removes it from the timeline selection.
 */
export function userSelectTimelineClip(
  clipId: string,
  opts: { additive: boolean; preserveIfSelected?: boolean },
): void {
  selectionStore.setState((state) => {
    if (opts.preserveIfSelected && state.timeline.selectedClipIds.has(clipId)) {
      return state;
    }

    const nextTimeline = computeTimelineSingleSelection(
      state.timeline,
      clipId,
      { toggle: opts.additive },
    );

    return {
      timeline: hasSameTimelineState(state.timeline, nextTimeline) ? state.timeline : nextTimeline,
      gallery: initialGalleryState(),
    };
  });
}

/**
 * User marquee timeline intent.
 *
 * `additive: true` means APPEND-ONLY for marquee selection. It never toggles
 * existing selected clips off.
 */
export function userSelectTimelineClips(
  clipIds: Iterable<string>,
  opts: { additive: boolean },
): void {
  const nextClipIds = new Set(clipIds);
  selectionStore.setState((state) => {
    const nextTimeline = opts.additive
      ? computeTimelineAppend(state.timeline, nextClipIds)
      : computeTimelineReplacement(state.timeline, nextClipIds);

    return {
      timeline: hasSameTimelineState(state.timeline, nextTimeline) ? state.timeline : nextTimeline,
      gallery: initialGalleryState(),
    };
  });
}

export function userClearAllSelection(): void {
  selectionStore.setState((state) => ({
    gallery: state.gallery.gallerySelectionMap.size === 0 ? state.gallery : initialGalleryState(),
    timeline: clearTimelineClipSelection(state.timeline),
  }));
}

export function composerRemoveAttachment(match: AttachmentMatch): void {
  selectionStore.setState((state) => {
    let galleryChanged = false;
    const nextGalleryMap = new Map(state.gallery.gallerySelectionMap);
    for (const [id, entry] of nextGalleryMap) {
      if (matchesAttachment({
        clipId: id,
        url: entry.url,
        mediaType: entry.mediaType,
        generationId: entry.generationId,
      }, match)) {
        nextGalleryMap.delete(id);
        galleryChanged = true;
      }
    }

    let timelineChanged = false;
    const nextTimelineIds = new Set(state.timeline.selectedClipIds);
    for (const clipId of state.timeline.selectedClipIds) {
      const clip = state.clipDataById.get(clipId);
      const shouldRemove = clip
        ? matchesAttachment(clip, match, { matchClipId: true })
        : false;

      if (shouldRemove) {
        nextTimelineIds.delete(clipId);
        timelineChanged = true;
      }
    }

    return {
      gallery: galleryChanged ? buildGalleryState(nextGalleryMap) : state.gallery,
      timeline: timelineChanged
        ? buildTimelineState(
            nextTimelineIds,
            getPrimaryClipId(nextTimelineIds, state.timeline.primaryClipId),
            state.timeline.selectedTrackId,
            state.timeline.additiveSelection,
          )
        : state.timeline,
    };
  });
}

export function composerClearAttachments(): void {
  selectionStore.setState((state) => ({
    gallery: state.gallery.gallerySelectionMap.size === 0 ? state.gallery : initialGalleryState(),
    timeline: clearTimelineClipSelection(state.timeline),
  }));
}

export function editorReplaceTimelineSelection(clipIds: Iterable<string>): void {
  const nextClipIds = new Set(clipIds);
  selectionStore.setState((state) => {
    const nextTimeline = computeTimelineReplacement(state.timeline, nextClipIds);
    return hasSameTimelineState(state.timeline, nextTimeline)
      ? state
      : { timeline: nextTimeline };
  });
}

export function editorSelectTimelineClip(clipId: string | null): void {
  selectionStore.setState((state) => {
    const nextTimeline = clipId
      ? computeTimelineSingleSelection(state.timeline, clipId)
      : clearTimelineClipSelection(state.timeline);
    return hasSameTimelineState(state.timeline, nextTimeline)
      ? state
      : { timeline: nextTimeline };
  });
}

export function editorClearTimelineSelection(): void {
  selectionStore.setState((state) => {
    const nextTimeline = clearTimelineClipSelection(state.timeline);
    return nextTimeline === state.timeline ? state : { timeline: nextTimeline };
  });
}

export function editorSetSelectedTrackId(trackId: string | null): void {
  selectionStore.setState((state) => (
    state.timeline.selectedTrackId === trackId
      ? state
      : {
          timeline: {
            ...state.timeline,
            selectedTrackId: trackId,
          },
        }
  ));
}

export function systemPruneTimelineSelection(validIds: ReadonlySet<string>): void {
  selectionStore.setState((state) => {
    const nextTimeline = computeTimelinePrune(state.timeline, validIds);
    return hasSameTimelineState(state.timeline, nextTimeline)
      ? state
      : { timeline: nextTimeline };
  });
}

export function systemResetTimelineSelection(): void {
  selectionStore.setState({ timeline: initialTimelineState() });
}

export function systemResetSelectionForProjectChange(): void {
  selectionStore.setState({
    gallery: initialGalleryState(),
    timeline: initialTimelineState(),
    shot: {
      ...initialShotState(),
      currentShotId: null,
      lastAffectedShotId: null,
    },
    clipDataById: initialClipDataById(),
  });
}

export function systemSyncGallerySelection(items: GallerySelectionItem[]): void {
  // System-level gallery sync (e.g. external state hydration). Does NOT clear
  // timeline — user-intent commands do that, system ones never should.
  const normalizedItems = items
    .map(normalizeSelectionItem)
    .filter((item): item is GallerySelectionEntry & { id: string } => item !== null);

  selectionStore.setState((state) => {
    const previous = state.gallery.gallerySelectionMap;
    if (normalizedItems.length === 0) {
      return previous.size === 0 ? state : { gallery: initialGalleryState() };
    }

    const next = new Map<string, GallerySelectionEntry>();
    let changed = !hasSameSelection(previous, normalizedItems);

    for (const item of normalizedItems) {
      const nextEntry = {
        url: item.url,
        mediaType: item.mediaType,
        generationId: item.generationId,
        variantId: item.variantId,
      };
      const previousEntry = previous.get(item.id);
      if (
        !previousEntry
        || previousEntry.url !== nextEntry.url
        || previousEntry.mediaType !== nextEntry.mediaType
        || previousEntry.generationId !== nextEntry.generationId
        || previousEntry.variantId !== nextEntry.variantId
      ) {
        changed = true;
      }
      next.set(item.id, nextEntry);
    }

    return changed || next.size !== previous.size
      ? { gallery: buildGalleryState(next) }
      : state;
  });
}

export function systemClearGallerySelection(): void {
  selectionStore.setState((state) => (
    state.gallery.gallerySelectionMap.size === 0
      ? state
      : { gallery: initialGalleryState() }
  ));
}

export function systemSetCurrentShotId(shotId: string | null): void {
  selectionStore.getState().setCurrentShotId(shotId);
}

export function systemSetLastAffectedShotId(shotIdOrUpdater: SetStateAction<string | null>): void {
  selectionStore.getState().setLastAffectedShotId(shotIdOrUpdater);
}

export function setTimelineClipData(entries: Iterable<SelectedMediaClip>): void {
  selectionStore.setState({
    clipDataById: new Map(Array.from(entries, (clip) => [clip.clipId, clip])),
  });
}

export function clearTimelineClipData(): void {
  selectionStore.setState({ clipDataById: initialClipDataById() });
}

export function __getSelectionStateForTests(): SelectionStoreState {
  return selectionStore.getState();
}

export function useGallerySelectionOptional() {
  return useGallerySelection();
}

export function useGallerySelection() {
  return useSelectionStore((state) => ({
    selectedGalleryIds: state.gallery.selectedGalleryIds,
    gallerySelectionMap: state.gallery.gallerySelectionMap,
    selectedGalleryClips: state.gallery.selectedGalleryClips,
    gallerySummary: state.gallery.gallerySummary,
  }), shallow);
}

export function useCurrentShot() {
  return useSelectionStore((state) => ({
    currentShotId: state.shot.currentShotId,
    setCurrentShotId: state.setCurrentShotId,
  }), shallow);
}

export function useLastAffectedShot() {
  return useSelectionStore((state) => ({
    lastAffectedShotId: state.shot.lastAffectedShotId,
    setLastAffectedShotId: state.setLastAffectedShotId,
  }), shallow);
}

export function useShotAdditionSelectionOptional() {
  return useSelectionStore((state) => ({
    selectedShotId: state.shot.shotAdditionSelectedShotId,
    selectShotForAddition: state.selectShotForAddition,
    clearSelectedShotForAddition: state.clearSelectedShotForAddition,
  }), shallow);
}

export function useTimelineSelectionStore() {
  return useSelectionStore((state) => ({
    selectedClipId: state.timeline.selectedClipId,
    selectedTrackId: state.timeline.selectedTrackId,
    selectedClipIds: state.timeline.selectedClipIds,
    primaryClipId: state.timeline.primaryClipId,
    additiveSelection: state.timeline.additiveSelection,
  }), shallow);
}

export interface UseTimelineMultiSelectResult {
  selectedClipIds: ReadonlySet<string>;
  selectedClipIdsRef: React.MutableRefObject<Set<string>>;
  additiveSelectionRef: React.MutableRefObject<boolean>;
  primaryClipId: string | null;
  isClipSelected: (clipId: string) => boolean;
  pruneSelection: (validIds: Set<string>) => void;
}

export function useTimelineMultiSelect(): UseTimelineMultiSelectResult {
  const {
    selectedClipIds,
    primaryClipId,
    additiveSelection,
  } = useTimelineSelectionStore();

  const selectedClipIdsRef = useRef<Set<string>>(new Set(selectedClipIds));
  const additiveSelectionRef = useRef(additiveSelection);

  useLayoutEffect(() => {
    selectedClipIdsRef.current = new Set(selectedClipIds);
    additiveSelectionRef.current = additiveSelection;
  }, [additiveSelection, selectedClipIds]);

  const isClipSelected = useCallback((clipId: string) => {
    return selectedClipIdsRef.current.has(clipId);
  }, []);

  return useMemo(() => ({
    selectedClipIds,
    selectedClipIdsRef,
    additiveSelectionRef,
    primaryClipId,
    isClipSelected,
    pruneSelection: systemPruneTimelineSelection,
  }), [
    isClipSelected,
    primaryClipId,
    selectedClipIds,
  ]);
}

export function __resetSelectionStoreForTests(): void {
  selectionStore.setState({
    gallery: initialGalleryState(),
    timeline: initialTimelineState(),
    shot: initialShotState(),
    clipDataById: initialClipDataById(),
  });
}
