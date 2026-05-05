import React, { type FC } from 'react';
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  interpolate,
  Sequence,
  Series,
  spring,
  useCurrentFrame,
  useVideoConfig,
  Video,
} from 'remotion';
import { composeAnimations, useTheme, type RuntimeTheme } from '@banodoco/timeline-composition/theme-api';
import {
  compileWithGlobalsAsync,
  compileWithGlobalsSync,
  type CompileResult,
} from '@/tools/video-editor/runtime-components/compileWithGlobals.ts';
import type { ResolvedTimelineClip } from '@/tools/video-editor/types/index.ts';

export interface SequenceComponentProps {
  clip: ResolvedTimelineClip;
  params?: Record<string, unknown>;
  theme?: RuntimeTheme;
  fps: number;
}

// Globals are built lazily so module load does not eagerly read every named
// `remotion` / `theme-api` import. Some test environments mock those modules
// with a partial export set, and accessing a missing export at module-evaluation
// time would throw before the consumer's `vi.mock` runs (the same pattern used
// in effects/compileEffect.tsx after T1).
function getSequenceGlobals(): Record<string, unknown> {
  return {
    React,
    useCurrentFrame,
    useVideoConfig,
    interpolate,
    spring,
    AbsoluteFill,
    Sequence,
    Series,
    Img,
    Video,
    Audio,
    Easing,
    useTheme,
    composeAnimations,
  };
}

const COMPILE_OPTIONS = {
  transforms: ['jsx', 'typescript'] as Array<'jsx' | 'typescript'>,
  jsxRuntime: 'classic' as const,
};

function createFailedSequence(message: string): FC<SequenceComponentProps> {
  return function FailedSequence() {
    void message;
    return null;
  };
}

export function compileSequenceComponent(code: string): FC<SequenceComponentProps> {
  const result = compileWithGlobalsSync<SequenceComponentProps>(code, getSequenceGlobals(), COMPILE_OPTIONS);
  return result.ok ? result.component : createFailedSequence(result.error);
}

export async function tryCompileSequenceComponentAsync(
  code: string,
): Promise<CompileResult<SequenceComponentProps>> {
  return compileWithGlobalsAsync<SequenceComponentProps>(code, getSequenceGlobals(), COMPILE_OPTIONS);
}

export async function compileSequenceComponentAsync(
  code: string,
): Promise<FC<SequenceComponentProps>> {
  const result = await tryCompileSequenceComponentAsync(code);
  return result.ok ? result.component : createFailedSequence(result.error);
}
