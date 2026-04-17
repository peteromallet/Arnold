import type { ReactNode } from 'react';
import { useEffect, useMemo, useRef } from 'react';
import { shallow } from 'zustand/shallow';
import { useStoreWithEqualityFn } from 'zustand/traditional';
import { createStore } from 'zustand/vanilla';
import { PANE_CONFIG } from '@/shared/config/panes';
import { usePaneLockPolicyState } from '@/shared/contexts/usePaneLockPolicyState';

export type PaneLockKey = 'shots' | 'tasks' | 'gens' | 'editor';

export interface PaneLocksState {
  shots: boolean;
  tasks: boolean;
  gens: boolean;
  editor: boolean;
}

export interface PanesStoreAvailability {
  bootstrapped: boolean;
}

export interface PanesStoreState {
  availability: PanesStoreAvailability;
  isGenerationsPaneLocked: boolean;
  setIsGenerationsPaneLocked: (isLocked: boolean) => void;
  isGenerationsPaneOpen: boolean;
  setIsGenerationsPaneOpen: (isOpen: boolean) => void;
  generationsPaneHeight: number;
  effectiveGenerationsPaneHeight: number;
  setGenerationsPaneHeight: (height: number) => void;
  isEditorPaneLocked: boolean;
  setIsEditorPaneLocked: (isLocked: boolean) => void;
  isEditorPaneOpen: boolean;
  setIsEditorPaneOpen: (isOpen: boolean) => void;
  editorPaneHeight: number;
  effectiveEditorPaneHeight: number;
  isShotsPaneLocked: boolean;
  setIsShotsPaneLocked: (isLocked: boolean) => void;
  shotsPaneWidth: number;
  setShotsPaneWidth: (width: number) => void;
  isTasksPaneLocked: boolean;
  setIsTasksPaneLocked: (isLocked: boolean) => void;
  tasksPaneWidth: number;
  setTasksPaneWidth: (width: number) => void;
  activeTaskId: string | null;
  setActiveTaskId: (taskId: string | null) => void;
  isTasksPaneOpen: boolean;
  setIsTasksPaneOpen: (isOpen: boolean) => void;
  resetAllPaneLocks: () => void;
  bootstrap: (input: PanesStoreBootstrapInput) => void;
  clearBootstrap: (owner?: symbol) => void;
  resetStore: () => void;
}

interface PanesStoreBootstrapSnapshot {
  viewportHeight: number;
  locks: PaneLocksState;
  isGenerationsPaneOpen: boolean;
  isEditorPaneOpen: boolean;
  isTasksPaneOpen: boolean;
}

interface PanesStoreBootstrapRuntime {
  setIsGenerationsPaneLocked: (isLocked: boolean) => void;
  setIsEditorPaneLocked: (isLocked: boolean) => void;
  setIsShotsPaneLocked: (isLocked: boolean) => void;
  setIsTasksPaneLocked: (isLocked: boolean) => void;
  setIsGenerationsPaneOpen: (isOpen: boolean) => void;
  setIsEditorPaneOpen: (isOpen: boolean) => void;
  setIsTasksPaneOpen: (isOpen: boolean) => void;
  resetAllPaneLocks: () => void;
}

export interface PanesStoreBootstrapInput extends PanesStoreBootstrapSnapshot, PanesStoreBootstrapRuntime {
  owner: symbol;
}

const MIN_EDITOR_HEIGHT = 200;

const UNLOCKED_PANES: PaneLocksState = {
  shots: false,
  tasks: false,
  gens: false,
  editor: false,
};

let activeBootstrapOwner: symbol | null = null;
let activeBootstrapSnapshot: PanesStoreBootstrapInput | null = null;
let activeBootstrapRuntime: PanesStoreBootstrapRuntime | null = null;

function getViewportHeight(): number {
  if (typeof window === 'undefined') {
    return 0;
  }

  return window.innerHeight;
}

