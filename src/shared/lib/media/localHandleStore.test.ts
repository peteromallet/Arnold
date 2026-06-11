import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createFakeIndexedDB } from 'fake-indexeddb';
import {
  deleteHandle,
  ensurePermission,
  getDirectoryHandle,
  getFileHandle,
  listHandleIds,
  loadHandle,
  saveDirectoryHandle,
  saveFileHandle,
  saveHandle,
} from './localHandleStore';

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

  it('saves and loads a file handle via typed helpers', async () => {
    const handle = {
      kind: 'file' as const,
      name: 'photo.jpg',
      queryPermission: vi.fn(),
      requestPermission: vi.fn(),
      getFile: vi.fn(),
    };

    await saveFileHandle('fh-1', handle);

    const loaded = await getFileHandle('fh-1');
    expect(loaded).not.toBeNull();
    expect(loaded?.kind).toBe('file');
    expect(loaded?.name).toBe('photo.jpg');
    expect(typeof loaded?.getFile).toBe('function');
  });

  it('saves and loads a directory handle via typed helpers', async () => {
    const handle = {
      kind: 'directory' as const,
      name: 'my-folder',
      queryPermission: vi.fn(),
      requestPermission: vi.fn(),
    };

    await saveDirectoryHandle('dh-1', handle);

    const loaded = await getDirectoryHandle('dh-1');
    expect(loaded).not.toBeNull();
    expect(loaded?.kind).toBe('directory');
    expect(loaded?.name).toBe('my-folder');
  });

  it('getFileHandle returns null for a directory handle', async () => {
    const dirHandle = {
      kind: 'directory' as const,
      name: 'assets',
      queryPermission: vi.fn(),
      requestPermission: vi.fn(),
    };

    await saveDirectoryHandle('dh-2', dirHandle);

    await expect(getFileHandle('dh-2')).resolves.toBeNull();
  });

  it('getDirectoryHandle returns null for a file handle', async () => {
    const fileHandle = {
      kind: 'file' as const,
      name: 'doc.pdf',
      queryPermission: vi.fn(),
      requestPermission: vi.fn(),
      getFile: vi.fn(),
    };

    await saveFileHandle('fh-2', fileHandle);

    await expect(getDirectoryHandle('fh-2')).resolves.toBeNull();
  });

  it('generic saveHandle and loadHandle work for both file and directory handles', async () => {
    const fileHandle = {
      kind: 'file' as const,
      name: 'generic-file.png',
      queryPermission: vi.fn(),
      requestPermission: vi.fn(),
      getFile: vi.fn(),
    };
    const dirHandle = {
      kind: 'directory' as const,
      name: 'generic-dir',
      queryPermission: vi.fn(),
      requestPermission: vi.fn(),
    };

    await saveHandle('g-1', fileHandle);
    await saveHandle('g-2', dirHandle);

    const loadedFile = await loadHandle('g-1');
    const loadedDir = await loadHandle('g-2');

    expect(loadedFile?.kind).toBe('file');
    expect(loadedFile?.name).toBe('generic-file.png');
    expect(typeof (loadedFile as { getFile?: unknown }).getFile).toBe('function');

    expect(loadedDir?.kind).toBe('directory');
    expect(loadedDir?.name).toBe('generic-dir');
  });

  it('getFileHandle returns null for a missing handle', async () => {
    await expect(getFileHandle('nonexistent')).resolves.toBeNull();
  });

  it('getDirectoryHandle returns null for a missing handle', async () => {
    await expect(getDirectoryHandle('nonexistent')).resolves.toBeNull();
  });

  it('deleteHandle removes file handles from typed lookups', async () => {
    const handle = {
      kind: 'file' as const,
      name: 'to-delete.png',
      queryPermission: vi.fn(),
      requestPermission: vi.fn(),
      getFile: vi.fn(),
    };

    await saveFileHandle('fh-del', handle);
    await expect(getFileHandle('fh-del')).resolves.not.toBeNull();

    await deleteHandle('fh-del');
    await expect(getFileHandle('fh-del')).resolves.toBeNull();
  });

  it('deleteHandle removes directory handles from typed lookups', async () => {
    const handle = {
      kind: 'directory' as const,
      name: 'to-delete-dir',
      queryPermission: vi.fn(),
      requestPermission: vi.fn(),
    };

    await saveDirectoryHandle('dh-del', handle);
    await expect(getDirectoryHandle('dh-del')).resolves.not.toBeNull();

    await deleteHandle('dh-del');
    await expect(getDirectoryHandle('dh-del')).resolves.toBeNull();
  });

  it('listHandleIds includes directory handles', async () => {
    const fileHandle = {
      kind: 'file' as const,
      name: 'f.png',
      queryPermission: vi.fn(),
      requestPermission: vi.fn(),
      getFile: vi.fn(),
    };
    const dirHandle = {
      kind: 'directory' as const,
      name: 'd',
      queryPermission: vi.fn(),
      requestPermission: vi.fn(),
    };

    await saveFileHandle('fh-list', fileHandle);
    await saveDirectoryHandle('dh-list', dirHandle);

    const ids = await listHandleIds();
    expect(ids).toContain('fh-list');
    expect(ids).toContain('dh-list');
  });

  it('ensurePermission with directory handle and readwrite mode queries then requests', async () => {
    const queryPermission = vi.fn().mockResolvedValue('prompt' as PermissionState);
    const requestPermission = vi.fn().mockResolvedValue('granted' as PermissionState);
    const dirHandle = {
      kind: 'directory' as const,
      name: 'rw-dir',
      queryPermission,
      requestPermission,
    };

    vi.stubGlobal('navigator', { userActivation: { isActive: true } });

    const result = await ensurePermission(dirHandle, 'readwrite');

    expect(queryPermission).toHaveBeenCalledWith({ mode: 'readwrite' });
    expect(requestPermission).toHaveBeenCalledWith({ mode: 'readwrite' });
    expect(result).toBe('granted');
  });

  it('ensurePermission with directory handle returns existing granted without requesting', async () => {
    const queryPermission = vi.fn().mockResolvedValue('granted' as PermissionState);
    const requestPermission = vi.fn();
    const dirHandle = {
      kind: 'directory' as const,
      name: 'granted-dir',
      queryPermission,
      requestPermission,
    };

    const result = await ensurePermission(dirHandle, 'readwrite');

    expect(queryPermission).toHaveBeenCalledWith({ mode: 'readwrite' });
    expect(requestPermission).not.toHaveBeenCalled();
    expect(result).toBe('granted');
  });

  it('ensurePermission with file handle preserves existing behavior', async () => {
    const queryPermission = vi.fn().mockResolvedValue('prompt' as PermissionState);
    const requestPermission = vi.fn().mockResolvedValue('granted' as PermissionState);
    const fileHandle = {
      kind: 'file' as const,
      name: 'perm-file.png',
      queryPermission,
      requestPermission,
      getFile: vi.fn(),
    };

    vi.stubGlobal('navigator', { userActivation: { isActive: true } });

    const result = await ensurePermission(fileHandle, 'read');

    expect(queryPermission).toHaveBeenCalledWith({ mode: 'read' });
    expect(requestPermission).toHaveBeenCalledWith({ mode: 'read' });
    expect(result).toBe('granted');
  });
});
