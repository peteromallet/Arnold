import type {ReactElement} from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {fitText} from '@remotion/layout-utils';
import {type AnimationReferenceList, type EffectProps, composeAnimations, useTheme} from '@banodoco/timeline-composition/theme-api';


type SectionHookParams = {
  kicker?: string;
  title?: string;
  subtitle?: string;
  entrance?: AnimationReferenceList;
  exit?: AnimationReferenceList;
};

export const SectionHook = ({clip, params: rawParams, fps}: EffectProps<SectionHookParams>): ReactElement => {
  const theme = useTheme();
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const params = rawParams ?? {};
  const content = (
    <div style={{maxWidth: 1620, textAlign: 'center'}}>
      {params.kicker ? (
        <div style={{color: theme.color.accent, fontFamily: theme.type.families.mono, fontSize: theme.type.size.small, letterSpacing: 0, marginBottom: 28}}>
          {params.kicker}
        </div>
      ) : null}
      <div style={{fontFamily: theme.type.families.heading, fontSize: Math.min(240, fitText({text: params.title ?? 'A new renaissance', withinWidth: 1620, fontFamily: theme.type.families.heading, fontWeight: theme.type.weight.bold}).fontSize), fontWeight: theme.type.weight.bold, lineHeight: 0.95}}>
        {params.title ?? 'A new renaissance'}
      </div>
      {params.subtitle ? (
        <div style={{fontFamily: theme.type.families.body, fontSize: theme.type.size.base, lineHeight: theme.type.lineHeight, marginTop: 32, maxWidth: 980, marginLeft: 'auto', marginRight: 'auto'}}>
          {params.subtitle}
        </div>
      ) : null}
    </div>
  );
  // Animation choice is authoritative from the effect's defaults.json; cut.py
  // strips entrance/exit overrides off branded clips before they hit the
  // timeline. The fallback here only applies when the effect is rendered
  // outside a timeline (e.g. the smoke fixture).
  const entered = composeAnimations({clip, refs: params.entrance ?? ['fade-up'], phase: 'entrance', content, text: params.title, theme, fps, elapsedFrames: frame});
  const animated = composeAnimations({clip, refs: params.exit ?? ['fade'], phase: 'exit', content: entered, text: params.title, theme, fps, elapsedFrames: Math.max(0, frame - (durationInFrames - 12))});
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', padding: '0 9%', color: theme.color.fg, background: theme.color.bg}}>
      {animated}
    </AbsoluteFill>
  );
};

export default SectionHook;
