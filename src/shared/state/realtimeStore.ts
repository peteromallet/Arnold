import { shallow } from 'zustand/shallow';
import { useStoreWithEqualityFn } from 'zustand/traditional';
import { createStore } from 'zustand/vanilla';
import { mapTaskDbRowToTask, isTaskDbRow } from '@/shared/lib/taskRowMapper';
import { resolveTaskProjectScope } from '@/shared/lib/tasks/resolveTaskProjectScope';
import { deepEqual } from '@/shared/lib/utils/deepEqual';
import { TASK_STATUS, type Task } from '@/types/tasks';

export interface PendingGenerationTaskSnapshot {
  id: string;
  status: Task['status'];
  task_type: Task['taskType'];
}

interface RealtimeTaskScopeState {
  tasks: Record<string, Task>;
  taskGenerationIds: Record<string, readonly string[]>;
  pendingTaskIdsByGeneration: Record<string, readonly string[]>;
  pendingTasksByGeneration: Record<string, readonly PendingGenerationTaskSnapshot[]>;
}

interface RealtimeStoreState {
  scopes: Record<string, RealtimeTaskScopeState>;
  upsertTask: (task: Task, projectId?: string | null) => Task | null;
  upsertTasks: (tasks: readonly Task[], projectId?: string | null) => Task[];
  resetScope: (projectId?: string | null) => void;
  resetAll: () => void;
}

const EMPTY_TASKS = Object.freeze({}) as Record<string, Task>;
const EMPTY_GENERATION_IDS = Object.freeze({}) as Record<string, readonly string[]>;
const EMPTY_PENDING_IDS = Object.freeze({}) as Record<string, readonly string[]>;
const EMPTY_PENDING_TASKS = Object.freeze({}) as Record<string, readonly PendingGenerationTaskSnapshot[]>;
const EMPTY_STRING_ARRAY = Object.freeze([]) as readonly string[];
const EMPTY_PENDING_TASK_ARRAY = Object.freeze([]) as readonly PendingGenerationTaskSnapshot[];

function createEmptyScopeState(): RealtimeTaskScopeState {
  return {
    tasks: EMPTY_TASKS,
    taskGenerationIds: EMPTY_GENERATION_IDS,
    pendingTaskIdsByGeneration: EMPTY_PENDING_IDS,
    pendingTasksByGeneration: EMPTY_PENDING_TASKS,
  };
}

function isPendingTaskStatus(status: Task['status']): boolean {
  return status === TASK_STATUS.QUEUED || status === TASK_STATUS.IN_PROGRESS;
}

function addGenerationId(target: Set<string>, value: unknown): void {
  if (typeof value !== 'string') {
    return;
  }

  const trimmed = value.trim();
  if (trimmed) {
    target.add(trimmed);
  }
}

function addGenerationIdsFromArray(target: Set<string>, value: unknown): void {
  if (!Array.isArray(value)) {
    return;
  }

  value.forEach((item) => addGenerationId(target, item));
}

function addGenerationIdsFromRecord(target: Set<string>, value: unknown): void {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return;
  }

  const record = value as Record<string, unknown>;
  addGenerationId(target, record.based_on);
  addGenerationId(target, record.source_generation_id);
  addGenerationId(target, record.generation_id);
  addGenerationId(target, record.input_generation_id);
  addGenerationId(target, record.parent_generation_id);
  addGenerationId(target, record.start_image_generation_id);
  addGenerationId(target, record.end_image_generation_id);
  addGenerationId(target, record.pair_shot_generation_id);
  addGenerationIdsFromArray(target, record.input_image_generation_ids);
  addGenerationIdsFromArray(target, record.pair_shot_generation_ids);
}

export function collectTaskGenerationIds(task: Task): readonly string[] {
  if (!isPendingTaskStatus(task.status)) {
    return EMPTY_STRING_ARRAY;
  }

  const generationIds = new Set<string>();
  addGenerationIdsFromRecord(generationIds, task.params);

  const params = task.params as Record<string, unknown>;
  addGenerationIdsFromRecord(generationIds, params.orchestrator_details);
  addGenerationIdsFromRecord(generationIds, params.full_orchestrator_payload);
  addGenerationIdsFromRecord(generationIds, params.individual_segment_params);

  if (generationIds.size === 0) {
    return EMPTY_STRING_ARRAY;
  }

  return Object.freeze(Array.from(generationIds));
}

function areStringArraysEqual(left: readonly string[], right: readonly string[]): boolean {
  if (left === right) {
    return true;
  }

  if (left.length !== right.length) {
    return false;
  }

  for (let index = 0; index < left.length; index += 1) {
    if (left[index] !== right[index]) {
      return false;
    }
  }

  return true;
}

