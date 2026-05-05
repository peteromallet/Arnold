/**
 * Persists the SequenceCreator panel's in-progress state across panel
 * close/reopen and full reloads, so users don't lose prompt text, generated
 * drafts, classifier verdicts, fork-pending state, or the latest generated
 * component when the dialog unmounts.
 *
 * Persisted (localStorage key 'reigh:video-editor:sequence-creator'):
 *   mode, generationMode, prompt, editPrompt, draftGroups, selectedGroupId,
 *   selectedDraftIndex, classifierVerdict, forkPending, generatedComponent.
 *
 * NOT persisted (kept as panel-local useState — deliberate):
 *   isGenerating, isSaving, abortRef — transient request lifecycle. A
 *   request that was in-flight before reload is gone after reload.
 *
 * Persisted but excluded via `partialize`:
 *   generationNote, actionError — transient feedback strings. Stale errors
 *   shown on reopen are confusing and never accurate.
 */
import type { SetStateAction } from 'react';
import { shallow } from 'zustand/shallow';
import { useStoreWithEqualityFn } from 'zustand/traditional';
import { persist, createJSONStorage } from 'zustand/middleware';
import { createStore } from 'zustand/vanilla';
import type {
  SequenceCreatorMode,
  SequenceDraftGroup,
} from '@/tools/video-editor/sequences/generation.ts';
import type { getBundledComponentSource } from '@/tools/video-editor/sequences/getBundledComponentSource.ts';

export type GenerationMode = 'auto' | 'code' | 'json';

export type ClassifierVerdict = {
  path: 'json' | 'code';
  reason: string;
};

export type ForkPending = {
  prompt: string;
  reason: string;
  selectedClipType: string;
  bundledSource: ReturnType<typeof getBundledComponentSource>;
};

export type GeneratedComponent = {
  code: string;
  name: string;
  description: string;
  schemaJson: object;
  defaultsJson: object;
};

export type SequenceCreatorPersistedState = {
  mode: SequenceCreatorMode;
  generationMode: GenerationMode;
  prompt: string;
  editPrompt: string;
  draftGroups: SequenceDraftGroup[];
  selectedGroupId: string | null;
  selectedDraftIndex: number;
  generationNote: string | null;
  actionError: string | null;
  classifierVerdict: ClassifierVerdict | null;
  forkPending: ForkPending | null;
  generatedComponent: GeneratedComponent | null;
};

type Updater<T> = T | ((current: T) => T);

function applyUpdater<T>(current: T, updater: Updater<T>): T {
  return typeof updater === 'function'
    ? (updater as (c: T) => T)(current)
    : updater;
}

export type SequenceCreatorActions = {
  setMode: (next: SetStateAction<SequenceCreatorMode>) => void;
  setGenerationMode: (next: SetStateAction<GenerationMode>) => void;
  setPrompt: (next: SetStateAction<string>) => void;
  setEditPrompt: (next: SetStateAction<string>) => void;
  setDraftGroups: (next: SetStateAction<SequenceDraftGroup[]>) => void;
  setSelectedGroupId: (next: SetStateAction<string | null>) => void;
  setSelectedDraftIndex: (next: SetStateAction<number>) => void;
  setGenerationNote: (next: SetStateAction<string | null>) => void;
  setActionError: (next: SetStateAction<string | null>) => void;
  setClassifierVerdict: (next: SetStateAction<ClassifierVerdict | null>) => void;
  setForkPending: (next: SetStateAction<ForkPending | null>) => void;
  setGeneratedComponent: (next: SetStateAction<GeneratedComponent | null>) => void;
  reset: () => void;
};

export type SequenceCreatorState = SequenceCreatorPersistedState & SequenceCreatorActions;

const INITIAL_STATE: SequenceCreatorPersistedState = {
  mode: 'generate',
  generationMode: 'auto',
  prompt: '',
  editPrompt: '',
  draftGroups: [],
  selectedGroupId: null,
  selectedDraftIndex: 0,
  generationNote: null,
  actionError: null,
  classifierVerdict: null,
  forkPending: null,
  generatedComponent: null,
};

const STORAGE_KEY = 'reigh:video-editor:sequence-creator';

const sequenceCreatorStore = createStore<SequenceCreatorState>()(
  persist(
    (set) => ({
      ...INITIAL_STATE,
      setMode: (next) => set((state) => ({ mode: applyUpdater(state.mode, next) })),
      setGenerationMode: (next) => set((state) => ({ generationMode: applyUpdater(state.generationMode, next) })),
      setPrompt: (next) => set((state) => ({ prompt: applyUpdater(state.prompt, next) })),
      setEditPrompt: (next) => set((state) => ({ editPrompt: applyUpdater(state.editPrompt, next) })),
      setDraftGroups: (next) => set((state) => ({ draftGroups: applyUpdater(state.draftGroups, next) })),
      setSelectedGroupId: (next) => set((state) => ({ selectedGroupId: applyUpdater(state.selectedGroupId, next) })),
      setSelectedDraftIndex: (next) => set((state) => ({ selectedDraftIndex: applyUpdater(state.selectedDraftIndex, next) })),
      setGenerationNote: (next) => set((state) => ({ generationNote: applyUpdater(state.generationNote, next) })),
      setActionError: (next) => set((state) => ({ actionError: applyUpdater(state.actionError, next) })),
      setClassifierVerdict: (next) => set((state) => ({ classifierVerdict: applyUpdater(state.classifierVerdict, next) })),
      setForkPending: (next) => set((state) => ({ forkPending: applyUpdater(state.forkPending, next) })),
      setGeneratedComponent: (next) => set((state) => ({ generatedComponent: applyUpdater(state.generatedComponent, next) })),
      reset: () => set(() => ({ ...INITIAL_STATE })),
    }),
    {
      name: STORAGE_KEY,
      version: 1,
      storage: createJSONStorage(() => localStorage),
      // Drop transient feedback strings from persisted output: stale notes
      // and errors after a reload are confusing and never accurate.
      partialize: (state): Partial<SequenceCreatorPersistedState> => ({
        mode: state.mode,
        generationMode: state.generationMode,
        prompt: state.prompt,
        editPrompt: state.editPrompt,
        draftGroups: state.draftGroups,
        selectedGroupId: state.selectedGroupId,
        selectedDraftIndex: state.selectedDraftIndex,
        classifierVerdict: state.classifierVerdict,
        forkPending: state.forkPending,
        generatedComponent: state.generatedComponent,
      }),
      migrate: (persistedState) => persistedState as SequenceCreatorPersistedState,
    },
  ),
);

export function useSequenceCreatorStore<T>(
  selector: (state: SequenceCreatorState) => T,
  equalityFn?: (left: T, right: T) => boolean,
): T {
  return useStoreWithEqualityFn(sequenceCreatorStore, selector, equalityFn ?? shallow);
}

export function getSequenceCreatorStore() {
  return sequenceCreatorStore;
}
