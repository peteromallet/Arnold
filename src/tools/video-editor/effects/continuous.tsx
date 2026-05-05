import type { FC } from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import type { EffectComponentProps } from '@/tools/video-editor/effects/entrances.tsx';

export const KenBurnsEffect: FC<EffectComponentProps> = ({ children, durationInFrames, intensity = 0.5 }) => {
  const frame = useCurrentFrame();
  const progress = durationInFrames <= 1 ? 1 : frame / durationInFrames;
  const scale = interpolate(progress, [0, 1], [1, 1 + intensity * 0.18]);
  const translateX = interpolate(progress, [0, 1], [0, -20 * intensity]);
  const translateY = interpolate(progress, [0, 1], [0, -10 * intensity]);
  return <AbsoluteFill style={{ width: '100%', height: '100%', transform: `scale(${scale}) translate(${translateX}px, ${translateY}px)` }}>{children}</AbsoluteFill>;
};

export const FloatEffect: FC<EffectComponentProps> = ({ children, intensity = 0.5 }) => {
  const frame = useCurrentFrame();
  const translateY = Math.sin(frame * 0.06) * 8 * intensity;
  const scale = 1 + Math.sin(frame * 0.04) * 0.02 * intensity;
  return <AbsoluteFill style={{ width: '100%', height: '100%', transform: `translateY(${translateY}px) scale(${scale})` }}>{children}</AbsoluteFill>;
};

export const GlitchEffect: FC<EffectComponentProps> = ({ children, intensity = 0.5 }) => {
  const frame = useCurrentFrame();
  const glitchCycle = frame % 36;
  const isGlitching = glitchCycle < 3;
  const offsetX = isGlitching ? Math.sin(frame * 17) * 10 * intensity : 0;
  const offsetY = isGlitching ? Math.cos(frame * 11) * 4 * intensity : 0;
  const skew = isGlitching ? Math.sin(frame * 19) * 4 * intensity : 0;
  return <AbsoluteFill style={{ width: '100%', height: '100%', transform: `translate(${offsetX}px, ${offsetY}px) skewX(${skew}deg)` }}>{children}</AbsoluteFill>;
};

export const SlowZoomEffect: FC<EffectComponentProps> = ({ children, durationInFrames, intensity = 0.5 }) => {
  const frame = useCurrentFrame();
  const progress = durationInFrames <= 1 ? 1 : frame / durationInFrames;
  const scale = interpolate(progress, [0, 1], [1, 1 + intensity * 0.1]);
  return <AbsoluteFill style={{ width: '100%', height: '100%', transform: `scale(${scale})` }}>{children}</AbsoluteFill>;
};

export const DriftEffect: FC<EffectComponentProps> = ({ children, durationInFrames, intensity = 0.5 }) => {
  const frame = useCurrentFrame();
  const progress = durationInFrames <= 1 ? 1 : frame / durationInFrames;
  const driftX = interpolate(progress, [0, 1], [0, 40 * intensity]);
  const driftY = Math.sin(frame * 0.025) * 10 * intensity;
  return <AbsoluteFill style={{ width: '100%', height: '100%', transform: `translate(${driftX}px, ${driftY}px)` }}>{children}</AbsoluteFill>;
};
