import { useContext } from 'react';
import {
  ImageGenerationFormCoreContext,
  ImageGenerationFormLorasContext,
  ImageGenerationFormPromptsContext,
  ImageGenerationFormReferencesContext,
  ImageGenerationFormUIContext,
} from '../ImageGenerationFormContext.token';
import type { ImageGenerationFormContextValue } from '../ImageGenerationFormContext.types';

function requireImageGenerationFormContext<T>(context: T | null, hookName: string): T {
  if (!context) {
    throw new Error(
      `${hookName} must be used within ImageGenerationFormProvider`,
    );
  }
  return context;
}

export function useFormUIContext() {
  const { uiState, uiActions } = requireImageGenerationFormContext(
    useContext(ImageGenerationFormUIContext),
    'useFormUIContext',
  );
  return { uiState, uiActions };
}

export function useFormCoreContext() {
  return requireImageGenerationFormContext(
    useContext(ImageGenerationFormCoreContext),
    'useFormCoreContext',
  );
}

export function useFormPromptsContext() {
  const { prompts, promptHandlers } = requireImageGenerationFormContext(
    useContext(ImageGenerationFormPromptsContext),
    'useFormPromptsContext',
  );
  return { ...prompts, ...promptHandlers };
}

export function useFormReferencesContext() {
  const { references, referenceHandlers } = requireImageGenerationFormContext(
    useContext(ImageGenerationFormReferencesContext),
    'useFormReferencesContext',
  );
  return { ...references, ...referenceHandlers };
}

export function useFormLorasContext() {
  const { loras, loraHandlers } = requireImageGenerationFormContext(
    useContext(ImageGenerationFormLorasContext),
    'useFormLorasContext',
  );
  return { ...loras, ...loraHandlers };
}