function getEffectivePaneHeights(params: {
  viewportHeight: number;
  idealEditorPaneHeight: number;
  generationsPaneHeight: number;
}) {
  const {
    viewportHeight,
    idealEditorPaneHeight,
    generationsPaneHeight,
  } = params;

  if (idealEditorPaneHeight + generationsPaneHeight <= viewportHeight) {
    return {
      effectiveEditorPaneHeight: idealEditorPaneHeight,
      effectiveGenerationsPaneHeight: generationsPaneHeight,
    };
  }

  if (viewportHeight >= generationsPaneHeight + MIN_EDITOR_HEIGHT) {
    return {
      effectiveEditorPaneHeight: viewportHeight - generationsPaneHeight,
      effectiveGenerationsPaneHeight: generationsPaneHeight,
    };
  }

  const denom = 2 * (idealEditorPaneHeight + generationsPaneHeight) - viewportHeight;
  const effectiveGenerationsPaneHeight = Math.round((viewportHeight * generationsPaneHeight) / denom);

  return {
    effectiveEditorPaneHeight: Math.max(viewportHeight - effectiveGenerationsPaneHeight, 0),
    effectiveGenerationsPaneHeight,
  };
}

function deriveLayout(params: {
  viewportHeight: number;
  generationsPaneHeight: number;
  isGenerationsPaneLocked: boolean;
  isGenerationsPaneOpen: boolean;
  isEditorPaneLocked: boolean;
  isEditorPaneOpen: boolean;
}) {
  const {
    viewportHeight,
    generationsPaneHeight,
    isGenerationsPaneLocked,
    isGenerationsPaneOpen,
    isEditorPaneLocked,
    isEditorPaneOpen,
  } = params;

  const editorVisible = isEditorPaneLocked || isEditorPaneOpen;
  const generationsVisible = isGenerationsPaneLocked || isGenerationsPaneOpen;
  const editorPaneHeight = Math.round(viewportHeight * 0.5);

  if (!(editorVisible && generationsVisible)) {
    return {
      editorPaneHeight,
      effectiveEditorPaneHeight: editorPaneHeight,
      effectiveGenerationsPaneHeight: generationsPaneHeight,
    };
  }

  const { effectiveEditorPaneHeight, effectiveGenerationsPaneHeight } = getEffectivePaneHeights({
    viewportHeight,
    idealEditorPaneHeight: editorPaneHeight,
    generationsPaneHeight,
  });

  return {
    editorPaneHeight,
    effectiveEditorPaneHeight,
    effectiveGenerationsPaneHeight,
  };
}

function createInitialSnapshot() {
  const viewportHeight = getViewportHeight();
  const generationsPaneHeight = PANE_CONFIG.dimensions.DEFAULT_HEIGHT;
  const layout = deriveLayout({
    viewportHeight,
    generationsPaneHeight,
    isGenerationsPaneLocked: false,
    isGenerationsPaneOpen: false,
    isEditorPaneLocked: false,
    isEditorPaneOpen: false,
  });

  return {
    availability: { bootstrapped: false } as PanesStoreAvailability,
    isGenerationsPaneLocked: false,
    isGenerationsPaneOpen: false,
    generationsPaneHeight,
    effectiveGenerationsPaneHeight: layout.effectiveGenerationsPaneHeight,
    isEditorPaneLocked: false,
    isEditorPaneOpen: false,
    editorPaneHeight: layout.editorPaneHeight,
    effectiveEditorPaneHeight: layout.effectiveEditorPaneHeight,
    isShotsPaneLocked: false,
    shotsPaneWidth: PANE_CONFIG.dimensions.DEFAULT_WIDTH,
    isTasksPaneLocked: false,
    tasksPaneWidth: PANE_CONFIG.dimensions.DEFAULT_WIDTH,
    activeTaskId: null as string | null,
    isTasksPaneOpen: false,
  };
}

