import {
  createContext,
  useContext,
  type PropsWithChildren,
  type ReactElement,
} from 'react';

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
  visual?: {
    canvas?: {
      width?: number;
      height?: number;
      fps?: number;
    };
  };
};

export type RuntimeTheme = Theme;

export const DEFAULT_THEME: Theme = {
  id: 'fallback',
  color: {
    fg: '#ffffff',
    bg: '#111111',
    accent: '#fde68a',
  },
  type: {
    families: {
      heading: 'Inter, sans-serif',
      body: 'Inter, sans-serif',
      mono: 'JetBrains Mono, monospace',
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
  visual: {
    canvas: {
      width: 1920,
      height: 1080,
      fps: 30,
    },
  },
};

const ThemeContext = createContext<RuntimeTheme>(DEFAULT_THEME);

export function ThemeProvider({
  children,
  value,
}: PropsWithChildren<{ value: RuntimeTheme }>): ReactElement {
  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): RuntimeTheme {
  return useContext(ThemeContext);
}
