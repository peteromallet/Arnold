import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { TOOL_IDS } from '@/shared/lib/tooling/toolIds';
import { useSearchParams } from 'react-router-dom';

import { ImageGenerationForm } from "@/shared/components/ImageGenerationForm";
import { MediaGallery } from "@/shared/components/MediaGallery";
import type { GeneratedImageWithMetadata } from "@/shared/components/MediaGallery/types";
import { Button } from "@/shared/components/ui/button";
import { useProject } from "@/shared/contexts/ProjectContext";
import { usePublicLoras, usePublicStyleReferences, useMyStyleReferences } from '@/features/resources/hooks/useResources';
import { PageFadeIn } from '@/shared/components/transitions/PageFadeIn';
import { useIsMobile, useIsTablet } from "@/shared/hooks/mobile";
import { SkeletonGallery } from '@/shared/components/ui/composed/skeleton-gallery';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/shared/components/ui/collapsible';
import { ChevronDown, ChevronLeft, Sparkles, Settings2 } from 'lucide-react';
import { DeleteGenerationConfirmDialog } from '@/shared/components/dialogs/DeleteGenerationConfirmDialog';
import { getProjectSelectionFallbackId } from '@/shared/contexts/projectSelectionStore';

import { useModifierKeys } from '@/features/gallery/components/GenerationsPane/hooks/useModifierKeys';
import { useImageGenGallery } from "../hooks/useImageGenGallery";
import { useImageGenActions } from "../hooks/useImageGenActions";
import { useImageGenSubmit } from "../hooks/useImageGenSubmit";
import { useGallerySelection } from '@/shared/state/selectionStore';

