// @vitest-environment jsdom
import React from 'react';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { TrackListRenderer } from '@/tools/video-editor/components/TimelineEditor/TrackListRenderer';
import type { TrackDefinition } from '@/tools/video-editor/types';
import type { TimelineRow } from '@/tools/video-editor/types/timeline-canvas';

const tracks: TrackDefinition[] = [
  { id: 'V1', kind: 'visual', label: 'V1' },
  { id: 'V2', kind: 'visual', label: 'V2' },
];

const rows: TimelineRow[] = [
  {
    id: 'V1',
    actions: [{ id: 'clip-1', start: 0, end: 2, effectId: 'effect-clip-1' }],
  },
  {
    id: 'V2',
    actions: [{ id: 'clip-2', start: 2, end: 4, effectId: 'effect-clip-2' }],
  },
];

describe('TrackListRenderer', () => {
  it('keeps unaffected row action renders stable when the clamp ring changes for another row', () => {
    const getActionRender = vi.fn((_action, _row, _width) => <div>clip</div>);
    const props = {
      rows,
      tracks,
      rowHeight: 48,
      startLeft: 0,
      pixelsPerSecond: 100,
      selectedTrackId: null,
      resizeClampedActionId: null,
      rowResizePreview: [{}, {}],
      resizeHandleWidth: 8,
      getActionRender,
      onSelectTrack: vi.fn(),
      onTrackChange: vi.fn(),
      onRemoveTrack: vi.fn(),
      onTrackDragEnd: vi.fn(),
      trackSensors: [] as never,
    } satisfies React.ComponentProps<typeof TrackListRenderer>;

    const { rerender } = render(<TrackListRenderer {...props} />);

    expect(getActionRender).toHaveBeenCalledTimes(2);
    expect(getActionRender.mock.calls.map(([action]) => action.id)).toEqual(['clip-1', 'clip-2']);

    rerender(
      <TrackListRenderer
        {...props}
        resizeClampedActionId="clip-1"
      />,
    );

    expect(getActionRender).toHaveBeenCalledTimes(3);
    expect(getActionRender.mock.calls.at(-1)?.[0].id).toBe('clip-1');
  });
});
