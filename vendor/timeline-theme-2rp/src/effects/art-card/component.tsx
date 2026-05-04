import type {ReactElement} from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {type AnimationReferenceList, type EffectProps, composeAnimations, useTheme} from '@banodoco/timeline-composition/theme-api';


type ArtCardParams = {
  title?: string;
  caption?: string;
  credit?: string;
  entrance?: AnimationReferenceList;
  exit?: AnimationReferenceList;
};

export const ArtCard = ({clip, params: rawParams, fps}: EffectProps<ArtCardParams>): ReactElement => {
  const theme = useTheme();
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const params = rawParams ?? {};
  const content = (
    <div style={{display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: 56, alignItems: 'center'}}>
      <div style={{border: `2px solid ${theme.color.accent}`, height: 620, boxShadow: `0 0 80px ${theme.color.accent}33`, background: 'linear-gradient(135deg, #18120b, #050505 70%)'}} />
      <div>
        <div style={{fontFamily: theme.type.families.heading, fontSize: 86, lineHeight: 1, fontWeight: theme.type.weight.bold}}>{params.title ?? 'Patronage returns'}</div>
        <div style={{fontFamily: theme.type.families.body, fontSize: 40, lineHeight: 1.2, marginTop: 28}}>{params.caption ?? 'The studio becomes a cathedral for new tools.'}</div>
        {params.credit ? <div style={{color: theme.color.accent, fontFamily: theme.type.families.mono, fontSize: 28, marginTop: 34}}>{params.credit}</div> : null}
      </div>
    </div>
  );
  const entered = composeAnimations({clip, refs: params.entrance ?? ['slide-left'], phase: 'entrance', content, text: params.title, theme, fps, elapsedFrames: frame});
  const animated = composeAnimations({clip, refs: params.exit ?? ['fade'], phase: 'exit', content: entered, text: params.title, theme, fps, elapsedFrames: Math.max(0, frame - (durationInFrames - 12))});
  return <AbsoluteFill style={{justifyContent: 'center', padding: '0 8%', color: theme.color.fg, background: theme.color.bg}}>{animated}</AbsoluteFill>;
};

export default ArtCard;
