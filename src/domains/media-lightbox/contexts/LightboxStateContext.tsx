/**
 * LightboxStateContext
 *
 * Provides shared state to deeply-nested lightbox components without prop drilling.
 * Organized into logical domains accessible via focused hooks:
 * - useLightboxCore() - onClose, readOnly, isMobile, selectedProjectId
 * - useLightboxMedia() - media, isVideo, effectiveUrls, dimensions
 * - useLightboxVariants() - variants, activeVariant, variant actions
 * - useLightboxNavigation() - navigation state and handlers
 *
 * Components should prefer these hooks over prop drilling for commonly-used values.
 */

import React, { createContext, useContext, RefObject } from 'react';
import type { GenerationRow } from '@/domains/generation/types';
import type { GenerationVariant } from '@/shared/hooks/variants/useVariants';
import type { CurrentSegmentImagesData } from '@/shared/components/VariantSelector/variantSourceImages';

// ============================================================================
// Core State
// ============================================================================

interface LightboxCoreState {
  onClose: () => void;
  readOnly: boolean;
  isMobile: boolean;
  isTabletOrLarger: boolean;
  selectedProjectId: string | null;
  actualGenerationId: string | null;
}

// ============================================================================
// Media State
// ============================================================================

interface LightboxMediaState {
  media: GenerationRow;
  isVideo: boolean;
  effectiveMediaUrl: string;
  effectiveVideoUrl: string;
  effectiveImageDimensions: { width: number; height: number } | null;
  imageDimensions: { width: number; height: number } | null;
  setImageDimensions: (dims: { width: number; height: number }) => void;
}

// ============================================================================
// Variant State
// ============================================================================

interface LightboxVariantState {
  variants: GenerationVariant[];
  activeVariant: GenerationVariant | null;
  primaryVariant: GenerationVariant | null;
  isLoadingVariants: boolean;
  // Handler-style names for UI components
  handleVariantSelect: (id: string) => void;
  handleMakePrimary: (id: string) => Promise<void>;
  handleDeleteVariant: (id: string) => Promise<void>;
  onLoadVariantSettings?: (variantParams: Record<string, unknown>) => void;
  onLoadVariantImages?: (variant: GenerationVariant) => void;
  currentSegmentImages?: CurrentSegmentImagesData;
  // Promotion
  promoteSuccess: boolean;
  isPromoting: boolean;
  handlePromoteToGeneration: (variantId: string) => Promise<void>;
  // Make main variant
  isMakingMainVariant: boolean;
  canMakeMainVariant: boolean;
  handleMakeMainVariant: () => Promise<void>;
  // Pending/unviewed counts
  pendingTaskCount: number;
  unviewedVariantCount: number;
  onMarkAllViewed: () => void;
  variantsSectionRef: RefObject<HTMLDivElement> | null;
}

// ============================================================================
// Navigation State
// ============================================================================

interface LightboxNavigationState {
  showNavigation: boolean;
  hasNext: boolean;
  hasPrevious: boolean;
  handleSlotNavNext: () => void;
  handleSlotNavPrev: () => void;
  swipeNavigation: {
    swipeHandlers: Record<string, unknown>;
    isSwiping: boolean;
    swipeOffset: number;
  };
}

// ============================================================================
// Combined Context Value
// ============================================================================

interface LightboxStateValue {
  core: LightboxCoreState;
  media: LightboxMediaState;
  variants: LightboxVariantState;
  navigation: LightboxNavigationState;
}

const LightboxCoreContext = createContext<LightboxCoreState | null>(null);
const LightboxMediaContext = createContext<LightboxMediaState | null>(null);
const LightboxVariantsContext = createContext<LightboxVariantState | null>(null);
const LightboxNavigationContext = createContext<LightboxNavigationState | null>(null);

// ============================================================================
// Provider Component
// ============================================================================

interface LightboxStateProviderProps {
  children: React.ReactNode;
  value: LightboxStateValue;
}

