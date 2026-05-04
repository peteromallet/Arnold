import { createContext, useContext, type PropsWithChildren } from 'react';

export type Theme = {
  id?: string;
  visual: {
    color: {
      accent: string;
      bg: string;
      fg?: string;
    };
    type: {
      families: {
        heading: string;
        body?: string;
        mono?: string;
      };
    };
  };
};

export const DEFAULT_THEME: Theme = {
  id: 'default',
  visual: {
    color: {
      accent: '#ffffff',
      bg: '#000000',
      fg: '#ffffff',
    },
    type: {
      families: {
        heading: 'Georgia, serif',
        body: 'Georgia, serif',
        mono: 'monospace',
      },
    },
  },
};

export type RuntimeTheme = Theme['visual'];

const ThemeContext = createContext<RuntimeTheme>(DEFAULT_THEME.visual);

export const ThemeProvider = ({
  children,
  value,
}: PropsWithChildren<{ value: Theme }>) => (
  <ThemeContext.Provider value={value.visual}>
    {children}
  </ThemeContext.Provider>
);

export const useTheme = (): RuntimeTheme => useContext(ThemeContext);
