type RecordShape = Record<string, unknown>;

export type TimelineConfigT = Record<string, unknown>;
export type TimelineClipT = Record<string, unknown>;
export type ThemeOverridesT = Record<string, unknown>;
export type TimelineOutputT = Record<string, unknown>;
export type AssetEntryT = Record<string, unknown>;
export type ThemeT = Record<string, unknown>;
export type ThemeRegistry = Record<string, Record<string, unknown>>;

const isRecord = (value: unknown): value is RecordShape => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const deepMerge = (base: RecordShape, overlay: RecordShape): RecordShape => {
  const merged: RecordShape = { ...base };
  for (const [key, value] of Object.entries(overlay)) {
    const baseValue = merged[key];
    if (isRecord(baseValue) && isRecord(value)) {
      merged[key] = deepMerge(baseValue, value);
    } else {
      merged[key] = value;
    }
  }
  return merged;
};

export function resolveTheme(
  config: {
    theme?: string | null;
    theme_overrides?: Record<string, unknown> | null;
  },
  registry: ThemeRegistry = {},
) {
  const themeId = config.theme ?? 'default';
  const base = registry[themeId] ?? { id: themeId };
  const overrides = isRecord(config.theme_overrides) ? config.theme_overrides : {};
  return deepMerge(base, overrides);
}