function areBootstrapInputsEqual(
  previous: PanesStoreBootstrapInput | null,
  next: PanesStoreBootstrapInput,
): boolean {
  return previous?.owner === next.owner
    && previous.viewportHeight === next.viewportHeight
    && previous.locks.shots === next.locks.shots
    && previous.locks.tasks === next.locks.tasks
    && previous.locks.gens === next.locks.gens
    && previous.locks.editor === next.locks.editor
    && previous.isGenerationsPaneOpen === next.isGenerationsPaneOpen
    && previous.isEditorPaneOpen === next.isEditorPaneOpen
    && previous.isTasksPaneOpen === next.isTasksPaneOpen
    && previous.setIsGenerationsPaneLocked === next.setIsGenerationsPaneLocked
    && previous.setIsEditorPaneLocked === next.setIsEditorPaneLocked
    && previous.setIsShotsPaneLocked === next.setIsShotsPaneLocked
    && previous.setIsTasksPaneLocked === next.setIsTasksPaneLocked
    && previous.setIsGenerationsPaneOpen === next.setIsGenerationsPaneOpen
    && previous.setIsEditorPaneOpen === next.setIsEditorPaneOpen
    && previous.setIsTasksPaneOpen === next.setIsTasksPaneOpen
    && previous.resetAllPaneLocks === next.resetAllPaneLocks;
}

function updateBootstrapRuntime(input: PanesStoreBootstrapInput | null): void {
  if (!input) {
    activeBootstrapRuntime = null;
    return;
  }

  activeBootstrapRuntime = {
    setIsGenerationsPaneLocked: input.setIsGenerationsPaneLocked,
    setIsEditorPaneLocked: input.setIsEditorPaneLocked,
    setIsShotsPaneLocked: input.setIsShotsPaneLocked,
    setIsTasksPaneLocked: input.setIsTasksPaneLocked,
    setIsGenerationsPaneOpen: input.setIsGenerationsPaneOpen,
    setIsEditorPaneOpen: input.setIsEditorPaneOpen,
    setIsTasksPaneOpen: input.setIsTasksPaneOpen,
    resetAllPaneLocks: input.resetAllPaneLocks,
  };
}

function buildBootstrappedState(
  currentState: Pick<
    PanesStoreState,
    | 'generationsPaneHeight'
    | 'shotsPaneWidth'
    | 'tasksPaneWidth'
    | 'activeTaskId'
  >,
  input: PanesStoreBootstrapInput,
) {
  const layout = deriveLayout({
    viewportHeight: input.viewportHeight,
    generationsPaneHeight: currentState.generationsPaneHeight,
    isGenerationsPaneLocked: input.locks.gens,
    isGenerationsPaneOpen: input.isGenerationsPaneOpen,
    isEditorPaneLocked: input.locks.editor,
    isEditorPaneOpen: input.isEditorPaneOpen,
  });

  return {
    availability: { bootstrapped: true } as PanesStoreAvailability,
    isGenerationsPaneLocked: input.locks.gens,
    isGenerationsPaneOpen: input.isGenerationsPaneOpen,
    generationsPaneHeight: currentState.generationsPaneHeight,
    effectiveGenerationsPaneHeight: layout.effectiveGenerationsPaneHeight,
    isEditorPaneLocked: input.locks.editor,
    isEditorPaneOpen: input.isEditorPaneOpen,
    editorPaneHeight: layout.editorPaneHeight,
    effectiveEditorPaneHeight: layout.effectiveEditorPaneHeight,
    isShotsPaneLocked: input.locks.shots,
    shotsPaneWidth: currentState.shotsPaneWidth,
    isTasksPaneLocked: input.locks.tasks,
    tasksPaneWidth: currentState.tasksPaneWidth,
    activeTaskId: currentState.activeTaskId,
    isTasksPaneOpen: input.isTasksPaneOpen,
  };
}

