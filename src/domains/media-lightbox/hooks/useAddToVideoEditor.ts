import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from '@/shared/components/ui/runtime/sonner';
import type { GenerationRow } from '@/domains/generation/types';
import { getGenerationId } from '@/shared/lib/media/mediaTypeHelpers';
import { useToolSettings } from '@/shared/hooks/settings/useToolSettings';
import { videoEditorSettings } from '@/tools/video-editor/settings/videoEditorDefaults';
import { videoEditorPathWithTimeline } from '@/tools/video-editor/lib/video-editor-path';
import { getClipTimelineDuration } from '@/tools/video-editor/lib/config-utils';
import {
  useTimelineEditorDataSafe,
  useTimelineEditorOpsSafe,
} from '@/tools/video-editor/hooks/timelineStore';
import {
  ADD_GENERATION_QUERY_PARAM,
  readPendingAdds,
  writePendingAdds,
  PENDING_ADDS_STORAGE_KEY,
} from './addToVideoEditorConstants';

export { ADD_GENERATION_QUERY_PARAM };

export type AddToVideoEditorPhase = 'idle' | 'staged';

interface UseAddToVideoEditorResult {
  onClick: () => void;
  phase: AddToVideoEditorPhase;
}

/**
 * Handler for adding the given media to the video editor timeline.
 *
 * Three branches:
 * 1. Editor is mounted (Timeline context available) → drop on the timeline immediately.
 * 2. Editor not mounted, first click → stage the generationId in localStorage and
 *    enter 'staged' phase (button shows a success state). No navigation.
 * 3. Editor not mounted, second click (already staged) → navigate to the editor;
 *    VideoEditorProvider drains the staged queue on mount.
 */
export function useAddToVideoEditor(media: GenerationRow | undefined): UseAddToVideoEditorResult {
  const ops = useTimelineEditorOpsSafe();
  const data = useTimelineEditorDataSafe();
  const navigate = useNavigate();
  const { settings: videoSettings } = useToolSettings(videoEditorSettings.id);

  const generationId = media ? (getGenerationId(media) ?? media.id) : null;

  const [phase, setPhase] = useState<AddToVideoEditorPhase>(() => {
    if (!generationId) return 'idle';
    return readPendingAdds().includes(generationId) ? 'staged' : 'idle';
  });

  useEffect(() => {
    if (!generationId) {
      setPhase('idle');
      return;
    }
    setPhase(readPendingAdds().includes(generationId) ? 'staged' : 'idle');
  }, [generationId]);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key !== PENDING_ADDS_STORAGE_KEY) return;
      if (!generationId) return;
      setPhase(readPendingAdds().includes(generationId) ? 'staged' : 'idle');
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [generationId]);

  const onClick = useCallback(() => {
    if (!media) return;
    if (!generationId) return;

    if (ops && data) {
      const assetKey = ops.registerGenerationAsset({
        generationId,
        variantType: media.type === 'video' ? 'video' : 'image',
        imageUrl: media.location ?? media.imageUrl ?? '',
        thumbUrl: media.thumbUrl ?? media.imageUrl ?? media.location ?? '',
      });
      if (!assetKey) {
        toast.error('Could not register asset');
        return;
      }
      const clips = data.resolvedConfig?.clips ?? [];
      const timelineEnd = clips.reduce(
        (max, clip) => Math.max(max, clip.at + getClipTimelineDuration(clip)),
        0,
      );
      ops.handleAssetDrop(assetKey, undefined, timelineEnd, false, false);
      return;
    }

    if (phase === 'staged') {
      const basePath = videoEditorPathWithTimeline(videoSettings?.lastTimelineId);
      const separator = basePath.includes('?') ? '&' : '?';
      navigate(`${basePath}${separator}${ADD_GENERATION_QUERY_PARAM}=${encodeURIComponent(generationId)}`);
      return;
    }

    const current = readPendingAdds();
    if (!current.includes(generationId)) {
      writePendingAdds([...current, generationId]);
    }
    setPhase('staged');
  }, [media, generationId, ops, data, navigate, videoSettings?.lastTimelineId, phase]);

  return { onClick, phase };
}
