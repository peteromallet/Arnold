import { createContext, useContext, type PropsWithChildren } from 'react';

export type Theme = {
  id: string;
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

export type RuntimeTheme = Theme;

export const DEFAULT_THEME: Theme = {
  id: 'default',
  color: {
    fg: '#ffffff',
    bg: '#101010',
    accent: '#fde68a',
  },
  type: {
    families: {
      heading: "'TTGertika', sans-serif",
      body: "'Inter', system-ui, sans-serif",
      mono: "'JetBrains Mono', ui-monospace, monospace",
    },
    size: {
      base: 56,
      small: 32,
      large: 128,
    },
    weight: {
      normal: 400,
      bold: 700,
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

const ThemeContext = createContext<RuntimeTheme>(DEFAULT_THEME);

export function ThemeProvider({
  value,
  children,
}: PropsWithChildren<{ value: RuntimeTheme }>) {
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
