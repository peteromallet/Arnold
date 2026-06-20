import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

vi.mock('@/shared/hooks/mobile', () => ({
  useIsMobile: vi.fn(() => false),
  useIsTablet: vi.fn(() => false),
}));

vi.mock('react-router-dom', () => ({
  useLocation: vi.fn(() => ({ pathname: '/travel' })),
}));

vi.mock('@/shared/config/panes', () => ({
  PANE_CONFIG: {
    timing: { HOVER_DELAY: 300, ANIMATION_DURATION: 300 },
  },
}));

vi.mock('@/shared/lib/typedEvents', () => ({
  dispatchAppEvent: vi.fn(),
  useAppEventListener: vi.fn(),
}));

import { useSlidingPane } from '../useSlidingPane';

describe('useSlidingPane', () => {
  const mockToggleLock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns expected shape', () => {
    const { result } = renderHook(() =>
      useSlidingPane({
        side: 'left',
        isLocked: false,
        onToggleLock: mockToggleLock,
      })
    );

    expect(typeof result.current.isOpen).toBe('boolean');
    expect(typeof result.current.isLocked).toBe('boolean');
    expect(typeof result.current.toggleLock).toBe('function');
    expect(typeof result.current.openPane).toBe('function');
    expect(typeof result.current.handlePaneEnter).toBe('function');
    expect(typeof result.current.handlePaneLeave).toBe('function');
    expect(typeof result.current.transformClass).toBe('string');
    expect(result.current.paneProps).toBeDefined();
    expect(typeof result.current.showBackdrop).toBe('boolean');
    expect(typeof result.current.closePane).toBe('function');
  });

  it('starts closed when not locked', () => {
    const { result } = renderHook(() =>
      useSlidingPane({
        side: 'left',
        isLocked: false,
        onToggleLock: mockToggleLock,
      })
    );

    expect(result.current.isOpen).toBe(false);
  });

  it('starts open when locked', () => {
    const { result } = renderHook(() =>
      useSlidingPane({
        side: 'left',
        isLocked: true,
        onToggleLock: mockToggleLock,
      })
    );

    expect(result.current.isOpen).toBe(true);
  });

  it('openPane opens the pane', () => {
    const { result } = renderHook(() =>
      useSlidingPane({
        side: 'right',
        isLocked: false,
        onToggleLock: mockToggleLock,
      })
    );

    act(() => {
      result.current.openPane();
    });

    expect(result.current.isOpen).toBe(true);
  });

  it('closePane closes the pane', () => {
    const { result } = renderHook(() =>
      useSlidingPane({
        side: 'right',
        isLocked: false,
        onToggleLock: mockToggleLock,
      })
    );

    act(() => {
      result.current.openPane();
    });

    expect(result.current.isOpen).toBe(true);

    act(() => {
      result.current.closePane();
    });

    expect(result.current.isOpen).toBe(false);
  });

  it('toggleLock calls onToggleLock', () => {
    const { result } = renderHook(() =>
      useSlidingPane({
        side: 'left',
        isLocked: false,
        onToggleLock: mockToggleLock,
      })
    );

    act(() => {
      result.current.toggleLock();
    });

    expect(mockToggleLock).toHaveBeenCalled();
  });

  it('toggleLock with force=true calls toggle when state differs', () => {
    const { result } = renderHook(() =>
      useSlidingPane({
        side: 'left',
        isLocked: false,
        onToggleLock: mockToggleLock,
      })
    );

    act(() => {
      result.current.toggleLock(true);
    });

    expect(mockToggleLock).toHaveBeenCalled();
  });

  it('toggleLock with force matching current state does not call toggle', () => {
    const { result } = renderHook(() =>
      useSlidingPane({
        side: 'left',
        isLocked: false,
        onToggleLock: mockToggleLock,
      })
    );

    act(() => {
      result.current.toggleLock(false);
    });

    expect(mockToggleLock).not.toHaveBeenCalled();
  });

  it('returns correct transform class for left pane (hidden)', () => {
    const { result } = renderHook(() =>
      useSlidingPane({
        side: 'left',
        isLocked: false,
        onToggleLock: mockToggleLock,
      })
    );

    expect(result.current.transformClass).toBe('-translate-x-full');
  });

  it('returns correct transform class for left pane (visible)', () => {
    const { result } = renderHook(() =>
      useSlidingPane({
        side: 'left',
        isLocked: true,
        onToggleLock: mockToggleLock,
      })
    );

    expect(result.current.transformClass).toBe('translate-x-0');
  });

  it('returns correct transform class for right pane (hidden)', () => {
    const { result } = renderHook(() =>
      useSlidingPane({
        side: 'right',
        isLocked: false,
        onToggleLock: mockToggleLock,
      })
    );

    expect(result.current.transformClass).toBe('translate-x-full');
  });

  it('returns correct transform class for bottom pane (hidden)', () => {
    const { result } = renderHook(() =>
      useSlidingPane({
        side: 'bottom',
        isLocked: false,
        onToggleLock: mockToggleLock,
      })
    );

    expect(result.current.transformClass).toBe('translate-y-full');
  });

  it('programmaticOpen opens the pane', () => {
    const { result } = renderHook(() =>
      useSlidingPane({
        side: 'left',
        isLocked: false,
        onToggleLock: mockToggleLock,
        programmaticOpen: true,
      })
    );

    expect(result.current.isOpen).toBe(true);
  });

  it('does not show backdrop on desktop', () => {
    const { result } = renderHook(() =>
      useSlidingPane({
        side: 'left',
        isLocked: false,
        onToggleLock: mockToggleLock,
      })
    );

    act(() => {
      result.current.openPane();
    });

    expect(result.current.showBackdrop).toBe(false);
  });

  it('calls onOpenChange when state changes', () => {
    const onOpenChange = vi.fn();
    const { result } = renderHook(() =>
      useSlidingPane({
        side: 'left',
        isLocked: false,
        onToggleLock: mockToggleLock,
        onOpenChange,
      })
    );

    act(() => {
      result.current.openPane();
    });

    expect(onOpenChange).toHaveBeenCalledWith(true);
  });

  it('hover-open survives unrelated re-renders', () => {
    const isLocked = false;
    const { result, rerender } = renderHook(() =>
      useSlidingPane({
        side: 'left',
        isLocked,
        onToggleLock: mockToggleLock,
      })
    );

    // Hover open
    act(() => {
      result.current.openPane();
    });
    expect(result.current.isOpen).toBe(true);

    // Re-render with same props (simulates unrelated parent re-render)
    rerender();
    expect(result.current.isOpen).toBe(true);
  });

  it('locking clears hover state so unlocking closes pane', () => {
    let isLocked = false;
    const { result, rerender } = renderHook(() =>
      useSlidingPane({
        side: 'left',
        isLocked,
        onToggleLock: mockToggleLock,
      })
    );

    // Hover open
    act(() => {
      result.current.openPane();
    });
    expect(result.current.isOpen).toBe(true);

    // Lock — pane stays open via isLocked, hover state gets cleared
    isLocked = true;
    rerender();
    expect(result.current.isOpen).toBe(true);

    // Unlock — pane closes because hover was cleared when locked
    isLocked = false;
    rerender();
    expect(result.current.isOpen).toBe(false);
  });

  it('programmatic open keeps pane open even after hover-leave', () => {
    const { result } = renderHook(() =>
      useSlidingPane({
        side: 'left',
        isLocked: false,
        onToggleLock: mockToggleLock,
        programmaticOpen: true,
      })
    );

    expect(result.current.isOpen).toBe(true);

    // Attempt to close via closePane (simulates hover leave)
    act(() => {
      result.current.closePane();
    });

    // Should stay open because programmaticOpen is true
    expect(result.current.isOpen).toBe(true);
  });
});
