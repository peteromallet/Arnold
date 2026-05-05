import React, { type FC } from 'react';
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import type { EffectComponentProps } from '@/tools/video-editor/effects/entrances';
import { useAudioParam, useAudioReactive } from '@/tools/video-editor/effects/useAudioReactive';
import {
  compileWithGlobalsAsync,
  compileWithGlobalsSync,
  preloadSucrase,
  type CompileResult as CompileResultGeneric,
} from '@/tools/video-editor/runtime-components/compileWithGlobals';

export type CompileResult = CompileResultGeneric<EffectComponentProps>;
export { preloadSucrase };

// Build globals lazily so module load does not eagerly read every named
// `remotion` import. Some test environments mock `remotion` with a partial
// export set, and accessing a missing export at module-evaluation time
// would throw before the consumer's `vi.mock` even gets a chance to run.
function getEffectGlobals(): Record<string, unknown> {
  return {
    React,
    useCurrentFrame,
    useVideoConfig,
    interpolate,
    spring,
    AbsoluteFill,
    useAudioReactive,
    useAudioParam,
  };
}

function createFailedEffect(message: string): FC<EffectComponentProps> {
  return function FailedEffect({ children }: EffectComponentProps) {
    void message;
    return <>{children}</>;
  };
}

export function compileEffect(code: string): FC<EffectComponentProps> {
  const result = compileWithGlobalsSync<EffectComponentProps>(code, getEffectGlobals());
  return result.ok ? result.component : createFailedEffect(result.error);
}

export async function tryCompileEffectAsync(code: string): Promise<CompileResult> {
  return compileWithGlobalsAsync<EffectComponentProps>(code, getEffectGlobals());
}

export async function compileEffectAsync(code: string): Promise<FC<EffectComponentProps>> {
  const result = await tryCompileEffectAsync(code);
  return result.ok ? result.component : createFailedEffect(result.error);
}
