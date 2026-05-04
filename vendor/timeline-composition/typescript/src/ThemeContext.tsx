// Sprint 5: physically moved here from tools/remotion/src/ThemeContext.tsx.
// The theme-api re-export now points at this in-package module.

import {createContext, useContext} from 'react';
import type {ReactNode} from 'react';

export type Theme = {
  id: string;
  visual: {
    color: {
      fg: string;
      bg: string;
      accent: string;
    };
    type: {
      families: {
        heading: string;
        body: string;
        mono?: string;
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
};

export type RuntimeTheme = Theme & {
  color: Theme['visual']['color'];
  type: Theme['visual']['type'];
  motion: Theme['visual']['motion'];
};

export const DEFAULT_THEME: Theme = {
  id: 'banodoco-default',
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
      },
      size: {
        base: 64,
        small: 36,
        large: 96,
      },
      weight: {
        normal: 400,
        bold: 700,
      },
      lineHeight: 1.1,
    },
    motion: {
      fadeMs: 250,
    },
    canvas: {
      width: 1920,
      height: 1080,
      fps: 30,
    },
  },
};

const toRuntimeTheme = (theme: Theme): RuntimeTheme => {
  return {
    ...theme,
    color: theme.visual.color,
    type: theme.visual.type,
    motion: theme.visual.motion,
  };
};

const DEFAULT_RUNTIME_THEME = toRuntimeTheme(DEFAULT_THEME);
const ThemeContext = createContext<RuntimeTheme>(DEFAULT_RUNTIME_THEME);

export const ThemeProvider = ({
  children,
  value,
}: {
  children: ReactNode;
  value?: Theme;
}): ReactNode => {
  return <ThemeContext.Provider value={value === undefined ? DEFAULT_RUNTIME_THEME : toRuntimeTheme(value)}>{children}</ThemeContext.Provider>;
};

export const useTheme = (): RuntimeTheme => {
  return useContext(ThemeContext);
};
