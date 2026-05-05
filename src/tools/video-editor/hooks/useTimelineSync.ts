import { useCallback, useRef } from 'react';
import type { PreviewHandle } from '@/tools/video-editor/components/PreviewPanel/RemotionPreview.tsx';
import type { TimelineCanvasHandle } from '@/tools/video-editor/types/timeline-canvas.ts';

interface UseTimelineSyncOptions {
  timelineRef: React.RefObject<TimelineCanvasHandle>;
  previewRef: React.RefObject<PreviewHandle>;
  setCurrentTime: React.Dispatch<React.SetStateAction<number>>;
  isSyncingFromPreview: React.MutableRefObject<boolean>;
  isSyncingFromTimeline: React.MutableRefObject<boolean>;
}

export function useTimelineSync({
  timelineRef,
  previewRef,
  setCurrentTime,
  isSyncingFromPreview,
  isSyncingFromTimeline,
}: UseTimelineSyncOptions) {
  const lastTimeUpdateRef = useRef(0);

  const onPreviewTimeUpdate = useCallback((time: number) => {
    if (isSyncingFromTimeline.current) {
      return;
    }

    timelineRef.current?.setTime(time);

    const now = performance.now();
    if (now - lastTimeUpdateRef.current > 250) {
      lastTimeUpdateRef.current = now;
      isSyncingFromPreview.current = true;
      setCurrentTime(time);
      requestAnimationFrame(() => {
        isSyncingFromPreview.current = false;
      });
    }
  }, [isSyncingFromPreview, isSyncingFromTimeline, setCurrentTime, timelineRef]);

  const onCursorDrag = useCallback((time: number) => {
    if (isSyncingFromPreview.current) {
      return;
    }

    isSyncingFromTimeline.current = true;
    previewRef.current?.seek(time);
    setCurrentTime(time);
    requestAnimationFrame(() => {
      isSyncingFromTimeline.current = false;
    });
  }, [isSyncingFromPreview, isSyncingFromTimeline, previewRef, setCurrentTime]);

  const onClickTimeArea = useCallback((time: number) => {
    previewRef.current?.seek(time);
    setCurrentTime(time);
    return undefined;
  }, [previewRef, setCurrentTime]);

  return { onPreviewTimeUpdate, onCursorDrag, onClickTimeArea };
}
