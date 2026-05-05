import type { FC } from 'react';
import { AbsoluteFill } from 'remotion';
import { useTheme, type RuntimeTheme } from '@banodoco/timeline-composition/theme-api';
import type { ResolvedTimelineClip } from '@/tools/video-editor/types/index.ts';

type TitleCardSequenceParams = {
  kicker?: string;
  title?: string;
  subtitle?: string;
};

type TitleCardSequenceProps = {
  clip: ResolvedTimelineClip;
  params?: TitleCardSequenceParams;
  theme?: RuntimeTheme;
  fps: number;
};

export const TitleCardSequence: FC<TitleCardSequenceProps> = ({ params }) => {
  const theme = useTheme();
  const kicker = typeof params?.kicker === 'string' && params.kicker.trim().length > 0
    ? params.kicker
    : 'TITLE';
  const title = typeof params?.title === 'string' && params.title.trim().length > 0
    ? params.title
    : 'Untitled';
  const subtitle = typeof params?.subtitle === 'string' ? params.subtitle.trim() : '';

  return (
    <AbsoluteFill
      data-testid="title-card-sequence"
      data-kicker={kicker}
      data-title={title}
      data-subtitle={subtitle}
      style={{
        alignItems: 'center',
        background: `linear-gradient(160deg, ${theme.color.bg} 0%, ${theme.color.accent}22 100%)`,
        color: theme.color.fg,
        display: 'flex',
        justifyContent: 'center',
        padding: '8%',
      }}
    >
      <div
        style={{
          border: `1px solid ${theme.color.accent}55`,
          boxShadow: `0 24px 80px ${theme.color.accent}18`,
          maxWidth: '82%',
          padding: '5.5% 6%',
          textAlign: 'center',
        }}
      >
        <div
          style={{
            color: theme.color.accent,
            fontFamily: theme.type.families.mono,
            fontSize: 24,
            letterSpacing: '0.22em',
            marginBottom: 18,
            textTransform: 'uppercase',
          }}
        >
          {kicker}
        </div>
        <div
          style={{
            fontFamily: theme.type.families.heading,
            fontSize: 88,
            lineHeight: 0.95,
            marginBottom: subtitle ? 20 : 0,
          }}
        >
          {title}
        </div>
        {subtitle ? (
          <div
            style={{
              color: `${theme.color.fg}cc`,
              fontFamily: theme.type.families.body,
              fontSize: 30,
              lineHeight: 1.3,
            }}
          >
            {subtitle}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

export default TitleCardSequence;
