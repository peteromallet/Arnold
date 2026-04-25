import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

let isDraggingFiles = false;

vi.mock('@/shared/state/dragOverlayStore', () => ({
  setDragging: (value: boolean) => {
    isDraggingFiles = value;
  },
}));

import { useGlobalFileDragDetection } from './useGlobalFileDragDetection';

function createFileDragEvent(type: 'dragenter' | 'dragover' | 'dragleave' | 'drop'): DragEvent {
  const event = new Event(type, { bubbles: true, cancelable: true }) as DragEvent;
  Object.defineProperty(event, 'dataTransfer', {
    value: { types: ['Files'] },
    configurable: true,
  });
  return event;
}

function createInternalDragEvent(type: 'dragenter' | 'dragover' | 'dragleave' | 'drop'): DragEvent {
  const event = new Event(type, { bubbles: true, cancelable: true }) as DragEvent;
  Object.defineProperty(event, 'dataTransfer', {
    value: { types: ['application/x-dnd-kit'] },
    configurable: true,
  });
  return event;
}

describe('useGlobalFileDragDetection', () => {
  afterEach(() => {
    isDraggingFiles = false;
  });

  it('tracks file drags with nested enter and leave events', () => {
    renderHook(() => useGlobalFileDragDetection());

    const firstEnter = createFileDragEvent('dragenter');
    const nestedEnter = createFileDragEvent('dragenter');
    const nestedLeave = createFileDragEvent('dragleave');
    const finalLeave = createFileDragEvent('dragleave');

    act(() => {
      window.dispatchEvent(firstEnter);
      window.dispatchEvent(nestedEnter);
    });
    expect(isDraggingFiles).toBe(true);

    act(() => {
      window.dispatchEvent(nestedLeave);
    });
    expect(isDraggingFiles).toBe(true);

    act(() => {
      window.dispatchEvent(finalLeave);
    });
    expect(isDraggingFiles).toBe(false);
  });

  it('prevents browser navigation for file dragover/drop and ignores internal drags', () => {
    renderHook(() => useGlobalFileDragDetection());

    const internalDragEnter = createInternalDragEvent('dragenter');
    const dragOver = createFileDragEvent('dragover');
    const drop = createFileDragEvent('drop');

    act(() => {
      window.dispatchEvent(internalDragEnter);
    });
    expect(isDraggingFiles).toBe(false);

    act(() => {
      window.dispatchEvent(dragOver);
    });
    expect(isDraggingFiles).toBe(true);
    expect(dragOver.defaultPrevented).toBe(true);

    act(() => {
      window.dispatchEvent(drop);
    });
    expect(isDraggingFiles).toBe(false);
    expect(drop.defaultPrevented).toBe(true);
  });
});
