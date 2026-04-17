import { useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { getSupabaseClientResult } from '@/integrations/supabase/client';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { useOnboarding } from '@/shared/hooks/useOnboarding';
import { useUserUIState } from '@/shared/hooks/useUserUIState';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { useProductTour } from '@/shared/hooks/useProductTour';

export function useOnboardingFlow() {
  const { showOnboardingModal, closeOnboardingModal } = useOnboarding();
  const navigate = useNavigate();
  const { selectedProjectId } = useProjectSelectionContext();
  const { startTour } = useProductTour();
  const tourStartTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTourStartTimeout = useCallback(() => {
    if (tourStartTimeoutRef.current) {
      clearTimeout(tourStartTimeoutRef.current);
      tourStartTimeoutRef.current = null;
    }
  }, []);

  // Handle onboarding modal close - navigate to Getting Started shot, then start tour
  const handleOnboardingClose = useCallback(async () => {
    closeOnboardingModal();

    if (selectedProjectId) {
      try {
        const clientResult = getSupabaseClientResult();
        if (!clientResult.ok) {
          normalizeAndPresentError(clientResult.error, {
            context: 'useOnboardingFlow.supabaseUnavailable',
            showToast: false,
          });
          return;
        }
        const client = clientResult.client;
        const { data: shot } = await client
          .from('shots')
          .select('id')
          .eq('project_id', selectedProjectId)
          .eq('name', 'Getting Started')
          .maybeSingle();

        if (shot) {
          navigate(`/tools/travel-between-images?shot=${shot.id}`);
          clearTourStartTimeout();
          tourStartTimeoutRef.current = setTimeout(() => {
            tourStartTimeoutRef.current = null;
            startTour();
          }, 1000);
        }
      } catch (err) {
        normalizeAndPresentError(err, {
          context: 'useOnboardingFlow.handleOnboardingClose',
          showToast: false,
        });
      }
    }
  }, [clearTourStartTimeout, closeOnboardingModal, selectedProjectId, navigate, startTour]);

  // Preload user settings to warm the cache for the welcome modal
  useUserUIState('generationMethods', { onComputer: true, inCloud: true });

  // Preload ProductTour chunk when onboarding is shown
  useEffect(() => {
    if (showOnboardingModal) {
      import('@/shared/components/ProductTour').catch((error) => {
        normalizeAndPresentError(error, {
          context: 'useOnboardingFlow.preloadProductTour',
          showToast: false,
        });
      });
    }
  }, [showOnboardingModal]);

  useEffect(() => clearTourStartTimeout, [clearTourStartTimeout]);

  return {
    showOnboardingModal,
    handleOnboardingClose,
  };
}
