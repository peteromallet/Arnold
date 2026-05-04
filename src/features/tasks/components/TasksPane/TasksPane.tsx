import React, { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useLocation } from 'react-router-dom';
import { shallow } from 'zustand/shallow';
import { useRenderLogger } from '@/shared/lib/debug/debugRendering';
import { TaskList } from './TaskList';
import { cn } from '@/shared/components/ui/contracts/cn';
import { Button } from '@/shared/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { ChevronDown, ChevronUp, Loader2, MessageSquareText, Mic, Square } from 'lucide-react';
import { PaneControlTab } from '@/shared/components/PaneControlTab';
import { useAgentChatActions } from '@/shared/contexts/AgentChatContext';
import { AgentChatPanel } from '@/tools/video-editor/components/AgentChat';
import { useProjectCrudContext, useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { useIncomingTasks } from '@/shared/contexts/IncomingTasksContext';
import { TasksPaneProcessingWarning } from '@/shared/components/ProcessingWarnings';
import { useBottomOffset } from '@/shared/hooks/layout/useBottomOffset';
import { MediaLightbox } from '@/domains/media-lightbox/MediaLightbox';
import { useListShots } from '@/shared/hooks/shots';
import { useLastAffectedShot } from '@/shared/hooks/shots/useLastAffectedShot';
import { useCurrentShot } from '@/shared/state/selectionStore';
import { usePaneInteractionLifecycle } from '@/shared/components/panes/usePaneInteractionLifecycle';
import { PaneBackdrop } from '@/shared/components/panes/PaneBackdrop';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, SelectSeparator } from '@/shared/components/ui/select';

// Import from new modules
import { STATUS_GROUPS, type FilterGroup } from './constants';
import { PaginationControls } from './components/PaginationControls';
import { useTasksLightbox } from './hooks/useTasksLightbox';
import { useShotActions } from './hooks/useShotActions';
import { useTasksPaneController } from './hooks/useTasksPaneController';
import { useTasksPaneSlidingPane } from './hooks/useTasksPaneSlidingPane';
import { useRenderBudget } from '@/shared/dev/useRenderBudget';
import { UI_Z_LAYERS } from '@/shared/lib/uiLayers';
import { usePanesStore } from '@/shared/state/panesStore';

interface TasksPaneProps {
  onOpenSettings: () => void;
}

