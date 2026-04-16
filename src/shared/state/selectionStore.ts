import {
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  type Dispatch,
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
  clearTimelineSelection: (options?: { clearGallery?: boolean }) => void;
  selectTimelineClip: (
    clipId: string,
    options?: SelectClipOptions,
    syncOptions?: { clearGallery?: boolean },
  ) => void;
  selectTimelineClips: (
    clipIds: Iterable<string>,
    syncOptions?: { clearGallery?: boolean },
  ) => void;
  addTimelineClips: (clipIds: Iterable<string>) => void;
  pruneTimelineSelection: (validIds: Set<string>) => void;
  setTimelineSelectedClipId: (
    updater: SetStateAction<string | null>,
    options?: { clearGallery?: boolean },
  ) => void;
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

const selectionStore = createStore<SelectionStoreState>((set, get) => ({
  gallery: initialGalleryState(),
  timeline: initialTimelineState(),
  shot: initialShotState(),

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
      const currentSelection = state.timeline.selectedClipIds;
      const currentPrimary = state.timeline.primaryClipId;

      if (options?.preserveSelection && currentSelection.has(clipId)) {
        return state;
      }

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

      const nextTimeline = buildTimelineState(
        nextSelection,
        nextPrimary,
        state.timeline.selectedTrackId,
        nextSelection.size > 1,
      );

      if (
        areSetsEqual(state.timeline.selectedClipIds, nextTimeline.selectedClipIds)
        && state.timeline.primaryClipId === nextTimeline.primaryClipId
        && state.timeline.selectedClipId === nextTimeline.selectedClipId
        && state.timeline.additiveSelection === nextTimeline.additiveSelection
      ) {
        return state;
      }

      return {
        timeline: nextTimeline,
        gallery: syncOptions?.clearGallery === false ? state.gallery : initialGalleryState(),
      };
    });
  },

  selectTimelineClips: (clipIds, syncOptions) => {
    const nextSelection = new Set<string>();
    for (const clipId of clipIds) {
      nextSelection.add(clipId);
    }

    set((state) => {
      const nextTimeline = buildTimelineState(
        nextSelection,
        null,
        state.timeline.selectedTrackId,
        nextSelection.size > 1,
      );

      if (
        areSetsEqual(state.timeline.selectedClipIds, nextTimeline.selectedClipIds)
        && state.timeline.primaryClipId === nextTimeline.primaryClipId
        && state.timeline.selectedClipId === nextTimeline.selectedClipId
        && state.timeline.additiveSelection === nextTimeline.additiveSelection
      ) {
        return state;
      }

      return {
        timeline: nextTimeline,
        gallery: syncOptions?.clearGallery === false ? state.gallery : initialGalleryState(),
      };
    });
  },

  addTimelineClips: (clipIds) => {
    const nextClipIds = new Set<string>();
    for (const clipId of clipIds) {
      nextClipIds.add(clipId);
    }

    set((state) => {
      const mergedSelection = new Set(state.timeline.selectedClipIds);
      nextClipIds.forEach((clipId) => mergedSelection.add(clipId));
      const nextPrimary = getPrimaryClipId(mergedSelection, state.timeline.primaryClipId);

      if (
        areSetsEqual(state.timeline.selectedClipIds, mergedSelection)
        && state.timeline.primaryClipId === nextPrimary
      ) {
        return state;
      }

      return {
        timeline: buildTimelineState(
          mergedSelection,
          nextPrimary,
          state.timeline.selectedTrackId,
          mergedSelection.size > 1,
        ),
      };
    });
  },

  pruneTimelineSelection: (validIds) => {
    set((state) => {
      const nextSelection = new Set<string>();
      for (const clipId of state.timeline.selectedClipIds) {
        if (validIds.has(clipId)) {
          nextSelection.add(clipId);
        }
      }

      const nextPrimary = getPrimaryClipId(nextSelection, state.timeline.primaryClipId);
      if (
        areSetsEqual(state.timeline.selectedClipIds, nextSelection)
        && state.timeline.primaryClipId === nextPrimary
      ) {
        return state;
      }

      return {
        timeline: buildTimelineState(
          nextSelection,
          nextPrimary,
          state.timeline.selectedTrackId,
          state.timeline.additiveSelection,
        ),
      };
    });
  },

  setTimelineSelectedClipId: (updater, options) => {
    const current = get().timeline.primaryClipId;
    const nextClipId = typeof updater === 'function'
      ? updater(current)
      : updater;

    if (nextClipId === null) {
      get().clearTimelineSelection(options);
      return;
    }

    get().selectTimelineClip(nextClipId, undefined, options);
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

  resetForProjectChange: () => ({
    gallery: initialGalleryState(),
    timeline: initialTimelineState(),
    shot: {
      ...initialShotState(),
      currentShotId: null,
      lastAffectedShotId: null,
    },
  }),
}));

export function useSelectionStoreApi() {
  return selectionStore;
}

function useSelectionStore<T>(
  selector: (state: SelectionStoreState) => T,
  equalityFn?: (left: T, right: T) => boolean,
): T {
  return useStoreWithEqualityFn(selectionStore, selector, equalityFn);
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
    selectGalleryItem: state.selectGalleryItem,
    selectGalleryItems: state.selectGalleryItems,
    deselectGalleryItems: state.deselectGalleryItems,
    clearGallerySelection: state.clearGallerySelection,
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
    setSelectedClipId: state.setTimelineSelectedClipId,
    setSelectedTrackId: state.setTimelineSelectedTrackId,
    clearSelection: state.clearTimelineSelection,
    selectClip: state.selectTimelineClip,
    selectClips: state.selectTimelineClips,
    addToSelection: state.addTimelineClips,
    pruneSelection: state.pruneTimelineSelection,
    resetSelection: state.resetTimelineSelection,
  }), shallow);
}

export interface UseTimelineMultiSelectResult {
  selectedClipIds: ReadonlySet<string>;
  selectedClipIdsRef: React.MutableRefObject<Set<string>>;
  additiveSelectionRef: React.MutableRefObject<boolean>;
  primaryClipId: string | null;
  selectClip: (clipId: string, opts?: SelectClipOptions) => void;
  selectClips: (clipIds: Iterable<string>) => void;
  addToSelection: (clipIds: Iterable<string>) => void;
  clearSelection: () => void;
  isClipSelected: (clipId: string) => boolean;
  pruneSelection: (validIds: Set<string>) => void;
}

export function useTimelineMultiSelect(): UseTimelineMultiSelectResult {
  const {
    selectedClipIds,
    primaryClipId,
    additiveSelection,
    clearSelection,
    selectClip,
    selectClips,
    addToSelection,
    pruneSelection,
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
    selectClip: (clipId: string, opts?: SelectClipOptions) => {
      selectionStore.getState().selectTimelineClip(clipId, opts, { clearGallery: false });
    },
    selectClips: (clipIds: Iterable<string>) => {
      selectionStore.getState().selectTimelineClips(clipIds, { clearGallery: false });
    },
    addToSelection,
    clearSelection: () => {
      selectionStore.getState().clearTimelineSelection({ clearGallery: false });
    },
    isClipSelected,
    pruneSelection,
  }), [
    addToSelection,
    additiveSelection,
    clearSelection,
    isClipSelected,
    primaryClipId,
    pruneSelection,
    selectClip,
    selectClips,
    selectedClipIds,
  ]);
}

export function __resetSelectionStoreForTests(): void {
  selectionStore.setState({
    gallery: initialGalleryState(),
    timeline: initialTimelineState(),
    shot: initialShotState(),
  });
}
