export const TIMELINE_CENTER_CLIP_EVENT = 'reigh:timeline-center-clip';

export type TimelineCenterClipEventDetail = {
  clipId: string;
};

export const requestCenterTimelineClip = (clipId: string): void => {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent<TimelineCenterClipEventDetail>(TIMELINE_CENTER_CLIP_EVENT, {
    detail: { clipId },
  }));
};
