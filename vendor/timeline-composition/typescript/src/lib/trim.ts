import type {TimelineClip} from '../types';
import {secondsToFrames} from './duration';

export const computeMediaTrim = (
  clip: Partial<Pick<TimelineClip, 'from' | 'to'>>,
  fps: number,
): {trimBefore: number; trimAfter?: number} => {
  const trimBeforeSeconds = typeof clip.from === 'number' && Number.isFinite(clip.from)
    ? Math.max(0, clip.from)
    : 0;
  const trimAfterSeconds = typeof clip.to === 'number' && Number.isFinite(clip.to) && clip.to > trimBeforeSeconds
    ? clip.to
    : undefined;

  return {
    trimBefore: secondsToFrames(trimBeforeSeconds, fps),
    ...(trimAfterSeconds === undefined ? {} : {trimAfter: secondsToFrames(trimAfterSeconds, fps)}),
  };
};
