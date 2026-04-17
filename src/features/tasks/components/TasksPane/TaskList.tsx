import React, { useMemo } from 'react';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { type PaginatedTasksResponse } from '@/shared/hooks/tasks/useTasks';
import { useIncomingTasks } from '@/shared/contexts/IncomingTasksContext';
import { TaskStatus, Task } from '@/types/tasks';
import { TaskItem } from './TaskItem';
import { IncomingTaskItem } from './IncomingTaskItem';
import { FilterGroup } from './constants';
import { TaskItemSkeleton } from './components/TaskItemSkeleton';
import { useTaskFiltering } from './hooks/useTaskFiltering';
import { useTaskListPresentationState } from './hooks/useTaskListPresentationState';
import type { TaskLightboxHandlers } from './types';

interface TaskListProps extends TaskLightboxHandlers {
  filterStatuses: TaskStatus[];
  activeFilter: FilterGroup;
  statusCounts: {
    processing: number;
    recentSuccesses: number;
    recentFailures: number;
  } | undefined;
  paginatedData?: PaginatedTasksResponse;
  isLoading?: boolean;
  currentPage?: number;
  activeTaskId?: string | null;
  mobileActiveTaskId?: string | null;
  onMobileActiveTaskChange?: (taskId: string | null) => void;
  taskTypeFilter?: string;
  showProjectIndicator?: boolean;
  projectNameMap?: Record<string, string>;
}

const TaskListComponent: React.FC<TaskListProps> = ({
  filterStatuses,
  activeFilter,
  statusCounts,
  paginatedData,
  isLoading = false,
  currentPage = 1,
  activeTaskId,
  onOpenImageLightbox,
  onOpenVideoLightbox,
  onCloseLightbox,
  mobileActiveTaskId,
  onMobileActiveTaskChange,
  showProjectIndicator = false,
  projectNameMap = {},
}) => {
  const { incomingTasks } = useIncomingTasks();
  const tasks = useMemo(() => paginatedData?.tasks ?? [], [paginatedData?.tasks]);

  const { newTaskIds, isFilterTransitioning } = useTaskListPresentationState({
    tasks,
    activeFilter,
    filterStatuses,
    currentPage,
    isLoading,
  });

  const {
    filteredTasks,
    visibleIncomingTasks,
    summaryMessage,
    knownEmptyProcessing,
    emptyMessage,
  } = useTaskFiltering({
    tasks,
    incomingTasks,
    activeFilter,
    statusCounts,
    paginatedData,
  });

  const showSkeleton = (isLoading || isFilterTransitioning) && !knownEmptyProcessing;
  const hasTaskContent = filteredTasks.length > 0
    || (activeFilter === 'Processing' && visibleIncomingTasks.length > 0);
  const showEmptyMessage = !showSkeleton
    && !hasTaskContent
    && !summaryMessage;

  return (
    <div className="p-4 h-full flex flex-col text-zinc-200">
      {summaryMessage && !showSkeleton && (
        <div className="p-3 mb-4 bg-zinc-800/95 rounded-md text-sm text-zinc-300 border border-zinc-700">
          {summaryMessage}
        </div>
      )}

      {showSkeleton && (() => {
        const skeletonCount = Math.min(
          activeFilter === 'Processing' ? (statusCounts?.processing ?? 4) : 4,
          4,
        );
        const variant = activeFilter === 'Succeeded' ? 'complete'
          : activeFilter === 'Failed' ? 'failed'
          : 'processing';
        return (
          <div className="space-y-1">
            {Array.from({ length: skeletonCount }, (_, i) => (
              <React.Fragment key={i}>
                <TaskItemSkeleton variant={variant} showImages={i % 2 === 0} showPrompt={i % 2 === 1} />
                {i < skeletonCount - 1 && <div className="h-0 border-b border-zinc-700/40 my-1" />}
              </React.Fragment>
            ))}
          </div>
        );
      })()}

      {showEmptyMessage && <p className="text-zinc-400 text-center">{emptyMessage}</p>}

      {!showSkeleton && hasTaskContent && (
        <div className="flex-grow -mr-4">
          <ScrollArea className="h-full pr-4">
            {filteredTasks.map((task: Task, idx: number) => (
              <React.Fragment key={task.id}>
                <TaskItem
                  task={task}
                  isNew={newTaskIds.has(task.id)}
                  isActive={task.id === activeTaskId}
                  onOpenImageLightbox={onOpenImageLightbox}
                  onOpenVideoLightbox={onOpenVideoLightbox}
                  onCloseLightbox={onCloseLightbox}
                  isMobileActive={mobileActiveTaskId === task.id}
                  onMobileActiveChange={onMobileActiveTaskChange}
                  showProjectIndicator={showProjectIndicator}
                  projectName={projectNameMap[task.projectId]}
                />
                {(idx < filteredTasks.length - 1
                  || (activeFilter === 'Processing' && visibleIncomingTasks.length > 0)) && (
                  <div className="h-0 border-b border-zinc-700/40 my-1" />
                )}
              </React.Fragment>
            ))}

            {visibleIncomingTasks.map((incomingTask, idx) => (
              <React.Fragment key={incomingTask.id}>
                <IncomingTaskItem task={incomingTask} />
                {idx < visibleIncomingTasks.length - 1 && (
                  <div className="h-0 border-b border-zinc-700/40 my-1" />
                )}
              </React.Fragment>
            ))}
          </ScrollArea>
        </div>
      )}
    </div>
  );
};

export const TaskList = React.memo(TaskListComponent);
