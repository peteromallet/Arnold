// @vitest-environment jsdom
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import OverlayEditor from '@/tools/video-editor/components/PreviewPanel/OverlayEditor';
import type { ClipMeta } from '@/tools/video-editor/lib/timeline-data';
import type { TimelineRow } from '@/tools/video-editor/types/timeline-canvas';

const baseRows: TimelineRow[] = [
  {
    id: 'V1',
    actions: [
      {
        id: 'clip-1',
        start: 0,
        end: 5,
      },
    ],
  },
];

const baseProps = (meta: Record<string, ClipMeta>, rows: TimelineRow[] = baseRows) => {
  const parent = document.createElement('div');
  const player = document.createElement('div');
  parent.appendChild(player);
  document.body.appendChild(parent);

  Object.defineProperty(player, 'offsetParent', {
    configurable: true,
    get: () => parent,
  });

  player.getBoundingClientRect = () => ({
    x: 100,
    y: 50,
    top: 50,
    left: 100,
    bottom: 590,
    right: 1060,
    width: 960,
    height: 540,
    toJSON: () => ({}),
  });

  parent.getBoundingClientRect = () => ({
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    bottom: 800,
    right: 1200,
    width: 1200,
    height: 800,
    toJSON: () => ({}),
  });

  return {
    cleanup: () => parent.remove(),
    props: {
      rows,
      meta,
      registry: {},
      currentTime: 1,
      playerContainerRef: { current: player },
      trackScaleMap: { V1: 1 },
      compositionWidth: 1920,
      compositionHeight: 1080,
      selectedClipId: 'clip-1',
      deviceClass: 'desktop' as const,
      inputModality: 'mouse' as const,
      interactionMode: 'move' as const,
      gestureOwner: 'none' as const,
      onSelectClip: vi.fn(),
      onOverlayChange: vi.fn(),
      setInputModalityFromPointerType: vi.fn(() => 'mouse' as const),
      setGestureOwner: vi.fn(),
      setContextTarget: vi.fn(),
      setInspectorTarget: vi.fn(),
      onDoubleClickAsset: vi.fn(),
    },
  };
};

describe('OverlayEditor', () => {
  const cleanups: Array<() => void> = [];

  afterEach(() => {
    while (cleanups.length > 0) {
      cleanups.pop()?.();
    }
  });

  it('starts inline text editing on double-click and commits text on blur', () => {
    const { props, cleanup } = baseProps({
      'clip-1': {
        track: 'V1',
        clipType: 'text',
        hold: 4,
        text: {
          content: 'Before',
          fontSize: 56,
          color: '#ffffff',
          align: 'center',
        },
      },
    });
    cleanups.push(cleanup);

    render(<OverlayEditor {...props} />);

    fireEvent.doubleClick(screen.getByRole('button', { name: /selected overlay before/i }));

    const editor = screen.getByDisplayValue('Before');
    fireEvent.change(editor, { target: { value: 'After' } });
    fireEvent.blur(editor);

    expect(props.onOverlayChange).toHaveBeenCalledWith('clip-1', {
      text: {
        content: 'After',
        fontSize: 56,
        color: '#ffffff',
        align: 'center',
      },
    });
  });

  it('suppresses crop handles for inline-text overlays even when selected', () => {
    const { props, cleanup } = baseProps({
      'clip-1': {
        track: 'V1',
        clipType: 'text',
        hold: 4,
        text: {
          content: 'Headline',
          fontSize: 56,
          color: '#ffffff',
          align: 'center',
        },
      },
    });
    cleanups.push(cleanup);

    const { container } = render(<OverlayEditor {...props} />);

    expect(container.querySelector('[class*=\"cursor-ew-resize\"]')).toBeNull();
    expect(container.querySelector('[class*=\"cursor-ns-resize\"]')).toBeNull();
  });

  it('opens the asset lightbox on media double-click instead of entering text edit mode', () => {
    const { props, cleanup } = baseProps({
      'clip-1': {
        track: 'V1',
        clipType: 'hold',
        hold: 4,
        asset: 'asset-1',
      },
    });
    cleanups.push(cleanup);

    render(<OverlayEditor {...props} />);

    fireEvent.doubleClick(screen.getByRole('button', { name: /selected overlay asset-1/i }));

    expect(props.onDoubleClickAsset).toHaveBeenCalledWith('asset-1', 'clip-1');
    expect(screen.queryByDisplayValue(/asset-1/i)).not.toBeInTheDocument();
  });

  it('excludes effect-layer clips from overlay rendering entirely', () => {
    const { props, cleanup } = baseProps({
      'clip-1': {
        track: 'V1',
        clipType: 'effect-layer',
        hold: 4,
      },
    });
    cleanups.push(cleanup);

    const { container } = render(<OverlayEditor {...props} />);

    expect(container.querySelector('[data-overlay-hit=\"true\"]')).toBeNull();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
