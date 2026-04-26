export const PANE_CONFIG = {
  dimensions: {
    DEFAULT_HEIGHT: 350,
    DEFAULT_WIDTH: 300,
  },
  timing: {
    HOVER_DELAY: 100,
    ANIMATION_DURATION: 300,
  },
  zIndex: {
    PANE: 'z-[60]',
    // Pane control tabs must sit above the GenerationsPane body/backdrop
    // (UI_Z_LAYERS.GENERATIONS_PANE = 100013, _BACKDROP = 100012) so the tab
    // stays clickable when the pane is open but not locked (i.e. when the
    // mobile backdrop renders and would otherwise cover the tab).
    CONTROL_LOCKED: 'z-[100015]',
    CONTROL_UNLOCKED: 'z-[100016]',
  },
  transition: {
    EASING: 'ease-smooth',
    PROPERTIES: {
      TRANSFORM_ONLY: 'transition-transform',
      TRANSFORM_OPACITY: 'transition-[transform,opacity]',
    }
  }
} as const;

export type PaneSide = 'left' | 'right' | 'bottom' | 'top';

interface PaneOffsets {
  bottom?: number;
  horizontal?: number;
}

export interface PanePosition {
  side: PaneSide;
  dimension: number;
  offsets: PaneOffsets;
  isVisible: boolean;
} 