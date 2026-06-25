// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useEffect, type ReactNode } from 'react';
import type {
  ProposalRuntime,
  TimelineProposal,
  TimelineReader,
  TimelineSnapshot,
  TimelineOps,
} from '@/sdk/index';
import type {
  TimelineDiff,
  TimelinePatch,
  TimelinePreviewResult,
} from '@/sdk/video/timeline/patch.ts';
import type { ProposalImportDiagnosticsState } from '@/tools/video-editor/hooks/timelineStore';
import type { VideoEditorRenderContext } from '@/tools/video-editor/runtime/extensionSurface';

type SlotRendererFn = (context: VideoEditorRenderContext) => ReactNode;

let mockProposalRuntime: ProposalRuntime | null = null;
let mockProposalImportDiagnostics: ProposalImportDiagnosticsState | null = null;
const mockSetProposalImportDiagnostics = vi.fn((diagnostics: ProposalImportDiagnosticsState | null) => {
  mockProposalImportDiagnostics = diagnostics;
});
const mockInvoke = vi.fn();
let mockTimelineOps: TimelineOps;
let mockReader: TimelineReader;

const mockStartRender = vi.fn();
let mockSlotRenderers: Partial<Record<string, SlotRendererFn>> = {};
let mockExportExtensions: any = {
  slots: {},
  dialogHost: { dialogs: [] },
  registry: { panels: [], inspectorSections: [] },
  outputFormats: [],
};
let mockRuntimeContext: any = null;

vi.mock('@/tools/video-editor/hooks/timelineStore.ts', () => ({
  useTimelineEditorData: () => ({
    dataRef: { current: null },
    data: null,
    selectedClipIds: new Set<string>(),
    selectedTrackId: null,
    resolvedConfig: null,
    deviceClass: 'desktop' as const,
    precisionEnabled: false,
    interactionMode: 'browse' as const,
    gestureOwner: null,
    inspectorTarget: { kind: 'timeline' as const },
  }),
  useTimelineEditorOps: () => ({
    applyEdit: vi.fn(),
    handleDeleteClips: vi.fn(),
    moveSelectedClipsToTrack: vi.fn(),
    handleToggleMuteClips: vi.fn(),
    handleSplitSelectedClip: vi.fn(),
    clearSelection: vi.fn(),
    setInspectorTarget: vi.fn(),
    setContextTarget: vi.fn(),
    setPrecisionEnabled: vi.fn(),
    setInteractionMode: vi.fn(),
  }),
  useTimelineChromeContext: () => ({
    saveStatus: 'saved' as const,
    isConflictExhausted: false,
    retrySaveAfterConflict: vi.fn(),
    reloadFromServer: vi.fn(),
    undo: vi.fn(),
    redo: vi.fn(),
    canUndo: false,
    canRedo: false,
    checkpoints: [],
    jumpToCheckpoint: vi.fn(),
    createManualCheckpoint: vi.fn(),
    timelineName: 'Test Timeline',
    setScaleWidth: vi.fn(),
    startRender: mockStartRender,
    renderStatus: 'idle' as const,
    renderProgress: null,
    renderResultUrl: null,
    renderResultFilename: null,
    renderDirty: false,
  }),
  useTimelinePlaybackContext: () => ({
    currentTime: 0,
    previewRef: { current: { togglePlayPause: vi.fn(), seek: vi.fn() } },
    formatTime: (t: number) => `${t.toFixed(1)}s`,
  }),
  useProposalRuntimeFromStoreSafe: () => mockProposalRuntime,
  useProposalImportDiagnosticsFromStoreSafe: () => mockProposalImportDiagnostics,
  useTimelineStoreApiSafe: () => ({
    getState: () => ({
      setProposalImportDiagnostics: mockSetProposalImportDiagnostics,
    }),
  }),
}));

vi.mock('@/tools/video-editor/hooks/useKeyboardShortcuts.ts', () => ({
  useKeyboardShortcuts: vi.fn(),
}));

vi.mock('@/tools/video-editor/hooks/useTimelineRealtime.ts', () => ({
  useTimelineRealtime: () => ({
    isOpen: false,
    setOpen: vi.fn(),
    keepLocalChanges: vi.fn(),
    discardAndReload: vi.fn(),
  }),
}));

vi.mock('@/tools/video-editor/hooks/useEditorSync.ts', () => ({
  useEditorSync: () => ({
    syncState: 'idle' as const,
    syncError: null,
    isSyncAvailable: false,
    performSync: vi.fn(),
    lastSyncResult: null,
  }),
}));

