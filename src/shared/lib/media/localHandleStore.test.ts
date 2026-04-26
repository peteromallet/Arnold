import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createFakeIndexedDB } from 'fake-indexeddb';
import { deleteHandle, listHandleIds, loadHandle, saveHandle } from './localHandleStore';

describe('localHandleStore', () => {
  beforeEach(() => {
    vi.stubGlobal('indexedDB', createFakeIndexedDB());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('saves and loads a persisted handle', async () => {
    const handle = {
      kind: 'file',
      name: 'image.png',
      queryPermission: vi.fn(),
      requestPermission: vi.fn(),
    };

    await saveHandle('handle-1', handle);

    await expect(loadHandle('handle-1')).resolves.toBe(handle);
  });

  it('lists handle ids and removes deleted handles', async () => {
    const firstHandle = {
      kind: 'file',
      name: 'first.png',
      queryPermission: vi.fn(),
      requestPermission: vi.fn(),
    };
    const secondHandle = {
      kind: 'file',
      name: 'second.png',
      queryPermission: vi.fn(),
      requestPermission: vi.fn(),
    };

    await saveHandle('handle-1', firstHandle);
    await saveHandle('handle-2', secondHandle);

    await expect(listHandleIds()).resolves.toEqual(['handle-1', 'handle-2']);

    await deleteHandle('handle-1');

    await expect(listHandleIds()).resolves.toEqual(['handle-2']);
    await expect(loadHandle('handle-1')).resolves.toBeNull();
  });
});
