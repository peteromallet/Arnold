import React, { useCallback, Suspense, useId } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { useExtraLargeModal } from '@/shared/hooks/useModal';
import { ImageGenerationForm } from '@/shared/components/ImageGenerationForm';
import { createTask } from '@/shared/lib/taskCreation';
import { useApiKeys } from '@/shared/hooks/settings/useApiKeys';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/shared/lib/queryKeys';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { useTaskPlaceholder } from '@/shared/hooks/tasks/useTaskPlaceholder';
import { Skeleton } from '@/shared/components/ui/skeleton';
import { ExternalLinkTooltipButton } from '@/shared/components/ui/composed/ExternalLinkTooltipButton';
import { useNavigate } from 'react-router-dom';
import { TOOL_ROUTES } from '@/shared/lib/tooling/toolRoutes';
import type { BatchImageGenerationTaskParams } from '@/shared/types/imageGeneration';

interface ImageGenerationModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Pre-select a specific shot when the modal opens */
  initialShotId?: string | null;
}

export const ImageGenerationModal: React.FC<ImageGenerationModalProps> = ({
  isOpen,
  onClose,
  initialShotId,
}) => {
  const modal = useExtraLargeModal();
  const footerPortalId = useId();
  const { selectedProjectId } = useProjectSelectionContext();
  const queryClient = useQueryClient();
  const { getApiKey } = useApiKeys();
  const navigate = useNavigate();
  const run = useTaskPlaceholder();

  const openaiApiKey = getApiKey('openai_api_key');

  const handleGenerate = useCallback(async (taskParams: BatchImageGenerationTaskParams): Promise<string[]> => {

    if (!selectedProjectId) {
      toast.error("No project selected. Please select a project before generating images.");
      return [];
    }

    await run({
      taskType: 'image_generation',
      label: taskParams.prompts?.[0]?.fullPrompt?.substring(0, 50) || 'Generating images...',
      context: 'ImageGenerationModal',
      toastTitle: 'Failed to create tasks',
      create: () => {
        const { project_id, ...input } = taskParams;
        return createTask({
          project_id,
          family: 'image_generation',
          input,
        });
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: queryKeys.unified.projectPrefix(selectedProjectId) });
      },
    });
    return [];
  }, [selectedProjectId, queryClient, run]);

  const handleNavigateToTool = useCallback(() => {
    onClose();
    navigate(TOOL_ROUTES.IMAGE_GENERATION);
  }, [onClose, navigate]);

  // Check if product tour is active (Joyride elements exist in DOM)
  const isTourActive = useCallback(() => {
    return !!document.querySelector('.react-joyride__overlay');
  }, []);

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        // Check tour status fresh (not stale render-time value)
        const tourActiveNow = isTourActive();

        // During tour, the modal is controlled entirely by the isOpen prop
        // (which is set by the closeGenerationModal event from ProductTour)
        // So we ignore onOpenChange during the tour
        if (!open && tourActiveNow) {
          return;
        }
        if (!open) onClose();
      }}
    >
      <DialogContent
        className={modal.className}
        style={{
          ...modal.style,
          maxWidth: '900px',
        }}
      >
        <DialogHeader className={modal.headerClass}>
          <div className="flex items-center gap-2">
            <DialogTitle className="text-xl font-light">Generate Images</DialogTitle>
            <ExternalLinkTooltipButton
              onClick={handleNavigateToTool}
              tooltipLabel="Open Tool"
              delayDuration={500}
            />
          </div>
        </DialogHeader>

        <div className={`${modal.scrollClass} -mx-6 px-6 flex-1 min-h-0 pb-4`}>
          <Suspense fallback={
            <div className="flex flex-col h-full">
              <div className="space-y-6 py-4 flex-1">
                {/* Main Content Layout - matches flex gap-6 flex-col md:flex-row */}
                <div className="flex gap-6 flex-col md:flex-row">
                  {/* Left Column - Prompts and Shot Selector */}
                  <div className="flex-1 space-y-6">
                    {/* PromptsSection skeleton */}
                    <div className="space-y-4">
                      <Skeleton className="h-8 w-32" />
                      <div className="space-y-3">
                        <Skeleton className="h-24 w-full rounded-md" />
                        <Skeleton className="h-24 w-full rounded-md" />
                      </div>
                      <div className="flex gap-2">
                        <Skeleton className="h-9 flex-1 rounded-md" />
                        <Skeleton className="h-9 w-24 rounded-md" />
                      </div>
                    </div>
                    {/* ShotSelector skeleton */}
                    <div className="space-y-2">
                      <Skeleton className="h-4 w-24" />
                      <Skeleton className="h-10 w-full rounded-md" />
                    </div>
                  </div>

                  {/* Right Column - ModelSection */}
                  <div className="md:w-80 space-y-6">
                    {/* ModelSection skeleton */}
                    <div className="space-y-4">
                      <Skeleton className="h-8 w-40" />
                      <div className="space-y-3">
                        <Skeleton className="h-32 w-full rounded-md" />
                        <div className="space-y-2">
                          <Skeleton className="h-4 w-20" />
                          <Skeleton className="h-10 w-full rounded-md" />
                        </div>
                        <div className="space-y-2">
                          <Skeleton className="h-4 w-24" />
                          <Skeleton className="h-10 w-full rounded-md" />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          }>
            <ImageGenerationForm
              onGenerate={handleGenerate}
              openaiApiKey={openaiApiKey}
              stickyFooter={true}
              footerPortalId={footerPortalId}
              initialShotId={initialShotId}
            />
          </Suspense>
        </div>

        {/* Footer portal target - outside scroll container so scrollbar appears behind it */}
        <div id={footerPortalId} className="-mx-6 -mb-6" />
      </DialogContent>
    </Dialog>
  );
};
