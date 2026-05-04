import type { FC } from 'react';
import { AbsoluteFill } from 'remotion';
import type { RuntimeTheme } from '@/tools/video-editor/compositions/fallback/theme-api';
import type { ResolvedTimelineClip } from '@/tools/video-editor/types';

type RegisteredSequenceComponent = FC<{
  clip: ResolvedTimelineClip;
  params: unknown;
  theme: RuntimeTheme;
  fps: number;
}>;

const ThemedSequenceStub: RegisteredSequenceComponent = ({ clip, theme }) => {
  return (
    <AbsoluteFill
      data-testid="fallback-themed-sequence"
      data-clip-type={clip.clipType ?? ''}
      style={{
        alignItems: 'center',
        background: theme.color.bg,
        color: theme.color.fg,
        display: 'flex',
        fontFamily: theme.type.families.body,
        justifyContent: 'center',
      }}
    >
      {clip.clipType ?? 'unknown-sequence'}
    </AbsoluteFill>
  );
};

export const THEME_PACKAGE_REGISTRY = {
  'section-hook': {
    component: ThemedSequenceStub,
    themeId: '2rp',
    source: 'fallback:@banodoco/timeline-theme-2rp',
  },
  'art-card': {
    component: ThemedSequenceStub,
    themeId: '2rp',
    source: 'fallback:@banodoco/timeline-theme-2rp',
  },
  'resource-card': {
    component: ThemedSequenceStub,
    themeId: '2rp',
    source: 'fallback:@banodoco/timeline-theme-2rp',
  },
  'cta-card': {
    component: ThemedSequenceStub,
    themeId: '2rp',
    source: 'fallback:@banodoco/timeline-theme-2rp',
  },
} as const;

export type ThemePackageClipType = keyof typeof THEME_PACKAGE_REGISTRY;
