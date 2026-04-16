import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '@/shared/contexts/ProjectContext';
import { usePanes } from '@/shared/contexts/PanesContext';
import { useCurrentShot } from '@/shared/state/selectionStore';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { parseTaskParams } from '@/shared/lib/taskTypeUtils';
import { getSupabaseClient as supabase } from '@/integrations/supabase/client';
import { Task } from '@/types/tasks';
import { GenerationRow } from '@/domains/generation/types';
import { isSegmentVideoTask, extractPairShotGenerationId, checkSegmentConnection } from '../utils/task-utils';
import { getTaskVariantId } from '../utils/getTaskVariantId';
import { travelShotUrl } from '@/shared/lib/tooling/toolRoutes';

type ActionEvent = React.MouseEvent | React.TouchEvent;

interface UseTaskNavigationOptions {
  task: Task;
  shotId: string | null;
  isMobile: boolean;
  /** External hover state — handlers clear it on navigation actions */
  setIsHoveringTaskItem: (hovering: boolean) => void;
  // Video data
  videoOutputs: GenerationRow[] | null;
  isLoadingVideoGen: boolean;
  waitingForVideoToOpen: boolean;
  ensureVideoFetch: () => void;
  triggerVideoOpen: () => void;
  clearVideoWaiting: () => void;
  // Image data
  generationData: GenerationRow | null;
  imageVariantId: string | null;
  // Task content type
  taskInfo: {
    isVideoTask: boolean;
    isImageTask: boolean;
    isCompletedVideoTask: boolean;
  };
  // Lightbox callbacks
  onOpenImageLightbox?: (task: Task, media: GenerationRow, initialVariantId?: string) => void;
  onOpenVideoLightbox?: (task: Task, media: GenerationRow[], videoIndex: number, initialVariantId?: string) => void;
  onCloseLightbox?: () => void;
  // Mobile state
  isMobileActive: boolean;
  onMobileActiveChange?: (taskId: string | null) => void;
}

interface UseTaskNavigationReturn {
  handleCheckProgress: () => Promise<void>;
  handleViewVideo: (e: ActionEvent) => Promise<void>;
  handleViewImage: (e: ActionEvent) => void;
  handleVisitShot: (e: ActionEvent) => void;
  handleMobileTap: (e: React.MouseEvent) => void;
  progressPercent: number | null;
}

/**
 * Hook that consolidates all navigation/action handlers for TaskItem.
 *
 * Handles: check-progress, view-video, view-image, visit-shot, mobile-tap,
 * and auto-open-lightbox-on-video-load.
 *
 * Hover state is managed externally (component-level) and passed in so that
 * useVideoGenerations can also read it for lazy-fetch triggering.
 */
