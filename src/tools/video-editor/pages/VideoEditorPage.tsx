/**
 * Internal Reigh route adapter for the in-app video editor page.
 * Not part of the supported public SDK surface.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Clapperboard, Pencil, Plus, Trash2 } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '@/shared/components/ui/button.tsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card.tsx';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import { Input } from '@/shared/components/ui/input.tsx';
import { Skeleton } from '@/shared/components/ui/skeleton.tsx';
import { useAuth } from '@/shared/contexts/AuthContext.tsx';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext.tsx';
import { useToolSettings } from '@/shared/hooks/settings/useToolSettings.ts';
import { toast } from '@/shared/components/ui/toast.tsx';
import { AstridBridgeDataProvider } from '@/tools/video-editor/data/AstridBridgeDataProvider.ts';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider.ts';
import { SupabaseDataProvider } from '@/tools/video-editor/data/SupabaseDataProvider.ts';
import { VideoEditorProvider } from '@/tools/video-editor/contexts/VideoEditorProvider.tsx';
import { getExtensionSmokeExtension } from '@/sdk/smoke/extensionSmoke';
import { useExtensionLoaderWiring } from '@/tools/video-editor/runtime/useExtensionLoaderWiring';
import { ReighVideoEditorShell } from '@/tools/video-editor/components/ReighVideoEditorShell.tsx';
import { useTimelinesList } from '@/tools/video-editor/hooks/useTimelinesList.ts';
import type { SaveStatus } from '@/tools/video-editor/hooks/useTimelinePersistence.ts';
import { videoEditorSettings } from '@/tools/video-editor/settings/videoEditorDefaults.ts';

type VideoEditorMode = 'app' | 'local';

type BridgeProject = {
  slug: string;
  name: string;
};

type BridgeTimeline = {
  timeline_id: string;
  timeline_ulid: string;
  slug: string;
  name: string;
  is_default: boolean;
};

type BridgeProjectsPayload = {
  projects?: BridgeProject[];
};

type BridgeTimelinesPayload = {
  timelines?: BridgeTimeline[];
};

type ProviderSelection = {
  dataProvider: DataProvider;
  projectId: string | null;
  timelineId: string;
  timelineName: string | null;
  userId: string;
  remountKey: string;
};

type AppRouteState = {
  timelineId: string | null;
};

type LocalRouteState = {
  projectSlug: string | null;
  timelineId: string | null;
};

const LOCAL_MODE_STORAGE_KEY = 'dev.videoEditor.localMode';
const LOCAL_BRIDGE_BASE_URL = '/api/astrid';

function readStoredLocalMode(): boolean {
  try {
    return window.localStorage.getItem(LOCAL_MODE_STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

function writeStoredLocalMode(enabled: boolean): void {
  try {
    window.localStorage.setItem(LOCAL_MODE_STORAGE_KEY, enabled ? '1' : '0');
  } catch {
    // Ignore storage failures in restricted contexts.
  }
}

function useVideoEditorModePreference() {
  const localModeAvailable = import.meta.env.DEV;
  const [mode, setMode] = useState<VideoEditorMode>(() => (
    localModeAvailable && readStoredLocalMode() ? 'local' : 'app'
  ));

  useEffect(() => {
    if (!localModeAvailable && mode !== 'app') {
      setMode('app');
      return;
    }
    if (localModeAvailable) {
      writeStoredLocalMode(mode === 'local');
    }
  }, [localModeAvailable, mode]);

  return {
    localModeAvailable,
    mode: localModeAvailable ? mode : 'app',
    setMode,
  };
}

async function fetchBridgeJson<T>(path: string): Promise<T> {
  const response = await fetch(`${LOCAL_BRIDGE_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Astrid bridge request failed: ${response.status} ${response.statusText}`);
  }
  return await response.json() as T;
}

function useBridgeProjects(enabled: boolean) {
  return useQuery({
    queryKey: ['astrid-bridge', 'projects'],
    enabled,
    queryFn: async () => {
      const payload = await fetchBridgeJson<BridgeProjectsPayload>('/projects');
      return Array.isArray(payload.projects) ? payload.projects : [];
    },
  });
}

function useBridgeTimelines(projectSlug: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ['astrid-bridge', 'projects', projectSlug, 'timelines'],
    enabled: enabled && Boolean(projectSlug),
    queryFn: async () => {
      const payload = await fetchBridgeJson<BridgeTimelinesPayload>(
        `/projects/${encodeURIComponent(projectSlug!)}/timelines`,
      );
      return Array.isArray(payload.timelines) ? payload.timelines : [];
    },
  });
}

function useBridgeHealth(enabled: boolean) {
  return useQuery({
    queryKey: ['astrid-bridge', 'health'],
    enabled,
    queryFn: async () => {
      const payload = await fetchBridgeJson<{ ok: boolean }>('/health');
      return payload.ok === true;
    },
    retry: 0,
  });
}

function useVideoEditorProviderSelection({
  mode,
  selectedProjectId,
  userId,
  appTimelineId,
  appTimelineName,
  localProjectSlug,
  localTimelineId,
  localTimelineName,
}: {
  mode: VideoEditorMode;
  selectedProjectId: string | null;
  userId: string | null;
  appTimelineId: string | null;
  appTimelineName: string | null;
  localProjectSlug: string | null;
  localTimelineId: string | null;
  localTimelineName: string | null;
}): ProviderSelection | null {
  return useMemo(() => {
    if (mode === 'local') {
      if (!localProjectSlug || !localTimelineId) {
        return null;
      }

      return {
        dataProvider: new AstridBridgeDataProvider({
          projectSlug: localProjectSlug,
          timelineRef: localTimelineId,
          timelineId: localTimelineId,
        }),
        projectId: localProjectSlug,
        timelineId: localTimelineId,
        timelineName: localTimelineName,
        userId: userId ?? 'local-bridge',
        remountKey: `local:${localProjectSlug}:${localTimelineId}`,
      };
    }

    if (!selectedProjectId || !userId || !appTimelineId) {
      return null;
    }

    return {
      dataProvider: new SupabaseDataProvider({ projectId: selectedProjectId, userId }),
      projectId: selectedProjectId,
      timelineId: appTimelineId,
      timelineName: appTimelineName,
      userId,
      remountKey: `app:${selectedProjectId}:${appTimelineId}`,
    };
  }, [
    appTimelineId,
    appTimelineName,
    localProjectSlug,
    localTimelineId,
    localTimelineName,
    mode,
    selectedProjectId,
    userId,
  ]);
}

function DevModeToggle({
  localModeAvailable,
  mode,
  setMode,
  disabled,
}: {
  localModeAvailable: boolean;
  mode: VideoEditorMode;
  setMode: (nextMode: VideoEditorMode) => void;
  disabled?: boolean;
}) {
  if (!localModeAvailable) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 rounded-lg border border-border bg-card/80 p-2">
      <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
        Mode
      </span>
      <Button
        type="button"
        size="sm"
        variant={mode === 'app' ? 'default' : 'outline'}
        onClick={() => setMode('app')}
        disabled={disabled}
      >
        App
      </Button>
      <Button
        type="button"
        size="sm"
        variant={mode === 'local' ? 'default' : 'outline'}
        onClick={() => setMode('local')}
        disabled={disabled}
      >
        Local
      </Button>
    </div>
  );
}

function TimelineList({ onSelect }: { onSelect: (timelineId: string) => void }) {
  const { selectedProjectId } = useProjectSelectionContext();
  const { userId } = useAuth();
  const { settings, update } = useToolSettings(videoEditorSettings.id, {
    projectId: selectedProjectId ?? undefined,
    enabled: Boolean(selectedProjectId),
  });
  const timelines = useTimelinesList(selectedProjectId, userId);
  const [newName, setNewName] = useState('Main timeline');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState('');
  const [autoCreating, setAutoCreating] = useState(false);

  // Auto-create a default timeline if the project has none
  useEffect(() => {
    if (
      !timelines.isLoading &&
      timelines.data &&
      timelines.data.length === 0 &&
      selectedProjectId &&
      userId &&
      !autoCreating &&
      !timelines.createTimeline.isPending
    ) {
      setAutoCreating(true);
      timelines.createTimeline
        .mutateAsync('Main timeline')
        .then(async (created) => {
          await update('project', { lastTimelineId: created.id });
          onSelect(created.id);
        })
        .catch(() => {
          setAutoCreating(false);
        });
    }
  }, [timelines.isLoading, timelines.data, selectedProjectId, userId, autoCreating, timelines.createTimeline, update, onSelect]);

  if (!selectedProjectId) {
    return (
      <Card className="mx-auto max-w-2xl">
        <CardHeader>
          <CardTitle>No project selected</CardTitle>
          <CardDescription>Select a project in the header to manage timelines.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-4 p-6">
      <Card>
        <CardHeader>
          <CardTitle>Video editor timelines</CardTitle>
          <CardDescription>Pick a timeline or create a new one for this project.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="Timeline name" />
            <Button
              type="button"
              onClick={async () => {
                const created = await timelines.createTimeline.mutateAsync(newName || 'Untitled timeline');
                await update('project', { lastTimelineId: created.id });
                onSelect(created.id);
              }}
              disabled={timelines.createTimeline.isPending}
            >
              <Plus className="mr-1 h-4 w-4" />
              Create timeline
            </Button>
          </div>

          <div className="grid gap-3">
            {timelines.isLoading && Array.from({ length: 3 }).map((_, index) => <Skeleton key={index} className="h-20 w-full" />)}
            {(timelines.data ?? []).map((timeline: { id: string; name: string; updated_at: string }) => {
              const isEditing = editingId === timeline.id;
              const isActive = settings?.lastTimelineId === timeline.id;

              return (
                <div key={timeline.id} className="flex items-center gap-3 rounded-xl border border-border bg-card/70 p-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                    <Clapperboard className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    {isEditing ? (
                      <Input value={editingName} onChange={(event) => setEditingName(event.target.value)} />
                    ) : (
                      <div className="truncate text-sm font-medium text-foreground">{timeline.name}</div>
                    )}
                    <div className="mt-1 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Updated {new Date(timeline.updated_at).toLocaleString()}
                      {isActive ? ' · Last opened' : ''}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {isEditing ? (
                      <Button
                        type="button"
                        size="sm"
                        onClick={async () => {
                          await timelines.renameTimeline.mutateAsync({ timelineId: timeline.id, name: editingName || timeline.name });
                          setEditingId(null);
                        }}
                      >
                        Save
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setEditingId(timeline.id);
                          setEditingName(timeline.name);
                        }}
                      >
                        <Pencil className="mr-1 h-3.5 w-3.5" />
                        Rename
                      </Button>
                    )}
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={async () => {
                        await update('project', { lastTimelineId: timeline.id });
                        onSelect(timeline.id);
                      }}
                    >
                      Open
                    </Button>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="text-destructive hover:text-destructive"
                      onClick={async () => {
                        await timelines.deleteTimeline.mutateAsync(timeline.id);
                        if (settings?.lastTimelineId === timeline.id) {
                          await update('project', { lastTimelineId: undefined });
                        }
                        toast.success('Timeline deleted');
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              );
            })}
            {!timelines.isLoading && (timelines.data?.length ?? 0) === 0 && (
              <div className="rounded-xl border border-dashed border-border p-10 text-center">
                <div className="text-sm font-medium text-foreground">No timelines yet</div>
                <div className="mt-1 text-xs text-muted-foreground">Create the first timeline to open the standalone editor.</div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function VideoEditorPage() {
  const { selectedProjectId } = useProjectSelectionContext();
  const [searchParams, setSearchParams] = useSearchParams();

  // ---- Smoke extension wiring (prepend when ?extensionSmoke=1) -------------
  const smokeDirectExtensions = useMemo(() => {
    const smokeExt = getExtensionSmokeExtension(searchParams);
    return smokeExt ? [smokeExt] : undefined;
  }, [searchParams]);

  // ---- M14: extension loader wiring (host-owned) --------------------------
  // Resolves direct-local extensions + optional repository state through the
  // ExtensionLoader pipeline.  When no repository is provided, direct-local
  // extensions pass through unchanged (backward compatible).
  const {
    resolvedExtensions,
    diagnostics: loaderDiagnostics,
    isResolving: loaderIsResolving,
  } = useExtensionLoaderWiring({
    directExtensions: smokeDirectExtensions,
    repository: null,
    bundleStore: null,
  });
  const { userId } = useAuth();
  const navigate = useNavigate();
  const { localModeAvailable, mode, setMode } = useVideoEditorModePreference();
  const [mountedSaveStatus, setMountedSaveStatus] = useState<SaveStatus>('saved');
  const creatingRef = useRef(false);
  const appTimelineId = searchParams.get('timeline');
  const localProjectSlug = searchParams.get('localProject');
  const localTimelineId = searchParams.get('localTimeline');
  const appRouteRef = useRef<AppRouteState>({ timelineId: appTimelineId });
  const localRouteRef = useRef<LocalRouteState>({
    projectSlug: localProjectSlug,
    timelineId: localTimelineId,
  });
  const timelines = useTimelinesList(selectedProjectId, userId);
  const bridgeHealth = useBridgeHealth(mode === 'local');
  const bridgeProjects = useBridgeProjects(mode === 'local');
  const bridgeTimelines = useBridgeTimelines(localProjectSlug, mode === 'local');
  const { settings, update } = useToolSettings(videoEditorSettings.id, {
    projectId: selectedProjectId ?? undefined,
    enabled: Boolean(selectedProjectId),
  });
  const appTimelineName = timelines.data?.find(
    (timeline: { id: string; name: string }) => timeline.id === appTimelineId,
  )?.name ?? null;
  const localTimelineName = bridgeTimelines.data?.find(
    (timeline) => timeline.timeline_id === localTimelineId,
  )?.name ?? null;
  const providerSelection = useVideoEditorProviderSelection({
    mode,
    selectedProjectId,
    userId,
    appTimelineId,
    appTimelineName,
    localProjectSlug,
    localTimelineId,
    localTimelineName,
  });

  useEffect(() => {
    if (appTimelineId !== null || mode === 'app') {
      appRouteRef.current = { timelineId: appTimelineId };
    }
  }, [appTimelineId, mode]);

  useEffect(() => {
    if (localProjectSlug !== null || localTimelineId !== null || mode === 'local') {
      localRouteRef.current = {
        projectSlug: localProjectSlug,
        timelineId: localTimelineId,
      };
    }
  }, [localProjectSlug, localTimelineId, mode]);

  useEffect(() => {
    setMountedSaveStatus('saved');
  }, [providerSelection?.remountKey]);

  const isSwitchBlockedBySave = mountedSaveStatus === 'saving';
  const confirmEditorRemount = useCallback(() => {
    if (!providerSelection) {
      return true;
    }
    if (mountedSaveStatus === 'saving') {
      return false;
    }
    if (mountedSaveStatus === 'dirty') {
      return window.confirm('You have unsaved timeline changes. Switch editors and discard them?');
    }
    if (mountedSaveStatus === 'error') {
      return window.confirm('The last timeline save failed. Switch editors anyway?');
    }
    return true;
  }, [mountedSaveStatus, providerSelection]);

  const setModeRoute = useCallback((nextMode: VideoEditorMode) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete('timeline');
      next.delete('localProject');
      next.delete('localTimeline');
      if (nextMode === 'app') {
        if (appRouteRef.current.timelineId) {
          next.set('timeline', appRouteRef.current.timelineId);
        }
      } else {
        if (localRouteRef.current.projectSlug) {
          next.set('localProject', localRouteRef.current.projectSlug);
        }
        if (localRouteRef.current.timelineId) {
          next.set('localTimeline', localRouteRef.current.timelineId);
        }
      }
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  const handleModeChange = useCallback((nextMode: VideoEditorMode) => {
    if (nextMode === mode) {
      return;
    }
    if (!confirmEditorRemount()) {
      return;
    }
    setMode(nextMode);
    setModeRoute(nextMode);
  }, [confirmEditorRemount, mode, setMode, setModeRoute]);

  const handleLocalProjectChange = useCallback((nextProjectSlug: string) => {
    if (nextProjectSlug === localProjectSlug) {
      return;
    }
    if (!confirmEditorRemount()) {
      return;
    }
    localRouteRef.current = {
      projectSlug: nextProjectSlug,
      timelineId: null,
    };
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete('timeline');
      next.set('localProject', nextProjectSlug);
      next.delete('localTimeline');
      return next;
    });
  }, [confirmEditorRemount, localProjectSlug, setSearchParams]);

  const handleLocalTimelineChange = useCallback((nextTimelineId: string) => {
    if (nextTimelineId === localTimelineId) {
      return;
    }
    if (!confirmEditorRemount()) {
      return;
    }
    localRouteRef.current = {
      projectSlug: localProjectSlug,
      timelineId: nextTimelineId,
    };
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete('timeline');
      next.set('localTimeline', nextTimelineId);
      return next;
    });
  }, [confirmEditorRemount, localProjectSlug, localTimelineId, setSearchParams]);

  // Reconcile the URL timelineId against the live list:
  // - if it exists in the list, persist it as lastTimelineId
  // - if the list has loaded and it's not there, clear the URL + setting so
  //   the auto-select effect below picks a valid timeline
  useEffect(() => {
    if (mode !== 'app' || !appTimelineId || !selectedProjectId || !timelines.data) {
      return;
    }

    if (timelines.data.some((timeline: { id: string }) => timeline.id === appTimelineId)) {
      void update('project', { lastTimelineId: appTimelineId });
      return;
    }

    // Invalid id — just clear the URL. We can't clear settings.lastTimelineId
    // here because deepMerge drops `undefined` patches; the restore effect
    // below is responsible for validating the persisted id against the list.
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete('timeline');
      return next;
    }, { replace: true });
  }, [appTimelineId, mode, selectedProjectId, setSearchParams, timelines.data, update]);

  useEffect(() => {
    if (mode !== 'app' || appTimelineId || !selectedProjectId || !userId) {
      return;
    }

    // Wait for the list before restoring or auto-picking — otherwise we'd
    // restore a stale lastTimelineId that no longer exists (which the strip
    // effect above would immediately delete, causing an infinite URL loop)
    // or create a duplicate "Main timeline".
    if (timelines.isLoading || timelines.error || !timelines.data) {
      return;
    }

    const persistedId = settings?.lastTimelineId;
    const persistedIsValid = persistedId
      && timelines.data.some((timeline: { id: string }) => timeline.id === persistedId);

    if (persistedIsValid) {
      setSearchParams((current) => {
        const next = new URLSearchParams(current);
        next.set('timeline', persistedId);
        return next;
      }, { replace: true });
      return;
    }

    const nextTimelineId = timelines.data[0]?.id;
    if (nextTimelineId) {
      void update('project', { lastTimelineId: nextTimelineId });
      setSearchParams((current) => {
        const next = new URLSearchParams(current);
        next.set('timeline', nextTimelineId);
        return next;
      }, { replace: true });
      return;
    }

    if (creatingRef.current || timelines.createTimeline.isPending) {
      return;
    }

    creatingRef.current = true;
    void timelines.createTimeline
      .mutateAsync('Main timeline')
      .then(async (created) => {
        await update('project', { lastTimelineId: created.id });
        setSearchParams((current) => {
          const next = new URLSearchParams(current);
          next.set('timeline', created.id);
          return next;
        }, { replace: true });
      })
      .catch((error) => {
        creatingRef.current = false;
        console.error('[video-editor] Failed to auto-create timeline', error);
        toast.error('Failed to create the default timeline');
      });
  }, [
    appTimelineId,
    mode,
    settings?.lastTimelineId,
    selectedProjectId,
    setSearchParams,
    timelines.createTimeline,
    timelines.data,
    timelines.error,
    timelines.isLoading,
    update,
    userId,
  ]);

  useEffect(() => {
    if (mode !== 'local' || bridgeProjects.isLoading || !bridgeProjects.data) {
      return;
    }

    const hasSelectedProject = localProjectSlug
      && bridgeProjects.data.some((project) => project.slug === localProjectSlug);
    const nextProjectSlug = hasSelectedProject
      ? localProjectSlug
      : bridgeProjects.data[0]?.slug ?? null;

    if (!nextProjectSlug || nextProjectSlug === localProjectSlug) {
      return;
    }

    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set('localProject', nextProjectSlug);
      next.delete('localTimeline');
      return next;
    }, { replace: true });
  }, [bridgeProjects.data, bridgeProjects.isLoading, localProjectSlug, mode, setSearchParams]);

  useEffect(() => {
    if (mode !== 'local' || !localProjectSlug || bridgeTimelines.isLoading || !bridgeTimelines.data) {
      return;
    }

    const hasSelectedTimeline = localTimelineId
      && bridgeTimelines.data.some((timeline) => timeline.timeline_id === localTimelineId);
    const nextTimelineId = hasSelectedTimeline
      ? localTimelineId
      : bridgeTimelines.data[0]?.timeline_id ?? null;

    if (!nextTimelineId || nextTimelineId === localTimelineId) {
      return;
    }

    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set('localTimeline', nextTimelineId);
      return next;
    }, { replace: true });
  }, [bridgeTimelines.data, bridgeTimelines.isLoading, localProjectSlug, localTimelineId, mode, setSearchParams]);

  if (mode === 'local') {
    const hasProjects = (bridgeProjects.data?.length ?? 0) > 0;
    const hasTimelines = (bridgeTimelines.data?.length ?? 0) > 0;

    return (
      <div className="flex h-full w-full flex-col overflow-hidden bg-background">
        <div className="border-b border-border px-4 py-3">
          <div className="flex flex-wrap items-center gap-3">
            <DevModeToggle
              localModeAvailable={localModeAvailable}
              mode={mode}
              setMode={handleModeChange}
              disabled={isSwitchBlockedBySave}
            />
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="video-editor-local-project">
                Project
              </label>
              <select
                id="video-editor-local-project"
                aria-label="Project"
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                value={localProjectSlug ?? ''}
                onChange={(event) => handleLocalProjectChange(event.target.value)}
                disabled={!hasProjects || isSwitchBlockedBySave}
              >
                {bridgeProjects.data?.map((project) => (
                  <option key={project.slug} value={project.slug}>
                    {project.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="video-editor-local-timeline">
                Timeline
              </label>
              <select
                id="video-editor-local-timeline"
                aria-label="Timeline"
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                value={localTimelineId ?? ''}
                onChange={(event) => handleLocalTimelineChange(event.target.value)}
                disabled={!hasTimelines || isSwitchBlockedBySave}
              >
                {bridgeTimelines.data?.map((timeline) => (
                  <option key={timeline.timeline_id} value={timeline.timeline_id}>
                    {timeline.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {bridgeHealth.isLoading ? (
          <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-4 p-6">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : bridgeHealth.error ? (
          <div className="flex flex-1 items-center justify-center px-6">
            <Card className="w-full max-w-md">
              <CardHeader>
                <CardTitle>Unable to reach the local bridge</CardTitle>
                <CardDescription>{bridgeHealth.error.message}</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Make sure Astrid is running locally:
                </p>
                <code className="mt-2 block rounded bg-muted px-2 py-1 text-xs">
                  cd ../Astrid && astrid serve --port 17333
                </code>
              </CardContent>
            </Card>
          </div>
        ) : bridgeProjects.error ? (
          <div className="flex flex-1 items-center justify-center px-6">
            <Card className="w-full max-w-md">
              <CardHeader>
                <CardTitle>Unable to reach the local bridge</CardTitle>
                <CardDescription>{bridgeProjects.error.message}</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Make sure Astrid is running locally:
                </p>
                <code className="mt-2 block rounded bg-muted px-2 py-1 text-xs">
                  cd ../Astrid && astrid serve --port 17333
                </code>
              </CardContent>
            </Card>
          </div>
        ) : bridgeTimelines.error ? (
          <div className="flex flex-1 items-center justify-center px-6">
            <Card className="w-full max-w-md">
              <CardHeader>
                <CardTitle>Unable to load local timelines</CardTitle>
                <CardDescription>{bridgeTimelines.error.message}</CardDescription>
              </CardHeader>
            </Card>
          </div>
        ) : bridgeProjects.isLoading || (localProjectSlug !== null && bridgeTimelines.isLoading) ? (
          <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-4 p-6">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : !hasProjects ? (
          <div className="flex flex-1 items-center justify-center px-6">
            <Card className="w-full max-w-md">
              <CardHeader>
                <CardTitle>No local Astrid projects found</CardTitle>
                <CardDescription>Start `astrid serve` with a projects root that contains `project.json` files.</CardDescription>
              </CardHeader>
            </Card>
          </div>
        ) : !hasTimelines || !providerSelection ? (
          <div className="flex flex-1 items-center justify-center px-6">
            <Card className="w-full max-w-md">
              <CardHeader>
                <CardTitle>No local timelines found</CardTitle>
                <CardDescription>Select a different project or add a timeline under the current Astrid projects root.</CardDescription>
              </CardHeader>
            </Card>
          </div>
        ) : (
          <div className={cn('min-h-0 flex-1 overflow-hidden bg-background')}>
            <VideoEditorProvider
              key={providerSelection.remountKey}
              dataProvider={providerSelection.dataProvider}
              projectId={providerSelection.projectId}
              timelineId={providerSelection.timelineId}
              timelineName={providerSelection.timelineName}
              userId={providerSelection.userId}
              onSaveStatusChange={setMountedSaveStatus}
              extensions={resolvedExtensions}
            >
              <ReighVideoEditorShell
                mode="full"
                timelineId={providerSelection.timelineId}
                onCreateTimeline={() => navigate('/')}
              />
            </VideoEditorProvider>
          </div>
        )}
      </div>
    );
  }

  if (!selectedProjectId) {
    return (
      <div className="flex h-full w-full flex-col bg-background">
        <div className="border-b border-border px-4 py-3">
          <DevModeToggle
            localModeAvailable={localModeAvailable}
            mode={mode}
            setMode={handleModeChange}
            disabled={isSwitchBlockedBySave}
          />
        </div>
        <TimelineList
          onSelect={(nextTimelineId) => {
            setSearchParams({ timeline: nextTimelineId });
          }}
        />
      </div>
    );
  }

  if (!userId || !providerSelection || !appTimelineId) {
    if (timelines.error) {
      return (
        <div className="flex h-screen items-center justify-center bg-background px-6">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>Unable to open video editor</CardTitle>
              <CardDescription>{timelines.error.message}</CardDescription>
            </CardHeader>
          </Card>
        </div>
      );
    }

    return null;
  }

  return (
    <div className={cn('flex h-full w-full flex-col overflow-hidden bg-background')}>
      <div className="border-b border-border px-4 py-3">
        <DevModeToggle localModeAvailable={localModeAvailable} mode={mode} setMode={setMode} />
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
        <VideoEditorProvider
          key={providerSelection.remountKey}
          dataProvider={providerSelection.dataProvider}
          projectId={providerSelection.projectId}
          timelineId={providerSelection.timelineId}
          timelineName={providerSelection.timelineName}
          userId={providerSelection.userId}
          onSaveStatusChange={setMountedSaveStatus}
          extensions={resolvedExtensions}
        >
          <ReighVideoEditorShell
            mode="full"
            timelineId={providerSelection.timelineId}
            onCreateTimeline={() => navigate('/')}
          />
        </VideoEditorProvider>
      </div>
    </div>
  );
}
