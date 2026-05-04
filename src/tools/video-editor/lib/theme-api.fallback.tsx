import {
  createContext,
  useContext,
  type PropsWithChildren,
} from 'react';

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
  id: string;
  visual: RuntimeTheme;
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
        mono: 'ui-monospace, monospace',
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
  },
};

const ThemeContext = createContext<RuntimeTheme>(DEFAULT_THEME.visual);

export function ThemeProvider({
  children,
  value,
}: PropsWithChildren<{ value: Theme }>) {
  return (
    <ThemeContext.Provider value={value.visual}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): RuntimeTheme {
  return useContext(ThemeContext);
}
