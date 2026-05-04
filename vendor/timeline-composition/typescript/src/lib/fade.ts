import {interpolate, useCurrentFrame} from 'remotion';
import type {TimelineClip} from '../types';
import {getClipDurationInFrames, secondsToFrames} from './duration';

const getEffectValue = (
  effects: TimelineClip['effects'],
  name: 'fade_in' | 'fade_out',
): number | null => {
  if (!effects) {
    return null;
  }

  if (!Array.isArray(effects)) {
    const effectsObj = effects as Record<string, unknown>;
    return typeof effectsObj[name] === 'number' ? (effectsObj[name] as number) : null;
  }

  for (const effect of effects as Array<Record<string, unknown>>) {
    if (typeof effect[name] === 'number') {
      return (effect[name] as number) ?? null;
    }
  }

  return null;
};

export const useFadeOpacity = (clip: TimelineClip, fps: number): number => {
  const frame = useCurrentFrame();
  const durationInFrames = getClipDurationInFrames(clip, fps);
  let opacity = 1;

  const fadeInSeconds = getEffectValue(clip.effects, 'fade_in');
  if (typeof fadeInSeconds === 'number' && Number.isFinite(fadeInSeconds) && fadeInSeconds > 0) {
    const fadeInFrames = secondsToFrames(fadeInSeconds, fps);
    opacity *= interpolate(frame, [0, fadeInFrames], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
  }

  const fadeOutSeconds = getEffectValue(clip.effects, 'fade_out');
  if (typeof fadeOutSeconds === 'number' && Number.isFinite(fadeOutSeconds) && fadeOutSeconds > 0) {
    const fadeOutFrames = secondsToFrames(fadeOutSeconds, fps);
    opacity *= interpolate(frame, [durationInFrames - fadeOutFrames, durationInFrames], [1, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
  }

  return opacity;
};
