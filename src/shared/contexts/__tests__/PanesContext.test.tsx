// @vitest-environment jsdom
import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  usePaneLockPolicyState: vi.fn(),
  setIsGenerationsPaneLocked: vi.fn(),
  setIsEditorPaneLocked: vi.fn(),
  setIsShotsPaneLocked: vi.fn(),
  setIsTasksPaneLocked: vi.fn(),
  setIsGenerationsPaneOpen: vi.fn(),
  setIsEditorPaneOpen: vi.fn(),
  setIsTasksPaneOpen: vi.fn(),
  resetAllPaneLocks: vi.fn(),
}));

vi.mock('../usePaneLockPolicyState', () => ({
  usePaneLockPolicyState: (...args: unknown[]) => mocks.usePaneLockPolicyState(...args),
}));

vi.mock('@/shared/config/panes', () => ({
  PANE_CONFIG: {
    dimensions: {
      DEFAULT_HEIGHT: 300,
      DEFAULT_WIDTH: 280,
    },
  },
}));

import {
  __resetPanesStoreForTests,
  PanesStoreBootstrapBoundary,
  usePanesStore,
  usePanesStoreAvailability,
} from '@/shared/state/panesStore';

function PanesStoreConsumer() {
  const availability = usePanesStoreAvailability();
  const isGenerationsPaneLocked = usePanesStore((state) => state.isGenerationsPaneLocked);
  const isGenerationsPaneOpen = usePanesStore((state) => state.isGenerationsPaneOpen);
  const isEditorPaneLocked = usePanesStore((state) => state.isEditorPaneLocked);
  const isEditorPaneOpen = usePanesStore((state) => state.isEditorPaneOpen);
  const isShotsPaneLocked = usePanesStore((state) => state.isShotsPaneLocked);
  const isTasksPaneLocked = usePanesStore((state) => state.isTasksPaneLocked);
  const isTasksPaneOpen = usePanesStore((state) => state.isTasksPaneOpen);
  const generationsPaneHeight = usePanesStore((state) => state.generationsPaneHeight);
  const effectiveGenerationsPaneHeight = usePanesStore((state) => state.effectiveGenerationsPaneHeight);
  const editorPaneHeight = usePanesStore((state) => state.editorPaneHeight);
  const effectiveEditorPaneHeight = usePanesStore((state) => state.effectiveEditorPaneHeight);
  const activeTaskId = usePanesStore((state) => state.activeTaskId);
  const setIsGenerationsPaneLocked = usePanesStore((state) => state.setIsGenerationsPaneLocked);
  const setIsShotsPaneLocked = usePanesStore((state) => state.setIsShotsPaneLocked);
  const setIsTasksPaneOpen = usePanesStore((state) => state.setIsTasksPaneOpen);
  const setGenerationsPaneHeight = usePanesStore((state) => state.setGenerationsPaneHeight);
  const setActiveTaskId = usePanesStore((state) => state.setActiveTaskId);
  const resetAllPaneLocks = usePanesStore((state) => state.resetAllPaneLocks);

  return (
    <div>
      <span data-testid="bootstrapped">{String(availability.bootstrapped)}</span>
      <span data-testid="gensLocked">{String(isGenerationsPaneLocked)}</span>
      <span data-testid="gensOpen">{String(isGenerationsPaneOpen)}</span>
      <span data-testid="editorLocked">{String(isEditorPaneLocked)}</span>
      <span data-testid="editorOpen">{String(isEditorPaneOpen)}</span>
      <span data-testid="shotsLocked">{String(isShotsPaneLocked)}</span>
      <span data-testid="tasksLocked">{String(isTasksPaneLocked)}</span>
      <span data-testid="tasksOpen">{String(isTasksPaneOpen)}</span>
      <span data-testid="gensHeight">{generationsPaneHeight}</span>
      <span data-testid="effectiveGensHeight">{effectiveGenerationsPaneHeight}</span>
      <span data-testid="editorHeight">{editorPaneHeight}</span>
      <span data-testid="effectiveEditorHeight">{effectiveEditorPaneHeight}</span>
      <span data-testid="activeTaskId">{activeTaskId ?? 'null'}</span>
      <button type="button" data-testid="lock-gens" onClick={() => setIsGenerationsPaneLocked(true)}>
        lock gens
      </button>
      <button type="button" data-testid="lock-shots" onClick={() => setIsShotsPaneLocked(true)}>
        lock shots
      </button>
      <button type="button" data-testid="open-tasks" onClick={() => setIsTasksPaneOpen(true)}>
        open tasks
      </button>
      <button type="button" data-testid="resize-gens" onClick={() => setGenerationsPaneHeight(420)}>
        resize
      </button>
      <button type="button" data-testid="set-task" onClick={() => setActiveTaskId('task-1')}>
        set task
      </button>
      <button type="button" data-testid="reset-locks" onClick={() => resetAllPaneLocks()}>
        reset
      </button>
    </div>
  );
}

function renderWithBootstrapBoundary() {
  return render(
    <PanesStoreBootstrapBoundary>
      <PanesStoreConsumer />
    </PanesStoreBootstrapBoundary>,
  );
}

