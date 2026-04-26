import React, { useState, useCallback } from 'react';
import { GenerationRow } from '@/domains/generation/types';
import { DerivedNavContext } from '../types';
import { transformExternalGeneration } from '../utils/external-generation-utils';
import { getSupabaseClient as supabase } from '@/integrations/supabase/client';
import { useAddImageToShot } from '@/shared/hooks/shots';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { useAppEventListener } from '@/shared/lib/typedEvents';
import { expandShotData } from '@/shared/lib/shots/shotData';

/** Generation row with JSONB shot_data associations */
interface GenerationWithShotData {
  shot_data?: Record<string, unknown> | null;
  [key: string]: unknown;
}

interface UseExternalGenerationsProps {
  selectedShotId?: string;
  optimisticOrder: GenerationRow[];
  images: GenerationRow[];
  setLightboxIndexRef: React.MutableRefObject<(index: number) => void>;
}

export function useExternalGenerations({
  selectedShotId,
  optimisticOrder,
  images,
  setLightboxIndexRef
}: UseExternalGenerationsProps) {
  const [externalGenerations, setExternalGenerations] = useState<GenerationRow[]>([]);
  const [tempDerivedGenerations, setTempDerivedGenerations] = useState<GenerationRow[]>([]);
  const [derivedNavContext, setDerivedNavContext] = useState<DerivedNavContext | null>(null);
  const [externalGenLightboxSelectedShot, setExternalGenLightboxSelectedShot] = useState<string | undefined>(selectedShotId);
  
  const { selectedProjectId } = useProjectSelectionContext();
  const { mutateAsync: addToShotMutation } = useAddImageToShot();
  const { mutateAsyncWithoutPosition: addToShotWithoutPositionMutation } = useAddImageToShot();
  
  // Listen for realtime generation updates
  const handleGenerationUpdate = useCallback(async (detail: { payloads: Array<{ generationId: string; upscaleCompleted?: boolean }> }) => {
    const { payloads = [] } = detail || {};

    for (const payload of payloads) {
      const { generationId, upscaleCompleted } = payload;

      if (!generationId) continue;

      const isInExternal = externalGenerations.some(gen => gen.id === generationId);
      const isInTempDerived = tempDerivedGenerations.some(gen => gen.id === generationId);

      if (upscaleCompleted && (isInExternal || isInTempDerived)) {

        try {
          const { data, error } = await supabase().from('generations')
            .select('*')
            .eq('id', generationId)
            .single();

          if (error) throw error;

          if (data) {
            const shotGenerations = expandShotData(
              (data as unknown as GenerationWithShotData).shot_data,
            );
            const transformedData = transformExternalGeneration(data, shotGenerations);

            if (isInExternal) {
              setExternalGenerations(prev =>
                prev.map(gen => gen.id === generationId ? transformedData : gen)
              );
            }
            if (isInTempDerived) {
              setTempDerivedGenerations(prev =>
                prev.map(gen => gen.id === generationId ? transformedData : gen)
              );
            }
          }
        } catch (err) {
          normalizeAndPresentError(err, { context: 'useExternalGenerations', showToast: false });
        }
      }
    }
  }, [externalGenerations, tempDerivedGenerations]);

  useAppEventListener('realtime:generation-update-batch', handleGenerationUpdate);
  
  // Adapter functions for shot management
  const handleExternalGenAddToShot = useCallback(async (generationId: string, imageUrl?: string, thumbUrl?: string): Promise<boolean> => {
    if (!externalGenLightboxSelectedShot || !selectedProjectId) {
      return false;
    }
    
    try {
      await addToShotMutation({
        shot_id: externalGenLightboxSelectedShot,
        generation_id: generationId,
        imageUrl,
        thumbUrl,
        project_id: selectedProjectId,
      });
      return true;
    } catch (error) {
      normalizeAndPresentError(error, { context: 'useExternalGenerations', toastTitle: 'Failed to add to shot' });
      return false;
    }
  }, [externalGenLightboxSelectedShot, selectedProjectId, addToShotMutation]);
  
  const handleExternalGenAddToShotWithoutPosition = useCallback(async (generationId: string, imageUrl?: string, thumbUrl?: string): Promise<boolean> => {
    if (!externalGenLightboxSelectedShot || !selectedProjectId) {
      return false;
    }
    
    try {
      await addToShotWithoutPositionMutation({
        shot_id: externalGenLightboxSelectedShot,
        generation_id: generationId,
        imageUrl,
        thumbUrl,
        project_id: selectedProjectId,
      });
      return true;
    } catch (error) {
      normalizeAndPresentError(error, { context: 'useExternalGenerations', toastTitle: 'Failed to add to shot' });
      return false;
    }
  }, [externalGenLightboxSelectedShot, selectedProjectId, addToShotWithoutPositionMutation]);
  
  // Handler to fetch and open an external generation
  const handleOpenExternalGeneration = useCallback(async (
    generationId: string,
    derivedContext?: string[]
  ) => {
    
    // Check if generation already exists BEFORE modifying state
    const baseImages = (optimisticOrder && optimisticOrder.length > 0) ? optimisticOrder : (images || []);
    const existingIndex = baseImages.findIndex(img => img.id === generationId);
    
    if (existingIndex !== -1) {
      // Set up derived navigation mode
      if (derivedContext && derivedContext.length > 0) {
        setDerivedNavContext({
          sourceGenerationId: generationId,
          derivedGenerationIds: derivedContext
        });
      } else if (derivedNavContext !== null) {
        setDerivedNavContext(null);
        setTempDerivedGenerations([]);
      }
      setLightboxIndexRef.current(existingIndex);
      return;
    }
    
    const externalIndex = externalGenerations.findIndex(img => img.id === generationId);
    if (externalIndex !== -1) {
      const calculatedIndex = baseImages.length + externalIndex;
      // Set up derived navigation mode
      if (derivedContext && derivedContext.length > 0) {
        setDerivedNavContext({
          sourceGenerationId: generationId,
          derivedGenerationIds: derivedContext
        });
      } else if (derivedNavContext !== null) {
        setDerivedNavContext(null);
        setTempDerivedGenerations([]);
      }
      setLightboxIndexRef.current(calculatedIndex);
      return;
    }
    
    const tempDerivedIndex = tempDerivedGenerations.findIndex(img => img.id === generationId);
    if (tempDerivedIndex !== -1) {
      const calculatedIndex = baseImages.length + externalGenerations.length + tempDerivedIndex;
      // Set up derived navigation mode
      if (derivedContext && derivedContext.length > 0) {
        setDerivedNavContext({
          sourceGenerationId: generationId,
          derivedGenerationIds: derivedContext
        });
        setLightboxIndexRef.current(calculatedIndex);
      } else if (derivedNavContext !== null) {
        // CRITICAL: We're exiting derived mode and the target is IN tempDerived
        
        const targetGeneration = tempDerivedGenerations[tempDerivedIndex];
        const newExternalIndex = externalGenerations.length;
        const newAbsoluteIndex = baseImages.length + newExternalIndex;
        
        // Add to externalGenerations
        setExternalGenerations(prev => [...prev, targetGeneration]);
        
        setLightboxIndexRef.current(newAbsoluteIndex);
        
        // Now safe to clear
        setDerivedNavContext(null);
        setTempDerivedGenerations([]);
      } else {
        // No context change, just update index
        setLightboxIndexRef.current(calculatedIndex);
      }
      return;
    }
    
    // Not found in any existing arrays - need to fetch
    // Set up derived navigation mode BEFORE clearing temp state
    if (derivedContext && derivedContext.length > 0) {
      setDerivedNavContext({
        sourceGenerationId: generationId,
        derivedGenerationIds: derivedContext
      });
    } else if (derivedNavContext !== null) {
      // Update lightbox index to a safe position BEFORE clearing temp derived
      // Point to end of externalGenerations (where new item will be added)
      const newIndex = baseImages.length + externalGenerations.length;
      setLightboxIndexRef.current(newIndex);
      // Now safe to clear without invalidating the index
      setDerivedNavContext(null);
      setTempDerivedGenerations([]);
    }
    
    try {
      const { data, error } = await supabase().from('generations')
        .select('*')
        .eq('id', generationId)
        .single();
      
      if (error) throw error;
      
      if (data) {
        const shotGenerations = expandShotData(
          (data as unknown as GenerationWithShotData).shot_data,
        );
        const transformedData = transformExternalGeneration(data, shotGenerations);
        
        if (derivedContext && derivedContext.length > 0) {
          setTempDerivedGenerations(prev => {
            const existingIdx = prev.findIndex(g => g.id === transformedData.id);
            if (existingIdx !== -1) {
              const newIndex = baseImages.length + externalGenerations.length + existingIdx;
              requestAnimationFrame(() => setLightboxIndexRef.current(newIndex));
              return prev;
            }
            
            const updated = [...prev, transformedData];
            const newIndex = baseImages.length + externalGenerations.length + updated.length - 1;
            requestAnimationFrame(() => setLightboxIndexRef.current(newIndex));
            return updated;
          });
        } else {
          setExternalGenerations(prev => {
            const existingIdx = prev.findIndex(g => g.id === transformedData.id);
            if (existingIdx !== -1) {
              const newIndex = baseImages.length + existingIdx;
              requestAnimationFrame(() => setLightboxIndexRef.current(newIndex));
              return prev;
            }
            
            const updated = [...prev, transformedData];
            const newIndex = baseImages.length + updated.length - 1;
            requestAnimationFrame(() => setLightboxIndexRef.current(newIndex));
            return updated;
          });
        }
      }
    } catch (error) {
      normalizeAndPresentError(error, { context: 'useExternalGenerations', toastTitle: 'Failed to load generation' });
    }
  }, [optimisticOrder, images, externalGenerations, tempDerivedGenerations, derivedNavContext, setLightboxIndexRef]);
  
  return {
    externalGenerations,
    setExternalGenerations,
    tempDerivedGenerations,
    setTempDerivedGenerations,
    derivedNavContext,
    setDerivedNavContext,
    externalGenLightboxSelectedShot,
    setExternalGenLightboxSelectedShot,
    handleExternalGenAddToShot,
    handleExternalGenAddToShotWithoutPosition,
    handleOpenExternalGeneration
  };
}
