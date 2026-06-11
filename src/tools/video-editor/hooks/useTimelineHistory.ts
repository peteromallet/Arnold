import { useCallback, useEffect, useRef, useState, type MutableRefObject } from 'react';
import {
  createTimelineCommandRunner,
  MEDIA_COMMAND_DESCRIPTORS,
  type TimelineCommandHistoryMetadata,
} from '@/tools/video-editor/commands/index.ts';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import { isDataProviderPersistenceEnabled } from '@/tools/video-editor/data/DataProvider.ts';
import type {
  CommandHistoryCommitMetadata,
  CommitDataOptions,
  CommitHistoryOptions,
} from '@/tools/video-editor/hooks/useTimelineCommit.ts';
import {
  isInteractionActive,
  type InteractionStateRef,
} from '@/tools/video-editor/lib/interaction-state.ts';
import {
  buildDataFromCurrentRegistry,
  buildDataFromSnapshot,
} from '@/tools/video-editor/lib/timeline-save-utils.ts';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import type { TimelineConfig } from '@/tools/video-editor/types/index.ts';
import type {
  Checkpoint,
  CheckpointTriggerType,
  UndoEntry,
  UndoSnapshot,
} from '@/tools/video-editor/types/history.ts';

const UNDO_STACK_LIMIT = 100;
const CHECKPOINT_LIMIT = 30;
const CHECKPOINT_RETENTION_MS = 24 * 60 * 60 * 1000;
const SESSION_IDLE_MS = 5 * 60 * 1000;
const EDIT_DISTANCE_CHECKPOINT_THRESHOLD = 30;
const UNTRANSACTED_COLLAPSE_WINDOW_MS = 300;
const historyCommandRunner = createTimelineCommandRunner([...MEDIA_COMMAND_DESCRIPTORS]);

export interface UseTimelineHistoryArgs {
  dataRef: MutableRefObject<TimelineData | null>;
  commitData: (nextData: TimelineData, options?: CommitDataOptions) => void;
  interactionStateRef: InteractionStateRef;
}

export interface UseTimelineHistoryResult {
  canUndo: boolean;
  canRedo: boolean;
  checkpoints: Checkpoint[];
  onBeforeCommit: (currentData: TimelineData, options: CommitHistoryOptions) => void;
  undo: () => void;
  redo: () => void;
  jumpToCheckpoint: (checkpointId: string) => void;
  createManualCheckpoint: (label?: string) => Promise<void>;
  createCheckpoint: (label?: string) => Promise<void>;
}

function cloneConfig(config: TimelineConfig): TimelineConfig {
  return structuredClone(config);
}

function buildSnapshot(currentData: TimelineData): UndoSnapshot {
  return {
    config: cloneConfig(currentData.config),
    registry: structuredClone(currentData.registry),
    signature: currentData.signature,
  };
}

function isCheckpointFresh(checkpoint: Checkpoint, now: number): boolean {
  return now - new Date(checkpoint.createdAt).getTime() <= CHECKPOINT_RETENTION_MS;
}

function trimCheckpoints(checkpoints: Checkpoint[], now = Date.now()): Checkpoint[] {
  const manual = checkpoints.filter((c) => c.triggerType === 'manual');
  const auto = checkpoints
    .filter((c) => c.triggerType !== 'manual' && isCheckpointFresh(c, now))
    .slice(0, CHECKPOINT_LIMIT);
  return [...manual, ...auto].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  );
}

function defaultCheckpointLabel(triggerType: CheckpointTriggerType): string {
  switch (triggerType) {
    case 'session_boundary':
      return 'Session checkpoint';
    case 'edit_distance':
      return 'Auto checkpoint';
    case 'semantic':
      return 'Before destructive edit';
    case 'manual':
      return 'Manual checkpoint';
  }
}

