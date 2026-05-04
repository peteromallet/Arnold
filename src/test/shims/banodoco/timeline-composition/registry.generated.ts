import type { FC } from 'react';
import type { ResolvedTimelineClip } from '@/tools/video-editor';
import type { RuntimeTheme } from './theme-api';

export type ThemePackageComponentProps = {
  clip: ResolvedTimelineClip;
  params: unknown;
  theme: RuntimeTheme;
  fps: number;
};

export type ThemePackageRegistryEntry = {
  component: FC<ThemePackageComponentProps>;
  themeId: string;
  source: string;
};

export const THEME_PACKAGE_CLIP_TYPES = [
  'section-hook',
  'art-card',
  'cta-card',
  'resource-card',
] as const;

export type ThemePackageClipType = (typeof THEME_PACKAGE_CLIP_TYPES)[number];

const NullSequence: FC<ThemePackageComponentProps> = () => null;

export const THEME_PACKAGE_REGISTRY: Record<ThemePackageClipType, ThemePackageRegistryEntry> = {
  'section-hook': {
    component: NullSequence,
    themeId: '2rp',
    source: 'installed:@banodoco/timeline-theme-2rp',
  },
  'art-card': {
    component: NullSequence,
    themeId: '2rp',
    source: 'installed:@banodoco/timeline-theme-2rp',
  },
  'cta-card': {
    component: NullSequence,
    themeId: '2rp',
    source: 'installed:@banodoco/timeline-theme-2rp',
  },
  'resource-card': {
    component: NullSequence,
    themeId: '2rp',
    source: 'installed:@banodoco/timeline-theme-2rp',
  },
};
