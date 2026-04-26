import { beforeEach, describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useLastAffectedShot } from '@/shared/hooks/shots/useLastAffectedShot';
import {
  __getSelectionStateForTests,
  __resetSelectionStoreForTests,
  systemSetLastAffectedShotId,
} from '@/shared/state/selectionStore';

describe('useLastAffectedShot', () => {
  beforeEach(() => {
    __resetSelectionStoreForTests();
  });

  it('returns the current store value', () => {
    systemSetLastAffectedShotId('shot-123');

    const { result } = renderHook(() => useLastAffectedShot());
    expect(result.current.lastAffectedShotId).toBe('shot-123');
  });

  it('updates through the exposed setter', () => {
    const { result } = renderHook(() => useLastAffectedShot());

    act(() => {
      result.current.setLastAffectedShotId('shot-456');
    });
    expect(__getSelectionStateForTests().shot.lastAffectedShotId).toBe('shot-456');
  });
});
