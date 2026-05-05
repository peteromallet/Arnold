import { useMemo } from 'react';
import { getTrackById } from '@/tools/video-editor/lib/editor-utils.ts';
import { getTimelineDurationInFrames, parseResolution } from '@/tools/video-editor/lib/config-utils.ts';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import type { TrackDefinition } from '@/tools/video-editor/types/index.ts';

export interface CompositionMetadata {
  fps: number;
  durationInFrames: number;
  compositionWidth: number;
  compositionHeight: number;
}

export function useDerivedTimeline(
  data: TimelineData | null,
  selectedClipId: string | null,
  selectedTrackId: string | null,
) {
  const resolvedConfig = useMemo(() => data?.resolvedConfig ?? null,
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional: signature covers resolved URLs
    [data?.signature],
  );

  const selectedClip = useMemo(() => {
    if (!resolvedConfig || !selectedClipId) {
      return null;
    }
    return resolvedConfig.clips.find((clip) => clip.id === selectedClipId) ?? null;
  }, [resolvedConfig, selectedClipId]);

  const selectedTrack = useMemo<TrackDefinition | null>(() => {
    if (!data) {
      return null;
    }

    const preferredTrackId = selectedClip?.track ?? selectedTrackId;
    return preferredTrackId ? getTrackById(data.resolvedConfig, preferredTrackId) : data.tracks[0] ?? null;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional: stableSignature covers structural timeline changes
  }, [data?.stableSignature, selectedClip, selectedTrackId]);

  const selectedClipHasPredecessor = useMemo(() => {
    if (!resolvedConfig || !selectedClip) {
      return false;
    }

    const siblings = resolvedConfig.clips
      .filter((clip) => clip.track === selectedClip.track)
      .sort((left, right) => left.at - right.at);
    const selectedIndex = siblings.findIndex((clip) => clip.id === selectedClip.id);
    return selectedIndex > 0;
  }, [resolvedConfig, selectedClip]);

  const compositionSize = useMemo(() => {
    return data ? parseResolution(data.output.resolution) : { width: 1280, height: 720 };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional: stableSignature covers output structure
  }, [data?.stableSignature]);

  const renderMetadata = useMemo<CompositionMetadata | null>(() => {
    if (!resolvedConfig) {
      return null;
    }

    const fps = resolvedConfig.output.fps;
    const { width, height } = parseResolution(resolvedConfig.output.resolution);

    return {
      fps,
      durationInFrames: getTimelineDurationInFrames(resolvedConfig, fps),
      compositionWidth: Math.max(1, width),
      compositionHeight: Math.max(1, height),
    };
  }, [resolvedConfig]);

  const trackScaleMap = useMemo(() => {
    if (!data) {
      return {};
    }

    return Object.fromEntries(data.tracks.map((track) => [track.id, track.scale ?? 1]));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional: stableSignature covers track structure
  }, [data?.stableSignature]);

  return {
    resolvedConfig,
    selectedClip,
    selectedTrack,
    selectedClipHasPredecessor,
    compositionSize,
    renderMetadata,
    trackScaleMap,
  };
}
