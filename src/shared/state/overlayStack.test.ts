// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  __resetOverlayStackForTests,
  useOverlayStackApi,
} from './overlayStack';

describe('overlayStack', () => {
  beforeEach(() => {
    __resetOverlayStackForTests();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('keeps modal pointer-events ownership until the last modal overlay closes', () => {
    const store = useOverlayStackApi();

    document.body.style.pointerEvents = 'auto';

    store.getState().pushOverlay({ id: 'dialog-a', type: 'dialog', modal: true });
    expect(document.body.style.pointerEvents).toBe('none');
    expect(store.getState().isTopmostModalOverlay('dialog-a')).toBe(true);

    store.getState().pushOverlay({ id: 'popover-b', type: 'popover', modal: false });
    expect(document.body.style.pointerEvents).toBe('none');
    expect(store.getState().isOverlayTopmost('popover-b')).toBe(true);
    expect(store.getState().isTopmostModalOverlay('dialog-a')).toBe(true);

    store.getState().pushOverlay({ id: 'dialog-c', type: 'dialog', modal: true });
    expect(document.body.style.pointerEvents).toBe('none');
    expect(store.getState().isTopmostModalOverlay('dialog-c')).toBe(true);

    store.getState().popOverlay('dialog-a');
    expect(document.body.style.pointerEvents).toBe('none');
    expect(store.getState().isTopmostModalOverlay('dialog-c')).toBe(true);

    store.getState().popOverlay('dialog-c');
    expect(document.body.style.pointerEvents).toBe('auto');
  });

  it('restores focus only when the closing overlay is the current topmost modal', async () => {
    const store = useOverlayStackApi();
    const openerA = document.createElement('button');
    const openerB = document.createElement('button');
    document.body.append(openerA, openerB);

    const focusSpyA = vi.spyOn(openerA, 'focus');
    const focusSpyB = vi.spyOn(openerB, 'focus');

    store.getState().pushOverlay({
      id: 'dialog-a',
      type: 'dialog',
      modal: true,
      restoreFocusTo: openerA,
    });
    store.getState().pushOverlay({
      id: 'dialog-b',
      type: 'dialog',
      modal: true,
      restoreFocusTo: openerB,
    });

    store.getState().popOverlay('dialog-a');
    await Promise.resolve();
    expect(focusSpyA).not.toHaveBeenCalled();

    store.getState().popOverlay('dialog-b');
    await Promise.resolve();
    expect(focusSpyB).toHaveBeenCalledTimes(1);
  });

  it('tracks layer order and topmost element membership independently from modality', () => {
    const store = useOverlayStackApi();
    const dialogElement = document.createElement('div');
    const popoverElement = document.createElement('div');
    const popoverChild = document.createElement('button');
    popoverElement.appendChild(popoverChild);

    store.getState().pushOverlay({
      id: 'dialog-a',
      type: 'dialog',
      modal: true,
      elements: [dialogElement],
    });
    store.getState().pushOverlay({
      id: 'popover-b',
      type: 'popover',
      elements: [popoverElement],
    });

    expect(store.getState().getOverlayLayer('dialog-a')).toBe(1);
    expect(store.getState().getOverlayLayer('popover-b')).toBe(2);
    expect(store.getState().overlayContainsElement('popover-b', popoverChild)).toBe(true);
    expect(store.getState().isElementWithinAnyOverlay(popoverChild)).toBe(true);
    expect(store.getState().getTopmostOverlayContainingElement(popoverChild)?.id).toBe('popover-b');
    expect(store.getState().getTopmostOverlayContainingElement(dialogElement)?.id).toBe('dialog-a');
  });

  it('updates tracked overlay fields without changing stack order', () => {
    const store = useOverlayStackApi();
    const nextElement = document.createElement('div');

    store.getState().pushOverlay({ id: 'menu-a', type: 'menu' });
    store.getState().pushOverlay({ id: 'dialog-b', type: 'dialog', modal: true });

    store.getState().updateOverlay('menu-a', {
      modal: true,
      restoreFocusTo: document.createElement('button'),
      elements: [nextElement],
    });

    expect(store.getState().getOverlayLayer('menu-a')).toBe(1);
    expect(store.getState().isTopmostModalOverlay('dialog-b')).toBe(true);
    expect(store.getState().overlayContainsElement('menu-a', nextElement)).toBe(true);
  });
});
