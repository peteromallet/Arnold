/**
 * TaskDetailsModal
 *
 * Modal dialog for viewing detailed task information for a generation.
 * Shows input images, settings, parameters, and allows applying settings.
 *
 * Moved from tools/travel-between-images/components/TaskDetailsModal.tsx
 * to shared/ because it's used by MediaGalleryLightbox and other shared components.
 */

import React, { ReactNode, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { useIsMobile } from '@/shared/hooks/mobile';
import { useLargeModal } from '@/shared/hooks/useModal';
import { Label } from '@/shared/components/ui/primitives/label';
import { normalizeTaskDetailsPayload } from '@/shared/components/TaskDetails/hooks/normalizeTaskDetailsPayload';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { useGenerationTaskDetails } from '@/shared/components/TaskDetails/hooks/useGenerationTaskDetails';
import { usePublicLoras } from '@/features/resources/hooks/useResources';
import {
  TaskDetailsEmptyState,
  TaskDetailsErrorState,
  TaskDetailsLoadingState,
} from '@/shared/components/TaskDetails/components/TaskDetailsStatusStates';
import {
  TaskDetailsSummaryControls,
  TaskDetailsSummarySection,
} from '@/shared/components/TaskDetails/components/TaskDetailsSummarySection';
import type { TaskGenerationDetailsRendererProps } from '@/shared/components/TaskDetails/components/TaskDetailsSummaryAndParams';
import { useTaskDetailsModalState } from '@/shared/components/TaskDetails/hooks/useTaskDetailsModalState';

interface TaskDetailsModalProps {
  generationId: string;
  children?: ReactNode;
  onApplySettingsFromTask?: (taskId: string, replaceImages: boolean, inputImages: string[]) => void;
  onClose?: () => void;
  onShowVideo?: () => void;
  isVideoContext?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  renderGenerationDetails?: (props: TaskGenerationDetailsRendererProps) => ReactNode;
}

const TaskDetailsModal: React.FC<TaskDetailsModalProps> = ({
  generationId,
  children,
  onApplySettingsFromTask,
  onClose,
  onShowVideo,
  isVideoContext,
  open,
  onOpenChange,
  renderGenerationDetails,
}) => {
  const isMobile = useIsMobile();
  const modal = useLargeModal();
  const [internalOpen, setInternalOpen] = useState(false);
  const isOpen = open !== undefined ? open : internalOpen;
  const setIsOpen = (value: boolean) => {
    if (onOpenChange) {
      onOpenChange(value);
    } else {
      setInternalOpen(value);
    }
  };
  const { selectedProjectId } = useProjectSelectionContext();
  const { data: availableLoras } = usePublicLoras();

  const {
    taskId,
    task,
    inputImages,
    isLoadingTask,
    taskError,
    taskDetailsStatus,
  } = useGenerationTaskDetails({
    generationId,
    projectId: selectedProjectId ?? null,
    enabled: isOpen,
    resolveMappingOnDemand: true,
  });
  const {
    replaceImages,
    setReplaceImages,
    showDetailedParams,
    setShowDetailedParams,
    showAllImages,
    setShowAllImages,
    showFullPrompt,
    setShowFullPrompt,
    showFullNegativePrompt,
    setShowFullNegativePrompt,
    paramsCopied,
    idCopied,
    handleCopyParams,
    handleCopyId,
  } = useTaskDetailsModalState({
    taskId,
    taskParams: task?.params,
  });

  const normalizedTaskPayload = React.useMemo(() => normalizeTaskDetailsPayload(task), [task]);
  const detailInputImages = normalizedTaskPayload.inputImages.length > 0
    ? normalizedTaskPayload.inputImages
    : inputImages;
  const summaryControls: TaskDetailsSummaryControls = {
    showAllImages,
    onShowAllImagesChange: setShowAllImages,
    showFullPrompt,
    onShowFullPromptChange: setShowFullPrompt,
    showFullNegativePrompt,
    onShowFullNegativePromptChange: setShowFullNegativePrompt,
    showDetailedParams,
    onShowDetailedParamsChange: setShowDetailedParams,
    paramsCopied,
    onCopyParams: () => {
      void handleCopyParams();
    },
  };

  const handleApplySettingsFromTask = () => {
    if (taskId && onApplySettingsFromTask && task) {
      // Pass the correctly ordered inputImages array (derived from task JSON sources)
      onApplySettingsFromTask(taskId, replaceImages, detailInputImages);
    }
    setIsOpen(false);
    onClose?.();
  };

  const isLoading = isLoadingTask;

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        setIsOpen(open);
        // If the dialog is transitioning from open -> closed, notify parent
        if (!open && onClose) {
          onClose();
        }
      }}
    >
      {/* Avoid rendering an active trigger when controlled via `open` to prevent unintended close events */}
      {!open && children && <DialogTrigger asChild>{children}</DialogTrigger>}
      <DialogContent
        className={modal.className}
        style={modal.style}
        aria-describedby="task-details-description"
      >
        <div className={modal.headerClass}>
          <DialogHeader>
            <div className="flex items-center justify-between">
              <DialogTitle className="sr-only">Task Details</DialogTitle>
              {taskId && (
                <button
                  onClick={handleCopyId}
                  className={`px-2 py-1 text-xs rounded transition-colors ${
                    idCopied ? 'text-green-400' : 'text-zinc-500 hover:text-zinc-200 hover:bg-zinc-700'
                  }`}
                >
                  {idCopied ? 'copied' : 'id'}
                </button>
              )}
            </div>
            <p id="task-details-description" className="sr-only">
              View details about the task that generated this video, including input images, settings, and parameters.
            </p>
          </DialogHeader>
        </div>

        <div className={modal.scrollClass}>
          {isLoading ? (
            <TaskDetailsLoadingState />
          ) : taskDetailsStatus === 'error' && !task ? (
            <TaskDetailsErrorState errorMessage={taskError?.message} />
          ) : task ? (
            <div className="space-y-6 p-4">
              <TaskDetailsSummarySection
                task={task}
                inputImages={detailInputImages}
                detailsVariant="modal"
                isMobile={isMobile}
                availableLoras={availableLoras}
                controls={summaryControls}
                renderGenerationDetails={renderGenerationDetails}
              />
            </div>
          ) : (
            <TaskDetailsEmptyState />
          )}
        </div>

        <div className={modal.footerClass}>
          <DialogFooter className="pt-4 border-t">
           <div className="flex w-full items-center gap-3">
              {detailInputImages.length > 0 && (
                <>
                  <div className="flex items-center gap-x-2">
                    <Checkbox
                      id="replaceImages"
                      checked={replaceImages}
                      onCheckedChange={(checked) => setReplaceImages(checked as boolean)}
                    />
                    <Label htmlFor="replaceImages" className={`text-sm font-light ${isMobile ? 'whitespace-pre-line leading-tight' : ''}`}>
                      {isMobile ? 'Replace\nthese\nimages' : 'Replace these images'}
                    </Label>
                  </div>
                  {onApplySettingsFromTask && task && taskId && (
                    <Button
                      variant="retro"
                      size="retro-sm"
                      onClick={handleApplySettingsFromTask}
                      className={`text-sm ${isMobile ? 'whitespace-pre-line leading-tight py-3 px-4 min-h-[3rem]' : ''}`}
                    >
                      {isMobile ? 'Apply\nSettings' : 'Apply Settings'}
                    </Button>
                  )}
                </>
              )}
              <div className="flex items-center gap-x-3 ml-auto">
              {/* Show Video button for mobile video context - now positioned directly to the left of close button */}
              {isMobile && isVideoContext && onShowVideo && (
                <Button
                  variant="secondary"
                  onClick={() => {
                    // Don't close modal immediately - let the onShowVideo handler manage the timing
                    onShowVideo();
                  }}
                  className="text-sm whitespace-pre-line leading-tight py-3 px-4 min-h-[3rem]"
                >
                  {'Show\nVideo'}
                </Button>
              )}
              <Button
                variant="outline"
                onClick={() => setIsOpen(false)}
                className={`text-sm ${isMobile ? 'whitespace-pre-line leading-tight py-3 px-4 min-h-[2.5rem]' : ''}`}
              >
                Close
              </Button>
            </div>
          </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export { TaskDetailsModal };