export const LightboxStateProvider: React.FC<LightboxStateProviderProps> = ({
  children,
  value,
}) => {
  return (
    <LightboxCoreContext.Provider value={value.core}>
      <LightboxMediaContext.Provider value={value.media}>
        <LightboxVariantsContext.Provider value={value.variants}>
          <LightboxNavigationContext.Provider value={value.navigation}>
            {children}
          </LightboxNavigationContext.Provider>
        </LightboxVariantsContext.Provider>
      </LightboxMediaContext.Provider>
    </LightboxCoreContext.Provider>
  );
};

// ============================================================================
// Consumer Hooks - Safe versions only (return defaults outside provider)
// ============================================================================

// Note: Non-safe versions (useLightboxState, useLightboxCore, etc.) are not
// exported as they are not used. All internal consumers use the Safe versions
// for safe operation outside the provider.

// ============================================================================
// Safe Hooks (for use outside provider - returns defaults)
// ============================================================================

const EMPTY_CORE: LightboxCoreState = {
  onClose: () => {},
  readOnly: true,
  isMobile: false,
  isTabletOrLarger: true,
  selectedProjectId: null,
  actualGenerationId: null,
};

const EMPTY_MEDIA: LightboxMediaState = {
  media: {} as GenerationRow,
  isVideo: false,
  effectiveMediaUrl: '',
  effectiveVideoUrl: '',
  effectiveImageDimensions: null,
  imageDimensions: null,
  setImageDimensions: () => {},
};

const EMPTY_VARIANTS: LightboxVariantState = {
  variants: [],
  activeVariant: null,
  primaryVariant: null,
  isLoadingVariants: false,
  handleVariantSelect: () => {},
  handleMakePrimary: async () => {},
  handleDeleteVariant: async () => {},
  onLoadVariantSettings: undefined,
  onLoadVariantImages: undefined,
  currentSegmentImages: undefined,
  promoteSuccess: false,
  isPromoting: false,
  handlePromoteToGeneration: async () => {},
  isMakingMainVariant: false,
  canMakeMainVariant: false,
  handleMakeMainVariant: async () => {},
  pendingTaskCount: 0,
  unviewedVariantCount: 0,
  onMarkAllViewed: () => {},
  variantsSectionRef: null,
};

const EMPTY_NAVIGATION: LightboxNavigationState = {
  showNavigation: false,
  hasNext: false,
  hasPrevious: false,
  handleSlotNavNext: () => {},
  handleSlotNavPrev: () => {},
  swipeNavigation: {
    swipeHandlers: {},
    isSwiping: false,
    swipeOffset: 0,
  },
};

/**
 * Safe version of useLightboxCore that returns defaults when used outside provider.
 * Use this in components that may render outside the lightbox context.
 */
export function useLightboxCoreSafe(): LightboxCoreState {
  const context = useContext(LightboxCoreContext);
  return context ?? EMPTY_CORE;
}

/**
 * Safe version of useLightboxMedia that returns defaults when used outside provider.
 */
export function useLightboxMediaSafe(): LightboxMediaState {
  const context = useContext(LightboxMediaContext);
  return context ?? EMPTY_MEDIA;
}

/**
 * Safe version of useLightboxVariants that returns defaults when used outside provider.
 */
export function useLightboxVariantsSafe(): LightboxVariantState {
  const context = useContext(LightboxVariantsContext);
  return context ?? EMPTY_VARIANTS;
}

/**
 * Safe version of useLightboxNavigation that returns defaults when used outside provider.
 */
export function useLightboxNavigationSafe(): LightboxNavigationState {
  const context = useContext(LightboxNavigationContext);
  return context ?? EMPTY_NAVIGATION;
}

// ============================================================================
// Export Types
// ============================================================================

export type {
  LightboxStateValue,
  LightboxCoreState,
  LightboxVariantState,
};

// Note: Default export removed as it was not used externally.
