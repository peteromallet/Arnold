import {
  DEFAULT_THEME,
  type Theme,
} from '@banodoco/timeline-composition/theme-api';
import type {
  ResolvedTimelineConfig,
  ThemeOverrides,
} from '@/tools/video-editor/types/index.ts';

type ThemeRegistry = Record<string, Theme>;

const THEME_2RP: Theme = {
  id: '2rp',
  visual: {
    color: {
      fg: '#ffffff',
      bg: '#000000',
      accent: '#fde68a',
    },
    type: {
      families: {
        heading: "'Sixtyfour', 'Sixtyfour Variable', monospace",
        body: "'Inter', system-ui, -apple-system, Helvetica, Arial, sans-serif",
        mono: "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
      },
      size: {
        base: 56,
        small: 32,
        large: 128,
      },
      weight: {
        normal: 300,
        bold: 500,
      },
      lineHeight: 1.1,
    },
    motion: {
      fadeMs: 500,
    },
    canvas: {
      width: 1920,
      height: 1080,
      fps: 30,
    },
  },
};

export const INSTALLED_TIMELINE_THEMES: ThemeRegistry = {
  '2rp': THEME_2RP,
};

export const AVAILABLE_TIMELINE_THEME_IDS = Object.keys(
  INSTALLED_TIMELINE_THEMES,
) as readonly string[];

export const isInstalledTimelineThemeId = (value: unknown): value is (typeof AVAILABLE_TIMELINE_THEME_IDS)[number] => {
  return typeof value === 'string' && Object.prototype.hasOwnProperty.call(INSTALLED_TIMELINE_THEMES, value);
};

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const deepMerge = <T extends Record<string, unknown>>(base: T, overlay: Record<string, unknown>): T => {
  const result: Record<string, unknown> = { ...base };
  for (const [key, value] of Object.entries(overlay)) {
    const baseValue = result[key];
    if (isRecord(baseValue) && isRecord(value)) {
      result[key] = deepMerge(baseValue, value);
    } else {
      result[key] = value;
    }
  }
  return result as T;
};

const cloneTheme = (theme: Theme): Theme => {
  return deepMerge(
    DEFAULT_THEME as unknown as Record<string, unknown>,
    theme as unknown as Record<string, unknown>,
  ) as unknown as Theme;
};

export const resolveTimelineRenderTheme = (
  config: Pick<ResolvedTimelineConfig, 'theme' | 'theme_overrides'>,
): Theme => {
  const installedTheme = typeof config.theme === 'string'
    ? INSTALLED_TIMELINE_THEMES[config.theme]
    : undefined;
  const baseTheme = cloneTheme(installedTheme ?? DEFAULT_THEME);
  const overrides = config.theme_overrides;
  if (!isRecord(overrides) || Object.keys(overrides).length === 0) {
    return baseTheme;
  }
  return deepMerge(
    baseTheme as unknown as Record<string, unknown>,
    overrides as ThemeOverrides,
  ) as unknown as Theme;
};
