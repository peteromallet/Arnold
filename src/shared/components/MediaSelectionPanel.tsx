/**
 * MediaSelectionPanel
 *
 * Shared gallery panel for selecting an image or video from the project.
 * Used by EditVideoPage (video selection) and EditImagesPage (image selection).
 */

import React, { useState } from 'react';
import { LayoutGrid } from 'lucide-react';
import { GenerationRow } from '@/domains/generation/types';
import { ReighLoading } from '@/shared/components/ReighLoading';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { useProjectGenerations, type GenerationsPaginatedResponse } from '@/shared/hooks/projects/useProjectGenerations';
import { MediaGallery, DEFAULT_GALLERY_FILTERS, type GalleryFilterState } from '@/shared/components/MediaGallery';
import { useListShots } from '@/shared/hooks/shots';

interface MediaSelectionPanelProps {
  /** Called when the user selects a media item */
  onSelect: (media: GenerationRow) => void;
  /** 'image' or 'video' */
  mediaType: 'image' | 'video';
  /** Header label, e.g. "Select a Video" */
  label?: string;
}

export function MediaSelectionPanel({ onSelect, mediaType, label }: MediaSelectionPanelProps) {
  const { selectedProjectId } = useProjectSelectionContext();
  const [galleryFilters, setGalleryFilters] = useState<GalleryFilterState>({
    ...DEFAULT_GALLERY_FILTERS,
    mediaType,
    toolTypeFilter: mediaType === 'image' ? false : true,
    excludePositioned: false,
  });
  const [currentPage, setCurrentPage] = useState(1);
  // Reset to page 1 when filters change (prev-value ref avoids useEffect+setState)
  const prevFilterKeyRef = React.useRef(`${galleryFilters.shotFilter}|${galleryFilters.searchTerm}`);
  const filterKey = `${galleryFilters.shotFilter}|${galleryFilters.searchTerm}`;
  if (prevFilterKeyRef.current !== filterKey) {
    prevFilterKeyRef.current = filterKey;
    if (currentPage !== 1) setCurrentPage(1);
  }
  const { data: shots } = useListShots(selectedProjectId);
  const itemsPerPage = 15;

  const {
    data: generationsData,
    isLoading: isGalleryLoading,
  } = useProjectGenerations(
    selectedProjectId || null,
    currentPage,
    itemsPerPage,
    true,
    {
      shotId: galleryFilters.shotFilter === 'all' ? undefined : galleryFilters.shotFilter,
      mediaType,
      searchTerm: galleryFilters.searchTerm.trim() || undefined
    }
  );

  const headerText = label ?? (mediaType === 'video' ? 'Select a Video' : 'Select an Image');

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-6 pt-4 pb-2 border-b">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <LayoutGrid className="w-4 h-4" />
          {headerText}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-0 m-0 relative pt-4 px-4 md:px-6">
         {isGalleryLoading && !generationsData ? (
            <ReighLoading />
         ) : (
            <MediaGallery
               images={(generationsData as GenerationsPaginatedResponse | undefined)?.items || []}
               onImageClick={(media) => onSelect(media as GenerationRow)}
               allShots={shots || []}
               filters={galleryFilters}
               onFiltersChange={setGalleryFilters}
               pagination={{
                 itemsPerPage,
                 offset: (currentPage - 1) * itemsPerPage,
                 totalCount: (generationsData as GenerationsPaginatedResponse | undefined)?.total || 0,
                 onServerPageChange: setCurrentPage,
                 serverPage: currentPage,
               }}
               config={{
                 showShotFilter: true,
                 showSearch: true,
                 hideTopFilters: true,
                 hideShotNotifier: true,
                 showDelete: false,
                 showDownload: false,
                 showShare: false,
                 showEdit: false,
                 showStar: false,
                 showAddToShot: false,
                 enableSingleClick: true,
                 hideBottomPagination: true,
                 videosAsThumbnails: mediaType === 'video',
               }}
            />
         )}
      </div>
    </div>
  );
}
