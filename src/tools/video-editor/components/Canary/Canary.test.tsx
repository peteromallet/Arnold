// @vitest-environment jsdom
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { CodePanelCanary } from '@/tools/video-editor/components/Canary/CodePanelCanary';
import { WritingPanelCanary } from '@/tools/video-editor/components/Canary/WritingPanelCanary';
import { StagePanelCanary } from '@/tools/video-editor/components/Canary/StagePanelCanary';
import type { VideoEditorRenderContext } from '@/tools/video-editor/runtime/extensionSurface';

// ---------------------------------------------------------------------------
// Minimal render context for canary tests
// ---------------------------------------------------------------------------

function mockContext(overrides?: Partial<VideoEditorRenderContext>): VideoEditorRenderContext {
  return {
    timelineId: 'test-timeline-123',
    timelineName: 'Test Timeline',
    userId: 'user-abc-12345678',
    provider: {} as VideoEditorRenderContext['provider'],
    data: {
      dataRef: { current: null },
      data: null,
      selectedClipIds: new Set(),
      selectedTrackId: null,
      resolvedConfig: null,
      deviceClass: 'desktop' as const,
      precisionEnabled: false,
      interactionMode: 'browse' as const,
      gestureOwner: null,
      inspectorTarget: { kind: 'timeline' as const },
    },
    ops: {} as VideoEditorRenderContext['ops'],
    chrome: {
      saveStatus: 'dirty' as const,
      isConflictExhausted: false,
      retrySaveAfterConflict: async () => {},
      reloadFromServer: async () => {},
      undo: () => {},
      redo: () => {},
      canUndo: false,
      canRedo: false,
      checkpoints: [],
      jumpToCheckpoint: () => {},
      createManualCheckpoint: () => {},
      timelineName: 'Test Timeline',
      setScaleWidth: () => {},
      startRender: async () => {},
      renderStatus: 'idle' as const,
      renderProgress: null,
      renderResultUrl: null,
      renderResultFilename: null,
      renderDirty: false,
    },
    playback: {
      currentTime: 0,
      previewRef: { current: null },
      formatTime: (t: number) => `${t.toFixed(1)}s`,
    },
    extensions: {
      slots: {},
      dialogHost: { dialogs: [] },
      registry: { panels: [], inspectorSections: [] },
      overlays: [],
    },
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// CodePanelCanary
// ---------------------------------------------------------------------------

describe('CodePanelCanary', () => {
  it('renders with the canary data attribute', () => {
    render(<CodePanelCanary context={mockContext()} />);
    expect(
      screen.getByText(/Code panel canary/i),
    ).toBeDefined();
  });

  it('displays the timeline name', () => {
    render(<CodePanelCanary context={mockContext()} />);
    expect(screen.getByText('Test Timeline')).toBeDefined();
  });

  it('displays save status', () => {
    render(<CodePanelCanary context={mockContext()} />);
    expect(screen.getByText(/dirty/)).toBeDefined();
  });

  it('shows a diagnostic banner with code and message', () => {
    render(<CodePanelCanary context={mockContext()} />);
    expect(screen.getByText('canary/syntax-warn')).toBeDefined();
    expect(
      screen.getByText(/Identifier 'name' used before its declaration/),
    ).toBeDefined();
  });

  it('shows the diagnostic source range', () => {
    render(<CodePanelCanary context={mockContext()} />);
    expect(screen.getByText(/L7:5–9/)).toBeDefined();
  });

  it('renders source lines with line numbers', () => {
    render(<CodePanelCanary context={mockContext()} />);
    // Line numbers 1-11 should be present
    for (let i = 1; i <= 11; i++) {
      expect(screen.getByText(String(i))).toBeDefined();
    }
  });

  it('highlights the marker span on the diagnostic line', () => {
    render(<CodePanelCanary context={mockContext()} />);
    const marker = document.querySelector(
      '[data-video-editor-canary-marker="true"]',
    );
    expect(marker).not.toBeNull();
    expect(marker!.textContent).toBe('name');
  });

  it('shows the M4 canary legend', () => {
    render(<CodePanelCanary context={mockContext()} />);
    expect(screen.getByText(/M4/)).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// WritingPanelCanary
// ---------------------------------------------------------------------------

describe('WritingPanelCanary', () => {
  it('renders with the canary data attribute', () => {
    render(<WritingPanelCanary context={mockContext()} />);
    expect(screen.getByText(/Writing panel canary/i)).toBeDefined();
  });

  it('shows source identity section', () => {
    render(<WritingPanelCanary context={mockContext()} />);
    expect(screen.getByText('Document Draft v3')).toBeDefined();
    expect(screen.getByText(/1250 words/)).toBeDefined();
  });

  it('shows timeline and user identity', () => {
    render(<WritingPanelCanary context={mockContext()} />);
    expect(screen.getByText(/Test Timeline/)).toBeDefined();
    expect(screen.getByText(/user-abc…/)).toBeDefined();
  });

  it('shows dirty save posture', () => {
    const ctx = mockContext();
    render(<WritingPanelCanary context={ctx} />);
    expect(screen.getByText(/Dirty — unsaved changes/)).toBeDefined();
  });

  it('shows saved posture when clean', () => {
    const ctx = mockContext({
      chrome: {
        ...mockContext().chrome,
        saveStatus: 'saved' as const,
      },
    });
    render(<WritingPanelCanary context={ctx} />);
    expect(screen.getByText(/Clean — all changes saved/)).toBeDefined();
  });

  it('renders all four canary diagnostics', () => {
    render(<WritingPanelCanary context={mockContext()} />);
    expect(screen.getByText(/Diagnostics \(4\)/)).toBeDefined();
    expect(screen.getByText('writing/grammar-error')).toBeDefined();
    expect(screen.getByText('writing/style-passive')).toBeDefined();
    expect(screen.getByText('writing/word-count-target')).toBeDefined();
    expect(screen.getByText('writing/repetition')).toBeDefined();
  });

  it('shows source ranges for diagnostics that have them', () => {
    render(<WritingPanelCanary context={mockContext()} />);
    const rangeEls = document.querySelectorAll(
      '[data-video-editor-canary-source-range="true"]',
    );
    expect(rangeEls.length).toBe(3); // 3 of 4 diagnostics have source ranges
    expect(rangeEls[0].textContent).toContain('L12:10–18');
  });

  it('shows the M4 canary legend', () => {
    render(<WritingPanelCanary context={mockContext()} />);
    expect(screen.getByText(/M4/)).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// StagePanelCanary
// ---------------------------------------------------------------------------

describe('StagePanelCanary', () => {
  it('renders with the canary data attribute', () => {
    render(<StagePanelCanary context={mockContext()} />);
    expect(screen.getByText(/Stage panel canary/i)).toBeDefined();
  });

  it('starts in empty state', () => {
    render(<StagePanelCanary context={mockContext()} />);
    expect(screen.getByText(/Empty — no timeline bound/)).toBeDefined();
  });

  it('cycles through states on toggle click', () => {
    render(<StagePanelCanary context={mockContext()} />);

    const toggleBtn = screen.getByRole('button', {
      name: /Cycle stage state/,
    });

    // empty → error
    fireEvent.click(toggleBtn);
    expect(screen.getByText(/Error — render failure/)).toBeDefined();

    // error → disabled
    fireEvent.click(toggleBtn);
    expect(screen.getByText(/Disabled — stage not available/)).toBeDefined();

    // disabled → empty
    fireEvent.click(toggleBtn);
    expect(screen.getByText(/Empty — no timeline bound/)).toBeDefined();
  });

  it('shows coordinate vocabulary', () => {
    render(<StagePanelCanary context={mockContext()} />);
    expect(screen.getByText(/Coordinate vocabulary/)).toBeDefined();
    expect(screen.getByText(/\(0, 0\)/)).toBeDefined();
    expect(screen.getByText(/\(1, 1\)/)).toBeDefined();
    expect(screen.getByText('px')).toBeDefined();
  });

  it('shows containment metadata', () => {
    render(<StagePanelCanary context={mockContext()} />);
    expect(screen.getByText('Containment')).toBeDefined();
    const bounds = screen.getAllByText(/1920/);
    expect(bounds.length).toBeGreaterThanOrEqual(2); // bounds + viewport
    const yesEls = screen.getAllByText('Yes');
    expect(yesEls.length).toBeGreaterThanOrEqual(1);
  });

  it('shows gesture policy', () => {
    render(<StagePanelCanary context={mockContext()} />);
    expect(screen.getByText(/Gesture policy/)).toBeDefined();
    expect(screen.getByText(/No direct manipulation tooling/)).toBeDefined();
  });

  it('shows timeline binding metadata when not empty', () => {
    render(<StagePanelCanary context={mockContext()} />);

    // Start in empty state – no binding
    expect(screen.getByText(/No timeline bound/)).toBeDefined();

    // Click to error state – binding shows
    const toggleBtn = screen.getByRole('button', {
      name: /Cycle stage state/,
    });
    fireEvent.click(toggleBtn);

    expect(screen.getByText(/Test Timeline/)).toBeDefined();
    expect(screen.getByText(/0s – 300s/)).toBeDefined();
    expect(screen.getByText('30')).toBeDefined();
  });

  it('shows the M3 canary legend', () => {
    render(<StagePanelCanary context={mockContext()} />);
    expect(screen.getByText(/M3/)).toBeDefined();
  });
});
