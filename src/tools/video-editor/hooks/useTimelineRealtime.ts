import { useCallback, useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { realtimeEventProcessor } from '@/shared/realtime/RealtimeEventProcessor.ts';
import { assetRegistryQueryKey, timelineQueryKey } from '@/tools/video-editor/hooks/useTimeline.ts';
import { timelineListQueryKey } from '@/tools/video-editor/hooks/useTimelinesList.ts';

interface UseTimelineRealtimeOptions {
  timelineId: string;
  conflictExhausted: boolean;
  onKeepLocalChanges: () => Promise<void>;
  onDiscardRemoteChanges: () => Promise<void>;
}

export function useTimelineRealtime({
  timelineId,
  conflictExhausted,
  onKeepLocalChanges,
  onDiscardRemoteChanges,
}: UseTimelineRealtimeOptions) {
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (conflictExhausted) {
      setIsOpen(true);
    }
  }, [conflictExhausted]);

  useEffect(() => {
    return realtimeEventProcessor.onEvent((event) => {
      if (event.type !== 'timelines-updated') {
        return;
      }

      const matching = event.timelines.find((timeline) => timeline.id === timelineId);
      if (!matching) {
        return;
      }

      void queryClient.invalidateQueries({ queryKey: timelineQueryKey(timelineId) });
      void queryClient.invalidateQueries({ queryKey: assetRegistryQueryKey(timelineId) });
      void queryClient.invalidateQueries({ queryKey: timelineListQueryKey(matching.projectId) });
    });
  }, [queryClient, timelineId]);

  const keepLocalChanges = useCallback(async () => {
    setIsOpen(false);
    if (conflictExhausted) {
      await onKeepLocalChanges();
    }
  }, [conflictExhausted, onKeepLocalChanges]);

  const discardAndReload = useCallback(async () => {
    setIsOpen(false);
    await onDiscardRemoteChanges();
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: timelineQueryKey(timelineId) }),
      queryClient.invalidateQueries({ queryKey: assetRegistryQueryKey(timelineId) }),
    ]);
  }, [onDiscardRemoteChanges, queryClient, timelineId]);

  return {
    isOpen,
    setOpen: setIsOpen,
    keepLocalChanges,
    discardAndReload,
  };
}
