import type { FC, ReactNode } from 'react';
import { secondsToFrames } from '@/tools/video-editor/lib/config-utils.ts';
import { DynamicEffectRegistry } from '@/tools/video-editor/effects/DynamicEffectRegistry.ts';
import { EffectErrorBoundary } from '@/tools/video-editor/effects/EffectErrorBoundary.tsx';
import { validateAndCoerceParams } from '@/tools/video-editor/effects/validateParams.ts';
import {
  BounceEntrance,
  FadeEntrance,
  FlipEntrance,
  MeteoriteEntrance,
  PulseEntrance,
  SlideDownEntrance,
  SlideLeftEntrance,
  SlideRightEntrance,
  SlideUpEntrance,
  ZoomInEntrance,
  ZoomSpinEntrance,
  type EffectComponentProps,
} from '@/tools/video-editor/effects/entrances.tsx';
import {
  DriftEffect,
  FloatEffect,
  GlitchEffect,
  KenBurnsEffect,
  SlowZoomEffect,
} from '@/tools/video-editor/effects/continuous.tsx';
import {
  DissolveExit,
  FadeOutExit,
  FlipExit,
  ShrinkExit,
  SlideDownExit,
  ZoomOutExit,
} from '@/tools/video-editor/effects/exits.tsx';
import type { ParameterSchema, ResolvedTimelineClip } from '@/tools/video-editor/types/index.ts';

export type ClipEffectComponent = FC<EffectComponentProps>;

export const entranceEffects: Record<string, ClipEffectComponent> = {
  'slide-up': SlideUpEntrance,
  'slide-down': SlideDownEntrance,
  'slide-left': SlideLeftEntrance,
  'slide-right': SlideRightEntrance,
  'zoom-in': ZoomInEntrance,
  'zoom-spin': ZoomSpinEntrance,
  pulse: PulseEntrance,
  fade: FadeEntrance,
  flip: FlipEntrance,
  bounce: BounceEntrance,
  meteorite: MeteoriteEntrance,
};

export const exitEffects: Record<string, ClipEffectComponent> = {
  'slide-down': SlideDownExit,
  'zoom-out': ZoomOutExit,
  flip: FlipExit,
  'fade-out': FadeOutExit,
  shrink: ShrinkExit,
  dissolve: DissolveExit,
};

export const continuousEffects: Record<string, ClipEffectComponent> = {
  'ken-burns': KenBurnsEffect,
  float: FloatEffect,
  glitch: GlitchEffect,
  'slow-zoom': SlowZoomEffect,
  drift: DriftEffect,
};

export const entranceEffectTypes = Object.keys(entranceEffects);
export const exitEffectTypes = Object.keys(exitEffects);
export const continuousEffectTypes = Object.keys(continuousEffects);

const allBuiltInEffects: Record<string, ClipEffectComponent> = {
  ...entranceEffects,
  ...exitEffects,
  ...continuousEffects,
};

let effectRegistry: DynamicEffectRegistry | null = null;

export function getEffectRegistry(): DynamicEffectRegistry {
  if (!effectRegistry) {
    effectRegistry = new DynamicEffectRegistry(allBuiltInEffects);
  }

  return effectRegistry;
}

export function replaceEffectRegistry(registry: DynamicEffectRegistry): DynamicEffectRegistry {
  effectRegistry = registry;
  return effectRegistry;
}

const resolveEffectName = (type: string): string => {
  return type.startsWith('custom:') ? type.slice(7) : type;
};

export const lookupEffect = (
  builtInMap: Record<string, ClipEffectComponent>,
  type: string,
): ClipEffectComponent | null => {
  const name = resolveEffectName(type);
  if (builtInMap[name]) {
    return builtInMap[name];
  }

  const registry = getEffectRegistry();
  return registry.get(name) ?? null;
};

type WrapWithEffectConfig = {
  effectName: string;
  durationInFrames: number;
  effectFrames?: number;
  intensity?: number;
  params?: Record<string, unknown>;
  schema?: ParameterSchema;
};

export const wrapWithEffect = (
  content: ReactNode,
  EffectComponent: ClipEffectComponent,
  { effectName, durationInFrames, effectFrames, intensity, params, schema }: WrapWithEffectConfig,
): ReactNode => {
  return (
    <EffectErrorBoundary effectName={effectName} fallback={content}>
      <EffectComponent
        durationInFrames={durationInFrames}
        effectFrames={effectFrames}
        intensity={intensity}
        params={validateAndCoerceParams(params, schema)}
      >
        {content}
      </EffectComponent>
    </EffectErrorBoundary>
  );
};

export const wrapWithClipEffects = (
  content: ReactNode,
  clip: ResolvedTimelineClip,
  durationInFrames: number,
  fps: number,
): ReactNode => {
  let wrapped = content;
  const registry = getEffectRegistry();

  const continuousEffect = clip.continuous;
  const continuous = continuousEffect ? lookupEffect(continuousEffects, continuousEffect.type) : null;
  if (continuousEffect && !continuous) {
    console.warn('[EffectWrap] continuous effect NOT FOUND for clip=%s type=%s', clip.id, continuousEffect.type);
  }
  if (continuous) {
    wrapped = wrapWithEffect(wrapped, continuous, {
      effectName: continuousEffect!.type,
      durationInFrames,
      effectFrames: durationInFrames,
      intensity: continuousEffect!.intensity ?? 0.5,
      params: continuousEffect!.params,
      schema: registry.getSchema(continuousEffect!.type),
    });
  }

  const entranceEffect = clip.entrance;
  const entrance = entranceEffect ? lookupEffect(entranceEffects, entranceEffect.type) : null;
  if (entrance) {
    wrapped = wrapWithEffect(wrapped, entrance, {
      effectName: entranceEffect!.type,
      durationInFrames,
      effectFrames: secondsToFrames(entranceEffect!.duration ?? 0.4, fps),
      intensity: entranceEffect!.intensity,
      params: entranceEffect!.params,
      schema: registry.getSchema(entranceEffect!.type),
    });
  }

  const exitEffect = clip.exit;
  const exit = exitEffect ? lookupEffect(exitEffects, exitEffect.type) : null;
  if (exit) {
    wrapped = wrapWithEffect(wrapped, exit, {
      effectName: exitEffect!.type,
      durationInFrames,
      effectFrames: secondsToFrames(exitEffect!.duration ?? 0.4, fps),
      intensity: exitEffect!.intensity,
      params: exitEffect!.params,
      schema: registry.getSchema(exitEffect!.type),
    });
  }

  return wrapped;
};
