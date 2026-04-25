import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import type { GeneratedImageWithMetadata } from '@/shared/components/MediaGallery/types';
import type { GallerySelectionItem } from '@/shared/state/selectionStore';

type SelectionRect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

type UseLassoSelectionParams = {
  containerRef: RefObject<HTMLElement | null>;
  items: GeneratedImageWithMetadata[];
  onSelectItems: (items: GallerySelectionItem[], options?: { append?: boolean }) => void;
};

type DragState = {
  startX: number;
  startY: number;
  append: boolean;
};

function toSelectionItem(image: GeneratedImageWithMetadata): GallerySelectionItem {
  return {
    id: image.id,
    url: image.url ?? image.thumbUrl ?? '',
    type: image.type ?? image.contentType ?? (image.isVideo ? 'video/mp4' : 'image/png'),
    generationId: image.generation_id ?? image.id,
  };
}

function rectsIntersect(a: DOMRect, b: DOMRect) {
  return !(a.right < b.left || a.left > b.right || a.bottom < b.top || a.top > b.bottom);
}

function isMultiSelectEvent(event: Pick<MouseEvent, 'shiftKey' | 'metaKey' | 'ctrlKey'>) {
  return event.shiftKey || event.metaKey || event.ctrlKey;
}

export function useLassoSelection({
  containerRef,
  items,
  onSelectItems,
}: UseLassoSelectionParams) {
  const [selectionRect, setSelectionRect] = useState<SelectionRect | null>(null);
  const dragStateRef = useRef<DragState | null>(null);

  const itemsById = useMemo(
    () => new Map(items.map((item) => [item.id, item])),
    [items],
  );

  const endSelection = useCallback((clientX: number, clientY: number) => {
    const container = containerRef.current;
    const dragState = dragStateRef.current;

    if (!container || !dragState) {
      dragStateRef.current = null;
      setSelectionRect(null);
      return;
    }

    const normalizedRect = new DOMRect(
      Math.min(dragState.startX, clientX),
      Math.min(dragState.startY, clientY),
      Math.abs(clientX - dragState.startX),
      Math.abs(clientY - dragState.startY),
    );

    const selectedItems = Array.from(
      container.querySelectorAll<HTMLElement>('[data-gallery-item-id]'),
    ).flatMap((element) => {
      const itemId = element.dataset.galleryItemId;
      const image = itemId ? itemsById.get(itemId) : undefined;
      if (!image) {
        return [];
      }

      return rectsIntersect(normalizedRect, element.getBoundingClientRect())
        ? [toSelectionItem(image)]
        : [];
    });

    onSelectItems(selectedItems, { append: dragState.append });
    dragStateRef.current = null;
    setSelectionRect(null);
  }, [containerRef, itemsById, onSelectItems]);

  useEffect(() => {
    const handleMouseMove = (event: MouseEvent) => {
      const dragState = dragStateRef.current;
      const container = containerRef.current;
      if (!dragState || !container) {
        return;
      }

      const bounds = container.getBoundingClientRect();
      const currentX = Math.min(Math.max(event.clientX, bounds.left), bounds.right);
      const currentY = Math.min(Math.max(event.clientY, bounds.top), bounds.bottom);
      const left = Math.min(dragState.startX, currentX) - bounds.left;
      const top = Math.min(dragState.startY, currentY) - bounds.top;

      setSelectionRect({
        left,
        top,
        width: Math.abs(currentX - dragState.startX),
        height: Math.abs(currentY - dragState.startY),
      });
    };

    const handleMouseUp = (event: MouseEvent) => {
      endSelection(event.clientX, event.clientY);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [containerRef, endSelection]);

  const handleMouseDown = useCallback((event: React.MouseEvent<HTMLElement>) => {
    if (event.button !== 0) {
      return;
    }

    const container = containerRef.current;
    const target = event.target as HTMLElement;
    if (!container || target.closest('[data-gallery-item-id]')) {
      return;
    }

    const bounds = container.getBoundingClientRect();
    dragStateRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      append: isMultiSelectEvent(event),
    };
    setSelectionRect({
      left: event.clientX - bounds.left,
      top: event.clientY - bounds.top,
      width: 0,
      height: 0,
    });
    event.preventDefault();
  }, [containerRef]);

  return {
    selectionRect,
    handleMouseDown,
  };
}
