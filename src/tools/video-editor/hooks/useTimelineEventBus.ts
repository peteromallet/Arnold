import type { CommitHistoryOptions, ScheduleSaveFn } from '@/tools/video-editor/hooks/useTimelineCommit.ts';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';

type TimelineEventMap = {
  beforeCommit: (currentData: TimelineData, options: CommitHistoryOptions) => void;
  pruneSelection: (validIds: Set<string>) => void;
  scheduleSave: ScheduleSaveFn;
  saveSuccess: () => void;
};

type TimelineEventName = keyof TimelineEventMap;

export class TimelineEventBus {
  private listeners = new Map<TimelineEventName, Set<(...args: unknown[]) => void>>();

  on<K extends TimelineEventName>(eventName: K, listener: TimelineEventMap[K]) {
    const listeners = this.listeners.get(eventName) ?? new Set();
    listeners.add(listener as (...args: unknown[]) => void);
    this.listeners.set(eventName, listeners);

    return () => {
      this.off(eventName, listener);
    };
  }

  off<K extends TimelineEventName>(eventName: K, listener: TimelineEventMap[K]) {
    const listeners = this.listeners.get(eventName);
    if (!listeners) {
      return;
    }

    listeners.delete(listener as (...args: unknown[]) => void);
    if (listeners.size === 0) {
      this.listeners.delete(eventName);
    }
  }

  emit<K extends TimelineEventName>(eventName: K, ...args: Parameters<TimelineEventMap[K]>) {
    const listeners = this.listeners.get(eventName);
    if (!listeners) {
      return;
    }

    for (const listener of [...listeners]) {
      listener(...args);
    }
  }
}
