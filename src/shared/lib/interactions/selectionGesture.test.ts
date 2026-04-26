import { describe, expect, it } from 'vitest';
import {
  isAdditiveSelectionEvent,
  isClickLikePointerGesture,
  isPrimaryPointer,
} from './selectionGesture';

describe('selectionGesture', () => {
  describe('isAdditiveSelectionEvent', () => {
    it('reads additive selection intent from the event modifiers', () => {
      expect(isAdditiveSelectionEvent({ metaKey: true, ctrlKey: false, shiftKey: false })).toBe(true);
      expect(isAdditiveSelectionEvent({ metaKey: false, ctrlKey: true, shiftKey: false })).toBe(true);
      expect(isAdditiveSelectionEvent({ metaKey: false, ctrlKey: false, shiftKey: true })).toBe(true);
      expect(isAdditiveSelectionEvent({ metaKey: false, ctrlKey: false, shiftKey: false })).toBe(false);
    });
  });

  describe('isPrimaryPointer', () => {
    it('accepts only the primary pointer button', () => {
      expect(isPrimaryPointer({ button: 0 })).toBe(true);
      expect(isPrimaryPointer({ button: 1 })).toBe(false);
      expect(isPrimaryPointer({ button: 2 })).toBe(false);
    });
  });

  describe('isClickLikePointerGesture', () => {
    it('treats movement within the threshold as click-like', () => {
      expect(isClickLikePointerGesture({ x: 10, y: 20 }, { x: 16, y: 24 })).toBe(true);
      expect(isClickLikePointerGesture({ x: 0, y: 0 }, { x: 8, y: 0 })).toBe(true);
    });

    it('rejects movement beyond the threshold', () => {
      expect(isClickLikePointerGesture({ x: 0, y: 0 }, { x: 9, y: 0 })).toBe(false);
      expect(isClickLikePointerGesture({ x: 0, y: 0 }, { x: 3, y: 5 }, 4)).toBe(false);
    });
  });
});
