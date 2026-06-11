import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import VideoEditorPage from '@/tools/video-editor/pages/VideoEditorPage.tsx';

const state = vi.hoisted(() => ({
  auth: { userId: 'user-1' as string | null },
  project: { selectedProjectId: 'project-1' as string | null },
  settings: {
    settings: { lastTimelineId: 'timeline-1' as string | undefined },
    update: vi.fn(async () => undefined),
  },
  timelines: {
    data: [{ id: 'timeline-1', name: 'Main timeline', updated_at: '2026-06-11T10:00:00Z' }],
    isLoading: false,
    error: null as Error | null,
    createTimeline: {
      isPending: false,
      mutateAsync: vi.fn(async () => ({ id: 'created-timeline' })),
    },
    renameTimeline: {
      mutateAsync: vi.fn(async () => undefined),
    },
    deleteTimeline: {
      mutateAsync: vi.fn(async () => undefined),
    },
  },
  providerMounts: 0,
  providerUnmounts: 0,
  supabaseCtor: vi.fn(function MockSupabaseProvider(this: Record<string, unknown>, options: unknown) {
    this.kind = 'supabase';
    this.options = options;
    this.resolveAssetUrl = vi.fn();
    this.loadTimeline = vi.fn();
    this.saveTimeline = vi.fn();
    this.loadAssetRegistry = vi.fn();
  }),
  bridgeCtor: vi.fn(function MockBridgeProvider(this: Record<string, unknown>, options: unknown) {
    this.kind = 'bridge';
    this.options = options;
    this.persistenceEnabled = false;
    this.resolveAssetUrl = vi.fn();
    this.loadTimeline = vi.fn();
    this.saveTimeline = vi.fn();
    this.loadAssetRegistry = vi.fn();
  }),
}));

vi.mock('@/shared/contexts/AuthContext.tsx', () => ({
  useAuth: () => state.auth,
}));

vi.mock('@/shared/contexts/ProjectContext.tsx', () => ({
  useProjectSelectionContext: () => state.project,
}));

vi.mock('@/shared/hooks/settings/useToolSettings.ts', () => ({
  useToolSettings: () => state.settings,
}));

vi.mock('@/tools/video-editor/hooks/useTimelinesList.ts', () => ({
  useTimelinesList: () => state.timelines,
}));

vi.mock('@/tools/video-editor/data/SupabaseDataProvider.ts', () => ({
  SupabaseDataProvider: state.supabaseCtor,
}));

vi.mock('@/tools/video-editor/data/AstridBridgeDataProvider.ts', () => ({
  AstridBridgeDataProvider: state.bridgeCtor,
}));

vi.mock('@/tools/video-editor/components/ReighVideoEditorShell.tsx', () => ({
  ReighVideoEditorShell: ({ timelineId }: { timelineId: string }) => (
    <div data-testid="video-editor-shell">{timelineId}</div>
  ),
}));

vi.mock('@/tools/video-editor/contexts/VideoEditorProvider.tsx', async () => {
  const ReactModule = await import('react');

  return {
    VideoEditorProvider: ({
      dataProvider,
      timelineId,
      timelineName,
      children,
    }: {
      dataProvider: { kind?: string };
      timelineId: string;
      timelineName?: string | null;
      children: React.ReactNode;
    }) => {
      ReactModule.useEffect(() => {
        state.providerMounts += 1;
        return () => {
          state.providerUnmounts += 1;
        };
      }, []);

      return (
        <div
          data-testid="video-editor-provider"
          data-kind={dataProvider.kind ?? 'unknown'}
          data-timeline-id={timelineId}
          data-timeline-name={timelineName ?? ''}
        >
          {children}
        </div>
      );
    },
  };
});

