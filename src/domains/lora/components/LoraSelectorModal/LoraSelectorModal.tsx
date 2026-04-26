import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs";

import { useExtraLargeModal } from '@/shared/hooks/useModal';
import { useScrollFade } from '@/shared/hooks/useScrollFade';
import { useListResources, useCreateResource, useUpdateResource, useDeleteResource } from '@/features/resources/hooks/useResources';
import { useUserUIState } from '@/shared/hooks/useUserUIState';
import { useOverlayStackApi } from '@/shared/state/overlayStack';

import { LoraSelectorModalProps } from './types';
import { CommunityLorasTab } from './components/CommunityLorasTab';
import { MyLorasTab } from './components/MyLorasTab/MyLorasTab';
import { LoraSelectorFooter } from './components/LoraSelectorFooter';
import { useLoraFilters } from './hooks/useLoraFilters';

export const LoraSelectorModal: React.FC<LoraSelectorModalProps> = ({
  isOpen,
  onClose,
  loras,
  onAddLora,
  onRemoveLora,
  onUpdateLoraStrength,
  selectedLoras,
  loraType,
}) => {
  const contentRef = React.useRef<HTMLDivElement | null>(null);
  const overlayStackApi = useOverlayStackApi();
  const myLorasResource = useListResources('lora');
  const createResource = useCreateResource();
  const updateResource = useUpdateResource();
  const deleteResource = useDeleteResource();

  // Privacy defaults for new LoRAs
  const { value: privacyDefaults } = useUserUIState('privacyDefaults', { resourcesPublic: true, generationsPublic: false });

  const {
    activeTab,
    setActiveTab,
    editingLora,
    handleEdit,
    clearEdit,
    switchToBrowse,
    showMyLorasOnly,
    setShowMyLorasOnly,
    showAddedLorasOnly,
    setShowAddedLorasOnly,
    filteredLoraCount,
    setFilteredLoraCount,
    selectedModelFilter,
    setSelectedModelFilter,
    selectedSubFilter,
    setSelectedSubFilter,
    currentPage,
    totalPages,
    onPageChange,
    handlePageChange,
  } = useLoraFilters(loraType);

  // Modal styling and scroll fade
  const modal = useExtraLargeModal('loraSelector');
  const { showFade, scrollRef } = useScrollFade({
    isOpen: isOpen,
    debug: false,
    preloadFade: modal.isMobile
  });
  const modalHeaderPaddingClass = modal.isMobile ? 'px-2 pt-1 pb-2' : 'px-6 pt-2 pb-2';
  const modalTabRowPaddingClass = `${modal.isMobile ? 'px-2' : 'px-6'} py-2 flex-shrink-0`;
  const handleOpenChange = React.useCallback((open: boolean) => {
    if (!open) {
      onClose();
    }
  }, [onClose]);

  React.useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      const content = contentRef.current;
      const target = event.target as Node | null;
      if (!content || !target) {
        return;
      }

      const topOverlay = overlayStackApi.getState().getTopOverlay();
      const contentOverlay = overlayStackApi.getState().getTopmostOverlayContainingElement(content);
      if (!topOverlay || !contentOverlay || topOverlay.id !== contentOverlay.id) {
        return;
      }

      if (content.contains(target)) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation?.();
      onClose();
    };

    document.addEventListener('pointerdown', handlePointerDown, true);
    return () => document.removeEventListener('pointerdown', handlePointerDown, true);
  }, [isOpen, onClose, overlayStackApi]);

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      {isOpen && (
        <DialogContent
          ref={contentRef}
          className={modal.className}
          style={modal.style}
        >
          <div className={modal.headerClass}>
            <DialogHeader className={`${modalHeaderPaddingClass} flex-shrink-0`}>
              <DialogTitle>LoRA Library</DialogTitle>
            </DialogHeader>
          </div>
          <div
            ref={scrollRef}
            className={modal.scrollClass}
          >
            <div className={modalTabRowPaddingClass}>
              <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full flex flex-col flex-1 overflow-hidden">
                <TabsList className="grid w-full grid-cols-2 mb-2">
                  <TabsTrigger value="browse" className="w-full">Browse LoRAs</TabsTrigger>
                  <TabsTrigger value="add-new" className="w-full">Add LoRA</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>

            {/* Tab Content */}
            <div className="flex-1 flex flex-col min-h-0">
              <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full flex flex-col flex-1 overflow-hidden">
                <TabsContent value="browse" className="flex-1 flex flex-col min-h-0">
                  <CommunityLorasTab
                    loras={loras}
                    onAddLora={onAddLora}
                    onRemoveLora={onRemoveLora}
                    onUpdateLoraStrength={onUpdateLoraStrength}
                    selectedLoras={selectedLoras}
                    myLorasResource={myLorasResource}
                    createResource={createResource}
                    updateResource={updateResource}
                    deleteResource={deleteResource}
                    onClose={onClose}
                    onEdit={handleEdit}
                    showMyLorasOnly={showMyLorasOnly}
                    setShowMyLorasOnly={setShowMyLorasOnly}
                    showAddedLorasOnly={showAddedLorasOnly}
                    setShowAddedLorasOnly={setShowAddedLorasOnly}
                    onProcessedLorasLengthChange={setFilteredLoraCount}
                    onPageChange={handlePageChange}
                    selectedModelFilter={selectedModelFilter}
                    setSelectedModelFilter={setSelectedModelFilter}
                    selectedSubFilter={selectedSubFilter}
                    setSelectedSubFilter={setSelectedSubFilter}
                  />
                </TabsContent>
                <TabsContent value="add-new" className="flex-1 min-h-0 overflow-auto">
                  <MyLorasTab
                    myLorasResource={myLorasResource}
                    deleteResource={deleteResource}
                    createResource={createResource}
                    updateResource={updateResource}
                    onSwitchToBrowse={switchToBrowse}
                    editingLora={editingLora}
                    onClearEdit={clearEdit}
                    defaultIsPublic={privacyDefaults.resourcesPublic}
                  />
                </TabsContent>
              </Tabs>
            </div>
          </div>

          {/* Control Panel Footer - Always sticks to bottom like PromptEditorModal */}
          {activeTab === 'browse' && (
            <LoraSelectorFooter
              footerClass={modal.footerClass}
              isMobile={modal.isMobile}
              showFade={showFade}
              showAddedLorasOnly={showAddedLorasOnly}
              setShowAddedLorasOnly={setShowAddedLorasOnly}
              showMyLorasOnly={showMyLorasOnly}
              setShowMyLorasOnly={setShowMyLorasOnly}
              filteredLoraCount={filteredLoraCount}
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={onPageChange}
              onClose={onClose}
            />
          )}
        </DialogContent>
      )}
    </Dialog>
  );
};
