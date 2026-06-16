import { act, cleanup, render } from '@testing-library/react';
import { createRef } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import type { DropIndicatorHandle } from '@/tools/video-editor/components/TimelineEditor/DropIndicator.tsx';
import { DropIndicator } from '@/tools/video-editor/components/TimelineEditor/DropIndicator.tsx';
import { VIDEO_EDITOR_THEME_VARS } from '@/tools/video-editor/lib/themeTokens.ts';

const mockEditArea = () => {
  const area = document.createElement('div');
  area.className = 'timeline-canvas-edit-area';
  area.getBoundingClientRect = () => ({
    top: 100,
    left: 100,
    right: 500,
    bottom: 200,
    width: 400,
    height: 100,
    x: 100,
    y: 100,
    toJSON: () => {},
  });
  document.body.appendChild(area);
  return area;
};

describe('DropIndicator', () => {
  afterEach(() => {
    cleanup();
  });

  it('portals drop indicator elements with video editor theme variables so CSS custom properties resolve', () => {
    const editArea = mockEditArea();
    const editAreaRef = { current: editArea } as React.MutableRefObject<HTMLElement | null>;
    const indicatorRef = createRef<DropIndicatorHandle>();

    render(<DropIndicator ref={indicatorRef} editAreaRef={editAreaRef} />);

    act(() => indicatorRef.current?.show({
      rowTop: 100,
      rowHeight: 48,
      rowLeft: 100,
      rowWidth: 400,
      lineLeft: 150,
      ghostLeft: 150,
      ghostTop: 102,
      ghostWidth: 100,
      ghostHeight: 44,
      ghostLabel: '2.5s',
      label: 'Track 1 · 2.5s',
      isNewTrack: false,
      newTrackKind: null,
      reject: false,
    }));

    const portalRoot = document.body.querySelector('[style*="--video-editor-accent-bg"]');
    expect(portalRoot).toBeInTheDocument();
    expect(portalRoot).toHaveStyle(VIDEO_EDITOR_THEME_VARS as Record<string, string>);

    expect(document.body.querySelector('.drop-indicator-row')).toBeInTheDocument();
    expect(document.body.querySelector('.drop-indicator-ghost')).toBeInTheDocument();
    expect(document.body.querySelector('.drop-indicator-line')).toBeInTheDocument();
    expect(document.body.querySelector('.drop-indicator-label')).toBeInTheDocument();

    editArea.remove();
  });
});