describe('panesStore bootstrap lifecycle', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerHeight', {
      configurable: true,
      writable: true,
      value: 600,
    });
    __resetPanesStoreForTests();
    vi.clearAllMocks();

    mocks.usePaneLockPolicyState.mockReturnValue({
      locks: {
        shots: false,
        tasks: false,
        gens: false,
        editor: false,
      },
      isGenerationsPaneOpenState: false,
      isEditorPaneOpenState: false,
      isTasksPaneOpenState: false,
      setIsGenerationsPaneLocked: mocks.setIsGenerationsPaneLocked,
      setIsEditorPaneLocked: mocks.setIsEditorPaneLocked,
      setIsShotsPaneLocked: mocks.setIsShotsPaneLocked,
      setIsTasksPaneLocked: mocks.setIsTasksPaneLocked,
      setIsGenerationsPaneOpen: mocks.setIsGenerationsPaneOpen,
      setIsEditorPaneOpen: mocks.setIsEditorPaneOpen,
      setIsTasksPaneOpen: mocks.setIsTasksPaneOpen,
      resetAllPaneLocks: mocks.resetAllPaneLocks,
    });
  });

  it('returns an unlocked default snapshot before bootstrap', () => {
    render(<PanesStoreConsumer />);

    expect(screen.getByTestId('bootstrapped')).toHaveTextContent('false');
    expect(screen.getByTestId('gensLocked')).toHaveTextContent('false');
    expect(screen.getByTestId('editorLocked')).toHaveTextContent('false');
    expect(screen.getByTestId('shotsLocked')).toHaveTextContent('false');
    expect(screen.getByTestId('tasksLocked')).toHaveTextContent('false');
    expect(screen.getByTestId('gensHeight')).toHaveTextContent('300');
    expect(screen.getByTestId('effectiveGensHeight')).toHaveTextContent('300');
    expect(screen.getByTestId('editorHeight')).toHaveTextContent('300');
    expect(screen.getByTestId('effectiveEditorHeight')).toHaveTextContent('300');
    expect(screen.getByTestId('activeTaskId')).toHaveTextContent('null');
  });

  it('hydrates the store from the bootstrap boundary and recomputes effective heights', () => {
    mocks.usePaneLockPolicyState.mockReturnValue({
      locks: {
        shots: true,
        tasks: false,
        gens: true,
        editor: false,
      },
      isGenerationsPaneOpenState: false,
      isEditorPaneOpenState: true,
      isTasksPaneOpenState: true,
      setIsGenerationsPaneLocked: mocks.setIsGenerationsPaneLocked,
      setIsEditorPaneLocked: mocks.setIsEditorPaneLocked,
      setIsShotsPaneLocked: mocks.setIsShotsPaneLocked,
      setIsTasksPaneLocked: mocks.setIsTasksPaneLocked,
      setIsGenerationsPaneOpen: mocks.setIsGenerationsPaneOpen,
      setIsEditorPaneOpen: mocks.setIsEditorPaneOpen,
      setIsTasksPaneOpen: mocks.setIsTasksPaneOpen,
      resetAllPaneLocks: mocks.resetAllPaneLocks,
    });

    renderWithBootstrapBoundary();

    expect(screen.getByTestId('bootstrapped')).toHaveTextContent('true');
    expect(screen.getByTestId('gensLocked')).toHaveTextContent('true');
    expect(screen.getByTestId('editorOpen')).toHaveTextContent('true');
    expect(screen.getByTestId('shotsLocked')).toHaveTextContent('true');
    expect(screen.getByTestId('tasksOpen')).toHaveTextContent('true');
    expect(screen.getByTestId('effectiveEditorHeight')).toHaveTextContent('300');
    expect(screen.getByTestId('effectiveGensHeight')).toHaveTextContent('300');
  });

  it('delegates runtime-backed mutations through the active bootstrap owner', () => {
    renderWithBootstrapBoundary();

    fireEvent.click(screen.getByTestId('lock-gens'));
    fireEvent.click(screen.getByTestId('lock-shots'));
    fireEvent.click(screen.getByTestId('open-tasks'));
    fireEvent.click(screen.getByTestId('reset-locks'));

    expect(mocks.setIsGenerationsPaneLocked).toHaveBeenCalledWith(true);
    expect(mocks.setIsShotsPaneLocked).toHaveBeenCalledWith(true);
    expect(mocks.setIsTasksPaneOpen).toHaveBeenCalledWith(true);
    expect(mocks.resetAllPaneLocks).toHaveBeenCalledTimes(1);
  });

  it('keeps local layout and active task state in the singleton store', () => {
    renderWithBootstrapBoundary();

    fireEvent.click(screen.getByTestId('resize-gens'));
    fireEvent.click(screen.getByTestId('set-task'));

    expect(screen.getByTestId('gensHeight')).toHaveTextContent('420');
    expect(screen.getByTestId('effectiveGensHeight')).toHaveTextContent('420');
    expect(screen.getByTestId('effectiveEditorHeight')).toHaveTextContent('300');
    expect(screen.getByTestId('activeTaskId')).toHaveTextContent('task-1');
  });

  it('clears the bootstrap snapshot on unmount and reset helper calls', () => {
    const view = renderWithBootstrapBoundary();

    fireEvent.click(screen.getByTestId('set-task'));
    expect(screen.getByTestId('bootstrapped')).toHaveTextContent('true');
    expect(screen.getByTestId('activeTaskId')).toHaveTextContent('task-1');

    view.unmount();

    render(<PanesStoreConsumer />);
    expect(screen.getByTestId('bootstrapped')).toHaveTextContent('false');
    expect(screen.getByTestId('activeTaskId')).toHaveTextContent('null');

    act(() => {
      __resetPanesStoreForTests();
    });

    expect(screen.getByTestId('bootstrapped')).toHaveTextContent('false');
    expect(screen.getByTestId('gensHeight')).toHaveTextContent('300');
  });
});
