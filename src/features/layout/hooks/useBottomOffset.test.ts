import { describe, it, expect, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useBottomOffset } from './useBottomOffset';

const mockPanesState = vi.hoisted(() => ({
  state: {
    isGenerationsPaneLocked: false,
    isGenerationsPaneOpen: false,
    effectiveGenerationsPaneHeight: 0,
  },
}));
const mockUseLightboxOpen = vi.fn();

vi.mock('@/shared/state/panesStore', () => ({
  usePanesStore: (selector: (state: typeof mockPanesState.state) => unknown) => selector(mockPanesState.state),
}));

vi.mock('@/shared/state/lightboxOpenState', () => ({
  useLightboxOpenState: () => mockUseLightboxOpen(),
}));

describe('useBottomOffset', () => {
  it('returns effectiveGenerationsPaneHeight when pane is locked', () => {
    mockPanesState.state = {
      isGenerationsPaneLocked: true,
      isGenerationsPaneOpen: false,
      effectiveGenerationsPaneHeight: 180,
    };
    mockUseLightboxOpen.mockReturnValue(false);

    const { result } = renderHook(() => useBottomOffset());
    expect(result.current).toBe(180);
  });

  it('returns effectiveGenerationsPaneHeight when pane is open', () => {
    mockPanesState.state = {
      isGenerationsPaneLocked: false,
      isGenerationsPaneOpen: true,
      effectiveGenerationsPaneHeight: 220,
    };
    mockUseLightboxOpen.mockReturnValue(false);

    const { result } = renderHook(() => useBottomOffset());
    expect(result.current).toBe(220);
  });

  it('returns 0 when pane is neither locked nor open', () => {
    mockPanesState.state = {
      isGenerationsPaneLocked: false,
      isGenerationsPaneOpen: false,
      effectiveGenerationsPaneHeight: 220,
    };
    mockUseLightboxOpen.mockReturnValue(false);

    const { result } = renderHook(() => useBottomOffset());
    expect(result.current).toBe(0);
  });

  it('returns 0 when lightbox is open regardless of pane state', () => {
    mockPanesState.state = {
      isGenerationsPaneLocked: true,
      isGenerationsPaneOpen: true,
      effectiveGenerationsPaneHeight: 150,
    };
    mockUseLightboxOpen.mockReturnValue(true);

    const { result } = renderHook(() => useBottomOffset());
    expect(result.current).toBe(0);
  });
});
