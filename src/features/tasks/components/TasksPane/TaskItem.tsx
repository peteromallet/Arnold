import React, { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/components/ui/contracts/cn';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { Task } from '@/types/tasks';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { useIsMobile } from '@/shared/hooks/mobile';
import { useCancelTask } from '@/shared/hooks/tasks/useTaskCancellation';
import { useTaskType } from '@/shared/hooks/tasks/useTaskType';
import { usePublicLoras } from '@/features/resources/hooks/useResources';
import { taskSupportsProgress } from '@/shared/lib/tasks/taskConfig';
import { taskQueryKeys } from '@/shared/lib/queryKeys/tasks';
import { parseTaskParamsForDisplay, extractShotId } from './utils/task-utils';
import { useTaskContentType } from './hooks/useTaskContentType';
import { useVideoGenerations } from './hooks/useVideoGenerations';
import { useImageGeneration } from './hooks/useImageGeneration';
import { useTaskNavigation } from './hooks/useTaskNavigation';
import { useTaskErrorDisplay } from './hooks/useTaskErrorDisplay';
import { useTaskItemDisplay } from './hooks/useTaskItemDisplay';
import { TaskItemActions } from './components/TaskItemActions';
import { TaskItemTooltip } from './components/TaskItemTooltip';
import { TaskItemPreview } from './components/TaskItemPreview';
import type { TaskLightboxHandlers } from './types';

interface TaskItemProps extends TaskLightboxHandlers {
  task: Task;
  isNew?: boolean;
  isActive?: boolean;
  isMobileActive?: boolean;
  onMobileActiveChange?: (taskId: string | null) => void;
  showProjectIndicator?: boolean;
  projectName?: string;
}

const TaskItemComponent: React.FC<TaskItemProps> = ({
  task,
  isNew = false,
  isActive = false,
  onOpenImageLightbox,
  onOpenVideoLightbox,
  onCloseLightbox,
  isMobileActive = false,
  onMobileActiveChange,
  showProjectIndicator = false,
  projectName,
}) => {
  const isMobile = useIsMobile();
  const { selectedProjectId, setSelectedProjectId } = useProjectSelectionContext();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const cancelTaskMutation = useCancelTask(selectedProjectId);

  const handleCancel = useCallback(() => {
    const queryKey = taskQueryKeys.paginated(selectedProjectId!);
    const previousData = queryClient.getQueryData(queryKey);

    queryClient.setQueriesData(
      { queryKey },
      (oldData: { tasks?: Task[]; total?: number } | undefined) => {
        if (!oldData?.tasks) return oldData;
        return {
          ...oldData,
          tasks: oldData.tasks.map((existingTask: Task) => (
            existingTask.id === task.id
              ? { ...existingTask, status: 'Cancelled' as const }
              : existingTask
          )),
        };
      },
    );

    cancelTaskMutation.mutate(task.id, {
      onError: (error) => {
        queryClient.setQueryData(queryKey, previousData);
        toast({
          title: 'Cancellation Failed',
          description: error.message || 'Could not cancel the task.',
          variant: 'destructive',
        });
      },
      onSettled: () => {
        queryClient.invalidateQueries({ queryKey });
      },
    });
  }, [cancelTaskMutation, queryClient, selectedProjectId, task.id]);
  const { data: taskTypeInfo } = useTaskType(task.taskType);
  const { data: availableLoras = [] } = usePublicLoras();

  const taskParams = useMemo(() => parseTaskParamsForDisplay(task.params), [task.params]);
  const parsedTaskParams = taskParams.parsed as Record<string, unknown>;
  const taskInfo = useTaskContentType({ task, taskParams, taskTypeInfo });

  const [isHoveringTaskItem, setIsHoveringTaskItem] = useState(false);
  const handleMouseEnter = useCallback(() => setIsHoveringTaskItem(true), []);
  const handleMouseLeave = useCallback(() => setIsHoveringTaskItem(false), []);
  const resetHoverState = useCallback(() => setIsHoveringTaskItem(false), []);

  const {
    videoOutputs,
    isLoadingVideoGen,
    waitingForVideoToOpen,
    ensureFetch: ensureVideoFetch,
    triggerOpen: triggerVideoOpen,
    clearWaiting: clearVideoWaiting,
  } = useVideoGenerations({
    task,
    taskParams,
    isVideoTask: taskInfo.isVideoTask,
    isCompletedVideoTask: taskInfo.isCompletedVideoTask,
    isHovering: isHoveringTaskItem,
  });

  const { generationData, variantId: imageVariantId } = useImageGeneration({
    task,
    taskParams,
    isImageTask: taskInfo.isImageTask,
  });

  const {
    createdTimeAgo,
    processingTime,
    completedTime,
    abbreviatedTaskType,
    travelImageUrls,
    imagesToShow,
    extraImageCount,
    shouldShowPromptPreview,
    promptPreviewText,
    variantName,
    statusBadgeClass,
  } = useTaskItemDisplay({
    task,
    parsedTaskParams,
    promptText: taskParams.promptText,
    taskTypeDisplayName: taskTypeInfo?.display_name,
    isVideoTask: taskInfo.isVideoTask,
    generationData,
    videoOutputs,
  });

  const shotId = useMemo(() => extractShotId(task), [task]);
  const { cascadedTaskId, cascadedTask, isCascadedTaskLoading } = useTaskErrorDisplay(task);

  const {
    handleCheckProgress,
    handleViewVideo,
    handleViewImage,
    handleVisitShot,
    handleMobileTap,
    progressPercent,
  } = useTaskNavigation({
    task,
    shotId,
    isMobile,
    setIsHoveringTaskItem,
    videoOutputs,
    isLoadingVideoGen,
    waitingForVideoToOpen,
    ensureVideoFetch,
    triggerVideoOpen,
    clearVideoWaiting,
    generationData,
    imageVariantId,
    taskInfo,
    onOpenImageLightbox,
    onOpenVideoLightbox,
    onCloseLightbox,
    isMobileActive,
    onMobileActiveChange,
  });

  const handleSwitchProject = (projectId: string) => {
    setSelectedProjectId(projectId);
    navigate('/');
  };

  const containerClass = cn(
    'relative p-3 mb-2 bg-zinc-800/95 rounded-md shadow border transition-colors overflow-hidden',
    isNew
      ? 'border-teal-400 animate-[flash_3s_ease-in-out]'
      : isActive
        ? 'border-blue-500 bg-blue-900/20 ring-2 ring-blue-400/50'
        : 'border-zinc-600 hover:border-zinc-400',
  );

  const taskItemContent = (
    <div
      className={containerClass}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={handleMobileTap}
    >
      <div className="flex justify-between items-center mb-1 gap-2">
        <div className="flex items-center gap-1 flex-1 min-w-0">
          <span className="text-sm font-light text-zinc-200 whitespace-nowrap overflow-hidden text-ellipsis cursor-default min-w-0">
            {abbreviatedTaskType}
          </span>

          <TaskItemActions
            task={task}
            isMobile={isMobile}
            isCompletedVideoTask={taskInfo.isCompletedVideoTask}
            isImageTask={taskInfo.isImageTask}
            generationData={generationData}
            isLoadingVideoGen={isLoadingVideoGen}
            waitingForVideoToOpen={waitingForVideoToOpen}
            onViewVideo={handleViewVideo}
            onViewImage={handleViewImage}
            onVisitShot={handleVisitShot}
            showProjectIndicator={showProjectIndicator}
            projectName={projectName}
            selectedProjectId={selectedProjectId || undefined}
            onSwitchProject={handleSwitchProject}
            shotId={shotId}
          />
        </div>

        <span className={`px-2 py-0.5 text-xs rounded-full flex-shrink-0 ${statusBadgeClass}`}>
          {task.status}
        </span>
      </div>

      <TaskItemPreview
        task={task}
        imagesToShow={imagesToShow}
        extraImageCount={extraImageCount}
        shouldShowPromptPreview={shouldShowPromptPreview}
        promptPreviewText={promptPreviewText}
        generationData={generationData}
        imageVariantId={imageVariantId}
        onOpenImageLightbox={onOpenImageLightbox}
        isHoveringTaskItem={isHoveringTaskItem}
        cascadedTaskId={cascadedTaskId}
        cascadedTask={cascadedTask}
        isCascadedTaskLoading={isCascadedTaskLoading}
      />

      <div className="flex items-center text-[11px] text-zinc-400">
        <span className="flex-1">
          {task.status === 'In Progress' && processingTime
            ? processingTime
            : task.status === 'Complete' && completedTime
              ? completedTime
              : `Created ${createdTimeAgo ?? 'Unknown'}`}
        </span>

        {variantName && (
          <span className="ml-2 px-1.5 py-0.5 bg-black/50 text-white text-[10px] rounded-md flex-shrink-0 preserve-case">
            {variantName}
          </span>
        )}

        {(task.status === 'Queued' || task.status === 'In Progress') && (
          <div className="flex items-center flex-shrink-0">
            {taskSupportsProgress(task.taskType) && task.status === 'In Progress' && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCheckProgress}
                disabled={progressPercent !== null}
                className="px-2 py-1 min-w-[80px] h-auto text-blue-400 hover:bg-blue-900/20 hover:text-blue-300 flex flex-col items-center justify-center"
              >
                <div className="text-xs leading-tight">
                  {progressPercent === null ? (
                    <>
                      <div>Check</div>
                      <div>Progress</div>
                    </>
                  ) : (
                    <>
                      <div>{progressPercent}%</div>
                      <div>Complete</div>
                    </>
                  )}
                </div>
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCancel}
              disabled={cancelTaskMutation.isPending}
              className="px-2 py-0.5 text-red-400 hover:bg-red-900/20 hover:text-red-300"
            >
              {cancelTaskMutation.isPending ? 'Cancelling...' : 'Cancel'}
            </Button>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <TaskItemTooltip
      task={task}
      isVideoTask={taskInfo.isVideoTask}
      isCompletedVideoTask={taskInfo.isCompletedVideoTask}
      showsTooltip={taskInfo.showsTooltip}
      isMobile={isMobile}
      travelImageUrls={travelImageUrls}
      videoOutputs={videoOutputs}
      generationData={generationData}
      onOpenVideoLightbox={onOpenVideoLightbox}
      onOpenImageLightbox={onOpenImageLightbox}
      onResetHoverState={resetHoverState}
      availableLoras={availableLoras}
    >
      {taskItemContent}
    </TaskItemTooltip>
  );
};

const TaskItem = React.memo(TaskItemComponent, (prevProps, nextProps) => {
  return (
    prevProps.task.id === nextProps.task.id
    && prevProps.task.status === nextProps.task.status
    && prevProps.task.errorMessage === nextProps.task.errorMessage
    && prevProps.isNew === nextProps.isNew
    && prevProps.isActive === nextProps.isActive
    && prevProps.isMobileActive === nextProps.isMobileActive
    && prevProps.showProjectIndicator === nextProps.showProjectIndicator
    && prevProps.projectName === nextProps.projectName
  );
});

export { TaskItem };
