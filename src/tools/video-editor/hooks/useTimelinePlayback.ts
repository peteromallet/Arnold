import { useCallback, useRef, useState } from 'react';
import type { PreviewHandle } from '@/tools/video-editor/components/PreviewPanel/RemotionPreview.tsx';
import { useTimelineSync } from '@/tools/video-editor/hooks/useTimelineSync.ts';
import type { TimelineCanvasHandle } from '@/tools/video-editor/types/timeline-canvas.ts';

export interface UseTimelinePlaybackResult {
  currentTime: number;
  setCurrentTime: React.Dispatch<React.SetStateAction<number>>;
  timelineRef: React.RefObject<TimelineCanvasHandle>;
  previewRef: React.RefObject<PreviewHandle>;
  playerContainerRef: React.RefObject<HTMLDivElement>;
  timelineWrapperRef: React.RefObject<HTMLDivElement>;
  onPreviewTimeUpdate: (time: number) => void;
  onCursorDrag: (time: number) => void;
  onClickTimeArea: (time: number) => undefined;
  formatTime: (time: number) => string;
}

export function useTimelinePlayback(): UseTimelinePlaybackResult {
  const timelineRef = useRef<TimelineCanvasHandle>(null);
  const previewRef = useRef<PreviewHandle>(null);
  const playerContainerRef = useRef<HTMLDivElement>(null);
  const timelineWrapperRef = useRef<HTMLDivElement>(null);
  const isSyncingFromPreview = useRef(false);
  const isSyncingFromTimeline = useRef(false);

  const [currentTime, setCurrentTime] = useState(0);

  const { onPreviewTimeUpdate, onCursorDrag, onClickTimeArea } = useTimelineSync({
    timelineRef,
    previewRef,
    setCurrentTime,
    isSyncingFromPreview,
    isSyncingFromTimeline,
  });

  const formatTime = useCallback((time: number) => {
    const mins = Math.floor(time / 60);
    const secs = Math.floor(time % 60);
    const ms = Math.floor((time % 1) * 100);
    return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
  }, []);

  return {
    currentTime,
    setCurrentTime,
    timelineRef,
    previewRef,
    playerContainerRef,
    timelineWrapperRef,
    onPreviewTimeUpdate,
    onCursorDrag,
    onClickTimeArea,
    formatTime,
  };
}
