import type {ReactElement} from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import type {
  AnimationReference,
  AnimationReferenceList,
  EffectProps,
} from '../../tools/remotion/src/effects.types';
import {composeAnimations} from '../../tools/remotion/src/lib/animations';

export type TextCardParams = {
  content?: string;
  align?: 'left' | 'center' | 'right';
  bold?: boolean;
  italic?: boolean;
  fontSizeOverride?: number | null;
  colorOverride?: string | null;
  typewriter?: boolean;
  typewriterDurationFraction?: number;
  entrance?: AnimationReferenceList | 'none';
  exit?: AnimationReferenceList | 'none';
  sustain?: AnimationReferenceList;
};

const JUSTIFY_CONTENT = {
  left: 'flex-start',
  center: 'center',
  right: 'flex-end',
} as const;

const ENTRANCE_DURATION_FRAMES = 18;
const EXIT_DURATION_FRAMES = 12;

const withDuration = (ref: AnimationReference, durationFrames: number): AnimationReference => {
  return typeof ref === 'string' ? {id: ref, durationFrames} : {...ref, durationFrames: ref.durationFrames ?? durationFrames};
};

const normalizeEntranceRefs = (
  params: TextCardParams,
  durationInFrames: number,
): AnimationReferenceList | undefined => {
  const entrance = params.entrance ?? 'fade-up';
  const refs = entrance === 'none'
    ? []
    : (Array.isArray(entrance) ? entrance : [entrance]).map((ref) => withDuration(ref, ENTRANCE_DURATION_FRAMES));
  const hasTypeOn = refs.some((ref) => typeof ref === 'string' ? ref === 'type-on' : ref.id === 'type-on');
  if (params.typewriter !== false && !hasTypeOn) {
    refs.push({
      id: 'type-on',
      durationFrames: durationInFrames,
      params: {
        durationFraction: params.typewriterDurationFraction ?? 0.55,
        startFrame: ENTRANCE_DURATION_FRAMES,
      },
    });
  }
  return refs.length > 0 ? refs : undefined;
};

const normalizeExitRefs = (params: TextCardParams): AnimationReferenceList | undefined => {
  const exit = params.exit ?? 'fade';
  if (exit === 'none') {
    return undefined;
  }
  return (Array.isArray(exit) ? exit : [exit]).map((ref) => withDuration(ref, EXIT_DURATION_FRAMES));
};

export const TextCard = ({
  clip,
  params: rawParams,
  theme,
}: EffectProps): ReactElement | null => {
  const params = rawParams as TextCardParams | undefined;
  const text = params?.content;
  if (!text) {
    return null;
  }

  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();

  const align = params.align ?? 'center';
  const baseContent = <span>{text}</span>;
  const entranceContent = composeAnimations({
    clip,
    refs: normalizeEntranceRefs(params, durationInFrames),
    phase: 'entrance',
    content: baseContent,
    text,
    theme,
    fps,
    elapsedFrames: frame,
  });
  const exitStart = Math.max(0, durationInFrames - EXIT_DURATION_FRAMES);
  const animatedContent = composeAnimations({
    clip,
    refs: normalizeExitRefs(params),
    phase: 'exit',
    content: entranceContent,
    text,
    theme,
    fps,
    elapsedFrames: Math.max(0, frame - exitStart),
  });

  return (
    <AbsoluteFill
      style={{
        position: 'absolute',
        left: clip.x ?? 0,
        top: clip.y ?? 0,
        width: clip.width ?? '100%',
        height: clip.height ?? '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: JUSTIFY_CONTENT[align],
        color: params.colorOverride ?? theme.color.fg,
        fontFamily: theme.type.families.heading,
        fontSize: params.fontSizeOverride ?? theme.type.size.base,
        fontWeight: params.bold ? theme.type.weight.bold : theme.type.weight.normal,
        fontStyle: params.italic ? 'italic' : 'normal',
        textAlign: align,
        whiteSpace: 'pre-wrap',
        lineHeight: theme.type.lineHeight,
        opacity: clip.opacity ?? 1,
        transformOrigin: 'center center',
        padding: '0 6%',
      }}
    >
      {animatedContent}
    </AbsoluteFill>
  );
};

export default TextCard;
