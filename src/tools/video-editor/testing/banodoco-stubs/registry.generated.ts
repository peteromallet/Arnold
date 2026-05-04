const NullThemeSequence = () => null;

export const THEME_PACKAGE_REGISTRY = {
  'section-hook': {
    component: NullThemeSequence,
    themeId: '2rp',
    source: '@banodoco/timeline-theme-2rp/mock',
  },
  'art-card': {
    component: NullThemeSequence,
    themeId: '2rp',
    source: '@banodoco/timeline-theme-2rp/mock',
  },
  'cta-card': {
    component: NullThemeSequence,
    themeId: '2rp',
    source: '@banodoco/timeline-theme-2rp/mock',
  },
  'resource-card': {
    component: NullThemeSequence,
    themeId: '2rp',
    source: '@banodoco/timeline-theme-2rp/mock',
  },
} as const;

export type ThemePackageClipType = keyof typeof THEME_PACKAGE_REGISTRY;

export const THEME_PACKAGE_CLIP_TYPES = Object.freeze(
  Object.keys(THEME_PACKAGE_REGISTRY) as ThemePackageClipType[],
);
