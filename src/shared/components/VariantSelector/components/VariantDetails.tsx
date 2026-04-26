/**
 * VariantDetails Component
 *
 * Shared component that fetches real task data for a variant and renders
 * GenerationDetails. Used by both VariantHoverDetails (desktop) and
 * MobileVariantDetails (mobile modal).
 */

import React from 'react';
import { GenerationDetails } from '@/domains/generation/components/GenerationDetails';
import type { LoraModel } from '@/domains/lora/types/lora';
import { getSourceTaskIdLegacyCompatible } from '@/shared/lib/taskIdHelpers';
import { useGetTask } from '@/shared/hooks/tasks/useTasks';
import type { GenerationVariant } from '@/shared/hooks/variants/useVariants';
import { TASK_STATUS } from '@/types/tasks';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';

interface VariantDetailsProps {
  variant: GenerationVariant;
  availableLoras?: LoraModel[];
}

export const VariantDetails: React.FC<VariantDetailsProps> = ({ variant, availableLoras }) => {
  const { selectedProjectId } = useProjectSelectionContext();
  const variantParams = variant.params;
  const sourceTaskId = getSourceTaskIdLegacyCompatible(variantParams);
  const { data: task, isLoading } = useGetTask(sourceTaskId || '', selectedProjectId ?? null);
  const taskTypeFromParams = typeof variantParams?.task_type === 'string'
    ? variantParams.task_type
    : (typeof variantParams?.created_from === 'string' ? variantParams.created_from : 'video_generation');
  const safeVariantParams = variantParams ?? {};

  if (task && !isLoading) {
    return (
      <GenerationDetails
        task={task}
        inputImages={[]}
        variant="hover"
        isMobile={false}
        availableLoras={availableLoras}
        showCopyButtons={true}
      />
    );
  }

  return (
    <GenerationDetails
      task={{
        id: variant.id,
        taskType: taskTypeFromParams,
        params: safeVariantParams,
        status: TASK_STATUS.COMPLETE,
        createdAt: variant.created_at,
        projectId: '',
      }}
      inputImages={[]}
      variant="hover"
      isMobile={false}
      availableLoras={availableLoras}
      showCopyButtons={true}
    />
  );
};
