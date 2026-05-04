// Sprint 5: physically moved here from tools/remotion/src/lib/animations.tsx.
// The theme-api re-export now points at this in-package module.

import type {ReactNode} from 'react';
import {
  ANIMATION_DEFAULTS,
  ANIMATION_META,
  ANIMATION_REGISTRY,
} from '../animations.generated';
import type {
  AnimationComponent,
  AnimationPhase,
  AnimationReference,
  AnimationReferenceList,
  AnimationMeta,
  HookAnimationComponent,
  HookAnimationResult,
  WrapperAnimationComponent,
} from '../effects-types';
import type {RuntimeTheme} from '../ThemeContext';
import type {TimelineClip} from '../types';

export type NormalizedAnimationReference = {
  id: string;
  durationFrames?: number;
  easing?: string;
  params: Record<string, unknown>;
};

export type ResolvedAnimation = NormalizedAnimationReference & {
  component: AnimationComponent;
  kind: 'wrapper' | 'hook';
  phase: AnimationPhase;
  durationFrames: number;
};

export type ComposeAnimationsInput = {
  clip: TimelineClip;
  refs: AnimationReferenceList | undefined;
  phase: AnimationPhase;
  content: ReactNode;
  text?: string;
  theme: RuntimeTheme;
  fps: number;
  elapsedFrames: number;
};

const isObjectReference = (value: unknown): value is Exclude<AnimationReference, string> => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const animationRegistry = ANIMATION_REGISTRY as Record<string, AnimationComponent | undefined>;
const animationDefaults = ANIMATION_DEFAULTS as Record<string, Record<string, unknown> | undefined>;
const animationMeta = ANIMATION_META as Record<string, AnimationMeta | undefined>;

const hasAnimationId = (id: string): boolean => Object.prototype.hasOwnProperty.call(animationRegistry, id);

export const normalizeAnimationReferences = (
  refs: AnimationReferenceList | undefined,
): NormalizedAnimationReference[] => {
  if (refs === undefined) {
    return [];
  }
  const refList = Array.isArray(refs) ? refs : [refs];
  return refList.map((ref) => {
    if (typeof ref === 'string') {
      if (!hasAnimationId(ref)) {
        throw new Error(`Unknown animation id '${ref}'`);
      }
      return {id: ref, params: {}};
    }
    if (!isObjectReference(ref) || typeof ref.id !== 'string' || ref.id.length === 0) {
      throw new Error('Animation reference objects must include a non-empty string id');
    }
    if (!hasAnimationId(ref.id)) {
      throw new Error(`Unknown animation id '${ref.id}'`);
    }
    return {
      id: ref.id,
      durationFrames: ref.durationFrames,
      easing: typeof ref.easing === 'string' ? ref.easing : undefined,
      params: ref.params && typeof ref.params === 'object' ? {...ref.params} : {},
    };
  });
};

export const resolveAnimationReferences = (
  refs: AnimationReferenceList | undefined,
  phase: AnimationPhase,
): ResolvedAnimation[] => {
  return normalizeAnimationReferences(refs).map((ref) => {
    const meta = animationMeta[ref.id];
    if (!meta) {
      throw new Error(`Unknown animation id '${ref.id}'`);
    }
    const metaPhase = meta.phase ?? 'any';
    const phaseMatches = metaPhase === 'any'
      || metaPhase === phase
      || (Array.isArray(metaPhase) && metaPhase.includes(phase));
    if (!phaseMatches) {
      throw new Error(`Animation '${ref.id}' is phase '${meta.phase}', not '${phase}'`);
    }

    const defaults = animationDefaults[ref.id] ?? {};
    const defaultDuration = typeof defaults.durationFrames === 'number'
      ? defaults.durationFrames
      : meta.defaultDurationFrames;
    const durationFrames = ref.durationFrames ?? defaultDuration;
    if (typeof durationFrames !== 'number' || !Number.isFinite(durationFrames) || durationFrames < 0) {
      throw new Error(`Animation '${ref.id}' must resolve to a non-negative durationFrames value`);
    }

    return {
      ...ref,
      params: {...defaults, ...ref.params},
      component: animationRegistry[ref.id] as AnimationComponent,
      kind: meta.kind,
      phase,
      durationFrames,
    };
  });
};

const isHookResultObject = (value: unknown): value is HookAnimationResult => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};

export const composeAnimations = ({
  clip,
  refs,
  phase,
  content,
  text,
  theme,
  fps,
  elapsedFrames,
}: ComposeAnimationsInput): ReactNode => {
  const resolved = resolveAnimationReferences(refs, phase);
  const hookAnimations = resolved.filter((animation) => animation.kind === 'hook');
  const wrapperAnimations = resolved.filter((animation) => animation.kind === 'wrapper');

  let nextContent = content;
  let nextText = text;
  let nextParams: Record<string, unknown> = {};

  for (const animation of hookAnimations) {
    const HookComponent = animation.component as HookAnimationComponent<Record<string, unknown>>;
    const result = HookComponent({
      clip,
      params: animation.params,
      theme,
      fps,
      phase,
      durationFrames: animation.durationFrames,
      elapsedFrames,
      animationId: animation.id,
      content: nextContent,
      text: nextText,
    });
    if (isHookResultObject(result)) {
      nextContent = result.content ?? nextContent;
      nextText = result.text ?? nextText;
      nextParams = {...nextParams, ...(result.params ?? {})};
    } else {
      nextContent = result;
    }
  }

  return wrapperAnimations.reduceRight((children, animation) => {
    const WrapperComponent = animation.component as WrapperAnimationComponent<Record<string, unknown>>;
    return (
      <WrapperComponent
        clip={clip}
        params={{...animation.params, ...nextParams}}
        theme={theme}
        fps={fps}
        phase={phase}
        durationFrames={animation.durationFrames}
        elapsedFrames={elapsedFrames}
        animationId={animation.id}
      >
        {children}
      </WrapperComponent>
    );
  }, nextContent);
};
