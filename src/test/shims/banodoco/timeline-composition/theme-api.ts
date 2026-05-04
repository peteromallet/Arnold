import { createContext, createElement, useContext, type FC, type PropsWithChildren } from 'react';

export type RuntimeTheme = {
  color: {
    fg: string;
    bg: string;
    accent: string;
  };
  type: {
    families: {
      heading: string;
      body: string;
      mono: string;
    };
    size: {
      base: number;
      small: number;
      large: number;
    };
    weight: {
      normal: number;
      bold: number;
    };
    lineHeight: number;
  };
  motion: {
    fadeMs: number;
  };
  canvas: {
    width: number;
    height: number;
    fps: number;
  };
};

export type Theme = {
  id?: string;
  visual?: Partial<RuntimeTheme>;
};

const DEFAULT_RUNTIME_THEME: RuntimeTheme = {
  color: {
    fg: '#ffffff',
    bg: '#000000',
    accent: '#ffffff',
  },
  type: {
    families: {
      heading: 'Georgia, serif',
      body: 'Inter, system-ui, sans-serif',
      mono: 'JetBrains Mono, ui-monospace, monospace',
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
};

export const DEFAULT_THEME: Theme = {
  id: 'default',
  visual: DEFAULT_RUNTIME_THEME,
};

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const deepMerge = <T extends Record<string, unknown>>(base: T, overlay: Record<string, unknown>): T => {
  const result: Record<string, unknown> = { ...base };
  for (const [key, value] of Object.entries(overlay)) {
    const current = result[key];
    if (isRecord(current) && isRecord(value)) {
      result[key] = deepMerge(current, value);
    } else {
      result[key] = value;
    }
  }
  return result as T;
};

const toRuntimeTheme = (theme: Theme | RuntimeTheme | null | undefined): RuntimeTheme => {
  if (isRecord(theme) && isRecord(theme.visual)) {
    return deepMerge(DEFAULT_RUNTIME_THEME, theme.visual);
  }
  if (isRecord(theme)) {
    return deepMerge(DEFAULT_RUNTIME_THEME, theme);
  }
  return DEFAULT_RUNTIME_THEME;
};

const ThemeContext = createContext<RuntimeTheme>(toRuntimeTheme(DEFAULT_THEME));

export const ThemeProvider: FC<PropsWithChildren<{ value: Theme | RuntimeTheme }>> = ({
  value,
  children,
}) => {
  return createElement(ThemeContext.Provider, { value: toRuntimeTheme(value) }, children);
};

export const useTheme = (): RuntimeTheme => useContext(ThemeContext);
