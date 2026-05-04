import type {ReactElement} from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {fitText} from '@remotion/layout-utils';
import {type AnimationReferenceList, type EffectProps, composeAnimations, useTheme} from '@banodoco/timeline-composition/theme-api';


type CtaCardParams = {
  title?: string;
  action?: string;
  note?: string;
  entrance?: AnimationReferenceList;
  exit?: AnimationReferenceList;
};

export const CtaCard = ({clip, params: rawParams, fps}: EffectProps<CtaCardParams>): ReactElement => {
  const theme = useTheme();
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const params = rawParams ?? {};
  const content = (
    <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', width: '100%'}}>
      <div style={{fontFamily: theme.type.families.heading, fontSize: Math.min(180, fitText({text: params.title ?? 'Imagine, then create', withinWidth: 1500, fontFamily: theme.type.families.heading, fontWeight: theme.type.weight.bold}).fontSize), lineHeight: 1, fontWeight: theme.type.weight.bold, textAlign: 'center'}}>{params.title ?? 'Imagine, then create'}</div>
      <div style={{color: theme.color.accent, fontFamily: theme.type.families.body, fontSize: 46, lineHeight: 1.15, marginTop: 36, textAlign: 'center'}}>{params.action ?? 'Join the second renaissance.'}</div>
      {params.note ? <div style={{fontFamily: theme.type.families.mono, fontSize: 26, marginTop: 32, opacity: 0.8, textAlign: 'center'}}>{params.note}</div> : null}
    </div>
  );
  const entered = composeAnimations({clip, refs: params.entrance ?? ['fade-up'], phase: 'entrance', content, text: params.title, theme, fps, elapsedFrames: frame});
  const animated = composeAnimations({clip, refs: params.exit ?? ['fade'], phase: 'exit', content: entered, text: params.title, theme, fps, elapsedFrames: Math.max(0, frame - (durationInFrames - 12))});
  return <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', padding: '0 8%', color: theme.color.fg, background: theme.color.bg}}>{animated}</AbsoluteFill>;
};

export default CtaCard;
