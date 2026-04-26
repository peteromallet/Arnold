import { useLightboxOpenState } from '@/shared/state/lightboxOpenState';
import { usePanesStore } from '@/shared/state/panesStore';

/**
 * Calculates side-pane handle offset from the generations pane state.
 */
export const useBottomOffset = (): number => {
  const isGenerationsPaneLocked = usePanesStore((state) => state.isGenerationsPaneLocked);
  const isGenerationsPaneOpen = usePanesStore((state) => state.isGenerationsPaneOpen);
  const effectiveGenerationsPaneHeight = usePanesStore((state) => state.effectiveGenerationsPaneHeight);
  const isLightboxOpen = useLightboxOpenState();

  if (isLightboxOpen) return 0;

  return (isGenerationsPaneLocked || isGenerationsPaneOpen)
    ? effectiveGenerationsPaneHeight
    : 0;
};
