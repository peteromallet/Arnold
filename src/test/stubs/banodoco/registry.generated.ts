export const THEME_PACKAGE_CLIP_TYPES: string[] = [];

export const THEME_PACKAGE_REGISTRY: Record<string, {
  component: () => null;
  themeId: string;
  source: string;
}> = {};
