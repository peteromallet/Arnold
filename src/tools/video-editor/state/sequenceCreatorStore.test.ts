import { describe, expect, it } from 'vitest';
import { getSequenceCreatorStore } from '@/tools/video-editor/state/sequenceCreatorStore';

describe('sequenceCreatorStore', () => {
  const getStore = () => getSequenceCreatorStore();

  it('initializes with sensible defaults', () => {
    const store = getStore();
    const state = store.getState();
    expect(state.mode).toBe('generate');
    expect(state.generationMode).toBe('auto');
    expect(state.prompt).toBe('');
    expect(state.editPrompt).toBe('');
    expect(state.draftGroups).toEqual([]);
    expect(state.selectedGroupId).toBeNull();
    expect(state.selectedDraftIndex).toBe(0);
    expect(state.generationNote).toBeNull();
    expect(state.actionError).toBeNull();
    expect(state.classifierVerdict).toBeNull();
    expect(state.forkPending).toBeNull();
    expect(state.generatedComponent).toBeNull();
    expect(state.generatedComponentSourceClipType).toBeUndefined();
  });

  it('resets to initial state', () => {
    const store = getStore();
    store.getState().setMode('edit');
    store.getState().setPrompt('test prompt');
    store.getState().setDraftGroups([
      {
        id: 'group-1',
        name: 'Test',
        prompt: 'test',
        drafts: [{ clipType: 'image-jump', hold: 3, params: {} }],
      },
    ]);
    store.getState().reset();
    const state = store.getState();
    expect(state.mode).toBe('generate');
    expect(state.prompt).toBe('');
    expect(state.draftGroups).toEqual([]);
  });

  it('persists and restores mode transitions', () => {
    const store = getStore();
    store.getState().setMode('edit');
    expect(store.getState().mode).toBe('edit');
    store.getState().setMode('library');
    expect(store.getState().mode).toBe('library');
    store.getState().setMode('generate');
    expect(store.getState().mode).toBe('generate');
  });

  it('handles draft group management', () => {
    const store = getStore();
    const group = {
      id: 'group-1',
      name: 'Test Group',
      prompt: 'Make it bounce',
      drafts: [
        { clipType: 'image-jump', hold: 3, params: { title: 'Test' } },
      ],
    };
    store.getState().setDraftGroups([group]);
    expect(store.getState().draftGroups).toHaveLength(1);
    expect(store.getState().draftGroups[0].name).toBe('Test Group');

    store.getState().setDraftGroups([]);
    expect(store.getState().draftGroups).toHaveLength(0);
  });

  it('manages prompt state', () => {
    const store = getStore();
    store.getState().setPrompt('A new animation');
    expect(store.getState().prompt).toBe('A new animation');
  });

  it('manages generated component state', () => {
    const store = getStore();
    store.getState().setGeneratedComponent({
      code: 'export default () => <div>Hello</div>',
      name: 'TestComponent',
      description: 'A test component',
      schemaJson: { type: 'object' },
      defaultsJson: { text: 'Hello' },
    });
    expect(store.getState().generatedComponent?.name).toBe('TestComponent');
    store.getState().setGeneratedComponent(null);
    expect(store.getState().generatedComponent).toBeNull();
  });

  it('tracks generated component source clipType', () => {
    const store = getStore();
    store.getState().setGeneratedComponentSourceClipType('custom:my-component-123');
    expect(store.getState().generatedComponentSourceClipType).toBe('custom:my-component-123');
    store.getState().setGeneratedComponentSourceClipType(undefined);
    expect(store.getState().generatedComponentSourceClipType).toBeUndefined();
  });
});