vi.mock('@/tools/video-editor/hooks/usePerfDiagnostics.ts', () => ({
  useRenderDiagnostic: vi.fn(),
}));

vi.mock('@/tools/video-editor/components/CommandPalette/CommandPalette.tsx', () => ({
  CommandPalette: ({ open }: { open: boolean }) =>
    open ? <div data-testid="command-palette">Command Palette</div> : null,
}));

vi.mock('@/tools/video-editor/lib/perf-diagnostics.ts', () => ({
  bootDiagnostics: vi.fn(),
  MemoryPressureDetector: { start: vi.fn(), stop: vi.fn() },
}));

vi.mock('@/tools/video-editor/runtime/useVideoEditorRenderContext.ts', () => ({
  useVideoEditorSlotRenderers: () => mockSlotRenderers,
  useVideoEditorRenderContext: () => ({
    provider: {} as any,
    timelineId: 'test-timeline',
    timelineName: 'Test Timeline',
    userId: 'user-1',
    extensions: mockExportExtensions,
    data: {} as any,
    ops: {} as any,
    chrome: {} as any,
    playback: {} as any,
  }),
  useVideoEditorAssetPanels: () => [],
  useVideoEditorDialogDescriptors: () => [],
  useVideoEditorPanelRegistry: () => ({ panels: [], inspectorSections: [] }),
  useResolvedVideoEditorPanelRegistry: () => ({
    assetPanels: [],
    inspectorSections: { all: [], beforeDefault: [], afterDefault: [] },
  }),
  useVideoEditorInspectorSections: () => [],
}));

vi.mock('@/tools/video-editor/components/PreviewPanel/PreviewPanel.tsx', () => ({
  PreviewPanel: () => <div data-testid="preview-panel">Preview</div>,
  default: () => <div data-testid="preview-panel">Preview</div>,
}));

vi.mock('@/tools/video-editor/components/PreviewPanel/useVideoEditorPreviewSurface.tsx', () => ({
  useVideoEditorPreviewSurface: () => ({
    slotRef: { current: null },
    portal: null,
  }),
}));

vi.mock('@/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx', () => ({
  PropertiesPanel: () => <div data-testid="properties-panel">Properties</div>,
}));

vi.mock('@/tools/video-editor/components/PropertiesPanel/VideoEditorAssetPanelSurface.tsx', () => ({
  VideoEditorAssetPanelSurface: () => <div data-testid="asset-panel-surface">Asset Panel</div>,
}));

vi.mock('@/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx', () => ({
  SequenceCreatorPanel: () => null,
}));

vi.mock('@/tools/video-editor/components/ThemeChip.tsx', () => ({
  ThemeChip: () => null,
}));

vi.mock('@/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx', () => ({
  TimelineEditor: () => <div data-testid="timeline-editor">Timeline Editor</div>,
}));

vi.mock('@/tools/video-editor/lib/config-utils.ts', () => ({
  getTimelineDurationInFrames: () => 300,
  parseResolution: () => ({ width: 1920, height: 1080 }),
}));

vi.mock('@/tools/video-editor/lib/keyboard-delete.ts', () => ({
  buildKeyboardDeleteMutation: () => null,
}));

vi.mock('@/tools/video-editor/lib/mobile-interaction-model.ts', () => ({
  areTimelineInteractionTargetsEqual: () => true,
}));

vi.mock('@/shared/lib/typedEvents.ts', () => ({
  dispatchAppEvent: vi.fn(),
}));

vi.mock('@/shared/state/selectionStore.ts', () => ({
  editorReplaceTimelineSelection: vi.fn(),
}));

vi.mock('@/tools/video-editor/contexts/DataProviderContext.tsx', () => ({
  useOptionalVideoEditorRuntime: () => mockRuntimeContext,
  useVideoEditorRuntime: () => {
    if (!mockRuntimeContext) throw new Error('No runtime context');
    return mockRuntimeContext;
  },
  DataProviderContext: {
    Provider: ({ children }: any) => children,
  },
}));

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: () => ({
    functions: { invoke: mockInvoke },
    channel: vi.fn(),
    removeChannel: vi.fn(),
    from: vi.fn(),
    auth: { getUser: vi.fn() },
  }),
}));

import { TimelineEditorShellCore } from '@/tools/video-editor/components/TimelineEditorShellCore';
import { useSendMessage } from '@/tools/video-editor/hooks/useAgentSession';
import { createProposalRuntime } from '@/tools/video-editor/lib/proposal-runtime';

