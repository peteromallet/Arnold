import { describe, expect, it, vi, beforeEach } from 'vitest';

const mocks = vi.hoisted(() => ({
  cleanupFile: vi.fn<(supabase: unknown, path: string) => Promise<void>>(),
  toErrorMessage: vi.fn((error: unknown) => (error instanceof Error ? error.message : String(error))),
}));

vi.mock('./storage.ts', () => ({
  cleanupFile: (...args: unknown[]) => mocks.cleanupFile(...(args as [unknown, string])),
}));

vi.mock('../_shared/errorMessage.ts', () => ({
  toErrorMessage: (...args: unknown[]) => mocks.toErrorMessage(...args),
}));

import { cleanupMaterializedInputs } from './cleanupMaterializedInputs.ts';
import type { TaskContext } from './completionHelpers.ts';

function makeTaskContext(materialized_inputs: TaskContext['materialized_inputs']): TaskContext {
  return {
    id: 'task-1',
    task_type: 'noop',
    project_id: 'project-1',
    params: {},
    result_data: null,
    tool_type: 'unknown',
    category: 'unknown',
    content_type: 'image',
    variant_type: null,
    materialized_inputs,
  };
}

function makeLogger() {
  return {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  };
}

describe('cleanupMaterializedInputs', () => {
  const supabaseAdmin = {} as unknown as Parameters<typeof cleanupMaterializedInputs>[0];

  beforeEach(() => {
    mocks.cleanupFile.mockReset();
    mocks.cleanupFile.mockResolvedValue(undefined);
  });

  it('returns [] for empty/null materialized_inputs without calling cleanupFile', async () => {
    const logger = makeLogger();

    expect(await cleanupMaterializedInputs(supabaseAdmin, makeTaskContext(null), logger)).toEqual([]);
    expect(await cleanupMaterializedInputs(supabaseAdmin, makeTaskContext([]), logger)).toEqual([]);
    expect(await cleanupMaterializedInputs(supabaseAdmin, makeTaskContext(undefined), logger)).toEqual([]);

    expect(mocks.cleanupFile).not.toHaveBeenCalled();
  });

  it('calls cleanupFile for kind:remote and tolerates missing-object (cleanupFile resolves silently)', async () => {
    const logger = makeLogger();
    const ctx = makeTaskContext([
      { generation_id: 'gen-1', kind: 'remote', target: 'projects/abc/source.png' },
    ]);

    const issues = await cleanupMaterializedInputs(supabaseAdmin, ctx, logger);

    expect(issues).toEqual([]);
    expect(mocks.cleanupFile).toHaveBeenCalledTimes(1);
    expect(mocks.cleanupFile).toHaveBeenCalledWith(supabaseAdmin, 'projects/abc/source.png');
  });

  it('skips kind:file records (no cleanupFile call) and logs the worker-side handoff', async () => {
    const logger = makeLogger();
    const ctx = makeTaskContext([
      { generation_id: 'gen-2', kind: 'file', target: '/Users/me/.reigh-local-files/gen-2.png' },
    ]);

    const issues = await cleanupMaterializedInputs(supabaseAdmin, ctx, logger);

    expect(issues).toEqual([]);
    expect(mocks.cleanupFile).not.toHaveBeenCalled();
    expect(logger.info).toHaveBeenCalledWith(
      expect.stringContaining('[MaterializedInputCleanup] worker-side cleanup for path='),
      expect.objectContaining({ generation_id: 'gen-2' }),
    );
  });

  it('produces a follow-up issue (no throw) when cleanupFile throws unexpectedly', async () => {
    const logger = makeLogger();
    mocks.cleanupFile.mockRejectedValueOnce(new Error('storage 500'));
    const ctx = makeTaskContext([
      { generation_id: 'gen-3', kind: 'remote', target: 'projects/abc/dead.png' },
      { generation_id: 'gen-4', kind: 'remote', target: 'projects/abc/alive.png' },
    ]);

    const issues = await cleanupMaterializedInputs(supabaseAdmin, ctx, logger);

    expect(issues).toHaveLength(1);
    expect(issues[0]).toMatchObject({
      step: 'materialized_input_cleanup',
      code: 'materialized_input_cleanup_failed',
    });
    expect(issues[0].message).toContain('projects/abc/dead.png');
    expect(mocks.cleanupFile).toHaveBeenCalledTimes(2);
  });

  it('handles mixed kinds in one task: remote → cleanupFile, file → skipped', async () => {
    const logger = makeLogger();
    const ctx = makeTaskContext([
      { generation_id: 'gen-a', kind: 'file', target: '/tmp/gen-a.png' },
      { generation_id: 'gen-b', kind: 'remote', target: 'objects/gen-b.png' },
    ]);

    const issues = await cleanupMaterializedInputs(supabaseAdmin, ctx, logger);

    expect(issues).toEqual([]);
    expect(mocks.cleanupFile).toHaveBeenCalledTimes(1);
    expect(mocks.cleanupFile).toHaveBeenCalledWith(supabaseAdmin, 'objects/gen-b.png');
  });

  it('records a follow-up issue and continues for malformed entries', async () => {
    const logger = makeLogger();
    const ctx = makeTaskContext([
      { generation_id: 'gen-x', kind: 'unknown', target: 'whatever' } as unknown as never,
      { generation_id: 'gen-y', kind: 'remote', target: 'objects/gen-y.png' },
    ]);

    const issues = await cleanupMaterializedInputs(supabaseAdmin, ctx, logger);

    expect(issues).toHaveLength(1);
    expect(issues[0].code).toBe('materialized_input_cleanup_failed');
    expect(mocks.cleanupFile).toHaveBeenCalledWith(supabaseAdmin, 'objects/gen-y.png');
  });
});
