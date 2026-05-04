import { beforeEach, describe, expect, it, vi } from 'vitest';

const GENERATION_IDS = {
  one: '11111111-1111-4111-8111-111111111111',
  two: '22222222-2222-4222-8222-222222222222',
  ok: '33333333-3333-4333-8333-333333333333',
  invalidTasks: '44444444-4444-4444-8444-444444444444',
  missing: '55555555-5555-4555-8555-555555555555',
} as const;

type InResponse = { data: Array<{ id: string; tasks: unknown; project_id: string | null }> | null; error: { message: string } | null };
type SingleResponse = {
  data: { id: string; project_id: string | null } | null;
  error: { message: string; code?: string } | null;
};

function createSupabaseClientMock(options?: {
  inResponse?: InResponse;
  singleResponse?: SingleResponse;
}) {
  const inResponse: InResponse = options?.inResponse ?? { data: [], error: null };
  const singleResponse: SingleResponse = options?.singleResponse ?? { data: null, error: null };

  const inMock = vi.fn().mockResolvedValue(inResponse);
  const maybeSingleMock = vi.fn().mockResolvedValue(singleResponse);
  const eqMock = vi.fn().mockReturnValue({ maybeSingle: maybeSingleMock });
  const selectMock = vi.fn((columns: string) => {
    if (columns === 'id, project_id') {
      return { eq: eqMock };
    }
    return { in: inMock };
  });
  const fromMock = vi.fn().mockReturnValue({ select: selectMock });

  return {
    client: { from: fromMock },
    mocks: { inMock, maybeSingleMock, eqMock, selectMock, fromMock },
  };
}

const { mockGetSupabaseClientResult } = vi.hoisted(() => ({
  mockGetSupabaseClientResult: vi.fn(),
}));

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClientResult: () => mockGetSupabaseClientResult(),
}));

vi.mock('@/shared/lib/tasks/orchestratorReference', () => ({
  applyRootTaskFilter: <T,>(query: T) => query,
}));

import {
  resolveGenerationTaskMapping,
  resolveGenerationTaskMappings,
  resolveGenerationProjectScope,
  resolveVariantProjectScope,
} from '../tasks/generationTaskRepository';