function mockPatch(overrides: Partial<TimelinePatch> = {}): TimelinePatch {
  return {
    version: 1,
    operations: [
      {
        op: 'clip.add',
        target: 'V1',
        payload: { track: 'V1', at: 0, clipType: 'video' },
      },
    ],
    source: 'ai-timeline-agent',
    ...overrides,
  };
}

function mockDiff(version = 8): TimelineDiff {
  return {
    version,
    entries: [
      {
        granularity: 'clip',
        kind: 'added',
        target: 'clip-generated',
        op: 'clip.add',
        after: { track: 'V1', at: 0, clipType: 'video' },
      },
    ],
    affectedObjectIds: ['clip-generated', 'V1'],
  };
}

function mockPreviewResult(): TimelinePreviewResult {
  return {
    diff: mockDiff(7),
    fullyPreviewable: true,
    diagnostics: [],
  };
}

function makeReader(currentVersion = 7): TimelineReader {
  return {
    snapshot: vi.fn(() => ({
      currentVersion,
      config: {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [{ id: 'V1', kind: 'visual', label: 'Visual 1' }],
        clips: [],
      },
    } as unknown as TimelineSnapshot)),
  } as unknown as TimelineReader;
}

function makeTimelineOps(): TimelineOps {
  return {
    validate: vi.fn(() => ({ valid: true, diagnostics: [] })),
    preview: vi.fn(() => mockPreviewResult()),
    apply: vi.fn(() => mockDiff()),
    checkpoint: vi.fn(() => 'checkpoint-1'),
    rollback: vi.fn(() => null),
    setAllTracksMuted: vi.fn(() => mockDiff()),
  };
}

function makeProposal(overrides: Partial<TimelineProposal> = {}): TimelineProposal {
  const now = Date.now();
  return {
    id: 'seeded-proposal-1',
    source: 'ai-timeline-agent',
    rationale: 'Seeded shell smoke proposal',
    state: 'pending',
    patch: mockPatch(),
    baseVersion: 7,
    previewable: true,
    previewDiff: mockDiff(7),
    createdAt: now - 1000,
    updatedAt: now,
    diagnostics: [],
    ...overrides,
  };
}

function seedRuntimeWithProposal(proposal: TimelineProposal): ProposalRuntime {
  const runtime = createProposalRuntime({
    timelineOps: mockTimelineOps,
    reader: mockReader,
  });
  const importableRuntime = runtime as ProposalRuntime & {
    importProposal(proposal: TimelineProposal): 'imported' | 'duplicate' | 'rejected';
  };
  importableRuntime.importProposal(proposal);
  return runtime;
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  };
}

function SendMessageProbe({ onSettled }: { onSettled: () => void }) {
  const sendMessage = useSendMessage('session-1', 'timeline-1');

  useEffect(() => {
    void sendMessage.mutateAsync({ message: 'Add the proposed clip' }).finally(onSettled);
  }, []);

  return <div data-testid="send-message-probe" data-status={sendMessage.status} />;
}

