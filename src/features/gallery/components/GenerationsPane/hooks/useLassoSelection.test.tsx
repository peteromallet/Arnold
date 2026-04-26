// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useLassoSelection } from './useLassoSelection';

function setRect(element: Element, rect: Pick<DOMRect, 'left' | 'top' | 'right' | 'bottom' | 'width' | 'height'>) {
  Object.defineProperty(element, 'getBoundingClientRect', {
    configurable: true,
    value: () => ({
      ...rect,
      x: rect.left,
      y: rect.top,
      toJSON: () => rect,
    }),
  });
}

function createMouseEvent(overrides: Partial<MouseEvent> & { target: HTMLElement }) {
  return {
    button: 0,
    clientX: 0,
    clientY: 0,
    shiftKey: false,
    metaKey: false,
    ctrlKey: false,
    preventDefault: vi.fn(),
    ...overrides,
  };
}

describe('useLassoSelection', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('selects intersecting items when dragging from the gallery background', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    setRect(container, { left: 0, top: 0, right: 300, bottom: 300, width: 300, height: 300 });

    const item = document.createElement('div');
    item.dataset.galleryItemId = 'g1';
    setRect(item, { left: 20, top: 20, right: 80, bottom: 80, width: 60, height: 60 });
    container.appendChild(item);

    const onSelectItems = vi.fn();
    const { result } = renderHook(() => useLassoSelection({
      containerRef: { current: container },
      items: [
        { id: 'g1', url: 'https://example.com/1.png', type: 'image/png' },
      ],
      onSelectItems,
    }));

    act(() => {
      result.current.handleMouseDown(createMouseEvent({
        target: container,
        clientX: 10,
        clientY: 10,
      }) as never);
    });

    expect(result.current.selectionRect).toEqual({
      left: 10,
      top: 10,
      width: 0,
      height: 0,
    });

    act(() => {
      window.dispatchEvent(new MouseEvent('mousemove', { clientX: 100, clientY: 100 }));
      window.dispatchEvent(new MouseEvent('mouseup', { clientX: 100, clientY: 100 }));
    });

    expect(onSelectItems).toHaveBeenCalledWith([
      {
        id: 'g1',
        url: 'https://example.com/1.png',
        type: 'image/png',
        generationId: 'g1',
      },
    ], { additive: false });
  });

  it('does not start lasso selection when the pointer starts on a gallery item', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    setRect(container, { left: 0, top: 0, right: 300, bottom: 300, width: 300, height: 300 });

    const item = document.createElement('div');
    item.dataset.galleryItemId = 'g1';
    container.appendChild(item);

    const onSelectItems = vi.fn();
    const { result } = renderHook(() => useLassoSelection({
      containerRef: { current: container },
      items: [
        { id: 'g1', url: 'https://example.com/1.png', type: 'image/png' },
      ],
      onSelectItems,
    }));

    act(() => {
      result.current.handleMouseDown(createMouseEvent({
        target: item,
        clientX: 10,
        clientY: 10,
      }) as never);
    });

    expect(result.current.selectionRect).toBeNull();

    act(() => {
      window.dispatchEvent(new MouseEvent('mouseup', { clientX: 100, clientY: 100 }));
    });

    expect(onSelectItems).not.toHaveBeenCalled();
  });

  it('appends to the existing selection when shift is held during a lasso drag', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    setRect(container, { left: 0, top: 0, right: 300, bottom: 300, width: 300, height: 300 });

    const item = document.createElement('div');
    item.dataset.galleryItemId = 'g2';
    setRect(item, { left: 40, top: 40, right: 90, bottom: 90, width: 50, height: 50 });
    container.appendChild(item);

    const onSelectItems = vi.fn();
    const { result } = renderHook(() => useLassoSelection({
      containerRef: { current: container },
      items: [
        { id: 'g2', url: 'https://example.com/2.mp4', isVideo: true },
      ],
      onSelectItems,
    }));

    act(() => {
      result.current.handleMouseDown(createMouseEvent({
        target: container,
        clientX: 10,
        clientY: 10,
        shiftKey: true,
      }) as never);
      window.dispatchEvent(new MouseEvent('mouseup', { clientX: 100, clientY: 100 }));
    });

    expect(onSelectItems).toHaveBeenCalledWith([
      {
        id: 'g2',
        url: 'https://example.com/2.mp4',
        type: 'video/mp4',
        generationId: 'g2',
      },
    ], { additive: true });
  });
});