const ImageGenerationToolPage: React.FC = React.memo(() => {
  const [formAssociatedShotId, setFormAssociatedShotId] = useState<string | null>(null);
  const [isFormExpanded, setIsFormExpanded] = useState<boolean>(() => {
    try {
      const raw = typeof window !== 'undefined' ? window.sessionStorage.getItem('ig:formExpanded') : null;
      if (raw === 'false') return false;
    } catch { /* intentionally ignored */ }
    return true;
  });

  const {
    selectedGalleryIds,
    selectGalleryItem,
  } = useGallerySelection();
  const modifierKeys = useModifierKeys();

  const buildSelectionMeta = useCallback((image: GeneratedImageWithMetadata) => ({
    url: image.url,
    type: image.type ?? image.contentType ?? (image.isVideo ? 'video/mp4' : 'image/png'),
    generationId: image.generation_id ?? image.id,
    variantId: image.primary_variant_id,
  }), []);

  const handleImageClick = useCallback((image: GeneratedImageWithMetadata) => {
    selectGalleryItem(image.id, buildSelectionMeta(image), { toggle: modifierKeys.isMultiSelectModifier });
  }, [buildSelectionMeta, modifierKeys.isMultiSelectModifier, selectGalleryItem]);

  const isMobile = useIsMobile();
  const isTablet = useIsTablet();
  const isPhoneOnly = isMobile && !isTablet;

  usePublicLoras();
  usePublicStyleReferences();
  useMyStyleReferences();

  const { selectedProjectId, projects } = useProject();

  const effectiveProjectId = useMemo(() => {
    if (selectedProjectId) return selectedProjectId;
    const fromRuntime = getProjectSelectionFallbackId();
    return fromRuntime ?? null;
  }, [selectedProjectId]);

  const currentProject = projects.find(project => project.id === selectedProjectId);
  const projectAspectRatio = currentProject?.aspectRatio;

  const formContainerRef = useRef<HTMLDivElement>(null);
  const collapsibleContainerRef = useRef<HTMLDivElement>(null);
  const [searchParams] = useSearchParams();

  const gallery = useImageGenGallery({
    projectId: selectedProjectId,
    effectiveProjectId,
    projectAspectRatio,
    formAssociatedShotId,
    isFormExpanded,
    isMobile,
    isPhoneOnly,
    searchParams,
    collapsibleContainerRef,
    formContainerRef,
  });

  const actions = useImageGenActions({
    projectId: selectedProjectId,
    effectiveProjectId,
    selectedShotFilter: gallery.galleryFilters.shotFilter,
    excludePositioned: gallery.galleryFilters.excludePositioned,
    generationsFilters: gallery.generationsFilters,
    currentPage: gallery.currentPage,
    itemsPerPage: gallery.itemsPerPage,
  });

  const form = useImageGenSubmit({
    projectId: selectedProjectId,
    effectiveProjectId,
  });

  const { setLastAffectedShotId } = actions;
  const { setGalleryFilters } = gallery;

  const handleFormShotChange = useCallback((shotId: string | null) => {
    setFormAssociatedShotId(shotId);
    if (shotId) {
      setLastAffectedShotId(shotId);
      setGalleryFilters(prev => ({ ...prev, shotFilter: shotId }));
    }
  }, [setLastAffectedShotId, setGalleryFilters]);

  useEffect(() => {
    const formCollapsedParam = searchParams.get('formCollapsed');
    if (formCollapsedParam === 'true') {
      setIsFormExpanded(false);
      try { window.sessionStorage.setItem('ig:formExpanded', 'false'); } catch { /* intentionally ignored */ }

      const newSearchParams = new URLSearchParams(searchParams);
      newSearchParams.delete('formCollapsed');
      const newUrl = newSearchParams.toString()
        ? `${window.location.pathname}?${newSearchParams.toString()}`
        : window.location.pathname;
      window.history.replaceState({}, '', newUrl);
    }
   
  }, [searchParams]); // Run when URL params change

  const handleCollapsibleOpenChange = useCallback((nextOpen: boolean) => {
    setIsFormExpanded(nextOpen);
    try { window.sessionStorage.setItem('ig:formExpanded', String(nextOpen)); } catch { /* intentionally ignored */ }
  }, []);

  return (
    <PageFadeIn>
      <div className="flex flex-col gap-y-6 pb-6 px-4 max-w-7xl mx-auto pt-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-light tracking-tight text-foreground">Image Generation</h1>
        </div>

        <div ref={collapsibleContainerRef} className="mb-2">
          <Collapsible
            open={isFormExpanded}
            onOpenChange={handleCollapsibleOpenChange}
          >
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                className={`${isFormExpanded ? 'w-full justify-between px-6 py-6 hover:bg-accent/50 bg-accent/10 border border-b-0 rounded-t-lg shadow-sm text-foreground' : 'w-full justify-between px-6 py-6 gradient-primary-collapsed rounded-lg'} ${!isFormExpanded && gallery.isSticky ? 'opacity-0 pointer-events-none' : 'opacity-100'} transition-all duration-700 ease-in-out transform hover:scale-[1.02] active:scale-[0.98]`}
                type="button"
              >
                <div className="flex items-center gap-2 transition-all duration-700 ease-in-out">
                  <Settings2 className={`h-4 w-4 transition-all duration-700 ease-in-out ${!isFormExpanded ? 'text-white' : 'text-foreground'}`} />
                  <span className={`font-light flex items-center gap-1 transition-all duration-700 ease-in-out ${!isFormExpanded ? 'text-white' : 'text-foreground'}`}>
                    Make images
                    <Sparkles className={`h-3 w-3 transition-all duration-700 ease-in-out ${!isFormExpanded ? 'text-white' : 'text-foreground'}`} />
                  </span>
                </div>
                <div className="transition-transform duration-700 ease-in-out">
                  {isFormExpanded ? (
                    <ChevronDown className="h-4 w-4 transition-all duration-700 ease-in-out text-foreground" />
                  ) : (
                    <ChevronLeft className="h-4 w-4 text-white transition-all duration-700 ease-in-out" />
                  )}
                </div>
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="overflow-hidden">
              <div ref={formContainerRef} className="p-6 border rounded-lg shadow-sm bg-card w-full max-w-full transition-all duration-700 ease-in-out">
                <ImageGenerationForm
                  onGenerate={form.handleNewGenerate}
                  openaiApiKey={form.openaiApiKey}
                  onShotChange={handleFormShotChange}
                />
              </div>
            </CollapsibleContent>
          </Collapsible>
        </div>

        <div ref={gallery.galleryRef as React.RefObject<HTMLDivElement>} className="pt-0">
          {(!effectiveProjectId || (gallery.isLoadingGenerations && gallery.imagesToShow.length === 0)) ? (
            <SkeletonGallery
              count={gallery.skeletonItemsPerPage}
              fixedColumns={gallery.skeletonColumns}
              showControls={true}
              projectAspectRatio={projectAspectRatio}
              gapClasses="gap-2 sm:gap-4"
            />
          ) : (
            <div className={gallery.isLoadingGenerations && gallery.isFilterChange ? 'opacity-60 pointer-events-none transition-opacity duration-200' : ''}>
              <MediaGallery
                images={gallery.imagesToShow}
                onDelete={actions.handleDeleteImage}
                onToggleStar={actions.handleToggleStar}
                onAddToLastShot={actions.handleAddImageToTargetShot}
                onAddToLastShotWithoutPosition={actions.handleAddImageToTargetShotWithoutPosition}
                allShots={actions.validShots}
                lastShotId={actions.targetShotInfo.targetShotIdForButton}
                lastShotNameForTooltip={actions.targetShotInfo.targetShotNameForButtonTooltip}
                currentToolType={TOOL_IDS.IMAGE_GENERATION}
                initialFilterState={true}
                filters={gallery.galleryFilters}
                onFiltersChange={gallery.handleGalleryFiltersChange}
                pagination={{
                  itemsPerPage: gallery.itemsPerPage,
                  offset: (gallery.currentPage - 1) * gallery.itemsPerPage,
                  totalCount: gallery.generationsResponse?.total ?? gallery.lastKnownTotal,
                  onServerPageChange: gallery.handleServerPageChange,
                  serverPage: gallery.currentPage,
                  enableAdjacentPagePreloading: true,
                }}
                currentToolTypeName="Image Generation"
                formAssociatedShotId={formAssociatedShotId}
                onSwitchToAssociatedShot={gallery.handleSwitchToAssociatedShot}
                generationFilters={gallery.generationsFilters}
                onCreateShot={actions.handleCreateShot}
                onBackfillRequest={actions.handleBackfillRequest}
                onImageClick={handleImageClick}
                selectedIds={selectedGalleryIds}
                config={{
                  reducedSpacing: true,
                  showShotFilter: true,
                  showSearch: true,
                  showShare: false,
                  enableSingleClick: true,
                }}
              />
            </div>
          )}
        </div>
      </div>
      <DeleteGenerationConfirmDialog {...actions.confirmDialogProps} />
    </PageFadeIn>
  );
}, () => true); // Always return true since component has no props

export default ImageGenerationToolPage;
