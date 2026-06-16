// @vitest-environment jsdom
import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { useTimeline } from '@/tools/video-editor/hooks/useTimeline.ts';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider.ts';
import { createDefaultTimelineConfig } from '@/tools/video-editor/lib/defaults.ts';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useTimeline', () => {
  it('suppresses direct saveTimeline mutations when provider persistence is disabled', async () => {
    const config = createDefaultTimelineConfig();
    const provider: DataProvider = {
      persistenceEnabled: false,
      loadTimeline: vi.fn(async () => ({ config, configVersion: 7 })),
      saveTimeline: vi.fn(async () => 8),
      loadAssetRegistry: vi.fn(async () => ({ assets: {} })),
      resolveAssetUrl: vi.fn(async (file: string) => file),
    };

    const hook = renderHook(
      () => useTimeline(provider, 'timeline-1'),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(hook.result.current.data).toEqual(config));

    await act(async () => {
      await hook.result.current.saveTimeline.mutateAsync({
        ...config,
        output: { ...config.output, file: 'read-only.mp4' },
      });
    });

    expect(provider.saveTimeline).not.toHaveBeenCalled();
  });
});
