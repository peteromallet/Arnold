import type { CSSProperties } from 'react';
import { interpolate } from 'remotion';

export type TransitionRenderer = (progress: number) => CSSProperties;

export const transitions: Record<string, TransitionRenderer> = {
  crossfade: (progress) => ({
    opacity: interpolate(progress, [0, 1], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    }),
  }),
  wipe: (progress) => ({
    clipPath: `inset(0 ${Math.max(0, (1 - progress) * 100)}% 0 0)`,
  }),
  'slide-push': (progress) => ({
    transform: `translateX(${interpolate(progress, [0, 1], [100, 0])}%)`,
  }),
  'zoom-through': (progress) => ({
    opacity: interpolate(progress, [0, 1], [0, 1]),
    transform: `scale(${interpolate(progress, [0, 1], [1.12, 1])})`,
  }),
};

/** Array of built-in transition type IDs — preserved for unmigrated callers. */
export const transitionTypes = Object.keys(transitions);
