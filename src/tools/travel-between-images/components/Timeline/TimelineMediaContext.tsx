/**
 * TimelineMediaContext — passes structure video + audio props from
 * ShotImagesEditor straight to TimelineContainer, skipping Timeline.
 */

import { createContext, useContext, type ReactNode } from 'react';
import type { PrimaryStructureVideo } from '@/shared/lib/tasks/travelBetweenImages';
import type {
  OnAudioChange,
  OnPrimaryStructureVideoInputChange,
  StructureVideoCollectionHandlers,
} from '@/tools/travel-between-images/types/mediaHandlers';

export interface TimelineMediaContextValue extends StructureVideoCollectionHandlers {
  primaryStructureVideo: PrimaryStructureVideo;
  onPrimaryStructureVideoInputChange?: OnPrimaryStructureVideoInputChange;
  audioUrl?: string | null;
  audioMetadata?: { duration: number; name?: string } | null;
  onAudioChange?: OnAudioChange;
  /** Model-specific FPS for frame↔seconds conversions on the timeline. */
  timelineFps: number;
}

type TimelineGuidanceMediaValue = Pick<
  TimelineMediaContextValue,
  | 'primaryStructureVideo'
  | 'onPrimaryStructureVideoInputChange'
  | 'structureVideos'
  | 'isStructureVideoLoading'
  | 'cachedHasStructureVideo'
  | 'onAddStructureVideo'
  | 'onUpdateStructureVideo'
  | 'onRemoveStructureVideo'
>;

type TimelineAudioMediaValue = Pick<
  TimelineMediaContextValue,
  'audioUrl' | 'audioMetadata' | 'onAudioChange'
>;

const TimelineGuidanceMediaContext = createContext<TimelineGuidanceMediaValue | null>(null);
const TimelineAudioMediaContext = createContext<TimelineAudioMediaValue | null>(null);
const TimelineFpsContext = createContext<number | null>(null);

export function TimelineMediaProvider({
  value,
  children,
}: {
  value: TimelineMediaContextValue;
  children: ReactNode;
}) {
  const guidanceValue: TimelineGuidanceMediaValue = {
    primaryStructureVideo: value.primaryStructureVideo,
    onPrimaryStructureVideoInputChange: value.onPrimaryStructureVideoInputChange,
    structureVideos: value.structureVideos,
    isStructureVideoLoading: value.isStructureVideoLoading,
    cachedHasStructureVideo: value.cachedHasStructureVideo,
    onAddStructureVideo: value.onAddStructureVideo,
    onUpdateStructureVideo: value.onUpdateStructureVideo,
    onRemoveStructureVideo: value.onRemoveStructureVideo,
  };
  const audioValue: TimelineAudioMediaValue = {
    audioUrl: value.audioUrl,
    audioMetadata: value.audioMetadata,
    onAudioChange: value.onAudioChange,
  };

  return (
    <TimelineFpsContext.Provider value={value.timelineFps}>
      <TimelineGuidanceMediaContext.Provider value={guidanceValue}>
        <TimelineAudioMediaContext.Provider value={audioValue}>
          {children}
        </TimelineAudioMediaContext.Provider>
      </TimelineGuidanceMediaContext.Provider>
    </TimelineFpsContext.Provider>
  );
}

function requireTimelineContextValue<T>(value: T | null, hookName: string): T {
  if (!value) {
    throw new Error(`${hookName} must be used within a TimelineMediaProvider`);
  }
  return value;
}

export function useTimelineGuidanceMedia(): TimelineGuidanceMediaValue {
  return requireTimelineContextValue(
    useContext(TimelineGuidanceMediaContext),
    'useTimelineGuidanceMedia',
  );
}

export function useTimelineAudioMedia(): TimelineAudioMediaValue {
  return requireTimelineContextValue(
    useContext(TimelineAudioMediaContext),
    'useTimelineAudioMedia',
  );
}

export function useTimelineFps(): number {
  return requireTimelineContextValue(
    useContext(TimelineFpsContext),
    'useTimelineFps',
  );
}

/** @deprecated Migrate production code to the narrower timeline-media hooks. */
export function useTimelineMedia(): TimelineMediaContextValue {
  const guidance = useTimelineGuidanceMedia();
  const audio = useTimelineAudioMedia();
  const timelineFps = useTimelineFps();

  return {
    ...guidance,
    ...audio,
    timelineFps,
  };
}
