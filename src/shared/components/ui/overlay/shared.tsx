import * as React from 'react';

// Regular modals (Dialog, AlertDialog, Popover, Select, etc.) must render above
// locked panes (GenerationsPane at 100013, GENERATIONS_DROP_CHIP at 100014,
// TASKS_PANE_TAB_ABOVE_LIGHTBOX at 100015, TASKS_PANE_CONTENT at 100016).
// The lightbox is the sole exception — it renders below panes so users can
// interact with locked panes while media is open.
export const OVERLAY_BASE_Z_INDEX = 110000;
export const LIGHTBOX_BASE_Z_INDEX = 1000;
const OVERLAY_LAYER_STEP = 10;

const OVERLAY_LAYER_SLOT_OFFSET = {
  backdrop: 0,
  positioner: 1,
  popup: 2,
} as const;

type OverlayLayerSlot = keyof typeof OVERLAY_LAYER_SLOT_OFFSET;

export function composeRefs<T>(
  ...refs: Array<React.Ref<T> | undefined | null>
): React.RefCallback<T> {
  return (node) => {
    refs.forEach((ref) => {
      if (typeof ref === 'function') {
        ref(node);
      } else if (ref) {
        (ref as React.MutableRefObject<T | null>).current = node;
      }
    });
  };
}

export function getOverlayLayerStyle(
  layer: number | null,
  slot: OverlayLayerSlot,
  style?: React.CSSProperties,
  options?: { baseZIndex?: number },
): React.CSSProperties {
  const resolvedLayer = Math.max(layer ?? 1, 1);
  const base = options?.baseZIndex ?? OVERLAY_BASE_Z_INDEX;

  return {
    ...(style ?? {}),
    zIndex:
      base +
      resolvedLayer * OVERLAY_LAYER_STEP +
      OVERLAY_LAYER_SLOT_OFFSET[slot],
  };
}
