import { createContext, useContext, type ReactNode } from 'react';

export type Theme = {
  id: string;
  visual: {
    color?: {
      fg?: string;
      bg?: string;
      accent?: string;
    };
    type?: {
      families?: {
        heading?: string;
        body?: string;
        mono?: string;
      };
    };
    motion?: Record<string, unknown>;
    canvas: {
      width: number;
      height: number;
      fps: number;
    };
  };
};

export type RuntimeTheme = Theme & {
  color: NonNullable<Theme['visual']['color']>;
  type: NonNullable<Theme['visual']['type']>;
  motion: NonNullable<Theme['visual']['motion']>;
  canvas: Theme['visual']['canvas'];
};

export const DEFAULT_THEME: Theme = {
  id: 'default',
  visual: {
    color: {
      fg: '#ffffff',
      bg: '#000000',
      accent: '#ffffff',
    },
    type: {
      families: {
        heading: 'Georgia, serif',
        body: 'Georgia, serif',
        mono: 'Menlo, monospace',
      },
    },
    motion: {
      fadeMs: 250,
    },
    canvas: {
      width: 1280,
      height: 720,
      fps: 30,
    },
  },
};

const toRuntimeTheme = (theme: Theme): RuntimeTheme => {
  return {
    ...theme,
    color: theme.visual.color ?? {},
    type: theme.visual.type ?? {},
    motion: theme.visual.motion ?? {},
    canvas: theme.visual.canvas,
  };
};

const ThemeContext = createContext<RuntimeTheme>(toRuntimeTheme(DEFAULT_THEME));

export function ThemeProvider({
  value,
  children,
}: {
  value: Theme;
  children: ReactNode;
}) {
  return <ThemeContext.Provider value={toRuntimeTheme(value)}>{children}</ThemeContext.Provider>;
}

export function useTheme(): RuntimeTheme {
  return useContext(ThemeContext);
}
