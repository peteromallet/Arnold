import * as React from 'react';

const OVERLAY_BASE_Z_INDEX = 1000;
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
): React.CSSProperties {
  const resolvedLayer = Math.max(layer ?? 1, 1);

  return {
    ...(style ?? {}),
    zIndex:
      OVERLAY_BASE_Z_INDEX +
      resolvedLayer * OVERLAY_LAYER_STEP +
      OVERLAY_LAYER_SLOT_OFFSET[slot],
  };
}