function buildPendingTaskSummaries(
  taskIds: readonly string[],
  tasks: Record<string, Task>,
  previous: readonly PendingGenerationTaskSnapshot[],
): readonly PendingGenerationTaskSnapshot[] {
  if (taskIds.length === 0) {
    return EMPTY_PENDING_TASK_ARRAY;
  }

  const previousById = new Map(previous.map((task) => [task.id, task]));
  const next = taskIds.flatMap((taskId) => {
    const task = tasks[taskId];
    if (!task || !isPendingTaskStatus(task.status)) {
      return [];
    }

    const existing = previousById.get(task.id);
    if (existing && existing.status === task.status && existing.task_type === task.taskType) {
      return [existing];
    }

    return [{
      id: task.id,
      status: task.status,
      task_type: task.taskType,
    }];
  });

  if (next.length === 0) {
    return EMPTY_PENDING_TASK_ARRAY;
  }

  if (next.length === previous.length && next.every((task, index) => task === previous[index])) {
    return previous;
  }

  return Object.freeze(next);
}

function resolveScopeKey(projectId?: string | null): string | null {
  return resolveTaskProjectScope(projectId);
}

function resolveTaskScopeKey(task: Task, projectId?: string | null): string | null {
  return resolveTaskProjectScope(projectId ?? task.projectId);
}

function getScopeState(
  scopes: Record<string, RealtimeTaskScopeState>,
  scopeKey: string,
): RealtimeTaskScopeState {
  return scopes[scopeKey] ?? createEmptyScopeState();
}

function buildUpdatedScopeState(scopeState: RealtimeTaskScopeState, task: Task): RealtimeTaskScopeState {
  const previousTask = scopeState.tasks[task.id];
  const nextTask = previousTask && deepEqual(previousTask, task) ? previousTask : task;
  const previousGenerationIds = scopeState.taskGenerationIds[task.id] ?? EMPTY_STRING_ARRAY;
  const nextGenerationIds = collectTaskGenerationIds(nextTask);
  const taskChanged = previousTask !== nextTask;
  const generationIdsChanged = !areStringArraysEqual(previousGenerationIds, nextGenerationIds);

  if (!taskChanged && !generationIdsChanged) {
    return scopeState;
  }

  const nextTasks = taskChanged
    ? { ...scopeState.tasks, [task.id]: nextTask }
    : scopeState.tasks;

  const nextTaskGenerationIds = { ...scopeState.taskGenerationIds };
  if (nextGenerationIds.length > 0) {
    nextTaskGenerationIds[task.id] = nextGenerationIds;
  } else {
    delete nextTaskGenerationIds[task.id];
  }

  const nextPendingTaskIdsByGeneration = { ...scopeState.pendingTaskIdsByGeneration };
  const nextPendingTasksByGeneration = { ...scopeState.pendingTasksByGeneration };

  const affectedGenerationIds = new Set<string>([
    ...previousGenerationIds,
    ...nextGenerationIds,
  ]);

  affectedGenerationIds.forEach((generationId) => {
    const previousTaskIds = scopeState.pendingTaskIdsByGeneration[generationId] ?? EMPTY_STRING_ARRAY;
    const shouldInclude = nextGenerationIds.includes(generationId);
    const alreadyIncluded = previousTaskIds.includes(task.id);

    let nextTaskIds = previousTaskIds;
    if (shouldInclude && !alreadyIncluded) {
      nextTaskIds = Object.freeze([...previousTaskIds, task.id]);
    } else if (!shouldInclude && alreadyIncluded) {
      nextTaskIds = Object.freeze(previousTaskIds.filter((pendingTaskId) => pendingTaskId !== task.id));
    }

    if (nextTaskIds.length === 0) {
      delete nextPendingTaskIdsByGeneration[generationId];
    } else {
      nextPendingTaskIdsByGeneration[generationId] = nextTaskIds;
    }

    const previousPendingTasks = scopeState.pendingTasksByGeneration[generationId] ?? EMPTY_PENDING_TASK_ARRAY;
    const nextPendingTasks = buildPendingTaskSummaries(nextTaskIds, nextTasks, previousPendingTasks);

    if (nextPendingTasks.length === 0) {
      delete nextPendingTasksByGeneration[generationId];
    } else {
      nextPendingTasksByGeneration[generationId] = nextPendingTasks;
    }
  });

  return {
    tasks: nextTasks,
    taskGenerationIds: nextTaskGenerationIds,
    pendingTaskIdsByGeneration: nextPendingTaskIdsByGeneration,
    pendingTasksByGeneration: nextPendingTasksByGeneration,
  };
}

