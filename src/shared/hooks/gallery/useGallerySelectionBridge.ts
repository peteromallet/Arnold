import { useCallback, useEffect, useRef } from 'react';
import type { GenerationRow } from '@/domains/generation/types';
import {
  systemClearGallerySelection,
  systemSyncGallerySelection,
  type GallerySelectionItem,
  useGallerySelectionOptional,
} from '@/shared/state/selectionStore';

interface UseGallerySelectionBridgeArgs {
  selectedIds: string[];
  images: GenerationRow[];
  clearLocalSelection: () => void;
}

export function useGallerySelectionBridge({
  selectedIds,
  images,
  clearLocalSelection,
}: UseGallerySelectionBridgeArgs): void {
  const gallery = useGallerySelectionOptional();
  const imagesRef = useRef(images);

  imagesRef.current = images;

  const syncLocalSelection = useCallback(() => {
    if (!gallery) {
      return;
    }

    const localSelection = new Set(selectedIds);
    const globalSelection = gallery.selectedGalleryIds;
    const matches = localSelection.size === globalSelection.size
      && selectedIds.every((id) => globalSelection.has(id));

    if (!matches && selectedIds.length > 0) {
      clearLocalSelection();
    }
  }, [clearLocalSelection, gallery, selectedIds]);

  useEffect(() => {
    if (!gallery) {
      return;
    }

    if (selectedIds.length === 0) {
      systemClearGallerySelection();
      return;
    }

    const items: GallerySelectionItem[] = selectedIds.flatMap((id) => {
      const image = imagesRef.current.find((candidate) => candidate.id === id);
      if (!image) {
        return [];
      }

      return [{
        id: image.id,
        url: image.imageUrl ?? image.location ?? '',
        type: image.type ?? image.contentType ?? 'image/png',
        generationId: image.generation_id ?? image.id,
        variantId: image.primary_variant_id ?? undefined,
      }];
    });

    if (items.length > 0) {
      systemSyncGallerySelection(items);
    }
  }, [gallery, selectedIds]);

  useEffect(() => {
    syncLocalSelection();
  }, [syncLocalSelection]);
}