describe('generationTaskRepository', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('maps query failures to query_failed status for each requested generation', async () => {
    const { client } = createSupabaseClientMock({
      inResponse: { data: null, error: { message: 'DB down' } },
    });
    mockGetSupabaseClientResult.mockReturnValue({ ok: true, client });

    const result = await resolveGenerationTaskMappings([GENERATION_IDS.one, GENERATION_IDS.two]);

    expect(result.get(GENERATION_IDS.one)).toMatchObject({ status: 'query_failed', taskId: null });
    expect(result.get(GENERATION_IDS.two)).toMatchObject({ status: 'query_failed', taskId: null });
  });

  it('marks invalid generation ids as not_loaded without querying Supabase', async () => {
    const { client, mocks } = createSupabaseClientMock();
    mockGetSupabaseClientResult.mockReturnValue({ ok: true, client });

    const result = await resolveGenerationTaskMappings(['temp-generation-id']);

    expect(result.get('temp-generation-id')).toMatchObject({ status: 'not_loaded', taskId: null });
    expect(mocks.fromMock).not.toHaveBeenCalled();
  });

  it('returns ok for both legacy string tasks and array tasks, plus missing_generation', async () => {
    const { client } = createSupabaseClientMock({
      inResponse: {
        data: [
          { id: GENERATION_IDS.ok, tasks: ['task-1', 'task-2'], project_id: 'project-1' },
          { id: GENERATION_IDS.invalidTasks, tasks: 'not-an-array', project_id: 'project-1' },
        ],
        error: null,
      },
    });
    mockGetSupabaseClientResult.mockReturnValue({ ok: true, client });

    const result = await resolveGenerationTaskMappings([
      GENERATION_IDS.ok,
      GENERATION_IDS.invalidTasks,
      GENERATION_IDS.missing,
    ]);

    expect(result.get(GENERATION_IDS.ok)).toMatchObject({ status: 'ok', taskId: 'task-1' });
    expect(result.get(GENERATION_IDS.invalidTasks)).toMatchObject({ status: 'ok', taskId: 'not-an-array' });
    expect(result.get(GENERATION_IDS.missing)).toMatchObject({ status: 'missing_generation', taskId: null });
  });

  it('enforces project scope and returns scope_mismatch for out-of-scope rows', async () => {
    const { client } = createSupabaseClientMock({
      inResponse: {
        data: [
          { id: GENERATION_IDS.one, tasks: ['task-1'], project_id: 'project-a' },
        ],
        error: null,
      },
    });
    mockGetSupabaseClientResult.mockReturnValue({ ok: true, client });

    const result = await resolveGenerationTaskMappings([GENERATION_IDS.one], { projectId: 'project-b' });

    expect(result.get(GENERATION_IDS.one)).toMatchObject({ status: 'scope_mismatch', taskId: null });
  });

  it('keeps bridge-facing single lookup aligned with mapping semantics', async () => {
    const { client } = createSupabaseClientMock({
      inResponse: {
        data: [{ id: GENERATION_IDS.one, tasks: ['task-1'], project_id: 'project-1' }],
        error: null,
      },
    });
    mockGetSupabaseClientResult.mockReturnValue({ ok: true, client });

    const mapping = await resolveGenerationTaskMapping(GENERATION_IDS.one);
    expect(mapping).toMatchObject({ generationId: GENERATION_IDS.one, status: 'ok', taskId: 'task-1' });
  });

  it('resolves project scope statuses for ok, missing_generation, and query_failed paths', async () => {
    const okClient = createSupabaseClientMock({
      singleResponse: { data: { id: 'gen-1', project_id: 'project-1' }, error: null },
    }).client;
    mockGetSupabaseClientResult.mockReturnValue({ ok: true, client: okClient });
    const ok = await resolveGenerationProjectScope('gen-1', 'project-1');
    expect(ok).toMatchObject({ status: 'ok', projectId: 'project-1' });

    const missingClient = createSupabaseClientMock({
      singleResponse: {
        data: null,
        error: { code: 'PGRST116', message: 'JSON object requested, multiple (or no) rows returned' },
      },
    }).client;
    mockGetSupabaseClientResult.mockReturnValue({ ok: true, client: missingClient });
    const missing = await resolveGenerationProjectScope('gen-1', 'project-1');
    expect(missing).toMatchObject({ status: 'missing_generation', projectId: null });

    const failedClient = createSupabaseClientMock({
      singleResponse: { data: null, error: { message: 'boom' } },
    }).client;
    mockGetSupabaseClientResult.mockReturnValue({ ok: true, client: failedClient });
    const failed = await resolveGenerationProjectScope('gen-1', 'project-1');
    expect(failed).toMatchObject({ status: 'query_failed', projectId: null });
  });

  it('classifies broken variant->generation linkage as missing_generation (not missing_variant)', async () => {
    const maybeSingleMock = vi.fn().mockResolvedValue({
      data: { id: 'var-1', generation_id: null, project_id: 'project-1' },
      error: null,
    });
    const eqMock = vi.fn().mockReturnValue({ maybeSingle: maybeSingleMock });
    const selectMock = vi.fn().mockReturnValue({ eq: eqMock });
    const fromMock = vi.fn().mockReturnValue({ select: selectMock });
    mockGetSupabaseClientResult.mockReturnValue({ ok: true, client: { from: fromMock } });

    const scope = await resolveVariantProjectScope('var-1', 'project-1');

    expect(scope).toMatchObject({
      variantId: 'var-1',
      generationId: null,
      projectId: 'project-1',
      status: 'missing_generation',
    });
  });
});
