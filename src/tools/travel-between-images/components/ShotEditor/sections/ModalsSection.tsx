/**
 * ModalsSection - Renders all modals used by ShotSettingsEditor
 *
 * Keeps modal rendering separate from main component logic.
 */

import React from 'react';
import { LoraSelectorModal } from '@/domains/lora/components';
import type { LoraModel } from '@/domains/lora/types/lora';
import { mapSelectedLorasForModal } from '@/shared/components/lora/mapSelectedLorasForModal';
import { SettingsModal } from '@/shared/components/SettingsModal/SettingsModal';
import { useShotSettingsGeneration } from '../ShotSettingsContext';
import type { ModalSelectedLora } from '../types/modalLora';
import { getModelSpec, type SelectedModel } from '@/tools/travel-between-images/settings';

interface ModalsSectionProps {
  // LoRA modal
  isLoraModalOpen: boolean;
  onLoraModalClose: () => void;
  onAddLora: (lora: LoraModel, isManualAction?: boolean, initialStrength?: number) => void;
  onRemoveLora: (loraId: string) => void;
  onUpdateLoraStrength: (loraId: string, strength: number) => void;
  selectedLoras: ModalSelectedLora[];
  selectedModel: SelectedModel;

  // Settings modal
  isSettingsModalOpen: boolean;
  onSettingsModalOpenChange: (open: boolean) => void;
}

export const ModalsSection: React.FC<ModalsSectionProps> = ({
  isLoraModalOpen,
  onLoraModalClose,
  onAddLora,
  onRemoveLora,
  onUpdateLoraStrength,
  selectedLoras,
  selectedModel,
  isSettingsModalOpen,
  onSettingsModalOpenChange,
}) => {
  const { availableLoras } = useShotSettingsGeneration();

  return (
    <>
      <LoraSelectorModal
        isOpen={isLoraModalOpen}
        onClose={onLoraModalClose}
        loras={availableLoras}
        onAddLora={onAddLora}
        onRemoveLora={onRemoveLora}
        onUpdateLoraStrength={onUpdateLoraStrength}
        selectedLoras={mapSelectedLorasForModal(selectedLoras, availableLoras)}
        loraType={getModelSpec(selectedModel).loraFamily}
      />

      <SettingsModal
        isOpen={isSettingsModalOpen}
        onOpenChange={onSettingsModalOpenChange}
      />
    </>
  );
};
