import type { FC } from 'react';
import * as compileSequenceModule from '@/tools/video-editor/sequences/compileSequenceComponent.tsx';
import type { SequenceComponentProps } from '@/tools/video-editor/sequences/compileSequenceComponent.tsx';
import { DynamicComponentRegistry } from '@/tools/video-editor/runtime-components/DynamicComponentRegistry.ts';

/**
 * DB-stored sequences are stored in the registry under their plain clipType
 * (e.g. `my-pulse`); referenced from timeline JSON as `custom:my-pulse`. The
 * default `normalizeName` strips the `custom:` prefix on lookup — mirrors
 * effects/DynamicEffectRegistry.ts:117-119 exactly.
 */
export class DynamicSequenceRegistry extends DynamicComponentRegistry<SequenceComponentProps, object> {
  constructor(builtIn: Record<string, FC<SequenceComponentProps>> = {}) {
    super({
      builtIn,
      // Resolve via module namespace so vi.spyOn(...) in tests can intercept
      // these calls without rebuilding the registry.
      compile: (code) => compileSequenceModule.compileSequenceComponent(code),
      compileAsync: (code) => compileSequenceModule.compileSequenceComponentAsync(code),
    });
  }
}
