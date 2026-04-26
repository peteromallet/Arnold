import { describe, expect, it } from 'vitest';
import { UI_Z_LAYERS } from './uiLayers';

describe('uiLayers', () => {
  it('keeps the cross-surface z-layer contract ordered as expected', () => {
    expect(UI_Z_LAYERS.HOME_GLASS_PANE).toBe(100);
    // Locked panes sit above the lightbox so users can still interact while a lightbox is open.
    expect(UI_Z_LAYERS.GENERATIONS_PANE_BACKDROP).toBeGreaterThan(UI_Z_LAYERS.LIGHTBOX_MODAL);
    expect(UI_Z_LAYERS.GENERATIONS_PANE).toBeGreaterThan(UI_Z_LAYERS.GENERATIONS_PANE_BACKDROP);
    expect(UI_Z_LAYERS.TASKS_PANE_TAB_ABOVE_LIGHTBOX).toBeGreaterThan(UI_Z_LAYERS.LIGHTBOX_MODAL);
    expect(UI_Z_LAYERS.TASKS_PANE_TAB_ABOVE_LIGHTBOX).toBeGreaterThan(UI_Z_LAYERS.GENERATIONS_PANE);
    expect(UI_Z_LAYERS.TASKS_PANE_CONTENT).toBeGreaterThan(UI_Z_LAYERS.LIGHTBOX_MODAL);
    expect(UI_Z_LAYERS.TASKS_PANE_CONTENT).toBeGreaterThan(UI_Z_LAYERS.GENERATIONS_PANE);
    expect(UI_Z_LAYERS.TASKS_PANE_CONTENT).toBeGreaterThan(UI_Z_LAYERS.GENERATIONS_DROP_CHIP);
    expect(UI_Z_LAYERS.TASKS_PANE_CONTENT).toBeGreaterThan(UI_Z_LAYERS.TASKS_PANE_TAB_ABOVE_LIGHTBOX);
    expect(UI_Z_LAYERS.TASKS_PANE_CONTENT).toBeLessThan(UI_Z_LAYERS.TOAST_VIEWPORT);
    expect(UI_Z_LAYERS.TOAST_VIEWPORT).toBeGreaterThan(UI_Z_LAYERS.TASKS_PANE_TAB_ABOVE_LIGHTBOX);
    expect(UI_Z_LAYERS.TASKS_PANE_TAB_BEHIND_LIGHTBOX).toBeLessThan(UI_Z_LAYERS.LIGHTBOX_MODAL);
  });
});
