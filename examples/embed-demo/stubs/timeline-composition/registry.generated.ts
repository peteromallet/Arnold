export type ThemePackageRegistryEntry = {
  component: unknown;
  themeId?: string;
  source?: string;
};

export type ThemePackageClipType = string;

export const THEME_PACKAGE_REGISTRY: Record<string, ThemePackageRegistryEntry> = {};