const TasksPaneComponent: React.FC<TasksPaneProps> = ({ onOpenSettings }) => {
  useRenderBudget('TasksPane', 5);
  const {
    isTasksPaneLocked,
    setIsTasksPaneLocked,
    tasksPaneWidth,
    activeTaskId,
    setActiveTaskId,
    isTasksPaneOpenProgrammatic,
    setIsTasksPaneOpenProgrammatic,
  } = usePanesStore((state) => ({
    isTasksPaneLocked: state.isTasksPaneLocked,
    setIsTasksPaneLocked: state.setIsTasksPaneLocked,
    tasksPaneWidth: state.tasksPaneWidth,
    activeTaskId: state.activeTaskId,
    setActiveTaskId: state.setActiveTaskId,
    isTasksPaneOpenProgrammatic: state.isTasksPaneOpen,
    setIsTasksPaneOpenProgrammatic: state.setIsTasksPaneOpen,
  }), shallow);

  // Project context & task helpers
  const { selectedProjectId } = useProjectSelectionContext();
  const { projects } = useProjectCrudContext();

  // Shots data for lightbox
  const { data: shots } = useListShots(selectedProjectId);
  const { currentShotId } = useCurrentShot();
  const { lastAffectedShotId } = useLastAffectedShot();

  // Get incoming/placeholder tasks for count calculation + cancellation
  const { incomingTasks, cancelAllIncoming } = useIncomingTasks();

  const {
    selectedFilter,
    selectedTaskType,
    projectScope,
    currentPage,
    mobileActiveTaskId,
    setProjectScope,
    setMobileActiveTaskId,
    handleFilterChange,
    handleTaskTypeChange,
    handlePageChange,
    handleCancelAllPending,
    isCancelAllPending,
    paginatedData,
    isPaginatedLoading,
    displayStatusCounts,
    isStatusCountsDegraded,
    failedStatusQueries,
    taskTypeOptions,
    totalTasks,
    totalPages,
    cancellableTaskCount,
    isAllProjectsMode,
    projectNameMap,
  } = useTasksPaneController({
    selectedProjectId,
    projects,
    incomingTasks,
    cancelAllIncoming,
  });

  // Simplified shot options for MediaLightbox
  const simplifiedShotOptions = useMemo(() => shots?.map(s => ({ id: s.id, name: s.name })) || [], [shots]);

  // Use extracted lightbox hook
  const {
    lightboxData,
    lightboxSelectedShotId,
    setLightboxSelectedShotId,
    taskDetailsData,
    lightboxProps,
    handleOpenImageLightbox,
    handleOpenVideoLightbox,
    handleCloseLightbox,
    handleOpenExternalGeneration,
  } = useTasksLightbox({
    selectedProjectId,
    currentShotId,
    lastAffectedShotId,
    setActiveTaskId,
    setIsTasksPaneOpen: setIsTasksPaneOpenProgrammatic,
  });

  // Use extracted shot actions hook
  const {
    optimisticPositionedIds,
    optimisticUnpositionedIds,
    handleAddToShot,
    handleAddToShotWithoutPosition,
    handleOptimisticPositioned,
    handleOptimisticUnpositioned,
  } = useShotActions({
    lightboxSelectedShotId,
    currentShotId,
    lastAffectedShotId,
    selectedProjectId,
  });

  useRenderLogger('TasksPane', { cancellableCount: cancellableTaskCount });

  const { isLocked, isOpen, toggleLock, openPane, paneProps, transformClass, handlePaneEnter, handlePaneLeave, showBackdrop, closePane } = useTasksPaneSlidingPane({
    isTasksPaneLocked,
    setIsTasksPaneLocked,
    isTasksPaneOpenProgrammatic,
    setIsTasksPaneOpenProgrammatic,
  });

  const { isPointerEventsEnabled } = usePaneInteractionLifecycle({
    isOpen: Boolean(isOpen),
  });

  // Sprint 3 adapter boundary: AgentChatPanel remains app-owned in TasksPane
  // instead of moving into the editor shell. The core talks to chat through
  // registration bridges; this pane still owns when chat is mounted and how the
  // split-button affordance drives it on Reigh routes.
  // Agent chat lives inside the action pane only on tool routes (where a timeline
  // makes sense). On other routes the pane is task-only.
  const { pathname } = useLocation();
  const isToolRoute = pathname.startsWith('/tools') || pathname === '/shots' || pathname === '/art';
  // null until AgentChatPanel mounts and registers; the split button stays hidden
  // until then so it can't be clicked before its handlers exist.
  const agentChatActions = useAgentChatActions();
  const readyAgentChatActions = isToolRoute ? agentChatActions : null;

  // Expand state: which half (if any) is currently filling the entire pane.
  // null = 50/50 split. Resets to null when the pane closes so reopening always
  // starts in the default split layout.
  const [expandedHalf, setExpandedHalf] = useState<'tasks' | 'chat' | null>(null);
  useEffect(() => {
    if (!isOpen && !isLocked) {
      setExpandedHalf(null);
    }
  }, [isOpen, isLocked]);
  const showChatHalf = isToolRoute && expandedHalf !== 'tasks';
  const showTasksHalf = expandedHalf !== 'chat';

  // Which agent action was used most recently. Drives which control sits as
  // the primary in the pane-control split button — secondary appears on hover.
  // Persisted to localStorage so the preference survives close/reopen.
  const [lastAgentAction, setLastAgentAction] = useState<'message' | 'voice'>(() => {
    if (typeof window === 'undefined') return 'message';
    const stored = window.localStorage.getItem('agentChat:lastAction');
    return stored === 'voice' || stored === 'message' ? stored : 'message';
  });
  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem('agentChat:lastAction', lastAgentAction);
  }, [lastAgentAction]);

  return (
    <>
      {/* Backdrop overlay for mobile - z-index just below TasksPane content (100016) */}
      <PaneBackdrop show={showBackdrop} zIndex={100000} onClose={closePane} />
      
      <PaneControlTab
        position={{ side: "right", paneDimension: tasksPaneWidth, bottomOffset: useBottomOffset() }}
        state={{ isLocked, isOpen: !!isOpen }}
        handlers={{ toggleLock, openPane, handlePaneEnter, handlePaneLeave }}
        display={{ paneIcon: "tasks", paneTooltip: "Open Action pane", allowMobileLock: true, shortcutHint: '⌥D' }}
        actions={{
          thirdButton: {
            onClick: openPane,
            ariaLabel: `Open Action pane (${cancellableTaskCount} active tasks)`,
            content: <span className="text-xs font-light">{cancellableTaskCount}</span>,
            tooltip: `${cancellableTaskCount} active task${cancellableTaskCount === 1 ? '' : 's'}`,
          },
          splitButton: readyAgentChatActions
            ? (() => {
                const messageAction = {
                  onClick: () => {
                    setLastAgentAction('message');
                    // markEngaged signals the auto-create-session gate inside the
                    // panel WITHOUT writing to panesStore.isTasksPaneOpen (which
                    // would short-circuit useSlidingPane.setOpen(false)).
                    readyAgentChatActions.markEngaged();
                    openPane();
                    // focusComposer is ref-backed, so even if the panel unmounts
                    // before the next frame the call is a safe no-op.
                    requestAnimationFrame(() => readyAgentChatActions.focusComposer());
                  },
                  ariaLabel: 'Open message composer',
                  tooltip: 'Open message',
                  content: <MessageSquareText className="h-4 w-4" />,
                };
                const voiceAction = {
                  onClick: () => {
                    setLastAgentAction('voice');
                    readyAgentChatActions.toggleRecording();
                  },
                  ariaLabel: readyAgentChatActions.isRecording ? 'Stop recording' : 'Start voice recording',
                  tooltip: readyAgentChatActions.isRecording ? 'Stop' : 'Voice (⌘⇧R)',
                  content: readyAgentChatActions.isRecording
                    ? <Square className="h-4 w-4" />
                    : <Mic className="h-4 w-4" />,
                };
                // Whichever the user invoked most recently is the primary
                // (full-cell) button; the other appears as a hover bubble.
                return lastAgentAction === 'voice'
                  ? { primary: voiceAction, secondary: messageAction }
                  : { primary: messageAction, secondary: voiceAction };
              })()
            : undefined,
        }}
        dataTour="tasks-pane-tab"
      />
      
      <div
        className="pointer-events-none"
        style={{
          position: 'fixed',
          right: 0,
          top: 0,
          bottom: 0,
          width: `${tasksPaneWidth}px`,
          // Content must sit above MediaLightbox and GenerationsPane; see UI_Z_LAYERS.
          zIndex: UI_Z_LAYERS.TASKS_PANE_CONTENT,
        }}
      >
        <div
          {...paneProps}
          data-tasks-pane="true"
          data-scroll-lock-scrollable="true"
          className={cn(
            'absolute top-0 right-0 h-full w-full bg-zinc-900/95 border-l border-zinc-700 shadow-xl transform transition-transform duration-300 ease-smooth flex flex-col pointer-events-auto',
            transformClass
          )}
        >
          {/* The pane-open-transition pointer-events gate is applied only to
              the tasks half (the original gated content). The chat half is the
              former popup — it lived outside the pane and was never gated, so
              we keep it always interactive to preserve that. Otherwise the
              attachment X buttons drop clicks during the 300ms slide-in. */}
          <div className="flex flex-col h-full">
            {/* Top half: tasks. Hidden when the chat half is expanded; otherwise
                flex-1 min-h-0 to share vertical space with the chat half on tool
                routes (or fill the pane on non-tool routes). `relative` anchors
                the absolute-positioned expand handle that bleeds into the bottom. */}
            {showTasksHalf && (
            <div className={cn(
              'flex-1 min-h-0 flex flex-col overflow-hidden relative',
              isPointerEventsEnabled ? 'pointer-events-auto' : 'pointer-events-none'
            )}>
            {/* Header */}
            <div className="p-2 border-b border-zinc-800 flex items-center justify-between flex-shrink-0">
              <h2 className="text-xl font-light text-zinc-200 ml-2">Action</h2>
              <div className="flex gap-2">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={handleCancelAllPending}
                      disabled={isCancelAllPending || cancellableTaskCount === 0}
                      className="flex items-center gap-2"
                    >
                      {isCancelAllPending ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Cancel All
                        </>
                      ) : (
                        'Cancel All'
                      )}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Cancel all queued tasks</TooltipContent>
                </Tooltip>
              </div>
            </div>
          
            {/* Status Filter Toggle — three buttons side-by-side, count inline as (N) so the row never overflows */}
            <div className="p-4 border-b border-zinc-800 flex-shrink-0">
              <div className="bg-zinc-800 rounded-lg p-1">
                <div className="flex gap-1">
                  {(['Processing', 'Succeeded', 'Failed'] as FilterGroup[]).map((filter) => {
                    const count = filter === 'Processing'
                      ? cancellableTaskCount
                      : filter === 'Succeeded'
                        ? (displayStatusCounts?.recentSuccesses || 0)
                        : (displayStatusCounts?.recentFailures || 0);

                    return (
                      <Button
                        key={filter}
                        variant={selectedFilter === filter ? "default" : "ghost"}
                        size="sm"
                        onClick={() => handleFilterChange(filter)}
                        className={cn(
                          "flex-1 text-xs flex items-center justify-center gap-1 px-2 min-w-0",
                          selectedFilter === filter
                            ? "bg-zinc-600 text-zinc-100 md:hover:bg-zinc-500"
                            : "text-zinc-400 md:hover:text-zinc-200 md:hover:bg-zinc-700"
                        )}
                      >
                        <span className="truncate">{filter}</span>
                        <span className={cn(
                          'font-light tabular-nums',
                          count === 0 ? 'opacity-40' : 'opacity-80'
                        )}>
                          ({count})
                        </span>
                      </Button>
                    );
                  })}
                </div>
              </div>

              {isStatusCountsDegraded && (
                <p className="mt-2 text-[11px] text-amber-300">
                  Task counters are partially degraded
                  {failedStatusQueries ? ` (${failedStatusQueries})` : ''}.
                </p>
              )}
              
              {/* Task Type + Project Scope Filters */}
              <div className="mt-2 flex items-center gap-2">
                <Select
                  value={selectedTaskType || 'all'}
                  onValueChange={(value) => handleTaskTypeChange(value === 'all' ? null : value)}
                >
                  <SelectTrigger variant="retro-dark" size="sm" colorScheme="zinc" className="h-7 !text-xs flex-1 min-w-0">
                    <SelectValue placeholder="All task types" />
                  </SelectTrigger>
                  <SelectContent variant="zinc">
                    <SelectItem variant="zinc" value="all" className="!text-xs">All task types</SelectItem>
                    {taskTypeOptions.length > 0 && <SelectSeparator className="bg-zinc-700" />}
                    {taskTypeOptions.map((type) => (
                      <SelectItem variant="zinc" key={type.value} value={type.value} className="!text-xs">
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                
                <Select
                  value={projectScope}
                  onValueChange={(value) => {
                    setProjectScope(value ?? 'current');
                    handlePageChange(1);
                  }}
                >
                  <SelectTrigger variant="retro-dark" size="sm" colorScheme="zinc" className="h-7 !text-xs flex-1 min-w-0">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent variant="zinc">
                    <SelectItem variant="zinc" value="current" className="!text-xs">This project</SelectItem>
                    <SelectItem variant="zinc" value="all" className="!text-xs">All projects</SelectItem>
                    {projects.filter(p => p.id !== selectedProjectId).length > 0 && <SelectSeparator className="bg-zinc-700" />}
                    {projects
                      .filter(p => p.id !== selectedProjectId)
                      .sort((a, b) => {
                        const aDate = a.createdAt ? new Date(a.createdAt).getTime() : 0;
                        const bDate = b.createdAt ? new Date(b.createdAt).getTime() : 0;
                        return bDate - aDate;
                      })
                      .map((project) => (
                        <SelectItem variant="zinc" key={project.id} value={project.id} className="!text-xs preserve-case">
                          {project.name}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <PaginationControls
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={handlePageChange}
              totalItems={totalTasks}
              isLoading={isPaginatedLoading}
              filterType={selectedFilter}
              recentCount={
                selectedFilter === 'Succeeded' ? displayStatusCounts?.recentSuccesses :
                selectedFilter === 'Failed' ? displayStatusCounts?.recentFailures :
                undefined
              }
            />

            <TasksPaneProcessingWarning onOpenSettings={onOpenSettings} />

            {/* Task list area — relative wrapper hosts the absolute-positioned
                bottom fade so scrolled-out content visibly trails off rather
                than hard-clipping at the divider. */}
            <div className="relative flex-grow overflow-hidden">
              <div
                className="absolute inset-0 overflow-y-auto"
                data-scroll-lock-scrollable="true"
              >
                <TaskList
                  filterStatuses={STATUS_GROUPS[selectedFilter]}
                  activeFilter={selectedFilter}
                  statusCounts={displayStatusCounts}
                  paginatedData={paginatedData}
                  isLoading={isPaginatedLoading}
                  currentPage={currentPage}
                  activeTaskId={activeTaskId}
                  onOpenImageLightbox={handleOpenImageLightbox}
                  onOpenVideoLightbox={handleOpenVideoLightbox}
                  onCloseLightbox={handleCloseLightbox}
                  mobileActiveTaskId={mobileActiveTaskId}
                  onMobileActiveTaskChange={setMobileActiveTaskId}
                  taskTypeFilter={selectedTaskType ?? undefined}
                  showProjectIndicator={isAllProjectsMode}
                  projectNameMap={projectNameMap}
                />
              </div>
              {/* Bottom fade — only visible when the chat half sits below */}
              {showChatHalf && (
                <div className="pointer-events-none absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-zinc-900 via-zinc-900/70 to-transparent" />
              )}
            </div>
            {/* Tasks expand / restore handle — bleeds into the bottom of the
                tasks content as an overlay. Doesn't take its own flex row, so
                the divider line below sits flush against the wrapper edge. */}
            {isToolRoute && (
              <button
                type="button"
                onClick={() => setExpandedHalf(expandedHalf === 'tasks' ? null : 'tasks')}
                className={cn(
                  'absolute bottom-0 left-0 right-0 z-20 flex items-center justify-center h-5',
                  'text-zinc-500 opacity-50 hover:opacity-100 hover:bg-zinc-800/60 hover:text-zinc-200',
                  'transition-all'
                )}
                aria-label={expandedHalf === 'tasks' ? 'Restore split layout' : 'Expand tasks to fill pane'}
                title={expandedHalf === 'tasks' ? 'Restore split' : 'Expand tasks'}
              >
                {expandedHalf === 'tasks'
                  ? <ChevronUp className="h-3 w-3" />
                  : <ChevronDown className="h-3 w-3" />}
              </button>
            )}
            </div>
            )}
            {/* Bottom half: agent chat thread. Only renders on tool routes and
                when not collapsed by the tasks-expanded state. The wrapper's
                top border IS the divider; the chat handle overlays the chat
                content rather than taking its own row. */}
            {showChatHalf && (
              <div
                className={cn(
                  // bg sits on the wrapper, NOT inside AgentChatPanel, so the
                  // pane bg → chat bg transition happens precisely at the
                  // border-t-2 divider line.
                  'overflow-hidden border-t-2 border-zinc-700 relative bg-zinc-950/60',
                  expandedHalf === 'chat' ? 'flex-1' : 'flex-1 min-h-0'
                )}
              >
                <AgentChatPanel />
                {/* Chat expand / restore handle — bleeds into the top of the chat */}
                <button
                  type="button"
                  onClick={() => setExpandedHalf(expandedHalf === 'chat' ? null : 'chat')}
                  className={cn(
                    'absolute top-0 left-0 right-0 z-20 flex items-center justify-center h-5',
                    'text-zinc-500 opacity-50 hover:opacity-100 hover:bg-zinc-800/60 hover:text-zinc-200',
                    'transition-all'
                  )}
                  aria-label={expandedHalf === 'chat' ? 'Restore split layout' : 'Expand chat to fill pane'}
                  title={expandedHalf === 'chat' ? 'Restore split' : 'Expand chat'}
                >
                  {expandedHalf === 'chat'
                    ? <ChevronDown className="h-3 w-3" />
                    : <ChevronUp className="h-3 w-3" />}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Centralized MediaLightbox */}
      {lightboxData && lightboxProps && createPortal(
        <MediaLightbox
          media={lightboxProps.media}
          onClose={handleCloseLightbox}
          navigation={{
            onNext: lightboxProps.onNext,
            onPrevious: lightboxProps.onPrevious,
            showNavigation: lightboxProps.showNavigation,
            hasNext: lightboxProps.hasNext,
            hasPrevious: lightboxProps.hasPrevious,
          }}
          features={{
            showImageEditTools: lightboxProps.showImageEditTools,
            showDownload: true,
            showMagicEdit: lightboxProps.showMagicEdit,
            showTaskDetails: true,
          }}
          taskDetailsData={taskDetailsData ?? undefined}
          shotWorkflow={{
            allShots: simplifiedShotOptions,
            selectedShotId: lightboxSelectedShotId || currentShotId || lastAffectedShotId || undefined,
            onShotChange: setLightboxSelectedShotId,
            onAddToShot: handleAddToShot,
            onAddToShotWithoutPosition: handleAddToShotWithoutPosition,
            optimisticPositionedIds,
            optimisticUnpositionedIds,
            onOptimisticPositioned: handleOptimisticPositioned,
            onOptimisticUnpositioned: handleOptimisticUnpositioned,
            onShowTick: async () => {},
          }}
          showTickForImageId={undefined}
          onOpenExternalGeneration={handleOpenExternalGeneration}
          tasksPaneOpen={true}
          tasksPaneWidth={tasksPaneWidth}
          initialVariantId={lightboxProps.initialVariantId}
          videoProps={{ fetchVariantsForSelf: lightboxProps.fetchVariantsForSelf }}
        />,
        document.body
      )}
    </>
  );
};

// Memoize TasksPane with custom comparison
export const TasksPane = React.memo(TasksPaneComponent, (prevProps, nextProps) => {
  return prevProps.onOpenSettings === nextProps.onOpenSettings;
});
