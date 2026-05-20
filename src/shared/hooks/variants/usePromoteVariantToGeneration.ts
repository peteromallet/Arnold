/**
 * usePromoteVariantToGeneration Hook
 *
 * Disabled legacy flow for creating a standalone generation from a variant.
 *
 * Used by:
 * - VariantSelector "Make new image" button
 * - ShotSelectorControls "Add as new image to shot" button
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { Json } from '@/integrations/supabase/jsonTypes';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { generationQueryKeys } from '@/shared/lib/queryKeys/generations';

export const VARIANT_PROMOTION_UNSUPPORTED_CODE = 'variant_promotion_unsupported';

export class VariantPromotionUnsupportedError extends Error {
  readonly code = VARIANT_PROMOTION_UNSUPPORTED_CODE;

  constructor() {
    super(
      'Creating a standalone generation from a variant is disabled because the auto-variant trigger no longer runs.',
    );
    this.name = 'VariantPromotionUnsupportedError';
  }
}

export function isVariantPromotionUnsupportedError(error: unknown): error is VariantPromotionUnsupportedError {
  return error instanceof VariantPromotionUnsupportedError
    || (
      typeof error === 'object'
      && error !== null
      && 'code' in error
      && (error as { code?: unknown }).code === VARIANT_PROMOTION_UNSUPPORTED_CODE
    );
}

interface PromoteVariantParams {
  /** ID of the variant to promote */
  variantId: string;
  /** Project ID for the new generation */
  projectId: string;
}

interface PromotedGeneration {
  id: string;
  location: string;
  thumbnail_url: string | null;
  type: string;
  project_id: string;
  based_on: string;
  params: Record<string, Json | undefined>;
}

/**
 * Hook for promoting a variant to a standalone generation
 */
export const usePromoteVariantToGeneration = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (_params: PromoteVariantParams): Promise<PromotedGeneration> => {
      throw new VariantPromotionUnsupportedError();
    },

    onSuccess: (data) => {
      // Invalidate generations queries to show the new generation in galleries
      queryClient.invalidateQueries({ queryKey: generationQueryKeys.all });
      queryClient.invalidateQueries({ queryKey: generationQueryKeys.byProjectAll });

      // Invalidate derived generations for the source
      if (data.based_on) {
        queryClient.invalidateQueries({
          queryKey: generationQueryKeys.derivedGenerations(data.based_on),
        });
      }
    },

    onError: (error) => {
      if (isVariantPromotionUnsupportedError(error)) {
        return;
      }

      normalizeAndPresentError(error, { context: 'usePromoteVariantToGeneration', toastTitle: 'Failed to create new image from variant' });
    },
  });
};

// NOTE: Default export removed - use named export { usePromoteVariantToGeneration } instead
