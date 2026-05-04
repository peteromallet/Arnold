// @vitest-environment jsdom
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TasksPane } from './TasksPane';

const useLocationMock = vi.fn();
const useAgentChatActionsMock = vi.fn();
const usePanesStoreMock = vi.fn();
const openPaneMock = vi.fn();
const toggleLockMock = vi.fn();
const handlePaneEnterMock = vi.fn();
const handlePaneLeaveMock = vi.fn();
const closePaneMock = vi.fn();
const handleFilterChangeMock = vi.fn();
const handleTaskTypeChangeMock = vi.fn();
const handlePageChangeMock = vi.fn();
const handleCancelAllPendingMock = vi.fn();
const setProjectScopeMock = vi.fn();
const setMobileActiveTaskIdMock = vi.fn();
const setIsTasksPaneOpenProgrammaticMock = vi.fn();
const setIsTasksPaneLockedMock = vi.fn();
const setActiveTaskIdMock = vi.fn();
const setLightboxSelectedShotIdMock = vi.fn();
const handleOpenImageLightboxMock = vi.fn();
const handleOpenVideoLightboxMock = vi.fn();
const handleCloseLightboxMock = vi.fn();
const handleOpenExternalGenerationMock = vi.fn();
const handleAddToShotMock = vi.fn();
const handleAddToShotWithoutPositionMock = vi.fn();
const handleOptimisticPositionedMock = vi.fn();
const handleOptimisticUnpositionedMock = vi.fn();

let paneControlProps: any = null;

vi.mock('react-dom', async () => {
  const actual = await vi.importActual<typeof import('react-dom')>('react-dom');
  return {
    ...actual,
    createPortal: (node: React.ReactNode) => node,
  };
});

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useLocation: () => useLocationMock(),
  };
});

vi.mock('@/shared/lib/debug/debugRendering', () => ({
  useRenderLogger: vi.fn(),
}));

vi.mock('@/shared/dev/useRenderBudget', () => ({
  useRenderBudget: vi.fn(),
}));

vi.mock('@/shared/components/ui/contracts/cn', () => ({
  cn: (...parts: Array<string | false | null | undefined>) => parts.filter(Boolean).join(' '),
}));

vi.mock('@/shared/components/ui/button', () => ({
  Button: ({ children, ...props }: any) => <button type="button" {...props}>{children}</button>,
}));

vi.mock('@/shared/components/ui/tooltip', () => ({
  Tooltip: ({ children }: any) => <>{children}</>,
  TooltipContent: ({ children }: any) => <>{children}</>,
  TooltipTrigger: ({ children }: any) => <>{children}</>,
}));

vi.mock('@/shared/components/PaneControlTab', () => ({
  PaneControlTab: (props: any) => {
    paneControlProps = props;
    const splitButton = props.actions?.splitButton;
    return (
      <div data-testid="pane-control-tab">
        <span data-testid="split-available">{String(Boolean(splitButton))}</span>
        {splitButton ? (
          <button type="button" onClick={splitButton.primary.onClick}>
            {splitButton.primary.ariaLabel}
          </button>
        ) : null}
      </div>
    );
  },
}));

vi.mock('@/shared/contexts/AgentChatContext', () => ({
  useAgentChatActions: (...args: unknown[]) => useAgentChatActionsMock(...args),
}));

vi.mock('@/tools/video-editor/components/AgentChat', () => ({
  AgentChatPanel: () => <div data-testid="agent-chat-panel" />,
}));

vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProjectSelectionContext: () => ({ selectedProjectId: 'project-1' }),
  useProjectCrudContext: () => ({ projects: [{ id: 'project-1', name: 'Project 1', createdAt: '2026-05-01T00:00:00.000Z' }] }),
}));

vi.mock('@/shared/contexts/IncomingTasksContext', () => ({
  useIncomingTasks: () => ({ incomingTasks: [], cancelAllIncoming: vi.fn() }),
}));

vi.mock('@/shared/components/ProcessingWarnings', () => ({
  TasksPaneProcessingWarning: () => <div data-testid="processing-warning" />,
}));

