/** Shared z-layer contract for cross-module overlay ordering. */
export const UI_Z_LAYERS = {
  HOME_GLASS_PANE: 100,
  LIGHTBOX_MODAL: 100010,
  // Locked panes must sit above the lightbox so users can still interact with them
  // while a lightbox is open.
  GENERATIONS_PANE_BACKDROP: 100012,
  GENERATIONS_PANE: 100013,
  TASKS_PANE_TAB_ABOVE_LIGHTBOX: 100014,
  TOAST_VIEWPORT: 100020,
  TASKS_PANE_TAB_BEHIND_LIGHTBOX: 99,
} as const;
