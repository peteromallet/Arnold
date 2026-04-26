import { useMemo } from 'react';
import { useGetTask } from '@/shared/hooks/tasks/useTasks';
import {
  getSourceTaskIdLegacyCompatible,
  hasOrchestratorDetails,
} from '@/shared/lib/taskIdHelpers';
import type { TaskDetailsData } from '../../types';

interface VariantTaskLike {
  params?: Record<string, unknown> | null;
}

interface UseVariantSourceTaskInput {
  projectId?: string | null;
  activeVariant: VariantTaskLike | null;
  taskDetailsData: TaskDetailsData | undefined;
}

export function useVariantSourceTask(input: UseVariantSourceTaskInput) {
  const { projectId, activeVariant, taskDetailsData } = input;

  const { variantSourceTaskId, variantHasOrchestratorDetails } = useMemo(() => {
    const variantParams = activeVariant?.params as Record<string, unknown> | undefined;
    return {
      variantSourceTaskId: getSourceTaskIdLegacyCompatible(variantParams),
      variantHasOrchestratorDetails: hasOrchestratorDetails(variantParams),
    };
  }, [activeVariant?.params]);

  const sourceTaskLookupId = (
    variantSourceTaskId
    && projectId
    && variantSourceTaskId !== taskDetailsData?.taskId
    && !variantHasOrchestratorDetails
  )
    ? variantSourceTaskId
    : '';

  const {
    data: variantSourceTask,
    error: variantSourceTaskQueryError,
    isLoading: isLoadingVariantTask,
  } = useGetTask(sourceTaskLookupId, projectId);
  const variantSourceTaskError = useMemo(() => {
    if (!variantSourceTaskQueryError) {
      return null;
    }
    return variantSourceTaskQueryError instanceof Error
      ? variantSourceTaskQueryError
      : new Error('Failed to fetch source task');
  }, [variantSourceTaskQueryError]);

  return {
    variantSourceTaskId,
    variantHasOrchestratorDetails,
    variantSourceTask,
    variantSourceTaskError,
    isLoadingVariantTask,
  };
}