describe('useSendMessage proposal vertical shell harness', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSlotRenderers = {};
    mockExportExtensions = {
      slots: {},
      dialogHost: { dialogs: [] },
      registry: { panels: [], inspectorSections: [] },
      outputFormats: [],
    };
    mockRuntimeContext = null;
    mockTimelineOps = makeTimelineOps();
    mockReader = makeReader(7);
    mockProposalRuntime = null;
    mockProposalImportDiagnostics = null;
    mockInvoke.mockResolvedValue({
      data: {
        session_id: 'session-1',
        status: 'waiting_user',
        turns_added: 1,
      },
      error: null,
    });
  });

  it('mounts the real shell-mounted ProposalPanel and renders seeded proposals and import diagnostics', () => {
    mockProposalRuntime = seedRuntimeWithProposal(makeProposal());
    mockProposalImportDiagnostics = {
      imported: 1,
      skipped: 0,
      rejected: 1,
      diagnostics: [
        {
          severity: 'warning',
          code: 'proposal-import/smoke-diagnostic',
          message: 'Smoke diagnostic is visible from the shell store.',
          proposalIndex: 0,
          proposalId: 'seeded-proposal-1',
        },
      ],
      timestamp: Date.now(),
    };

    render(<TimelineEditorShellCore timelineId="timeline-1" />);

    expect(screen.getByRole('region', { name: 'Proposal panel' })).toBeDefined();
    expect(screen.getByText('Seeded shell smoke proposal')).toBeDefined();
    expect(screen.getByText('ai-timeline-agent')).toBeDefined();
    expect(screen.getByText('[proposal-import/smoke-diagnostic]')).toBeDefined();
    expect(screen.getByText('Smoke diagnostic is visible from the shell store.')).toBeDefined();
  });

  it('imports edge proposals without applying them until the shell-mounted ProposalPanel accepts', async () => {
    const knownPatch = mockPatch({
      operations: [
        {
          op: 'clip.add',
          target: 'V1',
          payload: { track: 'V1', at: 3.5, clipType: 'video', label: 'Accepted from edge' },
        },
      ],
    });
    const edgeProposal = {
      id: 'edge-proposal-accept-1',
      source: 'ai-timeline-agent',
      rationale: 'Add an edge-generated clip for review',
      state: 'pending',
      patch: knownPatch,
      baseVersion: 7,
    };
    mockInvoke.mockResolvedValueOnce({
      data: {
        session_id: 'session-1',
        status: 'waiting_user',
        turns_added: 1,
        proposals: [edgeProposal],
        mutation_applied: false,
      },
      error: null,
    });
    mockProposalRuntime = createProposalRuntime({
      timelineOps: mockTimelineOps,
      reader: mockReader,
    });
    const wrapper = createWrapper();
    const onSettled = vi.fn();

    const { rerender } = render(
      <SendMessageProbe onSettled={onSettled} />,
      { wrapper },
    );

    await waitFor(() => expect(onSettled).toHaveBeenCalledTimes(1));
    expect(mockTimelineOps.apply).not.toHaveBeenCalled();
    expect(mockSetProposalImportDiagnostics).toHaveBeenCalledWith(expect.objectContaining({
      imported: 1,
      skipped: 0,
      rejected: 0,
      diagnostics: [],
    }));
    expect(mockProposalRuntime.list()).toEqual([
      expect.objectContaining({
        id: edgeProposal.id,
        source: edgeProposal.source,
        rationale: edgeProposal.rationale,
        baseVersion: 7,
        patch: knownPatch,
        state: 'pending',
      }),
    ]);

    rerender(<TimelineEditorShellCore timelineId="timeline-1" />);

    expect(screen.getByRole('region', { name: 'Proposal panel' })).toBeDefined();
    expect(screen.getByText(edgeProposal.rationale)).toBeDefined();
    expect(screen.getByText(edgeProposal.source)).toBeDefined();
    fireEvent.click(screen.getByRole('button', {
      name: `Proposal from ${edgeProposal.source}: ${edgeProposal.rationale} — Pending`,
    }));
    expect(screen.getByText('clip.add')).toBeDefined();
    expect(screen.getByText(/label=Accepted from edge/)).toBeDefined();
    expect(mockTimelineOps.apply).not.toHaveBeenCalled();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', {
        name: `Accept proposal from ${edgeProposal.source}`,
      }));
    });

    expect(mockTimelineOps.apply).toHaveBeenCalledTimes(1);
    expect(mockTimelineOps.apply).toHaveBeenCalledWith(knownPatch);
  });

  it('rejects imported edge proposals through the shell-mounted ProposalPanel without applying mutations', async () => {
    const knownPatch = mockPatch({
      operations: [
        {
          op: 'clip.add',
          target: 'V1',
          payload: { track: 'V1', at: 6, clipType: 'video', label: 'Rejected from edge' },
        },
      ],
    });
    const edgeProposal = {
      id: 'edge-proposal-reject-1',
      source: 'ai-timeline-agent',
      rationale: 'Reject this edge-generated clip after review',
      state: 'pending',
      patch: knownPatch,
      baseVersion: 7,
    };
    mockInvoke.mockResolvedValueOnce({
      data: {
        session_id: 'session-1',
        status: 'waiting_user',
        turns_added: 1,
        proposals: [edgeProposal],
        mutation_applied: false,
      },
      error: null,
    });
    mockProposalRuntime = createProposalRuntime({
      timelineOps: mockTimelineOps,
      reader: mockReader,
    });
    const wrapper = createWrapper();
    const onSettled = vi.fn();

    const { rerender } = render(
      <SendMessageProbe onSettled={onSettled} />,
      { wrapper },
    );

    await waitFor(() => expect(onSettled).toHaveBeenCalledTimes(1));
    expect(mockTimelineOps.apply).not.toHaveBeenCalled();

    rerender(<TimelineEditorShellCore timelineId="timeline-1" />);

    fireEvent.click(screen.getByRole('button', {
      name: `Proposal from ${edgeProposal.source}: ${edgeProposal.rationale} — Pending`,
    }));
    expect(screen.getByText(edgeProposal.rationale)).toBeDefined();
    expect(screen.getByText(/label=Rejected from edge/)).toBeDefined();
    expect(mockTimelineOps.apply).not.toHaveBeenCalled();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', {
        name: `Reject proposal from ${edgeProposal.source}`,
      }));
    });

    expect(mockTimelineOps.apply).not.toHaveBeenCalled();
    expect(mockProposalRuntime.list()).toEqual([
      expect.objectContaining({
        id: edgeProposal.id,
        state: 'rejected',
      }),
    ]);
    expect(screen.queryByRole('button', {
      name: `Proposal from ${edgeProposal.source}: ${edgeProposal.rationale} — Pending`,
    })).toBeNull();
    expect(screen.queryByRole('button', {
      name: `Accept proposal from ${edgeProposal.source}`,
    })).toBeNull();
    expect(screen.queryByRole('button', {
      name: `Reject proposal from ${edgeProposal.source}`,
    })).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Show rejected proposals' }));

    expect(screen.getByRole('button', {
      name: `Proposal from ${edgeProposal.source}: ${edgeProposal.rationale} — Rejected`,
    })).toBeDefined();
    expect(screen.queryByRole('button', {
      name: `Accept proposal from ${edgeProposal.source}`,
    })).toBeNull();
    expect(screen.queryByRole('button', {
      name: `Reject proposal from ${edgeProposal.source}`,
    })).toBeNull();
  });

  it('stores malformed edge proposal diagnostics and shows them in the shell-mounted ProposalPanel', async () => {
    const malformedProposal = {
      id: 'edge-proposal-malformed-1',
      source: 'ai-timeline-agent',
      rationale: 'This malformed proposal should be diagnostically rejected',
      state: 'pending',
      patch: {
        version: 1,
        operations: [
          {
            op: 'clip.add',
            target: '',
            payload: { track: 'V1', at: 9, clipType: 'video' },
          },
        ],
        source: 'ai-timeline-agent',
      },
      baseVersion: 7,
    };
    mockInvoke.mockResolvedValueOnce({
      data: {
        session_id: 'session-1',
        status: 'waiting_user',
        turns_added: 1,
        proposals: [malformedProposal],
        mutation_applied: false,
      },
      error: null,
    });
    mockProposalRuntime = createProposalRuntime({
      timelineOps: mockTimelineOps,
      reader: mockReader,
    });
    const wrapper = createWrapper();
    const onSettled = vi.fn();

    const { rerender } = render(
      <SendMessageProbe onSettled={onSettled} />,
      { wrapper },
    );

    await waitFor(() => expect(onSettled).toHaveBeenCalledTimes(1));
    expect(mockTimelineOps.apply).not.toHaveBeenCalled();
    expect(mockProposalRuntime.list()).toEqual([]);

    expect(mockSetProposalImportDiagnostics).toHaveBeenCalledWith(expect.objectContaining({
      imported: 0,
      skipped: 0,
      rejected: 1,
      diagnostics: expect.arrayContaining([
        expect.objectContaining({
          severity: 'error',
          code: 'proposal-import/invalid-patch',
          message: 'operations[0] "clip.add" requires a non-empty target',
          proposalIndex: 0,
          proposalId: malformedProposal.id,
          detail: expect.objectContaining({
            timelinePatchCode: 'timeline-patch/missing-target',
          }),
        }),
      ]),
    }));
    expect(mockProposalImportDiagnostics).toEqual(expect.objectContaining({
      rejected: 1,
      diagnostics: expect.arrayContaining([
        expect.objectContaining({
          code: 'proposal-import/invalid-patch',
          proposalId: malformedProposal.id,
          detail: expect.objectContaining({
            timelinePatchCode: 'timeline-patch/missing-target',
          }),
        }),
      ]),
    }));

    rerender(<TimelineEditorShellCore timelineId="timeline-1" />);

    expect(screen.getByRole('region', { name: 'Proposal panel' })).toBeDefined();
    expect(screen.getByRole('status', { name: 'Proposal import diagnostics' })).toBeDefined();
    expect(screen.getByText('1 rejected')).toBeDefined();
    expect(screen.getByText('operations[0] "clip.add" requires a non-empty target')).toBeDefined();
    expect(screen.getByText('[proposal-import/invalid-patch]')).toBeDefined();
    expect(screen.getByText('proposal #0')).toBeDefined();
  });
});