vi.mock('@/shared/hooks/layout/useBottomOffset', () => ({
  useBottomOffset: () => 0,
}));

vi.mock('@/domains/media-lightbox/MediaLightbox', () => ({
  MediaLightbox: () => <div data-testid="media-lightbox" />,
}));

vi.mock('@/shared/hooks/shots', () => ({
  useListShots: () => ({ data: [] }),
}));

vi.mock('@/shared/hooks/shots/useLastAffectedShot', () => ({
  useLastAffectedShot: () => ({ lastAffectedShotId: null }),
}));

vi.mock('@/shared/state/selectionStore', () => ({
  useCurrentShot: () => ({ currentShotId: null }),
}));

vi.mock('@/shared/components/panes/usePaneInteractionLifecycle', () => ({
  usePaneInteractionLifecycle: () => ({ isPointerEventsEnabled: true }),
}));

vi.mock('@/shared/components/panes/PaneBackdrop', () => ({
  PaneBackdrop: () => null,
}));

vi.mock('@/shared/components/ui/select', () => ({
  Select: ({ children }: any) => <div>{children}</div>,
  SelectContent: ({ children }: any) => <div>{children}</div>,
  SelectItem: ({ children }: any) => <div>{children}</div>,
  SelectTrigger: ({ children }: any) => <button type="button">{children}</button>,
  SelectValue: ({ placeholder }: any) => <span>{placeholder ?? 'value'}</span>,
  SelectSeparator: () => <div data-testid="select-separator" />,
}));

vi.mock('./TaskList', () => ({
  TaskList: () => <div data-testid="task-list" />,
}));

vi.mock('./components/PaginationControls', () => ({
  PaginationControls: () => <div data-testid="pagination-controls" />,
}));

vi.mock('./hooks/useTasksLightbox', () => ({
  useTasksLightbox: () => ({
    lightboxData: null,
    lightboxSelectedShotId: null,
    setLightboxSelectedShotId: setLightboxSelectedShotIdMock,
    taskDetailsData: null,
    lightboxProps: null,
    handleOpenImageLightbox: handleOpenImageLightboxMock,
    handleOpenVideoLightbox: handleOpenVideoLightboxMock,
    handleCloseLightbox: handleCloseLightboxMock,
    handleOpenExternalGeneration: handleOpenExternalGenerationMock,
  }),
}));

vi.mock('./hooks/useShotActions', () => ({
  useShotActions: () => ({
    optimisticPositionedIds: [],
    optimisticUnpositionedIds: [],
    handleAddToShot: handleAddToShotMock,
    handleAddToShotWithoutPosition: handleAddToShotWithoutPositionMock,
    handleOptimisticPositioned: handleOptimisticPositionedMock,
    handleOptimisticUnpositioned: handleOptimisticUnpositionedMock,
  }),
}));

vi.mock('./hooks/useTasksPaneController', () => ({
  useTasksPaneController: () => ({
    selectedFilter: 'Processing',
    selectedTaskType: null,
    projectScope: 'current',
    currentPage: 1,
    mobileActiveTaskId: null,
    setProjectScope: setProjectScopeMock,
    setMobileActiveTaskId: setMobileActiveTaskIdMock,
    handleFilterChange: handleFilterChangeMock,
    handleTaskTypeChange: handleTaskTypeChangeMock,
    handlePageChange: handlePageChangeMock,
    handleCancelAllPending: handleCancelAllPendingMock,
    isCancelAllPending: false,
    paginatedData: [],
    isPaginatedLoading: false,
    displayStatusCounts: {
      recentSuccesses: 0,
      recentFailures: 0,
    },
    isStatusCountsDegraded: false,
    failedStatusQueries: 0,
    taskTypeOptions: [],
    totalTasks: 0,
    totalPages: 1,
    cancellableTaskCount: 2,
    isAllProjectsMode: false,
    projectNameMap: {},
  }),
}));

