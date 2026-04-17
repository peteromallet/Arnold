import React, { useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useRenderLogger } from '@/shared/lib/debug/debugRendering';
import { TaskList } from './TaskList';
import { cn } from '@/shared/components/ui/contracts/cn';
import { Button } from '@/shared/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { Loader2 } from 'lucide-react';
import { PaneControlTab } from '@/shared/components/PaneControlTab';
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
import { StatusIndicator } from './components/StatusIndicator';
import { PaginationControls } from './components/PaginationControls';
import { useTasksLightbox } from './hooks/useTasksLightbox';
import { useShotActions } from './hooks/useShotActions';
import { useTasksPaneController } from './hooks/useTasksPaneController';
import { useTasksPaneSlidingPane } from './hooks/useTasksPaneSlidingPane';
import { useRenderBudget } from '@/shared/dev/useRenderBudget';
import { usePanesStore } from '@/shared/state/panesStore';

interface TasksPaneProps {
  onOpenSettings: () => void;
}

const TasksPaneComponent: React.FC<TasksPaneProps> = ({ onOpenSettings }) => {
  useRenderBudget('TasksPane', 5);
  const isTasksPaneLocked = usePanesStore((state) => state.isTasksPaneLocked);
  const setIsTasksPaneLocked = usePanesStore((state) => state.setIsTasksPaneLocked);
  const tasksPaneWidth = usePanesStore((state) => state.tasksPaneWidth);
  const activeTaskId = usePanesStore((state) => state.activeTaskId);
  const setActiveTaskId = usePanesStore((state) => state.setActiveTaskId);
  const isTasksPaneOpenProgrammatic = usePanesStore((state) => state.isTasksPaneOpen);
  const setIsTasksPaneOpenProgrammatic = usePanesStore((state) => state.setIsTasksPaneOpen);

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
    handleStatusIndicatorClick,
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

  return (
    <>
      {/* Backdrop overlay for mobile - z-index just below TasksPane (100001) */}
      <PaneBackdrop show={showBackdrop} zIndex={100000} onClose={closePane} />
      
      <PaneControlTab
        position={{ side: "right", paneDimension: tasksPaneWidth, bottomOffset: useBottomOffset() }}
        state={{ isLocked, isOpen: !!isOpen }}
        handlers={{ toggleLock, openPane, handlePaneEnter, handlePaneLeave }}
        display={{ paneIcon: "tasks", paneTooltip: "View all tasks", allowMobileLock: true, shortcutHint: '⌥D' }}
        actions={{
          thirdButton: {
            onClick: openPane,
            ariaLabel: `Open Tasks pane (${cancellableTaskCount} active tasks)`,
            content: <span className="text-xs font-light">{cancellableTaskCount}</span>,
            tooltip: `${cancellableTaskCount} active task${cancellableTaskCount === 1 ? '' : 's'}`,
          },
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
          // z-index must be above MediaLightbox (z-100000) so TasksPane stays on top
          // when images are dragged in reposition mode
          zIndex: 100001,
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
          <div
            className={cn(
              'flex flex-col h-full',
              isPointerEventsEnabled ? 'pointer-events-auto' : 'pointer-events-none'
            )}
          >
            {/* Header */}
            <div className="p-2 border-b border-zinc-800 flex items-center justify-between flex-shrink-0">
              <h2 className="text-xl font-light text-zinc-200 ml-2">Tasks</h2>
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
          
            {/* Status Filter Toggle */}
            <div className="p-4 border-b border-zinc-800 flex-shrink-0">
              <div className="bg-zinc-800 rounded-lg p-1 space-y-1">
                {/* Processing button */}
                <Button
                  variant={selectedFilter === 'Processing' ? "default" : "ghost"}
                  size="sm"
                  onClick={() => handleFilterChange('Processing')}
                  className={cn(
                    "w-full text-xs flex items-center justify-center",
                    selectedFilter === 'Processing'
                      ? "bg-zinc-600 text-zinc-100 md:hover:bg-zinc-500"
                      : "text-zinc-400 md:hover:text-zinc-200 md:hover:bg-zinc-700"
                  )}
                >
                  <span>Processing</span>
                  <StatusIndicator
                    count={cancellableTaskCount}
                    type="Processing"
                    isSelected={selectedFilter === 'Processing'}
                  />
                </Button>
                
                {/* Succeeded and Failed buttons */}
                <div className="flex gap-1">
                  {(['Succeeded', 'Failed'] as FilterGroup[]).map((filter) => {
                    const count = filter === 'Succeeded' 
                      ? (displayStatusCounts?.recentSuccesses || 0)
                      : (displayStatusCounts?.recentFailures || 0);
                    
                    return (
                      <Button
                        key={filter}
                        variant={selectedFilter === filter ? "default" : "ghost"}
                        size="sm"
                        onClick={() => handleFilterChange(filter)}
                        className={cn(
                          "flex-1 text-xs flex items-center justify-center",
                          selectedFilter === filter
                            ? "bg-zinc-600 text-zinc-100 md:hover:bg-zinc-500"
                            : "text-zinc-400 md:hover:text-zinc-200 md:hover:bg-zinc-700"
                        )}
                      >
                        <span>{filter}</span>
                        <StatusIndicator
                          count={count}
                          type={filter}
                          isSelected={selectedFilter === filter}
                          onClick={() => handleStatusIndicatorClick(filter)}
                        />
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
            
            <div
              className="flex-grow overflow-y-auto"
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
