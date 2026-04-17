// @vitest-environment jsdom

import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { setProjectSelectionSnapshot, resetProjectSelectionStoreForTests } from '@/shared/contexts/projectSelectionStore';
import type { Task } from '@/types/tasks';
import {
  __resetRealtimeTaskStoreForTests,
  resetRealtimeTaskScope,
  seedRealtimeTaskFromRow,
  seedRealtimeTasksFromRows,
  upsertRealtimeTaskSnapshot,
  upsertRealtimeTaskSnapshots,
  useRealtimePendingGenerationTasks,
  useRealtimeTask,
} from './realtimeStore';

function createTask(overrides: Partial<Task> = {}): Task {
  return {
    id: overrides.id ?? 'task-1',
    taskType: overrides.taskType ?? 'image_generation',
    params: overrides.params ?? {},
    status: overrides.status ?? 'Queued',
    createdAt: overrides.createdAt ?? '2026-04-17T00:00:00.000Z',
    projectId: overrides.projectId ?? 'project-1',
    ...overrides,
  };
}

describe('realtimeStore', () => {
  beforeEach(() => {
    __resetRealtimeTaskStoreForTests();
    resetProjectSelectionStoreForTests();
  });

  it('stores canonical tasks by effective project scope and supports single plus batch upserts', () => {
    setProjectSelectionSnapshot({ selectedProjectId: 'fallback-project' });

    const seeded = upsertRealtimeTaskSnapshot(createTask({
      id: 'task-single',
      projectId: 'project-1',
      params: { source_generation_id: 'gen-1' },
    }));
    const batch = upsertRealtimeTaskSnapshots([
      createTask({
        id: 'task-batch-1',
        projectId: 'project-1',
        params: { source_generation_id: 'gen-1' },
      }),
      createTask({
        id: 'task-batch-2',
        projectId: 'fallback-project',
        params: { source_generation_id: 'gen-2' },
      }),
    ]);

    const scopedTask = renderHook(() => useRealtimeTask('task-single', 'project-1'));
    const fallbackTask = renderHook(() => useRealtimeTask('task-batch-2'));

    expect(seeded).toMatchObject({
      id: 'task-single',
      projectId: 'project-1',
      taskType: 'image_generation',
    });
    expect(batch).toHaveLength(2);
    expect(scopedTask.result.current?.id).toBe('task-single');
    expect(fallbackTask.result.current?.id).toBe('task-batch-2');
  });

  it('hydrates from raw realtime rows through the canonical task-row mapper and ignores invalid rows', () => {
    const seeded = seedRealtimeTaskFromRow({
      id: 'task-row-1',
      task_type: 'video_generation',
      params: { parent_generation_id: 'gen-1' },
      status: 'In Progress',
      created_at: '2026-04-17T00:00:00.000Z',
      project_id: 'project-1',
      updated_at: null,
    });

    const batch = seedRealtimeTasksFromRows([
      {
        id: 'task-row-2',
        task_type: 'image_generation',
        params: { source_generation_id: 'gen-2' },
        status: 'Queued',
        created_at: '2026-04-17T00:00:00.000Z',
        project_id: 'project-1',
      },
      { invalid: true },
    ]);

    const seededHook = renderHook(() => useRealtimeTask('task-row-1', 'project-1'));
    const invalidHook = renderHook(() => useRealtimeTask('missing-task', 'project-1'));

    expect(seeded).toMatchObject({
      id: 'task-row-1',
      taskType: 'video_generation',
      projectId: 'project-1',
    });
    expect(batch.map((task) => task.id)).toEqual(['task-row-2']);
    expect(seededHook.result.current?.taskType).toBe('video_generation');
    expect(invalidHook.result.current).toBeNull();
  });

  it('narrows single-task subscriptions so unrelated task updates do not rerender other selectors', () => {
    upsertRealtimeTaskSnapshots([
      createTask({ id: 'task-a', projectId: 'project-1', params: { source_generation_id: 'gen-a' } }),
      createTask({ id: 'task-b', projectId: 'project-1', params: { source_generation_id: 'gen-b' } }),
    ]);

    let taskARenders = 0;
    let taskBRenders = 0;

    renderHook(() => {
      taskARenders += 1;
      return useRealtimeTask('task-a', 'project-1');
    });
    renderHook(() => {
      taskBRenders += 1;
      return useRealtimeTask('task-b', 'project-1');
    });

    act(() => {
      upsertRealtimeTaskSnapshot(createTask({
        id: 'task-a',
        projectId: 'project-1',
        status: 'In Progress',
        params: { source_generation_id: 'gen-a' },
      }));
    });

    expect(taskARenders).toBe(2);
    expect(taskBRenders).toBe(1);

    act(() => {
      upsertRealtimeTaskSnapshot(createTask({
        id: 'task-a',
        projectId: 'project-1',
        status: 'In Progress',
        params: { source_generation_id: 'gen-a' },
      }));
    });

    expect(taskARenders).toBe(2);
    expect(taskBRenders).toBe(1);
  });

  it('preserves stable pending-generation selector references for unrelated task updates', () => {
    upsertRealtimeTaskSnapshots([
      createTask({
        id: 'task-a',
        projectId: 'project-1',
        status: 'Queued',
        params: { source_generation_id: 'gen-1' },
      }),
      createTask({
        id: 'task-b',
        projectId: 'project-1',
        status: 'Queued',
        params: { source_generation_id: 'gen-2' },
      }),
    ]);

    let renders = 0;
    const { result } = renderHook(() => {
      renders += 1;
      return useRealtimePendingGenerationTasks('gen-1', 'project-1');
    });

    const firstPendingTasks = result.current.pendingTasks;

    act(() => {
      upsertRealtimeTaskSnapshot(createTask({
        id: 'task-b',
        projectId: 'project-1',
        status: 'In Progress',
        params: { source_generation_id: 'gen-2' },
      }));
    });

    expect(renders).toBe(1);
    expect(result.current.pendingTasks).toBe(firstPendingTasks);
    expect(result.current.pendingCount).toBe(1);
  });

  it('resets task snapshots by scope without affecting other project scopes', () => {
    upsertRealtimeTaskSnapshots([
      createTask({ id: 'task-project-1', projectId: 'project-1', params: { source_generation_id: 'gen-1' } }),
      createTask({ id: 'task-project-2', projectId: 'project-2', params: { source_generation_id: 'gen-2' } }),
    ]);

    const projectOne = renderHook(() => useRealtimeTask('task-project-1', 'project-1'));
    const projectTwo = renderHook(() => useRealtimeTask('task-project-2', 'project-2'));

    act(() => {
      resetRealtimeTaskScope('project-1');
    });

    expect(projectOne.result.current).toBeNull();
    expect(projectTwo.result.current?.id).toBe('task-project-2');
  });
});
