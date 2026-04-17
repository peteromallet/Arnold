import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

const mockNavigateToShot = vi.fn();
const mockCreateShot = vi.fn();

vi.mock('@/shared/hooks/shots/useShotNavigation', () => ({
  useShotNavigation: vi.fn(() => ({
    navigateToShot: mockNavigateToShot,
  })),
}));

vi.mock('@/shared/hooks/shotCreation/useShotCreation', () => ({
  useShotCreation: vi.fn(() => ({
    createShot: mockCreateShot,
    isCreating: false,
  })),
}));

import { useQuickShotCreate } from '../useQuickShotCreate';

describe('useQuickShotCreate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    mockCreateShot.mockResolvedValue({
      shotId: 'new-shot-1',
      shotName: 'Shot 1',
    });
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('returns expected shape', () => {
    const { result } = renderHook(() =>
      useQuickShotCreate({
        generationId: 'gen-1',
        shots: [],
      })
    );

    expect(result.current.isCreatingShot).toBe(false);
    expect(result.current.quickCreateSuccess.isSuccessful).toBe(false);
    expect(result.current.quickCreateSuccess.shotId).toBeNull();
    expect(typeof result.current.handleQuickCreateAndAdd).toBe('function');
    expect(typeof result.current.handleVisitCreatedShot).toBe('function');
    expect(typeof result.current.clearQuickCreateSuccess).toBe('function');
  });

  it('creates shot and sets success state', async () => {
    const onShotChange = vi.fn();
    const { result } = renderHook(() =>
      useQuickShotCreate({
        generationId: 'gen-1',
        shots: [],
        onShotChange,
      })
    );

    await act(async () => {
      await result.current.handleQuickCreateAndAdd();
    });

    expect(mockCreateShot).toHaveBeenCalledWith(
      expect.objectContaining({ generationId: 'gen-1' })
    );
    expect(onShotChange).toHaveBeenCalledWith('new-shot-1');
    expect(result.current.quickCreateSuccess.isSuccessful).toBe(true);
    expect(result.current.quickCreateSuccess.shotId).toBe('new-shot-1');
  });

  it('calls onLoadingStart and onLoadingEnd callbacks', async () => {
    const onLoadingStart = vi.fn();
    const onLoadingEnd = vi.fn();

    const { result } = renderHook(() =>
      useQuickShotCreate({
        generationId: 'gen-1',
        shots: [],
        onLoadingStart,
        onLoadingEnd,
      })
    );

    await act(async () => {
      await result.current.handleQuickCreateAndAdd();
    });

    expect(onLoadingStart).toHaveBeenCalledTimes(1);
    expect(onLoadingEnd).toHaveBeenCalledTimes(1);
  });

  it('handles createShot returning null', async () => {
    mockCreateShot.mockResolvedValue(null);

    const onShotChange = vi.fn();
    const { result } = renderHook(() =>
      useQuickShotCreate({
        generationId: 'gen-1',
        shots: [],
        onShotChange,
      })
    );

    await act(async () => {
      await result.current.handleQuickCreateAndAdd();
    });

    expect(onShotChange).not.toHaveBeenCalled();
    expect(result.current.quickCreateSuccess.isSuccessful).toBe(false);
  });

  it('clearQuickCreateSuccess resets success state', async () => {
    const { result } = renderHook(() =>
      useQuickShotCreate({
        generationId: 'gen-1',
        shots: [],
      })
    );

    await act(async () => {
      await result.current.handleQuickCreateAndAdd();
    });

    expect(result.current.quickCreateSuccess.isSuccessful).toBe(true);

    act(() => {
      result.current.clearQuickCreateSuccess();
    });

    expect(result.current.quickCreateSuccess.isSuccessful).toBe(false);
    expect(result.current.quickCreateSuccess.shotId).toBeNull();
  });

  it('handleVisitCreatedShot calls onClose and navigateToShot', async () => {
    const onClose = vi.fn();
    const { result } = renderHook(() =>
      useQuickShotCreate({
        generationId: 'gen-1',
        shots: [{ id: 'new-shot-1', name: 'Shot 1' }],
        onClose,
      })
    );

    await act(async () => {
      await result.current.handleQuickCreateAndAdd();
    });

    act(() => {
      result.current.handleVisitCreatedShot();
    });

    expect(onClose).toHaveBeenCalled();
    expect(mockNavigateToShot).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'new-shot-1' }),
      expect.objectContaining({ isNewlyCreated: true })
    );
  });

  it('passes custom shot name to createShot', async () => {
    const { result } = renderHook(() =>
      useQuickShotCreate({
        generationId: 'gen-1',
        shots: [],
      })
    );

    await act(async () => {
      await result.current.handleQuickCreateAndAdd('My Custom Shot');
    });

    expect(mockCreateShot).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'My Custom Shot' })
    );
  });
});
