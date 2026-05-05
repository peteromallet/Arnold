/**
 * Internal Reigh route adapter for the in-app video editor page.
 * Not part of the supported public SDK surface.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
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
import { SupabaseDataProvider } from '@/tools/video-editor/data/SupabaseDataProvider.ts';
import { VideoEditorProvider } from '@/tools/video-editor/contexts/VideoEditorProvider.tsx';
import { ReighVideoEditorShell } from '@/tools/video-editor/components/ReighVideoEditorShell.tsx';
import { useTimelinesList } from '@/tools/video-editor/hooks/useTimelinesList.ts';
import { videoEditorSettings } from '@/tools/video-editor/settings/videoEditorDefaults.ts';

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
  const { userId } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const creatingRef = useRef(false);
  const timelineId = searchParams.get('timeline');
  const provider = useMemo(() => {
    if (!selectedProjectId || !userId) {
      return null;
    }
    return new SupabaseDataProvider({ projectId: selectedProjectId, userId });
  }, [selectedProjectId, userId]);
  const timelines = useTimelinesList(selectedProjectId, userId);
  const { settings, update } = useToolSettings(videoEditorSettings.id, {
    projectId: selectedProjectId ?? undefined,
    enabled: Boolean(selectedProjectId),
  });
  const timelineName = timelines.data?.find((timeline: { id: string; name: string }) => timeline.id === timelineId)?.name ?? null;

  // Reconcile the URL timelineId against the live list:
  // - if it exists in the list, persist it as lastTimelineId
  // - if the list has loaded and it's not there, clear the URL + setting so
  //   the auto-select effect below picks a valid timeline
  useEffect(() => {
    if (!timelineId || !selectedProjectId || !timelines.data) {
      return;
    }

    if (timelines.data.some((timeline: { id: string }) => timeline.id === timelineId)) {
      void update('project', { lastTimelineId: timelineId });
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
  }, [selectedProjectId, setSearchParams, timelineId, timelines.data, update]);

  useEffect(() => {
    if (timelineId || !selectedProjectId || !userId) {
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
    settings?.lastTimelineId,
    selectedProjectId,
    setSearchParams,
    timelineId,
    timelines.createTimeline,
    timelines.data,
    timelines.error,
    timelines.isLoading,
    update,
    userId,
  ]);

  if (!selectedProjectId) {
    return (
      <TimelineList
        onSelect={(nextTimelineId) => {
          setSearchParams({ timeline: nextTimelineId });
        }}
      />
    );
  }

  if (!userId || !provider || !timelineId) {
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
    <div className={cn('h-full w-full overflow-hidden bg-background')}>
      <VideoEditorProvider
        dataProvider={provider}
        projectId={selectedProjectId}
        timelineId={timelineId}
        timelineName={timelineName}
        userId={userId}
      >
        <ReighVideoEditorShell
          mode="full"
          timelineId={timelineId}
          onCreateTimeline={() => navigate('/')}
        />
      </VideoEditorProvider>
    </div>
  );
}
