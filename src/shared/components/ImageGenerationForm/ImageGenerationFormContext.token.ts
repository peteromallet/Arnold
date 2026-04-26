import { createContext } from 'react';
import type { ImageGenerationFormContextValue } from './ImageGenerationFormContext.types';

export const ImageGenerationFormUIContext = createContext<
  Pick<ImageGenerationFormContextValue, 'uiState' | 'uiActions'> | null
>(null);
export const ImageGenerationFormCoreContext = createContext<ImageGenerationFormContextValue['core'] | null>(null);
export const ImageGenerationFormPromptsContext = createContext<
  Pick<ImageGenerationFormContextValue, 'prompts' | 'promptHandlers'> | null
>(null);
export const ImageGenerationFormReferencesContext = createContext<
  Pick<ImageGenerationFormContextValue, 'references' | 'referenceHandlers'> | null
>(null);
export const ImageGenerationFormLorasContext = createContext<
  Pick<ImageGenerationFormContextValue, 'loras' | 'loraHandlers'> | null
>(null);
