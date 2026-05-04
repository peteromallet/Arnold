import type {ReactElement, ReactNode} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {
  TRANSITION_DEFAULTS,
  TRANSITION_REGISTRY,
} from '../transitions.generated';
import type {
  TransitionComponent,
  TransitionReference,
  TransitionReferenceObject,
} from '../effects-types';
import type {RuntimeTheme} from '../ThemeContext';

export type ResolvedTransition = {
  id: string;
  durationFrames: number;
  params: Record<string, unknown>;
};

const transitionRegistry = TRANSITION_REGISTRY as Record<string, TransitionComponent | undefined>;
const transitionDefaults = TRANSITION_DEFAULTS as Record<string, Record<string, unknown> | undefined>;

const isObjectReference = (value: unknown): value is TransitionReferenceObject => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};

export const resolveTransitionReference = (
  ref: TransitionReference | undefined,
  theme: RuntimeTheme,
  fps: number,
): ResolvedTransition | null => {
  if (ref === undefined) {
    return null;
  }
  const id = typeof ref === 'string' ? ref : isObjectReference(ref) ? (ref.id ?? ref.type ?? '') : '';
  if (!id || !transitionRegistry[id]) {
    throw new Error(`Unknown transition id '${id}'`);
  }
  const defaults = transitionDefaults[id] ?? {};
  const params = typeof ref === 'string'
    ? {...defaults}
    : {...defaults, ...(ref.params ?? {})};
  const rawDurationFrames = typeof ref === 'string' ? undefined : ref.durationFrames;
  const durationSeconds = typeof ref === 'string' ? undefined : (ref as {duration?: number}).duration;
  const durationFrames = rawDurationFrames
    ?? (typeof durationSeconds === 'number' ? Math.round(durationSeconds * fps) : undefined)
    ?? (typeof defaults.durationFrames === 'number' ? defaults.durationFrames : 12);
  const component = transitionRegistry[id] as TransitionComponent<Record<string, unknown>>;
  component({transitionId: id, params, theme, fps, durationFrames});
  return {id, durationFrames, params};
};

export const TransitionSeries = ({children}: {children: ReactNode}): ReactElement => {
  return <AbsoluteFill>{children}</AbsoluteFill>;
};

export const CrossFadeLayer = ({
  children,
  role,
  durationFrames,
  transitionDurationFrames,
}: {
  children: ReactNode;
  role: 'from' | 'to';
  durationFrames: number;
  transitionDurationFrames: number;
}): ReactElement => {
  const frame = useCurrentFrame();
  const progress = role === 'from'
    ? interpolate(
      frame,
      [Math.max(0, durationFrames - transitionDurationFrames), durationFrames],
      [0, 1],
      {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
    )
    : interpolate(frame, [0, transitionDurationFrames], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
  return (
    <AbsoluteFill style={{opacity: role === 'from' ? 1 - progress : progress}}>
      {children}
    </AbsoluteFill>
  );
};
