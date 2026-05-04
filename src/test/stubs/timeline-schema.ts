export type ThemeRegistry = Record<string, Record<string, unknown>>;

export type TimelineConfigT = Record<string, unknown>;
export type TimelineClipT = Record<string, unknown>;
export type ThemeOverridesT = Record<string, unknown>;
export type TimelineOutputT = Record<string, unknown>;
export type AssetEntryT = Record<string, unknown>;
export type ThemeT = Record<string, unknown>;

export function resolveTheme(
  config: {
    theme?: string | null;
    theme_overrides?: Record<string, unknown> | null;
  },
  registry: ThemeRegistry = {},
) {
  const baseTheme = config.theme ? (registry[config.theme] ?? {}) : {};
  return {
    ...baseTheme,
    ...(config.theme_overrides ?? {}),
  };
}
