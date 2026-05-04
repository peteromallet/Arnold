import { act, render, screen } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import type { TimelineConfig } from '@/tools/video-editor/index.ts';
import {
  useVideoEditorCommands,
  useVideoEditorHost,
  useVideoEditorTimeline,
} from '@/tools/video-editor/browser/hooks.tsx';

const { applySequenceDraftToTimeline } = vi.hoisted(() => ({
  applySequenceDraftToTimeline: vi.fn(),
}));

const timelineState = {
  data: {
    config: {
      output: {
        resolution: '1280x720',
        fps: 30,
        file: 'output.mp4',
        background: null,
        background_scale: null,
      },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1', scale: 1, fit: 'contain', opacity: 1, blendMode: 'normal' }],
      clips: [],
    } as TimelineConfig,
    configVersion: 3,
    resolvedConfig: { clips: [], tracks: [], output: { resolution: '1280x720', fps: 30, file: 'output.mp4', background: null, background_scale: null } },
    registry: { assets: { 'asset-1': { file: 'example-image1.jpg', src: '/example-image1.jpg', type: 'image/jpeg' } } },
  },
  isLoading: false,
  selectedClipId: 'clip-1',
  selectedClipIds: new Set(['clip-1', 'clip-2']),
  selectedTrackId: 'V1',
};

const opsState = {
  selectClip: vi.fn(),
  selectClips: vi.fn(),
  addToSelection: vi.fn(),
  clearSelection: vi.fn(),
  setSelectedTrackId: vi.fn(),
  applyEdit: vi.fn(),
  registerAsset: vi.fn(async () => undefined),
};

const chromeState = {
  saveStatus: 'saved',
  renderStatus: 'idle',
  canUndo: true,
  canRedo: false,
  undo: vi.fn(),
  redo: vi.fn(),
  reloadFromServer: vi.fn(async () => undefined),
  startRender: vi.fn(async () => undefined),
};

const previewRef = {
  current: {
    seek: vi.fn(),
    play: vi.fn(),
    pause: vi.fn(),
    togglePlayPause: vi.fn(),
    isPlaying: false,
  },
};

vi.mock('@/tools/video-editor/contexts/DataProviderContext', () => ({
  useVideoEditorRuntime: () => ({
    timelineId: 'timeline-1',
    timelineName: 'Embed demo',
    userId: 'user-1',
    provider: {
      resolveAssetUrl: vi.fn(async (file: string) => `/provider/${file}`),
    },
    assetResolver: {
      resolveAssetUrl: vi.fn((file: string) => `/assets/${file}`),
    },
    exporter: null,
    hostContext: { projectId: 'project-1' },
  }),
}));

vi.mock('@/tools/video-editor/hooks/timelineStore', () => ({
  useTimelineDataSelector: (selector: (state: typeof timelineState) => unknown) => selector(timelineState),
  useTimelineOpsSelector: (selector: (state: typeof opsState) => unknown) => selector(opsState),
  useTimelineChromeSelector: (selector: (state: typeof chromeState) => unknown) => selector(chromeState),
  useTimelinePlaybackSelector: (selector: (state: { currentTime: number; previewRef: typeof previewRef }) => unknown) => (
    selector({ currentTime: 2.5, previewRef })
  ),
}));

vi.mock('@/tools/video-editor/sequence.ts', async () => {
  const actual = await vi.importActual<typeof import('@/tools/video-editor/sequence.ts')>('@/tools/video-editor/sequence.ts');
  return {
    ...actual,
    applySequenceDraftToTimeline,
  };
});

function HookProbe() {
  const host = useVideoEditorHost();
  const timeline = useVideoEditorTimeline();
  const commands = useVideoEditorCommands();

  return (
    <div>
      <div data-testid="timeline-name">{timeline.timelineName}</div>
      <div data-testid="selection">{timeline.selectedClipIds.join(',')}</div>
      <div data-testid="host-asset-url">{host.timelineId}</div>
      <button type="button" onClick={() => commands.selectClip('clip-9')}>select</button>
      <button type="button" onClick={() => commands.replaceTimelineConfig({ ...timeline.config!, clips: [{ id: 'clip-9', track: 'V1', at: 0, clipType: 'text', hold: 2 }] })}>replace</button>
      <button type="button" onClick={() => commands.seek(4)}>seek</button>
      <button
        type="button"
        onClick={() => {
          void commands.applySequenceDraft(
            { clipType: 'section-hook', hold: 3, params: { title: 'Launch' } },
            { mode: 'insert' },
          );
        }}
      >
        sequence
      </button>
    </div>
  );
}

describe('public browser hooks', () => {
  beforeEach(() => {
    applySequenceDraftToTimeline.mockReset();
    opsState.selectClip.mockClear();
    opsState.applyEdit.mockClear();
    previewRef.current.seek.mockClear();
  });

  it('exposes supported host and timeline data for custom browser shells', async () => {
    render(<HookProbe />);

    expect(screen.getByTestId('timeline-name')).toHaveTextContent('Embed demo');
    expect(screen.getByTestId('selection')).toHaveTextContent('clip-1,clip-2');
    expect(screen.getByTestId('host-asset-url')).toHaveTextContent('timeline-1');

    const host = useVideoEditorHost;
    expect(host).toBeTypeOf('function');
  });

  it('runs supported selection, playback, config, and sequence commands', async () => {
    applySequenceDraftToTimeline.mockResolvedValue({
      ok: true,
      clipId: 'clip-sequence',
      selectedClipId: 'clip-sequence',
      selectedTrackId: 'V1',
      config: {
        ...timelineState.data.config,
        clips: [{ id: 'clip-sequence', track: 'V1', at: 2.5, clipType: 'section-hook', hold: 3, params: { title: 'Launch' } }],
      },
    });

    render(<HookProbe />);

    await act(async () => {
      screen.getByRole('button', { name: 'select' }).click();
      screen.getByRole('button', { name: 'replace' }).click();
      screen.getByRole('button', { name: 'seek' }).click();
      screen.getByRole('button', { name: 'sequence' }).click();
    });

    expect(opsState.selectClip).toHaveBeenCalledWith('clip-9');
    expect(opsState.applyEdit).toHaveBeenNthCalledWith(1, {
      type: 'config',
      resolvedConfig: {
        ...timelineState.data.config,
        clips: [{ id: 'clip-9', track: 'V1', at: 0, clipType: 'text', hold: 2 }],
      },
    }, {
      selectedClipId: 'clip-1',
      selectedTrackId: 'V1',
      semantic: undefined,
    });
    expect(previewRef.current.seek).toHaveBeenCalledWith(4);
    expect(applySequenceDraftToTimeline).toHaveBeenCalledWith(
      timelineState.data.config,
      timelineState.data.registry,
      { clipType: 'section-hook', hold: 3, params: { title: 'Launch' } },
      expect.objectContaining({
        at: 2.5,
        mode: 'insert',
        selectedClipId: 'clip-1',
        selectedClipIds: ['clip-1', 'clip-2'],
        selectedTrackId: 'V1',
      }),
    );
    expect(opsState.applyEdit).toHaveBeenNthCalledWith(2, {
      type: 'config',
      resolvedConfig: {
        ...timelineState.data.config,
        clips: [{ id: 'clip-sequence', track: 'V1', at: 2.5, clipType: 'section-hook', hold: 3, params: { title: 'Launch' } }],
      },
    }, {
      selectedClipId: 'clip-sequence',
      selectedTrackId: 'V1',
      semantic: true,
    });
  });
});
