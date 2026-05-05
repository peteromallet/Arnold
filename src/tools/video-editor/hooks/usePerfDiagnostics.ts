import { useCallback } from 'react';
import {
  EffectLoopDetector,
  RenderStormDetector,
} from '@/tools/video-editor/lib/perf-diagnostics.ts';

export function useRenderDiagnostic(componentName: string) {
  RenderStormDetector.track(componentName);
}

export function useEffectDiagnostic(effectId: string) {
  return useCallback(() => {
    EffectLoopDetector.track(effectId);
  }, [effectId]);
}