function buildStateWithUpdatedGenerationsHeight(
  state: Pick<
    PanesStoreState,
    | 'availability'
    | 'generationsPaneHeight'
    | 'shotsPaneWidth'
    | 'tasksPaneWidth'
    | 'activeTaskId'
    | 'isGenerationsPaneLocked'
    | 'isGenerationsPaneOpen'
    | 'isEditorPaneLocked'
    | 'isEditorPaneOpen'
    | 'isShotsPaneLocked'
    | 'isTasksPaneLocked'
    | 'isTasksPaneOpen'
  >,
  generationsPaneHeight: number,
) {
  const viewportHeight = activeBootstrapSnapshot?.viewportHeight ?? getViewportHeight();
  const layout = deriveLayout({
    viewportHeight,
    generationsPaneHeight,
    isGenerationsPaneLocked: state.isGenerationsPaneLocked,
    isGenerationsPaneOpen: state.isGenerationsPaneOpen,
    isEditorPaneLocked: state.isEditorPaneLocked,
    isEditorPaneOpen: state.isEditorPaneOpen,
  });

  return {
    availability: state.availability,
    isGenerationsPaneLocked: state.isGenerationsPaneLocked,
    isGenerationsPaneOpen: state.isGenerationsPaneOpen,
    generationsPaneHeight,
    effectiveGenerationsPaneHeight: layout.effectiveGenerationsPaneHeight,
    isEditorPaneLocked: state.isEditorPaneLocked,
    isEditorPaneOpen: state.isEditorPaneOpen,
    editorPaneHeight: layout.editorPaneHeight,
    effectiveEditorPaneHeight: layout.effectiveEditorPaneHeight,
    isShotsPaneLocked: state.isShotsPaneLocked,
    shotsPaneWidth: state.shotsPaneWidth,
    isTasksPaneLocked: state.isTasksPaneLocked,
    tasksPaneWidth: state.tasksPaneWidth,
    activeTaskId: state.activeTaskId,
    isTasksPaneOpen: state.isTasksPaneOpen,
  };
}

const initialSnapshot = createInitialSnapshot();

const panesStore = createStore<PanesStoreState>((set, get) => ({
  ...initialSnapshot,
  setIsGenerationsPaneLocked: (isLocked) => {
    activeBootstrapRuntime?.setIsGenerationsPaneLocked(isLocked);
  },
  setIsGenerationsPaneOpen: (isOpen) => {
    activeBootstrapRuntime?.setIsGenerationsPaneOpen(isOpen);
  },
  setGenerationsPaneHeight: (height) => {
    set((state) => {
      if (state.generationsPaneHeight === height) {
        return state;
      }

      return buildStateWithUpdatedGenerationsHeight(state, height);
    });
  },
  setIsEditorPaneLocked: (isLocked) => {
    activeBootstrapRuntime?.setIsEditorPaneLocked(isLocked);
  },
  setIsEditorPaneOpen: (isOpen) => {
    activeBootstrapRuntime?.setIsEditorPaneOpen(isOpen);
  },
  setIsShotsPaneLocked: (isLocked) => {
    activeBootstrapRuntime?.setIsShotsPaneLocked(isLocked);
  },
  setShotsPaneWidth: (width) => {
    set((state) => (
      state.shotsPaneWidth === width
        ? state
        : { shotsPaneWidth: width }
    ));
  },
  setIsTasksPaneLocked: (isLocked) => {
    activeBootstrapRuntime?.setIsTasksPaneLocked(isLocked);
  },
  setTasksPaneWidth: (width) => {
    set((state) => (
      state.tasksPaneWidth === width
        ? state
        : { tasksPaneWidth: width }
    ));
  },
  setActiveTaskId: (taskId) => {
    set((state) => (
      state.activeTaskId === taskId
        ? state
        : { activeTaskId: taskId }
    ));
  },
  setIsTasksPaneOpen: (isOpen) => {
    activeBootstrapRuntime?.setIsTasksPaneOpen(isOpen);
  },
  resetAllPaneLocks: () => {
    activeBootstrapRuntime?.resetAllPaneLocks();
  },
  bootstrap: (input) => {
    if (areBootstrapInputsEqual(activeBootstrapSnapshot, input)) {
      return;
    }

    activeBootstrapOwner = input.owner;
    activeBootstrapSnapshot = input;
    updateBootstrapRuntime(input);

    set((state) => buildBootstrappedState(state, input));
  },
  clearBootstrap: (owner) => {
    if (owner && activeBootstrapOwner && owner !== activeBootstrapOwner) {
      return;
    }

    activeBootstrapOwner = null;
    activeBootstrapSnapshot = null;
    updateBootstrapRuntime(null);
    set(() => createInitialSnapshot());
  },
  resetStore: () => {
    activeBootstrapOwner = null;
    activeBootstrapSnapshot = null;
    updateBootstrapRuntime(null);
    set(() => createInitialSnapshot());
  },
}));

