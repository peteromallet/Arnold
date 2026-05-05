import type { FC, ReactNode } from 'react';
import { Sequence, useCurrentFrame } from 'remotion';
import {
  continuousEffects,
  getEffectRegistry,
  lookupEffect,
  wrapWithEffect,
} from '@/tools/video-editor/effects/index.tsx';
import { getClipDurationInFrames, secondsToFrames } from '@/tools/video-editor/lib/config-utils.ts';
import type { ResolvedTimelineClip } from '@/tools/video-editor/types/index.ts';

interface EffectLayerSequenceProps {
  clip: ResolvedTimelineClip;
  fps: number;
  children: ReactNode;
}

/**
 * Applies a continuous effect for the effect-layer clip's time range
 * while always passing children through. Outside the effect's range,
 * children render unmodified; inside the range, the effect is applied
 * with a local frame context so effect animations start from 0.
 */
export const EffectLayerSequence: FC<EffectLayerSequenceProps> = ({ clip, fps, children }) => {
  const frame = useCurrentFrame();
  const startFrame = Math.max(0, secondsToFrames(clip.at, fps));
  const durationInFrames = getClipDurationInFrames(clip, fps);

  if (!clip.continuous) {
    return <>{children}</>;
  }

  const Effect = lookupEffect(continuousEffects, clip.continuous.type);
  if (!Effect) {
    console.warn('[EffectLayer] effect NOT FOUND for clip=%s type=%s', clip.id, clip.continuous.type);
    return <>{children}</>;
  }

  // Outside the effect's time range, pass children through unchanged.
  if (frame < startFrame || frame >= startFrame + durationInFrames) {
    return <>{children}</>;
  }

  // Inside the range: wrap in a Sequence to give the effect a local frame
  // context (frame 0 = effect start), and nest children in an offsetting
  // Sequence so they still see the original composition time.
  const inner = startFrame === 0 ? children : <Sequence from={-startFrame}>{children}</Sequence>;

  return (
    <Sequence from={startFrame} durationInFrames={durationInFrames}>
      {wrapWithEffect(
        inner,
        Effect,
        {
          effectName: clip.continuous.type,
          durationInFrames,
          effectFrames: durationInFrames,
          intensity: clip.continuous.intensity ?? 0.5,
          params: clip.continuous.params,
          schema: getEffectRegistry().getSchema(clip.continuous.type),
        },
      )}
    </Sequence>
  );
};
