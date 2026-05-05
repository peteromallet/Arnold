import type { ClipTab } from '@/tools/video-editor/hooks/useEditorPreferences.ts';
import {
  getClipTypeOverlayBehavior,
  getRegisteredClipTypeDescriptor,
  isClipTypeCommandAvailable,
  isSequenceParamsSchema,
} from '@/tools/video-editor/clip-types/index.ts';
import type { ResolvedTimelineClip, TrackDefinition } from '@/tools/video-editor/types/index.ts';

const BASE_TABS: ClipTab[] = ['effects', 'timing'];

const buildCommandContext = (
  clip: ResolvedTimelineClip | null,
  track: TrackDefinition | null,
) => (
  clip
    ? { clip, track, selectedClipIds: [clip.id] }
    : { clip, track, selectedClipIds: [] }
);

export const getVisibleClipTabs = (
  clip: ResolvedTimelineClip | null,
  track: TrackDefinition | null,
): ClipTab[] => {
  const descriptor = getRegisteredClipTypeDescriptor(clip?.clipType);
  const overlay = getClipTypeOverlayBehavior(descriptor);
  const isSequenceClip = Boolean(descriptor && isSequenceParamsSchema(descriptor.paramsSchema));
  const isEffectLayer = descriptor?.renderCapabilities.previewRoute === 'effect-layer';
  const supportsAudio = Boolean(
    descriptor && isClipTypeCommandAvailable(descriptor, 'toggle-mute', buildCommandContext(clip, track)),
  );

  if (isEffectLayer || isSequenceClip) {
    return BASE_TABS;
  }

  const tabs: ClipTab[] = [...BASE_TABS];
  if (track?.kind === 'visual' && overlay.allowsBoundsEditing) {
    tabs.push('position');
  }
  if (supportsAudio) {
    tabs.push('audio');
  }
  if (overlay.supportsInlineTextEdit) {
    tabs.push('text');
  }
  return tabs;
};

export const getBulkVisibleTabs = (
  clips: ResolvedTimelineClip[],
  tracks: TrackDefinition[],
): ClipTab[] => {
  if (clips.length === 0) {
    return BASE_TABS;
  }

  const trackById = new Map(tracks.map((track) => [track.id, track] as const));
  const visibleTabsByClip = clips.map((clip) => getVisibleClipTabs(clip, trackById.get(clip.track) ?? null));
  const hasTab = (tab: ClipTab) => visibleTabsByClip.some((tabs) => tabs.includes(tab));
  const everyTab = (tab: ClipTab) => visibleTabsByClip.every((tabs) => tabs.includes(tab));

  const tabs: ClipTab[] = [...BASE_TABS];
  if (hasTab('position')) {
    tabs.push('position');
  }
  if (hasTab('audio')) {
    tabs.push('audio');
  }
  if (everyTab('text')) {
    tabs.push('text');
  }
  return tabs;
};

export const getSelectionDefaultClipTab = (
  clip: ResolvedTimelineClip | null,
  track: TrackDefinition | null,
): ClipTab => {
  const visibleTabs = getVisibleClipTabs(clip, track);
  return visibleTabs.includes('text') ? 'text' : 'effects';
};

export const getFallbackClipTab = (
  activeTab: ClipTab,
  visibleTabs: readonly ClipTab[],
): ClipTab => {
  return visibleTabs.includes(activeTab) ? activeTab : 'effects';
};