export function usePanesStoreApi() {
  return panesStore;
}

export function usePanesStore<T>(
  selector: (state: PanesStoreState) => T,
  equalityFn?: (left: T, right: T) => boolean,
): T {
  return useStoreWithEqualityFn(panesStore, selector, equalityFn);
}

export function usePanesStoreAvailability(): PanesStoreAvailability {
  return usePanesStore((state) => state.availability, shallow);
}

export function bootstrapPanesStore(input: PanesStoreBootstrapInput): void {
  panesStore.getState().bootstrap(input);
}

export function clearPanesStoreBootstrap(owner?: symbol): void {
  panesStore.getState().clearBootstrap(owner);
}

export function resetPanesStore(): void {
  panesStore.getState().resetStore();
}

/**
 * Singleton panes lifecycle contract:
 * - exactly one mounted bootstrap owner should drive runtime-backed pane state
 * - repeated bootstraps from that owner are idempotent
 * - reads outside bootstrap intentionally return the unlocked default snapshot
 */
export function useBootstrapPanesStore(): void {
  const ownerRef = useRef<symbol | null>(null);
  if (ownerRef.current === null) {
    ownerRef.current = Symbol('panes-store-bootstrap-owner');
  }

  const {
    locks,
    isGenerationsPaneOpenState,
    isEditorPaneOpenState,
    isTasksPaneOpenState,
    setIsGenerationsPaneLocked,
    setIsEditorPaneLocked,
    setIsShotsPaneLocked,
    setIsTasksPaneLocked,
    setIsGenerationsPaneOpen,
    setIsEditorPaneOpen,
    setIsTasksPaneOpen,
    resetAllPaneLocks,
  } = usePaneLockPolicyState();

  const bootstrapInput = useMemo<PanesStoreBootstrapInput>(() => ({
    owner: ownerRef.current as symbol,
    viewportHeight: getViewportHeight(),
    locks,
    isGenerationsPaneOpen: isGenerationsPaneOpenState,
    isEditorPaneOpen: isEditorPaneOpenState,
    isTasksPaneOpen: isTasksPaneOpenState,
    setIsGenerationsPaneLocked,
    setIsEditorPaneLocked,
    setIsShotsPaneLocked,
    setIsTasksPaneLocked,
    setIsGenerationsPaneOpen,
    setIsEditorPaneOpen,
    setIsTasksPaneOpen,
    resetAllPaneLocks,
  }), [
    locks,
    isGenerationsPaneOpenState,
    isEditorPaneOpenState,
    isTasksPaneOpenState,
    setIsGenerationsPaneLocked,
    setIsEditorPaneLocked,
    setIsShotsPaneLocked,
    setIsTasksPaneLocked,
    setIsGenerationsPaneOpen,
    setIsEditorPaneOpen,
    setIsTasksPaneOpen,
    resetAllPaneLocks,
  ]);

  bootstrapPanesStore(bootstrapInput);

  useEffect(() => {
    return () => {
      clearPanesStoreBootstrap(ownerRef.current ?? undefined);
    };
  }, []);
}

export function PanesStoreBootstrapBoundary({ children }: { children: ReactNode }) {
  useBootstrapPanesStore();
  return children;
}

export function __resetPanesStoreForTests(): void {
  resetPanesStore();
}