function renderPage(initialEntry: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <VideoEditorPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('VideoEditorPage', () => {
  const originalDEV = import.meta.env.DEV;

  beforeEach(() => {
    (import.meta.env as Record<string, unknown>).DEV = true;
    window.localStorage.clear();
    state.auth.userId = 'user-1';
    state.project.selectedProjectId = 'project-1';
    state.settings.settings = { lastTimelineId: 'timeline-1' };
    state.settings.update.mockClear();
    state.timelines.data = [{ id: 'timeline-1', name: 'Main timeline', updated_at: '2026-06-11T10:00:00Z' }];
    state.timelines.isLoading = false;
    state.timelines.error = null;
    state.timelines.createTimeline.isPending = false;
    state.timelines.createTimeline.mutateAsync.mockClear();
    state.timelines.renameTimeline.mutateAsync.mockClear();
    state.timelines.deleteTimeline.mutateAsync.mockClear();
    state.providerMounts = 0;
    state.providerUnmounts = 0;
    state.supabaseCtor.mockClear();
    state.bridgeCtor.mockClear();
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    (import.meta.env as Record<string, unknown>).DEV = originalDEV;
  });

  it('uses SupabaseDataProvider in App mode without bridge requests', async () => {
    renderPage('/tools/video-editor?timeline=timeline-1');

    const provider = await screen.findByTestId('video-editor-provider');

    expect(provider).toHaveAttribute('data-kind', 'supabase');
    expect(state.supabaseCtor).toHaveBeenCalledWith({ projectId: 'project-1', userId: 'user-1' });
    expect(state.bridgeCtor).not.toHaveBeenCalled();
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it('uses AstridBridgeDataProvider in Local mode with persistence disabled', async () => {
    window.localStorage.setItem('dev.videoEditor.localMode', '1');
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/api/astrid/health')) {
        return new Response(JSON.stringify({ ok: true, projects_root: '/tmp/test' }), { status: 200 });
      }
      if (url.endsWith('/api/astrid/projects')) {
        return new Response(JSON.stringify({
          projects: [{ slug: 'ados-talks', name: 'Ados Talks' }],
        }), { status: 200 });
      }
      if (url.endsWith('/api/astrid/projects/ados-talks/timelines')) {
        return new Response(JSON.stringify({
          timelines: [{
            timeline_id: '11111111-1111-1111-1111-111111111111',
            timeline_ulid: '01JM4K5N7P0000000000000017',
            slug: 'intro-cut',
            name: 'Intro Cut',
            is_default: true,
          }],
        }), { status: 200 });
      }
      throw new Error(`Unexpected bridge request: ${url}`);
    }));

    renderPage('/tools/video-editor?localProject=ados-talks&localTimeline=11111111-1111-1111-1111-111111111111');

    const provider = await screen.findByTestId('video-editor-provider');

    expect(provider).toHaveAttribute('data-kind', 'bridge');
    expect(state.bridgeCtor).toHaveBeenCalledWith({
      projectSlug: 'ados-talks',
      timelineRef: '11111111-1111-1111-1111-111111111111',
      timelineId: '11111111-1111-1111-1111-111111111111',
      persistenceDisabled: true,
    });
    expect(state.supabaseCtor).not.toHaveBeenCalled();
  });

  it('remounts the editor when the Local timeline selection changes', async () => {
    window.localStorage.setItem('dev.videoEditor.localMode', '1');
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/api/astrid/health')) {
        return new Response(JSON.stringify({ ok: true, projects_root: '/tmp/test' }), { status: 200 });
      }
      if (url.endsWith('/api/astrid/projects')) {
        return new Response(JSON.stringify({
          projects: [{ slug: 'ados-talks', name: 'Ados Talks' }],
        }), { status: 200 });
      }
      if (url.endsWith('/api/astrid/projects/ados-talks/timelines')) {
        return new Response(JSON.stringify({
          timelines: [
            {
              timeline_id: '11111111-1111-1111-1111-111111111111',
              timeline_ulid: '01JM4K5N7P0000000000000017',
              slug: 'intro-cut',
              name: 'Intro Cut',
              is_default: true,
            },
            {
              timeline_id: '22222222-2222-2222-2222-222222222222',
              timeline_ulid: '01JM4K5N7P0000000000000018',
              slug: 'alt-cut',
              name: 'Alt Cut',
              is_default: false,
            },
          ],
        }), { status: 200 });
      }
      throw new Error(`Unexpected bridge request: ${url}`);
    }));

    renderPage('/tools/video-editor?localProject=ados-talks&localTimeline=11111111-1111-1111-1111-111111111111');

    await screen.findByTestId('video-editor-provider');
    expect(state.providerMounts).toBe(1);
    expect(state.providerUnmounts).toBe(0);

    fireEvent.change(screen.getByLabelText('Local timeline'), {
      target: { value: '22222222-2222-2222-2222-222222222222' },
    });

    await waitFor(() => {
      expect(state.providerMounts).toBe(2);
      expect(state.providerUnmounts).toBe(1);
    });
  });

  it('shows unavailable state when bridge health check fails', async () => {
    window.localStorage.setItem('dev.videoEditor.localMode', '1');
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/api/astrid/health')) {
        return new Response(JSON.stringify({ error: 'unavailable' }), { status: 503 });
      }
      throw new Error(`Unexpected bridge request: ${url}`);
    }));

    renderPage('/tools/video-editor');

    await screen.findByText('Unable to reach the local bridge');
    expect(screen.queryByTestId('video-editor-provider')).toBeNull();
  });

  it('shows empty projects state when bridge has no projects', async () => {
    window.localStorage.setItem('dev.videoEditor.localMode', '1');
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/api/astrid/health')) {
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }
      if (url.endsWith('/api/astrid/projects')) {
        return new Response(JSON.stringify({ projects: [] }), { status: 200 });
      }
      throw new Error(`Unexpected bridge request: ${url}`);
    }));

    renderPage('/tools/video-editor');

    await screen.findByText('No local Astrid projects found');
    expect(screen.queryByTestId('video-editor-provider')).toBeNull();
  });

  it('shows empty timelines state when project exists but has no timelines', async () => {
    window.localStorage.setItem('dev.videoEditor.localMode', '1');
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/api/astrid/health')) {
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }
      if (url.endsWith('/api/astrid/projects')) {
        return new Response(JSON.stringify({
          projects: [{ slug: 'ados-talks', name: 'Ados Talks' }],
        }), { status: 200 });
      }
      if (url.endsWith('/api/astrid/projects/ados-talks/timelines')) {
        return new Response(JSON.stringify({ timelines: [] }), { status: 200 });
      }
      throw new Error(`Unexpected bridge request: ${url}`);
    }));

    renderPage('/tools/video-editor?localProject=ados-talks');

    await screen.findByText('No local timelines found');
    expect(screen.queryByTestId('video-editor-provider')).toBeNull();
  });

  it('shows read-only badge in Local mode', async () => {
    window.localStorage.setItem('dev.videoEditor.localMode', '1');
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/api/astrid/health')) {
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }
      if (url.endsWith('/api/astrid/projects')) {
        return new Response(JSON.stringify({
          projects: [{ slug: 'ados-talks', name: 'Ados Talks' }],
        }), { status: 200 });
      }
      if (url.endsWith('/api/astrid/projects/ados-talks/timelines')) {
        return new Response(JSON.stringify({
          timelines: [{
            timeline_id: '11111111-1111-1111-1111-111111111111',
            timeline_ulid: '01JM4K5N7P0000000000000017',
            slug: 'intro-cut',
            name: 'Intro Cut',
            is_default: true,
          }],
        }), { status: 200 });
      }
      throw new Error(`Unexpected bridge request: ${url}`);
    }));

    renderPage('/tools/video-editor?localProject=ados-talks&localTimeline=11111111-1111-1111-1111-111111111111');

    await screen.findByText('Read-only');
    await screen.findByTestId('video-editor-provider');
  });

  it('fetches health endpoint before loading projects in Local mode', async () => {
    window.localStorage.setItem('dev.videoEditor.localMode', '1');
    const fetchCalls: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      fetchCalls.push(url);
      if (url.endsWith('/api/astrid/health')) {
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }
      if (url.endsWith('/api/astrid/projects')) {
        return new Response(JSON.stringify({
          projects: [{ slug: 'ados-talks', name: 'Ados Talks' }],
        }), { status: 200 });
      }
      if (url.endsWith('/api/astrid/projects/ados-talks/timelines')) {
        return new Response(JSON.stringify({
          timelines: [{
            timeline_id: '11111111-1111-1111-1111-111111111111',
            timeline_ulid: '01JM4K5N7P0000000000000017',
            slug: 'intro-cut',
            name: 'Intro Cut',
            is_default: true,
          }],
        }), { status: 200 });
      }
      throw new Error(`Unexpected bridge request: ${url}`);
    }));

    renderPage('/tools/video-editor?localProject=ados-talks&localTimeline=11111111-1111-1111-1111-111111111111');

    await screen.findByTestId('video-editor-provider');

    // Health should be among the fetch calls
    const healthCalls = fetchCalls.filter(c => c.endsWith('/api/astrid/health'));
    expect(healthCalls.length).toBeGreaterThan(0);
  });
});
