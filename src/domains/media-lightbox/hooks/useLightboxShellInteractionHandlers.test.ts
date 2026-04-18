import React from 'react';
import { act, renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useLightboxShellInteractionHandlers } from './useLightboxShellInteractionHandlers';
import { isFloatingOverlayElement, shouldAllowTouchThrough } from '@/shared/lib/interactions/elementPolicy';
import { isElementWithinTopmostOverlay } from '@/shared/components/ui/overlay';

vi.mock('@/shared/lib/interactions/elementPolicy', () => ({
  isFloatingOverlayElement: vi.fn(),
  shouldAllowTouchThrough: vi.fn(),
}));

vi.mock('@/shared/components/ui/overlay', async () => {
  const actual = await vi.importActual<typeof import('@/shared/components/ui/overlay')>('@/shared/components/ui/overlay');
  return {
    ...actual,
    isElementWithinTopmostOverlay: vi.fn(),
  };
});

function createPointerEvent(target: EventTarget, currentTarget: EventTarget = target) {
  return {
    target,
    currentTarget,
    preventDefault: vi.fn(),
    stopPropagation: vi.fn(),
    nativeEvent: { stopImmediatePropagation: vi.fn() },
  } as unknown as React.PointerEvent;
}

function createMouseEvent(target: EventTarget, currentTarget: EventTarget = target) {
  return {
    target,
    currentTarget,
    stopPropagation: vi.fn(),
  } as unknown as React.MouseEvent;
}

function createTouchEvent(target: EventTarget) {
  return {
    target,
    preventDefault: vi.fn(),
    stopPropagation: vi.fn(),
    nativeEvent: { stopImmediatePropagation: vi.fn() },
  } as unknown as React.TouchEvent;
}

