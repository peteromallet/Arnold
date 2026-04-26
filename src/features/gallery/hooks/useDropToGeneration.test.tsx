import React from 'react';
import { beforeAll, describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const createGenerationForUploadedImageMock = vi.fn();
const createGenerationForUploadedVideoMock = vi.fn();
const toastErrorMock = vi.fn();
const toastInfoMock = vi.fn();
const normalizeAndPresentErrorMock = vi.fn();

vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProjectSelectionContext: () => ({ selectedProjectId: 'project-1' }),
}));

vi.mock('@/shared/lib/media/createGenerationFromFile', () => ({
  createGenerationForUploadedImage: (...args: unknown[]) => createGenerationForUploadedImageMock(...args),
  createGenerationForUploadedVideo: (...args: unknown[]) => createGenerationForUploadedVideoMock(...args),
}));

vi.mock('@/shared/components/ui/runtime/sonner', () => ({
  toast: {
    error: (...args: unknown[]) => toastErrorMock(...args),
    info: (...args: unknown[]) => toastInfoMock(...args),
  },
}));

vi.mock('@/shared/lib/errorHandling/runtimeError', () => ({
  normalizeAndPresentError: (...args: unknown[]) => normalizeAndPresentErrorMock(...args),
}));

let useDropToGeneration: typeof import('./useDropToGeneration').useDropToGeneration;

function createWrapper(queryClient: QueryClient) {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useDropToGeneration', () => {
  beforeAll(async () => {
    ({ useDropToGeneration } = await import('./useDropToGeneration'));
  });

  beforeEach(() => {
    vi.clearAllMocks();
    createGenerationForUploadedImageMock.mockResolvedValue({ id: 'gen-image' });
    createGenerationForUploadedVideoMock.mockResolvedValue({ id: 'gen-video' });
  });

  it('uploads supported files and invalidates only the selected project generation scope', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries').mockResolvedValue();

    const { result } = renderHook(() => useDropToGeneration(), {
      wrapper: createWrapper(queryClient),
    });

    const imageFile = new File(['image'], 'frame.png', { type: 'image/png' });
    const videoFile = new File(['video'], 'clip.mp4', { type: 'video/mp4' });

    await act(async () => {
      await result.current([imageFile, videoFile]);
    });

    expect(createGenerationForUploadedImageMock).toHaveBeenCalledWith({
      imageFile,
      projectId: 'project-1',
    });
    expect(createGenerationForUploadedVideoMock).toHaveBeenCalledWith({
      videoFile,
      projectId: 'project-1',
    });
    expect(invalidateQueriesSpy).toHaveBeenCalledWith({
      queryKey: ['unified-generations', 'project', 'project-1'],
    });
    expect(toastErrorMock).not.toHaveBeenCalled();
  });

  it('shows an informational toast and skips oversized files', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries').mockResolvedValue();

    const { result } = renderHook(() => useDropToGeneration(), {
      wrapper: createWrapper(queryClient),
    });

    const oversizedImage = new File(['x'], 'huge.png', { type: 'image/png' });
    Object.defineProperty(oversizedImage, 'size', { value: 25 * 1024 * 1024 });

    await act(async () => {
      await result.current([oversizedImage]);
    });

    expect(createGenerationForUploadedImageMock).not.toHaveBeenCalled();
    expect(createGenerationForUploadedVideoMock).not.toHaveBeenCalled();
    expect(toastInfoMock).toHaveBeenCalledTimes(1);
    expect(invalidateQueriesSpy).not.toHaveBeenCalled();
  });

  it('shows an error toast for unsupported files', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    const { result } = renderHook(() => useDropToGeneration(), {
      wrapper: createWrapper(queryClient),
    });

    const unsupportedFile = new File(['text'], 'notes.txt', { type: 'text/plain' });

    await act(async () => {
      await result.current([unsupportedFile]);
    });

    expect(toastErrorMock).toHaveBeenCalledWith('Unsupported file type: notes.txt');
    expect(createGenerationForUploadedImageMock).not.toHaveBeenCalled();
    expect(createGenerationForUploadedVideoMock).not.toHaveBeenCalled();
  });
});
