import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useLightboxNavigation } from './useLightboxNavigation';
import { __resetOverlayStackForTests, useOverlayStackApi } from '@/shared/state/overlayStack';

function dispatchKey(key: string) {
  act(() => {
    document.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
  });
}

describe('useLightboxNavigation', () => {
  afterEach(() => {
    cleanup();
    document.body.innerHTML = '';
    __resetOverlayStackForTests();
  });

  it('fires onPrevious for ArrowLeft when no dialog backdrop exists', () => {
    const onPrevious = vi.fn();
    const onClose = vi.fn();

    renderHook(() =>
      useLightboxNavigation({
        onNext: vi.fn(),
        onPrevious,
        onClose,
      }),
    );

    dispatchKey('ArrowLeft');

    expect(onPrevious).toHaveBeenCalledTimes(1);
    expect(onClose).not.toHaveBeenCalled();
  });

  it('fires onClose for Escape when no dialog backdrop exists', () => {
    const onClose = vi.fn();

    renderHook(() =>
      useLightboxNavigation({
        onNext: vi.fn(),
        onPrevious: vi.fn(),
        onClose,
      }),
    );

    dispatchKey('Escape');

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('suppresses navigation keys when a non-lightbox modal overlay is topmost and open', () => {
    const onPrevious = vi.fn();

    renderHook(() =>
      useLightboxNavigation({
        onNext: vi.fn(),
        onPrevious,
        onClose: vi.fn(),
      }),
    );

    const dialogPopup = document.createElement('div');
    dialogPopup.setAttribute('data-state', 'open');
    document.body.appendChild(dialogPopup);

    useOverlayStackApi().getState().pushOverlay({
      id: 'dialog-above-lightbox',
      type: 'dialog',
      modal: true,
      elements: [dialogPopup],
    });
    dispatchKey('ArrowLeft');

    expect(onPrevious).not.toHaveBeenCalled();
  });

  it('does not suppress navigation keys when the lightbox is topmost', () => {
    const onPrevious = vi.fn();

    const lightboxPopup = document.createElement('div');
    document.body.appendChild(lightboxPopup);

    useOverlayStackApi().getState().pushOverlay({
      id: 'lightbox',
      type: 'lightbox',
      modal: true,
      elements: [lightboxPopup],
    });

    renderHook(() =>
      useLightboxNavigation({
        onNext: vi.fn(),
        onPrevious,
        onClose: vi.fn(),
      }),
    );

    dispatchKey('ArrowLeft');

    expect(onPrevious).toHaveBeenCalledTimes(1);
  });

  it('does not suppress keys when a non-modal tooltip sits above the lightbox', () => {
    const onPrevious = vi.fn();
    const onClose = vi.fn();

    const lightboxPopup = document.createElement('div');
    lightboxPopup.setAttribute('data-state', 'open');
    document.body.appendChild(lightboxPopup);

    const tooltipPopup = document.createElement('div');
    tooltipPopup.setAttribute('data-state', 'open');
    document.body.appendChild(tooltipPopup);

    useOverlayStackApi().getState().pushOverlay({
      id: 'lightbox',
      type: 'lightbox',
      modal: true,
      elements: [lightboxPopup],
    });
    useOverlayStackApi().getState().pushOverlay({
      id: 'tooltip-above',
      type: 'tooltip',
      modal: false,
      elements: [tooltipPopup],
    });

    renderHook(() =>
      useLightboxNavigation({
        onNext: vi.fn(),
        onPrevious,
        onClose,
      }),
    );

    dispatchKey('ArrowLeft');
    dispatchKey('Escape');

    expect(onPrevious).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does not suppress keys when a modal overlay registers but is not actually open', () => {
    // Regression: a Base-UI Select/Popover registers with modal:true before its popup
    // opens (elements missing / data-state !== "open"). Previously this left
    // `getTopOverlay()` pointing at the stale entry and broke arrow/Escape in the lightbox.
    const onPrevious = vi.fn();
    const onClose = vi.fn();

    const lightboxPopup = document.createElement('div');
    lightboxPopup.setAttribute('data-state', 'open');
    document.body.appendChild(lightboxPopup);

    useOverlayStackApi().getState().pushOverlay({
      id: 'lightbox',
      type: 'lightbox',
      modal: true,
      elements: [lightboxPopup],
    });
    // Simulate a modal overlay registered with no open elements (what Base-UI does
    // during its mount phase before the popup acquires data-state="open").
    useOverlayStackApi().getState().pushOverlay({
      id: 'stale-select',
      type: 'select',
      modal: true,
    });

    renderHook(() =>
      useLightboxNavigation({
        onNext: vi.fn(),
        onPrevious,
        onClose,
      }),
    );

    dispatchKey('ArrowLeft');
    dispatchKey('Escape');

    expect(onPrevious).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('suppresses navigation keys when a modal overlay above the lightbox is actually open', () => {
    const onPrevious = vi.fn();
    const onClose = vi.fn();

    const lightboxPopup = document.createElement('div');
    lightboxPopup.setAttribute('data-state', 'open');
    document.body.appendChild(lightboxPopup);

    const selectPopup = document.createElement('div');
    selectPopup.setAttribute('data-state', 'open');
    document.body.appendChild(selectPopup);

    useOverlayStackApi().getState().pushOverlay({
      id: 'lightbox',
      type: 'lightbox',
      modal: true,
      elements: [lightboxPopup],
    });
    useOverlayStackApi().getState().pushOverlay({
      id: 'open-select',
      type: 'select',
      modal: true,
      elements: [selectPopup],
    });

    renderHook(() =>
      useLightboxNavigation({
        onNext: vi.fn(),
        onPrevious,
        onClose,
      }),
    );

    dispatchKey('ArrowLeft');
    dispatchKey('Escape');

    expect(onPrevious).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });
});
