import { useMemo } from 'react';
import { shallow } from 'zustand/shallow';
import { useSelectionStore } from '@/shared/state/selectionStore';
import {
  buildSummary,
  type SelectedMediaClip,
} from '@/tools/video-editor/hooks/useSelectedMediaClips';

export type { SelectedMediaClip };

export function mergeSelectedClips(
  timelineClips: SelectedMediaClip[],
  galleryClips: SelectedMediaClip[],
): SelectedMediaClip[] {
  const clipsByKey = new Map<string, SelectedMediaClip>();

  for (const clip of [...timelineClips, ...galleryClips]) {
    // Placeholder clips all have url:'' until editor data arrives. Key them by
    // clipId so multiple selected-but-unknown timeline clips do not collapse.
    const key = clip.isPlaceholder ? clip.clipId : clip.url;
    const existing = clipsByKey.get(key);
    if (existing) {
      const preferIncoming = !existing.generationId && Boolean(clip.generationId);
      const preferred = preferIncoming ? clip : existing;
      const secondary = preferIncoming ? existing : clip;

      clipsByKey.set(key, {
        ...preferred,
        generationId: preferred.generationId ?? secondary.generationId,
        variantId: preferred.variantId ?? secondary.variantId,
        isTimelineBacked: preferred.isTimelineBacked || secondary.isTimelineBacked,
        isPlaceholder: preferred.isPlaceholder && secondary.isPlaceholder,
        shotId: preferred.shotId ?? secondary.shotId,
        shotName: preferred.shotName ?? secondary.shotName,
        shotSelectionClipCount: preferred.shotSelectionClipCount ?? secondary.shotSelectionClipCount,
        trackId: preferred.trackId ?? secondary.trackId,
        at: preferred.at ?? secondary.at,
        duration: preferred.duration ?? secondary.duration,
        assetKey: preferred.assetKey || secondary.assetKey,
      });
      continue;
    }

    clipsByKey.set(key, clip);
  }

  return Array.from(clipsByKey.values());
}

export function makePlaceholderClip(clipId: string): SelectedMediaClip {
  return {
    clipId,
    assetKey: '',
    url: '',
    mediaType: 'image',
    isTimelineBacked: true,
    isPlaceholder: true,
  };
}

export function useCurrentAttachmentSet(): { clips: SelectedMediaClip[]; summary: string } {
  const { selectedClipIds, clipDataById, selectedGalleryClips } = useSelectionStore((state) => ({
    selectedClipIds: state.timeline.selectedClipIds,
    clipDataById: state.clipDataById,
    selectedGalleryClips: state.gallery.selectedGalleryClips,
  }), shallow);

  return useMemo(() => {
    let placeholderCount = 0;
    const timelineClips = Array.from(selectedClipIds, (clipId) => {
      const clip = clipDataById.get(clipId);
      if (clip) {
        return clip;
      }

      placeholderCount += 1;
      return makePlaceholderClip(clipId);
    });
    const clips = mergeSelectedClips(timelineClips, selectedGalleryClips);

    if (placeholderCount > 0 && import.meta.env.DEV) {
      console.warn(`[currentAttachmentSet] ${placeholderCount} placeholder(s) rendered`);
    }

    return {
      clips,
      summary: buildSummary(clips),
    };
  }, [clipDataById, selectedClipIds, selectedGalleryClips]);
}