export function useTaskNavigation({
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
}: UseTaskNavigationOptions): UseTaskNavigationReturn {
  const { selectedProjectId, setSelectedProjectId } = useProject();
  const { setActiveTaskId, setIsTasksPaneOpen } = usePanes();
  const { setCurrentShotId } = useCurrentShot();
  const navigate = useNavigate();

  const [progressPercent, setProgressPercent] = useState<number | null>(null);
  const progressTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (progressTimeoutRef.current) {
        clearTimeout(progressTimeoutRef.current);
      }
    };
  }, []);

  // Auto-open lightbox when video data loads after clicking
  useEffect(() => {
    if (waitingForVideoToOpen && !isLoadingVideoGen) {
      if (videoOutputs && videoOutputs.length > 0) {
        const initialVariantId = getTaskVariantId(videoOutputs[0]);
        if (onOpenVideoLightbox) {
          onOpenVideoLightbox(task, videoOutputs, 0, initialVariantId);
        }
        clearVideoWaiting();
      } else {
        // Query finished but no video found - show error
        normalizeAndPresentError(new Error(`Video query completed but no outputs found for task: ${task.id}`), { context: 'useTaskNavigation' });
        toast({
          title: 'Video not found',
          description: 'Could not locate the video output for this task.',
          variant: 'destructive',
        });
        clearVideoWaiting();
      }
    }
  }, [videoOutputs, waitingForVideoToOpen, isLoadingVideoGen, onOpenVideoLightbox, task, clearVideoWaiting, toast]);

  /** Switch to the task's project if it differs from the currently selected project */
  const switchToTaskProjectIfNeeded = useCallback(() => {
    if (task.projectId && task.projectId !== selectedProjectId) {
      setSelectedProjectId(task.projectId);
    }
  }, [task.projectId, selectedProjectId, setSelectedProjectId]);

  /** Navigate to a shot in the travel-between-images tool */
  const navigateToShot = useCallback(
    (targetShotId: string, state?: Record<string, unknown>) => {
      switchToTaskProjectIfNeeded();
      setCurrentShotId(targetShotId);
      navigate(travelShotUrl(targetShotId), {
        state: { fromShotClick: true, ...state },
      });
    },
    [switchToTaskProjectIfNeeded, setCurrentShotId, navigate],
  );

  // ---------------------------------------------------------------------------
  // handleCheckProgress
  // ---------------------------------------------------------------------------
  const handleCheckProgress = useCallback(async () => {
    const taskProjectId = task.projectId;
    if (!taskProjectId) return;

    const params = parseTaskParams(task.params);
    const orchestratorDetails = (params.orchestrator_details || {}) as Record<string, unknown>;
    const orchestratorId = task.id;
    const runId =
      (orchestratorDetails.run_id as string) ||
      (params.run_id as string) ||
      (params.orchestrator_run_id as string);

    try {
      // Build query filters - match the backend's findSiblingSegments logic
      const filters: string[] = [
        `params->>orchestrator_task_id_ref.eq.${orchestratorId}`,
        `params->>orchestrator_task_id.eq.${orchestratorId}`,
        `params->orchestrator_details->>orchestrator_task_id.eq.${orchestratorId}`,
      ];

      if (runId) {
        filters.push(
          `params->>run_id.eq.${runId}`,
          `params->>orchestrator_run_id.eq.${runId}`,
          `params->orchestrator_details->>run_id.eq.${runId}`,
        );
      }

      const { data: subtasks, error } = await supabase().from('tasks')
        .select('id, status')
        .eq('project_id', taskProjectId)
        .neq('id', task.id)
        .or(filters.join(','));

      if (error) throw error;

      const total = subtasks?.length || 0;
      const completed = subtasks?.filter((t) => t.status === 'Complete').length || 0;
      const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

      setProgressPercent(percent);
      if (progressTimeoutRef.current) {
        clearTimeout(progressTimeoutRef.current);
      }
      progressTimeoutRef.current = setTimeout(() => setProgressPercent(null), 5000);
    } catch (error) {
      normalizeAndPresentError(error, { context: 'TaskItem', toastTitle: 'Progress Check Failed' });
    }
  }, [task.projectId, task.params, task.id]);

  // ---------------------------------------------------------------------------
  // handleVisitShot
  // ---------------------------------------------------------------------------
  const handleVisitShot = useCallback(
    (e: ActionEvent) => {
      e.stopPropagation();
      e.preventDefault();
      if (!shotId) return;

      setIsHoveringTaskItem(false);
      navigateToShot(shotId);
    },
    [shotId, navigateToShot, setIsHoveringTaskItem],
  );

  // ---------------------------------------------------------------------------
  // handleViewVideo
  // ---------------------------------------------------------------------------
  const handleViewVideo = useCallback(
    async (e: ActionEvent) => {
      e.stopPropagation();
      e.preventDefault();
      setIsHoveringTaskItem(false);

      // For segment videos, try to open in shot context for full timeline integration
      if (isSegmentVideoTask(task) && shotId) {
        const pairShotGenerationId = extractPairShotGenerationId(task);
        const segmentConnection = await checkSegmentConnection(pairShotGenerationId, shotId);

        if (!segmentConnection.ok) {
          normalizeAndPresentError(new Error(segmentConnection.error), {
            context: 'TaskItem.checkSegmentConnection',
            showToast: false,
          });
        } else if (segmentConnection.connected) {
          onCloseLightbox?.();
          navigateToShot(shotId, { openSegmentSlot: pairShotGenerationId });
          return;
        }
        // Segment is orphaned - fall through to simple video viewer
      }

      // Default path: simple video lightbox
      if (onOpenVideoLightbox && videoOutputs && videoOutputs.length > 0) {
        const initialVariantId = getTaskVariantId(videoOutputs[0]);
        onOpenVideoLightbox(task, videoOutputs, 0, initialVariantId);
      } else {
        if (!isMobile) {
          setActiveTaskId(task.id);
          setIsTasksPaneOpen(true);
        }
        triggerVideoOpen();
      }
    },
    [
      task,
      shotId,
      videoOutputs,
      isMobile,
      onOpenVideoLightbox,
      onCloseLightbox,
      navigateToShot,
      triggerVideoOpen,
      setActiveTaskId,
      setIsTasksPaneOpen,
      setIsHoveringTaskItem,
    ],
  );

  // ---------------------------------------------------------------------------
  // handleViewImage
  // ---------------------------------------------------------------------------
  const handleViewImage = useCallback(
    (e: ActionEvent) => {
      e.stopPropagation();
      e.preventDefault();
      setIsHoveringTaskItem(false);

      if (generationData && onOpenImageLightbox) {
        const initialVariantId = getTaskVariantId(generationData, imageVariantId);
        onOpenImageLightbox(task, generationData, initialVariantId);
      }
    },
    [task, generationData, imageVariantId, onOpenImageLightbox, setIsHoveringTaskItem],
  );

  // ---------------------------------------------------------------------------
  // handleMobileTap
  // ---------------------------------------------------------------------------
  const handleMobileTap = useCallback(
    (e: React.MouseEvent) => {
      if (!isMobile) return;

      e.stopPropagation();
      e.preventDefault();

      const hasActionableContent =
        taskInfo.isCompletedVideoTask ||
        (taskInfo.isVideoTask && shotId) ||
        (taskInfo.isImageTask && generationData);

      if (hasActionableContent) {
        if (isMobileActive) {
          if (taskInfo.isCompletedVideoTask && onOpenVideoLightbox && videoOutputs && videoOutputs.length > 0) {
            onMobileActiveChange?.(null);
            const initialVariantId = getTaskVariantId(videoOutputs[0]);
            onOpenVideoLightbox(task, videoOutputs, 0, initialVariantId);
            return;
          }

          if (taskInfo.isVideoTask && shotId) {
            onMobileActiveChange?.(null);
            setCurrentShotId(shotId);
            navigate(travelShotUrl(shotId), { state: { fromShotClick: true } });
            return;
          }

          if (taskInfo.isImageTask && generationData) {
            onMobileActiveChange?.(null);
            // Navigate to shot context if applicable
            if (shotId) {
              onCloseLightbox?.();
              switchToTaskProjectIfNeeded();
              const variantId = getTaskVariantId(generationData, imageVariantId);
              setCurrentShotId(shotId);
              navigate(travelShotUrl(shotId), {
                state: {
                  fromShotClick: true,
                  openImageGenerationId: generationData.generation_id || generationData.id,
                  openImageVariantId: variantId,
                },
              });
              return;
            }
            if (onOpenImageLightbox) {
              const initialVariantId = getTaskVariantId(generationData, imageVariantId);
              onOpenImageLightbox(task, generationData, initialVariantId);
            }
            return;
          }
        } else {
          onMobileActiveChange?.(task.id);
          if (taskInfo.isVideoTask) {
            ensureVideoFetch();
          }
          return;
        }
      }

      onMobileActiveChange?.(isMobileActive ? null : task.id);
    },
    [
      isMobile,
      isMobileActive,
      task,
      shotId,
      videoOutputs,
      generationData,
      imageVariantId,
      taskInfo,
      onOpenVideoLightbox,
      onOpenImageLightbox,
      onCloseLightbox,
      onMobileActiveChange,
      ensureVideoFetch,
      switchToTaskProjectIfNeeded,
      setCurrentShotId,
      navigate,
    ],
  );

  return {
    handleCheckProgress,
    handleViewVideo,
    handleViewImage,
    handleVisitShot,
    handleMobileTap,
    progressPercent,
  };
}
