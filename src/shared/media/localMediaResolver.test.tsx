import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useLocalMediaUrl } from './localMediaResolver';

const loadHandleMock = vi.fn();
const createObjectURLMock = vi.fn();
const revokeObjectURLMock = vi.fn();

vi.mock('@/shared/lib/media/localHandleStore', () => ({
  loadHandle: (...args: unknown[]) => loadHandleMock(...args),
}));

describe('useLocalMediaUrl', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    createObjectURLMock.mockReturnValue('blob:local-media');
    global.URL.createObjectURL = createObjectURLMock as typeof URL.createObjectURL;
    global.URL.revokeObjectURL = revokeObjectURLMock as typeof URL.revokeObjectURL;
  });

  afterEach(() => {
    loadHandleMock.mockReset();
  });

  it('passes through remote media urls unchanged', () => {
    const { result } = renderHook(() => useLocalMediaUrl({
      id: 'gen-remote',
      location: 'https://example.com/remote.png',
      storage_mode: 'remote',
    }));

    expect(result.current).toEqual({
      url: 'https://example.com/remote.png',
      state: 'ready',
    });
  });

  it('memoizes object urls per generation id and revokes only after the final consumer unmounts', async () => {
    const handle = {
      kind: 'file',
      name: 'clip.mov',
      queryPermission: vi.fn().mockResolvedValue('granted'),
      requestPermission: vi.fn(),
      getFile: vi.fn().mockResolvedValue(new File(['video'], 'clip.mov', { type: 'video/mp4' })),
    };
    loadHandleMock.mockResolvedValue(handle);

    const generation = {
      id: 'gen-local',
      location: null,
      storage_mode: 'local' as const,
      local_handle_id: 'handle-1',
    };

    const first = renderHook(() => useLocalMediaUrl(generation));
    const second = renderHook(() => useLocalMediaUrl(generation));

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(first.result.current).toEqual({ url: 'blob:local-media', state: 'ready' });
    expect(second.result.current).toEqual({ url: 'blob:local-media', state: 'ready' });
    expect(createObjectURLMock).toHaveBeenCalledTimes(1);

    first.unmount();
    expect(revokeObjectURLMock).not.toHaveBeenCalled();

    second.unmount();
    expect(revokeObjectURLMock).toHaveBeenCalledWith('blob:local-media');
  });

  it('returns needs-permission without auto-requesting when permission is not granted', async () => {
    const handle = {
      kind: 'file',
      name: 'frame.png',
      queryPermission: vi.fn().mockResolvedValue('prompt'),
      requestPermission: vi.fn(),
      getFile: vi.fn(),
    };
    loadHandleMock.mockResolvedValue(handle);

    const { result } = renderHook(() => useLocalMediaUrl({
      id: 'gen-needs-permission',
      location: null,
      storage_mode: 'local',
      local_handle_id: 'handle-2',
    }));

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current).toEqual({ url: null, state: 'needs-permission' });
    expect(handle.requestPermission).not.toHaveBeenCalled();
  });
});