vi.mock('./hooks/useTasksPaneSlidingPane', () => ({
  useTasksPaneSlidingPane: () => ({
    isLocked: false,
    isOpen: true,
    toggleLock: toggleLockMock,
    openPane: openPaneMock,
    paneProps: {},
    transformClass: '',
    handlePaneEnter: handlePaneEnterMock,
    handlePaneLeave: handlePaneLeaveMock,
    showBackdrop: false,
    closePane: closePaneMock,
  }),
}));

vi.mock('@/shared/state/panesStore', () => ({
  usePanesStore: (selector: (state: any) => unknown) => selector(usePanesStoreMock()),
}));

function renderTasksPane() {
  return render(<TasksPane onOpenSettings={vi.fn()} />);
}

describe('TasksPane', () => {
  beforeEach(() => {
    paneControlProps = null;
    localStorage.clear();
    useLocationMock.mockReset();
    useAgentChatActionsMock.mockReset();
    openPaneMock.mockReset();
    toggleLockMock.mockReset();
    handlePaneEnterMock.mockReset();
    handlePaneLeaveMock.mockReset();
    closePaneMock.mockReset();
    handleFilterChangeMock.mockReset();
    handleTaskTypeChangeMock.mockReset();
    handlePageChangeMock.mockReset();
    handleCancelAllPendingMock.mockReset();
    setProjectScopeMock.mockReset();
    setMobileActiveTaskIdMock.mockReset();
    setIsTasksPaneOpenProgrammaticMock.mockReset();
    setIsTasksPaneLockedMock.mockReset();
    setActiveTaskIdMock.mockReset();
    setLightboxSelectedShotIdMock.mockReset();
    handleOpenImageLightboxMock.mockReset();
    handleOpenVideoLightboxMock.mockReset();
    handleCloseLightboxMock.mockReset();
    handleOpenExternalGenerationMock.mockReset();
    handleAddToShotMock.mockReset();
    handleAddToShotWithoutPositionMock.mockReset();
    handleOptimisticPositionedMock.mockReset();
    handleOptimisticUnpositionedMock.mockReset();
    useLocationMock.mockReturnValue({ pathname: '/tools/video-editor' });
    usePanesStoreMock.mockReturnValue({
      isTasksPaneLocked: false,
      setIsTasksPaneLocked: setIsTasksPaneLockedMock,
      tasksPaneWidth: 360,
      activeTaskId: null,
      setActiveTaskId: setActiveTaskIdMock,
      isTasksPaneOpen: true,
      setIsTasksPaneOpen: setIsTasksPaneOpenProgrammaticMock,
    });
    vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    }));
  });

  it('keeps the split button hidden until AgentChatPanel registers actions', () => {
    useAgentChatActionsMock.mockReturnValue(null);

    renderTasksPane();

    expect(screen.getByTestId('split-available')).toHaveTextContent('false');
    expect(screen.queryByRole('button', { name: 'Open message composer' })).not.toBeInTheDocument();
    expect(screen.getByTestId('agent-chat-panel')).toBeInTheDocument();
  });

  it('marks engaged, opens the pane, and focuses the composer once AgentChat actions are registered', () => {
    const callOrder: string[] = [];
    const markEngaged = vi.fn(() => {
      callOrder.push('mark');
    });
    const focusComposer = vi.fn(() => {
      callOrder.push('focus');
    });
    const toggleRecording = vi.fn();

    openPaneMock.mockImplementation(() => {
      callOrder.push('open');
    });
    useAgentChatActionsMock.mockReturnValue({
      toggleRecording,
      focusComposer,
      markEngaged,
      isRecording: false,
      isProcessing: false,
    });

    renderTasksPane();

    fireEvent.click(screen.getByRole('button', { name: 'Open message composer' }));

    expect(markEngaged).toHaveBeenCalledTimes(1);
    expect(openPaneMock).toHaveBeenCalledTimes(1);
    expect(globalThis.requestAnimationFrame).toHaveBeenCalledTimes(1);
    expect(focusComposer).toHaveBeenCalledTimes(1);
    expect(toggleRecording).not.toHaveBeenCalled();
    expect(callOrder).toEqual(['mark', 'open', 'focus']);
    expect(paneControlProps.actions.splitButton.primary.ariaLabel).toBe('Open message composer');
  });
});
