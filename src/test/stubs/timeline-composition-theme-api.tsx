import { createContext, useContext, type PropsWithChildren } from 'react';

export type Theme = {
  id?: string;
  visual?: {
    color?: Record<string, unknown>;
    type?: Record<string, unknown>;
    motion?: Record<string, unknown>;
    canvas?: Record<string, unknown>;
  };
  [key: string]: unknown;
};

export type RuntimeTheme = Theme;

export const DEFAULT_THEME: Theme = {
  id: 'default',
  visual: {
    color: {
      fg: '#ffffff',
      bg: '#000000',
      accent: '#38bdf8',
    },
    type: {
      families: {
        heading: 'system-ui',
        body: 'system-ui',
        mono: 'monospace',
      },
      size: {
        base: 48,
        small: 24,
        large: 96,
      },
      weight: {
        normal: 400,
        bold: 700,
      },
      lineHeight: 1.2,
    },
    motion: {
      fadeMs: 300,
    },
    canvas: {
      width: 1920,
      height: 1080,
      fps: 30,
    },
  },
};

const ThemeContext = createContext<RuntimeTheme>(DEFAULT_THEME);

export function ThemeProvider({
  value,
  children,
}: PropsWithChildren<{ value?: RuntimeTheme }>) {
  return (
    <ThemeContext.Provider value={value ?? DEFAULT_THEME}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