function upsertTaskIntoScopes(
  scopes: Record<string, RealtimeTaskScopeState>,
  task: Task,
  projectId?: string | null,
): Record<string, RealtimeTaskScopeState> {
  const scopeKey = resolveTaskScopeKey(task, projectId);
  if (!scopeKey) {
    return scopes;
  }

  const scopeState = getScopeState(scopes, scopeKey);
  const nextScopeState = buildUpdatedScopeState(scopeState, task);
  if (nextScopeState === scopeState) {
    return scopes;
  }

  return {
    ...scopes,
    [scopeKey]: nextScopeState,
  };
}

const realtimeTaskStore = createStore<RealtimeStoreState>((set, get) => ({
  scopes: {},
  upsertTask: (task, projectId) => {
    const scopeKey = resolveTaskScopeKey(task, projectId);
    if (!scopeKey) {
      return null;
    }

    set((state) => ({
      scopes: upsertTaskIntoScopes(state.scopes, task, projectId),
    }));

    return get().scopes[scopeKey]?.tasks[task.id] ?? null;
  },
  upsertTasks: (tasks, projectId) => {
    if (tasks.length === 0) {
      return [];
    }

    set((state) => {
      let nextScopes = state.scopes;
      tasks.forEach((task) => {
        nextScopes = upsertTaskIntoScopes(nextScopes, task, projectId);
      });

      return nextScopes === state.scopes
        ? state
        : { scopes: nextScopes };
    });

    return tasks.flatMap((task) => {
      const scopeKey = resolveTaskScopeKey(task, projectId);
      if (!scopeKey) {
        return [];
      }

      const seededTask = get().scopes[scopeKey]?.tasks[task.id];
      return seededTask ? [seededTask] : [];
    });
  },
  resetScope: (projectId) => {
    const scopeKey = resolveScopeKey(projectId);
    if (!scopeKey) {
      return;
    }

    set((state) => {
      if (!(scopeKey in state.scopes)) {
        return state;
      }

      const nextScopes = { ...state.scopes };
      delete nextScopes[scopeKey];
      return { scopes: nextScopes };
    });
  },
  resetAll: () => {
    set({ scopes: {} });
  },
}));

function useRealtimeTaskStore<T>(
  selector: (state: RealtimeStoreState) => T,
  equalityFn?: (left: T, right: T) => boolean,
): T {
  return useStoreWithEqualityFn(realtimeTaskStore, selector, equalityFn);
}

export function useRealtimeTask(taskId: string, projectId?: string | null): Task | null {
  return useRealtimeTaskStore((state) => {
    const scopeKey = resolveScopeKey(projectId);
    if (!scopeKey || !taskId) {
      return null;
    }

    return state.scopes[scopeKey]?.tasks[taskId] ?? null;
  });
}

export function getRealtimeTaskSnapshot(taskId: string, projectId?: string | null): Task | null {
  const scopeKey = resolveScopeKey(projectId);
  if (!scopeKey || !taskId) {
    return null;
  }

  return realtimeTaskStore.getState().scopes[scopeKey]?.tasks[taskId] ?? null;
}

export function useRealtimePendingGenerationTasks(
  generationId: string | null | undefined,
  projectId?: string | null,
): { pendingCount: number; pendingTasks: readonly PendingGenerationTaskSnapshot[] } {
  return useRealtimeTaskStore((state) => {
    const scopeKey = resolveScopeKey(projectId);
    if (!scopeKey || !generationId) {
      return {
        pendingCount: 0,
        pendingTasks: EMPTY_PENDING_TASK_ARRAY,
      };
    }

    const pendingTasks = state.scopes[scopeKey]?.pendingTasksByGeneration[generationId] ?? EMPTY_PENDING_TASK_ARRAY;
    return {
      pendingCount: pendingTasks.length,
      pendingTasks,
    };
  }, shallow);
}

export function upsertRealtimeTaskSnapshot(task: Task, projectId?: string | null): Task | null {
  return realtimeTaskStore.getState().upsertTask(task, projectId);
}

export function upsertRealtimeTaskSnapshots(tasks: readonly Task[], projectId?: string | null): Task[] {
  return realtimeTaskStore.getState().upsertTasks(tasks, projectId);
}

export function seedRealtimeTaskFromRow(row: unknown, projectId?: string | null): Task | null {
  if (!isTaskDbRow(row)) {
    return null;
  }

  return upsertRealtimeTaskSnapshot(mapTaskDbRowToTask(row), projectId);
}

export function seedRealtimeTasksFromRows(rows: readonly unknown[], projectId?: string | null): Task[] {
  const tasks = rows.flatMap((row) => (isTaskDbRow(row) ? [mapTaskDbRowToTask(row)] : []));
  return upsertRealtimeTaskSnapshots(tasks, projectId);
}

export function resetRealtimeTaskScope(projectId?: string | null): void {
  realtimeTaskStore.getState().resetScope(projectId);
}

export function __resetRealtimeTaskStoreForTests(): void {
  realtimeTaskStore.getState().resetAll();
}
