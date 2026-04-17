/**
 * ImageGenerationFormContext - Shared state for ImageGenerationForm sections
 *
 * Provides commonly-used state and actions to sub-components without prop drilling.
 * Sections pull from context instead of receiving 20-30 props each.
 *
 * Pattern from refactoring_patterns.md "Complex Editor Pattern":
 * - Sections pull from context → minimal props
 * - UI state from reducer → predictable updates
 * - Handlers memoized → stable references
 */

import React, { useMemo } from 'react';
import {
  ImageGenerationFormCoreContext,
  ImageGenerationFormLorasContext,
  ImageGenerationFormPromptsContext,
  ImageGenerationFormReferencesContext,
  ImageGenerationFormUIContext,
} from './ImageGenerationFormContext.token';
import type { ImageGenerationFormUIState, FormUIActions } from './state/useFormUIState';
import type {
  FormCoreState,
  FormLoraHandlers,
  FormLoraState,
  FormPromptHandlers,
  FormPromptState,
  FormReferenceHandlers,
  FormReferenceState,
  ImageGenerationFormContextValue,
} from './ImageGenerationFormContext.types';

;

// ============================================================================
// Context
// ============================================================================

export {
  useFormCoreContext,
  useFormLorasContext,
  useFormPromptsContext,
  useFormReferencesContext,
  useFormUIContext,
  
} from './hooks/useImageGenerationFormContexts';

// ============================================================================
// Provider
// ============================================================================

interface ImageGenerationFormProviderProps {
  value: ImageGenerationFormContextValue;
  children: React.ReactNode;
}

export function ImageGenerationFormProvider({
  value,
  children,
}: ImageGenerationFormProviderProps) {
  return (
    <ImageGenerationFormUIContext.Provider value={{ uiState: value.uiState, uiActions: value.uiActions }}>
      <ImageGenerationFormCoreContext.Provider value={value.core}>
        <ImageGenerationFormPromptsContext.Provider
          value={{ prompts: value.prompts, promptHandlers: value.promptHandlers }}
        >
          <ImageGenerationFormReferencesContext.Provider
            value={{ references: value.references, referenceHandlers: value.referenceHandlers }}
          >
            <ImageGenerationFormLorasContext.Provider
              value={{ loras: value.loras, loraHandlers: value.loraHandlers }}
            >
              {children}
            </ImageGenerationFormLorasContext.Provider>
          </ImageGenerationFormReferencesContext.Provider>
        </ImageGenerationFormPromptsContext.Provider>
      </ImageGenerationFormCoreContext.Provider>
    </ImageGenerationFormUIContext.Provider>
  );
}

// ============================================================================
// Context Value Builder Hook
// ============================================================================

interface UseContextValueProps {
  uiState: ImageGenerationFormUIState;
  uiActions: FormUIActions;
  core: FormCoreState;
  prompts: FormPromptState;
  promptHandlers: FormPromptHandlers;
  references: FormReferenceState;
  referenceHandlers: FormReferenceHandlers;
  loras: FormLoraState;
  loraHandlers: FormLoraHandlers;
}

/**
 * Builds memoized context value from component state.
 * Call this in the main component and pass to ImageGenerationFormProvider.
 */
export function useContextValue(props: UseContextValueProps): ImageGenerationFormContextValue {
  const {
    uiState,
    uiActions,
    core,
    prompts,
    promptHandlers,
    references,
    referenceHandlers,
    loras,
    loraHandlers,
  } = props;

  return useMemo<ImageGenerationFormContextValue>(() => ({
    uiState,
    uiActions,
    core,
    prompts,
    promptHandlers,
    references,
    referenceHandlers,
    loras,
    loraHandlers,
  }), [
    uiState,
    uiActions,
    core,
    prompts,
    promptHandlers,
    references,
    referenceHandlers,
    loras,
    loraHandlers,
  ]);
}
