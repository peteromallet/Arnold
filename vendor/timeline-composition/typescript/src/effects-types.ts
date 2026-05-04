// Sprint 5: physically moved here from tools/remotion/src/effects.types.ts.
// The theme-api re-export now points at this in-package module.

import type {CSSProperties, FC, ReactNode} from 'react';
import type {RuntimeTheme} from './ThemeContext';
import type {TimelineClip} from './types';

export type EffectProps<TParams = unknown> = {
  clip: TimelineClip;
  params: TParams;
  theme: RuntimeTheme;
  fps: number;
};

export type EffectComponent = FC<EffectProps>;

export type AnimationPhase = 'entrance' | 'sustain' | 'exit';
export type AnimationKind = 'wrapper' | 'hook';
export type AnimationEasing = 'linear' | 'ease-in' | 'ease-out' | 'ease-in-out' | string;

export type AnimationReferenceObject<TParams = Record<string, unknown>> = {
  id: string;
  durationFrames?: number;
  easing?: AnimationEasing;
  params?: TParams;
};

export type AnimationReference<TParams = Record<string, unknown>> =
  | string
  | AnimationReferenceObject<TParams>;

export type AnimationReferenceList<TParams = Record<string, unknown>> =
  | AnimationReference<TParams>
  | AnimationReference<TParams>[];

export type AnimationSlots<TParams = Record<string, unknown>> = {
  entrance?: AnimationReferenceList<TParams>;
  sustain?: AnimationReferenceList<TParams>;
  exit?: AnimationReferenceList<TParams>;
};

export type AnimationMeta = {
  id?: string;
  kind: AnimationKind;
  phase?: AnimationPhase | AnimationPhase[] | 'any';
  defaultDurationFrames?: number;
  [key: string]: unknown;
};

export type BaseAnimationProps<TParams = Record<string, unknown>> = {
  clip: TimelineClip;
  params: TParams;
  theme: RuntimeTheme;
  fps: number;
  phase: AnimationPhase;
  durationFrames: number;
  elapsedFrames: number;
  animationId: string;
};

export type WrapperAnimationProps<TParams = Record<string, unknown>> = BaseAnimationProps<TParams> & {
  children: ReactNode;
  style?: CSSProperties;
};

export type HookAnimationResult = {
  content?: ReactNode;
  text?: string;
  params?: Record<string, unknown>;
  style?: CSSProperties;
};

export type HookAnimationProps<TParams = Record<string, unknown>> = BaseAnimationProps<TParams> & {
  content: ReactNode;
  text?: string;
};

export type WrapperAnimationComponent<TParams = Record<string, unknown>> = FC<WrapperAnimationProps<TParams>>;
export type HookAnimationComponent<TParams = Record<string, unknown>> = (
  props: HookAnimationProps<TParams>,
) => HookAnimationResult | ReactNode;
export type AnimationComponent<TParams = Record<string, unknown>> =
  | WrapperAnimationComponent<TParams>
  | HookAnimationComponent<TParams>;

export type TransitionReferenceObject<TParams = Record<string, unknown>> = {
  id?: string;
  type?: string;
  duration?: number;
  durationFrames?: number;
  params?: TParams;
};

export type TransitionReference<TParams = Record<string, unknown>> =
  | string
  | TransitionReferenceObject<TParams>;

export type TransitionProps<TParams = Record<string, unknown>> = {
  transitionId: string;
  params: TParams;
  theme: RuntimeTheme;
  fps: number;
  durationFrames: number;
};

export type TransitionComponentResult = {
  presentation: unknown;
  timing: unknown;
};

export type TransitionComponent<TParams = Record<string, unknown>> = (
  props: TransitionProps<TParams>,
) => TransitionComponentResult;
