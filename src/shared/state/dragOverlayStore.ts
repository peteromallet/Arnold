import { createStore, useStore } from 'zustand';

interface DragOverlayStoreState {
  isDraggingFiles: boolean;
  setDragging: (isDraggingFiles: boolean) => void;
}

const dragOverlayStore = createStore<DragOverlayStoreState>((set) => ({
  isDraggingFiles: false,
  setDragging: (isDraggingFiles) => set({ isDraggingFiles }),
}));

export const setDragging = (isDraggingFiles: boolean): void => {
  dragOverlayStore.getState().setDragging(isDraggingFiles);
};

export function useIsDraggingFiles(): boolean {
  return useStore(dragOverlayStore, (state) => state.isDraggingFiles);
}