describe('useLightboxShellInteractionHandlers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(isFloatingOverlayElement).mockReturnValue(false);
    vi.mocked(shouldAllowTouchThrough).mockReturnValue(false);
    vi.mocked(isElementWithinTopmostOverlay).mockReturnValue(true);
  });

  afterEach(() => {
    document.querySelectorAll('[data-dialog-backdrop]').forEach((el) => el.remove());
  });

  it('closes on overlay pointer up when click starts and ends on overlay', () => {
    const onClose = vi.fn();
    const popup = document.createElement('div');
    const popupRef = { current: popup };
    const { result } = renderHook(() =>
      useLightboxShellInteractionHandlers({
        hasCanvasOverlay: false,
        isRepositionMode: false,
        isMobile: false,
        onClose,
        popupRef,
      }),
    );

    const overlay = document.createElement('div');
    const downEvent = createPointerEvent(overlay, overlay);
    const upEvent = createPointerEvent(overlay, overlay);

    act(() => {
      result.current.handleOverlayPointerDown(downEvent);
      result.current.handleOverlayPointerUp(upEvent);
    });

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(downEvent.preventDefault).toHaveBeenCalledTimes(1);
    expect(downEvent.stopPropagation).toHaveBeenCalledTimes(1);
    expect(downEvent.nativeEvent.stopImmediatePropagation).toHaveBeenCalledTimes(1);
    expect(upEvent.preventDefault).toHaveBeenCalledTimes(1);
    expect(upEvent.stopPropagation).toHaveBeenCalledTimes(1);
    expect(upEvent.nativeEvent.stopImmediatePropagation).toHaveBeenCalledTimes(1);
  });

  it('does not close on overlay pointer up while in reposition mode', () => {
    const onClose = vi.fn();
    const popupRef = { current: document.createElement('div') };
    const { result } = renderHook(() =>
      useLightboxShellInteractionHandlers({
        hasCanvasOverlay: false,
        isRepositionMode: true,
        isMobile: false,
        onClose,
        popupRef,
      }),
    );

    const overlay = document.createElement('div');
    const downEvent = createPointerEvent(overlay, overlay);
    const upEvent = createPointerEvent(overlay, overlay);

    act(() => {
      result.current.handleOverlayPointerDown(downEvent);
      result.current.handleOverlayPointerUp(upEvent);
    });

    expect(onClose).not.toHaveBeenCalled();
  });

  it('closes from background capture when pointer down/up are both on lightbox background', () => {
    const onClose = vi.fn();
    const popupRef = { current: document.createElement('div') };
    const { result } = renderHook(() =>
      useLightboxShellInteractionHandlers({
        hasCanvasOverlay: false,
        isRepositionMode: false,
        isMobile: false,
        onClose,
        popupRef,
      }),
    );

    const bg = document.createElement('div');
    bg.setAttribute('data-lightbox-bg', '');
    const downEvent = createPointerEvent(bg, bg);
    const clickEvent = createMouseEvent(bg, bg);

    act(() => {
      result.current.handleBgPointerDownCapture(downEvent);
      result.current.handleBgClickCapture(clickEvent);
    });

    expect(clickEvent.stopPropagation).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('stops content pointer propagation unless target is a floating overlay element', () => {
    const onClose = vi.fn();
    const popupRef = { current: document.createElement('div') };
    const { result } = renderHook(() =>
      useLightboxShellInteractionHandlers({
        hasCanvasOverlay: false,
        isRepositionMode: false,
        isMobile: false,
        onClose,
        popupRef,
      }),
    );

    const regularTarget = document.createElement('div');
    const regularEvent = createPointerEvent(regularTarget, regularTarget);
    act(() => {
      result.current.handleContentPointerDown(regularEvent);
    });
    expect(regularEvent.stopPropagation).toHaveBeenCalledTimes(1);

    vi.mocked(isFloatingOverlayElement).mockReturnValue(true);
    const floatingTarget = document.createElement('div');
    const floatingEvent = createPointerEvent(floatingTarget, floatingTarget);
    act(() => {
      result.current.handleContentPointerDown(floatingEvent);
    });
    expect(floatingEvent.stopPropagation).not.toHaveBeenCalled();
  });

  it('handles touch-through policy and mobile touch cancel behavior', () => {
    const onClose = vi.fn();
    const popupRef = { current: document.createElement('div') };
    const { result } = renderHook(() =>
      useLightboxShellInteractionHandlers({
        hasCanvasOverlay: true,
        isRepositionMode: false,
        isMobile: true,
        onClose,
        popupRef,
      }),
    );

    const target = document.createElement('div');
    const touchEvent = createTouchEvent(target);
    vi.mocked(shouldAllowTouchThrough).mockReturnValue(true);
    act(() => {
      result.current.handleTouchEvent(touchEvent);
    });
    expect(touchEvent.stopPropagation).not.toHaveBeenCalled();

    vi.mocked(shouldAllowTouchThrough).mockReturnValue(false);
    const blockedTouchEvent = createTouchEvent(target);
    act(() => {
      result.current.handleTouchEvent(blockedTouchEvent);
    });
    expect(blockedTouchEvent.stopPropagation).toHaveBeenCalledTimes(1);

    const cancelWithoutDialog = createTouchEvent(target);
    act(() => {
      result.current.handleTouchCancel(cancelWithoutDialog);
    });
    expect(cancelWithoutDialog.preventDefault).toHaveBeenCalledTimes(1);
    expect(cancelWithoutDialog.stopPropagation).toHaveBeenCalledTimes(1);
    expect(cancelWithoutDialog.nativeEvent.stopImmediatePropagation).toHaveBeenCalledTimes(1);
  });

  it('ignores overlay dismissal handlers when the lightbox is not topmost', () => {
    vi.mocked(isElementWithinTopmostOverlay).mockReturnValue(false);
    const onClose = vi.fn();
    const popupRef = { current: document.createElement('div') };
    const { result } = renderHook(() =>
      useLightboxShellInteractionHandlers({
        hasCanvasOverlay: false,
        isRepositionMode: false,
        isMobile: false,
        onClose,
        popupRef,
      }),
    );

    const overlay = document.createElement('div');
    const downEvent = createPointerEvent(overlay, overlay);
    const upEvent = createPointerEvent(overlay, overlay);

    act(() => {
      result.current.handleOverlayPointerDown(downEvent);
      result.current.handleOverlayPointerUp(upEvent);
    });

    expect(onClose).not.toHaveBeenCalled();
    expect(downEvent.preventDefault).not.toHaveBeenCalled();
    expect(upEvent.preventDefault).not.toHaveBeenCalled();
  });
});
