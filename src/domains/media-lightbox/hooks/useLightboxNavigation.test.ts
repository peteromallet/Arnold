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

  it('suppresses navigation keys when a non-lightbox overlay is topmost', () => {
    const onPrevious = vi.fn();

    renderHook(() =>
      useLightboxNavigation({
        onNext: vi.fn(),
        onPrevious,
        onClose: vi.fn(),
      }),
    );

    useOverlayStackApi().getState().pushOverlay({
      id: 'dialog-above-lightbox',
      type: 'dialog',
      modal: true,
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
});