const buildCommandHistoryEntry = (
  commandHistory: CommandHistoryCommitMetadata | undefined,
) => {
  if (
    !commandHistory
    || commandHistory.history.strategy !== 'inverse_transaction'
    || commandHistory.history.inverseTransaction === null
    || commandHistory.history.inverseTransaction.commands.length === 0
    || commandHistory.transaction.commands.length === 0
  ) {
    return undefined;
  }

  return {
    history: {
      ...commandHistory.history,
      inverseTransaction: structuredClone(commandHistory.history.inverseTransaction),
    },
    undoTransaction: structuredClone(commandHistory.history.inverseTransaction),
    redoTransaction: structuredClone(commandHistory.transaction),
  };
};

const mergeCommandHistoryMetadata = (
  previous: TimelineCommandHistoryMetadata,
  next: TimelineCommandHistoryMetadata,
  undoTransaction: NonNullable<UndoEntry['command']>['undoTransaction'],
): TimelineCommandHistoryMetadata => ({
  ...next,
  commandTypes: [...previous.commandTypes, ...next.commandTypes],
  commandIds: [...previous.commandIds, ...next.commandIds],
  inverseTransaction: structuredClone(undoTransaction),
  appliedCount: previous.appliedCount + next.appliedCount,
  failedCount: previous.failedCount + next.failedCount,
  partial: previous.partial || next.partial,
});

const mergeCollapsedEntry = (
  previous: UndoEntry,
  next: UndoEntry,
): UndoEntry => {
  if (!previous.command || !next.command) {
    return previous.command
      ? { ...previous, command: undefined }
      : previous;
  }

  const undoTransaction = {
    ...(next.command.undoTransaction.transactionId
      ? { transactionId: next.command.undoTransaction.transactionId }
      : previous.command.undoTransaction.transactionId
        ? { transactionId: previous.command.undoTransaction.transactionId }
        : {}),
    commands: [
      ...next.command.undoTransaction.commands,
      ...previous.command.undoTransaction.commands,
    ],
  };
  const redoTransaction = {
    ...(previous.command.redoTransaction.transactionId
      ? { transactionId: previous.command.redoTransaction.transactionId }
      : next.command.redoTransaction.transactionId
        ? { transactionId: next.command.redoTransaction.transactionId }
        : {}),
    commands: [
      ...previous.command.redoTransaction.commands,
      ...next.command.redoTransaction.commands,
    ],
  };

  return {
    ...previous,
    command: {
      history: mergeCommandHistoryMetadata(previous.command.history, next.command.history, undoTransaction),
      undoTransaction,
      redoTransaction,
    },
  };
};

