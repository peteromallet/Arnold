import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  __resetPanesStoreForTests,
  bootstrapPanesStore,
  clearPanesStoreBootstrap,
  usePanesStoreApi,
  type PanesStoreBootstrapInput,
} from './panesStore';

function makeBootstrapInput(owner: symbol): PanesStoreBootstrapInput {
  return {
    owner,
    viewportHeight: 900,
    locks: {
      shots: false,
      tasks: true,
      gens: false,
      editor: false,
    },
    isGenerationsPaneOpen: false,
    isEditorPaneOpen: false,
    isTasksPaneOpen: true,
    setIsGenerationsPaneLocked: vi.fn(),
    setIsEditorPaneLocked: vi.fn(),
    setIsShotsPaneLocked: vi.fn(),
    setIsTasksPaneLocked: vi.fn(),
    setIsGenerationsPaneOpen: vi.fn(),
    setIsEditorPaneOpen: vi.fn(),
    setIsTasksPaneOpen: vi.fn(),
    resetAllPaneLocks: vi.fn(),
  };
}

describe('panesStore bootstrap', () => {
  beforeEach(() => {
    __resetPanesStoreForTests();
  });

  afterEach(() => {
    __resetPanesStoreForTests();
  });

  it('does not notify subscribers again when only bootstrap callback identities change', () => {
    const owner = Symbol('test-bootstrap-owner');
    const store = usePanesStoreApi();
    let notificationCount = 0;
    const unsubscribe = store.subscribe(() => {
      notificationCount += 1;
    });

    try {
      const firstInput = makeBootstrapInput(owner);
      const secondInput = makeBootstrapInput(owner);
      expect(firstInput.setIsTasksPaneOpen).not.toBe(secondInput.setIsTasksPaneOpen);

      bootstrapPanesStore(firstInput);
      expect(notificationCount).toBe(1);

      bootstrapPanesStore(secondInput);
      expect(notificationCount).toBe(1);
    } finally {
      unsubscribe();
      clearPanesStoreBootstrap(owner);
    }
  });
});
