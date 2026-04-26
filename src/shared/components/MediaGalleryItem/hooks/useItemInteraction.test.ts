import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { GeneratedImageWithMetadata } from '@/shared/components/MediaGallery/types';
import { useItemInteraction } from './useItemInteraction';

const baseImage: GeneratedImageWithMetadata = {
  id: 'image-1',
  url: 'https://example.com/image-1.png',
};

function buildArgs(overrides: Partial<Parameters<typeof useItemInteraction>[0]> = {}) {
  return {
    image: baseImage,
    isMobile: true,
    mobileActiveImageId: null,
    enableSingleClick: false,
    onImageClick: vi.fn(),
    onMobileTap: vi.fn(),
    ...overrides,
  };
}

function buildInteractionEvent(options: {
  type?: string;
  target?: HTMLElement;
  path?: HTMLElement[];
  changedTouches?: Array<{ clientX: number; clientY: number }>;
}) {
  const target = options.target ?? document.createElement('div');
  const nativeEvent = options.path
    ? { composedPath: () => options.path }
    : {};

  return {
    type: options.type ?? 'click',
    target,
    nativeEvent,
    changedTouches: options.changedTouches ?? [{ clientX: 0, clientY: 0 }],
    preventDefault: vi.fn(),
  };
}

describe('useItemInteraction', () => {
  it('calls onImageClick for single-click mode and skips mobile tap', () => {
    const args = buildArgs({ enableSingleClick: true });
    const { result } = renderHook(() => useItemInteraction(args));
    const event = buildInteractionEvent({ path: [document.createElement('div')] });

    act(() => {
      result.current.handleInteraction(event as never);
    });

    expect(event.preventDefault).toHaveBeenCalledTimes(1);
    // multiSelect is derived from the synthetic event's metaKey/ctrlKey/shiftKey;
    // the buildInteractionEvent helper doesn't set them, so multiSelect is false.
    expect(args.onImageClick).toHaveBeenCalledWith(baseImage, { multiSelect: false });
    expect(args.onMobileTap).not.toHaveBeenCalled();
  });

  it('calls mobile tap handler when single-click mode is disabled', () => {
    const args = buildArgs({ enableSingleClick: false });
    const { result } = renderHook(() => useItemInteraction(args));
    const event = buildInteractionEvent({ path: [document.createElement('div')] });

    act(() => {
      result.current.handleInteraction(event as never);
    });

    expect(event.preventDefault).toHaveBeenCalledTimes(1);
    expect(args.onMobileTap).toHaveBeenCalledWith(baseImage);
    expect(args.onImageClick).not.toHaveBeenCalled();
  });

  it('returns early when interaction starts from button path on active item', () => {
    const button = document.createElement('button');
    const child = document.createElement('span');
    button.appendChild(child);

    const args = buildArgs({ mobileActiveImageId: baseImage.id });
    const { result } = renderHook(() => useItemInteraction(args));
    const event = buildInteractionEvent({ target: child, path: [child, button] });

    act(() => {
      result.current.handleInteraction(event as never);
    });

    expect(event.preventDefault).not.toHaveBeenCalled();
    expect(args.onImageClick).not.toHaveBeenCalled();
    expect(args.onMobileTap).not.toHaveBeenCalled();
  });

  it('returns early when touch movement passes threshold', () => {
    const args = buildArgs();
    const { result } = renderHook(() => useItemInteraction(args));

    act(() => {
      result.current.handleTouchStart({ touches: [{ clientX: 10, clientY: 10 }] } as never);
    });

    const touchEndEvent = buildInteractionEvent({
      type: 'touchend',
      changedTouches: [{ clientX: 30, clientY: 10 }],
      path: [document.createElement('div')],
    });

    act(() => {
      result.current.handleInteraction(touchEndEvent as never);
    });

    expect(touchEndEvent.preventDefault).not.toHaveBeenCalled();
    expect(args.onImageClick).not.toHaveBeenCalled();
    expect(args.onMobileTap).not.toHaveBeenCalled();
  });

  it('returns early for touchend events when no touchstart was captured', () => {
    const args = buildArgs();
    const { result } = renderHook(() => useItemInteraction(args));
    const touchEndEvent = buildInteractionEvent({
      type: 'touchend',
      changedTouches: [{ clientX: 10, clientY: 10 }],
      path: [document.createElement('div')],
    });

    act(() => {
      result.current.handleInteraction(touchEndEvent as never);
    });

    expect(touchEndEvent.preventDefault).not.toHaveBeenCalled();
    expect(args.onMobileTap).not.toHaveBeenCalled();
  });

  it('falls back to target.closest(button) when composedPath is unavailable', () => {
    const button = document.createElement('button');
    const child = document.createElement('span');
    button.appendChild(child);

    const args = buildArgs({ mobileActiveImageId: baseImage.id });
    const { result } = renderHook(() => useItemInteraction(args));
    const event = buildInteractionEvent({ target: child });

    act(() => {
      result.current.handleInteraction(event as never);
    });

    expect(event.preventDefault).not.toHaveBeenCalled();
    expect(args.onMobileTap).not.toHaveBeenCalled();
  });
});
