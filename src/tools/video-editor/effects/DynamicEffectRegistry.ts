import type { FC } from 'react';
import type { EffectComponentProps } from '@/tools/video-editor/effects/entrances';
import * as compileEffectModule from '@/tools/video-editor/effects/compileEffect';
import { DynamicComponentRegistry } from '@/tools/video-editor/runtime-components/DynamicComponentRegistry';
import type { ParameterSchema } from '@/tools/video-editor/types';

export class DynamicEffectRegistry extends DynamicComponentRegistry<EffectComponentProps, ParameterSchema> {
  constructor(builtIn: Record<string, FC<EffectComponentProps>>) {
    super({
      builtIn,
      // Resolve via the module namespace so vi.spyOn(compileEffectModule, ...)
      // in tests can intercept these calls without rebuilding the registry.
      compile: (code) => compileEffectModule.compileEffect(code),
      compileAsync: (code) => compileEffectModule.compileEffectAsync(code),
    });
  }
}
