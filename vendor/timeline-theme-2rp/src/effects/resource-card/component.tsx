import type {ReactElement} from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {type AnimationReferenceList, type EffectProps, composeAnimations, useTheme} from '@banodoco/timeline-composition/theme-api';


type ResourceCardParams = {
  label?: string;
  title?: string;
  detail?: string;
  metric?: string;
  previews?: string[];
  entrance?: AnimationReferenceList;
  exit?: AnimationReferenceList;
};

const PREVIEW_COUNT_DEFAULT = 3;

const PreviewTiles = ({urls, accent}: {urls: string[]; accent: string}): ReactElement => {
  const tiles = urls.length > 0 ? urls : new Array(PREVIEW_COUNT_DEFAULT).fill('');
  return (
    <div style={{display: 'flex', gap: 28, marginTop: 40}}>
      {tiles.slice(0, 3).map((url, idx) => (
        <div
          key={idx}
          style={{
            flex: '1 1 0',
            aspectRatio: '4 / 3',
            border: `2px solid ${accent}`,
            background: url
              ? `center/cover url("${url}")`
              : 'linear-gradient(135deg, #1a120a, #050505 70%)',
            boxShadow: `0 0 40px ${accent}22`,
          }}
        />
      ))}
    </div>
  );
};

export const ResourceCard = ({clip, params: rawParams, fps}: EffectProps<ResourceCardParams>): ReactElement => {
  const theme = useTheme();
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const params = rawParams ?? {};
  const previews = Array.isArray(params.previews) ? params.previews.filter((u) => typeof u === 'string') : [];
  const content = (
    <div style={{borderTop: `3px solid ${theme.color.accent}`, borderBottom: `3px solid ${theme.color.accent}`, padding: '44px 0', maxWidth: 1320, width: '100%'}}>
      <div style={{color: theme.color.accent, fontFamily: theme.type.families.mono, fontSize: 28, marginBottom: 18}}>{params.label ?? 'RESOURCE'}</div>
      <div style={{fontFamily: theme.type.families.heading, fontSize: 76, lineHeight: 1}}>{params.title ?? 'Leverage for creators'}</div>
      <div style={{fontFamily: theme.type.families.body, fontSize: 34, lineHeight: 1.2, marginTop: 22, color: theme.color.fg, opacity: 0.9}}>{params.detail ?? 'more surface area for craft, taste, and agency'}</div>
      <PreviewTiles urls={previews} accent={theme.color.accent} />
    </div>
  );
  const entered = composeAnimations({clip, refs: params.entrance ?? ['scale-in'], phase: 'entrance', content, text: params.title, theme, fps, elapsedFrames: frame});
  const animated = composeAnimations({clip, refs: params.exit ?? ['fade'], phase: 'exit', content: entered, text: params.title, theme, fps, elapsedFrames: Math.max(0, frame - (durationInFrames - 12))});
  return <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', padding: '0 8%', color: theme.color.fg, background: theme.color.bg}}>{animated}</AbsoluteFill>;
};

export default ResourceCard;
