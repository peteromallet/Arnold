/** Shared z-layer contract for cross-module overlay ordering. */
export const UI_Z_LAYERS = {
  HOME_GLASS_PANE: 100,
  LIGHTBOX_MODAL: 100010,
  // Locked panes must sit above the lightbox (but below non-lightbox modals,
  // which render at OVERLAY_BASE_Z_INDEX = 110000+, see shared.tsx).
  GENERATIONS_PANE_BACKDROP: 100012,
  GENERATIONS_PANE: 100013,
  GENERATIONS_DROP_CHIP: 100014,
  TASKS_PANE_TAB_ABOVE_LIGHTBOX: 100015,
  // Toasts must clear non-lightbox modals (110000+), so keep this above 110020
  // (the highest practical modal popup z at layer ~2).
  TOAST_VIEWPORT: 120000,
  TASKS_PANE_TAB_BEHIND_LIGHTBOX: 99,
} as const;
