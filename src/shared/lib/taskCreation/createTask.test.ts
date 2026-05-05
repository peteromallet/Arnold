import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/integrations/supabase/config/env', () => ({
  getSupabaseUrl: () => 'https://example.supabase.co',
  getSupabasePublishableKey: () => 'pk-test',
}));

vi.mock('@/shared/lib/supabaseSession', () => ({
  readAccessTokenFromStorage: () => 'token-test',
}));

vi.mock('@/shared/lib/errorHandling/runtimeError', () => ({
  normalizeAndPresentAndRethrow: (error: unknown) => {
    throw error;
  },
}));

import { createTask } from './createTask';
import { beginLocalWorkerSession } from './localWorkerSession';
import type { LocalWorkerSession, MaterializedInputRecord } from './localWorkerSession';

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue({
    ok: true,
    json: async () => ({ task_id: 'created-task', status: 'queued' }),
  });
  globalThis.fetch = fetchMock as unknown as typeof fetch;
});

afterEach(() => {
  vi.restoreAllMocks();
});

function lastFetchBody(): Record<string, unknown> {
  expect(fetchMock).toHaveBeenCalled();
  const call = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
  const init = call[1] as RequestInit;
  return JSON.parse(init.body as string) as Record<string, unknown>;
}

function fakeSessionWithRecords(records: MaterializedInputRecord[]): LocalWorkerSession {
  return {
    probe: () => Promise.resolve(false),
    register: () => undefined,
    records: () => records,
    cached: () => null,
  };
}

describe('createTask materialized_inputs body wiring', () => {
  it('omits materialized_inputs when no session is provided', async () => {
    await createTask({
      family: 'image-generation',
      project_id: 'proj-1',
      input: { prompt: 'hi' },
    });

    const body = lastFetchBody();
    expect(body).not.toHaveProperty('materialized_inputs');
    expect(body).toMatchObject({
      family: 'image-generation',
      project_id: 'proj-1',
      input: { prompt: 'hi' },
    });
    expect(body.idempotency_key).toEqual(expect.any(String));
  });

  it('omits materialized_inputs when session has no records', async () => {
    await createTask(
      { family: 'image-generation', project_id: 'proj-1', input: { prompt: 'hi' } },
      { localWorkerSession: beginLocalWorkerSession() },
    );

    const body = lastFetchBody();
    expect(body).not.toHaveProperty('materialized_inputs');
  });

  it('includes materialized_inputs when session has ≥1 record', async () => {
    const records: MaterializedInputRecord[] = [
      { generation_id: 'gen-a', kind: 'remote', target: 'user/uploads/a.png' },
      { generation_id: 'gen-b', kind: 'file', target: '/tmp/.reigh-local-files/gen-b.png' },
    ];

    await createTask(
      { family: 'travel', project_id: 'proj-2', input: { x: 1 } },
      { localWorkerSession: fakeSessionWithRecords(records) },
    );

    const body = lastFetchBody();
    expect(body.materialized_inputs).toEqual(records);
  });
});
