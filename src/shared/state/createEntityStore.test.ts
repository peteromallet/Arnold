// @vitest-environment jsdom

import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createEntityStore, type EntityStoreConfig } from './createEntityStore';

interface TestSettings {
  count: number;
  text: string;
}

function createTestStore(overrides?: Partial<EntityStoreConfig<TestSettings>>) {
  const load = vi.fn(async () => ({
    db: null,
    lastUsed: null,
  }));
  const save = vi.fn(async () => undefined);

  const store = createEntityStore<TestSettings>({
    toolId: 'test-store',
    defaults: {
      count: 0,
      text: '',
    },
    load,
    save,
    textFieldKeys: ['text'],
    ...overrides,
  });

  return { store, load, save };
}

describe('createEntityStore', () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  it('bootstraps entities with db data first, then last-used data, then defaults', () => {
    const { store } = createTestStore();

    store.getState().bootstrapEntity({
      entityId: 'db-first',
      db: { count: 7, text: 'db' },
      lastUsed: { count: 4, text: 'last-used' },
    });
    store.getState().bootstrapEntity({
      entityId: 'last-used',
      db: null,
      lastUsed: { count: 3, text: 'fallback' },
    });
    store.getState().bootstrapEntity({
      entityId: 'defaults',
      db: null,
      lastUsed: null,
    });

    expect(store.getState().entities['db-first']).toMatchObject({
      settings: { count: 7, text: 'db' },
      savedSettings: { count: 7, text: 'db' },
      hasPersistedData: true,
      status: 'ready',
    });
    expect(store.getState().entities['last-used']).toMatchObject({
      settings: { count: 3, text: 'fallback' },
      savedSettings: { count: 3, text: 'fallback' },
      hasPersistedData: false,
      status: 'ready',
    });
    expect(store.getState().entities.defaults).toMatchObject({
      settings: { count: 0, text: '' },
      savedSettings: { count: 0, text: '' },
      hasPersistedData: false,
      status: 'ready',
    });
  });

  it('creates one shared store per factory instance and lazily loads an entity once', async () => {
    const load = vi.fn(async () => ({
        db: { count: 2, text: 'loaded' },
        lastUsed: null,
      }));
    const { store } = createTestStore({
      load,
    });

    const first = renderHook(() => store.useEntity('shared'));
    const second = renderHook(() => store.useEntity('shared'));

    await waitFor(() => {
      expect(first.result.current.status).toBe('ready');
      expect(second.result.current.status).toBe('ready');
    });

    expect(load).toHaveBeenCalledTimes(1);
    expect(store.getState().entities.shared.settings).toEqual({ count: 2, text: 'loaded' });

    act(() => {
      first.result.current.updateField('count', 9);
    });

    expect(second.result.current.settings.count).toBe(9);
  });

  it('applies optimistic updates and saves them after the debounce window', async () => {
    vi.useFakeTimers();
    const save = vi.fn(async () => undefined);
    const { store } = createTestStore({
      save,
    });

    store.getState().bootstrapEntity({
      entityId: 'entity-1',
      db: null,
      lastUsed: null,
    });

    store.getState().updateField('entity-1', 'count', 4);

    expect(store.getState().entities['entity-1'].settings.count).toBe(4);
    expect(save).not.toHaveBeenCalled();

    vi.advanceTimersByTime(299);
    expect(save).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    await Promise.resolve();

    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith('entity-1', { count: 4, text: '' });
    expect(store.getState().entities['entity-1'].savedSettings).toEqual({ count: 4, text: '' });
  });

  it('keeps text-field edits local until flushed', async () => {
    vi.useFakeTimers();
    const save = vi.fn(async () => undefined);
    const { store } = createTestStore({
      save,
    });

    store.getState().bootstrapEntity({
      entityId: 'entity-1',
      db: null,
      lastUsed: null,
    });

    store.getState().updateField('entity-1', 'text', 'draft');

    vi.advanceTimersByTime(500);
    await Promise.resolve();

    expect(save).not.toHaveBeenCalled();
    expect(store.getState().entities['entity-1'].settings.text).toBe('draft');

    await store.getState().flushTextFields('entity-1');

    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith('entity-1', { count: 0, text: 'draft' });
  });

  it('reverts to the last bootstrapped or saved snapshot and resets locally without saving', async () => {
    vi.useFakeTimers();
    const save = vi.fn(async () => undefined);
    const { store } = createTestStore({
      save,
    });

    store.getState().bootstrapEntity({
      entityId: 'entity-1',
      db: null,
      lastUsed: { count: 5, text: 'seed' },
    });

    expect(store.getState().entities['entity-1'].settings).toEqual({ count: 5, text: 'seed' });

    store.getState().updateFields('entity-1', { count: 8, text: 'edited' });
    store.getState().revert('entity-1');

    expect(store.getState().entities['entity-1'].settings).toEqual({ count: 5, text: 'seed' });

    store.getState().updateField('entity-1', 'count', 11);
    store.getState().reset('entity-1');

    expect(store.getState().entities['entity-1'].settings).toEqual({ count: 0, text: '' });
    expect(store.getState().isDirty('entity-1')).toBe(false);

    store.getState().reset('entity-1', { count: 6, text: 'custom-defaults' });

    expect(store.getState().entities['entity-1'].settings).toEqual({ count: 6, text: 'custom-defaults' });
    expect(store.getState().isDirty('entity-1')).toBe(false);

    vi.runAllTimers();
    await Promise.resolve();

    expect(save).not.toHaveBeenCalled();
  });

  it('retains save errors until a later successful transition clears them', async () => {
    const save = vi
      .fn<(_: string, __: TestSettings) => Promise<void>>()
      .mockRejectedValueOnce(new Error('save failed'))
      .mockResolvedValueOnce(undefined);
    const { store } = createTestStore({
      save,
    });

    store.getState().bootstrapEntity({
      entityId: 'entity-1',
      db: null,
      lastUsed: null,
    });

    store.getState().updateField('entity-1', 'count', 3);
    await expect(store.getState().saveImmediate('entity-1')).rejects.toThrow('save failed');

    expect(store.getState().entities['entity-1'].status).toBe('error');
    expect(store.getState().entities['entity-1'].error?.message).toBe('save failed');
    expect(store.getState().isDirty('entity-1')).toBe(true);

    await store.getState().saveImmediate('entity-1');

    expect(store.getState().entities['entity-1']).toMatchObject({
      status: 'ready',
      error: null,
      savedSettings: { count: 3, text: '' },
    });
    expect(store.getState().isDirty('entity-1')).toBe(false);
  });

  it('refuses external sync while local edits or pending persistence exist', async () => {
    vi.useFakeTimers();
    const { store, save } = createTestStore();

    store.getState().bootstrapEntity({
      entityId: 'entity-1',
      db: { count: 1, text: 'db' },
      lastUsed: null,
    });

    store.getState().updateField('entity-1', 'count', 2);

    expect(store.getState().hasPendingPersistence('entity-1')).toBe(true);
    expect(
      store.getState().syncExternalEntity({
        entityId: 'entity-1',
        db: { count: 9, text: 'external' },
        lastUsed: null,
      })
    ).toBe(false);
    expect(store.getState().entities['entity-1'].settings).toEqual({ count: 2, text: 'db' });

    vi.runAllTimers();
    await Promise.resolve();
    expect(save).toHaveBeenCalledTimes(1);

    store.getState().updateTextField('entity-1', 'text', 'local draft');

    expect(store.getState().hasPendingPersistence('entity-1')).toBe(true);
    expect(
      store.getState().syncExternalEntity({
        entityId: 'entity-1',
        db: { count: 7, text: 'external draft' },
        lastUsed: null,
      })
    ).toBe(false);

    await store.getState().flushTextFields('entity-1');

    expect(
      store.getState().syncExternalEntity({
        entityId: 'entity-1',
        db: { count: 5, text: 'external synced' },
        lastUsed: null,
      })
    ).toBe(true);
    expect(store.getState().entities['entity-1']).toMatchObject({
      settings: { count: 5, text: 'external synced' },
      savedSettings: { count: 5, text: 'external synced' },
      status: 'ready',
    });
  });

  it('isolates subscriptions by entity id', async () => {
    const { store } = createTestStore();
    const renderCounts = {
      alpha: 0,
      beta: 0,
    };

    const alpha = renderHook(() => {
      renderCounts.alpha += 1;
      return store.useEntity('alpha');
    });
    const beta = renderHook(() => {
      renderCounts.beta += 1;
      return store.useEntity('beta');
    });

    await waitFor(() => {
      expect(alpha.result.current.status).toBe('ready');
      expect(beta.result.current.status).toBe('ready');
    });

    const betaRenderCountBeforeUpdate = renderCounts.beta;

    act(() => {
      alpha.result.current.updateField('count', 12);
    });

    expect(alpha.result.current.settings.count).toBe(12);
    expect(renderCounts.beta).toBe(betaRenderCountBeforeUpdate);
  });
});