export function useTimelineHistory({
  dataRef,
  commitData,
  interactionStateRef,
}: UseTimelineHistoryArgs): UseTimelineHistoryResult {
  const { provider, timelineId } = useVideoEditorRuntime();
  const undoStackRef = useRef<UndoEntry[]>([]);
  const redoStackRef = useRef<UndoEntry[]>([]);
  const lastEditTimestampRef = useRef<number | null>(null);
  const editsSinceLastCheckpointRef = useRef(0);
  const lastUntransactedEditAtRef = useRef<number | null>(null);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);

  const syncHistoryState = useCallback(() => {
    const nextCanUndo = undoStackRef.current.length > 0;
    const nextCanRedo = redoStackRef.current.length > 0;
    setCanUndo((current) => (current === nextCanUndo ? current : nextCanUndo));
    setCanRedo((current) => (current === nextCanRedo ? current : nextCanRedo));
  }, []);

  const appendCheckpoint = useCallback((checkpoint: Checkpoint) => {
    setCheckpoints((current) => {
      const deduped = [checkpoint, ...current.filter((entry) => entry.id !== checkpoint.id)];
      return trimCheckpoints(deduped);
    });
  }, []);

  const clearRedoStack = useCallback(() => {
    if (redoStackRef.current.length === 0) {
      return;
    }

    redoStackRef.current = [];
    syncHistoryState();
  }, [syncHistoryState]);

  const persistCheckpoint = useCallback(async (
    currentData: TimelineData,
    triggerType: CheckpointTriggerType,
    editsSinceLastCheckpoint: number,
    label?: string,
  ) => {
    if (!isDataProviderPersistenceEnabled(provider) || !provider.saveCheckpoint) {
      return;
    }

    const createdAt = new Date().toISOString();
    const checkpointInput = {
      timelineId,
      config: cloneConfig(currentData.config),
      createdAt,
      triggerType,
      label: label?.trim() || defaultCheckpointLabel(triggerType),
      editsSinceLastCheckpoint,
    };

    try {
      const checkpointId = await provider.saveCheckpoint(timelineId, checkpointInput);
      appendCheckpoint({
        id: checkpointId,
        ...checkpointInput,
      });
    } catch {
      // Checkpoint persistence is best-effort and should not interrupt editing.
    }
  }, [appendCheckpoint, provider, timelineId]);

  const applyHistoryEntry = useCallback((
    current: TimelineData,
    entry: UndoEntry,
    direction: 'undo' | 'redo',
  ) => {
    if (entry.command) {
      const transaction = direction === 'undo'
        ? entry.command.undoTransaction
        : entry.command.redoTransaction;
      const result = historyCommandRunner.apply(current, transaction);
      if (result.status === 'ok') {
        return result.nextData;
      }
    }

    const nextConfig = cloneConfig(entry.snapshot.config);
    return entry.snapshot.registry
      ? buildDataFromSnapshot(nextConfig, entry.snapshot.registry, current)
      : buildDataFromCurrentRegistry(nextConfig, current);
  }, []);

  const restoreHistoryEntry = useCallback((entry: UndoEntry, direction: 'undo' | 'redo') => {
    const current = dataRef.current;
    if (!current) {
      return false;
    }

    const nextData = applyHistoryEntry(current, entry, direction);
    commitData(
      nextData,
      { save: true, skipHistory: true },
    );
    lastEditTimestampRef.current = Date.now();
    lastUntransactedEditAtRef.current = null;
    return true;
  }, [applyHistoryEntry, commitData, dataRef]);

  const pushUndoEntry = useCallback((entry: UndoEntry) => {
    undoStackRef.current = [...undoStackRef.current, entry].slice(-UNDO_STACK_LIMIT);
    syncHistoryState();
  }, [syncHistoryState]);

  const onBeforeCommit = useCallback((currentData: TimelineData, options: CommitHistoryOptions) => {
    const now = Date.now();
    const topUndoEntry = undoStackRef.current[undoStackRef.current.length - 1] ?? null;
    const hasMatchingTransaction = Boolean(
      options.transactionId
      && topUndoEntry?.transactionId
      && topUndoEntry.transactionId === options.transactionId,
    );
    const isDebouncedUntransactedEdit = Boolean(
      !options.transactionId
      && !topUndoEntry?.transactionId
      && lastUntransactedEditAtRef.current !== null
      && now - lastUntransactedEditAtRef.current <= UNTRANSACTED_COLLAPSE_WINDOW_MS,
    );
    const isSessionBoundary = Boolean(
      lastEditTimestampRef.current !== null
      && now - lastEditTimestampRef.current > SESSION_IDLE_MS,
    );
    const shouldCreateDistanceCheckpoint =
      editsSinceLastCheckpointRef.current >= EDIT_DISTANCE_CHECKPOINT_THRESHOLD;

    let checkpointTrigger: CheckpointTriggerType | null = null;
    if (isSessionBoundary) {
      checkpointTrigger = 'session_boundary';
    } else if (options.semantic) {
      checkpointTrigger = 'semantic';
    } else if (shouldCreateDistanceCheckpoint) {
      checkpointTrigger = 'edit_distance';
    }

    if (checkpointTrigger) {
      void persistCheckpoint(
        currentData,
        checkpointTrigger,
        editsSinceLastCheckpointRef.current,
      );
      editsSinceLastCheckpointRef.current = 1;
    } else {
      editsSinceLastCheckpointRef.current += 1;
    }

    clearRedoStack();

    const nextEntry: UndoEntry = {
      snapshot: buildSnapshot(currentData),
      timestamp: new Date(now).toISOString(),
      transactionId: options.transactionId,
      command: buildCommandHistoryEntry(options.commandHistory),
    };

    if (hasMatchingTransaction || isDebouncedUntransactedEdit) {
      if (topUndoEntry) {
        undoStackRef.current = [
          ...undoStackRef.current.slice(0, -1),
          mergeCollapsedEntry(topUndoEntry, nextEntry),
        ];
      }
    } else {
      pushUndoEntry(nextEntry);
    }

    lastEditTimestampRef.current = now;
    if (!options.transactionId) {
      lastUntransactedEditAtRef.current = now;
    } else {
      lastUntransactedEditAtRef.current = null;
    }
  }, [clearRedoStack, persistCheckpoint, pushUndoEntry]);

  const undo = useCallback(() => {
    const current = dataRef.current;
    const entry = undoStackRef.current[undoStackRef.current.length - 1];
    if (!current || !entry || isInteractionActive(interactionStateRef)) {
      return;
    }

    if (!restoreHistoryEntry(entry, 'undo')) {
      return;
    }

    undoStackRef.current = undoStackRef.current.slice(0, -1);
    redoStackRef.current = [
      ...redoStackRef.current,
      {
        ...entry,
        snapshot: buildSnapshot(current),
        timestamp: new Date().toISOString(),
      },
    ].slice(-UNDO_STACK_LIMIT);
    syncHistoryState();
  }, [dataRef, interactionStateRef, restoreHistoryEntry, syncHistoryState]);

  const redo = useCallback(() => {
    const current = dataRef.current;
    const entry = redoStackRef.current[redoStackRef.current.length - 1];
    if (!current || !entry || isInteractionActive(interactionStateRef)) {
      return;
    }

    if (!restoreHistoryEntry(entry, 'redo')) {
      return;
    }

    redoStackRef.current = redoStackRef.current.slice(0, -1);
    undoStackRef.current = [
      ...undoStackRef.current,
      {
        ...entry,
        snapshot: buildSnapshot(current),
        timestamp: new Date().toISOString(),
      },
    ].slice(-UNDO_STACK_LIMIT);
    syncHistoryState();
  }, [dataRef, interactionStateRef, restoreHistoryEntry, syncHistoryState]);

  const jumpToCheckpoint = useCallback((checkpointId: string) => {
    const current = dataRef.current;
    const checkpoint = checkpoints.find((entry) => entry.id === checkpointId);
    if (!current || !checkpoint) {
      return;
    }

    undoStackRef.current = [];
    redoStackRef.current = [];
    syncHistoryState();
    restoreHistoryEntry({
      snapshot: {
        config: cloneConfig(checkpoint.config),
        signature: checkpoint.id,
      },
      timestamp: new Date().toISOString(),
    }, 'undo');
    editsSinceLastCheckpointRef.current = 0;
  }, [checkpoints, dataRef, restoreHistoryEntry, syncHistoryState]);

  const createManualCheckpoint = useCallback(async (label?: string) => {
    const current = dataRef.current;
    if (!current) {
      return;
    }

    await persistCheckpoint(
      current,
      'manual',
      editsSinceLastCheckpointRef.current,
      label,
    );
    editsSinceLastCheckpointRef.current = 0;
  }, [dataRef, persistCheckpoint]);

  useEffect(() => {
    if (!isDataProviderPersistenceEnabled(provider) || !provider.loadCheckpoints) {
      return;
    }

    let cancelled = false;

    void provider.loadCheckpoints(timelineId)
      .then((loadedCheckpoints) => {
        if (cancelled) {
          return;
        }

        setCheckpoints(trimCheckpoints(loadedCheckpoints));
      })
      .catch(() => {
        if (!cancelled) {
          setCheckpoints([]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [provider, timelineId]);

  return {
    canUndo,
    canRedo,
    checkpoints,
    onBeforeCommit,
    undo,
    redo,
    jumpToCheckpoint,
    createManualCheckpoint,
    createCheckpoint: createManualCheckpoint,
  };
}
